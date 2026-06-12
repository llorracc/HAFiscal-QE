"""
JAX MC kernel variant supporting Check / TaxCut / UI policy income overrides.

For Check: add CheckAmount[n] dollars to xi*pLvl for employed agents at t=0.
For TaxCut: multiply employed agents' xi*pLvl by tax_cut_multiplier per period.
For UI extension: extra IncUnemp for u3Q/u4Q during recession macros (BUG-043).

Kernel takes additional inputs:
  extra_income_per_agent_t0: (N,) — dollars added at t=0 (Check)
  tax_cut_factor_per_t: (T,) — multiplier on employed income (TaxCut)
"""
from __future__ import annotations
import os, numpy as np

import jax, jax.numpy as jnp
from jax import lax, random
from functools import partial


def compute_check_amount_per_agent(pLvl0, CheckStimLvl=1.0,
                                    cutoff_start=None, cutoff_end=None):
    """Mirror HARK's Check policy: per-agent dollar amount as function of pLvl.

    HARK formula:
      base = CheckStimLvl  (a per-agent dollar amount, e.g. $1000 = 1.0)
      scalar = 1 if pLvl < cutoff_start
             = 0 if pLvl > cutoff_end
             = 1 - (pLvl - start) / (end - start) otherwise
      Check[n] = base * scalar
    """
    N = pLvl0.shape[0]
    if cutoff_start is None or cutoff_end is None:
        # Default: uniform check
        return np.full(N, CheckStimLvl, dtype=np.float32)
    scalar = np.where(
        pLvl0 < cutoff_start, 1.0,
        np.where(pLvl0 > cutoff_end, 0.0,
                 1.0 - (pLvl0 - cutoff_start) / max(cutoff_end - cutoff_start, 1e-12))
    )
    return (CheckStimLvl * scalar).astype(np.float32)


def _mc_step_policy(carry, scan_in, *,
                    cfunc_table_macro, m_grid,
                    Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                    IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                    Splurge, LivPrb,
                    newborn_aNrm, newborn_pLvl,
                    T_age_max=100,
                    ):
    """Per-period step with policy-income overrides.

    scan_in: (rng_t, macro_t, extra_dollars_t, tax_cut_factor_t)
      extra_dollars_t: (N,) extra income dollars added for employed agents this period
      tax_cut_factor_t: scalar multiplier applied to employed agents' base income
    """
    aNrm_prev, pLvl_prev, mrkv_micro_prev, t_age_prev = carry
    rng_t, macro_t, extra_dollars_t, tax_cut_factor_t = scan_in
    rng_death, rng_mrkv, rng_atom = random.split(rng_t, 3)
    N = aNrm_prev.shape[0]
    J = MrkvArray_macro.shape[1]

    death_draw = random.uniform(rng_death, (N,))
    alive_mask = ~((death_draw >= LivPrb) | (t_age_prev >= T_age_max))

    cum_prob = jnp.cumsum(MrkvArray_macro[macro_t][mrkv_micro_prev], axis=-1)
    mrkv_draw = random.uniform(rng_mrkv, (N,))
    mrkv_micro_now = jnp.sum(mrkv_draw[:, None] > cum_prob, axis=-1).astype(jnp.int32)
    mrkv_micro_now = jnp.clip(mrkv_micro_now, 0, J - 1)

    pool_idx = jnp.arange(N) % newborn_aNrm.shape[0]
    aNrm_carry = jnp.where(alive_mask, aNrm_prev, newborn_aNrm[pool_idx])
    pLvl_carry = jnp.where(alive_mask, pLvl_prev, newborn_pLvl[pool_idx])
    mrkv_micro_now = jnp.where(alive_mask, mrkv_micro_now, 0)
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
    # Apply policy modifications:
    # 1. TaxCut: multiply employed xi by tax_cut_factor
    xi_post_taxcut = jnp.where(is_employed, xi * tax_cut_factor_t, xi)
    # 2. Check: add extra_dollars[n] per agent for employed only, as TranShk delta
    # extra_dollars is in $; convert to xi-equivalent: extra_xi = dollars / pLvl_now
    # But pLvl_now depends on psi which depends on this period's shock —
    # simpler: just add dollars to total income (pLvl × xi)
    mNrm = bNrm + xi_post_taxcut + jnp.where(is_employed, extra_dollars_t / (pLvl_carry * G_eff * psi_eff), 0.0)

    M = m_grid.shape[0]
    i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
    w_hi = (mNrm - m_grid[i_lo]) / (m_grid[i_lo + 1] - m_grid[i_lo])
    cNrm = cfunc_table_macro[mrkv_combined, i_lo] + w_hi * (
        cfunc_table_macro[mrkv_combined, i_lo + 1] - cfunc_table_macro[mrkv_combined, i_lo])

    pLvl_now = pLvl_carry * G_eff * psi_eff
    # Total xi-effective for income calculation (includes check + taxcut)
    xi_total = xi_post_taxcut + jnp.where(is_employed, extra_dollars_t / pLvl_now, 0.0)
    cLvl_sp = (1.0 - Splurge) * cNrm * pLvl_now + Splurge * pLvl_now * xi_total
    aNrm_next = mNrm - cLvl_sp / pLvl_now

    AggInc_t = jnp.sum(pLvl_now * xi_total)
    AggCons_t = jnp.sum(cLvl_sp)

    new_carry = (aNrm_next, pLvl_now, mrkv_micro_now, t_age_next)
    return new_carry, (AggInc_t, AggCons_t, cLvl_sp)


