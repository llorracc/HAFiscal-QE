"""
Speedup 2B: JAX-native iteration loop for HAFiscal's solve_agg_cons_markov.

The existing per-period kernel (jax_solver_kernel.solve_one_period_jax) is
fast but called once per backward-induction step from Python — each call
incurs JAX dispatch overhead (~ms). For an infinite-horizon problem (HAFiscal
recession: T_cycle=1, cycles=0), HARK iterates 50-100+ times to converge cFunc,
so dispatch overhead dominates.

This module wraps the per-period kernel in a lax.scan-based iteration that
runs N fixed iterations in ONE JIT'd call. The kernel itself is unchanged
(reuses jax_solver_kernel internals); only the iteration mechanism is moved
into JAX.

HARK upstream path
------------------
The same idea applies to HARK's solve_ConsAggMarkov (PR-3 #1779):
1. Refactor solve_one_period_ConsAggMarkov_jax to take (vPfuncNext_table,
   params) -> (cNrm, mNrm, BoroCnstNat) directly (pure JAX).
2. Add a `solve_until_convergence_jax(initial_table, params, max_iter, tol)`
   that uses lax.while_loop with convergence check.
3. PR these as a follow-up to #1779.

Current scope (HAFiscal-side)
-----------------------------
- Wraps the existing jax_solver_kernel.solve_one_period_jax
- Two iteration mechanisms: N FIXED iterations via lax.scan (iterate_cfunc_jax)
  and a lax.while_loop convergence-checked variant
  (iterate_cfunc_jax_until_convergence, later in this module)
- Used as a drop-in for agent.solve() (replaces N HARK iterations)
"""
from __future__ import annotations
import os
import numpy as np

try:
    import jax
    import jax.numpy as jnp
    from jax import lax
    _HAS_JAX = True
except ImportError:
    _HAS_JAX = False

if _HAS_JAX:
    from jax_solver_kernel import solve_one_period_jax
    # Reuse the input-extraction helpers from the single-period drop-in.
    from jax_solver_drop_in import (
        _DEFAULT_M_EVAL,
        _tabulate_vPfuncNext,
        _tabulate_mNrmMinNext,
        _extract_IncShk_arrays,
        _extract_CFunc_arrays,
        _sniff_elasticity,
    )


# --- Standard m_eval grid used by jax_solver_drop_in ---
_DEFAULT_M_EVAL = np.unique(np.concatenate([
    np.linspace(0.001, 0.1, 100),
    np.linspace(0.1, 1.0, 200),
    np.linspace(1.0, 5.0, 200),
    np.linspace(5.0, 50.0, 200),
]))


