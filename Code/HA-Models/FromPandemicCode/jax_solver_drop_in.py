"""Drop-in JAX replacement for solve_agg_cons_markov_alt.

Usage:
  from jax_solver_drop_in import solve_agg_cons_markov_jax
  agent.solve_one_period = solve_agg_cons_markov_jax

Or via env flag:
  HAFISCAL_USE_JAX_SOLVER=1 ...

The wrapper matches the signature of solve_agg_cons_markov_alt
(AggFiscalModel.py:1704-1887), tabulates HARK callables onto fixed grids,
calls the JAX kernel, and wraps results back into HARK-compatible callables.
"""
from __future__ import annotations
import os
import numpy as np
import jax
import jax.numpy as jnp

from jax_solver_kernel import solve_one_period_jax
from HARK.interpolation_jax import (linear_interp_1d, bilinear_interp,
                              linear_interp_on_interp_1d_general)


# --- Default eval grid for vPfuncNext tabulation ---
_DEFAULT_M_EVAL = np.unique(np.concatenate([
    np.linspace(0.001, 0.1, 100),
    np.linspace(0.1, 1.0, 200),
    np.linspace(1.0, 5.0, 200),
    np.linspace(5.0, 50.0, 200),
]))


def _sniff_elasticity(ADFunc):
    """Recover ADelasticity from ADFunc lambda.
    ADFunc(C, True) = C^elasticity. So elasticity = log(ADFunc(2.0, True)) / log(2.0).
    """
    val = ADFunc(np.asarray(2.0), True)
    if val == 1.0:
        return 0.0  # ADelasticity=0 case
    return float(np.log(float(val)) / np.log(2.0))


def _tabulate_vPfuncNext(solution_next, StateCount, m_eval, C_eval):
    table = np.zeros((StateCount, len(m_eval), len(C_eval)))
    mM, cC = np.meshgrid(m_eval, C_eval, indexing='ij')
    for j in range(StateCount):
        table[j] = solution_next.vPfunc[j](mM, cC)
    return table


def _tabulate_mNrmMinNext(solution_next, StateCount, C_eval):
    table = np.zeros((StateCount, len(C_eval)))
    is_callable = np.zeros(StateCount, dtype=bool)
    scalar = np.zeros(StateCount)
    for j in range(StateCount):
        m = solution_next.mNrmMin[j]
        if isinstance(m, (float, int, np.floating, np.integer)):
            is_callable[j] = False
            scalar[j] = float(m)
            table[j] = float(m) * C_eval
        else:
            is_callable[j] = True
            table[j] = m(C_eval)
    return table, is_callable, scalar


def _extract_IncShk_arrays(IncShkDstn, StateCount):
    max_atoms = max(len(np.asarray(IncShkDstn[j].pmv)) for j in range(StateCount))
    pmv = np.zeros((StateCount, max_atoms))
    perm = np.zeros((StateCount, max_atoms))
    tran = np.zeros((StateCount, max_atoms))
    for j in range(StateCount):
        d = IncShkDstn[j]
        n = len(np.asarray(d.pmv))
        pmv[j, :n] = np.asarray(d.pmv)
        perm[j, :n] = np.asarray(d.atoms[0])
        tran[j, :n] = np.asarray(d.atoms[1])
        perm[j, n:] = 1.0  # avoid div-by-zero (pmv=0 on pad → no contribution)
    return pmv, perm, tran


def _extract_CFunc_arrays(CFunc, StateCount):
    slope = np.zeros((StateCount, StateCount))
    intercept = np.zeros((StateCount, StateCount))
    for i in range(StateCount):
        for j in range(StateCount):
            r = CFunc[i][j]
            slope[i][j] = float(r.slope)
            intercept[i][j] = float(r.intercept)
    return slope, intercept


def _np_linear_interp_on_interp_1d_general(x_grids, y_grid, f_values, x_query, y_query):
    """Vectorized pure-numpy version of linear_interp_on_interp_1d_general.

    For each query: bracket in y_grid; do batched 1-D linear interp in x for each
    of two bracketing rows; linearly blend in y. All operations vectorized.
    """
    x_grids = np.asarray(x_grids)
    y_grid = np.asarray(y_grid)
    f_values = np.asarray(f_values)
    x_query = np.atleast_1d(np.asarray(x_query))
    y_query = np.atleast_1d(np.asarray(y_query))

    Ny, Nx = x_grids.shape
    N = x_query.shape[0]

    # Bracket in y_grid
    y_pos = np.clip(np.searchsorted(y_grid, y_query, side='left'), 1, Ny - 1)
    alpha_y = (y_query - y_grid[y_pos - 1]) / (y_grid[y_pos] - y_grid[y_pos - 1])

    # Gather per-query x_grids and f_values (shape (N, Nx))
    xg_lo = x_grids[y_pos - 1]  # (N, Nx)
    xg_hi = x_grids[y_pos]
    fv_lo = f_values[y_pos - 1]
    fv_hi = f_values[y_pos]

    # Batched 1-D linear interp on xg_lo and xg_hi
    def _interp_batch(xg, fv, xq):
        # xg, fv: (N, Nx); xq: (N,)
        # For each row k: find i_lo such that xg[k, i_lo] <= xq[k] < xg[k, i_lo+1]
        i_lo = np.clip((xg <= xq[:, None]).sum(axis=1) - 1, 0, Nx - 2)
        i_hi = i_lo + 1
        row = np.arange(N)
        x_lo = xg[row, i_lo]
        x_hi = xg[row, i_hi]
        f_lo = fv[row, i_lo]
        f_hi = fv[row, i_hi]
        alpha_x = np.where(x_hi > x_lo, (xq - x_lo) / (x_hi - x_lo), 0.0)
        return (1 - alpha_x) * f_lo + alpha_x * f_hi

    f_lo_eval = _interp_batch(xg_lo, fv_lo, x_query)
    f_hi_eval = _interp_batch(xg_hi, fv_hi, x_query)
    return (1 - alpha_y) * f_lo_eval + alpha_y * f_hi_eval


