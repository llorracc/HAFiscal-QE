"""
Cache API: cache key, save, load, drop-in cached_eco_solve.

On-disk layout:
    Code/HA-Models/solution_cache/
        __init__.py, cache.py, serialize.py, keys.py   # module files
        <parametrization>/
            <shock_type>/
                <human-tag>__<short-hash>.pkl          # gitignored
                <human-tag>__<short-hash>.meta.json    # gitignored

Atomic writes: pickle -> .pkl.tmp -> atomic rename to .pkl. Concurrent
writers are safe (last-writer-wins, no partial files).
"""
from __future__ import annotations
import json
import os
import pickle
import sys
import time

# Support both package import (from solution_cache import ...) and
# script-style execution (python solution_cache/cache.py).
try:
    from .keys import (
        gather_solve_inputs, hash_solve_inputs, parametrization_tag,
        check_provenance_match,
    )
    from .serialize import extract_eco_solution, reconstruct_eco_solution
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from keys import (
        gather_solve_inputs, hash_solve_inputs, parametrization_tag,
        check_provenance_match,
    )
    from serialize import extract_eco_solution, reconstruct_eco_solution


USE_CACHE_ENV_VAR = "HAFISCAL_USE_SOLUTION_CACHE"

# Cache root = same directory as this file (the solution_cache/ package).
# Parametrization subdirs live alongside the .py files.
_CACHE_ROOT = os.path.dirname(os.path.abspath(__file__))


def _parametrization_name(eco):
    """Best-effort label for the parametrization (used in path).

    Looks at how many cohorts/edu groups exist and tries to match the
    standard HAFiscal labels. Falls back to 'custom'.
    """
    n = len(eco.agents)
    if n == 1:
        return "HS_Only"
    if n == 3:
        return "Reduced_Run"
    if n == 21:
        return "Baseline"
    if n == 7:
        return "College_Beta_Het"
    return f"custom_{n}cohorts"


def cache_path_for_key(parametrization, shock_type, human_tag, key,
                         create_dir=False):
    """Return (pkl_path, meta_path) for the given key."""
    short = key[:8]
    dir_path = os.path.join(_CACHE_ROOT, parametrization, shock_type)
    if create_dir:
        os.makedirs(dir_path, exist_ok=True)
    pkl_path = os.path.join(dir_path, f"{human_tag}__{short}.pkl")
    meta_path = os.path.join(dir_path, f"{human_tag}__{short}.meta.json")
    return pkl_path, meta_path


def compute_solve_key(eco, shock_type="recession", mc_method="hark_mc",
                       seeds=(0,), use_shuffle=False,
                       init_panel_method="newborn_pool",
                       agent_count_per_cohort=None):
    """Compute the SHA256 cache key for the given solve configuration."""
    inputs = gather_solve_inputs(
        eco, shock_type=shock_type, mc_method=mc_method,
        seeds=seeds, use_shuffle=use_shuffle,
        init_panel_method=init_panel_method,
        agent_count_per_cohort=agent_count_per_cohort,
    )
    return hash_solve_inputs(inputs), inputs


