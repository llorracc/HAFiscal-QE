"""
JAX MC kernel variant: replay HARK's pre-computed shock_history rather than
sampling from distributions. Eliminates RNG-realization variance as a source
of JAX-vs-HARK discrepancy.

If this matches HARK bit-for-bit (within FP precision), residual ~0.5%
in Baseline diag6 was RNG. If still has residual, there's a logic bug.

Inputs (per cohort, shape (T, N)):
  hark_Mrkv:    int32, combined Mrkv index per agent per period
  hark_TranShk: float, transitory shock (post state-override by HARK)
  hark_PermShk: float, permanent shock (post state-override)
  hark_who_dies: bool, mortality flag

No randomness inside the scan — every value comes from the input arrays.
"""
from __future__ import annotations
import os, numpy as np
import jax, jax.numpy as jnp
from jax import lax
from functools import partial


def _mc_step_replay(carry, scan_in, *,
                     m_grid,
                     Rfree_macro, PermGroFac_macro,
                     Splurge,
                     newborn_aNrm, newborn_pLvl,
                     J):
    """Per-period step using HARK pre-computed shocks."""
    aNrm_prev, pLvl_prev = carry
    AggDemandFac_t, cfunc_table_t, mrkv_t, tran_t, perm_t, who_dies_t = scan_in
    N = aNrm_prev.shape[0]

    alive_mask = ~who_dies_t
    # Newborn replacement (deterministic pool indexing)
    pool_idx = jnp.arange(N) % newborn_aNrm.shape[0]
    aNrm_carry = jnp.where(alive_mask, aNrm_prev, newborn_aNrm[pool_idx])
    pLvl_carry = jnp.where(alive_mask, pLvl_prev, newborn_pLvl[pool_idx])

    mrkv_micro = mrkv_t % J
    mrkv_combined = mrkv_t  # full combined index from HARK

    R_now = Rfree_macro[mrkv_combined]
    # KEY FIX: HARK's shock_history['PermShk'] already INCLUDES PermGroFac.
    # Per HARK ConsAggShockModel.py:1136 and ConsIndShockModel.py:2238:
    #   PermShkNow = ShockDraws * PermGroFacNow
    # And HARK's transition: pLvl_now = pLvl_prev * shocks['PermShk']  (NO extra G)
    #                       bNrm = R * aNrm / shocks['PermShk']  (NO extra G)
    # So perm_t = psi * G already; don't multiply by G again.
    psi_eff = perm_t

    bNrm = R_now * aNrm_carry / psi_eff
    # HARK's get_states (with ad_in_budget=True): mNrm = bNrm + TranShk * AggDemandFac
    mNrm = bNrm + tran_t * AggDemandFac_t

    M = m_grid.shape[0]
    i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
    w_hi = (mNrm - m_grid[i_lo]) / (m_grid[i_lo + 1] - m_grid[i_lo])
    c_lo = cfunc_table_t[mrkv_combined, i_lo]
    c_hi = cfunc_table_t[mrkv_combined, i_lo + 1]
    cNrm = c_lo + w_hi * (c_hi - c_lo)

    pLvl_now = pLvl_carry * psi_eff  # FIX: no separate G; psi_eff already = psi*G
    cLvl_sp = (1.0 - Splurge) * cNrm * pLvl_now + Splurge * pLvl_now * tran_t * AggDemandFac_t
    aNrm_next = mNrm - cLvl_sp / pLvl_now

    AggInc_t = jnp.sum(pLvl_now * tran_t * AggDemandFac_t)
    AggCons_t = jnp.sum(cLvl_sp)

    new_carry = (aNrm_next, pLvl_now)
    return new_carry, (AggInc_t, AggCons_t, cLvl_sp)


@partial(jax.jit, static_argnames=('act_T', 'J'))
def _simulate_replay_core(carry0, AggDemandFac_path, cfunc_table_per_period,
                          mrkv_path, tran_path, perm_path, who_dies_path,
                          m_grid, Rfree_macro, PermGroFac_macro,
                          Splurge, newborn_aNrm, newborn_pLvl,
                          act_T, J):
    def step(carry, scan_in):
        return _mc_step_replay(
            carry, scan_in,
            m_grid=m_grid,
            Rfree_macro=Rfree_macro, PermGroFac_macro=PermGroFac_macro,
            Splurge=Splurge,
            newborn_aNrm=newborn_aNrm, newborn_pLvl=newborn_pLvl,
            J=J,
        )
    scan_inputs = (AggDemandFac_path, cfunc_table_per_period,
                   mrkv_path, tran_path, perm_path, who_dies_path)
    _, outs = lax.scan(step, carry0, scan_inputs)
    return outs


def simulate_jax_replay(aNrm0, pLvl0,
                         AggDemandFac_path,
                         cfunc_table_per_period, m_grid,
                         mrkv_path,        # (T, N) int32 — combined Mrkv per agent per period
                         tran_path,        # (T, N) float — TranShk
                         perm_path,        # (T, N) float — PermShk
                         who_dies_path,    # (T, N) bool
                         Rfree_macro, PermGroFac_macro,
                         Splurge,
                         newborn_aNrm, newborn_pLvl,
                         act_T, J):
    """Replay HARK's deterministic shock trajectory through JAX kernel."""
    fp = jnp.asarray(aNrm0).dtype
    carry0 = (jnp.asarray(aNrm0, dtype=fp),
              jnp.asarray(pLvl0, dtype=fp))
    outs = _simulate_replay_core(
        carry0,
        jnp.asarray(AggDemandFac_path, dtype=fp),
        jnp.asarray(cfunc_table_per_period, dtype=fp),
        jnp.asarray(mrkv_path, dtype=jnp.int32),
        jnp.asarray(tran_path, dtype=fp),
        jnp.asarray(perm_path, dtype=fp),
        jnp.asarray(who_dies_path, dtype=jnp.bool_),
        jnp.asarray(m_grid, dtype=fp),
        jnp.asarray(Rfree_macro, dtype=fp),
        jnp.asarray(PermGroFac_macro, dtype=fp),
        Splurge,
        jnp.asarray(newborn_aNrm, dtype=fp), jnp.asarray(newborn_pLvl, dtype=fp),
        act_T, J,
    )
    AggInc, AggCons, cLvl_panel = outs
    AggInc.block_until_ready()
    return AggInc, AggCons, cLvl_panel
