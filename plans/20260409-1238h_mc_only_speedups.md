# MC-only Pipeline Speedups (Plan)

**Status:** Plan committed; implementation to follow in a separate commit.
**Baseline run:** Smoke_Test under MC sequential, 14.96 min wall clock
(982 sec under cProfile).
**Baseline artifacts:**
- `runs/mc_smoke_cprofile_TIMESTAMP.log` (smoke stdout)
- `/tmp/hafiscal_mc_smoke.prof` (cProfile output, will be saved with the plan commit)

## Hardware

Reported by the host:

- **CPU:** Intel i9-13900K, 16 physical cores (8P+8E) / 32 logical cores (HT)
- **RAM:** 30 GiB total, ~27 GiB free
- **GPU:** none accessible from this WSL2 environment (no `nvidia-smi`,
  no CUDA, numba CPU-only)
- **BLAS:** OpenBLAS 0.3.23 with `MAX_THREADS=2`, `USE_OPENMP=` (no OpenMP).
  BLAS is essentially single-threaded — no oversubscription risk from
  forking, and no need to set `OMP_NUM_THREADS` / `MKL_NUM_THREADS` to
  prevent contention.
- **Workload context:** "essentially serving as a compute server for
  exactly and only this task" — full machine usage is fine.

**Implication:** the optimization story is entirely about CPU-level
Python parallelism breadth. There is no GPU lever. The current
`Simulate.py` `os.fork` dispatch creates only **7 worker processes** out
of **32 available cores** — we're using ~22% of the machine.

## Profile summary (MC, Smoke_Test, sequential, 982s under cProfile)

| Component | Cumulative | Self | Notes |
|---|---|---|---|
| `Run_FullRoutine` × 4 (recession + 3 policies) | 670s (68%) | — | Hot path |
| `Run_FullRoutineNoRecessions` × 3 | 302s (31%) | — | Hot path |
| `solve_agg_cons_markov_alt` × 8197 (Bellman) | 737s | 71s | Per-iter Bellman |
| `run_experiment` × 109 (MC sim) | 511s | — | The full sim+aggregate |
| `solve_if_changed` × 327 (`economy.solve()`) | 348s | — | Wraps Bellman |
| `simulate` / `sim_one_period` (HARK MC inner loop) | 158s | — | The N-agent forward pass |
| HARK `interpolation._evaluate` | 364s | 122s | Per-period cFunc evaluation |
| `deepcopy` (91M calls, mostly HARK internals) | 166s | 70s | HARK interpolation `__init__` |

**Key observations:**

1. **Bellman solves dominate even in MC mode** — ~70% of total cost is
   inside `economy.solve()`, not the MC simulation. This is because at
   Smoke_Test N=100 the simulation is cheap. At Baseline N≥10000 the
   simulation cost will scale linearly in N and become more important,
   but Bellman cost is invariant in N.

2. **The MC simulation inner loop (`sim_one_period`) is 158s = 16% of
   total at Smoke_Test scale.** This is parallelizable per agent type.

3. **`run_experiments_all_recessions` runs `max_recession_duration`
   sequential `run_experiment` calls** (Simulate.py:468 loop). At
   Baseline `max_recession_duration = 21`, so each Run_FullRoutine
   runs ~21 sequential simulations on the trained CFunc. These are
   independent and parallelizable.

4. **The current `os.fork` dispatch only parallelizes at the shock-type
   level.** 7 jobs on 32 cores leaves 25 cores idle for most of the run.

## Planned changes

### Change 1: Per-duration parallelism in `run_experiments_all_recessions` (and TM/AD variants)

**Where:** `Code/HA-Models/FromPandemicCode/Simulate.py`, the duration
loops in:
- `run_experiments_all_recessions` (line 468)
- `run_experiments_all_recessions_tm` (~line 510)
- `run_experiments_all_recessions_ad_tm` (~line 540)

**What:** Replace each sequential `for t in range(max_recession_duration)`
loop with an `os.fork`-based dispatcher (mirroring the shock-type
dispatch in commit 3ceacebb). Each child forks, runs one
`run_experiment` for its duration, writes the result to a temp file
keyed by duration index, and exits. Parent waits for all children and
collects.

The `AggDemandEconomy` and trained agent solutions are inherited via
copy-on-write, so no pickling is required. Each `run_experiment` call
is read-only with respect to the trained `agent.solution` and writes
its own copy of `AggCons / AggIncome / etc.` outputs.

**Cap:** Inner parallelism is bounded so that
`num_outer_forks × inner_workers ≤ os.cpu_count()`. With 7 outer
shock-type forks already in place and 32 cores, the inner cap defaults
to `max(1, 32 // num_outer_forks)` = 4. Override with
`HAFISCAL_DUR_WORKERS=N`. The outer fork sets `HAFISCAL_OUTER_FORK=1`
in its environment so the inner code knows it's in a child.

**Risk:** Low. Pure embarrassing parallelism over independent
`run_experiment` calls. No math change. The collected `all_results`
list is reordered by duration index after collection so the
`recession_prob_array` weighting is unchanged.

**Caveats:**
- Forking inside an already-forked process is safe on Linux but adds
  some PID accounting. The fork-bomb risk is bounded by the inner cap.
- Children must use `os._exit(0)` to skip parent atexit handlers
  (matches the shock-type dispatch convention).
- Pickle file collisions: each child writes to a tempfile with
  duration index in the name to avoid races.
- For Baseline `max_recession_duration=21` × 4 shock types × inner cap
  4 = 16-32 simultaneous workers, fully utilizing 32 cores.

**Expected speedup:** For MC at Baseline, the duration loop is the
inner bottleneck. With 4× per-shock-type parallelism on top of the
existing 7× shock-type parallelism, the effective concurrency goes
from 7 → ~28. **Wall clock 6-12 hr → ~2-4 hr.** TM-only would also
benefit but we already had 26 min and the bottleneck moves elsewhere.

### Change 2: Disable already-disabled change (placeholder for clarity)

We are NOT changing:
- AD iteration cap (would alter convergence tolerance — defer)
- BLAS thread count (already capped at 2, no oversubscription)
- The shock-type outer fork dispatch (already in place)
- Per-type Bellman parallelism (each type's Bellman is too tightly
  coupled to the shared CFunc within an AD iteration to parallelize
  cleanly — would require restructuring `solve_ad_recession`)
- Any GPU acceleration (not available)

## Validation protocol

After implementation:

1. Re-run Smoke_Test under MC (sequential mode via `HAFISCAL_NO_FORK=1`
   AND `HAFISCAL_DUR_WORKERS=1`) to confirm baseline. The four
   multipliers must match exactly to printed digits.
2. Re-run Smoke_Test under MC with both fork levels enabled. Same
   four multipliers must match (potentially with floating-point
   reduction-order drift at the ~1e-12 level).
3. Compare the AggCons/AggIncome trajectories from the `_results.csv`
   files: `np.allclose(rtol=1e-10)` should hold.
4. If 1-3 pass, launch the full Baseline run.

## Revert path

`git revert` the implementation commit. Set `HAFISCAL_DUR_WORKERS=1`
to disable the duration-level parallelism without reverting.
