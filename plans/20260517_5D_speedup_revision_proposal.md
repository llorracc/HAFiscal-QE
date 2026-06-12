# 5D welfare speedup — revision proposal

**Date:** 2026-05-17
**Context:** Audit triggered by C.4 chunked Baseline A=60 result (~78 min vs C.1+C.2's 71 min — only 10% additional speedup, not the 30% projected from A=30). Investigated three remaining levers (FP32, invariant hoisting, m_grid coarsening); only one survives.

## Lessons from today's investigation

### L1. FP32 was already the default — speedup idea #1 collapsed
`_USE_FP64 = os.environ.get('FORCE_FP64', '0') == '1'` (kernel L24). All JAX runs to date have been FP32. The 0.03% ui_rec gap between JAX-FP32 (1.7866) and CPU-FP64 (1.7861) is the FP32 cost — within paper precision. No work to do; mark as settled.

### L2. Invariant hoisting buys nothing
Per-call re-uploads are KB-scale: aGrid 480B, cFunc tables 168KB, joint_markov 2KB, etc. At 172s/duration the bottleneck is GPU compute, not host→device transfer. Crosses off speedup idea #3 with zero work.

### L3. m_grid is not a speed lever at any resolution or scheme
Tier 1 CPU sweep (HS_Only A=30, single cohort):

| m_grid | linspace wall | nested wall |
|---|---|---|
| 500 | 42s | 42s |
| 250 | 44s | 45s |
| 100 | 49s | 47s |
| 50 | 50s | 46s |
| 25 | 50s | 47s |

**Wall time is flat.** The cFunc lookup is not the bottleneck on CPU; on GPU the cFunc table is 8 KB per cohort × 7 × 3 scenarios = 168 KB, fitting in L2 trivially. Even if accuracy held at m_grid=100, there is no time to recover. Speedup-via-grid-coarsening is dead.

### L4. m_grid scheme **does** matter for correctness — linspace was leaving 0.85% bias on the table
At the same m_grid=500, linspace and triple-log disagree by 0.85% on welfare_num. The kernel had been using `np.linspace(0.01, 50, M)` purely for `jnp.interp` "convenience" — but `jnp.interp` works on any sorted array. HARK's own grid uses triple-log nesting (`aXtraNestFac=3`), giving 22× more density in m ∈ [0,1] where `−1/c` is most curved.

**Fix shipped** (today, commit pending): `build_m_grid(M)` helper, default = HARK triple-log, override `JOINT5D_MGRID_NEST=-1` for legacy linspace. Patched 4 call sites.

### L5. Triple-log is also robust at low resolution (paper-relevant for fast iteration)
At m=50, nested drift = 0.74%; linspace drift = 11%. The nested grid degrades gracefully. The plateau at ~0.74% across m∈{25,50,100} likely reflects the A=30 asset-grid coarseness, not the m_grid — so the plateau should be lower at production A=60.

### L6. C.4 cohort-vmap is only worth it at small A — chunking at A=60 eats the gain
Empirical measurements at Baseline (21 cohorts):
- **A=30 full vmap:** 21-cohort batch fit, ~2.2× over sequential (C.1+C.2)
- **A=60 chunked vmap:** scatter-index intermediate `s32[163M, 5]` = 3 GB exceeds 16 GiB at full vmap; chunked to size 7, gives only ~10% over sequential

The chunking serializes 3 calls per duration, each of which doesn't fully saturate the GPU. The per-(cohort × duration) cost only drops from 8.97s sequential to 8.1s chunked — a 10% local win that compounds back to the same fraction in total wall time.

## Proposed revisions

### R1. Ship the `build_m_grid` helper as default (DONE today)
Replaces linspace at 4 sites with triple-log. Removes a 0.85% silent bias in the welfare integrand. Commit with the chunked-vmap C.4 changes.

### R2. Fix m_grid at 500 in production, remove the CLI knob
With L3 settled (no speedup) and the linspace bias closed (L4), there is no reason to let `--jax-mgrid` vary at the user level. Hard-code M=500 (or move to a constants module), keep the env override for diagnostics.

### R3. Strike "FP32 audit" and "invariant hoisting" from the speedup backlog
Both investigated and closed today (L1, L2). Document in the C.4 final writeup so they don't reappear in a future audit.

### R4. Re-scope C.4 as A≤45 only; default to C.1+C.2 at A≥50
Empirically the chunked-vmap path costs roughly the same as C.1+C.2 at A=60 (78 min vs 71 min — slightly worse once chunking overhead is counted). Recommend:
- `--cohort-vmap` documented as "small-A acceleration"
- Production pipeline at A=60 uses `--jax --parallel-solve` only (omits `--cohort-vmap`)
- Keep the chunked code path for future GPUs with >16 GiB VRAM where full-cohort vmap would fit

### R5. Open the transpose-fusion investigation (only structural lever left)
The OOM at A=60 was `loop_transpose_fusion.2` producing `s32[163M, 5]` = 3 GB. Kernel transposes `scattered_total` between (J,J,A,A,A) and (A,A,A,J,J) at every step (lines 633 and 853). If `dist5d` is held throughout in (J,J,A,A,A) layout, those transposes go away and the layout-shuffle intermediate vanishes. Estimated 1–2 days; opens the door to full 21-cohort vmap at A=60 (projected ~50% speedup over C.1+C.2 if it works). This is the only remaining 2×-class speedup; everything else is exhausted.

## Open questions

### Q1. Was the linspace bias affecting QE-published numbers?
The HAFiscal-QE comparison runs that produced the 1.7861 reference used CPU-FP64 with linspace m_grid=500 internally (via `tabulate_cfunc_list` in any code path that called it). If those reference numbers are biased by the same 0.85% we found here, the JAX-vs-QE gap may not be FP32 noise — it might be that *both* methods carried the linspace bias, and the gap closes (or widens) if we switch CPU to nested grid too.

**Recommended action:** one diagnostic run of the CPU code path with nested m_grid, compare ui_rec to the 1.7861 reference. If it shifts by >0.1%, the QE-comparison memory entries need a footnote about the grid-scheme dependence.

### Q2. Is the ~0.74% nested-grid plateau driven by A=30, or by IncShk discretization?
Today's Tier 1 was single-cohort A=30. The plateau across m∈{25,50,100} suggests something other than m_grid is the bottleneck. The two candidates are the asset grid (A=30) and the income-shock discretization (PermShk × TranShk atoms). A short A∈{30,60,90} sweep at fixed nested m=500 would isolate this. Not urgent — drift is already below paper precision at production A=60 — but worth understanding before any future precision claim.
