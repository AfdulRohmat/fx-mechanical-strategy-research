"""Minimal, fail-closed Dukascopy JETTA monthly tick adapter."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

API_BASE_URL = "https://jetta.dukascopy.com/v1"
ALLOWED_HOST = "jetta.dukascopy.com"
PARSER_VERSION = "dukascopy-jetta-delta-json-v1"


class DukascopyMonthlyError(RuntimeError):
    """A source payload or monthly selection violates its contract."""


@dataclass(frozen=True)
class LastTick:
    observed_at_utc: datetime
    bid: float
    ask: float


@dataclass(frozen=True)
class SelectedMonthlyTick:
    currency: str
    symbol: str
    instrument_code: str
    month: date
    requested_hour_utc: datetime
    observed_at_utc: datetime
    bid: float
    ask: float
    raw_mid: float
    normalized_mid: float
    native_spread_pips: float
    source_url: str
    raw_path: Path
    raw_sha256: str
    raw_bytes: int


def tick_url(instrument_code: str, hour_utc: datetime) -> str:
    """Return the one-based JETTA path used by Dukascopy's export widget."""

    if hour_utc.tzinfo is None or hour_utc.utcoffset() is None:
        raise ValueError("Dukascopy request hour must be timezone-aware")
    hour = hour_utc.astimezone(UTC)
    if hour.minute or hour.second or hour.microsecond:
        raise ValueError("Dukascopy request must be an exact UTC hour")
    pieces = instrument_code.split("-")
    if len(pieces) != 2 or any(len(piece) != 3 for piece in pieces):
        raise ValueError(f"invalid Dukascopy instrument code: {instrument_code}")
    return (
        f"{API_BASE_URL}/ticks/{instrument_code}/"
        f"{hour.year}/{hour.month}/{hour.day}/{hour.hour}"
    )


def _numeric_array(document: dict[str, object], field: str) -> list[int | float]:
    value = document.get(field)
    if not isinstance(value, list):
        raise DukascopyMonthlyError(f"{field} must be an array")
    result = cast(list[object], value)
    if any(
        isinstance(item, bool)
        or not isinstance(item, int | float)
        or not math.isfinite(item)
        for item in result
    ):
        raise DukascopyMonthlyError(f"{field} must contain finite numbers")
    return cast(list[int | float], result)


def _decimal(document: dict[str, object], field: str) -> Decimal:
    value = document.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DukascopyMonthlyError(f"{field} must be numeric")
    result = Decimal(str(value))
    if not result.is_finite():
        raise DukascopyMonthlyError(f"{field} must be finite")
    return result


