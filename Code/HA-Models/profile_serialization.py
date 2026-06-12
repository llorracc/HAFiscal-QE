#!/usr/bin/env python
"""
Check agent object sizes and serialization overhead.
"""

import sys
import os
import time
import pickle

hark_version = os.environ.get('HARK_VERSION', 'unknown')
print(f"=== HARK version: {hark_version} ===")

import HARK
print(f"HARK version: {HARK.__version__}")

try:
    from HARK.distributions import Uniform
except ImportError:
    from HARK.distribution import Uniform

from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType

# Minimal params
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
    'AgentCount': 10000,
    'aXtraMin': 0.001,
    'aXtraMax': 40,
    'aXtraCount': 48,
    'aXtraNestFac': 3,
    'aXtraExtra': None,
    'vFuncBool': False,
    'CubicBool': False,
    'Rboro': 1.01,
    'Rsave': 1.01,
}

# Create unsolved agent
print("\n=== Unsolved agent ===")
agent_unsolved = KinkedRconsumerType(**init_params)
serialized_unsolved = pickle.dumps(agent_unsolved)
print(f"Unsolved agent pickle size: {len(serialized_unsolved):,} bytes")

# Time serialization
t0 = time.time()
for _ in range(10):
    pickle.dumps(agent_unsolved)
t1 = time.time()
print(f"Serialization time (unsolved): {(t1-t0)/10*1000:.2f}ms")

# Create solved agent
print("\n=== Solved agent ===")
agent_solved = KinkedRconsumerType(**init_params)
agent_solved.solve()
serialized_solved = pickle.dumps(agent_solved)
print(f"Solved agent pickle size: {len(serialized_solved):,} bytes")

# Time serialization
t0 = time.time()
for _ in range(10):
    pickle.dumps(agent_solved)
t1 = time.time()
print(f"Serialization time (solved): {(t1-t0)/10*1000:.2f}ms")

# Count attributes
print("\n=== Agent attributes ===")
print(f"Number of attributes: {len(vars(agent_solved))}")

# Check for large attributes
print("\n=== Large attributes ===")
for name, val in vars(agent_solved).items():
    try:
        size = len(pickle.dumps(val))
        if size > 10000:
            print(f"  {name}: {size:,} bytes")
    except:
        pass
