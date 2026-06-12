# JAX MC Speedup Brainstorm — 2026-05-20

**Premise.** Current end-to-end at Baseline 5× is **~1.9× over HARK** despite
the inner kernel being 5–10× per-iter faster. The gap between per-iter
speedup and end-to-end speedup is the symptom that speedups are bottlenecked
elsewhere — Python orchestration, host↔device transfers, cFunc table
rebuilds, and (still) HARK's solver. There is **a lot** of headroom.

Goal of this doc: identify every reasonable speedup avenue, estimate impact
+ effort, and propose a phased roll-out.

---

## Where time actually goes (per AD iteration, Baseline 5×)

Rough breakdown (estimates, units = seconds per iter):

| Phase | What | Wall | Why |
|---|---|---|---|
| H | `eco.solve()` HARK numpy | ~120s | longest cohort × parallel-21; HARK's per-state loop is inherently sequential |
| T | `extract_cfunc_table_per_period` | ~15–30s | Python double loop over `T × n_combined` HARK cFunc calls per cohort, ×21 cohorts |
| K | `simulate_jax_ad` JIT'd kernel | ~5–10s | Already fast (vmap'd over N, scan over T) but per-cohort × per-seed Python dispatch |
| O | Aggregation, CFunc update | ~1s | Pure numpy |

So each iter is ~150s; 10 iters = ~25 min. ~80% in H + T. Even if K went
to 0 the speedup would be only ~1.07× — **K is not the bottleneck**.

The real targets are **H** (HARK solve) and **T** (table rebuild).

---

## Bottleneck analysis: why each phase is slow

### H — HARK `eco.solve()`

- HARK's `solve_one_period_ConsAggMarkov` is a Python loop over StateCount
  (168 at Baseline recession) calling numba-compiled inner kernels.
- ~100 EGM iterations × T_cycle periods × 168 states = ~few million per-state
  EGM steps per cohort.
- Per-state numpy work is parallelizable in principle, but HARK's loop is
  sequential.
- This is what PR-3 (`ConsAggShockModelJAX`) addresses upstream, but HAFiscal
  has its own solver (`solve_agg_cons_markov_alt`) with HAFiscal-specific
  features (ADF, RecState).

### T — `extract_cfunc_table_per_period`

- Currently builds `(T, n_combined, M_grid)` tensor by calling
  `sol.cFunc[j](m_arr, Cratio_obs[t])` for each `(t, j)`.
- T ≈ 96, n_combined = 168, M_grid = 500 → 16,128 cFunc calls per cohort
  per AD iter.
- Each call: HARK's `LowerEnvelope2D` of `LinearInterpOnInterp1D` —
  numpy-side, not vectorized over `t`.
- Across 21 cohorts × 10 iters: ~3.4M cFunc calls per Baseline solve.

### K — `simulate_jax_ad`

- `lax.scan` over T periods with vectorized work across N agents.
- Per-cohort overhead: Python dispatch + JIT trace + host→device transfer of
  `cfunc_table` (~10 MB per cohort).
- Per-seed sequential: 4 seeds × 21 cohorts × 10 iters = 840 JIT calls per
  Baseline run.

---

## Speedup avenues

### TIER 1 — Quick wins (≤1 week each, low risk, additive)

#### 1A. Lift cFunc on a (m, C) grid ONCE per iter; bilinear-interp in-kernel
**What:** Replace `extract_cfunc_table_per_period(T, n_combined, M_grid)`
with `extract_cfunc_2d_table(n_combined, M_grid, C_grid)`. Build once per
cohort per iter on a coarse `C_grid` (e.g. 32 points). Per-period lookup
in the kernel becomes bilinear in `(m, C)` instead of linear in `m` at
pre-computed `C(t)`.

**Why faster:** Build cost drops from T·n_combined = 16,128 calls to
n_combined·C_grid = 5,376 calls per cohort per iter. **~3× table build
speedup.** Also: the (m, C) table is lift-able fully in JAX (lift via
vmap over (j, m_k, C_k) → vpfunc), eliminating the Python loop entirely.

**Risk:** Need to validate that bilinear-in-C agrees with the current
linear-at-fixed-C approach to ≤1e-4. The HARK 2D cFunc IS bilinear-on-
LinearInterp anyway, so this is mathematically equivalent up to lift
resolution.

