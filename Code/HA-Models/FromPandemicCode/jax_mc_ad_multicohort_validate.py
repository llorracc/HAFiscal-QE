"""
Step 11: validate multi-cohort JAX AD outer loop at Reduced_Run.

Generates HARK Reduced_Run AD reference, then runs JAX-backed multi-cohort
solve_ad_recession and compares Cratio_hist + wall time.
"""
import sys, os, pickle, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv_save = list(sys.argv)
sys.argv = [sys.argv_save[0]]

import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base
from jax_mc_ad_multicohort import solve_ad_recession_jax_multicohort


def gen_hark_ref(param='Reduced_Run', out_pkl=None):
    print(f"=== HARK AD ref: {param} ===", flush=True)
    ctx = build_and_solve(param)
    AggEco = ctx['AggEco']
    _ = run_base(ctx)
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')
    num_iter = ctx['num_max_iterations_solvingAD']
    cutoff = ctx['convergence_tol_solvingAD']

    iter_logs = []
    orig_run = eco.run_experiment

    def logged_run(*args, **kwargs):
        result = orig_run(*args, **kwargs)
        per_cohort_t0 = []
        for ThisType in eco.agents:
            per_cohort_t0.append({
                'aNrm_t0': np.asarray(ThisType.history['aNrm'][0]),
                'pLvl_t0': np.asarray(ThisType.history['pLvl'][0]),
                'Mrkv_t0': np.asarray(ThisType.shock_history['Mrkv'][0]),
            })
        iter_logs.append({
            'Cratio_hist': np.asarray(result['Cratio_hist']),
            'AggCons': np.asarray(result['AggCons']),
            'per_cohort_t0': per_cohort_t0,
        })
        return result

    eco.run_experiment = logged_run
    t0 = time.time()
    eco.solve_ad_recession(num_max_iterations=num_iter,
                            convergence_cutoff=cutoff, name=None)
    wall = time.time() - t0
    print(f"HARK AD: {wall:.1f}s in {len(iter_logs)} iters", flush=True)

    ref = {
        'iter_logs': iter_logs,
        'wall': wall,
        'num_iters': len(iter_logs),
        'base_AggCons': np.asarray(eco.base_AggCons),
        'ADelasticity': float(eco.ADelasticity),
        'num_base_MrkvStates': int(eco.num_base_MrkvStates),
        'num_experiment_periods': int(eco.num_experiment_periods),
        'convergence_cutoff': cutoff,
        'cohort_pop_factors': [float(getattr(a, 'pop_rescale_factor', 1.0))
                                for a in eco.agents],
        'cohort_AgentCount': [int(a.AgentCount) for a in eco.agents],
    }
    if out_pkl:
        os.makedirs(os.path.dirname(out_pkl), exist_ok=True)
        with open(out_pkl, 'wb') as f:
            pickle.dump(ref, f)
    return ref


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--param', default='Reduced_Run')
    p.add_argument('--ref', default='welfare6_RR_ad_ref/recession_AD.pkl')
    p.add_argument('--gen-ref', action='store_true', help='Regenerate HARK ref even if cached')
    args = p.parse_args(sys.argv_save[1:])

    sys.argv = [sys.argv_save[0]]

    if args.gen_ref or not os.path.exists(args.ref):
        ref = gen_hark_ref(args.param, args.ref)
    else:
        ref = pickle.load(open(args.ref, 'rb'))
        print(f"Loaded cached HARK ref: {args.ref}")

    print(f"\n=== JAX AD multicohort at {args.param} ===", flush=True)
    ctx = build_and_solve(args.param)
    AggEco = ctx['AggEco']
    _ = run_base(ctx)
    eco = deepcopy(AggEco)

    # init from HARK's last-iter per-cohort panels
    init_panels = []
    J = eco.num_base_MrkvStates
    for c in ref['iter_logs'][-1]['per_cohort_t0']:
        aNrm0 = c['aNrm_t0'].astype(np.float32)
        pLvl0 = c['pLvl_t0'].astype(np.float32)
        micro0 = (c['Mrkv_t0'] % J).astype(np.int32)
        init_panels.append((aNrm0, pLvl0, micro0))

    result = solve_ad_recession_jax_multicohort(
        eco, ref['base_AggCons'],
        num_max_iterations=ref['num_iters'] + 2,
        convergence_cutoff=ref['convergence_cutoff'],
        shock_type='recession',
        init_panels=init_panels,
        seeds=(0, 1, 2, 3),
        verbose=True)

    jax_c = result['final_Cratio_hist']
    hark_c = ref['iter_logs'][-1]['Cratio_hist']
    num_exp = ref['num_experiment_periods']
    n_act = num_exp + 12
    print(f"\nJAX  final Cratio[:12]: {jax_c[:12]}")
    print(f"HARK final Cratio[:12]: {hark_c[:12]}")
    rel = (jax_c - hark_c) / hark_c
    print(f"\nMax |rel diff| Cratio (first {n_act}): "
          f"{np.max(np.abs(rel[:n_act])):.4f}")
    print(f"Mean ratio JAX/HARK (active): "
          f"{np.mean(jax_c[:n_act]) / np.mean(hark_c[:n_act]):.4f}")
    print(f"\nWall: JAX {result['wall_time']:.1f}s vs HARK {ref['wall']:.1f}s "
          f"= {ref['wall'] / max(result['wall_time'], 0.01):.1f}x speedup")
    print(f"Iters: JAX {len(result['iter_history'])} vs HARK {ref['num_iters']}")


if __name__ == '__main__':
    main()
