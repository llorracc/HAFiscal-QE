#!/usr/bin/env python
"""
Profile runtime differences between HARK 0.14.1 and 0.17.0.

This script times individual operations to identify where the 2x slowdown occurs.
"""

import sys
import os
import time
import numpy as np

# Determine which version we're running
hark_version = os.environ.get('HARK_VERSION', 'unknown')
print(f"=== Profiling HARK version: {hark_version} ===")
print(f"Python version: {sys.version}")

# Import HARK
import HARK
print(f"HARK version: {HARK.__version__}")

# Handle import differences between HARK versions
try:
    from HARK.distributions import Uniform
except ImportError:
    from HARK.distribution import Uniform

from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType

# Setup parameters (minimal set for profiling)
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
    'AgentCount': 1000,
    'aXtraMin': 0.001,
    'aXtraMax': 40,
    'aXtraCount': 48,
    'aXtraNestFac': 3,
    'aXtraExtra': None,
    'vFuncBool': False,
    'CubicBool': False,
}

# For KinkedR
init_params['Rboro'] = 1.01
init_params['Rsave'] = 1.01

timings = {}

# Time agent construction
print("\n--- Timing agent construction ---")
t0 = time.time()
agent = KinkedRconsumerType(**init_params)
t1 = time.time()
timings['construction'] = t1 - t0
print(f"Construction: {timings['construction']:.3f}s")

# Time solving
print("\n--- Timing solve (200 iterations) ---")
agent.tolerance = 1e-6
t0 = time.time()
agent.solve()
t1 = time.time()
timings['solve'] = t1 - t0
print(f"Solve: {timings['solve']:.3f}s")
print(f"Solve iterations: {len(agent.solution)}")

# Time initialize_sim
print("\n--- Timing initialize_sim ---")
agent.T_sim = 500
agent.track_vars = ['aNrm', 'cNrm', 'pLvl']
t0 = time.time()
agent.initialize_sim()
t1 = time.time()
timings['initialize_sim'] = t1 - t0
print(f"Initialize sim: {timings['initialize_sim']:.3f}s")

# Time simulate
print("\n--- Timing simulate (500 periods) ---")
t0 = time.time()
agent.simulate()
t1 = time.time()
timings['simulate'] = t1 - t0
print(f"Simulate: {timings['simulate']:.3f}s")

# Time cFunc evaluation
print("\n--- Timing cFunc evaluation (10000 points) ---")
test_m = np.linspace(0.1, 10, 10000)
cFunc = agent.solution[0].cFunc
t0 = time.time()
for _ in range(100):
    c_vals = cFunc(test_m)
t1 = time.time()
timings['cFunc_eval'] = (t1 - t0) / 100
print(f"cFunc evaluation (10000 pts): {timings['cFunc_eval']*1000:.3f}ms")

# Summary
print("\n" + "="*50)
print("SUMMARY")
print("="*50)
total = sum(timings.values())
print(f"Total time: {total:.3f}s")
print()
for key, val in sorted(timings.items(), key=lambda x: -x[1]):
    pct = 100 * val / total
    print(f"  {key:20s}: {val:7.3f}s ({pct:5.1f}%)")

# Output as JSON for easy comparison
import json
print("\n--- JSON output ---")
output = {
    'hark_version': HARK.__version__,
    'python_version': sys.version.split()[0],
    'timings': timings,
    'total': total
}
print(json.dumps(output, indent=2))
