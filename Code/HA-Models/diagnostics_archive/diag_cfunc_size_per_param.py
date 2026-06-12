"""
Diagnostic for the Phase A.5.1 open mystery: why is Baseline 5D
per-task wall ~100× larger than Reduced_Run extrapolation predicts?

Hypothesis: at Baseline (7 β-atoms per education group), the
integrated cFunc objects are much larger and slower per evaluation
than at Reduced_Run (1 β-atom per group).

This script inspects cFunc objects WITHOUT running the kernel, so
it's fast (~3-5 min total for build + solve + inspect at both
parametrizations).
"""
from __future__ import annotations
import os, sys, time
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve


def inspect_cfuncs(agent, label):
    """Print stats about the cFunc list on this agent."""
    cf_list = agent.solution[0].cFunc
    sizes = []
    for j, cf in enumerate(cf_list):
        # cFunc is typically LinearInterp or similar; inspect attrs
        size_info = []
        for attr in ['x_list', 'y_list', 'm_list', 'c_list']:
            if hasattr(cf, attr):
                v = getattr(cf, attr)
                if hasattr(v, '__len__'):
                    size_info.append(f"{attr}.len={len(v)}")
        # Recursive for composite cFuncs (e.g., BilinearInterp)
        for attr in ['xInterpolators']:
            if hasattr(cf, attr):
                v = getattr(cf, attr)
                if hasattr(v, '__len__'):
                    size_info.append(f"{attr}.len={len(v)}")
        sizes.append((j, type(cf).__name__, size_info))
    print(f"  {label}: {len(cf_list)} cFuncs, J = {agent.num_base_MrkvStates}")
    # Show first 3 and last 1
    for j, tname, info in sizes[:3]:
        print(f"    cFunc[{j}]: {tname} {info}")
    if len(sizes) > 3:
        j, tname, info = sizes[-1]
        print(f"    cFunc[{j}]: {tname} {info}")

    # Time a representative cFunc call
    if cf_list:
        cf = cf_list[0]
        m_test = np.linspace(0.5, 50.0, 1000)
        c_test = np.ones_like(m_test)
        # Warmup
        try:
            _ = cf(m_test, c_test)
        except Exception:
            _ = cf(m_test)
        # Time
        t0 = time.time()
        N_TRIALS = 100
        for _ in range(N_TRIALS):
            try:
                _ = cf(m_test, c_test)
            except Exception:
                _ = cf(m_test)
        wall = (time.time() - t0) / N_TRIALS * 1e6  # µs
        print(f"    avg cFunc(m_grid[1000]) call: {wall:.1f} µs")


def main():
    for param in ['Reduced_Run', 'Baseline']:
        print(f"\n=== {param} ===")
        t0 = time.time()
        ctx = build_and_solve(param)
        AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
        AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
        print(f"  build + solve: {time.time()-t0:.1f}s")
        print(f"  n_cohorts: {len(AggEco_pol.agents)}")
        print()
        print("  POL agent[0]:")
        inspect_cfuncs(AggEco_pol.agents[0], "pol")
        print()
        print("  BASE agent[0]:")
        inspect_cfuncs(AggEco_base.agents[0], "base")


if __name__ == '__main__':
    main()
