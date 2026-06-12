# Composer: Phase 1 verification (Claude’s implementation)

**Date:** 2026-03-23  
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`  
**HEAD at verification:** `be9a8914` (includes prior `58444c83` Phase 1 bundle)

## What was checked

- **Git:** `HEAD` is `be9a8914` (“Initialize MC agents from TM ergodic…”), child of `58444c83` (“Phase 1: half-step TM fix, per-cohort ergodic, mCount=100 default, BUG-014”).
- **Code (spot review):** `tm_methods.py` — `compute_baseline_tm_data` stores `base_aPol`, `cohort_ergodic`; `propagate_experiment_tm` uses half-step when `base_aPol` is set; defaults `mCount=100`. `Simulate.py` — TM ergodic init + `mc_warmup` default 24. `test_tm_init_mc.py` — BUG-014 lognormal mean correction documented in code.
- **Runs (exit 0):**
  - `bash reproduce.sh --comp mini` (repo root)
  - `python test_cohort_ergodic.py` (FromPandemicCode)
  - `python test_halfstep_verify.py` (FromPandemicCode)

## Conclusion

**As best Composer could tell from this tree, Phase 1 written by Claude appears to work.** Full-size `validate_tm_ui.py` / `test_tm_init_mc.py` were not re-run in this pass; see `debug/20260323-1512h_full_execution_plan_for_AI_v2.md` for expected commands.

**Not verified here:** Phase 2 (Check NPV gap) — out of Phase 1 scope.
