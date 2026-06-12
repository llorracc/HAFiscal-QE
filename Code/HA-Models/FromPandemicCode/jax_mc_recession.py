"""
jax_mc_recession.py — Phase 8.1: extend JAX MC for recession scenarios.

The base kernel (jax_mc_minimal.simulate_jax) handles single-macro-state
scenarios. Recession scenarios have time-varying macro state via the
EconomyMrkv_path. This file adds a recession-aware kernel that takes
per-macro arrays and a macro-state schedule.

Per-period: macro_t = EconomyMrkv_path[t]. Transitions use
MrkvArray_macro[macro_t]; lookups use combined index = macro_t * J + micro.

KERNEL STATUS: prototype; validation against HARK recession.pkl pending.
"""
from __future__ import annotations
import os
import numpy as np

_HAS_JAX = False
try:
    import jax, jax.numpy as jnp
    from jax import lax, random
    from functools import partial
    _HAS_JAX = True
except ImportError:
    pass


if _HAS_JAX:

    def _mc_step_recession(carry, scan_in, *,
                           cfunc_table_macro, m_grid,
                           Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                           IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                           Splurge, LivPrb,
                           newborn_aNrm, newborn_pLvl,
                           pLvl_unemp_mode='qe',
                           T_age_max=100,
                           ):
        """Per-period step for recession scenario.

        scan_in = (rng_key, macro_t, AggDemandFac_t)
        carry = (aNrm_prev, pLvl_prev, mrkv_micro_prev, t_age_prev)
        """
        aNrm_prev, pLvl_prev, mrkv_micro_prev, t_age_prev = carry
        rng_t, macro_t, AggDemandFac_t = scan_in
        rng_death, rng_mrkv, rng_atom = random.split(rng_t, 3)
        N = aNrm_prev.shape[0]
        J = MrkvArray_macro.shape[1]   # micro-state count

        # Mortality (stochastic OR forced by age)
        death_draw = random.uniform(rng_death, (N,))
        stoch_die = death_draw >= LivPrb
        age_die = t_age_prev >= T_age_max
        alive_mask = ~(stoch_die | age_die)

        # Mrkv transition under CURRENT macro
        # MrkvArray_macro[macro_t] is (J, J); index by mrkv_micro_prev to get row
        cum_prob = jnp.cumsum(MrkvArray_macro[macro_t][mrkv_micro_prev], axis=-1)
        mrkv_draw = random.uniform(rng_mrkv, (N,))
        mrkv_micro_now = jnp.sum(mrkv_draw[:, None] > cum_prob, axis=-1).astype(jnp.int32)
        mrkv_micro_now = jnp.clip(mrkv_micro_now, 0, J - 1)

        # Newborn replacement (always to micro=0 = employed)
        pool_idx = jnp.arange(N) % newborn_aNrm.shape[0]
        aNrm_carry = jnp.where(alive_mask, aNrm_prev, newborn_aNrm[pool_idx])
        pLvl_carry = jnp.where(alive_mask, pLvl_prev, newborn_pLvl[pool_idx])
        mrkv_micro_now = jnp.where(alive_mask, mrkv_micro_now, 0)
        t_age_next = jnp.where(alive_mask, t_age_prev + 1, 0).astype(jnp.int32)

        # Combined index: macro * J + micro
        mrkv_combined = macro_t * J + mrkv_micro_now

        # Income shock atom draw — based on combined state
        cum_atom = jnp.cumsum(IncShk_pmv_macro[mrkv_combined], axis=-1)
        atom_draw = random.uniform(rng_atom, (N,))
        atom_idx = jnp.sum(atom_draw[:, None] > cum_atom, axis=-1).astype(jnp.int32)
        atom_idx = jnp.clip(atom_idx, 0, IncShk_pmv_macro.shape[-1] - 1)
        psi = IncShk_psi_macro[mrkv_combined, atom_idx]
        xi = IncShk_xi_macro[mrkv_combined, atom_idx]

        R_now = Rfree_macro[mrkv_combined]
        G_now = PermGroFac_macro[mrkv_combined]

        is_employed = (mrkv_micro_now == 0)
        if pLvl_unemp_mode == 'qe':
            psi_eff = jnp.where(is_employed, psi, 1.0)
            G_eff = jnp.where(is_employed, G_now, 1.0)
        else:
            psi_eff = psi
            G_eff = G_now

        bNrm = R_now * aNrm_carry / (G_eff * psi_eff)
        mNrm = bNrm + xi * AggDemandFac_t

        # cFunc lookup
        M = m_grid.shape[0]
        i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
        i_hi = i_lo + 1
        w_hi = (mNrm - m_grid[i_lo]) / (m_grid[i_hi] - m_grid[i_lo])
        c_lo = cfunc_table_macro[mrkv_combined, i_lo]
        c_hi = cfunc_table_macro[mrkv_combined, i_hi]
        cNrm = c_lo + w_hi * (c_hi - c_lo)

        pLvl_now = pLvl_carry * G_eff * psi_eff
        cLvl_sp = (1.0 - Splurge) * cNrm * pLvl_now + Splurge * pLvl_now * xi * AggDemandFac_t
        aNrm_next = mNrm - cLvl_sp / pLvl_now

        AggInc_t = jnp.sum(pLvl_now * xi * AggDemandFac_t)
        AggCons_t = jnp.sum(cLvl_sp)

        new_carry = (aNrm_next, pLvl_now, mrkv_micro_now, t_age_next)
        return new_carry, (AggInc_t, AggCons_t, cLvl_sp)


    @partial(jax.jit, static_argnames=('act_T', 'pLvl_unemp_mode', 'T_age_max'))
    def _simulate_recession_core(carry0, period_keys, EconomyMrkv_path, AggDemandFac_path,
                                  cfunc_table_macro, m_grid,
                                  Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                                  IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                                  Splurge, LivPrb,
                                  newborn_aNrm, newborn_pLvl,
                                  act_T, pLvl_unemp_mode='qe', T_age_max=100):
        def step(carry, scan_in):
            return _mc_step_recession(
                carry, scan_in,
                cfunc_table_macro=cfunc_table_macro, m_grid=m_grid,
                Rfree_macro=Rfree_macro, PermGroFac_macro=PermGroFac_macro,
                MrkvArray_macro=MrkvArray_macro,
                IncShk_psi_macro=IncShk_psi_macro,
                IncShk_xi_macro=IncShk_xi_macro,
                IncShk_pmv_macro=IncShk_pmv_macro,
                Splurge=Splurge, LivPrb=LivPrb,
                newborn_aNrm=newborn_aNrm, newborn_pLvl=newborn_pLvl,
                pLvl_unemp_mode=pLvl_unemp_mode,
                T_age_max=T_age_max,
            )
        scan_inputs = (period_keys, EconomyMrkv_path, AggDemandFac_path)
        _, outs = lax.scan(step, carry0, scan_inputs)
        return outs


    def simulate_jax_recession(aNrm0, pLvl0, mrkv_micro0,
                                EconomyMrkv_path, AggDemandFac_path,
                                cfunc_table_macro, m_grid,
                                Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                                IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                                Splurge, LivPrb,
                                newborn_aNrm, newborn_pLvl,
                                act_T, seed_base=0,
                                pLvl_unemp_mode='qe',
                                t_age0=None, T_age_max=100):
        """Recession-aware JAX MC. Inputs:
        - mrkv_micro0: (N,) initial micro state (0..J-1)
        - EconomyMrkv_path: (T,) macro state per period
        - AggDemandFac_path: (T,) aggregate-demand factor per period (1.0 for non-AD)
        - cfunc_table_macro: (n_macro * J, M_grid)
        - MrkvArray_macro: (n_macro, J, J)
        - IncShk_*_macro: ((n_macro * J), max_atoms)
        - Rfree_macro, PermGroFac_macro: (n_macro * J,)
        """
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
        master_key = random.PRNGKey(seed_base)
        period_keys = random.split(master_key, act_T)
        outs = _simulate_recession_core(
            carry0, period_keys,
            jnp.asarray(EconomyMrkv_path, dtype=jnp.int32),
            jnp.asarray(AggDemandFac_path, dtype=fp),
            cfunc_table_macro, m_grid,
            Rfree_macro, PermGroFac_macro, MrkvArray_macro,
            IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
            Splurge, LivPrb, newborn_aNrm, newborn_pLvl,
            act_T,
            pLvl_unemp_mode=pLvl_unemp_mode, T_age_max=T_age_max,
        )
        AggInc, AggCons, cLvl_panel = outs
        AggInc.block_until_ready()
        return AggInc, AggCons, cLvl_panel
