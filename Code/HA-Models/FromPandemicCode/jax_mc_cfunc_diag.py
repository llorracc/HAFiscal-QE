"""
Diagnose the cFunc value discrepancy.

Earlier observation: HARK's cFunc returns cNrm≈0.93 at m≈1.30, but my
tabulated cfunc_table[j, m_idx_for_1.30] returns ≈1.025. 10% gap.

This script calls HARK's cFunc directly and compares with my tabulation
at the same m values, to find where the discrepancy enters.
"""
from __future__ import annotations
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d_jax_kernel import (
    tabulate_cfunc_list, build_m_grid,
)


def main():
    print("=== cFunc value diagnostic ===")
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    AggEco.switch_shock_type('base')
    AggEco.solve()
    agent = AggEco.agents[0]
    J = int(agent.num_base_MrkvStates)
    print(f"J (num_base_MrkvStates): {J}")

    # Probe cFunc at several m values, across all Mrkv states
    M_grid_size = 500
    m_grid = build_m_grid(M_grid_size)
    cfunc_table = tabulate_cfunc_list(
        [agent.solution[0].cFunc[j] for j in range(J)],
        m_grid,
    )
    print(f"\nTabulated cFunc shape: {cfunc_table.shape}")
    print(f"m_grid sample: {m_grid[:5]} ... {m_grid[-5:]}")

    # Test points
    test_m = [0.1, 0.5, 1.0, 1.3, 2.0, 5.0, 10.0]
    print(f"\nDirect call vs tabulated lookup (Cratio=1.0):")
    print(f"{'state':<7} {'m':>6} {'direct':>10} {'tab(interp)':>14} {'diff':>10}")
    for j in range(J):
        for m in test_m:
            # Direct call: cFunc(m, Cratio=1.0)
            direct = float(agent.solution[0].cFunc[j](
                np.array([m]), np.array([1.0])
            )[0])
            # Tabulated lookup via linear interp on m_grid
            tab = float(np.interp(m, m_grid, cfunc_table[j]))
            diff = tab - direct
            print(f"{j:<7} {m:>6.2f} {direct:>10.4f} {tab:>14.4f} {diff:>+10.4f}")
        print()

    # Check if cFunc has 'fast' vs 'careful' attributes
    print(f"\ncFunc object info (state 0):")
    cf = agent.solution[0].cFunc[0]
    print(f"  type: {type(cf).__name__}")
    print(f"  module: {type(cf).__module__}")
    attrs = [a for a in dir(cf) if not a.startswith('_')]
    print(f"  attributes: {attrs[:20]}")

    # Check what happens when called via HARK MC's path
    print(f"\nHARK MC-style call (vector m, vector Cratio):")
    m_vec = np.array(test_m)
    cr_vec = np.full_like(m_vec, 1.0)
    for j in range(J):
        out = np.asarray(agent.solution[0].cFunc[j](m_vec, cr_vec))
        print(f"  j={j}: {out}")


if __name__ == '__main__':
    main()
