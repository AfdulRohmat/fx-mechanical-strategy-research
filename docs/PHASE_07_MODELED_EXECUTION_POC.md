# Phase 07 — Dukascopy plus modeled Exness Raw costs

Status: `POC_DIAGNOSTIC_ONLY`

Directional finding: `NON_POSITIVE_POINT_ESTIMATE`

## Why this is Phase 07

Phase 06 remains reserved for a prospective lockbox and was not activated by
the v1 historical gate. Phase 07 is a separate exploratory POC requested after
v1 closed as `NOT_TESTED`. It cannot alter that decision or start a prospective
clock.

## Data result

The downloader selected 1,620 month-end marks across nine currencies from
January 2010 through December 2024. Each mark is the last Dukascopy tick in the
16:00 UTC hour on the last available day at or before calendar month-end.

- 180 marks per currency;
- maximum weekend or holiday fallback: two calendar days;
- bid, ask, midpoint, observation timestamp, source URL, raw hash, and raw byte
  count retained;
- raw payloads remain ignored by Git;
- offline replay reproduces the evidence manifest byte-for-byte.

The independent BIS cross-source audit has positive monthly-return correlation
for all currencies. The minimum correlation is 0.697 and minimum directional
agreement is 73.7%. The difference is consistent with the deliberately
different timestamp rules: the BIS panel applies a conservative publication
lag, while this POC uses a tradable month-end hour.

## Cost model

The frozen manual assumptions are not historical Exness observations.
Dukascopy native spread is recorded but not charged. The simulation instead
deducts:

- the manually specified Exness Raw-like spread by pair;
- USD 3.50 commission per standard lot per side;
- manually specified slippage by pair;
- turnover from position changes, with a reversal charged as two one-way
  trades.

Favorable, base, and adverse assumptions were registered before the strategy
return was constructed. Swap and financing remain excluded.

## Primary result

The evaluation contains 167 synchronized portfolio months from February 2011
through December 2024.

| Measure | Result |
|---|---:|
| Gross spot-price annualized arithmetic mean | -0.99% |
| Base before-financing annualized arithmetic mean | -1.02% |
| Annualized modeled transaction cost | 0.03% |
| Annualized volatility | 6.25% |
| Zero-rate Sharpe | -0.16 |
| Cumulative compounded return | -15.54% |
| Maximum drawdown | -23.62% |
| Positive months | 43.7% |
| Monthly mean 95% moving-block interval | -0.31% to +0.16% |

Cost sensitivity does not change the interpretation:

| Scenario | Annualized mean before financing |
|---|---:|
| Favorable | -1.01% |
| Base | -1.02% |
| Adverse | -1.04% |

The gross result is already negative, and the difference across cost scenarios
is small because the rule trades only when its monthly position changes.

## Controls and stability

- B1 expanding-mean sign is approximately flat at -0.01% annualized.
- Primary minus B1 is -0.08% per month; its 95% interval of -0.30% to +0.13%
  includes zero.
- Always-short foreign currencies returns +2.35% annualized before financing,
  consistent with a static strong-USD exposure rather than successful timing.
- Only the 2011–2015 era is positive (+0.97% annualized). The 2016–2020 and
  2021–2024 eras are -1.89% and -2.37%.
- All nine leave-one-currency-out portfolios remain negative.
- JPY (+3.78% annualized) and AUD (+0.51%) are the only positive individual
  legs; the other seven are negative.

## Interpretation

Within this POC, there is no positive evidence for the frozen 12-month
spot-price TSMOM rule. The point estimate is negative before transaction costs,
the confidence interval includes zero, performance is not stable across eras,
and the result is not broad across currencies.

This does not prove that executable currency total-return momentum has no edge.
Financing and forward carry can change currency returns, and this POC does not
contain them. It does show that optimistic spread and commission assumptions do
not rescue the price-only implementation.

## Reproduce

Online acquisition and run:

```powershell
.\.venv\Scripts\python.exe -m fx_mechanical_research.phase07_poc
```

Immutable-cache replay:

```powershell
.\.venv\Scripts\python.exe -m fx_mechanical_research.phase07_poc --offline
```

Readable and machine evidence is under `evidence/phase07/`.
