# FX Mechanical Strategy Research

Status: **Phase 00 complete — paper backbone and research contract frozen**

Frozen on: **2026-09-06**

Backtest status: **not started**

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
- [`references/README.md`](references/README.md) — annotated bibliography,
  access status, and rules for local paper copies.

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
