---
date: 2026-05-17
status: STALLED — Phase C.4 detailed plan; deferred by PHASE_C_RESULTS.md (71 min/run acceptable)
related_plans:
  - 20260517_5D_jax_cpu_pipeline_plan.md
  - 20260516_5D_ambitious_parallelization.md
related_conclusions:
  - reproduce/logs/5D_parallel/PHASE_C_RESULTS.md
related_memory:
  - feedback_cascade_gating.md
  - feedback_parallelism.md
---

# Phase C.4 — Multi-cohort vmap on GPU

**Status:** STALLED

## Goal

Batch all `n_cohorts` cohorts on a leading GPU batch axis so the per-period
kernel processes them in parallel via `jax.vmap`. Currently the JAX driver
calls the per-cohort kernel **serially** 441 times for Baseline (21 cohorts ×
21 durations); with C.4 the per-duration kernel processes all 21 cohorts at
once, reducing the duration loop from 441 to 21 GPU calls.

**Expected wall reduction at Baseline A=60**: 71 min (C.1+C.2) → **~25-30 min**.

## Current state (post C.1+C.2)

For Baseline A=60:
- Setup (parallel solve via C.1): 22 min
- cFunc tabulation (once per cohort via C.2): ~1 min
- **Parallel region: 55 min** = 441 tasks × 7.5s/task at A=60

C.4 attacks the parallel region: 55 min → ~5-10 min via 21-way cohort batch.

## Memory budget analysis

GPU: RTX 4080 with 16 GiB VRAM (15.4 GiB free in practice).

Per-cohort tensor sizes at A=60, J=6, max_atoms=49 (HS_Only-like; Baseline is same J):

| Tensor | Single cohort | 21 cohorts (vmap) |
|---|---:|---:|
| `dist5d` (A,A,A,J,J) | 31 MB | 0.65 GB |
| `joint_markov` (J,J,J,J) | 5 KB | 5 KB (shared, no batch) |
| `cfunc_*_table` (J,M=500) at one macro | 12 KB | 252 KB (per-cohort) |
| `d_src_agg` (A,A,A,J,J) | 31 MB | 0.65 GB |
| Per-atom intermediate (J²,A³) | 31 MB | 0.65 GB |
| Per-atom weight × integrand (J²,A³) | 31 MB | 0.65 GB |
| Mortality newborn dist (A,A,A,J,J) | 31 MB | 0.65 GB |
| **Total per-step peak** | ~150 MB | **~3-4 GB** |

Comfortably fits in 16 GiB VRAM with margin.

Per-atom scan iteration: peak (n_cohorts × J² × A³) = 0.65 GB at A=60.
At A=90: 21 × 36 × 729000 × 4 = ~2.2 GB per intermediate — still fits.

## Implementation strategy

### Step 1: signature refactor (the easiest)

Add a leading cohort batch axis to all per-cohort tensors. Inputs become:

| Tensor | Old shape | New shape |
|---|---|---|
| `dist5d` | (A,A,A,J,J) | (C,A,A,A,J,J) |
| `cfunc_*_table_t` | (J,M) | (C,J,M) |
| `pmv_pn_q`, `xi_pn` etc. | (J,max_atoms) | (C,J,max_atoms) — see Step 2 |
| `joint_markov` | (J,J,J,J) | (J,J,J,J) — shared, no batch |
| `Rfree`, `PermGroFac` | (J,) | (C,J) |
| `Splurge`, `rho` | scalar | (C,) — see Step 3 |
| `newborn_dist5d_diag` | (A,A,A,J,J) | (C,A,A,A,J,J) |

Where C = n_cohorts.

### Step 2: handle IncShkDstn sharing

Within a Baseline education group, the 7 β-atoms share the same `IncShkDstn`.
Across ed_types, IncShkDstn DIFFERS. So:
- Option A (simplest): broadcast IncShkDstn to (C, J, max_atoms) — accepts
  redundancy across the 7-cohort blocks. ~3× wasted memory but trivial code.
- Option B (efficient): tag cohorts by ed_type and gather. More code, less
  memory.

