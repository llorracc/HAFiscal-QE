#!/usr/bin/env python
"""
Debug script to identify where numerical differences arise in Step 1 (splurge estimation).

This script:
1. Tests if solver solutions are identical for fixed parameters
2. Tests if simulations are identical given identical solutions
3. Identifies where differences first appear
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
print(f"DEBUG STEP 1 DIFFERENCES - Version: {VERSION}")
print(f"=" * 70)

# Set random seeds for reproducibility
np.random.seed(12345)

# Add paths
if VERSION == '0.14.1-bugfixed':
    sys.path.insert(0, '/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed/Code/HA-Models')
    sys.path.insert(0, '/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed/Code/HA-Models/Target_AggMPCX_LiquWealth')
    os.chdir('/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed/Code/HA-Models/Target_AggMPCX_LiquWealth')
elif VERSION == '0.17.0-native':
    sys.path.insert(0, '/home/econ-ark/GitHub/llorracc/HAFiscal-Latest/Code/HA-Models')
    sys.path.insert(0, '/home/econ-ark/GitHub/llorracc/HAFiscal-Latest/Code/HA-Models/Target_AggMPCX_LiquWealth')
    os.chdir('/home/econ-ark/GitHub/llorracc/HAFiscal-Latest/Code/HA-Models/Target_AggMPCX_LiquWealth')
else:
    print(f"ERROR: Unknown version {VERSION}")
    sys.exit(1)

# Import estimation code
from Estimation_BetaNablaSplurge import (
    init_dropout, init_highschool, init_college,
    DiscFacDstns, DiscFacCount
)

# Import HARK
if VERSION == '0.14.1-bugfixed':
    from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
    AgentType = KinkedRconsumerType
else:
    # For 0.17.0, use the synchronized RNG type
    sys.path.insert(0, '/home/econ-ark/GitHub/llorracc/HAFiscal-Latest/Code/HA-Models')
    from rng_synchronized_consumer import RNGSyncKinkedRconsumerType
    AgentType = RNGSyncKinkedRconsumerType

# Fixed test parameters (use the 0.14.1 estimated values)
TEST_SPLURGE = 0.2461138828477288
TEST_BETA = 0.9675511619351821
TEST_NABLA = 0.057804998532851315

print(f"\nTest Parameters:")
print(f"  splurge = {TEST_SPLURGE}")
print(f"  beta    = {TEST_BETA}")
print(f"  nabla   = {TEST_NABLA}")

# Build discount factor distribution
from HARK.distribution import Uniform
DiscFacDstn = Uniform(TEST_BETA - TEST_NABLA, TEST_BETA + TEST_NABLA).discretize(DiscFacCount)

print(f"\nDiscount Factor Distribution:")
print(f"  DiscFacCount = {DiscFacCount}")
print(f"  DiscFac values: {DiscFacDstn.atoms.flatten()}")

# ============================================================================
# PHASE 1: SOLVER COMPARISON
# ============================================================================
print(f"\n{'='*70}")
print("PHASE 1: SOLVER COMPARISON")
print(f"{'='*70}")

# Create agents for each education type
init_params_list = [init_dropout, init_highschool, init_college]
edu_names = ['Dropout', 'Highschool', 'College']

solver_results = {}

for edu_idx, (init_params, edu_name) in enumerate(zip(init_params_list, edu_names)):
    print(f"\n--- {edu_name} ---")
    
    # Create agent with first discount factor
    test_DiscFac = DiscFacDstn.atoms.flatten()[0]
    
    params = init_params.copy()
    params['DiscFac'] = test_DiscFac
    params['seed'] = 12345 + edu_idx
    
    agent = AgentType(**params)
    agent.solve()
    
    # Extract consumption function at test points
    cFunc = agent.solution[0].cFunc
    m_test = np.array([0.5, 1.0, 2.0, 5.0, 10.0, 20.0])
    c_values = cFunc(m_test)
    
    print(f"  DiscFac = {test_DiscFac}")
    print(f"  cFunc test points: {c_values}")
    
    # Store solver results
    solver_results[edu_name] = {
        'DiscFac': float(test_DiscFac),
        'cFunc_values': c_values.tolist(),
        'm_test': m_test.tolist(),
        'mNrmMin': float(agent.solution[0].mNrmMin),
    }
    
    # Also check MPC at m=1
    mpc_at_1 = cFunc.derivative(np.array([1.0]))[0]
    solver_results[edu_name]['MPC_at_m1'] = float(mpc_at_1)
    print(f"  MPC at m=1: {mpc_at_1}")

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

# Simulation parameters
T_sim = 200
AgentCount = 500

simulation_results = {}

for edu_idx, (init_params, edu_name) in enumerate(zip(init_params_list, edu_names)):
    print(f"\n--- {edu_name} ---")
    
    test_DiscFac = DiscFacDstn.atoms.flatten()[0]
    
    params = init_params.copy()
    params['DiscFac'] = test_DiscFac
    params['T_sim'] = T_sim
    params['AgentCount'] = AgentCount
    params['seed'] = 12345 + edu_idx
    
    agent = AgentType(**params)
    agent.solve()
    
    # Initialize with deterministic assets for reproducibility
    agent.initialize_sim()
    rng = np.random.RandomState(42 + edu_idx)
    agent.state_now['aNrm'] = rng.uniform(0.0, 2.0, size=AgentCount)
    
    # Simulate
    agent.simulate()
    
    # Extract results
    final_aNrm = agent.history['aNrm'][-1]
    final_cNrm = agent.history['cNrm'][-1]
    final_mNrm = agent.history['mNrm'][-1]
    
    simulation_results[edu_name] = {
        'mean_aNrm': float(np.mean(final_aNrm)),
        'mean_cNrm': float(np.mean(final_cNrm)),
        'mean_mNrm': float(np.mean(final_mNrm)),
        'std_aNrm': float(np.std(final_aNrm)),
        'aNrm_percentiles': np.percentile(final_aNrm, [10, 25, 50, 75, 90]).tolist(),
        'first_10_aNrm': final_aNrm[:10].tolist(),
    }
    
    print(f"  mean_aNrm = {simulation_results[edu_name]['mean_aNrm']:.6f}")
    print(f"  mean_cNrm = {simulation_results[edu_name]['mean_cNrm']:.6f}")
    print(f"  first_10_aNrm = {final_aNrm[:10]}")

# Save simulation results
sim_file = f"{OUTPUT_DIR}/simulation_{VERSION}.json"
with open(sim_file, 'w') as f:
    json.dump(simulation_results, f, indent=2)
print(f"\nSimulation results saved to: {sim_file}")

# ============================================================================
# PHASE 3: OBJECTIVE FUNCTION VALUE
# ============================================================================
print(f"\n{'='*70}")
print("PHASE 3: OBJECTIVE FUNCTION EVALUATION")
print(f"{'='*70}")

# Import the objective function
from Estimation_BetaNablaSplurge import FuncToMinimize

# Reset random state before evaluation
np.random.seed(12345)

obj_value = FuncToMinimize([TEST_BETA, TEST_NABLA], TEST_SPLURGE)
print(f"Objective function value: {obj_value}")

objective_results = {
    'splurge': TEST_SPLURGE,
    'beta': TEST_BETA,
    'nabla': TEST_NABLA,
    'objective_value': float(obj_value),
}

obj_file = f"{OUTPUT_DIR}/objective_{VERSION}.json"
with open(obj_file, 'w') as f:
    json.dump(objective_results, f, indent=2)
print(f"Objective results saved to: {obj_file}")

print(f"\n{'='*70}")
print("DEBUG COMPLETE")
print(f"{'='*70}")
