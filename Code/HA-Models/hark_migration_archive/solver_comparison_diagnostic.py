#!/usr/bin/env python3
"""
Careful diagnostic comparison of HARK 0.14.1 vs 0.17.0 solvers.

This script:
1. Sets up identical parameters for both versions
2. Solves a single period from the terminal period
3. Compares consumption function values at each gridpoint
4. Identifies exactly where discrepancies arise

To run on 0.14.1:
  /home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-baseline/.venv/bin/python solver_comparison_diagnostic.py

To run on 0.17.0:
  /home/econ-ark/GitHub/llorracc/HAFiscal-Latest/.venv/bin/python solver_comparison_diagnostic.py
"""

import sys
import os
import json
import numpy as np

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, 'Target_AggMPCX_LiquWealth'))

def run_single_period_solve():
    """
    Run a single period solve and extract all intermediate values.
    """
    import HARK
    from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
    
    hark_version = HARK.__version__
    print(f"HARK version: {hark_version}")
    print(f"HARK location: {HARK.__file__}")
    
    # Import HAFiscal parameters
    from SetupParamsCSTW import init_infinite
    
    # Create minimal parameter set for clean comparison
    params = init_infinite.copy()
    params['aXtraCount'] = 24  # Small grid for easier comparison
    params['T_cycle'] = 1      # Single period
    params['cycles'] = 0       # Infinite horizon
    
    # Explicitly set Rboro and Rsave to ensure they match
    Rfree = params['Rfree']
    params['Rboro'] = Rfree
    params['Rsave'] = Rfree
    
    print(f"\n=== Parameters ===")
    print(f"Rfree: {Rfree}")
    print(f"Rboro: {params['Rboro']}")
    print(f"Rsave: {params['Rsave']}")
    print(f"CRRA: {params['CRRA']}")
    print(f"DiscFac: {params['DiscFac']}")
    print(f"PermGroFac: {params['PermGroFac']}")
    print(f"aXtraCount: {params['aXtraCount']}")
    
    # Create agent
    agent = KinkedRconsumerType(**params)
    
    # Get the aXtraGrid that will be used
    aXtraGrid = agent.aXtraGrid
    print(f"\naXtraGrid (first 10): {aXtraGrid[:10]}")
    print(f"aXtraGrid length: {len(aXtraGrid)}")
    
    # Solve the agent
    print(f"\n=== Solving ===")
    agent.solve()
    
    # Get the solution
    sol = agent.solution[0]
    
    # Extract consumption function
    cFunc = sol.cFunc
    
    # Get the underlying data
    print(f"\n=== Solution Structure ===")
    print(f"cFunc type: {type(cFunc)}")
    
    # For LowerEnvelope, get the underlying functions
    if hasattr(cFunc, 'functions'):
        print(f"cFunc has {len(cFunc.functions)} underlying functions")
        for i, f in enumerate(cFunc.functions):
            print(f"  Function {i}: {type(f)}")
            if hasattr(f, 'x_list'):
                print(f"    x_list length: {len(f.x_list)}")
                print(f"    x_list first 5: {f.x_list[:5]}")
                print(f"    y_list first 5: {f.y_list[:5]}")
    
    # Get mNrmMin and related values
    print(f"\n=== Key Solution Values ===")
    print(f"mNrmMin: {sol.mNrmMin}")
    print(f"hNrm: {sol.hNrm}")
    print(f"MPCmin: {sol.MPCmin}")
    print(f"MPCmax: {sol.MPCmax}")
    
    # Evaluate cFunc at specific gridpoints
    test_m_values = np.array([0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0])
    print(f"\n=== cFunc Evaluation at Test Points ===")
    cFunc_values = []
    for m in test_m_values:
        c = cFunc(m)
        cFunc_values.append(c)
        print(f"  m={m:6.1f}: c={c:.15f}")
    
    # Also evaluate at the actual gridpoints used by the solver
    if hasattr(cFunc, 'functions') and hasattr(cFunc.functions[0], 'x_list'):
        x_grid = cFunc.functions[0].x_list
        y_grid = cFunc.functions[0].y_list
        print(f"\n=== cFunc at Internal Gridpoints (first 15) ===")
        for i in range(min(15, len(x_grid))):
            print(f"  m={x_grid[i]:12.8f}: c={y_grid[i]:.15f}")
    
    # Save results to JSON
    results = {
        "hark_version": hark_version,
        "Rfree": Rfree,
        "Rboro": params['Rboro'],
        "Rsave": params['Rsave'],
        "CRRA": params['CRRA'],
        "DiscFac": params['DiscFac'],
        "mNrmMin": float(sol.mNrmMin),
        "hNrm": float(sol.hNrm),
        "MPCmin": float(sol.MPCmin),
        "MPCmax": float(sol.MPCmax),
        "test_m_values": list(test_m_values),
        "cFunc_at_test_points": [float(c) for c in cFunc_values],
    }
    
    # Add internal gridpoints if available
    if hasattr(cFunc, 'functions') and hasattr(cFunc.functions[0], 'x_list'):
        results["internal_m_grid"] = [float(x) for x in cFunc.functions[0].x_list]
        results["internal_c_grid"] = [float(y) for y in cFunc.functions[0].y_list]
    
    output_file = f"/tmp/solver_diagnostic_{hark_version.replace('.', '_')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n=== Results saved to {output_file} ===")
    
    return results


