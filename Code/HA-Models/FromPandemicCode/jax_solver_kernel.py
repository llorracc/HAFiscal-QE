"""JAX EGM solver kernel for HAFiscal's AggFiscalType.

Replaces solve_agg_cons_markov_alt (AggFiscalModel.py:1704-1887) with a pure-JAX
equivalent. Operates on tabulated inputs (vPfuncNext + mNrmMinNext tables
extracted from HARK solution_next at fixed grids).

This is the P2+P3 deliverable: kernel covering full Ccount + multi-Markov-state.
P4 will validate at HAFiscal scale.

Reference math (matches AggFiscalModel.py:1704-1887):

  Loop 1 (per next-state j):
    EndOfPrdvP[j, c, a] = DiscFac * Σ_s pmv[j,s] * R[j] * psi[j,s]^(-rho)
                          * vPfuncNext[j](mNrmNext, Cnext)
    where mNrmNext = R[j]*aNrm/(G[j]*psi[j,s]) + ADF*xi[j,s]
          ADF = Cnext^(RecState[j] * elasticity)
          aNrm = aNrmMin[j,c] + aXtra[a]

  Loop 2 (per current state i):
    EndOfPrdvP_total[i, c, a] = LivPrb[i] * Σ_j MrkvArray[i,j] *
                                EndOfPrdvP_cond[j](aNrm_now, Cnext_ij)
    where Cnext_ij = CFunc[i,j] applied to Cgrid (linear: intercept + slope*(C-1))
          aNrm_now = aNrmMin_current[i,c] + aXtra[a]
          aNrmMin_current[i,c] = max_j (MrkvArray[i,j]>0) BoroCnstNat_cond[j](Cnext_ij)

    EGM: cNrm[i, c, a] = EndOfPrdvP_total^(-1/rho)
         mNrm[i, c, a] = aNrm_now[c, a] + cNrm[i, c, a]
"""
from __future__ import annotations
import jax
import jax.numpy as jnp
from functools import partial
from HARK.interpolation_jax import (linear_interp_1d, bilinear_interp,
                              linear_interp_on_interp_1d_general)


def _evaluate_vPfuncNext_table(table, m_eval, C_eval, m_query, C_query):
    """Bilinear interp into a (m_eval, C_eval) → vP table.

    table: shape (M_eval, C_eval) — vPfunc values at (m_eval[i], C_eval[j])
    m_query, C_query: broadcastable query points
    Returns vP at query points.
    """
    return bilinear_interp(table, m_eval, C_eval, m_query, C_query)


def _ad_factor(Cnext, RecState_int, ADelasticity):
    """ADF = Cnext ** (RecState * elasticity). RecState_int is 0 or 1."""
    return Cnext ** (RecState_int * ADelasticity)


