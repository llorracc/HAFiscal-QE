#!/usr/bin/env python
"""
Quick Comparison Script for HAFiscal 0.14.1 vs 0.17.0

This script runs a fast validation (~5-10 minutes) that tests key components
sequentially with controlled RNG to ensure deterministic comparison.

Usage:
    python quick_compare.py

Components tested:
    1. Solver: Compare consumption functions at test points
    2. Simulation: Compare wealth distributions after short simulation
    3. MPC Calculation: Compare MPCs from lottery win simulation
    4. Objective Function: Compare estimation objective at fixed parameters
"""

import subprocess
import json
import numpy as np
import os
import sys
import time
from pathlib import Path

# Configuration
VERSIONS = {
    '0.14.1-bugfixed': {
        'base': '/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed',
        'python': '/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed/.venv/bin/python',
    },
    '0.17.0-loky-warmup': {
        'base': '/home/econ-ark/GitHub/llorracc/HAFiscal-Latest',
        'python': '/home/econ-ark/GitHub/llorracc/HAFiscal-Latest/.venv/bin/python',
    }
}

OUTPUT_DIR = Path('/tmp/hafiscal_quick_compare')
OUTPUT_DIR.mkdir(exist_ok=True)

# Reduced parameters for quick testing
QUICK_PARAMS = {
    'AgentCount': 200,      # Reduced from 5000
    'T_sim': 100,           # Reduced from 800
    'TypeCount': 3,         # Reduced from 7 (just test 3 discount factor types)
}

def run_component_test(component_name: str, script_content: str) -> dict:
    """Run a component test for both versions and compare results."""
    
    print(f"\n{'='*70}")
    print(f"TESTING: {component_name}")
    print(f"{'='*70}")
    
    results = {}
    
    # Write the test script
    script_path = OUTPUT_DIR / f"test_{component_name}.py"
    script_path.write_text(script_content)
    
    for version, config in VERSIONS.items():
        print(f"\n  Running {version}...")
        start_time = time.time()
        
        output_file = OUTPUT_DIR / f"{component_name}_{version.replace('.', '_')}.json"
        
        env = os.environ.copy()
        env['HAFISCAL_VERSION'] = version
        env['HAFISCAL_BASE'] = config['base']
        env['QUICK_PARAMS'] = json.dumps(QUICK_PARAMS)
        env['OUTPUT_FILE'] = str(output_file)
        
        try:
            result = subprocess.run(
                [config['python'], str(script_path)],
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per component
            )
            
            elapsed = time.time() - start_time
            
            if result.returncode != 0:
                print(f"    ❌ FAILED (exit code {result.returncode})")
                print(f"    stderr: {result.stderr[:500]}")
                results[version] = {'status': 'failed', 'error': result.stderr[:500]}
            else:
                if output_file.exists():
                    with open(output_file) as f:
                        results[version] = json.load(f)
                    results[version]['status'] = 'success'
                    results[version]['elapsed'] = elapsed
                    print(f"    ✅ Completed in {elapsed:.1f}s")
                else:
                    print(f"    ❌ No output file generated")
                    results[version] = {'status': 'failed', 'error': 'No output file'}
                    
        except subprocess.TimeoutExpired:
            print(f"    ❌ TIMEOUT after 300s")
            results[version] = {'status': 'timeout'}
        except Exception as e:
            print(f"    ❌ ERROR: {e}")
            results[version] = {'status': 'error', 'error': str(e)}
    
    return results

