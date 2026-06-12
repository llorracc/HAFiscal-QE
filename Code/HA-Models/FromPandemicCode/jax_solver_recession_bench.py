"""Benchmark: full agent.solve() at HS_Only recession scale (StateCount=132).

This is the realistic production setup — much larger than HS_Only base (6 states).
Speedup should grow with scale since per-state HARK work scales while JAX
amortizes JIT compile across more states.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)

import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve
from jax_solver_drop_in import install_jax_solver


def main():
    print("=== Benchmark: HS_Only recession (StateCount=132) ===")
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']

    # HARK at recession
    eco_h = deepcopy(AggEco)
    eco_h.switch_shock_type('recession')
    agent_h = eco_h.agents[0]
    print(f"  StateCount: {len(eco_h.CFunc)}")
    print("\n[HARK] full solve ...", flush=True)
    t0 = time.time()
    agent_h.solve()
    t_hark = time.time() - t0
    print(f"  HARK: {t_hark:.2f}s")
    sol_h = agent_h.solution[0]
    StateCount = len(sol_h.cFunc)

    # JAX at recession
    eco_j = deepcopy(AggEco)
    eco_j.switch_shock_type('recession')
    agent_j = eco_j.agents[0]
    install_jax_solver(agent_j)
    print("\n[JAX-drop-in] full solve ...", flush=True)
    t0 = time.time()
    agent_j.solve()
    t_jax = time.time() - t0
    print(f"  JAX: {t_jax:.2f}s")
    sol_j = agent_j.solution[0]

    # Compare across all 132 states
    n_query = 50
    m_query = np.linspace(1.0, 10.0, n_query)
    C_query = np.full(n_query, 1.0)

    n_pass = 0
    max_rd_per_state = []
    for j in range(StateCount):
        c_h = sol_h.cFunc[j](m_query, C_query)
        c_j = sol_j.cFunc[j](m_query, C_query)
        rd = np.abs((c_j - c_h) / np.maximum(np.abs(c_h), 1e-12))
        max_rd_per_state.append(rd.max())
        if rd.max() < 5e-3:
            n_pass += 1
    max_rd = np.asarray(max_rd_per_state)

    print(f"\n=== Results ===")
    print(f"HARK: {t_hark:.1f}s")
    print(f"JAX:  {t_jax:.1f}s")
    print(f"Speedup: {t_hark/t_jax:.2f}x" if t_jax > 0 else "Speedup: N/A (negative time bug)")
    print(f"States pass at <5e-3: {n_pass}/{StateCount}")
    print(f"Global max rel diff: {max_rd.max():.4e}")
    print(f"Global mean rel diff: {max_rd.mean():.4e}")
    if n_pass == StateCount:
        print("\n✓ P6 recession-scale validation passes")


if __name__ == '__main__':
    main()
