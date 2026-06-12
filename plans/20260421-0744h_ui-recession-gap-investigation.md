# Plan: Overnight investigation of UI-recession W_6 gap vs HAFiscal-QE

**Date:** 2026-04-20 (late evening)
**Status:** Planned; ready to execute autonomously overnight
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_explore-further-speedups`
**Related plans:**
- `plans/20260419-1857h_welfare6-control-variate-implementation.md`
- `plans/20260420_multi-seed-mc-ui-cells.md`
**Related history:** `history/20260419-welfare6-TM-within-state-cross-scenario-bias.md`

---

## 1. What needs resolving

After correcting `diag_welfare6_se.py` and the CV machinery to use the paper's fixed AD=0 `NPV_AddInc` denominator (Welfare.py:277/284 convention), the current branch's welfare6 table (S=4 combined) is:

| Cell | Current (paper formula, S=4) | HAFiscal-QE | Gap |
|---|---:|---:|---:|
| Check Rec=0 | 0.966 | 0.96 | rounding ✓ |
| UI Rec=0 | 0.849 | 0.85 | within SE ✓ |
| TaxCut Rec=0 | 0.990 | 0.99 | ✓ |
| Check Rec=1 | 1.007 | 1.00 | ~0.01 ✓ |
| **UI Rec=1** | **1.455** | **1.82** | **−20% (≈12σ)** |
| TaxCut Rec=1 | 0.997 | 0.98 | ~0.02 ✓ |
| Check Rec=1 AD=1 | 1.341 | 1.35 | ~0.01 ✓ |
| **UI Rec=1 AD=1** | **1.736** | **2.13** | **−18% (≈10σ)** |
| TaxCut Rec=1 AD=1 | 1.133 | 1.11 | ~0.02 ✓ |

Seven of nine cells match the paper to within rounding/SE. Only **UI Rec=1 and UI Rec=1 AD=1** are materially off, by the same ~20%. The AD amplification ratio within the branch matches the paper (+19% vs paper's +17%), so the shortfall is specifically in the UI-recession *level* — something that suppresses W^U on `recessionUI` vs `recession` by ~20%, uniformly across AD settings.

The gap is not statistical: across-seed SE at S=4 is 0.031 for UI Rec=1 and 0.039 for UI Rec=1 AD=1, meaning the gap is 10–12σ.

## 2. Candidate hypotheses

**H1. Splurge-in-budget (Option D) is the culprit.** The re-estimated `ς = 0.2609` (vs 0.2461 in HAFiscal-QE) is specific to the Option D formulation; the budget-accounting change shifts consumption paths during prolonged unemployment even though the aggregate lottery MPC fit is unchanged.

**H2. HARK 0.14.1 → 0.17.0 upgrade.** Changes in `MarkovConsumerType` or the solver introduce differences in the UB2/UB-extended value function, affecting how UI-extended unemployment spells translate into consumption.

**H3. Calibration shift on the dropout group.** `β_dropout` fell from 0.719 → 0.700 and `∇_dropout` rose from 0.318 → 0.340 on this branch. Dropouts have the highest MPC and dominate the UI-welfare signal (high `1/u'(c_base)` weight); modest parameter shifts could drive a 20% W_6 move.

**H4. Mass-of-affected-agents difference.** UI extension under HARK 0.17.0 reaches a different fraction of agents in UB2-expiry than under 0.14.1, so the "treated population" differs.

## 3. Investigation strategy

Three tracks, overlapping in time to use the night efficiently.

### Track A (primary, definitive): splurge-in-budget off

`AggFiscalModel.py:1071` honours `HAFISCAL_SPLURGE_OLD=1` to restore the pre-splurge-in-budget asset-update behavior. This is the cleanest single-variable toggle for H1.

**Action:** rerun the full 12-scenario Baseline pipeline with `HAFISCAL_SPLURGE_OLD=1` set in the environment. Single seed (seed_offset=0) is sufficient to see whether the gap closes substantially.

**Expected result under H1:** splurge_old W_6(UI Rec=1) ≈ 1.82, W_6(UI Rec=1 AD=1) ≈ 2.13 — i.e., the gap closes.
**Expected result under NOT-H1:** splurge_old W_6 values stay near 1.45 / 1.74 — the gap does not close, and H1 is ruled out.

