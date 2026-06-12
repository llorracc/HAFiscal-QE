# Plan 2 (v2): Baseline-work refactor (optional caching within a phase)

**Status:** Draft (revision of `asymptotic-equality-driver-baseline-cache-refactor.md`)
**Scope:** Item **D** only — reduce redundant **baseline** setup and simulation **within** a phase/seed when the economic model already requires **separate** solves for **base** vs **policy**.

**Prerequisite:** Read `plans/20260408-1028h_asymptotic-equality-driver-ladder-presets_v2.md` (Plan 1 v2). Plan 2 does **not** replace Plan 1; it optimizes **internal** structure after behavior and defaults are clear.

---

## Problem statement

In `_run_norec_experiment` and analogous paths, each MC seed typically:

1. `setup_economy` → initial `solve`
2. TM init + `mc_burnin`, baseline `run_experiment` (`base`)
3. `switch_shock_type(policy)`, `solve`, `run_experiment` (policy)

Steps (2) and (3) are **economically required** for a correct multiplier (different decision rules under `base` vs `TaxCut` / `UI` / `Check` — see `AggFiscalModel.switch_shock_type`).

**Potential waste** to profile and then remove:

- Duplicate **baseline** work if the same baseline path is recomputed unnecessarily inside the same seed.
- Redundant **deepcopy** / **solve** ordering if baseline results could be reused before switching shock type (without skipping the **policy** solve).
- The recently-added **TM-P + TM-Q** ergodic computations in Phase 1 share most of their work (transition matrix construction, ergodic solve) and differ only in shock reweighting; they are an obvious cache target.

Plan 2 is **not** "merge baseline and policy into one solve" — that would be incorrect unless the model is redesigned so policy is a pure within-period shock on a **single** value function.

---

## Goals

1. **Profile** the hot path: `test_asymptotic_equality_revised.py` → `_run_norec_experiment`, `_run_recession_experiment`, and `_run_baseline_phase`, per seed.
2. **Refactor** only where profiling shows clear duplication **within** a single seed's baseline branch.
3. **Preserve** numerical outputs to a *defensible tolerance* (see Acceptance below — no longer "bit-identical").

---

## Tasks

1. **Profile** under the *current* default sweeps (multi-grid TM, multi-tier MC), **before** Plan 1 v2 lands, so duplication inside multi-grid loops is visible. Add lightweight timing logs (behind `--verbose` or env var) around: `setup_economy`, `solve`, `compute_baseline_tm_data`, `mc_burnin`, `run_experiment` (base), `switch_shock_type` + `solve`, `run_experiment` (policy).

2. For each phase type, draw a **call graph** of duplicate `setup_economy` / baseline `run_experiment` within the same seed loop, and of duplicate TM ergodic computations across the `neutral_measure=True` and `neutral_measure=False` paths.

3. If safe, extract a helper e.g. `run_mc_baseline_then_policy(economy, shock_type_policy, ...)` that:
   - calls `economy.save_state()` **before** any baseline run (hard requirement, see Risks);
   - runs baseline path once, stores baseline aggregates;
   - calls `economy.restore_state()` (or operates on a `deepcopy`) before `switch_shock_type`;
   - applies `switch_shock_type` + `solve` + policy `run_experiment` once;
   - returns objects needed for NPV / multiplier tables.
   The helper docstring must contain the inline `[math-deriv]` citations referenced by §13.5 of TMMC and the Comparison Registry in `test_asymptotic_equality_revised.py`. Do not lose them in the extraction.

4. Apply the same structural clarity to the **TM** side **only** if duplication exists. The TM-P + TM-Q baseline pair in `_run_baseline_phase` is intentional (each measure answers a different question — see Plan 1 v2 §B and registry items 2 and 4 in the driver docstring). If they are merged into a single shared computation, the merge must preserve both sets of moments and the `neutral_measure=True` / `neutral_measure=False` outputs must be available independently to callers.

5. **Regression check** (revised — see Acceptance below).

---

## Non-goals

- Changing default `--mc`/`--tm` or adding `--ladder` (Plan 1 v2).
- Skipping the **policy** `solve()` when `switch_shock_type` changes the Bellman problem.
- Caching solutions across **phases** or **seeds** (different RNG / state) unless explicitly designed and tested.
- **Caching `setup_economy` across MC seeds.** Per-seed `setup_economy` is intentional: it re-seeds the agent RNG so each seed produces an independent MC sample. HARK agents store RNG state in multiple places; a naive "setup once, re-seed N times" refactor will quietly produce correlated seeds that look like independent ones, inflating apparent seed-to-seed agreement. Do not attempt this.
- Eliminating `[math-deriv]` print sites or letting the new `MATH_REFS` lookups go stale during helper extraction.

---

## Acceptance

### Numerical regression criterion (revised — direction matters, not bit-identity)

**Old (v1):** "No change in default numerical results beyond floating-point noise for the same CLI and seed."

**New (v2):** Direction-of-the-fix is right; bit-identity is unnecessarily strict because legitimate refactors (e.g., parallel sums, reordered associative reductions) can shift the last few ULPs without indicating any bug.

The revised regression check has **two tolerance bands**:

