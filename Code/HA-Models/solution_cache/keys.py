"""
Key extraction: gather all numerical-result-affecting params from an eco/agent
into a stable dict, then SHA256 it.

Includes:
- Per-cohort solve-time numerical params (CRRA, DiscFac, Rfree, ...)
- Grid params (aXtraGrid contents, Cgrid contents)
- IncShkDstn atoms + probabilities
- MrkvArray
- AD-loop params (num_max_iterations_solvingAD, convergence_tol_solvingAD,
  Cfunc_iter_stepsize)
- ADelasticity
- Forward-sim params used during AD: AgentCount, shuffle on/off, seeds,
  init-panel method, MC method (HARK vs JAX), all HAFISCAL_* env flags
  that affect numerical output
- Provenance: HARK commit SHA, HAFiscal commit SHA, Python major.minor

Explicitly NOT in the key (numerical-equivalent across these):
- T_sim, AgentCount when not used for AD (only for post-AD reporting MC)
- HAFISCAL_JAX_MC_USE_2D_LIFT / VMAP_SEEDS / BATCH_TABLES / LAZY_PANEL /
  VMAP_COHORTS — these are speedup-only optimizations, parity-validated
- HAFISCAL_PARALLEL_SOLVE (just changes cohort scheduling, not output)
- HAFISCAL_USE_JAX_SOLVER (validated to give same converged cFunc)
- JAX backend (CPU vs GPU)
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import numpy as np


# Whitelist of HAFISCAL_* env vars that affect numerical output and MUST
# be in the cache key. (Tonight's speedup flags are NOT here.)
_HAFISCAL_NUMERICAL_ENV_VARS = (
    "HAFISCAL_PLVL_GROWS_DURING_UNEMP",
    "HAFISCAL_TM_CFUNC_OFFSET",
    "HAFISCAL_AGGREGATE_BY_EDU_SHARE",
    "HAFISCAL_UI_STATE_ENCODING",
    "HAFISCAL_SHUFFLE_MRKV_TRANSITION",
    "HAFISCAL_AGENTCOUNT_D",
    "HAFISCAL_AGENTCOUNT_H",
    "HAFISCAL_AGENTCOUNT_C",
    "HAFISCAL_INTERPRETATION",
    "HAFISCAL_WRAPPER_EDTYPES",
    "HAFISCAL_GICX_MODE",
    "HAFISCAL_NM_START_FROM_SAVED",
    # BUG-047: PERMGROFAC_FIX={0,1} toggles the PermGroFac^(-CRRA) factor in the
    # solver's marginal value -> changes the cFunc by ~6-7%. A FIX=0 (buggy) and a
    # FIX=1 (fixed) solution are NUMERICALLY DISTINCT and MUST NOT be cross-loaded.
    # Critically: the discount-factor calibration (beta) is ESTIMATED PAIRED with a
    # specific FIX regime (beta re-absorbs the fix to hit K/Y). Serving a cached
    # solution from the other regime to a given beta is a meaningless mismatched
    # pairing (a model that hits no targets). So this MUST be in the key.
    "HAFISCAL_PERMGROFAC_FIX",
    # 2B JAX-native iter loop replaces HARK's solve_agent. Parity vs HARK is
    # ~1e-3 (kernel-parity range), NOT bit-identical — so a 2B-solved cache
    # entry shouldn't be loaded under HARK mode. Treat as a numerically-
    # distinct path; the conservative thing is to key on it.
    "HAFISCAL_USE_JAX_2B",
    "HAFISCAL_USE_JAX_2B_VMAP",  # vmap variant of 2B; numerically equivalent
                                  # to serial 2B (parity 4e-10) but keep in
                                  # the key for forensics (different code path).
)


def _git_sha(repo_dir):
    """Return short git SHA of HEAD in repo_dir, or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _hafiscal_root():
    """Locate the HAFiscal repo root from this file's location."""
    here = os.path.abspath(os.path.dirname(__file__))
    # Walk up until we find .git
    cur = here
    while cur and cur != "/":
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        cur = os.path.dirname(cur)
    return None


