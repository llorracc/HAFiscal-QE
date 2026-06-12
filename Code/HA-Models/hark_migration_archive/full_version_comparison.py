#!/usr/bin/env python3
"""
Full Version Comparison: 0.14.1-bugfixed vs 0.17.0-native

This script performs a comprehensive comparison of the two versions using
full (non-quicktest) parameters to validate numerical equivalence.

Compares:
1. Solver output: consumption functions at many test points
2. Grid structure: underlying interpolation grids
3. Solution attributes: MPCmin, MPCmax, hNrm, etc.
4. Simulation with synchronized RNG
"""

import os
import sys
import json
import numpy as np
from pathlib import Path
from datetime import datetime

# Output directory
OUTPUT_DIR = Path("/tmp/hafiscal_full_comparison")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run_comparison_in_version(version_name, codebase_path, output_file):
    """Run comparison code in a specific version's environment."""
    
    comparison_code = '''
import sys
import os
import json
import numpy as np

# Add paths
sys.path.insert(0, os.path.join(os.getcwd(), 'Code/HA-Models'))
sys.path.insert(0, os.path.join(os.getcwd(), 'Code/HA-Models/Target_AggMPCX_LiquWealth'))

# Import HARK
import HARK
print(f"HARK version: {HARK.__version__}")

# Import based on version
hark_version = HARK.__version__

if hark_version.startswith('0.14'):
    # For bugfixed version, use the wrapper
    try:
        from hark_bugfix_wrapper import SmartConsumerType as ConsumerType
        print("Using SmartConsumerType (bugfix wrapper)")
    except ImportError:
        from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType as ConsumerType
        print("Using KinkedRconsumerType (original)")
else:
    from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType as ConsumerType
    print(f"Using KinkedRconsumerType (HARK {hark_version})")

from SetupParamsCSTW import init_infinite

# Use FULL parameters (not quicktest)
params = init_infinite.copy()
params['AgentCount'] = 5000     # Full agent count
params['T_sim'] = 100           # Substantial simulation
params['aXtraCount'] = 48       # Full grid resolution

# Ensure we're using the correct parameter names for the version
if hark_version.startswith('0.14'):
    params['aNrmInitMean'] = 0.0
    params['aNrmInitStd'] = 1.0
else:
    params['kLogInitMean'] = 0.0
    params['kLogInitStd'] = 1.0

results = {
    'hark_version': hark_version,
    'version_name': "VERSION_NAME_PLACEHOLDER",
}

# Create and solve agent
print("Creating agent...")
agent = ConsumerType(**params)

print("Solving agent (full convergence)...")
agent.solve()

# Get solution
sol = agent.solution[0]

# 1. Comprehensive cFunc evaluation
print("Evaluating consumption function...")
m_test_fine = np.concatenate([
    np.linspace(0.01, 1.0, 20),    # Dense near constraint
    np.linspace(1.0, 5.0, 20),     # Medium range
    np.linspace(5.0, 20.0, 20),    # Higher range
    np.linspace(20.0, 100.0, 20),  # Far from constraint
])

cFunc = sol.cFunc
if isinstance(cFunc, list):
    cFunc = cFunc[0]

c_values = []
for m in m_test_fine:
    try:
        c = float(cFunc(m))
        c_values.append(c)
    except:
        c_values.append(np.nan)

results['m_test_points'] = m_test_fine.tolist()
results['c_test_points'] = c_values

# 2. Grid structure analysis
print("Analyzing grid structure...")
if hasattr(cFunc, 'x_list'):
    results['cFunc_x_list'] = [float(x) for x in cFunc.x_list[:20]]  # First 20 points
    results['cFunc_y_list'] = [float(y) for y in cFunc.y_list[:20]]
    results['cFunc_grid_size'] = len(cFunc.x_list)
elif hasattr(cFunc, 'functions'):
    # May be a LowerEnvelope or similar
    results['cFunc_type'] = type(cFunc).__name__
    if hasattr(cFunc.functions[0], 'x_list'):
        results['cFunc_x_list'] = [float(x) for x in cFunc.functions[0].x_list[:20]]
        results['cFunc_y_list'] = [float(y) for y in cFunc.functions[0].y_list[:20]]
else:
    results['cFunc_type'] = type(cFunc).__name__

# 3. Solution attributes
print("Collecting solution attributes...")
attrs = ['MPCmin', 'MPCmax', 'hNrm', 'mNrmMin', 'cFuncLimitIntercept', 'cFuncLimitSlope']
for attr in attrs:
    if hasattr(sol, attr):
        val = getattr(sol, attr)
        if isinstance(val, (int, float, np.number)):
            results[attr] = float(val)
        elif isinstance(val, np.ndarray):
            results[attr] = val.tolist()

# 4. Simulation with deterministic initial conditions
print("Running simulation...")
np.random.seed(12345)
agent.initialize_sim()

# Set deterministic initial assets
det_rng = np.random.RandomState(42)
det_aNrm = np.exp(det_rng.normal(0, 1, agent.AgentCount))

if hasattr(agent, 'state_now'):
    agent.state_now['aNrm'] = det_aNrm
else:
    agent.aNrmNow = det_aNrm

# Simulate
sim_results = {'AggCons': [], 'AggWealth': [], 'AggIncome': []}
for t in range(20):  # 20 periods
    agent.simulate(1)
    
    if hasattr(agent, 'state_now'):
        aNrm = agent.state_now.get('aNrm', np.zeros(agent.AgentCount))
        pLvl = agent.state_now.get('pLvl', np.ones(agent.AgentCount))
    else:
        aNrm = getattr(agent, 'aNrmNow', np.zeros(agent.AgentCount))
        pLvl = getattr(agent, 'pLvlNow', np.ones(agent.AgentCount))
    
    if hasattr(agent, 'controls'):
        cNrm = agent.controls.get('cNrm', np.zeros(agent.AgentCount))
    else:
        cNrm = getattr(agent, 'cNrmNow', np.zeros(agent.AgentCount))
    
    sim_results['AggCons'].append(float(np.mean(cNrm * pLvl)))
    sim_results['AggWealth'].append(float(np.mean(aNrm * pLvl)))
    sim_results['AggIncome'].append(float(np.mean(pLvl)))

results['simulation'] = sim_results

# Final statistics
if hasattr(agent, 'state_now'):
    results['final_aNrm_mean'] = float(np.mean(agent.state_now['aNrm']))
    results['final_aNrm_std'] = float(np.std(agent.state_now['aNrm']))
else:
    results['final_aNrm_mean'] = float(np.mean(agent.aNrmNow))
    results['final_aNrm_std'] = float(np.std(agent.aNrmNow))

print("Done!")

# Save results
output_path = OUTPUT_PATH
with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)
print("Results saved to " + output_path)
'''
    
    # Replace placeholders
    comparison_code = comparison_code.replace('VERSION_NAME_PLACEHOLDER', version_name)
    comparison_code = comparison_code.replace('OUTPUT_PATH', f'"{output_file}"')
    
    # Write temporary script
    script_path = Path(codebase_path) / "temp_comparison.py"
    with open(script_path, 'w') as f:
        f.write(comparison_code)
    
    # Determine which venv to use
    if '0.14.1' in version_name:
        venv_path = Path(codebase_path) / ".venv-0.14.1"
    else:
        venv_path = Path(codebase_path) / ".venv"
    
    python_path = venv_path / "bin" / "python"
    
    # Run the script
    import subprocess
    cmd = f"cd {codebase_path} && {python_path} temp_comparison.py"
    print(f"\n{'='*70}")
    print(f"Running {version_name}...")
    print(f"{'='*70}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:500])
    
    # Clean up
    script_path.unlink(missing_ok=True)
    
    return result.returncode == 0


def compare_results(file1, file2):
    """Compare results from two versions."""
    with open(file1) as f:
        r1 = json.load(f)
    with open(file2) as f:
        r2 = json.load(f)
    
    print("\n" + "=" * 80)
    print("FULL VERSION COMPARISON RESULTS")
    print("=" * 80)
    
    print(f"\nVersion 1: {r1.get('version_name', 'unknown')} (HARK {r1.get('hark_version', '?')})")
    print(f"Version 2: {r2.get('version_name', 'unknown')} (HARK {r2.get('hark_version', '?')})")
    
    # 1. Consumption function comparison
    print("\n" + "-" * 80)
    print("1. CONSUMPTION FUNCTION COMPARISON")
    print("-" * 80)
    
    m_points = r1.get('m_test_points', [])
    c1 = r1.get('c_test_points', [])
    c2 = r2.get('c_test_points', [])
    
    if c1 and c2:
        diffs = []
        print(f"\n{'m':>10} | {'c (v1)':>15} | {'c (v2)':>15} | {'Diff':>12} | {'Diff %':>10}")
        print("-" * 70)
        
        # Sample some points
        indices = [0, 5, 10, 20, 30, 40, 50, 60, 70, 79] if len(m_points) >= 80 else range(min(10, len(m_points)))
        
        for i in indices:
            if i < len(c1) and i < len(c2):
                m = m_points[i]
                v1, v2 = c1[i], c2[i]
                diff = abs(v1 - v2)
                diff_pct = diff / v2 * 100 if v2 != 0 else 0
                diffs.append(diff_pct)
                print(f"{m:>10.4f} | {v1:>15.10f} | {v2:>15.10f} | {diff:>12.2e} | {diff_pct:>9.6f}%")
        
        max_diff = max(diffs) if diffs else 0
        avg_diff = np.mean(diffs) if diffs else 0
        print(f"\nMax difference: {max_diff:.8f}%")
        print(f"Avg difference: {avg_diff:.8f}%")
        
        if max_diff < 1e-10:
            print("✅ Consumption functions are IDENTICAL (within floating point precision)")
        elif max_diff < 0.01:
            print("✅ Consumption functions match within 0.01%")
        else:
            print(f"⚠️  Consumption functions differ by up to {max_diff:.4f}%")
    
    # 2. Grid structure
    print("\n" + "-" * 80)
    print("2. GRID STRUCTURE COMPARISON")
    print("-" * 80)
    
    x1 = r1.get('cFunc_x_list', [])
    x2 = r2.get('cFunc_x_list', [])
    
    if x1 and x2:
        print(f"\nFirst 10 grid points (x_list):")
        print(f"{'i':>5} | {'v1':>18} | {'v2':>18} | {'Match':>8}")
        print("-" * 55)
        for i in range(min(10, len(x1), len(x2))):
            match = "✅" if abs(x1[i] - x2[i]) < 1e-12 else "❌"
            print(f"{i:>5} | {x1[i]:>18.12f} | {x2[i]:>18.12f} | {match:>8}")
    
    # 3. Solution attributes
    print("\n" + "-" * 80)
    print("3. SOLUTION ATTRIBUTES")
    print("-" * 80)
    
    attrs = ['MPCmin', 'MPCmax', 'hNrm', 'mNrmMin']
    print(f"\n{'Attribute':>20} | {'v1':>18} | {'v2':>18} | {'Match':>8}")
    print("-" * 70)
    for attr in attrs:
        v1 = r1.get(attr, 'N/A')
        v2 = r2.get(attr, 'N/A')
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            match = "✅" if abs(v1 - v2) < 1e-12 else "❌"
            print(f"{attr:>20} | {v1:>18.12f} | {v2:>18.12f} | {match:>8}")
        else:
            print(f"{attr:>20} | {str(v1):>18} | {str(v2):>18} |")
    
    # 4. Simulation comparison
    print("\n" + "-" * 80)
    print("4. SIMULATION COMPARISON (20 periods)")
    print("-" * 80)
    
    sim1 = r1.get('simulation', {})
    sim2 = r2.get('simulation', {})
    
    if sim1 and sim2:
        cons1 = sim1.get('AggCons', [])
        cons2 = sim2.get('AggCons', [])
        
        print(f"\n{'Period':>8} | {'AggCons v1':>15} | {'AggCons v2':>15} | {'Diff %':>10}")
        print("-" * 55)
        for t in range(min(10, len(cons1), len(cons2))):
            c1, c2 = cons1[t], cons2[t]
            diff = abs(c1 - c2) / c2 * 100 if c2 != 0 else 0
            print(f"{t:>8} | {c1:>15.8f} | {c2:>15.8f} | {diff:>9.4f}%")
        
        print(f"\nFinal aNrm mean: v1={r1.get('final_aNrm_mean', 'N/A'):.6f}, v2={r2.get('final_aNrm_mean', 'N/A'):.6f}")
    
    # Save comparison summary
    summary = {
        'timestamp': datetime.now().isoformat(),
        'versions': [r1.get('version_name'), r2.get('version_name')],
        'cFunc_max_diff_pct': max_diff if 'max_diff' in dir() else None,
        'cFunc_avg_diff_pct': avg_diff if 'avg_diff' in dir() else None,
        'solver_identical': max_diff < 1e-10 if 'max_diff' in dir() else None,
    }
    
    summary_file = OUTPUT_DIR / "comparison_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"Comparison complete. Results saved to {OUTPUT_DIR}")
    print(f"{'='*80}")


if __name__ == "__main__":
    BASE_DIR = Path("/home/econ-ark/GitHub/llorracc")
    
    versions = [
        ("0.14.1-bugfixed", BASE_DIR / "HAFiscal-0.14.1-bugfixed"),
        ("0.17.0-native", BASE_DIR / "HAFiscal-Latest"),
    ]
    
    results_files = []
    
    for name, path in versions:
        output_file = OUTPUT_DIR / f"results_{name.replace('.', '_')}.json"
        results_files.append(output_file)
        
        success = run_comparison_in_version(name, str(path), str(output_file))
        if not success:
            print(f"❌ Failed to run {name}")
    
    # Compare if both succeeded
    if all(f.exists() for f in results_files):
        compare_results(results_files[0], results_files[1])
    else:
        print("❌ Could not compare - missing result files")
