#!/usr/bin/env python3
"""
Debug RNG Divergence Between HARK 0.14.1 and 0.17.0

This script traces RNG calls during simulation to identify where
the two versions diverge.
"""

import os
import sys
import json
import numpy as np
from pathlib import Path

OUTPUT_DIR = Path("/tmp/hafiscal_rng_debug")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def create_rng_tracing_code(version_name):
    """Create code that traces RNG state during simulation."""
    
    code = '''
import sys
import os
import json
import numpy as np

sys.path.insert(0, os.path.join(os.getcwd(), 'Code/HA-Models'))
sys.path.insert(0, os.path.join(os.getcwd(), 'Code/HA-Models/Target_AggMPCX_LiquWealth'))

import HARK
hark_version = HARK.__version__
print(f"HARK version: {hark_version}")

try:
    from HARK.distributions import Lognormal
except ImportError:
    from HARK.distribution import Lognormal
from SetupParamsCSTW import init_infinite

# For 0.17.0, we need to import the custom class with sim_birth override
if hark_version.startswith('0.17'):
    # Import the custom KinkedRconsumerType with sim_birth override
    from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType as BaseKinkedR
    
    class KinkedRconsumerType(BaseKinkedR):
        """Custom KinkedRconsumerType that matches 0.14.1 RNG behavior."""
        
        def sim_birth(self, which_agents):
            """Override sim_birth to match 0.14.1 RNG consumption."""
            N = np.sum(which_agents)
            if N == 0:
                return
            
            # Match 0.14.1: Create new Lognormal, consume RNG integer for seed
            self.state_now["aNrm"][which_agents] = Lognormal(
                mu=self.kLogInitMean,
                sigma=self.kLogInitStd,
                seed=self.RNG.integers(0, 2**31 - 1),
            ).draw(N)
            
            pLvlInitMeanNow = self.pLogInitMean + np.log(
                self.state_now.get("PlvlAgg", 1.0)
            )
            self.state_now["pLvl"][which_agents] = Lognormal(
                pLvlInitMeanNow,
                self.pLogInitStd,
                seed=self.RNG.integers(0, 2**31 - 1),
            ).draw(N)
            
            self.t_age[which_agents] = 0
            if not hasattr(self, "PerfMITShk"):
                self.PerfMITShk = False
            if not self.PerfMITShk:
                self.t_cycle[which_agents] = 0

elif hark_version.startswith('0.14'):
    # For bugfixed 0.14.1, use SmartConsumerType
    try:
        from hark_bugfix_wrapper import SmartConsumerType as KinkedRconsumerType
        print("Using SmartConsumerType (bugfix wrapper)")
    except ImportError:
        from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType
        print("Using KinkedRconsumerType")
else:
    from HARK.ConsumptionSaving.ConsIndShockModel import KinkedRconsumerType

# Set up parameters
params = init_infinite.copy()
params['AgentCount'] = 100  # Small for debugging
params['T_sim'] = 10

if hark_version.startswith('0.14'):
    params['aNrmInitMean'] = 0.0
    params['aNrmInitStd'] = 1.0
else:
    params['kLogInitMean'] = 0.0
    params['kLogInitStd'] = 1.0

# Create agent with FIXED seed
agent = KinkedRconsumerType(**params)
agent.seed = 12345  # Same seed for both versions

print("Solving agent...")
agent.solve()

print("Initializing simulation...")
# Reset RNG to known state before simulation
np.random.seed(12345)

agent.initialize_sim()

# Capture RNG state after initialize_sim
rng_state_after_init = agent.RNG.bit_generator.state.copy() if hasattr(agent.RNG, 'bit_generator') else None

# Set DETERMINISTIC initial state (bypass RNG for initial aNrm)
det_rng = np.random.RandomState(42)
initial_aNrm = np.exp(det_rng.normal(0, 1, agent.AgentCount))

if hasattr(agent, 'state_now'):
    agent.state_now['aNrm'] = initial_aNrm.copy()
else:
    agent.aNrmNow = initial_aNrm.copy()

# Capture RNG state before simulation
rng_state_before_sim = agent.RNG.bit_generator.state.copy() if hasattr(agent.RNG, 'bit_generator') else None

results = {
    'version': "VERSION_PLACEHOLDER",
    'hark_version': hark_version,
    'AgentCount': agent.AgentCount,
    'T_sim': params['T_sim'],
    'initial_aNrm_sum': float(np.sum(initial_aNrm)),
    'periods': [],
}

print("Running simulation with RNG tracing...")

for t in range(params['T_sim']):
    # Capture state BEFORE simulate
    if hasattr(agent, 'state_now'):
        aNrm_before = agent.state_now['aNrm'].copy()
        pLvl_before = agent.state_now['pLvl'].copy()
    else:
        aNrm_before = agent.aNrmNow.copy()
        pLvl_before = agent.pLvlNow.copy()
    
    # Run one period
    agent.simulate(1)
    
    # Capture state AFTER simulate
    if hasattr(agent, 'state_now'):
        aNrm_after = agent.state_now['aNrm'].copy()
        pLvl_after = agent.state_now['pLvl'].copy()
    else:
        aNrm_after = agent.aNrmNow.copy()
        pLvl_after = agent.pLvlNow.copy()
    
    if hasattr(agent, 'controls'):
        cNrm = agent.controls.get('cNrm', np.zeros(agent.AgentCount))
    else:
        cNrm = getattr(agent, 'cNrmNow', np.zeros(agent.AgentCount))
    
    # Check for deaths/births
    if hasattr(agent, 'who_dies'):
        n_deaths = int(np.sum(agent.who_dies))
    else:
        n_deaths = 0
    
    period_data = {
        'period': t,
        'aNrm_mean_before': float(np.mean(aNrm_before)),
        'aNrm_mean_after': float(np.mean(aNrm_after)),
        'pLvl_mean_before': float(np.mean(pLvl_before)),
        'pLvl_mean_after': float(np.mean(pLvl_after)),
        'cNrm_mean': float(np.mean(cNrm)),
        'AggCons': float(np.mean(cNrm * pLvl_after)),
        'AggWealth': float(np.mean(aNrm_after * pLvl_after)),
        'n_deaths': n_deaths,
        # Capture first few agent values for detailed comparison
        'aNrm_first5': [float(x) for x in aNrm_after[:5]],
        'pLvl_first5': [float(x) for x in pLvl_after[:5]],
        'cNrm_first5': [float(x) for x in cNrm[:5]],
    }
    
    results['periods'].append(period_data)
    print(f"  Period {t}: AggCons={period_data['AggCons']:.6f}, deaths={n_deaths}")

# Final RNG state
results['rng_state_type'] = str(type(agent.RNG))

print("\\nDone!")

output_path = OUTPUT_PATH
with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)
print("Results saved to: " + output_path)
'''
    return code


