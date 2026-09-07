# Modeled execution POC contract

Status: frozen before Dukascopy strategy-return construction

POC ID: `TSMOM_DUKASCOPY_EXNESS_RAW_COST_POC_V0_1`

## Question

Does the frozen 12-month G10 spot-price trend signal remain directionally
interesting after a manually assumed Exness Raw-like spread, commission, and
slippage model over 2010–2024?

This is an exploratory simulation after the historical v1 decision. It does not
replace or amend the v1 result, which remains `NOT_TESTED`.

## Data and timestamp

- Provider: Dukascopy JETTA tick history.
- Universe: AUD, CAD, CHF, EUR, GBP, JPY, NOK, NZD, and SEK versus USD.
- Observation: final tick in the 16:00–16:59 UTC hour on the last available day
  at or before calendar month-end.
- Holiday fallback: search backward at most seven calendar days.
- Sample: January 2010 through December 2024.
- Quotes are normalized to USD per foreign-currency unit.

The source format was inspected before registration to validate the adapter.
No candidate return, signal, or portfolio outcome was calculated before this
contract.

## Strategy

The signal is the sign of the compounded prior-12-month spot-price return. It is
applied to the following one-month spot-price change. Currency legs are equally
weighted and unscaled. B0–B2 controls use the same alignment and cost model.

This differs from v1 in one material way: the input is spot-price change, not
total return. The POC therefore cannot evaluate the frozen v1 H1–H5 hypotheses.

## Manual cost assumptions

The spread table is an explicit simulation assumption authorized by the user.
It is not represented as a measured historical Exness account record. The base
values in pips are:

| Pair | Spread | Slippage |
|---|---:|---:|
| EURUSD | 0.1 | 0.10 |
| GBPUSD | 0.2 | 0.15 |
| AUDUSD | 0.2 | 0.10 |
| NZDUSD | 0.4 | 0.15 |
| USDJPY | 0.2 | 0.10 |
| USDCAD | 0.3 | 0.10 |
| USDCHF | 0.3 | 0.10 |
| USDNOK | 12.0 | 2.00 |
| USDSEK | 12.0 | 2.00 |

Commission is USD 3.50 per standard lot per side. The model converts this to a
return on USD notional using the contemporaneous quote. Native Dukascopy spread
is recorded for audit but not charged, avoiding double-counting when the manual
Exness-like spread is applied.

Cost scenarios are frozen as:

- favorable: 0.75 times base spread and zero slippage;
- base: base spread and base slippage;
- adverse: two times base spread and two times base slippage.

Turnover is `abs(current_position - previous_position)`. Opening or closing one
unit incurs one one-way cost; reversing from long to short incurs two.

## Missing financing boundary

Swap, tom-next carry, and financing are excluded. All modeled “net” fields must
say `before_financing`. The POC may describe price predictability and
transaction-cost sensitivity but may not claim net trading profitability.

## Frozen statistics

- synchronized monthly portfolio unit;
- 10-month circular moving-block bootstrap;
- 10,000 resamples with seed 20260907;
- annualized arithmetic mean, volatility, Sharpe, maximum drawdown, and hit
  rate;
- paired primary-minus-B1 mean and bootstrap interval;
- predefined eras and leave-one-currency-out diagnostics.

## Permitted conclusion

The only status is `POC_DIAGNOSTIC_ONLY`. Favorable results cannot activate the
prospective Phase 06, change the v1 `NOT_TESTED` decision, or be called an
Exness historical backtest.