def parse_last_tick(payload: bytes, requested_hour_utc: datetime) -> LastTick | None:
    """Validate a delta payload and decode only its final tick."""

    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DukascopyMonthlyError("tick payload is not valid JSON") from exc
    if not isinstance(decoded, dict):
        raise DukascopyMonthlyError("tick payload must be an object")
    document = cast(dict[str, object], decoded)
    times = _numeric_array(document, "times")
    bids = _numeric_array(document, "bids")
    asks = _numeric_array(document, "asks")
    lengths = {len(times), len(bids), len(asks)}
    if len(lengths) != 1:
        raise DukascopyMonthlyError("tick arrays have inconsistent lengths")
    if not times:
        return None
    if any(not isinstance(value, int) or value < 0 for value in times):
        raise DukascopyMonthlyError("time deltas must be non-negative integers")
    if any(not isinstance(value, int) for value in (*bids, *asks)):
        raise DukascopyMonthlyError("price deltas must be integers")
    timestamp = document.get("timestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int):
        raise DukascopyMonthlyError("base timestamp must be integer milliseconds")
    hour = requested_hour_utc.astimezone(UTC)
    expected_timestamp = int(hour.timestamp() * 1000)
    if timestamp != expected_timestamp:
        raise DukascopyMonthlyError("base timestamp does not match request hour")
    multiplier = _decimal(document, "multiplier")
    bid = _decimal(document, "bid")
    ask = _decimal(document, "ask")
    if multiplier <= 0 or bid <= 0 or ask < bid:
        raise DukascopyMonthlyError("invalid base quote or multiplier")
    elapsed_ms = 0
    for time_delta, bid_delta, ask_delta in zip(times, bids, asks, strict=True):
        elapsed_ms += int(time_delta)
        bid += Decimal(int(bid_delta)) * multiplier
        ask += Decimal(int(ask_delta)) * multiplier
        if bid <= 0 or ask < bid:
            raise DukascopyMonthlyError("decoded quote is invalid")
    if elapsed_ms >= 3_600_000:
        raise DukascopyMonthlyError("decoded tick falls outside request hour")
    observed = datetime.fromtimestamp((timestamp + elapsed_ms) / 1000, UTC)
    return LastTick(observed_at_utc=observed, bid=float(bid), ask=float(ask))


def _fetch_payload(url: str, *, timeout_seconds: float, retries: int) -> bytes | None:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "fx-mechanical-strategy-research/0.1",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                final = urlparse(response.geturl())
                if final.hostname != ALLOWED_HOST or not final.path.startswith(
                    "/v1/ticks/"
                ):
                    raise DukascopyMonthlyError("unexpected source redirect")
                if response.status == 204:
                    return None
                if response.status != 200:
                    raise DukascopyMonthlyError(
                        f"unexpected HTTP status: {response.status}"
                    )
                return bytes(response.read())
        except HTTPError as exc:
            if exc.code in {404, 410}:
                return None
            last_error = exc
        except (URLError, TimeoutError, DukascopyMonthlyError) as exc:
            last_error = exc
        if attempt + 1 < retries:
            time.sleep(min(2**attempt, 8))
    raise DukascopyMonthlyError(f"failed to fetch {url}: {last_error}") from last_error


def _cache_paths(raw_root: Path, code: str, hour: datetime) -> tuple[Path, Path]:
    directory = raw_root / code / hour.strftime("%Y-%m-%d")
    return directory / f"{hour:%H}.payload.json", directory / f"{hour:%H}.no_data"


def load_or_fetch_hour(
    raw_root: Path,
    instrument_code: str,
    hour_utc: datetime,
    *,
    offline: bool,
    timeout_seconds: float = 30.0,
    retries: int = 6,
) -> tuple[LastTick | None, Path | None, bytes | None]:
    """Return a cached/fetched last tick and immutable raw payload."""

    payload_path, missing_path = _cache_paths(raw_root, instrument_code, hour_utc)
    if payload_path.is_file():
        payload = payload_path.read_bytes()
        return parse_last_tick(payload, hour_utc), payload_path, payload
    if missing_path.is_file():
        return None, None, None
    if offline:
        url = tick_url(instrument_code, hour_utc)
        raise DukascopyMonthlyError(f"offline cache miss: {url}")
    url = tick_url(instrument_code, hour_utc)
    fetched_payload = _fetch_payload(
        url,
        timeout_seconds=timeout_seconds,
        retries=retries,
    )
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    if fetched_payload is None:
        missing_path.write_text("NO_DATA\n", encoding="utf-8", newline="\n")
        return None, None, None
    tick = parse_last_tick(fetched_payload, hour_utc)
    payload_path.write_bytes(fetched_payload)
    if tick is None:
        return None, payload_path, fetched_payload
    return tick, payload_path, fetched_payload


def select_monthly_tick(
    *,
    raw_root: Path,
    currency: str,
    symbol: str,
    instrument_code: str,
    month: date,
    execution_hour_utc: int,
    maximum_lookback_days: int,
    pip_size: float,
    invert: bool,
    offline: bool,
) -> SelectedMonthlyTick:
    """Select the first non-empty backward hour at a fixed UTC clock time."""

    if month.day != 1:
        raise ValueError("month must be represented by its first day")
    next_month = (
        date(month.year + 1, 1, 1)
        if month.month == 12
        else date(month.year, month.month + 1, 1)
    )
    last_day = next_month - timedelta(days=1)
    for offset in range(maximum_lookback_days + 1):
        candidate_day = last_day - timedelta(days=offset)
        hour = datetime(
            candidate_day.year,
            candidate_day.month,
            candidate_day.day,
            execution_hour_utc,
            tzinfo=UTC,
        )
        tick, raw_path, payload = load_or_fetch_hour(
            raw_root,
            instrument_code,
            hour,
            offline=offline,
        )
        if tick is None or raw_path is None or payload is None:
            continue
        raw_mid = (tick.bid + tick.ask) / 2
        normalized = 1 / raw_mid if invert else raw_mid
        return SelectedMonthlyTick(
            currency=currency,
            symbol=symbol,
            instrument_code=instrument_code,
            month=month,
            requested_hour_utc=hour,
            observed_at_utc=tick.observed_at_utc,
            bid=tick.bid,
            ask=tick.ask,
            raw_mid=raw_mid,
            normalized_mid=normalized,
            native_spread_pips=(tick.ask - tick.bid) / pip_size,
            source_url=tick_url(instrument_code, hour),
            raw_path=raw_path,
            raw_sha256=hashlib.sha256(payload).hexdigest(),
            raw_bytes=len(payload),
        )
    raise DukascopyMonthlyError(
        f"no quote for {instrument_code} {month:%Y-%m} within lookback"
    )
