from __future__ import annotations

from datetime import date

import pytest

from fx_mechanical_research.schemas import (
    ClaimScope,
    MonthlyTotalReturn,
    SchemaError,
    TransactionCostObservation,
)


def test_transaction_cost_identity() -> None:
    cost = TransactionCostObservation(
        instrument_id="TEST",
        effective_date=date(2024, 1, 1),
        half_spread_return=0.001,
        commission_return=0.0002,
        slippage_return=0.0003,
        source_id="fixture",
    )

    assert cost.total_one_way_return == pytest.approx(0.0015)


def test_total_return_requires_executable_scope() -> None:
    with pytest.raises(SchemaError, match="requires executable evidence"):
        MonthlyTotalReturn(
            instrument_id="TEST",
            month=date(2024, 1, 1),
            price_return=0.02,
            financing_return=0.001,
            roll_return=0.0,
            spread_cost_return=0.0005,
            commission_cost_return=0.0002,
            slippage_cost_return=0.0003,
            net_total_return=0.02,
            claim_scope=ClaimScope.PREDICTABILITY_ONLY,
        )


def test_total_return_accounting_must_reconcile() -> None:
    with pytest.raises(SchemaError, match="accounting identity"):
        MonthlyTotalReturn(
            instrument_id="TEST",
            month=date(2024, 1, 1),
            price_return=0.02,
            financing_return=0.001,
            roll_return=0.0,
            spread_cost_return=0.0005,
            commission_cost_return=0.0002,
            slippage_cost_return=0.0003,
            net_total_return=0.5,
            claim_scope=ClaimScope.EXECUTABLE_TOTAL_RETURN,
        )


def test_total_return_accepts_reconciled_executable_record() -> None:
    record = MonthlyTotalReturn(
        instrument_id="TEST",
        month=date(2024, 1, 1),
        price_return=0.02,
        financing_return=0.001,
        roll_return=0.0,
        spread_cost_return=0.0005,
        commission_cost_return=0.0002,
        slippage_cost_return=0.0003,
        net_total_return=0.02,
        claim_scope=ClaimScope.EXECUTABLE_TOTAL_RETURN,
    )

    assert record.net_total_return == 0.02
