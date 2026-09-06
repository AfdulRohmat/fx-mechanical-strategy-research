# Technical Plan — FX Mechanical Strategy Research

Status: Phase 00 through Phase 04 complete or resolved

Primary contract: `RESEARCH_DECISION_CONTRACT.md` v0.1

## Architecture principles

- Separate source data, canonical market data, signals, execution, statistics,
  and decisions.
- Every decision field has both an observation timestamp and availability
  timestamp where those can differ.
- Strategy code consumes only canonical inputs, never provider-specific files.
- Every run is immutable and content-addressed.
- Human-readable reports and compact evidence are committed; large raw data are
  ignored but recorded by hash.
- The default test suite is network-free.

## Proposed package layout

```text
config/
  research_contract_v0_1.yaml
  sources.yaml
docs/
references/
  papers/
src/fx_mechanical_research/
  cli.py
  config.py
  sources/
  canonical/
  signals/
  execution/
  statistics/
  reporting/
tests/
artifacts/
```

The package and configuration are created only after Phase 01 decides which
instrument type can support the primary claim.

## Phase 00 — literature and contract freeze

Deliverables:

- annotated paper backbone;
- research decision contract;
- reference manifest and lawful local working-paper copies;
- technical phase plan;
- explicit contamination statement from earlier projects.

Exit condition: documents exist and no TSMOM v1 return has been computed.

Current status: `COMPLETE`.

## Phase 01 — free-source and instrument qualification

Goal: determine whether free data can support an executable total-return test.

Candidate source classes are evaluated in this order:

1. exchange-published or otherwise authoritative currency futures settlements,
   contract metadata, rolls, and historical bid/ask or cost evidence;
2. broker-exported spot/CFD prices with historical spread, commission, and swap;
3. forward or spot-plus-interest data adequate to construct currency excess
   returns;
4. official reference rates for non-executable predictability diagnostics only.

Required audits:

- licensing and redistribution terms;
- coverage by instrument and date;
- timezone, daylight-saving, holiday, and month-end conventions;
- raw versus adjusted contracts and roll reproducibility;
- survivorship and missingness;
- quote orientation and inverse consistency;
- timestamp availability;
- cost and financing coverage;
- evidence overlap with prior repositories.

Phase 01 must emit a source matrix with one of:

- `PASS_EXECUTABLE_TOTAL_RETURN`;
- `PASS_PREDICTABILITY_ONLY`;
- `REVIEW_REQUIRED`; or
- `FAIL`.

No candidate strategy PnL is computed in this phase.

Current status: `COMPLETE`.

Result: `PASS_PREDICTABILITY_ONLY`; the executable trading claim remains
`NOT_TESTED`. BIS XRU is qualified for a reference-rate diagnostic over the
source-selected common window beginning 2000-01-03. No free candidate passed
historical financing or total-return, complete transaction costs, and all-leg
instrument mechanics together. See `PHASE_01_SOURCE_QUALIFICATION.md` and
`../evidence/phase01/REPORT.md`.

This result activates only the predictability subset of Phase 02. Executable
return construction, primary TSMOM PnL, and Phases 03-05 remain blocked under
contract v0.1 unless a source passes `PASS_EXECUTABLE_TOTAL_RETURN` or a dated
pre-outcome contract amendment changes the claim.

## Phase 02 — canonical return and execution layer

Implement immutable schemas for:

```text
instrument_contract
raw_market_observation
canonical_daily_mark
contract_roll_event
financing_observation
transaction_cost_observation
monthly_total_return
```

Key tests:

- deterministic source parsing and SHA-256 manifest;
- no duplicate instrument/timestamp;
- causal adjusted-series construction;
- roll return identity against contract legs;
- pair inversion and USD orientation;
- month-end selection without future reach;
- missing and stale data fail closed;
- cost accounting identity;
- post-decision source mutation cannot alter earlier information silently.

Phase 02 selects the moving-block length from pre-strategy return dependence,
records the rule, and freezes it before signal evaluation.

Current status: `COMPLETE_PREDICTABILITY_ONLY`.

