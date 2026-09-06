# Phase 05 — Historical decision gate

Status: `COMPLETE`

Decision: `NOT_TESTED`

## Purpose

Phase 05 closes the historical v1 lineage without changing the frozen research
question. It verifies the Phase 01–04 evidence manifests, applies the decision
contract mechanically, and decides whether a prospective Phase 06 is allowed.

The gate deliberately distinguishes two conclusions:

- `NOT_TESTED` means the required executable evidence was unavailable, so no
  alpha conclusion is permitted;
- `DO_NOT_PROCEED_WITH_TSMOM_V1` means the data were adequate, the test ran, and
  at least one mandatory hypothesis or integrity gate failed.

## Implemented controls

- exact decision vocabulary is configuration-locked;
- all five registered TSMOM hypotheses are required;
- data adequacy is evaluated before hypothesis results;
- the cross-sectional challenger cannot alter the primary decision;
- every committed Phase 01–04 evidence file is checked against its SHA-256,
  byte count, and complete inventory;
- Phase 06 activates only for the exact historical proceed decision;
- an apparent proceed is rejected until power analysis and the prospective
  lockbox receive a separately reviewed implementation.

## Actual result

The four upstream evidence manifests passed their integrity audit. The
historical trading claim nevertheless remains `NOT_TESTED` because:

1. Phase 01 qualified BIS reference rates only for predictability;
2. Phase 02 did not build monthly executable total returns;
3. Phase 03 therefore stopped before opening the real outcome file;
4. H1–H5 consequently remain `NOT_TESTED`;
5. Phase 04 also stopped before evaluating its challenger.

There is no strategy return series, Sharpe ratio, confidence interval,
break-even cost, or corrected p-value in this lineage. The result is neither
evidence for an edge nor evidence against one.

## Phase 06

Phase 06 is `NOT_ACTIVATED`. The repository does not invent a prospective start
timestamp, effect size, or observation target from a historical test that never
ran.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m fx_mechanical_research.phase05_gate
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src
git diff --check
```

Machine-readable evidence is under `evidence/phase05/`.