def compare_results(component_name: str, results: dict, tolerance: float = 0.01) -> dict:
    """Compare results between versions."""
    
    comparison = {
        'component': component_name,
        'status': 'unknown',
        'differences': [],
        'max_diff': 0,
    }
    
    v1, v2 = list(VERSIONS.keys())
    
    if results.get(v1, {}).get('status') != 'success':
        comparison['status'] = f'{v1} failed'
        return comparison
    if results.get(v2, {}).get('status') != 'success':
        comparison['status'] = f'{v2} failed'
        return comparison
    
    r1, r2 = results[v1], results[v2]
    
    # Compare numeric values
    for key in r1:
        if key in ['status', 'elapsed', 'version']:
            continue
            
        if key not in r2:
            comparison['differences'].append(f"Key '{key}' missing in {v2}")
            continue
            
        val1, val2 = r1[key], r2[key]
        
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            if val1 != 0:
                rel_diff = abs(val1 - val2) / abs(val1)
            else:
                rel_diff = abs(val2) if val2 != 0 else 0
                
            comparison['max_diff'] = max(comparison['max_diff'], rel_diff)
            
            if rel_diff > tolerance:
                comparison['differences'].append(
                    f"{key}: {val1:.6g} vs {val2:.6g} (diff: {rel_diff*100:.2f}%)"
                )
        elif isinstance(val1, list) and isinstance(val2, list):
            arr1, arr2 = np.array(val1), np.array(val2)
            if arr1.shape == arr2.shape:
                with np.errstate(divide='ignore', invalid='ignore'):
                    rel_diff = np.abs(arr1 - arr2) / np.maximum(np.abs(arr1), 1e-10)
                    max_rel_diff = np.nanmax(rel_diff)
                    
                comparison['max_diff'] = max(comparison['max_diff'], max_rel_diff)
                
                if max_rel_diff > tolerance:
                    comparison['differences'].append(
                        f"{key}: max diff {max_rel_diff*100:.2f}%"
                    )
    
    if not comparison['differences']:
        comparison['status'] = 'PASS'
    else:
        comparison['status'] = 'DIFFERENCES FOUND'
    
    return comparison

# =============================================================================
# Component Test Scripts
# =============================================================================

SOLVER_TEST = '''
import sys
import os
import json
import numpy as np

VERSION = os.environ['HAFISCAL_VERSION']
BASE = os.environ['HAFISCAL_BASE']
QUICK_PARAMS = json.loads(os.environ['QUICK_PARAMS'])
OUTPUT_FILE = os.environ['OUTPUT_FILE']

sys.path.insert(0, f'{BASE}/Code/HA-Models')

np.random.seed(12345)

try:
    from HARK.distribution import Uniform
except ImportError:
    from HARK.distributions import Uniform

if VERSION == '0.14.1-bugfixed':
    from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
    AgentType = KinkedRconsumerType
else:
    from rng_synchronized_consumer import RNGSyncKinkedRconsumerType
    AgentType = RNGSyncKinkedRconsumerType

# Parameters
_LivPrb = 1 - 1/160
_Rfree = 1.02**0.25

base_params = {
    'CRRA': 2.0, 'Rfree': _Rfree, 'Rsave': _Rfree, 'Rboro': 1.137**0.25,
    'PermGroFac': [1.0], 'PermGroFacAgg': 1.01**0.25, 'BoroCnstArt': 0,
    'CubicBool': False, 'vFuncBool': False,
    'PermShkStd': [0.001**0.5], 'PermShkCount': 5,
    'TranShkStd': [0.132**0.5], 'TranShkCount': 5,
    'UnempPrb': 0.044, 'IncUnemp': 0.60,
    'UnempPrbRet': None, 'IncUnempRet': None,
    'aXtraMin': 0.00001, 'aXtraMax': 20, 'aXtraCount': 20,
    'aXtraExtra': [None], 'aXtraNestFac': 3,
    'LivPrb': [_LivPrb], 'DiscFac': 0.97, 'cycles': 0,
    'T_cycle': 1, 'T_retire': 0, 'T_sim': 100, 'T_age': None,
    'IndL': 10.0/9.0, 'aNrmInitMean': np.log(0.00001), 'aNrmInitStd': 0.0,
    'pLvlInitMean': 0.0, 'pLvlInitStd': 0.0, 'AgentCount': 200,
}

# Test with 3 discount factors
test_betas = [0.92, 0.96, 0.99]
results = {'version': VERSION}

m_test = np.array([0.5, 1.0, 2.0, 5.0, 10.0])

for i, beta in enumerate(test_betas):
    params = base_params.copy()
    params['DiscFac'] = beta
    params['seed'] = 12345 + i
    
    agent = AgentType(**params)
    agent.solve()
    
    cFunc = agent.solution[0].cFunc
    c_values = cFunc(m_test)
    
    results[f'cFunc_beta{i}'] = c_values.tolist()
    results[f'mNrmMin_beta{i}'] = float(agent.solution[0].mNrmMin)

with open(OUTPUT_FILE, 'w') as f:
    json.dump(results, f, indent=2)
'''

