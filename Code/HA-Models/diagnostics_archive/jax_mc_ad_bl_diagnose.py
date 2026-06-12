"""
Diagnose JAX-vs-HARK Cratio bias at Baseline (ratio 0.987 vs ~1.009 at smaller scales).

Strategy:
  At iter 1 the CFunc is identity (intercept=1, slope=0). Predicted Cratio_obs=1.0
  always, so ADF=1.0 always — there is NO AD feedback at iter 1.

  Iter 1's Cratio_hist therefore reflects ONLY the MC sim of the no-AD recession.
  If JAX's iter-1 Cratio matches HARK's iter-1 Cratio (0.98916 at Baseline),
  the bias comes from later AD iterations. If they disagree, the bias is in the
  MC kernel at Baseline-scale heterogeneity.

  Per-cohort: log each cohort's AggCons trajectory separately to see whether
  the disagreement is concentrated in specific atoms (e.g. high-beta).
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
    print("=== BL JAX-vs-HARK iter-1 diagnostic ===\n", flush=True)
    ref = pickle.load(open('welfare6_BL_ad_ref/recession_AD.pkl', 'rb'))
    hark_iter1_cratio = ref['iter_logs'][0]['Cratio_hist']
    hark_iter1_aggcons = ref['iter_logs'][0]['AggCons']
    base_AggCons = np.asarray(ref['base_AggCons'])
    print(f"HARK iter-1 Cratio[:5]: {hark_iter1_cratio[:5]}")
    print(f"HARK iter-1 AggCons[:5]: {hark_iter1_aggcons[:5]}")
    print(f"Baseline base_AggCons[0]: {base_AggCons[0]:.2f}")

    # Build eco fresh, keep CFunc identity (no AD effect)
    print("\nBuilding Baseline economy...", flush=True)
    t0 = time.time()
    ctx = build_and_solve('Baseline')
    print(f"build_and_solve: {time.time() - t0:.1f}s", flush=True)
    AggEco = ctx['AggEco']
    print("Running base...", flush=True)
    t0 = time.time()
    _ = run_base(ctx)
    print(f"run_base: {time.time() - t0:.1f}s", flush=True)
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')

    # Reset CFunc to identity, solve agents
    from AggFiscalModel import CRule
    n_combined = len(eco.CFunc)
    J = eco.num_base_MrkvStates
    n_macro = n_combined // J
    num_exp = eco.num_experiment_periods
    eco.CFunc = [[CRule(1.0, 0.0) for _ in range(n_combined)] for _ in range(n_combined)]
    for agent in eco.agents:
        agent.CFunc = eco.CFunc
    eco.ADelasticity = eco.demand_ADelasticity
    print("\nSolving eco with identity CFunc...", flush=True)
    t0 = time.time()
    eco.solve()
    print(f"eco.solve: {time.time() - t0:.1f}s", flush=True)

    # EconomyMrkv path
    act_T = eco.agents[0].T_sim
    EconomyMrkv_init = list(np.arange(1, num_exp + 1) * 2 + 1) + [1] * 12 + [0] * 20
    EconomyMrkv_path = (EconomyMrkv_init + [0] * act_T)[:act_T]

    # Identity CFunc => Cratio_obs = 1.0 always, ADF = 1.0 always
    Cratio_obs = np.ones(act_T)
    ADF_path = np.ones(act_T, dtype=np.float32)

    # Per-cohort JAX run, log individual contributions
    per_cohort_aggcons = []
    for c_idx, agent in enumerate(eco.agents):
        t_c = time.time()
        inp = extract_recession_kernel_inputs(agent, scenario='recession')
        m_grid = np.asarray(inp['m_grid'])
        cfunc_table = extract_cfunc_table_per_period(agent, Cratio_obs, m_grid,
                                                       n_combined=n_combined)
        nbA, nbP, _ = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99 + c_idx)
        N = agent.AgentCount
        # Use newborn pool for init (matches initialize_sim semantics)
        rs = np.random.RandomState(42 + c_idx)
        idx = rs.choice(len(nbA), size=N, replace=True)
        aNrm0 = np.asarray(nbA[idx]).astype(np.float32)
        pLvl0 = np.asarray(nbP[idx]).astype(np.float32)
        micro0 = np.zeros(N, dtype=np.int32)

        common = dict(
            Rfree_macro=jnp.asarray(inp['Rfree_macro']),
            PermGroFac_macro=jnp.asarray(inp['PermGroFac_macro']),
            MrkvArray_macro=jnp.asarray(inp['MrkvArray_macro']),
            IncShk_psi_macro=jnp.asarray(inp['IncShk_psi_macro']),
            IncShk_xi_macro=jnp.asarray(inp['IncShk_xi_macro']),
            IncShk_pmv_macro=jnp.asarray(inp['IncShk_pmv_macro']),
            Splurge=inp['Splurge'], LivPrb=inp['LivPrb'],
            newborn_aNrm=jnp.asarray(nbA), newborn_pLvl=jnp.asarray(nbP),
            act_T=act_T,
        )
        cons_per_seed = []
        for s in range(4):
            _, cons, _ = simulate_jax_ad(
                aNrm0, pLvl0, micro0,
                EconomyMrkv_path, ADF_path, cfunc_table,
                jnp.asarray(m_grid), **common, seed_base=s * 31 + c_idx)
            cons_per_seed.append(np.asarray(cons))
        ac = np.mean(cons_per_seed, axis=0)
        per_cohort_aggcons.append(ac)
        wall = time.time() - t_c
        # Print per-cohort iter 1 Cratio for this cohort alone (cohort vs its own base)
        # We don't have per-cohort base; approximate via ratio of recession to t>=num_exp+10
        recovery_mean = np.mean(ac[num_exp + 5:num_exp + 12])
        print(f"  cohort {c_idx:2d} N={N:4d} beta={float(agent.DiscFac):.4f}: "
              f"AggCons[0]={ac[0]:.2f} recovery~{recovery_mean:.2f} "
              f"recession_drop={ac[0]/recovery_mean - 1:+.3%} wall={wall:.1f}s",
              flush=True)

    jax_total = np.sum(per_cohort_aggcons, axis=0)
    jax_cratio = jax_total / base_AggCons
    print(f"\nJAX  iter-1 Cratio[:5]: {jax_cratio[:5]}")
    print(f"HARK iter-1 Cratio[:5]: {hark_iter1_cratio[:5]}")
    print(f"Mean ratio JAX/HARK iter-1 (first {num_exp+12}): "
          f"{np.mean(jax_cratio[:num_exp+12]) / np.mean(hark_iter1_cratio[:num_exp+12]):.4f}")
    print(f"\nPer-period rel diff JAX-HARK iter-1 Cratio[:{num_exp+5}]:")
    for t in range(num_exp + 5):
        print(f"  t={t:2d}: JAX={jax_cratio[t]:.4f} HARK={hark_iter1_cratio[t]:.4f} "
              f"rel={jax_cratio[t]/hark_iter1_cratio[t]-1:+.4%}")


if __name__ == '__main__':
    main()
