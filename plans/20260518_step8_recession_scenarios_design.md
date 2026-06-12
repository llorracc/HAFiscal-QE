# Step 8 — JAX MC for recession scenarios — design doc

**Date:** 2026-05-18
**Status:** DESIGN (not yet implemented)
**Prereq:** Step 7 complete; JAX kernel validated bit-comparable to HARK at base scenario

## Goal

Extend the JAX MC kernel to handle HAFiscal's recession scenarios (recession, recessionUI, recessionCheck, recessionTaxCut), which require time-varying macro state.

## What's different from base

| aspect | base scenario | recession scenarios |
|---|---|---|
| macro state | 1 (no recession) | 22-42 macro states (recession + recovery path) |
| MrkvArray | (J, J) | (n_macro, J, J) — per-macro transition |
| EconomyMrkv path | constant 0 | time-varying, e.g., [1, 3, 5, 7, 9, 0, 0, ...] |
| simulation | one path | multiple durations, weighted by recession_prob |
| IncShk | per-macro per-micro | per-(macro × micro) — but typically same for base macro |
| Cratio (AD) | 1.0 | 1.0 for non-AD, time-varying for AD scenarios |

## Architecture changes needed

### 1. Multi-macro kernel inputs

Add per-macro dimension:
- `cfunc_table_macro: (n_macro * J, M_grid)` — combined index = macro × J + micro
- `MrkvArray_macro: (n_macro, J, J)` — per-macro transition
- `IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro: (n_macro * J, max_atoms)` — per-(macro × micro)
- `EconomyMrkv_path: (T,)` — per-period macro state

### 2. Per-period macro indexing

In the JAX scan step, at each period t:
```python
macro_t = EconomyMrkv_path[t]  # scalar per period
combined_idx_t = macro_t * J + mrkv_micro_prev  # for transition lookup
mrkv_combined_now = sample from MrkvArray_macro[macro_t][mrkv_micro_prev]
# Then shock/cFunc lookups use mrkv_combined_now (already includes macro)
```

### 3. Per-duration aggregation

For each duration `d in 1..max_recession_duration`:
1. Build EconomyMrkv_path with recession ending at period d
2. Run JAX kernel for this path
3. Save (AggInc[d, :], AggCons[d, :], cLvl_panel[d, :, :])

Aggregate with `rec_probs[d]` (geometric distribution).

### 4. Welfare-6 cell post-processing

The output panels feed into existing `welfare6_mc()` which already handles per-duration aggregation. No changes needed there.

## Implementation plan

### Phase 8.1: Single-cohort recession (HS_Only, single duration)
- Extend `simulate_jax` to accept `EconomyMrkv_path` and multi-macro arrays
- Test with HS_Only recession scenario, single duration d=10
- Validate against HARK MC output (`recession.pkl`)
- ~half day

### Phase 8.2: Per-duration loop (HS_Only)
- Wrap recession sim in Python loop over durations 1..20
- Aggregate with rec_probs
- Verify welfare6 cell ui_rec matches HARK to within MC noise
- ~half day

### Phase 8.3: Multi-cohort + recession
- Extend `simulate_all_cohorts` for recession
- Verify Reduced_Run recession matches HARK
- ~half day

### Phase 8.4: AD scenarios
- Add Cratio time series as input to kernel
- Verify recession_AD, etc. match HARK
- AD outer loop stays in Python; JAX is inner sim
- ~1 day (the AD loop convergence is the tricky part)

**Total Step 8 estimate: 2-3 days.**

## Validation gates

1. recession scenario (single duration): JAX vs HARK AggInc per period correlation > 0.99, mean ratio 1.000 ± 1%
2. recession scenario (per-duration aggregate): same as #1
3. recessionUI (with UI extension): same
4. recessionCheck, recessionTaxCut: same
5. recession_AD (with aggregate demand): same after AD convergence
6. End-to-end welfare-6 cells (Check, UI, TaxCut, etc.): match HARK reference within MC SE

## Risks and unknowns

1. **Per-macro IncShkDstn**: HAFiscal modifies IncShkDstn per scenario (e.g., recessionUI adds UI benefits to xi for u3Q/u4Q during recession macro). My extract_hark_kernel_inputs only handles the base scenario; needs scenario-aware extension.

2. **BUG-043 UI encoding**: 6-state UI encoding with payout-based extension must be preserved exactly. The recessionUI scenario activates the extension at specific macro states.

3. **AD loop convergence**: Outer iteration over Cratio. Convergence criterion must match HARK's (typically 1e-2 relative tolerance).

4. **Per-duration cohort init**: each duration sim should start from same agent state. Currently the recession init applies the urate-spike which is per-cohort-specific. Need to preserve this.

5. **TM-initialized vs lognormal-initialized**: HAFiscal MC sometimes initializes from TM-a ergodic. JAX should support both modes.

## Speedup expectations

For Baseline 5× welfare-6 (12 scenarios × 4 AD iters × 20 durations × 21 cohorts × 100 periods × 160k agents):
- HARK current: ~3-5 hr per seed
- JAX expected: ~10-30 min per seed (depending on AD-loop iteration count)
- 10-30× wall-time speedup (lower than inner-kernel speedup due to AD-loop serialization)

## What this design does NOT cover

- Welfare-6 cell computation: already in `run_welfare6_parallel.py`'s `welfare6_mc()`; just feed it JAX outputs
- Multi-seed CRN preservation: each seed runs independently with shared random keys; CRN handled naturally
- Production CLI: `--use-jax-mc` flag on `run_welfare6_parallel.py` is Step 12

## Next step if greenlit

Begin Phase 8.1: extend `jax_mc_minimal.py` to accept `EconomyMrkv_path` and per-macro arrays. Estimated ~3-4 hours for the kernel extension; validation requires a HARK recession reference pickle (need to generate).
