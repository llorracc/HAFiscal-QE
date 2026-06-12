"""2B + cohort-vmap: solve all cohorts together in a single JIT'd
lax.while_loop with jax.vmap across cohorts.

Builds on jax_solver_iterated.iterate_cfunc_jax_until_convergence but
vmaps the per-period kernel across the cohort axis. All cohorts iterate
together; the while_loop convergence criterion is the max-cohort cFunc
diff. Wasted work on already-converged cohorts is bounded by the slowest
cohort's iter count; with warm_start (production AD outer loop), all
cohorts converge in similar iter counts so the waste is minimal.

The main savings vs serial cohort solves:
- One JIT compile instead of N
- One JAX dispatch per iter instead of N
- Per-iter overhead amortized across cohorts (HARK's biggest pain point)

Entry point: solve_all_cohorts_to_convergence_consumer_solutions.
"""
from __future__ import annotations
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "FromPandemicCode"))

try:
    import jax
    import jax.numpy as jnp
    from jax import lax
    _HAS_JAX = True
except ImportError:
    _HAS_JAX = False

if _HAS_JAX:
    from jax_solver_kernel import solve_one_period_jax
    from jax_solver_iterated import _tabulate_cFunc_2d, extract_solve_inputs


# Memoize the chunk_size that worked for a given (n_cohorts, StateCount)
# combination — avoids re-OOMing on every eco.solve() call during an AD loop.
_VMAP_CHUNK_SIZE_CACHE = {}


def extract_solve_inputs_stacked(agents, from_solutions=None, m_eval=None):
    """Stack per-cohort inputs into JAX arrays with cohort axis = 0.

    Args:
        agents: list of AggFiscalType cohorts.
        from_solutions: per-cohort initial beliefs (list, same length as agents).
            Default: agent.solution_terminal for each.
        m_eval: shared m_eval grid. Default: jax_solver_drop_in._DEFAULT_M_EVAL.

    Returns:
        dict of stacked arrays + shared scalars.
    """
    if not _HAS_JAX:
        raise RuntimeError("JAX not available")
    n_cohorts = len(agents)
    if from_solutions is None:
        from_solutions = [None] * n_cohorts

    # Extract per cohort, then stack
    per_cohort = [
        extract_solve_inputs(agent, solution_initial=from_solutions[i],
                              m_eval=m_eval)
        for i, agent in enumerate(agents)
    ]

    # Per-cohort (stacked, axis 0 = cohort)
    def _stack(key):
        return jnp.stack([pc[key] for pc in per_cohort], axis=0)

    # Shared (use cohort 0's values; assert equality on shared keys at debug)
    shared_keys = (
        'm_eval', 'C_eval', 'aXtraGrid', 'Cgrid',
        'CFunc_slope', 'CFunc_intercept',
        'RecState_per_state',
    )
    shared = {k: per_cohort[0][k] for k in shared_keys}
    # Scalars (shared)
    shared_scalars = {
        'CRRA': float(per_cohort[0]['CRRA']),
        'BoroCnstArt': float(per_cohort[0]['BoroCnstArt']),
        'ADelasticity': float(per_cohort[0]['ADelasticity']),
    }

    # Per-cohort stacked
    stacked = {
        'initial_vPfuncNext_table': _stack('initial_vPfuncNext_table'),  # (n_cohorts, S, M, C)
        'initial_cFunc_table':      _stack('initial_cFunc_table'),
        'mNrmMinNext_table':        _stack('mNrmMinNext_table'),  # (n_cohorts, S, C)
        'mNrmMinNext_is_callable':  _stack('mNrmMinNext_is_callable'),  # (n_cohorts, S)
        'mNrmMinNext_scalar':       _stack('mNrmMinNext_scalar'),
        'IncShk_pmv':               _stack('IncShk_pmv'),
        'IncShk_perm':              _stack('IncShk_perm'),
        'IncShk_tran':              _stack('IncShk_tran'),
        'LivPrb':                   _stack('LivPrb'),
        'DiscFac':                  jnp.asarray([float(pc['DiscFac']) for pc in per_cohort]),
        'Rfree':                    _stack('Rfree'),
        'PermGroFac':               _stack('PermGroFac'),
        'MrkvArray':                _stack('MrkvArray'),
    }
    out = {**stacked, **shared, **shared_scalars, 'n_cohorts': n_cohorts}
    return out