SIMULATION_TEST = '''
import sys
import os
import json
import numpy as np

VERSION = os.environ['HAFISCAL_VERSION']
BASE = os.environ['HAFISCAL_BASE']
QUICK_PARAMS = json.loads(os.environ['QUICK_PARAMS'])
OUTPUT_FILE = os.environ['OUTPUT_FILE']

sys.path.insert(0, f'{BASE}/Code/HA-Models')

np.random.seed(12345)

try:
    from HARK.distribution import Uniform
except ImportError:
    from HARK.distributions import Uniform

if VERSION == '0.14.1-bugfixed':
    from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
    AgentType = KinkedRconsumerType
else:
    from rng_synchronized_consumer import RNGSyncKinkedRconsumerType
    AgentType = RNGSyncKinkedRconsumerType

_LivPrb = 1 - 1/160
_Rfree = 1.02**0.25

base_params = {
    'CRRA': 2.0, 'Rfree': _Rfree, 'Rsave': _Rfree, 'Rboro': 1.137**0.25,
    'PermGroFac': [1.0], 'PermGroFacAgg': 1.01**0.25, 'BoroCnstArt': 0,
    'CubicBool': False, 'vFuncBool': False,
    'PermShkStd': [0.001**0.5], 'PermShkCount': 5,
    'TranShkStd': [0.132**0.5], 'TranShkCount': 5,
    'UnempPrb': 0.044, 'IncUnemp': 0.60,
    'UnempPrbRet': None, 'IncUnempRet': None,
    'aXtraMin': 0.00001, 'aXtraMax': 20, 'aXtraCount': 20,
    'aXtraExtra': [None], 'aXtraNestFac': 3,
    'LivPrb': [_LivPrb], 'DiscFac': 0.96, 'cycles': 0,
    'T_cycle': 1, 'T_retire': 0, 'T_age': None, 'IndL': 10.0/9.0,
    'aNrmInitMean': np.log(0.00001), 'aNrmInitStd': 0.0,
    'pLvlInitMean': 0.0, 'pLvlInitStd': 0.0,
    'AgentCount': QUICK_PARAMS['AgentCount'],
    'T_sim': QUICK_PARAMS['T_sim'],
}

params = base_params.copy()
params['seed'] = 12345

agent = AgentType(**params)
agent.solve()

# Initialize with deterministic assets
agent.initialize_sim()
rng = np.random.RandomState(42)
agent.state_now['aNrm'] = rng.uniform(0.0, 2.0, size=params['AgentCount'])

agent.simulate()

# Collect results
if 'aNrm' in agent.history:
    final_aNrm = agent.history['aNrm'][-1]
    final_cNrm = agent.history['cNrm'][-1]
else:
    final_aNrm = agent.state_now['aNrm']
    final_cNrm = agent.controls['cNrm']

results = {
    'version': VERSION,
    'mean_aNrm': float(np.mean(final_aNrm)),
    'std_aNrm': float(np.std(final_aNrm)),
    'mean_cNrm': float(np.mean(final_cNrm)),
    'percentiles_aNrm': np.percentile(final_aNrm, [10, 25, 50, 75, 90]).tolist(),
    'first_10_aNrm': final_aNrm[:10].tolist(),
}

with open(OUTPUT_FILE, 'w') as f:
    json.dump(results, f, indent=2)
'''