**Recommend Option A** for first implementation; revisit if memory is tight
(it isn't at A=60).

### Step 3: handle per-cohort scalars

`Splurge`, `rho`, `Cratio_pol`, `Cratio_none` could be per-cohort. In practice
they're shared within a parametrization (and across cohorts of same params).
**Pass as scalars** (not batched) — simpler.

`AggDemandFac_pol`, `AggDemandFac_none`, `TranShk_addition_*`: per-period
shared across cohorts. Pass as scalars/arrays of `J`, not batched.

`LivPrb_avg`, `pLvl_factor`, `N_eff`, `E_pLvl`: **per-cohort**. Pass as
`(C,)` arrays. The pLvl recurrence is done OUTSIDE the JIT kernel (in the
Python loop over durations) so the (C,) update is cheap CPU work.

### Step 4: refactor the per-step kernel

`_step_period_5d_jax_v3_impl` and its `_step_period_5d_jax_v3_impl_singleatom`
need to accept the batched inputs and produce batched outputs.

The cleanest way: add `jax.vmap` over the leading cohort axis around the
existing single-cohort kernel. Pseudocode:

```python
@jax.jit
def _step_period_5d_jax_v4_impl(
    dist5d_batch,  # (C, A, A, A, J, J)
    ...
):
    # vmap the v3 single-cohort kernel over the cohort axis
    vmapped = jax.vmap(
        _step_period_5d_jax_v3_impl_singleatom_singlecohort,
        in_axes=(None,  # atom_k (shared scalar)
                 0,     # dist5d_batch → cohort batch
                 None,  # aGrid (shared)
                 None,  # joint_markov (shared within parametrization)
                 0,     # d_src_agg per-cohort
                 0,     # cfunc_pol_table_per_cohort
                 0,     # cfunc_none_table_per_cohort
                 0,     # cfunc_b_table_per_cohort
                 None,  # m_grid (shared)
                 0,     # IncShk per-cohort (broadcast within ed_type)
                 ...)
    )
    # ... scan over atom_k as before, but vmap'd ...
```

The `jax.lax.scan` over atom_k stays — it accumulates per-cohort
intermediate state.

### Step 5: refactor `compute_joint_welfare5d_jax` driver

Instead of being called per-cohort, the driver is called ONCE per duration
with batched inputs assembled from all cohorts. The Python loop becomes:

```python
for d_idx, dur in enumerate(durations):
    path = build_path(dur)
    # Pass batched inputs
    res_batch = compute_joint_welfare5d_jax_batched(
        all_cohort_agents,  # list of n_cohorts agents
        all_cohort_bd,
        all_cohort_cfunc_tables,
        EconomyMrkv_path_pn=path, act_T=act_T,
    )
    # res_batch is per-cohort series; combine with cohort weights
    for c_idx in range(n_cohorts):
        welfare_num_total += rec_probs[d_idx] * res_batch[c_idx]['welfare_num_series']
        ...
```

Total GPU calls: 21 (one per duration), each with 21-way cohort batch.

### Step 6: handle pre-t0 SPIKE state-shift

Currently applied per-cohort in `compute_joint_welfare5d_jax`. In batched
form, apply to `dist5d_batch[c, :, :, :, 0, j_b]` for each cohort. The spike
fraction is constant across cohorts (it's a parameter, not cohort-specific),
so this becomes a single vectorized op.

### Step 7: pLvl recurrence per cohort

After each period, the pLvl_factor update uses the dist5d marginal (per
cohort). Currently scalar update. In batched form: (C,) vector update,
done on CPU after pulling marginals from GPU.

## Validation cascade (per [[feedback_cascade_gating]])

### Gate 1: HS_Only (n_cohorts=1) — bit-identical sanity

The batched kernel with n_cohorts=1 should give bit-identical results to
the current single-cohort kernel (since there's no actual vmap parallelism).
This is the basic correctness check.

Pass criterion: `np.allclose(rtol=1e-12)` on ui_rec, welfare_num_series.

### Gate 2: Reduced_Run (n_cohorts=3) — multi-cohort correctness

Run with 3-cohort batch. Compare per-cohort welfare series to the existing
per-cohort sequential runs.

Pass criterion: `np.allclose(rtol=1e-5)` per cohort.

### Gate 3: Baseline (n_cohorts=21) — full scale

Run with 21-cohort batch. Compare aggregate welfare to existing JAX
serial Baseline result (ui_rec_5D = 1.7866 at A=60).

Pass criterion: ui_rec rel diff < 0.5% (= paper precision; bit-identical
not expected due to fp ordering).

### Gate 4: speedup measurement

If Gate 3 passes, measure wall:
- C.1+C.2+C.4 at Baseline A=60 — expected ~25-30 min
- vs C.1+C.2 only (71 min) and JAX serial (86 min)

## Risk and failure modes

| Risk | Mitigation |
|---|---|
| Memory blowup at A=60 with batch | Monitor VRAM via `nvidia-smi`. Fallback: scan over cohorts in chunks of 7 (= ed-type groups). |
| Numerical drift from vmap | Use `rtol=1e-5` for FP32 vmap vs serial. Document if drift exceeds paper precision. |
| JIT compile time blows up | Specify static shapes carefully. May need separate JIT per n_cohorts (HS_Only=1, RR=3, Baseline=21). |
| Bilinear scatter doesn't vmap cleanly | The scatter writes to per-cohort dist5d_next slices. JAX `.at[].add()` should vmap over the leading cohort axis. Test in isolation. |
| Per-cohort newborn dist build | Currently done CPU-side per cohort. With batch, build all 21 newborn dists on CPU then stack to (C,A,A,A,J,J). |

## Implementation phases (cascade-gated)

| Phase | Description | Cost | Pass criterion |
|---|---|---:|---|
| **C.4.1** | Refactor `_step_period_5d_jax_v3` to add cohort batch axis (no driver changes yet) | 0.5 day | Manual call with n_cohorts=1 matches current at A=20 |
| **C.4.2** | Validate at HS_Only A=30 end-to-end | 0.25 day | Bit-identical to current |
| **C.4.3** | Build batched cohort-input assembly in driver | 0.5 day | Compiles; no runtime errors at Reduced_Run A=30 |
| **C.4.4** | Validate at Reduced_Run A=30 (3 cohorts) | 0.5 day | Per-cohort series match within rtol=1e-5 |
| **C.4.5** | Validate + benchmark at Baseline A=30 (21 cohorts) | 0.5 day | ui_rec within 0.5% of 1.7905; wall measurement |
| **C.4.6** | Validate at Baseline A=60 production | 0.5 day | ui_rec within 0.5% of 1.7866; wall ≤30 min |
| **C.4.7** | Document + cutover | 0.5 day | Plan committed; PHASE_C_FINAL doc |
| **Total** | | **3-4 days** | — |

## Cost-benefit summary

- **Cost**: 3-4 focused days of kernel + driver refactor with iterative validation
- **Benefit**: Baseline A=60 wall **71 min → 25-30 min** (~2.5× additional speedup on top of C.1+C.2; ~16-20× speedup vs the original CPU-only 8 hr 5 min)

ROI: if 5D Baseline runs are routine (≥weekly), the dev investment pays
back quickly. If once-per-month, the 71-min current state is fine.

## Decision triggers

Pursue C.4 if any of:
- 5D welfare measurement becomes a regular tool (>1×/week Baseline runs)
- Need to run cascade more deeply (A=90 / A=120 — though cascade rule says
  stop at A=60 for current parametrization)
- Multiple parametrization sweeps (HS_Only / Reduced_Run / Baseline / sensitivity
  analyses) become workflow

Defer C.4 if:
- Current 71-min Baseline meets workflow needs
- Higher-priority work (e.g., paper revisions, other validation) is queued
- The 3-4 day dev cost would delay other deliverables

## Out of scope

- Multi-GPU (single RTX 4080)
- FP16 / mixed precision (paper precision adequate at FP32)
- Switching to a different framework (numba CUDA, CuPy) — JAX is the established choice
- HARK changes (build_and_solve remains the same; only the per-period kernel changes)

## Files to be modified

- `Code/HA-Models/FromPandemicCode/welfare6_tm_joint5d_jax_kernel.py`
  - New `_step_period_5d_jax_v4_impl` and JIT'd wrapper
  - New `compute_joint_welfare5d_jax_batched` driver
- `Code/HA-Models/FromPandemicCode/welfare6_tm_joint5d_baseline.py`
  - New `--cohort-vmap` flag (or default behavior when --jax is set with n_cohorts > 1)
  - Refactored main loop: iterate durations only, call batched kernel
- New test files:
  - `validate_batched_jax_kernel.py` — bit-equivalence + speedup at each gate
