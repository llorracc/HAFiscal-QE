# Plan: Wire Cratio into TM for Aggregate Demand (AD) Feedback

**Date:** 2026-03-25
**Author:** Claude Opus 4.6
**Audience:** Another AI implementer (who needs explicit detail)

---

## 1. What this plan accomplishes

This plan enables the TM (Transition Matrix) method to produce
aggregate demand (AD) results by:

1. Making `propagate_experiment_tm` accept a time-varying
   `Cratio_path` instead of a scalar `Cratio`
2. Creating an AD iteration loop (`run_ad_tm`) that finds the
   fixed-point Cratio path
3. Wiring the AD loop into `Simulate.py`

After implementation, `sim_method='TM'` with `Run_AD=True` will
produce AD multipliers without any MC simulation.

---

## 2. Background: how AD works in MC

### 2.1 The economics

When the government gives agents a stimulus check, they consume
more.  This increased consumption boosts aggregate demand, which
further increases consumption (a multiplier effect).  The AD
feedback is:

```
Cratio[t] = 1 + ADelasticity × (AggCons[t] / AggCons_baseline - 1)
```

where `ADelasticity` is typically 0.3.  Cratio > 1 means the
economy is "running hot" and each agent's consumption is scaled up.

### 2.2 The iteration in MC

The MC AD solver (in `AggFiscalModel.py`) works as follows:

```
1. Initialize: Cratio_path = [1, 1, ..., 1]
2. Repeat up to num_max_iterations times:
   a. Set economy's CFunc[macro_i][macro_j] to map C → Cratio
      (intercept/slope linear rules derived from current solution)
   b. Solve agents under this CFunc
   c. Run MC experiment: simulate agents with Cratio_path
   d. Collect AggCons_path from MC
   e. Update Cratio_path from AggCons_path via AD elasticity
   f. Check convergence: max|change in CFunc| < tolerance?
3. Store converged CFunc (intercepts and slopes)
```

The key methods are:
- `solve_ad_recession` (line ~1201 of AggFiscalModel.py)
- `solve_ad_check_recession`
- `solve_ad_ui_extension_recession`
- `solve_ad_recession_taxcut`

Each follows the same pattern with minor variations.

### 2.3 How Cratio enters agent consumption

In MC (`get_controls`, line 874):

```python
cNrmNow[these] = self.solution[t].cFunc[j](
    self.state_now['mNrm'][these], CratioNow[these])
```

The `cFunc[j]` is a **genuine 2D interpolator** — a
`LowerEnvelope2D` wrapping `LinearInterpOnInterp1D` built on a
3-point `Cgrid = [0.8, 1.0, 1.2]`.  The solver builds separate
1D consumption functions for each Cgrid value, then interpolates
between them along the Cratio dimension.

**This means `cFunc(mNrm, Cratio)` ALREADY WORKS** — the second
argument is NOT ignored.  Composer's earlier report that "Cratio
is a no-op" was because Cratio=1.0 was always passed, which
happens to be the middle of the Cgrid and thus gives the same
answer as the Cratio=1 slice.  Passing Cratio=1.05 WILL change
consumption.

HOWEVER: there is a subtlety.  The `cFunc` is solved
simultaneously over `(mNrm, Cgrid)` where Cgrid represents the
NEXT PERIOD's expected aggregate consumption ratio, not the
current period's.  The solver computes optimal consumption today
given beliefs about tomorrow's aggregate state.  During the AD
iteration, the economy's `CFunc` (a `CRule` object) maps current
aggregate consumption to next period's Cratio.  This is how the
agent forms expectations about future aggregate conditions.

For TM: we don't need to replicate the agent-beliefs formation
(CFunc/CRule) within the TM.  We just need to evaluate `cFunc`
at the correct Cratio for each period, where Cratio is determined
by the AD iteration.

---

## 3. Current state of the TM code

### 3.1 `build_experiment_period_tm` (tm_methods.py, line ~835)

```python
def build_experiment_period_tm(agent, macro_t, macro_next,
                                dist_mGrid, Cratio=1.0, ...):
    for j in range(J_micro):
        cFunc_j = sol.cFunc[src_offset + j]
        m_eff = dist_mGrid + shift_j
        cPol_j = cFunc_j(m_eff, Cratio * np.ones_like(m_eff))
        aPol_j = np.maximum(m_eff - cPol_j, 0.0)
```

