"""Phase 02 causal canonical layer for BIS reference-rate diagnostics."""

from __future__ import annotations

import argparse
import calendar
import csv
import json
import math
from bisect import bisect_right
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import cast

from .phase01_sources import QualificationError, sha256_file
from .schemas import CanonicalDailyMark, ClaimScope, MonthlyReferenceChange


class CanonicalizationError(RuntimeError):
    """The reference source cannot satisfy the frozen canonical contract."""


@dataclass(frozen=True)
class DependenceRule:
    maximum_lag_months: int
    insignificant_run_length: int
    critical_value: float
    fallback_block_length_months: int
    sensitivity_blocks: tuple[int, ...]


@dataclass(frozen=True)
class Phase02Config:
    config_version: str
    contract_version: str
    generated_at_utc: str
    source_id: str
    expected_csv_sha256: str
    window_start: date
    window_end: date
    currency_areas: dict[str, str]
    observation_time: time
    availability_lag_days: int
    availability_time: time
    decision_time: time
    maximum_staleness_days: int
    dependence_rule: DependenceRule


@dataclass(frozen=True)
class ParsedMarks:
    marks: tuple[CanonicalDailyMark, ...]
    skipped_non_normal: dict[str, int]
    raw_to_canonical_identity_failures: int


@dataclass(frozen=True)
class MonthlyMark:
    currency: str
    month: date
    decision_at_utc: datetime
    observed_date: date
    observed_at_utc: datetime
    available_at_utc: datetime
    staleness_calendar_days: int
    usd_per_currency: float
    claim_scope: ClaimScope = ClaimScope.PREDICTABILITY_ONLY


@dataclass(frozen=True)
class DependenceSelection:
    observations: int
    significance_threshold: float
    autocorrelations: tuple[tuple[int, float], ...]
    selected_block_length_months: int
    selection_reason: str


def _dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CanonicalizationError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise CanonicalizationError(f"{label} must be an array")
    return cast(list[object], value)


def _str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CanonicalizationError(f"{label} must be a non-empty string")
    return value


def _int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise CanonicalizationError(f"{label} must be an integer")
    return value


