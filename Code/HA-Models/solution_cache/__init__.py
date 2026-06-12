"""
HAFiscal solution cache.

Stores AD-converged eco.solve() outputs keyed on every parameter that
affects the numerical result (solve params + AD-loop params + forward-sim
params used during AD + provenance SHAs). Lets parallel scripts (HARK MC,
JAX MC, 5D TM, ...) skip the expensive solve when one with matching
parameters already exists on disk.

Public API:
    from solution_cache import cached_eco_solve, compute_solve_key

    # Drop-in for eco.solve() — checks cache, hits = load, miss = solve+save
    cached_eco_solve(ctx, shock_type='recession', verbose=True)

    # Inspect what key would be used (no I/O)
    key = compute_solve_key(ctx['AggEco'], shock_type='recession')

Toggle: HAFISCAL_USE_SOLUTION_CACHE=1 (off by default).
"""
# Full registry of all HAFISCAL_* env flags: Code/HA-Models/docs/ENV_FLAGS.md
from .cache import (
    cached_eco_solve,
    compute_solve_key,
    cache_path_for_key,
    USE_CACHE_ENV_VAR,
)
from .serialize import (
    extract_eco_solution,
    reconstruct_eco_solution,
)
from .ad_cache import (
    cached_solve_ad_recession,
    cached_solve_ad_recession_hark,
)

__all__ = [
    "cached_eco_solve",
    "cached_solve_ad_recession",
    "cached_solve_ad_recession_hark",
    "compute_solve_key",
    "cache_path_for_key",
    "extract_eco_solution",
    "reconstruct_eco_solution",
    "USE_CACHE_ENV_VAR",
]
