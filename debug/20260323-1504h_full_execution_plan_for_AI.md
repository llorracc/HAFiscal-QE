# TM-vs-MC Validation: Full Execution Plan

**Date:** 2026-03-23
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
**Author:** Claude Opus 4.6
**Audience:** An AI agent with access to the codebase, no prior conversation context.

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

### What has been completed (commits up to `be9a8914`)

**Phase 1 (done):**
- Half-step TM at experiment boundary (closed a 21% UI consumption TE gap)
- Per-cohort ergodic distribution (exact age-dependent death)
- Default mCount raised from 50 to 100
- BUG-014: lognormal mean correction for pLvl initialization
- MC initialization from TM ergodic with 24-period warmup (replaces
  400-period burn-in)
- All validate scripts pass base_aPol for consistent half-step

**Verification commands for Phase 1:**
```bash
cd Code/HA-Models/FromPandemicCode
python AggFiscalMAIN_reduced.py --glp1  # TM-only, ~4 min
python validate_tm_ui.py --agents 200000 --seeds 3 --mcount 100  # ~3 min
python test_cohort_ergodic.py  # ~15s
python test_tm_init_mc.py  # ~7 min
cd /path/to/HAFiscal-Latest
bash reproduce.sh --comp mini  # ~10s
```

Expected: UI consumption TE rel error <4%, Check income TE <1%,
GLP-1 multipliers printed, mini passes.

---

## Phase 2: Debug the Check experiment 29% consumption TE gap

### Problem

The stimulus check ("Check") experiment shows TM NPV consumption
TE = 1.28 vs MC = 0.91 — a **29% discrepancy**.  Income TE matches
well (~1%).  This gap is independent of initialization method (both
TM-init and burn-in MC give ~0.91).

### Likely cause

The Check mechanism in TM uses `_compute_check_buckets` in
`tm_methods.py` to handle the pLvl-dependent stimulus check:
- The check amount depends on pLvl (phase-out for high earners)
- The TM splits agents into pLvl buckets, each with its own
  E[pLvl] and check amount
- The bucket construction or the interaction between buckets and
  the TM distribution may be incorrect

### How to investigate

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
   - Check: is the phase-out function applied consistently?
   - Check: is the check applied at the right period (t=0)?
   - Check: does the pLvl bucket E[pLvl] match the actual MC
     distribution?

3. **Write a diagnostic:**
   - Single college type (GLP-1 setup)
   - Run MC Check experiment, extract per-agent check amounts
   - Run TM Check experiment, extract per-bucket check amounts
   - Compare: total check disbursed, per-agent consumption
     response, NPV treatment effect

4. **Fix and validate:**
   - Once the discrepancy is identified, fix the TM Check
     implementation
   - Re-run `validate_tm_check.py --agents 200000 --seeds 3`
   - Target: <5% consumption TE rel error

### Key files

| File | What to look at |
|------|----------------|
| `tm_methods.py` | `_compute_check_buckets`, `propagate_experiment_tm` check period block, `_check_phase_out_scalar` |
| `AggFiscalModel.py` | `make_idiosyncratic_shock_histories` (Check branch), `CheckStimLvl`, `CheckPeriod` |
| `Simulate.py` | `run_experiments_no_recessions` for Check, `Run_FullRoutineNoRecessions` |
| `validate_tm_check.py` | Existing Check validation script |
| `Parameters.py` | `Check_changes`, `CheckStimLvl`, `CheckPeriod`, phase-out parameters |

---

## Phase 3: Per-cohort experiment propagation

### Problem

Currently `propagate_experiment_tm` propagates a single distribution
vector.  The per-cohort ergodic (from Phase 1) is only used for MC
initialization — TM propagation still uses the standard eigenvector
ergodic with effective death rate.  This means TM levels have a ~2%
bias (which cancels in treatment effects but affects absolute levels).

### What to do

Modify `propagate_experiment_tm` to propagate T_age separate cohort
distributions per period instead of one.  Each period:
1. Each cohort k ages to k+1
2. Apply the full TM transition (with LivPrb for random death only,
   NOT effective death)
3. Cohort at T_age is removed (forced death)
4. New cohort 0 = newborn distribution
5. Aggregate across cohorts for period consumption/income

### Implementation details

- The TM matrix used should have `LivPrb` (not `_effective_LivPrb`)
  for the random death component.  Build it with the raw LivPrb.
- Storage: T_age × (M × J) floats per period.  With T_age=200,
  M=100, J=4: 80,000 floats = 640KB.  Trivial.
- Runtime: T_age matrix-vector multiplies per period.  At ~100μs
  each: 200 × 100μs = 20ms per period.  For 100 periods: 2s.
  Still much faster than MC.
