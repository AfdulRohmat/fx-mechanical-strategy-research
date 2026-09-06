# Phase 03 - Frozen TSMOM Kernel and Eligibility Gate

Status: `COMPLETE_BLOCKED_BEFORE_OUTCOME`

Decision: `NOT_TESTED`

## What was engineered

The code transcribes the frozen TSMOM v1 mechanics without using actual FX
outcomes:

```text
signal at end of t = sign(compounded total return over prior 12 months)
holding return     = signal at t multiplied by total return in t+1
turnover units     = abs(current signal - previous signal)
trading cost       = turnover units multiplied by one-way cost
portfolio          = equal-weight synchronized G10 currency cluster
```

The executable input object requires `EXECUTABLE_TOTAL_RETURN`. A BIS
`PREDICTABILITY_ONLY` record cannot be constructed as strategy input.

Synthetic executable fixtures test:

- the signal window ends before the holding month;
- the holding-month return cannot enter its own signal;
- zero, positive, and negative signal semantics;
- first entry costs one unit and a long-to-short flip costs two units;
- net return equals gross return minus the incurred trading cost;
- B0 cash, B1 past-only expanding-mean sign, and B2 static exposures;
- equal weighting across the complete nine-currency month;
- duplicate, missing, non-consecutive, and unsynchronized rows fail closed; and
- a price-only claim scope is rejected at object construction.

These tests validate implementation invariants only. Their synthetic numbers
are not research evidence and are not included in result artifacts.

## Pre-outcome real-data gate

The gate reads only three upstream evidence files:

1. Phase 01 source decision;
2. Phase 02 claim scope; and
3. Phase 02 schema coverage.

It then compares them against the frozen requirements. The actual result was:

| Requirement | Actual | Gate |
| --- | --- | --- |
| `PASS_EXECUTABLE_TOTAL_RETURN` | `PASS_PREDICTABILITY_ONLY` | FAIL |
| `EXECUTABLE_TOTAL_RETURN` scope | `PREDICTABILITY_ONLY` | FAIL |
| Monthly total-return status `PASS` | `NOT_BUILT` | FAIL |

The declared outcome file was neither opened nor hashed. This ordering is tested
with a poison file: the gate still returns `NOT_TESTED` without reading it.

## Hypothesis status

| Hypothesis | Status |
| --- | --- |
| H1 positive net portfolio return | `NOT_TESTED` |
| H2 incremental to expanding-mean control | `NOT_TESTED` |
| H3 multiple-testing-adjusted superiority | `NOT_TESTED` |
| H4 breadth and time stability | `NOT_TESTED` |
| H5 cost capacity | `NOT_TESTED` |

No signal, strategy return, benchmark outcome, confidence interval, Reality
Check/SPA statistic, or PnL was computed on actual data.

## Trial registry

`config/trial_registry.jsonl` contains the single primary v1 trial with sequence
1, exact frozen parameters, `BLOCKED_BEFORE_OUTCOME`, and
`outcome_inspected=false`. The audit rejects duplicate identifiers, broken
sequences, or a mutated outcome flag. Git history and the committed SHA-256
provide the append-only audit trail.

## Deferred machinery

B3 volatility scaling, B4 calendar-cluster placebos, bootstrap inference,
Reality Check/SPA, era diagnostics, leave-one-currency-out analysis, and
break-even costs require actual eligible return observations. They are not run
or parameterized from reference-rate outcomes. Activating them requires the
same Phase 01 and Phase 02 executable-data gates to pass first.

## Evidence

- `config/tsmom_v0_1.json` - exact strategy and eligibility configuration;
- `config/trial_registry.jsonl` - append-only trial entry;
- `evidence/phase03/eligibility_gate.json` - upstream comparison;
- `evidence/phase03/trial_registry_audit.json` - registry integrity;
- `evidence/phase03/input_manifest.json` - hashes of gate inputs only;
- `evidence/phase03/summary.json` - H1-H5 statuses;
- `evidence/phase03/REPORT.md` - concise result; and
- `evidence/phase03/manifest.json` - evidence hashes.
