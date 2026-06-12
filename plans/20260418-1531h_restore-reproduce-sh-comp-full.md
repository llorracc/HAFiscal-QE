# Restore `./reproduce.sh --comp full` and align all `--comp` scopes with the current production workflow

**Created:** 2026-04-18
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_explore-further-speedups`
**Priority:** Blocks the `explore-further-speedups` plan. Nothing measurable can be done until the authoritative entry point works end-to-end on the current code.

## Problem

`./reproduce.sh --comp full` calls `reproduce/reproduce_computed.sh`, which calls `Code/HA-Models/do_all.py`, whose step 5 runs `AggFiscalMAIN.py` — a file that was **deleted at commit `c7e566d9` (chore: remove obsolete top-level scripts and docs)**. The pipeline aborts in step 5. The other `--comp` scopes are in various states: some still work against the current code, some don't, and none have been updated to use the post-bugfix production workflow (`run_hybrid_welfare6.py` + TM multiplier flow).

## Survey of current scope dispatchers

| `--comp` scope | Dispatcher | Calls | State |
|---|---|---|---|
| nano | `reproduce_computed_nano.sh` | `hark_version_comparison.py --level nano` | Independent; not affected by deletion |
| micro | `reproduce_computed_micro.sh` | `hark_version_comparison.py --level micro` | Independent; not affected |
| mini | `reproduce_computed_mini.sh` | `hark_version_comparison.py --level mini` | Independent; not affected |
| min | `reproduce_computed_min.sh` | `reproduce_min.py` + stash/restore | Works, but uses precomputed artifacts from a remote branch |
| TM-and-MC | `reproduce_computed_TM_and_MC.sh` | inline Python: `Simulate(...) + Output_Results(...) + Welfare_Results(...)` | **Works** — the most current end-to-end flow in tree, though does not yet use `run_hybrid_welfare6.py`'s CRN-paired welfare-6 |
| mc-only | `reproduce_computed_mc_only.sh` | `AggFiscalMAIN_reduced.py --baseline` | Works for MC multipliers / MC side |
| tm-only | `reproduce_computed_tm_only.sh` | `AggFiscalMAIN_reduced.py --baseline` | Works for TM multipliers / TM side |
| **full** | `reproduce_computed.sh` | `do_all.py` → **`AggFiscalMAIN.py` (DELETED)** | **Broken** |
| max | same as full + `HAFISCAL_RUN_STEP_3=true` | same | **Broken** |

## Current production workflow (the target)

Based on recent production runs (Phase 5 multiplier at commit `b1d42b9e`, Phase 6 / Phase 6-prime welfare at `8d6255dd` / `3986e1db`, MC-speedup parallel harness at `26c012f9`), the full Baseline-CRRA2 workflow has this shape:

1. **Step 1 — Splurge ς estimation.** `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py`. ~30 min. Unchanged.
2. **Step 2 — (β, ∇) estimation per education type.** `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py`. ~48 h on Baseline. Currently uses m-indexed TM; a matching a-indexed TM pass exists (`estim_phase2_tm_a.py`).
3. **Step 3 (optional) — Robustness (Splurge=0).** Same as step 2 but with `--splurge0`.
4. **Step 4 — HANK/SAM.** `HA-Fiscal-HANK-SAM.py` or `HA-Fiscal-HANK-SAM-to-python.py`. ~13 h.
5. **Step 5 — Policy comparison (TM multipliers + MC welfare-6).**
   - **5a (TM multipliers).** Produces `Tables/Baseline/Multiplier.tex` and policy figures. Runs via `AggFiscalMAIN_reduced.py --baseline` with `sim_method='TM'`, or via direct call to `Simulate(...) + Output_Results(...)` as in `reproduce_computed_TM_and_MC.sh` phase 1. ~9 h on Baseline.
   - **5b (MC welfare-6).** Produces `Tables/Baseline/welfare6.tex`. Runs via `run_hybrid_welfare6.py --baseline`, or the parallel harness `run_welfare6_parallel.py --baseline` (9.88× faster on 16 cores). ~35 min–6 h depending on parallelism. This is the post-bugfix replacement for the `Welfare_Results` call.

This decomposition is what `reproduce_computed_TM_and_MC.sh` already implements in spirit, except it uses the older `Welfare_Results(...)` welfare aggregator rather than the newer `run_hybrid_welfare6.py` path. The Phase 6 / Phase 6-prime production runs used `run_hybrid_welfare6.py`.

## Paper-output artifacts the full scope must produce

For `HAFiscal.tex` and its subfiles to compile with up-to-date numbers, the pipeline needs to produce, at minimum:

- `Target_AggMPCX_LiquWealth/Result_AllTarget.txt` (and `Splurge0` variant) — step 1 output, consumed by estimation code and by LaTeX table-generation scripts.
- `Target_AggMPCX_LiquWealth/Figures/` — step 1 MPC figures.
- `Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_*.txt` — step 2 output per education type.
- `Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj` (and `UI_extend_real` variant) — step 4 output.
- `Code/HA-Models/FromPandemicCode/Tables/Baseline/Multiplier.tex` — step 5a output.
- `Code/HA-Models/FromPandemicCode/Tables/Baseline/welfare6.tex` — step 5b output.
- `Code/HA-Models/FromPandemicCode/Figures/Baseline/` — various figures, from steps 1, 2, 5.

Paper robustness tables (CRRA1, CRRA3, R variants, ADElas, Rspell, LowerUBnoB, Splurge0) live under `Tables/<Parametrization>/` and are only built when the corresponding parametrization runs; the sensitivity parametrizations have not yet been re-run under the bugfix and so are out of scope for the current paper revision (tracked in `BUGS_private/HAFiscal_splurge_budget_inconsistency/results.md` §4).

## The restore

### Step A — Make `do_all.py` runnable

Replace the broken step-5 body in `do_all.py`:

```python
# Step 5: Comparing fiscal stimulus policies (Section 4)
if run_step_5:
    # ...
    os.chdir('FromPandemicCode')

    # 5a: TM multipliers
    os.system("python AggFiscalMAIN_reduced.py --baseline")

    # 5b: MC welfare-6 (parallel if the orchestrator is present; serial fallback)
    if os.path.exists('run_welfare6_parallel.py'):
        os.system("python run_welfare6_parallel.py --baseline")
    else:
        os.system("python run_hybrid_welfare6.py --baseline")

    os.chdir('../')
