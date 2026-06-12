"""
Parallel Pool Warmup Utility for HARK

This module provides utilities to pre-warm the joblib Loky worker pool,
avoiding the ~4s cold-start overhead from Numba JIT compilation in workers.

BACKGROUND
==========
HARK's multi_thread_commands uses joblib's Loky backend, which spawns separate
Python processes. Each worker must independently JIT-compile Numba functions
on first use, causing significant startup overhead.

SOLUTION
========
By warming the pool with a minimal solve() before the main optimization loop,
workers have already compiled the Numba code. Subsequent calls are 3-4x faster.

USAGE
=====
Option 1: Environment variable
    export HARK_WARM_POOL=1
    python Estimation_BetaNablaSplurge.py
    
Option 2: Call directly
    from parallel_warmup import warm_loky_pool
    warm_loky_pool(IndShockConsumerType)

PERFORMANCE
===========
- Without warming: First call ~4s, subsequent ~0.27s
- With warming: All calls ~0.27s (warmup cost ~4s paid once upfront)
- For 5+ optimization iterations, warming saves significant time
- (Numbers as of the HARK 0.14-era benchmarks; see numba_jit_overhead_mwe/.)

SEE ALSO
========
- numba_jit_overhead_mwe/ for detailed benchmarks and analysis
- https://github.com/econ-ark/HARK/issues/XXX (if issue is filed)
"""

import os
import sys
import time
import multiprocessing
from typing import Type, Optional, Dict, Any

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.abspath(__file__))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def is_warmup_enabled() -> bool:
    """Check if pool warmup is enabled via environment variable."""
    return os.environ.get('HARK_WARM_POOL', '0').lower() in ('1', 'true', 'yes')


def get_minimal_warmup_params() -> Dict[str, Any]:
    """
    Return parameters for warmup agent.
    
    NOTE: These must be realistic enough to trigger the same Numba code paths
    as the actual estimation. Using minimal params may cause Numba to recompile
    for different array shapes.
    """
    return {
        'CRRA': 2.0,
        'Rfree': [1.01],  # Must be list in HARK 0.17.0
        'DiscFac': 0.96,
        'LivPrb': [0.99],
        'PermGroFac': [1.01],
        'PermShkStd': [0.1],
        'PermShkCount': 7,  # Match typical estimation
        'TranShkStd': [0.1],
        'TranShkCount': 7,  # Match typical estimation
        'UnempPrb': 0.05,
        'UnempPrbRet': 0.0,
        'IncUnemp': 0.3,
        'IncUnempRet': 0.0,
        'BoroCnstArt': 0.0,
        'tax_rate': 0.0,
        'T_retire': 0,
        'T_age': None,
        'T_cycle': 1,
        'cycles': 0,
        'AgentCount': 5000,  # Match typical estimation to avoid Numba recompile
        'aXtraMin': 0.001,
        'aXtraMax': 40,
        'aXtraCount': 48,  # Match typical estimation
        'aXtraNestFac': 3,
        'aXtraExtra': None,
        'vFuncBool': False,
        'CubicBool': False,
    }


def warm_loky_pool(
    agent_class: Optional[Type] = None,
    params: Optional[Dict[str, Any]] = None,
    num_agents: int = 7,
    verbose: bool = True
) -> float:
    """
    Pre-warm the Loky worker pool to avoid Numba JIT compilation overhead.
    
    This function spawns Loky workers and runs a minimal solve() on each,
    ensuring that Numba functions are JIT-compiled in all workers before
    the main optimization loop begins.
    
    IMPORTANT: num_agents must match the number of agents used in your actual
    estimation. Joblib may not reuse workers if n_jobs changes between calls.
    
    Parameters
    ----------
    agent_class : type, optional
        The AgentType class to use for warmup. If None, uses IndShockConsumerType.
    params : dict, optional
        Parameters for warmup agents. If None, uses minimal defaults.
    num_agents : int, default 7
        Number of agents to use for warmup. MUST match the number used in
        your estimation (typically TypeCount = 7). Using a different number
        may cause joblib to create a different worker pool.
    verbose : bool, default True
        If True, print warmup timing information.
        
    Returns
    -------
    float
        Time taken for warmup in seconds.
        
    Example
    -------
    >>> from parallel_warmup import warm_loky_pool
    >>> from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType
    >>> warmup_time = warm_loky_pool(IndShockConsumerType, num_agents=7)
    Warming Loky pool with 7 agents... done (3.87s)
    >>> # Now multi_thread_commands calls will be fast
    """
    # Import here to avoid circular imports
    from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType
    from HARK.core import multi_thread_commands
    
    if agent_class is None:
        agent_class = IndShockConsumerType
    
    if params is None:
        params = get_minimal_warmup_params()
    
    if verbose:
        print(f"Warming Loky pool with {num_agents} agents... ", end='', flush=True)
    
    t0 = time.time()
    
    # Create agents - MUST use same count as estimation to reuse worker pool
    warmup_agents = []
    for j in range(num_agents):
        agent_params = params.copy()
        agent_params['seed'] = 99999 + j  # Distinct seeds
        warmup_agents.append(agent_class(**agent_params))
    
    # Run solve() in parallel - this triggers Numba JIT in all workers
    multi_thread_commands(warmup_agents, ['solve()'])
    
    elapsed = time.time() - t0
    
    if verbose:
        print(f"done ({elapsed:.2f}s)")
    
    return elapsed


