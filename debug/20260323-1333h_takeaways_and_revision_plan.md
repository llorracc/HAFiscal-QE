# Takeaways and Codebase Revision Plan

**Date:** 2026-03-23
**Author:** Claude Opus 4.6

---

## Takeaways

### T1. Minimum mCount = 100

At mCount=50, the TM grid discretization contributes ~2% error
on mean aNrm (per-cohort ergodic) and ~0.5% on consumption
treatment effects.  At mCount=100, these drop to ~0.8% and
~0.1% respectively.  The runtime cost is negligible (the TM
matrix-vector multiply is microseconds; the solve dominates).

**Default mCount should be 100, not 50.**

### T2. Half-step TM at experiment boundary is essential

The period-0 distribution must be computed from the post-
consumption (aNrm) ergodic + experiment transition + income,
not from the pre-consumption (mNrm) ergodic with labels shuffled.
Without this, the UI consumption TE has a 21% error.  With it,
the error is within MC sampling noise (+0.3σ at N=1M).

**Already implemented:** `base_aPol` parameter in
`propagate_experiment_tm`.  Must be passed by all callers.

### T3. Per-cohort ergodic replaces effective death rate

The `_effective_LivPrb` approximation applies death uniformly
across mNrm, but MC kills the oldest (wealthiest) agents.
The per-cohort approach (T_age separate distributions, one per
age) eliminates this bias with minimal runtime cost (~0.01s
for the ergodic, ~100× per-period cost which is still ≪ MC).

**Not yet integrated into production code.**

### T4. No within-cell jitter when sampling from TM ergodic

Adding uniform noise within grid cells inflates mean aNrm by
~10% via Jensen's inequality (cFunc is concave).  Sample on
exact grid points.  The TM ergodic is already the correct
discrete distribution; adding noise undoes it.

### T5. pLvl initialization with lognormal mean correction

When drawing pLvl for TM-initialized MC agents, the accumulated
PermShk must use Normal(-σ²k/2, σ√k), not Normal(0, σ√k).
Without the -σ²/2 correction, E[pLvl] overshoots by ~7%.
(BUG-014, already fixed.)

### T6. Independence of mNrm and pLvl is acceptable

The true cross-sectional Corr(aNrm, pLvl) ≈ -0.02.  Sampling
them independently introduces negligible error.  No joint
distribution modeling is needed.

### T7. pLvl scaling does not affect aNrm dynamics

Uniformly rescaling pLvl has zero effect on normalized savings
dynamics (confirmed by Composer experiment, scenarios D vs F).
The pLvl factorization error E[c·p] vs E[c]·E[p] is only 0.06%
of treatment effects.

### T8. GLP-1 mode is valuable for rapid iteration

Single college type, point discount factor, TM-only, fixed
recession duration: runs all experiments in <1 second (after
~2 min solve).  Essential for debugging and convergence testing.

### T9. AD loop needs MC (for now)

The aggregate demand feedback loop is hardwired to MC simulation.
TM-based AD is feasible but requires a separate development
effort.  Non-AD treatment effects and multipliers work with
TM alone.

### T10. Check experiment has a 29% TM-vs-MC gap (uninvestigated)

The Check (stimulus check) consumption TE shows TM=1.28 vs
MC=0.91 — a 29% discrepancy independent of initialization.
This is likely related to the pLvl-dependent check phase-out
mechanism in `_compute_check_buckets`.  Not yet debugged.

---

## Revision Plan

### Phase 1: Integrate proven fixes into tm_methods.py

**1a. Change default mCount from 50 to 100.**

Files: `tm_methods.py` (function signatures for
`compute_baseline_tm_data`, `run_experiment_tm_nonbase`,
`build_tm_agg_fiscal`).

Effort: trivial (change default parameter values).

**1b. Ensure all callers pass base_aPol for half-step.**

Files: `Simulate.py`, validate scripts, any other callers of
`propagate_experiment_tm`.

Currently the baseline propagation in `Simulate.py` and validate
scripts must explicitly pass `base_aPol=bd.get('base_aPol')`.
Verify all call sites do this.

Effort: small (audit + add parameter where missing).

**1c. Implement per-cohort ergodic in `build_tm_agg_fiscal`.**

Replace the current single-distribution ergodic (with effective
death rate) with T_age cohort distributions.  The aggregate
ergodic is the sum across cohorts.  Store it in the same format
as today (flat vector of length M×J) so downstream code
doesn't change.

The key change is inside `build_tm_agg_fiscal`:
- Build TM with LivPrb=1 (no death)
- Iterate: cohort_k = LivPrb × TM @ cohort_{k-1}
- Aggregate: ergodic = sum(cohorts) / sum(sum(cohorts))

Also store the per-cohort distributions in the baseline data
dict, since `propagate_experiment_tm` will need them for the
half-step (each cohort needs its own initial-step TM
application).

Effort: moderate (~1 hour).  The proof-of-concept works;
integration requires threading cohort arrays through
`propagate_experiment_tm`.

**1d. Remove within-cell jitter from TM→MC initialization.**

Files: `test_tm_init_mc.py` and any future `initialize_from_tm`
helper.

Effort: trivial (delete the jitter loop).

### Phase 2: Debug Check experiment gap

The 29% Check consumption TE discrepancy needs investigation.
The Check mechanism uses `_compute_check_buckets` which splits
agents into pLvl buckets for the phase-out computation.  This
may interact with the per-cohort ergodic (different cohorts
have different E[pLvl]).

Effort: 2-4 hours (diagnosis + fix).

### Phase 3: Integrate per-cohort propagation for experiments

Currently `propagate_experiment_tm` propagates a single
distribution vector.  With per-cohort tracking, it would
propagate T_age vectors per period.  This multiplies per-period
cost by T_age (~100×) but is still fast (~10s for all
experiments vs ~0.15s currently).

The half-step at period 0 must be applied to each cohort
separately (since each cohort has a different aNrm distribution).

Effort: moderate (~2 hours).  Can be deferred — the current
aggregate ergodic from phase 1c is sufficient for treatment
effects (the per-cohort propagation would improve level
accuracy but the TE improvement is small since errors cancel).

### Phase 4: TM-based AD solver (future)

Replace MC simulation inside the AD convergence loop with TM
propagation.  This would make the full reproduction pipeline
TM-only (currently AD requires MC).

Effort: significant (days).  Separate project.

---

## Priority Order

1. **1a** (mCount default) — 5 minutes
2. **1b** (base_aPol audit) — 30 minutes
3. **1d** (remove jitter) — 5 minutes
4. **1c** (per-cohort ergodic) — 1 hour
5. **Phase 2** (Check gap) — half day
6. **Phase 3** (per-cohort propagation) — half day
7. **Phase 4** (TM-based AD) — future project
