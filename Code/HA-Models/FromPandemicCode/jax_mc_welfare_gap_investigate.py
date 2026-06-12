"""Investigate the 6% welfare gap: where does it accumulate?

For HS_Only check_rec_AD, compute period-by-period:
  - HARK Cratio[t] for recession_AD and recessionCheck_AD
  - JAX  Cratio[t] for recession_AD and recessionCheck_AD
  - Cell-by-cell welfare felicity diff at each t

Hypothesis A: bias concentrated at t=0 only (e.g., Check delivery timing)
Hypothesis B: bias accumulates linearly across periods (drift)
Hypothesis C: bias scales with Cratio level (multiplicative)
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)

import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base
from jax_mc_ad_multicohort import solve_ad_recession_jax_multicohort


def run_hark_scenario(eco, shock_type, num_exp, num_iter, cutoff):
    eco_h = deepcopy(eco)
    eco_h.switch_shock_type(shock_type)
    if shock_type == 'recession':
        eco_h.solve_ad_recession(num_max_iterations=num_iter,
                                  convergence_cutoff=cutoff, name=shock_type)
    elif shock_type == 'recessionCheck':
        eco_h.solve_ad_check_recession(num_max_iterations=num_iter,
                                        convergence_cutoff=cutoff, name=shock_type)
    eco_h.restore_ADsolution(name=shock_type)
    rec_dict = {
        'shock_type': shock_type, 'UpdatePrb': 1.0,
        'Splurge': eco_h.agents[0].Splurge,
        'EconomyMrkv_init': list(np.arange(1, num_exp + 1) * 2 + 1) + [1]*12 + [0]*20,
    }
    return eco_h.run_experiment(**rec_dict, Full_Output=True)


def main():
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    base_result = run_base(ctx)
    num_exp = ctx['num_experiment_periods']

    print("\n[HARK] recession_AD ...", flush=True)
    hark_rec = run_hark_scenario(AggEco, 'recession', num_exp,
                                   ctx['num_max_iterations_solvingAD'],
                                   ctx['convergence_tol_solvingAD'])
    print("[HARK] recessionCheck_AD ...", flush=True)
    hark_chk = run_hark_scenario(AggEco, 'recessionCheck', num_exp,
                                   ctx['num_max_iterations_solvingAD'],
                                   ctx['convergence_tol_solvingAD'])

    print("\n[JAX-autoinit] recession_AD ...", flush=True)
    eco_j = deepcopy(AggEco)
    jax_rec = solve_ad_recession_jax_multicohort(
        eco_j, eco_j.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recession', init_panels=None,
        seeds=(0, 1, 2, 3), verbose=False)
    print("[JAX-autoinit] recessionCheck_AD ...", flush=True)
    eco_j2 = deepcopy(AggEco)
    jax_chk = solve_ad_recession_jax_multicohort(
        eco_j2, eco_j2.base_AggCons,
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'],
        shock_type='recessionCheck', init_panels=None,
        seeds=(0, 1, 2, 3), verbose=False)

    Tprint = 20
    h_rec_c = np.asarray(hark_rec['Cratio_hist'])[:Tprint]
    h_chk_c = np.asarray(hark_chk['Cratio_hist'])[:Tprint]
    j_rec_c = np.asarray(jax_rec['final_Cratio_hist'])[:Tprint]
    j_chk_c = np.asarray(jax_chk['final_Cratio_hist'])[:Tprint]

    print("\n=== Cratio period-by-period (recession_AD) ===")
    print(f"{'t':>3} {'HARK':>8} {'JAX':>8} {'JAX-HARK':>10} {'%':>7}")
    for t in range(Tprint):
        d = j_rec_c[t] - h_rec_c[t]
        p = d / h_rec_c[t] * 100
        print(f"{t:>3} {h_rec_c[t]:>8.4f} {j_rec_c[t]:>8.4f} {d:>+10.4f} {p:>+6.2f}%")

    print("\n=== Cratio period-by-period (recessionCheck_AD) ===")
    print(f"{'t':>3} {'HARK':>8} {'JAX':>8} {'JAX-HARK':>10} {'%':>7}")
    for t in range(Tprint):
        d = j_chk_c[t] - h_chk_c[t]
        p = d / h_chk_c[t] * 100
        print(f"{t:>3} {h_chk_c[t]:>8.4f} {j_chk_c[t]:>8.4f} {d:>+10.4f} {p:>+6.2f}%")

    # Check the off-by-one hypothesis: does JAX[t] match HARK[t+1] better?
    print("\n=== Off-by-one test (recessionCheck_AD): JAX[t] vs HARK[t+1] ===")
    print(f"{'t':>3} {'HARK[t+1]':>10} {'JAX[t]':>8} {'diff':>10} {'%':>7}")
    for t in range(min(Tprint, len(j_chk_c) - 1)):
        d = j_chk_c[t] - h_chk_c[t + 1]
        p = d / h_chk_c[t + 1] * 100
        print(f"{t:>3} {h_chk_c[t+1]:>10.4f} {j_chk_c[t]:>8.4f} {d:>+10.4f} {p:>+6.2f}%")

    # AggCons comparison at t=0 for recessionCheck — does JAX over-deliver Check?
    print("\n=== AggCons[0] (HARK includes Check at t=0) ===")
    print(f"HARK recession[0]:      {hark_rec['AggCons'][0]:.4f}")
    print(f"HARK recessionCheck[0]: {hark_chk['AggCons'][0]:.4f}")
    print(f"  HARK Check boost t=0: {hark_chk['AggCons'][0] - hark_rec['AggCons'][0]:+.4f}")
    print(f"JAX  recession[0]:      {jax_rec['final_AggCons'][0]:.4f}")
    print(f"JAX  recessionCheck[0]: {jax_chk['final_AggCons'][0]:.4f}")
    print(f"  JAX  Check boost t=0: {jax_chk['final_AggCons'][0] - jax_rec['final_AggCons'][0]:+.4f}")


if __name__ == '__main__':
    main()