@partial(jax.jit, static_argnames=('act_T', 'T_age_max'))
def _simulate_policy_core(carry0, period_keys, EconomyMrkv_path,
                          extra_dollars_path, tax_cut_path,
                          cfunc_table_macro, m_grid,
                          Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                          IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                          Splurge, LivPrb,
                          newborn_aNrm, newborn_pLvl,
                          act_T, T_age_max=100):
    def step(carry, scan_in):
        return _mc_step_policy(
            carry, scan_in,
            cfunc_table_macro=cfunc_table_macro, m_grid=m_grid,
            Rfree_macro=Rfree_macro, PermGroFac_macro=PermGroFac_macro,
            MrkvArray_macro=MrkvArray_macro,
            IncShk_psi_macro=IncShk_psi_macro,
            IncShk_xi_macro=IncShk_xi_macro,
            IncShk_pmv_macro=IncShk_pmv_macro,
            Splurge=Splurge, LivPrb=LivPrb,
            newborn_aNrm=newborn_aNrm, newborn_pLvl=newborn_pLvl,
            T_age_max=T_age_max,
        )
    scan_inputs = (period_keys, EconomyMrkv_path, extra_dollars_path, tax_cut_path)
    _, outs = lax.scan(step, carry0, scan_inputs)
    return outs


def simulate_jax_policy(aNrm0, pLvl0, mrkv_micro0,
                        EconomyMrkv_path,
                        extra_dollars_per_agent_path,   # (T, N) extra income dollars
                        tax_cut_factor_path,             # (T,) TaxCut multiplier
                        cfunc_table_macro, m_grid,
                        Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                        IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                        Splurge, LivPrb,
                        newborn_aNrm, newborn_pLvl,
                        act_T, seed_base=0, T_age_max=100, t_age0=None):
    """Run JAX MC with optional Check and TaxCut policy overrides.

    For base scenario: extra_dollars_path = zeros, tax_cut_path = ones
    For Check: extra_dollars_path[0, :] = per-agent CheckAmount, rest zero
    For TaxCut: tax_cut_path = TaxCutIncFactor while tax cut active, else 1
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
    period_keys = random.split(random.PRNGKey(seed_base), act_T)

    outs = _simulate_policy_core(
        carry0, period_keys,
        jnp.asarray(EconomyMrkv_path, dtype=jnp.int32),
        jnp.asarray(extra_dollars_per_agent_path, dtype=fp),
        jnp.asarray(tax_cut_factor_path, dtype=fp),
        cfunc_table_macro, m_grid,
        Rfree_macro, PermGroFac_macro, MrkvArray_macro,
        IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
        Splurge, LivPrb, newborn_aNrm, newborn_pLvl,
        act_T, T_age_max=T_age_max,
    )
    AggInc, AggCons, cLvl_panel = outs
    AggInc.block_until_ready()
    return AggInc, AggCons, cLvl_panel
