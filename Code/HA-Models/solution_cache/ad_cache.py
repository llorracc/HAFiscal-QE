"""
AD-converged result cache.

The single-`eco.solve()` cache (cache.py) helps when a script re-runs
HARK's backward induction with the SAME CFunc belief. But HAFiscal's AD
loop calls eco.solve() ~10 times per AD run with DIFFERENT CFunc beliefs
each iter — so the per-`eco.solve()` cache only saves the first solve
(and even then only if a downstream script re-uses that exact key).

This module caches the FULL AD-converged output of
solve_ad_recession_jax_multicohort:
  - eco.agents[c].solution[0] for all cohorts (converged cFunc/vPfunc/mNrmMin)
  - eco.CFunc (converged AD belief)
  - final_Cratio_hist, final_AggCons, final_AggIncome
  - per_cohort_cLvl panels (T, N_c) — needed for welfare cells
  - per_cohort_AggInc, cohort_weights
  - iter_history (for diagnostics)

On a cache hit, the entire AD loop (10× eco.solve() + JAX MC per iter)
is skipped. At Baseline 5x this turns ~30 min into ~1 s.

Toggle: same `HAFISCAL_USE_SOLUTION_CACHE=1` env var as the per-solve
cache. Off by default.
"""
from __future__ import annotations
import os
import pickle
import sys
import time

try:
    from .cache import (
        USE_CACHE_ENV_VAR, _atomic_pickle_write, _atomic_json_write,
        _parametrization_name, cache_path_for_key,
        _warn_provenance_mismatch,
    )
    from .keys import (
        gather_solve_inputs, hash_solve_inputs, parametrization_tag,
    )
    from .serialize import extract_eco_solution, reconstruct_eco_solution
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cache import (
        USE_CACHE_ENV_VAR, _atomic_pickle_write, _atomic_json_write,
        _parametrization_name, cache_path_for_key,
        _warn_provenance_mismatch,
    )
    from keys import (
        gather_solve_inputs, hash_solve_inputs, parametrization_tag,
    )
    from serialize import extract_eco_solution, reconstruct_eco_solution


def _ad_cache_key(eco, shock_type, mc_method, seeds, use_shuffle,
                    init_panel_method, agent_count_per_cohort,
                    num_max_iterations, convergence_cutoff):
    """Key for AD-converged result. Extends per-solve key with AD-specific
    parameters (max-iter, tol) that affect the convergence trajectory."""
    inputs = gather_solve_inputs(
        eco, shock_type=shock_type, mc_method=mc_method, seeds=seeds,
        use_shuffle=use_shuffle, init_panel_method=init_panel_method,
        agent_count_per_cohort=agent_count_per_cohort,
    )
    inputs["ad_outer"] = {
        "num_max_iterations": int(num_max_iterations),
        "convergence_cutoff": float(convergence_cutoff),
        "result_type": "ad_converged",  # disambiguates from per-solve key
    }
    return hash_solve_inputs(inputs), inputs


def _ad_cache_path(parametrization, shock_type, human_tag, key,
                    create_dir=False):
    """Same layout as per-solve cache, but with 'ad_' prefix in filename
    to disambiguate the two cache types."""
    short = key[:8]
    dir_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        parametrization, shock_type,
    )
    if create_dir:
        os.makedirs(dir_path, exist_ok=True)
    pkl_path = os.path.join(dir_path, f"ad_{human_tag}__{short}.pkl")
    meta_path = os.path.join(dir_path, f"ad_{human_tag}__{short}.meta.json")
    return pkl_path, meta_path


