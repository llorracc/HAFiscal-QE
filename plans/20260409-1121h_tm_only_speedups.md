# TM-only Pipeline Speedups (Plan)

**Status:** Plan committed; implementation to follow in a separate commit.
**Baseline run:** Smoke_Test, 261s intrinsic / 4.4 min wall clock.
**Baseline artifacts:**
- `runs/tm_only_smoke_cprofile_baseline.prof` (cProfile output)
- `runs/tm_only_smoke_hafiscal_profile_baseline.json` (existing instrumentation)
- `runs/tm_only_smoke_20260409T1437.log` (smoke test stdout)

## Profiling summary

| Component | Time | % of intrinsic |
|---|---|---|
| HARK Bellman solves (`solve_agg_cons_markov_alt` × 4160) | ~325s | 78% |
| `economy.solve()` total (29 calls × 12.3s avg) | ~357s | wraps the above |
| HARK interpolation (`_evaluate` × 1.2M) | ~140s | overlaps |
| **`deepcopy`** (44M calls, mostly CFunc snapshots in AD loop) | **81s** | **20%** |
| `propagate_experiment_tm` (TM forward pass) | ~48s | 12% |

The hot path is `Run_FullRoutine` × 4 shock types = 259s = 62% of total.
Each shock type runs ~5 AD iterations × one full `economy.solve()` per
iter = ~50s, × 4 shocks = ~200s of AD-loop time.

## Planned changes

### Change 1: Parallelize the four shock types

**Where:** `Code/HA-Models/FromPandemicCode/Simulate.py`, the loop near line 768 that
calls `Run_FullRoutine('recession')`, `Run_FullRoutine('recessionUI')`,
`Run_FullRoutine('recessionTaxCut')`, `Run_FullRoutine('recessionCheck')`.

**What:** Wrap the four calls in a `multiprocessing.Pool` (or
`concurrent.futures.ProcessPoolExecutor`) with `max_workers=4`. Each
`Run_FullRoutine` already deepcopies `AggDemandEconomy` internally and
trains its own CFunc, so the four are independent.

**Mechanism:** A worker function that takes `(shock_type, AggDemandEconomy_pickled,
Run_Dict, baseline_data, figs_dir)` and returns `(shock_type, dict_of_pickle_paths)`.
Workers write their `_results` pickles to `figs_dir` exactly as today;
the parent then continues with the existing post-processing path.

**Risk:** Low. Pure embarrassing parallelism. No math change. The only
shared state is the `figs_dir` (output directory) — workers write
disjoint filenames (`recession_results.pickle` vs `recessionUI_results.pickle`
etc.), so no race.

**Caveats / things to watch:**
- Pickling `AggDemandEconomy` and the agent list across the pool boundary
  takes ~5-10s of overhead per worker. With ~50s of work per worker, the
  net speedup is ~3× rather than 4× on a 4-core machine.
- Profile/log instrumentation (`hafiscal_progress`) writes to a single
  `/tmp/hafiscal_*.log` file. Need to either silence it in workers
  or guard the file writes with a process lock.
- HARK uses numpy / numba which release the GIL but processes are
  still preferred over threads here because of the deepcopy-heavy
  inner loop.

**Expected speedup:** 3-4× on the 4-shock phase. Smoke test ~4.4 min
→ ~1.7 min. Baseline ~1 hr → ~22 min.

### Change 2: Replace `deepcopy(self.CFunc)` with a tuple snapshot

**Where:** `Code/HA-Models/FromPandemicCode/AggFiscalModel.py`,
`solve_ad_recession` line ~1739 (and the `Compare_CFunc_Convergence`
helper it calls). The pattern is:

```python
Old_Cfunc = deepcopy(self.CFunc)
# ... build New_Cfunc, step toward it, install on self ...
Total_Diff = self.Compare_CFunc_Convergence(Old_Cfunc, self.CFunc)
```

`self.CFunc` is a 2D list of `CRule(intercept, slope)` objects. The
deepcopy is only used to compute a scalar distance for the convergence
check — `Old_Cfunc` is never mutated or held past that scalar
computation.

**What:** Replace with a flat tuple snapshot:

```python
def _cfunc_snapshot(cf):
    return [[(c.intercept, c.slope) for c in row] for row in cf]

def _cfunc_distance(snap, cf):
    return sum(abs(snap[i][j][0] - cf[i][j].intercept) +
               abs(snap[i][j][1] - cf[i][j].slope)
               for i in range(len(cf)) for j in range(len(cf[0])))
```

The `Compare_CFunc_Convergence` method already computes a sum-of-absolute-
differences over `(intercept, slope)`; the new helper produces an
identical scalar.

**Risk:** Low. Math-equivalent: identical convergence test, identical
convergence path. The only behavioral change is that the deepcopy
side-effect (e.g. cached attributes on `CRule`) no longer happens —
verified that `CRule` only carries `intercept` and `slope`.

**Expected speedup:** ~50-60s on smoke test (~20% of intrinsic). Most
of the 81s deepcopy total is concentrated in the AD-loop CFunc snapshot.

### NOT planned (intentionally)

- **AD iteration cap tuning** (lower `num_max_iterations_solvingAD` from
  15 → 8 at Baseline scale): potentially trades accuracy for speed
  in pathological cases. Defer until we have a baseline of converged
  numbers to compare against.
- **AD presolve dedup**: ~20s savings, requires touching the
  `Run_FullRoutine` boundary; not worth the complexity vs payoff.
- **Caching the base Bellman solve across shock types**: the test driver
  has this via `solve_or_cache`, but porting it to `Simulate.py` is
  more invasive. Deferred.

## Validation protocol

After implementation, the smoke test must produce **bit-identical**
multipliers and AggCons trajectories versus the baseline. To verify:

1. Re-run `AggFiscalMAIN_reduced.py --smoke-test` and capture stdout.
2. Compare the four printed multipliers (`NPV Multiplier check
   recession with AD: ...`) against the baseline log
   `runs/tm_only_smoke_20260409T1437.log` — must match to all
   printed digits.
3. Compare the `_results.pickle` files in `Figures/Smoke_Test/`
   against the pre-speedup versions: load both, assert numpy
   `array_equal` (or `allclose(rtol=1e-12)` for floats subject to
   reduction order changes from parallelism).

If parallelism introduces non-determinism in floating-point reduction
order, expect `allclose` rather than `array_equal`. Document the
tolerance.

## Revert path

`git revert` the implementation commit. The plan commit (this file)
stays. Pre-speedup state can be reconstructed by `git checkout` the
parent of the implementation commit.
