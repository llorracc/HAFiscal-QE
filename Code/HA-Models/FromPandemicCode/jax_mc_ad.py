"""
jax_mc_ad.py — Phase 8.4: AD outer loop integration for JAX MC.

Strategy: outer Python loop iterates Cratio belief CFunc → cFunc tables → JAX
sim → realized Cratio_hist → updated CFunc → ... mirroring HARK's
solve_ad_recession. JAX kernel is the existing recession kernel but with
TIME-VARYING cfunc_table (T, n_combined, M) so each period's c is looked up
against the predicted scalar Cratio_t baked into that period's table.

Why per-period table vs in-scan 2D bilinear? HARK's converged AD beliefs
yield a deterministic Cratio_pred_t per period given EconomyMrkv_path. We
precompute cFunc[j](m_grid, Cratio_pred_t) outside JAX once per iteration.
The per-period table costs T·n_combined·M·4 bytes ≈ 10 MB at HS_Only — fine.
"""
from __future__ import annotations
import os
import numpy as np

import jax, jax.numpy as jnp
from jax import lax, random
from functools import partial


def _mc_step_ad(carry, scan_in, *,
                m_grid,
                Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                Splurge, LivPrb,
                newborn_aNrm, newborn_pLvl,
                T_age_max=100):
    """Per-period step with time-varying cfunc_table and AggDemandFac.

    Mrkv timing convention (matches HARK): at t=0 (skip_transition=1) the
    input mrkv_micro_prev IS the Mrkv that agents observe — bypass the
    transition. At t>=1 (skip_transition=0) sample new Mrkv via MrkvArray.
    """
    aNrm_prev, pLvl_prev, mrkv_micro_prev, t_age_prev = carry
    # scan_in includes per-period policy overrides (tax_cut, check_dollars).
    # For no-policy AD scenarios, tax_cut_t=1.0 and check_dollars_t=(N,) zeros.
    (rng_t, macro_t, AggDemandFac_t, cfunc_table_t, skip_transition,
     tax_cut_t, check_dollars_t) = scan_in
    rng_death, rng_mrkv, rng_atom, rng_birth = random.split(rng_t, 4)
    N = aNrm_prev.shape[0]
    J = MrkvArray_macro.shape[1]

    death_draw = random.uniform(rng_death, (N,))
    alive_mask = ~((death_draw >= LivPrb) | (t_age_prev >= T_age_max))

    cum_prob = jnp.cumsum(MrkvArray_macro[macro_t][mrkv_micro_prev], axis=-1)
    mrkv_draw = random.uniform(rng_mrkv, (N,))
    mrkv_transitioned = jnp.sum(mrkv_draw[:, None] > cum_prob, axis=-1).astype(jnp.int32)
    mrkv_transitioned = jnp.clip(mrkv_transitioned, 0, J - 1)
    # At t=0: keep input directly (HARK reads pre-computed shock_history[0])
    # At t>=1: use the transitioned value
    mrkv_micro_now = jnp.where(skip_transition.astype(bool), mrkv_micro_prev, mrkv_transitioned)

    # Randomized newborn pool indexing per period — gives each death event a
    # fresh draw from the pool, matching HARK's sim_birth semantics in marginal
    # distribution. Previous fixed `arange(N) % pool_size` indexing was
    # deterministic per slot, causing systematic ~1% bias vs HARK at Baseline.
    pool_idx = random.randint(rng_birth, (N,), 0, newborn_aNrm.shape[0])
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

    # OPTIONAL policy income overrides — TaxCut multiplies employed xi,
    # Check adds dollars to employed (converted to xi-units via current pLvl).
    # These are passed through scan as 2 extra inputs; both 1.0/0.0 if no policy.
    pLvl_now_pre = pLvl_carry * G_eff * psi_eff
    xi_taxcut = jnp.where(is_employed, xi * tax_cut_t, xi)
    extra_xi = jnp.where(is_employed, check_dollars_t / pLvl_now_pre, 0.0)
    xi_total = xi_taxcut + extra_xi

    bNrm = R_now * aNrm_carry / (G_eff * psi_eff)
    # AD-aware budget: mNrm = bNrm + TranShk * AggDemandFac
    mNrm = bNrm + xi_total * AggDemandFac_t

    M = m_grid.shape[0]
    i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
    w_hi = (mNrm - m_grid[i_lo]) / (m_grid[i_lo + 1] - m_grid[i_lo])
    c_lo = cfunc_table_t[mrkv_combined, i_lo]
    c_hi = cfunc_table_t[mrkv_combined, i_lo + 1]
    cNrm = c_lo + w_hi * (c_hi - c_lo)

    pLvl_now = pLvl_now_pre  # already = pLvl_carry * G_eff * psi_eff
    cLvl_sp = (1.0 - Splurge) * cNrm * pLvl_now + Splurge * pLvl_now * xi_total * AggDemandFac_t
    aNrm_next = mNrm - cLvl_sp / pLvl_now

    AggInc_t = jnp.sum(pLvl_now * xi_total * AggDemandFac_t)
    AggCons_t = jnp.sum(cLvl_sp)

    new_carry = (aNrm_next, pLvl_now, mrkv_micro_now, t_age_next)
    return new_carry, (AggInc_t, AggCons_t, cLvl_sp)


@partial(jax.jit, static_argnames=('act_T', 'T_age_max'))
def _simulate_ad_core(carry0, period_keys, EconomyMrkv_path, AggDemandFac_path,
                      cfunc_table_per_period, skip_transition_path,
                      tax_cut_path, check_dollars_path, m_grid,
                      Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                      IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                      Splurge, LivPrb,
                      newborn_aNrm, newborn_pLvl,
                      act_T, T_age_max=100):
    def step(carry, scan_in):
        return _mc_step_ad(
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
                   cfunc_table_per_period, skip_transition_path,
                   tax_cut_path, check_dollars_path)
    _, outs = lax.scan(step, carry0, scan_inputs)
    return outs


