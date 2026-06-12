# MC welfare-6 speedup: plan + measurements

**Date:** 2026-04-18
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_MC-speedup-attempt`
**Scope:** Speed up the MC welfare-6 computation that dominates the
post-bugfix HAFiscal pipeline (`run_hybrid_welfare6.py`, ~5 h 45 min
serial on Baseline CRRA2). No changes to `Simulate.py`,
`AggFiscalModel.py`, `Parameters.py`, or any other existing file —
everything is added as new scripts, with process-local monkey-patches
where needed. The explicit goal is that the work can be folded back
into `run_hybrid_welfare6.py` later without any merge conflict.

## Relationship to prior plans

Two earlier plans covered overlapping territory:

- **`plans/20260401-1717h_mc-speedup-plan.md` (2026-04-01)** — broad strategy on an
  Intel i9-13900K / 32-thread / RTX 4080 machine: Harmenberg
  neutral-measure (5–10×), CPU parallelization of types/durations/seeds
  (4–8×), Numba JIT, GPU, combined 20–50×.

- **`plans/20260409-1238h_mc_only_speedups.md` (2026-04-11)** — tactical: add per-duration
  `os.fork` dispatch inside `Simulate.py`'s
  `run_experiments_all_recessions`, building on the already-in-place
  7-way shock-type outer fork. Projected 6–12 h → 2–4 h. Explicitly
  **defers** per-type Bellman parallelism ("too tightly coupled to the
  shared CFunc within an AD iteration") and AD tolerance changes
  ("would alter convergence tolerance — defer").

This plan diverges from both on two dimensions:

1. **Entry point.** We target `run_hybrid_welfare6.py` (the MC-only
   welfare-6 runner used by the hybrid pipeline after the bugfix),
   not `Simulate.py`. The hybrid pipeline runs this script as its
   welfare step (TM handles multipliers); this is the
   post-a-indexed-TM bottleneck of the full paper-reproduction flow.

2. **Don't-modify-existing-code constraint.** To avoid any chance of
   merge conflicts with the other machine doing Phase 6 welfare runs,
   every optimization lands as a new file plus process-local monkey-patches.
   The net code budget is ~1000 lines of new code and zero edits.

## Hardware context

- CPU: Apple Silicon (M-series), **16 physical cores**, no hyperthreading
  (16 logical == 16 physical).
- RAM: 64 GB unified memory.
- BLAS: Apple Accelerate / VecLib via numpy. The Accelerate BLAS
  (`VECLIB_MAXIMUM_THREADS`) and OpenMP/MKL thread pools default to
  multi-threaded, so fork-based parallelism must set all of
  `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
  `VECLIB_MAXIMUM_THREADS`, `NUMEXPR_NUM_THREADS` to 1 **before any
  numpy-using import** to avoid child oversubscription.

## Profile of serial `run_hybrid_welfare6.py` at Baseline CRRA2