This ALREADY passes Cratio to cFunc correctly.  The 2D cFunc
returns different consumption at different Cratio values.

### 3.2 `propagate_experiment_tm` (tm_methods.py, line ~1095)

```python
def propagate_experiment_tm(agent, baseline_ergodic, EconomyMrkv_init,
                            dist_mGrid, E_pLvl, Cratio=1.0, ...):
```

Takes a **scalar** Cratio.  Inside the loop:

```python
for t in range(act_T):
    TM_t, cPol_t = build_experiment_period_tm(
        agent, macro_t, macro_next, dist_mGrid, Cratio, ...)
```

The same scalar Cratio is used at every period.  For AD, we need
a different Cratio at each period.

### 3.3 `run_experiment_tm_nonbase` (tm_methods.py, line ~1382)

```python
def run_experiment_tm_nonbase(economy, shock_type, EconomyMrkv_init,
                              baseline_tm_data, mCount=100, Cratio=1.0, ...):
```

Also takes scalar Cratio, passes it through to `propagate_experiment_tm`.

---

## 4. Implementation plan (step by step)

### Step 1: Make `propagate_experiment_tm` accept a Cratio path

**File:** `tm_methods.py`

**Change the signature:**

```python
# OLD:
def propagate_experiment_tm(agent, baseline_ergodic, EconomyMrkv_init,
                            dist_mGrid, E_pLvl, Cratio=1.0, act_T=None,
                            ...):

# NEW:
def propagate_experiment_tm(agent, baseline_ergodic, EconomyMrkv_init,
                            dist_mGrid, E_pLvl, Cratio=1.0, act_T=None,
                            ...):
    # At the top of the function, convert scalar to array:
    if np.isscalar(Cratio):
        Cratio_path = np.full(act_T, float(Cratio))
    else:
        Cratio_path = np.asarray(Cratio, dtype=float)
```

**In the main loop, use `Cratio_path[t]`:**

Currently the code has a `tm_cache` keyed by
`(macro_t, macro_next, emp_tc)`.  With time-varying Cratio,
the cache key must include Cratio_t because a different Cratio
produces a different TM:

```python
# OLD:
cache_key = (macro_t, macro_next, emp_tc)

# NEW:
Cratio_t = float(Cratio_path[t])
cache_key = (macro_t, macro_next, emp_tc, Cratio_t)
```

And when building the TM:

```python
# OLD:
TM_t, cPol_t = build_experiment_period_tm(
    agent, macro_t, macro_next, dist_mGrid, Cratio, ...)

# NEW:
TM_t, cPol_t = build_experiment_period_tm(
    agent, macro_t, macro_next, dist_mGrid, Cratio_t, ...)
```

**Also fix the check period block** (if is_check_period), which
currently uses the scalar `Cratio`:

```python
# OLD (in check block):
TM_b, cPol_b = build_experiment_period_tm(
    agent, macro_t, macro_next, dist_mGrid, Cratio, ...)

# NEW:
TM_b, cPol_b = build_experiment_period_tm(
    agent, macro_t, macro_next, dist_mGrid, Cratio_t, ...)
```

**And the post-check bucket carry block** (the elif block),
which also builds a TM:

```python
# Look for all occurrences of 'Cratio' being passed to
# build_experiment_period_tm and replace with Cratio_t
```

**IMPORTANT:** The Composer version of tm_methods.py already uses
`Cratio_t` in the cache key.  Check whether your version does
too — if so, you mainly need the scalar→array conversion and
the per-period indexing.

### Step 2: Make `run_experiment_tm_nonbase` accept a Cratio path

**File:** `tm_methods.py`

Change the signature to accept array or scalar:

```python
# OLD:
def run_experiment_tm_nonbase(economy, shock_type, EconomyMrkv_init,
                              baseline_tm_data, mCount=100, Cratio=1.0, ...):

# NEW: (same signature, but document that Cratio can be array)
```

Pass through to `propagate_experiment_tm`:

