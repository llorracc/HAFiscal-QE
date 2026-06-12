#!/usr/bin/env python
"""
Minimum Working Example: Numba JIT Recompilation Overhead in multi_thread_commands

ISSUE SUMMARY
=============
When using `multi_thread_commands` with the default Loky backend, each worker process
must independently JIT-compile Numba-decorated functions. This causes significant
performance overhead, especially for the first call in a session.

OBSERVED BEHAVIOR
=================
- First multi_thread_commands call: ~4 seconds (with Loky backend)
- Subsequent calls (cached): ~0.3 seconds
- With threading backend: ~1.3 seconds consistently (no per-worker JIT)

ROOT CAUSE
==========
The Loky backend spawns separate Python processes that don't share the Numba JIT cache
from the main process. Each worker must independently compile Numba functions when they
are first called. HARK uses Numba in several performance-critical functions, causing
this overhead to accumulate.

IMPACT
======
For estimation workflows that call multi_thread_commands many times (e.g., during
parameter optimization), this can result in 2x or greater slowdown compared to:
1. Sequential execution
2. Threading backend
3. Pre-warmed Loky workers

REPRODUCTION
============
Run this script to see the timing comparisons:
    python mwe_numba_jit_overhead.py

Requirements:
    - HARK >= 0.17.0
    - Python >= 3.9
"""

import time
import warnings
import multiprocessing
from typing import List, Any

# Suppress Numba deprecation warnings for cleaner output
warnings.filterwarnings('ignore', category=DeprecationWarning)

import numpy as np
from joblib import Parallel, delayed

# HARK imports
import HARK
from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType

print("=" * 70)
print("Numba JIT Recompilation Overhead in multi_thread_commands")
print("=" * 70)
print(f"HARK version: {HARK.__version__}")
print(f"Python version: {__import__('sys').version.split()[0]}")
print(f"CPU count: {multiprocessing.cpu_count()}")
print()

# =============================================================================
# CONFIGURATION
# =============================================================================

NUM_AGENT_TYPES = 7  # Number of heterogeneous agent types (typical for estimation)
AGENT_COUNT = 5000   # Agents per type
NUM_TRIALS = 3       # Number of timing trials

