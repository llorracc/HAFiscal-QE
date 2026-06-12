#!/usr/bin/env python
"""
Standalone debug script to identify where numerical differences arise in Step 1.

This script does NOT import from Estimation_BetaNablaSplurge.py to avoid
triggering the full optimization.
"""

import sys
import os
import numpy as np
import json

# Determine which version we're running
VERSION = os.environ.get('HAFISCAL_VERSION', 'unknown')
OUTPUT_DIR = '/tmp/hafiscal_debug_step1'
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"=" * 70)
print(f"DEBUG STEP 1 - Version: {VERSION}")
print(f"=" * 70)

# Set random seeds for reproducibility
np.random.seed(12345)

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

# Import HARK
if VERSION == '0.14.1-bugfixed':
    from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
    AgentType = KinkedRconsumerType
else:
    from rng_synchronized_consumer import RNGSyncKinkedRconsumerType
    AgentType = RNGSyncKinkedRconsumerType

try:
    from HARK.distribution import Uniform
except ImportError:
    from HARK.distributions import Uniform

# ============================================================================
# PARAMETERS (copied from Estimation_BetaNablaSplurge.py to avoid import)
# ============================================================================

TypeCount = 7       # Number of consumer types

# Base params from SetupParamsCSTW.py
_LivPrb = 1-1/160
_Rfree = 1.02**0.25

base_params = {
    'CRRA': 2.0,
    'Rfree': _Rfree,
    'Rboro': 1.137**0.25,  # NOR parametrization
    'Rsave': _Rfree,
    'PermGroFac': [1.0],
    'PermGroFacAgg': 1.01**0.25,
    'BoroCnstArt': 0,
    'CubicBool': False,
    'vFuncBool': False,
    'PermShkStd': [0.001**0.5],
    'PermShkCount': 5,
    'TranShkStd': [0.132**0.5],
    'TranShkCount': 5,
    'UnempPrb': 0.044,
    'IncUnemp': 0.60,
    'UnempPrbRet': None,
    'IncUnempRet': None,
    'aXtraMin': 0.00001,
    'aXtraMax': 20,
    'aXtraCount': 20,
    'aXtraExtra': [None],
    'aXtraNestFac': 3,
    'LivPrb': [_LivPrb],
    'DiscFac': 0.97,  # dummy, will be overwritten
    'cycles': 0,
    'T_cycle': 1,
    'T_retire': 0,
    'T_sim': 800,
    'T_age': None,
    'IndL': 10.0/9.0,
    'aNrmInitMean': np.log(0.00001),
    'aNrmInitStd': 0.0,
    'pLvlInitMean': 0.0,
    'pLvlInitStd': 0.0,
    'AgentCount': 5000,
}

# Fixed test parameters (use the 0.14.1 estimated values)
TEST_SPLURGE = 0.2461138828477288
TEST_BETA = 0.9675511619351821
TEST_NABLA = 0.057804998532851315

print(f"\nTest Parameters:")
print(f"  splurge = {TEST_SPLURGE}")
print(f"  beta    = {TEST_BETA}")
print(f"  nabla   = {TEST_NABLA}")

# Build discount factor distribution
DiscFacDstn = Uniform(TEST_BETA - TEST_NABLA, TEST_BETA + TEST_NABLA).discretize(TypeCount)
beta_set = DiscFacDstn.atoms.flatten()

# Apply GIC tapering as in the estimation code
GICmaxBeta = (1-_LivPrb) + (base_params['PermGroFacAgg']**base_params['CRRA'])/_Rfree
minBeta = 0.01

print(f"\nGIC max beta: {GICmaxBeta}")
print(f"Raw beta_set: {beta_set}")

for j in range(TypeCount):
    taper_threshold = 0.01
    if beta_set[j] > GICmaxBeta - taper_threshold:
        beta_set[j] = GICmaxBeta - taper_threshold + (np.arctan((beta_set[j] - GICmaxBeta + taper_threshold)/taper_threshold))*taper_threshold/np.pi*2
    elif beta_set[j] < minBeta:
        beta_set[j] = minBeta

print(f"Tapered beta_set: {beta_set}")

