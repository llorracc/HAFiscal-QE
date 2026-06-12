---
date: 2026-05-17
status: PROPOSED — to start after current JAX cascade work completes
related_plans:
  - 20260516_5D_ambitious_parallelization.md
related_conclusions:
  - reproduce/logs/5D_parallel/B2_JIT_BREAKTHROUGH.md
related_memory:
  - feedback_parallelism.md
---

# Plan: CPU-parallelism opportunities for the JAX 5D workflow

## Problem

The current JAX 5D workflow at Baseline A=60 takes ~86 min total wall:
- **Setup (CPU, single-threaded): ~30 min** — `build_and_solve` for 63 agents
  (3 scenarios × 21 cohorts), all serial. GPU idle this entire time.
- **Parallel region (GPU, serial calls): ~55 min** — 441 (cohort, dur) tasks,
  each launches a JAX kernel sequentially because there's one GPU. CPU does
  small per-task preprocessing (joint_markov, atom-pair table, etc.) and then
  waits for GPU.

The 32 CPU cores plus the GPU are mostly idle most of the time. Four
unexploited parallelism opportunities.

## Phase C.1 — Parallel agent solves in setup (biggest win)

### Goal

Reduce setup from ~30 min → ~5-10 min by parallelizing the 63 agent solves
(currently serial inside `AggEco.solve()`).

### Analysis

Per the existing CPU Phase A driver, the solve step is single-threaded
because `AggEco.solve()` iterates agents sequentially. But:
- The 3 scenarios (pol, none, base) are independent — could run in 3 forked
  processes.
- Within each scenario, the 21 cohorts are independent — could fork further.

Total potential: 3 × 21 = 63-way parallelism, but cohort solves have
imbalanced wall times (β-atom 0 vs β-atom 6 differ). 10-20-way parallel is
realistic.

### Approach

Refactor `build_and_solve` (or wrap it) to:
1. Fork 3 processes, one per scenario
2. Within each scenario, use a Pool of (e.g.) 7 workers to solve 21 cohorts
3. Communicate solved cFunc tables back to the main process via shared
   files or pickle round-trip

OR simpler: directly solve agents one at a time but in a multiprocessing.Pool
of 8-16 workers, all sharing the same parameter loading.

### Risk

Medium. Agent solves are complex objects with internal state; pickling and
re-instantiating across processes can be fragile (BUG-043 era taught us
HARK has unpicklable closures). Use fork-COW + module globals as in the
existing driver.

### Expected wall reduction

Setup 30 min → ~5-8 min. Total Baseline A=60 wall: 86 min → 60 min.

### Cost

1-2 days.

## Phase C.2 — Pre-tabulate cFuncs in parallel with JIT compile

### Goal

Overlap CPU cFunc tabulation with GPU JIT compilation (currently both
serial and on the critical path).

### Analysis

When `compute_joint_welfare5d_jax` starts, it does:
1. cFunc tabulation for pol, none, base (CPU, ~5s × 3 = 15s per cohort)
2. JAX JIT compile of `_step_period_5d_jax_v3` (one-time per shape, ~1.5s)
3. Loop over periods (GPU)

Step 1 + 2 could run in parallel: launch the JIT compile in a thread while
the cFunc tabulation runs in main.

For Baseline (21 cohorts), cFunc tab is repeated 21 times. Total ~5 min of
CPU work. Could be pre-tabulated for all 21 cohorts upfront in parallel
(using a CPU Pool while JAX is compiling), saving most of that 5 min.

### Approach

1. After `build_and_solve`, launch a CPU Pool to pre-tabulate cFuncs for
   all 21 cohorts × 3 scenarios into a dict keyed by (cohort_idx, scenario).
2. Pass the pre-tabulated tables into the per-task driver.

### Risk

Low. cFunc tabulation is a pure function call.

### Expected wall reduction

~5 min total → ~30 sec. Total Baseline A=60 wall: 86 min → 81 min (~6% gain).

### Cost

Half day.

## Phase C.3 — Pipeline CPU preprocessing with GPU compute

### Goal

While GPU is computing period t of (cohort c, dur d), CPU prepares the
inputs for period t+1 (or for the next (cohort, dur) task).

### Analysis

Each period's GPU compute is ~0.17s at A=60. Preceding CPU work
(joint_markov + IncShk extraction + atom-pair table) is ~0.05-0.1s.
Sequential: 0.27s/period. Pipelined: max(0.17, 0.1) = 0.17s/period.
Savings: ~30%.

Over 40 periods × 441 tasks: ~30% × ~55 min = ~16 min saved.

### Approach

Use Python threading (since GIL released during JAX dispatch) or async
patterns. Each task launches GPU work, immediately starts preparing next.

JAX is already async-by-default (returns futures). The only blocker is the
pLvl_factor recurrence which reads `dist5d_jax.sum(axis=...)` synchronously.
Defer that to the end of the (cohort, dur) batch.

### Risk

Medium. Async patterns require careful management of futures; bug surface
is bigger.

### Expected wall reduction

~15 min off the 55-min parallel region. Total Baseline A=60: 86 min → 70 min.

### Cost

1-2 days.

## Phase C.4 — Multi-cohort GPU batch (deferred)

### Goal

Run multiple cohorts simultaneously on the GPU via `jax.vmap` over a
"cohort" leading axis.

### Analysis

Currently each cohort calls the JIT kernel sequentially. Memory permitting,
multiple cohorts could be processed in one GPU call.

Memory at A=60, 21 cohorts: per-cohort dist5d = 5 MB → all 21 = 105 MB.
Plus intermediates (~5× = 525 MB) — fits in 16 GiB VRAM.

But the kernel needs a beta-batch dimension (similar to Phase A.6 attempt),
which complicates cFunc indexing (different cohorts have different cFunc
tables). Possible but messy.

### Risk

High. Requires re-designing the kernel signature.

### Expected wall reduction

Could reduce parallel region from 55 min → ~10 min (5-6× from cohort batch).
Total Baseline A=60: 86 min → 40 min.

### Cost

3-5 days.

## Combined plan (sequential implementation)

| Phase | Cost | Cumulative wall (Baseline A=60) |
|---|---:|---:|
| Current (JAX only) | — | 86 min |
| + C.1 parallel solves | 1-2 days | ~60 min |
| + C.2 pre-tabulate cFuncs | 0.5 day | ~55 min |
| + C.3 CPU-GPU pipeline | 1-2 days | ~40 min |
| + C.4 cohort vmap on GPU | 3-5 days | **~15-20 min** |

Stop after C.1 if 60 min is acceptable; pursue C.2+C.3 if you want to
sub-1-hour; pursue C.4 if 5D needs to be a sub-30-min interactive tool.

## Recommended sequencing

1. **Do C.1 first** (biggest win, lowest risk per dollar of dev time)
2. **Then C.2** if you have a half-day spare
3. **C.3 only if you're regularly doing Baseline runs** (the 16-min savings
   accumulate)
4. **C.4 is the "make 5D interactive" investment** — defer until the use
   case justifies

## Out of scope

- Multi-GPU (only one RTX 4080 in this box)
- HARK rewrites (the build_and_solve internal logic is HARK; we can
  parallelize around it but not improve the per-agent solve cost)
- Streaming dist5d data (full GPU residency is correct)

## Triggers to start

- 5D becomes a regular tool with Baseline runs >1x/week → C.1 worth it
- Multi-tier runs (HS_Only + Reduced_Run + Baseline together) become routine → C.1+C.2
- Interactive 5D welfare exploration / what-if analysis becomes a workflow → C.3+C.4
