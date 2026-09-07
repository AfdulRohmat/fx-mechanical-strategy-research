# FX Mechanical Strategy Research

Status: **Phase 07 modeled-execution POC complete — non-positive point estimate**

Frozen on: **2026-09-06**

Trading backtest status: **`NOT_TESTED`**

Phase 01 decision: **`PASS_PREDICTABILITY_ONLY`**

Phase 02 decision: **`COMPLETE_PREDICTABILITY_ONLY`**

Phase 03 decision: **`NOT_TESTED`**

Phase 04 decision: **`NOT_TESTED`**

Phase 05 decision: **`NOT_TESTED`**

Phase 06 status: **`NOT_ACTIVATED`**

Phase 07 status: **`POC_DIAGNOSTIC_ONLY`**

This repository is an evidence-led research program for deterministic foreign
exchange strategies. It does not begin with a chart pattern and search for
parameters that make it profitable. It begins with an academic prior, defines
what would falsify the claim, and only then accesses candidate-strategy returns.

## Current research decision

The first candidate is a slow, multi-currency time-series trend/momentum rule:

- G10 currency instruments, normalized to a common USD orientation;
- monthly decisions from daily data;
- a fixed 12-month return-sign signal as the primary specification;
- one-month holding period;
- unscaled equal-weight implementation as the primary signal test;
- realistic spread, commission, roll, and financing costs where executable
  data permit a PnL claim.

USDJPY is one member of the test universe, not the sole source of evidence.
The literature indicates that much of currency momentum is systematic or
portfolio-level; a profitable aggregate result must not be misrepresented as a
standalone USDJPY edge.

Intraday session breakout, failed breakout, round-number, and fixing effects
are not part of v1. The papers support some of their market mechanisms, but the
evidence that a liquidity-demanding trader can capture them after costs is much
weaker. They require a separate preregistration if studied later.

## Phase 01 result

The official BIS bilateral-rate bulk file passed the machine coverage audit for
all nine non-USD G10 currencies. The source supplies 6,822 valid daily reference
observations per currency in the frozen common window from 2000-01-03 through
2026-08-28. The raw archive and extracted CSV are ignored by Git; their SHA-256
hashes and compact coverage evidence are committed.

That data cannot support an executable trading-return claim. It contains no
historical bid/ask, commission, broker financing, or futures roll execution.
Broker histories reviewed in Phase 01 expose useful bid/ask prices but no
verified public historical financing series. CME futures remain the preferred
instrument in principle, but free reproducible bulk history and all-leg coverage
were not verified.

Therefore Phase 01 did not calculate any signal or PnL. Under contract v0.1:

- a reference-rate `PREDICTABILITY_ONLY` diagnostic may proceed;
- the primary TSMOM net-return test remains `NOT_TESTED`;
- no strategy can advance to the prospective gate from price-only evidence.

The readable result is in
[`evidence/phase01/REPORT.md`](evidence/phase01/REPORT.md), while the full audit
contract and rationale are in
[`docs/PHASE_01_SOURCE_QUALIFICATION.md`](docs/PHASE_01_SOURCE_QUALIFICATION.md).

## Phase 02 result

The causal BIS adapter produced 61,398 daily canonical marks, 2,880 synchronized
month-end marks, and 2,871 monthly reference-rate changes. Raw
currency-per-USD values are inverted to USD-per-currency, observations receive a
conservative seven-day availability lag, and the month-end selector cannot use
future, forward-filled, or more than 14-day-old data.

The pre-signal dependence audit selected a 10-month moving-block length from 319
synchronized months; 3-, 6-, and 12-month sensitivities remain registered. No
TSMOM signal or executable PnL was calculated. See
[`evidence/phase02/REPORT.md`](evidence/phase02/REPORT.md) and
[`docs/PHASE_02_CANONICAL_LAYER.md`](docs/PHASE_02_CANONICAL_LAYER.md).

## Phase 03 result

