# Plan: pre-refactor source-code prep (on `_TM-vs-MC`, before kicking off `feature/cdc-esc-configurable`)

**Date:** 2026-04-26
**Status:** Planned (executing in this session)
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (the CDC anchor branch; prep stays here)
**Predecessor:** `plans/20260425-2137h_cdc-esc-configurable-refactor.md` (the refactor plan this prep enables)

## Goal

Land four small, safe, behavior-preserving changes on `_TM-vs-MC` before the CDC↔ESC configurable refactor begins on `feature/cdc-esc-configurable`. Each change is independently valuable and de-risks the larger refactor.

All four are committed individually so any one can be reverted in isolation if needed.

## Items

### Item 1 — Pre-stage ESC calibration files

Copy ESC's `Result_AllTarget.txt` and per-education `DiscFacEstim_*.txt` from `origin/maintain_bound_pair_fix_splurge` into the working tree under `_ESC`-suffixed names. CDC originals untouched.

```bash
git show origin/maintain_bound_pair_fix_splurge:Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt > Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget_ESC.txt
git show origin/maintain_bound_pair_fix_splurge:Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt > Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt
git show origin/maintain_bound_pair_fix_splurge:Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType0.txt > Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType0_ESC.txt
git show origin/maintain_bound_pair_fix_splurge:Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType1.txt > Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType1_ESC.txt
git show origin/maintain_bound_pair_fix_splurge:Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType2.txt > Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType2_ESC.txt
```

**Behavior change:** none. The files are added but no code reads them yet.

**Effort:** 5 min.

### Item 2 — Extract three inline interpretive blocks into named helpers

Three sites in the codebase will need CDC↔ESC parameterization during the refactor. Currently each is an inline block; extracting into a named module-level function lets the refactor's parameterization be a one-line dispatch instead of an inline rewrite.

**2a — `_option_d_wealth` closure → module-level `_wealth_under_cdc`** (`Estimation_BetaNablaSplurge.py:225-230`):

Currently a `def` nested inside `FagerengObjFunc`. Promote to a top-level function so the refactor can sit a `_wealth_under_esc` next to it and dispatch.

**2b — Lottery-MPC consumption formula → `_lottery_consumption_under_cdc`** (`Estimation_BetaNablaSplurge.py:341-349`):

Currently inline 8-line block. Extract the consumption + asset-update calculation into a function taking `(cFunc, m_base, m_lottery, splurge, xi_hark, TotIncNrm)` and returning `(c_base, a_base, c_actu, a_actu)`. Name: `_lottery_consumption_under_cdc(...)`.

**2c — `get_poststates` body → `_cdc_asset_rule`** (`AggFiscalModel.py:1075-1086`):

Currently inline if/else inside the override. Extract the splurge-in-budget asset-rule computation into a module-level function `_cdc_asset_rule(state_now, shocks, AggDemandFac, splurge) -> (aNrm, aLvl)` so the override is a one-liner and the future ESC version is a sibling helper.

**Behavior change:** none. Pure refactoring extraction; the helpers compute exactly the values the inline code computed; the call sites assign the same values to the same state vars.

**Effort:** 30-60 min, three commits (one per extraction so any single one is reversible).

### Item 3 — Document the K/Y aggregator's two-step CDC pattern

`Estimation_BetaNablaSplurge.py:461` (`CapAggj = np.sum((1-SplurgeEstimate)*EstTypeList[j].state_now["aLvl"])` — wait, that's the ESC pattern; the CDC pattern is `np.sum(EstTypeList[j].state_now["aLvl"])` after the line-225 wealth correction).

Add a 2-line comment near line 461 cross-referencing the wealth-correction at line 225, so a reader of the K/Y aggregator can see immediately how the splurge-in-budget rule reaches that line.

**Behavior change:** none. Comment-only.

**Effort:** 15 min.

### Item 4 — Add a fast pinned-baseline regression test

`Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py`. A small (single-type, short-horizon, ~100 agents) CDC simulation that asserts a handful of specific numerical values:

- A simulated `aLvl` value at a specific (period, agent_index) pin.
- The K/Y under the CDC wealth correction at a specific period.
- The cumulative `cLvl_splurge` over a short horizon.
- The per-agent `aNrm` post-`get_poststates` for the first period.

Uses seeded RNG for determinism. Runs in seconds. Catches behavior changes in the refactor faster than the 1-2-hour `--comp full --tm-only` run.

**Behavior change:** none. New test file; doesn't modify any production code.

**Effort:** 1-2 hours. The bulk of this is establishing what the right pin values should be (run the test once with `pytest --capture=no` to print the values, then hard-code them as assertions).

## Execution order

The smaller items (1, 2, 3) first; the larger item (4) last so that if it overruns, the small items have already landed.

1. Item 1 (ESC calibration files) — single commit.
2. Item 2a (`_wealth_under_cdc` extraction) — single commit.
3. Item 2b (`_lottery_consumption_under_cdc` extraction) — single commit.
4. Item 2c (`_cdc_asset_rule` extraction) — single commit.
5. Item 3 (K/Y aggregator comment) — single commit.
6. Item 4 (regression test) — single commit.

All commits push to `_TM-vs-MC` as they land.

## Validation per item

- **Items 1, 3:** no validation needed (no code logic touched).
- **Items 2a, 2b, 2c:** `pytest Code/HA-Models/FromPandemicCode/test_*.py` should pass without changes (existing tests cover the relevant code paths). If a test breaks, the extraction wasn't behavior-preserving and should be reverted/fixed.
- **Item 4:** the new test should pass under current `_TM-vs-MC` HEAD. If a future commit makes it fail, that future commit accidentally changed CDC behavior.

## Out of scope (deferred to feature branch)

- Adding the `CDCAggFiscalType` and `ESCAggFiscalType` subclass scaffolds — that's Phase A of the refactor, lives on the feature branch.
- Modifying any behavior under any code path.
- Modifying `Parameters.py` to read interpretation as a parameter — Phase D of the refactor.
- Pre-staging ESC `_a` TM kernel functions — Phase C of the refactor.

## Total estimated effort

~3 hours of focused work (most of it Item 4).

## Why on `_TM-vs-MC` rather than `feature/cdc-esc-configurable`

Each of these four items is genuinely valuable on `_TM-vs-MC` independent of the refactor: better tests, cleaner code, better documentation, easier-to-stage ESC. None of them changes behavior. So they belong on the canonical CDC branch, not buried in a feature-branch refactor that may take weeks to land.
