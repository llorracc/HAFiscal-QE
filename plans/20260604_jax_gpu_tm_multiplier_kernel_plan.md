# Plan: JAX-GPU TM **multiplier** kernel — extend the JAX-TM tooling from welfare-only to NPV multipliers

> ## ⛔ Phase-0 verdict (2026-06-04): SHELVED — GPU is the wrong tool here
> A Phase-0 spike (`Code/HA-Models/jax_tm_mult/phase0_harness.py`) measured the GPU vs CPU on a
> representative per-period TM-kernel op at Baseline-ish size (C=21, J=2, A=50, M=500, ATOMS=20):
> **GPU only 2.2× (fp32) / 1.6× (fp64)** over CPU. Root cause: the multiplier TM state is the
> *marginal* `(j,a)` ≈ 100 states/cohort × 21 ≈ **2,100 elements** — far too small to saturate a GPU
> (which wants millions). The welfare 5-D kernel hit 75–221× precisely because it's `J²·A³` = millions
> of cells; the multiplier marginal is ~1000× smaller. The small state that makes the multiplier *cheap*
> also makes it a *poor GPU target*. On top of that, the AD Phase-1 HARK `economy.solve()` (CPU/EGM)
> Amdahl-bounds end-to-end to ~2–4× (the same wall that capped JAX-MC at 2×).
> **Better alternative for throughput:** each TM multiplier run is an independent ~60–90 min CPU job;
> config-level CPU parallelism gives **~16–30× on 32 cores** for a sweep — far more than the GPU's ~2×,
> for a thin launcher instead of a 2–3 week kernel port. So: GPU stays reserved for *welfare* (large
> joint state); TM multipliers stay on CPU; build a CPU-parallel sweep harness if/when throughput is
> needed. (Precision aside: FP32 resolved a 0.01 multiplier delta to 3.6e-6, so FP64 isn't needed if
> ever built.)


**Date:** 2026-06-04
**Author:** Claude (with cdc)
**Status:** ⛔ SHELVED 2026-06-04 after a Phase-0 feasibility spike — see "Phase-0 verdict" below.
**Motivation:** Produce **noise-free (TM) NPV multipliers on the GPU** — combine the determinism of the
transition-matrix method (the right tool for resolving a ≤0.01 multiplier delta) with GPU speed. The
immediate use case is the kind of published-vs-fixed A/B multiplier comparison we ran for BUG-047,
where each Baseline-TM run currently takes ~60–90 min on CPU.

---

## 1. The landscape (what exists today)

Three relevant code bodies, mapped 2026-06-04:

**(a) The CPU TM multiplier path** — `tm_methods.py`:
- `run_ad_tm` (2843–3109): 2-phase AD outer loop → returns `NPV_AggCons`, `NPV_AggIncome`.
- `propagate_experiment_tm_a` (5295–5809): per-period forward propagation of a **marginal** distribution
  over state `(a, j)` — A=50 asset grid × J micro-Markov states ⇒ **~100–300 states per cohort**.
- `compute_period_aggregates_tm_a` (5023–5202): per-period aggregate consumption & income from
  `dist × cFunc`.
- Multiplier = `ΔNPV_AggCons / Gov_Spending` (`OtherFunctions.py:36`).
- **Hot spots:** sparse TM build + matvec (70–80%), HARK `economy.solve()` in AD Phase 1 (15–25%),
  cFunc eval (5–10%). **Pure numpy/scipy — no JAX.**

**(b) The JAX-GPU TM *welfare* kernel** — `welfare6_tm_joint5d_jax_kernel.py` (1803 lines):
- 5-D **joint** state `(a_p, a_n, a_b, j_p, j_b)` for CRN-coupled UI welfare. JIT'd `v3`, cohort-vmapped `v4`.
- **Already emits per-period aggregate consumption** (`cons_pol`, `cons_none`) — i.e. it is ~90% of the
  way to a multiplier; only the NPV sum is missing.
- **BUT:** research-grade ("NOT a production method. Triple-check only."), **non-AD** (Cratio≡1.0), an
  **unresolved ~25% welfare validation gap vs MC**, and **over-built for multipliers by ~1000×**
  (J²·A³ joint vs J·A marginal: A=500,J=2 ⇒ 0.13 GB/dist vs ~2 MB).

**(c) The JAX-MC AD kernel** — `jax_mc_ad_multicohort.py` (production):
- Full AD loop, multi-cohort vmap, ~2.0× end-to-end at Baseline, validated to ~1% (0.003% with RNG
  replay). **But it is MC — stochastic** — which defeats the entire reason we use TM (a noise-free
  ≤0.01 delta).

---

## 2. Architectural decision

**Build a NEW, purpose-built JAX-GPU TM-multiplier kernel on the marginal `(j, a)` state — do NOT
retrofit the 5-D welfare kernel, and do NOT route through JAX-MC.**

