from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from fx_mechanical_research.phase01_sources import (
    CheckStatus,
    QualificationError,
    Verdict,
    audit_bis_csv,
    derive_phase_verdict,
    derive_verdict,
    load_registry,
    resolve_checks,
    run_phase01,
    sha256_file,
)

REGISTRY_PATH = Path("config/source_registry_v0_1.json")


def _write_bis_fixture(
    path: Path,
    *,
    omitted_currency: str | None = None,
    duplicate_currency: str | None = None,
) -> None:
    registry = load_registry(REGISTRY_PATH)
    fieldnames = [
        "STRUCTURE",
        "FREQ:Frequency",
        "REF_AREA:Reference area",
        "CURRENCY:Currency",
        "COLLECTION:Collection",
        "TIME_PERIOD:Time period or range",
        "OBS_VALUE:Observation Value",
        "AVAILABILITY:Availability",
        "OBS_STATUS:Observation Status",
        "OBS_CONF:Observation confidentiality",
    ]
    rows: list[dict[str, str]] = []
    for currency, area in registry.required_currency_areas.items():
        if currency == omitted_currency:
            continue
        for observed, value in (("2000-01-03", "1.0"), ("2026-08-28", "1.1")):
            rows.append(
                {
                    "STRUCTURE": "dataflow",
                    "FREQ:Frequency": "D: Daily",
                    "REF_AREA:Reference area": f"{area}: Test area",
                    "CURRENCY:Currency": f"{currency}: Test currency",
                    "COLLECTION:Collection": (
                        "A: Average of observations through period"
                    ),
                    "TIME_PERIOD:Time period or range": observed,
                    "OBS_VALUE:Observation Value": value,
                    "AVAILABILITY:Availability": "A: All users",
                    "OBS_STATUS:Observation Status": "A: Normal value",
                    "OBS_CONF:Observation confidentiality": "F: Free",
                }
            )
        if currency == duplicate_currency:
            rows.append(dict(rows[-1]))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_registry_freezes_exactly_nine_non_usd_g10_legs() -> None:
    registry = load_registry(REGISTRY_PATH)

    assert tuple(sorted(registry.required_currency_areas)) == (
        "AUD",
        "CAD",
        "CHF",
        "EUR",
        "GBP",
        "JPY",
        "NOK",
        "NZD",
        "SEK",
    )
    assert set(registry.predictability_gate) < set(registry.executable_gate)
    assert registry.exact_tsmom_previously_computed is False
    assert registry.historical_fx_outcomes_previously_exposed is True
    assert len(registry.prior_evidence_overlap) == 4


def test_executable_verdict_requires_every_registered_component() -> None:
    registry = load_registry(REGISTRY_PATH)
    checks = {name: CheckStatus.PASS for name in registry.executable_gate}

    assert (
        derive_verdict(
            checks,
            predictability_gate=registry.predictability_gate,
            executable_gate=registry.executable_gate,
        )
        is Verdict.EXECUTABLE
    )
    checks["holding_return_or_financing"] = CheckStatus.FAIL
    assert (
        derive_verdict(
            checks,
            predictability_gate=registry.predictability_gate,
            executable_gate=registry.executable_gate,
        )
        is Verdict.PREDICTABILITY
    )


def test_unresolved_predictability_component_requires_review() -> None:
    registry = load_registry(REGISTRY_PATH)
    checks = {name: CheckStatus.PASS for name in registry.executable_gate}
    checks["research_use_terms"] = CheckStatus.REVIEW

    assert (
        derive_verdict(
            checks,
            predictability_gate=registry.predictability_gate,
            executable_gate=registry.executable_gate,
        )
        is Verdict.REVIEW
    )


def test_phase_verdict_uses_strongest_supported_claim() -> None:
    assert (
        derive_phase_verdict((Verdict.FAIL, Verdict.PREDICTABILITY, Verdict.REVIEW))
        is Verdict.PREDICTABILITY
    )
    assert (
        derive_phase_verdict((Verdict.PREDICTABILITY, Verdict.EXECUTABLE))
        is Verdict.EXECUTABLE
    )


def test_bis_audit_passes_complete_fixture(tmp_path: Path) -> None:
    registry = load_registry(REGISTRY_PATH)
    source = tmp_path / "bis.csv"
    _write_bis_fixture(source)

    audit = audit_bis_csv(source, registry)

    assert audit.passed is True
    assert len(audit.coverage) == 9
    assert all(item.valid_observations == 2 for item in audit.coverage)


def test_bis_audit_fails_missing_currency(tmp_path: Path) -> None:
    registry = load_registry(REGISTRY_PATH)
    source = tmp_path / "bis.csv"
    _write_bis_fixture(source, omitted_currency="JPY")

    audit = audit_bis_csv(source, registry)

    assert audit.passed is False
    jpy = next(item for item in audit.coverage if item.currency == "JPY")
    assert jpy.valid_observations == 0


def test_bis_audit_fails_duplicate_timestamp(tmp_path: Path) -> None:
    registry = load_registry(REGISTRY_PATH)
    source = tmp_path / "bis.csv"
    _write_bis_fixture(source, duplicate_currency="JPY")

    audit = audit_bis_csv(source, registry)

    assert audit.passed is False
    jpy = next(item for item in audit.coverage if item.currency == "JPY")
    assert jpy.duplicate_dates == 1


def test_dynamic_bis_checks_fail_closed() -> None:
    registry = load_registry(REGISTRY_PATH)
    candidate = next(
        item
        for item in registry.candidates
        if item.candidate_id == "bis_xru_reference_spot"
    )

    failed = resolve_checks(candidate, bis_coverage_passed=False)

    assert failed["full_g10_coverage"] is CheckStatus.FAIL
    assert failed["historical_marks"] is CheckStatus.FAIL


def test_phase01_emits_no_strategy_outcome(tmp_path: Path) -> None:
    source = tmp_path / "bis.csv"
    _write_bis_fixture(source)
    evidence = tmp_path / "evidence"

    summary = run_phase01(
        registry_path=REGISTRY_PATH,
        bis_csv_path=source,
        evidence_root=evidence,
    )

    assert summary["phase_decision"] == "PASS_PREDICTABILITY_ONLY"
    assert summary["trading_claim_status"] == "NOT_TESTED"
    assert summary["candidate_pnl_computed"] is False
    assert summary["historical_window_untouched"] is False
    serialized = json.dumps(summary).lower()
    assert "sharpe" not in serialized
    assert "mean_return" not in serialized
    assert (evidence / "manifest.json").is_file()
    assert (evidence / "prior_evidence_overlap.json").is_file()
    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        assert sha256_file(evidence / item["path"]) == item["sha256"]


def test_phase01_outputs_are_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "bis.csv"
    _write_bis_fixture(source)
    first = tmp_path / "first"
    second = tmp_path / "second"

    run_phase01(
        registry_path=REGISTRY_PATH,
        bis_csv_path=source,
        evidence_root=first,
    )
    run_phase01(
        registry_path=REGISTRY_PATH,
        bis_csv_path=source,
        evidence_root=second,
    )

    assert (first / "manifest.json").read_bytes() == (
        second / "manifest.json"
    ).read_bytes()


def test_registry_rejects_duplicate_candidate_id(tmp_path: Path) -> None:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    payload["candidates"].append(dict(payload["candidates"][0]))
    bad_registry = tmp_path / "registry.json"
    bad_registry.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(QualificationError, match="duplicate candidate id"):
        load_registry(bad_registry)