def _loop1_one_next_state(
    vPfuncNext_table_j,      # (M_eval, C_eval) — tabulated vPfunc[j]
    mNrmMinNext_table_j,     # (C_eval,) — tabulated mNrmMin[j] as func of C
    mNrmMinNext_is_callable_j, # bool: True if mNrmMin[j] varies with C; False if scalar
    mNrmMinNext_scalar_j,    # scalar fallback if not callable
    m_eval, C_eval,          # eval grids for vPfunc lookup
    IncShk_pmv_j,            # (ShkCount,)
    IncShk_perm_j,           # (ShkCount,)
    IncShk_tran_j,           # (ShkCount,)
    Rfree_j, PermGroFac_j,   # scalars
    DiscFac, CRRA,           # scalars
    aXtraGrid,               # (aCount,)
    Cgrid,                   # (Ccount,)
    RecState_j_int,          # int (0 or 1)
    ADelasticity,
):
    """Compute EndOfPrdvP[c, a] for one next-state j. Returns (EndOfPrdvP, BoroCnstNat_vec_j).

    EndOfPrdvP shape: (Ccount, aCount)
    BoroCnstNat_vec_j shape: (Ccount,)
    """
    Ccount = Cgrid.shape[0]
    aCount = aXtraGrid.shape[0]
    ShkCount = IncShk_pmv_j.shape[0]

    # Tile arrays to (Ccount, aCount, ShkCount)
    aXtra_t = jnp.broadcast_to(aXtraGrid[None, :, None], (Ccount, aCount, ShkCount))
    pmv_t = jnp.broadcast_to(IncShk_pmv_j[None, None, :], (Ccount, aCount, ShkCount))
    perm_t = jnp.broadcast_to(IncShk_perm_j[None, None, :], (Ccount, aCount, ShkCount))
    tran_noAD_t = jnp.broadcast_to(IncShk_tran_j[None, None, :], (Ccount, aCount, ShkCount))
    Cnext_t = jnp.broadcast_to(Cgrid[:, None, None], (Ccount, aCount, ShkCount))

    # AD factor on tran shocks
    ADF = _ad_factor(Cnext_t, RecState_j_int, ADelasticity)
    tran_t = ADF * tran_noAD_t

    # Borrowing constraint candidate at each (c, s): pick max over s within each c
    # Tile reduces to (Ccount, ShkCount) here (no aXtra needed since aXtra=0 for boundary)
    Cnext_cs = jnp.broadcast_to(Cgrid[:, None], (Ccount, ShkCount))
    perm_cs = jnp.broadcast_to(IncShk_perm_j[None, :], (Ccount, ShkCount))
    ADF_cs = _ad_factor(Cnext_cs, RecState_j_int, ADelasticity)
    tran_cs = ADF_cs * jnp.broadcast_to(IncShk_tran_j[None, :], (Ccount, ShkCount))

    mNrmMinNext_at_Cnext_cs = jnp.where(
        mNrmMinNext_is_callable_j,
        # Tabulated mNrmMinNext_table_j is shape (C_eval,). Evaluate via 1-D interp at Cnext.
        jax.vmap(lambda C: linear_interp_1d(C_eval, mNrmMinNext_table_j, C, lower_extrap=True))(
            Cnext_cs.flatten()).reshape(Cnext_cs.shape),
        # Scalar fallback: mNrmMinNext * Cnext
        mNrmMinNext_scalar_j * Cnext_cs,
    )

    aNrmMin_cand_cs = (PermGroFac_j * perm_cs / Rfree_j
                       * (mNrmMinNext_at_Cnext_cs - tran_cs))
    aNrmMin_vec = jnp.max(aNrmMin_cand_cs, axis=1)  # (Ccount,)

    # Tile aNrmMin to (Ccount, aCount, ShkCount)
    aNrmMin_t = jnp.broadcast_to(aNrmMin_vec[:, None, None], (Ccount, aCount, ShkCount))
    aNrmNow_t = aNrmMin_t + aXtra_t

    # Next-period market resources
    mNrmNext_t = Rfree_j * aNrmNow_t / (PermGroFac_j * perm_t) + tran_t

    # Next-period marginal value via tabulated vPfunc lookup (bilinear interp on (m_eval, C_eval))
    # BUG-047: include PermGroFac_j^(-CRRA) in the marginal-value factor. The standard
    # Carroll / HARK form is (PermGroFac*PermShk)^(-CRRA), consistent with the mNrmNext
    # transition above which divides by PermGroFac_j*perm_t. This JAX kernel previously
    # omitted PermGroFac^(-CRRA) (the same bug fixed in AggFiscalModel.py:1813) — leaving
    # the GPU solver in the legacy regime, ~5% off the now-default fixed HARK solver.
    vPnext_t = (Rfree_j * PermGroFac_j ** (-CRRA) * perm_t ** (-CRRA)
                * _evaluate_vPfuncNext_table(
                    vPfuncNext_table_j, m_eval, C_eval,
                    mNrmNext_t.flatten(), Cnext_t.flatten()
                ).reshape(mNrmNext_t.shape))

    # End-of-period marginal value
    EndOfPrdvP = DiscFac * jnp.sum(vPnext_t * pmv_t, axis=2)  # (Ccount, aCount)

    return EndOfPrdvP, aNrmMin_vec


def _build_BoroCnst_table(BoroCnstNat_vec_per_j, Cgrid):
    """Pack per-j BoroCnstNat as a callable via 1-D linear interp on Cgrid.

    Returns (StateCount, Ccount) → (StateCount, Cquery) function.
    """
    # Just return the array; evaluation handled per-call with linear_interp_1d.
    return BoroCnstNat_vec_per_j  # shape (StateCount, Ccount)


