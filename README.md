# FX Mechanical Strategy Research

Status: **Phase 01 complete - free-source qualification**

Frozen on: **2026-09-06**

Trading backtest status: **`NOT_TESTED`**

Phase 01 decision: **`PASS_PREDICTABILITY_ONLY`**

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
- [`references/README.md`](references/README.md) — annotated bibliography,
  access status, and rules for local paper copies.

## Reproduce Phase 01

Requires Python 3.12-3.14. Download the official BIS flat CSV archive to the
ignored raw-data folder, extract it, then run:

```powershell
New-Item -ItemType Directory -Force -Path data\raw\phase01
curl.exe -L "https://data.bis.org/static/bulk/WS_XRU_csv_flat.zip" `
  -o "data\raw\phase01\WS_XRU_csv_flat.zip"
tar -xf data\raw\phase01\WS_XRU_csv_flat.zip -C data\raw\phase01
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m fx_mechanical_research.phase01_sources
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src
```

Expected Phase 01 decision:

```text
PASS_PREDICTABILITY_ONLY
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
