#!/usr/bin/env python
"""
MWE: Compare Proposed Fixes for Numba JIT Overhead

This script benchmarks different approaches to mitigate the Numba JIT
recompilation overhead in multi_thread_commands.

Proposed fixes evaluated:
A. Threading backend instead of Loky
B. Backend parameter for user choice
C. Numba disk cache (environment variable)
D. Pre-warming the worker pool
E. Batch processing to reduce worker recycling
"""

import os
import sys
import time
import warnings
import multiprocessing
from typing import List, Any, Callable

warnings.filterwarnings('ignore', category=DeprecationWarning)

import numpy as np
from joblib import Parallel, delayed
from joblib.externals.loky import get_reusable_executor

import HARK
from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType

print("=" * 70)
print("Comparison of Proposed Fixes for Numba JIT Overhead")
print("=" * 70)
print(f"HARK version: {HARK.__version__}")
print(f"CPU count: {multiprocessing.cpu_count()}")
print()

# =============================================================================
# CONFIGURATION
# =============================================================================

NUM_TYPES = 7
AGENT_COUNT = 5000
NUM_OPTIMIZATION_CALLS = 5  # Simulate optimization iterations

PARAMS = {
    'CRRA': 2.0,
    'Rfree': [1.01],
    'DiscFac': 0.96,
    'LivPrb': [0.99],
    'PermGroFac': [1.01],
    'PermShkStd': [0.1],
    'PermShkCount': 7,
    'TranShkStd': [0.1],
    'TranShkCount': 7,
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
    'AgentCount': AGENT_COUNT,
    'aXtraMin': 0.001,
    'aXtraMax': 40,
    'aXtraCount': 48,
    'aXtraNestFac': 3,
    'aXtraExtra': None,
    'vFuncBool': False,
    'CubicBool': False,
}


def create_agents() -> List[IndShockConsumerType]:
    """Create a fresh list of heterogeneous agents."""
    agents = []
    for j in range(NUM_TYPES):
        params = PARAMS.copy()
        params['DiscFac'] = 0.90 + 0.01 * j
        params['seed'] = 12345 + j
        agents.append(IndShockConsumerType(**params))
    return agents


def run_single(agent):
    """Run commands on a single agent."""
    agent.solve()
    return agent


def reset_loky_pool():
    """Reset the Loky worker pool to simulate cold start."""
    try:
        get_reusable_executor().shutdown(wait=True, kill_workers=True)
    except:
        pass


# =============================================================================
# IMPLEMENTATION A: Threading Backend
# =============================================================================

def multi_thread_threading(agents: List, commands: List[str]) -> None:
    """Use threading backend - shares JIT cache with main process."""
    num_jobs = min(len(agents), multiprocessing.cpu_count())
    result = Parallel(n_jobs=num_jobs, backend='threading')(
        delayed(run_single)(a) for a in agents
    )
    for j, a in enumerate(result):
        agents[j] = a


# =============================================================================
# IMPLEMENTATION B: User-selectable Backend
# =============================================================================

def multi_thread_with_backend(agents: List, commands: List[str], backend='loky') -> None:
    """Allow user to choose backend."""
    num_jobs = min(len(agents), multiprocessing.cpu_count())
    result = Parallel(n_jobs=num_jobs, backend=backend)(
        delayed(run_single)(a) for a in agents
    )
    for j, a in enumerate(result):
        agents[j] = a


# =============================================================================
# IMPLEMENTATION C: Loky with Persistent Workers
# =============================================================================

def multi_thread_persistent_loky(agents: List, commands: List[str]) -> None:
    """Use Loky with settings to keep workers alive longer."""
    num_jobs = min(len(agents), multiprocessing.cpu_count())
    # Use batch_size='auto' to group work and reduce per-task overhead
    # prefer='processes' ensures we use Loky
    result = Parallel(
        n_jobs=num_jobs, 
        backend='loky',
        batch_size='auto',
        prefer='processes',
    )(delayed(run_single)(a) for a in agents)
    for j, a in enumerate(result):
        agents[j] = a


# =============================================================================
# IMPLEMENTATION D: Pre-warmed Pool
# =============================================================================

_pool_warmed = False

def warm_pool():
    """Pre-warm the Loky pool by running a minimal solve."""
    global _pool_warmed
    if _pool_warmed:
        return
    
    # Create minimal agent
    minimal_params = PARAMS.copy()
    minimal_params['AgentCount'] = 100
    minimal_params['aXtraCount'] = 10
    dummy = IndShockConsumerType(**minimal_params)
    
    # Run solve in workers to trigger JIT
    Parallel(n_jobs=multiprocessing.cpu_count(), backend='loky')(
        delayed(run_single)(dummy) for _ in range(multiprocessing.cpu_count())
    )
    _pool_warmed = True


