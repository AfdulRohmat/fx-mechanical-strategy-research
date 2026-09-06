# Paper Backbone — Mechanical FX Research

Status: frozen before v1 source qualification and strategy-return evaluation

Version: 0.1

Frozen on: 2026-09-06

## 1. Executive conclusion

Among price-based mechanical FX ideas, the best-supported starting point is a
diversified, slow trend/momentum test. This is a *relative research prior*, not
proof of a deployable edge.

The literature imposes three important constraints:

1. evidence is stronger at the diversified portfolio or systematic-factor level
   than for one currency pair;
2. volatility scaling and long-run average premia can resemble time-series
   momentum, so the signal must beat matched controls; and
3. statistical predictability is not enough when bid/ask, roll, financing, and
   market access consume the return.

## 2. Evidence map

| ID | Evidence | Main result | What it does not establish | Decision impact |
|---|---|---|---|---|
| P01 | Moskowitz, Ooi, and Pedersen (2012), *Time Series Momentum* | Past returns positively predict returns over roughly 1–12 month horizons across 58 liquid futures; a diversified TSMOM portfolio performs strongly. | It does not prove a robust edge in a single FX pair or at intraday horizons. | Use slow TSMOM as the primary candidate and evaluate it as a portfolio. |
| P02 | Huang, Li, Wang, and Zhou (2020), *Time Series Momentum: Is It There?* | Asset-by-asset and bootstrap evidence is weak; the strategy behaves similarly to a historical-mean strategy that does not require return predictability. | It does not show every implementation is unprofitable. | Require an expanding historical-mean control and do not rely on pooled significance alone. |
| P03 | Kim, Tse, and Wald (2016), *Time Series Momentum and Volatility Scaling* | Much of reported TSMOM alpha can be attributed to volatility scaling. | It does not invalidate every unscaled trend signal. | Keep the primary signal unscaled; treat volatility scaling as a matched diagnostic. |
| P04 | Menkhoff, Sarno, Schmeling, and Schrimpf (2012), *Currency Momentum Strategies* | Cross-sectional winner-minus-loser currency portfolios earn large historical spreads, partially reduced by transaction costs and constrained by limits to arbitrage. | It is not a one-pair directional rule and is not cost-free. | Retain cross-sectional momentum as a separately frozen benchmark after the primary replication. |
| P05 | Zhang (2022), *Dissecting Currency Momentum* | Currency momentum is concentrated in systematic carry and dollar factors; idiosyncratic currency returns contain little momentum. | It does not imply a given retail implementation can capture factor returns. | Require a G10 universe and report currency/factor attribution; USDJPY alone cannot approve the hypothesis. |
| P06 | Hutchinson et al. (2022), *Technical Trading Rule Profitability in Currencies: It’s All About Momentum* | Technical-rule mean Sharpe falls sharply out of sample and modest costs erase the later-period returns; TSMOM explains the rule family. | It does not prove all future rules have zero return. | Avoid indicator grids and require later-period, net-cost confirmation. |
| P07 | Osler (2003), *Currency Orders and Exchange-Rate Dynamics* | Stop-loss and take-profit orders cluster around round numbers; their different feedback effects explain both continuation after crossing and reversal at levels. | It does not prove the modern retail “liquidity sweep” template or its net profitability. | Round numbers may motivate a future, separately registered level study; they cannot validate v1. |
| P08 | Osler (2005), *Stop-Loss Orders and Price Cascades* | Rates move rapidly after reaching levels where stop-loss orders cluster; effects are larger and longer than at take-profit clusters. | Statistical association cannot fully prove causal order execution, and the sample is historical/dealer-specific. | Continuation and reversal must be competing hypotheses rather than a forced reversal narrative. |
| P09 | Breedon and Ranaldo (2013), *Intraday Patterns in FX Returns and Order Flow* | Currencies tend to depreciate in local trading hours, consistent with order-flow and inventory effects. | A session pattern is not automatically an executable strategy across pairs and eras. | Session is a conditioning variable for future research, not a v1 entry signal. |
| P10 | Krohn, Mueller, and Whelan (2024), *Foreign Exchange Fixings and Returns around the Clock* | Strong pre-fix USD appreciation and post-fix reversal appear across nine currencies over 21 years. A liquidity demander’s unconditional return turns negative after transaction costs. | A statistically strong return path is not necessarily arbitrageable by a retail trader. | Every future intraday study must cross a bid/ask executable-return gate. |
| P11 | Neely and Weller (2003), *Intraday Technical Trading in the Foreign Exchange Market* | Stable intraday predictability exists, but optimized rules produce no excess returns after reasonable costs and normal-hours restrictions. | Failure of its model search does not prove every possible rule is impossible. | Intraday is lower-priority and requires a higher burden of proof. |
| P12 | White (2000) and Bailey et al. (2015) | Reusing the same history across many model searches can make chance results look real; Reality Check and PBO quantify this risk. | These methods cannot repair contaminated data or an unfalsifiable hypothesis. | Log all trials, isolate one primary specification, apply family-wise inference, and create a prospective lockbox. |

