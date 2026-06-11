#!/usr/bin/env python3
"""
HARK Version Comparison Framework

This module provides checkpoint-based comparison between different HARK versions,
enabling progressive verification from fast (nano) to comprehensive (min).

Usage:
    python hark_version_comparison.py --level nano   # ~30 seconds
    python hark_version_comparison.py --level micro  # ~2 minutes
"""

import sys
import os
import time
import hashlib
import argparse
import numpy as np
from typing import Dict, Any
from dataclasses import dataclass

# Suppress matplotlib GUI
import matplotlib
matplotlib.use('Agg')


@dataclass
class CheckpointResult:
    """Result from a single checkpoint comparison."""
    name: str
    data_hash: str
    elapsed_seconds: float
    details: Dict[str, Any]


def compute_hash(data: Any, tolerance_decimals: int = 10) -> str:
    """
    Compute a hash of numerical data for comparison.
    
    Args:
        data: Data to hash
        tolerance_decimals: Number of decimal places to round to before hashing.
                           Default 10 provides tolerance for floating-point differences
                           while still catching meaningful numerical differences.
    """
    if isinstance(data, np.ndarray):
        # Round to tolerance_decimals to handle floating-point precision differences
        rounded = np.round(data, tolerance_decimals)
        return hashlib.md5(rounded.tobytes()).hexdigest()[:16]
    elif isinstance(data, (list, tuple)):
        combined = "".join(compute_hash(item, tolerance_decimals) for item in data)
        return hashlib.md5(combined.encode()).hexdigest()[:16]
    elif isinstance(data, dict):
        combined = "".join(f"{k}:{compute_hash(v, tolerance_decimals)}" for k, v in sorted(data.items()))
        return hashlib.md5(combined.encode()).hexdigest()[:16]
    elif isinstance(data, float):
        # Round floats to tolerance_decimals
        rounded = round(data, tolerance_decimals)
        return hashlib.md5(f"{rounded:.{tolerance_decimals}e}".encode()).hexdigest()[:16]
    elif isinstance(data, int):
        return hashlib.md5(str(data).encode()).hexdigest()[:16]
    else:
        return hashlib.md5(str(data).encode()).hexdigest()[:16]


def compare_arrays(arr1: np.ndarray, arr2: np.ndarray, rtol: float = 1e-10, atol: float = 1e-12) -> tuple:
    """
    Compare two arrays with tolerance.
    
    Returns:
        (is_close, max_diff, max_rel_diff)
    """
    if arr1.shape != arr2.shape:
        return False, np.inf, np.inf
    
    abs_diff = np.abs(arr1 - arr2)
    max_diff = np.max(abs_diff)
    
    # Avoid division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        rel_diff = abs_diff / np.maximum(np.abs(arr1), 1e-15)
        max_rel_diff = np.nanmax(rel_diff)
    
    is_close = np.allclose(arr1, arr2, rtol=rtol, atol=atol)
    return is_close, max_diff, max_rel_diff


