---
date: 2026-05-16
status: PROPOSED
keywords: [welfare-6, 5D, parallelism, performance, quick-win]
related_conclusions:
  - 2026-05-16_BUG046_FINAL_summary.md
  - 2026-05-16_canonical_config_recommendation.md
related_memory:
  - feedback_parallelism.md
  - feedback_cascade_gating.md
---

# Plan: 5D welfare driver duration-parallel quick win

## Goal

Cut the 5D welfare driver wall time on HS_Only at A=50 from **~740 s
sequential → ~75 s parallel** by parallelizing the per-recession-duration
loop. Brings 5D within ~25% of MC speed at HS_Only (MC ≈ 60 s) and makes
multi-tier 5D runs (e.g. for grid-convergence diagnosis or as
Tier-2 in the 3% gap investigation) cheap enough to iterate on.

## Why now

The 3%-residual investigation (5D 2.04 vs MC 2.10 at HS_Only) requires:
- multi-seed MC (cheap; already parallel)
- 5D grid sweep at A ∈ {20, 50, 100, 200} for welfare specifically (currently expensive)
- per-period intermediate diagnostics from 5D (currently a full re-run per
  variant)

At sequential speed, A=100 alone is ~50 min and A=200 is ~3 h. Iterating
on kernel variants becomes painful. The Pool refactor removes that
friction with one day of work and zero math risk.

## Current state

`welfare6_tm_joint5d_full.py:80-90` (read 2026-05-16):

```python
for d_idx, dur in enumerate(range(1, max_dur + 1)):
    path = _build_econ_mrkv_path(act_T, nep, dur)
    res = compute_joint_welfare5d(
        agent_pol, agent_none, agent_base, bd,
        EconomyMrkv_path_pn=path, act_T=act_T,
        verbose=(d_idx == 0),
    )
    welfare_num_total += rec_probs[d_idx] * res['welfare_num_series']
    AddInc_total_5D += rec_probs[d_idx] * (res['AggInc_pol_series'] - res['AggInc_none_series'])
    AddCons_total_5D += rec_probs[d_idx] * (res['AggCons_pol_series'] - res['AggCons_none_series'])
```

Each iteration is fully independent: input is `(path_d, agents, bd)`
where only `path_d` varies; output is three numpy arrays; reduction is a
weighted sum. No shared mutable state, no inter-duration ordering
dependency, no race conditions.

## Refactor design

Three-file scope:

1. **`welfare6_tm_joint5d_full.py`** — the driver. Replace the for-loop
   with `multiprocessing.Pool.map`. Worker count = `min(max_dur,
   os.cpu_count())` capped by a new `JOINT5D_NUM_WORKERS` env var.

2. **`welfare6_tm_joint5d.py`** — `compute_joint_welfare5d` is already a
   pure function in its inputs. No changes needed for the duration-level
   refactor. The agents/bd objects are picklable (the existing MC
   parallel driver `run_welfare6_parallel.py` already pickles agents).

3. **No changes to** `tm_methods.py`, `welfare6_scenario.py`,
   `EstimParameters.py` — duration parallelism is a driver-level concern.

### Worker function (~10 lines)

```python
def _run_one_duration(args):
    d_idx, dur, act_T, nep, agent_pol, agent_none, agent_base, bd = args
    path = _build_econ_mrkv_path(act_T, nep, dur)
    res = compute_joint_welfare5d(
        agent_pol, agent_none, agent_base, bd,
        EconomyMrkv_path_pn=path, act_T=act_T,
        verbose=False,  # workers don't print
    )
    return d_idx, res
```

### Driver replacement

```python
import multiprocessing as mp

num_workers = int(os.environ.get('JOINT5D_NUM_WORKERS',
                                  min(max_dur, os.cpu_count() or 1)))
work = [(d_idx, dur, act_T, nep, agent_pol, agent_none, agent_base, bd)
        for d_idx, dur in enumerate(range(1, max_dur + 1))]

with mp.Pool(num_workers) as pool:
    results = pool.map(_run_one_duration, work)

# Reduce
welfare_num_total = np.zeros(act_T)
AddInc_total_5D  = np.zeros(act_T)
AddCons_total_5D = np.zeros(act_T)
for d_idx, res in results:
    welfare_num_total += rec_probs[d_idx] * res['welfare_num_series']
    AddInc_total_5D   += rec_probs[d_idx] * (res['AggInc_pol_series']
                                              - res['AggInc_none_series'])
    AddCons_total_5D  += rec_probs[d_idx] * (res['AggCons_pol_series']
                                              - res['AggCons_none_series'])
```

## Phases (cascade-gated per `[[feedback_cascade_gating]]`)

### Phase 1 — Correctness baselines (~45 min)

Run the current sequential driver at **A=20** *and* **A=50**, dumping
full per-duration outputs to pickles for diff'ing. Output:
- `reproduce/logs/5D_parallel/baseline_A20_seq.pkl`
- `reproduce/logs/5D_parallel/baseline_A50_seq.pkl`

