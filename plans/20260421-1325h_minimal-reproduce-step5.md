# Plan: Minimal reproduction — prep then run Step 5 only

**Date:** 2026-04-21
**Status:** Planned; not started
**Branch target:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_explore-further-speedups`
**Predecessor plan:** `plans/20260421_auto-parallelism-heuristic.md` (done; auto-parallelism merged)

---

## 1. Goal

Produce the paper's computational outputs (tables + figures) without redoing work that's already committed and current. Specifically:

- **Skip Steps 1, 2** — their outputs (`Result_AllTarget.txt`, `DiscFacEstim_CRRA_2.0_R_1.01*.txt`) are committed and reflect the current splurge-in-budget + BUG-032-fixed configuration. They've been re-estimated on this branch; no stale.
- **Skip Step 3** (Splurge=0 Online Appendix robustness) — default off; adds ~48h; not needed for the main paper.
- **Skip Step 4** (HANK/SAM Jacobians + experiments) — user-requested skip. Step 4 outputs are used by Step 5 *only* for Figure 6 (which combines HANK/SAM policy outcomes with policy welfare). If we skip Step 4, Figure 6 may not be produced cleanly; flagged as a risk below.
- **Run Step 5** — the policy-comparison computations: Step 5a (TM multipliers via `AggFiscalMAIN_reduced.py`) and Step 5b (MC welfare-6 table).

Total expected wall time (with our auto-parallelism + parallel welfare6 wired in): **~10–11 hours** (vs default ~17h with serial Step 5b).

## 2. Background: why Steps 1 and 2 are current

**Step 1** estimates the splurge value ς by fitting the aggregate MPC time-path to Fagereng-Holm-Natvik 2021 data. Output: `Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt`:

```python
{'splurge': 0.2608750140503139, 'beta': 0.9610774318172289, 'nabla': 0.06684279084283819}
```

This value (0.2609) is the post-BUG-032 fix, specific to the splurge-in-budget formulation (commit `7d92b487`). It's committed. Running Step 1 again will reproduce this to within floating-point noise (per commit `5b9c02f3` verifying 0.14.1↔0.17.0 equivalence).

**Step 2** estimates per-education-group β, ∇ conditional on ς. Output: `Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01*.txt`, currently:

```python
{'EducationGroup': 0, 'beta': 0.6995, 'nabla': 0.3398, 'GICx': 6.0696, ...}
{'EducationGroup': 1, 'beta': 0.9302, 'nabla': 0.0705, 'GICx': 5.0963, ...}
{'EducationGroup': 2, 'beta': 0.9834, 'nabla': 0.0129, 'GICx': 6.6940, ...}
```

Also re-estimated under splurge-in-budget with ς=0.2609. Fresh.

**Together** Steps 1 and 2 would take 30 min + several hours (Step 2 is the NM optimization — recently sped up ~3× by the NM-tolerance + in-place warm-start commits on this branch). But there's no reason to redo them for the current configuration.

## 3. Background: two code paths produce `Tables/Baseline/welfare6.tex`

One lexical detail that could surprise us:

- **`Welfare.py::Welfare_Results`** (called from `Output_Results.py`) writes `welfare6.tex` using the **paper formula** (fixed AD=0 `NPV_AddInc_UI_Rec` denominator, Welfare.py:277/284). Produces the numbers that match HAFiscal-QE-paper-style. Run as part of Step 5a via `AggFiscalMAIN_reduced.py → Output_Results.py`.

- **`run_hybrid_welfare6.py`** writes `welfare6.tex` using a **cell-specific-denominator formula** (each AD=1 cell uses its own AD=1 `NPV_AggIncome` diff). Produces different numbers (earlier investigation showed UI Rec=1 AD=1 = 1.35 under this formula vs 1.74 under the paper formula). Called as Step 5b of do_all.py.

Since both write to the *same file path*, the **last writer wins**. do_all.py executes 5a then 5b, so run_hybrid_welfare6.py's buggy-formula output is what lands in `Tables/Baseline/welfare6.tex` at the end of a full run.

**Impact on this plan.** When we wire `run_welfare6_parallel.py` into Step 5b (prep task (a)), we inherit the same buggy formula from it (both scripts have a verbatim copy of `welfare6_mc`). If we want `Tables/Baseline/welfare6.tex` to have the paper-formula values, we need to either:

- (i) Patch `welfare6_mc` in both `run_hybrid_welfare6.py` and `run_welfare6_parallel.py` to use the paper's fixed AD=0 denominator, OR
- (ii) Have Step 5b NOT write `welfare6.tex` — leave the Welfare.py copy produced by Step 5a in place.

Recommendation: **(i)**, since the MC welfare6 pipeline should be internally consistent regardless of which entry point is used. One small diff in `welfare6_mc` to switch denominators.

## 4. Prep tasks

### (a) Wire `run_welfare6_parallel.py` into Step 5b

- Edit `do_all.py` to replace the Step 5b command with `run_welfare6_parallel.py --baseline --out-dir <scenario_dir> --table-dir Tables/Baseline`.
- The auto-parallel heuristic (merged earlier today) will pick duration/solve workers; no manual flags needed.
- **Also apply the paper-formula fix** in `welfare6_mc` of both `run_hybrid_welfare6.py` and `run_welfare6_parallel.py` (treat as part of (a)).
- Verify locally with a small smoke: `python run_welfare6_parallel.py --baseline --agent-count-total 400 --table-dir Tables/Baseline_smoke` and confirm it writes `Tables/Baseline_smoke/welfare6.tex`.

Effort: ~45 min (edits + smoke test).

### (b) Handle pre-existing modified files

Current uncommitted changes in working tree:
- `Code/HA-Models/Results/AllResults_CRRA_2.0_R_1.01.txt`
- `Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01*.txt` (main + edType1/2)
- `Code/HA-Models/Target_AggMPCX_LiquWealth/Figures/*.{pdf,png,svg}` (10 files: `AggMPC_LotteryWin_comparison`, `LiquWealth_Distribution_comparison`, and `_splurge0` variants)
- `plans/20260408-1024h_minimum-replicates-for-shuffle.md`
- Untracked: `Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType0.txt`, `plans/results/20260419_shuffle-method-limitations.md`, `Code/HA-Models/FromPandemicCode/diag_shuffle_working.py`

Most are *outputs* of Steps 1/2 that we're skipping, so they won't be overwritten by Step 5. But the figures in `Target_AggMPCX_LiquWealth/Figures/` are from Step 1 and aren't affected either.

**Decision point:** these pre-existing modifications predate this session. Two options:
- (b1) **Commit them on a side branch** for archival, then `git stash` to clean the tree before the run. Safest.
- (b2) **Leave them as-is** during the run. Step 5 won't touch them. Afterward, review + commit or discard.

Recommendation: (b2). Step 5 doesn't write any of the uncommitted files. Simpler.

Effort: ~5 min (confirm Step 5 writers don't collide with the listed paths).

### (c) Clean intermediate pickle directories

Current untracked pickle directories (Gitignored; not in .git):
- `welfare6_scenario_results_Baseline_{seed0,seed1,seed2,seed3,splurge_old,master_equiv,combined_S4,prev,auto_par,auto_par_N400}/`
- A symlink `welfare6_scenario_results_Baseline` → `_combined_S4`
- Total: ~2 GB

Step 5b writes to `Code/HA-Models/FromPandemicCode/welfare6_scenario_results/` (default) or whatever `--out-dir` specifies. If we pass `--out-dir Code/HA-Models/FromPandemicCode/welfare6_scenario_results_Baseline_reproduce` we sidestep any collision.

**Decision point:** keep or purge intermediate pickles?
- **Keep** (recommended): the seed0/seed1/.../master_equiv dirs document the overnight UI-gap investigation and let us regenerate `history/20260420-ui-recession-gap-resolution.md` numbers. They're ~2 GB but disk is cheap.
- **Purge**: remove all `welfare6_scenario_results_Baseline_*` dirs, keeping only committed code. Saves ~2 GB.

Recommendation: **keep** until the paper is resubmitted, then revisit.

Effort: ~2 min (create the backup subdirectory strategy if needed).

### (d) Skip Step 3

Two options:
- (d1) Do nothing special — default behaviour is `HAFISCAL_RUN_STEP_3=false`, so Step 3 skips.
- (d2) Add env-var controls for all steps (`HAFISCAL_RUN_STEP_1/2/4`) so skipping is explicit and composable.

Recommendation: **(d2)** — small code change, gives the reproduce script a knob for future targeted runs. One-commit change to `do_all.py`.

Effort: ~15 min.

## 5. Execution sequence

Once (a), (b), (c), (d) prep is done:

```bash
# From repo root; pinned to explicit skip of steps 1, 2, 3, 4:
cd /home/shared/github/llorracc/HAFiscal-Latest
export HAFISCAL_RUN_STEP_1=false
export HAFISCAL_RUN_STEP_2=false
export HAFISCAL_RUN_STEP_3=false
export HAFISCAL_RUN_STEP_4=false
# Step 5 remains on by default.

./reproduce.sh --comp full
```

Or, equivalently, to bypass the reproduce.sh wrapper overhead:
```bash
cd Code/HA-Models
HAFISCAL_RUN_STEP_1=false HAFISCAL_RUN_STEP_2=false \
HAFISCAL_RUN_STEP_3=false HAFISCAL_RUN_STEP_4=false \
python do_all.py
```

Expected progression:

| Step | Status | Runtime |
|---|---|---:|
| 1 (splurge) | skipped | 0 |
| 2 (β, ∇) | skipped | 0 |
| 3 (Splurge=0) | skipped | 0 |
| 4 (HANK/SAM) | skipped | 0 |
| **5a (TM multipliers)** | run | ~9 h |
| **5b (MC welfare-6, parallel)** | run | ~1 h |
| **Total** | | **~10 h** |

## 6. Deliverables

- [ ] `Code/HA-Models/FromPandemicCode/Tables/Baseline/Multiplier.tex` — updated TM multipliers.
- [ ] `Code/HA-Models/FromPandemicCode/Tables/Baseline/welfare6.tex` — updated MC welfare-6. Will reflect paper-formula values (1.46 / 1.74 for UI recession cells under current post-bugfix code — not HAFiscal-QE's 1.82 / 2.13).
- [ ] `Code/HA-Models/FromPandemicCode/Tables/Baseline/*.tex` — other tables produced by AggFiscalMAIN_reduced + Output_Results.
- [ ] Commit the new `Tables/Baseline/` outputs on the working branch.

## 7. Risks

- **Figure 6 not produced.** Step 5 tries to create Figure 6 by combining HANK/SAM Step 4 outputs with policy comparisons. If Step 4 outputs don't exist, this either (a) fails loudly and aborts Step 5 entirely, (b) produces a partial/corrupt figure, (c) silently skips. Need to check behaviour. If (a), Step 5 won't complete and we need to either run Step 4 or patch do_all.py to skip the Figure 6 sub-step.
  - **Pre-flight check**: look at the Figure 6 production code path and verify what happens if Step 4 outputs are missing. Decide: (i) always run Step 4, (ii) add a HAFISCAL_RUN_STEP_4_FIG6=false flag that disables the Figure 6 sub-step of Step 5, (iii) manually delete/patch the Figure 6 code before running.
- **Paper-formula fix in `welfare6_mc` introduces subtle regression.** We've tested the paper formula in the diagnostic scripts (`diag_welfare6_se.py`, `compute_welfare6_control_variate.py`), but not in the production `run_welfare6_parallel.py` or `run_hybrid_welfare6.py`. Smoke test in (a) addresses this.
- **Pre-existing M files touched after all.** Low risk per §4(b), but worth re-verifying after prep.
- **Step 5a takes 9h with no easy speedup available.** `AggFiscalMAIN_reduced.py` has its own parallelism knobs but we haven't tuned them. Out of scope here.

## 8. Order of operations and time budget

1. Prep (a) — wire parallel + apply formula fix, smoke test: 45 min.
2. Prep (d) — add STEP_N env vars to do_all.py: 15 min.
3. Prep (b) — confirm paths don't collide: 5 min.
4. Prep (c) — note pickle dirs preserved: 2 min.
5. Pre-flight: check Figure 6 behaviour without Step 4 outputs: 15 min.
6. Commit prep changes, push.
7. Kick off `do_all.py` with all step-skip env vars: ~10 h run.
8. Verify outputs, commit `Tables/Baseline/` updates, push.

**Total: ~1 h 20 min prep + ~10 h execution + 15 min cleanup = ~11.5 h wall.**

## 9. Stopping criteria

- If Step 5a fails within the first hour of run time → abort, debug.
- If Figure 6 sub-step fails → accept incomplete figure output, proceed, document gap.
- If `welfare6.tex` output has unexpected values → inspect, compare to pre-run expectation (paper formula current values 1.46 / 1.74), and verify the numerical workflow is correct.

## 10. After the run

- Compare output tables against `history/20260420-ui-recession-gap-resolution.md` predictions (UI Rec=1 ≈ 1.46, UI Rec=1 AD=1 ≈ 1.74).
- Cross-check against the existing `Tables/CRRA2/welfare6.tex` (paper canonical path) to see if paper-revision flags are needed.
- Generate the SE table companion (§ next plan): run `compute_welfare6_se_table.py` against the seed0..3 data and emit to `Tables/Baseline/welfare6_SE.tex` as the paper's uncertainty companion to `welfare6.tex`.