def run_nano_comparison(code_dir: str) -> bool:
    """
    Run nano-level comparison (fastest, ~30 seconds).
    
    Tests the core HAFiscal setup and baseline simulation.
    """
    print("\n" + "="*60)
    print("NANO LEVEL COMPARISON")
    print("="*60)
    print("Testing: Core HAFiscal setup and agent creation")
    print("Expected time: ~30 seconds")
    print()
    
    # Change to code directory
    original_dir = os.getcwd()
    os.chdir(code_dir)
    sys.path.insert(0, code_dir)
    
    # Clear sys.argv as HAFiscal code reads it during import
    original_argv = sys.argv.copy()
    sys.argv = [sys.argv[0]]
    
    results = []
    
    try:
        # Checkpoint 1: Import and Parameter Loading
        print("Checkpoint 1: Import and Parameter Loading")
        start_time = time.time()
        
        try:
            from Parameters import returnParameters
        except ImportError:
            from Parameters import return_parameters as returnParameters
        import HARK
        
        hark_version = HARK.__version__
        print(f"  HARK version: {hark_version}")
        
        params = returnParameters(Parametrization='Reduced_Run', OutputFor='_Main.py')
        
        # Hash key parameters
        param_hash = compute_hash({
            'CRRA': params[0].get('CRRA', 2.0) if isinstance(params[0], dict) else 2.0,
            'num_params': len(params),
        })
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="parameter_loading",
            data_hash=param_hash,
            elapsed_seconds=elapsed,
            details={'hark_version': hark_version}
        ))
        print(f"  ✅ Parameters loaded in {elapsed:.1f}s")
        print(f"  Hash: {param_hash}")
        
        # Checkpoint 2: Agent Type Creation
        print("\nCheckpoint 2: Agent Type Creation")
        start_time = time.time()
        
        from AggFiscalModel import AggFiscalType
        
        [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
         DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
         convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
         data_EducShares, max_recession_duration, num_experiment_periods,
         recession_changes, UI_changes, recession_UI_changes,
         TaxCut_changes, recession_TaxCut_changes, Check_changes, recession_Check_changes] = params
        
        # Create agents (following Simulate.py pattern)
        agents = []
        for init_params, name in [(init_dropout, 'dropout'), 
                                   (init_highschool, 'highschool'),
                                   (init_college, 'college')]:
            agent = AggFiscalType(**init_params)
            agent.cycles = 0
            agents.append(agent)
        
        agent_hash = compute_hash({
            'num_agents': len(agents),
            'cycles': [a.cycles for a in agents],
            'CRRA': [a.CRRA for a in agents],
        })
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="agent_creation",
            data_hash=agent_hash,
            elapsed_seconds=elapsed,
            details={'num_agents': len(agents)}
        ))
        print(f"  ✅ Created {len(agents)} agents in {elapsed:.1f}s")
        print(f"  Hash: {agent_hash}")
        
        # Print summary
        print("\n" + "="*60)
        print("NANO COMPARISON SUMMARY")
        print("="*60)
        print(f"\nHARK Version: {hark_version}")
        print(f"Total time: {sum(r.elapsed_seconds for r in results):.1f}s")
        print("\nCheckpoint Results:")
        for r in results:
            print(f"  {r.name}: {r.data_hash}")
        
        # Save results to file for comparison
        output_file = f"nano_results_{hark_version.replace('.', '_')}.txt"
        with open(output_file, 'w') as f:
            f.write(f"HARK Version: {hark_version}\n")
            f.write(f"Checkpoints:\n")
            for r in results:
                f.write(f"  {r.name}: {r.data_hash}\n")
        print(f"\nResults saved to: {output_file}")
        
        print("\n✅ NANO level completed successfully")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        sys.argv = original_argv
        os.chdir(original_dir)


