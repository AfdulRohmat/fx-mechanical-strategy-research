# Phase 04 - Cross-sectional challenger

Decision: `NOT_TESTED`

Status: `COMPLETE_BLOCKED_BEFORE_OUTCOME`

The single registered challenger is `MENKHOFF_MOM12_1_G10_THREE_BY_THREE_V0_1`. It is a disclosed
G10 adaptation anchored to Menkhoff et al. MOM12,1: rank the prior 12-month
executable total return, hold the three winners long and three losers short for
one month, leave three neutral, and rebalance monthly. Each leg has full unit
notional, so the portfolio is dollar-neutral with gross notional two.

The paper itself was hash-verified. Synthetic executable fixtures validate
ranking, causal formation, deterministic ties, leg weights, turnover, and cost
accounting. These synthetic values are not research evidence.

The real gate found 4 blockers before
`data/interim/phase02/monthly_reference_changes.csv` was opened:

- `PHASE01_EXECUTABLE_SOURCE_NOT_QUALIFIED`
- `PHASE02_SCOPE_NOT_EXECUTABLE`
- `PHASE02_TOTAL_RETURN_NOT_BUILT`
- `PHASE03_PRIMARY_NOT_EVALUATED_AND_SEALED`

No challenger signal, return, or PnL was computed. This separate lineage cannot
confirm or rescue TSMOM v1, and its status does not change the primary decision.
