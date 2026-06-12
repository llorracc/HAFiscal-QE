# Plan: Assess Quality of Initial Joint (mNrm, pLvl) Distributions

**Date:** 2026-03-23
**Author:** Claude Opus 4.6

---

## Question

When we initialize MC agents from the TM ergodic, we independently
sample:
- `(j, mNrm)` from the TM ergodic distribution
- `pLvl` from the analytical age-conditional lognormal

These are drawn **independently** — there is no modeled covariance
between mNrm and pLvl.  In the true ergodic cross-section, mNrm
and pLvl may be correlated (e.g., agents with high pLvl may have
systematically different savings behavior).

**Does this independence assumption cause the initialized MC
distribution to be non-stationary?  How fast do the marginals
and joint moments evolve over the first 20 periods?**

---

## Plan

### Step 1: Track marginal distributions over 20 periods

From TM-initialized MC (N=80K, college type), simulate 20 periods
under base conditions.  Each period, record:
- Mean, std, p25, p50, p75 of **aNrm** (end-of-period savings)
- Mean, std, p25, p50, p75 of **pLvl**
- Mean, std, p25, p50, p75 of **mNrm** (beginning-of-period resources)
- Per-state fractions

### Step 2: Track joint moments

Each period, record:
- `Corr(aNrm, pLvl)` — the key cross-sectional correlation
- `Corr(mNrm, pLvl)` (at beginning of period, if available)
- `Corr(log(aNrm+1), log(pLvl))` — log-space correlation
  (more natural for lognormal variables)

### Step 3: Compare with burn-in MC

Run the same 20-period tracking on a standard burn-in MC (400-period
burn-in).  This gives the "target" joint distribution.  Compare:
- Do the marginal moments match at t=0?
- Do the joint correlations match at t=0?
- If not, how many periods until the TM-initialized MC's moments
  converge to the burn-in MC's steady-state moments?

### Step 4: Assess whether independence matters

If `Corr(aNrm, pLvl)` at t=0 in TM-initialized MC differs
substantially from the burn-in MC, this means the independence
assumption is wrong and matters.  Key diagnostic:
- If Corr is ~0 in both → independence is fine
- If Corr is ~0 in TM-init but nonzero in burn-in → we're
  missing a real correlation and the distribution will evolve
  toward it over time
- If Corr stabilizes within a few periods → a short "warmup"
  (5-10 periods) after TM initialization would suffice

### Step 5: Conclusions

Report whether:
1. The marginals are approximately stationary (drift < 1%/period)
2. The joint distribution needs a warmup period
3. If so, how many periods

---

## Implementation

Single test script: `test_joint_distribution_quality.py`.
GLP-1 setup (college type, N=80K).
Output: table of moments by period + comparison with burn-in.

---

## Expected runtime

- TM ergodic + initialization: ~2s
- 20 periods of MC simulation: ~5s
- Burn-in MC (400 periods): ~15s
- Total: ~25s
