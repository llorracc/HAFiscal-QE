#!/usr/bin/env python3
"""
Diagnose Solver Divergence

This script runs in isolation to trace exactly where the solver diverges
between HARK 0.14.1 and 0.17.0.
"""

import os
import sys
import json
import numpy as np

script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

RESULTS_FILE = os.environ.get('QUICKTEST_RESULTS_FILE', '/tmp/hafiscal_quicktest/diagnose_solver.json')
VERSION = os.environ.get('HARK_VERSION', 'unknown')

def run_diagnosis():
    """Run detailed solver diagnosis."""
    print(f"=== Solver Divergence Diagnosis (HARK {VERSION}) ===")
    results = {'HARK_version': VERSION}
    
    np.random.seed(12345)
    
    try:
        import HARK
        hark_version = HARK.__version__
        print(f"Actual HARK version: {hark_version}")
        results['actual_version'] = hark_version
        
        if hark_version.startswith('0.14'):
            from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
        else:
            from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
        
        sys.path.insert(0, os.path.join(parent_dir, 'Target_AggMPCX_LiquWealth'))
        from SetupParamsCSTW import init_infinite
        
        # Use IDENTICAL parameters
        params = init_infinite.copy()
        params['T_sim'] = 10
        params['AgentCount'] = 200
        
        # Record key parameters
        print("\n--- Key Parameters ---")
        key_params = ['CRRA', 'Rfree', 'DiscFac', 'LivPrb', 'PermGroFac', 
                      'PermShkStd', 'TranShkStd', 'UnempPrb', 'IncUnemp',
                      'aXtraMax', 'aXtraCount', 'aXtraExtra', 'BoroCnstArt']
        
        for p in key_params:
            val = params.get(p, 'NOT SET')
            if isinstance(val, list) and len(val) > 0:
                val = val[0]
            print(f"  {p}: {val}")
            results[f'param_{p}'] = str(val)
        
        print("\n--- Creating Agent ---")
        agent = KinkedRconsumerType(**params)
        
        # Check internal attributes BEFORE solve
        print("\n--- Pre-Solve Agent State ---")
        
        # Check aXtraGrid
        if hasattr(agent, 'aXtraGrid'):
            aXtraGrid = agent.aXtraGrid
            print(f"  aXtraGrid: len={len(aXtraGrid)}, min={min(aXtraGrid):.4f}, max={max(aXtraGrid):.4f}")
            results['aXtraGrid_len'] = len(aXtraGrid)
            results['aXtraGrid_min'] = float(min(aXtraGrid))
            results['aXtraGrid_max'] = float(max(aXtraGrid))
            results['aXtraGrid_first5'] = [float(x) for x in aXtraGrid[:5]]
            results['aXtraGrid_last5'] = [float(x) for x in aXtraGrid[-5:]]
        else:
            print("  aXtraGrid: NOT SET YET")
        
        # Check income distribution before solve
        inc_dstn_attr = 'IncShkDstn' if hasattr(agent, 'IncShkDstn') else 'IncomeDstn'
        if hasattr(agent, inc_dstn_attr):
            inc_dstn = getattr(agent, inc_dstn_attr)
            try:
                if inc_dstn is not None and hasattr(inc_dstn, '__getitem__'):
                    dstn = inc_dstn[0]
                    if hasattr(dstn, 'atoms'):
                        print(f"  {inc_dstn_attr}: atoms shape={dstn.atoms.shape}, pmv len={len(dstn.pmv)}")
                        results['IncShkDstn_shape'] = list(dstn.atoms.shape)
                    elif hasattr(dstn, 'X'):
                        print(f"  {inc_dstn_attr}: X shape={dstn.X.shape}, pmf len={len(dstn.pmf)}")
                        results['IncShkDstn_shape'] = list(dstn.X.shape)
            except (TypeError, IndexError) as e:
                print(f"  {inc_dstn_attr}: {type(inc_dstn).__name__} (could not index)")
        
        print("\n--- Solving Agent ---")
        agent.solve()
        
        # Check solution structure
        print("\n--- Post-Solve Analysis ---")
        
        if hasattr(agent, 'solution') and len(agent.solution) > 0:
            sol = agent.solution[0]
            print(f"  Solution type: {type(sol).__name__}")
            results['solution_type'] = type(sol).__name__
            
            # Get cFunc
            if hasattr(sol, 'cFunc'):
                cFunc = sol.cFunc
                if isinstance(cFunc, list):
                    cFunc = cFunc[0]
                    print(f"  cFunc: list with {len(sol.cFunc)} elements, using first")
                    results['cFunc_is_list'] = True
                    results['cFunc_list_len'] = len(sol.cFunc)
                else:
                    print(f"  cFunc: single function")
                    results['cFunc_is_list'] = False
                
                # Check cFunc internal structure
                print(f"  cFunc type: {type(cFunc).__name__}")
                results['cFunc_type'] = type(cFunc).__name__
                
                # Check if it's a LinearInterp
                if hasattr(cFunc, 'x_list') and hasattr(cFunc, 'y_list'):
                    x_list = cFunc.x_list
                    y_list = cFunc.y_list
                    print(f"  cFunc.x_list: len={len(x_list)}, range=[{min(x_list):.4f}, {max(x_list):.4f}]")
                    print(f"  cFunc.y_list: len={len(y_list)}, range=[{min(y_list):.4f}, {max(y_list):.4f}]")
                    results['cFunc_x_len'] = len(x_list)
                    results['cFunc_x_min'] = float(min(x_list))
                    results['cFunc_x_max'] = float(max(x_list))
                    results['cFunc_y_min'] = float(min(y_list))
                    results['cFunc_y_max'] = float(max(y_list))
                    
                    # Full grid points
                    results['cFunc_x_list'] = [float(x) for x in x_list]
                    results['cFunc_y_list'] = [float(y) for y in y_list]
                
                # Check extrapolation settings
                if hasattr(cFunc, 'intercept_limit'):
                    print(f"  cFunc.intercept_limit: {cFunc.intercept_limit}")
                    results['cFunc_intercept_limit'] = float(cFunc.intercept_limit) if cFunc.intercept_limit is not None else None
                if hasattr(cFunc, 'slope_limit'):
                    print(f"  cFunc.slope_limit: {cFunc.slope_limit}")
                    results['cFunc_slope_limit'] = float(cFunc.slope_limit) if cFunc.slope_limit is not None else None
                
                # Evaluate at test points
                print("\n--- cFunc Evaluation at Test Points ---")
                m_test = np.array([0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 50.0])
                c_values = []
                
                for m in m_test:
                    try:
                        c = float(cFunc(m))
                        c_values.append(c)
                        print(f"  m={m:5.1f}: c={c:.10f}")
                    except Exception as e:
                        print(f"  m={m:5.1f}: ERROR - {e}")
                        c_values.append(None)
                
                results['m_test'] = list(m_test)
                results['c_values'] = c_values
            
            # Check MPCmin/MPCmax
            if hasattr(sol, 'MPCmin'):
                print(f"\n  MPCmin: {sol.MPCmin}")
                results['MPCmin'] = float(sol.MPCmin) if sol.MPCmin is not None else None
            if hasattr(sol, 'MPCmax'):
                print(f"  MPCmax: {sol.MPCmax}")
                results['MPCmax'] = float(sol.MPCmax) if sol.MPCmax is not None else None
            
            # Check hNrm (human wealth)
            if hasattr(sol, 'hNrm'):
                print(f"  hNrm: {sol.hNrm}")
                results['hNrm'] = float(sol.hNrm) if sol.hNrm is not None else None
            
            # Check mNrmMin (minimum m)
            if hasattr(sol, 'mNrmMin'):
                print(f"  mNrmMin: {sol.mNrmMin}")
                results['mNrmMin'] = float(sol.mNrmMin) if sol.mNrmMin is not None else None
        
        print("\n--- Diagnosis Complete ---")
        
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        results['error'] = str(e)
        results['traceback'] = traceback.format_exc()
    
    # Save results
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {RESULTS_FILE}")
    return results

if __name__ == '__main__':
    run_diagnosis()
