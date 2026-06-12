# Step 2 (`EstimAggFiscalMAIN.py`) — code analysis for Phase 1 speedup

**Date:** 2026-04-18
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_explore-further-speedups`
**Scope:** Characterize step 2's Nelder-Mead loop structure without running the 48 h pipeline, to identify concrete speedup targets for phases 1.1–1.3 of `plans/20260418_explore-further-speedups.md`.

## Step 2 loop structure

The outer loop iterates over education types 0, 1, 2. For each:

```python
f_temp = lambda x: betas_obj_func_educ(x[0], x[1], x[2], educ_type=edType)
initValues = [β₀, ∇₀, GICx₀]  # education-specific starting point
opt_params = minimize_nelder_mead(f_temp, initValues, verbose=True)
```

`minimize_nelder_mead` is HARK's wrapper around scipy's Nelder-Mead. For a 3-parameter problem, each NM iteration consumes 1-3 objective-function evaluations at new simplex points depending on the algorithm's state (reflection, expansion, contraction, shrink).

## What one NM iteration does

Inside `betas_obj_func_educ` (line ~977):

```python
# 1. Build DiscFac distribution from (β, ∇)
dfs = Uniform(beta-spread, beta+spread).discretize(DiscFacCount)

# 2. Rebuild agent list for this education type — THIS IS THE PROBLEMATIC LINE
TypeListNewEduc = []
for b in range(DiscFacCount):
    ThisType = deepcopy(BaseTypeList[educ_type])   # fresh copy loses prior solution
    ThisType.AgentCount = int(np.floor(AgentCountTotal * data_EducShares[educ_type] * dfs.pmv[b]))
    ThisType.DiscFac = dfs.atoms[0][b]
    ThisType.seed = n
    TypeListNewEduc.append(ThisType)

# 3. Splice into economy's agent list, preserving other education groups' state
TypeListAll = AggDemandEconomy.agents
TypeListAll[educ_type*DiscFacCount:(educ_type+1)*DiscFacCount] = TypeListNewEduc
AggDemandEconomy.agents = TypeListAll

# 4. Solve the economy (warm-start partially applies)
AggDemandEconomy.solve()

# 5. Simulate to steady state
AggDemandEconomy.reset()
for agent in AggDemandEconomy.agents:
    agent.initialize_sim()
    ...
AggDemandEconomy.make_history()
AggDemandEconomy.save_state()
baseline_commands = ['solve()', 'initialize_sim()', 'simulate()', 'save_state()']
_mtc(TypeListAll, baseline_commands)           # note: second solve

# 6. Compute Lorenz + K/Y targets
Stats = calc_estim_stats(TypeListAll)
lp = calc_lorenz_pts(TypeListNewEduc)
distance = sqrt(sumSquares_of_targets)
```

## Warm-start analysis (Phase 1.2 of the speedup plan)

`AggregateDemandEconomy.solve(warm_start=True)` already supports warm-starting at `AggFiscalModel.py:1840`:

```python
def solve(self, warm_start=True):
    """Solve all agents. When warm_start=True, use previous converged solution
    as starting point for HARK's infinite-horizon convergence loop, dramatically
    reducing iterations (from ~5-15 to ~1-2 per agent)."""
    from HARK.core import solve_agent
    for agent in self.agents:
        from_solution = None
        if warm_start and hasattr(agent, 'solution') and len(agent.solution) > 0:
            prev_sol = agent.solution[0]
            current_states = agent.MrkvArray[0].shape[0]
            prev_states = len(prev_sol.vPfunc) if hasattr(prev_sol, 'vPfunc') else 0
            if prev_states == current_states:
                from_solution = prev_sol
        agent.pre_solve()
        agent.solution = solve_agent(agent, False, from_solution=from_solution)
```

**The missed opportunity.** In the NM objective, step 2 of the loop above replaces the agents for the current education type with deep copies of `BaseTypeList[educ_type]`. `BaseTypeList` agents are created at module load (lines 688–696) but **never solved directly**, so their `.solution` attribute is empty. Each `deepcopy` produces a fresh agent with no stored solution. Result:

- For the education type currently being estimated (7 agents out of 21 at Baseline): cold solve every NM iteration.
- For the other two education types (14 agents): warm-start preserves prior solution → ~2 iterations each.

That's ~1/3 of the `AggregateDemandEconomy.solve()` cost paid cold every NM iteration.

**The fix (Phase 1.2 prototype).** Replace the deep-copy-and-splice with in-place mutation of the existing agents:

```python
# In-place update instead of deepcopy+splice — preserves .solution for warm-start
for b in range(DiscFacCount):
    agent = AggDemandEconomy.agents[educ_type*DiscFacCount + b]
    agent.AgentCount = int(np.floor(AgentCountTotal * data_EducShares[educ_type] * dfs.pmv[b]))
    agent.DiscFac = dfs.atoms[0][b]
    # Keep agent.solution intact — warm-start will use it
```

This is a ~10-line change in `betas_obj_func_educ`. Expected speedup on `AggDemandEconomy.solve()` within the NM loop: **2–3×** on the solver step (the fraction that was cold-solved, ~1/3, drops from cold to warm).

**Validation requirements.**
1. Confirm numerical equivalence at converged `(β, ∇, GICx)` — warm-start should only change the path to convergence, not the converged point.
2. Confirm `_mtc(TypeListAll, ['solve()', ...])` still produces the same wealth-distribution targets.
3. Test on a short NM run (say, 10 iterations) to see iteration-count drop from ~5-15 per solve to ~1-2 per solve.

## Double-solve (investigation needed)

Line 1009 calls `AggDemandEconomy.solve()`; line 1026 calls `_mtc(TypeListAll, ['solve()', 'initialize_sim()', 'simulate()', 'save_state()'])`. Both solve the agents. The second one is inside `_mtc` (multi-thread commands) which processes agents via a command-string-eval mechanism.

It is not immediately clear from the code whether:
- (a) line 1026's `'solve()'` is redundant because 1009 already solved — maybe `_mtc` solves the agents in a different way (e.g., different arguments), or
- (b) line 1026's `'solve()'` is needed because something between 1009 and 1026 invalidates the solution, or
- (c) the `'solve()'` in baseline_commands is redundant and could be dropped for a ~2× speedup in the NM iteration.

This is a measurement question — profile one NM iter and see whether the second solve actually does work.

## Parallel simplex (Phase 1.1)

HARK's `minimize_nelder_mead` wraps scipy's standard serial NM. Parallelizing simplex vertex evaluations requires replacing the NM driver with a concurrent-aware variant (or using `scipy.optimize.differential_evolution` which is natively parallel but a different algorithm). This is a larger change than Phase 1.2 and should be done after Phase 1.2 lands.

## Recommendation for next steps

1. **Run step 1 (in progress, background task `b4l4wyro6`)** to confirm the pipeline works end-to-end on current code.
2. **Implement the in-place update prototype** (Phase 1.2) on a non-production branch.
3. **Validate numerical equivalence** at 10-NM-iteration scale against the current code.
4. **Measure speedup** at Reduced_Run scope (not Baseline — still too expensive) to get a representative number before committing to a Baseline production rerun.
5. Defer Phase 1.1 (parallel simplex) until 1.2 is landed and measured.

The prototype is ~10 lines of code, ~0 validation compute, and would be worth approximately a 1.5× speedup on step 2 — cutting the 48 h Baseline bucket to ~32 h.