Rationale:
- The multiplier needs only the **marginal per-scenario** asset distribution `(J, A)`, not the 5-D
  joint coupling welfare needs. A new kernel is ~200 lines and ~1000× smaller in memory than the 5-D
  kernel; it reuses the proven primitives (`tabulate_cfunc_list`, the 1-D bilinear scatter, q-reweight)
  without the J⁴ joint-Markov machinery.
- Retrofitting the 5-D kernel inherits its incompleteness, its ~25% validation gap, and a state space
  three asset-axes too large.
- JAX-MC is mature but stochastic; the noise-free TM delta is the whole point.

This **is** "upgrading the JAX-TM tools" — it adds a TM kernel that targets multipliers, sitting beside
the existing TM welfare kernel and reusing its tabulation/scatter utilities.

---

## 3. The AD problem, and a simpler solution than the welfare kernel's

The welfare kernel deferred AD because it framed Cratio as a 2nd cFunc argument needing a **2-D
(m, Cratio) tabulation + 2-D interp**. For the **multiplier path that is unnecessary**: in
`propagate_experiment_tm_a`, within any one propagation pass the **Cratio path is fixed**, and each
period evaluates the cFunc at a **known scalar `Cratio_t`**. So:

> **Per-period 1-D re-tabulation.** Before each GPU propagation pass, tabulate `cFunc(·, Cratio_t)` on
> the m-grid → one `(J, M)` table per period (cheap, CPU, HARK cFunc eval). The GPU kernel keeps the
> existing **1-D `jnp.interp`** — no 2-D tabulation, no 2-D interp.

The AD outer loop then mirrors `run_ad_tm`:
- **Phase 1 (training):** loop { HARK `economy.solve()` [CPU] → tabulate per-period cFuncs at current
  Cratio path [CPU] → GPU-propagate worst-case path → aggregate C → update Cratio → check cFunc
  convergence }.
- **Phase 2 (eval):** forward-propagate Cratio through the converged cFunc, tabulate, single GPU
  propagation on the actual duration path → `AggCons`, `AggIncome` → NPV → multiplier.

**Amdahl honesty (critical):** Phase-1's repeated HARK `economy.solve()` is CPU/EGM and **not** part of
this port. As with JAX-MC (which plateaued at ~2× for exactly this reason), end-to-end speedup is
bounded by the HARK solves unless they are amortized. Two existing levers help: `skip_training=True`
(reuse the Phase-1 cFunc across the 12+ recession durations — only the first duration pays Phase 1) and
the **solution cache** (`HAFISCAL_USE_SOLUTION_CACHE=1`, ~5490× on a Baseline cache hit). With those,
the GPU-able propagation becomes the dominant remaining cost and the port pays off; without them,
expect a modest ~2–4×.

---

## 4. Phased implementation (each phase has a validation gate)

**Phase 0 — GPU reality + precision harness (prereq, ~0.5 day).**
- Confirm JAX actually executes on GPU, not a silent CPU fallback (the JAX 0.10.0 cuSPARSE/nvjitlink
  ABI gotcha; `apply_jax_gpu_patch.sh` / `GPU_SETUP.md`). `jax.default_backend()=='gpu'` already
  observed — confirm with a real kernel timing vs CPU.
- Stand up an FP32-vs-FP64 harness: the deliverable delta is ≤0.01, so FP32 NPV-sum error must be
  ≪ that. **Likely require FP64 for the multiplier NPV sums and for the A−B difference** even if the
  welfare kernel tolerated FP32. Gate: FP64 path matches numpy to 1e-9 on a toy propagation.

**Phase 1 — non-AD multiplier kernel (~2–3 days).**
- New module (in `Code/HA-Models/`, NOT `FromPandemicCode/`, per the new-code rule). Port the
  marginal `(j, a)` propagation: Markov transition (J×J), income-shock atoms, `m = R·a/(Γψ) + ξ_eff`,
  1-D cFunc interp, splurge blend, 1-D bilinear scatter, per-period `Σ AggCons / AggIncome`, NPV.
- Reuse `tabulate_cfunc_list` (1-D) and the 1-D analog of `_3d_bilinear_distribute_jax`.
- **Gate:** at HS_Only and Reduced_Run, the **no-AD** Check & TaxCut multipliers match
  `run_experiment_tm_nonbase` (numpy) to rtol 1e-5 (FP64). Bit-comparable per-period AggCons series.

**Phase 2 — AD outer loop (~3–5 days; the crux).**
- Implement Phase-1 training (HARK solve on CPU + per-period 1-D re-tabulation + GPU propagate +
  Cratio update + cFunc-convergence check) and Phase-2 eval. Match `run_ad_tm` semantics: ADF =
  Cratio^(κ·RecState), κ=0.3, `ad_timing='lagged'`, `cfunc_offset='mc'`, Cratio clip [0.8,1.2].
- Port the **Check per-bucket** handling in `compute_period_aggregates_tm_a` (the stimulus-check
  E_check_level_b path) — this is extra surface area beyond the plain aggregation.
