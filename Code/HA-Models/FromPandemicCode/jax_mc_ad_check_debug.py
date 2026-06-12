"""Surgical debug of Check-under-AD bug.

Steps:
1. Run JAX recession (no policy) → baseline Cratio
2. Run JAX 'recessionCheck' BUT with check_dollars=zero → must match #1
3. Run JAX 'recessionCheck' with actual check_dollars → compare to HARK
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
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    _ = run_base(ctx)

    # Get HARK init panels first
    print("\n=== Setup: HARK reference for init panels ===")
    from copy import deepcopy as _dc
    eco_h = _dc(AggEco)
    eco_h.switch_shock_type('recession')
    captured_init = []
    orig_run = eco_h.run_experiment
    def logged_run(*args, **kwargs):
        r = orig_run(*args, **kwargs)
        for ThisType in eco_h.agents:
            captured_init.append({
                'aNrm0': np.asarray(ThisType.history['aNrm'][0]),
                'pLvl0': np.asarray(ThisType.history['pLvl'][0]),
                'micro0': (np.asarray(ThisType.shock_history['Mrkv'][0]) % ThisType.num_base_MrkvStates).astype(np.int32),
            })
        return r
    eco_h.run_experiment = logged_run
    eco_h.solve_ad_recession(
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'], name=None)
    init_panels = [(c['aNrm0'].astype(np.float32), c['pLvl0'].astype(np.float32),
                    c['micro0']) for c in captured_init[-len(eco_h.agents):]]
    print(f"Captured {len(init_panels)} init panel(s)")

    # Test 1: pure recession (no policy) — production default init now uses aNrm_base
    print("\n=== Test 1: JAX recession (no policy, production default init) ===")
    eco1 = deepcopy(AggEco)
    res1 = solve_ad_recession_jax_multicohort(
        eco1, eco1.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recession',
        seeds=(0, 1, 2, 3), verbose=False)
    cratio_recession = res1['final_Cratio_hist']
    print(f"recession Cratio[:5]: {cratio_recession[:5]}")

    # Test 2: recessionCheck WITHOUT explicit init_panels (production default now uses aNrm_base/pLvl_base)
    print("\n=== Test 2: JAX recessionCheck (production default init) ===")
    eco2 = deepcopy(AggEco)
    res2 = solve_ad_recession_jax_multicohort(
        eco2, eco2.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recessionCheck',
        seeds=(0, 1, 2, 3), verbose=False)
    cratio_check = res2['final_Cratio_hist']
    print(f"recessionCheck Cratio[:5]: {cratio_check[:5]}")
    print(f"Check effect (Cratio_check / Cratio_recession): {cratio_check[0]/cratio_recession[0]:.4f}")
    print(f"Expected: Check should BOOST Cratio[0] above recession")


if __name__ == '__main__':
    main()