def _save_ad_result(eco, result, key, inputs, pkl_path, meta_path):
    """Save extracted eco state + AD outputs atomically."""
    extracted_eco = extract_eco_solution(eco)
    payload = {
        "version": 1,
        "key": key,
        "result_type": "ad_converged",
        "extracted_eco": extracted_eco,
        # Pickle the result dict's numerical contents directly (no HARK objects)
        "result": {
            "final_Cratio_hist": result["final_Cratio_hist"],
            "final_AggCons": result["final_AggCons"],
            "final_AggIncome": result.get("final_AggIncome"),
            "final_cLvl_all_splurge": result.get("final_cLvl_all_splurge"),
            "per_cohort_cLvl": result.get("per_cohort_cLvl"),
            "per_cohort_AggInc": result.get("per_cohort_AggInc"),
            "cohort_weights": result.get("cohort_weights"),
            "converged": result.get("converged"),
            "iter_history": [
                # Strip out 'cohort_times' which can be non-pickleable types
                {k: v for k, v in it.items() if k != "cohort_times"}
                for it in result.get("iter_history", [])
            ],
            "wall_time": result.get("wall_time"),
        },
        "saved_at": time.time(),
    }
    _atomic_pickle_write(pkl_path, payload)
    meta = {
        "version": 1,
        "key": key,
        "result_type": "ad_converged",
        "inputs": inputs,
        "saved_at": time.time(),
        "pkl_filename": os.path.basename(pkl_path),
        "wall_time": result.get("wall_time"),
        "converged": result.get("converged"),
        "n_iters": len(result.get("iter_history", [])),
    }
    _atomic_json_write(meta_path, meta)


def _load_ad_result(eco, pkl_path, meta_path=None):
    """Load cached AD result, reconstruct eco state, return result dict.
    Optionally pass the .meta.json path to enable provenance-mismatch warnings."""
    if meta_path is not None:
        _warn_provenance_mismatch(meta_path, label="solution_cache:AD")
    with open(pkl_path, "rb") as f:
        payload = pickle.load(f)
    if payload.get("version") != 1:
        raise ValueError(
            f"ad-cache version mismatch: got {payload.get('version')}, want 1")
    if payload.get("result_type") != "ad_converged":
        raise ValueError(
            f"ad-cache result_type mismatch: got {payload.get('result_type')}")
    reconstruct_eco_solution(eco, payload["extracted_eco"])
    return payload["result"]


def cached_solve_ad_recession(
        ctx, base_AggCons, num_max_iterations, convergence_cutoff,
        shock_type="recession",
        mc_method="jax_mc_2d_vmap",
        use_shuffle=False, init_panels=None,
        seeds=(0, 1, 2, 3), verbose=True,
        force_solve=False,
        init_panel_method=None,
        agent_count_per_cohort=None):
    """Drop-in cached wrapper for solve_ad_recession_jax_multicohort.

    Caches the FULL AD-converged output. On hit: skip entire AD loop,
    reconstruct eco state + return cached result dict.

    Args mirror solve_ad_recession_jax_multicohort, plus:
        mc_method: tag for the MC method used during AD (in cache key).
            Default 'jax_mc_2d_vmap' since this wraps the JAX multicohort.
        init_panel_method: tag for how init_panels were generated.
            Default depends on whether init_panels is None.
        agent_count_per_cohort: tuple of per-cohort N. Default = current
            agents' AgentCount values.
        force_solve: skip cache; always solve + save.

    Returns dict matching solve_ad_recession_jax_multicohort signature.
    """
    eco = ctx["AggEco"]

    # Cache off: pass through
    if os.environ.get(USE_CACHE_ENV_VAR, "0") != "1":
        from jax_mc_ad_multicohort import solve_ad_recession_jax_multicohort
        return solve_ad_recession_jax_multicohort(
            eco, base_AggCons,
            num_max_iterations=num_max_iterations,
            convergence_cutoff=convergence_cutoff,
            shock_type=shock_type, use_shuffle=use_shuffle,
            init_panels=init_panels, seeds=seeds, verbose=verbose,
        )

    # Determine init_panel_method tag
    if init_panel_method is None:
        init_panel_method = "explicit" if init_panels is not None else "hark_ref"

    # Compute key
    key, inputs = _ad_cache_key(
        eco, shock_type=shock_type, mc_method=mc_method, seeds=seeds,
        use_shuffle=use_shuffle, init_panel_method=init_panel_method,
        agent_count_per_cohort=agent_count_per_cohort,
        num_max_iterations=num_max_iterations,
        convergence_cutoff=convergence_cutoff,
    )

    pname = _parametrization_name(eco)
    seed_offset = seeds[0] if seeds else 0
    tag = parametrization_tag(
        eco, mc_method=mc_method, use_shuffle=use_shuffle,
        agent_count_per_cohort=agent_count_per_cohort,
        seed_offset=seed_offset)
    pkl_path, meta_path = _ad_cache_path(
        pname, shock_type, tag, key, create_dir=True)

    # Hit
    if (not force_solve) and os.path.exists(pkl_path):
        if verbose:
            print(f"[solution_cache:AD] HIT: {pkl_path}", flush=True)
        t0 = time.time()
        result = _load_ad_result(eco, pkl_path, meta_path=meta_path)
        if verbose:
            print(f"  loaded in {time.time()-t0:.2f}s; converged="
                  f"{result.get('converged')}, "
                  f"n_iters={len(result.get('iter_history', []))}", flush=True)
        return result

    # Miss: solve + save
    if verbose:
        print(f"[solution_cache:AD] MISS: running AD + saving to {pkl_path}",
              flush=True)
    from jax_mc_ad_multicohort import solve_ad_recession_jax_multicohort
    result = solve_ad_recession_jax_multicohort(
        eco, base_AggCons,
        num_max_iterations=num_max_iterations,
        convergence_cutoff=convergence_cutoff,
        shock_type=shock_type, use_shuffle=use_shuffle,
        init_panels=init_panels, seeds=seeds, verbose=verbose,
    )
    _save_ad_result(eco, result, key, inputs, pkl_path, meta_path)
    return result


