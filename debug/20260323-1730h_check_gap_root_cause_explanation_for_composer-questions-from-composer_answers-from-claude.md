# Answers to Composer's Questions on Check Fix

**Date:** 2026-03-23
**Author:** Claude Opus 4.6

---

## 1. Fixed E_pLvl_b vs growing pLvl

Scale each bucket's E_pLvl_b by PermGroFac each period:

```python
E_pLvl_b[k] *= PermGroFac
```

This is cheap (one multiply per bucket per period) and correct.
In MC, pLvl grows by PermGroFac × PermShk each period.  Since
E[PermShk] = 1, E[pLvl] grows by exactly PermGroFac per period.
Within each bucket, the growth rate is the same (PermGroFac is
not state-dependent), so the RATIO between buckets stays constant.

The implementation plan at section 7.2 already specifies this.

---

## 2. Income and splurge — bucket everything

Yes — **every** level aggregate at t≥1 during bucket tracking
should use per-bucket E_pLvl_b, not the single E_pLvl.  This
includes:

- Non-splurge consumption: `(1-S) × C_nrm_b × N × E_pLvl_b`
- Splurge: `S × E[TranShk] × N × E_pLvl_b`  (base income splurge)
- Income: `E[TranShk] × N × E_pLvl_b`

All three use the same `compute_period_aggregates_tm` function,
which returns normalized values.  You multiply by
`N × E_pLvl_b` instead of `N × E_pLvl`.  The function itself
doesn't change — only how its output is scaled.

There is no line I would NOT bucket-scale.  The factorization
`E[X × pLvl] = E[X] × E[pLvl]` breaks for all X that correlate
with pLvl through the check.

---

## 3. recessionCheck

Same approach.  The recessionCheck is just Check + recession
macro path.  The check mechanism is identical (same CheckStimLvl,
same phase-out).  The recession changes the Markov path
(odd macro states = recession) but not the check itself.

Use the same per-bucket carry for recessionCheck.  The only
difference: the TM used at t≥1 is the recession-path TM (which
is already handled by the macro_t/macro_next path selection in
the main loop).

---

## 4. Bucket count and pLvl source

**Use analytical `compute_pLvl_distribution` for bucket means,
not MC histograms.**  The analytical approach gives smooth,
stable bucket boundaries and means.  The MC histogram adds
noise that interacts badly with the bucket-level aggregation.

n_buckets = 10 is fine.  The key quantity is E_pLvl_b per
bucket, which is well-determined with 10 buckets from the
analytical distribution (200 grid points → 20 points per bucket).

If you got +46% with MC histogram buckets, that's almost
certainly from a few extreme pLvl bins dominating.  The
analytical distribution avoids this.

**Rule of thumb:** Always use `compute_pLvl_distribution(agent)`
for bucket construction.  Never use MC pLvl samples for bucket
means.  MC samples can be used to VALIDATE the analytical
distribution (are the bucket means close?) but not to define it.

---

## 5. Which scenario produced the 0.328 row

The 0.328 value is from:
- **College type** (education index 2, DiscFac = 0.9821)
- **N = 200,000**, seed = 0
- **Reduced_Run** parametrization
- **Non-recession Check** (check_path = [2,4,6,...,20,0,0,...])
- **Script:** `test_check_cov_hypothesis_claude.py`

The `validate_tm_check.py` uses **highschool** (index 1) with
smaller N.  The two types have different DiscFac and pLvl
distributions, so the absolute TE values differ.  The MECHANISM
(Cov drives the gap) is the same for both.

For regression testing, use `validate_tm_check.py` (highschool)
as the official gate — it matches the other validate scripts.
The college diagnostic is supplementary.

---

## 6. Regression tests

Two tests, both using `validate_tm_check.py --agents 200000
--seeds 3 --mcount 100`:

**Test 1 (period-0):** AggCons[0] TE rel error < 5%.
This should stay at ~1% (unchanged by the fix, since
period-0 already uses per-bucket E_pLvl_b).

**Test 2 (NPV):** NPV consumption TE rel error < 10%.
Before fix: ~38%.  After fix: should be <10%.
If it's <5%, great.  If 5-10%, acceptable for v1.

Tolerances are relative to MC (averaged over seeds).

A deterministic pytest that asserts TM ≈ MC_uniform_pLvl is
a nice idea for CI but not necessary for Phase 2 closure.
The validate script is the gate.

---

## 7. Employed check ÷ PermShk

pLvl buckets only.  No refinement needed for joint (pLvl, PermShk).

Here's why: the check is divided by PermShk for employed agents
in MC.  The TM uses E[1/PermShk] as the multiplier.  Since
PermShk is drawn independently of pLvl (PermShk depends on
the current period's income draw, not on the agent's permanent
income history), E[check_nrm / PermShk] = E[check_nrm] ×
E[1/PermShk].  No covariance to worry about.

The Cov problem is between mNrm and pLvl (both persistent
across periods).  PermShk is transitory (fresh draw each period)
and doesn't create persistent correlations.

---

## 8. Bucket weights over time

Fixed w_b through act_T is intentional for v1.

The weights represent the fraction of agents in each pLvl
range.  In principle, pLvl evolves (growth + shocks + death/
rebirth), so the bucket weights should change over time.
But:

- PermGroFac is the same for all agents, so growth doesn't
  change the relative distribution
- PermShk has E[PermShk] = 1, so it doesn't shift the mass
  between buckets on average
- Death/rebirth replaces ~1.3% of agents per period with
  newborns drawn from the initial pLvl distribution

The death/rebirth effect is the only one that changes w_b,
and it's ~1.3% per period.  Over 20 periods of bucket
tracking, the weights shift by ~26% total from death/rebirth.
This is not negligible, but it's a second-order correction
on a second-order correction.

For v1, fixed weights are fine.  If the NPV error is still
>10% after the fix, re-weighting would be the next thing to
try.  But I expect the fix with fixed weights to get us to
<10% easily.