MPC_TEST = '''
import sys
import os
import json
import numpy as np
import random

VERSION = os.environ['HAFISCAL_VERSION']
BASE = os.environ['HAFISCAL_BASE']
QUICK_PARAMS = json.loads(os.environ['QUICK_PARAMS'])
OUTPUT_FILE = os.environ['OUTPUT_FILE']

sys.path.insert(0, f'{BASE}/Code/HA-Models')

np.random.seed(12345)
random.seed(55)

try:
    from HARK.distribution import Uniform
except ImportError:
    from HARK.distributions import Uniform

if VERSION == '0.14.1-bugfixed':
    from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
    AgentType = KinkedRconsumerType
else:
    from rng_synchronized_consumer import RNGSyncKinkedRconsumerType
    AgentType = RNGSyncKinkedRconsumerType

_LivPrb = 1 - 1/160
_Rfree = 1.02**0.25

base_params = {
    'CRRA': 2.0, 'Rfree': _Rfree, 'Rsave': _Rfree, 'Rboro': 1.137**0.25,
    'PermGroFac': [1.0], 'PermGroFacAgg': 1.01**0.25, 'BoroCnstArt': 0,
    'CubicBool': False, 'vFuncBool': False,
    'PermShkStd': [0.001**0.5], 'PermShkCount': 5,
    'TranShkStd': [0.132**0.5], 'TranShkCount': 5,
    'UnempPrb': 0.044, 'IncUnemp': 0.60,
    'UnempPrbRet': None, 'IncUnempRet': None,
    'aXtraMin': 0.00001, 'aXtraMax': 20, 'aXtraCount': 20,
    'aXtraExtra': [None], 'aXtraNestFac': 3,
    'LivPrb': [_LivPrb], 'DiscFac': 0.96, 'cycles': 0,
    'T_cycle': 1, 'T_retire': 0, 'T_sim': 100, 'T_age': None, 'IndL': 10.0/9.0,
    'aNrmInitMean': np.log(0.00001), 'aNrmInitStd': 0.0,
    'pLvlInitMean': 0.0, 'pLvlInitStd': 0.0,
    'AgentCount': 100,  # Small for MPC test
}
base_params['kLogInitMean'] = base_params['aNrmInitMean']

params = base_params.copy()
params['seed'] = 12345

agent = AgentType(**params)
agent.solve()
agent.initialize_sim()
agent.simulate()

# MPC calculation
AgentCount = params['AgentCount']
N_Quarter = 8
lottery_size = 7.129 * (10/1.1) / (270/4)
SPLURGE = 0.25

agent.t_sim = 0

LotteryWin = np.zeros((AgentCount, N_Quarter))
for i in range(AgentCount):
    LotteryWin[i, random.randint(0, 3)] = 1

c_base = np.zeros((AgentCount, N_Quarter))
c_actu = np.zeros((AgentCount, N_Quarter))

for period in range(N_Quarter):
    agent.simulate(1)
    c_base[:, period] = agent.controls["cNrm"]
    
    Llvl = lottery_size * LotteryWin[:, period]
    Lnrm = Llvl / agent.state_now["pLvl"]
    SplurgeNrm = SPLURGE * Lnrm
    
    m_adj = agent.state_now["mNrm"] + Lnrm - SplurgeNrm
    c_actu[:, period] = agent.solution[0].cFunc(m_adj) + SplurgeNrm

# Annual MPC (first year = 4 quarters)
c_base_year1 = np.sum(c_base[:, :4] * agent.state_now["pLvl"][:, None], axis=1)
c_actu_year1 = np.sum(c_actu[:, :4] * agent.state_now["pLvl"][:, None], axis=1)
MPC_year1 = (c_actu_year1 - c_base_year1) / lottery_size

results = {
    'version': VERSION,
    'mean_MPC_year1': float(np.mean(MPC_year1)),
    'std_MPC_year1': float(np.std(MPC_year1)),
    'lottery_periods': [int(np.argmax(LotteryWin[i])) for i in range(10)],
    'first_10_MPC': MPC_year1[:10].tolist(),
}

with open(OUTPUT_FILE, 'w') as f:
    json.dump(results, f, indent=2)
'''