def _kernel_one_cohort_one_iter(
        vP_table_c, mNrmMinNext_table_c, mNrmMinNext_is_callable_c,
        mNrmMinNext_scalar_c, IncShk_pmv_c, IncShk_perm_c, IncShk_tran_c,
        LivPrb_c, DiscFac_c, Rfree_c, PermGroFac_c, MrkvArray_c,
        m_eval, C_eval, CRRA, BoroCnstArt, aXtraGrid, Cgrid,
        CFunc_slope, CFunc_intercept, ADelasticity, RecState_per_state):
    """One backward-induction step for one cohort. Returns cNrm/mNrm/bc tables
    + new cFunc_table + new vP_table. All inputs explicit (no closures over
    per-cohort vs shared), so this is easy to jax.vmap."""
    result = solve_one_period_jax(
        vP_table_c, m_eval, C_eval,
        mNrmMinNext_table_c, mNrmMinNext_is_callable_c, mNrmMinNext_scalar_c,
        IncShk_pmv_c, IncShk_perm_c, IncShk_tran_c,
        LivPrb_c, DiscFac_c, CRRA, Rfree_c, PermGroFac_c, MrkvArray_c,
        BoroCnstArt, aXtraGrid, Cgrid,
        CFunc_slope, CFunc_intercept, ADelasticity, RecState_per_state,
    )
    cFunc_new = _tabulate_cFunc_2d(
        result['cNrm'], result['mNrm'], result['BoroCnstNat_per_i'],
        BoroCnstArt, Cgrid, m_eval, C_eval,
    )
    vP_new = jnp.where(cFunc_new > 1e-12, cFunc_new ** (-CRRA), 1e12)
    return (result['cNrm'], result['mNrm'], result['BoroCnstNat_per_i'],
            cFunc_new, vP_new)


def iterate_cfunc_multicohort_until_convergence(stacked_inputs,
                                                  max_iters=500, tol=1e-7):
    """Run lax.while_loop over the per-cohort kernel, vmapped across cohorts.

    Args:
        stacked_inputs: dict from extract_solve_inputs_stacked.
        max_iters: hard iter cap.
        tol: max-over-cohorts cFunc-diff convergence threshold.

    Returns:
        dict with stacked outputs (cNrm, mNrm, BoroCnstNat_per_i, final_cFunc)
        plus n_iters and final_diff.
    """
    if not _HAS_JAX:
        raise RuntimeError("JAX not available")

    # vmap the per-cohort kernel across cohort axis 0 for per-cohort tensors,
    # None for shared ones.
    _kernel_vmapped = jax.vmap(
        _kernel_one_cohort_one_iter,
        in_axes=(
            0, 0, 0, 0,         # vP, mNrmMin_table, is_callable, scalar
            0, 0, 0,            # IncShk pmv/perm/tran
            0, 0, 0, 0, 0,      # LivPrb, DiscFac, Rfree, PermGroFac, MrkvArray
            None, None,         # m_eval, C_eval (shared)
            None, None,         # CRRA, BoroCnstArt
            None, None,         # aXtraGrid, Cgrid
            None, None,         # CFunc_slope, CFunc_intercept
            None, None,         # ADelasticity, RecState_per_state
        ),
    )

    si = stacked_inputs
    n_cohorts = si['n_cohorts']
    StateCount = si['MrkvArray'].shape[1]
    Ccount = si['Cgrid'].shape[0]
    aCount = si['aXtraGrid'].shape[0]

    # Initial carry: include zeros placeholders for kernel outputs (cNrm/mNrm/bc).
    # Shape conventions: stacked along cohort axis 0.
    zero_cNrm = jnp.zeros((n_cohorts, StateCount, Ccount, aCount), dtype=jnp.float64)
    zero_mNrm = jnp.zeros_like(zero_cNrm)
    zero_bc = jnp.zeros((n_cohorts, StateCount, Ccount), dtype=jnp.float64)

    init_state = (
        jnp.int32(0),
        si['initial_vPfuncNext_table'],
        si['initial_cFunc_table'],
        jnp.float64(jnp.inf),       # initial max-diff
        zero_cNrm,
        zero_mNrm,
        zero_bc,
    )

    max_iters_j = jnp.int32(max_iters)
    tol_j = jnp.float64(tol)

    def _cond(state):
        iter_idx, _, _, max_diff, *_ = state
        return jnp.logical_and(iter_idx < max_iters_j, max_diff > tol_j)

    def _body(state):
        iter_idx, vP_tables, cFunc_prevs, _max_diff, _cNrm, _mNrm, _bc = state
        cNrm_new, mNrm_new, bc_new, cFunc_new, vP_new = _kernel_vmapped(
            vP_tables, si['mNrmMinNext_table'], si['mNrmMinNext_is_callable'],
            si['mNrmMinNext_scalar'],
            si['IncShk_pmv'], si['IncShk_perm'], si['IncShk_tran'],
            si['LivPrb'], si['DiscFac'], si['Rfree'],
            si['PermGroFac'], si['MrkvArray'],
            si['m_eval'], si['C_eval'],
            si['CRRA'], si['BoroCnstArt'],
            si['aXtraGrid'], si['Cgrid'],
            si['CFunc_slope'], si['CFunc_intercept'],
            si['ADelasticity'], si['RecState_per_state'],
        )
        # Per-cohort diff = max over (StateCount, M, C); aggregate by max-over-cohorts
        per_cohort_diff = jnp.max(jnp.abs(cFunc_new - cFunc_prevs), axis=(1, 2, 3))
        max_diff_new = jnp.max(per_cohort_diff)
        return (iter_idx + 1, vP_new, cFunc_new, max_diff_new,
                cNrm_new, mNrm_new, bc_new)

    final_state = lax.while_loop(_cond, _body, init_state)
    iters_used, final_vP, final_cFunc, final_diff, \
        cNrm_final, mNrm_final, bc_final = final_state

    return {
        'cNrm': cNrm_final,                   # (n_cohorts, S, C, a)
        'mNrm': mNrm_final,
        'BoroCnstNat_per_i': bc_final,        # (n_cohorts, S, C)
        'final_cFunc_table': final_cFunc,
        'final_vPfuncNext_table': final_vP,
        'n_iters': int(iters_used),
        'final_diff': float(final_diff),
        'converged': bool(final_diff < tol),
    }


