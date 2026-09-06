# Phase 02 - Causal Canonical Reference-Rate Layer

Status: complete

Decision: `COMPLETE_PREDICTABILITY_ONLY`

Trading claim: `NOT_TESTED`

## Result

The Phase 02 adapter parsed the hash-locked BIS XRU source selected in Phase 01
and produced:

| Record | Count |
| --- | ---: |
| Canonical daily marks | 61,398 |
| Synchronized month-end marks | 2,880 |
| Monthly reference-rate changes | 2,871 |
| Synchronized change months | 319 |
| Executable total-return rows | 0 |

The panel contains nine currencies for every one of 320 calendar months from
January 2000 through August 2026. Sixty-seven non-normal source rows per currency
were explicitly skipped. No selected normal row failed inversion, uniqueness,
or confidentiality checks.

## Causal timestamp contract

The source supplies observations, not a historical publication-vintage table.
Phase 02 therefore applies a conservative frozen rule:

```text
observed_at_utc  = source date at 17:00:00 UTC
available_at_utc = observed date + 7 calendar days at 23:59:59 UTC
decision_at_utc = final calendar day of month at 23:59:59 UTC
```

The selector chooses the latest observation whose `available_at_utc` is no
later than the decision. It does not forward-fill weekends or holidays. A mark
older than 14 calendar days fails the run. Maximum staleness in the actual panel
was 11 days.

This lag is deliberately conservative. It prevents the weekly BIS bulk update
from being treated as if each compiled value had been available immediately on
its observation date.

## Quote orientation

BIS XRU values represent currency units per USD. The canonical value is:

```text
usd_per_currency = 1 / raw_currency_per_usd
```

Every selected row passed `raw * canonical = 1` within an absolute tolerance of
`1e-12`. Explicit identifiers such as `USD_PER_JPY_REFERENCE` avoid confusing
the canonical economic orientation with market pair naming conventions.

## Dependence rule frozen before signal evaluation

Only the equal-weight G10 monthly reference-change series was inspected. No
TSMOM signal or strategy return was constructed.

The registered rule calculates autocorrelations through lag 24 and uses the
two-sided threshold `1.96 / sqrt(n)`. When the last significant lag is followed
by at least three insignificant tail lags, the block length is one plus that
last significant lag. Otherwise, the 24-month fallback applies.

For 319 synchronized months:

- threshold: `0.1097389321`;
- significant lags: 7 and 9;
- last significant lag: 9; and
- selected moving-block length: **10 months**.

The already registered 3-, 6-, and 12-month sensitivity blocks remain required
if executable strategy inference becomes eligible.

## Executable schema gate

Immutable schemas now exist for instrument contracts, raw observations,
canonical marks, rolls, financing, transaction costs, reference changes, and
monthly total return. The total-return schema requires
`EXECUTABLE_TOTAL_RETURN` scope and enforces:

```text
net = price + financing + roll - spread - commission - slippage
```

The BIS layer cannot populate financing, transaction-cost, or roll records.
Consequently it cannot instantiate a monthly total-return record. Relabelling a
reference change as executable raises an error.

## Phase boundary

Phase 02 completes the canonical diagnostic layer but does not unblock the
historical trading test. Phase 03 can implement and unit-test the frozen TSMOM
engine against synthetic executable fixtures. Applying it to the actual BIS
panel must fail closed and emit `NOT_TESTED` without calculating real signal
outcomes.

## Evidence

- `config/canonical_reference_v0_1.json` - frozen Phase 02 contract;
- `evidence/phase02/summary.json` - machine-readable result;
- `evidence/phase02/sample_flow.json` - row accounting;
- `evidence/phase02/schema_coverage.json` - available and blocked schemas;
- `evidence/phase02/dependence_diagnostics.json` - all inspected ACF lags;
- `evidence/phase02/source_manifest.json` - input and ignored-output hashes;
- `evidence/phase02/REPORT.md` - concise result; and
- `evidence/phase02/manifest.json` - hashes of committed evidence.
