"""
JAX AD kernel variant (Test 2): match HARK newborn-mrkv semantics.

HARK's get_micro_markv_states_guts has a no-op line `MicroMrkvNow[dont_change] =
MicroMrkvNow[dont_change]` (AggFiscalModel:1267) that was intended to keep
newborns at their previous Mrkv but does nothing. Net effect: HARK newborns
get the standard transition based on dead-agent's prev Mrkv.

My original kernel forces newborn Mrkv to 0 (employed). This may bias
JAX toward more employed agents than HARK has, affecting income aggregation.

This variant removes the force-to-employed. Newborn mrkv = transitioned-from-
prev-mrkv (same as alive agents).
"""
from __future__ import annotations
import os, numpy as np
import jax, jax.numpy as jnp
from jax import lax, random
from functools import partial


def _mc_step_ad_v2(carry, scan_in, *,
                    m_grid,
                    Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                    IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                    Splurge, LivPrb,
                    newborn_aNrm, newborn_pLvl,
                    T_age_max=100):
    aNrm_prev, pLvl_prev, mrkv_micro_prev, t_age_prev = carry
    rng_t, macro_t, AggDemandFac_t, cfunc_table_t, skip_transition = scan_in
    rng_death, rng_mrkv, rng_atom = random.split(rng_t, 3)
    N = aNrm_prev.shape[0]
    J = MrkvArray_macro.shape[1]

    death_draw = random.uniform(rng_death, (N,))
    alive_mask = ~((death_draw >= LivPrb) | (t_age_prev >= T_age_max))

    cum_prob = jnp.cumsum(MrkvArray_macro[macro_t][mrkv_micro_prev], axis=-1)
    mrkv_draw = random.uniform(rng_mrkv, (N,))
    mrkv_transitioned = jnp.sum(mrkv_draw[:, None] > cum_prob, axis=-1).astype(jnp.int32)
    mrkv_transitioned = jnp.clip(mrkv_transitioned, 0, J - 1)
    mrkv_micro_now = jnp.where(skip_transition.astype(bool), mrkv_micro_prev, mrkv_transitioned)

    pool_idx = jnp.arange(N) % newborn_aNrm.shape[0]
    aNrm_carry = jnp.where(alive_mask, aNrm_prev, newborn_aNrm[pool_idx])
    pLvl_carry = jnp.where(alive_mask, pLvl_prev, newborn_pLvl[pool_idx])
    # NOTE v2: do NOT force newborn mrkv to 0. Let newborns inherit the transitioned
    # value (which is from dead-agent's prev_mrkv → transitioned). Matches HARK.
    t_age_next = jnp.where(alive_mask, t_age_prev + 1, 0).astype(jnp.int32)

    mrkv_combined = macro_t * J + mrkv_micro_now
    cum_atom = jnp.cumsum(IncShk_pmv_macro[mrkv_combined], axis=-1)
    atom_draw = random.uniform(rng_atom, (N,))
    atom_idx = jnp.sum(atom_draw[:, None] > cum_atom, axis=-1).astype(jnp.int32)
    atom_idx = jnp.clip(atom_idx, 0, IncShk_pmv_macro.shape[-1] - 1)
    psi = IncShk_psi_macro[mrkv_combined, atom_idx]
    xi = IncShk_xi_macro[mrkv_combined, atom_idx]
    R_now = Rfree_macro[mrkv_combined]
    G_now = PermGroFac_macro[mrkv_combined]

    is_employed = (mrkv_micro_now == 0)
    psi_eff = jnp.where(is_employed, psi, 1.0)
    G_eff = jnp.where(is_employed, G_now, 1.0)

    bNrm = R_now * aNrm_carry / (G_eff * psi_eff)
    mNrm = bNrm + xi * AggDemandFac_t

    M = m_grid.shape[0]
    i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
    w_hi = (mNrm - m_grid[i_lo]) / (m_grid[i_lo + 1] - m_grid[i_lo])
    c_lo = cfunc_table_t[mrkv_combined, i_lo]
    c_hi = cfunc_table_t[mrkv_combined, i_lo + 1]
    cNrm = c_lo + w_hi * (c_hi - c_lo)

    pLvl_now = pLvl_carry * G_eff * psi_eff
    cLvl_sp = (1.0 - Splurge) * cNrm * pLvl_now + Splurge * pLvl_now * xi * AggDemandFac_t
    aNrm_next = mNrm - cLvl_sp / pLvl_now

    AggInc_t = jnp.sum(pLvl_now * xi * AggDemandFac_t)
    AggCons_t = jnp.sum(cLvl_sp)

    new_carry = (aNrm_next, pLvl_now, mrkv_micro_now, t_age_next)
    return new_carry, (AggInc_t, AggCons_t, cLvl_sp)


