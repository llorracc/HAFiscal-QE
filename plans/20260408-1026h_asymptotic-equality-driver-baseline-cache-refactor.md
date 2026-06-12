# Plan 2: Baseline-work refactor (optional caching within a phase)

**Status:** Draft (implementation not started)  
**Scope:** Item **D** only — reduce redundant **baseline** setup and simulation **within** a phase/seed when the economic model already requires **separate** solves for **base** vs **policy**.

**Prerequisite:** Read `plans/20260408-1026h_asymptotic-equality-driver-ladder-presets.md` (Plan 1). Plan 2 does **not** replace Plan 1; it optimizes **internal** structure after behavior and defaults are clear.

---

## Problem statement

In `_run_norec_experiment` and analogous paths, each MC seed typically:

1. `setup_economy` → initial `solve`
2. TM init + `mc_burnin`, baseline `run_experiment` (`base`)
3. `switch_shock_type(policy)`, `solve`, `run_experiment` (policy)

Steps (2) and (3) are **economically required** for a correct multiplier (different decision rules under `base` vs `TaxCut` / `UI` / `Check` — see `AggFiscalModel.switch_shock_type`).

**Potential waste** to profile and then remove:

- Duplicate **baseline** work if the same baseline path is recomputed unnecessarily inside the same seed (e.g. multiple `setup_economy` calls where one would suffice).
- Redundant **deepcopy** / **solve** ordering if baseline results could be reused before switching shock type (without skipping the **policy** solve).

Plan 2 is **not** “merge baseline and policy into one solve” — that would be incorrect unless the model is redesigned so policy is a pure within-period shock on a **single** value function.

---

## Goals

1. **Profile** the hot path: `test_asymptotic_equality_revised.py` → `_run_norec_experiment`, `_run_recession_experiment`, and phase-1 baseline, per seed.
2. **Refactor** only where profiling shows clear duplication **within** a single seed’s baseline branch (e.g. ensure exactly one `run_experiment` for baseline before `store_baseline` and policy branch).
3. **Preserve** numerical outputs (or document acceptable floating-point drift if deterministic RNG ordering is preserved).

---

## Tasks

1. Add lightweight timing logs (behind `--verbose` or env var) around: `setup_economy`, `solve`, `compute_baseline_tm_data`, `mc_burnin`, `run_experiment` (base), `switch_shock_type` + `solve`, `run_experiment` (policy).

2. For each phase type (no-recession policy, recession policy, phase-1 baseline), draw a **call graph** of duplicate `setup_economy` / baseline `run_experiment` within the same seed loop.

3. If safe, extract a helper e.g. `run_mc_baseline_then_policy(economy, shock_type_policy, ...)` that:
   - runs baseline path once;
   - stores baseline aggregates;
   - applies `switch_shock_type` + `solve` + policy `run_experiment` once;
   - returns objects needed for NPV / multiplier tables.

4. Apply the same structural clarity to the **TM** side only if duplication exists (e.g. repeated `compute_baseline_tm_data` at the same `mCount` in one phase without need).

5. Add a **regression check**: compare key scalars (e.g. TM ref multiplier, MC-tiny multiplier) before/after refactor on a fixed seed.

---

## Non-goals

- Changing default `--mc`/`--tm` or adding `--ladder` (Plan 1).
- Skipping the **policy** `solve()` when `switch_shock_type` changes the Bellman problem.
- Caching solutions across **phases** or **seeds** (different RNG / state) unless explicitly designed and tested.

---

## Acceptance criteria

- No change in **default numerical results** beyond floating-point noise for the same CLI and seed.
- Wall-clock time reduction documented in commit message (e.g. “~X% on norec-taxcut MC-tiny”).
- Code paths remain easier to follow than before (single obvious baseline→policy sequence per seed).

---

## Risks

- Refactors that share mutable economy state between baseline and policy can introduce subtle bugs; prefer **immutable snapshots** or explicit `save_state`/`restore_state` patterns already used elsewhere in HAFiscal.

---

## Dependencies

- Plan 1 may land first so default runs are cheap and profiling uses representative invocations (`--ladder tiny`, etc.).
