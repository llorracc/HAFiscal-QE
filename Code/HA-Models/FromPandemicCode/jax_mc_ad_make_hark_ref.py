"""
Generate HARK AD-loop reference: HS_Only base recession.

Dumps per-iteration Cratio_hist, MacroCFunc (intercept/slope), and final
converged values for JAX validation.
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve


def main():
    out_dir = 'welfare6_HS_ad_ref'
    os.makedirs(out_dir, exist_ok=True)

    t0 = time.time()
    ctx = build_and_solve('HS_Only')
    print(f"build+solve: {time.time() - t0:.1f}s", flush=True)

    AggEco = ctx['AggEco']
    # Run base scenario first to populate base_AggCons (needed for Cratio_hist)
    from welfare6_scenario import run_base
    print("Running base scenario for base_AggCons...", flush=True)
    _ = run_base(ctx)

    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')
    num_iter = ctx['num_max_iterations_solvingAD']
    cutoff = ctx['convergence_tol_solvingAD']

    # Wrap run_experiment to capture per-iteration Cratio_hist
    iter_logs = []
    orig_run = eco.run_experiment

    def logged_run(*args, **kwargs):
        result = orig_run(*args, **kwargs)
        iter_logs.append({
            'Cratio_hist': np.asarray(result['Cratio_hist']),
            'AggCons': np.asarray(result['AggCons']),
            'AggIncome': np.asarray(result['AggIncome']),
            'aNrm_t0': np.asarray(result['aNrm_all'][0]),
            'pLvl_t0': np.asarray(result['pLvl_all'][0]),
            'Mrkv_t0': np.asarray(result['Mrkv_hist'][0]),
        })
        return result

    eco.run_experiment = logged_run

    t_ad = time.time()
    eco.solve_ad_recession(
        num_max_iterations=num_iter, convergence_cutoff=cutoff,
        name=None)
    wall = time.time() - t_ad
    print(f"AD solve: {wall:.1f}s in {len(iter_logs)} iters", flush=True)

    # Extract final CFunc (intercept/slope per state pair)
    n = len(eco.CFunc)
    intercept = np.array([[eco.CFunc[i][j].intercept for j in range(n)] for i in range(n)])
    slope = np.array([[eco.CFunc[i][j].slope for j in range(n)] for i in range(n)])
    macro_intercept = np.array([[eco.MacroCFunc[i][j].intercept for j in range(len(eco.MacroCFunc))]
                                 for i in range(len(eco.MacroCFunc))])
    macro_slope = np.array([[eco.MacroCFunc[i][j].slope for j in range(len(eco.MacroCFunc))]
                            for i in range(len(eco.MacroCFunc))])

    ref = {
        'iter_logs': iter_logs,
        'final_CFunc_intercept': intercept,
        'final_CFunc_slope': slope,
        'final_MacroCFunc_intercept': macro_intercept,
        'final_MacroCFunc_slope': macro_slope,
        'num_iters': len(iter_logs),
        'convergence_cutoff': cutoff,
        'base_AggCons': np.asarray(eco.base_AggCons),
        'ADelasticity': float(eco.ADelasticity),
        'num_base_MrkvStates': int(eco.num_base_MrkvStates),
        'num_experiment_periods': int(eco.num_experiment_periods),
    }
    with open(os.path.join(out_dir, 'recession_AD.pkl'), 'wb') as f:
        pickle.dump(ref, f)
    print(f"Saved: {os.path.join(out_dir, 'recession_AD.pkl')}", flush=True)
    print(f"Final Cratio_hist (first 12): {iter_logs[-1]['Cratio_hist'][:12]}", flush=True)


if __name__ == '__main__':
    main()