The BIS adapter produced 61,398 causal daily marks and 2,880 synchronized
month-end marks over 320 months. It created price-only changes, not executable
total returns. The frozen pre-signal ACF rule selected a 10-month moving block;
3-, 6-, and 12-month sensitivities remain registered. All execution-dependent
schemas fail closed because financing, roll, and transaction-cost observations
remain unavailable.

## Phase 03 — primary TSMOM replication

Implement only the frozen 12-month sign strategy and B0–B4 controls.

Outputs include:

- every instrument-month signal and its input window;
- gross and net instrument returns;
- synchronized portfolio returns;
- turnover and cost decomposition;
- paired control differences;
- block-bootstrap intervals;
- Reality Check or SPA result;
- leave-one-currency-out and predefined-era diagnostics;
- break-even costs;
- complete trial registry and run manifest.

The 1-, 3-, and 6-month diagnostics run only after the primary result is sealed
and may not alter it.

Current status: `COMPLETE_BLOCKED_BEFORE_OUTCOME`; decision `NOT_TESTED`.

The primary kernel, B0-B2 controls, cost/turnover identity, synchronized
portfolio aggregation, and trial-registry checks are covered by synthetic
executable fixtures. The actual Phase 02 outcome file was not read because the
upstream executable-source, claim-scope, and monthly-total-return gates all
failed. H1-H5 remain `NOT_TESTED`. B3-B4 outcome machinery and inferential
evaluation remain dormant until a real executable input is eligible.

## Phase 04 — cross-sectional challenger

This phase starts only after Phase 03 is immutable. Before any challenger PnL:

- choose one published cross-sectional currency momentum implementation;
- transcribe formation, holding, weighting, and rebalance rules;
- register the family size and multiple-testing treatment;
- declare whether qualified data reproduce forward/excess returns faithfully.

The challenger receives a separate decision. It cannot be labeled confirmation
of TSMOM and cannot rescue a failed TSMOM lineage.

Current status: `COMPLETE_BLOCKED_BEFORE_OUTCOME`; decision `NOT_TESTED`.

One challenger was preregistered:
`MENKHOFF_MOM12_1_G10_THREE_BY_THREE_V0_1`. It is explicitly a paper-anchored
G10 adaptation, not an exact replication of the paper's wider six-portfolio
universe. The hash-verified method, causal ranking, tie handling, full-notional
long/short legs, turnover, and costs pass synthetic tests. Real evaluation was
blocked before outcome access by Phase 01-03 eligibility failures.

## Phase 05 — historical decision gate

Aggregate the frozen evidence and emit exactly one v1 decision:

```text
NOT_TESTED
DO_NOT_PROCEED_WITH_TSMOM_V1
PROCEED_TO_PROSPECTIVE_OBSERVATION_TSMOM_V1
```

The report must explain the outcome in plain language and show:

- gross versus net result;
- signal versus matched-control result;
- portfolio versus individual-currency evidence;
- time stability;
- cost headroom;
- multiple-testing correction;
- limitations of the data and trader model.

## Phase 06 — prospective lockbox

Only an approved historical candidate enters this phase. Freeze:

- source adapters and versions;
- strategy and comparator code;
- environment lockfile;
- complete tests;
- configuration and costs;
- all input hashes;
- prospective start timestamp;
- power-derived observation requirement.

Prospective results are appended, never backfilled by modified code. Operational
monitoring must not reveal a tuned alternative in the same v1 lineage.

## Explicitly deferred research

Intraday session or level-based studies remain independent future projects. A
reasonable paper-led design would compare continuation after a decisive crossing
with reversal after a failed crossing, using round numbers or institutional
fixings defined ex ante. The evidence does not authorize calling every wick a
liquidity sweep or assuming reversal is the privileged direction.

## Quality gates

Once code exists, every phase merge requires:

```powershell
python -m pytest -q
ruff check .
mypy src
git diff --check
```

Additional invariant tests must cover look-ahead prevention, calendar clusters,
signal/return alignment, costs, rolls, deterministic random seeds, trial
registry immutability, and fail-closed gate logic.
