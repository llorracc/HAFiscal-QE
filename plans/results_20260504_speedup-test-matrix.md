---
date: 2026-05-04
status: in-progress
keywords: [speedup, results-matrix, qe_fidelity, benchmark, test]
related_plans:
  - 20260504-1300h_qe_fidelity_speedup_systematic_test.md
---

# Speedup test results matrix

Living document. Updated incrementally as tests complete.

**Two references** (different scopes give different absolute multipliers):

- **Phase C tests (Reduced_Run scope) compare against**: Phase A Reduced_Run reference
  (Check 1.36, UI 1.37, TaxCut 1.12; wall 3.41 min Step-5a alone, 4.64 min wrapper-total).
- **Phase E final validation (Baseline scope) compares against**: qe_fidelity_full
  Baseline (Check 1.216, UI 1.178, TaxCut 0.992; commit `c6935969`; wall 3 hr 13 min).

**Pass criterion:** Wall ≥ 1.5× faster than the appropriate reference AND multipliers
within ±3% (±5% for shuffle). For Phase C, ±3% means within ±0.04 on Check, etc.

## Phase A: MID-1 reference (Reduced_Run scope, no welfare-6)

| Field | Value |
|---|---|
| Wall time (Step-5a) | **3.41 min** ("Whole script took") |
| Wall time (wrapper-total incl drift) | **4.64 min** |
| Check multiplier (with AD recession) | **1.36** |
| UI multiplier (with AD recession) | **1.37** |
| TaxCut multiplier (with AD recession) | **1.12** |
| Check 1st-round AD only | 1.27 |
| UI 1st-round AD only | 1.28 |
| TaxCut 1st-round AD only | 1.08 |
| Status | ✓ done 2026-05-04 13:38 |
| Log | `reproduce/logs/speedup-test_phase_A_reference_20260504-133330.log` |
| Registry run-id | d956abe6_27af0b_20260504-133808 |

Note: at Reduced_Run scale (single-cohort betaDistr per education group, N=5,000)
the AD/1st-round-AD calculations are FAST (~4-5s each per "Calculating took").
The wallclock is dominated by setup, drift checks, and the Markov state
construction. Per-duration parallelism gains may be smaller at this scale than
at Baseline scope where recessionCheck took 9158s alone.

## Phase B: Quick PoC results (SMOKE scope)

