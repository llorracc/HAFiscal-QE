# TM-Initialized MC Agents & Check Treatment Effect Gap

**Date:** 2026-03-23
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
**Test script:** `Code/HA-Models/FromPandemicCode/test_tm_init_mc.py`
**Configuration:** GLP-1 mode — single college type (education index 2), point
discount factor (`DiscFacDstns[2].atoms[0][0]` = 0.9821), `Reduced_Run`
parametrization.

---

## 1. Goal

Eliminate (or drastically reduce) the ~400-period MC burn-in by
initializing MC agents directly from the TM ergodic distribution.
Then use this to compare TM and MC on the Check (stimulus check)
treatment effect.

## 2. Method

### 2.1 TM Ergodic Distribution

The transition matrix (TM) method computes the exact stationary
distribution `π(j, m)` over micro state `j ∈ {0,1,2,3}` (employed,
UB period 1, UB period 2, no benefits) and normalized market resources
`m = mNrm` on a grid of `mCount = 50` points.  This is the
beginning-of-period distribution: agents have received income but
have not yet consumed.

Key statistics of the ergodic (college type):
```
State 0 (employed):     frac = 0.973, mean mNrm = 2.30
State 1 (UB period 1):  frac = 0.018, mean mNrm = 2.00
State 2 (UB period 2):  frac = 0.006, mean mNrm = 1.76
State 3 (no benefits):  frac = 0.003, mean mNrm = 1.22
```

### 2.2 Sampling MC Agents from the Ergodic

For each of N = 80,000 agents:

1. **Draw `(j, mNrm)`** from the discrete ergodic distribution.
   Add uniform noise within each grid cell to avoid all agents
   sitting on exact grid points.

2. **Convert to end-of-period assets:**
   `aNrm = mNrm − cFunc_j(mNrm)`, since the MC's `save_state`
   records post-consumption assets.

3. **Draw age** from the ergodic age distribution:
   `P(age = k) ∝ LivPrb^(k−1)` for `k = 1, ..., T_age` where
   `T_age = 100`, `LivPrb = 0.99375`.

4. **Draw permanent income level:**
   ```
   log(pLvl) = Normal(pLogInitMean, pLogInitStd)  +  age × log(PermGroFac)
             + Normal(0, sqrt(PermShk_variance × age))
   ```
   where `pLogInitMean = 2.674`, `pLogInitStd = 0.53`,
   `PermGroFac = 1.004895`.  The third term accounts for the
   accumulated permanent shock variance over the agent's lifetime.

5. **Inject into MC agent:**
   Set `state_now['aNrm']`, `state_now['pLvl']`, `shocks['Mrkv']`,
   and `t_age` on the HARK agent object.  Also set economy-level
   state variables: `AggDemandFac = RfreeNow = CaggNow = Cratio = 1.0`.

### 2.3 Stationarity Verification

Simulated 10 periods under base conditions (no experiment shock) and
tracked mean aNrm, mean pLvl, and micro state fractions each period.

### 2.4 Check Treatment Effect Comparison

Ran the Check (stimulus check) experiment from the TM-initialized MC
state and compared the NPV consumption and income treatment effects
against:
- The TM result (analytical, no sampling noise)
- A standard burn-in MC (400-period burn-in, same N = 80,000)

---

## 3. Results

### 3.1 Stationarity Check

```
  t   mean_aNrm   mean_pLvl    frac_0
  0      1.4361     22.4661   0.97400
  1      1.4253     22.4464   0.97265
  ...
 10      1.3487     22.1714   0.97325
```

- **Micro state fractions**: stable (fluctuations < 0.2%) ✓
- **Mean aNrm**: drifts down 6.1% over 10 periods ✗
- **Mean pLvl**: drifts down 1.3% over 10 periods (mild)

The aNrm drift means agents start with too much savings relative
to the MC ergodic and gradually decumulate.  The burn-in MC converges
to mean aNrm = 1.259, while TM initialization gives 1.436.

**Likely causes of aNrm drift:**
- The TM ergodic's mNrm grid discretization produces a slightly
  different savings distribution than continuous MC
- The `aNrm = mNrm − cFunc(mNrm)` conversion uses the TM's cFunc
  evaluated on the grid, while MC agents use the HARK solver's
  interpolated cFunc at arbitrary mNrm values
- There may be a subtle mismatch between the TM's transition
  mechanics (which operate entirely in normalized space) and the
  MC's simulation mechanics (which track pLvl individually)