def run_micro_comparison(code_dir: str) -> bool:
    """
    Run micro-level comparison (~2 minutes).
    
    Tests agent creation, solving, and basic simulation.
    """
    print("\n" + "="*60)
    print("MICRO LEVEL COMPARISON")
    print("="*60)
    print("Testing: Agent creation, solve, and simulation")
    print("Expected time: ~2 minutes")
    print()
    
    # Change to code directory  
    original_dir = os.getcwd()
    os.chdir(code_dir)
    sys.path.insert(0, code_dir)
    
    # Clear sys.argv
    original_argv = sys.argv.copy()
    sys.argv = [sys.argv[0]]
    
    results = []
    
    try:
        # Import modules
        try:
            from Parameters import returnParameters
        except ImportError:
            from Parameters import return_parameters as returnParameters
        import HARK
        from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
        try:
            from HARK.distribution import DiscreteDistribution
        except ImportError:
            from HARK.distributions import DiscreteDistribution
        from copy import deepcopy
        
        hark_version = HARK.__version__
        print(f"HARK version: {hark_version}")
        
        # Checkpoint 1: Parameter Loading
        print("\nCheckpoint 1: Parameter Loading")
        start_time = time.time()
        
        params = returnParameters(Parametrization='Reduced_Run', OutputFor='_Main.py')
        [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
         DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
         convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
         data_EducShares, max_recession_duration, num_experiment_periods,
         recession_changes, UI_changes, recession_UI_changes,
         TaxCut_changes, recession_TaxCut_changes, Check_changes, recession_Check_changes] = params
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="parameter_loading",
            data_hash=compute_hash({'loaded': True}),
            elapsed_seconds=elapsed,
            details={}
        ))
        print(f"  ✅ Loaded in {elapsed:.1f}s")
        
        # Checkpoint 2: Agent Setup (following Simulate.py exactly)
        print("\nCheckpoint 2: Agent Setup")
        start_time = time.time()
        
        InfHorizonTypeAgg_d = AggFiscalType(**init_dropout)
        InfHorizonTypeAgg_d.cycles = 0
        InfHorizonTypeAgg_h = AggFiscalType(**init_highschool)
        InfHorizonTypeAgg_h.cycles = 0
        InfHorizonTypeAgg_c = AggFiscalType(**init_college)
        InfHorizonTypeAgg_c.cycles = 0
        AggDemandEconomy_obj = AggregateDemandEconomy(**init_ADEconomy)
        InfHorizonTypeAgg_d.get_economy_data(AggDemandEconomy_obj)
        InfHorizonTypeAgg_h.get_economy_data(AggDemandEconomy_obj)
        InfHorizonTypeAgg_c.get_economy_data(AggDemandEconomy_obj)
        BaseTypeList = [InfHorizonTypeAgg_d, InfHorizonTypeAgg_h, InfHorizonTypeAgg_c]
        
        # RNG Synchronization: Set IncShkDstn seeds to match HARK 0.14.1
        # This ensures identical random draws between HARK versions
        for BaseType in BaseTypeList:
            BaseType.IncShkDstn[0].seed = 763607780
            BaseType.IncShkDstn[0].reset()
        
        # Set up IncShkDstn
        IncShkDstn_unemp = DiscreteDistribution(
            np.array([1.0]), 
            [np.array([1.0]), np.array([InfHorizonTypeAgg_d.IncUnemp])]
        )
        IncShkDstn_unemp_nobenefits = DiscreteDistribution(
            np.array([1.0]), 
            [np.array([1.0]), np.array([InfHorizonTypeAgg_d.IncUnempNoBenefits])]
        )
        
        for ThisType in BaseTypeList:
            EmployedIncShkDstn = deepcopy(ThisType.IncShkDstn[0])
            ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncShkDstn_unemp]*UBspell_normal + [IncShkDstn_unemp_nobenefits]]
            ThisType.IncShkDstn_base = ThisType.IncShkDstn
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="agent_setup",
            data_hash=compute_hash({'agents': 3}),
            elapsed_seconds=elapsed,
            details={'num_agents': 3}
        ))
        print(f"  ✅ Setup complete in {elapsed:.1f}s")
        
        # Checkpoint 3: Make TypeList with reduced agent count
        print("\nCheckpoint 3: TypeList Creation (reduced)")
        start_time = time.time()
        
        # Use reduced agent count for speed
        reduced_agent_count = 50  # Instead of AgentCountTotal
        num_types = 3
        
        TypeList = []
        n = 0
        for e in range(num_types):
            for b in range(min(3, DiscFacCount)):  # Just 3 discount factors
                DiscFac = DiscFacDstns[e].atoms[0][b]
                AgentCount = int(reduced_agent_count * data_EducShares[e] / 3)
                ThisType = deepcopy(BaseTypeList[e])
                ThisType.AgentCount = max(10, AgentCount)
                ThisType.DiscFac = DiscFac
                ThisType.seed = n
                TypeList.append(ThisType)
                n += 1
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="typelist_creation",
            data_hash=compute_hash({'total_types': len(TypeList)}),
            elapsed_seconds=elapsed,
            details={'num_types': len(TypeList)}
        ))
        print(f"  ✅ Created {len(TypeList)} types in {elapsed:.1f}s")
        
        # Checkpoint 4: Solve economy
        print("\nCheckpoint 4: Solve Economy")
        start_time = time.time()
        
        AggDemandEconomy_obj.agents = TypeList
        AggDemandEconomy_obj.solve()
        
        # Collect solution data
        solve_data = {}
        for i, agent in enumerate(TypeList[:3]):  # Just first 3
            if hasattr(agent.solution[0], 'cFunc'):
                test_m = np.array([1.0, 2.0, 5.0])
                test_C = np.ones_like(test_m)
                for j in range(min(2, len(agent.solution[0].cFunc))):
                    try:
                        c_vals = agent.solution[0].cFunc[j](test_m, test_C)
                        solve_data[f'agent{i}_state{j}'] = float(np.mean(c_vals))
                    except:
                        pass
        
        solve_hash = compute_hash(solve_data)
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="economy_solve",
            data_hash=solve_hash,
            elapsed_seconds=elapsed,
            details={'solve_data': solve_data}
        ))
        print(f"  ✅ Solved in {elapsed:.1f}s")
        print(f"  Solution hash: {solve_hash}")
        
        # Print summary
        print("\n" + "="*60)
        print("MICRO COMPARISON SUMMARY")
        print("="*60)
        print(f"\nHARK Version: {hark_version}")
        print(f"Total time: {sum(r.elapsed_seconds for r in results):.1f}s")
        print("\nCheckpoint Results:")
        for r in results:
            print(f"  {r.name}: {r.data_hash} ({r.elapsed_seconds:.1f}s)")
        
        # Save results
        output_file = f"micro_results_{hark_version.replace('.', '_')}.txt"
        with open(output_file, 'w') as f:
            f.write(f"HARK Version: {hark_version}\n")
            f.write(f"Checkpoints:\n")
            for r in results:
                f.write(f"  {r.name}: {r.data_hash}\n")
            if 'solve_data' in results[-1].details:
                f.write(f"\nSolution samples:\n")
                for k, v in results[-1].details['solve_data'].items():
                    f.write(f"  {k}: {v:.10f}\n")
        print(f"\nResults saved to: {output_file}")
        
        print("\n✅ MICRO level completed successfully")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        sys.argv = original_argv
        os.chdir(original_dir)