## 3. Primary and challenger families

### 3.1 Primary: slow time-series trend/momentum

The v1 primary specification is deliberately narrow:

```text
decision frequency      monthly
information frequency   daily closes or settlement marks
signal                   sign of trailing 12-month total return
holding period           one month
portfolio                equal-weight across qualified G10 instruments
risk scaling             none in the primary result
```

The 1-, 3-, and 6-month horizons are literature diagnostics. They do not replace
the primary result or create a “best lookback” selection.

### 3.2 Required controls

The primary strategy must be compared with:

1. zero-position/cash;
2. an expanding historical-mean-sign strategy as in the Huang et al. critique;
3. always-long and always-short currency-basket exposures where meaningful;
4. the same signal and controls under identical ex-ante volatility scaling,
   reported only as a diagnostic; and
5. randomized or circularly shifted signals as a placebo distribution.

### 3.3 Registered later challenger

Cross-sectional currency momentum is the only planned v1 challenger family.
Its exact formation and holding rules must be transcribed from the selected
paper and frozen before its outcomes are computed. It cannot rescue a failed
TSMOM claim by retroactively becoming the primary hypothesis.

### 3.4 Outside v1

- intraday Asian-range or London-open breakout;
- failed breakout or liquidity-sweep reversal;
- support/resistance zones inferred from future pivots;
- RSI, MACD, EMA, Bollinger, ATR, or candlestick parameter grids;
- macro or central-bank filters from the closed fundamental projects;
- machine learning or genetic-program searches.

These ideas require new papers, a new contract, and a distinct outcome boundary.

## 4. Paper-to-engineering rules

| Literature risk | Engineering response |
|---|---|
| Portfolio evidence mistaken for a pair edge | Store and report portfolio, currency, leave-one-currency-out, and USD-factor attribution separately. |
| Volatility scaling creates apparent alpha | Primary result is unscaled; every scaled strategy receives an identically scaled control. |
| Carry or roll omitted from currency return | Use total-return instruments or explicit financing/roll. Price-only marks cannot support a PnL claim. |
| Intraday predictability consumed by spread | Simulator executes at bid/ask and reports break-even cost; mid-price is diagnostic only. |
| Thousands of tried rules create false positives | One primary lookback; immutable trial registry; White/SPA-style family correction and PBO diagnostics. |
| Old regime drives the full sample | Predefined eras, expanding walk-forward evaluation, and a post-code-freeze prospective lockbox. |
| Shared USD exposure inflates apparent breadth | Cluster inference by calendar period and report effective independent time observations. |
| A visually compelling failure is renamed and retested | A failed signal lineage closes; future families require a new preregistration and new evidence. |

## 5. What counts as paper-backed

A paper backs a research hypothesis when it supplies at least one of:

- replicated empirical predictability;
- a plausible market mechanism tied to observable variables; or
- a falsification method directly relevant to the claim.

It does not justify copying a headline return, assuming current profitability,
or importing parameters into a different instrument, horizon, cost model, or
trader type without a new test.

## 6. Final Phase 00 decision

Proceed to source qualification for a multi-currency, monthly TSMOM replication.
Do not build the intraday strategy engine yet. If qualified free data cannot
represent total returns and costs, the PnL branch must return `NOT_TESTED`; the
project may still run a clearly labeled non-executable predictability study.
