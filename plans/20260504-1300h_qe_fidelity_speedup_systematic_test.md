---
date: 2026-05-04
status: plan-draft
keywords: [speedup, MC, parallelism, shuffle, numba, multi-threading, qe_fidelity, benchmark]
related_bugs: []
related_plans:
  - 20260401-1717h_mc-speedup-plan.md
  - 20260408-1024h_minimum-replicates-for-shuffle.md
  - 20260408-1213h_single-cohort-plus-shuffle-implementation.md
  - 20260409-1238h_mc_only_speedups.md
  - 20260418-1441h_explore-further-speedups.md
related_conclusions:
  - 2026-05-04_qe_fidelity_full_vs_QE_published.md
---

# Systematic test of speedup ideas for qe_fidelity-style runs

## Goal

**Ultimate deliverable: a `qe_fidelity_fast` profile** that reproduces the qe_fidelity_full
**multipliers** (Check 1.216, UI 1.178, TaxCut 0.992) within ±3% in **dramatically less
wall time** than the 4 hr 9 min Step-5 reference.

To get there: measure the wall-time speedup (and multiplier-accuracy delta) of each
individually-applicable MC speedup technique against a fixed reference (the
qe_fidelity_full Step-5a configuration), then implement a combined `qe_fidelity_fast`
profile that bundles the winners.

**No re-estimation in scope.** All tests use the existing qe_fidelity_full β/∇/GICx
estimates (`Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt`, commit
`c6935969`) and the existing `Result_AllTarget_ESC.txt` splurge.

**Welfare is OUT OF SCOPE.** Per user direction (2026-05-04): accurate welfare
measurement requires much larger AgentCount than these speedup tests use. Do NOT
run Step-5b (`run_welfare6_parallel.py`) in any test, and do NOT compare against
the reference welfare-6 numbers. The qe_fidelity_fast profile will explicitly
exclude welfare; users wanting welfare must continue to use the slow accurate
qe_fidelity profile (which already runs welfare-6 with full N).

## Why this exists

The qe_fidelity_full reference run took 9 hr 51 min wall (Step-2 5h36 + Step-5a
3h13 + Step-5b 56min). The Step-5 portion alone — the bulk of any future
"reproduce-QE" run when estimates are already on disk — was ~4 hr 9 min and was
dominated by serial bottlenecks that we have multiple plausible techniques to
attack.

A side-by-side benchmark of each technique, validated against the qe_fidelity_full
multipliers, is needed before committing to a combined-speedup implementation.

## Reference benchmark (Phase A output)

**The reference run** is qe_fidelity_full **Step-5a only** (welfare omitted per
out-of-scope), re-run from the saved estimates (no Step-1 / Step-2). Concretely:

```
HAFISCAL_INTERPRETATION=ESC \
HAFISCAL_PERM_DURING_UNEMP=off \
HAFISCAL_SIM_METHOD=MC \
HAFISCAL_TM_A_INDEXED=1 \
HAFISCAL_TM_A_CACHE=1 \
HAFISCAL_DRIFT_HARD_FAIL=0 \
PYTHONUNBUFFERED=1 \
python AggFiscalMAIN_reduced.py --baseline
# NOTE: do NOT invoke run_welfare6_parallel.py — welfare out of scope per user
```

**Reference numerical outputs** (multipliers only; welfare ignored throughout):

| Multiplier (with AD) | Check | UI | TaxCut |
|---|---|---|---|
| qe_fidelity_full | 1.216 | 1.178 | 0.992 |

**Reference wall time:** Step-5a alone took 3h13m in the qe_fidelity_full run.
This is the wall-time target for the speedup measurements.

A speedup technique is a **WINNER** if it achieves ≥ 1.5× wall reduction on its
applicable scope **AND** produces **multipliers** within ±3% of the reference
(or within ±5% if the technique is a documented variance-reduction method like
shuffle that has known small-N bias). Welfare numbers are NOT compared.

## Test parametrizations