# Minimal parameters for IndShockConsumerType
BASE_PARAMS = {
    'CRRA': 2.0,
    'Rfree': [1.01],  # Must be list in HARK 0.17.0
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

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_agent_list(num_types: int = NUM_AGENT_TYPES) -> List[IndShockConsumerType]:
    """Create a list of heterogeneous agents with varying discount factors."""
    agents = []
    for j in range(num_types):
        params = BASE_PARAMS.copy()
        params['DiscFac'] = 0.90 + 0.01 * j
        params['seed'] = 12345 + j
        agent = IndShockConsumerType(**params)
        agents.append(agent)
    return agents


def run_commands_single(agent: Any, command_list: List[str]) -> Any:
    """Execute commands on a single agent (used by parallel backends)."""
    for command in command_list:
        method_name = command.rstrip('()')
        getattr(agent, method_name)()
    return agent


# =============================================================================
# MULTI-THREAD IMPLEMENTATIONS
# =============================================================================

def multi_thread_loky(agent_list: List, command_list: List[str]) -> None:
    """multi_thread_commands with Loky backend (default, uses multiprocessing)."""
    if len(agent_list) == 1:
        for cmd in command_list:
            getattr(agent_list[0], cmd.rstrip('()'))()
        return
    
    num_jobs = min(len(agent_list), multiprocessing.cpu_count())
    result = Parallel(n_jobs=num_jobs, backend='loky')(
        delayed(run_commands_single)(agent, command_list) 
        for agent in agent_list
    )
    for j, agent in enumerate(result):
        agent_list[j] = agent


def multi_thread_threading(agent_list: List, command_list: List[str]) -> None:
    """multi_thread_commands with threading backend (shared memory, no serialization)."""
    if len(agent_list) == 1:
        for cmd in command_list:
            getattr(agent_list[0], cmd.rstrip('()'))()
        return
    
    num_jobs = min(len(agent_list), multiprocessing.cpu_count())
    result = Parallel(n_jobs=num_jobs, backend='threading')(
        delayed(run_commands_single)(agent, command_list) 
        for agent in agent_list
    )
    for j, agent in enumerate(result):
        agent_list[j] = agent


def multi_thread_sequential(agent_list: List, command_list: List[str]) -> None:
    """Sequential execution (baseline, no parallelism)."""
    for agent in agent_list:
        for cmd in command_list:
            getattr(agent, cmd.rstrip('()'))()


# =============================================================================
# BENCHMARKING
# =============================================================================

def benchmark_implementation(name: str, impl_func, num_trials: int = NUM_TRIALS) -> dict:
    """Benchmark a multi_thread implementation."""
    print(f"\n{'='*60}")
    print(f"Benchmarking: {name}")
    print(f"{'='*60}")
    
    times = []
    for trial in range(num_trials):
        # Create fresh agents for each trial
        agents = create_agent_list()
        
        # Time the solve operation
        t0 = time.time()
        impl_func(agents, ['solve()'])
        elapsed = time.time() - t0
        times.append(elapsed)
        
        print(f"  Trial {trial + 1}: {elapsed:.3f}s")
    
    result = {
        'name': name,
        'times': times,
        'mean': np.mean(times),
        'std': np.std(times),
        'min': np.min(times),
        'max': np.max(times),
        'first': times[0],
        'subsequent_mean': np.mean(times[1:]) if len(times) > 1 else times[0],
    }
    
    print(f"\n  Summary:")
    print(f"    First call:      {result['first']:.3f}s")
    print(f"    Subsequent avg:  {result['subsequent_mean']:.3f}s")
    print(f"    Overall mean:    {result['mean']:.3f}s ± {result['std']:.3f}s")
    
    return result


def main():
    """Run all benchmarks and display comparison."""
    
    print("\n" + "=" * 70)
    print("BENCHMARK CONFIGURATION")
    print("=" * 70)
    print(f"  Agent types:    {NUM_AGENT_TYPES}")
    print(f"  Agents per type: {AGENT_COUNT:,}")
    print(f"  Total agents:   {NUM_AGENT_TYPES * AGENT_COUNT:,}")
    print(f"  Trials per impl: {NUM_TRIALS}")
    
    # Run benchmarks
    results = []
    
    # 1. Sequential (baseline)
    results.append(benchmark_implementation(
        "Sequential (baseline)", 
        multi_thread_sequential
    ))
    
    # 2. Threading backend
    results.append(benchmark_implementation(
        "Threading backend", 
        multi_thread_threading
    ))
    
    # 3. Loky backend (default)
    results.append(benchmark_implementation(
        "Loky backend (default)", 
        multi_thread_loky
    ))
    
    # 4. HARK's built-in multi_thread_commands
    from HARK.core import multi_thread_commands as hark_mtc
    results.append(benchmark_implementation(
        "HARK multi_thread_commands", 
        hark_mtc
    ))
    
    # ==========================================================================
    # SUMMARY COMPARISON
    # ==========================================================================
    
    print("\n" + "=" * 70)
    print("SUMMARY COMPARISON")
    print("=" * 70)
    
    print(f"\n{'Implementation':<30} {'First':>10} {'Subsequent':>12} {'Speedup':>10}")
    print("-" * 65)
    
    baseline_subsequent = results[0]['subsequent_mean']
    for r in results:
        speedup = baseline_subsequent / r['subsequent_mean'] if r['subsequent_mean'] > 0 else 0
        print(f"{r['name']:<30} {r['first']:>9.3f}s {r['subsequent_mean']:>11.3f}s {speedup:>9.2f}x")
    
    # ==========================================================================
    # KEY OBSERVATIONS
    # ==========================================================================
    
    print("\n" + "=" * 70)
    print("KEY OBSERVATIONS")
    print("=" * 70)
    
    loky_result = results[2]  # Loky backend
    threading_result = results[1]  # Threading backend
    sequential_result = results[0]  # Sequential
    
    print(f"""
1. FIRST-CALL OVERHEAD (Numba JIT compilation in workers):
   - Loky first call:     {loky_result['first']:.3f}s
   - Threading first call: {threading_result['first']:.3f}s
   - Overhead ratio:       {loky_result['first'] / threading_result['first']:.2f}x

2. SUBSEQUENT CALLS (after Numba cache is warmed):
   - Loky subsequent:     {loky_result['subsequent_mean']:.3f}s
   - Threading subsequent: {threading_result['subsequent_mean']:.3f}s
   - Sequential:          {sequential_result['subsequent_mean']:.3f}s

3. THE PROBLEM:
   Each Loky worker process must independently JIT-compile Numba functions.
   This happens on EVERY first call, causing {loky_result['first']:.1f}s overhead.
   
   In estimation workflows with many optimization iterations, worker pools
   may be recycled, causing repeated JIT compilation and ~2x slowdown.

4. POTENTIAL FIXES:
   a) Use threading backend (recommended for shared-memory systems)
   b) Pre-warm Numba cache before optimization
   c) Configure Loky to persist workers (max_nbytes, timeout settings)
   d) Add Numba cache=True to decorated functions
""")
    
    return results


if __name__ == "__main__":
    results = main()