**Effort:** 2–3 days (kernel change + driver wiring + parity tests).
**Speedup:** 1.5–2× on phase T; ~1.3× overall.

#### 1B. Vmap across seeds
**What:** Currently `for s in seeds: simulate_jax_ad(...)` is a Python
loop over 4 seeds. Wrap the JAX kernel with `jax.vmap` to run all 4 seeds
in one JIT call.

**Why faster:** Eliminates 3 Python→JAX dispatch round-trips per cohort
per iter (4 → 1). Saves ~10–50 ms per cohort per iter × 21 × 10 = ~10–100 s
per Baseline run. GPU also parallelizes naturally across the seed axis.

**Risk:** Memory: cLvl panel grows 4× in one batch. At Baseline, N=88k ×
T=96 × 4 seeds × 8 bytes ≈ 2.7 GB per cohort — fits in 16 GB VRAM but
tight when multiple cohorts.

**Effort:** 1 day (wrap kernel + handle output shape).
**Speedup:** 1.2–1.5× on phase K; minor overall but compounds with others.

#### 1C. Pre-allocate cfunc_table on GPU once per iter
**What:** Currently each cohort does `jnp.asarray(cfunc_table)` (CPU→GPU
transfer). For Baseline ~10 MB × 21 cohorts × 10 iters = 2.1 GB of
transfers per run.

**Why faster:** Build cfunc_tables for all cohorts at once (stacked into
`(n_cohorts, T_or_C, n_combined, M_grid)`), single host→device transfer.

**Risk:** Memory at Baseline: 21 × 100 MB = 2.1 GB on GPU. Fits.

**Effort:** 1 day (refactor cfunc table build to be batched).
**Speedup:** Minor (~5% per iter) but eliminates a Python overhead source.

#### 1D. Lazy cLvl panel materialization
**What:** During non-final AD iters, don't materialize the (T, N) cLvl
panel — only the aggregates (AggCons, AggInc). On the final iter, run
once more with panel materialization enabled.

**Why faster:** Writing the per-agent panel is GPU memory bandwidth.
Skipping it during the 10 convergence iters saves substantial bandwidth.
At Baseline: T=96 × N=88k × 8 bytes = 67 MB per cohort per iter × 21 ×
10 = 14 GB of GPU writes saved.

**Risk:** None. Final iter is explicitly when we need the panel for
welfare cells.

**Effort:** 0.5 day (add `materialize_panel` flag to the kernel).
**Speedup:** 1.2–1.5× on phase K; minor overall but easy.

### TIER 2 — Architectural (2–4 weeks each, moderate risk)

#### 2A. Vmap across cohorts
**What:** Stack all 21 cohorts into one big JAX call. The kernel becomes
`vmap(simulate_jax_ad)` over a cohort axis. State arrays become
`(n_cohorts, N, …)`.

**Why faster:** Eliminates per-cohort Python dispatch entirely. GPU's
parallelism naturally exploits the cohort axis (all cohorts compute
in parallel). At Baseline: 21 cohorts × 10 iters × ~50–100 ms dispatch
saved = 10–20 s per run. More importantly, fuses cohort work into a
single CUDA graph → fewer kernel launches → less GPU idle time.

**Risk:** **Cohort N varies** at Baseline 5× (4k / 22k / 14k per cohort).
Must pad to max N and mask. Adds ~30% wasted compute per cohort but the
parallelism gain dominates. Also: per-cohort parameters (DiscFac, etc.)
must be batched cleanly.

**Effort:** 1 week (refactor multicohort driver, careful with masking
and per-cohort state).
**Speedup:** 2–5× on phases K + T together; ~1.5–2× overall.

#### 2B. JAX-native solver (replace HARK eco.solve)
**What:** Port HAFiscal's `solve_agg_cons_markov_alt` to JAX. This is
analogous to PR-3's `solve_ConsAggMarkov_jax` but with HAFiscal-specific
features (ADF coupling, RecState, etc.).

HAFiscal already has `jax_solver_kernel.py` and `jax_solver_drop_in.py`
that do this — currently ~4.6× SLOWER than HARK due to Python dispatch
overhead in HARK's iter loop. Fixing requires:
  (a) Move the EGM ITERATION LOOP into JAX (`lax.fori_loop` or
      `lax.scan` over time-cycle).
  (b) Run on GPU.

