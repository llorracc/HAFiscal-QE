# Plan: Dual-Measure MC Integration into Reduced Reproduction Path

**Date**: 2026-04-02  
**Predecessor**: `plans/20260403-1253h_harmenberg-reduced-reproduce-acceleration-plan.md` (Phases 0–4)  
**Tools built**: `DualAggFiscalType` (`AggFiscalModel.py`), `DualMeasureMixin` (`HARK/dual_measure.py`), `aggregate_Q`, `compute_mean_pLvl`, `compute_pLvl_factor`  
**Validated by**: `test_dual_measure_phases.py` (27 tests, 8 phases), `test_dual_measure_hafiscal.py`, `Harmenberg-Four-Way-Comparison.ipynb` (Method E), `verify_four_methods_agreement.py` / `test_verify_four_methods_agreement.py` (baseline four-way TM vs MC P/Q), `history/20260404-hafiscal-four-way-verification-and-tm-init-report.md` (outcomes + lessons)

---

## Motivation

The original plan (Phases 0–4) accelerated the reduced `reproduce.sh --comp min` path by classifying outputs as Type A/B/C and applying Harmenberg neutral-measure TM for p-linear aggregates. That plan treated MC and TM as independent methods.

We now have **`DualAggFiscalType`** — a single simulation pass that produces both standard P-MC and Harmenberg Q-MC results from shared random draws. This changes the landscape:

- **Cross-validation**: P-MC and Q-MC from the same run give two independent estimates of every Type A/B aggregate, enabling automatic consistency checks.
- **Variance reduction**: Q-MC reduces aggregate consumption variance by ~8× (validated in notebook), allowing fewer agents or tighter confidence intervals.
- **TM ground truth**: Q-MC with large N provides a low-variance reference for TM grid convergence studies, replacing the need for separate large-MC reference runs.
- **Type C coverage**: The P-track retains full `pLvl` information, so non-p-linear statistics (welfare, Gini) come from the same simulation run — no separate MC pass needed.
- **Stimulus check**: The dual framework enables using P-track `pLvl` for means-test phase-out while Q-track provides the low-variance consumption aggregate.

---

## Phase 0 — Smoke Test: Wire `DualAggFiscalType` into `Simulate.py`

**Goal**: Replace `AggFiscalType` with `DualAggFiscalType` in the MC path when a new flag `sim_method='dual_MC'` (or `'both_dual'`) is set, verify the pipeline doesn't crash, and confirm P-track bit-matches standard MC.

**Tasks**:

0a. Add `sim_method='dual_MC'` option to `Simulate.py` alongside existing `'MC'`, `'TM'`, `'both'`.  When active:
  - Import `DualAggFiscalType` instead of `AggFiscalType` for agent construction
  - Call `agent.setup_Q_measure()` after `IncShkDstn` is built
  - Leave all downstream aggregation (experiments, NPV, etc.) using P-track only — Q-track is computed but ignored

0b. Run a single baseline experiment (no recession, no policy) with `dual_MC` at reduced agent count (N=100 per type).  Verify:
  - No crashes
  - `agent.history_Q['cNrm']` is populated (shape, no NaN after burn-in)
  - P-track `AggCons` exactly matches a standard MC run with the same seed

0c. Run one policy experiment (e.g. UI extension, no recession) with `dual_MC`.  Verify:
  - `run_experiments_no_recessions` completes without error
  - Pickled results are identical to standard MC (P-track)

**Acceptance**: Green `pytest` for smoke tests; P-track results byte-match standard MC.

**Estimated time**: 2–3 hours (mostly plumbing in `Simulate.py`)

---

## Phase 1 — P/Q Consistency for Type A/B Aggregates (No Recession)

**Goal**: For every no-recession policy experiment (UI extension, tax cut, stimulus check), confirm P-MC and Q-MC aggregates agree within statistical tolerance.

**Tasks**:

1a. After each no-recession experiment, compute both:
  - `C_P(t) = sum_i [cLvl_splurge_P_i(t)]` (standard P-aggregate)
  - `C_Q(t) = E_P[p] * sum_i [cLvl_splurge_Q_i(t) / pLvl_Q_i(t)]` (Harmenberg identity)

1b. For Type A/B experiments (UI extension, tax cut): verify `C_P` and `C_Q` agree within 2 cross-sectional SE at ≥85% of time periods (same criterion as `test_dual_measure_phases.py` Phase 3).

