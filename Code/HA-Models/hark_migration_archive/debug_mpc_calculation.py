#!/usr/bin/env python
"""
Debug MPC calculation specifically.
"""

import sys
import os
import numpy as np
import random
import json
from copy import deepcopy

VERSION = os.environ.get('HAFISCAL_VERSION', 'unknown')
OUTPUT_DIR = '/tmp/hafiscal_debug_step1'
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"=" * 70)
print(f"MPC CALCULATION DEBUG - Version: {VERSION}")
print(f"=" * 70)

# Setup paths
if VERSION == '0.14.1-bugfixed':
    BASE = '/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed'
elif VERSION == '0.17.0-native':
    BASE = '/home/econ-ark/GitHub/llorracc/HAFiscal-Latest'
else:
    print(f"ERROR: Unknown version {VERSION}")
    sys.exit(1)

sys.path.insert(0, f'{BASE}/Code/HA-Models')
sys.path.insert(0, f'{BASE}/Code/HA-Models/Target_AggMPCX_LiquWealth')

# Set seeds
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
    try:
        from rng_synchronized_consumer import RNGSyncKinkedRconsumerType
        AgentType = RNGSyncKinkedRconsumerType
        print("Using RNGSyncKinkedRconsumerType")
    except:
        from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
        AgentType = KinkedRconsumerType
        print("Using standard KinkedRconsumerType")

# Parameters
TypeCount = 7
_LivPrb = 1 - 1/160
_Rfree = 1.02**0.25

base_params = {
    'CRRA': 2.0,
    'Rfree': _Rfree,
    'Rsave': _Rfree,
    'Rboro': 1.137**0.25,
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
    'DiscFac': 0.97,
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
    'AgentCount': 500,  # Reduced for testing
}

# Add 0.14.1 compatibility aliases
base_params['kLogInitMean'] = base_params['aNrmInitMean']
base_params['kLogInitStd'] = base_params['aNrmInitStd']
base_params['pLogInitMean'] = base_params['pLvlInitMean']
base_params['pLogInitStd'] = base_params['pLvlInitStd']

# Test parameters
TEST_SPLURGE = 0.24906992981618237
TEST_BETA = 0.9675474591463475
TEST_NABLA = 0.05782806961924406

# Build discount factor distribution
DiscFacDstn = Uniform(TEST_BETA - TEST_NABLA, TEST_BETA + TEST_NABLA).discretize(TypeCount)
beta_set = DiscFacDstn.atoms.flatten().copy()

# Apply GIC tapering
GICmaxBeta = (1-_LivPrb) + (base_params['PermGroFacAgg']**base_params['CRRA'])/_Rfree
for j in range(TypeCount):
    taper_threshold = 0.01
    if beta_set[j] > GICmaxBeta - taper_threshold:
        beta_set[j] = GICmaxBeta - taper_threshold + (np.arctan((beta_set[j] - GICmaxBeta + taper_threshold)/taper_threshold))*taper_threshold/np.pi*2
    elif beta_set[j] < 0.01:
        beta_set[j] = 0.01

print(f"\nBeta set: {beta_set}")

# Create and solve agents SEQUENTIALLY (not parallel)
print("\nCreating agents sequentially...")
agents = []
for j in range(TypeCount):
    params = deepcopy(base_params)
    params['DiscFac'] = beta_set[j]
    params['seed'] = 12345 + j
    
    agent = AgentType(**params)
    agent.solve()
    agents.append(agent)
    print(f"  Agent {j}: DiscFac={beta_set[j]:.6f}, solved")

# Initialize and simulate SEQUENTIALLY
print("\nSimulating agents sequentially...")
for j, agent in enumerate(agents):
    agent.initialize_sim()
    agent.simulate()
    print(f"  Agent {j}: simulated, mean_aLvl={np.mean(agent.state_now['aLvl']):.4f}")

# Collect wealth
WealthNow = np.concatenate([agent.state_now["aLvl"] for agent in agents])
print(f"\nTotal wealth: mean={np.mean(WealthNow):.4f}")

# Now calculate MPC for a simple test
print("\n" + "="*70)
print("MPC CALCULATION TEST")
print("="*70)

# Reset random seed for MPC calculation
random.seed(55)

# Lottery parameters
lottery_size = np.array([1.625, 3.3741, 7.129, 40.0, 7.129]) * (10/1.1) / (270/4)
N_Quarter_Sim = 20
N_Year_Sim = int(N_Quarter_Sim/4)

