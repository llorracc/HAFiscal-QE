---
date: 2026-05-17 (overnight)
status: New-cascade-rule convergence test — HS_Only + Reduced_Run both stopped at A=60
related_plans:
  - plans/20260516_5D_ambitious_parallelization.md
related_memory:
  - feedback_grid_refinement_stepwise.md
---

# Cascade rule v2 (A=30→60→90→120, projection-based, 1% threshold)

User directive (2026-05-16 evening): replace the previous cascade rule
A=50→100→150 (0.3% threshold) with:

1. Start at A=30
2. Compute at A=60. Find worst-metric shift A=30→A=60.
3. Project A=60→A=90 shift = worst-metric shift × 0.5 (diminishing
   returns).
4. If projected ≥ 1% → run A=90; else STOP at A=60.
5. If at A=90: project A=90→A=120 similarly; STOP at A=90 if < 1%
   else run A=120 and stop.
6. **A=30 is the minimum grid for any 5D work** (no more A=20 or A=25).

## Results

### HS_Only

| Metric | A=30 | A=60 | Δ rel |
|---|---:|---:|---:|
| welfare_num_total | 8.190e+03 | 8.187e+03 | −0.032% |
| AddInc_total_5D | 4.015e+03 | 4.015e+03 | 0.000% |
| AddCons_total_5D | 4.047e+03 | 4.047e+03 | +0.001% |
| **ui_rec (5D-self)** | **2.0311** | **2.0304** | **−0.035%** |
| ui_rec (TM-a denom) | 2.0145 | 2.0139 | −0.030% |

Worst metric: ui_rec (5D-self) at 0.035%.
Projected A=60→A=90: **0.017%** (well below 1%).
**Decision: STOP at A=60.**

### Reduced_Run

| Metric | A=30 | A=60 | Δ rel |
|---|---:|---:|---:|
| welfare_num_total | 3.169e+03 | 3.166e+03 | −0.110% |
| AddInc_total_5D | 1.649e+03 | 1.649e+03 | 0.000% |
| AddCons_total_5D | 1.670e+03 | 1.670e+03 | +0.004% |
| **ui_rec (5D-self)** | **1.9074** | **1.9052** | **−0.115%** |

Worst metric: ui_rec (5D-self) at 0.115%.
Projected A=60→A=90: **0.058%** (well below 1%).
**Decision: STOP at A=60.**

## Walls

| Run | Wall |
|---|---:|
| HS_Only A=30 | 57s |
| HS_Only A=60 | 6.2 min |
| Reduced_Run A=30 | 4 min |
| Reduced_Run A=60 | 21.6 min (vs A=50's 12.7 min → ~1.7× factor for 1.2× grid) |

The empirical Reduced_Run wall scaling is gentler than HS_Only's A^5
(Reduced_Run shows ~A^2.3, possibly because tasks-per-worker > 1
amortizes some overhead).

## Production 5D welfare numbers (A=60 converged)

| Parametrization | ui_rec (5D-self) | ui_rec (TM-a) | MC fixed-Jensen | 5D−MC gap |
|---|---:|---:|---:|---:|
| HS_Only | **2.0304** | 2.0139 | 2.0953 | −3.1% |
| Reduced_Run | **1.9052** | n/a | 1.9973 | −4.6% |
| Baseline | infeasible on CPU | — | 1.8118 | — |

The 5D-MC gap is stable across HS_Only and Reduced_Run (3-5%).

## Note on prior A=50 / A=100 work

The A=50 and A=100 numbers from earlier cascade tests under the OLD
rule are still in `phase_A_*` and `cascade_HS_Only_A100.pkl`. The new
production grid going forward is **A=60** per the new cascade rule.

Comparison (HS_Only):
- A=30: ui_rec_5D = 2.0311 (NEW)
- A=50: ui_rec_5D = 2.0309 (OLD rule baseline)
- A=60: ui_rec_5D = 2.0304 (NEW cascade target)
- A=100: ui_rec_5D = 2.0299

All within 0.06% — A=30 already very close to the converged limit.
The A=60 number is preferred because it's the rule-canonical stopping
point.
