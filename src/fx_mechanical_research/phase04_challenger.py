"""Phase 04 paper-anchored cross-sectional challenger and eligibility gate."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from pathlib import Path
from typing import cast

from .phase01_sources import sha256_file
from .phase03_tsmom import ExecutableMonthlyInput


class ChallengerError(RuntimeError):
    """The challenger configuration or input violates its frozen contract."""


@dataclass(frozen=True)
class ChallengerConfig:
    config_version: str
    contract_version: str
    challenger_id: str
    generated_at_utc: str
    implementation_type: str
    paper_path: Path
    expected_paper_sha256: str
    universe: tuple[str, ...]
    formation_months: int
    holding_months: int
    long_count: int
    short_count: int
    neutral_count: int
    long_leg_weight: float
    short_leg_weight: float
    family_size: int
    required_phase01_decision: str
    required_phase02_claim_scope: str
    required_monthly_schema_status: str
    required_phase03_status: str


@dataclass(frozen=True)
class ChallengerRow:
    challenger_id: str
    month: date
    currency: str
    formation_start: date
    formation_end: date
    formation_return: float
    rank: int
    position: str
    weight: float
    previous_weight: float
    turnover_weight: float
    underlying_total_return: float
    trading_cost_return: float
    gross_contribution: float
    net_contribution: float


@dataclass(frozen=True)
class ChallengerPortfolioRow:
    challenger_id: str
    month: date
    long_currencies: tuple[str, ...]
    short_currencies: tuple[str, ...]
    neutral_currencies: tuple[str, ...]
    long_weight: float
    short_weight: float
    gross_notional: float
    gross_return: float
    trading_cost_return: float
    net_return: float


@dataclass(frozen=True)
class ChallengerEligibility:
    eligible: bool
    blockers: tuple[str, ...]
    actual: dict[str, str]


def _dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ChallengerError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ChallengerError(f"{label} must be an array")
    return cast(list[object], value)


def _str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ChallengerError(f"{label} must be a non-empty string")
    return value


def _int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ChallengerError(f"{label} must be an integer")
    return value


def _float(value: object, label: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ChallengerError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ChallengerError(f"{label} must be finite")
    return result


def load_challenger_config(path: Path, *, root: Path) -> ChallengerConfig:
    """Load the single frozen paper-anchored challenger."""

    raw = _dict(json.loads(path.read_text(encoding="utf-8")), "challenger config")
    paper = _dict(raw.get("paper"), "paper")
    eligibility = _dict(raw.get("eligibility"), "eligibility")
    universe = tuple(
        _str(item, "currency")
        for item in _list(raw.get("universe"), "universe")
    )
    result = ChallengerConfig(
        config_version=_str(raw.get("config_version"), "config version"),
        contract_version=_str(raw.get("contract_version"), "contract version"),
        challenger_id=_str(raw.get("challenger_id"), "challenger id"),
        generated_at_utc=_str(raw.get("generated_at_utc"), "generated_at_utc"),
        implementation_type=_str(
            raw.get("implementation_type"), "implementation type"
        ),
        paper_path=root / _str(paper.get("local_path"), "paper path"),
        expected_paper_sha256=_str(
            paper.get("expected_sha256"), "paper SHA-256"
        ),
        universe=universe,
        formation_months=_int(raw.get("formation_months"), "formation months"),
        holding_months=_int(raw.get("holding_months"), "holding months"),
        long_count=_int(raw.get("long_count"), "long count"),
        short_count=_int(raw.get("short_count"), "short count"),
        neutral_count=_int(raw.get("neutral_count"), "neutral count"),
        long_leg_weight=_float(raw.get("long_leg_weight"), "long leg weight"),
        short_leg_weight=_float(raw.get("short_leg_weight"), "short leg weight"),
        family_size=_int(raw.get("registered_family_size"), "family size"),
        required_phase01_decision=_str(
            eligibility.get("required_phase01_decision"), "Phase 01 requirement"
        ),
        required_phase02_claim_scope=_str(
            eligibility.get("required_phase02_claim_scope"), "Phase 02 requirement"
        ),
        required_monthly_schema_status=_str(
            eligibility.get("required_monthly_schema_status"), "schema requirement"
        ),
        required_phase03_status=_str(
            eligibility.get("required_phase03_status"), "Phase 03 requirement"
        ),
    )
    if result.implementation_type != "PAPER_ANCHORED_G10_ADAPTATION":
        raise ChallengerError("challenger must disclose its G10 adaptation")
    if len(universe) != 9 or len(set(universe)) != 9:
        raise ChallengerError("challenger requires nine unique G10 currencies")
    if (
        result.formation_months != 12
        or result.holding_months != 1
        or result.long_count != 3
        or result.short_count != 3
        or result.neutral_count != 3
    ):
        raise ChallengerError("challenger formation or portfolio counts changed")
    if result.long_count + result.short_count + result.neutral_count != len(universe):
        raise ChallengerError("challenger buckets do not cover the universe")
    if result.long_leg_weight != 1 or result.short_leg_weight != -1:
        raise ChallengerError("challenger must be dollar-neutral High minus Low")
    if result.family_size != 1:
        raise ChallengerError("only one challenger is registered")
    if (
        raw.get("can_confirm_tsmom") is not False
        or raw.get("can_rescue_tsmom") is not False
    ):
        raise ChallengerError("challenger cannot confirm or rescue TSMOM")
    if _str(raw.get("tie_break"), "tie break") != (
        "ASCENDING_CURRENCY_CODE_AFTER_SCORE"
    ):
        raise ChallengerError("challenger tie rule changed")
    if _str(raw.get("ranking_input"), "ranking input") != (
        "COMPOUNDED_EXECUTABLE_TOTAL_RETURN"
    ):
        raise ChallengerError("ranking input must be executable total return")
    if not result.paper_path.is_file():
        raise ChallengerError(f"paper not found: {result.paper_path}")
    paper_hash = sha256_file(result.paper_path)
    if paper_hash != result.expected_paper_sha256:
        raise ChallengerError("paper SHA-256 mismatch")
    return result


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _validate_panel(
    observations: tuple[ExecutableMonthlyInput, ...],
    config: ChallengerConfig,
) -> dict[str, list[ExecutableMonthlyInput]]:
    by_currency: dict[str, list[ExecutableMonthlyInput]] = {
        currency: [] for currency in config.universe
    }
    seen: set[tuple[str, date]] = set()
    for item in observations:
        if item.currency not in by_currency:
            raise ChallengerError(f"unregistered currency: {item.currency}")
        key = (item.currency, item.month)
        if key in seen:
            raise ChallengerError(f"duplicate currency-month: {key}")
        seen.add(key)
        by_currency[item.currency].append(item)
    common: tuple[date, ...] | None = None
    for currency, rows in by_currency.items():
        rows.sort(key=lambda item: item.month)
        if len(rows) <= config.formation_months:
            raise ChallengerError(f"insufficient formation history: {currency}")
        months = tuple(item.month for item in rows)
        if any(
            current != _next_month(previous)
            for previous, current in pairwise(months)
        ):
            raise ChallengerError(f"non-consecutive months: {currency}")
        if common is None:
            common = months
        elif common != months:
            raise ChallengerError("challenger panel is not synchronized")
    return by_currency


def build_challenger_rows(
    observations: tuple[ExecutableMonthlyInput, ...],
    config: ChallengerConfig,
) -> tuple[ChallengerRow, ...]:
    """Rank prior returns and apply the registered top/bottom-three portfolio."""

    by_currency = _validate_panel(observations, config)
    common_rows = by_currency[config.universe[0]]
    previous_weights = {currency: 0.0 for currency in config.universe}
    output: list[ChallengerRow] = []
    for index in range(config.formation_months, len(common_rows)):
        holding_month = common_rows[index].month
        scored: list[tuple[float, str]] = []
        for currency in config.universe:
            history = by_currency[currency][index - config.formation_months : index]
            score = math.prod(1 + item.total_return for item in history) - 1
            scored.append((score, currency))
        ranked = sorted(scored, key=lambda item: (item[0], item[1]))
        shorts = {currency for _, currency in ranked[: config.short_count]}
        longs = {currency for _, currency in ranked[-config.long_count :]}
        rank_by_currency = {
            currency: rank for rank, (_, currency) in enumerate(ranked, start=1)
        }
        score_by_currency = {currency: score for score, currency in scored}
        for currency in config.universe:
            current = by_currency[currency][index]
            history = by_currency[currency][index - config.formation_months : index]
            if currency in longs:
                position = "LONG"
                weight = config.long_leg_weight / config.long_count
            elif currency in shorts:
                position = "SHORT"
                weight = config.short_leg_weight / config.short_count
            else:
                position = "NEUTRAL"
                weight = 0.0
            previous = previous_weights[currency]
            turnover = abs(weight - previous)
            cost = turnover * current.one_way_cost_return
            gross = weight * current.total_return
            output.append(
                ChallengerRow(
                    challenger_id=config.challenger_id,
                    month=holding_month,
                    currency=currency,
                    formation_start=history[0].month,
                    formation_end=history[-1].month,
                    formation_return=score_by_currency[currency],
                    rank=rank_by_currency[currency],
                    position=position,
                    weight=weight,
                    previous_weight=previous,
                    turnover_weight=turnover,
                    underlying_total_return=current.total_return,
                    trading_cost_return=cost,
                    gross_contribution=gross,
                    net_contribution=gross - cost,
                )
            )
            previous_weights[currency] = weight
    output.sort(key=lambda item: (item.month, item.currency))
    return tuple(output)


def aggregate_challenger(
    rows: tuple[ChallengerRow, ...], config: ChallengerConfig
) -> tuple[ChallengerPortfolioRow, ...]:
    """Aggregate High minus Low while enforcing its notional identity."""

    grouped: dict[date, list[ChallengerRow]] = {}
    for row in rows:
        grouped.setdefault(row.month, []).append(row)
    output: list[ChallengerPortfolioRow] = []
    for month, cluster in sorted(grouped.items()):
        if {item.currency for item in cluster} != set(config.universe):
            raise ChallengerError(f"incomplete challenger month: {month}")
        longs = tuple(sorted(item.currency for item in cluster if item.weight > 0))
        shorts = tuple(sorted(item.currency for item in cluster if item.weight < 0))
        neutral = tuple(sorted(item.currency for item in cluster if item.weight == 0))
        long_weight = sum(item.weight for item in cluster if item.weight > 0)
        short_weight = sum(item.weight for item in cluster if item.weight < 0)
        gross_notional = sum(abs(item.weight) for item in cluster)
        if (
            len(longs) != config.long_count
            or len(shorts) != config.short_count
            or len(neutral) != config.neutral_count
            or not math.isclose(long_weight, 1.0, abs_tol=1e-12)
            or not math.isclose(short_weight, -1.0, abs_tol=1e-12)
            or not math.isclose(gross_notional, 2.0, abs_tol=1e-12)
        ):
            raise ChallengerError("challenger portfolio identity failed")
        output.append(
            ChallengerPortfolioRow(
                challenger_id=config.challenger_id,
                month=month,
                long_currencies=longs,
                short_currencies=shorts,
                neutral_currencies=neutral,
                long_weight=long_weight,
                short_weight=short_weight,
                gross_notional=gross_notional,
                gross_return=sum(item.gross_contribution for item in cluster),
                trading_cost_return=sum(
                    item.trading_cost_return for item in cluster
                ),
                net_return=sum(item.net_contribution for item in cluster),
            )
        )
    return tuple(output)


def evaluate_challenger_eligibility(
    *,
    config: ChallengerConfig,
    phase01_path: Path,
    phase02_summary_path: Path,
    phase02_schema_path: Path,
    phase03_summary_path: Path,
) -> ChallengerEligibility:
    """Evaluate upstream gates without accessing a challenger outcome."""

    phase01 = _dict(json.loads(phase01_path.read_text(encoding="utf-8")), "Phase 01")
    phase02 = _dict(
        json.loads(phase02_summary_path.read_text(encoding="utf-8")), "Phase 02"
    )
    schema = _dict(
        json.loads(phase02_schema_path.read_text(encoding="utf-8")), "schema"
    )
    phase03 = _dict(
        json.loads(phase03_summary_path.read_text(encoding="utf-8")), "Phase 03"
    )
    actual = {
        "phase01_decision": _str(phase01.get("phase_decision"), "Phase 01 decision"),
        "phase02_claim_scope": _str(phase02.get("claim_scope"), "Phase 02 scope"),
        "monthly_total_return_status": _str(
            schema.get("monthly_total_return"), "monthly total-return status"
        ),
        "phase03_status": _str(phase03.get("phase_status"), "Phase 03 status"),
    }
    blockers: list[str] = []
    for key, required, blocker in (
        (
            "phase01_decision",
            config.required_phase01_decision,
            "PHASE01_EXECUTABLE_SOURCE_NOT_QUALIFIED",
        ),
        (
            "phase02_claim_scope",
            config.required_phase02_claim_scope,
            "PHASE02_SCOPE_NOT_EXECUTABLE",
        ),
        (
            "monthly_total_return_status",
            config.required_monthly_schema_status,
            "PHASE02_TOTAL_RETURN_NOT_BUILT",
        ),
        (
            "phase03_status",
            config.required_phase03_status,
            "PHASE03_PRIMARY_NOT_EVALUATED_AND_SEALED",
        ),
    ):
        if actual[key] != required:
            blockers.append(blocker)
    return ChallengerEligibility(not blockers, tuple(blockers), actual)


def audit_challenger_trial(path: Path, config: ChallengerConfig) -> dict[str, object]:
    """Verify that exactly one registered challenger remains outcome-sealed."""

    rows = [
        _dict(json.loads(line), f"trial line {line_number}")
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            1,
        )
        if line.strip()
    ]
    sequences = [_int(row.get("sequence"), "sequence") for row in rows]
    if sequences != list(range(1, len(rows) + 1)):
        raise ChallengerError("trial registry sequence is not append-only")
    challengers = [
        row for row in rows if row.get("trial_id") == config.challenger_id
    ]
    if len(challengers) != config.family_size:
        raise ChallengerError("registered challenger family size changed")
    challenger = challengers[0]
    if challenger.get("outcome_inspected") is not False:
        raise ChallengerError("challenger outcome flag is contaminated")
    if challenger.get("status") != "BLOCKED_BEFORE_OUTCOME":
        raise ChallengerError("challenger registry status changed")
    return {
        "registry_entries": len(rows),
        "registered_challenger_family_size": len(challengers),
        "challenger_id": config.challenger_id,
        "challenger_status": challenger["status"],
        "challenger_outcome_inspected": challenger["outcome_inspected"],
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
    files = [
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
            "phase": "04-cross-sectional-challenger",
            "generated_at_utc": generated_at,
            "files": files,
        },
    )


def run_phase04_gate(
    *,
    root: Path,
    config_path: Path,
    trial_registry_path: Path,
    phase01_path: Path,
    phase02_summary_path: Path,
    phase02_schema_path: Path,
    phase03_summary_path: Path,
    outcome_path: Path,
    evidence_root: Path,
) -> dict[str, object]:
    """Register the challenger and stop before reading an ineligible outcome."""

    config = load_challenger_config(config_path, root=root)
    trial_audit = audit_challenger_trial(trial_registry_path, config)
    eligibility = evaluate_challenger_eligibility(
        config=config,
        phase01_path=phase01_path,
        phase02_summary_path=phase02_summary_path,
        phase02_schema_path=phase02_schema_path,
        phase03_summary_path=phase03_summary_path,
    )
    if eligibility.eligible:
        raise ChallengerError(
            "eligible challenger input requires a reviewed executable adapter"
        )
    summary: dict[str, object] = {
        "phase": "04-cross-sectional-challenger",
        "phase_status": "COMPLETE_BLOCKED_BEFORE_OUTCOME",
        "generated_at_utc": config.generated_at_utc,
        "decision": "NOT_TESTED",
        "challenger_id": config.challenger_id,
        "implementation_type": config.implementation_type,
        "registered_family_size": config.family_size,
        "eligibility": False,
        "blockers": list(eligibility.blockers),
        "outcome_path_declared": outcome_path.as_posix(),
        "outcome_file_read": False,
        "challenger_signal_evaluated": False,
        "challenger_pnl_computed": False,
        "can_confirm_tsmom": False,
        "can_rescue_tsmom": False,
    }
    gate = {
        "eligible": False,
        "actual": eligibility.actual,
        "required": {
            "phase01_decision": config.required_phase01_decision,
            "phase02_claim_scope": config.required_phase02_claim_scope,
            "monthly_total_return_status": config.required_monthly_schema_status,
            "phase03_status": config.required_phase03_status,
        },
        "blockers": list(eligibility.blockers),
        "checked_before_outcome_path": True,
        "outcome_file_read": False,
    }
    report = f"""# Phase 04 - Cross-sectional challenger

