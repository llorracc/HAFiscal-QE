# Answers to Composer Questions on Execution Plan

**Date:** 2026-03-23
**Answering:** Claude Opus 4.6
**Questions from:** `debug/20260323-1508h_full_execution_plan_for_AI_questions-from-composer.md`

---

## Phase 1 vs observed validation

**Q:** Which scalar must be <4%? The full-path max-rel can be huge
(60%) because later periods have near-zero treatment effects (the
denominator goes to zero).

**A:** The pass criterion is **AggCons[0] and AggIncome[0] period-0
treatment effect relative error**, not full-path max-rel.
Specifically:

```
rel_err = |TM_TE[0] - MC_TE[0]| / |MC_TE[0]|
```

where `TE[0] = experiment_AggCons[0] - baseline_AggCons[0]`.

The full-path max-rel is dominated by periods where the TE crosses
zero and is not a useful metric.  Period-0 is where the treatment
effect is largest and most meaningful.

Phase 1 passes: UI AggCons[0] rel err = 0.75%, AggIncome[0] = 1.16%
(from `validate_tm_ui.py --agents 200000 --seeds 3 --mcount 100`).

---

## Phase 2 (Check)

**Q:** Units of "1.28 vs 0.91"?

**A:** These are **NPV of the per-capita consumption treatment
effect** (in levels, not multipliers):

```python
npv_c = calculate_NPV(
    check_AggCons - base_AggCons, act_T, Rfree
)[-1] / N_agents
```

The 29% is computed as `(TM - MC) / MC = (1.28 - 0.91) / 0.91`.

**Q:** Which runs establish initialization independence?

**A:** `test_tm_init_mc.py` runs both TM-initialized MC and standard
burn-in MC for the Check experiment and reports both.  The key output:
```
TM-init MC: NPV_C_TE = 0.910
Burn-in MC: NPV_C_TE = 0.912
```
These match to <0.3%, confirming the gap is TM-vs-MC methodology,
not initialization.

**Q:** Success metric for Phase 2?

**A:** **Period-0 AggCons treatment effect relative error < 5%**,
measured from `validate_tm_check.py --agents 200000 --seeds 3`.
Currently this is ~1% for AggCons[0] but ~29% for the NPV.  The
NPV discrepancy may come from later periods accumulating errors.
Fix the period-0 error first; if the NPV remains bad, investigate
per-period TE profiles.

---

## Phase 3 (per-cohort propagation)

**Q:** How to avoid reopening timing issues without the half-step?

**A:** In per-cohort mode, each cohort's distribution IS the correct
beginning-of-period distribution for agents of that age.  There is
no timing mismatch because:

- In single-distribution mode: the ergodic is a mixture of all ages.
  When the experiment changes the transition, agents of different ages
  should get different period-0 distributions, but the single
  distribution can't represent this.  The half-step fixes this by
  consuming→saving→transitioning as one operation.

- In per-cohort mode: each cohort is already at the right point in
  the lifecycle.  Applying the experiment TM (with raw LivPrb) to
  each cohort separately gives the correct period-0 distribution per
  age.  No half-step needed.

**Regression checklist:** After implementing per-cohort propagation,
all of these must pass at their current error levels or better:
- `validate_tm_ui.py --agents 200000 --seeds 3 --mcount 100`:
  AggCons[0] TE < 4%
- `validate_tm_check.py --agents 200000 --seeds 3 --mcount 100`:
  AggIncome[0] TE < 1%
- `validate_tm_taxcut.py --agents 200000 --seeds 3 --mcount 100`:
  AggIncome[0] TE < 1%
- `bash reproduce.sh --comp mini`
- `python AggFiscalMAIN_reduced.py --glp1` produces sensible
  multipliers

**Q:** E[pLvl|age_k] = E[pLvl_init] × G^k ignoring employment?

**A:** This is intentional and correct for E[pLvl].  Since
E[PermShk] = 1 for both employed and unemployed states,
E[pLvl|age k] = E[pLvl_init] × G^k regardless of employment
history.  The employment state affects Var[pLvl|age] (unemployed
periods add no PermShk variance) but not the mean.  For
aggregation, only E[pLvl|age] matters (not the full conditional
distribution).  MC-estimated conditional means would be more
accurate for Var[pLvl] but we showed (test_pLvl_factorization.py)
that the Cov(c, pLvl) effect is only 0.06% of the TE.

**Q:** Should Check be fixed before cohort propagation?

**A:** Yes — **Phase 2 before Phase 3**.  The Check bucket logic
operates on the aggregate ergodic distribution.  Fixing it first
(Phase 2) means the fix works with the current single-distribution
propagation.  Phase 3 (per-cohort) would then need to adapt the
bucket logic to operate per-cohort, but the core fix would already
be validated.  The APIs should be independent: Phase 2 fixes
`_compute_check_buckets` internals, Phase 3 changes how
`propagate_experiment_tm` loops over time.

---

## Phase 4

**Q:** Should Phases 2-3 pre-design hooks for Phase 4?

**A:** No.  Phase 4 (TM-based AD) is out of scope until Phases 2-3
are closed.  The AD solver's interface is: give me a Cratio path,
I simulate and return aggregate consumption.  Swapping MC for TM
inside this interface is a clean substitution that doesn't require
API changes in Phases 2-3.  Don't over-engineer.

---

## Environment / repo hygiene

**Q:** Hard-coded paths?

**A:** The `/Volumes/Sync/GitHub/econ-ark/HARK` path is
machine-specific.  The actual rule is:

1. HARK must be installed from branch
   `main_improve-tm-vs-mc-sim-infra-and-examples` of the
   `econ-ark/HARK` repository
2. It must include the `ConsAggIndMarkovModel` module
3. The `./HARK` symlink in the project root points to the local
   HARK checkout (wherever it lives on your machine)

For CI or another machine, the HARK dependency should be installed
via `uv pip install -e /path/to/your/HARK/checkout` from the
correct branch.

**Q:** `/path/to/HAFiscal-Latest` placeholder?

**A:** Replace with the actual repo root.  The repo root is wherever
you cloned `HAFiscal-Latest`.  The `reproduce.sh` script must be
run from the repo root.  Code scripts run from
`Code/HA-Models/FromPandemicCode/`.

---

## Script inventory

**Q:** When to run `test_first_period_trace.py`?

**A:** It's a **Phase 2 diagnostic**.  It traces exactly what happens
in the first MC period after TM initialization: deaths, newborns,
per-state mNrm/aNrm, and compares with burn-in MC.  Run it when
investigating the Check gap to verify the period-0 distribution is
correct for the Check experiment.  It's not needed for Phase 3.