def run_debug_version(version_name, codebase_path, output_file):
    """Run RNG debug in a specific version."""
    
    code = create_rng_tracing_code(version_name)
    code = code.replace('VERSION_PLACEHOLDER', version_name)
    code = code.replace('OUTPUT_PATH', f'"{output_file}"')
    
    script_path = Path(codebase_path) / "temp_rng_debug.py"
    with open(script_path, 'w') as f:
        f.write(code)
    
    if '0.14.1' in version_name:
        venv = Path(codebase_path) / ".venv-0.14.1" / "bin" / "python"
    else:
        venv = Path(codebase_path) / ".venv" / "bin" / "python"
    
    import subprocess
    print(f"\n{'='*70}")
    print(f"Running {version_name}...")
    print(f"{'='*70}")
    
    result = subprocess.run(
        f"cd {codebase_path} && {venv} temp_rng_debug.py",
        shell=True, capture_output=True, text=True
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:1000])
    
    script_path.unlink(missing_ok=True)
    return result.returncode == 0


def compare_rng_results(file1, file2):
    """Compare RNG debug results."""
    with open(file1) as f:
        r1 = json.load(f)
    with open(file2) as f:
        r2 = json.load(f)
    
    print("\n" + "=" * 80)
    print("RNG DIVERGENCE ANALYSIS")
    print("=" * 80)
    
    print(f"\nVersion 1: {r1['version']} (HARK {r1['hark_version']})")
    print(f"Version 2: {r2['version']} (HARK {r2['hark_version']})")
    
    print("\n" + "-" * 80)
    print("PERIOD-BY-PERIOD COMPARISON")
    print("-" * 80)
    
    print(f"\n{'Period':>6} | {'AggCons v1':>12} | {'AggCons v2':>12} | {'Diff%':>8} | {'Deaths v1':>9} | {'Deaths v2':>9}")
    print("-" * 80)
    
    first_divergence = None
    for i, (p1, p2) in enumerate(zip(r1['periods'], r2['periods'])):
        c1, c2 = p1['AggCons'], p2['AggCons']
        diff = abs(c1 - c2) / c2 * 100 if c2 != 0 else 0
        
        if diff > 0.01 and first_divergence is None:
            first_divergence = i
        
        marker = " ***" if diff > 0.01 else ""
        print(f"{i:>6} | {c1:>12.8f} | {c2:>12.8f} | {diff:>7.4f}% | {p1['n_deaths']:>9} | {p2['n_deaths']:>9}{marker}")
    
    if first_divergence is not None:
        print(f"\n⚠️  First significant divergence at period {first_divergence}")
        
        print("\n" + "-" * 80)
        print(f"DETAILED COMPARISON AT PERIOD {first_divergence}")
        print("-" * 80)
        
        p1, p2 = r1['periods'][first_divergence], r2['periods'][first_divergence]
        
        print(f"\nAgent-level aNrm (first 5):")
        print(f"  v1: {p1['aNrm_first5']}")
        print(f"  v2: {p2['aNrm_first5']}")
        
        print(f"\nAgent-level cNrm (first 5):")
        print(f"  v1: {p1['cNrm_first5']}")
        print(f"  v2: {p2['cNrm_first5']}")
        
        print(f"\nAgent-level pLvl (first 5):")
        print(f"  v1: {p1['pLvl_first5']}")
        print(f"  v2: {p2['pLvl_first5']}")
    else:
        print("\n✅ No significant divergence detected!")


if __name__ == "__main__":
    BASE_DIR = Path("/home/econ-ark/GitHub/llorracc")
    
    versions = [
        ("0.14.1-bugfixed", BASE_DIR / "HAFiscal-0.14.1-bugfixed"),
        ("0.17.0-native", BASE_DIR / "HAFiscal-Latest"),
    ]
    
    files = []
    for name, path in versions:
        out = OUTPUT_DIR / f"rng_debug_{name.replace('.', '_')}.json"
        files.append(out)
        run_debug_version(name, str(path), str(out))
    
    if all(f.exists() for f in files):
        compare_rng_results(files[0], files[1])
