"""Drop-in 2B integration: replace HARK's `solve_agent` iter loop entirely
with the JAX `lax.while_loop` per-agent solve.

Where `jax_solver_drop_in.solve_agg_cons_markov_jax` replaces ONE backward-
induction step (still called repeatedly from HARK's Python iter loop), this
module replaces the ENTIRE iter loop in a single JIT'd `lax.while_loop`.

Usage (via env flag in AggregateDemandEconomy.solve):

    HAFISCAL_USE_JAX_2B=1 python welfare6_scenario.py --scenario base

Programmatic:

    from jax_solver_iterated_drop_in import solve_to_convergence_consumer_solution
    agent.pre_solve()
    agent.solution = solve_to_convergence_consumer_solution(
        agent, from_solution=prev_solution_for_warm_start, max_iters=500, tol=1e-7)
    agent.post_solve()
"""
from __future__ import annotations
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
# Need access to jax_solver_drop_in (wrappers) + jax_solver_kernel + this dir's
# jax_solver_iterated (the new while_loop kernel).
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "FromPandemicCode"))


def solve_to_convergence_consumer_solution(
        agent,
        max_iters=500,
        tol=1e-7,
        from_solution=None,
        verbose=False):
    """Drop-in for `HARK.core.solve_agent(agent, False, from_solution=...)`
    on a HAFiscal recession-state-space agent.

    Args:
        agent: HAFiscal AggFiscalType, post-pre_solve().
        max_iters: hard cap for the JAX while_loop (in case of non-convergence).
        tol: cFunc-table-diff convergence threshold.
        from_solution: previous ConsumerSolution to use as the initial belief
            (warm-start). Default: agent.solution_terminal (cold start).
        verbose: print n_iters + final diff on completion.

    Returns:
        list[ConsumerSolution] of length 1 (matches HARK's `solve_agent`
        return shape for infinite-horizon T_cycle=1, cycles=0 problem).
    """
    import jax
    jax.config.update("jax_enable_x64", True)

    from jax_solver_iterated import (
        extract_solve_inputs,
        iterate_cfunc_jax_until_convergence,
    )
    from jax_solver_drop_in import (
        _JAXcFuncWrap, _JAXvPfuncWrap, _JAXmNrmMinWrap,
    )
    from HARK.ConsumptionSaving.ConsAggShockModel import ConsumerSolution

    if from_solution is None:
        from_solution = agent.solution_terminal

    # 1. Extract all kernel arrays from the agent + initial belief
    inputs = extract_solve_inputs(agent, solution_initial=from_solution)

    # 2. Run the JAX while_loop to convergence (or max_iters)
    res = iterate_cfunc_jax_until_convergence(
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

    if verbose:
        print(f"[jax-2b] n_iters={res['n_iters']}, "
              f"final_diff={res['final_diff']:.2e}, "
              f"converged={res['converged']}", flush=True)

    # 3. Wrap output tables as HARK-compatible callables
    cNrm = np.asarray(res['cNrm'])              # (StateCount, Ccount, aCount)
    mNrm = np.asarray(res['mNrm'])
    BoroCnstNat_per_i = np.asarray(res['BoroCnstNat_per_i'])

    StateCount = cNrm.shape[0]
    Cgrid_np = np.asarray(agent.Cgrid)
    BoroCnstArt = float(agent.BoroCnstArt) if agent.BoroCnstArt is not None else 0.0
    CRRA = float(agent.CRRA)

    cFuncNow = []
    vPfuncNow = []
    mNrmMinNow = []
    for j in range(StateCount):
        cf = _JAXcFuncWrap(cNrm[j], mNrm[j], BoroCnstNat_per_i[j],
                           Cgrid_np, BoroCnstArt)
        cFuncNow.append(cf)
        vPfuncNow.append(_JAXvPfuncWrap(cf, CRRA))
        mNrmMinNow.append(_JAXmNrmMinWrap(BoroCnstNat_per_i[j],
                                          Cgrid_np, BoroCnstArt))

    sol = ConsumerSolution(cFunc=cFuncNow, vPfunc=vPfuncNow, mNrmMin=mNrmMinNow)
    return [sol]


def is_enabled():
    """Return True if HAFISCAL_USE_JAX_2B is set in the env."""
    return os.environ.get('HAFISCAL_USE_JAX_2B', '').lower() in ('1', 'on', 'true')
