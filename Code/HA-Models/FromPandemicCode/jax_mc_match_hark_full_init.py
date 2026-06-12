"""
Quickest Win Step 3+4: validate JAX kernel against HARK using HARK's
EXACT initial state (aNrm + pLvl + Mrkv from new aNrm_all_bs field).

Tests both pLvl_unemp_mode='qe' (HARK default convention) and 'shock'
(current JAX default before fix) to verify the fix actually closes the
level-offset gap.
"""
from __future__ import annotations
import os, sys, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import jax.numpy as jnp
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import (
    extract_hark_kernel_inputs, draw_newborn_pool_from_agent,
    _broadcast_employed_psi_to_all_states,
)
from jax_mc_minimal import simulate_jax


def main():
    pkl_path = os.environ.get(
        'HARK_PKL',
        'welfare6_stratified_bench_HS_Only_aNrm/base.pkl',
    )
    print(f"=== JAX MC vs HARK with EXACT init (aNrm + pLvl + Mrkv) ===")
    print(f"HARK pickle: {pkl_path}")
    if not os.path.exists(pkl_path):
        print(f"ERROR: pickle not found")
        return

    hark = pickle.load(open(pkl_path, 'rb'))
    print(f"Pickle keys: {list(hark.keys())}")
    if 'aNrm_all_bs' not in hark:
        print(f"ERROR: aNrm_all_bs not in pickle — old format")
        return

    hark_inc = np.asarray(hark['AggIncome'])
    hark_cons = np.asarray(hark['AggCons'])
    hark_aNrm0 = np.asarray(hark['aNrm_all_bs'][0])
    hark_pLvl0 = np.asarray(hark['pLvl_all_bs'][0])
    hark_mrkv0 = np.asarray(hark['Mrkv_hist_bs'][0]) % 6
    N = len(hark_aNrm0)
    act_T = len(hark_inc)
    print(f"\nHARK initial state at t=0 (EXACT from pickle):")
    print(f"  N={N}, act_T={act_T}")
    print(f"  aNrm stats: mean={hark_aNrm0.mean():.4f}  std={hark_aNrm0.std():.4f}  "
          f"min={hark_aNrm0.min():.4f}  max={hark_aNrm0.max():.4f}")
    print(f"  pLvl stats: mean={hark_pLvl0.mean():.4f}  std={hark_pLvl0.std():.4f}")
    print(f"  Mrkv dist: {np.bincount(hark_mrkv0, minlength=6)}")

    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    AggEco.switch_shock_type('base')
    AggEco.solve()
    agent = AggEco.agents[0]
    inp = extract_hark_kernel_inputs(agent, scenario='base')

    # BUG-040 perm_shocks_during_unemployment=True: broadcast employed psi
    # distribution to all Mrkv states (HAFiscal default).
    if getattr(agent, 'perm_shocks_during_unemployment', False):
        print("  perm_shocks_during_unemployment=True → broadcasting employed psi distribution to all states")
        new_psi, new_xi, new_pmv, new_natoms = _broadcast_employed_psi_to_all_states(
            inp['IncShk_psi'], inp['IncShk_xi'], inp['IncShk_pmv'], inp['IncShk_natoms'])
        inp['IncShk_psi'] = new_psi
        inp['IncShk_xi'] = new_xi
        inp['IncShk_pmv'] = new_pmv
        inp['IncShk_natoms'] = new_natoms

    aNrm0 = hark_aNrm0.astype(np.float32)
    pLvl0 = hark_pLvl0.astype(np.float32)
    mrkv0 = hark_mrkv0.astype(np.int32)
    # Draw newborn pool from HARK's actual kNrmInitDstn / pLvlInitDstn
    # (NOT from the post-warmup pLvl panel, which is what was biasing us)
    newborn_aNrm, newborn_pLvl, newborn_mrkv = draw_newborn_pool_from_agent(
        agent, pool_N=10000, seed=99)
    print(f"  newborn pool stats: aNrm mean={newborn_aNrm.mean():.5f}  "
          f"pLvl mean={newborn_pLvl.mean():.3f}  std={newborn_pLvl.std():.3f}")

    jargs = (aNrm0, pLvl0, mrkv0,
      jnp.asarray(inp['cfunc_table']), jnp.asarray(inp['m_grid']),
      jnp.asarray(inp['Rfree']), jnp.asarray(inp['PermGroFac']),
      jnp.asarray(inp['MrkvArray']),
      jnp.asarray(inp['IncShk_psi']), jnp.asarray(inp['IncShk_xi']),
      jnp.asarray(inp['IncShk_pmv']),
      1.0, 1.0, inp['Splurge'], inp['LivPrb'],
      jnp.asarray(newborn_aNrm), jnp.asarray(newborn_pLvl),
      jnp.asarray(newborn_mrkv))

    print(f"\nJAX comparison across pLvl_unemp_mode (warmup=0):")
    print(f"{'mode':>7}  {'r_inc':>8}  {'r_cons':>8}  {'corr_inc':>10}  {'corr_cons':>10}  {'corr_cons (skip1)':>18}")
    for mode in ['shock', 'grows', 'qe']:
        _ = simulate_jax(*jargs, act_T, seed_base=0, pLvl_unemp_mode=mode)
        jinc, jcons, _ = simulate_jax(*jargs, act_T, seed_base=0, pLvl_unemp_mode=mode)
        jinc = np.asarray(jinc); jcons = np.asarray(jcons)
        r_inc = jinc.mean()/hark_inc.mean()
        r_cons = jcons.mean()/hark_cons.mean()
        c_inc = np.corrcoef(jinc, hark_inc)[0,1]
        c_cons = np.corrcoef(jcons, hark_cons)[0,1]
        c_cons_s1 = np.corrcoef(jcons[1:], hark_cons[1:])[0,1]
        print(f"{mode:>7}  {r_inc:>8.4f}  {r_cons:>8.4f}  {c_inc:>10.4f}  {c_cons:>10.4f}  {c_cons_s1:>18.4f}")

    print(f"\nGate: ratio close to 1.0 + correlation close to 1.0 = kernel validated")


if __name__ == '__main__':
    main()
