"""
Extract / reconstruct HARK ConsumerSolution objects for HAFiscal recession
case.

The HAFiscal cFunc structure (per Markov state j) is:
    LowerEnvelope2D(
        VariableLowerBoundFunc2D(
            LinearInterpOnInterp1D(
                [LinearInterp(m_temp[k], c_temp[k]) for k in range(Mcount)],
                Mgrid,
            ),
            LinearInterp(Mgrid_with_0, BoroCnstNat_with_0),  # lower bound
        ),
        BilinearInterp(  # constraint branch — c <= m - BoroCnstArt
            [[0, 0], [1, 1]],
            [BoroCnstArt, BoroCnstArt + 1.0],
            [0, 1],
        ),
    )

mNrmMin[j] structure:
    UpperEnvelope(BoroCnstNat_func, ConstantFunction(BoroCnstArt))

We extract the numerical arrays only (no HARK objects in the pickle), then
reconstruct using HARK's existing classes on load. This makes the cache
robust to HARK *implementation* changes (e.g., adding new attributes) but
breaks if HARK *renames* these classes — a deliberately loud failure rather
than silent corruption.
"""
from __future__ import annotations
import numpy as np


def extract_eco_solution(eco):
    """Pull numerical state out of every cohort's .solution[0]. Returns
    a plain-dict-of-arrays structure suitable for np.savez or pickle.

    Returns:
        dict with key 'cohorts' = list of per-cohort dicts.
        Each per-cohort dict has cFunc, mNrmMin data per Markov state j.
    """
    cohorts_out = []
    for c_idx, agent in enumerate(eco.agents):
        sol = agent.solution[0]
        n_states = len(sol.cFunc)
        BoroCnstArt = float(agent.BoroCnstArt) if agent.BoroCnstArt is not None else 0.0

        per_state = []
        for j in range(n_states):
            cf_j = sol.cFunc[j]
            # Two supported layouts:
            #  (a) HARK LowerEnvelope2D — the original HAFiscal solver path
            #  (b) _JAXcFuncWrap — produced by the JAX 2B / drop-in solvers
            #      (HAFISCAL_USE_JAX_2B=1 or HAFISCAL_USE_JAX_SOLVER=1).
            # Both layouts hold the same underlying numerical content
            # (cNrm / mNrm / BoroCnstNat tables); we normalize to HARK's
            # extracted form so reconstruction is a single code path.
            is_jaxwrap = (type(cf_j).__name__ == "_JAXcFuncWrap")
            if is_jaxwrap:
                Cgrid_j = np.asarray(cf_j.Cgrid, dtype=np.float64)
                # _x_grids / _f_values already have a 0 prepended at the
                # bottom (matching HAFiscal's HARK extraction convention).
                xInterp_x_lists = [np.asarray(row, dtype=np.float64)
                                   for row in cf_j._x_grids]
                xInterp_y_lists = [np.asarray(row, dtype=np.float64)
                                   for row in cf_j._f_values]
                inner_y_list = Cgrid_j  # Mgrid == Cgrid in HAFiscal
                lower_x = Cgrid_j
                lower_y = np.asarray(cf_j.BoroCnstNat, dtype=np.float64)
            else:
                # Walk the HARK structure (assumes HAFiscal layout — see
                # module docstring). If layout differs, raise loudly.
                if not hasattr(cf_j, "functions") or len(cf_j.functions) != 2:
                    raise ValueError(
                        f"cohort {c_idx} state {j}: cFunc layout unexpected "
                        f"(no 2-func LowerEnvelope2D, not _JAXcFuncWrap); "
                        f"got {type(cf_j).__name__}")
                vlbf = cf_j.functions[0]  # VariableLowerBoundFunc2D
                inner = vlbf.func  # LinearInterpOnInterp1D
                lower = vlbf.lowerBound  # LinearInterp (BoroCnstNat as fn of M)

                # Per-M LinearInterp's x_list and y_list
                xInterp_x_lists = [np.asarray(xi.x_list, dtype=np.float64)
                                   for xi in inner.xInterpolators]
                xInterp_y_lists = [np.asarray(xi.y_list, dtype=np.float64)
                                   for xi in inner.xInterpolators]
                # Note: xInterpolators may have different-length x_lists,
                # so we store them as a list of arrays (not a stacked matrix).
                inner_y_list = np.asarray(inner.y_list, dtype=np.float64)

                lower_x = np.asarray(lower.x_list, dtype=np.float64)
                lower_y = np.asarray(lower.y_list, dtype=np.float64)

            # mNrmMin[j] — UpperEnvelope of BoroCnstNat_func and ConstantFunction(BoroCnstArt)
            # Both HARK and _JAXmNrmMinWrap expose the same logical content;
            # _JAXmNrmMinWrap stores it as BoroCnstNat + Cgrid + BoroCnstArt.
            mNrmMin_j = sol.mNrmMin[j]
            mNrmMin_BoroCnstNat_x = None
            mNrmMin_BoroCnstNat_y = None
            mNrmMin_constant = BoroCnstArt
            if type(mNrmMin_j).__name__ == "_JAXmNrmMinWrap":
                mNrmMin_BoroCnstNat_x = np.asarray(mNrmMin_j.Cgrid, dtype=np.float64)
                mNrmMin_BoroCnstNat_y = np.asarray(mNrmMin_j.BoroCnstNat, dtype=np.float64)
            elif hasattr(mNrmMin_j, "functions") and len(mNrmMin_j.functions) >= 1:
                # First func is the BoroCnstNat LinearInterp
                bc_func = mNrmMin_j.functions[0]
                if hasattr(bc_func, "x_list") and hasattr(bc_func, "y_list"):
                    mNrmMin_BoroCnstNat_x = np.asarray(bc_func.x_list, dtype=np.float64)
                    mNrmMin_BoroCnstNat_y = np.asarray(bc_func.y_list, dtype=np.float64)

            per_state.append({
                "xInterp_x_lists": xInterp_x_lists,  # list of (varying-len,) arrays
                "xInterp_y_lists": xInterp_y_lists,
                "inner_y_list": inner_y_list,
                "lower_x": lower_x,
                "lower_y": lower_y,
                "mNrmMin_BoroCnstNat_x": mNrmMin_BoroCnstNat_x,
                "mNrmMin_BoroCnstNat_y": mNrmMin_BoroCnstNat_y,
                "mNrmMin_constant": mNrmMin_constant,
            })

        # Per-cohort scalars / params needed for reconstruction
        cohorts_out.append({
            "n_states": n_states,
            "BoroCnstArt": BoroCnstArt,
            "CRRA": float(agent.CRRA),
            "per_state": per_state,
        })

    # Also save the eco's CFunc + MacroCFunc state — needed for AD-converged
    # belief reconstruction.
    eco_cfunc_out = None
    if hasattr(eco, "CFunc") and eco.CFunc is not None:
        # eco.CFunc is a list of lists of CRule(intercept, slope)
        N = len(eco.CFunc)
        slopes = np.zeros((N, N), dtype=np.float64)
        intercepts = np.zeros((N, N), dtype=np.float64)
        for i in range(N):
            for j in range(N):
                slopes[i, j] = float(eco.CFunc[i][j].slope)
                intercepts[i, j] = float(eco.CFunc[i][j].intercept)
        eco_cfunc_out = {"slopes": slopes, "intercepts": intercepts}

    return {
        "cohorts": cohorts_out,
        "eco_CFunc": eco_cfunc_out,
    }


