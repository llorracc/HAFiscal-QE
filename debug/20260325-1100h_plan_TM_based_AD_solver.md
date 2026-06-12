# Plan: TM-Based Aggregate Demand (AD) Solver

**Date:** 2026-03-25 11:00
**Author:** Claude Opus 4.6
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`

---

## 1. What AD does in the current MC code

The AD feedback loop solves for a path of aggregate consumption
ratios `Cratio[t]` such that the economy is self-consistent:
agents' consumption responds to aggregate demand, which is itself
determined by agents' consumption.

### The iteration (in `AggFiscalModel.py`)

The methods `solve_ad_recession`, `solve_ad_check_recession`,
`solve_ad_ui_extension_recession`, and `solve_ad_recession_taxcut`
all follow this pattern:

```
1. Start with Cratio_path = [1, 1, ..., 1]  (no AD effect)
2. Loop up to num_max_iterations:
   a. Set economy's CFunc to map aggregate consumption to Cratio
   b. Run MC experiment with current Cratio_path
   c. Measure resulting AggCons path
   d. Compute new Cratio_path from AggCons via the AD elasticity
   e. Check convergence: |change in CFunc| < tolerance?
   f. If converged, stop; else update and repeat
3. Store the converged solution (CFunc intercepts and slopes)
```

### The key equation

The AD feedback is:

```
Cratio[t] = 1 + ADelasticity × (AggCons[t] / AggCons_baseline - 1)
```

When consumption rises (e.g., from a stimulus check), Cratio > 1,
which further stimulates consumption (multiplier effect).  The
iteration finds the fixed point.

### What the MC provides

Each iteration calls `run_experiment()` (MC simulation) to compute
`AggCons[t]` for a given `Cratio_path`.  The MC simulates all
agents for all periods, with each agent's consumption scaled by
`Cratio[t]` at each period.

---

## 2. What needs to change for TM

The AD loop needs a function: `Cratio_path → AggCons_path`.
Currently this is MC's `run_experiment()`.  We replace it with
TM's `propagate_experiment_tm()`.

### The Cratio problem (known issue)

Composer's investigation found that `cFunc` ignores the Cratio
argument.  In `build_experiment_period_tm`, the code does:

```python
cPol_j = cFunc_j(m_eff, Cratio * np.ones_like(m_eff))
```

But `cFunc_j` is a `CRule` object that only uses its first
argument.  The second argument (Cratio) is silently ignored.

**This must be fixed first.**  Without it, TM cannot do AD.

### How Cratio works in MC

In MC, Cratio affects consumption through `get_controls`:

```python
def get_controls(self):
    CratioNow = self.get_Cratio_now()  # returns Cratio scalar
    for j in range(J):
        cNrm[state==j] = cFunc[j](mNrm[state==j], CratioNow)
```

The `CRule` objects in the solution are constructed so that
`CRule(mNrm, Cratio)` returns `Cratio * cFunc_base(mNrm)`.
But looking at the actual implementation:

```python
class CRule:
    def __init__(self, intercept, slope):
        self.intercept = intercept
        self.slope = slope
    def __call__(self, Cnow):
        return self.intercept + self.slope * Cnow
```

This takes ONE argument (Cnow, which is aggregate consumption
level, not Cratio).  The MC's `get_controls` must be doing
something different.

**Action item:** Read `AggFiscalType.get_controls` carefully to
understand exactly how Cratio enters consumption.  It may be that
Cratio multiplies the consumption AFTER cFunc evaluation, not as
an argument to cFunc.

---

## 3. Implementation plan

### Step 0: Understand the Cratio mechanism (research)

Read these methods in `AggFiscalModel.py`:
- `get_controls` — how agents compute cNrm given Cratio
- `get_Cratio_now` — how Cratio is derived from CFunc
- `solve_ad_recession` — the iteration loop
- `CRule` — what intercept/slope mean

Determine exactly how Cratio scales consumption.  Write a short
test confirming that MC consumption changes when Cratio changes.

**Expected finding:** Cratio likely multiplies the consumption
function output: `cNrm_actual = Cratio × cFunc(mNrm)`.  The
TM equivalent: `cPol_j = Cratio × cFunc_j(dist_mGrid)`.

### Step 1: Fix TM consumption scaling by Cratio

In `build_experiment_period_tm`, change:

```python
# Current (Cratio ignored):
cPol_j = cFunc_j(m_eff, Cratio * np.ones_like(m_eff))

# Fixed:
cPol_j = Cratio * cFunc_j(m_eff)
# (or however Cratio actually scales consumption in MC)
```

Also fix `aPol`:
```python
aPol_j = m_eff - cPol_j  # savings = mNrm - Cratio*cFunc(mNrm)
```

**Verify:** Run `propagate_experiment_tm` with Cratio=1.05 and
confirm AggCons changes (currently it doesn't).

### Step 2: Create `run_ad_tm` function

New function in `tm_methods.py`:

```python
def run_ad_tm(economy, shock_type, EconomyMrkv_init,
              baseline_tm_data, AggCons_baseline,
              ADelasticity, num_max_iterations=10,
              convergence_tol=0.01, mCount=100):
    """
    TM-based AD solver.  Iterates Cratio path to fixed point.

    Parameters
    ----------
    economy : AggregateDemandEconomy (with switch_shock_type already called)
    shock_type : str
    EconomyMrkv_init : list of int
    baseline_tm_data : list of dicts from compute_baseline_tm_data
    AggCons_baseline : np.ndarray, baseline AggCons path (from TM)
    ADelasticity : float (typically 0.3)
    num_max_iterations : int
    convergence_tol : float

    Returns
    -------
    dict with AggCons, AggIncome, Cratio_hist, NPV_AggCons, NPV_AggIncome
    """
    act_T = economy.act_T
    Cratio_path = np.ones(act_T)

    for iteration in range(num_max_iterations):
        # Run TM experiment with current Cratio_path
        result = propagate_with_cratio_path(
            economy, shock_type, EconomyMrkv_init,
            baseline_tm_data, Cratio_path, mCount)

        # Compute new Cratio from AD feedback
        AggCons_ratio = result['AggCons'] / AggCons_baseline
        Cratio_new = 1.0 + ADelasticity * (AggCons_ratio - 1.0)

        # Check convergence
        diff = np.max(np.abs(Cratio_new - Cratio_path))
        print(f"  AD iteration {iteration}: max|ΔCratio| = {diff:.6f}")
        if diff < convergence_tol:
            print(f"  Converged in {iteration+1} iterations")
            break

        Cratio_path = Cratio_new

    result['Cratio_hist'] = Cratio_path
    return result
