"""
Regenerate Baseline HARK AD reference, dumping additional per-cohort t_age_t0
for the residual-bias diagnosis (Test 3).
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base


def main():
    out_dir = 'welfare6_BL_ad_ref_v2'
    os.makedirs(out_dir, exist_ok=True)

    t0 = time.time()
    ctx = build_and_solve('Baseline')
    print(f"build_and_solve: {time.time()-t0:.1f}s", flush=True)
    AggEco = ctx['AggEco']
    _ = run_base(ctx)
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')

    # Add t_age to track_vars (so history['t_age'][0] gets dumped during sim)
    for agent in eco.agents:
        if 't_age' not in agent.track_vars:
            agent.track_vars = list(agent.track_vars) + ['t_age']

    num_iter = ctx['num_max_iterations_solvingAD']
    cutoff = ctx['convergence_tol_solvingAD']

    iter_logs = []
    orig_run = eco.run_experiment

    def logged_run(*args, **kwargs):
        result = orig_run(*args, **kwargs)
        per_cohort_t0 = []
        for ThisType in eco.agents:
            entry = {
                'aNrm_t0': np.asarray(ThisType.history['aNrm'][0]),
                'pLvl_t0': np.asarray(ThisType.history['pLvl'][0]),
                'Mrkv_t0': np.asarray(ThisType.shock_history['Mrkv'][0]),
            }
            if 't_age' in ThisType.history:
                entry['t_age_t0'] = np.asarray(ThisType.history['t_age'][0])
            per_cohort_t0.append(entry)
        iter_logs.append({
            'Cratio_hist': np.asarray(result['Cratio_hist']),
            'AggCons': np.asarray(result['AggCons']),
            'per_cohort_t0': per_cohort_t0,
        })
        return result

    eco.run_experiment = logged_run
    t_ad = time.time()
    eco.solve_ad_recession(num_max_iterations=num_iter,
                            convergence_cutoff=cutoff, name=None)
    wall = time.time() - t_ad
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
    out_pkl = os.path.join(out_dir, 'recession_AD.pkl')
    with open(out_pkl, 'wb') as f:
        pickle.dump(ref, f)
    print(f"Saved: {out_pkl}", flush=True)
    # Quick stats on t_age0
    for c_idx, c in enumerate(ref['iter_logs'][-1]['per_cohort_t0']):
        if 't_age_t0' in c:
            ta = c['t_age_t0']
            print(f"  cohort {c_idx:2d} t_age_t0: min={ta.min()} max={ta.max()} "
                  f"mean={ta.mean():.2f} median={np.median(ta):.1f}", flush=True)


if __name__ == '__main__':
    main()
