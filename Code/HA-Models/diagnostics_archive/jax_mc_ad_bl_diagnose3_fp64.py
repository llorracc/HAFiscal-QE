"""
Test 1: FP64 hypothesis for residual ~1% Baseline bias.

Hypothesis: JAX kernel FP32 has cumulative drift in pLvl/aNrm updates over
30+ periods, accumulating to ~1% by t=32.

Strategy: enable JAX x64 mode + cast all init arrays + extracted inputs to
float64, rerun diag2-equivalent at Baseline, compare residual to FP32.

If FP64 closes bias to <0.3%: FP precision was the source.
If unchanged: rule out FP, move to next test.
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

# IMPORTANT: enable JAX x64 BEFORE importing jax
os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)
print(f"JAX x64 enabled: {jax.config.jax_enable_x64}")

import numpy as np
import jax.numpy as jnp
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base
from jax_mc_hark_integration import extract_recession_kernel_inputs, draw_newborn_pool_from_agent
from jax_mc_ad import simulate_jax_ad, extract_cfunc_table_per_period, compute_AggDemandFac_path


def main():
    print("=== Test 1: FP64 hypothesis ===\n", flush=True)
    ref = pickle.load(open('welfare6_BL_ad_ref/recession_AD.pkl', 'rb'))
    hark_cratio = ref['iter_logs'][-1]['Cratio_hist']
    hark_aggcons = ref['iter_logs'][-1]['AggCons']
    base_AggCons = np.asarray(ref['base_AggCons'])

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
        MacroCFunc[2 * j + 3][2 * j + 5] = CRule(float(hark_cratio[j + 1]), 0.0)
    MacroCFunc[2 * num_exp + 1][1] = CRule(float(hark_cratio[num_exp]), 0.0)
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
    ADF_path = compute_AggDemandFac_path(Cratio_obs, EconomyMrkv_path, 1, eco.demand_ADelasticity)
    # Use float64 for ADF_path too
    ADF_path = ADF_path.astype(np.float64)

    per_cohort_init = ref['iter_logs'][-1]['per_cohort_t0']
    cohort_weights = ref['cohort_pop_factors']
    per_cohort_aggcons = []

    for c_idx, agent in enumerate(eco.agents):
        t_c = time.time()
        inp = extract_recession_kernel_inputs(agent, scenario='recession')
        m_grid = np.asarray(inp['m_grid']).astype(np.float64)  # FP64
        cfunc_table = extract_cfunc_table_per_period(agent, Cratio_obs, m_grid,
                                                       n_combined=n_combined).astype(np.float64)
        nbA, nbP, _ = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99+c_idx)
        nbA = nbA.astype(np.float64)
        nbP = nbP.astype(np.float64)
        h_p = per_cohort_init[c_idx]
        # FP64 init
        aNrm0 = np.asarray(h_p['aNrm_t0']).astype(np.float64)
        pLvl0 = np.asarray(h_p['pLvl_t0']).astype(np.float64)
        micro0 = (np.asarray(h_p['Mrkv_t0']) % J).astype(np.int32)

        common = dict(
            Rfree_macro=jnp.asarray(inp['Rfree_macro'], dtype=jnp.float64),
            PermGroFac_macro=jnp.asarray(inp['PermGroFac_macro'], dtype=jnp.float64),
            MrkvArray_macro=jnp.asarray(inp['MrkvArray_macro'], dtype=jnp.float64),
            IncShk_psi_macro=jnp.asarray(inp['IncShk_psi_macro'], dtype=jnp.float64),
            IncShk_xi_macro=jnp.asarray(inp['IncShk_xi_macro'], dtype=jnp.float64),
            IncShk_pmv_macro=jnp.asarray(inp['IncShk_pmv_macro'], dtype=jnp.float64),
            Splurge=inp['Splurge'], LivPrb=inp['LivPrb'],
            newborn_aNrm=jnp.asarray(nbA), newborn_pLvl=jnp.asarray(nbP),
            act_T=act_T,
        )
        cons_per_seed = []
        for s in range(4):
            _, cons, _ = simulate_jax_ad(
                aNrm0, pLvl0, micro0,
                EconomyMrkv_path, ADF_path, cfunc_table,
                jnp.asarray(m_grid), **common, seed_base=s*31+c_idx)
            cons_per_seed.append(np.asarray(cons))
        ac = np.mean(cons_per_seed, axis=0)
        per_cohort_aggcons.append(ac)
        print(f"  cohort {c_idx:2d} N={agent.AgentCount:4d} JAX-fp64 AggCons[0]={ac[0]:.2f} wall={time.time()-t_c:.1f}s",
              flush=True)

    jax_total = np.sum([ac * cohort_weights[i] for i, ac in enumerate(per_cohort_aggcons)], axis=0)
    jax_cratio = jax_total / base_AggCons
    print(f"\n=== FP64 Summary ===")
    print(f"JAX-fp64 AggCons[0]={jax_total[0]:.2f}, HARK AggCons[0]={hark_aggcons[0]:.2f}, "
          f"ratio={jax_total[0]/hark_aggcons[0]:.4f}")
    print(f"JAX-fp64 Cratio[:5]: {jax_cratio[:5]}")
    print(f"HARK Cratio[:5]: {hark_cratio[:5]}")
    n_act = num_exp + 12
    print(f"Mean ratio JAX-fp64/HARK Cratio (first {n_act}): "
          f"{np.mean(jax_cratio[:n_act])/np.mean(hark_cratio[:n_act]):.4f}")
    rel = (jax_cratio[:n_act] - hark_cratio[:n_act]) / hark_cratio[:n_act]
    print(f"Max |rel diff|: {np.max(np.abs(rel)):.4f}, mean diff: {np.mean(rel):+.4f}")


if __name__ == '__main__':
    main()
