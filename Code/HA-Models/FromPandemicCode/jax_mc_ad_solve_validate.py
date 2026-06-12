"""
Step 8.4 Phase B validation: full JAX-backed AD outer loop vs HARK.

Runs solve_ad_recession_jax on HS_Only and compares per-iter Cratio_hist
and final converged values to HARK's iter_logs.
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base
from jax_mc_ad_solve import solve_ad_recession_jax


def main():
    print("=== Step 8.4 Phase B — Full JAX AD outer loop vs HARK ===\n",
          flush=True)
    ref = pickle.load(open('welfare6_HS_ad_ref/recession_AD.pkl', 'rb'))
    print(f"HARK ref: {ref['num_iters']} iters")
    for k, it in enumerate(ref['iter_logs']):
        print(f"  iter {k+1}: Cratio_hist[0]={it['Cratio_hist'][0]:.4f}")

    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    base_result = run_base(ctx)
    base_AggCons = AggEco.base_AggCons

    eco = deepcopy(AggEco)

    # Use HARK's last-iter init state for fair MC comparison
    last_iter = ref['iter_logs'][-1]
    J = eco.num_base_MrkvStates
    h_aNrm0 = np.asarray(last_iter['aNrm_t0']).astype(np.float32)
    h_pLvl0 = np.asarray(last_iter['pLvl_t0']).astype(np.float32)
    h_micro0 = (np.asarray(last_iter['Mrkv_t0']) % J).astype(np.int32)

    t_start = time.time()
    result = solve_ad_recession_jax(
        eco, base_AggCons,
        num_max_iterations=ref['num_iters'] + 2,
        convergence_cutoff=ref['convergence_cutoff'],
        shock_type='recession',
        init_aNrm=h_aNrm0, init_pLvl=h_pLvl0, init_micro=h_micro0,
        seeds=(0, 1, 2, 3),
        verbose=True)
    print(f"\nJAX AD wall: {result['wall_time']:.1f}s in {len(result['iter_history'])} iters; "
          f"converged={result['converged']}")
    print(f"HARK AD wall: ~18.8s in {ref['num_iters']} iters")

    # Compare final Cratio_hist
    jax_c = result['final_Cratio_hist']
    hark_c = ref['iter_logs'][-1]['Cratio_hist']
    print(f"\nJAX  final Cratio[:12]: {jax_c[:12]}")
    print(f"HARK final Cratio[:12]: {hark_c[:12]}")
    rel = (jax_c - hark_c) / hark_c
    print(f"\nMax |rel diff| Cratio (first {ref['num_experiment_periods']+12}): "
          f"{np.max(np.abs(rel[:ref['num_experiment_periods']+12])):.4f}")
    print(f"Mean ratio JAX/HARK Cratio (active): "
          f"{np.mean(jax_c[:ref['num_experiment_periods']+12]) / np.mean(hark_c[:ref['num_experiment_periods']+12]):.4f}")


if __name__ == '__main__':
    main()