def _hark_root():
    """Locate the HARK install dir for SHA tracking."""
    try:
        import HARK
        return os.path.dirname(os.path.dirname(HARK.__file__))
    except ImportError:
        return None


def _canonicalize_array(arr):
    """Convert numpy array to a stable JSON-serializable form."""
    a = np.asarray(arr)
    return {
        "_array": True,
        "shape": list(a.shape),
        "dtype": str(a.dtype),
        # Use float64 hash for floats (avoid platform-specific repr issues).
        # For exact reproducibility, hash the bytes.
        "sha256": hashlib.sha256(np.ascontiguousarray(
            a.astype(np.float64) if a.dtype.kind == "f" else a
        ).tobytes()).hexdigest(),
    }


def _canonicalize_dstn(dstn):
    """Canonicalize a HARK distribution (pmv + atoms)."""
    return {
        "_dstn": True,
        "pmv": _canonicalize_array(dstn.pmv),
        "atoms": [_canonicalize_array(a) for a in dstn.atoms],
    }


def _canonicalize_value(v):
    """Convert any param to a stable JSON-serializable form."""
    if isinstance(v, np.ndarray):
        return _canonicalize_array(v)
    if isinstance(v, (list, tuple)):
        return [_canonicalize_value(x) for x in v]
    if isinstance(v, (int, float, str, bool, type(None))):
        return v
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    # HARK distribution-like
    if hasattr(v, "pmv") and hasattr(v, "atoms"):
        return _canonicalize_dstn(v)
    # Indexable container of distributions
    if hasattr(v, "__iter__") and not isinstance(v, dict):
        try:
            return [_canonicalize_value(x) for x in v]
        except Exception:
            pass
    # Fallback: string repr (may break determinism; ideally avoid)
    return f"<unencoded:{type(v).__name__}:{repr(v)[:120]}>"


def _agent_params_dict(agent):
    """Per-cohort agent params that affect the solve output."""
    params = {}
    # Scalar / list params
    for attr in (
        "CRRA", "DiscFac", "BoroCnstArt", "T_age", "T_cycle", "cycles",
        "Splurge",
    ):
        if hasattr(agent, attr):
            params[attr] = _canonicalize_value(getattr(agent, attr))
    # Array / list params
    for attr in (
        "Rfree", "LivPrb", "PermGroFac", "PermGroFacAgg",
        "aXtraGrid", "Cgrid",
    ):
        if hasattr(agent, attr):
            params[attr] = _canonicalize_value(getattr(agent, attr))
    # IncShkDstn — list of distributions per Markov state per cycle
    if hasattr(agent, "IncShkDstn"):
        try:
            iss = agent.IncShkDstn
            params["IncShkDstn"] = _canonicalize_value(iss)
        except Exception as e:
            params["IncShkDstn_error"] = str(e)
    # MrkvArray and CondMrkvArrays
    if hasattr(agent, "MrkvArray"):
        params["MrkvArray"] = _canonicalize_value(agent.MrkvArray)
    if hasattr(agent, "CondMrkvArrays"):
        params["CondMrkvArrays"] = _canonicalize_value(agent.CondMrkvArrays)
    # Number of base Mrkv states (affects state-space size)
    if hasattr(agent, "num_base_MrkvStates"):
        params["num_base_MrkvStates"] = int(agent.num_base_MrkvStates)
    return params


def _ad_params_dict(eco):
    """AD-loop params (eco-level)."""
    params = {}
    for attr in (
        "num_max_iterations_solvingAD", "convergence_tol_solvingAD",
        "Cfunc_iter_stepsize", "demand_ADelasticity", "ADelasticity",
        "num_experiment_periods",
    ):
        if hasattr(eco, attr):
            params[attr] = _canonicalize_value(getattr(eco, attr))
    return params


