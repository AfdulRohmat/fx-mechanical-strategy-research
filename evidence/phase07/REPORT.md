# Phase 07 - Modeled execution POC

Status: `POC_DIAGNOSTIC_ONLY`

Directional finding: `NON_POSITIVE_POINT_ESTIMATE`

## Result

The 12-month spot-price trend rule was evaluated over 167
synchronized portfolio months using 1620 Dukascopy month-end marks.
Under the frozen base spread, commission, and slippage assumptions, its
annualized arithmetic return before financing is -1.02%, versus a gross
spot-price return of -0.99%. Modeled transaction costs remove
0.03% per year. The zero-rate annualized Sharpe is -0.16,
the cumulative compounded return is -15.54%, and maximum drawdown is
-23.62%.

The 95% moving-block interval for monthly mean return is
[-0.31%, 0.16%], which includes zero. The paired
primary-minus-B1 mean is -0.08% per month with interval
[-0.30%, 0.13%]. Favorable and adverse execution
assumptions produce annualized means of -1.01% and
-1.04%; costs do not explain the negative gross result.

Only 1/3 predefined eras have a positive point
estimate, and 9/9 leave-one-currency-out
portfolios are non-positive. Cross-source validation against the independent
BIS panel remains positive for every currency: minimum monthly-return
correlation 0.697 and minimum sign agreement
73.7%.

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
