# Phase 04 - Cross-Sectional Challenger Gate

Status: `COMPLETE_BLOCKED_BEFORE_OUTCOME`

Decision: `NOT_TESTED`

## Published backbone

The challenger is anchored to Menkhoff, Sarno, Schmeling, and Schrimpf,
*Currency Momentum Strategies*, BIS Working Paper 366. The locally stored paper
matches SHA-256:

```text
a6e394d52b2821aa1e811e9bffe313ef4718dae1a20d5599c0fe00701453ad42
```

The paper:

- computes U.S.-investor currency excess returns from one-month forward and
  subsequent spot rates;
- uses actual end-of-month rather than monthly-average observations;
- sorts currencies on formation periods including 12 months;
- studies holding periods including one month;
- forms High-minus-Low, dollar-neutral portfolios; and
- adjusts dynamic portfolios using bid and ask quotes.

Its primary empirical universe contains up to 48 currencies split into six
portfolios. That exact construction cannot be reproduced with nine currencies.
The paper also notes a G10 industry implementation that is long the three best
and short the three worst currencies over the preceding 12 months.

## Registered adaptation

The single challenger is:

```text
MENKHOFF_MOM12_1_G10_THREE_BY_THREE_V0_1
```

Its rules were frozen before outcome access:

- universe: nine non-USD G10 currencies;
- ranking value: compounded executable total return over the prior 12 months;
- holding period: one month;
- long: three highest-ranked currencies;
- short: three lowest-ranked currencies;
- neutral: middle three currencies;
- tie break: ascending currency code after score;
- weights: `+1/3` per winner and `-1/3` per loser;
- portfolio: long notional `+1`, short notional `-1`, gross notional `2`;
- rebalance: monthly; and
- cost: absolute weight change multiplied by one-way cost.

This is labelled `PAPER_ANCHORED_G10_ADAPTATION`. It must not be reported as an
exact Menkhoff et al. replication.

## Synthetic invariant coverage

Tests verify:

- the holding-month return cannot affect its own formation rank;
- winners, losers, and neutral currencies number exactly three each;
- equal scores use the deterministic currency-code tie rule;
- both full-notional legs sum to zero net exposure and two gross exposure;
- initial entry incurs turnover on both legs;
- an unchanged next-month ranking incurs no new spot-weight turnover;
- executable scope is inherited from the Phase 03 input contract; and
- paper, configuration, registry, and upstream evidence are hash-addressed.

Synthetic values are implementation tests, not challenger research results.

## Real-data gate

The real-data gate stopped on four conditions:

```text
PHASE01_EXECUTABLE_SOURCE_NOT_QUALIFIED
PHASE02_SCOPE_NOT_EXECUTABLE
PHASE02_TOTAL_RETURN_NOT_BUILT
PHASE03_PRIMARY_NOT_EVALUATED_AND_SEALED
```

The declared outcome file was not opened or hashed. No rank, position, return,
cost, or PnL was calculated on the BIS panel.

## Interpretation boundary

The challenger is a separate research lineage. Even a future positive result
would not confirm the time-series return-sign mechanism. It cannot rescue a
failed or untested TSMOM v1 result. Its registered family size is one; adding a
formation horizon, holding horizon, bucket size, or tie policy creates another
trial and requires multiple-testing treatment.

## Evidence

- `config/cross_sectional_challenger_v0_1.json` - frozen adaptation;
- `config/trial_registry.jsonl` - appended challenger trial;
- `evidence/phase04/eligibility_gate.json` - four upstream checks;
- `evidence/phase04/trial_registry_audit.json` - family-size and seal audit;
- `evidence/phase04/input_manifest.json` - paper/config/upstream hashes;
- `evidence/phase04/summary.json` - decision and claim boundary;
- `evidence/phase04/REPORT.md` - concise result; and
- `evidence/phase04/manifest.json` - evidence hashes.
