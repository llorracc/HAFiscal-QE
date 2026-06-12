# PR-3 (`ConsAggShockModelJAX`) — WIP Status, 2026-05-20 ~01:00 AM

## Summary

Drafted a full JAX port of `solve_ConsAggMarkov` in the PR-3 worktree.
Test failed with **76% relative error** (c_jax = 4.53 vs c_np = 2.57 at
the standard test fixture's MSS query point). The bug is real (not a
tolerance issue) and I couldn't localize it after ~25 minutes of careful
inspection. **Committed as WIP, NOT pushed.**

## Where it lives

- **Worktree:** `/home/shared/github/econ-ark/HARK-pr3-AggShockMarkovJAX`
- **Branch:** `gpu-jax-pr3-AggShockMarkovJAX-v2` (based on PR-2 branch)
- **WIP commit:** the most recent commit on that branch (has full
  diagnostic message in body)

## What's working

- File structure correct (`HARK/ConsumptionSaving/ConsAggShockModelJAX.py`
  + `tests/ConsumptionSaving/test_ConsAggShockModelJAX.py`)
- JIT-compiled inner kernel (`_expected_vp_next_2d`) compiles and runs
  without errors
- Outer-loop structure mirrors `solve_ConsAggMarkov` line-by-line
- Wrapper class `AggShockMarkovConsumerTypeJAX` integrates with HARK's
  Market/economy infrastructure
- Test harness is correct (parallel numpy + JAX agents in identical
  `CobbDouglasMarkovEconomy`)

## What's broken

EndOfPrdvP from JAX kernel ≈ 0.32 × EndOfPrdvP from numpy solver, which
inverts via the EGM step to **c_jax ≈ 3.1^(1/CRRA) × c_np ≈ 1.76 × c_np**.

That's a uniform multiplicative factor (across the test point), suggesting
a constant-factor bug — most likely a missing or doubled scalar like
`PermGroFac`, `DiscFac`, or one of the aggregate shock factors. The signs
match (consumption isn't NaN/negative), and the magnitudes are within an
order of unity, so it's not a sign error or broken lookup.

## Debugging plan for morning

In priority order:

1. **Sanity-check the lift.** Print
   `vp_table[10, 5]` vs `vpfunc(vp_m_grid[10], vp_M_grid[5])` —
   should agree exactly.

2. **Print intermediate values from `_expected_vp_next_2d`.** Pick
   one (M=MSS, a=BoroCnstNat+1.0) point and print:
   - `mNext` (Mcount=1, aCount=1, ShkCount values)
   - `vp_next` (after bilinear lookup)
   - `vP_factor` (Reff × PermShkTotal^(-CRRA))
   - The summand `pmv × vP_factor × vp_next`
   - Compare each to the corresponding HARK quantity at the same point
   to see exactly where the divergence begins.

3. **Suspect: `PermGroFac_total = PermGroFac * PermGroFacAgg[j]`.**
   HARK's `PermShkTotal_array` includes `PermGroFac` as a *float*
   (single-period growth factor for individual), but in some
   AggShockMarkov configurations `PermGroFac` is a length-1 list. If my
   `float(PermGroFac * PermGroFacAgg[j])` is silently using a wrong index,
   that could explain a constant-factor bug.

4. **Alternative fix path: `jax.pure_callback` for `vPfuncNext`.**
   Replace the lift+bilinear approach with a direct callback to the
   numpy `vpfunc`. Loses per-iter JIT benefit but eliminates the lift
   as a bug source. Tested pattern in JAX.

## Why I stopped at ~76% error

Per memory: "do not ship rushed/broken code at 1 AM." Better to commit
the WIP with a clear plan than to push a PR with a 76% math error or
spend another hour debugging tired.

The PR-1 (#1777) and PR-2 (#1778) work is correct and pushed; those are
the deliverables this overnight session shipped.

## Estimated time to fix

If the bug is what I suspect (constant-factor scalar), 30-60 min in the
morning. If the bilinear lift is the issue (table indexing, search
semantics, or extrapolation), 1-3 hours and possibly a rework to use
`jax.pure_callback`.

PR-3 is genuinely 3-5 days of work; this WIP is the first ~50% — about
right for one overnight session.
