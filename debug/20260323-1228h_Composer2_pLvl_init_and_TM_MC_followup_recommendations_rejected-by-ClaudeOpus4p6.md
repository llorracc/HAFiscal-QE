# Evaluation of Composer2 pLvl Init Recommendations

**Evaluator:** Claude Opus 4.6
**Date:** 2026-03-23
**Input document:** `debug/20260323-1228h_Composer2_pLvl_init_and_TM_MC_followup_recommendations.md`

---

## Prompt

> read debug/20260323-1228h_Composer2_pLvl_init_and_TM_MC_followup_recommendations.md, which contains recommendations from another AI for further improvements in the construction of the initial distribution of p. Evaluate these recommendations and assess whether they are worth implementing, or whether they would require a fair amount of work for a modest (or even negligible) amount of improvement.

---

## Assessment of Recommendations

**R1 (Shared helper for pLvl init) — Low priority, moderate effort.**
The formula is 3 lines. `compute_pLvl_distribution` already exists in `tm_methods.py` and handles the cohort math. Extracting a `draw_log_pLvl_conditional_on_age` helper is clean software engineering but doesn't solve any current problem. After the BUG-014 fix, the initialization is 0.4% off — good enough. **Skip for now.**

**R2 (Refactor test to use shared helper) — Skip.** Depends on R1. The test works.

**R3 (Scalar rescale to match E[pLvl]) — Negligible benefit, trivial effort.**
After BUG-014, we're at 20.95 vs 21.02 (0.4% off). A 2-line rescale would close this, but 0.4% is noise-level and cancels in treatment effects. **Not worth the code clutter.** If we ever need it, it's `agent_pLvl *= E_pLvl_analytical / np.mean(agent_pLvl)`.

**R4 (Employment-conditioned pLvl correction) — Negligible benefit, moderate complexity.**
E[PermShk] = 1 for both employed and unemployed, so E[pLvl|age, state] is the same regardless of employment state. The only difference is variance (unemployed periods don't add PermShk variance), which affects ~3% of the population by a tiny amount. **Not worth pursuing.**

**R5 (Documentation) — Already mostly done.** The BUG-014 entry, changelog, and debug document cover it. Adding a cross-link somewhere is a 1-line edit but doesn't meaningfully improve discoverability.

**R6 (Out of scope acknowledgment) — Agree.** Full joint analytical `(Mrkv, mNrm, pLvl)` init is over-engineering for something the TM ergodic + simple pLvl sampling already handles to 0.4%.

**Bottom line:** None of these are worth implementing right now. The BUG-014 fix already brought pLvl initialization to within 0.4% of the analytical value. The remaining work items are the **aNrm drift (6%)** and the **Check TM-vs-MC gap (29%)**, both of which are unrelated to pLvl initialization.
