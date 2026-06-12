#!/usr/bin/env python3
"""
Detailed diagnostic of how each solver constructs its asset grid.
"""

import sys
import os
import numpy as np

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, 'Target_AggMPCX_LiquWealth'))

import HARK
print(f"HARK version: {HARK.__version__}")
print(f"HARK location: {HARK.__file__}")

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

print(f"\n=== Parameters ===")
print(f"Rfree: {Rfree}")
print(f"Rboro: {params['Rboro']}")
print(f"Rsave: {params['Rsave']}")

# Create agent
agent = KinkedRconsumerType(**params)

# Check aXtraGrid
aXtraGrid = agent.aXtraGrid
print(f"\n=== aXtraGrid ===")
print(f"Length: {len(aXtraGrid)}")
print(f"First 10 values: {aXtraGrid[:10]}")
print(f"Last 5 values: {aXtraGrid[-5:]}")

# Check BoroCnstNat calculation
print(f"\n=== Borrowing Constraint ===")
print(f"BoroCnstArt (artificial): {agent.BoroCnstArt}")

# For HARK 0.17.0, check the solver that will be used
hark_version = HARK.__version__
if hark_version.startswith('0.17'):
    print(f"\n=== HARK 0.17.0 Solver Analysis ===")
    print(f"Solver function: {agent.solve_one_period}")
    
    # Check what happens when Rboro == Rsave
    print(f"Rboro == Rsave: {agent.Rboro == agent.Rsave}")
    
    # Let's trace what happens in the solver
    # First, let's manually check what the IndShock solver would do
    
    # The IndShock solver uses: aNrmNow = np.asarray(aXtraGrid) + BoroCnstNat
    # We need to figure out what BoroCnstNat is
    
    # In solve_one_period_ConsIndShock, BoroCnstNat is calculated from
    # calc_boro_const_nat(solution_next.mNrmMin, IncShkDstn, Rfree, PermGroFac, use_infimum=False)
    
    # Let's solve and then check
    print("\nSolving agent...")
    agent.solve()
    
    sol = agent.solution[0]
    print(f"mNrmMin from solution: {sol.mNrmMin}")
    
    # Now let's manually trace the grid construction
    # Check the cFunc's underlying data
    cFunc = sol.cFunc
    if hasattr(cFunc, 'functions') and hasattr(cFunc.functions[0], 'x_list'):
        x_list = cFunc.functions[0].x_list
        print(f"\ncFunc x_list (mNrm gridpoints):")
        print(f"  Length: {len(x_list)}")
        print(f"  First 10: {x_list[:10]}")
        
        # Calculate what the grid "should" be
        # aNrmNow = aXtraGrid + BoroCnstNat
        # Then mNrmNow = cNrmNow + aNrmNow
        
        # What we see in x_list is the final mNrm after adding consumption
        # But the initial aNrmNow would be aXtraGrid + BoroCnstNat
        
        # Let's check if BoroCnstNat matches mNrmMin
        mNrmMin = sol.mNrmMin
        BoroCnstNat_guess = x_list[0]  # Should be at or near BoroCnstNat
        
        print(f"\n  First gridpoint (BoroCnstNat?): {x_list[0]}")
        print(f"  Second gridpoint: {x_list[1]}")
        print(f"  Difference: {x_list[1] - x_list[0]}")

elif hark_version.startswith('0.14'):
    print(f"\n=== HARK 0.14.1 Solver Analysis ===")
    
    # In 0.14.1, the KinkedR solver checks KinkBool = (Rboro > Rsave)
    # When KinkBool is False, it uses: aNrmNow = np.asarray(self.aXtraGrid) + self.mNrmMinNow
    
    print("Solving agent...")
    agent.solve()
    
    sol = agent.solution[0]
    print(f"mNrmMin from solution: {sol.mNrmMin}")
    
    cFunc = sol.cFunc
    if hasattr(cFunc, 'functions') and hasattr(cFunc.functions[0], 'x_list'):
        x_list = cFunc.functions[0].x_list
        print(f"\ncFunc x_list (mNrm gridpoints):")
        print(f"  Length: {len(x_list)}")
        print(f"  First 10: {x_list[:10]}")
        print(f"\n  First gridpoint: {x_list[0]}")
        print(f"  Second gridpoint: {x_list[1]}")
        print(f"  Difference: {x_list[1] - x_list[0]}")