class _JAXcFuncWrap:
    """HARK-compatible cFunc[j](m, C) callable backed by JAX-solver output tables.

    Implements: c = min(unconstrained(m, C), m - BoroCnstArt)
    Uses pure-numpy linear interp (no JAX dispatch from inside HARK's solve loop).
    """

    def __init__(self, cNrm_i, mNrm_i, BoroCnstNat_i, Cgrid, BoroCnstArt):
        # cNrm_i: (Ccount, aCount), mNrm_i: (Ccount, aCount), BoroCnstNat_i: (Ccount,)
        self.cNrm = np.asarray(cNrm_i)
        self.mNrm = np.asarray(mNrm_i)
        self.BoroCnstNat = np.asarray(BoroCnstNat_i)
        self.Cgrid = np.asarray(Cgrid)
        self.BoroCnstArt = float(BoroCnstArt) if BoroCnstArt is not None else 0.0
        # Precompute shifted grids
        self._x_grids = np.concatenate(
            [np.zeros((self.cNrm.shape[0], 1)),
             self.mNrm - self.BoroCnstNat[:, None]], axis=1)
        self._f_values = np.concatenate(
            [np.zeros((self.cNrm.shape[0], 1)), self.cNrm], axis=1)

    def __call__(self, m, C):
        m_arr = np.asarray(m)
        C_arr = np.asarray(C)
        orig_shape = m_arr.shape
        m_flat = np.atleast_1d(m_arr).flatten()
        C_flat = np.atleast_1d(C_arr).flatten()
        if C_flat.shape[0] == 1 and m_flat.shape[0] > 1:
            C_flat = np.broadcast_to(C_flat, m_flat.shape)
        if m_flat.shape[0] == 1 and C_flat.shape[0] > 1:
            m_flat = np.broadcast_to(m_flat, C_flat.shape)

        # Shift m by BoroCnstNat at the query C
        bn_at_C = np.interp(C_flat, self.Cgrid, self.BoroCnstNat)
        m_shifted = m_flat - bn_at_C

        c_unc = _np_linear_interp_on_interp_1d_general(
            self._x_grids, self.Cgrid, self._f_values, m_shifted, C_flat)
        c_cnst = m_flat - self.BoroCnstArt
        c_out = np.minimum(c_unc, c_cnst)
        # Apply NaN for m < BoroCnstArt (HARK convention)
        c_out = np.where(m_flat < self.BoroCnstArt, np.nan, c_out)
        if orig_shape == ():
            return float(c_out[0])
        return c_out.reshape(orig_shape)

    def derivativeX(self, m, C):
        """Used by HARK for marginal value computation. Finite-difference approximation."""
        h = 1e-5
        return (self(m + h, C) - self(m - h, C)) / (2 * h)

    def distance(self, other):
        """HARK MetricObject distance: max abs diff in cNrm table."""
        if not isinstance(other, _JAXcFuncWrap):
            return float('inf')
        if self.cNrm.shape != other.cNrm.shape:
            return float('inf')
        return float(np.max(np.abs(self.cNrm - other.cNrm)))


class _JAXvPfuncWrap:
    """HARK-compatible vPfunc[j](m, C) = u'(cFunc[j](m, C)) = c^(-CRRA)."""

    def __init__(self, cFuncWrap, CRRA):
        self.cFunc = cFuncWrap
        self.CRRA = float(CRRA)

    def __call__(self, m, C):
        c = self.cFunc(m, C)
        return np.maximum(c, 1e-12) ** (-self.CRRA)

    def distance(self, other):
        """Defer to underlying cFunc.distance."""
        if not isinstance(other, _JAXvPfuncWrap):
            return float('inf')
        return self.cFunc.distance(other.cFunc)


