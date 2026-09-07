from __future__ import annotations

import json
from datetime import UTC, date, datetime
from itertools import pairwise
from pathlib import Path

import pytest

from fx_mechanical_research.dukascopy_monthly import (
    DukascopyMonthlyError,
    SelectedMonthlyTick,
    parse_last_tick,
    select_monthly_tick,
    tick_url,
)
from fx_mechanical_research.phase07_poc import (
    ModeledPocError,
    PocStrategy,
    build_monthly_inputs,
    build_strategy_rows,
    cross_source_audit,
    load_poc_config,
    moving_block_mean_interval,
)

CONFIG_PATH = Path("config/modeled_execution_poc_v0_1.json")


def _payload(hour: datetime, *, bid: float = 150.0, ask: float = 150.002) -> bytes:
    return json.dumps(
        {
            "timestamp": int(hour.timestamp() * 1000),
            "multiplier": 0.001,
            "bid": bid,
            "ask": ask,
            "times": [100, 200],
            "bids": [1, -1],
            "asks": [1, 1],
            "bidVolumes": [1.0, 1.0],
            "askVolumes": [1.0, 1.0],
        },
        separators=(",", ":"),
    ).encode()


def _months(count: int) -> tuple[date, ...]:
    months: list[date] = []
    cursor = date(2020, 1, 1)
    for _ in range(count):
        months.append(cursor)
        cursor = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
    return tuple(months)


def _synthetic_marks() -> tuple[SelectedMonthlyTick, ...]:
    config = load_poc_config(CONFIG_PATH)
    output: list[SelectedMonthlyTick] = []
    for instrument in config.instruments:
        for index, month in enumerate(_months(14)):
            normalized = 1.01**index
            if index == 13:
                normalized *= 0.8
            raw_mid = 1 / normalized if instrument.invert else normalized
            hour = datetime(month.year, month.month, 28, 16, tzinfo=UTC)
            output.append(
                SelectedMonthlyTick(
                    currency=instrument.currency,
                    symbol=instrument.symbol,
                    instrument_code=instrument.dukascopy_code,
                    month=month,
                    requested_hour_utc=hour,
                    observed_at_utc=hour,
                    bid=raw_mid - instrument.pip_size,
                    ask=raw_mid + instrument.pip_size,
                    raw_mid=raw_mid,
                    normalized_mid=normalized,
                    native_spread_pips=2.0,
                    source_url="https://jetta.dukascopy.com/v1/ticks/test",
                    raw_path=Path("unused"),
                    raw_sha256="a" * 64,
                    raw_bytes=100,
                )
            )
    output.sort(key=lambda item: (item.month, item.currency))
    return tuple(output)


def test_tick_parser_decodes_delta_payload_and_one_based_url() -> None:
    hour = datetime(2024, 1, 31, 16, tzinfo=UTC)

    tick = parse_last_tick(_payload(hour), hour)

    assert tick is not None
    assert tick.observed_at_utc == hour.replace(microsecond=300_000)
    assert tick.bid == pytest.approx(150.0)
    assert tick.ask == pytest.approx(150.004)
    assert tick_url("USD-JPY", hour).endswith("/USD-JPY/2024/1/31/16")


def test_tick_parser_allows_intermediate_cross_but_rejects_crossed_final() -> None:
    hour = datetime(2024, 1, 31, 16, tzinfo=UTC)
    document = json.loads(_payload(hour, bid=150.0, ask=150.001))
    document["bids"] = [2, 0]
    document["asks"] = [0, 2]

    tick = parse_last_tick(json.dumps(document).encode(), hour)

    assert tick is not None
    assert tick.ask > tick.bid
    document["asks"] = [0, 0]
    with pytest.raises(DukascopyMonthlyError, match="final decoded quote is crossed"):
        parse_last_tick(json.dumps(document).encode(), hour)


def test_month_selector_uses_cached_backward_fallback_and_inverts(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw"
    no_data = raw_root / "USD-JPY" / "2024-01-31" / "16.no_data"
    no_data.parent.mkdir(parents=True)
    no_data.write_text("NO_DATA\n", encoding="utf-8")
    hour = datetime(2024, 1, 30, 16, tzinfo=UTC)
    payload_path = raw_root / "USD-JPY" / "2024-01-30" / "16.payload.json"
    payload_path.parent.mkdir(parents=True)
    payload_path.write_bytes(_payload(hour))

    selected = select_monthly_tick(
        raw_root=raw_root,
        currency="JPY",
        symbol="USDJPY",
        instrument_code="USD-JPY",
        month=date(2024, 1, 1),
        execution_hour_utc=16,
        maximum_lookback_days=7,
        pip_size=0.01,
        invert=True,
        offline=True,
    )

    assert selected.requested_hour_utc.date() == date(2024, 1, 30)
    assert selected.normalized_mid == pytest.approx(1 / selected.raw_mid)


def test_config_rejects_financing_or_v1_relabel(tmp_path: Path) -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    payload["cost_model"]["financing_included"] = True
    mutated = tmp_path / "poc.json"
    mutated.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModeledPocError, match="financing"):
        load_poc_config(mutated)


def test_primary_uses_prior_window_and_cost_scenarios_are_ordered() -> None:
    config = load_poc_config(CONFIG_PATH)
    marks = _synthetic_marks()
    scenario_inputs = {
        scenario.name: build_monthly_inputs(marks, config, scenario)
        for scenario in config.scenarios
    }

    costs = {
        name: next(row for row in rows if row.currency == "JPY").one_way_cost_return
        for name, rows in scenario_inputs.items()
    }
    assert costs["FAVORABLE"] < costs["BASE"] < costs["ADVERSE"]

    base = next(item for item in config.scenarios if item.name == "BASE")
    rows = build_strategy_rows(
        scenario_inputs["BASE"],
        config,
        base,
        PocStrategy.PRIMARY,
    )
    jpy = next(row for row in rows if row.currency == "JPY")
    assert jpy.month == date(2021, 2, 1)
    assert jpy.signal == 1
    assert jpy.spot_price_return < 0
    assert jpy.turnover_units == 1
    assert jpy.before_financing_return < jpy.gross_price_return


def test_block_bootstrap_is_deterministic() -> None:
    values = (0.01, -0.02, 0.03, 0.0, 0.01, -0.01)

    first = moving_block_mean_interval(values, block=3, resamples=500, seed=7)
    second = moving_block_mean_interval(values, block=3, resamples=500, seed=7)

    assert first == second
    assert first[0] <= first[1]


def test_cross_source_audit_detects_matching_orientation(tmp_path: Path) -> None:
    marks = _synthetic_marks()
    rows = ["currency,month,start_mark_date,end_mark_date,simple_change,claim_scope"]
    by_currency: dict[str, list[SelectedMonthlyTick]] = {}
    for mark in marks:
        by_currency.setdefault(mark.currency, []).append(mark)
    for currency, currency_marks in by_currency.items():
        currency_marks.sort(key=lambda item: item.month)
        for previous, current in pairwise(currency_marks):
            change = current.normalized_mid / previous.normalized_mid - 1
            rows.append(
                f"{currency},{current.month.isoformat()},x,x,{change},"
                "PREDICTABILITY_ONLY"
            )
    reference = tmp_path / "reference.csv"
    reference.write_text("\n".join(rows) + "\n", encoding="utf-8")

    audit = cross_source_audit(marks, reference)

    assert len(audit) == 9
    assert all(row["pearson_correlation"] == pytest.approx(1.0) for row in audit)
