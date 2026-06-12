# Further speedups for the full reproduce.sh workflow

**Created:** 2026-04-18
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_explore-further-speedups` (off `matsya` at commit `c2146a7e`)
**Starting state:** matsya with the MC-welfare-6 subprocess parallelism already applied (9.88× Baseline, commit `26c012f9`) and the earlier per-duration fork dispatch / 3-edType runner / Step-2 parallelization already in tree.

## Scope

The "full" reproduce.sh workflow is `do_all.py`, five steps (step 3 optional):

| Step | Script(s) | Current expected duration (Baseline) |
|---|---|---:|
| 1. Splurge estimation | `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py` | ~30 min |
| 2. Discount factor estimation | `EstimAggFiscalMAIN.py` | **~48 h** |
| 3. Robustness (Splurge=0) — optional | `EstimAggFiscalMAIN.py` with `Splurge=0` | ~48 h |
| 4. HANK/SAM Jacobians + experiments | `HA-Fiscal-HANK-SAM.py` + HANK/SAM policy runs | ~13 h |
| 5. Policy comparison | `AggFiscalMAIN.py` + `Welfare.py` | ~12 h |
| **Total (no step 3)** | | **~72 h / 3 days** |

Step 2 dominates the wall-clock budget at ≥ 65 %; step 4 and step 5 are the next two buckets. Step 1 is small. Step 3, when run, doubles the total.

**Already applied** speedups on `matsya`:
- Scenario-level subprocess parallelism on MC welfare-6 (9.88× on the welfare part of step 5).
- Per-duration fork dispatch in `Simulate.py` (helps step 5).
- 3-edType parallel runner for Phase 2 TM estimation (`f6291a74`).
- Parallelized `multi_thread_commands_fake` in step 2 estimation (`e377dfed`).

**Not yet explored** — the targets of this plan:
- Intra-step-2 parallelism of the Nelder–Mead search on (β, ∇) per education type.
- Warm-starting / caching across step 2 iterations.
- AD-tolerance and AgentCount sensitivity for step 5 production (measured small on MC welfare-6; re-measure end-to-end).
- Harmenberg neutral-measure MC (variance reduction, not parallelism).
- Numba JIT on the HARK inner simulation loop hot path.
- Step 4 (HANK/SAM) — never specifically profiled; likely the easiest large win of the three post-step-2 buckets.
- BLAS/thread-pool tuning — fork-based parallelism requires the children to use 1 thread to avoid oversubscription; verify that the parent processes aren't being similarly throttled unnecessarily.
- Disk I/O (pickling cost at fork boundaries; log-writing in hot paths).

## Approach

The plan is measurement-first. We do not implement any optimization without a profile showing where the time goes on the current codebase, and we do not declare success without a before/after measurement on a representative parametrization. Each phase is a decision gate.

## Phase 0 — Instrumentation and a baseline wall-clock profile

**Goal:** A reproducible end-to-end profile of `do_all.py` on the current matsya HEAD showing where time is spent at the sub-step granularity. This is the reference all subsequent phases are measured against.

- Run `do_all.py` end-to-end on the Baseline parametrization with `HAFISCAL_RUN_STEP_3=false`, with `hafiscal_progress.py` tracking in effect (already supports per-substep timing).
- Capture per-script CPU time (total) and wall-clock time (with the parallelism knobs enabled) for each substep.
- Capture per-process memory high-water marks to rule out memory pressure as a confound.
- Run on at least two parametrizations (Reduced_Run and Baseline) so we can cross-validate optimizations at Reduced scale before committing to Baseline runs.
- Deliverable: `plans/results_20260418_baseline-profile.md` with a per-substep table, and the raw `hafiscal_progress` JSON stored alongside.

**Estimated compute:** 72 h wall on Baseline, possibly less if some substeps can be replaced with cached outputs from recent production runs. On Reduced_Run it's probably under 2 h.

**Exit criterion:** a table mapping wall-time to (step, substep, hot file path). Any optimization targeting a < 5 % slice is de-prioritized in favor of a larger bucket.

## Phase 1 — Step 2 (EstimAggFiscalMAIN) deep dive

Step 2 is the dominant bucket (~65 % of total wall time on Baseline). Three sub-targets, ordered by expected impact:

### 1.1 Nelder-Mead parallelism

**Observation.** Step 2 estimates `(β, ∇)` per education type via Nelder–Mead. Each Nelder–Mead function evaluation solves the model at a candidate `(β, ∇)` and computes a distance to the SCF wealth distribution. Within a single Nelder–Mead step the evaluations at the trial simplex vertices are independent and can be computed in parallel.

**Action.**
1. Profile one education type's Nelder-Mead trajectory: how many function evaluations; what fraction are at "new" simplex points (parallelizable) vs "reflection/contraction" points that depend on the current best.
2. If the parallelizable fraction is ≥ 30 %, implement a `scipy.optimize`-compatible wrapper that evaluates simplex vertices concurrently via `multiprocessing.get_context('fork')`.
3. Validate numerical identity against serial (bit-identical on the final `(β, ∇)` and intermediate trajectory at a fixed seed).

**Expected speedup.** Upper bound set by simplex size (4 for a 2-parameter problem); realistic 1.5–2× on step 2 alone.

### 1.2 Warm-starting across Nelder-Mead iterations

**Observation.** Each Nelder-Mead function evaluation re-solves the economy from scratch at the trial `(β, ∇)`. The solver already supports warm-starting (propagating `cFunc` across iterations of the Krusell-Smith outer loop). If `cFunc` from a previous Nelder-Mead iteration is close to the new candidate's solution — and it usually is, because Nelder-Mead moves in small steps — warm-starting should cut solver iterations by 2–3×.

**Action.**
1. Profile solver iterations per Nelder-Mead function evaluation currently.
2. Add a `warm_cfunc` argument to the solve step and cache the previous Nelder-Mead evaluation's `cFunc`.
3. Validate numerical identity (converged `cFunc` should be identical to machine precision — warm start only changes the starting point, not the convergence point).

**Expected speedup.** 1.5–3× on step 2.

### 1.3 Steady-state / ergodic distribution caching

**Observation.** Step 2 repeatedly simulates to stationarity to compute wealth-distribution targets. For the base parametrization (no recession, no policy), the ergodic distribution depends only on `(β, ∇, ς, …)`. Within a Nelder-Mead iteration the ergodic is recomputed every time; a cache keyed on the parameter tuple could hit at later Nelder-Mead iterations that happen to revisit nearby points.

**Action.** Measure the recompute-vs-hit ratio; implement an LRU cache keyed on rounded `(β, ∇)` if the hit rate is promising.

**Expected speedup.** Uncertain — probably 1.1–1.3×, dependent on Nelder-Mead trajectory.

## Phase 2 — Step 5 (policy simulation + welfare) tightening

Step 5 is the second bucket. MC welfare-6 subprocess parallelism is already in tree (9.88× on Baseline for the welfare portion). Remaining candidates:

### 2.1 Measure the multiplier half of step 5 (TM)

Step 5 has a TM multiplier half and an MC welfare half. The welfare half has been attacked; the multiplier half has not been profiled since the a-indexed TM refactor. Profile it, identify hot buckets, apply the same scenario-level subprocess parallelism if the TM code structure supports it.

**Expected speedup.** 2–4× on the TM half.

### 2.2 End-to-end AD-tolerance and AgentCount tuning

The MC-welfare-6 measurements plan (`plans/20260418_mc-speedup-measurements.md`) found AD tolerance of 2e-2 is free at 2-decimal precision; AgentCountTotal = 5000 loses 0.03–0.05 on UI Rec=1 but saves 23 %. Those knobs are per-file defaults; in `do_all.py` step 5 they are not exposed. Wire them through so step 5 can pick `ad-tolerance 2e-2` and get ~5 % free. N-down to 5000 is a judgment call; leave as CLI-only (non-default) for now.

### 2.3 Reduce or eliminate redundant solves

Step 5 runs `AggFiscalMAIN.py` which internally has `Simulate.py` which solves the economy for each scenario. Audit whether the solver's output is cached across scenarios that happen to share `(β, ∇, ς)` and differ only in the recession / policy path; if not, add caching.

## Phase 3 — Step 4 (HANK/SAM) profile

HANK/SAM is a separate computational block (the Auclert et al. sequence-space Jacobian approach) with its own hot paths. Never been profiled. Projected 13 h on Baseline.

**Action.** Profile `HA-Fiscal-HANK-SAM.py` substeps. Likely candidates:
- Jacobian computation: embarrassingly parallel across the `T × T` grid; check if already vectorized.
- Impulse-response calculations: independent across policy scenarios.
- Cached steady-state objects reusable across perturbations.

**Expected speedup.** Unknown until profiled. Conservative estimate 2×.

## Phase 4 — Variance-reduction / algorithmic levers

These change the simulation's statistical properties, not just its run time, so each requires careful validation.

### 4.1 Harmenberg neutral-measure MC

**Strategy 1 in `mc-speedup-plan.md`; explicitly deferred there.** HARK has built-in support. The theoretical argument is that simulating under the Q-measure reduces cross-sectional variance in wealth by a factor related to the permanent-income variance, so a 5–10× smaller `AgentCountTotal` yields the same precision. On Baseline with `N = 10000` → `N = 1000–2000` is plausible without loss of precision at step 2's wealth-Lorenz target or step 5's welfare-6.

**Action.**
1. Integrate Harmenberg into HAFiscal's splurge-aware simulation. The splurge rule `c = (1−ς)cFunc(m) + ς·y` uses both `m` (normalized) and `y` (level → needs permanent income to reconstruct) — care is required that the measure change is applied consistently in both components.
2. Validate on a small parametrization by comparing aggregate moments and welfare-6 against the default-measure MC at matched precision.
3. If validated, decrement `AgentCountTotal` by 5× and re-run step 2 and step 5.

**Expected speedup.** 3–5× on steps 2 + 5 combined.

**Risk.** Medium — the splurge term complicates the measure change. Budget two weeks for validation before production use.

### 4.2 Numba JIT on the HARK inner loop

**Deferred in `mc-speedup-plan.md`** because it diverges from upstream HARK. Still defer unless a profile shows a single Python-level loop dominating; if so, reconsider with a standalone Numba-jitted replacement for that loop, monkey-patched in at run time.

## Phase 5 — Systems-level tuning

### 5.1 BLAS / thread-pool auditing

The MC welfare-6 parallelism requires `OMP_NUM_THREADS=MKL_NUM_THREADS=…=1` in children. Confirm that:
- The parent process uses all available BLAS threads when running serial phases.
- No child process is silently multi-threading and oversubscribing.
- Switching BLAS backend (OpenBLAS vs MKL vs Accelerate) changes performance meaningfully.

**Action.** Micro-benchmark the hot linear-algebra calls (interp + solver) on each BLAS backend available.

### 5.2 Pickle / fork overhead

Fork-based parallelism copies-on-write. Measure the per-child startup cost (`welfare6_scenario.py` subprocess launch); if > 5 s, consider a pre-forked worker pool rather than per-scenario subprocess spawn.

### 5.3 I/O buffering

Large pickled output files in step 5 (`cLvl_all_splurge` for 10 k agents × T periods × 12 scenarios) may be I/O-bound. Profile; consider `gzip=1` compression trade-off or on-demand recomputation.

## Cross-cutting: regression protection

Any speedup must be measured against a reference run of `do_all.py` on the matsya HEAD. A regression harness:

- Run matsya HEAD serial end-to-end on Reduced_Run; capture all `.tex` table outputs.
- After each candidate optimization, re-run on Reduced_Run and diff the `.tex` outputs at 2-decimal precision.
- Promote to Baseline only after Reduced_Run diff is within tolerance.

## Sequencing

Execute phases in order 0 → 1.2 → 1.1 → 1.3 → 2.1 → 2.2 → 3 → 4.1 → 4.2 → 5. Rationale:
- Phase 0 gives a measured ranking of where to spend effort, which may reorder the remainder.
- Within phase 1, warm-starting (1.2) has higher expected value at lower risk than Nelder-Mead parallelism (1.1).
- Phase 4.1 (Harmenberg) is the biggest remaining theoretical win but the longest validation tail; queue it once the easier wins are landed.
- Phase 4.2 (Numba) stays reserved unless phase 0 / 1 profiling shows a hot Python loop worth attacking.

## Deliverables

- `plans/results_20260418_baseline-profile.md` — phase 0 profile.
- Per-phase "before/after" measurements docs: `plans/results_20260418_step2-warmstart.md`, etc.
- Validation scripts for each optimization, alongside the existing `validate_mc_crn.py` / `validate_duration_pool.py` / `validate_solve_pool.py`.
- A final rollup doc `plans/results_20260418_full-reproduce-speedup-summary.md` giving the end-to-end before/after table and total wall-clock reduction on Baseline.

## Estimated timeline

If all phases succeed at their expected-speedup midpoints: Baseline `do_all.py` wall drops from ~72 h to ~12–18 h. A conservative estimate accounting for phase-1 risk and phase-4.1 validation: ~24–30 h, a 2.5–3× end-to-end win. This is additional to the ~10× already realized on the step-5 welfare portion.

Effort: phases 0 + 2.2 + 5 are quick (days each); phase 1 is the bulk (1–2 weeks); phase 4.1 is the longest tail (~2 weeks of validation). The full exploration is a month of focused work, but can be stopped after phase 1 if the step-2 speedup is enough for operational needs.

## Non-goals

- GPU / JAX ports.
- Upstream HARK refactoring.
- Changes to the model's economics (calibration targets, parameters, CRRA, etc.).
- Changes that would conflict with the ongoing welfare-drop investigation on the private fork (`llorracc/HAFiscal-welfare-drop-investigation`). That fork explicitly needs the 0.14.1 codebase unchanged; speedup work on this branch stays on the 0.17.0 side.