def _tabulate_cFunc_2d(cNrm_tables, mNrm_tables, BoroCnstNat_per_i,
                        BoroCnstArt, Cgrid, m_eval, C_eval):
    """Tabulate cFunc[j](m_eval, C_eval) from kernel output tables.

    cNrm/mNrm tables: (StateCount, Ccount, aCount)
    BoroCnstNat_per_i: (StateCount, Ccount)

    Returns (StateCount, M_eval, C_eval) cFunc table.
    """
    StateCount = cNrm_tables.shape[0]
    Ccount = cNrm_tables.shape[1]
    M_eval = m_eval.shape[0]
    Cev = C_eval.shape[0]

    # For each (j, c_idx_in_Cgrid), the cFunc is parameterized by
    # (mNrm[j,c,:] - BoroCnstNat_per_i[j,c], cNrm[j,c,:]) — i.e., we shift m
    # by the borrowing constraint before linear interp.
    # For querying at (m, C), we:
    #   1. Find c_lo/c_hi in Cgrid surrounding C
    #   2. For each, do linear interp in m_shifted on cNrm[j, c, :]
    #   3. Linear blend in C
    # And add the borrowing-constraint kink (cFunc = min(c_unc, m - BoroCnstArt))

    def _per_state(j):
        # For each (j), evaluate cFunc at all (m_eval[i], C_eval[k]) → (M, Cev)
        cnrm_j = cNrm_tables[j]  # (Ccount, aCount)
        mnrm_j = mNrm_tables[j]
        bc_j = BoroCnstNat_per_i[j]  # (Ccount,)

        # For each k in Cev: bracket in Cgrid, then for each m do interp
        def _per_C(k):
            C_query = C_eval[k]
            c_pos = jnp.clip(
                jnp.searchsorted(Cgrid, C_query, side='right') - 1,
                0, Ccount - 2)
            w_C = (C_query - Cgrid[c_pos]) / (Cgrid[c_pos + 1] - Cgrid[c_pos])

            # Per-c_pos cNrm/mNrm/bc for the bracketing c_pos and c_pos+1
            cnrm_lo = cnrm_j[c_pos]
            cnrm_hi = cnrm_j[c_pos + 1]
            mnrm_lo = mnrm_j[c_pos]
            mnrm_hi = mnrm_j[c_pos + 1]
            bc_lo = bc_j[c_pos]
            bc_hi = bc_j[c_pos + 1]

            # Linear interp in m_shifted on the cohort lo/hi cNrm-vs-mNrm
            # Note: we evaluate at m_eval (not m_eval-bc), then bc shifts inside
            def _per_m(m_query):
                # Lo c: interp at m_query (which is mNrm domain after shift)
                aCount = cnrm_lo.shape[0]
                # mNrm grid prepended with bc_lo at bottom (zero c)
                # cNrm grid prepended with 0
                m_grid_lo = jnp.concatenate([jnp.array([bc_lo]), mnrm_lo])
                c_grid_lo = jnp.concatenate([jnp.array([0.0]), cnrm_lo])
                m_grid_hi = jnp.concatenate([jnp.array([bc_hi]), mnrm_hi])
                c_grid_hi = jnp.concatenate([jnp.array([0.0]), cnrm_hi])

                i_lo = jnp.clip(
                    jnp.searchsorted(m_grid_lo, m_query, side='right') - 1,
                    0, aCount - 1)
                w_lo = jnp.where(
                    m_grid_lo[i_lo + 1] > m_grid_lo[i_lo],
                    (m_query - m_grid_lo[i_lo])
                    / (m_grid_lo[i_lo + 1] - m_grid_lo[i_lo]),
                    0.0)
                c_unc_lo = c_grid_lo[i_lo] + w_lo * (c_grid_lo[i_lo + 1] - c_grid_lo[i_lo])

                i_hi = jnp.clip(
                    jnp.searchsorted(m_grid_hi, m_query, side='right') - 1,
                    0, aCount - 1)
                w_hi = jnp.where(
                    m_grid_hi[i_hi + 1] > m_grid_hi[i_hi],
                    (m_query - m_grid_hi[i_hi])
                    / (m_grid_hi[i_hi + 1] - m_grid_hi[i_hi]),
                    0.0)
                c_unc_hi = c_grid_hi[i_hi] + w_hi * (c_grid_hi[i_hi + 1] - c_grid_hi[i_hi])

                c_unc = (1 - w_C) * c_unc_lo + w_C * c_unc_hi
                # Borrowing constraint: c <= m - BoroCnstArt
                c_cnst = m_query - BoroCnstArt
                return jnp.minimum(c_unc, c_cnst)

            return jax.vmap(_per_m)(m_eval)  # (M,)

        return jax.vmap(_per_C)(jnp.arange(Cev)).T  # (M, Cev)

    return jax.vmap(_per_state)(jnp.arange(StateCount))  # (StateCount, M, Cev)


