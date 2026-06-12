<!-- Status: DONE (superseded by implementation) -->
# Plan: BUG-018 — align synthetic `pLvl` unemployment rate with TM ergodic

## Goal

Use the **same** unemployment rate for the synthetic `pLvl` draw as TM uses for `E[pLvl]`: `u_ergodic` from `compute_baseline_tm_data`, not bare `Urate_normal` when they differ.

## Steps (done)

1. Add `unemployment_rate_for_tm_synthetic_pLvl(bd_i, agent)` in `tm_methods.py` (fallback to `Urate_normal` if `u_ergodic` missing).
2. Replace `Urate_normal` in `effective_pLvl_growth` / `effective_perm_shock_variance_periods` at:
   - `verify_four_methods_agreement._mc_burnin_tm_init`
   - `Simulate.py` TM-init path
   - `test_asymptotic_equality_revised.mc_burnin`
3. Document as **BUG-018** in `BUGS_private/` and update `HARK+HAFiscal_TM_vs_MC_bug_index.md`.
4. Smoke-test imports + short burn-in; run `test_tm_init_mc` / full asymptotic ladder as needed in CI.

## Follow-ups (optional)

- Migrate the same helper into remaining diagnostics that duplicate the synthetic-`pLvl` block (many `diag_*.py` / `phase*.py` files still pass `Urate_normal` when they are paired with TM data that could supply `u_ergodic`).
- Notebook `pLvl_TM_init_ergodic_gap.ipynb`: refresh narrative now that the **u mismatch** branch is fixed in main pipelines.