def _loop2_one_current_state(
    i,                              # int — current state
    EndOfPrdvP_cond,                # (StateCount, Ccount, aCount)
    BoroCnstNat_per_j,              # (StateCount, Ccount)
    EndOfPrdvP_aGrids,              # (StateCount, Ccount, aCount+1) — aXtra prepended with 0
    EndOfPrdvP_nvrs,                # (StateCount, Ccount, aCount+1) — nvrs(EndOfPrdvP) prepended with 0
    MrkvArray,                      # (StateCount, StateCount)
    LivPrb_i,                       # scalar
    CRRA,
    CFunc_slope, CFunc_intercept,   # (StateCount, StateCount)
    Cgrid, aXtraGrid,
):
    """For current state i: compute cNrm and mNrm tables (Ccount, aCount).

    Returns (cNrm, mNrm, BoroCnstNat_vec_i) where:
      cNrm shape (Ccount, aCount)
      mNrm shape (Ccount, aCount)
      BoroCnstNat_vec_i shape (Ccount,) — the natural constraint for current state i
    """
    StateCount = MrkvArray.shape[0]
    Ccount = Cgrid.shape[0]
    aCount = aXtraGrid.shape[0]

    # Cnext_ij[j, c] = CFunc[i,j](Cgrid[c]) = intercept[i,j] + slope[i,j]*(Cgrid[c] - 1)
    Cnext_ij = (CFunc_intercept[i][:, None]
                + CFunc_slope[i][:, None] * (Cgrid[None, :] - 1.0))  # (StateCount, Ccount)

    # BoroCnstNat_at_Cnext[j, c] = BoroCnstNat_cond[j](Cnext_ij[j, c])
    def per_j_BoroCnstNat(j):
        return jax.vmap(
            lambda C: linear_interp_1d(Cgrid, BoroCnstNat_per_j[j], C, lower_extrap=True)
        )(Cnext_ij[j])  # (Ccount,)

    BoroCnstNat_at_Cnext = jax.vmap(per_j_BoroCnstNat)(jnp.arange(StateCount))
    # shape (StateCount, Ccount)

    # Mask infeasible transitions (MrkvArray[i,j] == 0)
    mask = (MrkvArray[i] > 0)[:, None]  # (StateCount, 1)
    BoroCnstNat_masked = jnp.where(mask, BoroCnstNat_at_Cnext, -jnp.inf)
    aNrmMin_vec_i = jnp.max(BoroCnstNat_masked, axis=0)  # (Ccount,)

    aNrmMin_t = jnp.broadcast_to(aNrmMin_vec_i[:, None], (Ccount, aCount))
    aNrmNow_t = aNrmMin_t + aXtraGrid[None, :]  # (Ccount, aCount)

    # For each j, evaluate EndOfPrdvP_cond[j] at (aNrmNow_t, Cnext_ij[j])
    # HARK's VariableLowerBoundFunc2D shifts query: inner_fn(x - lb(y), y).
    # So we must compute (aNrmNow - BoroCnstNat_cond[j](Cnext)) before the bilinear lookup.
    def per_j_EndOfPrdvP(j):
        Cnext_jc_a = jnp.broadcast_to(Cnext_ij[j][:, None], (Ccount, aCount))

        # Compute BoroCnstNat_cond[j] at each Cnext_ij[j, c] (varies by c, broadcast over a)
        BoroCnstNat_cond_j_at_Cnext = jax.vmap(
            lambda C: linear_interp_1d(Cgrid, BoroCnstNat_per_j[j], C, lower_extrap=True)
        )(Cnext_ij[j])  # (Ccount,)
        BoroCnstNat_shift = jnp.broadcast_to(
            BoroCnstNat_cond_j_at_Cnext[:, None], (Ccount, aCount))

        # Shifted query points
        aNrm_query_shifted = aNrmNow_t - BoroCnstNat_shift  # (Ccount, aCount)

        nvrs_value = linear_interp_on_interp_1d_general(
            EndOfPrdvP_aGrids[j],          # (Ccount, aCount+1)
            Cgrid,                          # (Ccount,)
            EndOfPrdvP_nvrs[j],             # (Ccount, aCount+1)
            aNrm_query_shifted.flatten(),
            Cnext_jc_a.flatten(),
        ).reshape((Ccount, aCount))
        # Convert nvrs → vP: vP = nvrs ^ (-CRRA), handle nvrs=0 → vP=inf safely
        nvrs_safe = jnp.maximum(nvrs_value, 1e-12)
        vP = nvrs_safe ** (-CRRA)
        return vP

    vP_per_j = jax.vmap(per_j_EndOfPrdvP)(jnp.arange(StateCount))
    # shape (StateCount, Ccount, aCount)

    # Weight by MrkvArray and sum
    weighted = MrkvArray[i][:, None, None] * vP_per_j  # (StateCount, Ccount, aCount)
    EndOfPrdvP_total = LivPrb_i * jnp.sum(weighted, axis=0)  # (Ccount, aCount)

    # EGM step
    cNrm = EndOfPrdvP_total ** (-1.0 / CRRA)
    mNrm = aNrmNow_t + cNrm

    return cNrm, mNrm, aNrmMin_vec_i