To keep iteration cheap, three parametrizations are used:

### 🟢 SMOKE (Phase B)
- Existing `Smoke_Test` parametrization in `Parameters.py` (AgentCountTotal=100, T_sim=22, act_T=100, num_max_iterations_solvingAD=5)
- Used **only** for crash-test / smoke validation of each speedup
- Wall: ~5-15 min for full Step-5
- **Pass criterion:** runs to completion, produces a Multiplier.tex with non-NaN values

### 🟡 MID (Phase C) — initial round uses MID-1 only

**MID-1: Single shock-type, full AgentCount** (the user's example "single-agent, no-AD, but full AgentCount" generalized)
- Use existing `Reduced_Run` parametrization (AgentCountTotal=5,000, act_T=100) but **patch to single shock_type** (just `recessionCheck` — the slow holdout)
- Skip welfare-6 (Step-5b) for these tests
- Wall: should be ~30-60 min on reference; ~5-30 min for working speedups
- **Pass criterion:** Check multiplier within ±3% of qe_fidelity_full's 1.216

**MID-2 (DEFERRED to follow-up round, NOT in initial systematic test):** All 4
recession shock_types, single cohort (HS_Only), no-AD only. Useful later for
testing per-shock-type fork quality, but not required for the initial winner-set
identification.

### 🔴 FULL (only for the combined plan, NOT individual ideas)
- Full Baseline qe_fidelity Step-5 (same as the reference run)
- Used only after all winners are identified to validate the combined implementation
- Wall: target ≤ 1 hr (vs the 4h09m reference)

## Speedup ideas to test

### Idea A: Per-duration fork on AD scenarios 🌟 (BIGGEST EXPECTED WIN)

**What:** Apply `_fork_dispatch_durations` (already in `Simulate.py`) to the
AD-effects code path (`run_experiments_all_recessions_ad_tm` line 798 +
`solve_ad_recession` per-iter loop), which today runs 21 duration variants
sequentially per AD iteration.

**Why expected to work:** No-AD already uses this fork (lines 712, 771); same
pattern. The AD code does have CFunc state shared across iterations, but within
one iteration the 21 duration variants are independent given the current CFunc.

**Quick PoC (Phase B):**
- Add fork dispatch to `solve_ad_recession`'s inner duration loop
- Run SMOKE scope with 1 shock_type
- **Pass:** completes, output non-NaN, wall comparable to non-AD smoke
- **Pre-test:** confirm CFunc isolation across fork children (the children share
  parent's CFunc but each child has its own modifications discarded — this is
  how no-AD already works)

**Mid-sized test (Phase C):**
- MID-1 (single shock_type recessionCheck, full Reduced N)
- Measure: wall time, Check NPV multiplier, NPV iteration count
- **Pass:** wall ≥ 3× faster than reference single-shock recessionCheck;
  Check multiplier within ±3% of qe_fidelity_full's 1.216

**Risk:** AD CFunc convergence might depend on duration ordering (e.g., t=0
result feeds into t=1's starting CFunc). Need to read the iter loop carefully
before committing to fork.

---

### Idea B: HARK real `multi_thread_commands` for Step-5 type-level parallelism

**What:** Today we force `multi_thread_commands_fake` (sequential) via
`HAFISCAL_SERIAL=1`. The real version uses joblib to solve all 21 types
concurrently. We forced fake because the real one OOMs after hundreds of NM
evaluations in Step-2. Step-5 has no NM loop, so the OOM concern doesn't apply.

**Why expected to work:** Solving 21 types is the dominant inner cost of each
shock_type's no-AD/AD computation. Type-level parallelism could give 5-10×
speedup on a 32-core machine if the joblib spawn cost is amortized over enough
evaluations.

**Quick PoC (Phase B):**
- Set `HAFISCAL_SERIAL=0` for Step-5 only (Step-5a doesn't need it false in
  Step-2 path since Step-2 is skipped for our purposes)
- Run SMOKE scope
- **Pass:** completes, output non-NaN, no OOM during the run
- **Watch:** memory high-water mark — if it grows linearly with eval count
  (joblib worker leak), the technique is unsuitable

**Mid-sized test (Phase C):**
- MID-1 (single shock_type recessionCheck, full Reduced N) — initially with this idea
  ON in isolation; the per-shock-type fork already exists in current code, so the
  comparison is "type-level joblib parallelism within one shock_type vs single-thread
  within one shock_type"
- Measure: wall time, Check multiplier, peak RSS (watch for OOM)
- **Pass:** wall ≥ 2× faster than reference; Check multiplier within ±3%
- **Decision:** monkey-patch HARK in this codebase per user direction (no upstream PR for this experiment)

**Risk:** OOM. If observed, technique is dead unless we fix joblib re-import
behavior upstream.

---

### Idea C: Variance-reduction shuffle (HAFISCAL_MC_SHUFFLE + HAFISCAL_INCOME_SHUFFLE)

**What:** Replace stochastic Markov-state transitions and per-period income-shock
draws with deterministic ones that match expected frequencies. Lets us achieve
target accuracy at smaller N. Per
`plans/20260408-1213h_single-cohort-plus-shuffle-implementation.md`: at N=1500
per cohort + shuffle, "MC sampling variance on per-period AggCons essentially zero".

**Why expected to work:** N=10,000 in qe_fidelity → if shuffle lets us drop to
N=1,500 (same per-cohort minimum-occupancy) total simulation cost drops 6.7×.
Speedup is in N, not in walls of compute organization.

**Quick PoC (Phase B):**
- Set `HAFISCAL_MC_SHUFFLE=1 HAFISCAL_INCOME_SHUFFLE=1` at SMOKE scope
- **Pass:** completes, output non-NaN, log shows `[shuffle] mc_shuffle=True income_shuffle=True`
- **Watch:** crashes (shuffle requires minimum-occupancy thresholds; SMOKE's N=100
  may be below threshold for HS/C cohorts. May need HS_Only for the PoC)

**Mid-sized test (Phase C):**
- MID-1 with HAFISCAL_MC_SHUFFLE=1 + HAFISCAL_INCOME_SHUFFLE=1 at the existing
  Reduced_Run N=5,000 (above the per-cohort minimum-occupancy threshold for HS,
  marginal for D)
- Measure: wall time, Check multiplier
- **Pass:** wall ≥ 2× faster than MID-1 reference (same N, shuffle is variance
  reduction so wall savings come from removing stochastic-draw cost); Check
  multiplier within ±5% of qe_fidelity_full's 1.216 (variance-reduction
  technique with documented small-N bias gets wider tolerance)
- **Note on N reduction:** the bigger speedup from shuffle would come from
  reducing N (e.g., to 1,500 per cohort). That requires re-running at MID-1 with
  N=1,500 — also test this in Phase C as a paired sub-test, since the headline
  speedup story for shuffle is "tighter accuracy at smaller N"

**Risk:** shuffle changes the random seed effectively; small numerical drift
expected. Acceptable up to ±5% (variance-reduction technique with known small-N
bias) per pass criterion.

---

### Idea D: Numba JIT on HARK simulation hot path

**What:** Add `@numba.njit` decorators to HARK's `interpolation._evaluate` and
related inner-loop functions. Per `plans/20260401-1717h_mc-speedup-plan.md`,
profiled at 364 sec (~25% of MC simulate time at smoke scale).

**Why expected to work:** Pure Python interpretation overhead in the inner-most
agent simulation loop is ~10-50× slower than equivalent C/Numba. Numba can
typically claim 5-10× of that.

**Quick PoC (Phase B):**
- Identify the single hottest function (probably HARK's `_evaluate` or
  `simulate`'s `sim_one_period`)
- Numba-decorate it (carefully — Numba requires some refactoring for type stability)
- Run SMOKE scope
- **Pass:** completes, multipliers match scipy-reference within numerical noise
  (~1e-6)
- **Watch:** numba compilation time — first run will include JIT compile cost
  (~5-30s); the speedup measure must be from a warm-cache run

**Mid-sized test (Phase C):**
- MID-1 (single shock_type recessionCheck, full Reduced N) with Numba
- Measure: warm-cache wall time, Check multiplier
- **Pass:** wall ≥ 2× faster than reference; Check multiplier within ±0.5%
  (numerical-precision-only deviation expected)

**Risk:** HARK is upstream code. Numba'ing it requires either:
1. Monkey-patching at process start (intrusive)
2. Forking HARK (maintenance burden)
3. Contributing upstream (depends on HARK maintainers' acceptance)
For this experiment, monkey-patch is acceptable per user direction (no upstream
HARK PR required for this test cycle). Long-term path is upstream PR after the
fast profile is validated.

---

### Idea E: BLAS thread tuning

**What:** Today, fork-based parallelism forces children to use single-thread BLAS
(`OPENBLAS_NUM_THREADS=1` etc.) to avoid oversubscription. The PARENT processes
(orchestrating bash, do_all.py, etc.) could use multi-threaded BLAS during
inactive child phases.

**Why expected to work:** Marginal at best — most of the real numpy work happens
in child processes which would still need to be single-threaded. The parent
cost is small.

**Quick PoC (Phase B):**
- Run SMOKE scope with `OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8` set globally,
  but `HAFISCAL_NO_FORK=1` (sequential mode) so we measure the BLAS speedup not
  oversubscription artifacts
- **Pass:** completes, no-fork result identical to reference

**Mid-sized test (Phase C):**
- MID-1 + multi-threaded BLAS but **fork ON**
- Measure: wall time, peak load average (oversubscription indicator)
- **Pass:** wall ≥ 1.2× faster than reference AND no load-average pathology
- **Failure mode:** load > 64 (2× cores) suggests oversubscription; reject

**Risk:** Lower-priority idea (~1.1-1.3× best case). Test only if other ideas
underperform.

---

### Idea F: Loose AD convergence tolerance

**What:** `solve_ad_recession`'s `convergence_cutoff` defaults to 1e-3 (per
AggFiscalModel.py:1976 signature). Loosening to 1e-2 would cut AD iters from
~5 to ~3.

**Why expected to work:** The 1e-3 vs 1e-2 difference manifests as a 1% CFunc
shift, which likely propagates to <0.1% in NPV multipliers. Already partially
tested in MC welfare-6 speedup work (`plans/20260418-1237h_mc-speedup-measurements.md`).

**Quick PoC (Phase B):**
- Run SMOKE scope with hardcoded convergence_cutoff=1e-2 (patch in
  AggFiscalModel.py line ~1976 or via env override if one exists; create one
  if not)
- **Pass:** completes, multipliers within ±0.5% of SMOKE-reference

**Mid-sized test (Phase C):**
- MID-1 with loose tolerance
- Measure: wall time, AD iter count (should drop ~40%), multipliers
- **Pass:** AD iters reduce 30-50%; multipliers within ±1% of qe_fidelity_full

**Risk:** Low. This is a tunable knob without architectural change.

---

### Idea G: HARK's `_solve_one_period` Bellman cache (HAFISCAL_NO_SOLVE_CACHE)

**What:** `Code/HA-Models/FromPandemicCode/test_asymptotic_equality_revised.py:183`
references a `SOLVE_CACHE` keyed on (parametrization, shock_type) → list of
agent.solution deepcopies. Today this is enabled by default in test code (env
var `HAFISCAL_NO_SOLVE_CACHE=1` disables it). Need to confirm whether
`AggFiscalMAIN_reduced.py` uses this cache or not — if not, plumbing it in
could save substantial Bellman-solve time.

**Why expected to work:** Per the MC speedup profile (`plans/20260401-1717h_mc-speedup-plan.md`),
Bellman solves dominate at ~70% of MC cost. If consecutive shock_types repeat
the same Bellman solve (same agent params), caching avoids re-solving.

**Quick PoC (Phase B):**
- Read `test_asymptotic_equality_revised.py` to understand the cache structure
- Determine whether the cache key/hit pattern applies to `AggFiscalMAIN_reduced.py`
- If yes, plumb in cache for SMOKE scope test
- If the cache infrastructure is purely test-only and doesn't apply, skip this idea

**Mid-sized test (Phase C):**
- Only if PoC succeeds. MID-1, measure cache hit rate + wall time.
- **Pass:** cache hit rate ≥ 30%; wall ≥ 1.5× faster

**Risk:** Cache may not apply outside test path; dead idea if so.

---

## Work breakdown

### Phase 0: Setup (~30 min wall)
1. Add a one-off script `Code/HA-Models/FromPandemicCode/run_step5a_only.py` that:
   - Skips Step-1 + Step-2 entirely
   - Reads the existing `DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt` for β/∇/GICx
   - Invokes ONLY `AggFiscalMAIN_reduced.py --baseline` (Step-5a multipliers)
   - **Does NOT invoke `run_welfare6_parallel.py`** — welfare out of scope
   - This avoids 6 hr of Step-2 re-estimation + 1 hr of welfare-6 each test cycle
2. Verify the baseline reference: re-run `run_step5a_only.py` once on current code, confirm multipliers match qe_fidelity_full (Check 1.216, UI 1.178, TaxCut 0.992)
3. Set up a simple results-table file `plans/results_20260504_speedup-test-matrix.md` to track PoC + mid-test outcomes per idea

### Phase A: Reference benchmark establishment (~1-2 hr wall)
- Run `run_step5a_only.py` once at the **MID-1** scope (Reduced_Run + single shock_type recessionCheck) to get the per-shock-type reference wall time and multiplier
- Skip MID-2 in initial round per user direction
- Run uses the EXISTING qe_fidelity_full estimates (no Step-2)
- Run skips welfare-6 (Step-5b)
- Record reference numbers in the results-table file

### Phase B: Quick PoCs (~2-4 hr wall total — most ideas ~5-15 min each)
For each idea A through G:
1. Implement the speedup at SMOKE scope (smallest possible diff to existing code)
2. Run SMOKE
3. Pass/fail check per idea-specific criteria
4. Record outcome + wall time + any errors in the results-table file
5. If FAIL: note why, decide whether to skip mid-sized or fix and retry

Ideas that pass PoC graduate to Phase C.

### Phase C: Mid-sized tests (~2-6 hr wall total per idea, depending on which mid-test applies)
For each idea that passed PoC:
1. Implement at MID-1 scope (single shock_type recessionCheck, full Reduced N=5,000, no welfare-6) — per user direction, MID-2 deferred to follow-up round
2. Run mid-sized test
3. Compare wall time and Check multiplier to the MID-1 reference from Phase A
4. Record speedup factor + accuracy delta in results-table

Ideas that achieve **≥ 1.5× speedup AND multipliers within ±3%** (or ±5% for shuffle) are WINNERS.

### Phase D: Decision matrix (no compute, ~30 min)
- Compile results table
- Score each idea: speedup × accuracy preservation
- Identify pairwise compatibility:
  - Idea A (per-duration fork) + Idea B (multi_thread_commands type-level fork) — may oversubscribe
  - Idea A + Idea C (shuffle) — independent, stackable
  - Idea D (Numba) + everything — independent, stackable
  - Idea E (BLAS threads) + fork-based ideas — likely conflict (oversubscription)
- Rank winners by expected combined gain

### Phase E: qe_fidelity_fast profile plan (separate plan document)
**Output:** a NEW plan file `plans/YYYYMMDD-HHMMh_qe_fidelity_fast_profile.md` that
specifies how to land a `qe_fidelity_fast` profile in `reproduce.sh`:

1. Lists the WINNERS from Phase D — the combination of speedups that get bundled
2. Specifies what `reproduce.sh --profile qe_fidelity_fast` will do:
   - Inherit qe_fidelity's methodology env vars (ESC, perm_shocks=off, NM tol 1e-4, legacy GICx)
   - Add the speedup env vars / code paths from the winners
   - **Explicitly skip welfare-6** (welfare requires larger AgentCount than these
     speedups support — users wanting accurate welfare must use slow qe_fidelity)
   - Document the multiplier-only output guarantee
3. Identifies any additional engineering needed for safe combination
   (e.g., dynamic worker pool that respects fork + thread oversubscription)
4. Defines a single FULL-scope test against the qe_fidelity_full multipliers reference
   (Check 1.216, UI 1.178, TaxCut 0.992 ± 2%)
5. Schedules the FULL-scope `qe_fidelity_fast` validation run

Note: Phase E PRODUCES a plan, not an implementation. The `qe_fidelity_fast`
profile addition to reproduce.sh + final FULL test is its own subsequent work.

## Pass/fail criteria summary

| Phase | Pass criterion |
|---|---|
| Phase B (smoke) | Runs to completion, multipliers non-NaN, no OOM |
| Phase C (mid) | Wall ≥ 1.5× faster than reference AND multipliers within ±3% (or ±5% for shuffle) |
| Phase D | Identify ≥ 2 winners with stackable speedups |
| Phase E | Plan document exists; FULL test specification clear |

## Out of scope

- **Welfare** (Step-5b, `run_welfare6_parallel.py`): per user direction, accurate
  welfare measurement requires much larger AgentCount than this speedup work
  uses. The qe_fidelity_fast profile will skip welfare. Welfare numbers are NOT
  compared in any test. Users wanting welfare continue to use slow qe_fidelity.
- **Re-estimation**: Step-1 splurge and Step-2 β/∇/GICx use existing
  qe_fidelity_full values. No NM iterations in any test.
- **GPU**: hardware doesn't have it.
- **Step-2 parallelism techniques** (NM simplex parallelism, cFunc warm-start
  across NM iters): out of scope per "no re-estimation" constraint.
- **HANK/SAM** (Step-4): out of scope.
- **Robustness Step-3** (Splurge=0): out of scope.

## Tracking

Results table will live at `plans/results_20260504_speedup-test-matrix.md`.
That file gets updated incrementally as each test completes — it's the
single source of truth for which speedups won.

## Estimated total wall time for the test plan

- Phase 0: 30 min (setup)
- Phase A: ~1-2 hr (single reference run, MID-1 scope)
- Phase B: ~3-4 hr (7 quick PoCs)
- Phase C: ~5-8 hr (MID-1 tests for 5-7 PoC-pass ideas, sequentially)
- Phase D: 30 min (decision)
- Phase E: 1 hr (write the qe_fidelity_fast profile plan)

**Total: ~12-16 hr wall** for the full systematic test (initial round, MID-1 only).

If we want faster turnaround within this scope:
- Run Phase B PoCs in parallel where possible (most are small enough that 2-3 can fit on the box concurrently)
- Defer MID-2 follow-up round (already done per user direction)

## Resolved scoping decisions (2026-05-04)

Per user direction:
- **Welfare**: out of scope; ignore everywhere (Step-5b never runs in tests, welfare numbers never compared)
- **Pass criterion**: ±3% on multipliers (was ±2%)
- **MID-2**: deferred to follow-up round; initial systematic test uses MID-1 only
- **Ideas E (BLAS) + G (solve cache)**: NOT skipped; included in initial round
- **Idea B (HARK multi_thread_commands)**: monkey-patch in this codebase OK
- **Idea D (Numba)**: monkey-patch in this codebase OK
- **Phase E output**: test plan only (no production-default recommendation included)
- **Ultimate deliverable**: a `qe_fidelity_fast` profile in reproduce.sh that
  reproduces qe_fidelity_full multipliers within ±3% in dramatically less wall
  time, explicitly skipping welfare
