"""
Sanity check: HS_Only replay kernel test.

Generates HARK ref (HS_Only, ~10s presolve), dumps shock_history, runs JAX
replay, compares. If JAX-replay matches HARK to high precision at HS_Only,
the replay kernel logic is correct. Then Baseline replay test will answer
the bias question definitively.
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)

import numpy as np
import jax.numpy as jnp
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base
from jax_mc_hark_integration import extract_recession_kernel_inputs, draw_newborn_pool_from_agent
from jax_mc_ad import extract_cfunc_table_per_period, compute_AggDemandFac_path
from jax_mc_ad_replay import simulate_jax_replay


def main():
    print("=== HS_Only replay sanity check ===", flush=True)
    t0 = time.time()
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    _ = run_base(ctx)
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')
    for agent in eco.agents:
        if 't_age' not in agent.track_vars:
            agent.track_vars = list(agent.track_vars) + ['t_age']
    print(f"build/base: {time.time()-t0:.1f}s", flush=True)

    # Run HARK AD with shock dump
    iter_logs = []
    orig_run = eco.run_experiment
    def logged_run(*args, **kwargs):
        result = orig_run(*args, **kwargs)
        per_cohort = []
        for ThisType in eco.agents:
            per_cohort.append({
                'aNrm_t0': np.asarray(ThisType.history['aNrm'][0]),
                'pLvl_t0': np.asarray(ThisType.history['pLvl'][0]),
                'shock_Mrkv': np.asarray(ThisType.shock_history['Mrkv'], dtype=np.int32),
                'shock_TranShk': np.asarray(ThisType.shock_history['TranShk'], dtype=np.float64),
                'shock_PermShk': np.asarray(ThisType.shock_history['PermShk'], dtype=np.float64),
                'shock_who_dies': np.asarray(ThisType.shock_history['who_dies'], dtype=bool),
            })
        iter_logs.append({
            'Cratio_hist': np.asarray(result['Cratio_hist']),
            'AggCons': np.asarray(result['AggCons']),
            'per_cohort': per_cohort,
        })
        return result
    eco.run_experiment = logged_run

    t0 = time.time()
    eco.solve_ad_recession(num_max_iterations=ctx['num_max_iterations_solvingAD'],
                            convergence_cutoff=ctx['convergence_tol_solvingAD'], name=None)
    print(f"HARK AD: {time.time()-t0:.1f}s ({len(iter_logs)} iters)", flush=True)

    hark_cratio = iter_logs[-1]['Cratio_hist']
    hark_aggcons = iter_logs[-1]['AggCons']
    base_AggCons = np.asarray(eco.base_AggCons)

    # Install converged MacroCFunc + re-solve agents (same as diag2/diag5)
    from AggFiscalModel import CRule
    n_combined = len(eco.CFunc)
    J = eco.num_base_MrkvStates
    n_macro = n_combined // J
    num_exp = eco.num_experiment_periods
    MacroCFunc = [[CRule(1.0, 0.0) for _ in range(n_macro)] for _ in range(n_macro)]
    MacroCFunc[0][3] = CRule(float(hark_cratio[0]), 0.0)
    for j in range(num_exp - 1):
        MacroCFunc[2*j+3][2*j+5] = CRule(float(hark_cratio[j+1]), 0.0)
    MacroCFunc[2*num_exp+1][1] = CRule(float(hark_cratio[num_exp]), 0.0)
    MacroCFunc[1][1] = CRule(float(np.mean(hark_cratio[num_exp+1:num_exp+10])), 0.0)
    eco.CFunc = eco.Macro_2_Micro_CFunc(MacroCFunc)
    for agent in eco.agents:
        agent.CFunc = eco.CFunc
    eco.ADelasticity = eco.demand_ADelasticity

    t0 = time.time()
    eco.solve()
    print(f"Re-solve at converged CFunc: {time.time()-t0:.1f}s", flush=True)

    act_T = len(hark_cratio)
    EconomyMrkv_init = list(np.arange(1, num_exp+1)*2+1) + [1]*12 + [0]*20
    EconomyMrkv_path = (EconomyMrkv_init + [0]*act_T)[:act_T]
    macros = np.array(EconomyMrkv_path, dtype=int)
    Cratio_obs = np.zeros(act_T)
    Cratio_obs[0] = MacroCFunc[0][macros[0]].intercept
    for t in range(1, act_T):
        i, j = macros[t-1], macros[t]
        rule = MacroCFunc[i][j]
        Cratio_obs[t] = rule.intercept + rule.slope * (Cratio_obs[t-1] - 1.0)
    ADF_path = compute_AggDemandFac_path(Cratio_obs, EconomyMrkv_path, 1, eco.demand_ADelasticity).astype(np.float64)

    # Run JAX replay
    per_cohort = iter_logs[-1]['per_cohort']
    per_cohort_aggcons = []
    for c_idx, agent in enumerate(eco.agents):
        t_c = time.time()
        inp = extract_recession_kernel_inputs(agent, scenario='recession')
        m_grid = np.asarray(inp['m_grid']).astype(np.float64)
        cfunc_table = extract_cfunc_table_per_period(agent, Cratio_obs, m_grid,
                                                       n_combined=n_combined).astype(np.float64)
        nbA, nbP, _ = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99+c_idx)
        nbA = nbA.astype(np.float64); nbP = nbP.astype(np.float64)
        h_p = per_cohort[c_idx]
        aNrm0 = np.asarray(h_p['aNrm_t0']).astype(np.float64)
        pLvl0 = np.asarray(h_p['pLvl_t0']).astype(np.float64)
        mrkv_path = np.asarray(h_p['shock_Mrkv']).astype(np.int32)
        tran_path = np.asarray(h_p['shock_TranShk']).astype(np.float64)
        perm_path = np.asarray(h_p['shock_PermShk']).astype(np.float64)
        who_dies_path = np.asarray(h_p['shock_who_dies']).astype(bool)
        _, cons, _ = simulate_jax_replay(
            aNrm0, pLvl0, ADF_path, cfunc_table, jnp.asarray(m_grid),
            mrkv_path, tran_path, perm_path, who_dies_path,
            Rfree_macro=jnp.asarray(inp['Rfree_macro'], dtype=jnp.float64),
            PermGroFac_macro=jnp.asarray(inp['PermGroFac_macro'], dtype=jnp.float64),
            Splurge=inp['Splurge'],
            newborn_aNrm=jnp.asarray(nbA), newborn_pLvl=jnp.asarray(nbP),
            act_T=act_T, J=J)
        ac = np.asarray(cons)
        per_cohort_aggcons.append(ac)
        print(f"  cohort {c_idx} N={agent.AgentCount} JAX-replay AggCons[0]={ac[0]:.4f} wall={time.time()-t_c:.1f}s",
              flush=True)

    jax_total = np.sum(per_cohort_aggcons, axis=0)
    jax_cratio = jax_total / base_AggCons
    print(f"\n=== HS_Only Replay Summary ===")
    print(f"JAX-replay AggCons[0]={jax_total[0]:.6f}, HARK={hark_aggcons[0]:.6f}, ratio={jax_total[0]/hark_aggcons[0]:.6f}")
    print(f"JAX Cratio[:8]: {jax_cratio[:8]}")
    print(f"HARK Cratio[:8]: {hark_cratio[:8]}")
    n_act = num_exp + 12
    rel = (jax_cratio[:n_act] - hark_cratio[:n_act]) / hark_cratio[:n_act]
    print(f"Mean ratio JAX-replay/HARK (first {n_act}): {np.mean(jax_cratio[:n_act])/np.mean(hark_cratio[:n_act]):.6f}")
    print(f"Max |rel diff|: {np.max(np.abs(rel)):.6f}, mean diff: {np.mean(rel):+.6f}")


if __name__ == '__main__':
    main()