1c. For stimulus check: document the expected P/Q discrepancy due to non-p-linearity of the phase-out function. Compute the bias ratio `(NPV_Q - NPV_P) / NPV_P` and verify it is small for the p-linear component of the check.

1d. Compute and report variance reduction ratio `Var(C_P) / Var(C_Q)` for each experiment. Expected: 5–15× for UI/tax cut, lower for stimulus check.

1e. Write these checks as a `pytest` module that runs alongside the existing `test_tm_baseline.py` pattern.

**Acceptance**: Automated P/Q consistency and variance reduction tests pass for all no-recession experiments.

**Estimated time**: 3–4 hours

---

## Phase 2 — Recession Experiments with Dual MC

**Goal**: Extend dual MC to recession scenarios (Markov state transitions, time-varying `PermGroFac`, `AggDemandFac`), and validate P/Q consistency under macro shocks.

**Tasks**:

2a. Verify `DualAggFiscalType._transition_Q()` correctly handles recession-mode `AggDemandFac != 1.0` and `MrkvNowPcvd` switching.  The Q-track must use the same `AggDemandFac` and `Mrkv` transitions as the P-track.

2b. Run `run_experiments_all_recessions` with `dual_MC` for each shock type (recession, recession+UI, recession+tax cut, recession+check).  Verify no crashes.

2c. For each recession experiment, compute and log:
  - P/Q consistency of `AggCons` differenced paths (experiment minus baseline)
  - NPV of differenced aggregates under both measures
  - Variance reduction ratio on the **differenced** series (this is the economically relevant quantity)

2d. Verify `pLvl_factor` (from `compute_pLvl_factor`) tracks the empirical `E_P[pLvl(t)] / E_P[pLvl_ss]` under the recession unemployment path to within 5%.

2e. Add recession experiments to the Phase 1 pytest module.

**Acceptance**: All recession dual-MC experiments complete; P/Q NPV differentials within tolerance for Type A/B.

**Estimated time**: 4–5 hours

---

## Phase 3 — TM Cross-Validation Using Q-MC as Reference

**Goal**: Use the low-variance Q-MC aggregates as ground truth to validate TM results, replacing the need for very-large-N standard MC reference runs.

**Tasks**:

3a. For baseline and each policy experiment, compute the TM-based aggregate (`AggCons_TM`) and the Q-MC aggregate (`AggCons_Q`).  Report `(TM - Q) / Q` as percentage error at each time period.

3b. Run TM at multiple grid sizes (`tm_mCount` in {30, 50, 75, 100}) and measure TM–vs–Q convergence.  Plot error as a function of `tm_mCount`.  Identify the coarsest grid where TM matches Q-MC within 0.5% for all Type A/B quantities.

3c. Compare TM Harmenberg 1D (`tm_neutral_measure=True`) vs TM Standard 2D at matched total state counts.  Q-MC provides the referee.

3d. For the stimulus check specifically: compare TM p-bucketing aggregates against P-MC (which correctly handles the phase-out), and document TM bucket count requirements.

3e. Summarize findings in a table: for each output × grid setting, report TM error vs Q-MC, TM error vs P-MC, and whether the TM result falls within the Q-MC 95% confidence band.

**Acceptance**: Documented grid convergence table with Q-MC reference; recommended `tm_mCount` for reduced path identified.

**Estimated time**: 4–6 hours (mostly running sweeps and analyzing results)

---

## Phase 4 — AD Loop with Dual MC

**Goal**: Test dual MC within the aggregate demand (AD) iteration loop, where the economy's aggregate consumption feeds back into individual budget constraints.

**Tasks**:

4a. Wire dual MC into the AD iteration in `Simulate.py`:
  - The AD loop updates `AggDemandFac` based on aggregate consumption
  - Both P-track and Q-track should receive the updated `AggDemandFac` each iteration
  - Decision: use P-aggregate or Q-aggregate for the AD feedback? Default to P (conservative — no Harmenberg assumptions in the equilibrium concept), but compute Q-aggregate as a diagnostic.

4b. Run AD iterations for one shock type (e.g. tax cut recession) with `dual_MC`.  Compare:
  - Number of iterations to convergence
  - Converged `AggCons` under P-aggregate feedback vs Q-aggregate feedback
  - Wall-clock time vs TM AD

