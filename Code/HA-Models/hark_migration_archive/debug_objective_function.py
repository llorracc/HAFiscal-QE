#!/usr/bin/env python
"""
Test if the objective function returns identical values for both versions.
"""

import sys
import os
import numpy as np
import json
import random

# Determine which version we're running
VERSION = os.environ.get('HAFISCAL_VERSION', 'unknown')
OUTPUT_DIR = '/tmp/hafiscal_debug_step1'
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"=" * 70)
print(f"OBJECTIVE FUNCTION TEST - Version: {VERSION}")
print(f"=" * 70)

# Setup paths based on version
if VERSION == '0.14.1-bugfixed':
    BASE = '/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed'
elif VERSION == '0.17.0-native':
    BASE = '/home/econ-ark/GitHub/llorracc/HAFiscal-Latest'
else:
    print(f"ERROR: Unknown version {VERSION}")
    sys.exit(1)

sys.path.insert(0, f'{BASE}/Code/HA-Models')
sys.path.insert(0, f'{BASE}/Code/HA-Models/Target_AggMPCX_LiquWealth')
os.chdir(f'{BASE}/Code/HA-Models/Target_AggMPCX_LiquWealth')

# Set seeds BEFORE any imports that might use RNG
np.random.seed(12345)
random.seed(55)

# Import the objective function (this will trigger setup code)
print("\nImporting objective function...")
from Estimation_BetaNablaSplurge import FuncToMinimize, FagerengObjFunc, EstTypeList, TypeCount

# Test parameters
TEST_SPLURGE = 0.2461138828477288
TEST_BETA = 0.9675511619351821
TEST_NABLA = 0.057804998532851315

# Also test with 0.17.0's estimated values
TEST_SPLURGE_017 = 0.278591821512686
TEST_BETA_017 = 0.9761598810841959
TEST_NABLA_017 = 0.04417473222090803

print("\n" + "="*70)
print("Testing objective function at 0.14.1 estimated parameters")
print("="*70)

# Reset RNG state
np.random.seed(12345)
random.seed(55)
for j in range(TypeCount):
    EstTypeList[j].reset_rng()

obj_value_014 = FuncToMinimize([TEST_BETA, TEST_NABLA], TEST_SPLURGE)
print(f"Splurge={TEST_SPLURGE:.6f}, Beta={TEST_BETA:.6f}, Nabla={TEST_NABLA:.6f}")
print(f"Objective value: {obj_value_014}")

print("\n" + "="*70)
print("Testing objective function at 0.17.0 estimated parameters")
print("="*70)

# Reset RNG state
np.random.seed(12345)
random.seed(55)
for j in range(TypeCount):
    EstTypeList[j].reset_rng()

obj_value_017 = FuncToMinimize([TEST_BETA_017, TEST_NABLA_017], TEST_SPLURGE_017)
print(f"Splurge={TEST_SPLURGE_017:.6f}, Beta={TEST_BETA_017:.6f}, Nabla={TEST_NABLA_017:.6f}")
print(f"Objective value: {obj_value_017}")

# Save results
results = {
    'version': VERSION,
    'params_014': {
        'splurge': TEST_SPLURGE,
        'beta': TEST_BETA,
        'nabla': TEST_NABLA,
        'objective': float(obj_value_014)
    },
    'params_017': {
        'splurge': TEST_SPLURGE_017,
        'beta': TEST_BETA_017,
        'nabla': TEST_NABLA_017,
        'objective': float(obj_value_017)
    }
}

obj_file = f"{OUTPUT_DIR}/objective_{VERSION}.json"
with open(obj_file, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to: {obj_file}")

print(f"\n{'='*70}")
print("TEST COMPLETE")
print(f"{'='*70}")
