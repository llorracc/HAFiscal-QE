"""
Validate jax_mc_recession against HARK recession scenario at dur=0
(bootstrap-source single-duration realization).
"""
from __future__ import annotations
import os, sys, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import jax.numpy as jnp
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import (
    extract_recession_kernel_inputs, draw_newborn_pool_from_agent,
)
from jax_mc_recession import simulate_jax_recession


def main():
    print("=== JAX recession kernel validation at HS_Only dur=0 ===")
    pkl = 'welfare6_HS_recession_ref/recession.pkl'
    hark = pickle.load(open(pkl, 'rb'))
    h_aNrm0 = np.asarray(hark['aNrm_all_bs'][0])
    h_pLvl0 = np.asarray(hark['pLvl_all_bs'][0])
    h_mrkv0 = np.asarray(hark['Mrkv_hist_bs'][0])  # combined Mrkv (macro*J + micro)
    # HARK Mrkv_hist_bs[0] is the t=0 combined Mrkv (e.g., macro=1 (recession spike) × J + micro)
    # We need to extract: micro = Mrkv % J, and starting macro = path[0]
    J = 6
    h_micro0 = h_mrkv0 % J
    h_macro0 = h_mrkv0 // J
    print(f"HARK t=0: micro distribution {np.bincount(h_micro0, minlength=J)}")
    print(f"HARK t=0: macro distribution {np.bincount(h_macro0, minlength=22)}")
    print(f"HARK dur=0 per_dur_cLvl_all_splurge shape: {hark['per_dur_cLvl_all_splurge'].shape}")
    # per_dur[0] is dur=0 realization
    h_per_dur = np.asarray(hark['per_dur_cLvl_all_splurge'])
    print(f"HARK per_dur[0] (dur=0) panel mean: {h_per_dur[0].mean(axis=1)[:5]} ... {h_per_dur[0].mean(axis=1)[-5:]}")

    # For dur=0: macro path = [3, 4, 6, 8, 10, 12, 14, 16, 18, 20, 0, ...]
    num_experiment_periods = 10
    rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 20
    rec_path[0:1] = [rec_path[0] + 1]   # dur=0 means recession lasts 1 period
    act_T = 40
    path = rec_path[:act_T]
    while len(path) < act_T:
        path.append(0)
    print(f"\\nMacro path (first 15): {path[:15]}")

    # Build model and extract per-macro inputs
    print("\\nBuilding model + extracting recession inputs...")
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    AggEco.switch_shock_type('recession')
    AggEco.solve()
    agent = AggEco.agents[0]
    inp = extract_recession_kernel_inputs(agent, scenario='recession')
    print(f"  cfunc_table_macro shape: {inp['cfunc_table_macro'].shape}")
    print(f"  MrkvArray_macro shape: {inp['MrkvArray_macro'].shape}")
    print(f"  IncShk_psi_macro shape: {inp['IncShk_psi_macro'].shape}")

    nbA, nbP, nbM = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99)
    AggDemandFac_path = np.ones(act_T, dtype=np.float32)

    aNrm0 = h_aNrm0.astype(np.float32)
    pLvl0 = h_pLvl0.astype(np.float32)
    mrkv_micro0 = h_micro0.astype(np.int32)

    print("\\nRunning JAX recession kernel...")
    import time
    _ = simulate_jax_recession(
        aNrm0, pLvl0, mrkv_micro0,
        path, AggDemandFac_path,
        jnp.asarray(inp['cfunc_table_macro']), jnp.asarray(inp['m_grid']),
        jnp.asarray(inp['Rfree_macro']), jnp.asarray(inp['PermGroFac_macro']),
        jnp.asarray(inp['MrkvArray_macro']),
        jnp.asarray(inp['IncShk_psi_macro']), jnp.asarray(inp['IncShk_xi_macro']),
        jnp.asarray(inp['IncShk_pmv_macro']),
        inp['Splurge'], inp['LivPrb'],
        jnp.asarray(nbA), jnp.asarray(nbP),
        act_T=act_T, seed_base=0, pLvl_unemp_mode='qe')

    means = []
    cons_means = []
    for s in range(8):
        inc, cons, _ = simulate_jax_recession(
            aNrm0, pLvl0, mrkv_micro0,
            path, AggDemandFac_path,
            jnp.asarray(inp['cfunc_table_macro']), jnp.asarray(inp['m_grid']),
            jnp.asarray(inp['Rfree_macro']), jnp.asarray(inp['PermGroFac_macro']),
            jnp.asarray(inp['MrkvArray_macro']),
            jnp.asarray(inp['IncShk_psi_macro']), jnp.asarray(inp['IncShk_xi_macro']),
            jnp.asarray(inp['IncShk_pmv_macro']),
            inp['Splurge'], inp['LivPrb'],
            jnp.asarray(nbA), jnp.asarray(nbP),
            act_T=act_T, seed_base=s, pLvl_unemp_mode='qe')
        means.append(float(inc.mean()))
        cons_means.append(float(cons.mean()))
    print(f"\\nJAX 8-seed recession (dur=0):")
    print(f"  AggInc mean: {np.mean(means):.3f}  std: {np.std(means, ddof=1):.3f}")
    print(f"  AggCons mean: {np.mean(cons_means):.3f}")

    # HARK dur=0 — compute its AggIncome from per_dur cLvl
    # Actually AggIncome stored is dur-prob-weighted. For dur=0 specific, compute from
    # per_dur_cLvl_all_splurge[0] / cLvl_all_splurge -> proxy.
    # The cleanest: just compare to bootstrap-source mean (which IS dur=0)
    h_cLvl0 = np.asarray(hark['cLvl_all_splurge_bs'])
    print(f"\\nHARK dur=0 (bootstrap-source) mean cLvl per period: {h_cLvl0.mean(axis=1).mean():.3f}")
    # Sum per period across agents = total cons per period; mean over T
    hark_cons_mean = h_cLvl0.sum(axis=1).mean()
    print(f"HARK AggCons(dur=0) mean: {hark_cons_mean:.3f}")
    print(f"Ratio JAX/HARK AggCons: {np.mean(cons_means)/hark_cons_mean:.4f}")


if __name__ == '__main__':
    main()