```python
result_i = propagate_experiment_tm(
    agent, bd['ergodic'], EconomyMrkv_init, bd['dist_mGrid'],
    bd['E_pLvl'], Cratio=Cratio, ...)  # Cratio can be scalar or path
```

### Step 3: Verify Cratio actually changes consumption

Write a test script `test_cratio_effect_claude.py`:

```python
# Build baseline TM data
bl = compute_baseline_tm_data(AggEco, mCount=100)
bd = bl[0]

# Run TM at Cratio=1.0
r1 = propagate_experiment_tm(agent, bd['ergodic'], path,
    bd['dist_mGrid'], bd['E_pLvl'], Cratio=1.0, ...)

# Run TM at Cratio=1.05
r2 = propagate_experiment_tm(agent, bd['ergodic'], path,
    bd['dist_mGrid'], bd['E_pLvl'], Cratio=1.05, ...)

print(f"AggCons[0] at Cratio=1.0:  {r1['AggCons'][0]}")
print(f"AggCons[0] at Cratio=1.05: {r2['AggCons'][0]}")
print(f"Difference: {r2['AggCons'][0] - r1['AggCons'][0]}")
# This MUST be nonzero.  If zero, the wiring is broken.
```

### Step 4: Create `run_ad_tm` function

**File:** `tm_methods.py`

This is the AD iteration loop for TM:

```python
def run_ad_tm(economy, shock_type, EconomyMrkv_init,
              baseline_tm_data, AggCons_baseline,
              ADelasticity=0.3, num_max_iterations=10,
              convergence_tol=0.004, mCount=100,
              check_info_per_type=None, verbose=True):
    """
    TM-based AD solver.  Iterates Cratio path to fixed point.

    Parameters
    ----------
    economy : AggregateDemandEconomy
        Economy with shock_type already set and solved.
    shock_type : str
    EconomyMrkv_init : list of int
    baseline_tm_data : list of dicts from compute_baseline_tm_data
    AggCons_baseline : np.ndarray, shape (act_T,)
        Baseline AggCons (from TM base experiment).
    ADelasticity : float
        AD feedback elasticity (default 0.3).
    num_max_iterations : int
    convergence_tol : float
        Convergence criterion on max|ΔCratio|.
    mCount : int
    check_info_per_type : list or None
        Per-type check_info dicts (for Check/recessionCheck).
    verbose : bool

    Returns
    -------
    dict with AggCons, AggIncome, Cratio_hist, NPV_AggCons, NPV_AggIncome
    """
    act_T = economy.act_T
    agents = economy.agents
    Rfree = agents[0].Rfree[0]

    Cratio_path = np.ones(act_T)

    for iteration in range(num_max_iterations):
        # Run TM with current Cratio_path
        AggCons_total = np.zeros(act_T)
        AggIncome_total = np.zeros(act_T)

        for i, agent in enumerate(agents):
            bd = baseline_tm_data[i]
            ci = (check_info_per_type[i]
                  if check_info_per_type is not None else None)
            result_i = propagate_experiment_tm(
                agent, bd['ergodic'], EconomyMrkv_init,
                bd['dist_mGrid'], bd['E_pLvl'],
                Cratio=Cratio_path,
                act_T=act_T,
                check_info=ci,
                shock_type=shock_type,
                base_aPol=bd.get('base_aPol'),
            )
            AggCons_total += result_i['AggCons']
            AggIncome_total += result_i['AggIncome']

        # Compute new Cratio from AD feedback
        # Cratio_new[t] = 1 + elasticity * (AggCons[t]/AggCons_base[t] - 1)
        ratio = AggCons_total / np.maximum(AggCons_baseline, 1e-10)
        Cratio_new = 1.0 + ADelasticity * (ratio - 1.0)

        # Check convergence
        diff = np.max(np.abs(Cratio_new - Cratio_path))
        if verbose:
            print(f"  AD iter {iteration}: max|ΔCratio| = {diff:.6f}, "
                  f"mean Cratio = {np.mean(Cratio_new):.4f}")

        if diff < convergence_tol:
            if verbose:
                print(f"  Converged in {iteration+1} iterations")
            break

        Cratio_path = Cratio_new.copy()

    # Final result with converged Cratio
    AggCons_final = np.zeros(act_T)
    AggIncome_final = np.zeros(act_T)
    for i, agent in enumerate(agents):
        bd = baseline_tm_data[i]
        ci = (check_info_per_type[i]
              if check_info_per_type is not None else None)
        result_i = propagate_experiment_tm(
            agent, bd['ergodic'], EconomyMrkv_init,
            bd['dist_mGrid'], bd['E_pLvl'],
            Cratio=Cratio_path,
            act_T=act_T,
            check_info=ci,
            shock_type=shock_type,
            base_aPol=bd.get('base_aPol'),
        )
        AggCons_final += result_i['AggCons']
        AggIncome_final += result_i['AggIncome']

    Cratio_hist = np.ones(act_T) * Cratio_path
    NPV_AggCons = calculate_NPV(AggCons_final, act_T, Rfree)
    NPV_AggIncome = calculate_NPV(AggIncome_final, act_T, Rfree)

    return {
        'AggCons': AggCons_final,
        'AggIncome': AggIncome_final,
        'Cratio_hist': Cratio_hist,
        'NPV_AggCons': NPV_AggCons,
        'NPV_AggIncome': NPV_AggIncome,
    }
```