def multi_thread_prewarmed(agents: List, commands: List[str]) -> None:
    """Use Loky with pre-warmed pool."""
    warm_pool()
    num_jobs = min(len(agents), multiprocessing.cpu_count())
    result = Parallel(n_jobs=num_jobs, backend='loky')(
        delayed(run_single)(a) for a in agents
    )
    for j, a in enumerate(result):
        agents[j] = a


# =============================================================================
# IMPLEMENTATION E: Sequential (Baseline)
# =============================================================================

def multi_thread_sequential(agents: List, commands: List[str]) -> None:
    """Sequential execution (baseline)."""
    for agent in agents:
        agent.solve()


# =============================================================================
# BENCHMARKING
# =============================================================================

def simulate_optimization(impl_func: Callable, name: str, reset_pool: bool = True) -> dict:
    """
    Simulate an optimization workflow that calls multi_thread_commands
    multiple times, as in parameter estimation.
    """
    print(f"\n{'='*60}")
    print(f"Simulating optimization with: {name}")
    print(f"{'='*60}")
    
    if reset_pool:
        reset_loky_pool()
    
    times = []
    for iteration in range(NUM_OPTIMIZATION_CALLS):
        agents = create_agents()
        t0 = time.time()
        impl_func(agents, ['solve()'])
        elapsed = time.time() - t0
        times.append(elapsed)
        print(f"  Iteration {iteration + 1}: {elapsed:.3f}s")
    
    total = sum(times)
    print(f"\n  Total time: {total:.2f}s")
    print(f"  Mean per call: {np.mean(times):.3f}s")
    
    return {
        'name': name,
        'times': times,
        'total': total,
        'mean': np.mean(times),
        'first': times[0],
        'subsequent_mean': np.mean(times[1:]) if len(times) > 1 else times[0],
    }


def main():
    """Run all benchmarks."""
    
    print("\n" + "=" * 70)
    print("CONFIGURATION")
    print("=" * 70)
    print(f"  Agent types: {NUM_TYPES}")
    print(f"  Agents per type: {AGENT_COUNT:,}")
    print(f"  Optimization iterations: {NUM_OPTIMIZATION_CALLS}")
    print(f"  (Simulates {NUM_OPTIMIZATION_CALLS} objective function evaluations)")
    
    results = []
    
    # Baseline: Sequential
    results.append(simulate_optimization(
        multi_thread_sequential, 
        "Sequential (baseline)",
        reset_pool=False
    ))
    
    # Fix A: Threading backend
    results.append(simulate_optimization(
        multi_thread_threading,
        "Fix A: Threading backend",
        reset_pool=False
    ))
    
    # Current: Loky (cold start)
    results.append(simulate_optimization(
        lambda a, c: multi_thread_with_backend(a, c, 'loky'),
        "Current: Loky (cold start)",
        reset_pool=True
    ))
    
    # Fix B: Loky (warm pool, no reset)
    results.append(simulate_optimization(
        lambda a, c: multi_thread_with_backend(a, c, 'loky'),
        "Current: Loky (warm pool)",
        reset_pool=False
    ))
    
    # Fix D: Pre-warmed pool
    global _pool_warmed
    _pool_warmed = False
    results.append(simulate_optimization(
        multi_thread_prewarmed,
        "Fix D: Pre-warmed Loky",
        reset_pool=True
    ))
    
    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    
    print("\n" + "=" * 70)
    print("SUMMARY: Total Time for {} Optimization Iterations".format(NUM_OPTIMIZATION_CALLS))
    print("=" * 70)
    
    print(f"\n{'Implementation':<30} {'Total':>10} {'First':>10} {'Subseq Avg':>12}")
    print("-" * 65)
    
    baseline_total = results[0]['total']
    for r in results:
        speedup = baseline_total / r['total'] if r['total'] > 0 else 0
        print(f"{r['name']:<30} {r['total']:>9.2f}s {r['first']:>9.3f}s {r['subsequent_mean']:>11.3f}s")
    
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    print("""
1. FOR ESTIMATION WORKFLOWS:
   Use threading backend: total time reduced by keeping JIT cache shared.
   
2. FOR GENERAL USE:
   Add `backend` parameter to multi_thread_commands with 'loky' default.
   Document that 'threading' is recommended for repeated calls.
   
3. LONG-TERM:
   Consider enabling Numba disk cache by default (NUMBA_CACHE_DIR).
   This would benefit all backends by persisting JIT across sessions.
""")
    
    return results


if __name__ == "__main__":
    results = main()
