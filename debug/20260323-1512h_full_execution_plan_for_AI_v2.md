# TM-vs-MC Validation: Full Execution Plan (v2)

**Date:** 2026-03-23 (revised)
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
**Author:** Claude Opus 4.6
**Audience:** An AI agent with access to the codebase, no prior conversation context.
**Revision note:** v2 incorporates answers to Composer questions from v1.

---

## Background

HAFiscal is a heterogeneous-agent consumption model that simulates
fiscal policy experiments (UI extensions, tax cuts, stimulus checks)
using Monte Carlo (MC) simulation.  A parallel Transition Matrix (TM)
method was added to compute the same experiments analytically (no
sampling noise, orders of magnitude faster).

This plan tracks validation of TM against MC and fixes to make them
agree.  The work is on branch
`0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`.

### Metric conventions used throughout this document

**Treatment effect (TE):** `TE[t] = experiment_AggX[t] - baseline_AggX[t]`
for X ∈ {Cons, Income}.

**Period-0 relative error (the primary pass/fail metric):**
```
rel_err = |TM_TE[0] - MC_TE[0]| / |MC_TE[0]|
```

The full-path max-rel-error is NOT used as a pass criterion because
later periods have near-zero TE (denominator → 0), making the ratio
meaningless.  It may be reported for information but should be ignored
for pass/fail.

**NPV TE (per-capita):**
```python
npv = calculate_NPV(experiment_AggX - baseline_AggX, act_T, Rfree)[-1] / N_agents
```
This is the total discounted treatment effect per agent over all
periods.  Units are consumption/income levels, not multipliers.
The multiplier is NPV_C / NPV_Y.

---

## What has been completed (commits up to `be9a8914`)

### Phase 1 (done)

- **Half-step TM** at experiment boundary — fixes 21% UI consumption
  TE gap by correctly modeling the transition from burn-in to
  experiment period 0
- **Per-cohort ergodic** — T_age separate age-cohort distributions
  eliminate death-rate composition bias.  Stored as `cohort_ergodic`
  in baseline data for MC initialization; standard eigenvector
  ergodic used for TM propagation (half-step requires it as fixed
  point)
- **Default mCount = 100** (was 50)
- **BUG-014** — lognormal mean correction for pLvl initialization
- **MC initialization from TM ergodic** with 24-period warmup
  (replaces 400-period burn-in in `Simulate.py`)
- **All validate scripts** pass `base_aPol` for consistent half-step

### Phase 1 verification

```bash
cd Code/HA-Models/FromPandemicCode

# GLP-1 mode: single college type, TM-only (~4 min, mostly solve)
python AggFiscalMAIN_reduced.py --glp1

# UI validation: period-0 TE should be <4% rel err
python validate_tm_ui.py --agents 200000 --seeds 3 --mcount 100
# Expected: AggCons[0] TE rel err ~0.75%, AggIncome[0] ~1.16%

# Cohort ergodic vs MC burn-in (~15s)
python test_cohort_ergodic.py
# Expected: per-cohort TM mean aNrm within ~0.8% of MC at mCount=100

# TM-init MC matches burn-in MC for Check TE (~7 min)
python test_tm_init_mc.py
# Expected: TM-init MC Check TE within 0.3% of burn-in MC

# Reproduce suite
cd /repo/root  # replace with actual repo root
bash reproduce.sh --comp mini
# Expected: passes
```

---

## Phase 2: Debug the Check experiment 29% consumption TE gap

**Execute Phase 2 BEFORE Phase 3.**

### Problem

The stimulus check ("Check") experiment shows:
- TM NPV per-capita consumption TE = 1.28
- MC NPV per-capita consumption TE = 0.91
- Gap: (1.28 - 0.91) / 0.91 = **+29%** (TM overstates)
- Income TE matches well (~1%)
- The gap is **independent of MC initialization method** — both
  TM-initialized MC and burn-in MC give ~0.91 (confirmed by
  `test_tm_init_mc.py`)

### Likely cause

The Check mechanism in TM uses `_compute_check_buckets` in
`tm_methods.py` to handle the pLvl-dependent stimulus check:
- The check amount depends on pLvl (phase-out for high earners)
- The TM splits agents into pLvl buckets, each with its own
  E[pLvl] and check amount
- The bucket construction or the interaction between buckets and
  the TM distribution may be incorrect

### Investigation steps

1. **Read the Check TM implementation:**
   - `tm_methods.py`: search for `_compute_check_buckets`,
     `check_info`, and the `is_check_period` block inside
     `propagate_experiment_tm` (~line 1140-1155)
   - `AggFiscalModel.py`: search for `CheckStimLvl`,
     `CheckPeriod`, `make_idiosyncratic_shock_histories` to
     understand how MC implements the check