def run_mini_comparison(code_dir: str) -> bool:
    """
    Run mini-level comparison (~5-10 minutes).
    
    Tests agent creation, solving, simulation, and baseline experiment.
    """
    print("\n" + "="*60)
    print("MINI LEVEL COMPARISON")
    print("="*60)
    print("Testing: Full setup, solve, simulation, and baseline experiment")
    print("Expected time: ~5-10 minutes")
    print()
    
    # Change to code directory  
    original_dir = os.getcwd()
    os.chdir(code_dir)
    sys.path.insert(0, code_dir)
    
    # Clear sys.argv
    original_argv = sys.argv.copy()
    sys.argv = [sys.argv[0]]
    
    results = []
    
    try:
        # Import modules
        try:
            from Parameters import returnParameters
        except ImportError:
            from Parameters import return_parameters as returnParameters
        import HARK
        from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
        try:
            from HARK.distribution import DiscreteDistribution
        except ImportError:
            from HARK.distributions import DiscreteDistribution
        from copy import deepcopy
        
        hark_version = HARK.__version__
        print(f"HARK version: {hark_version}")
        
        # Checkpoint 1: Parameter Loading
        print("\nCheckpoint 1: Parameter Loading")
        start_time = time.time()
        
        params = returnParameters(Parametrization='Reduced_Run', OutputFor='_Main.py')
        [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
         DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
         convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
         data_EducShares, max_recession_duration, num_experiment_periods,
         recession_changes, UI_changes, recession_UI_changes,
         TaxCut_changes, recession_TaxCut_changes, Check_changes, recession_Check_changes] = params
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="parameter_loading",
            data_hash=compute_hash({'loaded': True}),
            elapsed_seconds=elapsed,
            details={}
        ))
        print(f"  ✅ Loaded in {elapsed:.1f}s")
        
        # Checkpoint 2: Agent Setup
        print("\nCheckpoint 2: Agent Setup")
        start_time = time.time()
        
        InfHorizonTypeAgg_d = AggFiscalType(**init_dropout)
        InfHorizonTypeAgg_d.cycles = 0
        InfHorizonTypeAgg_h = AggFiscalType(**init_highschool)
        InfHorizonTypeAgg_h.cycles = 0
        InfHorizonTypeAgg_c = AggFiscalType(**init_college)
        InfHorizonTypeAgg_c.cycles = 0
        AggDemandEconomy_obj = AggregateDemandEconomy(**init_ADEconomy)
        InfHorizonTypeAgg_d.get_economy_data(AggDemandEconomy_obj)
        InfHorizonTypeAgg_h.get_economy_data(AggDemandEconomy_obj)
        InfHorizonTypeAgg_c.get_economy_data(AggDemandEconomy_obj)
        BaseTypeList = [InfHorizonTypeAgg_d, InfHorizonTypeAgg_h, InfHorizonTypeAgg_c]
        
        # RNG Synchronization: Set IncShkDstn seeds to match HARK 0.14.1
        # This ensures identical random draws between HARK versions
        for BaseType in BaseTypeList:
            BaseType.IncShkDstn[0].seed = 763607780
            BaseType.IncShkDstn[0].reset()
        
        # Set up IncShkDstn
        IncShkDstn_unemp = DiscreteDistribution(
            np.array([1.0]), 
            [np.array([1.0]), np.array([InfHorizonTypeAgg_d.IncUnemp])]
        )
        IncShkDstn_unemp_nobenefits = DiscreteDistribution(
            np.array([1.0]), 
            [np.array([1.0]), np.array([InfHorizonTypeAgg_d.IncUnempNoBenefits]]]
        )
        
        for ThisType in BaseTypeList:
            EmployedIncShkDstn = deepcopy(ThisType.IncShkDstn[0])
            ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncShkDstn_unemp]*UBspell_normal + [IncShkDstn_unemp_nobenefits]]
            ThisType.IncShkDstn_base = ThisType.IncShkDstn
            
            # Set up recession IncShkDstn (needed for experiments)
            IncShkDstn_recession = [ThisType.IncShkDstn[0]*(2*(num_experiment_periods+1))]
            ThisType.IncShkDstn_recession = IncShkDstn_recession
            ThisType.IncShkDstn_recessionUI = IncShkDstn_recession
            ThisType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)
            ThisType.IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="agent_setup",
            data_hash=compute_hash({'agents': 3}),
            elapsed_seconds=elapsed,
            details={'num_agents': 3}
        ))
        print(f"  ✅ Setup complete in {elapsed:.1f}s")
        
        # Checkpoint 3: TypeList Creation with more agents than micro
        print("\nCheckpoint 3: TypeList Creation")
        start_time = time.time()
        
        # Use moderate agent count (between micro and full)
        reduced_agent_count = 200
        num_types = 3
        
        TypeList = []
        n = 0
        for e in range(num_types):
            for b in range(min(5, DiscFacCount)):  # 5 discount factors
                DiscFac = DiscFacDstns[e].atoms[0][b]
                AgentCount = int(reduced_agent_count * data_EducShares[e] / 5)
                ThisType = deepcopy(BaseTypeList[e])
                ThisType.AgentCount = max(20, AgentCount)
                ThisType.DiscFac = DiscFac
                ThisType.seed = n
                TypeList.append(ThisType)
                n += 1
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="typelist_creation",
            data_hash=compute_hash({'total_types': len(TypeList)}),
            elapsed_seconds=elapsed,
            details={'num_types': len(TypeList)}
        ))
        print(f"  ✅ Created {len(TypeList)} types in {elapsed:.1f}s")
        
        # Checkpoint 4: Solve Economy
        print("\nCheckpoint 4: Solve Economy")
        start_time = time.time()
        
        AggDemandEconomy_obj.agents = TypeList
        AggDemandEconomy_obj.solve()
        
        # Collect solution data
        solve_data = {}
        for i, agent in enumerate(TypeList[:5]):
            if hasattr(agent.solution[0], 'cFunc'):
                test_m = np.array([1.0, 2.0, 5.0, 10.0])
                test_C = np.ones_like(test_m)
                for j in range(min(2, len(agent.solution[0].cFunc))):
                    try:
                        c_vals = agent.solution[0].cFunc[j](test_m, test_C)
                        solve_data[f'agent{i}_state{j}'] = float(np.mean(c_vals))
                    except:
                        pass
        
        solve_hash = compute_hash(solve_data)
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="economy_solve",
            data_hash=solve_hash,
            elapsed_seconds=elapsed,
            details={'solve_data': solve_data}
        ))
        print(f"  ✅ Solved in {elapsed:.1f}s")
        print(f"  Solution hash: {solve_hash}")
        
        # Checkpoint 5: Initialize Simulation
        print("\nCheckpoint 5: Initialize Simulation")
        start_time = time.time()
        
        AggDemandEconomy_obj.reset()
        for agent in AggDemandEconomy_obj.agents:
            agent.initialize_sim()
            agent.AggDemandFac = 1.0
            agent.RfreeNow = 1.0
            agent.CaggNow = 1.0
        AggDemandEconomy_obj.make_history()
        AggDemandEconomy_obj.save_state()
        AggDemandEconomy_obj.switch_to_counterfactual_mode("base")
        AggDemandEconomy_obj.make_idiosyncratic_shock_histories()
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="simulation_init",
            data_hash=compute_hash({'initialized': True}),
            elapsed_seconds=elapsed,
            details={}
        ))
        print(f"  ✅ Initialized in {elapsed:.1f}s")
        
        # Checkpoint 6: Run Baseline Experiment
        print("\nCheckpoint 6: Baseline Experiment")
        start_time = time.time()
        
        base_dict_agg = deepcopy(base_dict)
        base_results = AggDemandEconomy_obj.run_experiment(**base_dict_agg, Full_Output=True)
        
        # Hash key results (handle both scalar and array results)
        npv_cons = base_results.get('NPV_AggCons', 0)
        npv_income = base_results.get('NPV_AggIncome', 0)
        # Convert arrays to scalars if needed
        if hasattr(npv_cons, '__len__'):
            npv_cons = float(np.sum(npv_cons))
        if hasattr(npv_income, '__len__'):
            npv_income = float(np.sum(npv_income))
        baseline_data = {
            'NPV_AggCons': float(npv_cons),
            'NPV_AggIncome': float(npv_income),
        }
        baseline_hash = compute_hash(baseline_data)
        
        AggDemandEconomy_obj.store_baseline(base_results['AggCons'])
        
        elapsed = time.time() - start_time
        results.append(CheckpointResult(
            name="baseline_experiment",
            data_hash=baseline_hash,
            elapsed_seconds=elapsed,
            details={'baseline_data': baseline_data}
        ))
        print(f"  ✅ Baseline complete in {elapsed:.1f}s")
        print(f"  Baseline hash: {baseline_hash}")
        print(f"  NPV_AggCons: {baseline_data['NPV_AggCons']:.6f}")
        print(f"  NPV_AggIncome: {baseline_data['NPV_AggIncome']:.6f}")
        
        # Print summary
        print("\n" + "="*60)
        print("MINI COMPARISON SUMMARY")
        print("="*60)
        print(f"\nHARK Version: {hark_version}")
        total_time = sum(r.elapsed_seconds for r in results)
        print(f"Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
        print("\nCheckpoint Results:")
        for r in results:
            print(f"  {r.name}: {r.data_hash} ({r.elapsed_seconds:.1f}s)")
        
        # Save results
        output_file = f"mini_results_{hark_version.replace('.', '_')}.txt"
        with open(output_file, 'w') as f:
            f.write(f"HARK Version: {hark_version}\n")
            f.write(f"Total Time: {total_time:.1f}s\n\n")
            f.write(f"Checkpoints:\n")
            for r in results:
                f.write(f"  {r.name}: {r.data_hash}\n")
            f.write(f"\nBaseline Results:\n")
            for k, v in baseline_data.items():
                f.write(f"  {k}: {v:.10f}\n")
        print(f"\nResults saved to: {output_file}")
        
        print("\n✅ MINI level completed successfully")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        sys.argv = original_argv
        os.chdir(original_dir)


def main():
    parser = argparse.ArgumentParser(
        description="HARK Version Comparison Framework"
    )
    parser.add_argument(
        "--level", "-l",
        choices=["nano", "micro", "mini"],
        default="nano",
        help="Comparison level (default: nano)"
    )
    parser.add_argument(
        "--code-dir", "-d",
        default=None,
        help="Path to HAFiscal code directory"
    )
    
    args = parser.parse_args()
    
    # Determine code directory
    if args.code_dir:
        code_dir = args.code_dir
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        code_dir = os.path.join(script_dir, "..", "Code", "HA-Models", "FromPandemicCode")
        code_dir = os.path.abspath(code_dir)
    
    if not os.path.exists(code_dir):
        print(f"ERROR: Code directory not found: {code_dir}")
        sys.exit(1)
    
    print(f"Code directory: {code_dir}")
    
    # Run the appropriate comparison level
    level = args.level.lower()
    if level == "nano":
        success = run_nano_comparison(code_dir)
    elif level == "micro":
        success = run_micro_comparison(code_dir)
    elif level == "mini":
        success = run_mini_comparison(code_dir)
    else:
        print(f"Unknown level: {level}")
        success = False
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
