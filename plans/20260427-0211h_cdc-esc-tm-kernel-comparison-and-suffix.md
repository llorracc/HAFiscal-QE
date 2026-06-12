# CDC↔ESC consistency: TM kernel build, TM-based comparison, then filename suffix

**Date:** 2026-04-27 (rewritten 2026-04-27 after surfacing the ESC TM kernel gap)
**Branch target:** `bug034-035-cdc-consistency-cleanup` (or successor)
**Predecessor:** `plans/20260426-1319h_BUG-034+035-cdc-step1-step2-consistency-cleanup.md` (BUG-034+035 fixes are landed)
**Note:** This file was originally scoped as "Phase A — Filename suffix for CDC vs ESC outputs." Rewritten to reflect the discovery that the TM kernel has CDC-only `_a` functions; an ESC-faithful TM kernel does not exist. Building one is now the critical-path priority because:
  - We already have CDC + ESC calibration values on disk (CDC from today's Tier 3 HS-only, ESC pre-staged from Edmund at commit `db48d328`).
  - With both calibration sets in hand, we can develop and validate the ESC TM kernel independently against ESC MC, without first re-running estimation.
  - Once ESC TM works, the CDC vs ESC comparison runs in TM mode (~hours, not ~days).
  - Filename-suffix wiring is only needed when we re-run estimation; it can wait.

## 1. Revised priority structure

| Phase | What | Why this priority | Cost |
|---|---|---|---|
| **0** | ESC TM kernel build (6 functions) | First priority — long pole, gates the whole comparison | ~1-2 weeks dev |
| **1** | ESC TM kernel validation (vs ESC MC, vs reference values) | Confirms kernel correctness before Phase 2 trusts it | ~3-5 days (mostly MC compute for the comparison anchor) |
| **2** | TM-based CDC vs ESC comparison | First scientifically meaningful CDC vs ESC comparison; uses fast TM | ~1-2 days code + hours of TM compute |
| **3** | Filename suffix wiring + Step 5 dir split (was original Phase A) | Needed only when we re-run estimation; can wait until Phase 2 dictates whether re-estimation is needed | ~4-5 hr code |
| **4** | (optional) Re-estimate ESC under MC with post-fix code | Only if Phase 2 reveals Edmund's pre-staged ESC values are stale | ~5 hr compute |
| **5** | (optional) MC mode for ESC Step 5 outputs | Only if Phase 2's TM comparison reveals MC↔TM divergence under ESC | ~6-12 hr compute per scenario |

Critical path: **Phase 0 → Phase 1 → Phase 2.** Phases 3-5 are independent of the critical path and can be slotted in around the long Phase 0 dev cycle.

## 2. Goal

Enable CDC vs ESC comparison using the fast TM-based Step 5 pipeline, so we can iterate on the comparison in hours rather than days. Filename-suffix wiring (formerly Phase A) is preserved as Phase 3 — needed only when we re-run estimation.

## 3. Pre-existing state

### 3.1 Calibration files we have

| | CDC | ESC |
|---|---|---|
| Step 1 file | `Target_AggMPCX_LiquWealth/Result_AllTarget_CDC.txt` ✅ (today: ς=0.2571, β=0.9608, ∇=0.0713) | `Target_AggMPCX_LiquWealth/Result_AllTarget_ESC.txt` (Edmund: ς=0.26718, β=0.97148, ∇=0.05892) |
| Step 2 HS file | `Results/DiscFacEstim_CRRA_2.0_R_1.01_edType1_CDC.txt` ✅ (today: β=0.8995, ∇=0.1055, GICx=4.86) | (within consolidated `DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt`: β=0.9298, ∇=0.0708, GICx=4.20) |
| Step 2 dropout/college | not yet (Tier 3 multi-cohort pending) | (within consolidated ESC file) |

We have ENOUGH calibration data to start Phase 0.

### 3.2 TM code state

`Code/HA-Models/FromPandemicCode/tm_methods.py` has THREE families of functions:

| Family | Lines | Status under CDC/ESC | Action |
|---|---|---|---|
| Legacy `_m`-indexed | ~435-1700 | **Broken under any splurge-in-budget interpretation** (collapses ξ-variance, per BUG-033) | Leave alone; not anchor for either CDC or ESC |
| CDC `_a`-indexed | ~2696-3268 (six functions: 33.4-33.9) | **CDC-only.** Asset rule `g(a,ξ) = (R/Γ)·a + (1−ς)·[ξ − cFunc(...)]` hardcoded | Keep byte-identical (preserves CDC pin tests) |
| ESC `_a`-indexed | does not exist | needs to be built | **Phase 0** |

## 4. Phase 0 — Build the ESC TM kernel

### 4.0 Math

CDC asset rule (current `_build_period_tm_a`):
```
g_CDC(a, ξ) = (R/Γ)·a + (1−ς)·[ξ − cFunc((R/Γ)·a + ξ)]
```
Reference: (eq:budget-CDC) of `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md`.

ESC asset rule (to be added):
```
g_ESC(a, ξ) = (R/Γ)·a + ξ − cFunc((R/Γ)·a + ξ)
```
Reference: (eq:budget-ESC) of same doc.

Difference: ESC drops the `(1−ς)·` factor on the `[ξ − cFunc(...)]` block. Under ESC, the splurger's `ς·ξ` consumption stays on a separate ledger and never enters the optimizer's `a`; the kernel evolves only the optimizer's per-Optimizer asset.

Note the cFunc evaluation point `m = (R/Γ)·a + ξ` is the same in both kernels — that's because under both interpretations the optimizer sees the same `m_opt`. The interpretive difference is in the BUDGET (how `a` evolves), not in the policy function evaluation.

### 4.1 Implementation approach

**Recommendation: sibling functions, not inline conditionals.**

Build six new ESC sibling functions paralleling the CDC `_a` family:

| New function | Mirrors | Diff from CDC sibling |
|---|---|---|
| `_build_period_tm_a_esc` | `_build_period_tm_a` (line 2715) | Use `g_ESC` instead of `g_CDC` (drop `(1−ς)·` factor on `[ξ − cFunc(...)]` block); a-grid interpreted as `a_opt` not `a_tot` |
| `build_tm_agg_fiscal_a_esc` | `build_tm_agg_fiscal_a` (line 2912) | Calls `_build_period_tm_a_esc` instead of CDC kernel |
| `compute_type_aggregates_tm_a_esc` | `compute_type_aggregates_tm_a` (line 2968) | Aggregator math is mostly shared, but: K/Y aggregator needs to know whether to multiply by `(1−ς)` (ESC: yes; CDC: no, BUG-034 fix); cFunc evaluation for c_actual uses ESC formula `cFunc(m_opt)` not the CDC household-bargain expression |
| `compute_period_aggregates_tm_a_esc` | `compute_period_aggregates_tm_a` (line 3082) | Same as above, per-period |
| `build_experiment_period_tm_a_esc` | `build_experiment_period_tm_a` (line 3184) | ESC asset rule in experiment-period kernel; AD/scenario-shock plumbing should be identical |
| `propagate_experiment_tm_a_esc` | `propagate_experiment_tm_a` (line 3268) | Top-level wrapper; chains the ESC builders together |

Rationale for sibling-not-conditional:
- Keeps existing CDC code byte-identical → CDC pin tests unaffected → preserves the regression safety net.
- Avoids interpretive logic spreading through the kernel (each function has one clear interpretation).
- Easier to maintain: each formula change is local to one function, not gated by a flag check.
- Phase 3 (suffix wiring) decides which family to call based on `HAFISCAL_INTERPRETATION`; the dispatch lives at one level up, not inside the kernel.

### 4.2 Dispatch layer

Outside the kernels (in `AggFiscalModel.py` or wherever the tm_a path is invoked), add an interpretation-aware dispatcher:

```python
from _interpretation import get_interpretation  # see Phase 3 helper module
interp = get_interpretation()

if interp == 'CDC':
    propagate_experiment_tm_a(...)
elif interp == 'ESC':
    propagate_experiment_tm_a_esc(...)
```

Default = CDC means existing behavior unchanged.

### 4.3 Step 0 sub-tasks

| Sub-step | What | Cost |
|---|---|---|
| 0.1 | **Sub-plan: paired code-cheat-sheet + math-cheat-sheet, with pause-and-derive for any code operation lacking explicit math justification.** See `plans/20260427-1512h_code-and-math-cheat-sheets-for-tm-a-esc.md` for the full sub-plan structure, deliverables, and equation-naming convention. The sub-plan produces (a) `code_cheatsheet_tm_a_kernel.md` with per-function operation-by-operation cross-references to labeled equations, (b) `math_cheatsheet_tm_a_kernel.md` as the reverse index, and (c) updates to the math docs to add labeled equations for any code operation discovered to lack one. Cheat-sheets become the implementation specification for 0.2-0.5 and the debugging reference for Phase 1. | ~6-9 hr |
| 0.2 | Write `_build_period_tm_a_esc` (lowest-level kernel) + unit test (`g_ESC(a,ξ)` returns correct values for hand-computed cases). Implementation works from the 33.4 entry of the code-cheat-sheet. | ~1 day |
| 0.3 | Write `build_tm_agg_fiscal_a_esc` + `compute_type_aggregates_tm_a_esc` + `compute_period_aggregates_tm_a_esc` (the static-period stack). Implementation works from 33.5-33.7 entries. | ~1-2 days |
| 0.4 | Write `build_experiment_period_tm_a_esc` + `propagate_experiment_tm_a_esc` (the experiment stack: AD, recession, Check, UI, TaxCut scenarios). Implementation works from 33.8-33.9 entries. | ~2-3 days |
| 0.5 | Wire dispatch layer in `AggFiscalModel.py` | ~30 min |
| 0.6 | Smoke test: under `HAFISCAL_INTERPRETATION=ESC`, the ESC TM kernel runs end-to-end without crashing | ~10 min compute |
| 0.7 | Commit + push (one focused commit per sub-step; per-function commits during 0.1's cheat-sheet authoring) | as we go |

**Total Phase 0 cost: ~1-2 weeks dev (now including the ~6-9 hr cheat-sheet sub-plan upfront, which removes implementation surprise risk in 0.2-0.5). No long-running compute in Phase 0; smoke test only.**

### 4.4 Risks

1. **CDC-implicit assumptions in shared code**: some plumbing might silently assume CDC's a-grid interpretation. Mitigation: search `tm_methods.py` for hardcoded `(1.0 - Splurge)` / `(1 - splurge)` patterns; flag any in non-`_a` functions for review.
2. **AD loop interaction**: the aggregate-demand recovery loop currently assumes CDC dynamics in some intermediate quantities. Mitigation: identify any AD-loop math that depends on the asset rule (vs the policy rule); these sites need ESC analogs.
3. **Numerical stability**: ESC kernel may have different convergence behavior at the edges (small `a`, large `ξ`). Mitigation: comprehensive test grid in Phase 1 that exercises corner cases.

## 5. Phase 1 — ESC TM kernel validation

### 5.0a Sub-plan: paired cheat-sheets for convergence validation

Phase 1 begins with executing the cheat-sheets sub-plan at
`plans/20260427-1656h_code-and-math-cheat-sheets-for-phase-1-convergence.md`,
analogous to the Phase 0.1 sub-plan that produced
`code_cheatsheet_tm_a_kernel.md` + `math_cheatsheet_tm_a_kernel.md`.

The Phase 1 cheat-sheets specify, for each test harness in the
cascade-gated convergence validation:
- which labeled math claim it validates (`(eq:asymptotic-rate)`,
  `(eq:cross-method-convergence)`, etc.)
- which tier (L3a/b/c/d) it runs at
- pass criterion + HALT criterion
- estimated cost

Pause-and-derive discipline applies: any convergence claim a test exercises
that lacks a labeled equation triggers derivation + addition to the
appropriate math doc (likely a new `why_convergence_validation.md`)
BEFORE the harness implementation begins.

Cost: ~5-7 hr for the sub-plan; output is the implementation specification
for steps 1.1-1.12 below.

### 5.0b Direct kernel invocation, not full pipeline

**Important constraint surfaced during Phase 0.5/0.6:** the existing
production pipeline (`Simulate.py` → `AggFiscalMAIN.py`) sets
`agent.tm_a_indexed = True` but no production caller yet invokes
`propagate_experiment_tm_a` from `tm_methods.py`. That dispatch wiring
is a pending **BUG-033 Phase 5** item, out of scope here.

Until BUG-033 Phase 5 lands, Phase 1 validation runs via **direct
kernel invocation** rather than via `./reproduce.sh --comp X
HAFISCAL_INTERPRETATION=ESC`. The smoke test at
`Code/HA-Models/FromPandemicCode/test_esc_tm_kernel_smoke.py` already
exercises this pattern: build an `AggFiscalType`, solve, then call
`build_tm_agg_fiscal_a` / `compute_type_aggregates_tm_a` /
`propagate_experiment_tm_a` directly with `interpretation='ESC'`.

This is acceptable for Phase 1 (the MC↔TM convergence claim is about
kernel-level moments, not pipeline-level outputs). It will become
a limitation only at the Phase 2 step where comparing Step-5
multipliers + welfare under each interpretation could in principle go
through `./reproduce.sh`.

### 5.0 Core validation requirement: MC↔TM asymptotic convergence

**Phase 1's exit criterion is asymptotic convergence of MC and TM to the same limit.** A single matched-RNG comparison at one (AgentCount, grid_size) configuration is insufficient — two implementations can agree at one configuration by luck while a structural bug lurks at the limit. The defensible test is convergence: as MC AgentCount → ∞ and TM grid quality → fine, both methods must approach the SAME limit value, within tolerance.

This standard already exists in the CDC codebase as a precedent:
- `Code/HA-Models/FromPandemicCode/test_mc_convergence.py` — checks whether the MC TaxCut multiplier converges to the TM reference value as N grows, with the explicit framing: *"If MC converges down → TM is correct, MC at N=2000 was noisy/biased. If MC stays up → TM has a bug we still need to find."*
- `Code/HA-Models/FromPandemicCode/test_mc_sample_size_estimation.py` — runs MC at multiple N values and extrapolates `std ∝ 1/√N` to project the N required for a target SE.

These are the templates. **The ESC TM kernel does not get to be called "validated" until it passes the analogous test.**

### 5.1 Validation layers (in order)

**Layer 1 — unit (formula correctness)**: ESC asset rule `g_ESC(a, ξ)` returns expected values for hand-computed test cases. Catches arithmetic errors in the inner-most function. ~30 min.

**Layer 2 — matched-RNG quick sanity**: ESC TM and ESC MC at one fixed (small grid, fixed AgentCount) configuration agree within loose tolerance. NOT a sufficient validation — only catches gross bugs (sign errors, dropped terms, wrong indexing). ~half day.

**Layer 3 — MC↔TM asymptotic convergence (CORE REQUIREMENT) — TIERED execution**:

The convergence test itself must be tiered from cheapest to most expensive. Each tier acts as a gate: only escalate to the next tier if the current tier shows clean convergence. Catching a kernel bug at single-cohort N=500 takes minutes; catching it at 21-type Baseline takes days.

**Configuration tiers (gate-by-gate; STOP on each failure):**

| Tier | Cohort scope | MC AgentCount sweep | TM grid sweep | Cost (compute) |
|---|---|---|---|---|
| **L3a** | single cohort (HS, edType=1) | N ∈ {500, 1k, 5k} × 5 seeds | a-grid ∈ {50, 100, 200} × ξ-grid ∈ {7} | ~1-2 hr total |
| **L3b** | single cohort (HS) — fine | N ∈ {5k, 25k} × 10 seeds | a-grid ∈ {200, 500, 1000} × ξ-grid ∈ {7, 14} | ~3-5 hr |
| **L3c** | all 3 cohorts at Reduced_Run scope | N ∈ {25k, 125k} × 10 seeds | a-grid ∈ {500, 1000} × ξ-grid ∈ {14, 28} | ~half day to a day |
| **L3d** | full Baseline (21 types) | N ∈ {125k, 500k} × 10 seeds | a-grid = 1000 × ξ-grid = 28 (single fine grid) | ~1-2 days |

Required at each tier:
- MC mean(moment | N) approaches a limit `M_MC^*` as N grows (`std/√N → 0`).
- TM moment(grid) approaches a limit `M_TM^*` as the grid refines.
- `|M_MC^* − M_TM^*| < tolerance` for each tracked moment.

**HALT criteria — at any tier:**
- MC standard error doesn't shrink as `1/√N` (suggests MC noise is non-i.i.d. — bug)
- TM doesn't stabilize across the grid sweep (suggests grid is too coarse OR kernel has a discretization-amplified bug)
- MC and TM converge to *different* limits (suggests one or both implementations have a structural bug)

In all halt cases, **stop and debug at the current tier — do NOT escalate.** Debugging at small scope is dramatically cheaper.

**Recommended scenarios:** baseline + TaxCut (mirrors `test_mc_convergence.py`). Add UI / Check / recession scenarios only at L3c+ tiers.

**Recommended calibration:** fixed throughout — Edmund's pre-staged ESC values from `Result_AllTarget_ESC.txt` + `DiscFacEstim_*_ESC.txt`. Don't re-estimate during validation.

**Tolerance:** 0.5% on K/Y and aggregate moments; 1-2% on tail-sensitive percentiles. Tighter at finer L3 tiers.

**Compute cost summary (gated escalation):** L3a passes → spend L3b time. L3b passes → spend L3c time. L3c passes → spend L3d time. Total only goes to ~2-3 days IF all preceding tiers passed; failure at L3a saves all subsequent compute.

**Layer 4 — vs Edmund's reference**: ESC TM kernel + pre-staged ESC calibration produces SCF-comparable wealth moments within tolerance of Edmund's published ESC results. Sanity that the new kernel is consistent with prior ESC work. ~1 day.

### 5.2 Same-standard CDC convergence check (precondition)

Before validating ESC against this convergence standard, **first verify the CDC kernel passes the same test**, using `test_mc_convergence.py` as the seed (extend its scope to baseline + multiplier under more grid/N configurations if needed). If CDC fails the convergence test, that's a known unknown that needs resolution before we can trust ANY MC↔TM comparison — including ESC's. Cheap to find out: ~half day.

### 5.3 Regression check for CDC kernel

After ESC sibling functions land, re-run CDC TM through the existing `_a` family. Pin tests must still pass: confirms we didn't accidentally break the CDC kernel. ~5 min compute. Independent of the convergence test in 5.2.

### 5.4 Sub-tasks

| Sub-step | What | Cost |
|---|---|---|
| 1.0 | CDC MC↔TM convergence sanity at L3a (extend `test_mc_convergence.py`) — precondition gate | ~few hr code + ~1-2 hr compute |
| 1.1 | Layer-1 unit tests for `g_ESC` | ~30 min |
| 1.2 | Layer-2 matched-RNG quick sanity | ~half day |
| 1.3 | L3 build MC sweep harness (multi-N, multi-seed, parameterized by cohort scope) | ~half day code |
| 1.4 | L3 build TM sweep harness (multi-grid, parameterized by cohort scope) | ~half day code |
| 1.5 | L3a run + analyze: single-cohort HS, small N, coarse grid | ~1-2 hr compute, ~hr analysis |
| 1.6 | L3b run + analyze: single-cohort HS, fine | ~3-5 hr compute, ~hr analysis (only if L3a passes) |
| 1.7 | L3c run + analyze: 3 cohorts at Reduced_Run | ~half day to a day compute (only if L3b passes) |
| 1.8 | L3d run + analyze: full Baseline | ~1-2 days compute (only if L3c passes) |
| 1.9 | Layer-4 reference comparison (Edmund's values) | ~1 day |
| 1.10 | CDC regression check (pin tests) | ~5 min |
| 1.11 | Phase 1 sign-off report (does ESC TM converge to ESC MC limit at all tiers? within tolerance?) | ~half day |
| 1.12 | Commit + push | as we go (commit per tier completion) |

**Total Phase 1 cost: ~5-7 days code + ~2-3 days compute IF all tiers pass cleanly. Failure at L3a/L3b saves the L3c/L3d compute. Compute is mostly background; can overlap with Phase 0 development.**

### 5.5 What "ESC TM works" means after Phase 1

- ✅ ESC TM passes Layer 3 convergence test against ESC MC → kernel is structurally correct.
- ✅ ESC TM agrees with Edmund's reference (Layer 4) → kernel is consistent with prior ESC work.
- ✅ CDC TM still passes its own pin tests (5.3) → no collateral damage.
- ✅ CDC TM also passes its own MC↔TM convergence test (5.2) → both methods are self-consistent on a baseline we already trust.

Only with all four green does ESC TM advance to Phase 2. Anything red → HALT, debug, retry.

## 6. Phase 2 — TM-based CDC vs ESC comparison

### 6.0 Critical caveats from Phase 0/0.6 findings

Two findings during Phase 0 work shape Phase 2 expectations:

**(a) `A_nrm_ESC ≠ (1-ς) · A_nrm_CDC` at the aggregate level.**
The Phase 0.6 smoke test confirmed: even though the BUG-034 fix's per-aggregator scaling (in `compute_type_aggregates_tm_a`) multiplies `A_nrm` by `(1-ς)` under ESC, the kernel ergodics ALSO differ between CDC and ESC (different asset rules → different evolution → different ergodic distribution of `a`). Net result: at the smoke test, `A_nrm_ESC / A_nrm_CDC ≈ 0.85` (not 0.74 = 1-ς). This is correct behavior; do NOT design Phase 2 comparisons assuming a simple `(1-ς)` rescaling between interpretations.

For Phase 2 sub-task 2.5 ("which moments diverge most?"), this means:
- For aggregate-level comparisons, expect non-trivial CDC↔ESC ratios that depend on the cohort + scenario, NOT a clean `(1-ς)` shift.
- Tolerances on cross-method or cross-interpretation comparisons should be calibrated to this. A "5% difference" between CDC and ESC outputs is plausibly real, not a bug.

**(b) Direct kernel invocation, not full pipeline (BUG-033 Phase 5 gap).**
Per §5.0b above, Phase 2 cannot run via `./reproduce.sh --comp full HAFISCAL_INTERPRETATION=ESC` until BUG-033 Phase 5 (production-pipeline dispatch into `propagate_experiment_tm_a`) lands. Phase 2 sub-tasks 2.1 and 2.2 below are revised to use direct kernel invocation, mirroring the smoke-test pattern in `test_esc_tm_kernel_smoke.py`.

If full-pipeline runs are needed (e.g., for `Tables/Baseline_*` regeneration that downstream LaTeX needs), BUG-033 Phase 5 becomes a hard prerequisite. Plan for Phase 2 to surface this requirement explicitly to the user, with a recommendation to schedule BUG-033 Phase 5 before any full-pipeline output regeneration under ESC.

### 6.1 What we compare

Step-5-equivalent outputs under both interpretations:

- Multipliers (UI extension, tax cuts, stimulus checks) under each interpretation — computed via direct invocation of `propagate_experiment_tm_a`
- Welfare changes by wealth percentile — using the TM-derived consumption distributions
- Aggregate consumption / asset trajectories during recession + recovery

### 6.2 Inputs

| | CDC | ESC |
|---|---|---|
| Calibration | Today's CDC values (Tier 3 HS-only + TM-a Apr-18 for dropout/college, with BUG-036-fixed dropout) | Edmund's pre-staged ESC values (or Phase 4 re-estimation if needed) |
| TM kernel | Existing CDC `_a` family with `interpretation='CDC'` | Same kernel with `interpretation='ESC'` (no sibling functions per Phase 0.2 design choice) |
| Step 5 driver | Direct kernel invocation (per §6.0(b)); not `AggFiscalMAIN.py` until BUG-033 Phase 5 lands | same |
| Outputs | Per-direct-invocation tables/figures; eventually `Tables/Baseline_CDC/` after BUG-033 Phase 5 + Phase 3.A.8 | Per-direct-invocation tables/figures; eventually `Tables/Baseline_ESC/` |

### 6.3 Sub-tasks

| Sub-step | What | Cost |
|---|---|---|
| 2.1 | Direct invocation: build agent w/ `interpretation='CDC'`, run `propagate_experiment_tm_a` for each scenario (UI/TaxCut/Check), collect aggregates | ~half day code + ~1-2 hr compute |
| 2.2 | Same for `interpretation='ESC'` (uses Edmund's calibration; mind §6.0(a) caveat) | ~half day code + ~1-2 hr compute (largely re-runs of 2.1 with different agent + interpretation kwarg) |
| 2.3 | Side-by-side comparison table (multipliers × policies × interpretations) | ~half day |
| 2.4 | Welfare-by-percentile comparison plot | ~half day |
| 2.5 | Diagnostic: which moments diverge most? Which converge? Per §6.0(a), expect non-trivial ratios that don't reduce to `(1-ς)` rescaling — interpret the divergences in terms of WHICH scenario / WHICH cohort drives them | ~1 day |
| 2.6 | Brief write-up: implications for which interpretation to publish; also: list any moments where the CDC↔ESC gap is large enough to warrant `BUG-033 Phase 5 + full-pipeline regeneration` before publication | ~half day |
| 2.7 | Commit + push | as we go |

**Total Phase 2 cost: ~1-2 days code + ~3-4 hr compute.** (Largely unchanged from prior estimate; the direct-invocation approach is roughly the same cost as a pipeline-driven approach since the comparison code has to be written either way.)

## 7. Phase 3 — Filename suffix wiring (was original Phase A)

This was the original scope of this plan; preserved here, deprioritized to after Phase 2 because:
- Tier 3 multi-cohort can run with the existing manual-`cp` Phase-C-style backup pattern (one extra `cp` round, ~30 sec).
- ESC TM kernel work doesn't write new estimation files; it reads existing calibration and writes Step 5 outputs.
- Step 5 output dir split (Q4) IS needed for Phase 2; pull it forward to Phase 2 if needed.

### 7.1 Design decisions (resolved 2026-04-27)

1. **Configuration mechanism: BOTH env var and CLI flag.** Resolution precedence: CLI flag > env var > default `CDC`. Estimation scripts gain `--interpretation CDC|ESC`; wrapper scripts read env var.

2. **Pre-staged `_ESC` files: rename.** Consolidated `DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt` → `..._ESC_legacy_consolidated.txt`. New ESC runs adopt per-edType naming.

3. **Filename suffix (not separate output dirs)** for calibration files.

4. **Step 5 outputs: directory split.** `Tables/Baseline/` → `Tables/Baseline_CDC/` + `Tables/Baseline_ESC/`. Pulled forward to Phase 2 if Step 5 outputs need to be cleanly separated for the comparison.

### 7.2 Sub-tasks (was Phase A.1 - A.8)

| Sub-step | What | Cost |
|---|---|---|
| 3.1 | `Code/HA-Models/_interpretation.py` helper module + unit test | ~30 min |
| 3.2 | Wire writers (Estimation_BetaNablaSplurge.py + EstimAggFiscalMAIN.py): suffix injection at write sites | ~45 min |
| 3.3 | Wire 11 readers with backward-compat fallback | ~1 hr |
| 3.4 | Conditionalize 12 BUG-034/035 sites | ~30 min |
| 3.5 | Pin tests: update CDC, add ESC | ~30 min |
| 3.6 | Smoke validation under each `HAFISCAL_INTERPRETATION` value | ~10 min |
| 3.7 | Step 5 dir split (formerly A.8) — may be pulled forward to Phase 2 | ~1 hr |
| 3.8 | Commit + push (one commit per sub-step) | as we go |

**Total Phase 3 cost: ~4-5 hr code, no compute.**

### 7.3 Affected files (writers / readers / sites)

(Same lists as the original Phase A scoping — preserved for reference.)

**Writers:**
- `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py:785–818` — `/Result_AllTarget*.txt` write paths
- `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py:1169–1194` — `df_resFileStr` construction

**Readers (must look for suffixed first, fall back un-suffixed):**
- `Code/HA-Models/FromPandemicCode/EstimParameters.py:8` — `_SPLURGE_RESULT`
- `Code/HA-Models/FromPandemicCode/Parameters.py:39, 68` — Splurge_txt_location
- `Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py:54–63` — `CDC_CALIBRATION_PINS`
- `Code/HA-Models/FromPandemicCode/estim_phase2_tm.py` — DiscFacEstim reads
- `Code/HA-Models/FromPandemicCode/estim_phase2_tm_a.py` — DiscFacEstim reads
- `Code/HA-Models/FromPandemicCode/run_phase2_parallel.py`
- `Code/HA-Models/FromPandemicCode/launch_track_a_prime.sh`
- `Code/HA-Models/full_reproduction_orchestrator.py:92–93`
- `Code/HA-Models/full_compare.py:60–61`
- `Code/HA-Models/compare_versions.py:46–47`

**Conditionalize BUG-034/035 sites:**
- `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py` — 11 sites (lines 117, 132, 140, 170, 175, 203, 287, 296, 415, 428, 432)
- `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py:104` — `BaseType` class selection

**New tests:**
- `Code/HA-Models/FromPandemicCode/test_esc_baseline_pin.py`

## 8. Phase 4 (optional) — ESC re-estimation under MC with post-fix code

Triggered only if Phase 2 TM comparison reveals that Edmund's pre-staged ESC values (from `origin/maintain_bound_pair_fix_splurge`) are stale relative to current ESC code semantics. ~5 hr compute.

## 9. Phase 5 (optional) — MC mode for ESC Step 5 outputs

Triggered only if Phase 2 TM comparison reveals MC↔TM divergence under ESC that wasn't expected. ~6-12 hr compute per scenario.

## 10. Open questions

1. **AD loop under ESC**: does the aggregate-demand recovery loop's intermediate-quantity math depend on the CDC asset rule, or only on the policy rule? Need to audit during Phase 0.5. If yes, AD loop needs ESC-specific math too.

2. **Welfare aggregator under ESC**: per `models_CDC_and_ESC.md` and Edmund's Apr 23 clarification, welfare = `u(cLvl_splurge / pLvl)` is interpretation-INDEPENDENT. Confirm this still holds under the new ESC TM kernel before Phase 2's welfare comparison.

3. **Cross-validation reference data**: do we have an external reference (Edmund's plots, prior published numbers) that ESC TM Step-5 outputs can be compared against, beyond just CDC TM and ESC MC? Helpful for catching subtle bugs.

4. **Phase 2 timing relative to Tier 3 multi-cohort**: Tier 3 multi-cohort (Step 2 for edType=0,2 under CDC) can run in background during Phase 0. By the time Phase 0 finishes (~1-2 weeks), CDC will have all 3 cohorts; ESC will have Edmund's all-3-cohort consolidated values. Both ready for Phase 2 simultaneously. Recommend kicking off multi-cohort now in background as parallel work.

## 11. Reference docs

- `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md` — math definitions of CDC and ESC
- `plans/20260425-2102h_cdc-implementation-map.md` rows 33.4-33.9 — list of CDC `_a` functions with ESC analog notes
- `plans/20260423-1934h_estimate-ESC-in-parallel.md` — earlier scoping (predates this plan)
- `plans/20260425-2137h_cdc-esc-configurable-refactor.md` — earlier scoping (predates this plan)
- `BUGS_private/HAFiscal_BUG-033_*.md` — original BUG-033 work that established the `_a`-indexed kernel

## 12. BUG-033 Phase 5 — production-pipeline dispatch (out of scope here, but explicitly flagged)

The plan above (Phase 0 through Phase 5) builds an interpretation-aware TM-a kernel chain at the function-API + agent-attribute level, validates it via direct kernel invocation (Phase 1), and produces CDC↔ESC comparisons via direct invocation (Phase 2). All of this **bypasses** the production pipeline (`Simulate.py` → `AggFiscalMAIN.py` → ... → `propagate_experiment_tm_a`).

The reason: `Simulate.py:294-297` propagates the `tm_a_indexed` flag to agents but **no production caller actually invokes `propagate_experiment_tm_a` from `tm_methods.py`**. That dispatch wiring was BUG-033 Phase 5, which has not landed yet.

This affects:
- **`./reproduce.sh --comp <scope> ...`** runs cannot use the TM-a kernel chain (CDC or ESC) until Phase 5 lands.
- **`Tables/Baseline_*` regeneration** (which downstream LaTeX consumes) requires Phase 5 to be wired before any interpretation can drive it.
- **Full-paper compute reproducibility under each interpretation** requires Phase 5.

For Phase 1 (kernel validation) and Phase 2 (CDC↔ESC moment comparison), direct kernel invocation is sufficient and preserves the cascade-gating discipline. For anything beyond — anything that the paper depends on regenerating from scratch under each interpretation — BUG-033 Phase 5 becomes a hard prerequisite.

Recommended sequence if production-pipeline regeneration is needed:
1. Complete Phase 1 (validates the kernel chain works at the function level).
2. Complete Phase 2 (CDC↔ESC comparison via direct invocation; quantifies whether the interpretation choice meaningfully shifts published outputs).
3. **IF Phase 2 reveals meaningful shifts** that warrant ESC-side full-pipeline regeneration → schedule BUG-033 Phase 5 (wire the production dispatch).
4. **IF Phase 2 reveals shifts are within tolerance for paper purposes** → BUG-033 Phase 5 can stay deferred; ESC results are reported as direct-invocation supplements.

This sequencing means BUG-033 Phase 5 is a CONDITIONAL follow-up, not an unconditional prerequisite. Phase 2 is the gate that determines whether to invest in it.