@partial(jax.jit, static_argnames=('act_T', 'T_age_max'))
def _simulate_ad_core_v2(carry0, period_keys, EconomyMrkv_path, AggDemandFac_path,
                          cfunc_table_per_period, skip_transition_path, m_grid,
                          Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                          IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                          Splurge, LivPrb,
                          newborn_aNrm, newborn_pLvl,
                          act_T, T_age_max=100):
    def step(carry, scan_in):
        return _mc_step_ad_v2(
            carry, scan_in,
            m_grid=m_grid,
            Rfree_macro=Rfree_macro, PermGroFac_macro=PermGroFac_macro,
            MrkvArray_macro=MrkvArray_macro,
            IncShk_psi_macro=IncShk_psi_macro,
            IncShk_xi_macro=IncShk_xi_macro,
            IncShk_pmv_macro=IncShk_pmv_macro,
            Splurge=Splurge, LivPrb=LivPrb,
            newborn_aNrm=newborn_aNrm, newborn_pLvl=newborn_pLvl,
            T_age_max=T_age_max,
        )
    scan_inputs = (period_keys, EconomyMrkv_path, AggDemandFac_path,
                   cfunc_table_per_period, skip_transition_path)
    _, outs = lax.scan(step, carry0, scan_inputs)
    return outs


def simulate_jax_ad_v2(aNrm0, pLvl0, mrkv_micro0,
                        EconomyMrkv_path, AggDemandFac_path,
                        cfunc_table_per_period, m_grid,
                        Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                        IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                        Splurge, LivPrb,
                        newborn_aNrm, newborn_pLvl,
                        act_T, seed_base=0, T_age_max=100, t_age0=None):
    fp = jnp.asarray(aNrm0).dtype
    N = aNrm0.shape[0]
    if t_age0 is None:
        rs = np.random.RandomState(seed_base + 7919)
        cum_p = (1 - LivPrb ** (np.arange(T_age_max + 1) + 1)) / max(
            1 - LivPrb ** (T_age_max + 1), 1e-12)
        t_age0_arr = np.searchsorted(cum_p, rs.uniform(size=N)).astype(np.int32)
    else:
        t_age0_arr = np.asarray(t_age0, dtype=np.int32)
    carry0 = (jnp.asarray(aNrm0, dtype=fp),
              jnp.asarray(pLvl0, dtype=fp),
              jnp.asarray(mrkv_micro0, dtype=jnp.int32),
              jnp.asarray(t_age0_arr, dtype=jnp.int32))
    period_keys = random.split(random.PRNGKey(seed_base), act_T)
    skip_transition = np.zeros(act_T, dtype=np.int32)
    skip_transition[0] = 1

    outs = _simulate_ad_core_v2(
        carry0, period_keys,
        jnp.asarray(EconomyMrkv_path, dtype=jnp.int32),
        jnp.asarray(AggDemandFac_path, dtype=fp),
        jnp.asarray(cfunc_table_per_period, dtype=fp),
        jnp.asarray(skip_transition, dtype=jnp.int32),
        jnp.asarray(m_grid, dtype=fp),
        jnp.asarray(Rfree_macro, dtype=fp),
        jnp.asarray(PermGroFac_macro, dtype=fp),
        jnp.asarray(MrkvArray_macro, dtype=fp),
        jnp.asarray(IncShk_psi_macro, dtype=fp),
        jnp.asarray(IncShk_xi_macro, dtype=fp),
        jnp.asarray(IncShk_pmv_macro, dtype=fp),
        Splurge, LivPrb,
        jnp.asarray(newborn_aNrm, dtype=fp), jnp.asarray(newborn_pLvl, dtype=fp),
        act_T, T_age_max=T_age_max,
    )
    AggInc, AggCons, cLvl_panel = outs
    AggInc.block_until_ready()
    return AggInc, AggCons, cLvl_panel
