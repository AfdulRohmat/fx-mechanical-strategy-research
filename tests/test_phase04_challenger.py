from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from fx_mechanical_research.phase01_sources import sha256_file
from fx_mechanical_research.phase03_tsmom import ExecutableMonthlyInput
from fx_mechanical_research.phase04_challenger import (
    ChallengerError,
    aggregate_challenger,
    audit_challenger_trial,
    build_challenger_rows,
    load_challenger_config,
    run_phase04_gate,
)
from fx_mechanical_research.schemas import ClaimScope

CONFIG_PATH = Path("config/cross_sectional_challenger_v0_1.json")
TRIAL_REGISTRY = Path("config/trial_registry.jsonl")


def _months(count: int) -> list[date]:
    months: list[date] = []
    cursor = date(2000, 1, 1)
    for _ in range(count):
        months.append(cursor)
        cursor = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
    return months


def _ranked_panel(
    *,
    holding_return: float = 0.01,
    all_formation_equal: bool = False,
    months: int = 13,
) -> tuple[ExecutableMonthlyInput, ...]:
    config = load_challenger_config(CONFIG_PATH, root=Path.cwd())
    dates = _months(months)
    output: list[ExecutableMonthlyInput] = []
    for currency_index, currency in enumerate(config.universe):
        formation_return = (
            0.01 if all_formation_equal else 0.001 * (currency_index + 1)
        )
        for index, month in enumerate(dates):
            total_return = formation_return if index < 12 else holding_return
            output.append(
                ExecutableMonthlyInput(
                    currency=currency,
                    month=month,
                    total_return=total_return,
                    one_way_cost_return=0.003,
                    claim_scope=ClaimScope.EXECUTABLE_TOTAL_RETURN,
                )
            )
    return tuple(output)


def test_config_is_hash_anchored_and_discloses_adaptation() -> None:
    config = load_challenger_config(CONFIG_PATH, root=Path.cwd())

    assert config.implementation_type == "PAPER_ANCHORED_G10_ADAPTATION"
    assert sha256_file(config.paper_path) == config.expected_paper_sha256
    assert config.formation_months == 12
    assert config.holding_months == 1
    assert (config.long_count, config.short_count, config.neutral_count) == (3, 3, 3)


def test_challenger_ranks_prior_window_and_builds_three_by_three() -> None:
    config = load_challenger_config(CONFIG_PATH, root=Path.cwd())

    rows = build_challenger_rows(_ranked_panel(), config)
    portfolio = aggregate_challenger(rows, config)

    assert len(portfolio) == 1
    assert portfolio[0].long_currencies == ("NOK", "NZD", "SEK")
    assert portfolio[0].short_currencies == ("AUD", "CAD", "CHF")
    assert portfolio[0].neutral_currencies == ("EUR", "GBP", "JPY")
    assert portfolio[0].long_weight == pytest.approx(1.0)
    assert portfolio[0].short_weight == pytest.approx(-1.0)
    assert portfolio[0].gross_notional == pytest.approx(2.0)


def test_initial_rebalance_costs_full_long_and_short_notional() -> None:
    config = load_challenger_config(CONFIG_PATH, root=Path.cwd())
    rows = build_challenger_rows(_ranked_panel(), config)

    portfolio = aggregate_challenger(rows, config)[0]

    assert portfolio.gross_return == pytest.approx(0.0)
    assert portfolio.trading_cost_return == pytest.approx(0.006)
    assert portfolio.net_return == pytest.approx(-0.006)


def test_holding_month_return_does_not_change_formation_rank() -> None:
    config = load_challenger_config(CONFIG_PATH, root=Path.cwd())
    panel = list(_ranked_panel())
    panel = [
        ExecutableMonthlyInput(
            currency=row.currency,
            month=row.month,
            total_return=(
                0.99
                if row.currency == "AUD" and row.month == date(2001, 1, 1)
                else row.total_return
            ),
            one_way_cost_return=row.one_way_cost_return,
            claim_scope=row.claim_scope,
        )
        for row in panel
    ]

    rows = build_challenger_rows(tuple(panel), config)
    aud = next(row for row in rows if row.currency == "AUD")

    assert aud.position == "SHORT"
    assert aud.formation_end == date(2000, 12, 1)


def test_ties_use_currency_code_deterministically() -> None:
    config = load_challenger_config(CONFIG_PATH, root=Path.cwd())
    rows = build_challenger_rows(
        _ranked_panel(all_formation_equal=True),
        config,
    )

    portfolio = aggregate_challenger(rows, config)[0]

    assert portfolio.short_currencies == ("AUD", "CAD", "CHF")
    assert portfolio.long_currencies == ("NOK", "NZD", "SEK")


def test_second_unchanged_rebalance_has_zero_turnover() -> None:
    config = load_challenger_config(CONFIG_PATH, root=Path.cwd())
    rows = build_challenger_rows(_ranked_panel(months=14), config)
    portfolio = aggregate_challenger(rows, config)

    assert len(portfolio) == 2
    assert portfolio[1].trading_cost_return == pytest.approx(0.0)


def test_trial_registry_contains_one_sealed_challenger() -> None:
    config = load_challenger_config(CONFIG_PATH, root=Path.cwd())

    audit = audit_challenger_trial(TRIAL_REGISTRY, config)

    assert audit["registered_challenger_family_size"] == 1
    assert audit["challenger_outcome_inspected"] is False


def test_challenger_gate_stops_before_poison_outcome(tmp_path: Path) -> None:
    outcome = tmp_path / "must_not_be_read.csv"
    outcome.write_bytes(b"\xff\xfe poison")
    evidence = tmp_path / "evidence"

    summary = run_phase04_gate(
        root=Path.cwd(),
        config_path=CONFIG_PATH,
        trial_registry_path=TRIAL_REGISTRY,
        phase01_path=Path("evidence/phase01/decision.json"),
        phase02_summary_path=Path("evidence/phase02/summary.json"),
        phase02_schema_path=Path("evidence/phase02/schema_coverage.json"),
        phase03_summary_path=Path("evidence/phase03/summary.json"),
        outcome_path=outcome,
        evidence_root=evidence,
    )

    assert summary["decision"] == "NOT_TESTED"
    assert summary["outcome_file_read"] is False
    assert summary["challenger_signal_evaluated"] is False
    assert len(summary["blockers"]) == 4
    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        assert sha256_file(evidence / item["path"]) == item["sha256"]


def test_mutated_paper_hash_fails_before_engine(tmp_path: Path) -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["paper"]["expected_sha256"] = "0" * 64
    mutated = tmp_path / "challenger.json"
    mutated.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ChallengerError, match="paper SHA-256 mismatch"):
        load_challenger_config(mutated, root=Path.cwd())