### 3.2 pLvl Initialization

| Quantity | Value |
|----------|-------|
| `exp(pLogInitMean)` | 14.50 |
| `E[pLvl_init]` (with lognormal variance) | 16.69 |
| `compute_analytical_mean_pLvl` | 21.02 |
| MC initialized mean pLvl | 22.47 |
| MC burn-in mean pLvl | 20.90 |

The initialized mean pLvl (22.47) overshoots the analytical value
(21.02) by 7%.  This is because the PermShk variance accumulation
formula `Normal(0, sqrt(σ² × age))` is approximate — it assumes
independent PermShk draws, but the actual cross-section also includes
selection effects (agents with very high/low pLvl die and are replaced).

### 3.3 Check Treatment Effect

| Method | NPV Cons TE | NPV Inc TE |
|--------|-------------|------------|
| TM (mCount=50) | 1.278 | 0.987 |
| MC, TM-initialized (3 seeds) | 0.910 | 0.994 |
| MC, burn-in (1 seed) | 0.912 | — |

**Key finding:** The TM-initialized MC matches the burn-in MC almost
exactly (0.910 vs 0.912, < 0.3% difference).  This confirms the
TM initialization is working correctly for practical purposes — the
aNrm drift is cosmetic for the treatment effect comparison because
both base and experiment start from the same initialized state.

**However:** There is a large TM-vs-MC gap on the Check consumption
TE: TM gives 1.278, MC gives 0.910 — a **29% discrepancy**.  This
gap is the same regardless of initialization method, indicating it
is a real TM-vs-MC methodological difference for the Check experiment,
not an initialization issue.

The income TE matches well (TM 0.987 vs MC 0.994 = 0.7%).

---

## 4. Conclusions

### What works
- **TM initialization of MC agents is viable.** The treatment effect
  from TM-initialized MC matches burn-in MC to < 0.3%, confirming
  the ergodic sampling is correct for the consumption function and
  state distribution.
- **State fractions** from TM initialization are stable over time.
- **Income treatment effects** match between TM and MC for Check.

### What needs further work

1. **aNrm drift (6% over 10 periods):** The TM ergodic gives
   systematically higher mean aNrm than the MC burn-in.  This may be
   a grid discretization effect or a mismatch in the normalized vs
   level-space mechanics.  Does not affect treatment effects (cancels
   in base − experiment difference) but should be understood.

2. **Check consumption TE gap (29%):** The TM overestimates the Check
   NPV consumption treatment effect by 29% relative to MC.  This is
   NOT from initialization — it's a TM-vs-MC methodological gap
   specific to the Check experiment.  Previously, the UI experiment
   was validated to < 1% agreement after the half-step fix.  The
   Check experiment likely requires a similar fix, possibly related
   to how the stimulus check's pLvl-dependent transfer is handled
   in the TM (via `_compute_check_buckets` and the per-bucket TM
   approach in `propagate_experiment_tm`).

3. **pLvl initialization overshoots by 7%.** The accumulated PermShk
   variance formula is approximate.  A more accurate approach would
   draw pLvl from the true cross-sectional distribution (which
   accounts for mortality selection), or run a short (~20 period)
   MC "warmup" after TM initialization to let pLvl variance settle.

### Recommended next steps
- Debug the 29% Check TM-vs-MC gap (the `_compute_check_buckets`
  mechanism in `tm_methods.py`)
- Investigate why TM ergodic mean aNrm (1.436) differs from MC
  burn-in (1.259) — likely the `compute_analytical_mean_pLvl`
  returning 21.02 vs actual MC mean pLvl of 20.90 affects the
  TM's level scaling

---

## 5. File References

| File | Role |
|------|------|
| `Code/HA-Models/FromPandemicCode/test_tm_init_mc.py` | Test script (this experiment) |
| `Code/HA-Models/FromPandemicCode/tm_methods.py` | TM implementation: `compute_baseline_tm_data`, `propagate_experiment_tm`, `compute_analytical_mean_pLvl` |
| `Code/HA-Models/FromPandemicCode/AggFiscalModel.py` | MC model: `AggFiscalType`, `AggregateDemandEconomy` |
| `Code/HA-Models/FromPandemicCode/Simulate.py` | Orchestration: `Simulate()` function with `sim_method`, `GLP1` flags |
| `Code/HA-Models/FromPandemicCode/AggFiscalMAIN_reduced.py` | Entry point: `--glp1` flag |