def solve_one_period_jax(
    # vPfuncNext as tabulated bilinear on (m_eval, C_eval), shape (StateCount, M_eval, C_eval)
    vPfuncNext_table,
    m_eval, C_eval,
    # mNrmMinNext: (StateCount, C_eval) table if callable, plus per-state callable flag
    mNrmMinNext_table,                 # (StateCount, C_eval)
    mNrmMinNext_is_callable,           # (StateCount,) bool
    mNrmMinNext_scalar,                # (StateCount,) — used when not callable
    # IncShkDstn arrays
    IncShk_pmv,                        # (StateCount, ShkCount)
    IncShk_perm,                       # (StateCount, ShkCount)
    IncShk_tran,                       # (StateCount, ShkCount)
    LivPrb,                            # (StateCount,)
    DiscFac, CRRA,                     # scalars
    Rfree,                             # (StateCount,)
    PermGroFac,                        # (StateCount,)
    MrkvArray,                         # (StateCount, StateCount)
    BoroCnstArt,                       # scalar
    aXtraGrid,                         # (aCount,)
    Cgrid,                             # (Ccount,)
    CFunc_slope, CFunc_intercept,      # (StateCount, StateCount)
    ADelasticity,
    RecState_per_state,                # (StateCount,) int — 0/1 per state for ADFunc
):
    """One backward-induction step. Returns cNrm/mNrm tables and BoroCnstNat per (state, c).

    Returns dict with:
      cNrm: (StateCount, Ccount, aCount)
      mNrm: (StateCount, Ccount, aCount)
      BoroCnstNat_per_j: (StateCount, Ccount) — natural constraint from Loop 1
      BoroCnstNat_per_i: (StateCount, Ccount) — natural constraint from Loop 2 (cFunc usage)
    """
    StateCount = Rfree.shape[0]
    Ccount = Cgrid.shape[0]
    aCount = aXtraGrid.shape[0]

    # === Loop 1: per next-state j, compute EndOfPrdvP_cond + BoroCnstNat ===
    def per_next_state(j):
        return _loop1_one_next_state(
            vPfuncNext_table[j], mNrmMinNext_table[j],
            mNrmMinNext_is_callable[j], mNrmMinNext_scalar[j],
            m_eval, C_eval,
            IncShk_pmv[j], IncShk_perm[j], IncShk_tran[j],
            Rfree[j], PermGroFac[j], DiscFac, CRRA,
            aXtraGrid, Cgrid,
            RecState_per_state[j], ADelasticity,
        )

    # vmap over next-state j. Returns (StateCount, Ccount, aCount), (StateCount, Ccount)
    EndOfPrdvP_cond_all, BoroCnstNat_per_j = jax.vmap(per_next_state)(jnp.arange(StateCount))

    # Prepend 0 to aXtra grid and to nvrs(EndOfPrdvP) for boundary handling
    # aGrid_with_0[j, c, :] = [0, aNrmMin[j,c]+aXtra[0], aNrmMin[j,c]+aXtra[1], ...]
    # Actually HARK does: BilinearInterp(np.transpose(EndOfPrdvPnvrs), np.insert(aXtraGrid, 0, 0.0), Cgrid)
    # So the underlying grid is np.insert(aXtraGrid, 0, 0.0) — NOT aNrmMin+aXtra.
    # The "VariableLowerBoundFunc2D" wrapper SHIFTS query points by BoroCnstNat(C) before lookup.
    # So the EndOfPrdvP_nvrs values are indexed by aXtra (relative to aNrmMin), not absolute aNrm.
    aXtra_with_0 = jnp.concatenate([jnp.zeros(1), aXtraGrid])  # (aCount+1,)
    EndOfPrdvP_nvrs = EndOfPrdvP_cond_all ** (-1.0 / CRRA)
    EndOfPrdvP_nvrs_with_0 = jnp.concatenate(
        [jnp.zeros((StateCount, Ccount, 1)), EndOfPrdvP_nvrs], axis=2)  # (StateCount, Ccount, aCount+1)
    EndOfPrdvP_aGrids = jnp.broadcast_to(
        aXtra_with_0[None, None, :], (StateCount, Ccount, aCount + 1))

    # === Loop 2: per current state i, compute cNrm/mNrm ===
    def per_current_state(i):
        return _loop2_one_current_state(
            i, EndOfPrdvP_cond_all, BoroCnstNat_per_j,
            EndOfPrdvP_aGrids, EndOfPrdvP_nvrs_with_0,
            MrkvArray, LivPrb[i], CRRA,
            CFunc_slope, CFunc_intercept, Cgrid, aXtraGrid,
        )

    cNrm_all, mNrm_all, BoroCnstNat_per_i = jax.vmap(per_current_state)(jnp.arange(StateCount))

    return {
        'cNrm': cNrm_all,                       # (StateCount, Ccount, aCount)
        'mNrm': mNrm_all,                       # (StateCount, Ccount, aCount)
        'BoroCnstNat_per_j': BoroCnstNat_per_j, # (StateCount, Ccount) — from Loop 1
        'BoroCnstNat_per_i': BoroCnstNat_per_i, # (StateCount, Ccount) — from Loop 2
    }