### Step 5: Wire into Simulate.py

In `Simulate.py`, the AD block for each recession shock type
currently does:

```python
if Run_AD:
    if not use_MC:
        print(f'WARNING: AD loop requires MC simulation. '
              f'Skipping AD for {shock_type}...')
    else:
        # MC AD code...
```

Change to:

```python
if Run_AD:
    if use_TM:
        # TM-based AD
        from tm_methods import run_ad_tm
        AggDemandEconomy_Routine.switch_shock_type(shock_type)
        AggDemandEconomy_Routine.solve()

        # Need baseline AggCons for the AD feedback denominator
        # Use the non-AD TM result (already computed)
        AggCons_base = base_results_tm['AggCons']

        check_info_list = None
        if shock_type in ('recessionCheck',):
            check_info_list = [
                {'period': 0, 'buckets': _compute_check_buckets(a, bd['E_pLvl'])}
                for a, bd in zip(AggDemandEconomy_Routine.agents, baseline_tm_data)
            ]

        results_AD_tm = run_ad_tm(
            AggDemandEconomy_Routine, shock_type,
            EconomyMrkv_init, baseline_tm_data,
            AggCons_base,
            ADelasticity=AggDemandEconomy.agents[0].ADelasticity,
            num_max_iterations=num_max_iterations_solvingAD,
            convergence_tol=convergence_tol_solvingAD,
            check_info_per_type=check_info_list,
        )
        suffix = '_AD' if sim_method == 'both' else '_AD'
        save_as_pickle(shock_type + '_results' + suffix,
                       results_AD_tm, figs_dir)
    elif use_MC:
        # existing MC AD code (unchanged)
        ...
```

**IMPORTANT:** The existing MC AD path re-solves agents inside the
iteration loop (because CFunc changes the agent beliefs).  The TM
AD solver does NOT re-solve agents — it just evaluates the existing
2D cFunc at different Cratio values.  This is a simplification:
it assumes the consumption function's dependence on Cratio
(captured by the 3-point Cgrid interpolation) is sufficient.
If the converged Cratio is far from 1.0 (outside [0.8, 1.2]),
this interpolation may be inaccurate.

### Step 6: Handle the ADelasticity parameter

The AD elasticity is stored in the economy:

```python
ADelasticity = AggDemandEconomy.agents[0].ADelasticity
```

For `Reduced_Run`: `ADelasticity = 0.3` (from `Parameters.py`).

### Step 7: Handle the recession duration loop

The existing code averages AD results over recession durations:

```python
for dur in range(max_recession_duration):
    path = [...]  # recession path of length dur
    results_AD = run_experiments_all_recessions(...)
```

Create a TM equivalent:

```python
def run_experiments_all_recessions_ad_tm(dict_changes, economy,
        baseline_tm_data, AggCons_baseline, ...):
    shock_type = dict_changes['shock_type']
    all_results = []
    for dur in range(max_recession_duration):
        path = [...]  # same path construction as MC
        result = run_ad_tm(economy, shock_type, path,
            baseline_tm_data, AggCons_baseline, ...)
        all_results.append(result)
    # Average over durations
    avg_results = {}
    for key in ['AggCons', 'AggIncome']:
        avg_results[key] = sum(
            all_results[t][key] * recession_prob_array[t]
            for t in range(max_recession_duration))
    return [avg_results, all_results]
```