Established by a one-shot serial run with per-phase timing (using a
single-scenario `welfare6_scenario.py` driver with `duration-workers=1`
and `solve-workers=1`, which mirrors `run_hybrid_welfare6.py`'s flow):

| Phase | Serial time | Share | Notes |
|---|---:|---:|---|
| Build + solve | 41 s | 2 % | Independent per scenario |
| AD convergence solve (5 iterations × ~313 s) | 1 566 s | 89 % | 5 iters × (run_experiment ≈ 150 s + type-serial solve ≈ 160 s) |
| Duration loop (21 runs of `run_experiment`, serial) | 201 s | 11 % | Iterates through recession durations |
| **Per AD scenario total** | **1 810 s (30 min)** | | Longest scenario |
| Non-AD recession scenario | ~1 800 s | | 1 solve + 21-duration loop (no AD convergence) |
| Norec scenario | ~1 600 s | | 1 solve + 1 run_experiment |
| Base scenario | 50 s | | Shortest scenario |

12 scenarios × serial wait = **~5 h 45 min** (CPU-sum measured under
parallel execution).

## Strategies (ordered by measured impact)

### Strategy A — Outer: scenario-level subprocess parallelism

**Mechanic.** Launch one independent Python subprocess per welfare-6
scenario (12 total). Each subprocess rebuilds and re-solves its own
economy copy from scratch, runs its assigned scenario, pickles
`cLvl_all_splurge / AggCons / AggIncome`. Orchestrator waits for all
subprocesses, loads the pickles, computes the welfare-6 table inline.

**Why this works on CRN.** Every HARK seed used by the simulation is
deterministic (`agent.seed = e * DiscFacCount + d`, `IncShkDstn[0].seed
= 763607780`). Separate subprocesses with identical seeds produce
identical shock histories and identical simulation output.

**Files.**
- `Code/HA-Models/FromPandemicCode/welfare6_scenario.py` — per-scenario
  runner with `--scenario`, `--parametrization`, `--out-dir`. Mirrors
  `run_hybrid_welfare6.py`'s economy-build and scenario-dispatch
  verbatim so the aggregated output is bit-identical to serial.
- `Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py` —
  orchestrator. Writes `Tables/{param}_parallel/welfare6.tex` so serial
  artifacts are left untouched.
- `Code/HA-Models/FromPandemicCode/validate_mc_crn.py` +
  `run_mc_crn_validation.py` — CRN sanity runner. Runs a minimal MC
  pipeline twice as independent subprocesses, compares shock histories
  and experiment outputs element-wise. Must pass before trusting (A).

**Expected speedup.** Critical path becomes `max(scenario_time)`. With
4 AD scenarios at ~30 min each running concurrently, wall ≈ 30 min.
Actual: **9.88× on Baseline (5 h 45 min → 35 min)**; the critical path
was a ~35 min AD scenario rather than 30 min due to parallel I/O &
subprocess-startup contention.

**Memory budget.** 12 subprocesses × ~300 MB each ≈ 3.6 GB peak.
Negligible on a 64 GB machine.

### Strategy B — CRN determinism validation (prerequisite)

Before any parallelism is usable for welfare-6, we must verify that
`make_idiosyncratic_shock_histories()`, `run_experiment()`, and — when
enabled — `solve_ad_*` all produce bit-identical outputs across
subprocess invocations with identical seeds.

**Protocol.** Three nested validations:
1. HS_Only (1 type) serial vs serial subprocess — cheapest smoke test.
2. Reduced_Run (3 types) to exercise cross-type determinism.
3. Reduced_Run `--with-ad` to exercise the iterative AD convergence
   loop, which could in principle reorder floating-point operations
   across subprocesses.

All three must show element-wise equality (`np.array_equal` true on
shock histories + `cLvl_all_splurge` + `AggCons` + `AggIncome`).

**Result.** All three passed; all 11 arrays bit-identical across
subprocesses in every configuration. No relaxation of the bit-identity
criterion was needed.

### Strategy C — Inner: duration-level pool

**Mechanic.** Within a recession-or-AD scenario, the 21-duration loop
in `_prob_weighted_rec` is embarrassingly parallel (each duration is
an independent `eco.run_experiment(…)` on the already-solved economy).
Use `multiprocessing.get_context('fork').Pool(N)` with a module-level
`_POOL_ECO` that is set in the parent before `Pool()` creation, so
forked children inherit the solved economy via copy-on-write without
pickling.

**Flag.** `--duration-workers N` on `welfare6_scenario.py`.

**Validation.** `validate_duration_pool.py` runs the same scenario
serial vs pool-parallel and compares pickles element-wise. Must pass
before using.

**Expected impact.** On Reduced_Run the duration loop is ~10 s of the
~80 s AD scenario (8 %) — small lever. On Baseline the duration loop
is 201 s of the 1 810 s AD scenario (11 %). Even with 8 workers the
ceiling is 11 % × (1 − 1/8) ≈ 10 % per scenario.

**Measured.** Reduced_Run pool × 4: 82 s → 80 s (1.03×); Reduced_Run
pool × 11: 82 s → 82 s (1.00×). Baseline not tested because the
Baseline-level measurement would be dominated by the AD solve (which
this strategy doesn't touch).

### Strategy D — Inner: type-parallel solve (monkey-patched)

**Mechanic.** `AggregateDemandEconomy.solve()` iterates over
`self.agents` serially (21 types on Baseline). Replace it with a
fork-Pool version that (a) calls `pre_solve()` on all agents in the
parent (so mutations persist across the fork), (b) forks N workers
which each call `solve_agent()` on their assigned agent, (c) on join,
installs returned solutions and calls `post_solve()` in the parent.
Monkey-patch via `AggregateDemandEconomy.solve = _parallel_agg_solve`
at module import time in `welfare6_scenario.py` — process-local; the
file on disk is untouched.

**Flag.** `--solve-workers N` on `welfare6_scenario.py`.

**Why `mc_only_speedups.md` deferred this.** That plan's concern was
that the per-type Bellman is "tightly coupled to the shared CFunc
within an AD iteration." This turns out to be correct about the
outer loop — each AD iteration does reassign the shared CFunc across
all types, and the loop across iterations stays sequential — but
within a single iteration, once CFunc is set, the per-agent solves
ARE independent. The monkey-patch parallelizes only the inside of
one iteration and leaves the outer iteration loop serial.

**Validation.** `validate_solve_pool.py` runs the same AD scenario
with `--solve-workers 1` vs `N`. Must produce bit-identical arrays.

**Measured.** Reduced_Run solve-pool × 3: 88 s → 74 s (1.17×).
Baseline solve-pool × 8: 1 810 s → 1 144 s (**1.58×**), with the AD
solve phase dropping from 1 566 s to 910 s (1.72× speedup on the
phase). Not 8× because each AD iteration is roughly half
`run_experiment` (can't be attacked by type-parallelism) and half
`solve` (the part we parallelize). Theoretical ceiling with 8 workers
on 21 types ≈ 2.6× on the solve phase; we realized ~65 % of that
ceiling (typical for load-imbalanced parallel work).

**Limit on the 16-core machine.** Combining (A) 12-way scenario
parallelism with (D) solve-workers > 1 oversubscribes. 12 × 2 = 24
processes on 16 cores is ~1.5× oversubscribed; 12 × 4 = 48 is 3×.
Strategy (D) is most useful for:
- Single-scenario sensitivity/debug runs on the full Baseline.
- Machines with >>16 cores where (A) doesn't saturate.

### Strategy E — AD convergence tolerance

**Mechanic.** `convergence_tol_solvingAD` defaults to 1 E-2 in
`Parameters.py`. Loosening to 2 E-2 or 5 E-2 can cut 1–2 AD iterations.

**Flag.** `--ad-tolerance T` on `welfare6_scenario.py`. Forwarded by
`run_welfare6_parallel.py`.

**Why `mc_only_speedups.md` deferred this.** Convergence tolerance is
a modeling choice; changing it alters the final CFunc and could shift
welfare-6 numbers. The defer was correct in principle — the
sensitivity needed to be measured before defaulting.

**Measured.**

| Tolerance | Iters/AD scenario | welfare6 (Rec=1, AD=1) (Reduced_Run) | Reduced_Run wall |
|---|---|---|---:|
| 1 E-2 (default) | 3–4 | 1.02 / 1.42 / 1.00 | 99 s |
| 2 E-2 | 3 | 1.02 / 1.42 / 1.00 | 95 s |
| 5 E-2 | 2–3 | 1.02 / 1.42 / 1.00 | 95 s |
| 1 E-3 (tighter) | 5 | 1.02 / 1.42 / 1.00 | 100 s |

**Welfare6 unchanged at 2-decimal precision at every tolerance.** At
Baseline, loosening to 2 E-2 drops AD iterations from 5 → 3 and shaves
~2 min off the 35-min wall (5-6 % pipeline speedup). Small but free.

### Strategy F — AgentCountTotal sensitivity

**Mechanic.** Override Parameters.py's `AgentCountTotal` via CLI. Halves
every MC pass; has no effect on the AD solve phase.

**Flag.** `--agent-count-total N` on `welfare6_scenario.py`. Forwarded.

**Measured (Reduced_Run sweep at N ∈ {2500, 5000, 10000, 15000}).**

| N | Wall | UI Rec=1 AD=0 | UI Rec=1 AD=1 |
|---|---:|---:|---:|
| 2500 | 97 s | 1.50 | 1.38 |
| 5000 (default) | 96 s | 1.57 | 1.42 |
| 10000 | 99 s | 1.53 | 1.39 |
| 15000 | 104 s | 1.56 | 1.41 |

Check and Tax cut stable to 2-decimal across all N. **UI Rec=1 cells
wobble 0.04-0.07** at 2-decimal precision — CRN pairing doesn't fully
cancel noise when the denominator (NPV of UI-added income) is small.

**Recommendation.** Do not reduce N below the Parameters.py default
for production welfare-6 runs. For development/sensitivity work,
N = 5000 saves ~8 min (~23 %) on Baseline but costs 0.03–0.05 of
welfare-6-UI precision.

## What we explicitly did not pursue

- **Edit `Simulate.py`** — would create merge conflicts with the other
  machine doing Phase 6 production runs. New-files approach chosen
  instead. `mc_only_speedups.md`'s `os.fork` approach remains available
  for a future refactor that absorbs the new-files prototype.
- **Harmenberg neutral-measure MC (`mc-speedup-plan.md` Strategy 1).**
  Biggest theoretical payoff (5–10× via variance reduction) but a
  separate project — HARK has built-in support but integrating into
  HAFiscal's splurge-aware simulation needs more validation than a
  week of work allows. See `plans/harmenberg-*` for existing work.
- **Numba JIT on HARK's inner simulation loop.** Invasive, diverges
  from upstream HARK, risks subtle drift; defer.
- **GPU / JAX rewrite.** Multi-week engineering; not worth it on a
  well-specified CPU machine with 16 cores.

## Validation protocol (applied)

For each strategy above:

1. **Syntax + import check** on new files.
2. **Numerical equivalence** on the cheapest parametrization (HS_Only
   or Reduced_Run): compare element-wise pickled arrays against the
   serial reference. Expect `np.array_equal == True`.
3. **Escalate to Baseline** only after HS_Only or Reduced_Run passes.
4. **Full-pipeline equivalence** on the welfare-6 `.tex` output: same
   2-decimal numbers as `run_hybrid_welfare6.py` serial.

Satisfied at every step on this branch (commit log from `097b35a6`
onward).

## Outcome summary

| Strategy | Flag | Impact on Baseline wall | Precision cost |
|---|---|---|---|
| A. Scenario parallelism | (default on `run_welfare6_parallel.py`) | 5h 45m → **35 min (9.88×)** | None |
| B. CRN validation | (prerequisite) | (enables A, C, D) | — |
| C. Duration pool | `--duration-workers N` | Marginal (~11 % ceiling on AD; dominated by AD solve) | None |
| D. Type-parallel solve | `--solve-workers N` | 1.58× per AD scenario; can't stack with A on 16 cores | None |
| E. AD tolerance | `--ad-tolerance T` | 5-6 % free | None at 2-decimal |
| F. Agent count | `--agent-count-total N` | Up to 23 % at N=5000 (projected) | UI Rec=1 wobbles 0.04-0.07 |

**Net.** The dominant win is Strategy A (scenario parallelism). The
inner-level strategies (C, D) combine poorly with A on a 16-core
machine because A already saturates the core budget; they become
useful on smaller machines or for single-scenario runs. E and F are
free-to-slightly-costly knobs for development-mode runs.

## Revert path

- Disable every optimization by passing no flags: `--duration-workers`,
  `--solve-workers`, `--ad-tolerance`, `--agent-count-total` all
  default to the serial/Parameters.py values.
- To un-parallelize at the scenario level, run `run_hybrid_welfare6.py`
  directly (the new harness does not replace it; it sits alongside).
- To remove the new code entirely: `git rm` the five new files listed
  below; no other file has been touched.

## Files added

All under `Code/HA-Models/FromPandemicCode/`:

- `validate_mc_crn.py` — per-process CRN dump.
- `run_mc_crn_validation.py` — CRN validation driver.
- `welfare6_scenario.py` — per-scenario MC runner with four parallelism knobs.
- `run_welfare6_parallel.py` — multi-scenario orchestrator.
- `validate_duration_pool.py` — serial vs duration-pool A/B comparator.
- `validate_solve_pool.py` — serial vs solve-pool A/B comparator.

Total: ~1000 lines of new code, 0 lines of existing code changed.