def maybe_warm_pool(
    agent_class: Optional[Type] = None, 
    num_agents: int = 7,
    verbose: bool = True
) -> float:
    """
    Warm the pool if HARK_WARM_POOL environment variable is set.
    
    This is a convenience function that checks the environment variable
    and only warms if enabled. Safe to call unconditionally.
    
    Parameters
    ----------
    agent_class : type, optional
        The AgentType class to use for warmup.
    num_agents : int, default 7
        Number of agents to use for warmup. MUST match TypeCount.
    verbose : bool, default True
        If True, print warmup timing information.
        
    Returns
    -------
    float
        Time taken for warmup, or 0.0 if warmup was skipped.
        
    Example
    -------
    >>> # In estimation script:
    >>> from parallel_warmup import maybe_warm_pool
    >>> maybe_warm_pool(num_agents=7)  # Only warms if HARK_WARM_POOL=1
    """
    if is_warmup_enabled():
        return warm_loky_pool(agent_class, num_agents=num_agents, verbose=verbose)
    elif verbose:
        print("Pool warmup disabled (set HARK_WARM_POOL=1 to enable)")
    return 0.0


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Parallel Pool Warmup Utility - Self Test")
    print("=" * 60)
    print()
    
    from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType
    from HARK.core import multi_thread_commands
    
    # Test 1: Without warmup
    print("TEST 1: Without pool warmup")
    print("-" * 40)
    
    # Force cold pool by shutting down existing workers
    try:
        from joblib.externals.loky import get_reusable_executor
        get_reusable_executor().shutdown(wait=True, kill_workers=True)
    except:
        pass
    
    params = get_minimal_warmup_params()
    params['AgentCount'] = 5000  # More realistic
    params['aXtraCount'] = 48
    
    agents1 = [IndShockConsumerType(**{**params, 'DiscFac': 0.9 + 0.01*j, 'seed': 12345+j}) 
               for j in range(7)]
    
    t0 = time.time()
    multi_thread_commands(agents1, ['solve()'])
    cold_time = time.time() - t0
    print(f"Cold pool solve time: {cold_time:.2f}s")
    
    # Test 2: Second call (warm pool)
    print()
    print("TEST 2: With warm pool (no explicit warmup)")
    print("-" * 40)
    
    agents2 = [IndShockConsumerType(**{**params, 'DiscFac': 0.9 + 0.01*j, 'seed': 12345+j}) 
               for j in range(7)]
    
    t0 = time.time()
    multi_thread_commands(agents2, ['solve()'])
    warm_time = time.time() - t0
    print(f"Warm pool solve time: {warm_time:.2f}s")
    
    # Test 3: With explicit warmup
    print()
    print("TEST 3: With explicit pool warmup")
    print("-" * 40)
    
    # Force cold pool
    try:
        get_reusable_executor().shutdown(wait=True, kill_workers=True)
    except:
        pass
    
    warmup_time = warm_loky_pool(IndShockConsumerType)
    
    agents3 = [IndShockConsumerType(**{**params, 'DiscFac': 0.9 + 0.01*j, 'seed': 12345+j}) 
               for j in range(7)]
    
    t0 = time.time()
    multi_thread_commands(agents3, ['solve()'])
    warmed_time = time.time() - t0
    print(f"After warmup solve time: {warmed_time:.2f}s")
    
    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Cold pool (first call):     {cold_time:.2f}s")
    print(f"Warm pool (second call):    {warm_time:.2f}s")
    print(f"Explicit warmup cost:       {warmup_time:.2f}s")
    print(f"After explicit warmup:      {warmed_time:.2f}s")
    print()
    print(f"Speedup (cold vs warm):     {cold_time/warm_time:.1f}x")
    print(f"Break-even iterations:      {warmup_time / (cold_time - warmed_time):.1f}")
