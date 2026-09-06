# Research Decision Contract — TSMOM v1

Status: frozen before source qualification and strategy-return evaluation

Contract version: 0.1

Frozen on: 2026-09-06

## 1. Research question

Does a pre-specified 12-month time-series momentum signal produce positive and
incremental net returns across a diversified G10 currency universe at monthly
frequency, after costs and after controlling for simpler sources of apparent
performance?

The unit of evidence is the synchronized currency portfolio and its monthly
return history. USDJPY is a constituent and diagnostic, not the approval unit.

## 2. Claim boundary

TSMOM v1 tests a slow price-based strategy. It does not test:

- a general claim that technical analysis works;
- intraday breakout, reversal, liquidity sweep, SMC, or price-action setups;
- a fundamental directional filter;
- optimal leverage or portfolio allocation;
- readiness for live capital.

## 3. Evidence history and contamination statement

Earlier repositories accessed and analyzed parts of 2024–2026 FX history for
other hypotheses. Therefore:

- no past window is described as untouched;
- historical splits are construction and validation evidence only;
- the exact feasible periods are set in Phase 01 from source coverage, without
  reference to strategy returns;
- a genuine prospective lockbox starts only after the v1 implementation,
  configuration, tests, input manifest, and strategy hash are frozen.

No TSMOM v1 PnL was computed before this contract was written.

## 4. Instrument and data gate

The preferred evidence is from tradable currency futures, forwards, or a broker
instrument with sufficient historical cost and financing information. Phase 01
must choose exactly one primary implementation before return evaluation.

For a PnL claim, every instrument requires:

```text
instrument identifier and contract convention
price orientation and USD normalization
decision and execution timestamps
bid/ask or defensible historical transaction-cost model
commission
roll or contract-chain rule
financing/swap where applicable
holiday and missing-observation rules
source terms, retrieval timestamp, and SHA-256
```

Official reference or mid-price data without executable cost history may support
only a predictability study. It cannot produce `PROCEED_TO_PROSPECTIVE_OBSERVATION_TSMOM_V1`.

## 5. Frozen primary strategy

For instrument `i` at the final eligible observation of month `t`:

```text
trailing_return_12m[i,t]
    = total return from the final eligible mark of t-12 to t

signal[i,t]
    = +1 if trailing_return_12m[i,t] > 0
    = -1 if trailing_return_12m[i,t] < 0
    =  0 if it is zero or unavailable

gross_strategy_return[i,t+1]
    = signal[i,t] * total_return[i,t+1]
```

The portfolio is the equal-weight mean of all eligible currency-instrument
returns. Primary exposure is unscaled. No skip month, neutral band, trend
strength threshold, stop loss, take profit, or regime filter is permitted.

The lookback and next-month return use information available at the decision
timestamp. Revised or back-adjusted data must be versioned and shown not to move
historical decisions unexpectedly.

## 6. Costs

Net return deducts every cost caused by a position change, contract roll, and
holding mechanism. Costs may vary by instrument and time if supported by source
data; otherwise a conservative frozen schedule and sensitivity band are required.

The report must include:

- gross and net returns;
- turnover;
- cost by spread, commission, roll, financing, and slippage component;
- break-even one-way cost;
- missing-cost exclusions; and
- results at registered base, favorable, and adverse cost assumptions.

The base cost is selected from source evidence before strategy outcomes. A
favorable-cost result cannot rescue failure at the base cost.

## 7. Baselines and matched controls

### B0 — Cash

Zero active currency exposure and zero excess return.

### B1 — Expanding historical mean sign

For each instrument, take the sign of the expanding mean return estimated only
from data available before the decision. This control tests the critique that
TSMOM performance can resemble a strategy based on unconditional mean premia.

### B2 — Static exposure controls

Always-long and always-short currency baskets, using the same instruments,
weights, holding timestamps, and costs where the comparison is meaningful.

### B3 — Volatility-scaled diagnostic

Apply a past-only volatility target to TSMOM and every matched control. Scaling
may change risk but cannot be credited as evidence for the return-sign signal.

