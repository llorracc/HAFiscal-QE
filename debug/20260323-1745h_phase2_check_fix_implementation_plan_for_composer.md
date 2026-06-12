# Phase 2 Check Fix: Per-Bucket Propagation Implementation Plan

**Date:** 2026-03-23 17:45
**Author:** Claude Opus 4.6
**Audience:** Composer (implementing AI)
**Branch to work on:** `phase2-check-fix-composer` (create from `5a6d56f3`)

---

## 1. The problem (what you're fixing)

The TM overestimates the Check consumption treatment effect at
periods 1+ by ~65% per period.  Period 0 is correct.

**Root cause:** The check gives low-pLvl agents a bigger normalized
transfer (check_nrm = CheckStimLvl / pLvl).  They save more of it.
At period 1+, agents with high mNrm (from check savings) have low
pLvl.  The TM computes `AggCons = N × E[pLvl] × E[cFunc(mNrm)]`,
which equals `E[c] × E[p]`.  But the true value is
`E[c × p] = E[c] × E[p] + Cov(c, p)`, and `Cov < 0` because
high-c agents have low-p.  TM overestimates by ignoring the Cov.

**Proof:** `test_check_cov_hypothesis_claude.py` shows that MC with
uniform pLvl (replacing each agent's pLvl with E[pLvl]) matches TM
to within 1% at every period.  The entire gap is from the covariance.

---

## 2. The fix (what you're implementing)

Currently, at the check period (t=0), the code propagates
`n_buckets` separate distributions (one per pLvl bucket), each with
its own E_pLvl_b.  At period 1, these are merged into a single
distribution and the standard path takes over with a single E_pLvl.

**The fix:** Continue propagating the per-bucket distributions
at periods 1, 2, ..., K (where K ≈ 20-30).  Each bucket retains
its E_pLvl_b.  After K periods, merge back to a single distribution.

---

## 3. Where the code lives

All changes are in one function: `propagate_experiment_tm` in
`tm_methods.py`.  No other files need to change.

---

## 4. Current code flow (what happens now)

Here is the current flow in `propagate_experiment_tm`, simplified:

```python
# Before the main loop: dist is a single vector of shape (M*J,)

for t in range(act_T):

    if is_check_period:          # only at t=0
        # Loop over buckets
        for bucket in buckets:
            TM_b, cPol_b = build_experiment_period_tm(..., mNrm_shift=bucket['mNrm_shift'])
            # Consumption for this bucket (uses E_pLvl_b)
            C_level_agg += w_b * (nonsplurge_b + splurge_b)
            Y_level_agg += w_b * (income_b)
            # Transition for this bucket
            dist_next_agg += w_b * (TM_b @ dist)

        C_series[t] = C_level_agg
        Y_series[t] = Y_level_agg
        dist = dist_next_agg   # <-- MERGES all buckets into one distribution
        continue

    else:                        # t >= 1, standard path
        TM_t, cPol_t = build_experiment_period_tm(agent, macro_t, macro_next, ...)
        agg_t = compute_period_aggregates_tm(dist, cPol_t, ...)
        C_series[t] = N * E_pLvl * agg_t['C_splurge_nrm']    # <-- single E_pLvl
        Y_series[t] = N * E_pLvl * agg_t['Income_nrm']
        dist = TM_t @ dist
```

The problem is on the line marked "MERGES all buckets into one
distribution" and the lines marked "single E_pLvl".

---

## 5. New code flow (what you're changing it to)

```python
# Before the main loop:
dist = ...           # single vector, shape (M*J,)
bucket_dists = None  # will be set at the check period
bucket_weights = None
bucket_E_pLvl = None
BUCKET_PROPAGATION_PERIODS = 20  # how many periods to track buckets

for t in range(act_T):

    if is_check_period:          # only at t=0
        # Same as before: loop over buckets for consumption
        bucket_dists = []
        bucket_weights = []
        bucket_E_pLvl = []

        for bucket in buckets:
            TM_b, cPol_b = build_experiment_period_tm(..., mNrm_shift=bucket['mNrm_shift'])
            C_level_agg += w_b * (nonsplurge_b + splurge_b)
            Y_level_agg += w_b * (income_b)
            # Store per-bucket distribution (NOT merged)
            dist_next_b = TM_b @ dist
            bucket_dists.append(dist_next_b)
            bucket_weights.append(w_b)
            bucket_E_pLvl.append(bucket['E_pLvl_b'])

        C_series[t] = C_level_agg
        Y_series[t] = Y_level_agg

        # Normalize each bucket distribution
        for k in range(len(bucket_dists)):
            d = bucket_dists[k]
            if sp.issparse(d):
                d = np.asarray(d).flatten()
            d = np.maximum(d, 0.0)
            s = np.sum(d)
            if s > 0:
                d /= s
            bucket_dists[k] = d

        # Also set dist = weighted sum (for fallback / debugging)
        dist = sum(w * d for w, d in zip(bucket_weights, bucket_dists))
        dist /= np.sum(dist)
        continue

    elif bucket_dists is not None:
        # PERIODS 1..K: propagate per-bucket distributions
        TM_t, cPol_t = build_experiment_period_tm(agent, macro_t, macro_next, ...)

        # Get IncShkDstn for splurge/income computation
        IncShkDstn_t = [agent.IncShkDstn[0][macro_t * J_micro + j] for j in range(J_micro)]

        C_level_agg = 0.0
        Y_level_agg = 0.0

        for k in range(len(bucket_dists)):
            w_b = bucket_weights[k]
            E_pLvl_b = bucket_E_pLvl[k]
            d_b = bucket_dists[k]

            # Consumption for this bucket (same as standard path but with E_pLvl_b)
            agg_b = compute_period_aggregates_tm(d_b, cPol_t, dist_mGrid, IncShkDstn_t, Splurge)
            C_level_agg += w_b * agent.AgentCount * E_pLvl_b * agg_b['C_splurge_nrm']
            Y_level_agg += w_b * agent.AgentCount * E_pLvl_b * agg_b['Income_nrm']

            # Transition this bucket to the next period
            d_next = TM_t @ d_b
            if sp.issparse(d_next):
                d_next = np.asarray(d_next).flatten()
            d_next = np.maximum(d_next, 0.0)
            s = np.sum(d_next)
            if s > 0:
                d_next /= s
            bucket_dists[k] = d_next

        C_series[t] = C_level_agg
        Y_series[t] = Y_level_agg

        # Also update the aggregate dist (for periods after bucket tracking ends)
        dist = sum(w * d for w, d in zip(bucket_weights, bucket_dists))
        dist /= np.sum(dist)

        # After K periods, stop per-bucket tracking
        periods_since_check = t - check_info['period']
        if periods_since_check >= BUCKET_PROPAGATION_PERIODS:
            bucket_dists = None  # revert to standard path
        continue

    else:
        # Standard path (no check, or after bucket tracking ended)
        # ... unchanged from current code ...
```

---

## 6. Detailed instructions

### 6.1 Add a constant

At the top of `propagate_experiment_tm`, add:

```python
BUCKET_PROPAGATION_PERIODS = 20
```

This controls how many periods after the check to track per-bucket
distributions.  20 is enough — the Cov decays by ~(1-MPC)^t per
period, so after 20 periods it's very small.

### 6.2 Add state variables before the main loop

Before the `for t in range(act_T)` loop, add:

```python
bucket_dists = None
bucket_weights = None
bucket_E_pLvl = None
```

### 6.3 Modify the check period block (t=0)

Currently the check block ends with:

```python
dist = np.maximum(dist_next_agg, 0.0)
s = np.sum(dist)
if s > 0:
    dist /= s
continue
```

Change this to: instead of merging into `dist_next_agg`, store
per-bucket distributions separately.  See the pseudocode in
section 5 for the exact structure.

**What to keep:** The consumption and income computation inside
the bucket loop stays exactly the same — that's already correct
(it uses per-bucket E_pLvl_b).

**What to change:** Instead of `dist_next_agg += w_b * (TM_b @ dist)`,
store each `TM_b @ dist` in `bucket_dists[k]`.

### 6.4 Add the per-bucket propagation block (t=1..K)

Add an `elif bucket_dists is not None:` block after the check
block.  This block:

1. Builds ONE TM for the current period (standard, no mNrm_shift)
2. Loops over buckets:
   a. Computes consumption from `bucket_dists[k]` using
      `compute_period_aggregates_tm` (existing function)
   b. Multiplies by `bucket_E_pLvl[k]` (NOT the global E_pLvl)
   c. Transitions `bucket_dists[k]` via the standard TM
3. Sums consumption/income across buckets
4. After BUCKET_PROPAGATION_PERIODS periods, sets
   `bucket_dists = None` to stop tracking

### 6.5 The standard path (t>K) is unchanged

Once `bucket_dists` is set to None, the code falls through to the
existing standard path.  No changes needed there.

---

## 7. Important details you must get right

### 7.1 The TM for periods 1+ is UNSHIFTED

At t≥1, there is no check.  The TM is the standard
`build_experiment_period_tm(agent, macro_t, macro_next, dist_mGrid,
Cratio)` with NO `mNrm_shift`.  Build it ONCE per period and
reuse for all buckets.

### 7.2 Each bucket's E_pLvl_b is CONSTANT over time

The bucket's E_pLvl does not change — it's the average pLvl of
agents in that pLvl range, determined at period 0.  The pLvl
evolves by PermGroFac each period, but since PermGroFac is the
same for all agents, the RATIO between buckets stays constant.
(If you wanted to be precise, you could multiply E_pLvl_b by
PermGroFac each period, but this is a tiny correction — the
important thing is that different buckets have different E_pLvl.)

Actually, to be precise: multiply each bucket's E_pLvl_b by
PermGroFac each period:

```python
for k in range(len(bucket_E_pLvl)):
    bucket_E_pLvl[k] *= PermGroFac_avg
```

where `PermGroFac_avg = agent.PermGroFac[0][0]`.  This ensures
the level scaling grows correctly over time.  The BASELINE also
uses E_pLvl (which was computed analytically and already accounts
for the age distribution), so for the treatment effect the growth
largely cancels.  But it's cleaner to include it.

### 7.3 Normalization of bucket distributions

Each `bucket_dists[k]` should sum to 1 (it's a probability
distribution over (j, mNrm) for agents in that pLvl bucket).
Normalize after each TM transition.

### 7.4 The aggregate `dist` should still be maintained

Keep updating `dist = sum(w_b * d_b)` even during bucket tracking.
This ensures that if anything else in the code reads `dist`, it
gets a reasonable answer.  And when bucket tracking ends, `dist`
is ready for the standard path.

### 7.5 The `employed_tran_shk_scale` parameter

If the shock_type involves TaxCut, there's an `emp_tc` factor.
For Check (not recessionTaxCut), `emp_tc = 1.0`.  Pass it through
as before: the bucket loop at t=0 uses it, and the standard TM
at t≥1 uses it.

### 7.6 Handling `check_info['period']` ≠ 0

The check can theoretically occur at any period (set by
`check_info['period']`).  In practice it's always period 0.
But write the code generically: start bucket tracking at
`check_info['period']`, not at t=0.

---

## 8. Testing

### 8.1 Run `test_check_perperiod_claude.py`

This shows the per-period TE profile.  After the fix, the
period-1+ TM values should be close to MC_real (not MC_uniform):

```
Before fix:  t=1: TM=0.109, MC_real=0.066, MC_uniform=0.110
After fix:   t=1: TM≈0.066  (should match MC_real)
```

### 8.2 Run `validate_tm_check.py`

```bash
python validate_tm_check.py --agents 200000 --seeds 3 --mcount 100
```

**Pass criterion:** Period-0 AggCons TE rel error < 5%.
The period-0 should stay at ~1% (unchanged).
The NPV gap should drop from ~38% to much less (maybe <5%).

### 8.3 Run the regression checks

```bash
python validate_tm_ui.py --agents 200000 --seeds 3 --mcount 100
python AggFiscalMAIN_reduced.py --glp1
bash reproduce.sh --comp mini
```

These should be unaffected (UI and TaxCut don't use check buckets).

---

## 9. What NOT to change

- Do NOT change `_compute_check_buckets` — the bucket setup is fine
- Do NOT change `build_experiment_period_tm` — the mNrm_shift
  mechanism is correct for period 0
- Do NOT change `compute_period_aggregates_tm` — it's correct
- Do NOT change anything in the standard (non-check) path
- Do NOT change anything for recession experiments
- Do NOT add pLvl as a TM state variable
- Do NOT change the MC code

---

## 10. Summary of changes

One function modified: `propagate_experiment_tm` in `tm_methods.py`.

Three additions:
1. State variables (`bucket_dists`, `bucket_weights`, `bucket_E_pLvl`)
   initialized before the main loop
2. Modified check block: stores per-bucket distributions instead of
   merging them
3. New `elif bucket_dists is not None:` block for periods 1..K that
   propagates per-bucket distributions with per-bucket E_pLvl

Runtime cost: ~10× per period for ~20 periods after the check.
With 100 periods total and n_buckets=10: 10 × 20 = 200 extra
TM transitions.  At ~0.1ms each: ~20ms total.  Negligible.