**Why faster:** Eliminates ALL HARK Python overhead. The full T_cycle
solve fuses into one JIT'd graph. At Baseline 5× scale (168 states ×
50 EGM iters × T_cycle), GPU throughput easily 5–20× over numpy/numba.

**Risk:** Substantial. The solver has many features (vFunc, Cubic,
constrained branches) that need careful porting. Validation against
HARK's converged cFunc must be ≤1e-3 across all per-state evaluations.

**Effort:** 2–3 weeks (much of the kernel exists in
`jax_solver_kernel.py`; rework is the iter loop + GPU + per-state
validation).
**Speedup:** Eliminates phase H entirely → ~3–10× overall.

#### 2C. AD outer loop as `lax.while_loop`
**What:** Currently AD is a Python `for it in range(num_iters)` with
`if Total_Diff < cutoff: break`. Could be a `lax.while_loop` that fuses
all iterations into one JIT'd graph.

**Why faster:** Eliminates per-iter Python dispatch. Avoids re-tracing
the kernel for each iter (currently JIT cache hit, but still ms-level
overhead).

**Risk:** Requires phases H, T, K to all be JAX-native (i.e., 2B done).
Also: convergence check inside while_loop adds branching that can hurt
performance.

**Effort:** 1 week, gated on 2B.
**Speedup:** 1.2–1.5× on top of 2B.

### TIER 3 — Memory and precision (1–2 weeks each)

#### 3A. float32 throughout the kernel (selectively float64)
**What:** Currently mixed float32/float64. Convert all hot-path state
to float32 except aggregates (AggCons, Cratio) where precision matters.

**Why faster:** 2× memory bandwidth on GPU, 2× math throughput on most
GPUs (RTX 4080 supports TF32 — 8× over fp64).

**Risk:** Cumulative error over T=96 periods × 10 AD iters. Welfare
cell precision must stay within 0.5%. Need careful validation.

**Effort:** 1 week (dtype audit + parity).
**Speedup:** 1.5–2× on phases K + T.

#### 3B. Reduce N for early AD iters (convergence acceleration)
**What:** Use smaller N (say 1k per cohort) for AD iters 1–7 (where the
fixed point is roughly forming), then full N (10k or more) for iters
8–10 to lock in precision.

**Why faster:** Most of the AD iteration work is finding the
fixed-point cFunc, which doesn't need full-precision Cratio. The actual
welfare measurement does need full N.

**Risk:** Convergence behavior may differ. Need to verify that the
reduced-N fixed point and full-N fixed point are within the AD tolerance.

**Effort:** 1 week (driver change + convergence study).
**Speedup:** 3–7× on phases K + T during early iters; ~1.5–2× overall.

### TIER 4 — Algorithmic (research-grade, weeks–months)

#### 4A. Quasi-Monte Carlo (Sobol)
**What:** Replace pseudo-random shocks with low-discrepancy Sobol sequence.

**Why:** O(N^-1) convergence vs MC's O(N^-0.5) → same precision at N/10.

**Risk:** Need to be very careful that the shock structure (per-agent
i.i.d. across time) is respected. May not apply directly to AD context.

**Effort:** 2+ weeks of research + validation.
**Speedup:** Potentially 5–10× via N reduction. But research-heavy.

#### 4B. Variance reduction (importance sampling on rare events)
**What:** Welfare-relevant events (UI receipt, recession × stimulus) are
rare. Importance-sample them.

**Why:** Variance reduction → smaller N for same precision.

**Risk:** Already explored partially per memory; "joint-state sampling
bias" is non-trivial.

**Effort:** Research project.
**Speedup:** Highly problem-dependent.

#### 4C. Stochastic approximation for AD fixed point
**What:** Robbins-Monro–style update instead of iterating to convergence.

**Why:** Converges in O(log(1/tol)) instead of fixed-point iteration.

**Effort:** Research, may not apply cleanly.

### TIER 5 — Niche (specific wins, days each)

#### 5A. Uniform m_grid → O(1) bucket lookup
**What:** If `m_grid` is uniform spacing, replace `searchsorted` with
`((m - m0) / dm).astype(int)`.