# --------------------------------------------------------------------------
# HARK-AD wrapper (covers eco.solve_ad_recession + the 3 wrapper methods:
# solve_ad_check_recession / solve_ad_ui_extension_recession / solve_ad_recession_taxcut,
# which are all thin wrappers around solve_ad_recession with different shock_type).
#
# Unlike the JAX path, HARK's solve_ad_recession ends with `store_ADsolution(name)`,
# populating eco.stored_solutions[name]. We cache that snapshot directly so the
# downstream restore_ADsolution(name) works unchanged.
# --------------------------------------------------------------------------


def _save_hark_ad_result(eco, name, key, inputs, pkl_path, meta_path):
    """Save eco.stored_solutions[name] + post-AD eco state atomically."""
    extracted_eco = extract_eco_solution(eco)  # cFunc/mNrmMin per cohort + eco.CFunc
    stored = eco.stored_solutions[name]
    # The stored snapshot's CFunc usually equals eco.CFunc at this point, but
    # extract it independently in case of any caller-side mutation between
    # store_ADsolution and our save.
    N = len(stored.CFunc)
    import numpy as np
    stored_slopes = np.zeros((N, N), dtype=np.float64)
    stored_intercepts = np.zeros((N, N), dtype=np.float64)
    for i in range(N):
        for j in range(N):
            stored_slopes[i, j] = float(stored.CFunc[i][j].slope)
            stored_intercepts[i, j] = float(stored.CFunc[i][j].intercept)

    # Per-cohort stored agent_solutions: re-use the same numerical extractor
    # we use for eco.agents (they're the same shape). Walk the
    # stored.agent_solutions[i][0] structure, mirroring extract_eco_solution
    # but reading from the snapshot rather than the live agent.
    cohort_snapshots = []
    for i, agent in enumerate(eco.agents):
        sol = stored.agent_solutions[i][0]
        # Reuse extract by temporarily pointing agent.solution at sol — avoids
        # duplicating the (verbose) extraction code.
        original = agent.solution
        agent.solution = [sol]
        try:
            single = extract_eco_solution_single_cohort(agent)
        finally:
            agent.solution = original
        cohort_snapshots.append(single)

    payload = {
        "version": 1,
        "key": key,
        "result_type": "hark_ad_converged",
        "extracted_eco": extracted_eco,
        "stored": {
            "name": name,
            "ADelasticity": float(stored.ADelasticity),
            "CFunc_slopes": stored_slopes,
            "CFunc_intercepts": stored_intercepts,
            "cohort_snapshots": cohort_snapshots,
        },
        "saved_at": time.time(),
    }
    _atomic_pickle_write(pkl_path, payload)
    meta = {
        "version": 1,
        "key": key,
        "result_type": "hark_ad_converged",
        "inputs": inputs,
        "saved_at": time.time(),
        "pkl_filename": os.path.basename(pkl_path),
    }
    _atomic_json_write(meta_path, meta)


