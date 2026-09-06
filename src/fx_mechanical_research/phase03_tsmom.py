"""Phase 03 frozen TSMOM kernel and real-data eligibility gate."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import cast

from .phase01_sources import sha256_file
from .schemas import ClaimScope


class StrategyError(RuntimeError):
    """The frozen strategy or its input violates a mandatory invariant."""


class StrategyId(StrEnum):
    PRIMARY = "TSMOM_V1_PRIMARY"
    B0_CASH = "B0_CASH"
    B1_EXPANDING_MEAN = "B1_EXPANDING_MEAN_SIGN"
    B2_ALWAYS_LONG = "B2_ALWAYS_LONG"
    B2_ALWAYS_SHORT = "B2_ALWAYS_SHORT"


@dataclass(frozen=True)
class StrategyConfig:
    config_version: str
    contract_version: str
    strategy_id: str
    generated_at_utc: str
    universe: tuple[str, ...]
    lookback_months: int
    holding_months: int
    block_length_months: int
    sensitivity_blocks: tuple[int, ...]
    bootstrap_resamples: int
    bootstrap_seed: int
    required_phase01_decision: str
    required_phase02_claim_scope: str
    required_monthly_schema_status: str


@dataclass(frozen=True)
class ExecutableMonthlyInput:
    """Synthetic-testable input contract for a future executable source."""

    currency: str
    month: date
    total_return: float
    one_way_cost_return: float
    claim_scope: ClaimScope

    def __post_init__(self) -> None:
        if len(self.currency) != 3 or self.month.day != 1:
            raise StrategyError("invalid currency-month key")
        if not math.isfinite(self.total_return) or self.total_return <= -1:
            raise StrategyError("total return must be finite and greater than -1")
        if (
            not math.isfinite(self.one_way_cost_return)
            or self.one_way_cost_return < 0
        ):
            raise StrategyError("one-way cost must be finite and non-negative")
        if self.claim_scope is not ClaimScope.EXECUTABLE_TOTAL_RETURN:
            raise StrategyError("TSMOM input must be executable total return")


@dataclass(frozen=True)
class StrategyRow:
    strategy_id: StrategyId
    currency: str
    holding_month: date
    input_window_start: date
    input_window_end: date
    trailing_metric: float
    signal: int
    previous_signal: int
    turnover_units: int
    underlying_total_return: float
    trading_cost_return: float
    gross_strategy_return: float
    net_strategy_return: float


@dataclass(frozen=True)
class PortfolioRow:
    strategy_id: StrategyId
    month: date
    eligible_currencies: int
    gross_return: float
    net_return: float
    turnover_units: int
    trading_cost_return: float


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    blockers: tuple[str, ...]
    phase01_decision: str
    phase02_claim_scope: str
    monthly_total_return_status: str


def _dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise StrategyError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise StrategyError(f"{label} must be an array")
    return cast(list[object], value)


def _str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise StrategyError(f"{label} must be a non-empty string")
    return value


def _int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise StrategyError(f"{label} must be an integer")
    return value


def load_strategy_config(path: Path) -> StrategyConfig:
    """Load the exact Phase 00 TSMOM contract transcription."""

    raw = _dict(json.loads(path.read_text(encoding="utf-8")), "strategy config")
    primary = _dict(raw.get("primary"), "primary")
    costs = _dict(raw.get("costs"), "costs")
    controls = _dict(raw.get("controls"), "controls")
    inference = _dict(raw.get("inference"), "inference")
    eligibility = _dict(raw.get("eligibility"), "eligibility")
    if _str(primary.get("signal_rule"), "signal rule") != (
        "SIGN_COMPOUNDED_TRAILING_TOTAL_RETURN"
    ):
        raise StrategyError("primary signal rule changed")
    if _int(primary.get("zero_or_missing_signal"), "zero signal") != 0:
        raise StrategyError("zero return must produce a zero signal")
    if _str(primary.get("weighting"), "weighting") != (
        "EQUAL_WEIGHT_ELIGIBLE_CURRENCIES"
    ):
        raise StrategyError("primary weighting changed")
    if _str(primary.get("exposure"), "exposure") != "UNSCALED":
        raise StrategyError("primary exposure changed")
    if _str(costs.get("turnover_units"), "turnover") != (
        "ABS_CURRENT_SIGNAL_MINUS_PREVIOUS_SIGNAL"
    ):
        raise StrategyError("turnover rule changed")
    if _str(costs.get("missing_cost"), "missing cost") != "FAIL":
        raise StrategyError("missing costs must fail")
    required_controls = {
        "B0_CASH",
        "B1_EXPANDING_MEAN_SIGN",
        "B2_ALWAYS_LONG",
        "B2_ALWAYS_SHORT",
        "B3_VOLATILITY_SCALED",
        "B4_PLACEBO",
    }
    if set(controls) != required_controls:
        raise StrategyError("registered control family changed")
    universe = tuple(
        _str(item, "currency")
        for item in _list(raw.get("universe"), "universe")
    )
    if len(universe) != 9 or len(set(universe)) != 9:
        raise StrategyError("strategy requires nine unique G10 currencies")
    sensitivities = tuple(
        _int(item, "sensitivity block")
        for item in _list(
            inference.get("sensitivity_block_lengths_months"),
            "sensitivity blocks",
        )
    )
    result = StrategyConfig(
        config_version=_str(raw.get("config_version"), "config version"),
        contract_version=_str(raw.get("contract_version"), "contract version"),
        strategy_id=_str(raw.get("strategy_id"), "strategy id"),
        generated_at_utc=_str(raw.get("generated_at_utc"), "generated_at_utc"),
        universe=universe,
        lookback_months=_int(primary.get("lookback_months"), "lookback"),
        holding_months=_int(primary.get("holding_months"), "holding"),
        block_length_months=_int(
            inference.get("moving_block_length_months"), "block length"
        ),
        sensitivity_blocks=sensitivities,
        bootstrap_resamples=_int(
            inference.get("bootstrap_resamples"), "bootstrap resamples"
        ),
        bootstrap_seed=_int(inference.get("seed"), "bootstrap seed"),
        required_phase01_decision=_str(
            eligibility.get("required_phase01_decision"), "phase01 requirement"
        ),
        required_phase02_claim_scope=_str(
            eligibility.get("required_phase02_claim_scope"), "phase02 requirement"
        ),
        required_monthly_schema_status=_str(
            eligibility.get("required_monthly_schema_status"), "schema requirement"
        ),
    )
    if result.lookback_months != 12 or result.holding_months != 1:
        raise StrategyError("TSMOM v1 formation or holding period changed")
    if result.block_length_months != 10:
        raise StrategyError("Phase 02 selected block length changed")
    if result.bootstrap_resamples < 10_000:
        raise StrategyError("at least 10,000 bootstrap resamples are required")
    return result


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _validate_panel(
    observations: tuple[ExecutableMonthlyInput, ...], config: StrategyConfig
) -> dict[str, list[ExecutableMonthlyInput]]:
    by_currency: dict[str, list[ExecutableMonthlyInput]] = {
        currency: [] for currency in config.universe
    }
    seen: set[tuple[str, date]] = set()
    for item in observations:
        if item.currency not in by_currency:
            raise StrategyError(f"unregistered currency: {item.currency}")
        key = (item.currency, item.month)
        if key in seen:
            raise StrategyError(f"duplicate currency-month: {key}")
        seen.add(key)
        by_currency[item.currency].append(item)
    reference_months: tuple[date, ...] | None = None
    for currency, rows in by_currency.items():
        rows.sort(key=lambda item: item.month)
        if len(rows) <= config.lookback_months:
            raise StrategyError(f"insufficient history for {currency}")
        months = tuple(item.month for item in rows)
        if any(
            current != _next_month(previous)
            for previous, current in pairwise(months)
        ):
            raise StrategyError(f"non-consecutive months for {currency}")
        if reference_months is None:
            reference_months = months
        elif months != reference_months:
            raise StrategyError("currency panel is not synchronized")
    return by_currency


def build_strategy_rows(
    observations: tuple[ExecutableMonthlyInput, ...],
    config: StrategyConfig,
    strategy_id: StrategyId,
) -> tuple[StrategyRow, ...]:
    """Evaluate a frozen rule on executable fixtures with causal alignment."""

    by_currency = _validate_panel(observations, config)
    output: list[StrategyRow] = []
    for currency in config.universe:
        rows = by_currency[currency]
        previous_signal = 0
        for index in range(config.lookback_months, len(rows)):
            history = rows[index - config.lookback_months : index]
            current = rows[index]
            if strategy_id is StrategyId.PRIMARY:
                trailing = math.prod(1 + item.total_return for item in history) - 1
                signal = _sign(trailing)
            elif strategy_id is StrategyId.B1_EXPANDING_MEAN:
                expanding = rows[:index]
                trailing = sum(item.total_return for item in expanding) / len(expanding)
                signal = _sign(trailing)
            elif strategy_id is StrategyId.B2_ALWAYS_LONG:
                trailing = 1.0
                signal = 1
            elif strategy_id is StrategyId.B2_ALWAYS_SHORT:
                trailing = -1.0
                signal = -1
            elif strategy_id is StrategyId.B0_CASH:
                trailing = 0.0
                signal = 0
            else:
                raise StrategyError(f"unsupported strategy: {strategy_id}")
            turnover = abs(signal - previous_signal)
            cost = turnover * current.one_way_cost_return
            gross = signal * current.total_return
            net = gross - cost
            output.append(
                StrategyRow(
                    strategy_id=strategy_id,
                    currency=currency,
                    holding_month=current.month,
                    input_window_start=history[0].month,
                    input_window_end=history[-1].month,
                    trailing_metric=trailing,
                    signal=signal,
                    previous_signal=previous_signal,
                    turnover_units=turnover,
                    underlying_total_return=current.total_return,
                    trading_cost_return=cost,
                    gross_strategy_return=gross,
                    net_strategy_return=net,
                )
            )
            previous_signal = signal
    output.sort(key=lambda item: (item.holding_month, item.currency))
    return tuple(output)


def aggregate_equal_weight(
    rows: tuple[StrategyRow, ...], config: StrategyConfig
) -> tuple[PortfolioRow, ...]:
    """Preserve each synchronized month as the statistical dependence unit."""

    grouped: dict[date, list[StrategyRow]] = {}
    for row in rows:
        grouped.setdefault(row.holding_month, []).append(row)
    output: list[PortfolioRow] = []
    required = set(config.universe)
    for month, cluster in sorted(grouped.items()):
        if {item.currency for item in cluster} != required:
            raise StrategyError(f"incomplete portfolio month: {month}")
        strategy_ids = {item.strategy_id for item in cluster}
        if len(strategy_ids) != 1:
            raise StrategyError("portfolio cluster mixes strategy ids")
        count = len(cluster)
        output.append(
            PortfolioRow(
                strategy_id=cluster[0].strategy_id,
                month=month,
                eligible_currencies=count,
                gross_return=sum(item.gross_strategy_return for item in cluster)
                / count,
                net_return=sum(item.net_strategy_return for item in cluster) / count,
                turnover_units=sum(item.turnover_units for item in cluster),
                trading_cost_return=sum(item.trading_cost_return for item in cluster)
                / count,
            )
        )
    return tuple(output)


def evaluate_real_data_eligibility(
    *,
    phase01_decision_path: Path,
    phase02_summary_path: Path,
    phase02_schema_path: Path,
    config: StrategyConfig,
) -> EligibilityResult:
    """Inspect only upstream gates; never open an outcome file on failure."""

    phase01 = _dict(
        json.loads(phase01_decision_path.read_text(encoding="utf-8")),
        "Phase 01 decision",
    )
    phase02 = _dict(
        json.loads(phase02_summary_path.read_text(encoding="utf-8")),
        "Phase 02 summary",
    )
    schema = _dict(
        json.loads(phase02_schema_path.read_text(encoding="utf-8")),
        "Phase 02 schema",
    )
    phase01_decision = _str(phase01.get("phase_decision"), "phase01 decision")
    phase02_scope = _str(phase02.get("claim_scope"), "phase02 claim scope")
    total_return_status = _str(
        schema.get("monthly_total_return"), "monthly total return status"
    )
    blockers: list[str] = []
    if phase01_decision != config.required_phase01_decision:
        blockers.append(
            "PHASE01_EXECUTABLE_TOTAL_RETURN_SOURCE_NOT_QUALIFIED"
        )
    if phase02_scope != config.required_phase02_claim_scope:
        blockers.append("PHASE02_CLAIM_SCOPE_IS_NOT_EXECUTABLE")
    if total_return_status != config.required_monthly_schema_status:
        blockers.append("PHASE02_MONTHLY_TOTAL_RETURN_NOT_BUILT")
    return EligibilityResult(
        eligible=not blockers,
        blockers=tuple(blockers),
        phase01_decision=phase01_decision,
        phase02_claim_scope=phase02_scope,
        monthly_total_return_status=total_return_status,
    )


def audit_trial_registry(path: Path, config: StrategyConfig) -> dict[str, object]:
    """Validate the append-only, pre-outcome trial registry."""

    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = _dict(json.loads(line), f"trial registry line {line_number}")
            rows.append(row)
    if not rows:
        raise StrategyError("trial registry is empty")
    sequences = [_int(row.get("sequence"), "trial sequence") for row in rows]
    if sequences != list(range(1, len(rows) + 1)):
        raise StrategyError("trial registry sequence is not append-only")
    trial_ids = [_str(row.get("trial_id"), "trial id") for row in rows]
    if len(trial_ids) != len(set(trial_ids)):
        raise StrategyError("duplicate trial id")
    primary = next(
        (row for row in rows if row.get("trial_id") == config.strategy_id),
        None,
    )
    if primary is None:
        raise StrategyError("primary trial is not registered")
    if primary.get("outcome_inspected") is not False:
        raise StrategyError("primary trial outcome flag is contaminated")
    if primary.get("status") != "BLOCKED_BEFORE_OUTCOME":
        raise StrategyError("primary trial status is inconsistent with source gate")
    return {
        "registry_entries": len(rows),
        "unique_trial_ids": len(set(trial_ids)),
        "primary_trial_id": config.strategy_id,
        "primary_status": primary["status"],
        "primary_outcome_inspected": primary["outcome_inspected"],
        "registry_sha256": sha256_file(path),
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_manifest(root: Path, generated_at: str) -> None:
    rows = [
        {
            "path": path.name,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.iterdir())
        if path.is_file() and path.name != "manifest.json"
    ]
    _write_json(
        root / "manifest.json",
        {
            "phase": "03-tsmom-replication",
            "generated_at_utc": generated_at,
            "files": rows,
        },
    )


def run_phase03_gate(
    *,
    config_path: Path,
    trial_registry_path: Path,
    phase01_decision_path: Path,
    phase02_summary_path: Path,
    phase02_schema_path: Path,
    evidence_root: Path,
    outcome_path: Path,
) -> dict[str, object]:
    """Emit NOT_TESTED before accessing price-only outcome data."""

    config = load_strategy_config(config_path)
    registry_audit = audit_trial_registry(trial_registry_path, config)
    eligibility = evaluate_real_data_eligibility(
        phase01_decision_path=phase01_decision_path,
        phase02_summary_path=phase02_summary_path,
        phase02_schema_path=phase02_schema_path,
        config=config,
    )
    if eligibility.eligible:
        raise StrategyError(
            "eligible executable input requires a separately reviewed data adapter"
        )
    summary: dict[str, object] = {
        "phase": "03-tsmom-replication",
        "phase_status": "COMPLETE_BLOCKED_BEFORE_OUTCOME",
        "generated_at_utc": config.generated_at_utc,
        "decision": "NOT_TESTED",
        "eligibility": False,
        "blockers": list(eligibility.blockers),
        "outcome_path_declared": outcome_path.as_posix(),
        "outcome_file_read": False,
        "candidate_signal_evaluated": False,
        "candidate_pnl_computed": False,
        "hypotheses": {
            f"TSMOM_H{number}_{name}": "NOT_TESTED"
            for number, name in (
                (1, "NET_PORTFOLIO"),
                (2, "INCREMENTAL_SIGNAL"),
                (3, "MULTIPLE_TESTING"),
                (4, "BREADTH_AND_TIME_STABILITY"),
                (5, "COST_CAPACITY"),
            )
        },
    }
    gate_payload = {
        "eligible": eligibility.eligible,
        "phase01_decision": eligibility.phase01_decision,
        "required_phase01_decision": config.required_phase01_decision,
        "phase02_claim_scope": eligibility.phase02_claim_scope,
        "required_phase02_claim_scope": config.required_phase02_claim_scope,
        "monthly_total_return_status": eligibility.monthly_total_return_status,
        "required_monthly_total_return_status": (
            config.required_monthly_schema_status
        ),
        "blockers": list(eligibility.blockers),
        "checked_before_outcome_path": True,
        "outcome_file_read": False,
    }
    report = f"""# Phase 03 - Frozen TSMOM replication