**Wall-clock:** ~1 h (same as previous full regens). Run in background.

**Command:**
```bash
cd /home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
HAFISCAL_SPLURGE_OLD=1 /home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python \
    run_welfare6_parallel.py --baseline --max-parallel 12 --duration-workers 4 \
    --out-dir welfare6_scenario_results_Baseline_splurge_old
```

### Track B (diagnostics on existing data, no new runs)

While Track A's subprocess runs, extract evidence from the already-computed seed0 pickles. Four diagnostics, all quick (~5-15 min each):

**B1. Per-education-group decomposition of W_6(UI Rec=1) and W_6(UI Rec=1 AD=1).**
If the entire shortfall is concentrated in dropouts, that supports H3 (calibration); if spread proportionally across ed groups, it's a structural issue (H1/H2).

**B2. UI-affected-agent mass over time.**
Count agents with `j^recessionUI_{i,t} ≠ j^recession_{i,t}` at each t. Compare:
- What fraction of agents are in UB2-extended (expected micro-states) at each t?
- How does this fraction evolve?
- Does the integrated affected-mass match the fiscal-cost NPV ratio `NPV_AddInc_UI_Rec / (IncUnemp × mean_pLvl × periods)` (a sanity check)?
Low affected-mass → H4.

**B3. Per-agent consumption response of UI-affected agents.**
For agents in the UI-affected set, compute the distribution of `Δc_it = c_recessionUI_{i,t} − c_recession_{i,t}` across (t, i). Compare:
- Mean and distribution of `Δc` per affected agent.
- How much of the consumption difference happens early (t small, asset-accumulation regime) vs late (drawdown regime).
- The full `u(c_pol) − u(c_none)` distribution weighted by `1/u'(c_base)`.
A weak/short-lived consumption response points to H1/H2 (asset dynamics or value-function differences).

**B4. Per-seed stability check.**
Per-seed W_6 values from the seed0..3 pickles already show what the across-seed SD is. Confirm at S=4 under the corrected formula that per-seed values are tightly clustered around 1.45 / 1.74 — not spread out to encompass 1.82 / 2.13. (Already done in the earlier diag output but record formally.)

### Track C (post-A, only if H1 is ruled out)

If splurge_old does NOT close the gap, rule out H1 and investigate:

**C1. Compare `update_mrkv_array` and `IncShkDstn_recessionUI` construction on this branch vs HAFiscal-QE.** Specifically whether the UB extension period, the UB → noUB transition probability, or the benefit level under UB-extended changed between branches.

