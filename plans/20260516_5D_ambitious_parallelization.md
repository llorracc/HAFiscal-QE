---
date: 2026-05-16 (revised 2026-05-16 21:40 ET after Phase A Baseline-infeasibility discovery)
status: REVISED — Phase A scope reduced; Phase B promoted to critical path
keywords: [welfare-6, 5D, parallelism, JAX, GPU, cohort, performance, roadmap]
related_plans:
  - 20260516_5D_duration_parallel_quickwin.md
related_conclusions:
  - 2026-05-16_BUG046_FINAL_summary.md
related_memory:
  - feedback_parallelism.md
  - feedback_cascade_gating.md
  - feedback_deferred_followups.md
  - feedback_grid_refinement_stepwise.md
  - reference_econ_mw_wsl_gpu_stack.md
---

# Plan: ambitious 5D welfare driver parallelization roadmap

## REVISION SUMMARY (2026-05-16 evening)

Phase A (cohort-axis CPU Pool) **delivered for HS_Only (1 cohort) and
Reduced_Run (3 cohorts)** as expected. **For Baseline (21 cohorts at
A=50) it was empirically infeasible**: 22 workers at 99.6% CPU for
3 hr 45 min produced ZERO completed tasks. Root cause is the J⁴ inner
loop in `_step_period_5d` at Baseline's recession Markov state space
(J_pn ≈ 132 or 252 with AD scenarios, vs HS_Only's J=24 → (132/24)⁴ ≈
915× per-task cost).

**Implications:**
1. Phase A's claim "unblocks Baseline" was wrong. Cohort parallelism
   doesn't address the J⁴ Python-overhead bottleneck.
2. Phase B (JAX-GPU port of `_step_period_5d`) is the only credible
   path to Baseline 5D in usable time. Promoted from "ambitious
   extension" to **critical path**.
3. A new option, **Phase A.5 (CPU sparsity + vectorization)**, is
   worth exploring as a lower-risk alternative or complement to
   Phase B.

The original phase numbering is preserved below for continuity, but
the recommended order is now: **A (done for HS_Only/Reduced_Run) → A.5
(profile + sparsity) → B (JAX-GPU)**, not the original ROI ranking.

---

## Context

The quick-win duration-loop parallelization (commit `a9c692f9`, plan
`20260516_5D_duration_parallel_quickwin.md`) achieved 3.3× speedup at
HS_Only A=50 — taking per-cell 5D/MC ratio from ~110× to ~30×.

GPU stack on `econ-mw-wsl` is fully installed (RTX 4080, 16 GiB,
CC 8.9, CUDA 12.6, cuDNN 9.22 — see
`[[reference_econ_mw_wsl_gpu_stack]]`). JAX-GPU is the headline target.

## Cross-phase invariants

All phases share a correctness gate against the existing sequential
pickle baselines (`reproduce/logs/5D_parallel/baseline_*.pkl`) via
`Code/HA-Models/FromPandemicCode/check_5d_parallel_equivalence.py`.

Pass criterion depends on numerical precision:
- **Pure CPU-CPU comparison (FP64 vs FP64, same code path)**:
  `np.array_equal == True` (zero ULP, bit-identical).
- **CPU-CPU comparison (FP64 vs FP64, different code path)**: 
  `np.allclose(rtol=1e-10)` — small numpy/BLAS environment differences
  acceptable. Used in Phase A v1 vs v2 (~1e-11 typical).
- **CPU-FP64 baseline vs GPU-FP32**: `np.allclose(rtol=1e-5, atol=1e-6)`
  on raw per-duration series, AND headline welfare cells (ui_rec etc.)
  agree to **paper precision (4 decimals)** after rounding. Used in
  Phase B. See "Precision decision" below.

## Precision decision: FP32 acceptable on GPU

Default JAX on GPU is FP32. We **accept FP32** for the JAX port rather
than forcing `jax_enable_x64`. Rationale:
- Headline output is welfare ratios rounded to 4 decimals (e.g.
  `ui_rec = 1.81`). FP32 has ~7 decimal digits of precision — well
  above paper precision.
- 5D `dist5d` array is `(A, A, A, J_pn, J_b)` = 50³·24² ≈ 72M
  elements. FP32 halves memory vs FP64 (290 MB vs 580 MB per array)
  and roughly doubles throughput on Ada Lovelace.