```

This preserves step 1–4 as they are and puts step 5 onto the current production path. The change is localized to 10–15 lines of `do_all.py`.

### Step B — Verify `do_all.py`'s other step references

Audit every `os.system("python ...")` in `do_all.py` against the current file tree:

- Step 1: `Estimation_BetaNablaSplurge.py` — exists ✓
- Step 2: `EstimAggFiscalMAIN.py`, `CreateLPfig.py`, `CreateIMPCfig.py`, `estimBetas_tabular_generate.py`, `nonTargetedMoments_tabular_generate.py` — all verified present ✓
- Step 3: `EstimAggFiscalMAIN.py` with `--splurge0` flag — check whether this flag exists on the current version of the estimation script
- Step 4: `HA-Fiscal-HANK-SAM.py` — exists ✓; also check whether `HA-Fiscal-HANK-SAM-to-python.py` is the intended newer version
- Step 5: broken as above; fixed in Step A

Document in the header comment of `do_all.py` which production commit last validated each step.

### Step C — Make `--comp full` end-to-end runnable at Reduced_Run scope first

Before committing to a full Baseline run (~72 h), validate the whole pipeline at Reduced_Run scope. That requires either:

- Adding a `--reduced` flag to `do_all.py` that threads through each substep, or
- A separate `do_all_reduced.py` wrapper (preferred — avoids CLI-plumbing changes to the Baseline path)

The Reduced_Run pipeline should complete in ≤ 2 h and exercise all five steps' code paths.

### Step D — Align the other `--comp` scopes with the new step-5 path

- **TM-and-MC.** Update the inline Python in `reproduce_computed_TM_and_MC.sh` to call `run_hybrid_welfare6.py` (or its parallel sibling) for the welfare half, replacing the older `Welfare_Results(...)` call. This brings TM-and-MC onto the same welfare path as `--comp full`.
- **mc-only / tm-only.** These already point at `AggFiscalMAIN_reduced.py --baseline`. No change needed; they remain the single-method diagnostics.
- **min.** Uses precomputed artifacts from a remote branch; update the `REQUIRED_FILES` list if any new outputs are produced by the revised step 5.
- **mini / micro / nano.** Independent of the step-5 change; no update needed.

### Step E — Regression check against `reproduce_computed_TM_and_MC.sh`'s output

If `reproduce_computed_TM_and_MC.sh` already produces `Multiplier.tex` + `welfare6.tex` on Baseline in ~13 h (its expected budget), the new `--comp full` should produce identical tables at 2-decimal precision. If they differ, identify why before claiming the restore is done.

## Sequencing

1. Step A (do_all.py step-5 replacement) — 30 min of edits.
2. Step B (path audit of all do_all.py os.system lines) — 15 min.
3. Step C (Reduced_Run validation of the full pipeline) — ~2 h compute, + a few hours to wire up `--reduced`.
4. Step D (TM-and-MC alignment) — 30 min of edits.
5. Step E (regression check) — runs alongside a Baseline `--comp full` production run.

Total effort to make `--comp full` work: ~half a day of focused coding plus a Reduced_Run validation pass.

Only after this is done does the `explore-further-speedups` plan (`plans/20260418_explore-further-speedups.md`) become actionable. Its Phase 0 profile run assumes an end-to-end runnable `--comp full`.

## Deliverables

1. A revised `do_all.py` with step 5 working on current code.
2. A `do_all_reduced.py` (or `--reduced` flag) for the fast-validation pipeline.
3. A revised `reproduce_computed_TM_and_MC.sh` using the current welfare-6 path.
4. Documentation update: one sentence each in `reproduce.sh`'s `--help` and in `README.md` noting the current step-5 composition.
5. A successful Reduced_Run invocation of `./reproduce.sh --comp full --reduced` (or equivalent) recorded in `plans/results/`.

## Non-goals

- Do not re-run the Baseline yet; that is the speedup plan's Phase 0.
- Do not change any production-calibration numbers.
- Do not change the Splurge0 / CRRA1 / CRRA3 / ADElas / Rfree / Rspell / LowerUBnoB sensitivity runs' code — they remain outside the paper's main pipeline until re-run under the bugfix.
- Do not touch the welfare-drop investigation fork.