def _atomic_pickle_write(path, obj):
    """Pickle obj to path atomically (write to .tmp then rename)."""
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _atomic_json_write(path, obj):
    """Write JSON to path atomically."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def save_to_cache(eco, key, inputs, pkl_path, meta_path):
    """Extract solution + write pickle + meta atomically."""
    extracted = extract_eco_solution(eco)
    payload = {
        "version": 1,
        "key": key,
        "extracted": extracted,
        "saved_at": time.time(),
    }
    _atomic_pickle_write(pkl_path, payload)
    meta = {
        "version": 1,
        "key": key,
        "inputs": inputs,
        "saved_at": time.time(),
        "pkl_filename": os.path.basename(pkl_path),
    }
    _atomic_json_write(meta_path, meta)


def _warn_provenance_mismatch(meta_path, label="solution_cache"):
    """If the .meta.json next to the pkl records a different HAFiscal/HARK SHA
    or Python version than the current process, print a one-line warning.
    The cache is still used — this is informational only."""
    if not os.path.exists(meta_path):
        return
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        cached_prov = (meta.get("inputs") or {}).get("provenance") or {}
        diffs = check_provenance_match(cached_prov)
        if diffs:
            parts = ", ".join(f"{k}: {cv}→{nv}" for (k, cv, nv) in diffs)
            print(f"[{label}] provenance mismatch (using cache anyway): {parts}",
                  flush=True)
    except (OSError, ValueError, KeyError):
        pass  # Best-effort; never block loading


def load_from_cache(eco, pkl_path, meta_path=None):
    """Load cached solution and reconstruct into eco in place. Optionally
    pass the .meta.json path to enable provenance-mismatch warnings."""
    if meta_path is not None:
        _warn_provenance_mismatch(meta_path, label="solution_cache")
    with open(pkl_path, "rb") as f:
        payload = pickle.load(f)
    if payload.get("version") != 1:
        raise ValueError(
            f"cache version mismatch: got {payload.get('version')}, want 1")
    reconstruct_eco_solution(eco, payload["extracted"])


def cached_eco_solve(ctx, shock_type="recession",
                      mc_method="hark_mc", seeds=(0,),
                      use_shuffle=False, init_panel_method="newborn_pool",
                      agent_count_per_cohort=None,
                      verbose=True, force_solve=False):
    """Drop-in replacement for the typical
        eco.switch_shock_type(shock_type); eco.solve()
    sequence. Checks the cache first; loads on hit, solves+saves on miss.

    Args:
        ctx: dict from build_and_solve(...) containing 'AggEco'.
        shock_type: 'recession', 'recessionCheck', etc.
        mc_method, seeds, use_shuffle, init_panel_method,
        agent_count_per_cohort: forward-sim params that affect the
            AD-converged result. Pass whatever values your downstream
            forward-sim will use.
        verbose: log cache hits/misses.
        force_solve: skip cache; always solve + save.

    Behavior:
        - Cache off (HAFISCAL_USE_SOLUTION_CACHE != '1'): just calls
          eco.switch_shock_type + eco.solve as before.
        - Cache on + hit: loads from disk, mutates eco in place.
        - Cache on + miss: solves, saves, returns.

    Returns:
        dict with 'cache_hit' (bool), 'wall' (seconds), 'pkl_path' (or None).
    """
    eco = ctx["AggEco"]
    do_switch = shock_type not in (None, "base")

    # Off: just solve
    if os.environ.get(USE_CACHE_ENV_VAR, "0") != "1":
        t0 = time.time()
        if do_switch:
            eco.switch_shock_type(shock_type)
        eco.solve()
        return {"cache_hit": False, "wall": time.time() - t0, "pkl_path": None}

    # On: compute key, look up, decide
    if do_switch:
        eco.switch_shock_type(shock_type)
    key, inputs = compute_solve_key(
        eco, shock_type=shock_type, mc_method=mc_method, seeds=seeds,
        use_shuffle=use_shuffle, init_panel_method=init_panel_method,
        agent_count_per_cohort=agent_count_per_cohort,
    )
    pname = _parametrization_name(eco)
    seed_offset = seeds[0] if seeds else 0
    tag = parametrization_tag(
        eco, mc_method=mc_method, use_shuffle=use_shuffle,
        agent_count_per_cohort=agent_count_per_cohort, seed_offset=seed_offset)
    pkl_path, meta_path = cache_path_for_key(
        pname, shock_type, tag, key, create_dir=True)

    if (not force_solve) and os.path.exists(pkl_path):
        if verbose:
            print(f"[solution_cache] HIT: {pkl_path}", flush=True)
        t0 = time.time()
        load_from_cache(eco, pkl_path, meta_path=meta_path)
        return {"cache_hit": True, "wall": time.time() - t0,
                "pkl_path": pkl_path}

    # Miss: solve + save
    if verbose:
        print(f"[solution_cache] MISS: solving + saving to {pkl_path}",
              flush=True)
    t0 = time.time()
    eco.solve()
    wall_solve = time.time() - t0
    save_to_cache(eco, key, inputs, pkl_path, meta_path)
    return {"cache_hit": False, "wall": wall_solve, "pkl_path": pkl_path}
