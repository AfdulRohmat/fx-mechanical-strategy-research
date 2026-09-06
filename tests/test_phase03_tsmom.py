from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from fx_mechanical_research.phase01_sources import sha256_file
from fx_mechanical_research.phase03_tsmom import (
    ExecutableMonthlyInput,
    StrategyError,
    StrategyId,
    aggregate_equal_weight,
    audit_trial_registry,
    build_strategy_rows,
    load_strategy_config,
    run_phase03_gate,
)
from fx_mechanical_research.schemas import ClaimScope

CONFIG_PATH = Path("config/tsmom_v0_1.json")
TRIAL_REGISTRY = Path("config/trial_registry.jsonl")


def _months(count: int) -> list[date]:
    result: list[date] = []
    cursor = date(2000, 1, 1)
    for _ in range(count):
        result.append(cursor)
        cursor = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
    return result


def _panel(
    returns: list[float], *, one_way_cost: float = 0.001
) -> tuple[ExecutableMonthlyInput, ...]:
    config = load_strategy_config(CONFIG_PATH)
    rows = [
        ExecutableMonthlyInput(
            currency=currency,
            month=month,
            total_return=returns[index],
            one_way_cost_return=one_way_cost,
            claim_scope=ClaimScope.EXECUTABLE_TOTAL_RETURN,
        )
        for currency in config.universe
        for index, month in enumerate(_months(len(returns)))
    ]
    return tuple(rows)


def test_config_is_exact_frozen_primary() -> None:
    config = load_strategy_config(CONFIG_PATH)

    assert config.lookback_months == 12
    assert config.holding_months == 1
    assert config.block_length_months == 10
    assert config.bootstrap_resamples == 10_000


def test_price_only_input_is_rejected() -> None:
    with pytest.raises(StrategyError, match="must be executable"):
        ExecutableMonthlyInput(
            currency="JPY",
            month=date(2024, 1, 1),
            total_return=0.01,
            one_way_cost_return=0.001,
            claim_scope=ClaimScope.PREDICTABILITY_ONLY,
        )


def test_primary_signal_uses_prior_twelve_months_and_next_month_return() -> None:
    config = load_strategy_config(CONFIG_PATH)
    observations = _panel([0.01] * 12 + [-0.02])

    rows = build_strategy_rows(observations, config, StrategyId.PRIMARY)
    jpy = next(item for item in rows if item.currency == "JPY")

    assert jpy.holding_month == date(2001, 1, 1)
    assert jpy.input_window_start == date(2000, 1, 1)
    assert jpy.input_window_end == date(2000, 12, 1)
    assert jpy.signal == 1
    assert jpy.turnover_units == 1
    assert jpy.gross_strategy_return == pytest.approx(-0.02)
    assert jpy.net_strategy_return == pytest.approx(-0.021)


def test_signal_flip_charges_two_units_of_turnover() -> None:
    config = load_strategy_config(CONFIG_PATH)
    observations = _panel([0.01] * 12 + [-0.5, 0.02])

    rows = build_strategy_rows(observations, config, StrategyId.PRIMARY)
    jpy = [item for item in rows if item.currency == "JPY"]

    assert [item.signal for item in jpy] == [1, -1]
    assert [item.turnover_units for item in jpy] == [1, 2]
    assert jpy[1].trading_cost_return == pytest.approx(0.002)
    assert jpy[1].net_strategy_return == pytest.approx(-0.022)


def test_expanding_mean_control_is_past_only() -> None:
    config = load_strategy_config(CONFIG_PATH)
    observations = _panel([0.01] * 12 + [-0.9])

    rows = build_strategy_rows(
        observations,
        config,
        StrategyId.B1_EXPANDING_MEAN,
    )

    assert all(row.signal == 1 for row in rows)


def test_equal_weight_portfolio_preserves_month_cluster() -> None:
    config = load_strategy_config(CONFIG_PATH)
    observations = _panel([0.01] * 12 + [0.02])
    rows = build_strategy_rows(observations, config, StrategyId.PRIMARY)

    portfolio = aggregate_equal_weight(rows, config)

    assert len(portfolio) == 1
    assert portfolio[0].eligible_currencies == 9
    assert portfolio[0].gross_return == pytest.approx(0.02)
    assert portfolio[0].net_return == pytest.approx(0.019)


def test_panel_with_missing_currency_month_fails_closed() -> None:
    config = load_strategy_config(CONFIG_PATH)
    observations = tuple(
        row
        for row in _panel([0.01] * 14)
        if not (row.currency == "JPY" and row.month == date(2000, 6, 1))
    )

    with pytest.raises(StrategyError, match="non-consecutive months"):
        build_strategy_rows(observations, config, StrategyId.PRIMARY)


def test_trial_registry_rejects_contaminated_outcome_flag(tmp_path: Path) -> None:
    config = load_strategy_config(CONFIG_PATH)
    row = json.loads(TRIAL_REGISTRY.read_text(encoding="utf-8"))
    row["outcome_inspected"] = True
    registry = tmp_path / "registry.jsonl"
    registry.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(StrategyError, match="contaminated"):
        audit_trial_registry(registry, config)


def test_real_gate_stops_before_outcome_file(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    outcome = tmp_path / "must_not_be_read.csv"
    outcome.write_bytes(b"\xff\xfe poison")

    summary = run_phase03_gate(
        config_path=CONFIG_PATH,
        trial_registry_path=TRIAL_REGISTRY,
        phase01_decision_path=Path("evidence/phase01/decision.json"),
        phase02_summary_path=Path("evidence/phase02/summary.json"),
        phase02_schema_path=Path("evidence/phase02/schema_coverage.json"),
        evidence_root=evidence,
        outcome_path=outcome,
    )

    assert summary["decision"] == "NOT_TESTED"
    assert summary["outcome_file_read"] is False
    assert summary["candidate_signal_evaluated"] is False
    gate = json.loads((evidence / "eligibility_gate.json").read_text(encoding="utf-8"))
    assert len(gate["blockers"]) == 3
    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        assert sha256_file(evidence / item["path"]) == item["sha256"]
