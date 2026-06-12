<!-- Status: DONE (superseded by implementation) -->
# Plan: Scale TM from Diagnostic to Production

**Date:** March 29, 2026  
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`  
**Goal:** Replace MC simulation with TM for all policy experiments in the paper.

---

## Current State

All 16 TM bugs (BUG-001–BUG-016) are fixed. Validation on a **single
highschool type, `Reduced_Run`, 200K MC agents × 3 seeds** shows all
7 experiment types within ~1–2% NPV relative error.

The paper's Step 5 (`AggFiscalMAIN.py`) needs TM to produce identical output
dictionaries for `Output_Results.py` and `Welfare.py`. The relevant outputs
are NPV multipliers (Multiplier.tex), welfare measures (welfare6.tex), IRF
figures, and cumulative multiplier plots.

---

## Dimensions to Scale

| Dimension | Current (diagnostic) | Target (production) |
|-----------|---------------------|---------------------|
| Agent types | 1 (highschool, point β) | 21 (3 edu × 7 β) |
| Parametrization | `Reduced_Run` | `Baseline` |
| act_T / NPV horizon | 100 | 400 |
| T_age (lifecycle) | 100 | 200 |
| num_experiment_periods | 10 | 20 |
| max_recession_duration | 11 | 21 |
| Recession averaging | single duration | weighted over all durations |
| AD feedback | none | full AD + 1st-round AD |
| DiscFacCount | 1 | 7 |

---

## Risk Assessment

Each dimension introduces potential failure modes:

| Risk | Dimension | Why it could fail | Detection |
|------|-----------|-------------------|-----------|
| R1: Multi-type aggregation | types 1→3 | Bug in per-type weighting or E_pLvl scaling | NPV error > 3% |
| R2: β spread / grid coverage | DiscFac 1→7 | Very patient or impatient agents near grid edges | Per-type NPV breakdown shows outlier |
| R3: Longer horizon accumulation | act_T 100→400 | pLvl_factor drift over 400 periods | Late-period per-period error growth |
| R4: Recession averaging | single→weighted | Probability weighting or averaging bug | Averaged multiplier error > 3% |
| R5: AD iteration convergence | no AD→AD | TM AD loop converges to different point than MC | AD multiplier ratio diverges |
| R6: Pipeline integration | diagnostic→Simulate.py | Output dict keys don't match expected schema | Output_Results.py crashes or produces NaN |

---

## Phased Plan

### Phase 1 — Three Education Types (Reduced_Run, single recession duration)

**Tests risks:** R1 (multi-type aggregation)

**Setup:**
- 3 types: dropout, highschool, college — each with point β (DiscFacCount=1)
- `Reduced_Run` parametrization (act_T=100, T_age=100)
- Single fixed recession duration (same as current diag scripts)
- MC: 200K agents total (split by `data_EducShares`), 3 seeds
- TM: mCount=100

**Experiments:** All 7 (recession, recessionUI, recessionTaxCut, recessionCheck,
Check, TaxCut, UI)

**What to check:**
- Aggregate NPV treatment effects: expect < 3% relative error
- Per-type breakdown: each education type should individually match within ~3%
- E_pLvl per type: verify pLvl_factor works with different PermGroFac values

**Estimated runtime:** 30–60 min  
**Go/no-go:** If any experiment shows > 5% NPV error, stop and diagnose.

---

### Phase 2 — Full 21 Types (Reduced_Run, single recession duration)

**Tests risks:** R2 (β spread / grid coverage)

**Setup:**
- 21 types: 3 edu × 7 β (full Simulate.py type construction)
- `Reduced_Run` parametrization
- MC: 500K agents total (smallest type ≈ 500K × 0.093 / 7 ≈ 6,600), 3 seeds
- TM: mCount=150 (finer grid for wider wealth distribution)

**Experiments:** recession, recessionCheck, recessionTaxCut, recessionUI
(skip no-recession variants — they have no recession-specific machinery, so
if they worked in Phase 1 they will work here)

**What to check:**
- Aggregate NPV treatment effects: expect < 3% relative error
- Per-type breakdown: look for outliers among the 21 types (especially
  extreme-β agents where the wealth distribution may pile up near grid edges)
- Compare mCount=150 vs mCount=200 for one experiment to verify grid adequacy

**Estimated runtime:** 1–3 hours  
**Go/no-go:** If grid resolution is the issue, increase mCount. If a
specific type dominates the error, investigate that type's wealth distribution.

---

### Phase 3 — Recession Duration Averaging (Reduced_Run, 3 types)

**Tests risks:** R4 (recession averaging)

**Setup:**
- 3 types, `Reduced_Run` (DiscFacCount=1)
- Run full `run_experiments_all_recessions_tm` and MC equivalent
- max_recession_duration=11, weighted by `recession_prob_array`
- MC: 200K × 3 seeds × 11 durations

**Experiments:** recession, recessionCheck (the two that most stress the
recession duration machinery)

**What to check:**
- Duration-averaged NPV multiplier: expect < 3% relative error
- Per-duration breakdown: verify each duration individually matches, not just
  the average (the average could hide compensating errors)
- Multiplier table format: verify TM output dict has all keys needed by
  `Output_Results.py`

**Estimated runtime:** 1–2 hours  
**Go/no-go:** If averaging is off, compare individual durations to find which
duration introduces the discrepancy.

**Note:** Phases 2 and 3 test independent dimensions and can run in parallel.

---

### Phase 4 — Baseline Parametrization (3 types, single recession duration)

**Tests risks:** R3 (longer horizon accumulation)

**Setup:**
- 3 types, `Baseline` parametrization BUT with DiscFacCount=1 (override)
- act_T=400, T_age=200, num_experiment_periods=20
- MC: 200K × 3 seeds (4x longer per seed than Reduced_Run due to act_T)
- TM: mCount=100

**Experiments:** recession, recessionTaxCut (the two that most stress
pLvl_factor and tax cut timing over extended horizons)

**What to check:**
- NPV at t=400: does the error grow compared to t=100?
- Plot per-period TM−MC error: look for systematic drift in later periods
- pLvl_factor at t=400: has it drifted significantly?

**Estimated runtime:** 2–4 hours  
**Go/no-go:** If errors grow linearly with horizon, the pLvl_factor formula
has a systematic bias. If errors plateau, longer horizons are fine.

---

### Phase 5 — Pipeline Integration (Reduced_Run, 3 types, sim_method='both')

**Tests risks:** R6 (pipeline integration)

**Setup:**
- Run `AggFiscalMAIN.py` with `sim_method='both'`, `Reduced_Run`
- This exercises the full Simulate.py pathway end-to-end
- Includes recession averaging, base experiment, all shock types

**What to check:**
- Both `_TM` and `_MC` pickle files are produced for every experiment
- `Output_Results.py` can load both variants and produce tables/figures
- `Welfare.py` can run on both variants
- Compare the Multiplier.tex table entries from TM vs MC

**Experiments:** All (recession, recessionCheck, recessionUI, recessionTaxCut,
Check, UI, TaxCut) × {noAD, AD, 1stRoundAD}

**Estimated runtime:** 1–3 hours (Reduced_Run is fast, even with AD)  
**Go/no-go:** If Output_Results.py or Welfare.py crashes on TM output, fix
the output dict format. This phase is about structural correctness, not
numerical accuracy.

---

### Phase 6 — Full Reduced_Run Integration (21 types, recession averaging, AD)

**Tests risks:** R2 + R4 + R5 combined

**Setup:**
- 21 types, `Reduced_Run`, `sim_method='both'`
- Full recession averaging (max_recession_duration=11)
- AD + 1st-round AD
- MC: standard Reduced_Run AgentCountTotal (100 — but this gives ~5 agents
  per type, which is far too few for validation; override to 500K total)
- TM: mCount=150

**What to check:**
- Multiplier.tex: 10yr NPV multipliers for Check, UI, TaxCut × {noAD, AD, 1stRoundAD}
- welfare6.tex: welfare metrics
- All per-experiment NPV treatment effects
- AD convergence: does TM converge in fewer iterations than MC?

**Estimated runtime:** 4–8 hours  
**Go/no-go:** This is the dress rehearsal. If multipliers match within 5%,
proceed to Baseline. If AD is the problem, investigate `run_ad_tm`
convergence.

---

### Phase 7 — Full Baseline Production Validation (21 types, all features)

**Tests risks:** All combined at production scale

**Setup:**
- 21 types, `Baseline` parametrization, `sim_method='both'`
- act_T=400, max_recession_duration=21
- Full AD iteration (15 iterations, tolerance 1e-4)
- MC: standard Baseline AgentCountTotal=10,000
- TM: mCount=200

**What to check:**
- Multiplier.tex: must match MC to within roundoff of displayed precision
- welfare6.tex: same
- Cumulative multiplier figures: overlay TM vs MC curves
- Per-experiment NPV comparison table

**Estimated runtime:** 12–24 hours (schedule overnight or weekend)  
**Go/no-go:** If MC and TM tables agree at displayed precision, validation
is complete. Any discrepancy should trace back to an already-tested dimension.

---

### Phase 8 — Production Switch and Paper Generation

**Not a validation phase — this is the deployment.**

- Set `sim_method='TM'` as default in `AggFiscalMAIN.py`
- Run full Step 5 with TM only
- Generate paper tables and figures
- Verify LaTeX compilation produces correct paper
- Optionally: keep `sim_method='both'` as a CI/CD check that runs periodically

**Estimated runtime:** TM-only should be 10–100x faster than MC. Step 5
should drop from ~12 hours to minutes-to-an-hour depending on AD iterations.

---

## Efficiency Principles

1. **Fail fast, fix early:** Each phase tests one new dimension. If it fails,
   the root cause is isolated to that dimension. Never combine untested
   dimensions.

2. **Minimum viable MC:** Use just enough MC agents and seeds to distinguish
   TM error from MC noise. Rule of thumb: MC sampling noise at 200K×3 seeds
   is ~0.5%, so anything under ~1.5% TM error is "in the noise."

3. **TM first, MC second:** Within each phase, run TM first (seconds to
   minutes). Sanity-check TM output (no NaN, reasonable magnitudes) before
   committing to the long MC run.

4. **Parallelize independent phases:** Phases 2 and 3 test independent
   dimensions. They can run simultaneously.

5. **Reuse MC baselines:** A Phase 1 MC run produces base + recession MC
   results that can be reused for Phase 3's recession averaging (just re-run
   with more durations).

6. **Skip redundant combinations:** No-recession experiments (Check, TaxCut,
   UI) don't use recession machinery, so if they pass in Phase 1, they don't
   need retesting in later phases.

---

## Decision Points

| After Phase | Decision |
|-------------|----------|
| 1 | Multi-type works → proceed. Error > 5% → diagnose per-type. |
| 2 | β spread OK → proceed. Grid issues → increase mCount or adjust grid bounds. |
| 3 | Averaging works → proceed. Bias → check probability weighting. |
| 4 | Horizon OK → proceed. Drift → revisit pLvl_factor formula. |
| 5 | Pipeline works → proceed. Format issues → fix output dict. |
| 6 | Dress rehearsal passes → proceed to overnight run. |
| 7 | Production validated → switch to TM. |

---

## Estimated Total Timeline

| Phase | Duration | Cumulative | Can parallelize with |
|-------|----------|------------|---------------------|
| 1 | 30–60 min | 1 hr | — |
| 2 | 1–3 hr | 4 hr | Phase 3 |
| 3 | 1–2 hr | 4 hr | Phase 2 |
| 4 | 2–4 hr | 8 hr | — |
| 5 | 1–3 hr | 11 hr | — |
| 6 | 4–8 hr | 19 hr | — |
| 7 | 12–24 hr | 43 hr | — |

**Best case:** ~2–3 days with parallelization, assuming no bugs found.  
**If bugs are found:** Add 2–4 hours per bug for diagnosis and fix, then
re-run that phase.

The critical path is Phases 4→5→6→7 (sequential, ~20–40 hours). Phases 1–3
are the quick screening tests that catch most problems early.
