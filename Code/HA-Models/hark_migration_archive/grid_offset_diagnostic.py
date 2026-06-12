#!/usr/bin/env python3
"""
Diagnose the difference in grid offset between 0.14.1 and 0.17.0.
"""

import sys
import os
import numpy as np

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, 'Target_AggMPCX_LiquWealth'))

import HARK
print(f"HARK version: {HARK.__version__}")

from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
from SetupParamsCSTW import init_infinite

# Create minimal parameter set
params = init_infinite.copy()
params['aXtraCount'] = 24
params['T_cycle'] = 1
params['cycles'] = 0

Rfree = params['Rfree']
params['Rboro'] = Rfree
params['Rsave'] = Rfree

# Create agent
agent = KinkedRconsumerType(**params)

aXtraGrid = agent.aXtraGrid
print(f"\naXtraGrid[0] = {aXtraGrid[0]}")
print(f"aXtraGrid[1] = {aXtraGrid[1]}")

hark_version = HARK.__version__

if hark_version.startswith('0.14'):
    print("\n=== 0.14.1 Grid Construction ===")
    # In 0.14.1, we need to trace through the solver
    # Let's set up the solver manually
    
    # Trigger pre-solve to set up parameters
    agent.pre_solve()
    
    # Check mNrmMinNow
    print(f"mNrmMinNow: {agent.mNrmMinNow if hasattr(agent, 'mNrmMinNow') else 'N/A'}")
    print(f"BoroCnstNat: {agent.BoroCnstNat if hasattr(agent, 'BoroCnstNat') else 'N/A'}")
    
    # The key is: in 0.14.1, the KinkedR solver when KinkBool=False uses:
    # aNrmNow = np.asarray(self.aXtraGrid) + self.mNrmMinNow
    
    # But wait - this is using mNrmMinNow, not BoroCnstNat
    # mNrmMinNow should be 0 when BoroCnstArt is 0 and BoroCnstNat is negative
    
    # Let me check the actual value
    if hasattr(agent, 'mNrmMinNow'):
        mNrmMinNow = agent.mNrmMinNow
    else:
        mNrmMinNow = 0.0  # Default
    
    print(f"\nGrid offset (mNrmMinNow): {mNrmMinNow}")
    print(f"aNrmNow[0] would be: {aXtraGrid[0] + mNrmMinNow}")
    print(f"aNrmNow[1] would be: {aXtraGrid[1] + mNrmMinNow}")
    
    # Now solve and check
    print("\nSolving...")
    agent.solve()
    
    sol = agent.solution[0]
    cFunc = sol.cFunc
    x_list = cFunc.functions[0].x_list
    
    print(f"\nActual cFunc gridpoints:")
    print(f"  x[0] = {x_list[0]}")
    print(f"  x[1] = {x_list[1]}")

elif hark_version.startswith('0.17'):
    print("\n=== 0.17.0 Grid Construction ===")
    
    # In 0.17.0, when Rboro == Rsave, it delegates to solve_one_period_ConsIndShock
    # which uses: aNrmNow = np.asarray(aXtraGrid) + BoroCnstNat
    
    # First, solve to get BoroCnstNat
    print("Solving...")
    agent.solve()
    
    sol = agent.solution[0]
    
    # BoroCnstNat is calculated in the solver
    # Let's trace what happens
    
    # From solve_one_period_ConsIndShock:
    # BoroCnstNat = calc_boro_const_nat(solution_next.mNrmMin, IncShkDstn, Rfree, PermGroFac, use_infimum=False)
    # mNrmMinNow = calc_mNrmMin_from_boro_cnst(BoroCnstArt, BoroCnstNat)
    
    # The key difference might be that 0.17.0 uses BoroCnstNat directly for grid offset
    # while 0.14.1 uses mNrmMinNow (which could be 0 if BoroCnstArt=0)
    
    cFunc = sol.cFunc
    x_list = cFunc.functions[0].x_list
    
    print(f"\nActual cFunc gridpoints:")
    print(f"  x[0] = {x_list[0]} (BoroCnstNat)")
    print(f"  x[1] = {x_list[1]}")
    
    # What BoroCnstNat would be
    BoroCnstNat = x_list[0]  # The first inserted point
    
    print(f"\nGrid offset (BoroCnstNat): {BoroCnstNat}")
    print(f"aNrmNow[0] would be: {aXtraGrid[0] + BoroCnstNat}")
    print(f"aNrmNow[1] would be: {aXtraGrid[1] + BoroCnstNat}")
    
    # After EGM, mNrmNow = cNrmNow + aNrmNow
    # The first point in x_list (after insertion) is BoroCnstNat
    # The second point is mNrmNow[0] from EGM
    
    print(f"\nThe issue: aXtraGrid[0] = {aXtraGrid[0]} is very small")
    print(f"So aNrmNow[0] = {aXtraGrid[0]} + {BoroCnstNat} ≈ {BoroCnstNat}")
    print(f"After EGM, mNrmNow[0] is close to aNrmNow[0] since consumption at low assets is low")
