"""HARK ref v5: full AD convergence (no MAX_ITER cap) for TM-vs-MC apples-to-apples."""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base


def main():
    out_dir = 'welfare6_BL_ad_ref_v5'
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    ctx = build_and_solve('Baseline')
    print(f"build_and_solve: {time.time()-t0:.1f}s", flush=True)
    AggEco = ctx['AggEco']
    _ = run_base(ctx)
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')
    for agent in eco.agents:
        if 't_age' not in agent.track_vars:
            agent.track_vars = list(agent.track_vars) + ['t_age']

    captured = {id(a): {'aNrm_init': [], 'pLvl_init': []} for a in eco.agents}
    for agent in eco.agents:
        orig_mort = agent.get_mortality
        cap = captured[id(agent)]
        def make_wrap(a_ref, c_ref, of):
            def wrapped():
                of()
                c_ref['aNrm_init'].append(np.asarray(a_ref.state_now['aNrm']).copy())
                c_ref['pLvl_init'].append(np.asarray(a_ref.state_now['pLvl']).copy())
            return wrapped
        agent.get_mortality = make_wrap(agent, cap, orig_mort)

    # Force full AD convergence
    num_iter = 10  # plenty
    cutoff = 1e-3  # standard
    print(f"Running HARK AD with num_iter={num_iter}, tol={cutoff}", flush=True)

    iter_logs = []
    orig_run = eco.run_experiment
    def logged_run(*args, **kwargs):
        for cv in captured.values():
            cv['aNrm_init'].clear(); cv['pLvl_init'].clear()
        result = orig_run(*args, **kwargs)
        per_cohort = []
        for ThisType in eco.agents:
            cap = captured[id(ThisType)]
            entry = {
                'aNrm_t0': np.asarray(ThisType.history['aNrm'][0]),
                'pLvl_t0': np.asarray(ThisType.history['pLvl'][0]),
                'Mrkv_t0': np.asarray(ThisType.shock_history['Mrkv'][0]),
                'shock_Mrkv': np.asarray(ThisType.shock_history['Mrkv'], dtype=np.int32),
                'shock_TranShk': np.asarray(ThisType.shock_history['TranShk'], dtype=np.float64),
                'shock_PermShk': np.asarray(ThisType.shock_history['PermShk'], dtype=np.float64),
                'shock_who_dies': np.asarray(ThisType.shock_history['who_dies'], dtype=bool),
                'aNrm_init_perperiod': np.stack(cap['aNrm_init'], axis=0).astype(np.float64),
                'pLvl_init_perperiod': np.stack(cap['pLvl_init'], axis=0).astype(np.float64),
            }
            if 't_age' in ThisType.history:
                entry['t_age_t0'] = np.asarray(ThisType.history['t_age'][0])
            per_cohort.append(entry)
        iter_logs.append({
            'Cratio_hist': np.asarray(result['Cratio_hist']),
            'AggCons': np.asarray(result['AggCons']),
            'per_cohort': per_cohort,
        })
        return result

    eco.run_experiment = logged_run
    t_ad = time.time()
    eco.solve_ad_recession(num_max_iterations=num_iter, convergence_cutoff=cutoff, name=None)
    wall = time.time() - t_ad
    print(f"HARK AD: {wall:.1f}s in {len(iter_logs)} iters", flush=True)

    ref = {
        'iter_logs': iter_logs, 'wall': wall, 'num_iters': len(iter_logs),
        'base_AggCons': np.asarray(eco.base_AggCons),
        'ADelasticity': float(eco.ADelasticity),
        'num_base_MrkvStates': int(eco.num_base_MrkvStates),
        'num_experiment_periods': int(eco.num_experiment_periods),
        'convergence_cutoff': cutoff,
        'cohort_pop_factors': [float(getattr(a, 'pop_rescale_factor', 1.0)) for a in eco.agents],
        'cohort_AgentCount': [int(a.AgentCount) for a in eco.agents],
        'cohort_T_age': [int(getattr(a, 'T_age', 100) or 100) for a in eco.agents],
    }
    out_pkl = os.path.join(out_dir, 'recession_AD.pkl')
    with open(out_pkl, 'wb') as f:
        pickle.dump(ref, f)
    print(f"Saved: {out_pkl}", flush=True)
    for k, it in enumerate(iter_logs):
        print(f"  iter {k+1}: Cratio[0]={it['Cratio_hist'][0]:.5f}, mean[:32]={it['Cratio_hist'][:32].mean():.5f}", flush=True)


if __name__ == '__main__':
    main()