# Test with just the first agent type
ThisType = agents[0]
ThisType.t_sim = 0  # Reset simulation counter

AgentCount = ThisType.AgentCount
print(f"\nTesting with Agent 0, AgentCount={AgentCount}")

# Record random state before lottery assignment
rand_state_before = random.getstate()

# Create lottery wins array
LotteryWin = np.zeros((AgentCount, N_Quarter_Sim))
for i in range(AgentCount):
    LotteryWin[i, random.randint(0, 3)] = 1

# Record random state after lottery assignment
rand_state_after = random.getstate()

print(f"Random calls made for lottery: {AgentCount}")
print(f"First 10 lottery periods: {[np.argmax(LotteryWin[i]) for i in range(10)]}")

# Calculate MPC for one lottery size
k = 4  # Representative lottery size
c_base = np.zeros((AgentCount, N_Quarter_Sim))
c_base_Lvl = np.zeros((AgentCount, N_Quarter_Sim))
c_actu = np.zeros((AgentCount, N_Quarter_Sim))
c_actu_Lvl = np.zeros((AgentCount, N_Quarter_Sim))
a_actu = np.zeros((AgentCount, N_Quarter_Sim))

for period in range(N_Quarter_Sim):
    ThisType.simulate(1)
    
    c_base[:, period] = ThisType.controls["cNrm"]
    c_base_Lvl[:, period] = c_base[:, period] * ThisType.state_now["pLvl"]
    
    Llvl = lottery_size[k] * LotteryWin[:, period]
    Lnrm = Llvl / ThisType.state_now["pLvl"]
    SplurgeNrm = TEST_SPLURGE * Lnrm
    
    R_kink = np.where(a_actu[:, period-1] < 0, base_params['Rboro'], base_params['Rsave'])
    
    if period == 0:
        m_adj = ThisType.state_now["mNrm"] + Lnrm - SplurgeNrm
        c_actu[:, period] = ThisType.solution[0].cFunc(m_adj) + SplurgeNrm
        c_actu_Lvl[:, period] = c_actu[:, period] * ThisType.state_now["pLvl"]
        a_actu[:, period] = ThisType.state_now["mNrm"] + Lnrm - c_actu[:, period]
    else:
        m_adj = a_actu[:, period-1] * R_kink / ThisType.shocks["PermShk"] + ThisType.shocks["TranShk"] + Lnrm - SplurgeNrm
        c_actu[:, period] = ThisType.solution[0].cFunc(m_adj) + SplurgeNrm
        c_actu_Lvl[:, period] = c_actu[:, period] * ThisType.state_now["pLvl"]
        a_actu[:, period] = a_actu[:, period-1] * R_kink / ThisType.shocks["PermShk"] + ThisType.shocks["TranShk"] + Lnrm - c_actu[:, period]

# Calculate annual MPCs
MPC_by_year = np.zeros((AgentCount, N_Year_Sim))
for year in range(N_Year_Sim):
    c_actu_year = np.sum(c_actu_Lvl[:, year*4:(year+1)*4], axis=1)
    c_base_year = np.sum(c_base_Lvl[:, year*4:(year+1)*4], axis=1)
    MPC_by_year[:, year] = (c_actu_year - c_base_year) / lottery_size[k]

print(f"\nMPC by year (first 10 agents):")
for year in range(N_Year_Sim):
    print(f"  Year {year+1}: {MPC_by_year[:10, year]}")

print(f"\nMean MPC by year (all agents):")
for year in range(N_Year_Sim):
    print(f"  Year {year+1}: {np.mean(MPC_by_year[:, year]):.6f}")

# Save results
results = {
    'version': VERSION,
    'lottery_periods_first10': [int(np.argmax(LotteryWin[i])) for i in range(10)],
    'mean_MPC_by_year': [float(np.mean(MPC_by_year[:, y])) for y in range(N_Year_Sim)],
    'mean_wealth': float(np.mean(WealthNow)),
    'first10_MPC_year1': MPC_by_year[:10, 0].tolist(),
}

output_file = f"{OUTPUT_DIR}/mpc_debug_{VERSION}.json"
with open(output_file, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to: {output_file}")

print(f"\n{'='*70}")
print("MPC DEBUG COMPLETE")
print(f"{'='*70}")