def simulate_jax_ad(aNrm0, pLvl0, mrkv_micro0,
                    EconomyMrkv_path, AggDemandFac_path,
                    cfunc_table_per_period,
                    m_grid,
                    Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                    IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                    Splurge, LivPrb,
                    newborn_aNrm, newborn_pLvl,
                    act_T, seed_base=0, T_age_max=100, t_age0=None,
                    tax_cut_path=None, check_dollars_path=None):
    """Run JAX MC for AD scenario with time-varying cfunc_table per period.

    cfunc_table_per_period: (T, n_combined, M_grid) — must satisfy T == act_T
    AggDemandFac_path: (T,) — derived from belief CFunc rule applied along
      EconomyMrkv_path; this is the AggDemandFac AGENTS observe at period t.
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

    # skip_transition[t]: 1 at t=0 (use input mrkv), 0 elsewhere (transition).
    # Matches HARK's pre-computed shock_history[0] semantics.
    skip_transition = np.zeros(act_T, dtype=np.int32)
    skip_transition[0] = 1

    # Default policy overrides: no tax cut, no check dollars
    if tax_cut_path is None:
        tax_cut_path = np.ones(act_T, dtype=np.float32)
    if check_dollars_path is None:
        check_dollars_path = np.zeros((act_T, N), dtype=np.float32)

    outs = _simulate_ad_core(
        carry0, period_keys,
        jnp.asarray(EconomyMrkv_path, dtype=jnp.int32),
        jnp.asarray(AggDemandFac_path, dtype=fp),
        jnp.asarray(cfunc_table_per_period, dtype=fp),
        jnp.asarray(skip_transition, dtype=jnp.int32),
        jnp.asarray(tax_cut_path, dtype=fp),
        jnp.asarray(check_dollars_path, dtype=fp),
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


def extract_cfunc_table_per_period(agent, Cratio_path, m_grid, n_combined,
                                    n_macro=None, num_base_MrkvStates=None):
    """Build (T, n_combined, M) cFunc table at HARK-converged 2D cFunc evaluated
    at scalar Cratio_path[t].

    For each t and combined state j: table[t, j, :] = sol.cFunc[j](m_grid, Cratio_path[t]).
    """
    T = len(Cratio_path)
    M = len(m_grid)
    table = np.zeros((T, n_combined, M), dtype=np.float32)
    sol = agent.solution[0]
    m_arr = np.asarray(m_grid)
    for t in range(T):
        c_arr = np.full(M, float(Cratio_path[t]))
        for j in range(n_combined):
            try:
                table[t, j, :] = sol.cFunc[j](m_arr, c_arr)
            except TypeError:
                # Fallback for 1-arg cFunc (no AD)
                table[t, j, :] = sol.cFunc[j](m_arr)
    return table


# ============================================================================
# Speedup 1A: lift cFunc once on (m, C) grid; bilinear in kernel
# ============================================================================

# Default C-axis lift grid. Covers a generous Cratio range. With 32 points on
# [0.5, 1.5], lift spacing is ~0.032; bilinear-in-C error is O(dx^2) ≈ 1e-3
# but with cFunc near-linear-in-C the actual error is much smaller (validated
# to <1e-4 vs per-period evaluation).
_DEFAULT_C_LIFT_MIN = 0.5
_DEFAULT_C_LIFT_MAX = 1.5
_DEFAULT_C_LIFT_N = 32


def extract_cfunc_2d_table(agent, m_grid, n_combined,
                             C_lift_min=_DEFAULT_C_LIFT_MIN,
                             C_lift_max=_DEFAULT_C_LIFT_MAX,
                             C_lift_n=_DEFAULT_C_LIFT_N):
    """Lift HARK 2D cFunc on a uniform (m, C) grid ONCE per cohort per AD iter.

    Returns:
        table: (n_combined, M_grid, C_grid) float32 tensor
        C_grid: (C_grid,) uniform grid in Cratio

    The kernel can then evaluate cFunc(m, C) at any (m, C) query via bilinear
    interpolation into this table. This replaces the previous per-period
    rebuild (extract_cfunc_table_per_period) which did T * n_combined HARK
    cFunc calls; the lift only does n_combined * C_grid calls. With C_grid=32
    vs T=96, that's a ~3x reduction in HARK cFunc evaluations during the
    table build phase.

    Note: this is for the AD case (cFunc takes (m, C)). For non-AD cFunc
    that takes only m, callers should still use extract_cfunc_table_per_period
    or skip lifting entirely.
    """
    M = len(m_grid)
    C_grid = np.linspace(C_lift_min, C_lift_max, C_lift_n, dtype=np.float64)
    table = np.zeros((n_combined, M, C_lift_n), dtype=np.float32)
    sol = agent.solution[0]
    m_arr = np.asarray(m_grid)
    for j in range(n_combined):
        for k, c_val in enumerate(C_grid):
            c_arr = np.full(M, float(c_val))
            try:
                table[j, :, k] = sol.cFunc[j](m_arr, c_arr)
            except TypeError:
                # Fallback for 1-arg cFunc (no AD)
                table[j, :, k] = sol.cFunc[j](m_arr)
    return table, C_grid.astype(np.float32)


def _mc_step_ad_2d(carry, scan_in, *,
                    m_grid, C_grid,
                    Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                    IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                    Splurge, LivPrb,
                    newborn_aNrm, newborn_pLvl,
                    cfunc_2d_table,
                    T_age_max=100):
    """Per-period step using bilinear-in-(m, C) cFunc lookup.

    cfunc_2d_table: (n_combined, M, C_grid)
    Cratio_obs[t] is per-period scalar in scan_in.
    """
    aNrm_prev, pLvl_prev, mrkv_micro_prev, t_age_prev = carry
    (rng_t, macro_t, AggDemandFac_t, Cratio_obs_t, skip_transition,
     tax_cut_t, check_dollars_t) = scan_in
    rng_death, rng_mrkv, rng_atom, rng_birth = random.split(rng_t, 4)
    N = aNrm_prev.shape[0]
    J = MrkvArray_macro.shape[1]

    death_draw = random.uniform(rng_death, (N,))
    alive_mask = ~((death_draw >= LivPrb) | (t_age_prev >= T_age_max))

    cum_prob = jnp.cumsum(MrkvArray_macro[macro_t][mrkv_micro_prev], axis=-1)
    mrkv_draw = random.uniform(rng_mrkv, (N,))
    mrkv_transitioned = jnp.sum(mrkv_draw[:, None] > cum_prob, axis=-1).astype(jnp.int32)
    mrkv_transitioned = jnp.clip(mrkv_transitioned, 0, J - 1)
    mrkv_micro_now = jnp.where(skip_transition.astype(bool), mrkv_micro_prev, mrkv_transitioned)

    pool_idx = random.randint(rng_birth, (N,), 0, newborn_aNrm.shape[0])
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

    pLvl_now_pre = pLvl_carry * G_eff * psi_eff
    xi_taxcut = jnp.where(is_employed, xi * tax_cut_t, xi)
    extra_xi = jnp.where(is_employed, check_dollars_t / pLvl_now_pre, 0.0)
    xi_total = xi_taxcut + extra_xi

    bNrm = R_now * aNrm_carry / (G_eff * psi_eff)
    mNrm = bNrm + xi_total * AggDemandFac_t

    # Bilinear lookup into (n_combined, M, C_grid) at (mNrm, Cratio_obs_t)
    M = m_grid.shape[0]
    Cn = C_grid.shape[0]
    # m-axis bracket
    i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
    w_m = (mNrm - m_grid[i_lo]) / (m_grid[i_lo + 1] - m_grid[i_lo])
    # C-axis bracket (uniform grid so we can compute directly; but searchsorted
    # is safer if grid is non-uniform)
    k_lo = jnp.clip(jnp.searchsorted(C_grid, Cratio_obs_t, side='right') - 1, 0, Cn - 2)
    w_C = (Cratio_obs_t - C_grid[k_lo]) / (C_grid[k_lo + 1] - C_grid[k_lo])

    c_00 = cfunc_2d_table[mrkv_combined, i_lo, k_lo]
    c_10 = cfunc_2d_table[mrkv_combined, i_lo + 1, k_lo]
    c_01 = cfunc_2d_table[mrkv_combined, i_lo, k_lo + 1]
    c_11 = cfunc_2d_table[mrkv_combined, i_lo + 1, k_lo + 1]
    cNrm = (
        (1 - w_m) * (1 - w_C) * c_00
        + w_m * (1 - w_C) * c_10
        + (1 - w_m) * w_C * c_01
        + w_m * w_C * c_11
    )

    pLvl_now = pLvl_now_pre
    cLvl_sp = (1.0 - Splurge) * cNrm * pLvl_now + Splurge * pLvl_now * xi_total * AggDemandFac_t
    aNrm_next = mNrm - cLvl_sp / pLvl_now

    AggInc_t = jnp.sum(pLvl_now * xi_total * AggDemandFac_t)
    AggCons_t = jnp.sum(cLvl_sp)

    new_carry = (aNrm_next, pLvl_now, mrkv_micro_now, t_age_next)
    return new_carry, (AggInc_t, AggCons_t, cLvl_sp)


@partial(jax.jit, static_argnames=('act_T', 'T_age_max'))
def _simulate_ad_core_2d(carry0, period_keys, EconomyMrkv_path, AggDemandFac_path,
                          Cratio_obs_path,
                          cfunc_2d_table, m_grid, C_grid,
                          skip_transition_path,
                          tax_cut_path, check_dollars_path,
                          Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                          IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                          Splurge, LivPrb,
                          newborn_aNrm, newborn_pLvl,
                          act_T, T_age_max=100):
    def step(carry, scan_in):
        return _mc_step_ad_2d(
            carry, scan_in,
            m_grid=m_grid, C_grid=C_grid,
            Rfree_macro=Rfree_macro, PermGroFac_macro=PermGroFac_macro,
            MrkvArray_macro=MrkvArray_macro,
            IncShk_psi_macro=IncShk_psi_macro,
            IncShk_xi_macro=IncShk_xi_macro,
            IncShk_pmv_macro=IncShk_pmv_macro,
            Splurge=Splurge, LivPrb=LivPrb,
            newborn_aNrm=newborn_aNrm, newborn_pLvl=newborn_pLvl,
            cfunc_2d_table=cfunc_2d_table,
            T_age_max=T_age_max,
        )
    scan_inputs = (period_keys, EconomyMrkv_path, AggDemandFac_path,
                   Cratio_obs_path, skip_transition_path,
                   tax_cut_path, check_dollars_path)
    _, outs = lax.scan(step, carry0, scan_inputs)
    return outs


# Speedup 1D: variant that drops the per-period cLvl_panel output.
# Saves T*N float writes per call; on the AD non-final iters we don't need
# the panel (only the aggregate AggCons/AggInc series). The final iter still
# needs the panel for welfare cells.
@partial(jax.jit, static_argnames=('act_T', 'T_age_max'))
def _simulate_ad_core_2d_no_panel(carry0, period_keys, EconomyMrkv_path,
                                    AggDemandFac_path, Cratio_obs_path,
                                    cfunc_2d_table, m_grid, C_grid,
                                    skip_transition_path,
                                    tax_cut_path, check_dollars_path,
                                    Rfree_macro, PermGroFac_macro,
                                    MrkvArray_macro,
                                    IncShk_psi_macro, IncShk_xi_macro,
                                    IncShk_pmv_macro,
                                    Splurge, LivPrb,
                                    newborn_aNrm, newborn_pLvl,
                                    act_T, T_age_max=100):
    def step(carry, scan_in):
        new_carry, (AggInc_t, AggCons_t, _cLvl_sp_unused) = _mc_step_ad_2d(
            carry, scan_in,
            m_grid=m_grid, C_grid=C_grid,
            Rfree_macro=Rfree_macro, PermGroFac_macro=PermGroFac_macro,
            MrkvArray_macro=MrkvArray_macro,
            IncShk_psi_macro=IncShk_psi_macro,
            IncShk_xi_macro=IncShk_xi_macro,
            IncShk_pmv_macro=IncShk_pmv_macro,
            Splurge=Splurge, LivPrb=LivPrb,
            newborn_aNrm=newborn_aNrm, newborn_pLvl=newborn_pLvl,
            cfunc_2d_table=cfunc_2d_table,
            T_age_max=T_age_max,
        )
        # Drop the cLvl_sp output — only return aggregates
        return new_carry, (AggInc_t, AggCons_t)
    scan_inputs = (period_keys, EconomyMrkv_path, AggDemandFac_path,
                   Cratio_obs_path, skip_transition_path,
                   tax_cut_path, check_dollars_path)
    _, outs = lax.scan(step, carry0, scan_inputs)
    return outs


def _gen_t_age0(seed_base, N, LivPrb, T_age_max):
    """Reproduce the per-seed t_age0 draw from simulate_jax_ad_2d."""
    rs = np.random.RandomState(seed_base + 7919)
    cum_p = (1 - LivPrb ** (np.arange(T_age_max + 1) + 1)) / max(
        1 - LivPrb ** (T_age_max + 1), 1e-12)
    return np.searchsorted(cum_p, rs.uniform(size=N)).astype(np.int32)


def simulate_jax_ad_2d(aNrm0, pLvl0, mrkv_micro0,
                        EconomyMrkv_path, AggDemandFac_path, Cratio_obs_path,
                        cfunc_2d_table, m_grid, C_grid,
                        Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                        IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                        Splurge, LivPrb,
                        newborn_aNrm, newborn_pLvl,
                        act_T, seed_base=0, T_age_max=100, t_age0=None,
                        tax_cut_path=None, check_dollars_path=None):
    """JAX MC AD with bilinear-in-(m, C) cFunc lift (Speedup 1A).

    cfunc_2d_table: (n_combined, M, C_grid)
    Cratio_obs_path: (T,) per-period Cratio agents observe
    C_grid: (C_grid,) uniform grid covering Cratio range
    """
    fp = jnp.asarray(aNrm0).dtype
    N = aNrm0.shape[0]
    if t_age0 is None:
        t_age0_arr = _gen_t_age0(seed_base, N, LivPrb, T_age_max)
    else:
        t_age0_arr = np.asarray(t_age0, dtype=np.int32)
    carry0 = (jnp.asarray(aNrm0, dtype=fp),
              jnp.asarray(pLvl0, dtype=fp),
              jnp.asarray(mrkv_micro0, dtype=jnp.int32),
              jnp.asarray(t_age0_arr, dtype=jnp.int32))
    period_keys = random.split(random.PRNGKey(seed_base), act_T)

    skip_transition = np.zeros(act_T, dtype=np.int32)
    skip_transition[0] = 1

    if tax_cut_path is None:
        tax_cut_path = np.ones(act_T, dtype=np.float32)
    if check_dollars_path is None:
        check_dollars_path = np.zeros((act_T, N), dtype=np.float32)

    outs = _simulate_ad_core_2d(
        carry0, period_keys,
        jnp.asarray(EconomyMrkv_path, dtype=jnp.int32),
        jnp.asarray(AggDemandFac_path, dtype=fp),
        jnp.asarray(Cratio_obs_path, dtype=fp),
        jnp.asarray(cfunc_2d_table, dtype=fp),
        jnp.asarray(m_grid, dtype=fp),
        jnp.asarray(C_grid, dtype=fp),
        jnp.asarray(skip_transition, dtype=jnp.int32),
        jnp.asarray(tax_cut_path, dtype=fp),
        jnp.asarray(check_dollars_path, dtype=fp),
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


# ============================================================================
# Speedup 1B: vmap across seeds
# ============================================================================

def simulate_jax_ad_2d_vmap_seeds(seed_bases,
                                    aNrm0, pLvl0, mrkv_micro0,
                                    EconomyMrkv_path, AggDemandFac_path,
                                    Cratio_obs_path,
                                    cfunc_2d_table, m_grid, C_grid,
                                    Rfree_macro, PermGroFac_macro,
                                    MrkvArray_macro,
                                    IncShk_psi_macro, IncShk_xi_macro,
                                    IncShk_pmv_macro,
                                    Splurge, LivPrb,
                                    newborn_aNrm, newborn_pLvl,
                                    act_T, T_age_max=100,
                                    tax_cut_path=None,
                                    check_dollars_path=None,
                                    materialize_panel=True):
    """Run multiple seeds in ONE JIT call via vmap.

    Returns:
        AggInc:    (S, T)
        AggCons:   (S, T)
        cLvl_panel: (S, T, N)

    Bit-equivalent to looping simulate_jax_ad_2d over seeds (validated to
    floating-point noise; differences come only from JIT compilation order).
    """
    fp = jnp.asarray(aNrm0).dtype
    N = aNrm0.shape[0]
    S = len(seed_bases)

    # Per-seed t_age0 (NumPy side, then stacked)
    t_age0_stack = np.stack(
        [_gen_t_age0(s, N, LivPrb, T_age_max) for s in seed_bases], axis=0
    )  # (S, N)
    # Per-seed period_keys
    period_keys_stack = jnp.stack(
        [random.split(random.PRNGKey(int(s)), act_T) for s in seed_bases], axis=0
    )  # (S, T, 2)

    aNrm0_j = jnp.asarray(aNrm0, dtype=fp)
    pLvl0_j = jnp.asarray(pLvl0, dtype=fp)
    mrkv0_j = jnp.asarray(mrkv_micro0, dtype=jnp.int32)
    t_age0_j = jnp.asarray(t_age0_stack, dtype=jnp.int32)  # (S, N)

    # Carry varies in t_age axis only (other carry components shared across seeds).
    # Broadcast/stack to (S, ...).
    aNrm0_s = jnp.broadcast_to(aNrm0_j, (S,) + aNrm0_j.shape)
    pLvl0_s = jnp.broadcast_to(pLvl0_j, (S,) + pLvl0_j.shape)
    mrkv0_s = jnp.broadcast_to(mrkv0_j, (S,) + mrkv0_j.shape)
    # t_age0_j is already (S, N)

    skip_transition = np.zeros(act_T, dtype=np.int32)
    skip_transition[0] = 1

    if tax_cut_path is None:
        tax_cut_path = np.ones(act_T, dtype=np.float32)
    if check_dollars_path is None:
        check_dollars_path = np.zeros((act_T, N), dtype=np.float32)

    # All non-seed inputs are shared. Bind them in a closure for the vmap.
    cfunc_j = jnp.asarray(cfunc_2d_table, dtype=fp)
    m_grid_j = jnp.asarray(m_grid, dtype=fp)
    C_grid_j = jnp.asarray(C_grid, dtype=fp)
    EM_j = jnp.asarray(EconomyMrkv_path, dtype=jnp.int32)
    ADF_j = jnp.asarray(AggDemandFac_path, dtype=fp)
    Cr_j = jnp.asarray(Cratio_obs_path, dtype=fp)
    skip_j = jnp.asarray(skip_transition, dtype=jnp.int32)
    tc_j = jnp.asarray(tax_cut_path, dtype=fp)
    cd_j = jnp.asarray(check_dollars_path, dtype=fp)
    Rfree_j = jnp.asarray(Rfree_macro, dtype=fp)
    PGF_j = jnp.asarray(PermGroFac_macro, dtype=fp)
    Mrkv_j = jnp.asarray(MrkvArray_macro, dtype=fp)
    PsiM_j = jnp.asarray(IncShk_psi_macro, dtype=fp)
    XiM_j = jnp.asarray(IncShk_xi_macro, dtype=fp)
    PmvM_j = jnp.asarray(IncShk_pmv_macro, dtype=fp)
    nbA_j = jnp.asarray(newborn_aNrm, dtype=fp)
    nbP_j = jnp.asarray(newborn_pLvl, dtype=fp)

    if materialize_panel:
        def per_seed_run(aNrm0_one, pLvl0_one, mrkv0_one, t_age0_one, pk_one):
            carry0 = (aNrm0_one, pLvl0_one, mrkv0_one, t_age0_one)
            return _simulate_ad_core_2d(
                carry0, pk_one, EM_j, ADF_j, Cr_j, cfunc_j, m_grid_j, C_grid_j,
                skip_j, tc_j, cd_j,
                Rfree_j, PGF_j, Mrkv_j, PsiM_j, XiM_j, PmvM_j,
                Splurge, LivPrb, nbA_j, nbP_j,
                act_T, T_age_max=T_age_max,
            )

        AggInc, AggCons, cLvl_panel = jax.vmap(per_seed_run)(
            aNrm0_s, pLvl0_s, mrkv0_s, t_age0_j, period_keys_stack
        )
        AggInc.block_until_ready()
        return AggInc, AggCons, cLvl_panel
    else:
        # Speedup 1D: skip the (S, T, N) panel materialization on non-final iters
        def per_seed_run_no_panel(aNrm0_one, pLvl0_one, mrkv0_one, t_age0_one, pk_one):
            carry0 = (aNrm0_one, pLvl0_one, mrkv0_one, t_age0_one)
            return _simulate_ad_core_2d_no_panel(
                carry0, pk_one, EM_j, ADF_j, Cr_j, cfunc_j, m_grid_j, C_grid_j,
                skip_j, tc_j, cd_j,
                Rfree_j, PGF_j, Mrkv_j, PsiM_j, XiM_j, PmvM_j,
                Splurge, LivPrb, nbA_j, nbP_j,
                act_T, T_age_max=T_age_max,
            )

        AggInc, AggCons = jax.vmap(per_seed_run_no_panel)(
            aNrm0_s, pLvl0_s, mrkv0_s, t_age0_j, period_keys_stack
        )
        AggInc.block_until_ready()
        return AggInc, AggCons, None


# ============================================================================
# Speedup 2A: vmap across cohorts (and seeds), pad to max_N + active_mask
# ============================================================================

def _mc_step_ad_2d_masked(carry, scan_in, *,
                            m_grid, C_grid,
                            Rfree_macro, PermGroFac_macro, MrkvArray_macro,
                            IncShk_psi_macro, IncShk_xi_macro, IncShk_pmv_macro,
                            Splurge, LivPrb,
                            newborn_aNrm, newborn_pLvl,
                            cfunc_2d_table,
                            active_mask,
                            T_age_max=100):
    """Per-period step that respects an active_mask: padding agents contribute
    zero to AggInc/AggCons sums.

    Mirrors _mc_step_ad_2d exactly; only difference is the final sum masks
    contributions from inactive (padding) agents.
    """
    aNrm_prev, pLvl_prev, mrkv_micro_prev, t_age_prev = carry
    (rng_t, macro_t, AggDemandFac_t, Cratio_obs_t, skip_transition,
     tax_cut_t, check_dollars_t) = scan_in
    rng_death, rng_mrkv, rng_atom, rng_birth = random.split(rng_t, 4)
    N = aNrm_prev.shape[0]
    J = MrkvArray_macro.shape[1]

    death_draw = random.uniform(rng_death, (N,))
    alive_mask = ~((death_draw >= LivPrb) | (t_age_prev >= T_age_max))

    cum_prob = jnp.cumsum(MrkvArray_macro[macro_t][mrkv_micro_prev], axis=-1)
    mrkv_draw = random.uniform(rng_mrkv, (N,))
    mrkv_transitioned = jnp.sum(mrkv_draw[:, None] > cum_prob, axis=-1).astype(jnp.int32)
    mrkv_transitioned = jnp.clip(mrkv_transitioned, 0, J - 1)
    mrkv_micro_now = jnp.where(skip_transition.astype(bool), mrkv_micro_prev, mrkv_transitioned)

    pool_idx = random.randint(rng_birth, (N,), 0, newborn_aNrm.shape[0])
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

    pLvl_now_pre = pLvl_carry * G_eff * psi_eff
    xi_taxcut = jnp.where(is_employed, xi * tax_cut_t, xi)
    extra_xi = jnp.where(is_employed, check_dollars_t / pLvl_now_pre, 0.0)
    xi_total = xi_taxcut + extra_xi

    bNrm = R_now * aNrm_carry / (G_eff * psi_eff)
    mNrm = bNrm + xi_total * AggDemandFac_t

    M = m_grid.shape[0]
    Cn = C_grid.shape[0]
    i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
    w_m = (mNrm - m_grid[i_lo]) / (m_grid[i_lo + 1] - m_grid[i_lo])
    k_lo = jnp.clip(jnp.searchsorted(C_grid, Cratio_obs_t, side='right') - 1, 0, Cn - 2)
    w_C = (Cratio_obs_t - C_grid[k_lo]) / (C_grid[k_lo + 1] - C_grid[k_lo])

    c_00 = cfunc_2d_table[mrkv_combined, i_lo, k_lo]
    c_10 = cfunc_2d_table[mrkv_combined, i_lo + 1, k_lo]
    c_01 = cfunc_2d_table[mrkv_combined, i_lo, k_lo + 1]
    c_11 = cfunc_2d_table[mrkv_combined, i_lo + 1, k_lo + 1]
    cNrm = (
        (1 - w_m) * (1 - w_C) * c_00
        + w_m * (1 - w_C) * c_10
        + (1 - w_m) * w_C * c_01
        + w_m * w_C * c_11
    )

    pLvl_now = pLvl_now_pre
    cLvl_sp = (1.0 - Splurge) * cNrm * pLvl_now + Splurge * pLvl_now * xi_total * AggDemandFac_t
    aNrm_next = mNrm - cLvl_sp / pLvl_now

    # Masked aggregates: padding agents (active_mask=False) contribute 0
    AggInc_t = jnp.sum(jnp.where(active_mask, pLvl_now * xi_total * AggDemandFac_t, 0.0))
    AggCons_t = jnp.sum(jnp.where(active_mask, cLvl_sp, 0.0))

    new_carry = (aNrm_next, pLvl_now, mrkv_micro_now, t_age_next)
    return new_carry, (AggInc_t, AggCons_t, cLvl_sp)


@partial(jax.jit, static_argnames=('act_T', 'T_age_max'))
def _simulate_ad_core_2d_masked(carry0, period_keys, EconomyMrkv_path,
                                  AggDemandFac_path, Cratio_obs_path,
                                  cfunc_2d_table, m_grid, C_grid,
                                  skip_transition_path,
                                  tax_cut_path, check_dollars_path,
                                  Rfree_macro, PermGroFac_macro,
                                  MrkvArray_macro,
                                  IncShk_psi_macro, IncShk_xi_macro,
                                  IncShk_pmv_macro,
                                  Splurge, LivPrb,
                                  newborn_aNrm, newborn_pLvl,
                                  active_mask,
                                  act_T, T_age_max=100):
    def step(carry, scan_in):
        return _mc_step_ad_2d_masked(
            carry, scan_in,
            m_grid=m_grid, C_grid=C_grid,
            Rfree_macro=Rfree_macro, PermGroFac_macro=PermGroFac_macro,
            MrkvArray_macro=MrkvArray_macro,
            IncShk_psi_macro=IncShk_psi_macro,
            IncShk_xi_macro=IncShk_xi_macro,
            IncShk_pmv_macro=IncShk_pmv_macro,
            Splurge=Splurge, LivPrb=LivPrb,
            newborn_aNrm=newborn_aNrm, newborn_pLvl=newborn_pLvl,
            cfunc_2d_table=cfunc_2d_table,
            active_mask=active_mask,
            T_age_max=T_age_max,
        )
    scan_inputs = (period_keys, EconomyMrkv_path, AggDemandFac_path,
                   Cratio_obs_path, skip_transition_path,
                   tax_cut_path, check_dollars_path)
    _, outs = lax.scan(step, carry0, scan_inputs)
    return outs


@partial(jax.jit, static_argnames=('act_T', 'T_age_max'))
def _simulate_ad_core_2d_masked_no_panel(carry0, period_keys, EconomyMrkv_path,
                                           AggDemandFac_path, Cratio_obs_path,
                                           cfunc_2d_table, m_grid, C_grid,
                                           skip_transition_path,
                                           tax_cut_path, check_dollars_path,
                                           Rfree_macro, PermGroFac_macro,
                                           MrkvArray_macro,
                                           IncShk_psi_macro, IncShk_xi_macro,
                                           IncShk_pmv_macro,
                                           Splurge, LivPrb,
                                           newborn_aNrm, newborn_pLvl,
                                           active_mask,
                                           act_T, T_age_max=100):
    def step(carry, scan_in):
        new_carry, (AggInc_t, AggCons_t, _cLvl_unused) = _mc_step_ad_2d_masked(
            carry, scan_in,
            m_grid=m_grid, C_grid=C_grid,
            Rfree_macro=Rfree_macro, PermGroFac_macro=PermGroFac_macro,
            MrkvArray_macro=MrkvArray_macro,
            IncShk_psi_macro=IncShk_psi_macro,
            IncShk_xi_macro=IncShk_xi_macro,
            IncShk_pmv_macro=IncShk_pmv_macro,
            Splurge=Splurge, LivPrb=LivPrb,
            newborn_aNrm=newborn_aNrm, newborn_pLvl=newborn_pLvl,
            cfunc_2d_table=cfunc_2d_table,
            active_mask=active_mask,
            T_age_max=T_age_max,
        )
        return new_carry, (AggInc_t, AggCons_t)
    scan_inputs = (period_keys, EconomyMrkv_path, AggDemandFac_path,
                   Cratio_obs_path, skip_transition_path,
                   tax_cut_path, check_dollars_path)
    _, outs = lax.scan(step, carry0, scan_inputs)
    return outs


def simulate_jax_ad_2d_vmap_cohorts_seeds(
        # Per-cohort stacked init panels (n_cohorts, max_N)
        aNrm0_stk, pLvl0_stk, mrkv_micro0_stk, active_mask_stk,
        # Per-cohort seed bases (n_cohorts, n_seeds) — vmap over both axes
        seed_bases_stk,
        # Shared per-iter inputs (T,)
        EconomyMrkv_path, AggDemandFac_path, Cratio_obs_path,
        skip_transition_path,
        # Per-cohort policy paths (n_cohorts, T) and (n_cohorts, T, max_N)
        tax_cut_path_stk, check_dollars_path_stk,
        # Per-cohort cfunc table (n_cohorts, n_combined, M, C_grid)
        cfunc_2d_table_stk, m_grid, C_grid,
        # Per-cohort macro params (n_cohorts, n_combined) and similar
        Rfree_macro_stk, PermGroFac_macro_stk, MrkvArray_macro_stk,
        IncShk_psi_macro_stk, IncShk_xi_macro_stk, IncShk_pmv_macro_stk,
        # Per-cohort scalars (n_cohorts,)
        Splurge_stk, LivPrb_stk,
        # Per-cohort newborn pools (n_cohorts, pool_N)
        newborn_aNrm_stk, newborn_pLvl_stk,
        # Static
        act_T, T_age_max=100,
        materialize_panel=True):
    """vmap across cohorts (outer) and seeds (inner) — single JIT call.

    Inputs: most arrays are stacked along a leading cohort axis. Within a
    cohort, agents are padded to max_N, with active_mask marking real agents.

    Returns:
        AggInc:  (n_cohorts, n_seeds, T)
        AggCons: (n_cohorts, n_seeds, T)
        cLvl_panel: (n_cohorts, n_seeds, T, max_N) if materialize_panel else None
    """
    fp = aNrm0_stk.dtype
    n_cohorts, max_N = aNrm0_stk.shape
    n_seeds = seed_bases_stk.shape[1]

    # Build per-cohort per-seed t_age0 and period_keys on the NumPy side
    # (deterministic given seed_base). t_age0 generation depends on LivPrb
    # per cohort.
    t_age0_stack = np.zeros((n_cohorts, n_seeds, max_N), dtype=np.int32)
    period_keys_stack = np.zeros((n_cohorts, n_seeds, act_T, 2), dtype=np.uint32)
    LivPrb_np = np.asarray(LivPrb_stk)
    for c in range(n_cohorts):
        for s_idx in range(n_seeds):
            sb = int(seed_bases_stk[c, s_idx])
            t_age0_stack[c, s_idx] = _gen_t_age0(
                sb, max_N, float(LivPrb_np[c]), T_age_max)
            pk = jax.random.split(jax.random.PRNGKey(sb), act_T)
            period_keys_stack[c, s_idx] = np.asarray(pk)

    t_age0_j = jnp.asarray(t_age0_stack, dtype=jnp.int32)
    period_keys_j = jnp.asarray(period_keys_stack)

    aNrm0_j = jnp.asarray(aNrm0_stk, dtype=fp)
    pLvl0_j = jnp.asarray(pLvl0_stk, dtype=fp)
    mrkv0_j = jnp.asarray(mrkv_micro0_stk, dtype=jnp.int32)
    active_mask_j = jnp.asarray(active_mask_stk, dtype=jnp.bool_)
    cfunc_j = jnp.asarray(cfunc_2d_table_stk, dtype=fp)
    m_grid_j = jnp.asarray(m_grid, dtype=fp)
    C_grid_j = jnp.asarray(C_grid, dtype=fp)
    EM_j = jnp.asarray(EconomyMrkv_path, dtype=jnp.int32)
    ADF_j = jnp.asarray(AggDemandFac_path, dtype=fp)
    Cr_j = jnp.asarray(Cratio_obs_path, dtype=fp)
    skip_j = jnp.asarray(skip_transition_path, dtype=jnp.int32)
    tc_j = jnp.asarray(tax_cut_path_stk, dtype=fp)
    cd_j = jnp.asarray(check_dollars_path_stk, dtype=fp)
    Rfree_j = jnp.asarray(Rfree_macro_stk, dtype=fp)
    PGF_j = jnp.asarray(PermGroFac_macro_stk, dtype=fp)
    Mrkv_j = jnp.asarray(MrkvArray_macro_stk, dtype=fp)
    PsiM_j = jnp.asarray(IncShk_psi_macro_stk, dtype=fp)
    XiM_j = jnp.asarray(IncShk_xi_macro_stk, dtype=fp)
    PmvM_j = jnp.asarray(IncShk_pmv_macro_stk, dtype=fp)
    nbA_j = jnp.asarray(newborn_aNrm_stk, dtype=fp)
    nbP_j = jnp.asarray(newborn_pLvl_stk, dtype=fp)
    Splurge_j = jnp.asarray(Splurge_stk, dtype=fp)
    LivPrb_j = jnp.asarray(LivPrb_stk, dtype=fp)

    if materialize_panel:
        core_fn = _simulate_ad_core_2d_masked
    else:
        core_fn = _simulate_ad_core_2d_masked_no_panel

    def per_cohort_per_seed(aNrm0_one, pLvl0_one, mrkv0_one, t_age0_one,
                              pk_one, active_mask_one, tc_one, cd_one,
                              cfunc_one, Rfree_one, PGF_one, Mrkv_one,
                              Psi_one, Xi_one, Pmv_one,
                              Splurge_scalar, LivPrb_scalar,
                              nbA_one, nbP_one):
        carry0 = (aNrm0_one, pLvl0_one, mrkv0_one, t_age0_one)
        return core_fn(
            carry0, pk_one, EM_j, ADF_j, Cr_j, cfunc_one, m_grid_j, C_grid_j,
            skip_j, tc_one, cd_one,
            Rfree_one, PGF_one, Mrkv_one, Psi_one, Xi_one, Pmv_one,
            Splurge_scalar, LivPrb_scalar, nbA_one, nbP_one,
            active_mask_one,
            act_T, T_age_max=T_age_max,
        )

    # Inner vmap: across seeds (broadcast cohort-specific args)
    def per_cohort_all_seeds(aNrm0_c, pLvl0_c, mrkv0_c, t_age0_c,
                              pk_c, active_mask_c, tc_c, cd_c,
                              cfunc_c, Rfree_c, PGF_c, Mrkv_c,
                              Psi_c, Xi_c, Pmv_c,
                              Splurge_c, LivPrb_c, nbA_c, nbP_c):
        # Per-cohort: aNrm0_c, pLvl0_c, mrkv0_c, active_mask_c, cfunc_c, etc.
        # are scalar in cohort axis, but vary by seed only in t_age0 and pk.
        # Broadcast cohort-shared args to (n_seeds, ...)
        def per_seed_in_cohort(t_age0_s, pk_s):
            return per_cohort_per_seed(
                aNrm0_c, pLvl0_c, mrkv0_c, t_age0_s,
                pk_s, active_mask_c, tc_c, cd_c,
                cfunc_c, Rfree_c, PGF_c, Mrkv_c,
                Psi_c, Xi_c, Pmv_c,
                Splurge_c, LivPrb_c, nbA_c, nbP_c)
        return jax.vmap(per_seed_in_cohort)(t_age0_c, pk_c)

    outs = jax.vmap(per_cohort_all_seeds)(
        aNrm0_j, pLvl0_j, mrkv0_j, t_age0_j,
        period_keys_j, active_mask_j, tc_j, cd_j,
        cfunc_j, Rfree_j, PGF_j, Mrkv_j, PsiM_j, XiM_j, PmvM_j,
        Splurge_j, LivPrb_j, nbA_j, nbP_j
    )
    if materialize_panel:
        AggInc, AggCons, cLvl_panel = outs
        AggInc.block_until_ready()
        return AggInc, AggCons, cLvl_panel
    else:
        AggInc, AggCons = outs
        AggInc.block_until_ready()
        return AggInc, AggCons, None


def build_predicted_Cratio_path(MacroCFunc_intercept, MacroCFunc_slope,
                                 EconomyMrkv_path, num_base_MrkvStates,
                                 Cratio_init=1.0):
    """Iterate belief CFunc rule along the macro path to predict per-period Cratio
    AGENTS observe at each period t.

    CratioNext = intercept[macro_t, macro_next] + slope[macro_t, macro_next] * (Cratio_now - 1.0)
    Returns: (T,) array of Cratio agents observe at each t.
    """
    T = len(EconomyMrkv_path)
    macros = [m // num_base_MrkvStates for m in EconomyMrkv_path]  # macro indices
    Cratio_obs = np.zeros(T, dtype=np.float64)
    Cratio_obs[0] = Cratio_init
    Cratio_now = Cratio_init
    for t in range(T - 1):
        i = macros[t]; j = macros[t + 1]
        Cratio_next = MacroCFunc_intercept[i, j] + MacroCFunc_slope[i, j] * (Cratio_now - 1.0)
        Cratio_obs[t + 1] = Cratio_next
        Cratio_now = Cratio_next
    return Cratio_obs


def compute_AggDemandFac_path(Cratio_obs_path, EconomyMrkv_path, num_base_MrkvStates,
                              ADelasticity):
    """ADF_t = Cratio_obs[t] ** (RecState_t * ADelasticity), RecState_t = macro_t % 2."""
    macros = np.array([m // num_base_MrkvStates for m in EconomyMrkv_path])
    RecState = (macros % 2).astype(np.float64)
    return (np.asarray(Cratio_obs_path) ** (RecState * ADelasticity)).astype(np.float32)
