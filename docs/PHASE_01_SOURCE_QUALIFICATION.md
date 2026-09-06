# Phase 01 - Free Source and Instrument Qualification

Status: complete

Decision: `PASS_PREDICTABILITY_ONLY`

Trading claim: `NOT_TESTED`

Frozen audit time: 2026-09-06T17:09:48Z

## Purpose

Phase 01 asks a narrower question than whether the strategy is profitable:

> Can a free, reproducible data source represent the complete return earned by
> the frozen G10 strategy after realistic trading and holding costs?

The answer is currently no. Free official data do support a clean test of spot
reference-rate predictability. Treating that price change as trading PnL would
cross the claim boundary frozen in `RESEARCH_DECISION_CONTRACT.md`.

## Non-scored gate

The audit does not assign subjective points or weights. A candidate must pass
every relevant Boolean component.

The predictability gate requires:

1. free reproducible access;
2. sufficient research-use terms;
3. all nine non-USD G10 legs;
4. historical price or settlement marks; and
5. documented observation and availability timing.

The executable gate requires all of the above plus:

1. historical trading costs;
2. holding return, forward points, embedded carry, or broker financing; and
3. complete instrument mechanics, including rolls where applicable.

A single missing field prevents `PASS_EXECUTABLE_TOTAL_RETURN`. This avoids
using an arbitrary score to offset a non-negotiable execution gap.

## Audited sources

### BIS bilateral exchange rates