Each pickle must contain, for every `d_idx ∈ {0..10}`:
- `welfare_num_series` (full `(act_T,)` array, every period)
- `AggInc_pol_series`, `AggInc_none_series` (full arrays)
- `AggCons_pol_series`, `AggCons_none_series` (full arrays)
- `sum(w_num)`, `sum(AddInc_5D)` as scalar summaries
- `welfare_num_total`, `AddInc_total_5D`, `AddCons_total_5D` (the
  final reduced arrays)

The pickle is the ground truth. Keep the `.log` alongside.

### Phase 2 — Implement Pool refactor (~2 h coding)

Edits to `welfare6_tm_joint5d_full.py` only. Include:
- `--workers N` CLI flag (also `JOINT5D_NUM_WORKERS` env var)
- `--dump-per-duration <path>` flag to write the same full-series
  pickle as Phase 1 (drives the Phase 3 diff)
- Per-duration timing collected in worker, returned in `res`
- Aggregate timing log: total wall, mean per-duration, worker count
- Reduction in `d_idx` order (NOT pool-completion order) so
  floating-point summation is deterministic

### Phase 3 — Rigorous equivalence check (~30 min)

Run parallel at A=20 *and* A=50 across worker counts. Build a
correctness matrix:

| A   | workers | Expected diff vs sequential pickle |
|-----|---------|------------------------------------|
| 20  | 1       | **0.0 exactly** (bit-identical)    |
| 20  | 4       | **0.0 exactly** (deterministic reduction in d_idx order) |
| 20  | 11      | **0.0 exactly**                    |
| 50  | 1       | **0.0 exactly**                    |
| 50  | 11      | **0.0 exactly**                    |

For each (A, workers) cell, diff:
1. The 3 final reduced arrays (`welfare_num_total`, etc.) element-wise
2. Every per-duration `*_series` array element-wise (all 11 durations
   × all `act_T` periods × 5 series = 11 · T · 5 scalars to check)

Pass criterion: **`np.array_equal(seq, par) == True`** for every array
in every cell. If any single element differs by even one ULP, halt
and investigate — there should be no source of non-determinism in this
refactor (pure function, same arithmetic, same reduction order). A
nonzero diff is a bug, not roundoff.

Diff report goes to `reproduce/logs/5D_parallel/phase3_equivalence.md`
with a per-cell PASS/FAIL line and, on failure, the (d_idx, t) of the
first divergent element.

### Phase 4 — Speedup measurement at A=50 (~15 min)

Once Phase 3 passes, re-run A=50 at workers ∈ {1, 4, 8, 11} with timing
captured. Confirm:
- workers=1 ≈ sequential A=50 baseline (~740 s)
- workers=11 ≈ 75–100 s (target: ≥ 8× speedup)
- Speedup curve is consistent with Amdahl bounds (single-thread setup
  cost: ~10 s before parallel region)

Report in `reproduce/logs/5D_parallel/A50_speedup.md`.

### Phase 5 — Cohort outer-loop (deferred unless requested)

For Baseline scope (21 cohorts), there's an outer cohort loop that's
also embarrassingly parallel. NOT in this quick-win plan; treat as a
follow-on. Document in the conclusions doc that this is the obvious
next step if 5D performance becomes a recurring bottleneck.

## Validation budget

- Phase 1: sequential baseline pickles at A=20 and A=50 (ground truth)
- Phase 3: full-series, all-durations, all-cells element-wise diff with
  `np.array_equal` (strict equality, no tolerance) at 5 (A × workers)
  configurations
- Phase 4: speedup vs Amdahl prediction (engineering check, not model)

The math is unchanged. Risk surface is limited to: pickling errors in
the worker arg tuple, numpy buffer aliasing across processes (unlikely
since we return fresh arrays), forking issues with HARK's lazy imports
(the MC parallel driver has solved this; reuse the same
`multiprocessing.set_start_method('spawn')` if needed), and any hidden
non-determinism inside `compute_joint_welfare5d` (the function should
be pure-deterministic given fixed inputs; if Phase 3 finds non-zero
diff at workers=1, that's the smoking gun for hidden non-determinism
and needs to be fixed *before* enabling parallelism).

## Out of scope

- JAX / numba / GPU kernel rewrite (big-win plan; separate)
- Cohort-level parallelism for Baseline scope (Phase 5, deferred)
- Welfare-cell parallelism (only 2 UI cells; gain modest at HS_Only)
- Algorithmic changes to `compute_joint_welfare5d` (untouched)

## Estimated wall (start to finish)

| Phase | Wall |
|---|---|
| 1. Sequential baselines (A=20, A=50) | 45 min |
| 2. Implement Pool refactor | 2 h |
| 3. Full-series equivalence check (5 configs) | 30 min |
| 4. Speedup measurement at A=50 | 15 min |
| **Total** | **~3.5 h** |

## Open items deferred to follow-on (per `[[feedback_deferred_followups]]`)

1. Cohort-axis parallelism (21-way at Baseline; ~10× additional speedup)
2. JAX port of `compute_joint_welfare5d` inner kernel (5–50×)
3. Welfare-cell parallelism (2× for UI rec + rec_AD)

Trigger to revisit: any moment 5D wall time becomes the gating
bottleneck of an investigation (e.g. when running A=100/200 grid
convergence at Baseline).
