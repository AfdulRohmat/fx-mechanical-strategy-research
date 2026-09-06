# Phase 01 - Free source and instrument qualification

Decision: `PASS_PREDICTABILITY_ONLY`

Trading-claim status: `NOT_TESTED`

## Plain-language result

Free data are sufficient to test whether the frozen 12-month signal predicts
the next reference-rate movement across the G10 basket. They are not sufficient
to claim a tradable net return. No audited free source stack currently combines
historical holding return or financing, transaction costs, and instrument
mechanics for all nine non-USD G10 legs.

This is a data-boundary result, not evidence that TSMOM works or fails. Phase 01
did not calculate a return, signal, Sharpe ratio, confidence interval, or PnL.

## Candidate matrix

| Candidate | Class | Verdict | Missing or unresolved execution fields |
| --- | --- | --- | --- |
| `bis_xru_reference_spot` | official_reference_rate | `PASS_PREDICTABILITY_ONLY` | historical_trading_costs;holding_return_or_financing;instrument_mechanics |
| `federal_reserve_h10` | official_reference_rate | `REVIEW_REQUIRED` | research_use_terms;historical_trading_costs;holding_return_or_financing;instrument_mechanics |
| `dukascopy_jforex_spot` | broker_spot | `REVIEW_REQUIRED` | research_use_terms;historical_trading_costs;holding_return_or_financing;instrument_mechanics |
| `oanda_v20_spot` | broker_spot | `REVIEW_REQUIRED` | free_reproducible_access;research_use_terms;historical_trading_costs;holding_return_or_financing;instrument_mechanics |
| `cme_currency_futures` | exchange_futures | `REVIEW_REQUIRED` | free_reproducible_access;research_use_terms;full_g10_coverage;historical_marks;historical_trading_costs |
| `bis_spot_plus_policy_proxy` | spot_plus_interest_proxy | `REVIEW_REQUIRED` | full_g10_coverage;historical_trading_costs;holding_return_or_financing;instrument_mechanics |

`bis_xru_reference_spot` is selected only for a possible price-predictability
diagnostic. It is not selected as the executable v1 instrument.

## Verified BIS coverage

The official bulk CSV was audited rather than trusting a catalog description.
The common diagnostic window was frozen as 2000-01-03 through at
least 2026-08-28, before any candidate return was read.

| Currency | BIS area | First valid date | Last valid date | Valid rows | Gate |
| --- | --- | --- | --- | ---: | --- |
| AUD | AU | 1971-01-04 | 2026-09-01 | 14,140 | PASS |
| CAD | CA | 1945-01-01 | 2026-09-01 | 21,093 | PASS |
| CHF | CH | 1953-09-01 | 2026-09-01 | 18,858 | PASS |
| EUR | XM | 1974-06-28 | 2026-09-01 | 13,291 | PASS |
| GBP | GB | 1953-08-10 | 2026-09-01 | 18,868 | PASS |
| JPY | JP | 1969-12-01 | 2026-09-01 | 14,417 | PASS |
| NOK | NO | 1953-12-14 | 2026-09-01 | 18,768 | PASS |
| NZD | NZ | 1971-01-04 | 2026-09-01 | 14,133 | PASS |
| SEK | SE | 1953-09-01 | 2026-09-01 | 18,857 | PASS |

Bulk CSV SHA-256: `7b9a08e589c910f3b17cdac46960a51f3f29b48108b2c03217013c8713fdab84`

## Prior evidence overlap

The exact TSMOM v1 return was not previously computed, but related repositories
already exposed overlapping FX outcomes. No historical period is labelled an
untouched holdout.

| Repository | Prior source | Exposed scope |
| --- | --- | --- |
| `gbpusd-mechanical-structure` | HistData GBPUSD bid/ask | GBPUSD history including 2024-2025 |
| `fx-fundamental-analysis` | Dukascopy USDJPY bid/ask | USDJPY employment-event windows from 2017-2024 |
| `fx-fundamental-bias-engine` | ECB G10 reference rates | G10 development/evaluation data through 2022 plus source POC samples |
| `fx-structural-policy-divergence` | ECB G10 reference rates | G10 diagnostic outcomes from 2013-2025 |

## What remains blocked

- CME futures remain the preferred tradable implementation, but credential-free
  bulk contract history, permissions, and continuous liquid coverage for all
  nine legs were not verified.
- Broker bid/ask history can measure spreads, but neither reviewed broker exposes
  a verified public historical financing series for the required period.
- A policy-rate differential is not a substitute for forward points or realized
  broker swap because it omits basis, tenor conventions, and broker markup.
- Reference rates contain no executable bid/ask, commission, roll, or financing.

## Authorized next work

Phase 02 may build a causal canonical layer for a clearly labelled
`PREDICTABILITY_ONLY` diagnostic, including the one-week availability lag and
quote inversion. Under contract v0.1, primary strategy PnL and Phases 03-05 stay
blocked until an executable total-return source passes qualification. An
alternative is a dated contract amendment that explicitly changes the research
claim; it must happen before outcome inspection.
