"""Phase 07 exploratory Dukascopy plus Exness Raw-like cost simulation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import cast

from .dukascopy_monthly import SelectedMonthlyTick, select_monthly_tick
from .phase01_sources import sha256_file


class ModeledPocError(RuntimeError):
    """The POC configuration, data, or computation violates its contract."""


class PocStrategy(StrEnum):
    PRIMARY = "TSMOM_12M_SPOT_PRICE"
    B0_CASH = "B0_CASH"
    B1_EXPANDING_MEAN = "B1_EXPANDING_MEAN_SIGN"
    B2_ALWAYS_LONG = "B2_ALWAYS_LONG"
    B2_ALWAYS_SHORT = "B2_ALWAYS_SHORT"


@dataclass(frozen=True)
class InstrumentAssumption:
    currency: str
    symbol: str
    dukascopy_code: str
    invert: bool
    pip_size: float
    spread_pips: float
    slippage_pips: float


@dataclass(frozen=True)
class CostScenario:
    name: str
    spread_multiplier: float
    slippage_multiplier: float


@dataclass(frozen=True)
class PocConfig:
    poc_id: str
    registered_at_utc: str
    first_month: date
    last_month: date
    execution_hour_utc: int
    maximum_lookback_days: int
    lookback_months: int
    block_length_months: int
    bootstrap_resamples: int
    seed: int
    commission_usd_per_lot_per_side: float
    lot_units: int
    instruments: tuple[InstrumentAssumption, ...]
    scenarios: tuple[CostScenario, ...]
    eras: tuple[tuple[date, date], ...]


@dataclass(frozen=True)
class ModeledMonthlyInput:
    currency: str
    month: date
    spot_price_return: float
    one_way_cost_return: float


@dataclass(frozen=True)
class PocStrategyRow:
    scenario: str
    strategy: PocStrategy
    currency: str
    month: date
    signal: int
    previous_signal: int
    turnover_units: int
    spot_price_return: float
    gross_price_return: float
    modeled_transaction_cost_return: float
    before_financing_return: float


@dataclass(frozen=True)
class PocPortfolioRow:
    scenario: str
    strategy: PocStrategy
    month: date
    eligible_currencies: int
    gross_price_return: float
    modeled_transaction_cost_return: float
    before_financing_return: float


def _dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ModeledPocError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ModeledPocError(f"{label} must be an array")
    return cast(list[object], value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ModeledPocError(f"{label} must be a non-empty string")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ModeledPocError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ModeledPocError(f"{label} must be finite")
    return result


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModeledPocError(f"{label} must be an integer")
    return value


def _month(value: object, label: str) -> date:
    text = _string(value, label)
    try:
        return date.fromisoformat(f"{text}-01")
    except ValueError as exc:
        raise ModeledPocError(f"{label} must use YYYY-MM") from exc


def load_poc_config(path: Path) -> PocConfig:
    """Load and enforce the exploratory claim boundary and frozen assumptions."""

    raw = _dict(json.loads(path.read_text(encoding="utf-8")), "POC config")
    if raw.get("lineage") != "EXPLORATORY_POST_V1":
        raise ModeledPocError("POC must remain outside the v1 lineage")
    if raw.get("claim_scope") != "MODELED_EXECUTION_BEFORE_FINANCING":
        raise ModeledPocError("POC claim scope changed")
    source = _dict(raw.get("source"), "source")
    if source.get("api_base_url") != "https://jetta.dukascopy.com/v1":
        raise ModeledPocError("unregistered Dukascopy API")
    sample = _dict(raw.get("sample"), "sample")
    strategy = _dict(raw.get("strategy"), "strategy")
    statistics_config = _dict(raw.get("statistics"), "statistics")
    costs = _dict(raw.get("cost_model"), "cost model")
    decision = _dict(raw.get("decision_boundary"), "decision boundary")
    if costs.get("financing_included") is not False:
        raise ModeledPocError("financing must remain explicitly excluded")
    if costs.get("native_dukascopy_spread_charged") is not False:
        raise ModeledPocError("Dukascopy spread would double-count modeled spread")
    if decision.get("cannot_change_v1_decision") is not True:
        raise ModeledPocError("POC cannot change the historical v1 decision")
    if decision.get("cannot_activate_phase06") is not True:
        raise ModeledPocError("POC cannot activate prospective Phase 06")
    if strategy.get("signal") != "SIGN_COMPOUNDED_TRAILING_SPOT_PRICE_RETURN":
        raise ModeledPocError("POC signal changed")
    controls = {
        _string(value, "control")
        for value in _list(strategy.get("controls"), "controls")
    }
    if controls != {
        "B0_CASH",
        "B1_EXPANDING_MEAN_SIGN",
        "B2_ALWAYS_LONG",
        "B2_ALWAYS_SHORT",
    }:
        raise ModeledPocError("POC control family changed")
    instruments: list[InstrumentAssumption] = []
    for raw_item in _list(raw.get("universe"), "universe"):
        item = _dict(raw_item, "instrument")
        orientation = _string(item.get("quote_orientation"), "orientation")
        if orientation not in {"USD_PER_CURRENCY", "CURRENCY_PER_USD"}:
            raise ModeledPocError("unknown quote orientation")
        instrument = InstrumentAssumption(
            currency=_string(item.get("currency"), "currency"),
            symbol=_string(item.get("symbol"), "symbol"),
            dukascopy_code=_string(item.get("dukascopy_code"), "Dukascopy code"),
            invert=orientation == "CURRENCY_PER_USD",
            pip_size=_number(item.get("pip_size"), "pip size"),
            spread_pips=_number(
                item.get("assumed_base_spread_pips"), "spread pips"
            ),
            slippage_pips=_number(
                item.get("assumed_base_slippage_pips"), "slippage pips"
            ),
        )
        if min(
            instrument.pip_size,
            instrument.spread_pips,
            instrument.slippage_pips,
        ) < 0:
            raise ModeledPocError("cost and pip assumptions cannot be negative")
        instruments.append(instrument)
    expected_currencies = {
        "AUD",
        "CAD",
        "CHF",
        "EUR",
        "GBP",
        "JPY",
        "NOK",
        "NZD",
        "SEK",
    }
    actual_currencies = {item.currency for item in instruments}
    if len(instruments) != 9 or actual_currencies != expected_currencies:
        raise ModeledPocError("POC requires the exact nine-currency universe")
    raw_scenarios = _dict(costs.get("scenarios"), "cost scenarios")
    scenarios = tuple(
        CostScenario(
            name=name,
            spread_multiplier=_number(
                _dict(raw_scenarios.get(name), name).get("spread_multiplier"),
                f"{name} spread multiplier",
            ),
            slippage_multiplier=_number(
                _dict(raw_scenarios.get(name), name).get("slippage_multiplier"),
                f"{name} slippage multiplier",
            ),
        )
        for name in ("FAVORABLE", "BASE", "ADVERSE")
    )
    raw_eras = _list(statistics_config.get("predefined_eras"), "eras")
    eras: list[tuple[date, date]] = []
    for index, raw_era in enumerate(raw_eras):
        values = _list(raw_era, f"era {index}")
        if len(values) != 2:
            raise ModeledPocError("each era needs start and end")
        eras.append((_month(values[0], "era start"), _month(values[1], "era end")))
    config = PocConfig(
        poc_id=_string(raw.get("poc_id"), "POC id"),
        registered_at_utc=_string(raw.get("registered_at_utc"), "registration"),
        first_month=_month(sample.get("first_month"), "first month"),
        last_month=_month(sample.get("last_month"), "last month"),
        execution_hour_utc=_integer(
            sample.get("execution_hour_utc"), "execution hour"
        ),
        maximum_lookback_days=_integer(
            sample.get("maximum_calendar_lookback_days"), "lookback days"
        ),
        lookback_months=_integer(strategy.get("lookback_months"), "lookback"),
        block_length_months=_integer(
            statistics_config.get("moving_block_length_months"), "block length"
        ),
        bootstrap_resamples=_integer(
            statistics_config.get("bootstrap_resamples"), "bootstrap resamples"
        ),
        seed=_integer(statistics_config.get("seed"), "seed"),
        commission_usd_per_lot_per_side=_number(
            costs.get("commission_usd_per_lot_per_side"), "commission"
        ),
        lot_units=_integer(costs.get("standard_lot_base_units"), "lot units"),
        instruments=tuple(instruments),
        scenarios=scenarios,
        eras=tuple(eras),
    )
    if (
        config.first_month >= config.last_month
        or config.lookback_months != 12
        or config.bootstrap_resamples != 10_000
        or config.block_length_months != 10
        or not 0 <= config.execution_hour_utc <= 23
        or config.maximum_lookback_days < 0
        or config.commission_usd_per_lot_per_side < 0
        or config.lot_units <= 0
    ):
        raise ModeledPocError("invalid frozen POC parameter")
    return config


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def month_range(first: date, last: date) -> tuple[date, ...]:
    months: list[date] = []
    cursor = first
    while cursor <= last:
        months.append(cursor)
        cursor = _next_month(cursor)
    return tuple(months)


def acquire_monthly_marks(
    config: PocConfig,
    raw_root: Path,
    *,
    offline: bool,
    workers: int = 5,
) -> tuple[SelectedMonthlyTick, ...]:
    """Fetch instrument-months concurrently with an immutable local cache."""

    months = month_range(config.first_month, config.last_month)
    output: list[SelectedMonthlyTick] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                select_monthly_tick,
                raw_root=raw_root,
                currency=instrument.currency,
                symbol=instrument.symbol,
                instrument_code=instrument.dukascopy_code,
                month=month,
                execution_hour_utc=config.execution_hour_utc,
                maximum_lookback_days=config.maximum_lookback_days,
                pip_size=instrument.pip_size,
                invert=instrument.invert,
                offline=offline,
            ): (instrument.currency, month)
            for instrument in config.instruments
            for month in months
        }
        for future in as_completed(futures):
            currency, month = futures[future]
            try:
                selected = future.result()
            except Exception as exc:
                raise ModeledPocError(
                    f"source acquisition failed for {currency} {month:%Y-%m}"
                ) from exc
            output.append(selected)
            if len(output) % len(months) == 0:
                print(
                    f"acquired {len(output)}/{len(futures)} monthly marks",
                    flush=True,
                )
    output.sort(key=lambda item: (item.month, item.currency))
    expected = len(months) * len(config.instruments)
    if len(output) != expected:
        raise ModeledPocError(f"incomplete monthly panel: {len(output)}/{expected}")
    return tuple(output)


def _one_way_cost(
    mark: SelectedMonthlyTick,
    instrument: InstrumentAssumption,
    scenario: CostScenario,
    config: PocConfig,
) -> float:
    spread_rate = (
        instrument.spread_pips
        * scenario.spread_multiplier
        * instrument.pip_size
        / mark.raw_mid
        / 2
    )
    slippage_rate = (
        instrument.slippage_pips
        * scenario.slippage_multiplier
        * instrument.pip_size
        / mark.raw_mid
    )
    usd_notional = float(config.lot_units)
    if not instrument.invert:
        usd_notional *= mark.raw_mid
    commission_rate = config.commission_usd_per_lot_per_side / usd_notional
    return spread_rate + slippage_rate + commission_rate


def build_monthly_inputs(
    marks: tuple[SelectedMonthlyTick, ...],
    config: PocConfig,
    scenario: CostScenario,
) -> tuple[ModeledMonthlyInput, ...]:
    """Convert marks to synchronized spot-price changes and one-way modeled costs."""

    instruments = {item.currency: item for item in config.instruments}
    by_currency: dict[str, list[SelectedMonthlyTick]] = {
        currency: [] for currency in instruments
    }
    for mark in marks:
        by_currency[mark.currency].append(mark)
    output: list[ModeledMonthlyInput] = []
    expected_months: tuple[date, ...] | None = None
    for currency, currency_marks in by_currency.items():
        currency_marks.sort(key=lambda item: item.month)
        months = tuple(mark.month for mark in currency_marks)
        if expected_months is None:
            expected_months = months
        elif months != expected_months:
            raise ModeledPocError("monthly mark panel is not synchronized")
        for previous, current in pairwise(currency_marks):
            if current.month != _next_month(previous.month):
                raise ModeledPocError(f"non-consecutive mark for {currency}")
            spot_return = current.normalized_mid / previous.normalized_mid - 1
            output.append(
                ModeledMonthlyInput(
                    currency=currency,
                    month=current.month,
                    spot_price_return=spot_return,
                    one_way_cost_return=_one_way_cost(
                        previous,
                        instruments[currency],
                        scenario,
                        config,
                    ),
                )
            )
    output.sort(key=lambda item: (item.month, item.currency))
    return tuple(output)


def _sign(value: float) -> int:
    return int(value > 0) - int(value < 0)


def build_strategy_rows(
    inputs: tuple[ModeledMonthlyInput, ...],
    config: PocConfig,
    scenario: CostScenario,
    strategy: PocStrategy,
) -> tuple[PocStrategyRow, ...]:
    """Run a frozen strategy on spot-price returns without relabeling total return."""

    by_currency: dict[str, list[ModeledMonthlyInput]] = {
        item.currency: [] for item in config.instruments
    }
    for item in inputs:
        by_currency[item.currency].append(item)
    output: list[PocStrategyRow] = []
    for currency, rows in by_currency.items():
        rows.sort(key=lambda item: item.month)
        previous_signal = 0
        for index in range(config.lookback_months, len(rows)):
            history = rows[index - config.lookback_months : index]
            current = rows[index]
            if strategy is PocStrategy.PRIMARY:
                signal = _sign(
                    math.prod(1 + row.spot_price_return for row in history) - 1
                )
            elif strategy is PocStrategy.B1_EXPANDING_MEAN:
                signal = _sign(
                    statistics.fmean(
                        row.spot_price_return for row in rows[:index]
                    )
                )
            elif strategy is PocStrategy.B2_ALWAYS_LONG:
                signal = 1
            elif strategy is PocStrategy.B2_ALWAYS_SHORT:
                signal = -1
            elif strategy is PocStrategy.B0_CASH:
                signal = 0
            else:
                raise ModeledPocError(f"unsupported strategy: {strategy}")
            turnover = abs(signal - previous_signal)
            gross = signal * current.spot_price_return
            cost = turnover * current.one_way_cost_return
            output.append(
                PocStrategyRow(
                    scenario=scenario.name,
                    strategy=strategy,
                    currency=currency,
                    month=current.month,
                    signal=signal,
                    previous_signal=previous_signal,
                    turnover_units=turnover,
                    spot_price_return=current.spot_price_return,
                    gross_price_return=gross,
                    modeled_transaction_cost_return=cost,
                    before_financing_return=gross - cost,
                )
            )
            previous_signal = signal
    output.sort(key=lambda item: (item.month, item.currency))
    return tuple(output)


def aggregate_portfolio(
    rows: tuple[PocStrategyRow, ...], config: PocConfig
) -> tuple[PocPortfolioRow, ...]:
    """Equal-weight synchronized currency legs by calendar month."""

    grouped: dict[date, list[PocStrategyRow]] = {}
    for row in rows:
        grouped.setdefault(row.month, []).append(row)
    required = {item.currency for item in config.instruments}
    output: list[PocPortfolioRow] = []
    for month, cluster in sorted(grouped.items()):
        if {item.currency for item in cluster} != required:
            raise ModeledPocError(f"incomplete portfolio month: {month}")
        if len({item.strategy for item in cluster}) != 1:
            raise ModeledPocError("portfolio month mixes strategies")
        count = len(cluster)
        output.append(
            PocPortfolioRow(
                scenario=cluster[0].scenario,
                strategy=cluster[0].strategy,
                month=month,
                eligible_currencies=count,
                gross_price_return=statistics.fmean(
                    item.gross_price_return for item in cluster
                ),
                modeled_transaction_cost_return=statistics.fmean(
                    item.modeled_transaction_cost_return for item in cluster
                ),
                before_financing_return=statistics.fmean(
                    item.before_financing_return for item in cluster
                ),
            )
        )
    return tuple(output)


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def moving_block_mean_interval(
    values: tuple[float, ...], *, block: int, resamples: int, seed: int
) -> tuple[float, float]:
    """Two-sided circular moving-block percentile interval for a monthly mean."""

    if not values or block <= 0 or resamples <= 0:
        raise ValueError("bootstrap inputs must be positive and non-empty")
    generator = random.Random(seed)
    count = len(values)
    estimates: list[float] = []
    for _ in range(resamples):
        sample: list[float] = []
        while len(sample) < count:
            start = generator.randrange(count)
            sample.extend(values[(start + offset) % count] for offset in range(block))
        estimates.append(statistics.fmean(sample[:count]))
    return _percentile(estimates, 0.025), _percentile(estimates, 0.975)


def return_metrics(
    values: tuple[float, ...], config: PocConfig, *, with_interval: bool = True
) -> dict[str, float | int | None]:
    if not values:
        raise ModeledPocError("cannot summarize an empty return series")
    mean = statistics.fmean(values)
    volatility = statistics.stdev(values) if len(values) > 1 else 0.0
    annual_mean = mean * 12
    annual_volatility = volatility * math.sqrt(12)
    wealth = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in values:
        wealth *= 1 + value
        peak = max(peak, wealth)
        max_drawdown = min(max_drawdown, wealth / peak - 1)
    lower: float | None = None
    upper: float | None = None
    if with_interval:
        lower, upper = moving_block_mean_interval(
            values,
            block=config.block_length_months,
            resamples=config.bootstrap_resamples,
            seed=config.seed,
        )
    return {
        "months": len(values),
        "mean_monthly": mean,
        "mean_monthly_ci_low": lower,
        "mean_monthly_ci_high": upper,
        "annualized_arithmetic_mean": annual_mean,
        "annualized_volatility": annual_volatility,
        "annualized_sharpe_zero_rate": (
            annual_mean / annual_volatility if annual_volatility > 0 else None
        ),
        "cumulative_compounded_return": wealth - 1,
        "maximum_drawdown": max_drawdown,
        "positive_month_fraction": sum(value > 0 for value in values) / len(values),
    }


def cross_source_audit(
    marks: tuple[SelectedMonthlyTick, ...],
    reference_changes_path: Path,
) -> list[dict[str, object]]:
    """Compare direction and scale with the independent Phase 02 BIS panel."""

    reference: dict[tuple[str, date], float] = {}
    with reference_changes_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            currency = row.get("currency")
            month_text = row.get("month")
            change_text = row.get("simple_change")
            if currency is None or month_text is None or change_text is None:
                raise ModeledPocError("Phase 02 reference row is incomplete")
            reference[(currency, date.fromisoformat(month_text))] = float(change_text)
    by_currency: dict[str, list[SelectedMonthlyTick]] = {}
    for mark in marks:
        by_currency.setdefault(mark.currency, []).append(mark)
    output: list[dict[str, object]] = []
    for currency, currency_marks in sorted(by_currency.items()):
        currency_marks.sort(key=lambda item: item.month)
        dukascopy: list[float] = []
        bis: list[float] = []
        for previous, current in pairwise(currency_marks):
            key = (currency, current.month)
            if key not in reference:
                continue
            dukascopy.append(current.normalized_mid / previous.normalized_mid - 1)
            bis.append(reference[key])
        if len(dukascopy) < 2:
            raise ModeledPocError(f"insufficient BIS overlap for {currency}")
        correlation = statistics.correlation(dukascopy, bis)
        output.append(
            {
                "currency": currency,
                "overlap_months": len(dukascopy),
                "pearson_correlation": correlation,
                "mean_absolute_return_difference": statistics.fmean(
                    abs(left - right)
                    for left, right in zip(dukascopy, bis, strict=True)
                ),
                "sign_agreement_fraction": statistics.fmean(
                    _sign(left) == _sign(right)
                    for left, right in zip(dukascopy, bis, strict=True)
                ),
            }
        )
    return output


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_csv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_marks(path: Path, marks: tuple[SelectedMonthlyTick, ...]) -> None:
    _write_csv(
        path,
        (
            "month",
            "currency",
            "symbol",
            "requested_hour_utc",
            "observed_at_utc",
            "bid",
            "ask",
            "raw_mid",
            "normalized_mid",
            "native_spread_pips",
            "raw_sha256",
        ),
        [
            {
                "month": mark.month.isoformat(),
                "currency": mark.currency,
                "symbol": mark.symbol,
                "requested_hour_utc": mark.requested_hour_utc.isoformat(),
                "observed_at_utc": mark.observed_at_utc.isoformat(),
                "bid": mark.bid,
                "ask": mark.ask,
                "raw_mid": mark.raw_mid,
                "normalized_mid": mark.normalized_mid,
                "native_spread_pips": mark.native_spread_pips,
                "raw_sha256": mark.raw_sha256,
            }
            for mark in marks
        ],
    )


def _manifest(evidence_root: Path, generated_at: str) -> None:
    files = [
        {
            "path": path.name,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(evidence_root.iterdir())
        if path.is_file() and path.name != "manifest.json"
    ]
    _write_json(
        evidence_root / "manifest.json",
        {
            "phase": "07-modeled-execution-poc",
            "generated_at_utc": generated_at,
            "files": files,
        },
    )


def run_phase07(
    *,
    root: Path,
    config_path: Path,
    raw_root: Path,
    interim_root: Path,
    evidence_root: Path,
    reference_changes_path: Path,
    offline: bool,
) -> dict[str, object]:
    """Acquire monthly marks, simulate frozen costs, and emit bounded evidence."""

    config = load_poc_config(config_path)
    marks = acquire_monthly_marks(config, raw_root, offline=offline)
    interim_marks = interim_root / "monthly_marks.csv"
    _write_marks(interim_marks, marks)
    cross_source_rows = cross_source_audit(marks, reference_changes_path)
    all_strategy_rows: dict[tuple[str, PocStrategy], tuple[PocStrategyRow, ...]] = {}
    all_portfolios: list[PocPortfolioRow] = []
    strategies = tuple(PocStrategy)
    for scenario in config.scenarios:
        inputs = build_monthly_inputs(marks, config, scenario)
        for strategy in strategies:
            strategy_rows = build_strategy_rows(inputs, config, scenario, strategy)
            all_strategy_rows[(scenario.name, strategy)] = strategy_rows
            all_portfolios.extend(aggregate_portfolio(strategy_rows, config))
    all_portfolios.sort(key=lambda row: (row.scenario, row.strategy, row.month))

    metric_rows: list[dict[str, object]] = []
    for scenario in config.scenarios:
        for strategy in strategies:
            rows = [
                row
                for row in all_portfolios
                if row.scenario == scenario.name and row.strategy is strategy
            ]
            net_values = tuple(row.before_financing_return for row in rows)
            gross_values = tuple(row.gross_price_return for row in rows)
            metrics = return_metrics(net_values, config)
            metric_rows.append(
                {
                    "scenario": scenario.name,
                    "strategy": strategy.value,
                    **metrics,
                    "gross_annualized_arithmetic_mean": statistics.fmean(gross_values)
                    * 12,
                    "annualized_modeled_transaction_cost": statistics.fmean(
                        row.modeled_transaction_cost_return for row in rows
                    )
                    * 12,
                }
            )

    base_primary = [
        row
        for row in all_portfolios
        if row.scenario == "BASE" and row.strategy is PocStrategy.PRIMARY
    ]
    base_b1 = [
        row
        for row in all_portfolios
        if row.scenario == "BASE" and row.strategy is PocStrategy.B1_EXPANDING_MEAN
    ]
    if [row.month for row in base_primary] != [row.month for row in base_b1]:
        raise ModeledPocError("primary and B1 months do not align")
    paired_values = tuple(
        primary.before_financing_return - control.before_financing_return
        for primary, control in zip(base_primary, base_b1, strict=True)
    )
    paired_low, paired_high = moving_block_mean_interval(
        paired_values,
        block=config.block_length_months,
        resamples=config.bootstrap_resamples,
        seed=config.seed,
    )
    paired_control = {
        "comparison": "BASE_PRIMARY_MINUS_B1_BEFORE_FINANCING",
        "months": len(paired_values),
        "mean_monthly_difference": statistics.fmean(paired_values),
        "mean_monthly_difference_ci_low": paired_low,
        "mean_monthly_difference_ci_high": paired_high,
    }

    era_rows: list[dict[str, object]] = []
    for era_start, era_end in config.eras:
        values = tuple(
            row.before_financing_return
            for row in base_primary
            if era_start <= row.month <= era_end
        )
        era_rows.append(
            {
                "era_start": era_start.isoformat(),
                "era_end": era_end.isoformat(),
                **return_metrics(values, config, with_interval=False),
            }
        )

    loo_rows: list[dict[str, object]] = []
    base_instrument_rows = all_strategy_rows[("BASE", PocStrategy.PRIMARY)]
    for excluded in sorted(item.currency for item in config.instruments):
        by_month: dict[date, list[float]] = {}
        for row in base_instrument_rows:
            if row.currency != excluded:
                by_month.setdefault(row.month, []).append(row.before_financing_return)
        values = tuple(statistics.fmean(by_month[month]) for month in sorted(by_month))
        loo_rows.append(
            {
                "excluded_currency": excluded,
                **return_metrics(values, config, with_interval=False),
            }
        )

    instrument_rows: list[dict[str, object]] = []
    for currency in sorted(item.currency for item in config.instruments):
        selected_rows = [
            row for row in base_instrument_rows if row.currency == currency
        ]
        values = tuple(row.before_financing_return for row in selected_rows)
        instrument_rows.append(
            {
                "currency": currency,
                **return_metrics(values, config, with_interval=False),
                "gross_annualized_arithmetic_mean": statistics.fmean(
                    row.gross_price_return for row in selected_rows
                )
                * 12,
                "annualized_modeled_transaction_cost": statistics.fmean(
                    row.modeled_transaction_cost_return for row in selected_rows
                )
                * 12,
                "annualized_turnover_units": statistics.fmean(
                    row.turnover_units for row in selected_rows
                )
                * 12,
            }
        )

    base_metrics = next(
        row
        for row in metric_rows
        if row["scenario"] == "BASE"
        and row["strategy"] == PocStrategy.PRIMARY.value
    )
    ci_low = cast(float, base_metrics["mean_monthly_ci_low"])
    directional_finding = (
        "POSITIVE_MEAN_INTERVAL_ABOVE_ZERO"
        if ci_low > 0
        else "POSITIVE_POINT_ESTIMATE_ONLY"
        if cast(float, base_metrics["mean_monthly"]) > 0
        else "NON_POSITIVE_POINT_ESTIMATE"
    )
    summary: dict[str, object] = {
        "phase": "07-modeled-execution-poc",
        "poc_id": config.poc_id,
        "status": "POC_DIAGNOSTIC_ONLY",
        "claim_scope": "MODELED_EXECUTION_BEFORE_FINANCING",
        "directional_finding": directional_finding,
        "first_source_month": marks[0].month.isoformat(),
        "last_source_month": marks[-1].month.isoformat(),
        "monthly_marks": len(marks),
        "portfolio_months": len(base_primary),
        "currencies": len(config.instruments),
        "financing_included": False,
        "v1_historical_decision": "NOT_TESTED",
        "v1_decision_changed": False,
        "phase06_activated": False,
        "data_quality": {
            "phase02_bis_min_monthly_return_correlation": min(
                cast(float, row["pearson_correlation"])
                for row in cross_source_rows
            ),
            "phase02_bis_min_sign_agreement": min(
                cast(float, row["sign_agreement_fraction"])
                for row in cross_source_rows
            ),
        },
        "base_primary_metrics": base_metrics,
        "base_primary_minus_b1": paired_control,
    }
    evidence_root.mkdir(parents=True, exist_ok=True)
    _write_json(evidence_root / "summary.json", summary)
    _write_json(evidence_root / "paired_control.json", paired_control)
    metric_fields = tuple(metric_rows[0])
    _write_csv(evidence_root / "strategy_metrics.csv", metric_fields, metric_rows)
    _write_csv(evidence_root / "era_metrics.csv", tuple(era_rows[0]), era_rows)
    _write_csv(
        evidence_root / "leave_one_out.csv", tuple(loo_rows[0]), loo_rows
    )
    _write_csv(
        evidence_root / "instrument_metrics.csv",
        tuple(instrument_rows[0]),
        instrument_rows,
    )
    _write_csv(
        evidence_root / "portfolio_returns.csv",
        (
            "scenario",
            "strategy",
            "month",
            "eligible_currencies",
            "gross_price_return",
            "modeled_transaction_cost_return",
            "before_financing_return",
        ),
        [
            {
                "scenario": row.scenario,
                "strategy": row.strategy.value,
                "month": row.month.isoformat(),
                "eligible_currencies": row.eligible_currencies,
                "gross_price_return": row.gross_price_return,
                "modeled_transaction_cost_return": row.modeled_transaction_cost_return,
                "before_financing_return": row.before_financing_return,
            }
            for row in all_portfolios
        ],
    )
    _write_csv(
        evidence_root / "cost_assumptions.csv",
        (
            "currency",
            "symbol",
            "assumed_base_spread_pips",
            "assumed_base_slippage_pips",
            "commission_usd_per_lot_per_side",
            "assumption_basis",
        ),
        [
            {
                "currency": item.currency,
                "symbol": item.symbol,
                "assumed_base_spread_pips": item.spread_pips,
                "assumed_base_slippage_pips": item.slippage_pips,
                "commission_usd_per_lot_per_side": (
                    config.commission_usd_per_lot_per_side
                ),
                "assumption_basis": "MANUAL_SIMULATION_NOT_ACCOUNT_OBSERVATION",
            }
            for item in config.instruments
        ],
    )
    coverage_rows: list[dict[str, object]] = []
    for instrument in config.instruments:
        selected = [mark for mark in marks if mark.currency == instrument.currency]
        coverage_rows.append(
            {
                "currency": instrument.currency,
                "symbol": instrument.symbol,
                "months": len(selected),
                "first_month": selected[0].month.isoformat(),
                "last_month": selected[-1].month.isoformat(),
                "maximum_calendar_fallback_days": max(
                    (
                        _next_month(mark.month)
                        - timedelta(days=1)
                        - mark.requested_hour_utc.date()
                    ).days
                    for mark in selected
                ),
                "median_native_spread_pips": round(
                    statistics.median(
                        mark.native_spread_pips for mark in selected
                    ),
                    6,
                ),
            }
        )
    _write_csv(
        evidence_root / "source_coverage.csv",
        tuple(coverage_rows[0]),
        coverage_rows,
    )
    _write_csv(
        evidence_root / "cross_source_audit.csv",
        tuple(cross_source_rows[0]),
        cross_source_rows,
    )
    source_rows = [
        {
            "month": mark.month.isoformat(),
            "currency": mark.currency,
            "requested_hour_utc": mark.requested_hour_utc.isoformat(),
            "observed_at_utc": mark.observed_at_utc.isoformat(),
            "source_url": mark.source_url,
            "raw_sha256": mark.raw_sha256,
            "raw_bytes": mark.raw_bytes,
        }
        for mark in marks
    ]
    _write_csv(
        evidence_root / "source_manifest.csv", tuple(source_rows[0]), source_rows
    )
    _write_json(
        evidence_root / "input_manifest.json",
        {
            "config_sha256": sha256_file(config_path),
            "contract_sha256": sha256_file(
                root / "docs/MODELED_EXECUTION_POC_CONTRACT.md"
            ),
            "trial_registry_sha256": sha256_file(root / "config/trial_registry.jsonl"),
            "monthly_marks_sha256": sha256_file(interim_marks),
            "phase02_reference_changes_sha256": sha256_file(
                reference_changes_path
            ),
            "raw_snapshot_count": len(marks),
            "raw_snapshot_chain_sha256": hashlib.sha256(
                "\n".join(mark.raw_sha256 for mark in marks).encode()
            ).hexdigest(),
        },
    )
    annual = cast(float, base_metrics["annualized_arithmetic_mean"])
    gross_annual = cast(float, base_metrics["gross_annualized_arithmetic_mean"])
    annual_cost = cast(
        float, base_metrics["annualized_modeled_transaction_cost"]
    )
    interval_low = cast(float, base_metrics["mean_monthly_ci_low"])
    interval_high = cast(float, base_metrics["mean_monthly_ci_high"])
    cumulative = cast(float, base_metrics["cumulative_compounded_return"])
    drawdown = cast(float, base_metrics["maximum_drawdown"])
    sharpe_value = base_metrics["annualized_sharpe_zero_rate"]
    sharpe_text = (
        "null" if sharpe_value is None else f"{cast(float, sharpe_value):.2f}"
    )
    favorable_metrics = next(
        row
        for row in metric_rows
        if row["scenario"] == "FAVORABLE"
        and row["strategy"] == PocStrategy.PRIMARY.value
    )
    adverse_metrics = next(
        row
        for row in metric_rows
        if row["scenario"] == "ADVERSE"
        and row["strategy"] == PocStrategy.PRIMARY.value
    )
    favorable_annual = cast(
        float, favorable_metrics["annualized_arithmetic_mean"]
    )
    adverse_annual = cast(float, adverse_metrics["annualized_arithmetic_mean"])
    paired_mean = cast(float, paired_control["mean_monthly_difference"])
    paired_ci_low = cast(float, paired_control["mean_monthly_difference_ci_low"])
    paired_ci_high = cast(float, paired_control["mean_monthly_difference_ci_high"])
    positive_eras = sum(cast(float, row["mean_monthly"]) > 0 for row in era_rows)
    nonpositive_loo = sum(
        cast(float, row["mean_monthly"]) <= 0 for row in loo_rows
    )
    min_correlation = min(
        cast(float, row["pearson_correlation"]) for row in cross_source_rows
    )
    min_sign_agreement = min(
        cast(float, row["sign_agreement_fraction"]) for row in cross_source_rows
    )
    report = f"""# Phase 07 - Modeled execution POC