---

## 5. Files to modify

| File | Changes |
|------|---------|
| `tm_methods.py` | (1) `propagate_experiment_tm`: scalar→array Cratio, per-period Cratio_t in cache key and TM build. (2) `run_experiment_tm_nonbase`: pass Cratio through. (3) New function `run_ad_tm`. |
| `Simulate.py` | Wire TM AD path into the `if Run_AD` block. Add `run_experiments_all_recessions_ad_tm`. |

**Do NOT modify:** `AggFiscalModel.py` (the MC AD solver stays
unchanged), `Parameters.py`, `Output_Results.py`.

---

## 6. Testing

### Test 1: Cratio changes consumption

```bash
python test_cratio_effect_claude.py
```

Verify: AggCons differs between Cratio=1.0 and Cratio=1.05.
If zero difference, the wiring is broken.

### Test 2: AD iteration converges

Run with GLP-1 (fast):

```python
python AggFiscalMAIN_reduced.py --glp1
# But with Run_AD=True in GLP-1 mode
```

Verify: AD iteration prints decreasing max|ΔCratio| and converges
in ~4 iterations.

### Test 3: AD multipliers match MC

Run `validate_tm_check.py` or a custom script that compares:
- TM non-AD multiplier (no Cratio feedback)
- TM AD multiplier (with Cratio feedback)
- Published MC AD multiplier

Expected: TM AD multiplier should be ~10-30% higher than non-AD
(the AD amplification).  Published values:
- Check non-AD: 0.879, AD: 1.234 (ratio 1.40)
- UI non-AD: 0.906, AD: 1.211 (ratio 1.34)

### Test 4: Regression

```bash
python validate_tm_ui.py --agents 200000 --seeds 3 --mcount 100
python AggFiscalMAIN_reduced.py --glp1
bash reproduce.sh --comp mini
```

Non-AD results must be unchanged.

---

## 7. Edge cases to handle

### 7.1 Cratio outside Cgrid range [0.8, 1.2]

If the AD iteration produces Cratio > 1.2 or < 0.8, the cFunc
interpolation is extrapolating.  Linear extrapolation may be
reasonable for small exceedances.  For safety, clip:

```python
Cratio_t = np.clip(Cratio_path[t], 0.8, 1.2)
```

Or warn if clipping occurs.

### 7.2 Negative AggCons in denominator

If `AggCons_baseline[t]` is near zero (late periods), the ratio
`AggCons / AggCons_baseline` can blow up.  Use:

```python
ratio = AggCons_total / np.maximum(AggCons_baseline, 1e-10)
```

### 7.3 Non-convergence

If the iteration doesn't converge in `num_max_iterations`, print
a warning but still return the last result.  The MC solver does
the same.

### 7.4 The 1stRoundAD variant

The paper also reports "1st round AD" (one iteration only).
For TM, this is just `run_ad_tm(..., num_max_iterations=1)`.

---

## 8. Runtime estimate

Each AD iteration = one `propagate_experiment_tm` call per type.
With 21 types, act_T=400, mCount=100: ~5 seconds per iteration.
With ~4 iterations to convergence: ~20 seconds per shock type.
With 4 recession types × 11 durations: ~15 minutes total.

Compare MC AD: ~6 hours.  **Speedup: ~24×.**

---

## 9. What this plan does NOT cover

- Re-solving agents with updated CFunc beliefs during the TM AD
  iteration.  The MC AD solver re-solves agents each iteration
  (because agents' beliefs about future aggregate conditions
  change).  The TM AD solver uses the SAME cFunc throughout,
  relying on the 3-point Cgrid interpolation.  This is a
  simplification.  If results differ significantly from MC AD,
  consider adding a re-solve step.

- The `solve_ad_*` methods in `AggFiscalModel.py` update
  `self.intercept_prev` and `self.slope_prev` for the economy's
  CFunc.  The TM AD solver does not need these (it directly
  computes Cratio from AggCons).  But `Output_Results.py` may
  expect the stored CFunc — check if it's used downstream.