def _float(value: object, label: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise CanonicalizationError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise CanonicalizationError(f"{label} must be finite")
    return result


def _token(value: str) -> str:
    return value.split(":", maxsplit=1)[0].strip()


def load_config(path: Path) -> Phase02Config:
    """Load and validate the frozen reference canonicalization contract."""

    raw = _dict(json.loads(path.read_text(encoding="utf-8")), "config")
    source = _dict(raw.get("source"), "source")
    window = _dict(raw.get("window"), "window")
    month_end = _dict(raw.get("month_end"), "month_end")
    dependence = _dict(raw.get("dependence_rule"), "dependence_rule")
    scope = _str(raw.get("claim_scope"), "claim_scope")
    if scope != ClaimScope.PREDICTABILITY_ONLY.value:
        raise CanonicalizationError("BIS reference layer must be predictability-only")
    if _str(source.get("raw_orientation"), "raw_orientation") != "CURRENCY_PER_USD":
        raise CanonicalizationError("unexpected raw orientation")
    if (
        _str(source.get("canonical_orientation"), "canonical_orientation")
        != "USD_PER_CURRENCY"
    ):
        raise CanonicalizationError("unexpected canonical orientation")
    if _str(source.get("normal_status_code"), "normal status") != "A":
        raise CanonicalizationError("only BIS normal status A is supported")
    if _str(source.get("free_confidentiality_code"), "free code") != "F":
        raise CanonicalizationError("only BIS free confidentiality F is supported")
    if _str(month_end.get("selection"), "month-end selection") != (
        "LATEST_OBSERVATION_AVAILABLE_BY_DECISION"
    ):
        raise CanonicalizationError("month-end selection must be causal")
    if month_end.get("allow_forward_fill") is not False:
        raise CanonicalizationError("forward fill must remain disabled")
    if month_end.get("require_synchronized_g10") is not True:
        raise CanonicalizationError("synchronized G10 months are mandatory")
    if _str(dependence.get("selection"), "dependence selection") != (
        "ONE_PLUS_LAST_SIGNIFICANT_ACF_WITH_INSIGNIFICANT_TAIL"
    ):
        raise CanonicalizationError("unexpected dependence selection rule")

    area_raw = _dict(raw.get("required_currency_areas"), "currency areas")
    areas = {
        _str(key, "currency"): _str(value, "area")
        for key, value in area_raw.items()
    }
    if len(areas) != 9 or len(set(areas.values())) != 9:
        raise CanonicalizationError("exactly nine unique G10 mappings are required")
    lag = _int(source.get("availability_lag_calendar_days"), "availability lag")
    max_staleness = _int(
        month_end.get("maximum_staleness_calendar_days"), "maximum staleness"
    )
    if lag < 1 or max_staleness < lag:
        raise CanonicalizationError("availability and staleness rules are invalid")

    sensitivity = tuple(
        _int(item, "sensitivity block")
        for item in _list(
            dependence.get("sensitivity_block_lengths_months"),
            "sensitivity blocks",
        )
    )
    rule = DependenceRule(
        maximum_lag_months=_int(
            dependence.get("maximum_lag_months"), "maximum lag"
        ),
        insignificant_run_length=_int(
            dependence.get("insignificant_run_length"), "insignificant run"
        ),
        critical_value=_float(
            dependence.get("two_sided_normal_critical_value"), "critical value"
        ),
        fallback_block_length_months=_int(
            dependence.get("fallback_block_length_months"), "fallback block"
        ),
        sensitivity_blocks=sensitivity,
    )
    if (
        rule.maximum_lag_months < 1
        or rule.insignificant_run_length < 1
        or rule.fallback_block_length_months < 1
        or not rule.sensitivity_blocks
    ):
        raise CanonicalizationError("dependence rule values must be positive")

    start = date.fromisoformat(_str(window.get("start"), "window start"))
    end = date.fromisoformat(_str(window.get("end"), "window end"))
    if end <= start:
        raise CanonicalizationError("window end must follow start")
    return Phase02Config(
        config_version=_str(raw.get("config_version"), "config version"),
        contract_version=_str(raw.get("contract_version"), "contract version"),
        generated_at_utc=_str(raw.get("generated_at_utc"), "generated_at_utc"),
        source_id=_str(source.get("source_id"), "source id"),
        expected_csv_sha256=_str(
            source.get("expected_csv_sha256"), "expected CSV hash"
        ),
        window_start=start,
        window_end=end,
        currency_areas=areas,
        observation_time=time.fromisoformat(
            _str(source.get("observation_time_utc"), "observation time")
        ),
        availability_lag_days=lag,
        availability_time=time.fromisoformat(
            _str(source.get("availability_time_utc"), "availability time")
        ),
        decision_time=time.fromisoformat(
            _str(month_end.get("decision_time_utc"), "decision time")
        ),
        maximum_staleness_days=max_staleness,
        dependence_rule=rule,
    )


def parse_bis_reference_marks(path: Path, config: Phase02Config) -> ParsedMarks:
    """Parse the registered BIS slice, normalize orientation, and fail closed."""

    actual_hash = sha256_file(path)
    if actual_hash != config.expected_csv_sha256:
        raise CanonicalizationError(
            f"BIS CSV hash mismatch: expected {config.expected_csv_sha256}, "
            f"received {actual_hash}"
        )
    selected: list[CanonicalDailyMark] = []
    seen: set[tuple[str, date]] = set()
    skipped = {currency: 0 for currency in config.currency_areas}
    identity_failures = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "FREQ:Frequency",
            "REF_AREA:Reference area",
            "CURRENCY:Currency",
            "TIME_PERIOD:Time period or range",
            "OBS_VALUE:Observation Value",
            "OBS_STATUS:Observation Status",
            "OBS_CONF:Observation confidentiality",
        }
        missing = sorted(required - set(reader.fieldnames or ()))
        if missing:
            raise CanonicalizationError(f"BIS CSV missing columns: {missing}")
        for row in reader:
            if _token(row["FREQ:Frequency"]) != "D":
                continue
            currency = _token(row["CURRENCY:Currency"])
            area = config.currency_areas.get(currency)
            if area is None or _token(row["REF_AREA:Reference area"]) != area:
                continue
            observed = date.fromisoformat(row["TIME_PERIOD:Time period or range"])
            if not config.window_start <= observed <= config.window_end:
                continue
            if _token(row["OBS_STATUS:Observation Status"]) != "A":
                skipped[currency] += 1
                continue
            if _token(row["OBS_CONF:Observation confidentiality"]) != "F":
                raise CanonicalizationError(f"non-free BIS observation: {currency}")
            try:
                raw_value = float(row["OBS_VALUE:Observation Value"])
            except ValueError as exc:
                raise CanonicalizationError(
                    f"invalid normal BIS value: {currency} {observed}"
                ) from exc
            if not math.isfinite(raw_value) or raw_value <= 0:
                raise CanonicalizationError(
                    f"invalid normal BIS value: {currency} {observed}"
                )
            key = (currency, observed)
            if key in seen:
                raise CanonicalizationError(f"duplicate BIS observation: {key}")
            seen.add(key)
            observed_at = datetime.combine(
                observed,
                config.observation_time,
                tzinfo=UTC,
            )
            available_at = datetime.combine(
                observed + timedelta(days=config.availability_lag_days),
                config.availability_time,
                tzinfo=UTC,
            )
            canonical_value = 1.0 / raw_value
            if not math.isclose(
                raw_value * canonical_value,
                1.0,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                identity_failures += 1
            selected.append(
                CanonicalDailyMark(
                    source_id=config.source_id,
                    instrument_id=f"USD_PER_{currency}_REFERENCE",
                    currency=currency,
                    observed_date=observed,
                    observed_at_utc=observed_at,
                    available_at_utc=available_at,
                    usd_per_currency=canonical_value,
                    claim_scope=ClaimScope.PREDICTABILITY_ONLY,
                )
            )
    selected.sort(key=lambda item: (item.currency, item.observed_date))
    counts = {
        currency: sum(item.currency == currency for item in selected)
        for currency in config.currency_areas
    }
    missing_currencies = [currency for currency, count in counts.items() if count == 0]
    if missing_currencies:
        raise CanonicalizationError(f"missing G10 marks: {missing_currencies}")
    if identity_failures:
        raise CanonicalizationError("quote inversion identity failed")
    return ParsedMarks(tuple(selected), skipped, identity_failures)


def _month_starts(start: date, end: date) -> tuple[date, ...]:
    months: list[date] = []
    cursor = date(start.year, start.month, 1)
    final = date(end.year, end.month, 1)
    while cursor <= final:
        months.append(cursor)
        cursor = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
    return tuple(months)


def build_monthly_marks(
    marks: tuple[CanonicalDailyMark, ...], config: Phase02Config
) -> tuple[MonthlyMark, ...]:
    """Select only observations known by each frozen month-end decision."""

    by_currency: dict[str, list[CanonicalDailyMark]] = {
        currency: [] for currency in config.currency_areas
    }
    for mark in marks:
        by_currency[mark.currency].append(mark)
    result: list[MonthlyMark] = []
    for month in _month_starts(config.window_start, config.window_end):
        final_day = calendar.monthrange(month.year, month.month)[1]
        month_end = date(month.year, month.month, final_day)
        decision = datetime.combine(month_end, config.decision_time, tzinfo=UTC)
        for currency in sorted(config.currency_areas):
            candidates = by_currency[currency]
            availability = [item.available_at_utc for item in candidates]
            position = bisect_right(availability, decision) - 1
            if position < 0:
                raise CanonicalizationError(
                    f"no {currency} mark available for {month.isoformat()}"
                )
            chosen = candidates[position]
            staleness = (month_end - chosen.observed_date).days
            if staleness < config.availability_lag_days:
                raise CanonicalizationError("month-end selector reached future data")
            if staleness > config.maximum_staleness_days:
                raise CanonicalizationError(
                    f"stale {currency} month-end mark: {month} age={staleness}"
                )
            result.append(
                MonthlyMark(
                    currency=currency,
                    month=month,
                    decision_at_utc=decision,
                    observed_date=chosen.observed_date,
                    observed_at_utc=chosen.observed_at_utc,
                    available_at_utc=chosen.available_at_utc,
                    staleness_calendar_days=staleness,
                    usd_per_currency=chosen.usd_per_currency,
                )
            )
    expected = len(_month_starts(config.window_start, config.window_end)) * len(
        config.currency_areas
    )
    if len(result) != expected:
        raise CanonicalizationError("month-end G10 panel is not synchronized")
    return tuple(result)


def build_monthly_reference_changes(
    monthly_marks: tuple[MonthlyMark, ...], config: Phase02Config
) -> tuple[MonthlyReferenceChange, ...]:
    """Build price-only changes without promoting them to total returns."""

    by_currency: dict[str, list[MonthlyMark]] = {
        currency: [] for currency in config.currency_areas
    }
    for mark in monthly_marks:
        by_currency[mark.currency].append(mark)
    changes: list[MonthlyReferenceChange] = []
    for currency in sorted(by_currency):
        ordered = sorted(by_currency[currency], key=lambda item: item.month)
        for previous, current in pairwise(ordered):
            changes.append(
                MonthlyReferenceChange(
                    currency=currency,
                    month=current.month,
                    start_mark_date=previous.observed_date,
                    end_mark_date=current.observed_date,
                    simple_change=(
                        current.usd_per_currency / previous.usd_per_currency - 1.0
                    ),
                )
            )
    changes.sort(key=lambda item: (item.month, item.currency))
    return tuple(changes)


def synchronized_market_changes(
    changes: tuple[MonthlyReferenceChange, ...], config: Phase02Config
) -> tuple[tuple[date, float], ...]:
    """Average the complete currency cluster for dependence selection only."""

    grouped: dict[date, list[MonthlyReferenceChange]] = {}
    for item in changes:
        grouped.setdefault(item.month, []).append(item)
    synchronized: list[tuple[date, float]] = []
    required = set(config.currency_areas)
    for month, rows in sorted(grouped.items()):
        if {item.currency for item in rows} != required:
            raise CanonicalizationError(f"incomplete currency cluster: {month}")
        synchronized.append(
            (month, sum(item.simple_change for item in rows) / len(rows))
        )
    return tuple(synchronized)


def _autocorrelation(values: tuple[float, ...], lag: int) -> float:
    mean = sum(values) / len(values)
    denominator = sum((value - mean) ** 2 for value in values)
    if denominator == 0:
        return 0.0
    numerator = sum(
        (values[index] - mean) * (values[index - lag] - mean)
        for index in range(lag, len(values))
    )
    return numerator / denominator


def select_dependence_block(
    synchronized: tuple[tuple[date, float], ...], rule: DependenceRule
) -> DependenceSelection:
    """Freeze a block length from market dependence before signal evaluation."""

    values = tuple(value for _, value in synchronized)
    required = rule.maximum_lag_months + rule.insignificant_run_length + 2
    if len(values) < required:
        raise CanonicalizationError("insufficient months for dependence selection")
    threshold = rule.critical_value / math.sqrt(len(values))
    acfs = tuple(
        (lag, _autocorrelation(values, lag))
        for lag in range(1, rule.maximum_lag_months + 1)
    )
    significant = [lag for lag, value in acfs if abs(value) > threshold]
    if not significant:
        return DependenceSelection(
            observations=len(values),
            significance_threshold=threshold,
            autocorrelations=acfs,
            selected_block_length_months=1,
            selection_reason=(
                "No significant autocorrelation; one-month block selected."
            ),
        )
    last_significant = max(significant)
    insignificant_tail = rule.maximum_lag_months - last_significant
    if insignificant_tail >= rule.insignificant_run_length:
        return DependenceSelection(
            observations=len(values),
            significance_threshold=threshold,
            autocorrelations=acfs,
            selected_block_length_months=last_significant + 1,
            selection_reason=(
                "One plus the last significant autocorrelation lag, followed by "
                f"at least {rule.insignificant_run_length} insignificant tail lags."
            ),
        )
    return DependenceSelection(
        observations=len(values),
        significance_threshold=threshold,
        autocorrelations=acfs,
        selected_block_length_months=rule.fallback_block_length_months,
        selection_reason="No qualifying run; frozen fallback applied.",
    )


def _serialize(value: object) -> str:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, date | datetime):
        return value.isoformat()
    return str(value)