- The half-step at period 0 must be applied per-cohort: each
  cohort has its own aNrm distribution, so the initial-step TM
  gives a different period-0 distribution for each cohort.
- Aggregate consumption = sum over cohorts of (cohort_weight ×
  E[pLvl|age_k] × C_nrm_k).  This requires per-cohort E[pLvl],
  which is E[pLvl_init] × G^k.

### Validation

- Per-cohort TM aggregate consumption should be closer to MC
  burn-in than the single-distribution TM
- Treatment effects should be similar (they already match well)
- Level accuracy should improve from ~1.2% to <0.5%

### Key constraint

The standard ergodic must remain available for the half-step TM
(it's the fixed point of the standard TM).  The per-cohort
propagation uses a different TM (with raw LivPrb, not effective),
so the half-step approach needs rethinking for per-cohort mode.
One option: skip the half-step entirely in per-cohort mode, since
each cohort's distribution is already the correct beginning-of-
period distribution for that age (no need to consume→save→
transition like the single-distribution case).

---

## Phase 4: TM-based AD solver (future project)

### Problem

The aggregate demand (AD) feedback loop requires iterating:
guess aggregate demand → simulate → measure consumption →
update guess → repeat.  Currently this uses MC simulation
inside the loop.  TM can replace MC here, making the full
reproduction pipeline TM-only.

### Scope

- Modify `solve_ad_recession` and related methods in
  `AggFiscalModel.py` to accept a simulation engine
  (MC or TM)
- The TM engine would call `propagate_experiment_tm` with
  a Cratio path instead of running MC
- The convergence criterion and iteration logic stay the same

### Effort

Significant (days).  Separate project.  Not blocking any
current validation work.

---

## Testing and Reproduction Commands

### Quick smoke test (~5 min)
```bash
cd Code/HA-Models/FromPandemicCode
python AggFiscalMAIN_reduced.py --glp1
```
Should print GLP-1 multipliers for all shock types.

### Full MC+TM comparison (~15 min)
```bash
# Set sim_method='both' in AggFiscalMAIN_reduced.py, then:
cd Code/HA-Models/FromPandemicCode
MPLBACKEND=Agg python AggFiscalMAIN_reduced.py
```

### Reproduce suite
```bash
cd /path/to/HAFiscal-Latest
bash reproduce.sh --comp nano   # ~5s
bash reproduce.sh --comp micro  # ~7s
bash reproduce.sh --comp mini   # ~10s
bash reproduce.sh --comp min    # ~15 min
```

### Individual validation scripts
```bash
cd Code/HA-Models/FromPandemicCode
python validate_tm_ui.py --agents 200000 --seeds 3 --mcount 100
python validate_tm_check.py --agents 200000 --seeds 3 --mcount 100
python validate_tm_taxcut.py --agents 200000 --seeds 3 --mcount 100
```

### Diagnostic scripts (in FromPandemicCode/)
| Script | Purpose |
|--------|---------|
| `test_cohort_ergodic.py` | Compare per-cohort vs standard ergodic vs MC burn-in |
| `test_tm_init_mc.py` | TM-initialized MC: stationarity check + Check TE |
| `test_joint_distribution_quality.py` | 20-period marginal/joint moment tracking |
| `test_first_period_trace.py` | Per-step MC vs TM comparison at period 0 |
| `test_glp1_convergence.py` | N and mCount convergence sweep |
| `test_final_convergence.py` | Definitive N sweep for UI consumption TE |

---

## HARK Dependency Note

The UV venv (`/.venv-darwin-arm64`) needs HARK from the local
`./HARK` symlink (→ `/Volumes/Sync/GitHub/econ-ark/HARK` on branch
`main_improve-tm-vs-mc-sim-infra-and-examples`).  This branch has
`ConsAggIndMarkovModel` needed by `Parameters.py`.  If imports fail:
- Check for stale `site-packages/HARK/` directory shadowing the
  editable install (remove it)
- The `HARK/` symlink in project root can cause namespace conflicts
  when running from the project root; reproduce scripts cd to
  code dirs to avoid this
- **Never downgrade HARK** to work around import errors; debug the
  current version instead

---

## Bug Documentation

All bugs are documented in:
- `BUGS_private/HARK+HAFiscal_TM_vs_MC_bug_index.md` (index with
  summary table)
- `BUGS_private/HARK+HAFiscal_TM_vs_MC_changelog.md` (per-change
  details and revert instructions)
- `debug/` directory contains per-session analysis documents

Current bug count: BUG-001 through BUG-014.
