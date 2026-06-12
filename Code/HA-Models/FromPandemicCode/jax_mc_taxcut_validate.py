"""
Validate JAX TaxCut scenario against HARK, then compute taxcut_norec
welfare cell vs HARK reference.

TaxCut policy: employed agents' xi (TranShk) multiplied by TaxCutIncFactor
during 8 active periods where Mrkv ∈ [2J, 9·2J) — i.e. macro states 2..17.
For norec_path = [2,4,...,20,0...], 8 of the 10 experiment periods are active.
"""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
import jax.numpy as jnp
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import extract_recession_kernel_inputs, draw_newborn_pool_from_agent
from jax_mc_policy_scenarios import simulate_jax_policy
from run_welfare6_parallel import welfare6_mc


def main():
    print("=== JAX TaxCut scenario validation ===")
    hark_tc = pickle.load(open('welfare6_HS_taxcut_ref/TaxCut.pkl', 'rb'))
    hark_base = pickle.load(open('welfare6_HS_clean_nshuf_4seed/seed0/base.pkl', 'rb'))
    h_aNrm0 = np.asarray(hark_base['aNrm_all_bs'][0]).astype(np.float32)
    h_pLvl0 = np.asarray(hark_base['pLvl_all_bs'][0]).astype(np.float32)
    h_micro0 = (np.asarray(hark_base['Mrkv_hist_bs'][0]) % 6).astype(np.int32)
    N = len(h_aNrm0); act_T = 40; J = 6

    hark_w6 = welfare6_mc(hark_tc, hark_base, hark_base, act_T, 1.01, 2.0)
    print(f"HARK taxcut_norec welfare cell: {hark_w6:.6f}")

    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    AggEco.switch_shock_type('TaxCut'); AggEco.solve()
    agent = AggEco.agents[0]
    inp = extract_recession_kernel_inputs(agent, scenario='TaxCut')

    TaxCutIncFactor = float(agent.TaxCutIncFactor)
    num_exp = 10
    norec_path = (list(np.arange(1, num_exp + 1) * 2) + [0] * 20 + [0] * act_T)[:act_T]
    tax_cut_path = np.array([
        TaxCutIncFactor if (2 * J <= norec_path[t] < 9 * 2 * J) else 1.0
        for t in range(act_T)
    ], dtype=np.float32)

    extra_dollars_zero = np.zeros((act_T, N), dtype=np.float32)
    tax_cut_ones = np.ones(act_T, dtype=np.float32)
    nbA, nbP, _ = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99)

    common = dict(
        cfunc_table_macro=jnp.asarray(inp['cfunc_table_macro']),
        m_grid=jnp.asarray(inp['m_grid']),
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

    ws = []
    for s in range(8):
        inc_b, cons_b, panel_b = simulate_jax_policy(
            h_aNrm0, h_pLvl0, h_micro0, norec_path,
            extra_dollars_zero, tax_cut_ones, **common, seed_base=s)
        inc_t, cons_t, panel_t = simulate_jax_policy(
            h_aNrm0, h_pLvl0, h_micro0, norec_path,
            extra_dollars_zero, tax_cut_path, **common, seed_base=s)
        pol = {'AggIncome': np.asarray(inc_t), 'AggCons': np.asarray(cons_t),
               'cLvl_all_splurge': np.asarray(panel_t)}
        none = {'AggIncome': np.asarray(inc_b), 'AggCons': np.asarray(cons_b),
                'cLvl_all_splurge': np.asarray(panel_b)}
        ws.append(welfare6_mc(pol, none, none, act_T, 1.01, 2.0))

    print(f"JAX 8-seed welfare cells: {[round(w, 4) for w in ws]}")
    print(f"JAX mean: {np.mean(ws):.6f}")
    print(f"HARK ref: {hark_w6:.6f}")
    print(f"Ratio: {np.mean(ws) / hark_w6:.4f}")


if __name__ == '__main__':
    main()
