<!-- Status: DONE (superseded by implementation) -->
# TM Scale-Up Validation — Status Report

**Companion to:** `tm_scaleup_plan.md`  
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`  
**Last updated:** 2026-03-30

---

## Executive Summary

Phases 1–5 of the 8-phase TM scale-up plan are complete. The central
finding is highly consistent across all tested dimensions:

> **Differenced policy effects (the paper's reported outputs) agree
> within ~1% between TM and MC.** Raw recession NPVs carry a 3–16%
> systematic TM bias that cancels almost perfectly in differencing.

---

## Phase Results

### Phase 1 — Three Education Types (Reduced_Run, single recession duration)

**Status:** Conditional PASS  
**Script:** `phase1_3types_validation.py`  
**Runtime:** ~60 min (200K agents × 6 seeds)  
**Config:** 3 edu types (point β), Reduced_Run, act_T=100, mCount=100


| Metric                     | Value                                             |
| -------------------------- | ------------------------------------------------- |
| Differenced policy effects | < 1% relative error                               |
| Raw recession NPV          | ~5% (TM less negative than MC)                    |
| Per-type breakdown         | Dropout −0.34%, HighSchool −0.83%, College −3.32% |


**Notes:** The ~5% raw recession error is driven mostly by the College
type (3.3%).  Paper outputs use differenced quantities, so this is
acceptable.  Increased seeds from 3→6 confirmed the error is systematic,
not MC noise.

---

### Phase 2 — Full 21 Types (Reduced_Run, single recession duration)

**Status:** Conditional PASS  
**Script:** `phase2_21types_validation.py`  
**Runtime:** 49.6 min (100K agents × 3 seeds, TM mCount=150)  
**Config:** 21 types (3 edu × 7 β), Reduced_Run, act_T=100


| Experiment              | TM NPV     | MC NPV     | Rel Error  | MC Std |
| ----------------------- | ---------- | ---------- | ---------- | ------ |
| recession               | −1.2107    | −1.2642    | +4.23%     | 0.0224 |
| recessionCheck          | −0.2537    | −0.3193    | +20.54%    | 0.0225 |
| Check                   | 0.9567     | 0.9442     | +1.33%     | 0.0002 |
| **recCheck−rec (diff)** | **0.9570** | **0.9450** | **+1.28%** | 0.0002 |


**Notes:** The 20.5% recessionCheck error is a denominator effect — the
absolute error (~~0.066) is similar to recession's (~~0.054), but divides
by a much smaller NPV (−0.32 vs −1.26).  The differenced quantity
(+1.28%) is what matters for the paper.

**Technical fix applied:** The no-deepcopy MC approach required adding
`eco_mc.switch_shock_type(shock_type)` before each `run_experiment()`
call to rebuild the economy-level `CFunc` with the correct Markov state
dimensions.  Without this, `CFunc[0][12]` IndexError occurred.

---

### Phase 3 — Recession Duration Averaging (Reduced_Run, 3 types)

**Status:** PASS  
**Script:** `phase3_recession_avg_validation.py`  
**Runtime:** 18.8 min (200K agents × 3 seeds, 11 durations)  
**Config:** 3 types (point β), Reduced_Run, max_recession_duration=11


| Experiment              | TM NPV     | MC NPV     | Rel Error  | MC Std |
| ----------------------- | ---------- | ---------- | ---------- | ------ |
| recession (avg)         | −2.1272    | −2.0687    | −2.83%     | 0.0061 |
| recessionCheck (avg)    | −1.0916    | −1.0419    | −4.78%     | 0.0063 |
| **recCheck−rec (diff)** | **1.0356** | **1.0269** | **+0.85%** | 0.0003 |


Per-duration breakdown (recession):


| Duration | Prob  | TM NPV | MC NPV | Rel Error  |
| -------- | ----- | ------ | ------ | ---------- |
| 1        | 0.167 | −0.474 | −0.491 | +3.5%      |
| 2        | 0.139 | −0.877 | −0.846 | −3.7%      |
| 3        | 0.116 | −1.278 | −1.230 | −3.9%      |
| 4        | 0.097 | −1.677 | −1.650 | −1.6%      |
| ...      | ...   | ...    | ...    | −2% to −4% |
| 11       | 0.162 | −4.370 | −4.219 | −3.6%      |


**Notes:** Per-duration errors are stable at 2–4% with no systematic
growth.  Probability-weighted averaging produces −2.83% overall — well
within tolerance.  The differenced quantity (+0.85%) is the best result
across all phases.

---

### Phase 4 — Baseline Parametrization (3 types, single recession duration)

**Status:** Conditional PASS  
**Script:** `phase4_baseline_params_validation.py`  
**Runtime:** 7.2 min (200K agents × 3 seeds)  
**Config:** 3 types (point β), **Baseline** (act_T=400, T_age=200, num_experiment_periods=20)


| Experiment              | TM NPV     | MC NPV     | Rel Error  | MC Std |
| ----------------------- | ---------- | ---------- | ---------- | ------ |
| recession               | −1.7144    | −2.0479    | +16.29%    | 0.1059 |
| recessionCheck          | −0.7102    | −1.0535    | +32.59%    | 0.1051 |
| Check                   | 1.0045     | 0.9944     | +1.02%     | 0.0009 |
| **recCheck−rec (diff)** | **1.0042** | **0.9944** | **+0.99%** | 0.0009 |


Per-period TM−MC error (recession):


| Period | TM      | MC      | Abs Error | Rel Error |
| ------ | ------- | ------- | --------- | --------- |
| t=0    | −0.2387 | −0.2623 | +0.024    | +9.0%     |
| t=10   | −0.0130 | −0.0201 | +0.007    | +35.2%    |
| t=50   | −0.0074 | −0.0116 | +0.004    | +36.1%    |
| t=100  | −0.0048 | −0.0039 | −0.001    | −21.5%    |
| t=200  | −0.0020 | +0.0003 | −0.002    | —         |


**Notes:** The raw recession error (16.3%) is larger than Reduced_Run
(4.2%), driven by longer horizons amplifying the pLvl_factor
approximation error.  However, MC noise is also much larger (std/NPV =
5.2%).  The key metric — differenced policy effect — remains within 1%.

Per-period errors peak at t=10–50 and decay, then show a small negative
tail at t>100 where TM retains a slight negative residual while MC has
settled to zero.  This tail contributes to the NPV but is small in
absolute terms.

---

### Phase 5 — Pipeline Integration (Reduced_Run, sim_method='both')

**Status:** PASS  
**Script:** `phase5_pipeline_test.py`  
**Runtime:** 8.0 min  
**Config:** Full `Simulate()` with `sim_method='both'`, Reduced_Run, no AD

**Verified:**

- `Simulate()` completes without errors with `sim_method='both'` ✓
- Both `_TM` and `_MC` pickle files produced for all 7 experiment types
(recession, recessionCheck, recessionUI, recessionTaxCut, Check, UI,
TaxCut) ✓
- TM output dicts have correct structure (`AggCons`, `AggIncome`,
`NPV_AggCons`, `NPV_AggIncome`) ✓
- `Output_Results()` successfully loads TM pickle files ✓

**Known issue:** `Output_Results()` fails when AD experiment files are
missing (returns `0` instead of dict, then `0['AggCons']` raises
TypeError).  This is pre-existing — `Output_Results` doesn't gracefully
handle partial experiment sets.

---

## Remaining Phases

### Phase 6 — Full Reduced_Run Dress Rehearsal

- 21 types, recession averaging, AD feedback
- Estimated 4–8 hours
- Tests AD convergence (the only untested dimension)

### Phase 7 — Full Baseline Production Validation

- 21 types, Baseline params, all features
- Estimated 12–24 hours (overnight)
- Final numerical validation

### Phase 8 — Production Switch

- Set `sim_method='TM'` as default
- Regenerate paper tables and figures
- Verify LaTeX compilation

---

## Cross-Phase Patterns

1. **Differenced quantities are robust:** Across all phases, the
  differenced policy effects (e.g., recessionCheck − recession) are
   within ~1% of MC.  This is the metric that matters for the paper.
2. **Raw recession NPVs carry systematic bias:** TM recession NPVs are
  consistently less negative than MC (single-duration) or slightly more
   negative (duration-averaged), with 3–16% relative errors.  The
   direction and magnitude depend on parametrization.
3. **The bias cancels in differencing:** Because the bias applies
  similarly to recession and recessionCheck (or other recession
   variants), it cancels when computing policy effects.
4. **MC noise is the practical bottleneck:** At 200K agents × 3 seeds,
  MC noise is ~0.5–5% depending on parametrization.  Distinguishing TM
   error from MC noise requires more seeds for production validation.
5. **Check (no recession) is near-exact:** The stimulus check experiment
  without recession (pure TM distribution propagation) consistently
   shows ~1% error, confirming the TM machinery itself is accurate.

