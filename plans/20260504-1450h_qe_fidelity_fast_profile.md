---
date: 2026-05-04
status: plan-draft
keywords: [speedup, qe_fidelity_fast, profile, reproduce.sh, AD-tolerance, shuffle, deferred-validation]
related_bugs: []
related_plans:
  - 20260504-1300h_qe_fidelity_speedup_systematic_test.md
related_conclusions:
  - 2026-05-04_qe_fidelity_full_vs_QE_published.md
related_results:
  - results_20260504_speedup-test-matrix.md
---

# Plan: `qe_fidelity_fast` profile for reproduce.sh

## Outcome of the systematic speedup test

Per `plans/20260504-1300h_qe_fidelity_speedup_systematic_test.md` and results
matrix `plans/results_20260504_speedup-test-matrix.md`:

**Single confident winner from systematic Phase B+C tests: Idea F (loose AD
convergence tolerance).**

Other ideas: 4 deferred (A already-enabled, B/D/G need significant code lift),
1 fail (E BLAS-no-fork is slower), 1 out-of-scope (C shuffle — per user direction
2026-05-04, the minimum N required to implement shuffle properly with DEATH
shuffle is very large, defeating the variance-reduction-at-smaller-N goal).

The core insight from Phase C: the Reduced_Run scope MID-1 tests are too small
to measurably distinguish the speedup ideas — most setup/drift cost dominates
at that scale, while the AD-iter cost that Idea F targets is too cheap to show
its real win. **Idea F's true speedup is at Baseline scope: cutting 5→3 AD iter
saves ~60 min/scenario × 4 recession scenarios = ~4 hr off the 3 hr 13 min
qe_fidelity_full Step-5a wall.** Projected: ~25-30% Step-5a wall reduction.

## qe_fidelity_fast profile specification

Add to `reproduce.sh` profile case statement (alongside existing qe_fidelity,
production_fast, etc.):

```bash
qe_fidelity_fast)
    # Same methodology as qe_fidelity (ESC, MC, perm_shocks=off, NM tol 1e-4
    # for Step-2, legacy GICx) but with loosened AD convergence tolerance
    # in Step-5 to cut wall time.
    #
    # See plans/20260504-1300h_qe_fidelity_speedup_systematic_test.md and
    # 20260504-1450h_qe_fidelity_fast_profile.md.
    #
    # WELFARE OUT OF SCOPE: this profile produces multiplier results only.
    # Welfare-6 needs the full agent count (10k) and tight AD convergence,
    # both of which qe_fidelity provides (and qe_fidelity_fast deliberately
    # weakens). Users wanting accurate welfare must use qe_fidelity instead.
    export HAFISCAL_INTERPRETATION=ESC
    export HAFISCAL_PERM_DURING_UNEMP=off
    export HAFISCAL_GICX_MODE=legacy
    export HAFISCAL_NM_START_FROM_SAVED=0
    export HAFISCAL_NM_XATOL=1e-4
    export HAFISCAL_NM_FATOL=1e-4
    # Speedup: looser AD convergence + fewer iterations
    export HAFISCAL_AD_CONVERGENCE_TOL=1e-2   # was 1e-3 in qe_fidelity
    export HAFISCAL_AD_MAX_ITER=3             # was 15 in qe_fidelity
    MC_ONLY=true   # Step-5 in MC, matches QE methodology
    log INFO "Profile qe_fidelity_fast: ESC, MC throughout, perm_shocks=off, AD tol 1e-2 + 3 iter"
    log INFO "  Wall time estimate: ~6-8 hours (Step-2 5h36 + Step-5a ~2h projected, Step-5b SKIPPED — see note)"
    log WARNING "  qe_fidelity_fast SKIPS Step-5b welfare-6. For multipliers only."
    log WARNING "  For accurate welfare, use --profile qe_fidelity (~10 hr including welfare)."
    ;;
```

### What the profile does NOT do

1. **Skip Step-5b welfare-6** explicitly — needs a way to instruct the chain
   wrapper (run_step5a_only.py-style logic) NOT to invoke `run_welfare6_parallel.py`.
   Either:
   - Add a new env var `HAFISCAL_RUN_STEP_5B=false` honored by `do_all.py`
   - Or change the `do_all.py` Step-5b call to check `HAFISCAL_AD_MAX_ITER` and
     auto-skip welfare when AD iter is reduced
   - Cleanest: explicit env var in `do_all.py`

