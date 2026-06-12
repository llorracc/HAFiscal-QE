"""
Trace per-agent pLvl + aNrm trajectories: JAX vs HARK.

The HARK pickle has full T×N panels for pLvl and aNrm. Run JAX with
HARK's exact t=0 state and compare trajectories agent-by-agent to
pinpoint where the 2.2% drift enters.
"""
from __future__ import annotations
import os, sys, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import jax.numpy as jnp
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import extract_hark_kernel_inputs, draw_newborn_pool_from_agent
from jax_mc_minimal import simulate_jax, _mc_step_jax


def main():
    pkl = 'welfare6_HS_clean_nshuf/base.pkl'
    hark = pickle.load(open(pkl, 'rb'))
    h_pLvl = np.asarray(hark['pLvl_all_bs'])    # (T, N)
    h_aNrm = np.asarray(hark['aNrm_all_bs'])    # (T, N)
    h_mrkv = np.asarray(hark['Mrkv_hist_bs']) % 6  # (T, N)
    T, N = h_pLvl.shape
    print(f"HARK panels: T={T}, N={N}")

    print(f"\nHARK pLvl mean over time:")
    print(f"  t=0:  {h_pLvl[0].mean():.4f}  std={h_pLvl[0].std():.4f}")
    print(f"  t=10: {h_pLvl[10].mean():.4f}  std={h_pLvl[10].std():.4f}")
    print(f"  t=20: {h_pLvl[20].mean():.4f}  std={h_pLvl[20].std():.4f}")
    print(f"  t=30: {h_pLvl[30].mean():.4f}  std={h_pLvl[30].std():.4f}")
    print(f"  t=39: {h_pLvl[39].mean():.4f}  std={h_pLvl[39].std():.4f}")
    print(f"\nHARK aNrm mean over time:")
    print(f"  t=0:  {h_aNrm[0].mean():.4f}  std={h_aNrm[0].std():.4f}")
    print(f"  t=20: {h_aNrm[20].mean():.4f}  std={h_aNrm[20].std():.4f}")
    print(f"  t=39: {h_aNrm[39].mean():.4f}  std={h_aNrm[39].std():.4f}")

    # Run JAX
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    AggEco.switch_shock_type('base')
    AggEco.solve()
    agent = AggEco.agents[0]
    inp = extract_hark_kernel_inputs(agent, scenario='base')

    aNrm0 = h_aNrm[0].astype(np.float32)
    pLvl0 = h_pLvl[0].astype(np.float32)
    mrkv0 = h_mrkv[0].astype(np.int32)
    nbA, nbP, nbM = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99)

    # Manual scan loop (we need pLvl/aNrm trajectories, not just AggInc/Cons)
    # Use simulate_jax which returns cLvl_panel; but pLvl is internal.
    # Easier: re-run kernel manually period-by-period extracting state.
    import jax, jax.numpy as jnp
    from jax import random, lax

    # Inputs
    cfunc_table = jnp.asarray(inp['cfunc_table'])
    m_grid = jnp.asarray(inp['m_grid'])
    Rfree = jnp.asarray(inp['Rfree'])
    PermGroFac = jnp.asarray(inp['PermGroFac'])
    MrkvArray = jnp.asarray(inp['MrkvArray'])
    IncShk_psi = jnp.asarray(inp['IncShk_psi'])
    IncShk_xi = jnp.asarray(inp['IncShk_xi'])
    IncShk_pmv = jnp.asarray(inp['IncShk_pmv'])
    newborn_aNrm_j = jnp.asarray(nbA)
    newborn_pLvl_j = jnp.asarray(nbP)
    newborn_mrkv_j = jnp.asarray(nbM)

    def step_with_state(carry, key):
        aNrm_prev, pLvl_prev, mrkv_prev = carry
        # Same logic as _mc_step_jax but returns the new carry as part of output
        N = aNrm_prev.shape[0]
        J = MrkvArray.shape[0]
        rng_death, rng_mrkv, rng_atom = random.split(key, 3)

        death_draw = random.uniform(rng_death, (N,))
        alive_mask = death_draw < inp['LivPrb']

        mrkv_draw = random.uniform(rng_mrkv, (N,))
        cum_prob = jnp.cumsum(MrkvArray[mrkv_prev], axis=-1)
        mrkv_now = jnp.sum(mrkv_draw[:, None] > cum_prob, axis=-1)
        mrkv_now = jnp.clip(mrkv_now, 0, J - 1)

        pool_idx = jnp.arange(N) % newborn_aNrm_j.shape[0]
        aNrm_carry = jnp.where(alive_mask, aNrm_prev, newborn_aNrm_j[pool_idx])
        pLvl_carry = jnp.where(alive_mask, pLvl_prev, newborn_pLvl_j[pool_idx])
        mrkv_now = jnp.where(alive_mask, mrkv_now, newborn_mrkv_j[pool_idx])

        atom_draw = random.uniform(rng_atom, (N,))
        cum_atom = jnp.cumsum(IncShk_pmv[mrkv_now], axis=-1)
        atom_idx = jnp.sum(atom_draw[:, None] > cum_atom, axis=-1)
        max_atoms = IncShk_pmv.shape[-1]
        atom_idx = jnp.clip(atom_idx, 0, max_atoms - 1)
        psi = IncShk_psi[mrkv_now, atom_idx]
        xi = IncShk_xi[mrkv_now, atom_idx]

        R_now = Rfree[mrkv_now]
        G_now = PermGroFac[mrkv_now]
        # 'qe' mode logic
        is_employed = (mrkv_now == 0)
        psi_eff = jnp.where(is_employed, psi, 1.0)
        G_eff = jnp.where(is_employed, G_now, 1.0)

        bNrm = R_now * aNrm_carry / (G_eff * psi_eff)
        mNrm = bNrm + xi * 1.0  # AggDemandFac=1

        # cFunc lookup (searchsorted)
        M = m_grid.shape[0]
        i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
        i_hi = i_lo + 1
        m_lo = m_grid[i_lo]
        m_hi = m_grid[i_hi]
        w_hi = (mNrm - m_lo) / (m_hi - m_lo)
        c_lo = cfunc_table[mrkv_now, i_lo]
        c_hi = cfunc_table[mrkv_now, i_hi]
        cNrm = c_lo + w_hi * (c_hi - c_lo)

        pLvl_now = pLvl_carry * G_eff * psi_eff
        cLvl = cNrm * pLvl_now
        cLvl_splurge = (1.0 - inp['Splurge']) * cLvl + inp['Splurge'] * pLvl_now * xi * 1.0
        aNrm_next = mNrm - cLvl_splurge / pLvl_now

        new_carry = (aNrm_next, pLvl_now, mrkv_now)
        # Output: full state (aNrm_next, pLvl_now, mrkv_now)
        return new_carry, (aNrm_next, pLvl_now, mrkv_now)

    carry0 = (jnp.asarray(aNrm0), jnp.asarray(pLvl0), jnp.asarray(mrkv0))
    keys = random.split(random.PRNGKey(0), T)
    _, (a_traj, p_traj, m_traj) = lax.scan(step_with_state, carry0, keys)
    a_traj = np.asarray(a_traj); p_traj = np.asarray(p_traj); m_traj = np.asarray(m_traj)
    # a_traj/p_traj/m_traj shape: (T, N) — these are the state AFTER each period

    print(f"\nJAX pLvl mean over time (after each period):")
    print(f"  t=0:  {p_traj[0].mean():.4f}  std={p_traj[0].std():.4f}")
    print(f"  t=10: {p_traj[10].mean():.4f}  std={p_traj[10].std():.4f}")
    print(f"  t=20: {p_traj[20].mean():.4f}  std={p_traj[20].std():.4f}")
    print(f"  t=39: {p_traj[39].mean():.4f}  std={p_traj[39].std():.4f}")
    print(f"\nJAX aNrm mean over time:")
    print(f"  t=0:  {a_traj[0].mean():.4f}")
    print(f"  t=20: {a_traj[20].mean():.4f}")
    print(f"  t=39: {a_traj[39].mean():.4f}")

    print(f"\nRatio JAX/HARK pLvl by period:")
    for t in [0, 1, 2, 5, 10, 15, 20, 25, 30, 35, 39]:
        r = p_traj[t].mean() / h_pLvl[t].mean() if t > 0 else 1.0
        # NOTE: t=0 in p_traj is AFTER one JAX step; HARK's t=0 is the initial state
        # So compare p_traj[t] with h_pLvl[t+1] for like-with-like
        if t + 1 < T:
            r_aligned = p_traj[t].mean() / h_pLvl[t+1].mean()
            print(f"  t={t:2d}: JAX p_traj[{t}]={p_traj[t].mean():.4f}  HARK p_all_bs[{t+1}]={h_pLvl[t+1].mean():.4f}  ratio={r_aligned:.4f}")


if __name__ == '__main__':
    main()
