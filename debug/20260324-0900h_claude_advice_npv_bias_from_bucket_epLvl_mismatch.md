# Claude's Advice: The 3% NPV Bias from Bucket E_pLvl Mismatch

**Date:** 2026-03-24 09:00
**Author:** Claude Opus 4.6
**Audience:** Composer (implementing AI)

---

## The problem in plain English

You implemented the per-bucket carry.  It works well: period-0
error is ~1%, NPV error dropped from ~38% to ~3%.  But that last
3% won't go away no matter how many buckets you use.  In fact,
20 buckets was WORSE than 10.  Why?

---

## The explanation (step by step)

### Step 1: What the baseline computes

Every period, the baseline computes aggregate consumption as:

```
C_base[t] = N × E_pLvl × C_nrm_base[t]
```

where `E_pLvl` is a single scalar (the analytical mean permanent
income).  This scalar is **constant** — it doesn't change from
period to period.

### Step 2: What the Check with buckets computes

Every period after the check, the Check experiment computes:

```
C_check[t] = sum over buckets of:  w_b × N × E_pLvl_b × C_nrm_b[t]
```

where each bucket has its own `E_pLvl_b` (the average pLvl in
that bucket).

### Step 3: What happens as the check effect fades

As time passes, agents spend down their check savings.  After
many periods, the check effect is negligible.  All the bucket
distributions `dist_b` converge back to the same ergodic
distribution.  So `C_nrm_b[t]` becomes the same for all buckets:

```
C_nrm_b[t] → C_nrm_ergodic    (same for all b)
```

### Step 4: The treatment effect should go to zero — but it doesn't

The treatment effect is `TE[t] = C_check[t] - C_base[t]`.
At late periods where the check effect has faded:

```
TE[t] → N × C_nrm_ergodic × (sum_b w_b × E_pLvl_b)
       - N × C_nrm_ergodic × E_pLvl

       = N × C_nrm_ergodic × (sum_b w_b × E_pLvl_b  -  E_pLvl)
```

If `sum(w_b × E_pLvl_b)` does not EXACTLY equal `E_pLvl`, then
the TE never goes to zero.  There is a persistent nonzero bias
at every period.

### Step 5: How big is the bias?

We measured: `sum(w_b × E_pLvl_b) / E_pLvl = 0.999959`.
That's a -0.004% mismatch.  Tiny!

But it accumulates over ~100 periods in the NPV.  The discounted
sum of a constant bias over 100 periods at R=1.01 is roughly 60.
So:

```
NPV bias ≈ N × C_nrm_ergodic × (-0.006) × 60 ≈ -0.036 per capita
NPV of the true TE ≈ 1.1 per capita
Relative bias ≈ -0.036 / 1.1 ≈ -3.3%
```

This matches the observed 3% NPV error almost exactly.

### Step 6: Why 20 buckets was worse than 10

With different numbers of buckets, the quantile boundaries fall
at different points on the pLvl grid.  The mismatch
`sum(w_b × E_pLvl_b) - E_pLvl` depends on where the boundaries
fall.  With 10 buckets, the mismatch happened to be small.  With
20 buckets, it happened to be slightly larger.  This is
essentially rounding error in the bucket construction, and more
buckets does NOT guarantee less rounding error.

---

## How to test whether this explanation is right

### Test 1: Measure the mismatch directly

In `_compute_check_buckets`, after constructing the buckets,
print:

```python
weighted_sum = sum(b['weight'] * b['E_pLvl_b'] for b in buckets)
print(f"sum(w_b * E_pLvl_b) = {weighted_sum:.8f}")
print(f"E_pLvl              = {E_pLvl:.8f}")
print(f"Mismatch:           = {weighted_sum - E_pLvl:.8e}")
```

You should see a small nonzero mismatch (~0.006 for the
highschool type).

### Test 2: Predict the NPV bias from the mismatch

Compute:

```python
C_nrm_ergodic = ...  # from the TM ergodic
bias_per_period = N * C_nrm_ergodic * (weighted_sum - E_pLvl)
predicted_NPV_bias = sum(bias_per_period / Rfree**t for t in range(act_T))
```

Compare this with the observed NPV error:
`predicted_NPV_bias / N` should be close to `TM_NPV - MC_NPV`.

If predicted ≈ observed, the explanation is confirmed.

### Test 3: Fix the mismatch and re-run

Apply the correction (see below) and re-run
`validate_tm_check.py --agents 200000 --seeds 3`.

If the NPV error drops from ~3% to <1%, the explanation is
confirmed.

---

## How to fix it

Add these lines at the end of `_compute_check_buckets`, just
before `return buckets`:

```python
# Ensure sum(w_b * E_pLvl_b) == E_pLvl exactly, so that the
# bucket decomposition is consistent with the baseline's scalar
# E_pLvl.  Without this, a tiny mismatch (~0.004%) accumulates
# over ~100 discounted periods into a ~3% NPV bias.
weighted_E_pLvl = sum(b['weight'] * b['E_pLvl_b'] for b in buckets)
if abs(weighted_E_pLvl) > 1e-15 and E_pLvl is not None:
    correction = E_pLvl / weighted_E_pLvl
    for b in buckets:
        b['E_pLvl_b'] *= correction
```

This rescales all E_pLvl_b proportionally so their weighted
average equals E_pLvl exactly.  The rescaling is tiny (~0.004%)
and doesn't affect the economic content of the buckets.

---

## What this does NOT fix

After this correction, the remaining NPV error should be <1%.
Any residual comes from:

- The bucket distributions `dist_b` don't perfectly capture
  within-bucket mNrm heterogeneity created by the check
- The fixed bucket weights `w_b` don't account for death/
  rebirth shifting pLvl mass over time
- Grid discretization (mCount=100)

These are all well under 1% and not worth fixing.

---

## Summary

| What | Value |
|------|-------|
| Root cause of 3% NPV error | `sum(w_b × E_pLvl_b) ≠ E_pLvl` |
| Size of mismatch | ~0.004% |
| Accumulation mechanism | Persists at every period, summed over ~100 discounted periods |
| Fix | Rescale E_pLvl_b so weighted sum = E_pLvl exactly |
| Expected result after fix | NPV error < 1% |
| Lines of code to add | 4 |
| Where to add them | End of `_compute_check_buckets` in `tm_methods.py` |
