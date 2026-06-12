# Shuffle MC vs Regular MC: NM convergence comparison

**Date:** 2026-04-19 ~07:50
**Scope:** HS full NM, xtol=ftol=1e-3, HAFISCAL_NM_IN_PLACE=1, default
AgentCountTotal (~5,200 HS agents under Baseline cohort weights).

## Setup

Two parallel runs, same everything except the shuffle flags:

- **Regular MC** (`bf09wo0pm`): `HAFISCAL_MC_SHUFFLE=0 HAFISCAL_INCOME_SHUFFLE=0`
- **Shuffle MC** (`bibudxdv0`): `HAFISCAL_MC_SHUFFLE=1 HAFISCAL_INCOME_SHUFFLE=1`

## Result (corrected from trajectory iter_sec, excluding ~25 min module-setup overhead)

Shuffle-on was killed at iter 109 after 76 min of NM wall without terminating. Regular MC converged at iter 88 in 59 min of NM wall.

| Metric | Regular MC | Shuffle MC (killed, not converged) |
|---|---:|---:|
| NM iters | 88 (converged) | 109 |
| Per-iter mean (NM only) | **40.5 s** | **42.1 s** (+4 % slower) |
| Total NM wall | 59.4 min | 76.6 min (+29 % and counting) |
| Final β (trajectory last) | 0.930185 | 0.927926 (drifting) |
| Final ∇ (trajectory last) | 0.070449 | 0.072902 (drifting) |
| Best distance seen | 1.8999 | 1.8201 |
| Reference calibration | β = 0.9298, ∇ = 0.0708 | — |

**Correction to my first-pass analysis.** Earlier I reported "shuffle 33 % faster per iter" based on total elapsed time divided by iteration count — that included ~25 min of one-time module setup (Parameters.py load, AggDemandEconomy construction, initial solve, shock-history generation). The trajectory's actual iter_sec (wall time of each NM function evaluation inside `betas_obj_func_educ`) shows shuffle is **about the same or marginally slower per iter** (+4 %). Shuffle's in-shuffle bookkeeping overhead ≈ the savings from avoiding random draws.

## Interpretation

**Shuffle is not faster per iteration** — marginally slower (+4 %) in the true NM-eval cost, once module-setup overhead is excluded. Shuffle's deterministic transitions save some RNG work but add their own bookkeeping; net roughly wash.

**Shuffle takes more NM iterations to converge under matched 1e-3 tolerance** — and has not terminated by iter 109 (vs Regular MC's 88). My best hypothesis for why:

1. Shuffle's bias characteristics (measured at the isolated-moment level in the Apr 18 overnight experiment: shuffle shifts median aLvlPI by ~0.01 vs Regular MC) mean the shuffle-MC objective has its minimum at a slightly different (β, ∇). NM has to find a new minimum.
2. That new minimum is in a flatter region: shuffle's lower variance lets NM see smaller features of the objective, and the NM simplex has to contract harder to reach the xtol=1e-3 stopping condition.

The earlier Apr 18 overnight experiment (`test_shuffle_hs_precision.py`) showed shuffle reduces cross-seed SD on wealth moments by 40–71 %. That was measured on ONE moment at ONE calibration point. The current test is the end-to-end translation: does that SD reduction become a wall-time win via fewer NM iterations? **Answer: no. At HS 1e-3 on Baseline cohort-weighted N, shuffle costs ~29 % more wall time and still hasn't converged, converging toward a different point than Regular MC.**

## Caveats

- This is ONE edtype (HS) at ONE tolerance (1e-3). Shuffle might behave differently on DO, COL, or at different tolerances.
- Shuffle-on hasn't fully terminated yet — its final numbers may shift.
- The comparison is at HS's Baseline-share N (~5,200 agents). The Apr 18 shuffle-precision experiment was at the "minimum replicate" sizes (N=1,200 and N=8,400) which are different.

## Recommendation

**Keep Regular MC as the default for step 2 estimation.** The promising shuffle SD-reduction result (71 % on median aLvlPI at N=8,400) does not translate into a net wall-time speedup under tight-NM-tolerance estimation at the Baseline cohort-weighted N. Shuffle remains gated behind `HAFISCAL_MC_SHUFFLE=1 HAFISCAL_INCOME_SHUFFLE=1` for opt-in use.

Possible follow-ups (not overnight-sized):

1. Test shuffle at LOOSER tolerance (1e-2). If shuffle's flatter landscape converges well at 1e-2 too, the total wall may still end up faster than regular MC at 1e-2.
2. Test shuffle at the per-group minimum-replicate N (1,200 or 8,400), not the Baseline cohort-weighted N. The lower-N regime is where shuffle's SD reduction is relatively most important.
3. Test shuffle on DO and COL separately — HS may just be a hard case.