**Why:** searchsorted is O(log M); bucket is O(1). Saves a few
microseconds per agent per period.

**Risk:** None if grid is actually uniform.
**Effort:** 1 hour.
**Speedup:** Marginal (~3–5%).

#### 5B. Pre-compute (1-p) cumulative distributions for shocks
**What:** Sampling currently does `cumsum(pmv)` + comparison per agent
per period. Could pre-compute cumulative + use `jax.random.choice`
which is faster on GPU.

**Effort:** 1 day.
**Speedup:** ~5%.

#### 5C. Bundle agent state into one pytree (vs 4 separate arrays)
**What:** carry is `(aNrm, pLvl, mrkv, t_age)` — 4 arrays.

**Why:** Fewer XLA scheduling overheads.
**Effort:** 0.5 day.
**Speedup:** ~5%.

---

## Multiplicative effect of stacking

If we apply 1A + 1B + 1D + 2A + 2B end-to-end:
- 1A: 1.3× overall
- 1B: 1.1× overall
- 1D: 1.1× overall
- 2A: 1.6× overall
- 2B: 5× overall (eliminates phase H)

Product: ~12× overall speedup. So **Baseline 5× from ~35 min → ~3 min**.

Adding Tier 3 (3A, 3B): another ~2× → **~1.5 min**.

Adding Tier 4 (variance reduction): another ~3× via N reduction → **~30 s**.

So the realistic ceiling — without research-grade work — is roughly **20×
overall** (~2 min per Baseline 5× solve) achievable with Tier 1 + Tier 2.

---

## Recommended roll-out

### Phase α (1–2 weeks, low risk)
1A + 1B + 1D in parallel. Each ~1 week, additive. Validation: end-to-end
parity vs current JAX MC at HS_Only and Baseline default. Expect **2× overall**.

### Phase β (2–3 weeks, moderate risk)
1C + 2A. Bigger refactor but well-defined. Validation: bit-comparable
output. Expect **3–4× overall** cumulative.

### Phase γ (4–6 weeks, high risk)
2B + 2C. The big swing — eliminates HARK in the AD loop. Validation:
welfare cells within paper-grade tolerance vs HARK reference. Expect
**10–15× overall** cumulative.

### Phase δ (gated on outcomes)
3A + 3B for additional gains; Tier 4 (QMC) only if the deliverables are
high-priority enough to justify research investment.

---

## What this means for HAFiscal user experience

| Today | Phase α | Phase β | Phase γ |
|---|---|---|---|
| Baseline 5× welfare verify: 45 min | ~22 min | ~12 min | ~4 min |
| Full AD solve at Baseline 5×: ~35 min | ~17 min | ~10 min | ~3 min |
| Welfare-6 paper-precision run: ~1 hr | ~30 min | ~15 min | ~5 min |

For a paper-precision run cycle that today takes 5–6 hours, Phase γ
turns it into **30 minutes**. Iteration speed for the research team
changes qualitatively.

---

## Open questions to triage before starting

1. **Memory budget on the 4080.** Phase α (vmap seeds) and 2A (vmap
   cohorts) both increase VRAM. Need to confirm what fits at Baseline
   5× (cohort N=88k highest).
2. **HAFiscal's JAX solver (`jax_solver_kernel.py`) vs PR-3.** Phase 2B
   is HAFiscal-specific (ADF, RecState, etc.). Does the existing
   `jax_solver_kernel.py` cover this, or does it need significant
   extension?
3. **Validation budget.** Each phase needs paper-grade welfare validation
   (≤0.5% vs HARK). At Baseline 5× that's ~45 min per validation run.
   ~10 validation runs per phase = 5–8 hours of compute. Need a
   cascade-gating plan.
4. **PR-3 dependency.** Phase 2B benefits from PR-3 merging upstream;
   could land in parallel.

---

## Pre-commitment to validation gates

For each phase, define the pass criteria UPFRONT:
- **Phase α:** parity to ≤1e-4 vs current JAX MC; end-to-end wall
  measured ≥1.7× speedup.
- **Phase β:** parity to ≤1e-4; speedup ≥3×.
- **Phase γ:** welfare-6 cells within ≤0.3% of HARK at Baseline; speedup
  ≥8×.

If any phase fails its parity gate, debug before moving on.