def _env_dict():
    """Numerical-output-affecting env vars (whitelisted)."""
    return {
        k: os.environ.get(k, "")
        for k in _HAFISCAL_NUMERICAL_ENV_VARS
    }


def _provenance_dict():
    """Versions / SHAs for cross-checking."""
    hafiscal = _hafiscal_root()
    hark = _hark_root()
    return {
        "hafiscal_sha": _git_sha(hafiscal) if hafiscal else "unknown",
        "hark_sha": _git_sha(hark) if hark else "unknown",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
    }


def gather_solve_inputs(eco, shock_type, mc_method="hark_mc",
                         seeds=(0,), use_shuffle=False,
                         init_panel_method="newborn_pool",
                         agent_count_per_cohort=None):
    """Gather everything that determines the AD-converged eco.solve() output.

    Args:
        eco: HAFiscal AggEconomy object (post-build, pre-solve)
        shock_type: 'recession', 'recessionCheck', etc.
        mc_method: 'hark_mc' / 'jax_mc' / 'jax_mc_replay_v2' / etc.
        seeds: tuple of seed offsets used during AD
        use_shuffle: bool
        init_panel_method: 'newborn_pool' / 'hark_ref' / 'explicit' / ...
        agent_count_per_cohort: tuple of per-cohort N, or None for default

    Returns:
        dict suitable for hashing (all values canonicalized).
    """
    return {
        "shock_type": shock_type,
        "mc_method": mc_method,
        "seeds": list(seeds),
        "use_shuffle": bool(use_shuffle),
        "init_panel_method": init_panel_method,
        "agent_count_per_cohort": (
            list(agent_count_per_cohort)
            if agent_count_per_cohort is not None
            else [int(a.AgentCount) for a in eco.agents]
        ),
        "n_cohorts": len(eco.agents),
        "agents": [_agent_params_dict(a) for a in eco.agents],
        "ad": _ad_params_dict(eco),
        "env": _env_dict(),
        "provenance": _provenance_dict(),
    }


# Top-level keys in the inputs dict that are metadata-only — they appear
# in the .meta.json sidecar for forensics but are EXCLUDED from the hash
# so e.g. committing to HAFiscal mid-session doesn't invalidate the cache.
# Numerical-output-affecting params (env, agent params, AD-loop, etc.)
# remain in the hash.
_HASH_EXCLUDED_TOP_KEYS = ("provenance",)


def hash_solve_inputs(inputs):
    """SHA256 of canonical JSON of the inputs dict, EXCLUDING metadata-only
    top-level keys (see ``_HASH_EXCLUDED_TOP_KEYS``). Stable across HAFiscal/
    HARK commits — provenance SHAs land in metadata, not the hash key."""
    hashable = {k: v for k, v in inputs.items()
                if k not in _HASH_EXCLUDED_TOP_KEYS}
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def check_provenance_match(meta_provenance, current_provenance=None):
    """Compare a cached meta's provenance dict to the current env.

    Returns a list of (field, cached_val, current_val) tuples for fields
    that differ. Empty list = full match.
    """
    if current_provenance is None:
        current_provenance = _provenance_dict()
    diffs = []
    for k, cached_v in meta_provenance.items():
        cur_v = current_provenance.get(k)
        if cur_v != cached_v:
            diffs.append((k, cached_v, cur_v))
    return diffs


def parametrization_tag(eco, mc_method="hark_mc", use_shuffle=False,
                          agent_count_per_cohort=None, seed_offset=0):
    """Human-readable filename tag combining the most navigable params."""
    if agent_count_per_cohort is None:
        agent_count_per_cohort = [int(a.AgentCount) for a in eco.agents]
    ac_str = "-".join(str(n) for n in agent_count_per_cohort)
    shuf_str = "shuf" if use_shuffle else "noshuf"
    return f"AC{ac_str}__mc-{mc_method}__{shuf_str}__seed{seed_offset}"