The frozen TSMOM kernel and fail-closed eligibility gate are implemented. Unit
tests cover prior-12-month signal alignment, next-month application, position
flips, one-way costs, past-only expanding-mean controls, synchronized portfolio
aggregation, and rejection of price-only inputs.

The real run stopped before opening the Phase 02 reference-change file because
there is no executable source, executable claim scope, or monthly total-return
table. H1-H5 therefore remain `NOT_TESTED`; this is not a failed alpha result.
See [`evidence/phase03/REPORT.md`](evidence/phase03/REPORT.md) and
[`docs/PHASE_03_TSMOM_GATE.md`](docs/PHASE_03_TSMOM_GATE.md).

## Phase 04 result

One cross-sectional challenger is preregistered as a disclosed G10 adaptation
of Menkhoff et al. MOM12,1: rank executable prior-12-month returns, hold the top
three long and bottom three short for one month, and rebalance monthly. The
paper hash, causal ranking, deterministic ties, dollar-neutral leg weights,
turnover, and costs are covered by tests.

The challenger stopped before actual outcomes because Phase 03 was not evaluated
and executable total returns remain unavailable. It cannot confirm or rescue
TSMOM v1. See [`evidence/phase04/REPORT.md`](evidence/phase04/REPORT.md) and
[`docs/PHASE_04_CHALLENGER_GATE.md`](docs/PHASE_04_CHALLENGER_GATE.md).

## Phase 05 result

The historical decision gate verified every committed Phase 01–04 evidence
manifest and emitted exactly one contract-valid decision: `NOT_TESTED`.
Executable holding returns and complete costs were unavailable, so the primary
strategy and challenger both stopped before reading real outcomes. No alpha
hypothesis failed because none received an eligible real-data test.

Phase 06 remains `NOT_ACTIVATED`; a prospective clock and observation target
cannot be derived without a historical proceed result and power analysis. See
[`evidence/phase05/REPORT.md`](evidence/phase05/REPORT.md),
[`docs/PHASE_05_HISTORICAL_DECISION.md`](docs/PHASE_05_HISTORICAL_DECISION.md),
and the readable end-to-end review in
[`docs/RESEARCH_REVIEW_PHASE_00_05.md`](docs/RESEARCH_REVIEW_PHASE_00_05.md).

## Phase 07 modeled-execution POC

A separate post-v1 POC combines 1,620 Dukascopy month-end bid/ask snapshots
over 2010–2024 with frozen manual Exness Raw-like spread, commission, and
slippage assumptions. Swap and financing are excluded, so all modeled net
results are explicitly before financing.

The 12-month spot-price TSMOM portfolio has a -1.02% annualized arithmetic mean,
-0.16 Sharpe, and -15.54% cumulative return across 167 months under the base
cost scenario. Its gross mean is already negative at -0.99% annualized; changing
from favorable to adverse costs moves the result only from -1.01% to -1.04%.
The monthly mean interval includes zero, only one of three predefined eras is
positive, and all nine leave-one-currency-out portfolios remain negative.

This POC provides no positive evidence for the price-only rule, but it is not a
test of total-return currency momentum because carry is missing. It does not
change v1 `NOT_TESTED` or activate Phase 06. See
[`docs/PHASE_07_MODELED_EXECUTION_POC.md`](docs/PHASE_07_MODELED_EXECUTION_POC.md)
and [`evidence/phase07/REPORT.md`](evidence/phase07/REPORT.md).

## Why this candidate

The academic record is mixed but informative:

- diversified trend and currency momentum have substantial historical support;
- later papers dispute whether the return-sign signal itself, rather than
  portfolio construction or volatility scaling, creates the apparent edge;
- generic intraday technical rules often lose their excess return after
  realistic costs;
- clustered conditional orders explain continuation and reversal near some
  levels, but do not prove a generic retail "liquidity sweep" strategy.

That disagreement gives us a falsifiable research question. The project must
test the strongest published criticism, not just reproduce the favorable paper.