# ============================================================================
# PHASE 1: SOLVER COMPARISON
# ============================================================================
print(f"\n{'='*70}")
print("PHASE 1: SOLVER COMPARISON")
print(f"{'='*70}")

solver_results = {}

for j in range(TypeCount):
    print(f"\n--- Agent Type {j} (DiscFac={beta_set[j]:.6f}) ---")
    
    params = base_params.copy()
    params['DiscFac'] = beta_set[j]
    params['seed'] = 12345 + j
    
    agent = AgentType(**params)
    agent.solve()
    
    # Extract consumption function at test points
    cFunc = agent.solution[0].cFunc
    m_test = np.array([0.5, 1.0, 2.0, 5.0, 10.0, 20.0])
    c_values = cFunc(m_test)
    
    print(f"  cFunc test points: {c_values}")
    
    # MPC at m=1
    mpc_at_1 = cFunc.derivative(np.array([1.0]))[0]
    print(f"  MPC at m=1: {mpc_at_1:.8f}")
    
    solver_results[f'agent_{j}'] = {
        'DiscFac': float(beta_set[j]),
        'cFunc_values': c_values.tolist(),
        'm_test': m_test.tolist(),
        'mNrmMin': float(agent.solution[0].mNrmMin),
        'MPC_at_m1': float(mpc_at_1),
    }

# Save solver results
solver_file = f"{OUTPUT_DIR}/solver_{VERSION}.json"
with open(solver_file, 'w') as f:
    json.dump(solver_results, f, indent=2)
print(f"\nSolver results saved to: {solver_file}")

# ============================================================================
# PHASE 2: SIMULATION COMPARISON
# ============================================================================
print(f"\n{'='*70}")
print("PHASE 2: SIMULATION COMPARISON")
print(f"{'='*70}")

T_sim = 200
AgentCount = 500

simulation_results = {}

for j in range(TypeCount):
    print(f"\n--- Agent Type {j} ---")
    
    params = base_params.copy()
    params['DiscFac'] = beta_set[j]
    params['T_sim'] = T_sim
    params['AgentCount'] = AgentCount
    params['seed'] = 12345 + j
    
    agent = AgentType(**params)
    
    # Set track_vars for older HARK versions
    if hasattr(agent, 'track_vars'):
        agent.track_vars = ['aNrm', 'cNrm', 'mNrm', 'pLvl']
    
    agent.solve()
    
    # Initialize with deterministic assets
    agent.initialize_sim()
    rng = np.random.RandomState(42 + j)
    agent.state_now['aNrm'] = rng.uniform(0.0, 2.0, size=AgentCount)
    
    # Simulate
    agent.simulate()
    
    # Extract results (handle API differences)
    if 'aNrm' in agent.history:
        final_aNrm = agent.history['aNrm'][-1]
        final_cNrm = agent.history['cNrm'][-1]
    elif hasattr(agent, 'aNrmNow_hist'):
        final_aNrm = agent.aNrmNow_hist[-1]
        final_cNrm = agent.cNrmNow_hist[-1]
    else:
        # Try state_now
        final_aNrm = agent.state_now['aNrm']
        final_cNrm = agent.controls['cNrm'] if 'cNrm' in agent.controls else agent.state_now.get('cNrm', np.zeros(AgentCount))
    
    simulation_results[f'agent_{j}'] = {
        'mean_aNrm': float(np.mean(final_aNrm)),
        'mean_cNrm': float(np.mean(final_cNrm)),
        'std_aNrm': float(np.std(final_aNrm)),
        'first_10_aNrm': final_aNrm[:10].tolist(),
        'first_10_cNrm': final_cNrm[:10].tolist(),
    }
    
    print(f"  mean_aNrm = {simulation_results[f'agent_{j}']['mean_aNrm']:.6f}")
    print(f"  mean_cNrm = {simulation_results[f'agent_{j}']['mean_cNrm']:.6f}")

# Save simulation results
sim_file = f"{OUTPUT_DIR}/simulation_{VERSION}.json"
with open(sim_file, 'w') as f:
    json.dump(simulation_results, f, indent=2)
print(f"\nSimulation results saved to: {sim_file}")

print(f"\n{'='*70}")
print("DEBUG COMPLETE")
print(f"{'='*70}")
