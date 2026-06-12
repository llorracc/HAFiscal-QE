<!-- Status: DONE (superseded by implementation) -->
# Asymptotic Equality Test Plan: Four-Way Method Convergence in HAFiscal

**Date**: 2026-04-02
**Branch**: `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
**Companion**:
- `Harmenberg-Four-Way-Comparison.ipynb` (simple IndShock validation)
- `history/20260331-mathematical-derivations-harmenberg.md` (math)
- `history/20260402-reduced-run-harmenberg-output-type-map.md` (Type A/B/C)
- `history/20260404-hafiscal-four-way-verification-and-tm-init-report.md` — **outcome report** (baseline, single-type checker, TM init stability, lessons; AI-facing)

**Status (2026-04)**: Baseline **single education type**, `shock_type="base"`, is covered end-to-end by `Code/HA-Models/FromPandemicCode/verify_four_methods_agreement.py` (and `test_verify_four_methods_agreement.py`). That script compares **four** paths: MC P, MC Q (`DualAggFiscalType`), TM P (`run_experiment_tm`, `neutral_measure=False`), TM Q (`run_experiment_tm`, `neutral_measure=True`). The table in the Goal section below still describes the **full-paper** asymptotic program (multi-type, multi-scenario); for TM-P availability, treat the single-type baseline checker as the canonical HAFiscal TM-P reference unless a scenario is not yet implemented in `run_experiment_tm`.

**Revised phased ladder (supersedes ordering/prerequisites for execution):** `plans/20260404-1746h_asymptotic-equality-test-plan_revised.md` — incorporates four-way baseline gatekeeper, `act_T`/init lessons, **per-type** TM + MC + `baseline_tm_data[i]` alignment, and remaps original Phases 1–7 to phases A–G + `test_asymptotic_equality_revised.py` **named** phases (`--phase harness`, …; legacy `0`–`7` still work).

## Goal

Verify **asymptotic equality**: as MC agent counts grow and TM grids refine,
all four methods converge to the same answer for every HAFiscal experiment:

| Label | Method | Measure |
|-------|--------|---------|
| **P-MC** | Standard Monte Carlo | Physical measure P |
| **Q-MC** | Harmenberg neutral MC | Q-measure (via `DualAggFiscalType`) |
| **TM-P** | 2D Transition Matrix | Physical (standard `NewKeynesianConsumerType`) — *not available in HAFiscal pipeline; use P-MC as reference* |
| **TM-Q** | 1D Transition Matrix | Harmenberg neutral Q (`tm_neutral_measure=True`) |

In practice, HAFiscal does not implement a 2D TM path, so the comparison is
**P-MC vs Q-MC vs TM-Q** (three-way). We use multi-seed P-MC averages at
high agent counts as the "ground truth" reference where TM-Q is not available.

**Target**: 1–2% agreement on all Type A/B outputs (aggregate C, aggregate Y,
NPV multipliers) across all three methods.

## Lessons from the Notebook

The `Harmenberg-Four-Way-Comparison.ipynb` (simple `IndShockConsumerType`,
DiscFac=0.90, no Markov) established:

| Finding | Detail |
|---------|--------|
| **MC convergence** | 5,000 agents × 3 seeds gives ~0.3% error vs TM reference |
| **Q variance reduction** | ~100× lower variance for aggregate C per period |
| **TM grid convergence** | n_m ≥ 50 gives sub-0.1% error for aggregate C |
| **TM grid spacing** | Exponential nesting (`mFac=3`) concentrates points near zero |
| **TM boundaries** | `mMax=50` is ample for DiscFac=0.90; HAFiscal uses `aXtraMax=40` for the solver and `mMax=50` for TM |
| **Dual MC pairing** | P-track and Q-track from same seed match independent runs |
| **Ergodic dist** | Q-MC histogram matches TM-Q ergodic density with 10k agents |

**Key difference for HAFiscal**: HAFiscal has Markov states (4 micro × varying
macro), education heterogeneity (3 types × discount-factor bins), splurge, and
policy experiments. The notebook's simple model had none of these. We expect
HAFiscal to need **more agents and finer grids** for equivalent precision.

## Methodology

### Reference Values

For each test, compute reference values from:
1. **TM-Q fine**: `tm_mCount=150`, `tm_neutral_measure=True` (best available for Type A/B)
2. **P-MC large**: `AgentCountTotal=50000`, 5 seeds, averaged (ground truth for quantities TM cannot compute)

### MC Sweep Parameters

| Config label | `AgentCountTotal` | Seeds | Est. time (baseline) |
|-------------|-------------------|-------|---------------------|
| MC-tiny | 200 | 2 | ~5s |
| MC-small | 1,000 | 3 | ~15s |
| MC-med | 2,000 | 4 | ~45s |
| MC-large | 4,000 | 5 | ~90s |
| MC-xlarge | 8,000 | 6 | ~5min |
| MC-ref | 50,000 | 5 | ~10min |

### TM Grid Sweep Parameters

| Config label | `tm_mCount` | `mMax` | `mFac` | Est. time |
|-------------|-------------|--------|--------|-----------|
| TM-coarse | 30 | 50 | 3 | ~3s |
| TM-default | 50 | 50 | 3 | ~5s |
| TM-medium | 75 | 50 | 3 | ~8s |
| TM-fine | 100 | 50 | 3 | ~12s |
| TM-xfine | 150 | 50 | 3 | ~20s |
| TM-ultra | 200 | 80 | 3 | ~40s |

### Error Metric

For a quantity X computed by method M vs reference R:

```
relative_error_pct = 100 * |X_M - X_R| / |X_R|
```

Target: < 2% for all Type A/B outputs.

### Seed-Averaged MC

For MC methods, compute `X_MC = mean(X over seeds)` and
`SE_MC = std(X over seeds) / sqrt(n_seeds)`. Report both point estimate
error and standard error.

---

## Test Phases (Ordered by Estimated Runtime)

### Phase 0: Infrastructure — Test Harness Script (~30 min to write)

Create `Code/HA-Models/FromPandemicCode/test_asymptotic_equality_revised.py` that:
- Accepts CLI flags for which phase to run
- Parametrizes MC agent counts and TM grid specs
- Runs all three methods (P-MC, Q-MC, TM-Q) for each experiment
- Collects results into a structured dict
- Produces a summary table and (optionally) convergence plots
- Uses `Parametrization='Reduced_Run'` with `DiscFacCount=1` throughout
  (simplest structural config: 3 education types × 1 discount factor each)

### Phase 1: Baseline Ergodic Distribution (~2 min per config)

**What**: After burn-in, compare the steady-state distribution of `mNrm`
across methods. This is the foundation — if the ergodic distributions
disagree, nothing downstream will match.

**Quantities to compare**:
1. `E[mNrm]` — mean normalized market resources (per education type)
2. `E[cNrm]` — mean normalized consumption
3. `Var(mNrm)` — dispersion of normalized resources
4. `E[pLvl]` — mean permanent income level (P-MC only; analytical for TM-Q)
5. Aggregate consumption level `C = E_P[p · c(m)]`
6. Aggregate income level `Y = E_P[p · (θ · ADF)]`

**Methods**:
- **TM-Q**: Compute from ergodic distribution `erg_dstn` and policy grids
- **Q-MC**: Burn-in via `DualAggFiscalType`, then harvest `history_Q['mNrm'][-1,:]`
- **P-MC**: Same agent, harvest `history['mNrm'][-1,:]` and `history['pLvl'][-1,:]`

**Sweeps**: All TM grid sizes × MC-small, MC-med, MC-large (skip MC-ref for now)

**Expected runtime**: ~2 min per (TM, MC) pair × 6 TM × 3 MC = ~36 configs × 2 min ≈ 72 min.
But many can be batched (one MC run gives both P-MC and Q-MC). Realistic: ~30 min.

**Success criterion**: E[mNrm] and aggregate C agree to < 1% between
TM-Q (fine) and MC-large (3 seeds).

**Diagnostic if failing**: 
- Compare per-education-type distributions separately
- Check if burn-in is long enough (increase `mc_warmup` from 24 to 100)
- Check TM grid boundary: does the ergodic distribution have mass near `mMax`?
- If MC mean differs from TM by > 2% even at MC-xlarge, suspect a code bug
  in the aggregation formula (aggregation uses `E_P[p]` scaling)

### Phase 2: No-Recession Experiments — Stimulus Check (~3 min per config)

**What**: The simplest policy experiment. A one-time stimulus check with no
recession (no Markov state change). This isolates the "inject income, track
spending response" pathway.

**Quantities**:
1. `AggCons` time series (T=22 periods post-shock)
2. `AggIncome` time series
3. `NPV_AggCons` at terminal period
4. Multiplier = NPV_AggCons / NPV_AggIncome

**Why first among experiments**: No Markov state switching, shortest recession
duration (zero), simplest income shock structure. The stimulus check is also
an interesting test because it's the one policy that is **not p-linear**
(phase-out depends on income level), so Q-MC should show slight bias vs P-MC.

**Sweeps**: TM-default, TM-fine, TM-xfine × MC-med, MC-large

**Expected runtime**: ~3 min per config. ~12 configs × 3 min = ~36 min.

**Success criterion**: NPV multiplier agrees to < 2% across all three methods
at TM-fine / MC-large.

**Diagnostic if failing**:
- If TM-Q vs P-MC disagree by > 2%: check `calculate_NPV` sign conventions
- If Q-MC vs P-MC disagree by > 2%: expected for stimulus check due to
  non-p-linearity (§19 of math-derive-harm). Document the gap and verify it
  shrinks for UB extension (which IS p-linear).
- If Q-MC ≈ P-MC but both differ from TM-Q: grid resolution issue

### Phase 3: No-Recession Experiments — UB Extension and Tax Cut (~3 min each)

In **`test_asymptotic_equality_revised.py`**, UI extension and TaxCut are **separate CLI phases** (`--phase norec-ui`, `--phase norec-taxcut`; legacy `3` / `4`) so each experiment is its own step; recession steps are **`recession-baseline`** and **`recession-policies`**; AD stub is **`ad-loop`** (`plans/20260404-1746h_asymptotic-equality-test-plan_revised.md` §3).

**What**: Two more no-recession experiments that ARE p-linear (unlike stimulus
check), so Q-MC should exactly match P-MC in the limit.

**UB Extension**: Extends unemployment benefits. Purely p-linear (benefits
scale with permanent income via the `IncUnemp` replacement rate).

**Tax Cut**: Multiplicative change to transitory income. P-linear by
construction (multiplier on θ).

**Quantities**: Same as Phase 2 (AggCons series, NPV, multiplier).

**Sweeps**: TM-fine, TM-xfine × MC-med, MC-large

**Expected runtime**: ~3 min × 2 experiments × 8 configs = ~48 min.

**Success criterion**: All three methods agree to < 1% on NPV multiplier
for UB extension and tax cut (tighter than Phase 2 because these are p-linear).

**Diagnostic if failing**:
- UB ext: check `switch_shock_type` correctly modifies `IncShkDstn` and
  that `setup_Q_measure()` rebuilds `IncShkDstn_Q`
- Tax cut: check `hit_with_recession_shock` stores `_Q_TranShk_mult`
  and `_draw_Q_shocks` applies it
- If Q-MC and P-MC agree but TM-Q differs: check `tm_methods.run_experiment_tm`
  time-varying Markov transition arrays

### Phase 4: Recession Experiments — Baseline Recession (~5 min per config)

**What**: A recession with Markov state switching (22 or 42 macro states ×
4 micro states). This is the core HAFiscal use case. The recession alone
(no policy response) tests whether the three methods track the aggregate
demand drop and recovery identically.

**Quantities**:
1. `AggCons` recession path (with AD feedback)
2. `AggIncome` recession path
3. Duration-weighted NPV
4. `pLvl_factor` path (TM-Q analytical vs P-MC empirical `E[p_t]/E[p_ss]`)

**Sweeps**: TM-fine × MC-med, MC-large

**Expected runtime**: Recession experiments are ~2× slower due to more Markov
states. ~5 min × 6 configs = ~30 min.

**Success criterion**: Recession `AggCons` path agrees to < 2% at each
time period. `pLvl_factor` matches P-MC empirical mean(pLvl)/mean(pLvl_ss)
to < 1%.

**Diagnostic if failing**:
- Check Markov transition matrix dimensions match between TM and MC
- Check `pLvl_factor` computation in `tm_methods` vs empirical from MC
- If early periods match but later periods diverge: suspect `pLvl_factor`
  drift or AD feedback divergence

### Phase 5: Recession + Policy Experiments (~5 min each)

**What**: The full HAFiscal policy experiments: recession + {check, UB ext,
tax cut}. These are the paper's main results.

**Quantities**: Same as Phase 4, plus policy-vs-baseline differences
(the "delta" that defines the multiplier).

**Order** (by expected difficulty):
1. Recession + UB extension (p-linear, cleanest)
2. Recession + Tax cut (p-linear)
3. Recession + Stimulus check (non-p-linear, expect Q-MC bias)

**Sweeps**: TM-fine × MC-large

**Expected runtime**: ~5 min × 3 experiments × 3 configs = ~45 min.

**Success criterion**: Multipliers (NPV ΔC / NPV ΔY) agree to < 2%.

### Phase 6: AD Loop Convergence (~10 min per config)

**What**: The aggregate demand feedback loop. This is the most expensive
experiment and the one most sensitive to small differences in aggregate C,
because the AD loop feeds back into the transitory shock `AggDemandFac`.

**Quantities**:
1. Converged `AggDemandFac` path
2. `AggCons` after AD convergence
3. NPV multiplier after AD convergence

**Sweeps**: TM-fine × MC-large (only 2 configs)

**Expected runtime**: AD loop runs 5 iterations (reduced). ~10 min × 2 = 20 min.

**Success criterion**: Converged multiplier agrees to < 2%.

**Diagnostic if failing**:
- AD convergence tolerance in reduced run is 1E-2 (coarse). If the three
  methods find different converged points, tighten tolerance and add iterations.
- Check that the AD feedback uses the same aggregation formula for all methods.

### Phase 7: Comprehensive Convergence Sweep (~2 hours)

**What**: After Phases 1–6 identify any issues and establish baseline specs,
run a full convergence sweep to document the specs needed for 1–2% agreement.

**Sweep structure** (for each experiment that showed > 1% error in earlier phases):
- Fix TM-Q at TM-xfine (150 points) as reference
- Sweep MC from MC-tiny to MC-ref
- For each MC size, run 5 seeds
- Record: mean, SE, relative error vs TM-Q reference

Produce a table:

```
Experiment          | MC AgentCount | Seeds | Rel Error (%) | SE (%) | TM mCount | TM Error (%)
--------------------|---------------|-------|---------------|--------|-----------|-------------
Baseline C          | 1000          | 3     | 1.2           | 0.8    | 50        | 0.3
Baseline C          | 5000          | 3     | 0.4           | 0.3    | 75        | 0.1
...
Check (no-rec) NPV  | 10000         | 5     | 0.8           | 0.4    | 100       | 0.05
...
```

**Expected runtime**: ~2 hours total (many small runs).

---

## Spec Tracking: Minimum for 1–2% Agreement

This section will be filled in as phases complete. Initial guesses based on
the notebook results (simple model) scaled up for HAFiscal complexity:

| Experiment | MC AgentCount (est) | MC Seeds (est) | TM mCount (est) | Notes |
|-----------|--------------------:|---------------:|-----------------:|-------|
| Baseline ergodic | 5,000 | 3 | 50 | Notebook: 5k/3 was 0.3% |
| No-rec Check | 10,000 | 3 | 75 | Non-p-linear; Q-MC has inherent bias |
| No-rec UB ext | 5,000 | 3 | 50 | P-linear; expect fast convergence |
| No-rec Tax cut | 5,000 | 3 | 50 | P-linear |
| Recession baseline | 10,000 | 5 | 75 | More Markov states |
| Rec + UB ext | 10,000 | 5 | 75 | |
| Rec + Tax cut | 10,000 | 5 | 75 | |
| Rec + Check | 10,000 | 5 | 100 | Non-p-linear |
| AD loop | 10,000 | 5 | 100 | Feedback amplifies errors |

---

## Discrepancy Diagnosis Protocol

When a test shows > 2% error that does not shrink with more agents/finer grid:

1. **Isolate the method pair**: Which two methods disagree?
   - P-MC vs Q-MC: likely non-p-linearity (§19) or `_draw_Q_shocks` bug
   - P-MC vs TM-Q: could be grid boundary, aggregation formula, or `pLvl_factor`
   - Q-MC vs TM-Q: likely `pLvl_factor` (analytical vs empirical E[p])

2. **Check the math**: Revisit the relevant section of `math-derive-harm`:
   - §2 for shock reweighting
   - §7 for aggregation under Q
   - §8 for splurge term
   - §15 for Q-MC scalar aggregation
   - §19 for non-p-linear policies

3. **Trace the code path**: Use the per-period `AggCons` time series to find
   the first period where methods diverge. Inspect agent-level quantities
   at that period.

4. **Resolution categories**:
   - **Grid/sample size**: Document the minimum spec needed and move on
   - **Approximation**: Inherent to the method (e.g., Q-MC for stimulus check).
     Document the expected bias and verify it's bounded.
   - **Bug**: Fix the code, re-run all prior phases, update this document.

---

## Implementation Notes

### Using `Parametrization='Reduced_Run'` Throughout

All tests use `DiscFacCount=1` (one discount factor per education type)
to keep the structural model simple while still exercising the full Markov
machinery. This means 3 agent types × 1 bin = 3 agents in the economy.
The `AgentCountTotal` is split across these 3 types by `data_EducShares`.

### Solver Grid vs TM Grid

The consumption function solver uses `aXtraCount=48`, `aXtraMax=40`,
`PermShkCount=7`, `TranShkCount=7`. These are **not** varied in this plan —
they affect the quality of the consumption function, not the simulation.
The TM grid (`mCount`, `mMax`, `mFac`) is a separate grid for the
distribution tracking.

For the convergence sweep, if TM errors plateau above 1%, we may also
need to refine the solver grid (`aXtraCount`). This would be diagnosed
by TM-xfine and TM-ultra giving the same answer.

### Dual MC Setup

`DualAggFiscalType` runs P-MC and Q-MC simultaneously from a single
simulation, sharing random draws. This means for each MC configuration,
we get both P-MC and Q-MC results from one run, halving the total MC
computation.

### `HAFISCAL_FAST_GRIDS` Environment Variable

Setting `HAFISCAL_FAST_GRIDS=1` reduces solver grids (aXtraCount=24,
PermShkCount=5, TranShkCount=5). We should test with and without this
to verify the solver grid is not the bottleneck.

---

## Estimated Total Runtime

| Phase | Estimated Time |
|-------|---------------|
| 0: Infrastructure | 30 min (writing code) |
| 1: Baseline ergodic | 30 min |
| 2: No-rec Check | 36 min |
| 3: No-rec UB/Tax | 48 min |
| 4: Recession baseline | 30 min |
| 5: Rec + policies | 45 min |
| 6: AD loop | 20 min |
| 7: Full sweep | 2 hours |
| **Total** | **~5.5 hours** |

Phases 1–3 together take ~2 hours and cover all the "fast" tests.
If bugs are found, debugging time adds to this estimate.

---

## Deliverables

1. **Test script**: `test_asymptotic_equality_revised.py` with phase-by-phase CLI (`--phase harness`, …)
2. **Results document**: `history/20260402-asymptotic-equality-results.md`
   with convergence tables and diagnosed discrepancies
3. **Spec table**: Updated version of the "Minimum for 1–2% Agreement"
   table above, with actual measured values
4. **Code fixes**: Any bugs discovered during testing
5. **Updated `reproduce_min.py`**: If specs need to change for the reduced
   pipeline to achieve 1–2% cross-method agreement
