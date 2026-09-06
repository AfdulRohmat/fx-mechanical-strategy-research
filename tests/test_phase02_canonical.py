from __future__ import annotations

import csv
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from fx_mechanical_research.phase01_sources import sha256_file
from fx_mechanical_research.phase02_canonical import (
    CanonicalizationError,
    DependenceRule,
    build_monthly_marks,
    build_monthly_reference_changes,
    load_config,
    parse_bis_reference_marks,
    run_phase02,
    select_dependence_block,
    synchronized_market_changes,
)
from fx_mechanical_research.schemas import ClaimScope

BASE_CONFIG = Path("config/canonical_reference_v0_1.json")


def _month_range(start: date, count: int) -> list[date]:
    result: list[date] = []
    cursor = start
    for _ in range(count):
        result.append(cursor)
        cursor = (
            date(cursor.year + 1, 1, 20)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 20)
        )
    return result


def _write_source(
    path: Path,
    *,
    months: int = 18,
    duplicate: bool = False,
) -> None:
    base = json.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    fields = [
        "FREQ:Frequency",
        "REF_AREA:Reference area",
        "CURRENCY:Currency",
        "TIME_PERIOD:Time period or range",
        "OBS_VALUE:Observation Value",
        "OBS_STATUS:Observation Status",
        "OBS_CONF:Observation confidentiality",
    ]
    rows: list[dict[str, str]] = []
    for currency, area in base["required_currency_areas"].items():
        for index, observed in enumerate(_month_range(date(2000, 1, 20), months)):
            rows.append(
                {
                    "FREQ:Frequency": "D: Daily",
                    "REF_AREA:Reference area": f"{area}: Area",
                    "CURRENCY:Currency": f"{currency}: Currency",
                    "TIME_PERIOD:Time period or range": observed.isoformat(),
                    "OBS_VALUE:Observation Value": str(
                        1.0 + index / 100 + len(currency)
                    ),
                    "OBS_STATUS:Observation Status": "A: Normal value",
                    "OBS_CONF:Observation confidentiality": "F: Free",
                }
            )
    if duplicate:
        rows.append(dict(rows[0]))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_config(path: Path, source: Path, *, months: int = 18) -> None:
    payload = json.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    month_dates = _month_range(date(2000, 1, 20), months)
    payload["source"]["expected_csv_sha256"] = sha256_file(source)
    payload["window"]["start"] = month_dates[0].isoformat()
    payload["window"]["end"] = month_dates[-1].isoformat()
    payload["dependence_rule"]["maximum_lag_months"] = 3
    payload["dependence_rule"]["insignificant_run_length"] = 2
    payload["dependence_rule"]["fallback_block_length_months"] = 3
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_parser_inverts_orientation_and_lags_availability(tmp_path: Path) -> None:
    source = tmp_path / "bis.csv"
    config_path = tmp_path / "config.json"
    _write_source(source)
    _write_config(config_path, source)
    config = load_config(config_path)

    parsed = parse_bis_reference_marks(source, config)
    first = parsed.marks[0]

    assert first.claim_scope is ClaimScope.PREDICTABILITY_ONLY
    assert first.observed_at_utc == datetime(2000, 1, 20, 17, tzinfo=UTC)
    assert first.available_at_utc == datetime(2000, 1, 27, 23, 59, 59, tzinfo=UTC)
    assert first.usd_per_currency == pytest.approx(0.25)


def test_parser_fails_on_source_mutation(tmp_path: Path) -> None:
    source = tmp_path / "bis.csv"
    config_path = tmp_path / "config.json"
    _write_source(source)
    _write_config(config_path, source)
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(CanonicalizationError, match="hash mismatch"):
        parse_bis_reference_marks(source, load_config(config_path))


def test_parser_fails_on_duplicate_observation(tmp_path: Path) -> None:
    source = tmp_path / "bis.csv"
    config_path = tmp_path / "config.json"
    _write_source(source, duplicate=True)
    _write_config(config_path, source)

    with pytest.raises(CanonicalizationError, match="duplicate BIS observation"):
        parse_bis_reference_marks(source, load_config(config_path))


def test_month_end_marks_use_only_available_history(tmp_path: Path) -> None:
    source = tmp_path / "bis.csv"
    config_path = tmp_path / "config.json"
    _write_source(source)
    _write_config(config_path, source)
    config = load_config(config_path)
    parsed = parse_bis_reference_marks(source, config)

    monthly = build_monthly_marks(parsed.marks, config)

    january = next(
        item
        for item in monthly
        if item.currency == "JPY" and item.month == date(2000, 1, 1)
    )
    assert january.observed_date == date(2000, 1, 20)
    assert january.available_at_utc <= january.decision_at_utc


def test_reference_changes_stay_non_executable(tmp_path: Path) -> None:
    source = tmp_path / "bis.csv"
    config_path = tmp_path / "config.json"
    _write_source(source)
    _write_config(config_path, source)
    config = load_config(config_path)
    parsed = parse_bis_reference_marks(source, config)
    monthly = build_monthly_marks(parsed.marks, config)

    changes = build_monthly_reference_changes(monthly, config)
    synchronized = synchronized_market_changes(changes, config)

    assert all(item.claim_scope is ClaimScope.PREDICTABILITY_ONLY for item in changes)
    assert len(synchronized) == 17


def test_dependence_selection_is_mechanical() -> None:
    synchronized = tuple(
        (date(2000 + index // 12, index % 12 + 1, 1), 0.0)
        for index in range(36)
    )
    rule = DependenceRule(
        maximum_lag_months=6,
        insignificant_run_length=3,
        critical_value=1.96,
        fallback_block_length_months=6,
        sensitivity_blocks=(3, 6, 12),
    )

    result = select_dependence_block(synchronized, rule)

    assert result.selected_block_length_months == 1
    assert len(result.autocorrelations) == 6


def test_phase02_run_emits_no_pnl_and_verified_manifest(tmp_path: Path) -> None:
    source = tmp_path / "bis.csv"
    config_path = tmp_path / "config.json"
    _write_source(source)
    _write_config(config_path, source)
    evidence = tmp_path / "evidence"

    summary = run_phase02(
        config_path=config_path,
        bis_csv_path=source,
        interim_root=tmp_path / "interim",
        evidence_root=evidence,
    )

    assert summary["claim_scope"] == "PREDICTABILITY_ONLY"
    assert summary["trading_claim_status"] == "NOT_TESTED"
    assert summary["candidate_signal_evaluated"] is False
    assert summary["candidate_pnl_computed"] is False
    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        assert sha256_file(evidence / item["path"]) == item["sha256"]