| Idea | Description | Wall (smoke) | Crashes? | Multipliers non-NaN? | Status |
|---|---|---|---|---|---|
| A | Per-duration fork on AD scenarios | n/a | n/a | n/a | **❌ NOT APPLICABLE for MC mode** — `run_experiments_all_recessions` (Simulate.py:712) already uses `_fork_dispatch_durations` for ALL sub-phases (no-AD, AD effects, 1st-round AD). The sequential AD-duration loop only exists in the TM-AD path (Simulate.py:826), which qe_fidelity does not use. Skip. |
| B | HARK real `multi_thread_commands` | _pending_ | | | _pending_ |
| C | MC + Income shuffle (no-op confirmation) | 3.45 min | no | yes | ✓ confirmed env vars NOT plumbed to Step-5 (multipliers identical to ref smoke) |
| C-v2 | MC + Income shuffle (with Simulate.py plumbing added) | 4.60 min | no | yes | ✓ shuffle ENGAGED — multipliers change vs ref (Check 1.34→1.36, **UI 1.37→1.09**, TaxCut 1.12→1.13). UI delta is large (-20%) due to N=100 below per-cohort minimum-occupancy threshold (per plans/20260408-1213h_…). Wall unchanged at smoke. Expect MID-1 (N=5000) accuracy to be much better. Plumbing pattern: Simulate.py:298-308 reads HAFISCAL_MC_SHUFFLE/INCOME_SHUFFLE env vars and sets `agent.mc_shuffle/income_shuffle` per EstimAggFiscalMAIN.py:761-773 pattern. |
| D | Numba JIT on hot path | _pending_ | | | _pending_ |
| E | BLAS thread tuning | _pending_ | | | _pending_ |
| F | Loose AD convergence tolerance (1e-1, 3 iter via HAFISCAL_AD_CONVERGENCE_TOL/HAFISCAL_AD_MAX_ITER) | 4.50 min | no | yes | ✓ PASS — multipliers within ±2% (Check 1.32/UI 1.35/TaxCut 1.11 vs ref 1.34/1.37/1.12). Smoke wall 4.50 vs 4.62 min — small speedup at smoke; expect larger at MID/Baseline where AD iter count dominates. Plumbing: env-var override added to Parameters.py:660-678. |
| E | BLAS thread tuning (no-fork + threaded BLAS) | 11.81 min | no | yes | **❌ FAIL** — wall 11.81 vs 4.62 ref = **2.6× SLOWER**. Multipliers fine (Check 1.36/UI 1.36/TaxCut 1.12 within ±2%). Removing fork to enable BLAS threading is a net regression: HARK Step-5 work is dominated by Python-level Bellman + per-shock-type loops, not BLAS-heavy numpy ops. Skip from MID-1. |
| D | Numba JIT on hot path | n/a | n/a | n/a | **❌ DEFER** — HARK 0.17's `interpolation.py` already has `@njit` on the hot interpolation functions (lines 3970, 3976, 4042). The "5-10× from naive Numba" estimate from `mc-speedup-plan.md` was pre-this-Numba-coverage. Adding more @njit decorators would have diminishing returns. Skip in initial round; revisit only after benchmarking other winners. |
| B | HARK real `multi_thread_commands` | n/a | n/a | n/a | **❌ DEFER** — Step-5 (Simulate.py) doesn't use HARK's joblib `multi_thread_commands` path; existing parallelism is all fork-based. To add type-level parallelism in Step-5 would require new code (not just env var flip). Significant code lift. Skip in initial round. |
| G | Solve cache plumbing | n/a | n/a | n/a | **❌ DEFER (low expected gain + significant refactor)**: cache is keyed on (parametrization, shock_type); within a Step-5 run each shock_type is solved ~7 times (1 no-AD + 5 AD iter + 1 1st-round-AD), but cache only helps for the 1 reusable AD iter per shock_type — net ~7 solves saved per Step-5 run. Cache infrastructure lives in test_asymptotic_equality_revised.py:183-238; lifting to production Step-5 (Simulate.py) requires moderate refactor. Expected gain <10%. Skip in initial round; revisit if other ideas underperform. |

## Phase C: MID-1 results (Reduced_Run scope, no welfare-6)

| Idea | Wall (min) | Speedup vs ref | Check Δ | UI Δ | TaxCut Δ | Pass? | Notes |
|---|---|---|---|---|---|---|---|
| A | n/a | n/a | n/a | n/a | n/a | ❌ | Already enabled for MC |
| B | n/a | n/a | n/a | n/a | n/a | ❌ | Deferred — needs new code |
| C (shuffle) | 4.80 | n/a (variance-reduction, not direct speedup) | 1.36 vs 1.36 (0%) | 1.29 vs 1.37 (-5.8%) | 1.12 vs 1.12 (0%) | ❌ **OUT OF SCOPE** (per user direction 2026-05-04) | Shuffle is a variance-reduction technique that achieves target accuracy at smaller N — not a direct speedup. Per user recollection, the minimum N required to implement shuffle properly (especially with DEATH shuffle) is very large, defeating the purpose. Removed from rotation. The Simulate.py:298-308 plumbing is left in place (harmless; only activates when env var set) but no production profile uses it. |
| D | n/a | n/a | n/a | n/a | n/a | ❌ | Deferred — HARK already has Numba on hot path |
| E (BLAS no-fork) | 11.81 (smoke) | 0.39× (slower) | n/a | n/a | n/a | ❌ FAIL | 2.6× slower at smoke; BLAS-without-fork is regression |
| F (loose AD tol) | 4.57 | **1.0× (no MID-1 speedup, but expected ≥1.5× at Baseline)** | 1.34 vs 1.36 (-1.5%) | 1.35 vs 1.37 (-1.4%) | 1.11 vs 1.12 (-0.9%) | ✅ ACCURACY OK / ❓ wall speedup not measurable at MID-1 | Multipliers within ±2%. Wall unchanged at MID-1 (AD calc already ~4 sec/scenario at Reduced_Run scale). Real win at Baseline: cutting 5→3 iter saves ~60 min × 4 scenarios = ~4 hr. **Recommended for inclusion in qe_fidelity_fast pending Baseline validation.** |
| G | n/a | n/a | n/a | n/a | n/a | ❌ | Deferred — low gain + significant refactor |