def iterate_cfunc_jax(
        initial_vPfuncNext_table,  # (StateCount, M_eval, C_eval)
        m_eval, C_eval,
        mNrmMinNext_table,
        mNrmMinNext_is_callable, mNrmMinNext_scalar,
        IncShk_pmv, IncShk_perm, IncShk_tran,
        LivPrb, DiscFac, CRRA, Rfree, PermGroFac, MrkvArray,
        BoroCnstArt, aXtraGrid, Cgrid,
        CFunc_slope, CFunc_intercept,
        ADelasticity, RecState_per_state,
        n_iters):
    """Run N fixed backward-induction iterations in ONE JIT'd lax.scan call.

    Each iteration:
      1. Call solve_one_period_jax with current vPfuncNext_table → cNrm/mNrm/bc
      2. Tabulate cFunc on (m_eval, C_eval) from the new tables
      3. vPfuncNext_table_new = cFunc_table ** (-CRRA)

    Returns the final (cNrm, mNrm, BoroCnstNat_per_i) tables after n_iters.
    """
    if not _HAS_JAX:
        raise RuntimeError("JAX not available")

    BoroCnstArt_f = float(BoroCnstArt) if BoroCnstArt is not None else 0.0

    @jax.jit
    def _iter_body(carry, _xs):
        vP_table = carry  # (StateCount, M_eval, C_eval)
        result = solve_one_period_jax(
            vP_table, m_eval, C_eval,
            mNrmMinNext_table, mNrmMinNext_is_callable, mNrmMinNext_scalar,
            IncShk_pmv, IncShk_perm, IncShk_tran,
            LivPrb, DiscFac, CRRA, Rfree, PermGroFac, MrkvArray,
            BoroCnstArt_f, aXtraGrid, Cgrid,
            CFunc_slope, CFunc_intercept,
            ADelasticity, RecState_per_state,
        )
        # Tabulate new cFunc on (m_eval, C_eval) → new vPfuncNext_table
        cFunc_table = _tabulate_cFunc_2d(
            result['cNrm'], result['mNrm'], result['BoroCnstNat_per_i'],
            BoroCnstArt_f, Cgrid, m_eval, C_eval,
        )
        # vPfunc = c^(-CRRA); guard c=0 with epsilon
        vP_new = jnp.where(
            cFunc_table > 1e-12, cFunc_table ** (-CRRA), 1e12)
        # Pass the new vP_table forward; also export the latest cNrm/mNrm/bc
        return vP_new, (result['cNrm'], result['mNrm'],
                        result['BoroCnstNat_per_i'])

    # Run n_iters via lax.scan
    final_vP, all_outs = lax.scan(_iter_body, initial_vPfuncNext_table,
                                    None, length=n_iters)
    # Take only the final iteration's outputs
    cNrm_final = all_outs[0][-1]
    mNrm_final = all_outs[1][-1]
    bc_final = all_outs[2][-1]
    return {
        'cNrm': cNrm_final,
        'mNrm': mNrm_final,
        'BoroCnstNat_per_i': bc_final,
        'final_vPfuncNext_table': final_vP,
    }


# --------------------------------------------------------------------------
# 2B: lax.while_loop variant — iterate until cFunc-table converges or
# max_iters is hit. The cFunc convergence diff is computed inside the JAX
# loop, so we never round-trip through Python.
# --------------------------------------------------------------------------


def iterate_cfunc_jax_until_convergence(
        initial_vPfuncNext_table,
        initial_cFunc_table,           # (StateCount, M_eval, C_eval) — used for diff
        m_eval, C_eval,
        mNrmMinNext_table,
        mNrmMinNext_is_callable, mNrmMinNext_scalar,
        IncShk_pmv, IncShk_perm, IncShk_tran,
        LivPrb, DiscFac, CRRA, Rfree, PermGroFac, MrkvArray,
        BoroCnstArt, aXtraGrid, Cgrid,
        CFunc_slope, CFunc_intercept,
        ADelasticity, RecState_per_state,
        max_iters=100,
        tol=1e-7):
    """Iterate the per-period kernel under lax.while_loop until
    max(|cFunc_table_new - cFunc_table_old|) < tol OR iter_count >= max_iters.

    All convergence logic lives inside JIT — no Python iter dispatch overhead.

    Returns dict with the final cNrm/mNrm/BoroCnstNat tables, the final
    cFunc table, n_iters actually used, and final diff.
    """
    if not _HAS_JAX:
        raise RuntimeError("JAX not available")

    BoroCnstArt_f = float(BoroCnstArt) if BoroCnstArt is not None else 0.0
    # Convert max_iters/tol to JAX-friendly values
    max_iters_j = jnp.int32(max_iters)
    tol_j = jnp.float64(tol)

    StateCount = MrkvArray.shape[0]
    Ccount = Cgrid.shape[0]
    aCount = aXtraGrid.shape[0]
    M_eval = m_eval.shape[0]

    # Carry shape: (iter_idx, vP_table, cFunc_prev, diff, cNrm, mNrm, BoroCnstNat_per_i)
    # — by including the kernel result arrays in the carry, we avoid the
    # redundant final kernel call (one full iter saved on the hot path).
    init_state = (
        jnp.int32(0),
        initial_vPfuncNext_table,                          # (StateCount, M_eval, C_eval)
        initial_cFunc_table,                               # (StateCount, M_eval, C_eval)
        jnp.float64(jnp.inf),
        jnp.zeros((StateCount, Ccount, aCount), dtype=jnp.float64),
        jnp.zeros((StateCount, Ccount, aCount), dtype=jnp.float64),
        jnp.zeros((StateCount, Ccount), dtype=jnp.float64),
    )

    def _cond(state):
        iter_idx, _vP, _cFunc_prev, diff, _cNrm, _mNrm, _bc = state
        return jnp.logical_and(iter_idx < max_iters_j, diff > tol_j)

    def _body(state):
        iter_idx, vP_table, cFunc_prev, _diff, _cNrm, _mNrm, _bc = state
        result = solve_one_period_jax(
            vP_table, m_eval, C_eval,
            mNrmMinNext_table, mNrmMinNext_is_callable, mNrmMinNext_scalar,
            IncShk_pmv, IncShk_perm, IncShk_tran,
            LivPrb, DiscFac, CRRA, Rfree, PermGroFac, MrkvArray,
            BoroCnstArt_f, aXtraGrid, Cgrid,
            CFunc_slope, CFunc_intercept,
            ADelasticity, RecState_per_state,
        )
        cFunc_new = _tabulate_cFunc_2d(
            result['cNrm'], result['mNrm'], result['BoroCnstNat_per_i'],
            BoroCnstArt_f, Cgrid, m_eval, C_eval,
        )
        vP_new = jnp.where(
            cFunc_new > 1e-12, cFunc_new ** (-CRRA), 1e12)
        diff_new = jnp.max(jnp.abs(cFunc_new - cFunc_prev))
        return (iter_idx + 1, vP_new, cFunc_new, diff_new,
                result['cNrm'], result['mNrm'], result['BoroCnstNat_per_i'])

    final_state = lax.while_loop(_cond, _body, init_state)
    iters_used, final_vP, final_cFunc, final_diff, \
        cNrm_final, mNrm_final, bc_final = final_state

    return {
        'cNrm': cNrm_final,
        'mNrm': mNrm_final,
        'BoroCnstNat_per_i': bc_final,
        'final_cFunc_table': final_cFunc,
        'final_vPfuncNext_table': final_vP,
        'n_iters': int(iters_used),
        'final_diff': float(final_diff),
        'converged': bool(final_diff < tol),
    }


