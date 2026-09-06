# Research review — Phase 00 through Phase 05

## Executive conclusion

The v1 program produced a valid research infrastructure and a qualified
price-only FX panel, but it did not produce an executable strategy backtest.
The only defensible trading conclusion is `NOT_TESTED`.

This is a data-boundary result, not a negative alpha result. Calling it
`DO_NOT_PROCEED` would falsely imply that H1–H5 were estimated and failed.

## Phase-by-phase result

| Phase | Question answered | Result | What it does not establish |
|---|---|---|---|
| 00 | What exactly will be tested? | Contract v0.1 frozen before TSMOM PnL | Whether TSMOM is profitable |
| 01 | Can a free source support the trading claim? | `PASS_PREDICTABILITY_ONLY` | Executable holding return after costs |
| 02 | Can the chosen source be normalized causally? | 61,398 daily marks; 2,871 monthly changes | Tradable total returns |
| 03 | Is the primary implementation fail-closed? | Synthetic invariants pass; real outcome unopened | H1–H5 outcomes |
| 04 | Is one paper-led challenger preregistered independently? | MOM12,1 G10 adaptation sealed; outcome unopened | Challenger performance or confirmation |
| 05 | What historical decision follows from the contract? | `NOT_TESTED`; Phase 06 inactive | Presence or absence of edge |

## What was learned

The free BIS source is useful for reproducible direction and predictability
research. Across the nine non-USD G10 currencies it provides a synchronized
reference-rate history, explicit quote orientation, and an auditable official
source. It is not sufficient for a PnL claim because reference marks do not
contain the actual holding mechanism, historical bid/ask execution, commission,
financing or forward carry, and roll mechanics.

The engineering lineage also demonstrated that a strategy can be implemented
and tested synthetically without allowing inadequate real data to leak into an
apparently realistic backtest. That separation is the main successful output of
v1.

## What remains unknown

- whether the 12-month TSMOM portfolio has positive net mean return;
- whether it adds information beyond an expanding-mean sign rule;
- whether it survives family-wise multiple-testing correction;
- whether performance is broad across currencies and predefined eras;
- whether its cost headroom exceeds a defensible executable cost base;
- whether the Menkhoff-inspired challenger has any net edge in this G10 form.

## Why Phase 06 must remain closed

The prospective phase requires an effect size and dependence structure from an
eligible historical strategy test so that its observation requirement can be
set by power analysis. Because that test does not exist, opening Phase 06 now
would replace a research rule with an arbitrary calendar target.

## Honest next choices

1. Qualify executable currency futures, forwards, or broker export data and
   rerun the unchanged v1 lineage.
2. Preregister a narrower reference-rate predictability study whose conclusion
   is explicitly not trading profitability.
3. Close v1 permanently as `NOT_TESTED` and begin a separately preregistered
   mechanical hypothesis.

No option should reuse the current price-only panel under the label “net PnL.”