4c. Investigate whether Q-aggregate feedback reduces AD iteration noise (since Q-aggregate has lower variance, the AD target may converge faster).  If so, quantify the speedup.

4d. Add AD consistency checks to the test suite.

**Acceptance**: AD loop completes with dual MC; converged aggregates match TM AD within documented tolerance.

**Estimated time**: 3–4 hours

---

## Phase 5 — Integration into `reproduce_min.py` and Documentation

**Goal**: Make dual MC a usable option in the reduced reproduction pipeline with proper flags, tests, and documentation.

**Tasks**:

5a. Add `sim_method='dual_MC'` to `AggFiscalMAIN_reduced.py` as an opt-in flag.  Provide CLI argument `--dual-mc` to enable it.

5b. When `dual_MC` is active, emit additional diagnostic output alongside standard results:
  - Variance reduction report (one line per experiment)
  - P/Q consistency summary
  - Comparison against TM (if TM also ran via `sim_method='both_dual'`)

5c. Ensure `Output_Results.py` can consume dual-MC pickled results (P-track format is identical to standard MC; Q-track stored separately).

5d. Update `reproduce_min.py` / `reproduce.sh` to optionally invoke `--dual-mc` mode.  Default remains TM-only for backward compatibility.

5e. Write or update documentation:
  - `history/` note: "Dual-Measure MC in HAFiscal" summarizing implementation, math references, and validation results
  - Add comments in `Simulate.py` pointing to the Harmenberg identity, notebook §8j, and type-map
  - Update `CLAUDE.md` with the new `sim_method` option

5f. Final regression test: run `reproduce_min.py` in TM-only mode and `dual_MC` mode, compare all published outputs.

**Acceptance**: `./reproduce.sh --comp min` works unchanged; `--dual-mc` flag produces consistent results with P/Q diagnostics; documentation in place.

**Estimated time**: 3–4 hours

---

## Summary

| Phase | Goal | Key deliverable | Est. hours |
|-------|------|-----------------|------------|
| **0** | Smoke test: wire `DualAggFiscalType` into `Simulate.py` | P-track byte-matches standard MC | 2–3 |
| **1** | P/Q consistency for no-recession experiments | Automated consistency + variance reduction tests | 3–4 |
| **2** | Recession experiments with dual MC | Recession P/Q validation, `pLvl_factor` check | 4–5 |
| **3** | TM cross-validation using Q-MC reference | Grid convergence table, recommended `tm_mCount` | 4–6 |
| **4** | AD loop with dual MC | AD convergence comparison, Q-feedback experiment | 3–4 |
| **5** | `reproduce_min.py` integration + docs | CLI flag, diagnostics, documentation | 3–4 |
| **Total** | | | **19–26** |

---

## Dependencies and Risks

| Risk | Mitigation |
|------|------------|
| `DualAggFiscalType` + `switch_to_counterfactual_mode` interaction | Phase 0c specifically tests this; the counterfactual mode deletes `agent.solution` and re-solves — must verify `setup_Q_measure()` is called again after re-solve |
| Q-aggregate feedback in AD loop changes equilibrium | Phase 4 defaults to P-feedback; Q-feedback is experimental/diagnostic only |
| Stimulus check P/Q bias confuses downstream tables | Phase 1c documents the known bias; Phase 3d validates TM buckets as the correct approach for checks |
| Memory overhead from Q-state arrays at full agent count | Measured in notebook: ~6 MB per 200K agents — negligible |
| RNG synchronization across HARK versions | Existing `IncShkDstn[0].seed = 763607780` pattern in `Simulate.py` must be preserved; `setup_Q_measure()` does not affect RNG state |

---

## References

- `Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb` — Method E validation
- `Code/HA-Models/FromPandemicCode/test_dual_measure_phases.py` — 27 phased tests
- `Code/HA-Models/FromPandemicCode/test_dual_measure_hafiscal.py` — integration tests
- `HARK/dual_measure.py` — `DualMeasureMixin`, `aggregate_Q`, `compute_mean_pLvl`, `compute_pLvl_factor`
- `history/20260402-reduced-run-harmenberg-output-type-map.md` — Type A/B/C classification
- `plans/20260403-1253h_harmenberg-reduced-reproduce-acceleration-plan.md` — predecessor plan
- `plans/20260403-1253h_hark-dual-measure-mc-plan.md` — HARK implementation plan (completed)
