"""
HARK ref v4: also captures per-period post-sim_birth state (aNrm, pLvl).

Wraps each agent's get_mortality with a hook that records state_now AFTER
sim_birth (which is what HARK then copies to state_prev for use in transition).
This is the missing piece for FULLY bit-aligned JAX replay — eliminates the
newborn-replacement realization mismatch on top of shock-realization mismatch.
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base


def main():
    out_dir = 'welfare6_BL_ad_ref_v4'
    os.makedirs(out_dir, exist_ok=True)

    t0 = time.time()
    ctx = build_and_solve('Baseline')
    print(f"build_and_solve: {time.time()-t0:.1f}s", flush=True)
    AggEco = ctx['AggEco']
    _ = run_base(ctx)
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')

    # Wrap each agent's get_mortality to capture post-sim_birth state
    captured = {id(a): {'aNrm_init': [], 'pLvl_init': []} for a in eco.agents}
    for agent in eco.agents:
        orig_mort = agent.get_mortality
        cap = captured[id(agent)]
        def make_wrapper(agent_ref, cap_ref, orig_fn):
            def wrapped():
                orig_fn()
                # state_now['aNrm'] and ['pLvl'] now reflect sim_birth's reset
                # for dead agents (alive agents have their prior state_now values)
                cap_ref['aNrm_init'].append(np.asarray(agent_ref.state_now['aNrm']).copy())
                cap_ref['pLvl_init'].append(np.asarray(agent_ref.state_now['pLvl']).copy())
            return wrapped
        agent.get_mortality = make_wrapper(agent, cap, orig_mort)
        if 't_age' not in agent.track_vars:
            agent.track_vars = list(agent.track_vars) + ['t_age']

    num_iter = ctx['num_max_iterations_solvingAD']
    cutoff = ctx['convergence_tol_solvingAD']

    iter_logs = []
    orig_run = eco.run_experiment

    def logged_run(*args, **kwargs):
        # Clear captured between iterations (only keep final iter's capture)
        for cap_v in captured.values():
            cap_v['aNrm_init'].clear()
            cap_v['pLvl_init'].clear()
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
                # NEW v4: post-sim_birth state per period (T, N)
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
        'cohort_T_age': [int(getattr(a, 'T_age', 100) or 100) for a in eco.agents],
    }
    out_pkl = os.path.join(out_dir, 'recession_AD.pkl')
    with open(out_pkl, 'wb') as f:
        pickle.dump(ref, f)
    print(f"Saved: {out_pkl}", flush=True)
    sz_mb = os.path.getsize(out_pkl) / (1024*1024)
    print(f"File size: {sz_mb:.1f} MB", flush=True)
    # Sanity: print captured shapes
    p0 = iter_logs[-1]['per_cohort'][0]
    print(f"Cohort 0 capture shapes: aNrm_init_perperiod={p0['aNrm_init_perperiod'].shape}, "
          f"shock_Mrkv={p0['shock_Mrkv'].shape}", flush=True)


if __name__ == '__main__':
    main()