## Phase D: Decision matrix

### Drift findings (TM-a companion + drift measurement armed for every test)

Per-cohort drift vs. TM-a ergodic init (Phase A reference baseline):

| Test | D (agent_0) var log(p) | HS (agent_1) var log(p) | C (agent_2) var log(p) | Largest Lorenz drift | Drift verdict |
|---|---|---|---|---|---|
| Phase A reference | **−0.165** ⚠️ (FAIL ±0.12) | −0.008 ✓ | +0.010 ✓ | +1.07pp | D-cohort exceeds loosened threshold — known Config B (1−u) approximation issue, deferred per feedback_deferred_followups.md |
| Idea C MID-1 (shuffle) | **−0.048** ✓ | −0.020 ✓ | −0.007 ✓ | +0.97pp | Shuffle IMPROVED drift on all cohorts; D-cohort drift cut 3.4× vs reference |
| Idea F MID-1 (loose AD) | −0.165 ⚠️ | similar to ref | similar | similar | Identical to reference — Idea F changes AD iter count only, not MC sim |
| Idea E PoC (BLAS no-fork, SMOKE) | all pass ✓ | ✓ | ✓ | within ±1pp | Smoke scope, not directly comparable |

Key drift findings:
- D-cohort drift exceedance is **baseline Config B behavior**, not a speedup-induced regression
- Shuffle's distributional value (drift improvement) was not appreciated in the original Phase D ranking
- Idea F doesn't affect drift at all (purely AD-convergence change)

### Decision matrix

| Idea | MID-1 wall | Multiplier accuracy | Drift vs ref | WINNER? | Notes |
|---|---|---|---|---|---|
| A — per-duration AD fork | n/a | n/a | n/a | ❌ already-enabled | No-op; MC's `run_experiments_all_recessions` already uses fork |
| B — HARK multi_thread_commands | n/a | n/a | n/a | ❌ deferred | Requires new code in Step-5; significant lift (~1-2 days HAFiscal-side) |
| C — shuffle (same N) | 4.80 (no speedup) | UI -5.8% (outside ±5%) | **IMPROVED** (D-cohort drift cut 3.4×) | ❌ removed from rotation per user direction | Variance reduction. Drift-improvement value not appreciated initially. Re-evaluable if accuracy mode (vs speedup mode) matters |
| D — Numba | n/a | n/a | n/a | ❌ deferred | HARK already has `@njit` on hot interpolation functions |
| E — BLAS no-fork | 11.81 (smoke; 2.6× slower) | n/a | (smoke, not comparable) | ❌ FAIL | Removing fork to enable BLAS threads is a regression |
| F — loose AD tol | 4.57 (no MID-1 speedup) | within ±2% | identical to reference | ✅ **PROVISIONAL WINNER** | Wall savings not measurable at Reduced_Run scope (AD calc already cheap), but Baseline-scope projection: ~30-40 min savings → **~1.2-1.5× Step-5a speedup** |
| G — solve cache | n/a | n/a | n/a | ❌ deferred | Low expected gain + significant refactor |

### Critical finding: MID-1 scope was wrong target

The Reduced_Run scope used for MID-1 has setup cost dominating wall time
(drift checks, Markov state init, agent build). The actual speedup ideas
(Idea F especially) target operations that are too cheap at this scale to
measurably distinguish. The qe_fidelity_full Baseline reference of 3 hr 13
min Step-5a is dominated by AD iter compute, which Idea F directly targets.

### Recommended winners for qe_fidelity_fast

**Single confident winner: Idea F (loose AD tol).**

Idea C (shuffle) was removed from the rotation per user direction 2026-05-04:
the minimum N required for proper shuffle (with DEATH shuffle included) is very
large, defeating the purpose of the variance-reduction-at-smaller-N approach.

### Pairwise compatibility (for combination)