def extract_eco_solution_single_cohort(agent):
    """Extract the numerical state of a single cohort's solution[0]. Used by
    the HARK-AD cache to snapshot eco.stored_solutions[name].agent_solutions[i][0]
    (which is structurally identical to agent.solution[0])."""
    import numpy as np
    sol = agent.solution[0]
    n_states = len(sol.cFunc)
    BoroCnstArt = float(agent.BoroCnstArt) if agent.BoroCnstArt is not None else 0.0

    per_state = []
    for j in range(n_states):
        cf_j = sol.cFunc[j]
        # Two supported layouts: HARK LowerEnvelope2D or _JAXcFuncWrap
        # (see serialize.extract_eco_solution for the same dispatch).
        is_jaxwrap = (type(cf_j).__name__ == "_JAXcFuncWrap")
        if is_jaxwrap:
            Cgrid_j = np.asarray(cf_j.Cgrid, dtype=np.float64)
            xInterp_x_lists = [np.asarray(row, dtype=np.float64)
                               for row in cf_j._x_grids]
            xInterp_y_lists = [np.asarray(row, dtype=np.float64)
                               for row in cf_j._f_values]
            inner_y_list = Cgrid_j
            lower_x = Cgrid_j
            lower_y = np.asarray(cf_j.BoroCnstNat, dtype=np.float64)
        else:
            if not hasattr(cf_j, "functions") or len(cf_j.functions) != 2:
                raise ValueError(
                    f"single-cohort extract: state {j} cFunc layout "
                    f"unexpected (got {type(cf_j).__name__})")
            vlbf = cf_j.functions[0]
            inner = vlbf.func
            lower = vlbf.lowerBound

            xInterp_x_lists = [np.asarray(xi.x_list, dtype=np.float64)
                               for xi in inner.xInterpolators]
            xInterp_y_lists = [np.asarray(xi.y_list, dtype=np.float64)
                               for xi in inner.xInterpolators]
            inner_y_list = np.asarray(inner.y_list, dtype=np.float64)
            lower_x = np.asarray(lower.x_list, dtype=np.float64)
            lower_y = np.asarray(lower.y_list, dtype=np.float64)

        mNrmMin_j = sol.mNrmMin[j]
        mNrmMin_BoroCnstNat_x = None
        mNrmMin_BoroCnstNat_y = None
        if type(mNrmMin_j).__name__ == "_JAXmNrmMinWrap":
            mNrmMin_BoroCnstNat_x = np.asarray(mNrmMin_j.Cgrid, dtype=np.float64)
            mNrmMin_BoroCnstNat_y = np.asarray(mNrmMin_j.BoroCnstNat, dtype=np.float64)
        elif hasattr(mNrmMin_j, "functions") and len(mNrmMin_j.functions) >= 1:
            bc_func = mNrmMin_j.functions[0]
            if hasattr(bc_func, "x_list") and hasattr(bc_func, "y_list"):
                mNrmMin_BoroCnstNat_x = np.asarray(bc_func.x_list, dtype=np.float64)
                mNrmMin_BoroCnstNat_y = np.asarray(bc_func.y_list, dtype=np.float64)

        per_state.append({
            "xInterp_x_lists": xInterp_x_lists,
            "xInterp_y_lists": xInterp_y_lists,
            "inner_y_list": inner_y_list,
            "lower_x": lower_x,
            "lower_y": lower_y,
            "mNrmMin_BoroCnstNat_x": mNrmMin_BoroCnstNat_x,
            "mNrmMin_BoroCnstNat_y": mNrmMin_BoroCnstNat_y,
            "mNrmMin_constant": BoroCnstArt,
        })

    return {
        "n_states": n_states,
        "BoroCnstArt": BoroCnstArt,
        "CRRA": float(agent.CRRA),
        "per_state": per_state,
    }