Decision: `NOT_TESTED`

Status: `COMPLETE_BLOCKED_BEFORE_OUTCOME`

The Phase 03 engine transcribes the frozen 12-month sign rule, one-month holding
alignment, equal-weight aggregation, turnover-cost identity, and B0-B2 matched
controls. Synthetic executable fixtures verify those invariants.

The real-data gate failed before `{outcome_path.as_posix()}` was opened:

{chr(10).join(f'- `{blocker}`' for blocker in eligibility.blockers)}

Phase 01 qualified only reference-rate predictability. Phase 02 consequently
built zero monthly total-return rows. Running the actual TSMOM signal would
silently turn price changes into PnL, so no candidate signal, strategy return,
control outcome, bootstrap interval, or multiple-testing statistic was computed.

All five registered hypotheses remain `NOT_TESTED`. This is not a negative
alpha result. It is enforcement of the executable-data boundary.
"""
    evidence_root.mkdir(parents=True, exist_ok=True)
    _write_json(evidence_root / "summary.json", summary)
    _write_json(evidence_root / "eligibility_gate.json", gate_payload)
    _write_json(evidence_root / "trial_registry_audit.json", registry_audit)
    _write_json(
        evidence_root / "input_manifest.json",
        {
            "strategy_config_sha256": sha256_file(config_path),
            "trial_registry_sha256": sha256_file(trial_registry_path),
            "phase01_decision_sha256": sha256_file(phase01_decision_path),
            "phase02_summary_sha256": sha256_file(phase02_summary_path),
            "phase02_schema_sha256": sha256_file(phase02_schema_path),
            "outcome_file_hashed": False,
            "outcome_file_read": False,
        },
    )
    (evidence_root / "REPORT.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )
    _write_manifest(evidence_root, config.generated_at_utc)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/tsmom_v0_1.json"))
    parser.add_argument(
        "--trial-registry",
        type=Path,
        default=Path("config/trial_registry.jsonl"),
    )
    parser.add_argument(
        "--phase01-decision",
        type=Path,
        default=Path("evidence/phase01/decision.json"),
    )
    parser.add_argument(
        "--phase02-summary",
        type=Path,
        default=Path("evidence/phase02/summary.json"),
    )
    parser.add_argument(
        "--phase02-schema",
        type=Path,
        default=Path("evidence/phase02/schema_coverage.json"),
    )
    parser.add_argument(
        "--outcome-path",
        type=Path,
        default=Path("data/interim/phase02/monthly_reference_changes.csv"),
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("evidence/phase03"),
    )
    args = parser.parse_args()
    result = run_phase03_gate(
        config_path=args.config,
        trial_registry_path=args.trial_registry,
        phase01_decision_path=args.phase01_decision,
        phase02_summary_path=args.phase02_summary,
        phase02_schema_path=args.phase02_schema,
        evidence_root=args.evidence_root,
        outcome_path=args.outcome_path,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