def solve_all_cohorts_to_convergence_consumer_solutions(
        agents, max_iters=500, tol=1e-7, from_solutions=None, verbose=False,
        chunk_size=None):
    """Drop-in for the per-cohort `solve_agent` loop in
    AggregateDemandEconomy.solve. Returns a list of [ConsumerSolution]
    (one per cohort, matching the loop's `solve_agent` output shape).

    chunk_size: vmap this many cohorts at a time. None = all-at-once (max
    memory). At Baseline (21 cohorts, StateCount=252), all-at-once needs
    ~13+ GB; chunk_size=4 keeps it under ~3 GB. Default (None) tries
    all-at-once, then falls back to chunk_size=4 on OOM.
    """
    if not _HAS_JAX:
        raise RuntimeError("JAX not available")
    import jax
    jax.config.update("jax_enable_x64", True)

    from jax_solver_drop_in import (
        _JAXcFuncWrap, _JAXvPfuncWrap, _JAXmNrmMinWrap,
    )
    from HARK.ConsumptionSaving.ConsAggShockModel import ConsumerSolution

    if from_solutions is None:
        from_solutions = [agent.solution_terminal for agent in agents]

    n_cohorts = len(agents)
    # Check memoized chunk size from prior OOMs in this process
    StateCount_key = agents[0].MrkvArray[0].shape[0]
    cache_key = (n_cohorts, StateCount_key)
    if chunk_size is None and cache_key in _VMAP_CHUNK_SIZE_CACHE:
        chunk_size = _VMAP_CHUNK_SIZE_CACHE[cache_key]
        if verbose:
            print(f"[jax-2b-vmap] using cached chunk_size={chunk_size} "
                  f"for (n_cohorts={n_cohorts}, StateCount={StateCount_key})",
                  flush=True)

    if chunk_size is None or chunk_size >= n_cohorts:
        # Try all-at-once first; on OOM, fall back to chunked.
        try:
            si = extract_solve_inputs_stacked(agents, from_solutions=from_solutions)
            res = iterate_cfunc_multicohort_until_convergence(
                si, max_iters=max_iters, tol=tol)
            cNrm_all = np.asarray(res['cNrm'])
            mNrm_all = np.asarray(res['mNrm'])
            bc_all = np.asarray(res['BoroCnstNat_per_i'])
            if verbose:
                print(f"[jax-2b-vmap] all-at-once: n_cohorts={n_cohorts}, "
                      f"n_iters={res['n_iters']}, "
                      f"final_diff={res['final_diff']:.2e}, "
                      f"converged={res['converged']}", flush=True)
        except Exception as e:
            err_str = str(e)
            if "RESOURCE_EXHAUSTED" not in err_str and "out of memory" not in err_str.lower():
                raise
            if verbose:
                print(f"[jax-2b-vmap] all-at-once OOM, falling back to "
                      f"chunk_size=4: {err_str[:100]}...", flush=True)
            chunk_size = 4
            # Remember this for subsequent calls in this process
            _VMAP_CHUNK_SIZE_CACHE[cache_key] = chunk_size
            # Drop into chunked path below
            cNrm_all = mNrm_all = bc_all = None

    if chunk_size is not None and chunk_size < n_cohorts:
        # Chunked vmap: keeps memory bounded.
        cNrm_chunks = []
        mNrm_chunks = []
        bc_chunks = []
        max_iter_used = 0
        max_final_diff = 0.0
        all_converged = True
        n_chunks = (n_cohorts + chunk_size - 1) // chunk_size
        for chunk_idx, start in enumerate(range(0, n_cohorts, chunk_size)):
            end = min(start + chunk_size, n_cohorts)
            agents_chunk = agents[start:end]
            from_sols_chunk = from_solutions[start:end]
            si = extract_solve_inputs_stacked(agents_chunk,
                                                from_solutions=from_sols_chunk)
            res = iterate_cfunc_multicohort_until_convergence(
                si, max_iters=max_iters, tol=tol)
            cNrm_chunks.append(np.asarray(res['cNrm']))
            mNrm_chunks.append(np.asarray(res['mNrm']))
            bc_chunks.append(np.asarray(res['BoroCnstNat_per_i']))
            max_iter_used = max(max_iter_used, res['n_iters'])
            max_final_diff = max(max_final_diff, res['final_diff'])
            all_converged = all_converged and res['converged']
            if verbose:
                print(f"[jax-2b-vmap] chunk {chunk_idx + 1}/{n_chunks} "
                      f"(cohorts {start}-{end - 1}): "
                      f"n_iters={res['n_iters']}, "
                      f"final_diff={res['final_diff']:.2e}", flush=True)
        cNrm_all = np.concatenate(cNrm_chunks, axis=0)
        mNrm_all = np.concatenate(mNrm_chunks, axis=0)
        bc_all = np.concatenate(bc_chunks, axis=0)
        if verbose:
            print(f"[jax-2b-vmap] all chunks done: max iters={max_iter_used}, "
                  f"max final_diff={max_final_diff:.2e}, "
                  f"all converged={all_converged}", flush=True)

    # Need si for shared-param wrapping (Cgrid, BoroCnstArt, CRRA).
    # Re-derive from agent 0 if not set (chunked path).
    si = extract_solve_inputs_stacked([agents[0]],
                                       from_solutions=[from_solutions[0]])

    Cgrid_np = np.asarray(si['Cgrid'])
    BoroCnstArt = float(si['BoroCnstArt'])
    CRRA = float(si['CRRA'])

    per_cohort_solutions = []
    for c_idx in range(n_cohorts):
        cNrm = cNrm_all[c_idx]
        mNrm = mNrm_all[c_idx]
        bc = bc_all[c_idx]
        StateCount = cNrm.shape[0]
        cFuncNow = []
        vPfuncNow = []
        mNrmMinNow = []
        for j in range(StateCount):
            cf = _JAXcFuncWrap(cNrm[j], mNrm[j], bc[j], Cgrid_np, BoroCnstArt)
            cFuncNow.append(cf)
            vPfuncNow.append(_JAXvPfuncWrap(cf, CRRA))
            mNrmMinNow.append(_JAXmNrmMinWrap(bc[j], Cgrid_np, BoroCnstArt))
        sol = ConsumerSolution(cFunc=cFuncNow, vPfunc=vPfuncNow, mNrmMin=mNrmMinNow)
        per_cohort_solutions.append([sol])

    return per_cohort_solutions


def is_enabled():
    """Return True if HAFISCAL_USE_JAX_2B_VMAP=1."""
    return os.environ.get('HAFISCAL_USE_JAX_2B_VMAP', '').lower() in ('1', 'on', 'true')
