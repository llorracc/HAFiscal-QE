"""
Test 3: pass HARK's actual t_age0 distribution to JAX.

Uses welfare6_BL_ad_ref_v2/recession_AD.pkl which has per-cohort t_age_t0
dumped from HARK history (track_vars includes 't_age').

If JAX bias closes when using HARK's t_age, the ergodic t_age sampling I do
internally was the source. If not, rule out.
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
import jax.numpy as jnp
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base
from jax_mc_hark_integration import extract_recession_kernel_inputs, draw_newborn_pool_from_agent
from jax_mc_ad import simulate_jax_ad, extract_cfunc_table_per_period, compute_AggDemandFac_path


def main():
    print("=== Test 3: HARK t_age0 init hypothesis ===\n", flush=True)
    ref_v2 = pickle.load(open('welfare6_BL_ad_ref_v2/recession_AD.pkl', 'rb'))
    hark_cratio = ref_v2['iter_logs'][-1]['Cratio_hist']
    hark_aggcons = ref_v2['iter_logs'][-1]['AggCons']
    base_AggCons = np.asarray(ref_v2['base_AggCons'])

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
    ADF_path = compute_AggDemandFac_path(Cratio_obs, EconomyMrkv_path, 1, eco.demand_ADelasticity)

    per_cohort_init = ref_v2['iter_logs'][-1]['per_cohort_t0']
    cohort_weights = ref_v2['cohort_pop_factors']
    per_cohort_aggcons = []

    has_tage = 't_age_t0' in per_cohort_init[0]
    print(f"\nt_age_t0 available in v2 ref: {has_tage}")
    if has_tage:
        for c_idx, c in enumerate(per_cohort_init[:3]):
            ta = c['t_age_t0']
            print(f"  cohort {c_idx} t_age0: mean={ta.mean():.2f} max={ta.max()}")

    for c_idx, agent in enumerate(eco.agents):
        t_c = time.time()
        inp = extract_recession_kernel_inputs(agent, scenario='recession')
        m_grid = np.asarray(inp['m_grid'])
        cfunc_table = extract_cfunc_table_per_period(agent, Cratio_obs, m_grid,
                                                       n_combined=n_combined)
        nbA, nbP, _ = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99+c_idx)
        h_p = per_cohort_init[c_idx]
        aNrm0 = np.asarray(h_p['aNrm_t0']).astype(np.float32)
        pLvl0 = np.asarray(h_p['pLvl_t0']).astype(np.float32)
        micro0 = (np.asarray(h_p['Mrkv_t0']) % J).astype(np.int32)
        # KEY: pass HARK's actual t_age0
        t_age0 = np.asarray(h_p['t_age_t0']).astype(np.int32) if has_tage else None

        # KEY: T_age_max from agent (200 at Baseline, 100 at HS_Only/RR).
        # JAX default of 100 kills agents 100 periods early at Baseline.
        T_age_max = int(getattr(agent, 'T_age', 100) or 100)
        common = dict(
            Rfree_macro=jnp.asarray(inp['Rfree_macro']),
            PermGroFac_macro=jnp.asarray(inp['PermGroFac_macro']),
            MrkvArray_macro=jnp.asarray(inp['MrkvArray_macro']),
            IncShk_psi_macro=jnp.asarray(inp['IncShk_psi_macro']),
            IncShk_xi_macro=jnp.asarray(inp['IncShk_xi_macro']),
            IncShk_pmv_macro=jnp.asarray(inp['IncShk_pmv_macro']),
            Splurge=inp['Splurge'], LivPrb=inp['LivPrb'],
            newborn_aNrm=jnp.asarray(nbA), newborn_pLvl=jnp.asarray(nbP),
            act_T=act_T, t_age0=t_age0, T_age_max=T_age_max,
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
        print(f"  cohort {c_idx:2d} N={agent.AgentCount:4d} JAX-tage AggCons[0]={ac[0]:.2f} wall={time.time()-t_c:.1f}s",
              flush=True)

    jax_total = np.sum([ac * cohort_weights[i] for i, ac in enumerate(per_cohort_aggcons)], axis=0)
    jax_cratio = jax_total / base_AggCons
    print(f"\n=== t_age Summary ===")
    print(f"JAX-tage AggCons[0]={jax_total[0]:.2f}, HARK={hark_aggcons[0]:.2f}, "
          f"ratio={jax_total[0]/hark_aggcons[0]:.4f}")
    print(f"JAX-tage Cratio[:5]: {jax_cratio[:5]}")
    print(f"HARK     Cratio[:5]: {hark_cratio[:5]}")
    n_act = num_exp + 12
    print(f"Mean ratio JAX-tage/HARK Cratio (first {n_act}): "
          f"{np.mean(jax_cratio[:n_act])/np.mean(hark_cratio[:n_act]):.4f}")
    rel = (jax_cratio[:n_act] - hark_cratio[:n_act]) / hark_cratio[:n_act]
    print(f"Max |rel diff|: {np.max(np.abs(rel)):.4f}, mean diff: {np.mean(rel):+.4f}")


if __name__ == '__main__':
    main()