**C2. Check `ConsMarkovModel.py` (HAFiscal's local copy) for any HARK-upgrade-related changes** to the agent's value function / policy function that affect the UB-extended state. `git log master...HEAD -- Code/HA-Models/FromPandemicCode/ConsMarkovModel.py` will surface recent changes.

**C3. Look for any differences in how AD convergence is computed** — not the AD amplification ratio (matches), but the *level* of AD under recessionUI specifically.

## 4. Tier/phase ordering

**Phase 1 (00:00 – 01:00): Launch splurge_old rerun + kick off Track B diagnostics.**
- Trigger Track A in background (~1 h wall).
- Run B1, B2, B3, B4 during this window. Save outputs to `history/20260420_ui_recession_gap/` (new directory).

**Phase 2 (01:00 – 01:30): Track A finishes → combine + compare.**
- Wait for notification that splurge_old rerun completes.
- Run `diag_welfare6_se.py` (modified temporarily to point at the splurge_old directory).
- Tabulate: splurge_old W_6 vs current W_6 vs HAFiscal-QE for all 9 cells.
- Decision:
  - **Gap closes substantially on UI Rec=1:** H1 confirmed. Stop. Write up. Go to Phase 5.
  - **Gap partially closes (~½ the way):** H1 partial; continue to Phase 3.
  - **Gap unchanged:** H1 ruled out; continue to Phase 3.

**Phase 3 (01:30 – 02:30, only if H1 not fully confirmed): Track C.**
- Run C1, C2, C3 investigations.
- Search for HARK-version-related commits / model-behavior changes in the working copy's `ConsMarkovModel.py`, `AggFiscalModel.py`, `Parameters.py`.
- Document findings.

**Phase 4 (optional, 02:30 – 04:00): targeted multi-seed of splurge_old.**
- If Phase 2's single-seed result looks suggestive but not decisive, run 3 more seeds of splurge_old to tighten the estimate.
- Total: 3 × 1h = 3h wall if sequential.

**Phase 5: Write up final report.**
- Destination: `history/20260420-ui-recession-gap-resolution.md`.
- Content: definitive-or-narrowed cause, supporting evidence from Tracks A/B/C, recommended next action.
- Should be readable in 5 minutes.

## 5. Failure modes and mitigations

**Splurge_old run fails or crashes.** Possible if the env-var code path has bitrotted since last test. Mitigation: test with a single scenario first (`--scenarios base` + `HAFISCAL_SPLURGE_OLD=1`) before committing to the full 12.

**Splurge_old gives wildly different values on *all* cells, not just UI.** Unexpected. Would indicate `HAFISCAL_SPLURGE_OLD=1` also changes dynamics on Check/TaxCut cells. Document the divergence; pick an additional single-variable diagnostic.

**Diagnostics reveal multiple contributing factors.** Likely — real problems rarely have a single cause. Report the decomposition: "X% of the gap comes from H1, Y% from H3, residual unexplained."

**Ran out of time before Phase 5.** Write the report in draft form as soon as Phase 2/3 completes, regardless of polish. The user needs a clear conclusion when they wake up, even if investigation remains incomplete.

## 6. Deliverables at wake-up

- [ ] `welfare6_scenario_results_Baseline_splurge_old/` (12 pickles from Track A).
- [ ] `history/20260420_ui_recession_gap/` containing B1–B4 diagnostic outputs.
- [ ] `history/20260420-ui-recession-gap-resolution.md` — one-page summary of what was found, with the concluding attribution and recommended next step.

## 7. Stopping criteria / time budget

Hard stop: if any single step runs >3× expected time, abandon it and move on. The priority is a reasoned written conclusion at wake-up, not exhaustive coverage.

Soft stop: if H1 is clearly confirmed in Phase 2 (gap closes >70% under splurge_old), declare victory and skip Phases 3–4.

## 8. Concrete command sequence

```bash
# Phase 1a: sanity-test HAFISCAL_SPLURGE_OLD on base scenario first (~1 min)
cd /home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
mkdir -p /tmp/splurge_old_smoke
HAFISCAL_SPLURGE_OLD=1 /home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python \
    welfare6_scenario.py --scenario base --baseline --agent-count-total 400 \
    --out-dir /tmp/splurge_old_smoke
# verify it runs and produces different cLvl than current base

# Phase 1b: launch full splurge_old pipeline (~1 h background)
HAFISCAL_SPLURGE_OLD=1 /home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python \
    run_welfare6_parallel.py --baseline --max-parallel 12 --duration-workers 4 \
    --out-dir welfare6_scenario_results_Baseline_splurge_old &
# save PID for monitoring

# Phase 1c (parallel): Track B diagnostics
mkdir -p /home/shared/github/llorracc/HAFiscal-Latest/history/20260420_ui_recession_gap
# run B1, B2, B3, B4 scripts (to be written)

# Phase 2 (after splurge_old finishes):
# Temporary symlink to let existing scripts read splurge_old data
mv welfare6_scenario_results_Baseline welfare6_scenario_results_Baseline_current
ln -sfn welfare6_scenario_results_Baseline_splurge_old welfare6_scenario_results_Baseline
/home/shared/github/llorracc/HAFiscal-Latest/.venv-linux-x86_64/bin/python diag_welfare6_se.py
# revert symlink afterwards
rm welfare6_scenario_results_Baseline
mv welfare6_scenario_results_Baseline_current welfare6_scenario_results_Baseline

# Phase 5: write report
```

## 9. What counts as a "well-supported resolution"

One of:
- **H1 confirmed** with quantitative evidence: splurge_old rerun recovers HAFiscal-QE UI values within a few %.
- **H1 ruled out + H2/H3/H4 narrowed** with at least one diagnostic in Track B/C pointing clearly at the mechanism.
- **Gap partially attributed**: X% from H1, residual from other mechanism(s), with clear decomposition.

If none of these hold after Phase 3, the report will honestly say so and recommend the specific next experiment that would resolve it (e.g., checking out HARK 0.14.1 in a side worktree and re-running — probably a multi-hour follow-up, not overnight).
