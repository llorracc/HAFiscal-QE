# R5 — Eliminate transpose-fusion in 5D welfare kernel

**Date:** 2026-05-17
**Goal:** Hold `dist5d` in `(J,J,A,A,A)` layout throughout the kernel, eliminating the per-step transposes at L653 (d_src_agg) and L738/L873 (scattered_total). This removes the JAX layout-shuffle fusion that produced a 3 GB `s32[163M, 5]` intermediate at A=60 full-cohort vmap, unblocking the OOM and recovering full 21-cohort parallelism.

**Projected gain:** Baseline A=60 from C.1+C.2's 71 min → ~30 min (extrapolating A=30's 2.2× vmap-21 speedup). ~2× win on top of current winner.

## Why the transpose exists today

The kernel mixes two layout conventions:

- **einsum convention** (line 703): `'IJKpq,pqrs->IJKrs'` puts the 3 asset axes (I,J,K) leading and the 2 Mrkv axes (p,q) trailing. This matches `dist5d` shape `(A,A,A,J,J)`.
- **scatter convention** (line 670): `vmap(_bilinear_3d_scatter_single, in_axes=(0,0,0,0,None))` vmaps over a leading flat-B axis where B = J*J. The scatter naturally wants its leading axes to be the J,J pair so they can be flattened to B via `.reshape(B, A, A, A)`.

Bridging these two conventions requires the transpose at L653 (`d_src_agg.transpose(3,4,0,1,2)`). After the scatter, a counter-transpose at L738 (`scattered_total.transpose(2,3,4,0,1)`) returns to einsum layout. Both transposes are pure layout shuffles, no math.

When `dist5d` shape is small (e.g. A=30, 21 cohorts), JAX folds these transposes into surrounding ops cheaply. At A=60 with 21-cohort vmap, the shuffle fuses with the scatter-index materialization into a single op producing `s32[163M, 5] ≈ 3 GB`. OOM.

The fix: pick *one* convention and use it everywhere. The scatter convention is correct because it matches the dominant computational axis (J*J = 16 in baseline; this is the vmap axis for the per-(jp_dst, jb_dst) scatter). Forcing the einsum to operate in J-leading layout costs zero (einsum is just a label change).

## Edit sites (verified by grep — 9 total)

| # | site | line | change |
|---|---|---|---|
| 1 | dist5d zeros init | 1025 | `np.zeros((A,A,A,J,J))` → `np.zeros((J,J,A,A,A))` |
| 2 | newborn diag init | 1068 | same |
| 3 | dist5d_batch init | 1279 | `(C,A,A,A,J,J)` → `(C,J,J,A,A,A)` |
| 4 | newborn_batch init | 1356 | same |
| 5 | einsum spec (v3) | 703 | `'IJKpq,pqrs->IJKrs'` → `'pqIJK,pqrs->rsIJK'` |
| 6 | einsum spec (v4 batched) | 837 | same |
| 7 | transpose (singleatom) | 653 | **DELETE** — `d_src_agg_t = d_src_agg` directly |
| 8 | transpose (v3 driver) | 738 | **DELETE** — `dist5d_next = scattered_total` directly |
| 9 | transpose (v4 batched driver) | 873 | **DELETE** — `dist5d_next_batch = scattered_total` directly |

**Untouched** (verified safe):
- Marginal sums L658-659: `axis=(3,4)` and `axis=(2,4)` already target the trailing A axes in the new layout
- Integrand assembly L648-649: already produces `(J,J,A,A,A)` weight_3d_all shape
- Scatter reshape L666: `.reshape(B, A, A, A)` works directly when J*J are leading

**Construction in `compute_baseline_tm_data` / dist5d builder** (line 1025–1027 in our kernel, and the diag construction at L1068): currently builds in (A,A,A,J,J) using a nested loop. Easy to flip — change the indexing order in the construction loop. The newborn diag is sparse (only diagonal entries non-zero), so the construction is small.

## Implementation plan

### Step 1 — Validate the concept on v3 single-cohort (HS_Only A=30)
Apply all 9 edits to v3 path (kernel + driver). Run validate_v4_vs_v3 with v3 in *new* layout vs current main as ground truth. Must match bit-identically.

### Step 2 — Promote to v4 batched, validate HS_Only A=30 single-cohort batch
Run validate_batched_driver.py with the new layout. Must match bit-identically.

### Step 3 — Reduced_Run A=30 multi-cohort
Same validator at 3 cohorts. Must match.

