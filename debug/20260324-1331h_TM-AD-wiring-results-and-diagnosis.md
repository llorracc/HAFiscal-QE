# TM AD Wiring: Implementation, Results, and Diagnosis of Zero Amplification

**Date:** 2026-03-24
**Author:** Claude Opus 4.6
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`

---

## 1. What was done

### 1.1 Goal

Wire a time-varying `Cratio` path into the TM (Transition Matrix) method so
that `sim_method='TM'` with `Run_AD=True` produces aggregate demand (AD)
multipliers without Monte Carlo simulation.

### 1.2 Implementation summary

Three files were modified:

**`tm_methods.py`:**
1. `propagate_experiment_tm` — accepts `Cratio` as scalar or array; converts
   scalar to `np.full(act_T, Cratio)` at entry; uses `Cratio_path[t]` per
   period in both the check-period and non-check branches; includes
   `Cratio_t` in the TM cache key.
2. `run_experiment_tm_nonbase` — passes `Cratio` through; `Cratio_hist`
   reflects actual values used (not hardcoded `np.ones`).
3. New function `run_ad_tm` — AD iteration loop: starts with
   `Cratio_path = np.ones(act_T)`, runs all agent types via
   `propagate_experiment_tm`, computes
   `Cratio_new = 1 + ADelasticity * (AggCons/baseline - 1)`, clips to
   `[0.8, 1.2]`, repeats until `max|delta Cratio| < tol`.

**`Simulate.py`:**
1. Added `run_ad_tm` to imports.
2. New helper `run_experiments_all_recessions_ad_tm` — loops over recession
   durations, calls `run_ad_tm` for each, averages with
   `recession_prob_array`.
3. `Run_AD` block: added TM path before MC path (both can run when
   `sim_method='both'`).
4. `Run_1stRoundAD` block: same pattern with `num_max_iterations=1`.
5. GLP-1 mode no longer forces `Run_AD=False`.

### 1.3 Testing performed

| Test | Result |
|------|--------|
| Syntax check (both files) | Pass |
| `import tm_methods; inspect.signature(run_ad_tm)` | Pass |
| Scalar-to-array Cratio conversion unit test | Pass |
| GLP-1 run (1 college type, TM, AD) | Pass — AD converges in 1 iter |
| Full Baseline run (21 types, TM, AD) | Pass — 441 min, all pickles saved |

---

## 2. Results

### 2.1 Full Baseline (CRRA2) — TM vs Published MC

Run configuration: `Parametrization='Baseline'`, `sim_method='TM'`,
21 agent types (3 education groups x 7 discount factors), `act_T=400`,
`mCount=100`, 21 recession durations averaged.

Output directory: `Figures/CRRA2_TM/`

#### Non-AD multipliers (treatment effect NPV(dC) / NPV(dY)):

| Policy | TM | Published MC | % Error |
|--------|---:|------------:|--------:|
| rec.UI | 0.929 | 0.906 | **+2.6%** |
| rec.TaxCut | 0.853 | 0.846 | **+0.8%** |
| rec.Check | 1.289 | 0.878 | **+46.8%** |

UI and TaxCut match MC closely. The Check discrepancy is a **pre-existing
bug** in the TM check-bucket/pLvl wiring (tracked separately, predates
this AD work).

#### AD amplification ratio (AD multiplier / non-AD multiplier):

| Policy | TM | Published MC |
|--------|---:|------------:|
| Check | **1.000** | 1.399 |
| UI | **1.000** | 1.334 |
| TaxCut | **1.000** | 1.152 |

**The TM AD produces zero amplification.** All AD multipliers are identical
to non-AD multipliers.

#### AD iteration convergence log (representative: recessionUI, duration 5):

```
AD-TM iter 0: max|dCratio| = 0.004484, mean Cratio = 0.9999
AD-TM iter 1: max|dCratio| = 0.000000, mean Cratio = 0.9999
AD-TM converged in 2 iterations
```

The Cratio path deviates from 1.0 by only ~0.0001-0.0005. After one
iteration, the correction is so small it rounds to 0.000000. The iteration
"converges" but to a fixed point where Cratio ~ 1.0 everywhere.

### 2.2 Runtime

| Phase | Time |
|-------|-----:|
| Baseline (solve + TM) | 21 min |
| Per recession shock (solve + nonAD + AD + 1stAD) | ~85 min |
| 4 recession shocks | 340 min |
| 3 no-recession shocks (solve + TM) | ~60 min |
| **Total** | **441 min (7.4 hrs)** |

For comparison, the full MC run with AD takes ~5 days.

---

## 3. Diagnosis: why TM AD produces zero amplification

### 3.1 How MC AD works (the correct mechanism)

The MC AD has **two interacting feedback channels**:

**Channel A — Income scaling (AggDemandFac):**
In `AggFiscalType.get_shocks()` (AggFiscalModel.py:734):
```python
self.state_now["mNrm"] = self.state_now["bNrm"] + self.shocks['TranShk'] * self.AggDemandFac
```
When `Cratio > 1`, `AggDemandFac = Cratio^ADelasticity > 1`, so agents
receive **more income**. This is a direct demand-side boost.

**Channel B — Beliefs (CFunc re-solve):**
In `solve_ad_recession()` (AggFiscalModel.py:1390-1469), each AD iteration:
1. Runs the MC experiment to get `Cratio_hist`
2. Updates `MacroCFunc` — the economy's consumption ratio transition rules
3. Re-solves all agents with the updated `CFunc`
4. Agents now **anticipate** future AD effects when making consumption
   decisions

The solver (line 975) embeds AggDemandFac into the consumption function:
```python
AggDemandFacnext_array = ADFunc(Cnext_array, RecState)
TranShkValsNext_tiled = AggDemandFacnext_array * TranShkValsNext_tiled_noAD
```

This means the consumption function is **solved differently** for each
Cgrid point — higher expected Cratio means higher expected future income,
which changes optimal consumption today.

### 3.2 How TM AD works (the current implementation)

The TM AD skips both channels:

**Channel A is missing:** The TM computes income from `IncShkDstn`
directly — it never multiplies TranShk by AggDemandFac. The `Cratio`
parameter only enters via the second argument to `cFunc(mNrm, Cratio)`,
which affects the **consumption policy** but not the **income**.

**Channel B is missing:** The TM AD does not re-solve agents. It evaluates
the **same** cFunc (solved once at Cratio=1.0 with `CFunc` = identity)
at different Cratio values. But with `CFunc` = identity (intercept=1,
slope=0), the 2D cFunc was solved with the **same** income expectations
for all Cgrid points. Varying Cratio at evaluation time has minimal effect
because the solver already "knows" that all Cgrid values produce the same
income.

### 3.3 Why Cratio ~ 1.0 (the arithmetic)

The AD formula is:
```
Cratio_new[t] = 1 + ADelasticity * (AggCons_experiment[t] / AggCons_baseline[t] - 1)
```

In the TM, both `AggCons_experiment` and `AggCons_baseline` are computed
from the **same** cFunc (solved without AD feedback). The ratio
`AggCons_experiment / AggCons_baseline` differs from 1.0 only because of
the policy shock (check, UI, tax cut), but the AD **amplification** of
that difference is absent. The difference is small (~0.1-0.5%), so
`Cratio ~ 1 + 0.3 * 0.003 ~ 1.001`. This Cratio is then fed back, but
evaluating `cFunc(m, 1.001)` vs `cFunc(m, 1.0)` produces a negligible
difference because the cFunc was solved under the assumption that all
Cgrid values yield the same AggDemandFac.

In contrast, the MC AD feedback is much larger because:
1. AggDemandFac scales **income** directly (Channel A), so higher Cratio →
   higher mNrm → more consumption → even higher Cratio
2. Re-solving agents (Channel B) makes them **anticipate** the feedback,
   further amplifying consumption

### 3.4 Summary of the failure mode

The TM AD implementation correctly wires Cratio through the code but
misses the two mechanisms that make AD amplification work:
1. **No income scaling** — TranShk is not multiplied by AggDemandFac
2. **No belief updating** — cFunc is not re-solved with updated CFunc/CRule

The result is a fixed point at Cratio ~ 1.0 with zero amplification.

---

## 4. Debugging plan: how to fix TM AD

### 4.1 Minimal fix: add income scaling (Channel A only)

The simplest fix adds the AggDemandFac income scaling to the TM without
re-solving agents. This captures the direct demand effect but not the
anticipation effect.

**Where to change:** `build_experiment_period_tm()` (tm_methods.py:835)

Currently:
```python
cPol_j = cFunc_j(m_eff, Cratio * np.ones_like(m_eff))
```

The TM builds transition matrices using `IncShkDstn` for income draws.
To add AggDemandFac scaling:

1. Compute `AggDemandFac = Cratio^ADelasticity` (during recession states)
2. Scale `TranShk` atoms in `IncShkDstn` by `AggDemandFac` before building
   the TM
3. This gives agents more income when Cratio > 1, creating the feedback loop

**Specific changes needed:**
- In `build_experiment_period_tm`, accept `ADelasticity` and `RecState`
- Compute `AggDemandFac = Cratio ** (ADelasticity * RecState)`
- Scale `IncShkDstn[j].atoms[1]` (TranShk values) by `AggDemandFac`
- Also scale the splurge income in `compute_period_aggregates_tm`

**Expected outcome:** This should produce AD amplification because higher
Cratio → higher income → more consumption → higher Cratio (positive
feedback). The amplification will be smaller than MC (missing Channel B)
but should be meaningful.

**Estimated effort:** ~50 lines of code changes in `tm_methods.py`.

### 4.2 Full fix: add income scaling + re-solve (Channels A + B)

To fully replicate MC AD, the TM AD iteration would need to:
1. Run TM experiment with current Cratio path → get `Cratio_hist`
2. Update `MacroCFunc` from `Cratio_hist` (same logic as MC, line 1432)
3. Set `economy.CFunc = Macro_2_Micro_CFunc(MacroCFunc)`
4. **Re-solve** all agents: `economy.solve()`
5. Rebuild baseline TM data with new cFunc
6. Repeat from step 1

This is much more expensive (~20 min solve per iteration × ~5 iterations
= ~100 min per shock type) but should closely match MC AD.

**Estimated effort:** ~100 lines, mainly in `run_ad_tm`.

### 4.3 Recommended approach

Start with **4.1 (income scaling only)**. This is the minimal change that
should produce meaningful AD amplification. If the resulting multipliers
are within ~10% of published MC AD values, Channel A alone may be
sufficient. If not, proceed to 4.2.

### 4.4 Diagnostic test to validate the fix

Before running the full model, verify on a single agent type:

```python
# 1. Run TM at Cratio=1.0 with NO income scaling → get AggCons_base
# 2. Run TM at Cratio=1.05 with NO income scaling → get AggCons_a
# 3. Run TM at Cratio=1.05 WITH income scaling (TranShk *= 1.05^0.3) → get AggCons_b
#
# Expected:
#   AggCons_a ~ AggCons_base (tiny difference — this is the current bug)
#   AggCons_b > AggCons_base (meaningful difference — income scaling works)
```

If `AggCons_b` shows a ~1-2% increase over `AggCons_base` when
Cratio=1.05, the income scaling is working and the AD iteration should
produce amplification.

---

## 5. Files modified in this implementation

| File | Changes |
|------|---------|
| `tm_methods.py` | `propagate_experiment_tm`: array Cratio + per-period indexing; `run_experiment_tm_nonbase`: Cratio_hist fix; new `run_ad_tm` function |
| `Simulate.py` | Import `run_ad_tm`; new `run_experiments_all_recessions_ad_tm`; TM paths in `Run_AD` and `Run_1stRoundAD` blocks; GLP-1 no longer forces AD off |
| `run_full_tm_ad.py` | Test script for full Baseline TM+AD run (new file) |
| `test_glp1_ad_tm.py` | Test script for GLP-1 TM+AD run (new file) |

Results saved in: `Figures/CRRA2_TM/` (28 pickle files).

---

## 6. Pre-existing issue: Check multiplier

The stimulus check (recessionCheck) non-AD multiplier is 1.289 in TM vs
0.878 in MC (+46.8% error). This predates the AD work and is tracked
separately. It likely stems from the check-bucket pLvl decomposition in
`propagate_experiment_tm` (the check period branch at line ~1219). UI and
TaxCut do not have this issue because they modify the Markov transition
structure rather than injecting a one-time transfer.

---

## 7. Key code references

### MC AD feedback chain (AggFiscalModel.py):
- `ADFunc` definition: line 1150 — `lambda C, RecState: C**(RecState * ADelasticity)`
- Income scaling: line 734 — `mNrm = bNrm + TranShk * AggDemandFac`
- Cratio computation: line 1122 — `Cratio = AggCons / base_AggCons[t]`
- CFunc update: line 1131 — `AggDemandFacNext = ADFunc(CratioNext, RecState)`
- Solver income scaling: line 975-976 — `TranShkValsNext *= AggDemandFac`
- AD iteration loop: line 1390-1469 — `solve_ad_recession()`

### TM code (tm_methods.py):
- `build_experiment_period_tm`: line ~835 — builds one-period TM
- `propagate_experiment_tm`: line ~1095 — propagates distribution
- `run_ad_tm`: line ~1472 — AD iteration loop (new)
- `cFunc` evaluation: line ~863 — `cFunc_j(m_eff, Cratio * ones)`

### Simulate.py:
- TM AD wiring: `Run_AD` block, `if use_TM:` branch
- AD helper: `run_experiments_all_recessions_ad_tm()`