### B4 — Placebo signals

Circularly shift or block-randomize signals without breaking cross-currency
calendar dependence. Placebos estimate how often the observed result could arise
without the proposed timing relationship.

## 8. Registered hypotheses

### `TSMOM_H1_NET_PORTFOLIO`

The primary unscaled portfolio has positive mean net return in the historical
validation sample. Supported only when the two-sided 95% moving-block bootstrap
interval for mean net return lies wholly above zero.

### `TSMOM_H2_INCREMENTAL_SIGNAL`

TSMOM adds information beyond B1. Supported only when the two-sided 95% paired
moving-block bootstrap interval for `TSMOM net return - B1 net return` lies
wholly above zero.

### `TSMOM_H3_MULTIPLE_TESTING`

The primary strategy is superior to the registered benchmark family after a
White Reality Check or Hansen SPA procedure at family-wise `alpha = 0.05`.

### `TSMOM_H4_BREADTH_AND_TIME_STABILITY`

The expected sign must remain positive in every predefined validation era and
every leave-one-currency-out portfolio. Confidence intervals are reported but
are not required to exclude zero separately in each lower-powered slice.

### `TSMOM_H5_COST_CAPACITY`

The lower bound of the bootstrap interval for break-even one-way cost must
exceed the registered base one-way cost. This tests whether the edge has cost
headroom rather than surviving only at a point estimate.

## 9. Secondary diagnostics

The following cannot overturn a failed primary gate:

- 1-, 3-, and 6-month lookbacks;
- volatility-scaled results;
- individual pair results;
- gross returns;
- alternative favorable costs;
- selected subperiods;
- cross-sectional currency momentum.

They are reported to explain failure or motivate a new preregistration.

## 10. Statistical contract

- Primary time unit: synchronized calendar month.
- Dependence unit: the whole cross-currency month, never individual pair rows.
- Inference: circular moving-block bootstrap over month clusters.
- Block length: selected mechanically from return dependence in Phase 02 and
  frozen before strategy evaluation; a 3-, 6-, and 12-month sensitivity is
  reported.
- Resamples: at least 10,000 with a frozen seed.
- Point estimates and two-sided 95% percentile intervals are always reported.
- All attempted strategy IDs, parameters, and run hashes enter an append-only
  trial registry, including failed and abandoned runs.
- Family-wide inference includes every outcome-inspected strategy variant.
- PBO/CSCV is reported when the number and structure of tried configurations
  make it identifiable; it is not used to erase the trial history.

## 11. Historical research gate

The result is `PROCEED_TO_PROSPECTIVE_OBSERVATION_TSMOM_V1` only when:

1. executable total-return and cost data pass Phase 01;
2. `TSMOM_H1_NET_PORTFOLIO` through `TSMOM_H5_COST_CAPACITY` are all supported;
3. no timestamp, orientation, roll, cost, or missing-data integrity gate fails;
4. diagnostics do not reveal a coding or data artifact; and
5. the complete code, configuration, inputs, tests, trial registry, and manifest
   are hash-frozen before the prospective start timestamp.

A mandatory failure produces `DO_NOT_PROCEED_WITH_TSMOM_V1`. Inadequate data or
an unexecutable price-only study produces `NOT_TESTED` for the trading claim.

## 12. Prospective gate

Passing historical research authorizes observation, not trading. Prospective
evidence begins after the frozen timestamp and runs without parameter changes.
Its minimum duration and required number of independent monthly observations
must be determined by a power analysis based on the frozen historical effect,
then rounded upward. This rule avoids inventing a convenient calendar threshold.

Any modification creates v2, preserves v1, and starts a new prospective clock.

## 13. Change control

After freeze, a change to the primary universe, instrument type, signal,
lookback, holding period, weight, cost base, comparator, inference, or gate
requires:

1. a dated amendment written before inspecting the affected outcome;
2. a reason independent of strategy performance;
3. a new hypothesis/version identifier if the tested claim changes; and
4. preservation of the original result without relabeling it exploratory.