The [BIS XRU bulk download](https://data.bis.org/bulkdownload) is free and
requires no account. Its [permitted-use terms](https://data.bis.org/help/legal)
allow use with required source citation and disclaim warranties. The file
contains compiled daily reference rates sourced mainly from the ECB and Federal
Reserve in recent periods and other official sources historically, as described
in the [XRU overview](https://data.bis.org/topics/XRU).

The actual 448,056,161-byte flat CSV was inspected. All nine required mappings
passed:

```text
AUD/AU  CAD/CA  CHF/CH  EUR/XM  GBP/GB
JPY/JP  NOK/NO  NZD/NZ  SEK/SE
```

Each mapping has 6,822 valid observations in the common window from 2000-01-03
through 2026-08-28. No selected series has duplicate dates, invalid normal
observations, or non-free confidentiality flags. The committed manifest records
the archive and CSV SHA-256 hashes; raw data remain outside Git.

Limitations:

- values represent currency units per USD and require causal inversion to a
  common USD-per-currency orientation;
- the observations are reference rates, not broker fills;
- the compiled file is updated weekly and has no historical vintage archive in
  this project, so Phase 02 must apply a conservative availability lag;
- there are no historical spreads, commissions, financing debits or credits,
  or contract rolls.

The recent observations are compiled primarily from ECB rates measured at
13:15 GMT and Federal Reserve rates measured at 17:00 GMT. Phase 02 must retain
the source convention, treat non-normal rows as missing, avoid weekend or
holiday forward-filling, and select the last earlier available observation for
month-end decisions. The fixed GMT convention does not inherit a local
daylight-saving clock shift, but the contributing source can change over time.

Verdict: `PASS_PREDICTABILITY_ONLY`.

### Federal Reserve H.10

[Federal Reserve H.10](https://www.federalreserve.gov/releases/h10/hist/) lists
all nine required currency histories from 2000 onward and documents the
reference-rate convention. It is useful as an independent cross-check of
orientation and large moves. Its raw-data redistribution terms still require a
final review before mirroring, and it contains no executable costs or carry.

Verdict: `REVIEW_REQUIRED`.

### Dukascopy historical bid/ask

[Dukascopy documents historical best bid/ask prices](https://www.dukascopy.com/swiss/english/about/faq/?mob=0)
and volumes. This can improve spread measurement. However, its
[overnight policy](https://www.dukascopy.com/swiss/english/forex/forex-trading-accounts/overnight/)
is dynamic and the audit did not find a public historical swap-rate series.
Historical commission/account tier and raw redistribution terms also remain
unresolved.

Verdict: `REVIEW_REQUIRED`.

### OANDA v20

[OANDA documents bid, ask, and midpoint candles](https://developer.oanda.com/rest-live-v20/instrument-df/)
plus current instrument financing parameters. The API
[requires an account token](https://developer.oanda.com/rest-live-v20/authentication/),
and the audit did not verify a public historical financing series that another
researcher can reproduce without credentials.

Verdict: `REVIEW_REQUIRED`.

### CME currency futures

Futures are the preferred instrument conceptually: settlement-to-settlement
returns embed interest-rate differentials and contract rolls can be represented
explicitly. CME documents [daily settlements](https://www.cmegroup.com/market-data/daily-settlements.html),
[DataMine](https://www.cmegroup.com/datamine.html), and
[continuous series](https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html).
Phase 01 did not verify a free, credential-free bulk archive with contract-level
history, suitable permissions, cost evidence, and liquid continuous coverage
for every required G10 leg.

Verdict: `REVIEW_REQUIRED`.

### Spot plus policy-rate proxy

Combining BIS spot with policy rates could use free sources, but policy coverage
was not downloaded in this phase and a policy-rate difference is not a realized
one-month forward discount or broker swap. It omits cross-currency basis,
tenor/day-count conventions, and broker markup. It is not accepted as a
total-return construction.

Verdict: `REVIEW_REQUIRED`.

## Prior-research overlap

The source audit also checked earlier repositories. Exact TSMOM v1 PnL has not
been computed, but relevant outcomes are not untouched:

- `gbpusd-mechanical-structure` inspected HistData GBPUSD bid/ask history,
  including 2024-2025;
- `fx-fundamental-analysis` inspected Dukascopy USDJPY event windows from
  2017-2024;
- `fx-fundamental-bias-engine` inspected G10 ECB reference-rate samples and
  development/evaluation outcomes through 2022; and
- `fx-structural-policy-divergence` evaluated ECB G10 reference-rate outcomes
  over 2013-2025.

Those projects tested different hypotheses and do not reveal the exact TSMOM v1
result. They do prevent us from calling any overlapping historical window a
genuine holdout. The machine-readable disclosure is committed as
`evidence/phase01/prior_evidence_overlap.json`.

## Frozen common window

The diagnostic source window begins on 2000-01-03 and must extend through at
least 2026-08-28. This was selected from source coverage before any TSMOM return
or candidate outcome was calculated. It is not described as untouched because
other projects in the workspace previously exposed portions of FX history.

## Decision consequence

Phase 01 is complete, but it has not tested the trading hypothesis. The current
branch may proceed only to a Phase 02 canonical reference-rate layer that is
explicitly labelled `PREDICTABILITY_ONLY`. The layer must implement:

- source hashes and immutable raw manifests;
- exact G10 mappings and quote inversion;
- conservative availability timestamps;
- month-end selection without future reach;
- missing/stale-data failure; and
- H.10 cross-source diagnostics if legal review permits local retrieval.

Primary TSMOM PnL, net-return hypotheses H1-H5, and any proceed decision remain
blocked. They can be unblocked by a source that passes the existing executable
gate, or by a dated contract amendment written before outcome inspection.

## Evidence map

- `config/source_registry_v0_1.json` - frozen candidates, facts, and gate fields;
- `src/fx_mechanical_research/phase01_sources.py` - deterministic audit logic;
- `tests/test_phase01_sources.py` - fail-closed invariant tests;
- `evidence/phase01/source_matrix.csv` - all source decisions;
- `evidence/phase01/bis_coverage.json` - actual G10 coverage audit;
- `evidence/phase01/raw_source_manifest.json` - raw hashes without raw data;
- `evidence/phase01/decision.json` - machine-readable result;
- `evidence/phase01/prior_evidence_overlap.json` - prior outcome exposure;
- `evidence/phase01/REPORT.md` - short readable report; and
- `evidence/phase01/manifest.json` - hashes of committed Phase 01 evidence.
