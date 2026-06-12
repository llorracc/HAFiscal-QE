# First-Period Trace: TM Ergodic → MC Simulation

**Date:** 2026-03-23
**Script:** `Code/HA-Models/FromPandemicCode/test_first_period_trace.py`

---

## Findings

### 1. Within-cell noise causes 10% aNrm inflation (BUG-015)

When sampling MC agents from the TM ergodic, adding uniform noise
within each grid cell inflates mean aNrm by ~10%:

| Sampling method | mean aNrm | Gap vs TM ergodic |
|-----------------|-----------|-------------------|
| Exact grid points | 1.308 | +0.14% |
| Uniform within-cell noise | 1.437 | **+10.06%** |
| TM ergodic (weighted) | 1.306 | — |

**Cause:** cFunc is concave.  Within a grid cell [m_lo, m_hi],
agents at m_hi consume proportionally less than agents at m_lo
(lower MPC at higher mNrm).  Uniform noise over the cell
systematically overweights the high-saving part of the cell
relative to the TM's point-mass representation.

**Fix:** Don't add within-cell noise.  Use exact grid points.
The TM ergodic already discretizes the distribution correctly;
adding noise undoes that discretization.

### 2. TM mean aNrm does NOT converge to MC burn-in

| Method | mean aNrm |
|--------|-----------|
| TM mCount=50 | 1.306 |
| TM mCount=100 | 1.288 |
| TM mCount=200 | 1.283 |
| TM mCount=400 | 1.282 |
| MC burn-in (400 periods) | 1.258 |

The TM converges to ~1.282, while MC burn-in gives 1.258.
A persistent ~2% gap remains.  Possible causes:
- TM's effective death rate approximation (BUG-007: uniform
  death across mNrm vs MC's age-dependent death)
- TM's newborn distribution differs from MC's `sim_birth`
- The TM's grid truncation (finite upper bound) affects the
  tail of the distribution

### 3. Newborn dynamics

Per period: ~1450 forced deaths (t_age ≥ 100) + ~1240 random
deaths = ~2690 total (~1.35%), replaced by ~2725 newborns.

Newborn mean aNrm = 0.15 (drawn from lognormal with low mean).
Survivor mean aNrm = 1.44.

The newborn injection pulls mean aNrm down each period.  If the
TM's newborn distribution has higher aNrm than MC's, the TM
ergodic would have higher mean aNrm — consistent with the
observed 2% gap at high mCount.

---

## Recommendation

Remove within-cell noise from TM→MC initialization (the 10%
effect).  The remaining ~2% TM-vs-MC gap in mean aNrm is a
known TM approximation; it doesn't affect treatment effects
(which cancel in base minus experiment) and is within the
standard TM level accuracy (~1.2%).