OBJECTIVE_TEST = '''
import sys
import os
import json
import numpy as np
import random
from copy import deepcopy

VERSION = os.environ['HAFISCAL_VERSION']
BASE = os.environ['HAFISCAL_BASE']
QUICK_PARAMS = json.loads(os.environ['QUICK_PARAMS'])
OUTPUT_FILE = os.environ['OUTPUT_FILE']

sys.path.insert(0, f'{BASE}/Code/HA-Models')

np.random.seed(12345)
random.seed(55)

try:
    from HARK.distribution import Uniform
    from HARK.utilities import get_lorenz_shares
except ImportError:
    from HARK.distributions import Uniform
    from HARK.utilities import get_lorenz_shares

if VERSION == '0.14.1-bugfixed':
    from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
    AgentType = KinkedRconsumerType
else:
    from rng_synchronized_consumer import RNGSyncKinkedRconsumerType
    AgentType = RNGSyncKinkedRconsumerType

_LivPrb = 1 - 1/160
_Rfree = 1.02**0.25

base_params = {
    'CRRA': 2.0, 'Rfree': _Rfree, 'Rsave': _Rfree, 'Rboro': 1.137**0.25,
    'PermGroFac': [1.0], 'PermGroFacAgg': 1.01**0.25, 'BoroCnstArt': 0,
    'CubicBool': False, 'vFuncBool': False,
    'PermShkStd': [0.001**0.5], 'PermShkCount': 5,
    'TranShkStd': [0.132**0.5], 'TranShkCount': 5,
    'UnempPrb': 0.044, 'IncUnemp': 0.60,
    'UnempPrbRet': None, 'IncUnempRet': None,
    'aXtraMin': 0.00001, 'aXtraMax': 20, 'aXtraCount': 20,
    'aXtraExtra': [None], 'aXtraNestFac': 3,
    'LivPrb': [_LivPrb], 'DiscFac': 0.96, 'cycles': 0,
    'T_cycle': 1, 'T_retire': 0, 'T_age': None, 'IndL': 10.0/9.0,
    'aNrmInitMean': np.log(0.00001), 'aNrmInitStd': 0.0,
    'pLvlInitMean': 0.0, 'pLvlInitStd': 0.0,
    'AgentCount': QUICK_PARAMS['AgentCount'],
    'T_sim': QUICK_PARAMS['T_sim'],
}

# Test parameters
TEST_BETA = 0.96
TEST_NABLA = 0.05
TypeCount = QUICK_PARAMS['TypeCount']

# Build agents SEQUENTIALLY
beta_set = Uniform(TEST_BETA - TEST_NABLA, TEST_BETA + TEST_NABLA).discretize(TypeCount).atoms.flatten()

agents = []
for j in range(TypeCount):
    params = deepcopy(base_params)
    params['DiscFac'] = beta_set[j]
    params['seed'] = 12345 + j
    agent = AgentType(**params)
    agent.solve()
    agents.append(agent)

# Simulate SEQUENTIALLY
for j, agent in enumerate(agents):
    agent.initialize_sim()
    rng = np.random.RandomState(42 + j)
    agent.state_now['aNrm'] = rng.uniform(0.0, 2.0, size=base_params['AgentCount'])
    agent.simulate()

# Collect wealth
WealthNow = np.concatenate([agent.state_now["aLvl"] for agent in agents])

# Compute targets
lorenz_target = np.array([0.029, 0.354, 1.84, 7.42])/100
try:
    lorenz_model = get_lorenz_shares(WealthNow, percentiles=np.array([0.25, 0.50, 0.75, 0.99]))
except:
    lorenz_model = get_lorenz_shares(WealthNow, percentiles=np.array([25, 50, 75, 99]))

lorenz_error = float(np.sqrt(np.sum((lorenz_model - lorenz_target)**2)))

results = {
    'version': VERSION,
    'mean_wealth': float(np.mean(WealthNow)),
    'lorenz_model': lorenz_model.tolist(),
    'lorenz_error': lorenz_error,
    'beta_set': beta_set.tolist(),
}

with open(OUTPUT_FILE, 'w') as f:
    json.dump(results, f, indent=2)
'''

def main():
    print("=" * 70)
    print("HAFiscal QUICK COMPARISON")
    print("=" * 70)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Quick params: {QUICK_PARAMS}")
    
    start_time = time.time()
    
    all_comparisons = []
    
    # Run component tests
    components = [
        ('solver', SOLVER_TEST),
        ('simulation', SIMULATION_TEST),
        ('mpc', MPC_TEST),
        ('objective', OBJECTIVE_TEST),
    ]
    
    for name, script in components:
        results = run_component_test(name, script)
        comparison = compare_results(name, results)
        all_comparisons.append(comparison)
        
        # Print comparison
        print(f"\n  Comparison: {comparison['status']}")
        if comparison['differences']:
            for diff in comparison['differences'][:5]:
                print(f"    - {diff}")
        print(f"  Max relative difference: {comparison['max_diff']*100:.4f}%")
    
    # Summary
    total_time = time.time() - start_time
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_pass = True
    for comp in all_comparisons:
        status_icon = "✅" if comp['status'] == 'PASS' else "⚠️"
        print(f"  {status_icon} {comp['component']}: {comp['status']} (max diff: {comp['max_diff']*100:.2f}%)")
        if comp['status'] != 'PASS':
            all_pass = False
    
    print(f"\nTotal time: {total_time:.1f}s")
    
    if all_pass:
        print("\n✅ ALL COMPONENTS MATCH (within 1% tolerance)")
    else:
        print("\n⚠️ SOME DIFFERENCES DETECTED - review above")
    
    # Save full results
    summary_file = OUTPUT_DIR / 'comparison_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(all_comparisons, f, indent=2)
    print(f"\nFull results saved to: {summary_file}")
    
    return 0 if all_pass else 1

if __name__ == '__main__':
    sys.exit(main())
