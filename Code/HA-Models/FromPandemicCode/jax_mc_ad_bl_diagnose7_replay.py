"""
Test 5: RNG-aligned replay — pass HARK's actual shock_history to JAX, eliminating
RNG variance as source of error.

Expected outcome:
- If kernel logic is correct: JAX-replay matches HARK to FP precision (<0.01%)
- If still has bias: there's a remaining kernel bug

This directly answers user's question: "if there WERE a way to align RNG, would
that eliminate one source of error?"
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
    print(f"=== Test 5: HARK shock replay (RNG alignment) ===", flush=True)
    print(f"JAX x64: {jax.config.jax_enable_x64}", flush=True)
    ref_v3 = pickle.load(open('welfare6_BL_ad_ref_v3/recession_AD.pkl', 'rb'))
    hark_cratio = ref_v3['iter_logs'][-1]['Cratio_hist']
    hark_aggcons = ref_v3['iter_logs'][-1]['AggCons']
    base_AggCons = np.asarray(ref_v3['base_AggCons'])

    t0 = time.time()
    ctx = build_and_solve('Baseline')
    AggEco = ctx['AggEco']
    _ = run_base(ctx)
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')
    print(f"build/solve/base: {time.time()-t0:.1f}s", flush=True)

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

    print("Solving eco...", flush=True)
    t0 = time.time()
    eco.solve()
    print(f"solve: {time.time()-t0:.1f}s", flush=True)

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

    per_cohort = ref_v3['iter_logs'][-1]['per_cohort']
    cohort_weights = ref_v3['cohort_pop_factors']
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

        # HARK shock arrays (the RNG alignment)
        mrkv_path = np.asarray(h_p['shock_Mrkv']).astype(np.int32)         # (T, N)
        tran_path = np.asarray(h_p['shock_TranShk']).astype(np.float64)    # (T, N)
        perm_path = np.asarray(h_p['shock_PermShk']).astype(np.float64)    # (T, N)
        who_dies_path = np.asarray(h_p['shock_who_dies']).astype(bool)      # (T, N)

        _, cons, _ = simulate_jax_replay(
            aNrm0, pLvl0,
            ADF_path,
            cfunc_table, jnp.asarray(m_grid),
            mrkv_path, tran_path, perm_path, who_dies_path,
            Rfree_macro=jnp.asarray(inp['Rfree_macro'], dtype=jnp.float64),
            PermGroFac_macro=jnp.asarray(inp['PermGroFac_macro'], dtype=jnp.float64),
            Splurge=inp['Splurge'],
            newborn_aNrm=jnp.asarray(nbA), newborn_pLvl=jnp.asarray(nbP),
            act_T=act_T, J=J)
        ac = np.asarray(cons)
        per_cohort_aggcons.append(ac)
        print(f"  cohort {c_idx:2d} N={agent.AgentCount:4d} JAX-replay AggCons[0]={ac[0]:.2f} wall={time.time()-t_c:.1f}s",
              flush=True)

    jax_total = np.sum([ac * cohort_weights[i] for i, ac in enumerate(per_cohort_aggcons)], axis=0)
    jax_cratio = jax_total / base_AggCons
    print(f"\n=== Replay Summary ===")
    print(f"JAX-replay AggCons[0]={jax_total[0]:.4f}, HARK={hark_aggcons[0]:.4f}, "
          f"ratio={jax_total[0]/hark_aggcons[0]:.6f}")
    print(f"JAX-replay Cratio[:5]: {jax_cratio[:5]}")
    print(f"HARK Cratio[:5]: {hark_cratio[:5]}")
    n_act = num_exp + 12
    print(f"Mean ratio JAX-replay/HARK (first {n_act}): "
          f"{np.mean(jax_cratio[:n_act])/np.mean(hark_cratio[:n_act]):.6f}")
    rel = (jax_cratio[:n_act] - hark_cratio[:n_act]) / hark_cratio[:n_act]
    print(f"Max |rel diff|: {np.max(np.abs(rel)):.6f}, mean diff: {np.mean(rel):+.6f}")

    print(f"\nPer-period rel diff (first 16):")
    for t in range(16):
        print(f"  t={t:2d}: JAX={jax_cratio[t]:.6f} HARK={hark_cratio[t]:.6f} rel={rel[t]:+.6%}")


if __name__ == '__main__':
    main()