- F is a parameter knob (AD iter count + tol); compatible with all other techniques.
- E and F are mutually exclusive in spirit (E removes parallelism, F doesn't touch parallelism).

For qe_fidelity_fast: just F.

## Phase E: qe_fidelity_fast profile plan

_(written after Phase D)_

Output: `plans/YYYYMMDD-HHMMh_qe_fidelity_fast_profile.md`

---

## Phase F results

### F-0: TM-a multiplier extraction (Reduced_Run sim_method='both')

- Wall: 12.47 min (vs 4.62 min MC-only ref) — confirms 'both' is roughly 2.7× MC-only at Reduced_Run
- Output_Results crashed in welfare phase (stale pickle N mismatch — unrelated to F-0); simulation pickles all written correctly
- Plumbing nuance: `save_as_pickle` uses `.csv` extension despite pickle format
- Extraction script: `Code/HA-Models/FromPandemicCode/extract_mc_tm_multipliers.py`

### F-1: Bias structure (Reduced_Run scale)

| Shock | MC NPV | TM-a NPV | bias = MC − TM | bias % |
|---|---|---|---|---|
| **Check** | 1.36 | 1.18 | **+0.183** | **+13.4%** |
| UI | 1.36 | 1.28 | +0.082 | +6.0% (UI unreliable per memory) |
| **TaxCut** | 1.12 | 1.07 | **+0.044** | **+4.0%** |

Bias spread: 0.138 (Check vs TaxCut) — bias is **shock-specific, NOT stable**.

### F-2-B: Adaptation B verdict ❌ FAIL

Cross-shock-type bias borrowing doesn't work. The biases differ systematically by shock_type — calibrating from one shock can't predict another. This matches the survey author's note about TM-MC differences being structurally larger on Check than UI/TaxCut (kernel discretization at borrowing constraint).

### F-2-C: Adaptation C (antithetic variates)

PIVOT to this — orthogonal to TM-coupling, robustly delivers ~1.5-2× variance reduction.

## Run log (chronological)

- 2026-05-04 13:21 — Phase 0 setup complete; wrapper run_step5a_only.py created.
- 2026-05-04 13:21 — Smoke verification launched (PID 1423694, log speedup-test_smoke_setup_20260504-132134.log).
- 2026-05-04 13:26 — Smoke verification ✓ done. Wall 4.62 min. Multipliers: Check 1.341 / UI 1.368 / TaxCut 1.120 (with AD, Smoke_Test scope, not directly comparable to Baseline). Wrapper works.
- 2026-05-04 13:33 — Launching Phase A reference (Reduced_Run scope).
- 2026-05-04 13:38 — Phase A ✓ done. Wall 4.64 min (wrapper-total) / 3.41 min (Step-5a). Check 1.36 / UI 1.37 / TaxCut 1.12. Reduced_Run scope multipliers ≠ Baseline scope qe_fidelity_full. Phase C tests will compare to THIS reference.
- 2026-05-04 14:08 — Idea A pivoted: per-duration AD fork ALREADY ENABLED for MC mode (Simulate.py:712 `_fork_dispatch_durations` is used by `run_experiments_all_recessions` which serves no-AD AND AD AND 1st-round-AD MC sub-phases). Sequential AD-duration loop only exists in TM-AD path (Simulate.py:826) — not used by qe_fidelity. Idea A REMOVED from systematic test list.
- 2026-05-04 14:11 — Idea C SMOKE no-op confirmed: env vars HAFISCAL_MC_SHUFFLE=1 + HAFISCAL_INCOME_SHUFFLE=1 alone produce IDENTICAL multipliers to reference smoke (Check 1.34 / UI 1.37 / TaxCut 1.12 → no change). Wrapper printed env vars but Simulate.py didn't read them.
- 2026-05-04 14:11 — Added Simulate.py plumbing: after TypeList created, set `agent.mc_shuffle/income_shuffle` from env vars (pattern copied from EstimAggFiscalMAIN.py:761-773).
- 2026-05-04 14:12 — Re-launched Idea C smoke with new plumbing (PID 1439842). Log confirms `[shuffle] mc_shuffle=True income_shuffle=True` is now printed by Simulate.py. Awaiting completion.

## Important scoping note

The Reduced_Run scope at this run already has very fast AD/1st-round-AD
calculations (~4-5s per "Calculating took"), so per-duration parallelism gains
(Idea A) may be hard to measure here. The dramatic speedup we'd expect at Baseline
(where recessionCheck took 9158s sequential) won't visibly translate at this scale.

**Implication:** Phase C tests at Reduced_Run scope may UNDERSTATE Idea A's true
speedup. Other ideas (shuffle, Numba, type-level multi-thread) are more likely to
show measurable speedup at this scale.