## Documents

- [`docs/PAPER_BACKBONE.md`](docs/PAPER_BACKBONE.md) — evidence map and the
  translation from papers to engineering decisions.
- [`docs/RESEARCH_DECISION_CONTRACT.md`](docs/RESEARCH_DECISION_CONTRACT.md) —
  frozen hypotheses, evidence boundaries, gates, and permitted conclusions.
- [`docs/TECHNICAL_PLAN.md`](docs/TECHNICAL_PLAN.md) — phased implementation
  plan from source qualification through the prospective lockbox.
- [`docs/PHASE_01_SOURCE_QUALIFICATION.md`](docs/PHASE_01_SOURCE_QUALIFICATION.md)
  - source requirements, audited candidates, result, and permitted next work.
- [`docs/PHASE_02_CANONICAL_LAYER.md`](docs/PHASE_02_CANONICAL_LAYER.md) -
  causal normalization, month-end selection, and dependence-rule result.
- [`docs/PHASE_03_TSMOM_GATE.md`](docs/PHASE_03_TSMOM_GATE.md) - frozen kernel,
  synthetic invariants, and the real-data eligibility result.
- [`docs/PHASE_04_CHALLENGER_GATE.md`](docs/PHASE_04_CHALLENGER_GATE.md) -
  paper-anchored adaptation and separate evaluation gate.
- [`docs/PHASE_05_HISTORICAL_DECISION.md`](docs/PHASE_05_HISTORICAL_DECISION.md)
  - manifest audit, final historical decision, and Phase 06 gate.
- [`docs/RESEARCH_REVIEW_PHASE_00_05.md`](docs/RESEARCH_REVIEW_PHASE_00_05.md) -
  readable end-to-end findings, unknowns, and honest next choices.
- [`docs/MODELED_EXECUTION_POC_CONTRACT.md`](docs/MODELED_EXECUTION_POC_CONTRACT.md)
  - frozen post-v1 assumptions and permitted claim.
- [`docs/PHASE_07_MODELED_EXECUTION_POC.md`](docs/PHASE_07_MODELED_EXECUTION_POC.md)
  - readable POC result and limitations.
- [`references/README.md`](references/README.md) — annotated bibliography,
  access status, and rules for local paper copies.

## Verify the checkout and reproduce Phase 07

Requires Python 3.12-3.14. Install the package and run the network-free quality
gates:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src
```

Populate the ignored Dukascopy cache and run Phase 07, or replay an existing
complete cache without network access:

```powershell
.\.venv\Scripts\python.exe -m fx_mechanical_research.phase07_poc
.\.venv\Scripts\python.exe -m fx_mechanical_research.phase07_poc --offline
```

Phase 01–05 evidence is an immutable historical snapshot. Do not overwrite its
default evidence directories after later append-only trial entries; reproduce
an older phase into a separate target directory when auditing it.

Expected historical v1 decision and separate POC status:

```text
NOT_TESTED
POC_DIAGNOSTIC_ONLY
```

## Relationship to earlier projects

The closed `gbpusd-mechanical-structure` research and the fundamental research
repositories are negative evidence, not parameter libraries. Their neutral data
validation, causal timestamp, cost-model, bootstrap, and artifact patterns may
be reused. Their outcome-selected signals, thresholds, and filters may not.

Because earlier projects exposed parts of 2024–2026 FX history, no historical
window in this workspace will be called an untouched holdout. A true prospective
lockbox starts only after the v1 code and manifest are frozen.

## Decision vocabulary

Historical research can end only as:

- `NOT_TESTED` — qualified data or executable costs are unavailable;
- `DO_NOT_PROCEED_WITH_TSMOM_V1` — a mandatory gate fails; or
- `PROCEED_TO_PROSPECTIVE_OBSERVATION_TSMOM_V1` — all retrospective gates pass.

The last state is not approval for live trading. Deployment requires sufficient
post-freeze prospective evidence under a separately registered risk mandate.