def reconstruct_eco_solution(eco, extracted):
    """Inverse of extract_eco_solution.

    Mutates `eco` in place: sets each agent.solution[0] = ConsumerSolution
    with reconstructed cFunc/vPfunc/mNrmMin, and restores eco.CFunc.

    HARK classes are imported lazily (raises ImportError loud-on-mismatch).
    """
    from HARK.ConsumptionSaving.ConsAggShockModel import ConsumerSolution
    from HARK.interpolation import (
        BilinearInterp, ConstantFunction, LinearInterp, LinearInterpOnInterp1D,
        LowerEnvelope2D, MargValueFuncCRRA, UpperEnvelope, VariableLowerBoundFunc2D,
    )
    from AggFiscalModel import CRule

    cohorts = extracted["cohorts"]
    if len(cohorts) != len(eco.agents):
        raise ValueError(
            f"reconstruct: cached cohorts={len(cohorts)} != "
            f"eco.agents={len(eco.agents)}")

    for c_idx, (agent, c_data) in enumerate(zip(eco.agents, cohorts)):
        n_states = c_data["n_states"]
        BoroCnstArt = c_data["BoroCnstArt"]
        CRRA = c_data["CRRA"]

        cFuncNow = []
        vPfuncNow = []
        mNrmMinNow = []

        for j in range(n_states):
            ps = c_data["per_state"][j]
            inner_y_list = ps["inner_y_list"]
            xInterps = [
                LinearInterp(x, y)
                for x, y in zip(ps["xInterp_x_lists"], ps["xInterp_y_lists"])
            ]
            inner = LinearInterpOnInterp1D(xInterps, inner_y_list)
            BoroCnstNat = LinearInterp(ps["lower_x"], ps["lower_y"])
            vlbf = VariableLowerBoundFunc2D(inner, BoroCnstNat)

            # Constraint branch — c <= m - BoroCnstArt
            cFuncCnst = BilinearInterp(
                np.array([[0.0, 0.0], [1.0, 1.0]]),
                np.array([BoroCnstArt, BoroCnstArt + 1.0]),
                np.array([0.0, 1.0]),
            )
            cf_j = LowerEnvelope2D(vlbf, cFuncCnst)
            cFuncNow.append(cf_j)
            vPfuncNow.append(MargValueFuncCRRA(cf_j, CRRA))

            # mNrmMin[j] = UpperEnvelope(BoroCnstNat_func, ConstantFunction(BoroCnstArt))
            if (ps["mNrmMin_BoroCnstNat_x"] is not None
                    and ps["mNrmMin_BoroCnstNat_y"] is not None):
                bc_func_j = LinearInterp(
                    ps["mNrmMin_BoroCnstNat_x"], ps["mNrmMin_BoroCnstNat_y"])
                mNrmMinNow.append(UpperEnvelope(
                    bc_func_j, ConstantFunction(BoroCnstArt)))
            else:
                mNrmMinNow.append(ConstantFunction(BoroCnstArt))

        agent.solution = [ConsumerSolution(
            cFunc=cFuncNow, vPfunc=vPfuncNow, mNrmMin=mNrmMinNow,
        )]

    # Restore eco.CFunc
    eco_cfunc = extracted.get("eco_CFunc")
    if eco_cfunc is not None:
        slopes = eco_cfunc["slopes"]
        intercepts = eco_cfunc["intercepts"]
        N = slopes.shape[0]
        eco.CFunc = [
            [CRule(float(intercepts[i, j]), float(slopes[i, j]))
             for j in range(N)]
            for i in range(N)
        ]
        # Re-attach to each agent
        for agent in eco.agents:
            agent.CFunc = eco.CFunc