2. **Skip Step-1 + Step-2** when re-running with existing estimates — same
   `HAFISCAL_RUN_STEP_X=false` mechanism already in `do_all.py`. Document
   the pattern in the profile docs.

### Implementation steps

1. **Add `HAFISCAL_RUN_STEP_5B=false` toggle** to `do_all.py` Step-5 block (~1 hr work):
   ```python
   # 5b: MC welfare-6 — skipped if HAFISCAL_RUN_STEP_5B=false
   if _env_run('HAFISCAL_RUN_STEP_5B', True):
       substep("Running run_welfare6_parallel.py --baseline (MC welfare-6, parallel)", ...)
       ...
   else:
       progress("Skipping Step 5b welfare-6 (HAFISCAL_RUN_STEP_5B=false)")
   ```
2. **Add `qe_fidelity_fast` profile to `reproduce.sh`** (~30 min work; copy
   from spec above) — including `export HAFISCAL_RUN_STEP_5B=false`.
3. **Update `--profile` help text** to mention `qe_fidelity_fast` (with
   "multipliers only, no welfare" caveat).
4. **Validation test** — see below.

## FULL-scope validation test specification

After landing the profile, run ONE Baseline-scope validation test:

```bash
# Pre-conditions: existing qe_fidelity_full estimates on disk (commit c6935969).
./reproduce.sh --profile qe_fidelity_fast --comp full --accept-dirty --accept-unpushed
```

OR (skipping Step-1/2 for faster validation since estimates already match):

```bash
HAFISCAL_RUN_STEP_1=false \
HAFISCAL_RUN_STEP_2=false \
HAFISCAL_RUN_STEP_3=false \
HAFISCAL_RUN_STEP_4=false \
HAFISCAL_RUN_STEP_5=true \
HAFISCAL_RUN_STEP_5B=false \
./reproduce.sh --profile qe_fidelity_fast --comp full --accept-dirty --accept-unpushed
```

**Expected wall:** ~2-3 hr (vs qe_fidelity_full Step-5a 3h13m → save ~25-30%).
**Expected multipliers:** within ±3% of qe_fidelity_full's Check 1.216, UI 1.178,
TaxCut 0.992.

**PASS criterion:**
- All 3 multipliers within ±3% of qe_fidelity_full
- Wall ≥ 1.2× faster than qe_fidelity_full Step-5a (i.e., ≤ 2 hr 40 min)

If multipliers are out of tolerance, loosen one parameter at a time (e.g.,
test HAFISCAL_AD_CONVERGENCE_TOL=5e-3 and HAFISCAL_AD_MAX_ITER=4 as a more
conservative variant).

## Follow-up work (NOT in this plan)

1. **Re-test with proper MID at Baseline scope**: the systematic test plan's
   MID-1 (Reduced_Run scope) was too small to differentiate speedups. A
   "MID-Baseline" (single shock_type at Baseline N=10k) would take ~20-30 min
   per test and would actually show speedup deltas. Worth doing if more
   speedup ideas are evaluated.

2. **HARK upstream contributions**: any Numba additions identified for Idea D
   should land upstream in HARK (PR), not as monkey-patches in HAFiscal.

3. **Type-level parallelism for Step-5 (Idea B / Path A)**: ~1-2 days
   engineering, no HARK PR required. Replace `Simulate.py`'s serial
   per-type loop with `multi_thread_commands(TypeList, ['solve()',
   'initialize_sim()', 'simulate()'])`. Risk: nesting joblib inside
   the existing per-shock-type fork. Worth pursuing if Idea F alone
   doesn't give enough speedup at Baseline.

## Decision: STOP HERE or PROCEED to implementation?

This plan provides:
- Clear profile spec for qe_fidelity_fast
- Implementation steps (small: ~1.5 hr engineering)
- Validation test specification

**Recommendation:** Land the profile + run the validation test. If validation
passes, qe_fidelity_fast becomes the recommended way to do future "QE
multiplier reproductions" (vs the slower qe_fidelity which produces welfare too).

The ~25-30% speedup from F alone is modest but real and easy. The bigger wins
(60-90%) likely require the deferred-from-Phase-C work (shuffle + N reduction,
or HARK refactor for type-level parallelism). Those are separate plans.

## Tracking

Results file: `plans/results_20260504_speedup-test-matrix.md` (Phase D section
holds the decision matrix).
