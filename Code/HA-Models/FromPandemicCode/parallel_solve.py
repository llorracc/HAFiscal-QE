"""Cohort parallelization for AggregateDemandEconomy.solve().

Drop-in parallel replacement for eco.solve() that distributes the per-cohort
HARK solves across multiprocessing workers via fork (avoiding pickle issues
with the AggregateDemandEconomy lambda ADFunc).

Usage (programmatic):
    from parallel_solve import parallel_eco_solve
    parallel_eco_solve(eco, n_workers=8)

Usage (env flag, monkey-patches eco.solve):
    HAFISCAL_PARALLEL_SOLVE=8 python ...
    # then welfare6_scenario / run_welfare6_parallel calls eco.solve() — parallel.

The implementation uses module-level globals (`_AGENTS_CACHE`, `_FROM_SOLUTIONS`)
so workers can access agents via index without pickling the agent objects
through the multiprocessing queue. Returns ConsumerSolution per agent
(picklable).

IMPORTANT: set OMP_NUM_THREADS=1 (or low) before parallelizing — otherwise
numpy BLAS threads in each worker oversubscribe the CPU.
"""
from __future__ import annotations
import os
import multiprocessing as mp


# Module-level state for fork-based parallel solve
_AGENTS_CACHE = None
_FROM_SOLUTIONS = None


def _solve_worker(idx):
    """Worker: solve agent at _AGENTS_CACHE[idx], return (idx, solution).

    Runs in a forked subprocess. Reads agent + from_solution from the
    module globals (inherited via fork). Returns ConsumerSolution which
    pickles fine for return to parent.
    """
    from HARK.core import solve_agent
    agent = _AGENTS_CACHE[idx]
    from_sol = _FROM_SOLUTIONS[idx] if _FROM_SOLUTIONS else None
    agent.pre_solve()
    solution = solve_agent(agent, False, from_solution=from_sol)
    agent.post_solve()
    return idx, solution


def parallel_eco_solve(eco, n_workers=None, warm_start=True, verbose=False):
    """Parallel replacement for eco.solve() — solves all cohorts concurrently.

    Args:
      eco: AggregateDemandEconomy with .agents list
      n_workers: number of parallel workers (default: env var or N_cohorts capped at cpu_count)
      warm_start: pass previous solution as from_solution (matches HARK warm_start)
      verbose: print timing info
    """
    global _AGENTS_CACHE, _FROM_SOLUTIONS

    n_cohorts = len(eco.agents)
    if n_workers is None:
        env = os.environ.get('HAFISCAL_PARALLEL_SOLVE', '')
        if env.isdigit() and int(env) > 0:
            n_workers = int(env)
        else:
            n_workers = min(n_cohorts, os.cpu_count() or 1)
    n_workers = max(1, min(n_workers, n_cohorts))

    if n_workers == 1:
        # Sequential fallback (no fork overhead)
        return _sequential_solve(eco, warm_start=warm_start)

    # Build from_solutions (warm-start cache) in parent
    from_solutions = []
    for agent in eco.agents:
        from_sol = None
        if warm_start and hasattr(agent, 'solution') and agent.solution and len(agent.solution) > 0:
            prev_sol = agent.solution[0]
            current_states = agent.MrkvArray[0].shape[0]
            prev_states = len(prev_sol.vPfunc) if hasattr(prev_sol, 'vPfunc') else 0
            if prev_states == current_states:
                from_sol = prev_sol
        from_solutions.append(from_sol)

    # Set module globals BEFORE forking so workers inherit them
    _AGENTS_CACHE = list(eco.agents)
    _FROM_SOLUTIONS = from_solutions

    if verbose:
        import time
        t0 = time.time()
        print(f"[parallel_solve] {n_cohorts} cohorts / {n_workers} workers ...",
              flush=True)

    try:
        # Force fork start method on Linux; on macOS it changed to spawn in Py3.8+
        ctx = mp.get_context('fork')
        with ctx.Pool(n_workers) as pool:
            results = pool.map(_solve_worker, range(n_cohorts))
    finally:
        # Clear globals so they're not held in memory
        _AGENTS_CACHE = None
        _FROM_SOLUTIONS = None

    # Assign solutions back to agents
    for idx, sol in results:
        eco.agents[idx].solution = sol

    if verbose:
        print(f"[parallel_solve] done in {time.time()-t0:.2f}s", flush=True)


def _sequential_solve(eco, warm_start=True):
    """Sequential fallback (matches AggregateDemandEconomy.solve)."""
    from HARK.core import solve_agent
    for agent in eco.agents:
        from_solution = None
        if warm_start and hasattr(agent, 'solution') and agent.solution and len(agent.solution) > 0:
            prev_sol = agent.solution[0]
            current_states = agent.MrkvArray[0].shape[0]
            prev_states = len(prev_sol.vPfunc) if hasattr(prev_sol, 'vPfunc') else 0
            if prev_states == current_states:
                from_solution = prev_sol
        agent.pre_solve()
        agent.solution = solve_agent(agent, False, from_solution=from_solution)
        agent.post_solve()


def install_parallel_solve_via_env(eco):
    """If HAFISCAL_PARALLEL_SOLVE is set, replace eco.solve with parallel version.

    Returns True if installed, False if env var not set or value is invalid.
    """
    env = os.environ.get('HAFISCAL_PARALLEL_SOLVE', '')
    if not env or env == '0':
        return False
    try:
        n_workers = int(env) if env.isdigit() else None  # None = auto
    except ValueError:
        return False
    # Monkey-patch: bind parallel_eco_solve as eco.solve
    original_solve = eco.solve
    def _patched_solve(self=eco, warm_start=True):
        parallel_eco_solve(self, n_workers=n_workers, warm_start=warm_start)
    # Preserve original under _solve_sequential for debugging
    eco._solve_sequential = original_solve
    eco.solve = _patched_solve
    print(f"[parallel_solve] eco.solve patched with parallel ({n_workers or 'auto'} workers)",
          flush=True)
    return True
