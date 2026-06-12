"""
Validate JAX Check (stimulus check) scenario against HARK, then
compute check_norec welfare cell vs HARK reference.
"""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
import jax.numpy as jnp
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import extract_recession_kernel_inputs, draw_newborn_pool_from_agent
from jax_mc_policy_scenarios import simulate_jax_policy, compute_check_amount_per_agent
from run_welfare6_parallel import welfare6_mc


def main():
    print("=== JAX Check scenario validation ===")
    hark_chk = pickle.load(open('welfare6_HS_check_ref/Check.pkl','rb'))
    hark_base = pickle.load(open('welfare6_HS_clean_nshuf_4seed/seed0/base.pkl','rb'))
    h_aNrm0 = np.asarray(hark_base['aNrm_all_bs'][0]).astype(np.float32)
    h_pLvl0 = np.asarray(hark_base['pLvl_all_bs'][0]).astype(np.float32)
    h_mrkv0 = np.asarray(hark_base['Mrkv_hist_bs'][0])
    J = 6
    h_micro0 = (h_mrkv0 % J).astype(np.int32)
    N = len(h_aNrm0); act_T = 40

    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    # Use Check scenario solved agent (different IncShkDstn)
    AggEco.switch_shock_type('Check')
    AggEco.solve()
    agent = AggEco.agents[0]
    inp = extract_recession_kernel_inputs(agent, scenario='Check')

    CheckStimLvl = float(agent.CheckStimLvl)
    cutoff_start = float(agent.CheckStimLvl_PLvl_Cutoff_start)
    cutoff_end = float(agent.CheckStimLvl_PLvl_Cutoff_end)
    print(f"CheckStimLvl={CheckStimLvl}, cutoffs=[{cutoff_start},{cutoff_end}]")

    # Build per-agent Check amount: applied at t=0 for employed only
    check_per_agent_dollars = compute_check_amount_per_agent(
        h_pLvl0, CheckStimLvl, cutoff_start, cutoff_end)
    print(f"Check per agent: mean={check_per_agent_dollars.mean():.4f}, "
          f"fraction nonzero={(check_per_agent_dollars > 0).mean():.3f}")

    # extra_dollars_path: (T, N) - check at t=0 only
    extra_dollars_path = np.zeros((act_T, N), dtype=np.float32)
    extra_dollars_path[0, :] = check_per_agent_dollars
    tax_cut_path = np.ones(act_T, dtype=np.float32)

    # EconomyMrkv_path for Check: norec_path = [2, 4, ..., 20, 0, ...]
    num_exp = 10
    norec_path = list(np.arange(1, num_exp + 1) * 2) + [0] * 20
    norec_path = (norec_path + [0] * act_T)[:act_T]

    nbA, nbP, nbM = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99)

    print(f"\nRunning JAX Check scenario...")
    _ = simulate_jax_policy(
        h_aNrm0, h_pLvl0, h_micro0,
        norec_path, extra_dollars_path, tax_cut_path,
        jnp.asarray(inp['cfunc_table_macro']), jnp.asarray(inp['m_grid']),
        jnp.asarray(inp['Rfree_macro']), jnp.asarray(inp['PermGroFac_macro']),
        jnp.asarray(inp['MrkvArray_macro']),
        jnp.asarray(inp['IncShk_psi_macro']), jnp.asarray(inp['IncShk_xi_macro']),
        jnp.asarray(inp['IncShk_pmv_macro']),
        inp['Splurge'], inp['LivPrb'], jnp.asarray(nbA), jnp.asarray(nbP),
        act_T=act_T, seed_base=0)

    j_inc_means = []; j_cons_means = []
    j_panels = []
    for s in range(4):
        inc, cons, panel = simulate_jax_policy(
            h_aNrm0, h_pLvl0, h_micro0,
            norec_path, extra_dollars_path, tax_cut_path,
            jnp.asarray(inp['cfunc_table_macro']), jnp.asarray(inp['m_grid']),
            jnp.asarray(inp['Rfree_macro']), jnp.asarray(inp['PermGroFac_macro']),
            jnp.asarray(inp['MrkvArray_macro']),
            jnp.asarray(inp['IncShk_psi_macro']), jnp.asarray(inp['IncShk_xi_macro']),
            jnp.asarray(inp['IncShk_pmv_macro']),
            inp['Splurge'], inp['LivPrb'], jnp.asarray(nbA), jnp.asarray(nbP),
            act_T=act_T, seed_base=s)
        j_inc_means.append(float(inc.mean()))
        j_cons_means.append(float(cons.mean()))
        j_panels.append(np.asarray(panel))
    print(f"JAX Check 4-seed AggInc mean: {np.mean(j_inc_means):.3f}")
    print(f"JAX Check 4-seed AggCons mean: {np.mean(j_cons_means):.3f}")

    h_inc = np.asarray(hark_chk['AggIncome'])
    h_cons = np.asarray(hark_chk['AggCons'])
    print(f"\nHARK Check AggInc mean: {h_inc.mean():.3f}")
    print(f"HARK Check AggCons mean: {h_cons.mean():.3f}")
    print(f"Ratio: AggInc={np.mean(j_inc_means)/h_inc.mean():.4f}, "
          f"AggCons={np.mean(j_cons_means)/h_cons.mean():.4f}")


if __name__ == '__main__':
    main()
