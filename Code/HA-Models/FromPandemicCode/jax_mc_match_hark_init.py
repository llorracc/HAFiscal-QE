"""
Tighter HARK comparison: use HARK's actual initial state vectors
(pLvl_all_bs[0], Mrkv_hist_bs[0]) as starting point for JAX MC.
This isolates the simulation engine logic from initialization differences.
"""
from __future__ import annotations
import os, sys, time, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import jax.numpy as jnp
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import extract_hark_kernel_inputs
from jax_mc_minimal import simulate_jax, simulate_np


def main():
    print("=== JAX MC tight match against HARK MC (HS_Only base) ===")
    pkl_path = 'welfare6_stratified_bench_HS_Only/seed0/base.pkl'
    if not os.path.exists(pkl_path):
        print(f"ERROR: HARK pickle not found at {pkl_path}")
        return

    print(f"\n[1/4] Load HARK pickle: {pkl_path}")
    hark = pickle.load(open(pkl_path, 'rb'))
    hark_AggInc = np.asarray(hark['AggIncome'])
    hark_AggCons = np.asarray(hark['AggCons'])
    hark_pLvl0 = np.asarray(hark['pLvl_all_bs'][0])
    hark_mrkv0 = np.asarray(hark['Mrkv_hist_bs'][0]) % 6   # micro state only
    N = len(hark_pLvl0)
    act_T = len(hark_AggInc)
    print(f"  N={N}, act_T={act_T}")
    print(f"  HARK Mrkv0 distribution: {np.bincount(hark_mrkv0, minlength=6)}")
    print(f"  HARK pLvl0 stats: mean={hark_pLvl0.mean():.3f}, std={hark_pLvl0.std():.3f}")

    print(f"\n[2/4] build_and_solve + extract kernel inputs...")
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    AggEco.switch_shock_type('base')
    AggEco.solve()
    agent = AggEco.agents[0]
    inp = extract_hark_kernel_inputs(agent, scenario='base')

    # HARK's pickle doesn't store aNrm explicitly. We'd need to derive it from
    # the simulation history. For an initial-condition match, we don't have
    # aNrm0 directly. Best we can do: use HARK's pLvl0, Mrkv0; for aNrm0, use
    # the agent's freshly-initialized state (lognormal-drawn) as a proxy.
    agent.initialize_sim()
    # Try to pull aNrm0 from agent state matching N
    if N <= len(agent.state_now['aNrm']):
        aNrm0 = np.asarray(agent.state_now['aNrm'][:N], dtype=np.float32)
    else:
        # Replicate / cycle
        a_full = np.asarray(agent.state_now['aNrm'])
        aNrm0 = np.tile(a_full, (N // len(a_full) + 1,))[:N].astype(np.float32)
    pLvl0 = hark_pLvl0.astype(np.float32)
    mrkv0 = hark_mrkv0.astype(np.int32)

    nb_N = 200
    newborn_aNrm = aNrm0[:nb_N].copy()
    newborn_pLvl = pLvl0[:nb_N].copy()
    newborn_mrkv = np.zeros(nb_N, dtype=np.int32)

    print(f"  Using HARK pLvl0 + Mrkv0; aNrm0 from agent's lognormal init (proxy)")

    print(f"\n[3/4] Run JAX kernel...")
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
    _ = simulate_jax(*jax_args, act_T, seed_base=0)
    t0 = time.time()
    jax_inc, jax_cons, _ = simulate_jax(*jax_args, act_T, seed_base=0)
    wall_jax = time.time() - t0
    jax_inc_np = np.asarray(jax_inc)
    jax_cons_np = np.asarray(jax_cons)
    print(f"  JAX wall: {wall_jax:.4f}s")
    print(f"  HARK runtime_s (reported): {hark.get('runtime_s', 'n/a')}")

    print(f"\n[4/4] Per-period comparison (HARK vs JAX):")
    print(f"  {'t':>3}  {'HARK AggInc':>14}  {'JAX AggInc':>14}  {'ratio':>8}  {'HARK Cons':>14}  {'JAX Cons':>14}")
    for t in [0, 1, 2, 5, 10, 20, 30, 39]:
        if t < act_T:
            print(f"  {t:>3}  {hark_AggInc[t]:>14.3f}  {jax_inc_np[t]:>14.3f}  "
                  f"{jax_inc_np[t]/hark_AggInc[t]:>7.4f}  "
                  f"{hark_AggCons[t]:>14.3f}  {jax_cons_np[t]:>14.3f}")

    print(f"\n  Mean ratio JAX/HARK AggInc: {jax_inc_np.mean()/hark_AggInc.mean():.4f}")
    print(f"  Mean ratio JAX/HARK AggCons: {jax_cons_np.mean()/hark_AggCons.mean():.4f}")
    corr_inc = np.corrcoef(jax_inc_np, hark_AggInc)[0, 1]
    corr_cons = np.corrcoef(jax_cons_np, hark_AggCons)[0, 1]
    print(f"  Per-period corr AggInc:  {corr_inc:.4f}")
    print(f"  Per-period corr AggCons: {corr_cons:.4f}")
    print(f"\n  Speedup: JAX {wall_jax*1000:.1f}ms vs HARK {hark.get('runtime_s', 'n/a')}s = "
          f"{hark.get('runtime_s', 0)/wall_jax:.1f}x")


if __name__ == '__main__':
    main()