- **Gate:** Check & TaxCut **recession+AD** and **1st-round AD** multipliers match `run_ad_tm` (numpy)
  to paper precision (1e-4 after rounding) at HS_Only + Reduced_Run.

**Phase 3 — multi-cohort batching + Baseline (~2–3 days).**
- vmap the propagation over the 21 Baseline cohorts (mirror the welfare kernel's `v4` cohort-vmap).
  Handle per-cohort `AgentCount`, `E_pLvl`, `pLvl_factor` level-scaling and population weighting.
- **Gate:** reproduce the BUG-047 **A-vs-B Baseline-TM** comparison (Check 1.20 / TaxCut 0.99 for the
  published world) to ≤0.005 absolute, and the A→B delta to within FP noise of the CPU TM delta.

**Phase 4 — benchmark + opt-in wiring (~2 days).**
- Wall-clock + GPU-utilization benchmark vs CPU TM at Baseline; report the honest end-to-end speedup
  with vs without `skip_training` / solution-cache. Memory-bandwidth vs compute characterization.
- Opt-in env flag (e.g. `HAFISCAL_USE_JAX_TM_MULT=1`) wired into the multiplier path; default off;
  bit-precision regression test committed.

---

## 5. Reuse map

| Need | Reuse / build |
|---|---|
| cFunc tabulation on m-grid | **Reuse** `tabulate_cfunc_list` (1-D, per-period at Cratio_t) |
| 1-D bilinear scatter onto aGrid | **Adapt** `_3d_bilinear_distribute_jax` → 1-D (much simpler) |
| Income-shock atom arrays | **Reuse** `extract_incshk_arrays` / q-reweight |
| Marginal `(J,A)` propagation | **Build new** (the welfare kernel is 5-D joint — not reusable) |
| Per-period Σ AggCons / AggIncome + NPV | **Build new** (welfare kernel emits cons but not NPV) |
| AD outer loop (Phase1/Phase2, Cratio) | **Build new** (welfare kernel is non-AD) |
| Check per-bucket aggregation | **Port** from `compute_period_aggregates_tm_a` |

---

## 6. Risks

1. **FP32 vs the ≤0.01 delta (highest).** The deliverable is a sub-1% difference; FP32 NPV-sum and
   A−B cancellation error could be the same order. Mitigation: FP64 for NPV/aggregation; Phase-0
   precision gate; report FP32-vs-FP64 sensitivity.
2. **Amdahl ceiling from HARK Phase-1 solves.** Realistic end-to-end ~2–4× unless `skip_training` +
   solution-cache amortize the solves (same lesson as JAX-MC's 2× plateau). Set expectations.
3. **Silent GPU→CPU fallback** (JAX 0.10.0 cuSPARSE). Phase-0 gate with a real-kernel timing.
4. **Check per-bucket complexity.** The stimulus-check path is the most intricate part of the numpy
   aggregator; budget for it explicitly in Phase 2.
5. **AD fixed-point convergence on GPU** (FP32 jitter could perturb the Cratio iteration). Use FP64 in
   the AD loop; match the numpy convergence trace iteration-by-iteration at HS_Only.

---

## 7. Effort & payoff

- **Effort:** ~2–3 weeks (Ph0 0.5d, Ph1 2–3d, Ph2 3–5d, Ph3 2–3d, Ph4 2d + validation).
- **Payoff:** propagation itself likely 10–50× on GPU; **end-to-end** ~2–4× without solve-amortization,
  larger with `skip_training` + solution-cache (the solve drops out, propagation dominates). A Baseline
  TM multiplier run ~60–90 min → plausibly ~15–30 min (uncached) or much less (cached).
- **When it's worth it:** if TM multiplier *sweeps* become routine (e.g. re-running A/B across many
  calibrations, robustness grids, or CRRA/R variations). For a one-off A/B comparison it is **not**
  worth 2–3 weeks — the CPU run finishes within the hour.

## 8. Alternatives considered & rejected

- **Retrofit the 5-D welfare kernel to emit multipliers + AD.** Rejected: research-grade, incomplete,
  ~25% validation gap, over-built (J²·A³) for a marginal quantity; the 2-D (m,Cratio) tabulation it
  would need is avoidable via per-period 1-D re-tabulation anyway.
- **Use JAX-MC (already AD + multiplier-capable).** Rejected for this purpose: MC is stochastic, which
  defeats the noise-free reason we use TM for the ≤0.01 delta. (JAX-MC remains the right tool for
  *welfare* GPU work.)

## 9. Decision needed from the user

This is a 2–3 week build whose end-to-end speedup is Amdahl-bounded by HARK solves unless paired with
the solution cache. **Worth starting only if GPU-accelerated noise-free TM multiplier *sweeps* are on
the roadmap.** If the near-term need is just occasional A/B comparisons, the existing CPU TM path is
adequate and this should stay a documented, ready-to-execute plan.