def _reconstruct_cohort_solution(c_data):
    """Inverse of extract_eco_solution_single_cohort. Returns a list with
    one ConsumerSolution (HAFiscal uses time_inv = single-period infinite-horizon)."""
    import numpy as np
    from HARK.ConsumptionSaving.ConsAggShockModel import ConsumerSolution
    from HARK.interpolation import (
        BilinearInterp, ConstantFunction, LinearInterp, LinearInterpOnInterp1D,
        LowerEnvelope2D, MargValueFuncCRRA, UpperEnvelope, VariableLowerBoundFunc2D,
    )
    n_states = c_data["n_states"]
    BoroCnstArt = c_data["BoroCnstArt"]
    CRRA = c_data["CRRA"]
    cFuncNow, vPfuncNow, mNrmMinNow = [], [], []
    for j in range(n_states):
        ps = c_data["per_state"][j]
        xInterps = [LinearInterp(x, y)
                    for x, y in zip(ps["xInterp_x_lists"], ps["xInterp_y_lists"])]
        inner = LinearInterpOnInterp1D(xInterps, ps["inner_y_list"])
        BoroCnstNat = LinearInterp(ps["lower_x"], ps["lower_y"])
        vlbf = VariableLowerBoundFunc2D(inner, BoroCnstNat)
        cFuncCnst = BilinearInterp(
            np.array([[0.0, 0.0], [1.0, 1.0]]),
            np.array([BoroCnstArt, BoroCnstArt + 1.0]),
            np.array([0.0, 1.0]),
        )
        cf_j = LowerEnvelope2D(vlbf, cFuncCnst)
        cFuncNow.append(cf_j)
        vPfuncNow.append(MargValueFuncCRRA(cf_j, CRRA))
        if (ps["mNrmMin_BoroCnstNat_x"] is not None
                and ps["mNrmMin_BoroCnstNat_y"] is not None):
            bc_func_j = LinearInterp(
                ps["mNrmMin_BoroCnstNat_x"], ps["mNrmMin_BoroCnstNat_y"])
            mNrmMinNow.append(UpperEnvelope(bc_func_j, ConstantFunction(BoroCnstArt)))
        else:
            mNrmMinNow.append(ConstantFunction(BoroCnstArt))
    return [ConsumerSolution(cFunc=cFuncNow, vPfunc=vPfuncNow, mNrmMin=mNrmMinNow)]


def _load_hark_ad_result(eco, name, pkl_path, meta_path=None):
    """Load cached HARK-AD result. Mutates eco in-place so that:
      - eco.agents[i].solution = reconstructed converged solution
      - eco.CFunc = reconstructed converged AD belief
      - eco.stored_solutions[name] is populated (so caller's
        restore_ADsolution(name) works unchanged)
    """
    if meta_path is not None:
        _warn_provenance_mismatch(meta_path, label="solution_cache:HARK-AD")
    with open(pkl_path, "rb") as f:
        payload = pickle.load(f)
    if payload.get("version") != 1:
        raise ValueError(
            f"hark-ad cache version mismatch: got {payload.get('version')}")
    if payload.get("result_type") != "hark_ad_converged":
        raise ValueError(
            f"hark-ad cache result_type mismatch: got {payload.get('result_type')}")

    # Step 1: reconstruct the live eco state (sets agent.solution + eco.CFunc).
    reconstruct_eco_solution(eco, payload["extracted_eco"])

    # Step 2: populate eco.stored_solutions[name] with the cached snapshot.
    # The downstream pattern in welfare6_scenario.run_recession_AD is:
    #     <wrapper resolves above to call solve_ad_recession>
    #     eco.switch_shock_type(shock_type)
    #     eco.restore_ADsolution(name=shock_type)
    # which needs eco.stored_solutions[name].CFunc / ADelasticity / agent_solutions.
    from AggFiscalModel import CRule
    import numpy as np

    if not hasattr(eco, "stored_solutions"):
        eco.stored_solutions = {}

    stored = payload["stored"]
    slopes = stored["CFunc_slopes"]
    intercepts = stored["CFunc_intercepts"]
    N = slopes.shape[0]
    stored_CFunc = [
        [CRule(float(intercepts[i, j]), float(slopes[i, j]))
         for j in range(N)]
        for i in range(N)
    ]

    # Use HARK's Model class as the namespace object (matches what
    # AggregateDemandEconomy.store_ADsolution does)
    from HARK.core import Model
    snap = Model()
    snap.CFunc = stored_CFunc
    snap.ADelasticity = float(stored["ADelasticity"])
    snap.agent_solutions = [
        _reconstruct_cohort_solution(cs) for cs in stored["cohort_snapshots"]
    ]
    eco.stored_solutions[name] = snap


