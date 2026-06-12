"""
Step 8.4 Phase B: Python AD outer loop calling JAX MC.

Mirrors AggregateDemandEconomy.solve_ad_recession but replaces the
HARK CPU MC sim with JAX MC. Agent.solve() still runs in HARK.

Algorithm per iter:
  1. (Re)build CFunc from per-state intercept/slope; call agent.solve().
  2. Build Cratio_obs_path from current MacroCFunc beliefs (iterating along
     EconomyMrkv_init macro schedule).
  3. Build cfunc_table_per_period (T, n_combined, M) from agent.solution.
  4. Run JAX MC kernel → realized AggCons_t.
  5. Compute Cratio_hist = AggCons / base_AggCons.
  6. Build new MacroCFunc from Cratio_hist (matches lines 2343-2347).
  7. Map MacroCFunc → MicroCFunc; step toward it; install.
  8. Check Total_Diff convergence.
"""
from __future__ import annotations
import os, time
import numpy as np
import jax.numpy as jnp
from jax_mc_ad import (simulate_jax_ad, extract_cfunc_table_per_period,
                        compute_AggDemandFac_path)
from jax_mc_hark_integration import extract_recession_kernel_inputs, draw_newborn_pool_from_agent


def solve_ad_recession_jax(eco, base_AggCons,
                            num_max_iterations, convergence_cutoff,
                            shock_type='recession',
                            init_aNrm=None, init_pLvl=None, init_micro=None,
                            seeds=(0, 1, 2, 3),
                            verbose=True):
    """JAX-backed analog of AggregateDemandEconomy.solve_ad_recession.

    Mutates eco in place: installs converged CFunc and re-solves agents.

    Returns: dict with 'Cratio_hist', 'iter_history', 'wall_time'.
    """
    from AggFiscalModel import CRule

    eco.switch_shock_type(shock_type)
    n_combined = len(eco.CFunc)
    J = eco.num_base_MrkvStates
    n_macro = n_combined // J
    num_exp = eco.num_experiment_periods
    ADelasticity = eco.demand_ADelasticity
    eco.ADelasticity = ADelasticity

    # Reset CFunc to identity (matches solve_ad_recession line 2306-2307)
    eco.CFunc = [[CRule(1.0, 0.0) for _ in range(n_combined)] for _ in range(n_combined)]
    for agent in eco.agents:
        agent.CFunc = eco.CFunc

    # Build EconomyMrkv schedule (same as solve_ad_recession)
    act_T = eco.agents[0].T_sim
    EconomyMrkv_init = list(np.arange(1, num_exp + 1) * 2 + 1) + [1] * 12 + [0] * 20
    EconomyMrkv_path = (EconomyMrkv_init + [0] * act_T)[:act_T]
    macros = np.array([m for m in EconomyMrkv_path], dtype=int)  # combined macro index

    MacroCFunc = [[CRule(1.0, 0.0) for _ in range(n_macro)] for _ in range(n_macro)]

    base_AggCons = np.asarray(base_AggCons)
    iter_history = []
    wall_start = time.time()
    converged = False

    for it in range(num_max_iterations):
        iter_start = time.time()
        if verbose:
            print(f"  [jax-ad iter {it+1}/{num_max_iterations}] solving agent...",
                  flush=True)
        eco.solve()
        agent = eco.agents[0]
        inp = extract_recession_kernel_inputs(agent, scenario=shock_type)
        m_grid = np.asarray(inp['m_grid'])

        # Build Cratio_obs path from CURRENT MacroCFunc beliefs
        Cratio_obs = np.zeros(act_T)
        # Initial: at t=0 agents observe CFunc[0][macros[0]].intercept (per HARK
        # sow_init), which under MacroCFunc indexing == MacroCFunc[0][macros[0]]
        Cratio_obs[0] = MacroCFunc[0][macros[0]].intercept
        for t in range(1, act_T):
            i, j = macros[t - 1], macros[t]
            rule = MacroCFunc[i][j]
            Cratio_obs[t] = rule.intercept + rule.slope * (Cratio_obs[t - 1] - 1.0)
        ADF_path = compute_AggDemandFac_path(Cratio_obs, EconomyMrkv_path, 1, ADelasticity)

        cfunc_table = extract_cfunc_table_per_period(agent, Cratio_obs, m_grid,
                                                     n_combined=n_combined)
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

        cons_runs = []
        for s in seeds:
            _, cons, _ = simulate_jax_ad(
                init_aNrm, init_pLvl, init_micro,
                EconomyMrkv_path, ADF_path, cfunc_table,
                jnp.asarray(m_grid), **common, seed_base=s)
            cons_runs.append(np.asarray(cons))
        AggCons_realized = np.mean(cons_runs, axis=0)
        Cratio_hist = AggCons_realized / base_AggCons

        # Build new MacroCFunc from realized Cratio (matches solve_ad_recession 2343-2347)
        new_MacroCFunc = [[CRule(1.0, 0.0) for _ in range(n_macro)] for _ in range(n_macro)]
        new_MacroCFunc[0][3] = CRule(float(Cratio_hist[0]), 0.0)
        for j in range(num_exp - 1):
            new_MacroCFunc[2 * j + 3][2 * j + 5] = CRule(float(Cratio_hist[j + 1]), 0.0)
        new_MacroCFunc[2 * num_exp + 1][1] = CRule(float(Cratio_hist[num_exp]), 0.0)
        recovery_window = Cratio_hist[num_exp + 1:num_exp + 10]
        new_MacroCFunc[1][1] = CRule(float(np.mean(recovery_window)), 0.0)

        # Step CFunc toward new
        Old_CFunc = eco.CFunc
        New_CFunc = eco.Macro_2_Micro_CFunc(new_MacroCFunc)
        step = eco.Cfunc_iter_stepsize
        Step_CFunc = [[CRule(1.0, 0.0) for _ in range(n_combined)] for _ in range(n_combined)]
        for ii in range(n_combined):
            for jj in range(n_combined):
                Step_CFunc[ii][jj].slope = (
                    Old_CFunc[ii][jj].slope
                    + step * (New_CFunc[ii][jj].slope - Old_CFunc[ii][jj].slope))
                Step_CFunc[ii][jj].intercept = (
                    Old_CFunc[ii][jj].intercept
                    + step * (New_CFunc[ii][jj].intercept - Old_CFunc[ii][jj].intercept))
        eco.CFunc = Step_CFunc
        for agent in eco.agents:
            agent.CFunc = eco.CFunc
        MacroCFunc = new_MacroCFunc

        Total_Diff = eco.Compare_CFunc_Convergence(Old_CFunc, eco.CFunc)
        iter_history.append({
            'iter': it + 1,
            'Cratio_hist': Cratio_hist.copy(),
            'Total_Diff': Total_Diff,
            'wall': time.time() - iter_start,
        })
        if verbose:
            print(f"  [jax-ad iter {it+1}] Total_Diff={Total_Diff:.4g}, "
                  f"Cratio[0]={Cratio_hist[0]:.4f}, wall={iter_history[-1]['wall']:.1f}s",
                  flush=True)
        if Total_Diff < convergence_cutoff:
            converged = True
            break

    wall = time.time() - wall_start
    if verbose:
        print(f"[jax-ad] {len(iter_history)} iters, "
              f"converged={converged}, wall={wall:.1f}s")
    return {
        'iter_history': iter_history,
        'final_Cratio_hist': iter_history[-1]['Cratio_hist'],
        'converged': converged,
        'wall_time': wall,
    }
