"""Quick inspection of HAFiscal agent structure."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
from welfare6_scenario import build_and_solve

ctx = build_and_solve('HS_Only')
agent = ctx['AggEco'].agents[0]
print(f"agent.IncShkDstn type: {type(agent.IncShkDstn)}")
print(f"agent.IncShkDstn len: {len(agent.IncShkDstn)}")
print(f"agent.IncShkDstn[0] type: {type(agent.IncShkDstn[0])}")
if hasattr(agent.IncShkDstn[0], '__len__'):
    print(f"agent.IncShkDstn[0] len: {len(agent.IncShkDstn[0])}")
print(f"agent.IncShkDstn[0]: {agent.IncShkDstn[0]}")
print(f"agent.IncShkDstn[0][0] type: {type(agent.IncShkDstn[0][0]) if hasattr(agent.IncShkDstn[0], '__getitem__') else 'N/A'}")
if hasattr(agent.IncShkDstn[0], '__getitem__'):
    try:
        x = agent.IncShkDstn[0][0]
        print(f"agent.IncShkDstn[0][0]: {x}, type={type(x)}")
        if hasattr(x, 'pmv'):
            print(f"  .pmv shape: {np.asarray(x.pmv).shape}, .atoms: {len(x.atoms) if hasattr(x, 'atoms') else 'N/A'}")
    except Exception as e:
        print(f"  error: {e}")

print(f"agent.solve_one_period: {agent.solve_one_period}")
print(f"agent.MrkvArray type: {type(agent.MrkvArray)}, len: {len(agent.MrkvArray)}")
if hasattr(agent.MrkvArray[0], 'shape'):
    print(f"agent.MrkvArray[0] shape: {agent.MrkvArray[0].shape}")
print(f"agent.num_base_MrkvStates: {agent.num_base_MrkvStates}")
print(f"agent.Cgrid: {agent.Cgrid}")
print(f"agent.CFunc: {type(agent.CFunc)}, len: {len(agent.CFunc) if hasattr(agent.CFunc, '__len__') else 'N/A'}")
