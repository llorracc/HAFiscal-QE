#!/usr/bin/env python
"""
Profile multi-agent runtime to find where 2x slowdown occurs.
"""

import sys
import os
import time
import numpy as np

hark_version = os.environ.get('HARK_VERSION', 'unknown')
print(f"=== Profiling HARK version: {hark_version} ===")

import HARK
print(f"HARK version: {HARK.__version__}")

try:
    from HARK.distributions import Uniform
except ImportError:
    from HARK.distribution import Uniform

from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType

# Import multi_thread_commands from the right place
if HARK.__version__.startswith('0.14'):
    from HARK.parallel import multi_thread_commands
else:
    from HARK.core import multi_thread_commands

# Setup parameters
init_params = {
    'CRRA': 2.0,
    'Rfree': 1.01,
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
    'AgentCount': 10000,  # Same as estimation
    'aXtraMin': 0.001,
    'aXtraMax': 40,
    'aXtraCount': 48,
    'aXtraNestFac': 3,
    'aXtraExtra': None,
    'vFuncBool': False,
    'CubicBool': False,
    'Rboro': 1.01,
    'Rsave': 1.01,
    'T_sim': 1200,  # Same as estimation
}

NUM_TYPES = 7  # Same as estimation

print(f"\n=== Creating {NUM_TYPES} agent types ===")
timings = {}

# Create agent types
t0 = time.time()
agents = []
for j in range(NUM_TYPES):
    params = init_params.copy()
    params['DiscFac'] = 0.90 + 0.01 * j  # Vary discount factor
    params['seed'] = 12345 + j
    agent = KinkedRconsumerType(**params)
    agent.T_sim = init_params['T_sim']
    agent.track_vars = ['aNrm', 'cNrm', 'pLvl']
    agents.append(agent)
t1 = time.time()
timings['create_agents'] = t1 - t0
print(f"Create {NUM_TYPES} agents: {timings['create_agents']:.3f}s")

# Time solve with multi_thread_commands
print(f"\n=== Timing multi_thread_commands (solve) ===")
t0 = time.time()
multi_thread_commands(agents, ['solve()'])
t1 = time.time()
timings['mtc_solve'] = t1 - t0
print(f"multi_thread_commands solve: {timings['mtc_solve']:.3f}s")

# Time initialize_sim with multi_thread_commands
print(f"\n=== Timing multi_thread_commands (initialize_sim) ===")
t0 = time.time()
multi_thread_commands(agents, ['initialize_sim()'])
t1 = time.time()
timings['mtc_init_sim'] = t1 - t0
print(f"multi_thread_commands initialize_sim: {timings['mtc_init_sim']:.3f}s")

# Time simulate with multi_thread_commands
print(f"\n=== Timing multi_thread_commands (simulate) ===")
t0 = time.time()
multi_thread_commands(agents, ['simulate()'])
t1 = time.time()
timings['mtc_simulate'] = t1 - t0
print(f"multi_thread_commands simulate: {timings['mtc_simulate']:.3f}s")

# Time all together (like estimation does)
print(f"\n=== Timing all-in-one multi_thread_commands ===")
# Re-create agents
agents2 = []
for j in range(NUM_TYPES):
    params = init_params.copy()
    params['DiscFac'] = 0.90 + 0.01 * j
    params['seed'] = 12345 + j
    agent = KinkedRconsumerType(**params)
    agent.T_sim = init_params['T_sim']
    agent.track_vars = ['aNrm', 'cNrm', 'pLvl']
    agents2.append(agent)

t0 = time.time()
multi_thread_commands(agents2, ['solve()', 'initialize_sim()', 'simulate()'])
t1 = time.time()
timings['mtc_all'] = t1 - t0
print(f"multi_thread_commands all: {timings['mtc_all']:.3f}s")

# Summary
print("\n" + "="*50)
print("SUMMARY")
print("="*50)
total = sum(timings.values())
print(f"Total profiled time: {total:.3f}s")
print()
for key, val in sorted(timings.items(), key=lambda x: -x[1]):
    pct = 100 * val / total
    print(f"  {key:20s}: {val:7.3f}s ({pct:5.1f}%)")

# Output as JSON
import json
print("\n--- JSON output ---")
output = {
    'hark_version': HARK.__version__,
    'num_types': NUM_TYPES,
    'agent_count': init_params['AgentCount'],
    't_sim': init_params['T_sim'],
    'timings': timings,
    'total': total
}
print(json.dumps(output, indent=2))
