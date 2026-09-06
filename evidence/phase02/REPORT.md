# Phase 02 - Causal canonical reference-rate layer

Decision: `COMPLETE_PREDICTABILITY_ONLY`

Trading claim: `NOT_TESTED`

The verified BIS slice produced 61,398 canonical daily marks,
2,880 synchronized month-end marks, and 2,871 monthly
reference-rate changes. Every raw currency-per-USD value was inverted to
USD-per-currency and passed the inverse identity check.

Each observation becomes available seven calendar days later at 23:59:59 UTC.
Month-end selection uses only marks available by the decision timestamp, never
forward-fills weekends or holidays, and fails when staleness exceeds
14 days. Maximum observed staleness was
11 days.

The dependence rule inspected only the synchronized equal-weight market-change
series, before any TSMOM signal. It selected a moving-block length of
10 month(s); registered sensitivities
remain 3, 6, and 12 months.

No executable monthly total return was built because the source has no
financing, transaction-cost, or roll observations. No TSMOM signal, strategy
return, control result, or PnL was computed. Phase 03 real-data evaluation must
fail closed while Phase 01 remains `PASS_PREDICTABILITY_ONLY`.
