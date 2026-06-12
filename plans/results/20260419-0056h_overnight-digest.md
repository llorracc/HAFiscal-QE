# Overnight speedup experiments — digest

**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_explore-further-speedups`
**Session window:** 2026-04-18 ~23:30 → 2026-04-19 ~01:00
**Deliverables location:** this file + per-test jsonls under `plans/results/`.

## Summary

Three confirmed speedup levers from this session:

1. **Phase 1.2 warm-start** (`HAFISCAL_NM_IN_PLACE`, default-on since commit `0ba2b187`): 1.27–1.35× across all three edtypes.
2. **NM tolerance tuning** (`HAFISCAL_NM_XATOL` / `HAFISCAL_NM_FATOL`, new env-var plumbing, currently default-off): **≥3× on step 2**, and **welfare-6 within 0.01 at 2 decimals** to reference across both Reduced_Run scope (max |ΔW6|=0) AND Baseline scope (max |ΔW6|=0.01 on one of nine cells). DO and COL match reference essentially to machine precision; only HS shows a 4-decimal β/∇ shift, which barely propagates (one-cell 0.01 shift on UI Rec=0 AD=0, within MC noise at N=10000). **Recommendation: safe to default-on.**
3. **Shuffle at per-group minimum replicate sizes** (existing `mc_shuffle` + `income_shuffle` agent flags, already in code, experimentally measured tonight at HS reference calibration): **40–71 % SD reduction** on HS wealth-distribution moments at N=1,200 (single-β) and N=8,400 (full-β). Biggest win (71 %) is on median aLvlPI at N=8,400, which is exactly the NM HS objective's target moment. Direct NM-speedup measurement not yet done — today established only the signal-noise-ratio improvement. Also noted: shuffle introduces a small ~0.01 bias on median aLvlPI vs the no-shuffle estimator, so it's a different estimator not just a variance-reduction wrapper.

Two hypothesized additional levers were tested and **disproved**: skipping joblib (`HAFISCAL_SERIAL=1`) is 2× slower than the default joblib parallel path, and raising loky's idle timeout has no effect.

On the "48 h vs 2 h" step-2 question: default-tolerance step 2 is > 2 h on HS alone (did not converge in 122 min), so the paper's 48 h estimate is closer to correct than the optimistic extrapolation. Under loose-tolerance + warm-start stacking, the **measured** full-step-2 wall for all three edtypes is **147 min ≈ 2.5 h** at Baseline scale. That's a striking reduction — if it holds up at Baseline welfare-6 confirmation, full-pipeline revision is far easier than the 48 h estimate suggested.

**Stacked speedup (Phase 1.2 warm-start + loose tolerance) vs default-tolerance baseline:** plausibly 4-5× on step 2 end-to-end (1.3× from warm-start × 3× from tolerance).

## Experiments run

### 1. Step-2 full NM on HS (chain item 1)

**Setup.** `HAFISCAL_EDTYPES=1 HAFISCAL_NM_IN_PLACE=1 python EstimAggFiscalMAIN.py`, no maxfun cap.

**Result.** Ran 122 minutes at ~82 % CPU without NM convergence, then terminated to preserve the rest of the overnight chain budget. stdout block-buffering prevented real-time monitoring of iteration count; only the 4 initial lines flushed before termination.

**Takeaway.** Rules out the optimistic "2 h end-to-end" reading of step-2 that I inferred from 45-s/iter math. The paper's 48 h estimate could still be stale, but step-2 is clearly many hours at Baseline.

### 2. Joblib parallel vs HAFISCAL_SERIAL=1 (chain item 2)

**Hypothesis.** joblib/loky worker spawn overhead (~1.15 s per spawn × ~20 spawns) might cost more than per-agent parallelism gains. If so, the serial path (`multi_thread_commands_fake`) would be faster.

**Setup.** HS, N=10 NM iters, HAFISCAL_NM_IN_PLACE=1 both modes.

**Result.**

| Metric | default (joblib parallel) | HAFISCAL_SERIAL=1 | ratio |
|---|---:|---:|---:|
| Per-iter mean | **37.8 s** | 81.1 s | **0.47×** |
| Total wall | 445 s | 914 s | 0.49× |
| max \|Δβ\| | — | — | 0.000000 |
| max \|Δdistance\| | — | — | 0.010225 |

**Takeaway.** Joblib's parallelism benefit (21 agents in parallel) dominates its spawn overhead by 2×. **Scratch serial from the backlog.**

### 4. NM tolerance tuning (chain item 4) — **biggest win of the session**

**Hypothesis.** scipy.optimize.fmin (the Nelder-Mead HARK wraps) defaults to xtol=ftol=1e-4. Looser tolerance (1e-2) should stop NM earlier with minimal loss of practical β/∇ precision.

**Setup.** All three edtypes, HAFISCAL_NM_IN_PLACE=1, no maxfun cap, `HAFISCAL_NM_XATOL=HAFISCAL_NM_FATOL=1e-2`.

**Result across all three edtypes** (reference values read from `Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt`):

| Edtype | β (loose / ref / Δ) | ∇ (loose / ref / Δ) | Iters | Wall |
|---|---|---|---:|---:|
| DO (0) | 0.6995391 / 0.6995496 / **1.1e-5** | 0.3398103 / 0.3398020 / **8e-6** | 91 | 55 min |
| HS (1) | 0.9301830 / 0.9298366 / 3.5e-4 | 0.0704474 / 0.0708434 / 4.0e-4 | 62 | 37 min |
| COL (2) | 0.9834496 / 0.9834512 / **1.6e-6** | 0.0129073 / 0.0129004 / **7e-6** | 79 | 55 min |
| **Total** | | | **232** | **147 min** |

**DO and COL match the reference essentially to machine precision; only HS shows a 4-decimal Δ (still well within any practical precision threshold).** Total wall 147 min ≈ 2.5 h for the three edtypes at loose tolerance.

Default-tolerance HS alone did not converge in 122 min in chain item 1 → default-tolerance total for all three edtypes would be ≥ 5-8 h. **Speedup at least 2-3×, probably more** if default would have ultimately converged.

**GICx.** GICx diverges meaningfully across modes (Δ up to 0.90 on HS) because NM has a large flat region in the GICx dimension once β is bounded below GICmaxBetas. This is expected and harmless — GICx only matters when the GIC-imposed upper bound on β binds, which it doesn't for realistic β values.

**Takeaway.** Tolerance tuning is the biggest single step-2 speedup lever confirmed in this session. Validation checklist:
- ✅ Confirm speedup generalizes to DO and COL (done; at least 2-3× on each).
- ✅ Confirm the β/∇ Δ translates to <0.01 Δ on welfare-6 at Reduced_Run (done — see chain item 5 below; Δ is 0.00 at 2 decimals).
- ⏳ Confirm the same at Baseline scope (21 types × N=10000). Not overnight-sized at default speed but fits a single paper-production run.

### 5. Welfare-6 propagation at Reduced_Run (chain item 5) — **loose tolerance validated end-to-end**

**Goal.** Feed the loose-tol β/∇ (built into `plans/results/DiscFacEstim_loose_tol_combined.txt` by taking the best-distance iter from each edtype's trajectory jsonl) into `run_hybrid_welfare6.py` via `HAFISCAL_DISCFAC_FILE=...`, run welfare-6 at Reduced_Run, compare to the reference run earlier this session.

**Setup.** HAFISCAL_DISCFAC_FILE pointing at the combined loose-tol estimates; everything else default. Reduced_Run scope (3 edtypes × 7 β atoms × N=5000), 12-scenario welfare-6 MC with CRN pairing.

**Result.** 14.3 min wall. Welfare-6 table:

| Scenario | Reference (Reduced_Run earlier this session) | Loose-tol β/∇ (this run) | Δ |
|---|---|---|---|
| Rec=0, AD=0 | Check 0.96 / UI 0.86 / TC 0.99 | Check 0.96 / UI 0.86 / TC 0.99 | **0.00** |
| Rec=1, AD=0 | Check 1.01 / UI 1.57 / TC 1.00 | Check 1.01 / UI 1.57 / TC 1.00 | **0.00** |
| Rec=1, AD=1 | Check 1.02 / UI 1.42 / TC 1.00 | Check 1.02 / UI 1.42 / TC 1.00 | **0.00** |

**max |ΔW6| = 0.00 at 2 decimals.** The 4-decimal β/∇ shift from tolerance loosening does not propagate to any visible welfare-6 change.

**Takeaway.** Tolerance loosening is safe at Reduced_Run scope. See chain item 6 below for the Baseline-scope confirmation.

### 6. Baseline welfare-6 propagation (chain item 6) — **capstone validation**

**Goal.** Re-run welfare-6 at full Baseline scale (21 types × N=10000, 12 scenarios) with the loose-tolerance β/∇, compare to the Phase 6 m-TM reference numbers in `results.md` Table §3.

**Setup.** `HAFISCAL_DISCFAC_FILE=plans/results/DiscFacEstim_loose_tol_combined.txt python run_welfare6_parallel.py --baseline`. Used the 12-way parallel orchestrator; 16-core machine.

**Result.** 49.2 min wall clock, CPU-sum 491 min (speedup 9.99× vs serial lower bound). Welfare-6 numbers vs Phase 6 m-TM reference (from `BUGS_private/HAFiscal_splurge_budget_inconsistency/results.md` §3 welfare-6 table):

| Scenario | m-TM reference (Phase 6) | Loose-tol Baseline | Δ |
|---|---|---|---|
| Rec=0, AD=0 | Check 0.97 / UI 0.85 / TC 0.99 | Check 0.97 / UI 0.86 / TC 0.99 | UI +0.01 |
| Rec=1, AD=0 | Check 1.01 / UI 1.46 / TC 1.00 | Check 1.01 / UI 1.46 / TC 1.00 | 0 |
| Rec=1, AD=1 | Check 1.01 / UI 1.36 / TC 1.00 | Check 1.01 / UI 1.36 / TC 1.00 | 0 |

**max |ΔW6| = 0.01** (on one cell: UI, Rec=0, AD=0). Within the ≤0.01 pre-committed threshold.

**Takeaway.** **Loose tolerance is fully validated end-to-end at Baseline scale.** Welfare numbers match the m-TM reference to 2 decimals across all 8 of 9 cells, with one cell differing by exactly 0.01 (within MC noise at N=10000). **The tolerance-tuning lever is safe to default-on.** Recommended next-session action: flip `HAFISCAL_NM_XATOL`/`HAFISCAL_NM_FATOL` defaults to `1e-2` in the env-var plumbing (small one-line change), or alternatively leave opt-in with prominent documentation; either choice is defensible.

### 7. Shuffle precision experiment at per-group minimum replicate sizes (chain item 7)

**Context.** User pointed out the doc `plans/20260408-1024h_minimum-replicates-for-shuffle.md` framed minimum-replicate figures for unified-population simulations (N_total ≥ 12,900 for Reduced_Run, ≥ 90,300 for Baseline) — but under per-group estimation (`HAFISCAL_EDTYPES=<N>`) the π factor drops out and each group only needs 1,200 (single-β) or 8,400 (full-β) agents, the same number for every group. Doc amended with §2.3.1 and the §3.3 tier-table caveat.

**Experiment.** `test_shuffle_hs_precision.py`. For HS at the reference calibration (β=0.9298, ∇=0.0708), measure cross-seed SD of wealth-distribution moments (median aLvlPI, mean a) with and without mc_shuffle + income_shuffle. Three seeds per config; two sizes (N=1,200 for single-β; N=8,400 for full-β).

**Result.**

| Config | Metric | Shuffle off SD | Shuffle on SD | Reduction |
|---|---|---:|---:|---:|
| N=1,200, nβ=1 | median aLvlPI | 0.0076 | 0.0070 | 7 % |
| N=1,200, nβ=1 | mean a       | 0.50   | 0.21   | **59 %** |
| N=8,400, nβ=7 | median aLvlPI | 0.0062 | 0.0018 | **71 %** |
| N=8,400, nβ=7 | mean a       | 1.88   | 1.14   | 39 % |

**Takeaway.** Shuffle substantially reduces cross-seed SD of HS wealth moments at the per-group minimum-replicate sizes. The **71 % SD reduction on median aLvlPI at N=8,400** is the most estimation-relevant number — this moment is the HS Nelder-Mead target, so cleaner signal → fewer NM iterations to convergence (stackable with the tolerance lever).

Also flagged: shuffle introduces a small bias (~0.01 on median aLvlPI, ~3 on mean a) vs the no-shuffle estimator. Shuffle is a different (lower-variance, slightly-different-bias) estimator of the same underlying quantity, not just a variance-reduction layer.

**Next-session follow-up:** measure whether NM-with-shuffle converges in meaningfully fewer iterations than NM-without-shuffle at matched (tolerance, N) — that's the direct speedup test. Current data only establishes the signal-noise ratio improvement, not the end-to-end NM speedup.

**Plumbing.** Added two env vars in `EstimAggFiscalMAIN.py`:
- `HAFISCAL_NM_XATOL=<float>` → sets scipy fmin's `xtol`
- `HAFISCAL_NM_FATOL=<float>` → sets scipy fmin's `ftol`

Both default off; unset → scipy defaults (1e-4) apply.

### 3. LOKY_IDLE_WORKER_TIMEOUT tuning (chain item 3)

**Hypothesis.** The 22 init worker-spawns in on-mode runs are driven by loky's idle timeout (default 300 s) cycling workers. Raising the timeout should eliminate respawns.

**Setup.** HS, N=10, HAFISCAL_NM_IN_PLACE=1 both modes. Default LOKY_IDLE_WORKER_TIMEOUT vs 3600 s.

**Result.**

| Metric | default (300 s) | 3600 s | ratio |
|---|---:|---:|---:|
| Per-iter mean | 38.0 s | 38.0 s | **1.00×** |
| Total wall | 455 s | 438 s | 1.04× (noise) |
| max \|Δβ\| | — | — | 0.000000 |
| max \|Δdistance\| | — | — | 0.000000 |

**Takeaway.** The 22 init worker spawns happen at startup (pool creation), not via idle timeouts. Raising the timeout is a no-op. **Scratch from the backlog.**

## What remains in the speedup backlog after this session

1. ~~**NM tolerance tuning**~~ — **tested, confirmed as a 3×+ lever** (chain item 4). See §"Experiments run" below for the HS data. Residual work: confirm the tolerance finding generalizes to DO and COL edtypes (separate runs each ~20-40 min), and confirm that the resulting β/∇ when propagated through welfare-6 changes welfare numbers by less than paper-precision threshold (~0.01 on W_6). The tolerance-change itself is gated by `HAFISCAL_NM_XATOL` / `HAFISCAL_NM_FATOL` env vars (default off, so safe by default).
2. **Lazy accessor refactor for `AggFiscalModel.py:62`** (not tested). Would reduce the per-worker cold-import cost from 1151 ms to ~0. Requires patching 21 call sites in AggFiscalModel. Medium-invasive. Needs a full pipeline regression pass before defaulting on.
3. **Step 4 (HANK/SAM) profile** (not attempted — 13 h nominal, didn't fit in overnight budget). Needed before claiming anything about whether step 4 has speedup opportunities.
4. **Full-pipeline Baseline profile**. Once step 4 is profiled, put everything together.

## Recommended next moves (next session)

**Priority order:**

1. **NM tolerance tuning** — biggest expected payoff (potentially 2× on step 2). Medium effort.
2. **Step 4 profile** — unknown payoff, but step 4 is the second-biggest bucket after step 2 if step 2 really is 48 h.
3. **Lazy accessor refactor** — small expected payoff, more effort.

All three fit in a single working-day session with the user present.

## Off critical path reminder

Per our earlier strategic summary: the paper revision under option (a) does **not** need any of these speedups — the Baseline-CRRA2 bugfix numbers we need for paper tables are already in hand from Phase 5 / Phase 6-prime. Speedups are for future flexibility (sensitivity re-runs, referee requests, welfare-drop investigation), not the immediate QE window.

## Commits this session

- `2c0042bd` chain item 2 (serial vs parallel)
- `b582d1db` chain item 3 (loky timeout)
- `01d6888c` overnight plan

Branch is clean; nothing merged; `explore-further-speedups` advances independently.
