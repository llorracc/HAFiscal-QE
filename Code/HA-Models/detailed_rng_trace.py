#!/usr/bin/env python3
"""
Detailed RNG trace to identify divergence point between HARK versions.
"""

import subprocess
import json
from pathlib import Path

OUTPUT_DIR = Path("/tmp/hafiscal_rng_trace")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run_014_trace():
    """Run detailed trace in 0.14.1-bugfixed."""
    
    code = '''
import sys
import numpy as np
import json

sys.path.insert(0, 'Code/HA-Models')
sys.path.insert(0, 'Code/HA-Models/Target_AggMPCX_LiquWealth')
from SetupParamsCSTW import init_infinite
from hark_bugfix_wrapper import SmartConsumerType

params = init_infinite.copy()
params['AgentCount'] = 10
params['T_sim'] = 5
params['aNrmInitMean'] = 0.0
params['aNrmInitStd'] = 1.0

agent = SmartConsumerType(**params)
agent.seed = 12345

trace = {"version": "0.14.1-bugfixed", "steps": []}

# Solve
agent.solve()
trace["steps"].append({"step": "solve", "status": "done"})

# Before initialize_sim - get distribution state
inc_draws_pre = agent.IncShkDstn[0].draw(3)
trace["steps"].append({
    "step": "pre_init",
    "IncShkDstn_draws": inc_draws_pre.tolist()
})

# Initialize sim
agent.initialize_sim()

# After initialize_sim
inc_draws_post = agent.IncShkDstn[0].draw(3)
rng_state = agent.RNG.integers(0, 1000, size=5).tolist()
trace["steps"].append({
    "step": "post_init",
    "IncShkDstn_draws": inc_draws_post.tolist(),
    "agent_RNG_draws": rng_state
})

# Reset RNG to known state
agent.RNG = np.random.default_rng(12345)

# Set deterministic initial assets
det_rng = np.random.RandomState(42)
initial_aNrm = np.exp(det_rng.normal(0, 1, agent.AgentCount))
agent.state_now['aNrm'] = initial_aNrm.copy()
trace["steps"].append({
    "step": "set_initial",
    "initial_aNrm": initial_aNrm.tolist()
})

# Run simulation with detailed trace
for t in range(3):
    # Get state before
    aNrm_before = agent.state_now['aNrm'].copy()
    pLvl_before = agent.state_now['pLvl'].copy()
    
    # Get RNG state before simulate
    rng_pre = agent.RNG.integers(0, 1000, size=3).tolist()
    agent.RNG = np.random.default_rng(12345 + t * 1000)  # Reset for reproducibility
    
    agent.simulate(1)
    
    aNrm_after = agent.state_now['aNrm']
    pLvl_after = agent.state_now['pLvl']
    cNrm = agent.controls.get('cNrm', np.zeros(agent.AgentCount))
    
    trace["steps"].append({
        "step": f"period_{t}",
        "aNrm_before": aNrm_before.tolist(),
        "aNrm_after": aNrm_after.tolist(),
        "pLvl_before": pLvl_before.tolist(),
        "pLvl_after": pLvl_after.tolist(),
        "cNrm": cNrm.tolist(),
        "AggCons": float(np.mean(cNrm * pLvl_after))
    })

with open("/tmp/hafiscal_rng_trace/trace_014.json", "w") as f:
    json.dump(trace, f, indent=2)
print("Done!")
'''
    
    result = subprocess.run(
        ["bash", "-c", f"cd /home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed && source .venv-0.14.1/bin/activate && python -c '{code}'"],
        capture_output=True, text=True
    )
    print("0.14.1:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:500])


def run_017_trace():
    """Run detailed trace in 0.17.0-native."""
    
    code = '''
import sys
import numpy as np
import json

sys.path.insert(0, 'Code/HA-Models')
sys.path.insert(0, 'Code/HA-Models/Target_AggMPCX_LiquWealth')
from SetupParamsCSTW import init_infinite
from rng_synchronized_consumer import RNGSyncKinkedRconsumerType

params = init_infinite.copy()
params['AgentCount'] = 10
params['T_sim'] = 5
params['kLogInitMean'] = 0.0
params['kLogInitStd'] = 1.0

agent = RNGSyncKinkedRconsumerType(**params)
agent.seed = 12345

trace = {"version": "0.17.0-native", "steps": []}

# Solve
agent.solve()
trace["steps"].append({"step": "solve", "status": "done"})

# Before initialize_sim - get distribution state
inc_draws_pre = agent.IncShkDstn[0].draw(3)
trace["steps"].append({
    "step": "pre_init",
    "IncShkDstn_draws": inc_draws_pre.tolist()
})

# Initialize sim
agent.initialize_sim()

# After initialize_sim
inc_draws_post = agent.IncShkDstn[0].draw(3)
rng_state = agent.RNG.integers(0, 1000, size=5).tolist()
trace["steps"].append({
    "step": "post_init",
    "IncShkDstn_draws": inc_draws_post.tolist(),
    "agent_RNG_draws": rng_state
})

# Reset RNG to known state
agent.RNG = np.random.default_rng(12345)

# Set deterministic initial assets
det_rng = np.random.RandomState(42)
initial_aNrm = np.exp(det_rng.normal(0, 1, agent.AgentCount))
agent.state_now['aNrm'] = initial_aNrm.copy()
trace["steps"].append({
    "step": "set_initial",
    "initial_aNrm": initial_aNrm.tolist()
})

# Run simulation with detailed trace
for t in range(3):
    # Get state before
    aNrm_before = agent.state_now['aNrm'].copy()
    pLvl_before = agent.state_now['pLvl'].copy()
    
    # Get RNG state before simulate
    rng_pre = agent.RNG.integers(0, 1000, size=3).tolist()
    agent.RNG = np.random.default_rng(12345 + t * 1000)  # Reset for reproducibility
    
    agent.simulate(1)
    
    aNrm_after = agent.state_now['aNrm']
    pLvl_after = agent.state_now['pLvl']
    cNrm = agent.controls.get('cNrm', np.zeros(agent.AgentCount))
    
    trace["steps"].append({
        "step": f"period_{t}",
        "aNrm_before": aNrm_before.tolist(),
        "aNrm_after": aNrm_after.tolist(),
        "pLvl_before": pLvl_before.tolist(),
        "pLvl_after": pLvl_after.tolist(),
        "cNrm": cNrm.tolist(),
        "AggCons": float(np.mean(cNrm * pLvl_after))
    })

with open("/tmp/hafiscal_rng_trace/trace_017.json", "w") as f:
    json.dump(trace, f, indent=2)
print("Done!")
'''
    
    result = subprocess.run(
        ["bash", "-c", f"cd /home/econ-ark/GitHub/llorracc/HAFiscal-Latest && source .venv/bin/activate && python -c '{code}'"],
        capture_output=True, text=True
    )
    print("0.17.0:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:500])


def compare_traces():
    """Compare the two traces."""
    with open("/tmp/hafiscal_rng_trace/trace_014.json") as f:
        t014 = json.load(f)
    with open("/tmp/hafiscal_rng_trace/trace_017.json") as f:
        t017 = json.load(f)
    
    print("\n" + "=" * 80)
    print("TRACE COMPARISON")
    print("=" * 80)
    
    for s014, s017 in zip(t014["steps"], t017["steps"]):
        step = s014["step"]
        print(f"\n--- {step} ---")
        
        if step == "pre_init" or step == "post_init":
            d014 = s014.get("IncShkDstn_draws", [])
            d017 = s017.get("IncShkDstn_draws", [])
            if d014 != d017:
                print(f"  ❌ IncShkDstn_draws differ:")
                print(f"     0.14.1: {d014}")
                print(f"     0.17.0: {d017}")
            else:
                print(f"  ✅ IncShkDstn_draws match")
        
        if step.startswith("period_"):
            agg014 = s014.get("AggCons")
            agg017 = s017.get("AggCons")
            diff = abs(agg014 - agg017) / agg014 * 100 if agg014 else 0
            
            if diff > 0.001:
                print(f"  ❌ AggCons: {agg014:.8f} vs {agg017:.8f} ({diff:.4f}%)")
                
                # Check pLvl
                p014 = s014.get("pLvl_after", [])
                p017 = s017.get("pLvl_after", [])
                if p014 != p017:
                    print(f"     pLvl differs!")
                    for i, (p1, p2) in enumerate(zip(p014[:5], p017[:5])):
                        if abs(p1 - p2) > 1e-10:
                            print(f"       Agent {i}: {p1:.8f} vs {p2:.8f}")
            else:
                print(f"  ✅ AggCons: {agg014:.8f}")


if __name__ == "__main__":
    print("Running 0.14.1-bugfixed trace...")
    run_014_trace()
    
    print("\nRunning 0.17.0-native trace...")
    run_017_trace()
    
    compare_traces()