def evaluate_cFunc(cNrm_table, mNrm_table, BoroCnstNat_per_i, BoroCnstArt,
                   Cgrid, state_i, m_query, C_query):
    """Evaluate the unconstrained cFunc for state i at (m_query, C_query).

    Uses linear_interp_on_interp_1d_general with per-Cgrid x_grids = (mNrm[i, c, :] - BoroCnstNat[i, c]).

    NOTE: this is the UNCONSTRAINED component (cFuncBase). For full cFuncNow you'd
    apply LowerEnvelope2D with cFuncCnst. For interior points well above BoroCnstArt,
    this matches HARK's cFunc.
    """
    cNrm_i = cNrm_table[state_i]     # (Ccount, aCount)
    mNrm_i = mNrm_table[state_i]     # (Ccount, aCount)
    BoroCnstNat_i = BoroCnstNat_per_i[state_i]  # (Ccount,)

    # Per-C: x_grid = [0, mNrm[c, 0] - BoroCnstNat[c], mNrm[c, 1] - BoroCnstNat[c], ...]
    aCount = cNrm_i.shape[1]
    Ccount = Cgrid.shape[0]
    m_shifted = mNrm_i - BoroCnstNat_i[:, None]  # (Ccount, aCount)
    x_grids = jnp.concatenate([jnp.zeros((Ccount, 1)), m_shifted], axis=1)  # (Ccount, aCount+1)
    f_values = jnp.concatenate([jnp.zeros((Ccount, 1)), cNrm_i], axis=1)    # (Ccount, aCount+1)

    # Shift query m by BoroCnstNat at the query C
    BoroCnstNat_at_C = jax.vmap(
        lambda C: linear_interp_1d(Cgrid, BoroCnstNat_i, C, lower_extrap=True)
    )(jnp.atleast_1d(C_query))
    m_query_shifted = jnp.atleast_1d(m_query) - BoroCnstNat_at_C

    cFuncBase = linear_interp_on_interp_1d_general(
        x_grids, Cgrid, f_values,
        m_query_shifted, jnp.atleast_1d(C_query))
    return cFuncBase