def cached_solve_ad_recession_hark(
        ctx, num_max_iterations, convergence_cutoff,
        shock_type, name=None,
        seeds=(0,), use_shuffle=False,
        agent_count_per_cohort=None,
        verbose=True, force_solve=False):
    """Cache wrapper for eco.solve_ad_recession (HARK MC AD path).

    Drop-in replacement for the four HARK-AD methods on AggregateDemandEconomy:
        - solve_ad_recession              (shock_type='recession')
        - solve_ad_check_recession        (shock_type='recessionCheck')
        - solve_ad_ui_extension_recession (shock_type='recessionUI')
        - solve_ad_recession_taxcut       (shock_type='recessionTaxCut')

    On hit: reconstructs the post-AD eco state AND populates
    eco.stored_solutions[name] so that downstream restore_ADsolution works
    unchanged.

    On miss: calls eco.solve_ad_recession(num_max_iterations, convergence_cutoff,
    name, shock_type) — which itself calls store_ADsolution(name) at the end —
    then saves the snapshot.

    Args:
        ctx: dict containing 'AggEco'.
        num_max_iterations, convergence_cutoff: AD-loop params.
        shock_type: 'recession' / 'recessionCheck' / 'recessionUI' / 'recessionTaxCut'.
        name: name for store_ADsolution. Defaults to shock_type.
        seeds, use_shuffle, agent_count_per_cohort: forward-sim params (in cache key).
        force_solve: skip cache; always solve + save.
    """
    eco = ctx["AggEco"]
    if name is None:
        name = shock_type

    # Cache off → pass through
    if os.environ.get(USE_CACHE_ENV_VAR, "0") != "1":
        eco.solve_ad_recession(
            num_max_iterations=num_max_iterations,
            convergence_cutoff=convergence_cutoff,
            name=name, shock_type=shock_type,
        )
        return

    # Compute key (mc_method='hark_mc' distinguishes from JAX path entries)
    key, inputs = _ad_cache_key(
        eco, shock_type=shock_type, mc_method="hark_mc", seeds=seeds,
        use_shuffle=use_shuffle, init_panel_method="hark_internal",
        agent_count_per_cohort=agent_count_per_cohort,
        num_max_iterations=num_max_iterations,
        convergence_cutoff=convergence_cutoff,
    )

    pname = _parametrization_name(eco)
    seed_offset = seeds[0] if seeds else 0
    tag = parametrization_tag(
        eco, mc_method="hark_mc", use_shuffle=use_shuffle,
        agent_count_per_cohort=agent_count_per_cohort,
        seed_offset=seed_offset)
    # Use a different filename prefix so HARK-AD entries don't collide with
    # JAX-AD entries (different result_type, different reconstruction logic).
    pkl_path, meta_path = _ad_cache_path(
        pname, shock_type, f"hark_{tag}", key, create_dir=True)

    if (not force_solve) and os.path.exists(pkl_path):
        if verbose:
            print(f"[solution_cache:HARK-AD] HIT: {pkl_path}", flush=True)
        t0 = time.time()
        _load_hark_ad_result(eco, name, pkl_path, meta_path=meta_path)
        if verbose:
            print(f"  loaded in {time.time()-t0:.2f}s; "
                  f"reconstructed stored_solutions['{name}']", flush=True)
        return

    if verbose:
        print(f"[solution_cache:HARK-AD] MISS: running solve_ad_recession + "
              f"saving to {pkl_path}", flush=True)
    eco.solve_ad_recession(
        num_max_iterations=num_max_iterations,
        convergence_cutoff=convergence_cutoff,
        name=name, shock_type=shock_type,
    )
    _save_hark_ad_result(eco, name, key, inputs, pkl_path, meta_path)
