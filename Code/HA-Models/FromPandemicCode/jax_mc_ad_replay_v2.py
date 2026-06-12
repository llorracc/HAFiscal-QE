"""
Replay kernel v2: full HARK alignment.

Difference vs v1 (jax_mc_ad_replay.py): instead of using a fixed newborn pool
indexed by `arange(N) % pool_size`, take HARK's captured per-period post-
sim_birth state (aNrm_init, pLvl_init) and use those values for dead slots.

This eliminates the second RNG-related error source (newborn-replacement
realization mismatch). Combined with shock_history replay (v1 already does
this), should bring JAX-vs-HARK agreement to FP precision.

Inputs vs v1:
  newborn_aNrm_path: (T, N) — HARK's post-sim_birth aNrm at each period
  newborn_pLvl_path: (T, N) — HARK's post-sim_birth pLvl at each period
  (replaces newborn_aNrm, newborn_pLvl which were just 1D pool)
"""
from __future__ import annotations
import os, numpy as np
import jax, jax.numpy as jnp
from jax import lax
from functools import partial


def _mc_step_replay_v2(carry, scan_in, *,
                        m_grid,
                        Rfree_macro, PermGroFac_macro,
                        Splurge, J):
    aNrm_prev, pLvl_prev = carry
    (AggDemandFac_t, cfunc_table_t, mrkv_t, tran_t, perm_t, who_dies_t,
     nb_aNrm_t, nb_pLvl_t) = scan_in
    N = aNrm_prev.shape[0]

    alive_mask = ~who_dies_t
    # NEW v2: use HARK's per-period captured newborn values directly
    aNrm_carry = jnp.where(alive_mask, aNrm_prev, nb_aNrm_t)
    pLvl_carry = jnp.where(alive_mask, pLvl_prev, nb_pLvl_t)

    mrkv_micro = mrkv_t % J
    mrkv_combined = mrkv_t

    R_now = Rfree_macro[mrkv_combined]
    psi_eff = perm_t  # already includes G

    bNrm = R_now * aNrm_carry / psi_eff
    mNrm = bNrm + tran_t * AggDemandFac_t

    M = m_grid.shape[0]
    i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
    w_hi = (mNrm - m_grid[i_lo]) / (m_grid[i_lo + 1] - m_grid[i_lo])
    c_lo = cfunc_table_t[mrkv_combined, i_lo]
    c_hi = cfunc_table_t[mrkv_combined, i_lo + 1]
    cNrm = c_lo + w_hi * (c_hi - c_lo)

    pLvl_now = pLvl_carry * psi_eff
    cLvl_sp = (1.0 - Splurge) * cNrm * pLvl_now + Splurge * pLvl_now * tran_t * AggDemandFac_t
    aNrm_next = mNrm - cLvl_sp / pLvl_now

    AggInc_t = jnp.sum(pLvl_now * tran_t * AggDemandFac_t)
    AggCons_t = jnp.sum(cLvl_sp)

    new_carry = (aNrm_next, pLvl_now)
    return new_carry, (AggInc_t, AggCons_t, cLvl_sp)


@partial(jax.jit, static_argnames=('act_T', 'J'))
def _simulate_replay_v2_core(carry0, AggDemandFac_path, cfunc_table_per_period,
                              mrkv_path, tran_path, perm_path, who_dies_path,
                              nb_aNrm_path, nb_pLvl_path,
                              m_grid, Rfree_macro, PermGroFac_macro,
                              Splurge, act_T, J):
    def step(carry, scan_in):
        return _mc_step_replay_v2(
            carry, scan_in,
            m_grid=m_grid,
            Rfree_macro=Rfree_macro, PermGroFac_macro=PermGroFac_macro,
            Splurge=Splurge, J=J,
        )
    scan_inputs = (AggDemandFac_path, cfunc_table_per_period,
                   mrkv_path, tran_path, perm_path, who_dies_path,
                   nb_aNrm_path, nb_pLvl_path)
    _, outs = lax.scan(step, carry0, scan_inputs)
    return outs


def simulate_jax_replay_v2(aNrm0, pLvl0,
                            AggDemandFac_path,
                            cfunc_table_per_period, m_grid,
                            mrkv_path, tran_path, perm_path, who_dies_path,
                            nb_aNrm_path, nb_pLvl_path,
                            Rfree_macro, PermGroFac_macro,
                            Splurge, act_T, J):
    """Fully RNG-aligned replay. Should match HARK to FP precision."""
    fp = jnp.asarray(aNrm0).dtype
    carry0 = (jnp.asarray(aNrm0, dtype=fp),
              jnp.asarray(pLvl0, dtype=fp))
    outs = _simulate_replay_v2_core(
        carry0,
        jnp.asarray(AggDemandFac_path, dtype=fp),
        jnp.asarray(cfunc_table_per_period, dtype=fp),
        jnp.asarray(mrkv_path, dtype=jnp.int32),
        jnp.asarray(tran_path, dtype=fp),
        jnp.asarray(perm_path, dtype=fp),
        jnp.asarray(who_dies_path, dtype=jnp.bool_),
        jnp.asarray(nb_aNrm_path, dtype=fp),
        jnp.asarray(nb_pLvl_path, dtype=fp),
        jnp.asarray(m_grid, dtype=fp),
        jnp.asarray(Rfree_macro, dtype=fp),
        jnp.asarray(PermGroFac_macro, dtype=fp),
        Splurge, act_T, J,
    )
    AggInc, AggCons, cLvl_panel = outs
    AggInc.block_until_ready()
    return AggInc, AggCons, cLvl_panel