Decision: `NOT_TESTED`

Status: `COMPLETE_BLOCKED_BEFORE_OUTCOME`

The single registered challenger is `{config.challenger_id}`. It is a disclosed
G10 adaptation anchored to Menkhoff et al. MOM12,1: rank the prior 12-month
executable total return, hold the three winners long and three losers short for
one month, leave three neutral, and rebalance monthly. Each leg has full unit
notional, so the portfolio is dollar-neutral with gross notional two.

The paper itself was hash-verified. Synthetic executable fixtures validate
ranking, causal formation, deterministic ties, leg weights, turnover, and cost
accounting. These synthetic values are not research evidence.

The real gate found {len(eligibility.blockers)} blockers before
`{outcome_path.as_posix()}` was opened:

{chr(10).join(f'- `{blocker}`' for blocker in eligibility.blockers)}

No challenger signal, return, or PnL was computed. This separate lineage cannot
confirm or rescue TSMOM v1, and its status does not change the primary decision.
"""
    evidence_root.mkdir(parents=True, exist_ok=True)
    _write_json(evidence_root / "summary.json", summary)
    _write_json(evidence_root / "eligibility_gate.json", gate)
    _write_json(evidence_root / "trial_registry_audit.json", trial_audit)
    _write_json(
        evidence_root / "input_manifest.json",
        {
            "config_sha256": sha256_file(config_path),
            "paper_sha256": sha256_file(config.paper_path),
            "trial_registry_sha256": sha256_file(trial_registry_path),
            "phase01_sha256": sha256_file(phase01_path),
            "phase02_summary_sha256": sha256_file(phase02_summary_path),
            "phase02_schema_sha256": sha256_file(phase02_schema_path),
            "phase03_summary_sha256": sha256_file(phase03_summary_path),
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
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/cross_sectional_challenger_v0_1.json"),
    )
    parser.add_argument(
        "--trial-registry",
        type=Path,
        default=Path("config/trial_registry.jsonl"),
    )
    parser.add_argument(
        "--outcome-path",
        type=Path,
        default=Path("data/interim/phase02/monthly_reference_changes.csv"),
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("evidence/phase04"),
    )
    args = parser.parse_args()
    root = Path.cwd()
    result = run_phase04_gate(
        root=root,
        config_path=args.config,
        trial_registry_path=args.trial_registry,
        phase01_path=root / "evidence/phase01/decision.json",
        phase02_summary_path=root / "evidence/phase02/summary.json",
        phase02_schema_path=root / "evidence/phase02/schema_coverage.json",
        phase03_summary_path=root / "evidence/phase03/summary.json",
        outcome_path=args.outcome_path,
        evidence_root=args.evidence_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
