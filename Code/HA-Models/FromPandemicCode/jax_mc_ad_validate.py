"""
Step 8.4 validation: JAX AD kernel vs HARK AD-converged simulation.

Strategy:
  1. Load HARK reference (welfare6_HS_ad_ref/recession_AD.pkl).
  2. Reproduce HARK setup, replace CFunc with converged values, re-solve agent.
  3. Build Cratio_obs path = MacroCFunc.intercept[macro_{t-1}, macro_t] along
     the EconomyMrkv_init path (intercept is what AGENTS observe).
  4. Compute AggDemandFac_path = Cratio_obs ** (RecState * ADelasticity).
  5. Extract per-period (T, n_combined, M) cFunc table using converged agent.
  6. Run JAX kernel; compare AggCons trajectory + Cratio_hist to HARK ref.
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
import jax.numpy as jnp
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base
from jax_mc_hark_integration import extract_recession_kernel_inputs, draw_newborn_pool_from_agent
from jax_mc_ad import (simulate_jax_ad, extract_cfunc_table_per_period,
                        compute_AggDemandFac_path)


def main():
    print("=== Step 8.4 — JAX AD kernel validation ===\n", flush=True)
    ref = pickle.load(open('welfare6_HS_ad_ref/recession_AD.pkl', 'rb'))
    hark_cratio = ref['iter_logs'][-1]['Cratio_hist']
    hark_aggcons = ref['iter_logs'][-1]['AggCons']
    base_AggCons = ref['base_AggCons']
    ADelasticity = ref['ADelasticity']
    num_base = ref['num_base_MrkvStates']
    num_exp = ref['num_experiment_periods']
    macro_inter = ref['final_MacroCFunc_intercept']
    macro_slope = ref['final_MacroCFunc_slope']
    print(f"HARK ref: {ref['num_iters']} AD iters; ADelasticity={ADelasticity}")
    print(f"HARK Cratio_hist[:12]: {hark_cratio[:12]}")

    # Reproduce HARK setup
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    _ = run_base(ctx)  # populates base_AggCons
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')

    # Install HARK's converged CFunc into the eco, then solve agent
    n_combined = ref['final_CFunc_intercept'].shape[0]
    from AggFiscalModel import CRule
    eco.CFunc = [[CRule(float(ref['final_CFunc_intercept'][i, j]),
                        float(ref['final_CFunc_slope'][i, j]))
                  for j in range(n_combined)] for i in range(n_combined)]
    for agent in eco.agents:
        agent.CFunc = eco.CFunc
    eco.ADelasticity = ADelasticity
    eco.solve()
    agent = eco.agents[0]

    # Extract recession kernel inputs
    inp = extract_recession_kernel_inputs(agent, scenario='recession')
    n_macro = inp['MrkvArray_macro'].shape[0]
    J = inp['MrkvArray_macro'].shape[1]
    m_grid = np.asarray(inp['m_grid'])
    M = len(m_grid)

    # Initial panel from HARK's actual AD-recession run (last iter)
    last_iter = ref['iter_logs'][-1]
    h_aNrm0 = np.asarray(last_iter['aNrm_t0']).astype(np.float32)
    h_pLvl0 = np.asarray(last_iter['pLvl_t0']).astype(np.float32)
    h_micro0 = (np.asarray(last_iter['Mrkv_t0']) % J).astype(np.int32)
    N = len(h_aNrm0)
    print(f"Init from HARK AD-recession run (last iter): N={N}, "
          f"<aNrm>={h_aNrm0.mean():.3f}, <pLvl>={h_pLvl0.mean():.3f}")

    # EconomyMrkv path matching HARK's recession_dict
    act_T = len(hark_aggcons)
    EconomyMrkv_init = list(np.arange(1, num_exp + 1) * 2 + 1) + [1] * 12 + [0] * 20
    EconomyMrkv_path = (EconomyMrkv_init + [0] * act_T)[:act_T]
    macros = np.array([m for m in EconomyMrkv_path], dtype=int)  # combined macro index

    # Build Cratio_obs path: agents observe predicted Cratio.
    # At t=0: Cratio_obs = MacroCFunc[0][macros[0]].intercept (initial sow).
    # At t>0: Cratio_obs[t] = MacroCFunc[macros[t-1]][macros[t]].apply(Cratio_realized[t-1])
    # With slope=0 at convergence: Cratio_obs[t] = intercept[macros[t-1], macros[t]].
    Cratio_obs = np.zeros(act_T)
    Cratio_obs[0] = macro_inter[0, macros[0]]
    for t in range(1, act_T):
        i, j = macros[t - 1], macros[t]
        Cratio_obs[t] = macro_inter[i, j] + macro_slope[i, j] * (Cratio_obs[t - 1] - 1.0)
    print(f"Cratio_obs[:12]: {Cratio_obs[:12]}")

    ADF_path = compute_AggDemandFac_path(Cratio_obs, EconomyMrkv_path, 1, ADelasticity)
    print(f"ADF_path[:12]: {ADF_path[:12]}")

    # Build per-period cfunc table
    t0 = time.time()
    cfunc_table = extract_cfunc_table_per_period(agent, Cratio_obs, m_grid, n_combined=n_macro * J)
    print(f"cfunc_table build: {time.time() - t0:.1f}s; shape={cfunc_table.shape}")

    nbA, nbP, _ = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99)

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

    # Run JAX over multiple seeds
    seeds = list(range(4))
    cons_runs = []
    for s in seeds:
        inc, cons, _ = simulate_jax_ad(
            h_aNrm0, h_pLvl0, h_micro0,
            EconomyMrkv_path, ADF_path, cfunc_table,
            jnp.asarray(m_grid),
            **common, seed_base=s)
        cons_runs.append(np.asarray(cons))
    cons_mean = np.mean(cons_runs, axis=0)
    cratio_jax = cons_mean / np.asarray(base_AggCons)
    print(f"\nJAX Cratio[:12]: {cratio_jax[:12]}")
    print(f"HARK Cratio[:12]: {hark_cratio[:12]}")

    diff = cratio_jax - np.asarray(hark_cratio)
    rel = diff / np.asarray(hark_cratio)
    print(f"\nMax |rel diff| Cratio (first {num_exp+12} periods): {np.max(np.abs(rel[:num_exp+12])):.4f}")
    print(f"RMS rel diff Cratio (active periods): {np.sqrt(np.mean(rel[:num_exp+12]**2)):.4f}")
    print(f"Mean ratio JAX/HARK Cratio (active): {np.mean(cratio_jax[:num_exp+12]) / np.mean(hark_cratio[:num_exp+12]):.4f}")


if __name__ == '__main__':
    main()