- The welfare-6 numerator has a `u(c_pol) − u(c_none)` cancellation
  that worried me, but `c_pol ≈ c_none` only in non-recession cells
  (which we don't care about for UI) and the magnitudes are
  `O(c^{1-γ}) ≈ O(1/c) ≈ O(0.1)` — FP32's ~1e-7 absolute precision
  is fine.
- If a specific cell shows precision pathologies during validation,
  we can selectively promote that cell to FP64 without abandoning
  FP32 elsewhere.

The Phase B equivalence harness must demonstrate that this decision
holds empirically — not just argued from first principles.

## Phase A — Cohort-axis CPU Pool — DONE for small parametrizations only

### Status (revised)

Delivered for HS_Only and Reduced_Run. **NOT feasible for Baseline**
on CPU — see revision summary.

### What worked

- HS_Only A=20: 27.5 s wall, ui_rec=2.0400 (bit-identical to quick-win baseline)
- Reduced_Run A=20: 90 s wall, **first-ever 5D Reduced_Run number
  ui_rec=1.9140** (vs MC fixed-Jensen 1.9973 → 4% gap, consistent with
  HS_Only's 3% gap)
- Phase A driver `welfare6_tm_joint5d_baseline.py` works correctly
  for any parametrization with sufficiently small J × A.

### What didn't work

- Baseline A=50: 22 workers, 99.6% CPU each, 3 hr 45 min, **0 of 441
  tasks completed**. Killed. Per-task cost extrapolation suggests
  ~15 hr/task on CPU at this grid.

### Why Baseline blew up

The per-step kernel `_step_period_5d` has a quadruply-nested Python
loop over `(j_pn_src, j_b_src, j_pn_dst, j_b_dst)`. With sparsity
skip on zero entries, the actual iteration count is much less than
J⁴ but still proportional to J_pn × J_b × (effective non-zero
transitions). At HS_Only J=24 this is ~30k iterations per period; at
Baseline (recession with AD: J_pn ≈ 252) it's ~tens of millions per
period, and per-iteration cost includes cFunc evaluations that are
themselves O(A) numpy ops.

The cohort axis of Phase A is fully parallelizable but the per-task
cost dominates. Phase A is NOT the right tool for Baseline.

## Phase A.5 — CPU profile + sparsity + vectorization — NEW

### Goal

Before committing to the multi-day JAX-GPU port, **profile the
per-step kernel on Reduced_Run A=50 to identify where time actually
goes**. Two possible outcomes:

1. **Bottleneck is Python overhead in the quadruple loop**: numpy
   vectorization or numba `@njit` could give 10-100× without GPU.
   Path forward: rewrite the kernel as a vectorized tensor op.
2. **Bottleneck is cFunc evaluation**: the HARK cFunc objects do
   scipy.interpolate work that's hard to vectorize. Path forward:
   precompute cFunc tabulations on a flat grid, replace cFunc calls
   with direct array lookups.

Either way the result is a CPU-resident kernel that's 10-100×
faster, which may make Baseline A=50 feasible (~minutes instead of
days).

### Why first (before Phase B)

- **Low risk**: incremental optimization of existing code. No new
  dependencies, no precision concerns.
- **Diagnostic value**: even if it doesn't make Baseline feasible
  alone, the profiling output informs Phase B's port strategy.
- **Could obviate Phase B**: if 50× sparsity+vectorization on CPU is
  enough for Baseline, the multi-day JAX port may be unnecessary.

### Plan

A.5.1 — Run cProfile on a single Reduced_Run cohort at A=50 with
one duration, capture which functions dominate.

A.5.2 — Vectorize the quadruple loop. Convert
`for j_pn_src, j_b_src, j_pn_dst, j_b_dst` into broadcasting over
4D index arrays, exploiting numpy's BLAS.

A.5.3 — Tabulate cFunc on a flat (m_grid, j_pn) array, replace
in-loop `cFunc[j](m, Cratio)` with `np.interp` lookups.

A.5.4 — Re-benchmark Reduced_Run A=50 single-cohort. If <10× total
speedup, give up on A.5 and go to Phase B. If 50×+, retry Baseline
A=50.

### Estimated cost

1-3 days. Lower risk than Phase B.

## Phase A.6 — beta-vectorize the per-cohort kernel — NEW (2026-05-17)

### Background

The current Phase A driver runs `n_cohorts × n_durations` = 21 × 21
= 441 independent (cohort, dur) tasks at Baseline. But within each
education group, the 7 β-atoms share the **income process** entirely:
- `CondMrkvArrays` (macro Markov transitions)
- `IncShkDstn` (income shock distributions)
- The duration-Markov path
- The joint Markov tensor (`compute_joint_markov` output)

The β values only enter through the agent's **solved cFuncs** (and
the initial baseline_tm_data ergodic). So the per-period kernel
evolves 7 different `dist5d` arrays in lockstep — same shocks, same
Markov realizations, different consumption policies.

The optimal factoring: **63 tasks** (= n_durations × n_ed_types =
21 × 3), each evolving 7 dist5d arrays in parallel inside.

### Goal

Refactor `compute_joint_welfare5d` / `_step_period_5d` to accept a
**leading β-batch dimension** on `dist5d` (shape becomes
`(n_beta, A, A, A, J_pn, J_b)`). At each period:
- Markov path step: same for all 7 betas (broadcast)
- IncShkDstn atom enumeration: same for all 7 betas (broadcast)
- cFunc lookup: 7 separate calls (one per β) — broadcast result to
  match dist5d batch shape
- Asset update + 3D bilinear distribute: vectorized over β-batch
- Welfare integrand sum: per-β scalar accumulator

Within an education type, the driver evolves one (n_beta=7, A, A, A,
J, J) tensor per (dur) — single Python iteration, single
compute_joint_markov call, but 7-way cFunc evaluation.

### Speedup estimate

NOT a clean 7× because cFunc evaluations are still 7-fold (one per
β). Realistic factor:
- Python-interpreter overhead savings (Markov path build, IncShkDstn
  extraction, joint_markov build): ~7× on those sub-tasks
- Per-period loop body: same total cFunc work, but interpreter
  overhead amortized
- Memory: dist5d storage is 7× larger per task but # of tasks is 7×
  fewer → same total memory budget

Best estimate: **1.5–3× total wall speedup**. For Baseline:
8 hr → 3–5 hr.

### Risk

Medium. Pure refactor of the existing pure-numpy kernel (no new
deps, no precision concerns). Risk surface: the per-period kernel
has many small numpy ops that broadcast in subtle ways; introducing
a leading β-batch axis could expose hidden assumptions.

### Validation

Reuse the bit-identical equivalence harness:
- Run β-vectorized kernel with `n_beta=1` and confirm bit-identical
  to existing per-cohort output
- Run β-vectorized with `n_beta=7` and confirm sum-of-7-betas
  matches the existing 7 independent runs at FP64 tolerance
- Run full HS_Only (1 cohort = 1 beta) — trivially identical to
  current
- Run full Reduced_Run (3 cohorts = 1 beta each per ed_type, since
  Reduced_Run uses DiscFacCount=1) — same as Baseline-style
  vectorization with `n_beta=1`. Should be identical.
- Run full Baseline (3 ed_types × 7 betas = 21 cohorts) — diff vs
  existing Baseline A=60 pickle (`cascade2_Baseline_A60.pkl`).
  Pass: `np.allclose(rtol=1e-10)` on welfare_num_total + all 3
  reduced arrays.

### Estimated cost

0.5–1 day of careful refactor + 0.5 day validation = 1–1.5 days.

### Combined with A.5 + BLAS fix

A.6 (beta-vectorize) on top of A.5 (numpy vectorize the J⁴ loop) on
top of BLAS-thread-cap fix could compound to ~5–10× total wall
speedup at Baseline. 8 hr → 1–2 hr.

### Defer or do?

Depends on workflow needs. If Baseline 5D needs to be a regular
tool (e.g., re-run for every BUG investigation, multiple grid
checkpoints), A.6 is worth the 1–2 days. If it's a one-time
validation, the existing 8-hour run is acceptable.

## Phase B — JAX-GPU port — CRITICAL PATH

### Status

- **B.0 done**: jax 0.10.0 installed; RTX 4080 accessible via
  `jax.devices()`
- **B.1 done**: `compute_joint_markov_jax` ported; 75-221× speedup
  at production J; FP64 bit-exact / FP32 abs-precision ~1e-7
- **B.2 Step 1 done**: `bilinear_3d_distribute_jax` ported; mass
  conservation 6.3e-9; FP32 abs-precision ~5e-6 at A=50
- **B.2 Step 2-5 NOT done**: the big work (port `_step_period_5d`)
  is multi-day. See `reproduce/logs/5D_parallel/B2_HANDOFF.md` for
  detailed implementation plan.

### Goal

JIT-compile and GPU-execute the per-step kernel. Use `jax.vmap` to
parallelize the duration axis (11) and welfare-cell axis (2 for UI)
inside a single JIT region. Cohort axis iterated on CPU outer loop.
Target: **HS_Only ui_rec 198 s → ~5-15 s; Baseline ui_rec from
infeasible → ~30-60 min**.

### Why JAX-GPU as primary (not numba-CPU)

- GPU stack already installed and verified
- `jax[cuda12]` pip wheels work directly
- 5D dist5d at A=50 FP32: 290 MB → fits comfortably in 16 GiB VRAM
- Ada Lovelace tensor cores (CC 8.9) accelerate dense contractions
- `vmap` over duration + cell axes simplifies parallelism

Numba-CPU is the fallback only.

### VRAM budget

Grid sweeps follow the cascade rule `[[feedback_grid_refinement_stepwise]]`
(v2 of 2026-05-16): **A=30 → A=60 → A=90 (optionally 120)**,
projection-based. Find worst-metric A=30→A=60 shift, project A=60→A=90
shift as 0.5× that, advance only if projected ≥ 1%. A=150+ is out of
scope. Minimum grid for any 5D work: A=30. Empirical 2026-05-17:
both HS_Only and Reduced_Run converged at A=60 (worst-metric shifts
0.035% / 0.115% respectively).

The 16 GiB RTX 4080 has **two distinct VRAM cliffs**:

- **Soft cliff** (around A=75-100, depending on vmap width). The full
  (duration × cell) vmap stops fitting. Mitigation is a narrower
  `vmap_axes` and an extra outer Python loop — **same kernel
  signature, no restructuring**. CPU-side outer iteration is
  performance-neutral at A=100+ (single-instance compute saturates
  bandwidth; launch overhead negligible).
- **Hard cliff** (around A≈160). A *single* `dist5d` instance stops
  fitting. Mitigation requires chunking the `(A, A, A, J, J)` tensor
  itself across multiple kernel launches with explicit boundary
  stitching — **fundamental restructuring**. This is the architectural
  reason A=200 is out of scope.

Per-array sizes (FP32, J=24 for HS_Only):

| A | Single `dist5d` | Cell-vmap (2×) | Duration-vmap (11×) | Full vmap (22×) |
|---:|---:|---:|---:|---:|
| 50  | 288 MB  | 0.6 GB  | 3.2 GB  | 6.3 GB (fits) |
| 100 | 2.3 GB  | 4.6 GB (fits) | 25 GB | 51 GB |
| 150 | 7.8 GB  | 15.5 GB (tight) | 85 GB | 171 GB |
| 200 | **18.4 GB (overflows single)** | — | — | — |

**Important caveat**: VRAM table above is for J=24 (HS_Only). At Baseline,
J_pn could be 132-252; per-array memory scales as J². So Baseline `dist5d`
at A=50 is up to 290 MB × (132/24)² = ~8.8 GB single instance. Cohort axis
on CPU is correct (one Baseline cohort per GPU invocation).

### Implementation

1. **Port `_step_period_5d` to JAX**. Pure-functional rewrite using
   `jnp` instead of `np`. Replace `scipy.interpolate` cFunc evaluation
   with explicit JAX lookup against precomputed cFunc tabulations
   (same as A.5.3 if done).
2. **Wrap with `jax.jit`**. Trace once per (A, J_pn, J_b, act_T) shape.
3. **Apply `jax.vmap`** over duration + cell axes; iterate cohorts on
   CPU outer.
4. **Precision**: FP32 default, FORCE_FP64=1 escape hatch.

### Validation gates

Per `[[feedback_cascade_gating]]`:

- B.1 done.
- B.2 Step 1 done.
- B.2 Step 2: single (j_pn_src, j_b_src, j_pn_dst, j_b_dst) at A=10
- B.2 Step 3: all J² src/dst combinations at A=10
- B.2 Step 4: single duration at A=25
- B.2 Step 5: full A=50 HS_Only — diff vs `baseline_A50_seq.pkl`
- B.3: full HS_Only A=50 production
- B.4: full Baseline A=50 — diff vs Phase A reference IF A.5 produced
  one (otherwise spot-check by running A=20 first)
- B.5: cascade A∈{30,60,90,120} per v2 projection rule (HS_Only and
  Reduced_Run already converged at A=60 on CPU; Baseline cascade
  awaits Phase B)

### Risk

**Medium-high.** Main failure modes:
1. HARK cFunc objects don't cleanly cross to JAX → solution: flat
   tabulation
2. JAX FP32 produces welfare ratios off by >0.01 → selective FP64

### Fallback: numba-CPU port (~1-2 days)

If after 2 days of B work we don't have B.2 Step 4 passing, abandon
JAX and do a numba-CPU port. Same kernel rewrite, no GPU memory
budget concerns, single-thread performance gain only (3-10× expected).

## Combined milestones (revised 2026-05-17)

| After phase | HS_Only A=60 ui_rec | Reduced_Run A=60 ui_rec | Baseline A=60 ui_rec | Notes |
|---|---:|---:|---:|---|
| Quick-win (done) | 6 min | infeasible | infeasible | HS_Only only |
| + Phase A (done) | 6 min | **22 min** | infeasible-22-worker hang | Reduced_Run new |
| + BLAS-thread-cap fix (done) | 6 min | 22 min | **8 hr** | Baseline unblocked! |
| + Phase A.5 (CPU vectorize, ?) | ~1-3 min | ~7 min | **~3-5 hr** | depends on speedup |
| + Phase A.6 (beta-vectorize) | n/a | n/a | **~3-5 hr** | only helps Baseline (HS_Only is 1 cohort, Reduced_Run has DiscFacCount=1) |
| + Phase A.5 + A.6 combined | n/a | n/a | **~1-2 hr** | compound speedup |
| + Phase B (JAX-GPU + vmap) | **~10-30 s** | **~30-60 s** | **~15-30 min** | full speedup |

Top row is the current bound; bottom row is the JAX-GPU goal.

## Decision off-ramps

- **After Phase A.5.1 profile**: if profile shows Python overhead is
  the bottleneck, A.5 is worthwhile. If cFunc evaluation dominates,
  flat tabulation in A.5 also helps Phase B.
- **After Phase A.5.4 measurement**: if Baseline A=50 becomes
  feasible (~hours wall) on CPU, Phase B may be deferred until a
  specific GPU-only need arises.
- **After Phase B.2 Step 4**: if single-duration JAX validates,
  commit to finishing B. Fails after 2 days → numba fallback.

## Total estimated wall

| Path | Dev wall | Notes |
|---|---:|---|
| BLAS fix only (done) | hours | Baseline at 8 hr per A=60 run |
| + Phase A.6 (beta-vectorize) | +1-1.5 days | Baseline → ~3-5 hr per A=60 |
| + Phase A.5 (numpy vectorize) | +1-3 days | Baseline → ~3-5 hr (different lever) |
| + Phase A.5 + A.6 combined | +2-3 days | Baseline → ~1-2 hr |
| + Phase B (JAX-GPU, success) | +3-5 days | Baseline → ~15-30 min |
| Phase B fail → numba fallback | +1-2 days | smaller gain |

## Triggers to start the work

Per `[[feedback_deferred_followups]]`:
- 3%-gap investigation Tier 2 (cascade grid-convergence sweep at
  Baseline per `[[feedback_grid_refinement_stepwise]]` v2:
  A=30→60→90→120) → Phase B becomes time-critical. HS_Only +
  Reduced_Run cascade already done on CPU; both converged at A=60.
- Decision to publish 5D-derived welfare numbers → Phase A.5 or B
  mandatory for Baseline
- Repeated 5D runs from another bug hunt → A.5 worth doing first

## Out of scope

- HARK PR for JIT-friendly kernel signature
- Algorithmic changes (adaptive grid, etc.)
- Multi-GPU scaling
- FP64 by default