2. **Compare TM vs MC Check mechanics step by step:**
   - In MC: the check adds `CheckStimLvl * phase_out(pLvl)` to
     each agent's TranShk at the check period
   - In TM: the check shifts the mNrm grid by
     `check_amount / pLvl` (normalized) per pLvl bucket
   - Verify: is the phase-out function applied consistently?
   - Verify: is the check applied at the right period (t=0)?
   - Verify: does the pLvl bucket E[pLvl] match the actual MC
     distribution?

3. **Write a diagnostic** (GLP-1 setup, single college type):
   - Run MC Check experiment, extract per-agent check amounts,
     consumption response at period 0
   - Run TM Check experiment, extract per-bucket check amounts,
     consumption response at period 0
   - Compare: total check disbursed, mean consumption response,
     NPV treatment effect
   - Use `test_first_period_trace.py` as a template for per-step
     MC tracing

4. **Fix and validate:**
   - Once the discrepancy is identified, fix the TM Check
     implementation
   - Re-run: `validate_tm_check.py --agents 200000 --seeds 3`
   - **Pass criterion:** Period-0 AggCons TE rel err < 5%
   - If NPV still has large error after period-0 is fixed,
     investigate per-period TE profile for later periods

### Key files

| File | What to look at |
|------|----------------|
| `tm_methods.py` | `_compute_check_buckets`, `propagate_experiment_tm` (check period block ~line 1140), `_check_phase_out_scalar` |
| `AggFiscalModel.py` | `make_idiosyncratic_shock_histories` (Check branch), `CheckStimLvl`, `CheckPeriod` |
| `Simulate.py` | `run_experiments_no_recessions` for Check, `Run_FullRoutineNoRecessions` |
| `validate_tm_check.py` | Existing Check validation script |
| `Parameters.py` | `Check_changes`, `CheckStimLvl`, `CheckPeriod`, phase-out parameters |
| `test_first_period_trace.py` | Phase 2 diagnostic — traces MC period-0 step by step |

---

## Phase 3: Per-cohort experiment propagation

**Execute Phase 3 AFTER Phase 2.**

### Problem

Currently `propagate_experiment_tm` propagates a single distribution
vector.  The per-cohort ergodic (from Phase 1) is only used for MC
initialization — TM propagation still uses the standard eigenvector
ergodic with effective death rate.  This means TM levels have a ~2%
bias (which cancels in treatment effects but affects absolute levels).

### Design

Modify `propagate_experiment_tm` to propagate T_age separate cohort
distributions per period instead of one.  Each period:
1. Each cohort k ages to k+1
2. Apply the experiment TM transition (with raw `LivPrb`, NOT
   `_effective_LivPrb`) for random death within each cohort
3. Cohort at T_age is removed entirely (forced death — exact)
4. New cohort 0 = newborn distribution
5. Aggregate across cohorts for period consumption/income:
   `AggCons[t] = sum_k weight_k * E[pLvl|age_k] * C_nrm_k`
   where `E[pLvl|age_k] = E[pLvl_init] * G^k`

**Why E[pLvl|age_k] = E[pLvl_init] × G^k is correct:**
E[PermShk] = 1 for both employed and unemployed states (unemployed
have deterministic PermShk = 1.0, employed have E[PermShk] = 1 by
construction of the lognormal approximation).  Therefore
E[pLvl|age k] = E[pLvl_init] × G^k regardless of employment
history.  Employment affects Var[pLvl|age] but not the mean, and
the Cov(c, pLvl) factorization error was measured at 0.06% of TE
(`test_pLvl_factorization.py`).

### Why no half-step is needed in per-cohort mode

In single-distribution mode, the ergodic is a mixture of all ages.
When the experiment changes the transition, agents of different ages
should get different period-0 distributions, but the single vector
can't represent this.  The half-step fixes this by
consuming→saving→transitioning as one operation.

In per-cohort mode, each cohort's distribution IS the correct
beginning-of-period distribution for agents of that age.  Applying
the experiment TM to each cohort separately gives the correct
period-0 distribution per age.  No half-step needed — the timing
issue that motivated the half-step doesn't exist when distributions
are tracked per-cohort.

### Implementation details

- Build TM with raw `LivPrb` (not `_effective_LivPrb`) for the
  random death component.  `_effective_LivPrb` is only needed for
  the single-distribution approximation.
- Storage: T_age × (M × J) floats per period.  With T_age=200,
  M=100, J=4: 80,000 floats = 640KB.  Trivial.
- Runtime: T_age matrix-vector multiplies per period.  At ~100μs
  each: 200 × 100μs = 20ms per period.  For 100 periods: 2s.
  Still much faster than MC.
- The Check bucket logic (`_compute_check_buckets`) from Phase 2
  operates on the aggregate distribution, not per-cohort.  The
  Phase 2 fix should work with the current aggregate ergodic.
  Phase 3 would then apply the check per-cohort (each cohort has
  a different E[pLvl], so the check normalized amount differs).
  The APIs are independent: Phase 2 fixes bucket internals,
  Phase 3 changes the propagation loop.