Status: `POC_DIAGNOSTIC_ONLY`

Directional finding: `{directional_finding}`

## Result

The 12-month spot-price trend rule was evaluated over {len(base_primary)}
synchronized portfolio months using {len(marks)} Dukascopy month-end marks.
Under the frozen base spread, commission, and slippage assumptions, its
annualized arithmetic return before financing is {annual:.2%}, versus a gross
spot-price return of {gross_annual:.2%}. Modeled transaction costs remove
{annual_cost:.2%} per year. The zero-rate annualized Sharpe is {sharpe_text},
the cumulative compounded return is {cumulative:.2%}, and maximum drawdown is
{drawdown:.2%}.

The 95% moving-block interval for monthly mean return is
[{interval_low:.2%}, {interval_high:.2%}], which includes zero. The paired
primary-minus-B1 mean is {paired_mean:.2%} per month with interval
[{paired_ci_low:.2%}, {paired_ci_high:.2%}]. Favorable and adverse execution
assumptions produce annualized means of {favorable_annual:.2%} and
{adverse_annual:.2%}; costs do not explain the negative gross result.

Only {positive_eras}/{len(era_rows)} predefined eras have a positive point
estimate, and {nonpositive_loo}/{len(loo_rows)} leave-one-currency-out
portfolios are non-positive. Cross-source validation against the independent
BIS panel remains positive for every currency: minimum monthly-return
correlation {min_correlation:.3f} and minimum sign agreement
{min_sign_agreement:.1%}.

