"""TM-a warm-start cache: persistent disk-cache of build_tm_agg_fiscal_a output.

Per plan 20260503-1437h_mc_tma_companion_and_drift.md Phase 3.

The TM-a build is dominated by:
  - agent.solve()           — solving the Bellman equation for cFunc per Markov state
  - transition matrix construction over the (j, a) grid

For the SAME (β, ∇, CRRA, R, IncShkDstn, MrkvArray, T_age, LivPrb, PermGroFac,
aMin, aMax, aCount), the TM matrix + ergodic are identical. Re-computing them
on every calcAllResults / multiplier pass wastes hours.

This cache:
  - Keys on a SHA-256 hash of the canonical config (numpy arrays serialized
    deterministically, env / commit-version included)
  - Stores under Code/HA-Models/Results/registry/tm_a_cache/<key>.pkl
  - Invalidates when HARK version OR build_tm_agg_fiscal_a code commit changes
  - Atomic write via .tmp + os.replace

Cache benefit:
  - Within NM convergence: ZERO (each NM eval changes β → different solution)
  - Across calcAllResults runs at same converged cal: HUGE (skip the ~1 min
    per-cohort solve + matrix build)
  - For repeated multiplier runs (e.g., sensitivity analysis): HUGE

API:
  cache_key(agent, aCount, aMin, aMax, aFac, neutral_measure, interpretation)
    → 16-char SHA-256 prefix
  get(cache_key) → tm_data dict OR None
  put(cache_key, tm_data) → atomic write
  clear() → remove all cached entries (e.g., on suspected stale cache)

Cache invalidation triggers:
  - HARK version mismatch (recorded in cache file)
  - tm_methods.py commit SHA mismatch (recorded in cache file)
  - Manual clear() call
"""

from __future__ import annotations

import hashlib
import os
import pickle
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np


_HERE = Path(__file__).resolve().parent
_HA_ROOT = _HERE.parent
_REPO_ROOT = _HA_ROOT.parent.parent
_CACHE_DIR = _HA_ROOT / "Results" / "registry" / "tm_a_cache"


def _hark_version() -> str:
    try:
        import HARK
        return getattr(HARK, "__version__", "unknown")
    except Exception:
        return "unknown"


def _tm_methods_commit() -> str:
    """SHA of last commit that touched tm_methods.py — invalidates cache on code change."""
    try:
        out = subprocess.check_output(
            ["git", "log", "-n", "1", "--format=%H", "--",
             str(_HERE / "tm_methods.py")],
            cwd=str(_REPO_ROOT), stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()[:12]
    except Exception:
        return "unknown"


def _agent_signature(agent) -> dict[str, Any]:
    """Extract the parts of `agent` that determine the TM matrix + ergodic.

    Order matters: same fields, same order = same hash. Keep it stable.
    """
    sig: dict[str, Any] = {
        "DiscFac": float(agent.DiscFac),
        "CRRA": float(agent.CRRA),
        "Rfree": tuple(np.asarray(agent.Rfree).flatten().tolist()),
        "PermGroFac": tuple(np.asarray(agent.PermGroFac[0]).flatten().tolist()),
        "LivPrb": tuple(np.asarray(agent.LivPrb[0]).flatten().tolist()),
        "T_age": int(getattr(agent, "T_age", 0) or 0),
        "MrkvArray_shape": tuple(np.asarray(agent.MrkvArray[0]).shape),
        "MrkvArray_hash": hashlib.sha256(np.asarray(agent.MrkvArray[0]).tobytes()).hexdigest()[:16],
        "interpretation": getattr(agent, "interpretation", "CDC"),
    }
    # IncShkDstn hash: for each Markov state, hash atoms+probs
    isd = agent.IncShkDstn[0]
    isd_hash = hashlib.sha256()
    for jp in range(len(isd)):
        d = isd[jp]
        atoms_arr = np.asarray(d.atoms)
        pmv_arr = np.asarray(d.pmv)
        isd_hash.update(atoms_arr.tobytes())
        isd_hash.update(pmv_arr.tobytes())
    sig["IncShkDstn_hash"] = isd_hash.hexdigest()[:16]
    return sig


def cache_key(
    agent,
    *,
    aCount: int = 200,
    aMin: float = 0.0,
    aMax: float | None = None,
    aFac: int = 3,
    neutral_measure: bool = False,
    interpretation: str | None = None,
) -> str:
    """Compute a stable 16-char cache key for the given (agent, build args)."""
    sig = _agent_signature(agent)
    sig["aCount"] = int(aCount)
    sig["aMin"] = float(aMin)
    sig["aMax"] = float(aMax) if aMax is not None else None
    sig["aFac"] = int(aFac)
    sig["neutral_measure"] = bool(neutral_measure)
    if interpretation is not None:
        sig["interpretation"] = interpretation
    sig["__hark"] = _hark_version()
    sig["__tm_methods_commit"] = _tm_methods_commit()
    canon = repr(sorted(sig.items())).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()[:16]


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.pkl"


def get(key: str) -> dict | None:
    """Return cached tm_data dict, or None if not in cache (or invalidated)."""
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            cached = pickle.load(f)
    except Exception:
        return None
    # Validate version markers
    if cached.get("__hark_version") != _hark_version():
        return None
    if cached.get("__tm_methods_commit") != _tm_methods_commit():
        return None
    return cached.get("tm_data")


def put(key: str, tm_data: dict) -> Path:
    """Atomically write tm_data to cache. Returns the saved path."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(key)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "tm_data": tm_data,
        "__hark_version": _hark_version(),
        "__tm_methods_commit": _tm_methods_commit(),
    }
    with open(tmp, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(str(tmp), str(path))
    return path


def clear() -> int:
    """Remove all cached entries. Returns count cleared."""
    if not _CACHE_DIR.exists():
        return 0
    n = 0
    for f in _CACHE_DIR.iterdir():
        if f.suffix == ".pkl":
            f.unlink()
            n += 1
    return n


def stats() -> dict[str, Any]:
    """Return cache stats for diagnostics."""
    if not _CACHE_DIR.exists():
        return {"n_entries": 0, "total_size_mb": 0.0, "dir": str(_CACHE_DIR)}
    files = list(_CACHE_DIR.glob("*.pkl"))
    total = sum(f.stat().st_size for f in files)
    return {
        "n_entries": len(files),
        "total_size_mb": round(total / 1024 / 1024, 2),
        "dir": str(_CACHE_DIR),
    }


# ---------- CLI for inspection ----------

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "stats":
        s = stats()
        print(f"  entries: {s['n_entries']}")
        print(f"  size:    {s['total_size_mb']} MB")
        print(f"  dir:     {s['dir']}")
    elif cmd == "clear":
        n = clear()
        print(f"  cleared {n} entries")
    elif cmd == "list":
        if not _CACHE_DIR.exists():
            print("  (cache not initialized)")
        else:
            for f in sorted(_CACHE_DIR.glob("*.pkl")):
                size_kb = f.stat().st_size / 1024
                print(f"  {f.name}  {size_kb:.1f} KB")
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python _tm_a_cache.py [stats|clear|list]")