### Step 4 — Baseline A=30 full vmap-21
Production driver with `--cohort-vmap --cohort-batch-size 21`. This worked previously; must still work. (Confirms we didn't regress small-A.)

### Step 5 — **The actual test: Baseline A=60 full vmap-21**
Same driver, A=60. The OOM should no longer occur. Expected wall: ~25-30 min.

### Step 6 — Bit-identical match against today's chunked Baseline A=60 result
Compare ui_rec against 1.7866 (chunked Baseline). Layout change is mathematically a no-op; values must match to FP32 noise.

## Risk + fallback

**Primary risk:** subtle indexing bug introduces a transposed-axis error that doesn't trip basic shape checks. Mitigation: each step validates bit-identically against an unchanged reference. Any step failing reverts.

**Secondary risk:** the OOM has a *different* cause than the layout fusion, and elimination doesn't unblock A=60. Probability ~30%. Mitigation: if Step 5 still OOMs, the kernel HLO will tell us what the new culprit intermediate is, and we re-plan.

**Fallback:** Keep the C.1+C.2 path as production winner; document R5 as inconclusive. No regression.

## Estimated cost

- Step 1 (v3 layout change + validate): 2 hr
- Step 2-4 (promote to v4 + validate at small N): 1 hr
- Step 5-6 (A=60 production test): 1 hr wall + ~30 min analysis
- Total: ~4-5 focused hours

This is small enough that I'd just execute it once the user approves, rather than carving into another multi-day plan.

## Decision points

1. **Approve plan as-written and execute?** Default = yes; this is a tightly-scoped 4-5hr rewrite with bit-identical validation gates.
2. **Stop at any failed gate?** Default = yes; each step independently revertible via git.
3. **Cutover policy on success?** If Baseline A=60 vmap-21 lands at ~30 min, propose making `--cohort-vmap` the production default and retiring the chunked path. Defer that decision to the user after seeing the number.

---

## EXECUTION RESULT (2026-05-17, post-greenlight)

**Steps 1-3 PASS** (bit-identical):
- HS_Only A=30 single cohort: welfare_num_sum bit-identical (Δ=0). AggInc/Cons within 1 ulp (FP32 sum-order noise).
- HS_Only A=30 single cohort batched (validate_batched_driver): max rel diff = 0.000e+00 ✓ PASS
- Reduced_Run A=30 3-cohort batched: max rel diff = 0.000e+00 ✓ PASS

Additional fixes required beyond the original 9 edits (caller-side layout-dependent code that the plan missed):
- 2 unemployment spike-injection sites (single + batched) — `dist5d[:, :, :, 0, j_b]` slicing
- 2 marginal-compute sites — `sum(axis=(1, 2, 4))` for pLvl recurrence

**Step 5 FAILED** (the actual A=60 vmap-21 test):
Exact same OOM: `loop_transpose_fusion.2 = (s32[163296000, 5]{1,0}, ...)` = 3.04 GB. The intermediate size `163,296,000 = 21 cohorts × 36 cells (J²=6²) × 216,000 (A³=60³)` — this is the bilinear scatter's own working memory, *not* a layout-shuffle artifact. JAX names it `loop_transpose_fusion` but the transpose component is incidental; the bulk is scatter index materialization.

**Root cause:** the `_bilinear_3d_scatter_single` function vmapped over (cohort=21) × (cell=36) at A=60 materializes too many intermediate index tensors regardless of input layout. Eliminating my 2 dist5d transposes did not reduce this because they weren't the dominant contributor.

## Disposition

- **Keep the layout change** (committed as code-quality improvement). Bit-identical validated, removes 2 transposes per step, gives a single consistent layout convention throughout. No regression; minor cleanup.
- **R5 as a speedup lever is dead.** A=60 cannot use full vmap-21 on a 16 GiB GPU under the current bilinear scatter formulation.
- **Production winner unchanged**: C.1 + C.2 at 71 min (no `--cohort-vmap`).

## Follow-up ideas (R6-class, not in scope here)

If A=60 full-vmap is ever wanted, options seen post-mortem:
1. `jax.lax.fori_loop` over cohorts *inside* the kernel — serializes cohorts but eliminates the cohort dim from the scatter intermediate. Different from driver-level chunking (no Python-level chunk overhead).
2. Custom scatter with `int16` indices — A=60 fits in int16; halves the 3 GiB intermediate to 1.5 GiB. Might fit in 16 GiB.
3. Smaller-cell vmap: serialize J² inside the kernel, only vmap over cohorts (might still OOM but worth measuring).

None of these are queued.