1. **Tight band — full per-period series, not just NPV scalar.** For
   each phase exercised by the regression test, capture the
   per-period `AggCons` and `AggIncome` series (and per-type variants
   where the runner produces them) before and after the refactor at
   a fixed seed, fixed `Parametrization`, fixed `--ladder` cell.
   Assert that **every per-period element** agrees to within
   `rtol = 1e-9` and `atol = 1e-9` (i.e. essentially numerical noise
   from associative re-ordering, but tighter than any
   floating-point-relevant statistic). This catches RNG-ordering
   shifts because such shifts produce differences orders of
   magnitude larger than `1e-9` even at small N.

2. **Loose band — multipliers and aggregates.** NPV multipliers,
   per-cell summary numbers, per-type moment tables: agree to
   `rtol = 1e-12, atol = 1e-12` (i.e. they should match exactly to
   double precision because they are derived from the per-period
   series via deterministic linear operations).

If the per-period series passes the tight band but the multipliers
fail the loose band, the bug is in the post-processing pipeline, not
the refactor — investigate and fix before merging.

If the per-period series **fails** the tight band, the most likely
cause is RNG ordering. Do **not** widen the band — diagnose. Common
causes:
- A `deepcopy` was added or removed in a place that consumes RNG.
- A `save_state` / `restore_state` pair is missing.
- A `setup_economy` call was moved across a seed-loop iteration.

### Coverage criterion

The regression check must run on at least these combinations:

- One **no-recession** policy phase (e.g. `norec-taxcut`).
- One **recession** policy phase (e.g. `recession-policies` for `recessionCheck`). The recession path is the most fragile because `act_T` is restored after `switch_to_counterfactual_mode` and that ordering must be preserved.
- A `--ladder smoke` cell (paired-cell wiring; quick).
- A `--ladder quick` cell at `MC-med + TM-100` (large enough that
  RNG-ordering shifts stand out clearly above sampling noise).

For each combination, run the per-period series check and the
multiplier check. Document the seed used.

### Wall-clock criterion

- Wall-clock time reduction documented in commit message (e.g. "~X% on `norec-taxcut --ladder smoke`").
- Code paths remain easier to follow than before (single obvious baseline → policy sequence per seed; helper docstring documents the `save_state`/`restore_state` contract).

---

## Risks

- **Mutable economy state shared between baseline and policy.** Refactors that rely on the caller having already called `save_state()` (or that mutate the economy in place between baseline and policy) can introduce subtle bugs. **Hard requirement:** the helper signature must call `save_state()` itself before the baseline run and `restore_state()` (or deepcopy) before `switch_shock_type` — do not delegate this to the caller.

- **RNG-ordering shifts from helper extraction.** The most likely failure mode of this refactor. The tight per-period band in the Acceptance section is designed specifically to catch this; do not loosen it without diagnosis.

- **Loss of `[math-deriv]` citations.** Helpers extracted from phase runners may absorb the `print(f"  [math-deriv] ...")` calls, hiding them from the caller's output. The helper docstring must explicitly carry the `MATH_REFS` keys it consumes, and the print sites must remain at the same logical level (one print per comparison table, not buried inside a helper).

- **Profiling under post-Plan-1 defaults.** If Plan 1 v2 lands first and the per-phase defaults are simplified (paired-cell), profiling will not exercise the multi-grid TM loop and any duplication there will go unnoticed. Profile **first**, against the current defaults, then refactor; the dependency on Plan 1 is *reversed* from the v1 plan.

---

## Dependencies

- **None.** Plan 1 v2 should land first only for user-visible behavior; Plan 2's profiling step must run against the *current* multi-grid defaults so cross-grid duplication is visible. Sequence:
  1. Profile under current defaults (Plan 2 Task 1).
  2. Land Plan 1 v2 (paired-cell `--ladder`).
  3. Land Plan 2 refactor on top, with regression checks running against both `--ladder smoke` and explicit multi-grid invocations.

---

## Why this version exists

This document supersedes `asymptotic-equality-driver-baseline-cache-refactor.md`. Changes:

1. **Acceptance criterion is no longer "bit-identical".** v1 demanded "no change beyond floating-point noise", which is effectively bit-identity on the full per-period series. That is too strict — legitimate refactors (parallel sums, associative reordering, BLAS routine swaps) can shift the last few ULPs without indicating a bug. v2 uses a tight `rtol/atol = 1e-9` band on the per-period series (still tight enough to catch RNG-ordering shifts, which produce differences orders of magnitude larger) and a separate `rtol/atol = 1e-12` band on derived multipliers.
2. **Regression coverage is expanded.** v1 said "key scalars (e.g. TM ref multiplier, MC-tiny multiplier)". TM ref multiplier doesn't depend on the MC refactor at all, and MC-tiny is too noisy to expose RNG shifts. v2 mandates: full per-period series (not just NPV scalar), per-type, at least one recession phase, at a sample size large enough to make shifts visible (`--ladder quick` cell at `MC-med + TM-100`).
3. **`save_state` / `restore_state` is a hard helper requirement**, not a preference.
4. **`setup_economy`-across-seeds caching is in Non-goals**, to forestall the most likely RNG-correlation bug.
5. **Plan 1 dependency is reversed.** Profile **before** Plan 1 lands, so cross-grid duplication is visible.
6. **`[math-deriv]` citations are explicitly preserved** across helper extraction.
7. **TM-P + TM-Q intentional duplication** (registry items 2 and 4 in the driver docstring) is documented as an exception that should not be collapsed without preserving both outputs.
