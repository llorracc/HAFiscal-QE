# Phase A2: Baseline drift root cause investigation

**Direction:** Drilled down from Baseline to Smoke_Test (3 types, N=100)
to isolate the TM↔MC gap.

## Findings

### Finding 1: TM produces a perfectly constant non-recession baseline

```
Baseline   (21 types, N=10000): TM AggIncome[0..399] = 194557.41 (constant)
Smoke_Test (3 types,  N=100):   TM AggIncome[0..99]  = 1615.0381 (constant)
```

TM correctly identifies the analytic ergodic in both parametrizations.

### Finding 2: MC's non-recession baseline is HIGH and DRIFTS upward

```
Baseline   MC AggIncome:  197K (p=0)  → 204K (p=18)   mean 201185 (+3.4% vs TM)
Smoke_Test MC AggIncome: 1728 (p=0)  → 1851 (p=19)   mean (40 per) 1795 (+11.2% vs TM)
```

The drift is MC-side, parametrization-INDEPENDENT, and direction-consistent (UP).
Smoke_Test shows the drift MORE strongly than Baseline because at N=100 the
sampling variance amplifies any structural bias.

### Finding 3: The drift is in the NO-RECESSION baseline

The base experiment uses `EconomyMrkv_init = [0]*act_T` (no recessions during
the experiment). Yet TM and MC disagree by 3-11%. So the divergence does NOT
come from recession transitions during the experiment — it comes from the
INITIALIZATION / BURN-IN, which includes recession dynamics in MC's case.

## Root cause hypothesis

MC's burn-in (`make_history` over `act_T = 400` periods at Baseline, with
the full Markov chain that includes recessions) leaves the agent population
in a state where `E[pLvl]` has drifted upward. TM, computing the analytic
ergodic for `shock_type='base'`, never simulates the burn-in and gets a
clean steady-state value.

The drift is consistent with **incomplete lognormal mean correction on the
permanent-income shocks** — if `E[exp(ε_p)] ≠ 1` exactly in the realized
draws, mean pLvl grows exponentially over the burn-in horizon.

This is in the family of:
- **BUG-014** (lognormal mean correction in pLvl init) — fixed for TM init
- **BUG-018** (Urate mismatch in synthetic pLvl) — fixed for TM init
- **BUG-019** (compute_pLvl_distribution variance) — fixed for TM

All three were fixed for the TM init path. The fix may not have been ported
to (or may differ from) the MC `make_history` / `make_idiosyncratic_shock_histories`
path.

## Variance reduction status

`Code/HA-Models/FromPandemicCode/hafiscal_normalization.py` defines
`HAFiscalNormalizationMixin` (a subclass of HARK's
`PermanentIncomeNormalizationMixin`) that does per-period E[pLvl]
normalization to remove sampling drift.

`AggFiscalModel.py:1355` defines `NormalizedAggFiscalType` using this mixin.

**`Simulate.py:161` uses plain `AggFiscalType`, NOT `NormalizedAggFiscalType`.**
The variance-reduction mixin is defined but NOT wired into the production
pipeline.

If the normalization is mathematically correct, swapping `AggFiscalType` →
`NormalizedAggFiscalType` in `Simulate.py:161` should make MC's baseline
match TM's analytic value to floating-point precision.

## Why the asymptotic-equality work missed this

The test driver (`test_asymptotic_equality_revised.py`) has its own
`setup_economy` that does NOT use the same burn-in path as `Simulate.py`.
Specifically the test driver phases use a custom burn-in sequence
(`burnin_glp2`) that bypasses the production `make_history` call. So the
test driver's MC and TM agree because they both use a controlled
initialization, while `Simulate.py`'s MC and TM diverge because the MC
goes through the production burn-in.

This is consistent with the user's recollection of an "MC noise reduction
scheme that calculated analytically what the level of income SHOULD be" —
that scheme exists in the test driver / variance-reduction infrastructure,
but is NOT active in `Simulate.py`.

## Recommended next step

Single highest-value experiment: rerun Smoke_Test MC with `Simulate.py:161`
swapped to `NormalizedAggFiscalType`. ~10 min wall clock.

Outcomes:
1. **MC baseline becomes flat at 1615.04 matching TM** → root cause confirmed,
   the fix is to wire `NormalizedAggFiscalType` into the production path.
2. **MC baseline still drifts** → the normalization mixin itself has a bug
   at Smoke_Test scale; investigate the mixin.
3. **MC baseline matches a different constant** → the normalization is using
   the wrong analytic reference; investigate `effective_pLvl_growth`.

After the Smoke_Test result is known, repeat at Baseline to confirm the
fix scales.
