"""Immutable canonical schemas shared by mechanical-research phases."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum


class SchemaError(ValueError):
    """A canonical record violates a frozen invariant."""


class ClaimScope(StrEnum):
    """Maximum claim supported by the source record."""

    PREDICTABILITY_ONLY = "PREDICTABILITY_ONLY"
    EXECUTABLE_TOTAL_RETURN = "EXECUTABLE_TOTAL_RETURN"


class InstrumentKind(StrEnum):
    """Permitted primary instrument representations."""

    REFERENCE_SPOT = "REFERENCE_SPOT"
    BROKER_SPOT = "BROKER_SPOT"
    FORWARD = "FORWARD"
    FUTURE = "FUTURE"


def _positive_finite(value: float, field: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise SchemaError(f"{field} must be positive and finite")


def _finite(value: float, field: str) -> None:
    if not math.isfinite(value):
        raise SchemaError(f"{field} must be finite")


def _aware_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise SchemaError(f"{field} must be timezone-aware UTC")


@dataclass(frozen=True)
class InstrumentContract:
    """Tradable or diagnostic instrument identity and quote convention."""

    instrument_id: str
    currency: str
    kind: InstrumentKind
    quote_orientation: str
    claim_scope: ClaimScope

    def __post_init__(self) -> None:
        if not self.instrument_id or len(self.currency) != 3:
            raise SchemaError("instrument identity is invalid")
        if self.quote_orientation not in {
            "CURRENCY_PER_USD",
            "USD_PER_CURRENCY",
        }:
            raise SchemaError("unsupported quote orientation")


@dataclass(frozen=True)
class RawMarketObservation:
    """Provider-native mark with distinct observation and availability times."""

    source_id: str
    instrument_id: str
    currency: str
    observed_at_utc: datetime
    available_at_utc: datetime
    raw_value: float
    raw_orientation: str
    source_status: str

    def __post_init__(self) -> None:
        if not self.source_id or not self.instrument_id:
            raise SchemaError("source and instrument identifiers are required")
        _aware_utc(self.observed_at_utc, "observed_at_utc")
        _aware_utc(self.available_at_utc, "available_at_utc")
        if self.available_at_utc < self.observed_at_utc:
            raise SchemaError("availability cannot precede observation")
        _positive_finite(self.raw_value, "raw_value")


@dataclass(frozen=True)
class CanonicalDailyMark:
    """One normalized USD-per-currency reference mark."""

    source_id: str
    instrument_id: str
    currency: str
    observed_date: date
    observed_at_utc: datetime
    available_at_utc: datetime
    usd_per_currency: float
    claim_scope: ClaimScope

    def __post_init__(self) -> None:
        _aware_utc(self.observed_at_utc, "observed_at_utc")
        _aware_utc(self.available_at_utc, "available_at_utc")
        if self.observed_at_utc.date() != self.observed_date:
            raise SchemaError("observed date and timestamp disagree")
        if self.available_at_utc < self.observed_at_utc:
            raise SchemaError("availability cannot precede observation")
        _positive_finite(self.usd_per_currency, "usd_per_currency")


@dataclass(frozen=True)
class MonthlyReferenceChange:
    """Non-executable price change between two causal monthly marks."""

    currency: str
    month: date
    start_mark_date: date
    end_mark_date: date
    simple_change: float
    claim_scope: ClaimScope = ClaimScope.PREDICTABILITY_ONLY

    def __post_init__(self) -> None:
        if self.month.day != 1:
            raise SchemaError("month must be represented by its first date")
        if self.end_mark_date <= self.start_mark_date:
            raise SchemaError("monthly mark dates must increase")
        _finite(self.simple_change, "simple_change")
        if self.claim_scope is not ClaimScope.PREDICTABILITY_ONLY:
            raise SchemaError("reference change cannot be labelled executable")


@dataclass(frozen=True)
class ContractRollEvent:
    """Explicit futures roll needed by an executable chain."""

    instrument_id: str
    roll_date: date
    from_contract: str
    to_contract: str
    roll_cost_return: float

    def __post_init__(self) -> None:
        if not self.from_contract or not self.to_contract:
            raise SchemaError("both roll legs are required")
        if self.from_contract == self.to_contract:
            raise SchemaError("roll legs must differ")
        _finite(self.roll_cost_return, "roll_cost_return")


@dataclass(frozen=True)
class FinancingObservation:
    """Holding debit or credit for a broker/forward implementation."""

    instrument_id: str
    effective_date: date
    long_return: float
    short_return: float
    source_id: str

    def __post_init__(self) -> None:
        if not self.instrument_id or not self.source_id:
            raise SchemaError("financing identifiers are required")
        _finite(self.long_return, "long_return")
        _finite(self.short_return, "short_return")


@dataclass(frozen=True)
class TransactionCostObservation:
    """One-way trading-cost components in return units."""

    instrument_id: str
    effective_date: date
    half_spread_return: float
    commission_return: float
    slippage_return: float
    source_id: str

    def __post_init__(self) -> None:
        for field, value in (
            ("half_spread_return", self.half_spread_return),
            ("commission_return", self.commission_return),
            ("slippage_return", self.slippage_return),
        ):
            _finite(value, field)
            if value < 0:
                raise SchemaError(f"{field} cannot be negative")

    @property
    def total_one_way_return(self) -> float:
        return (
            self.half_spread_return
            + self.commission_return
            + self.slippage_return
        )


@dataclass(frozen=True)
class MonthlyTotalReturn:
    """Executable total return whose accounting identity must reconcile."""

    instrument_id: str
    month: date
    price_return: float
    financing_return: float
    roll_return: float
    spread_cost_return: float
    commission_cost_return: float
    slippage_cost_return: float
    net_total_return: float
    claim_scope: ClaimScope

    def __post_init__(self) -> None:
        if self.month.day != 1:
            raise SchemaError("month must be represented by its first date")
        if self.claim_scope is not ClaimScope.EXECUTABLE_TOTAL_RETURN:
            raise SchemaError("monthly total return requires executable evidence")
        values = (
            self.price_return,
            self.financing_return,
            self.roll_return,
            self.spread_cost_return,
            self.commission_cost_return,
            self.slippage_cost_return,
            self.net_total_return,
        )
        if not all(math.isfinite(value) for value in values):
            raise SchemaError("monthly total-return components must be finite")
        if any(
            value < 0
            for value in (
                self.spread_cost_return,
                self.commission_cost_return,
                self.slippage_cost_return,
            )
        ):
            raise SchemaError("cost components cannot be negative")
        expected = (
            self.price_return
            + self.financing_return
            + self.roll_return
            - self.spread_cost_return
            - self.commission_cost_return
            - self.slippage_cost_return
        )
        if not math.isclose(expected, self.net_total_return, abs_tol=1e-12):
            raise SchemaError("monthly total-return accounting identity failed")