CanonicalRow = CanonicalDailyMark | MonthlyMark | MonthlyReferenceChange


def _write_dataclasses(path: Path, rows: tuple[CanonicalRow, ...]) -> None:
    if not rows:
        raise CanonicalizationError(f"cannot write empty canonical file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    first = asdict(rows[0])
    fieldnames = list(first)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: _serialize(value) for key, value in asdict(row).items()}
            )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _manifest(root: Path, phase: str, generated_at: str) -> None:
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
        {"phase": phase, "generated_at_utc": generated_at, "files": files},
    )


def run_phase02(
    *,
    config_path: Path,
    bis_csv_path: Path,
    interim_root: Path,
    evidence_root: Path,
) -> dict[str, object]:
    """Run canonicalization and emit only price-predictability evidence."""

    config = load_config(config_path)
    parsed = parse_bis_reference_marks(bis_csv_path, config)
    monthly = build_monthly_marks(parsed.marks, config)
    changes = build_monthly_reference_changes(monthly, config)
    synchronized = synchronized_market_changes(changes, config)
    dependence = select_dependence_block(synchronized, config.dependence_rule)

    daily_path = interim_root / "canonical_daily_marks.csv"
    monthly_path = interim_root / "canonical_month_end_marks.csv"
    change_path = interim_root / "monthly_reference_changes.csv"
    _write_dataclasses(daily_path, parsed.marks)
    _write_dataclasses(monthly_path, monthly)
    _write_dataclasses(change_path, changes)

    months = sorted({item.month for item in monthly})
    staleness = [item.staleness_calendar_days for item in monthly]
    summary: dict[str, object] = {
        "phase": "02-canonical-reference-layer",
        "phase_status": "COMPLETE",
        "generated_at_utc": config.generated_at_utc,
        "claim_scope": ClaimScope.PREDICTABILITY_ONLY.value,
        "trading_claim_status": "NOT_TESTED",
        "source_id": config.source_id,
        "daily_marks": len(parsed.marks),
        "monthly_marks": len(monthly),
        "monthly_reference_changes": len(changes),
        "synchronized_months": len(synchronized),
        "first_month": months[0].isoformat(),
        "last_month": months[-1].isoformat(),
        "maximum_observed_staleness_days": max(staleness),
        "selected_block_length_months": (
            dependence.selected_block_length_months
        ),
        "candidate_signal_evaluated": False,
        "candidate_pnl_computed": False,
        "executable_total_return_built": False,
    }
    schema_coverage = {
        "instrument_contract": "DIAGNOSTIC_REFERENCE_ONLY",
        "raw_market_observation": "PASS",
        "canonical_daily_mark": "PASS",
        "contract_roll_event": "NOT_AVAILABLE",
        "financing_observation": "NOT_AVAILABLE",
        "transaction_cost_observation": "NOT_AVAILABLE",
        "monthly_reference_change": "PASS_PREDICTABILITY_ONLY",
        "monthly_total_return": "NOT_BUILT",
    }
    dependence_payload = {
        "series": "EQUAL_WEIGHT_G10_MONTHLY_REFERENCE_CHANGE",
        "signal_or_strategy_used": False,
        "observations": dependence.observations,
        "significance_threshold": dependence.significance_threshold,
        "selected_block_length_months": dependence.selected_block_length_months,
        "selection_reason": dependence.selection_reason,
        "sensitivity_block_lengths_months": list(
            config.dependence_rule.sensitivity_blocks
        ),
        "autocorrelations": [
            {"lag_months": lag, "autocorrelation": value}
            for lag, value in dependence.autocorrelations
        ],
    }
    source_manifest = {
        "raw_bis_csv": {
            "filename": bis_csv_path.name,
            "sha256": sha256_file(bis_csv_path),
            "bytes": bis_csv_path.stat().st_size,
            "committed": False,
        },
        "config": {
            "filename": config_path.name,
            "sha256": sha256_file(config_path),
            "bytes": config_path.stat().st_size,
        },
        "generated_interim_files": [
            {
                "path": path.name,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "committed": False,
            }
            for path in (daily_path, monthly_path, change_path)
        ],
    }
    sample_flow = {
        "selected_normal_daily_rows": len(parsed.marks),
        "skipped_non_normal_rows": parsed.skipped_non_normal,
        "quote_inversion_identity_failures": (
            parsed.raw_to_canonical_identity_failures
        ),
        "calendar_months": len(months),
        "required_currencies_per_month": len(config.currency_areas),
        "synchronized_month_end_marks": len(monthly),
        "reference_changes": len(changes),
        "total_return_rows": 0,
    }
    report = f"""# Phase 02 - Causal canonical reference-rate layer

Decision: `COMPLETE_PREDICTABILITY_ONLY`

Trading claim: `NOT_TESTED`

The verified BIS slice produced {len(parsed.marks):,} canonical daily marks,
{len(monthly):,} synchronized month-end marks, and {len(changes):,} monthly
reference-rate changes. Every raw currency-per-USD value was inverted to
USD-per-currency and passed the inverse identity check.

Each observation becomes available seven calendar days later at 23:59:59 UTC.
Month-end selection uses only marks available by the decision timestamp, never
forward-fills weekends or holidays, and fails when staleness exceeds
{config.maximum_staleness_days} days. Maximum observed staleness was
{max(staleness)} days.

The dependence rule inspected only the synchronized equal-weight market-change
series, before any TSMOM signal. It selected a moving-block length of
{dependence.selected_block_length_months} month(s); registered sensitivities
remain 3, 6, and 12 months.

No executable monthly total return was built because the source has no
financing, transaction-cost, or roll observations. No TSMOM signal, strategy
return, control result, or PnL was computed. Phase 03 real-data evaluation must
fail closed while Phase 01 remains `PASS_PREDICTABILITY_ONLY`.
"""
    evidence_root.mkdir(parents=True, exist_ok=True)
    _write_json(evidence_root / "summary.json", summary)
    _write_json(evidence_root / "schema_coverage.json", schema_coverage)
    _write_json(evidence_root / "dependence_diagnostics.json", dependence_payload)
    _write_json(evidence_root / "source_manifest.json", source_manifest)
    _write_json(evidence_root / "sample_flow.json", sample_flow)
    (evidence_root / "REPORT.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )
    _manifest(evidence_root, "02-canonical-reference-layer", config.generated_at_utc)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/canonical_reference_v0_1.json"),
    )
    parser.add_argument(
        "--bis-csv",
        type=Path,
        default=Path("data/raw/phase01/WS_XRU_csv_flat.csv"),
    )
    parser.add_argument(
        "--interim-root",
        type=Path,
        default=Path("data/interim/phase02"),
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("evidence/phase02"),
    )
    args = parser.parse_args()
    try:
        result = run_phase02(
            config_path=args.config,
            bis_csv_path=args.bis_csv,
            interim_root=args.interim_root,
            evidence_root=args.evidence_root,
        )
    except (CanonicalizationError, QualificationError) as exc:
        raise SystemExit(f"Phase 02 failed closed: {exc}") from exc
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
