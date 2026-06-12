---
date: 2026-05-16 22:25 ET
status: HS_Only cascade complete — A=50 is converged baseline
related_plans:
  - plans/20260516_5D_ambitious_parallelization.md
related_memory:
  - feedback_grid_refinement_stepwise.md
---

# HS_Only 5D welfare cascade convergence — A=50 → A=100

## Stepwise rule outcome

**STOP at A=50.** All metrics shift < 0.1% from A=50 to A=100 — well
within the 0.3% threshold from `[[feedback_grid_refinement_stepwise]]`.
No need to run A=150.

## Side-by-side comparison

| Quantity | A=50 | A=100 | Δ rel |
|---|---:|---:|---:|
| NPV(welfare_num) | 7.979e+03 | 7.975e+03 | -0.05% |
| NPV(AddInc) TM-a | 3.927e+03 | 3.927e+03 | 0.00% |
| NPV(AddInc) 5D | 3.894e+03 | 3.894e+03 | 0.00% |
| NPV(AddCons) TM-a | 3.996e+03 | 3.996e+03 | 0.00% |
| NPV(AddCons) 5D | 3.965e+03 | 3.965e+03 | 0.00% |
| **ui_rec (TM-a denom)** | **2.0143** | **2.0133** | **-0.05%** |
| **ui_rec (5D-self denom)** | **2.0309** | **2.0299** | **-0.05%** |

## Implication for the 5D-vs-MC 3% gap investigation

The 3% gap between 5D (2.04) and MC fixed-Jensen (2.10) at HS_Only is
**NOT explained by grid coarseness**. A=50 is already at the
convergence floor; refining to A=100 does not move the needle.

This puts the gap firmly in:
- MC sampling noise (single-seed N=49k can have ~1-2% noise on UI welfare)
- Or residual 5D kernel alignment (FIX #1-#12 may not be complete)

Tier 1 of the gap diagnosis (`plan B.5 off-ramp`) — multi-seed MC at
N=49k to nail down sampling SE — becomes the priority for the next
diagnostic round.

## Wall-time finding (calibration update)

A=50 sequential per-task wall: ~60s (per Phase 4 quick-win measurements)
A=100 sequential per-task wall: **~2,200s = ~37 min** (per this run)

That's a 35× wall increase for a 2× grid scale. NOT cubic (A^3 = 8×)
as the plan assumed. Effective scaling is closer to **A^5**, which
means:

- A=150 per-task: ~2,200 × (150/100)^5 = ~16,700s = ~4.6 hours
- A=200 per-task: ~2,200 × (200/100)^5 = ~70,000s = ~19 hours

The plan's VRAM-budget table accurately captured A=150 as "tight" on
GPU, but the wall-time cost on CPU is much worse than the plan
implied. **The A=150 row in the milestones table should be marked
"CPU-infeasible, GPU-only"** if we ever need it.

## Why per-task scales as A^5 rather than A^3

Hypothesis: the per-step kernel iterates over `(A, A, A)` asset-grid
states (= A^3 cells) and for each does cFunc lookup that's O(log A)
or O(A) per lookup. Combined with the J^4 src/dst loop (constant in A)
and the bilinear scatter (each iteration is O(1) per cell but spreads
to 8 corners), the per-step cost is approximately:

  O(act_T × J^4_eff × A^3 × cFunc_cost(A))

If cFunc evaluation itself is roughly O(A) (linear scan of the
knot array, or scipy's bisect), total scaling is A^4.

If there's also a 3D mass-distribution step that's O(A^2) at each
boundary, total could reach A^5 in practice.

Either way, the empirical A^5 scaling at HS_Only is the relevant
data point. **A=200 on CPU is infeasible** regardless of which
theoretical scaling is exact.

## Updated recommendation for Phase B priority

Phase B is now MORE valuable, not less:
- HS_Only A=50 is converged → 5D delivers a high-confidence welfare number
- But the 3% gap to MC is not closed by grid refinement
- The 3% gap diagnosis requires running MC at multi-seed, OR running
  A=100 at Baseline (currently infeasible)
- Phase B (JAX-GPU) unblocks Baseline at any A; that's the only
  remaining path to closing the gap diagnosis at the Baseline scope.