```

### Step 3: Create `propagate_with_cratio_path`

This is a variant of `propagate_experiment_tm` that accepts a
time-varying `Cratio_path[t]` and uses `Cratio_path[t]` at each
period when building the TM:

```python
def propagate_with_cratio_path(economy, shock_type, EconomyMrkv_init,
                                baseline_tm_data, Cratio_path, mCount):
    # For each type:
    for i, agent in enumerate(economy.agents):
        bd = baseline_tm_data[i]
        result_i = propagate_experiment_tm(
            agent, bd['ergodic'], EconomyMrkv_init, bd['dist_mGrid'],
            bd['E_pLvl'], Cratio=Cratio_path,  # time-varying!
            act_T=act_T, base_aPol=bd['base_aPol'],
            shock_type=shock_type, check_info=check_info_i)
        ...
```

Currently `propagate_experiment_tm` accepts a scalar `Cratio`.
It needs to accept a path (array of length act_T) and use
`Cratio_path[t]` when building each period's TM.

**Note:** With a time-varying Cratio, the TM cache key must
include Cratio_t to avoid reusing the wrong cached TM.  This is
already handled: the cache key is `(macro_t, macro_next, emp_tc)`;
we add Cratio_t to it.  Actually, looking at the code, the cache
key already includes Cratio in Composer's version:
`(macro_t, macro_next, emp_tc, Cratio_t)`.

### Step 4: Wire into Simulate.py

In `Simulate.py`, the AD block currently does:

```python
if Run_AD:
    if not use_MC:
        print('WARNING: AD loop requires MC simulation.')
    else:
        AggDemandEconomy_Routine.solve_ad_recession(...)
```

Change to:

```python
if Run_AD:
    if use_TM:
        # TM-based AD
        result_AD = run_ad_tm(
            AggDemandEconomy_Routine, shock_type,
            EconomyMrkv_init, baseline_tm_data,
            AggCons_baseline_tm, ADelasticity, ...)
        save_as_pickle(shock_type + '_results_AD', result_AD, figs_dir)
    elif use_MC:
        # MC-based AD (existing code)
        AggDemandEconomy_Routine.solve_ad_recession(...)
```

### Step 5: Handle recession duration averaging

The AD experiments average over recession durations (11 paths).
For each duration, the AD loop runs separately.  The TM AD solver
handles one path at a time; the averaging loop in Simulate.py
wraps it, same as for non-AD.

---

## 4. Runtime estimate

Each AD iteration requires one `propagate_experiment_tm` call.
With 21 types, act_T=100, mCount=100: ~2 seconds per iteration.
With ~4 iterations to convergence: ~8 seconds per shock type.
With 4 recession shock types × 11 durations: ~350 seconds (~6 min).

Compare with MC AD: ~2 minutes per iteration × 4 iterations ×
4 types × 11 durations = ~6 hours.

**Speedup: ~60×.**

---

## 5. Validation

Compare TM AD multipliers with MC AD multipliers:
- Published (MC): Check AD=1.234, UI AD=1.211, TaxCut AD=0.978
- TM AD should be within ~5% of these

Also verify:
- Cratio_path converges (not oscillating or diverging)
- The number of iterations matches MC (~4)
- Non-AD results are unchanged (regression check)

---

## 6. Prerequisites

Before implementing:
1. **Understand the Cratio mechanism** (Step 0) — must be done first
2. **Phase 2 Check fix merged** to main branch
3. **validate scripts use burn=400** (so MC comparisons are fair)

---

## 7. Files to modify

| File | Change |
|------|--------|
| `tm_methods.py` | Fix Cratio in `build_experiment_period_tm`; add `run_ad_tm`; make `propagate_experiment_tm` accept Cratio path |
| `Simulate.py` | Wire TM AD solver into the AD block |
| `AggFiscalModel.py` | Read-only: understand `get_controls`, `solve_ad_*` |

---

## 8. Risk assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Cratio mechanism is more complex than expected | Medium | Step 0 research before coding |
| AD iteration doesn't converge with TM | Low | Same economics as MC; start from MC's converged Cratio if needed |
| TaxCut AD wrong due to BUG-010 | High | Known issue; document, don't block on it |
| Check AD bucket carry interacts with Cratio | Medium | Test with and without bucket carry |

---

## 9. Priority and timeline

This is **Phase 4** — the last major feature.  Estimated effort:
- Step 0 (research): 1 hour
- Steps 1-2 (core): 2-3 hours
- Steps 3-4 (wiring): 1-2 hours
- Step 5 (validation): 1-2 hours
- Total: **1 day**

After this, the full reproduction pipeline can run TM-only,
producing all tables and figures (non-AD and AD).