def compare_results():
    """
    Compare results from both versions.
    """
    import json
    
    try:
        with open("/tmp/solver_diagnostic_0_14_1.json", 'r') as f:
            results_014 = json.load(f)
    except FileNotFoundError:
        print("0.14.1 results not found. Run with 0.14.1 first.")
        return
    
    try:
        with open("/tmp/solver_diagnostic_0_17_0.json", 'r') as f:
            results_017 = json.load(f)
    except FileNotFoundError:
        print("0.17.0 results not found. Run with 0.17.0 first.")
        return
    
    print("\n" + "=" * 70)
    print("COMPARISON OF HARK 0.14.1 vs 0.17.0 SOLVER RESULTS")
    print("=" * 70)
    
    # Compare key values
    print("\n=== Key Solution Values ===")
    for key in ["mNrmMin", "hNrm", "MPCmin", "MPCmax"]:
        v014 = results_014[key]
        v017 = results_017[key]
        diff = abs(v017 - v014)
        rel_diff = diff / abs(v014) if v014 != 0 else float('inf')
        match = "✓" if rel_diff < 1e-10 else "✗"
        print(f"  {key:10s}: 0.14.1={v014:20.15f}  0.17.0={v017:20.15f}  diff={diff:.2e} ({rel_diff*100:.6f}%) {match}")
    
    # Compare cFunc at test points
    print("\n=== cFunc at Test Points ===")
    for i, m in enumerate(results_014["test_m_values"]):
        c014 = results_014["cFunc_at_test_points"][i]
        c017 = results_017["cFunc_at_test_points"][i]
        diff = abs(c017 - c014)
        rel_diff = diff / abs(c014) if c014 != 0 else float('inf')
        match = "✓" if rel_diff < 1e-10 else "✗"
        print(f"  m={m:6.1f}: 0.14.1={c014:18.15f}  0.17.0={c017:18.15f}  diff={diff:.2e} ({rel_diff*100:.6f}%) {match}")
    
    # Compare internal gridpoints if available
    if "internal_m_grid" in results_014 and "internal_m_grid" in results_017:
        print("\n=== Internal Gridpoints ===")
        
        m_grid_014 = results_014["internal_m_grid"]
        c_grid_014 = results_014["internal_c_grid"]
        m_grid_017 = results_017["internal_m_grid"]
        c_grid_017 = results_017["internal_c_grid"]
        
        print(f"  0.14.1 grid length: {len(m_grid_014)}")
        print(f"  0.17.0 grid length: {len(m_grid_017)}")
        
        if len(m_grid_014) != len(m_grid_017):
            print("  ⚠️  GRID LENGTHS DIFFER!")
        
        # Find maximum discrepancy
        max_m_diff = 0
        max_c_diff = 0
        max_c_rel_diff = 0
        
        min_len = min(len(m_grid_014), len(m_grid_017))
        print(f"\n  First 15 gridpoints comparison:")
        for i in range(min(15, min_len)):
            m014, m017 = m_grid_014[i], m_grid_017[i]
            c014, c017 = c_grid_014[i], c_grid_017[i]
            
            m_diff = abs(m017 - m014)
            c_diff = abs(c017 - c014)
            c_rel_diff = c_diff / abs(c014) if c014 != 0 else float('inf')
            
            max_m_diff = max(max_m_diff, m_diff)
            max_c_diff = max(max_c_diff, c_diff)
            max_c_rel_diff = max(max_c_rel_diff, c_rel_diff)
            
            m_match = "✓" if m_diff < 1e-10 else "✗"
            c_match = "✓" if c_rel_diff < 1e-10 else "✗"
            
            print(f"    [{i:2d}] m: {m014:12.8f} vs {m017:12.8f} ({m_diff:.2e}) {m_match}")
            print(f"         c: {c014:12.8f} vs {c017:12.8f} ({c_rel_diff*100:.6f}%) {c_match}")
        
        print(f"\n  Maximum m difference: {max_m_diff:.2e}")
        print(f"  Maximum c difference: {max_c_diff:.2e}")
        print(f"  Maximum c relative diff: {max_c_rel_diff*100:.6f}%")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--compare":
        compare_results()
    else:
        run_single_period_solve()
        print("\n" + "-" * 70)
        print("To compare results, run both versions then:")
        print("  python solver_comparison_diagnostic.py --compare")
