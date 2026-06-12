"""Baseline 5x (N=160000) wall-time benchmark: JAX MC vs HARK.

Measures:
  - JAX MC kernel call time (after JIT) at Baseline 5x dimensions
  - JAX AD outer loop wall time vs HARK
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)

import numpy as np
import jax.numpy as jnp
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base
from jax_mc_ad_multicohort import solve_ad_recession_jax_multicohort


def main():
    print("=== Baseline 5x wall-time benchmark (JAX MC) ===", flush=True)
    print(f"AGENTCOUNT_TOTAL = {os.environ.get('HAFISCAL_AGENTCOUNT_TOTAL', 'NOT_SET')}", flush=True)
    print(f"AD_MAX_ITER = {os.environ.get('HAFISCAL_AD_MAX_ITER', 'NOT_SET')}", flush=True)

    t0 = time.time()
    ctx = build_and_solve('Baseline')
    AggEco = ctx['AggEco']
    print(f"build_and_solve: {time.time()-t0:.1f}s (n_cohorts={len(AggEco.agents)})", flush=True)

    t0 = time.time()
    _ = run_base(ctx)
    print(f"run_base: {time.time()-t0:.1f}s", flush=True)

    # Print scale
    total_N = sum(a.AgentCount for a in AggEco.agents)
    print(f"Total agents across cohorts: {total_N}", flush=True)

    # JAX AD recession (no policy)
    print("\nRunning JAX AD recession ...", flush=True)
    eco_j = deepcopy(AggEco)

    # Get HARK init panels (needed for proper Cratio).
    # For 5x benchmark, take just the post-burn-in state directly (skip HARK AD run).
    init_panels = []
    for a in AggEco.agents:
        aNrm_b = np.asarray(getattr(a, 'aNrm_base', a.state_now.get('aNrm', np.zeros(a.AgentCount)))).astype(np.float32)
        pLvl_b = np.asarray(getattr(a, 'pLvl_base', a.state_now.get('pLvl', np.ones(a.AgentCount)))).astype(np.float32)
        micro0 = np.zeros(a.AgentCount, dtype=np.int32)  # approx (Mrkv spike skipped for benchmark)
        init_panels.append((aNrm_b, pLvl_b, micro0))

    t0 = time.time()
    res = solve_ad_recession_jax_multicohort(
        eco_j, eco_j.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recession', init_panels=init_panels,
        seeds=(0, 1, 2, 3), verbose=True)
    wall_jax = time.time() - t0
    print(f"\n=== Baseline 5x: JAX AD recession wall = {wall_jax:.1f}s ({wall_jax/60:.1f} min) ===")
    print(f"Iters: {len(res['iter_history'])}, converged: {res['converged']}")
    print(f"Cratio[0]: {res['final_Cratio_hist'][0]:.4f}")

    # Compare to known HARK Baseline timing (~35 min from prior measurements)
    HARK_baseline_min = 35.0
    print(f"\nReference: HARK Baseline recession AD ≈ {HARK_baseline_min:.1f} min from earlier overnight run")
    speedup = (HARK_baseline_min * 60) / wall_jax if wall_jax > 0 else float('inf')
    print(f"Implied JAX/HARK speedup: {speedup:.1f}x")


if __name__ == '__main__':
    main()