The moving-block interval and all alternative cost scenarios are recorded in
`strategy_metrics.csv`. The paired primary-minus-B1 result is recorded in
`paired_control.json`; predefined eras, instrument metrics, and
leave-one-currency-out diagnostics are also committed.

## Boundary

This is not an Exness historical backtest. Prices come from Dukascopy and the
Exness Raw-like spread table is a manual simulation assumption, not measured
account history. Swap and financing are absent, so every modeled net field is
explicitly before financing.

The historical v1 decision remains `NOT_TESTED`, and Phase 06 remains inactive.
"""
    (evidence_root / "REPORT.md").write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )
    _manifest(evidence_root, config.registered_at_utc)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/modeled_execution_poc_v0_1.json"),
    )
    parser.add_argument(
        "--raw-root", type=Path, default=Path("data/raw/phase07/dukascopy")
    )
    parser.add_argument(
        "--interim-root", type=Path, default=Path("data/interim/phase07")
    )
    parser.add_argument(
        "--evidence-root", type=Path, default=Path("evidence/phase07")
    )
    parser.add_argument(
        "--phase02-reference",
        type=Path,
        default=Path("data/interim/phase02/monthly_reference_changes.csv"),
    )
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    summary = run_phase07(
        root=Path.cwd(),
        config_path=args.config,
        raw_root=args.raw_root,
        interim_root=args.interim_root,
        evidence_root=args.evidence_root,
        reference_changes_path=args.phase02_reference,
        offline=args.offline,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