# --------------------------------------------------------------------------
# Input extraction: gather all kernel inputs from a fully-built HAFiscal agent
# + initial belief solution. Output is a dict ready to pass into either the
# fixed-iter (iterate_cfunc_jax) or convergence (iterate_cfunc_jax_until_convergence)
# entry point.
# --------------------------------------------------------------------------

def extract_solve_inputs(agent, solution_initial=None, m_eval=None):
    """Gather all per-period kernel inputs from a HAFiscal agent.

    Args:
        agent: AggFiscalType (post-update_solution_terminal).
        solution_initial: HARK ConsumerSolution to use as the initial belief.
            Default: ``agent.solution_terminal``.
        m_eval: 1-D numpy array of m-grid evaluation points. Default:
            jax_solver_drop_in._DEFAULT_M_EVAL.

    Returns:
        dict suitable for ``iterate_cfunc_jax_until_convergence`` (and the
        fixed-iter sibling). Includes both the initial vPfuncNext_table and
        the initial cFunc_table — the cFunc one is used as the previous-iter
        reference for the lax.while_loop convergence check.
    """
    if not _HAS_JAX:
        raise RuntimeError("JAX not available")

    StateCount = agent.MrkvArray[0].shape[0]
    Cgrid = np.asarray(agent.Cgrid)
    Ccount = Cgrid.size
    aXtraGrid = np.asarray(agent.aXtraGrid)

    if solution_initial is None:
        solution_initial = agent.solution_terminal
    if m_eval is None:
        m_eval = _DEFAULT_M_EVAL
    m_eval = np.asarray(m_eval)
    C_eval = Cgrid  # the cFunc convergence check uses the Cgrid as eval pts

    # Tabulate the initial belief (vPfuncNext) and reverse-engineer cFunc_table
    # from it: cFunc = vPfunc ** (-1/CRRA).
    vP_init_table = _tabulate_vPfuncNext(solution_initial, StateCount,
                                         m_eval, C_eval)
    cFunc_init_table = np.where(vP_init_table > 1e-12,
                                vP_init_table ** (-1.0 / float(agent.CRRA)),
                                1e12)

    mNrmMinNext_table, mNrmMin_is_callable, mNrmMin_scalar = \
        _tabulate_mNrmMinNext(solution_initial, StateCount, C_eval)

    IncShkDstn = agent.IncShkDstn[0]  # time_inv → period 0 is the all-periods one
    IncShk_pmv, IncShk_perm, IncShk_tran = _extract_IncShk_arrays(
        IncShkDstn, StateCount)

    CFunc_slope, CFunc_intercept = _extract_CFunc_arrays(agent.CFunc, StateCount)
    # ADFunc is built by AggFiscalType.update_AggDemandFunc — extract elasticity
    # the same way the drop-in solver does.
    if hasattr(agent, 'ADFunc') and agent.ADFunc is not None:
        ADelasticity = _sniff_elasticity(agent.ADFunc)
    else:
        ADelasticity = float(getattr(agent, 'ADelasticity', 0.0))

    num_base = int(getattr(agent, 'num_base_MrkvStates', 4))
    RecState_per_state = np.array(
        [((j // num_base) % 2 == 1) for j in range(StateCount)], dtype=np.int32)

    Rfree = np.asarray(agent.Rfree) if hasattr(agent.Rfree, '__len__') \
        else np.full(StateCount, float(agent.Rfree))
    PermGroFac = np.asarray(agent.PermGroFac[0]) \
        if isinstance(agent.PermGroFac, list) \
        else np.asarray(agent.PermGroFac)
    LivPrb = np.asarray(agent.LivPrb[0]) \
        if isinstance(agent.LivPrb, list) \
        else np.asarray(agent.LivPrb)

    return {
        'initial_vPfuncNext_table': jnp.asarray(vP_init_table),
        'initial_cFunc_table':      jnp.asarray(cFunc_init_table),
        'm_eval':                    jnp.asarray(m_eval),
        'C_eval':                    jnp.asarray(C_eval),
        'mNrmMinNext_table':         jnp.asarray(mNrmMinNext_table),
        'mNrmMinNext_is_callable':   jnp.asarray(mNrmMin_is_callable),
        'mNrmMinNext_scalar':        jnp.asarray(mNrmMin_scalar),
        'IncShk_pmv':                jnp.asarray(IncShk_pmv),
        'IncShk_perm':               jnp.asarray(IncShk_perm),
        'IncShk_tran':               jnp.asarray(IncShk_tran),
        'LivPrb':                    jnp.asarray(LivPrb),
        'DiscFac':                   float(agent.DiscFac),
        'CRRA':                      float(agent.CRRA),
        'Rfree':                     jnp.asarray(Rfree),
        'PermGroFac':                jnp.asarray(PermGroFac),
        'MrkvArray':                 jnp.asarray(agent.MrkvArray[0]),
        'BoroCnstArt':               float(agent.BoroCnstArt)
                                       if agent.BoroCnstArt is not None else 0.0,
        'aXtraGrid':                 jnp.asarray(aXtraGrid),
        'Cgrid':                     jnp.asarray(Cgrid),
        'CFunc_slope':               jnp.asarray(CFunc_slope),
        'CFunc_intercept':           jnp.asarray(CFunc_intercept),
        'ADelasticity':              float(ADelasticity),
        'RecState_per_state':        jnp.asarray(RecState_per_state),
    }


def solve_to_convergence_from_agent(agent, max_iters=100, tol=1e-7,
                                       solution_initial=None):
    """End-to-end convenience: extract inputs from agent + run while_loop.

    Returns the dict from ``iterate_cfunc_jax_until_convergence``."""
    inputs = extract_solve_inputs(agent, solution_initial=solution_initial)
    return iterate_cfunc_jax_until_convergence(
        initial_vPfuncNext_table=inputs['initial_vPfuncNext_table'],
        initial_cFunc_table=inputs['initial_cFunc_table'],
        m_eval=inputs['m_eval'],
        C_eval=inputs['C_eval'],
        mNrmMinNext_table=inputs['mNrmMinNext_table'],
        mNrmMinNext_is_callable=inputs['mNrmMinNext_is_callable'],
        mNrmMinNext_scalar=inputs['mNrmMinNext_scalar'],
        IncShk_pmv=inputs['IncShk_pmv'],
        IncShk_perm=inputs['IncShk_perm'],
        IncShk_tran=inputs['IncShk_tran'],
        LivPrb=inputs['LivPrb'],
        DiscFac=inputs['DiscFac'],
        CRRA=inputs['CRRA'],
        Rfree=inputs['Rfree'],
        PermGroFac=inputs['PermGroFac'],
        MrkvArray=inputs['MrkvArray'],
        BoroCnstArt=inputs['BoroCnstArt'],
        aXtraGrid=inputs['aXtraGrid'],
        Cgrid=inputs['Cgrid'],
        CFunc_slope=inputs['CFunc_slope'],
        CFunc_intercept=inputs['CFunc_intercept'],
        ADelasticity=inputs['ADelasticity'],
        RecState_per_state=inputs['RecState_per_state'],
        max_iters=max_iters,
        tol=tol,
    )