class _JAXmNrmMinWrap:
    """HARK-compatible mNrmMin[j](C) = max(BoroCnstNat(C), BoroCnstArt)."""

    def __init__(self, BoroCnstNat_i, Cgrid, BoroCnstArt):
        self.BoroCnstNat = np.asarray(BoroCnstNat_i)
        self.Cgrid = np.asarray(Cgrid)
        self.BoroCnstArt = float(BoroCnstArt) if BoroCnstArt is not None else 0.0

    def __call__(self, C):
        C_arr = np.atleast_1d(np.asarray(C))
        bn = np.interp(C_arr, self.Cgrid, self.BoroCnstNat)
        return np.maximum(bn, self.BoroCnstArt)


def solve_agg_cons_markov_jax(
    solution_next, IncShkDstn, LivPrb, DiscFac, CRRA, Rfree, PermGroFac,
    MrkvArray, BoroCnstArt, aXtraGrid, Cgrid, CFunc, ADFunc,
    num_experiment_periods, num_base_MrkvStates,
):
    """Drop-in replacement for solve_agg_cons_markov_alt using JAX kernel.

    Signature matches AggFiscalModel.py:1704. Tabulates HARK callables onto
    fixed grids, calls JAX kernel, returns ConsumerSolution with
    HARK-compatible callable wrappers.
    """
    from HARK.ConsumptionSaving.ConsAggShockModel import ConsumerSolution

    StateCount = MrkvArray.shape[0]
    Ccount = Cgrid.size

    m_eval = _DEFAULT_M_EVAL
    C_eval = np.asarray(Cgrid)

    vPfuncNext_table = _tabulate_vPfuncNext(solution_next, StateCount, m_eval, C_eval)
    mNrmMinNext_table, mNrmMin_is_callable, mNrmMin_scalar = _tabulate_mNrmMinNext(
        solution_next, StateCount, C_eval)

    IncShk_pmv, IncShk_perm, IncShk_tran = _extract_IncShk_arrays(IncShkDstn, StateCount)
    CFunc_slope, CFunc_intercept = _extract_CFunc_arrays(CFunc, StateCount)

    ADelasticity = _sniff_elasticity(ADFunc)
    RecState_per_state = np.array(
        [((j // num_base_MrkvStates) % 2 == 1) for j in range(StateCount)],
        dtype=np.int32)

    result = solve_one_period_jax(
        jnp.asarray(vPfuncNext_table),
        jnp.asarray(m_eval), jnp.asarray(C_eval),
        jnp.asarray(mNrmMinNext_table),
        jnp.asarray(mNrmMin_is_callable),
        jnp.asarray(mNrmMin_scalar),
        jnp.asarray(IncShk_pmv),
        jnp.asarray(IncShk_perm),
        jnp.asarray(IncShk_tran),
        jnp.asarray(LivPrb),
        float(DiscFac), float(CRRA),
        jnp.asarray(Rfree),
        jnp.asarray(PermGroFac),
        jnp.asarray(MrkvArray),
        float(BoroCnstArt) if BoroCnstArt is not None else 0.0,
        jnp.asarray(aXtraGrid),
        jnp.asarray(Cgrid),
        jnp.asarray(CFunc_slope),
        jnp.asarray(CFunc_intercept),
        ADelasticity,
        jnp.asarray(RecState_per_state),
    )

    cNrm = np.asarray(result['cNrm'])              # (StateCount, Ccount, aCount)
    mNrm = np.asarray(result['mNrm'])
    BoroCnstNat_per_i = np.asarray(result['BoroCnstNat_per_i'])

    # Wrap per-state results
    cFuncNow = []
    vPfuncNow = []
    mNrmMinNow = []
    for j in range(StateCount):
        cf = _JAXcFuncWrap(cNrm[j], mNrm[j], BoroCnstNat_per_i[j], Cgrid, BoroCnstArt)
        cFuncNow.append(cf)
        vPfuncNow.append(_JAXvPfuncWrap(cf, CRRA))
        mNrmMinNow.append(_JAXmNrmMinWrap(BoroCnstNat_per_i[j], Cgrid, BoroCnstArt))

    return ConsumerSolution(cFunc=cFuncNow, vPfunc=vPfuncNow, mNrmMin=mNrmMinNow)


def install_jax_solver(agent):
    """Install JAX solver on a HAFiscal agent.

    Replaces agent.solve_one_period with the JAX implementation. The numpy
    reference (solve_agg_cons_markov_alt) is preserved as agent._solve_one_period_numpy.
    """
    if not hasattr(agent, '_solve_one_period_numpy'):
        agent._solve_one_period_numpy = agent.solve_one_period
    agent.solve_one_period = solve_agg_cons_markov_jax


def maybe_install_via_env(eco):
    """If HAFISCAL_USE_JAX_SOLVER=1, install JAX solver on all agents in eco."""
    if os.environ.get('HAFISCAL_USE_JAX_SOLVER', '0') == '1':
        for agent in eco.agents:
            install_jax_solver(agent)
        print(f"[jax_solver] installed on {len(eco.agents)} agents", flush=True)
        return True
    return False