### Regression checklist

After implementing per-cohort propagation, ALL of these must pass
at their current error levels or better:

```bash
# UI: AggCons[0] TE rel err < 4%
python validate_tm_ui.py --agents 200000 --seeds 3 --mcount 100

# Check: AggCons[0] TE rel err < 5%; AggIncome[0] TE rel err < 1% (guard)
python validate_tm_check.py --agents 200000 --seeds 3 --mcount 100

# TaxCut: AggIncome[0] TE rel err < 1%
python validate_tm_taxcut.py --agents 200000 --seeds 3 --mcount 100

# Reproduce suite
bash reproduce.sh --comp mini

# GLP-1 multipliers should be sensible (no sign flips, no NaN)
python AggFiscalMAIN_reduced.py --glp1
```

---

## Phase 4: TM-based AD solver (future project)

**Out of scope until Phases 2-3 are closed.**

The aggregate demand (AD) feedback loop requires iterating:
guess aggregate demand → simulate → measure consumption →
update guess → repeat.  Currently this uses MC simulation
inside the loop.  TM can replace MC here, making the full
reproduction pipeline TM-only.

The AD solver's interface is: give me a Cratio path, I simulate
and return aggregate consumption.  Swapping MC for TM inside this
interface is a clean substitution.  No API pre-design or hooks
are needed in Phases 2-3.

Effort: significant (days).  Separate project.

---

## Testing and Reproduction Commands

### Quick smoke test (~5 min)
```bash
cd Code/HA-Models/FromPandemicCode
python AggFiscalMAIN_reduced.py --glp1
```
Should print GLP-1 multipliers for all shock types.

### Full MC+TM comparison
```bash
# Edit AggFiscalMAIN_reduced.py: set sim_method = 'both'
cd Code/HA-Models/FromPandemicCode
MPLBACKEND=Agg python AggFiscalMAIN_reduced.py
```

### Reproduce suite (run from repo root)
```bash
bash reproduce.sh --comp nano   # ~5s
bash reproduce.sh --comp micro  # ~7s
bash reproduce.sh --comp mini   # ~10s
bash reproduce.sh --comp min    # ~15 min
```

### Individual validation scripts (run from FromPandemicCode/)
```bash
python validate_tm_ui.py --agents 200000 --seeds 3 --mcount 100
python validate_tm_check.py --agents 200000 --seeds 3 --mcount 100
python validate_tm_taxcut.py --agents 200000 --seeds 3 --mcount 100
```

### Diagnostic scripts (in FromPandemicCode/)

| Script | Purpose | When to use |
|--------|---------|-------------|
| `test_cohort_ergodic.py` | Compare per-cohort vs standard ergodic vs MC burn-in | Phase 1 validation, Phase 3 development |
| `test_tm_init_mc.py` | TM-initialized MC: stationarity + Check TE | Phase 1 validation |
| `test_joint_distribution_quality.py` | 20-period marginal/joint moment tracking | Phase 1 validation |
| `test_first_period_trace.py` | Per-step MC vs TM comparison at period 0 | **Phase 2 Check debugging** |
| `test_glp1_convergence.py` | N and mCount convergence sweep | Accuracy characterization |
| `test_final_convergence.py` | Definitive N sweep for UI consumption TE | Phase 1 validation |

---

## HARK Dependency

The project requires HARK from branch
`main_improve-tm-vs-mc-sim-infra-and-examples` of the
`econ-ark/HARK` repository.  This branch includes the
`ConsAggIndMarkovModel` module needed by `Parameters.py`.

**Setup (machine-independent):**
```bash
# Clone or checkout the correct HARK branch
git clone https://github.com/econ-ark/HARK.git /your/path/to/HARK
cd /your/path/to/HARK
git checkout main_improve-tm-vs-mc-sim-infra-and-examples

# Install as editable into the project venv
uv pip install --python /path/to/HAFiscal/.venv/bin/python -e /your/path/to/HARK
```

**Troubleshooting:**
- If imports fail with `ModuleNotFoundError: ConsAggIndMarkovModel`,
  verify HARK is on the correct branch
- If `HARK.__file__` is `None`, check for a stale
  `site-packages/HARK/` directory shadowing the editable install
  (remove it)
- The `HARK/` symlink in the project root can cause namespace
  conflicts when running from the project root; run code from
  `Code/HA-Models/FromPandemicCode/` instead
- **Never downgrade HARK** to work around import errors; debug the
  current version instead

---

## Bug Documentation

All bugs are documented in:
- `BUGS_private/HARK+HAFiscal_TM_vs_MC_bug_index.md` — index with
  summary table (BUG-001 through BUG-014)
- `BUGS_private/HARK+HAFiscal_TM_vs_MC_changelog.md` — per-change
  details and revert instructions
- `debug/` directory — per-session analysis and diagnostic results
