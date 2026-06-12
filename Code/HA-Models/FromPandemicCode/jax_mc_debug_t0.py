"""Debug the t=0 AggCons mismatch between JAX kernel and HARK MC."""
from __future__ import annotations
import os, sys, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import jax.numpy as jnp
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import extract_hark_kernel_inputs
from jax_mc_minimal import simulate_jax, simulate_np


def main():
    print("=== Debug t=0 AggCons mismatch ===")
    pkl_path = 'welfare6_stratified_bench_HS_Only/seed0/base.pkl'
    hark = pickle.load(open(pkl_path, 'rb'))
    hark_cLvl0 = np.asarray(hark['cLvl_all_splurge'][0])
    hark_pLvl0 = np.asarray(hark['pLvl_all_bs'][0])
    hark_mrkv0 = np.asarray(hark['Mrkv_hist_bs'][0]) % 6
    N = len(hark_pLvl0)

    print(f"\nHARK at t=0 (post-init, possibly post-warmup):")
    print(f"  pLvl: mean={hark_pLvl0.mean():.3f}, std={hark_pLvl0.std():.3f}, "
          f"min={hark_pLvl0.min():.3f}, max={hark_pLvl0.max():.3f}")
    print(f"  cLvl_splurge[0]: mean={hark_cLvl0.mean():.3f}, std={hark_cLvl0.std():.3f}, "
          f"min={hark_cLvl0.min():.3f}, max={hark_cLvl0.max():.3f}")
    print(f"  Mrkv state dist: {np.bincount(hark_mrkv0, minlength=6)}")

    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    AggEco.switch_shock_type('base')
    AggEco.solve()
    agent = AggEco.agents[0]
    inp = extract_hark_kernel_inputs(agent, scenario='base')

    agent.initialize_sim()
    aNrm_agent_init = np.asarray(agent.state_now['aNrm'][:N], dtype=np.float32)
    print(f"\nAgent.state_now['aNrm'] right after initialize_sim():")
    print(f"  aNrm: mean={aNrm_agent_init.mean():.3f}, std={aNrm_agent_init.std():.3f}, "
          f"min={aNrm_agent_init.min():.3f}, max={aNrm_agent_init.max():.3f}")
    pLvl_agent_init = np.asarray(agent.state_now['pLvl'][:N], dtype=np.float32)
    print(f"  pLvl: mean={pLvl_agent_init.mean():.3f}, std={pLvl_agent_init.std():.3f}")

    # Run HARK's first sim period to see what cFunc gives
    # The expected per-agent cLvl_splurge given (a,p,j) is roughly:
    #   m = R*a/(G*ψ) + ξ
    #   c = (1-S)·cFunc(m)·p·G·ψ + S·p·G·ψ·ξ
    # At ξ=1, ψ=1 (no shock), c = (1-S)·cFunc(R*a) + S
    # For comparison, no-shock cons would be:
    R = float(agent.Rfree[0])
    G = float(agent.PermGroFac[0][0])
    S = float(agent.Splurge)
    j = 0  # employed
    a_test = aNrm_agent_init.mean()
    m_test = R * a_test / G + 1.0  # ψ=ξ=1
    cFunc_test = float(inp['cfunc_table'][j, np.argmin(np.abs(inp['m_grid'] - m_test))])
    cons_estim = (1 - S) * cFunc_test * pLvl_agent_init.mean() * G + \
                  S * pLvl_agent_init.mean() * G * 1.0
    print(f"\nFirst-period estimate (no shock, j=0, mean state):")
    print(f"  a_mean={a_test:.3f}, m={m_test:.3f}, cFunc(m)={cFunc_test:.3f}")
    print(f"  per-agent cons estim: {cons_estim:.3f}, aggregate: {cons_estim*N:.3f}")
    print(f"  HARK cons[0]: {hark_cLvl0.mean():.3f}/agent, {hark_cLvl0.mean()*N:.3f} total")

    print(f"\n=== Try: feed HARK's cLvl[0] back-implied state to JAX ===")
    # HARK's cLvl[0] / pLvl[0] = c_normalized
    # If c = (1-S)*cFunc(m) + S*ξ (with shock ξ), and ξ_mean ≈ 1.0:
    #   c ≈ (1-S)*cFunc(m) + S
    # solve back for cFunc(m), then for m, then for a = (m - 1)*G/R
    cNrm_implied = hark_cLvl0 / hark_pLvl0
    # Subtract splurge contribution (assuming ξ~1): cFunc(m) ≈ (c - S)/(1-S)
    cFunc_implied = (cNrm_implied - S) / (1 - S)
    print(f"  cNrm_implied (HARK c/p): mean={cNrm_implied.mean():.3f}, std={cNrm_implied.std():.3f}")
    print(f"  cFunc_implied:           mean={cFunc_implied.mean():.3f}, std={cFunc_implied.std():.3f}")

    # JAX run with HARK init
    nb_N = 200
    aNrm0 = aNrm_agent_init.copy()
    pLvl0 = hark_pLvl0.astype(np.float32)
    mrkv0 = hark_mrkv0.astype(np.int32)
    newborn_aNrm = aNrm0[:nb_N].copy()
    newborn_pLvl = pLvl0[:nb_N].copy()
    newborn_mrkv = np.zeros(nb_N, dtype=np.int32)

    jax_args = (
        aNrm0, pLvl0, mrkv0,
        jnp.asarray(inp['cfunc_table']), jnp.asarray(inp['m_grid']),
        jnp.asarray(inp['Rfree']), jnp.asarray(inp['PermGroFac']),
        jnp.asarray(inp['MrkvArray']),
        jnp.asarray(inp['IncShk_psi']), jnp.asarray(inp['IncShk_xi']),
        jnp.asarray(inp['IncShk_pmv']),
        1.0, 1.0, inp['Splurge'], inp['LivPrb'],
        jnp.asarray(newborn_aNrm), jnp.asarray(newborn_pLvl),
        jnp.asarray(newborn_mrkv),
    )
    _ = simulate_jax(*jax_args, 1, seed_base=0)
    jax_inc, jax_cons, jax_panel = simulate_jax(*jax_args, 1, seed_base=0)
    jax_panel_np = np.asarray(jax_panel)
    print(f"\nJAX first-period cLvl[0,:] panel: mean={jax_panel_np[0].mean():.3f}, std={jax_panel_np[0].std():.3f}")
    print(f"HARK cLvl[0,:] panel: mean={hark_cLvl0.mean():.3f}, std={hark_cLvl0.std():.3f}")
    print(f"Per-agent ratio JAX/HARK: mean = {(jax_panel_np[0]/hark_cLvl0).mean():.3f}")


if __name__ == '__main__':
    main()
