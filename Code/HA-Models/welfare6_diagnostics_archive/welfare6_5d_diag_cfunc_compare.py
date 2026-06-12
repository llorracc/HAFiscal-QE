"""
Compare cFunc_pol vs cFunc_none at various (m, j) points.
Determines whether cFunc_pol > cFunc_none (= my fix #11 INCREASES welfare)
or cFunc_pol < cFunc_none (= surprising direction).
"""
import os, sys
os.environ.setdefault('HAFISCAL_UI_STATE_ENCODING', 'bug_fix')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve

print("=== Compare cFunc_pol vs cFunc_none for HS_Only bug_fix ===")
ctx = build_and_solve('HS_Only')
AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()

agent_pol = AggEco_pol.agents[0]
agent_none = AggEco_none.agents[0]
J = agent_pol.num_base_MrkvStates
print(f"\nJ = {J}")
print(f"len(cFuncs_pol) = {len(agent_pol.solution[0].cFunc)}")
print(f"len(cFuncs_none) = {len(agent_none.solution[0].cFunc)}")

m_grid = np.array([1.0, 5.0, 10.0, 20.0, 50.0])
state_names = ['e', 'u1Q', 'u2Q', 'u3Q', 'u4Q', 'noBen']
Cratio = np.ones_like(m_grid)

# At macro=3 (recession Q1), check cFunc per state
for macro_idx in [3, 4, 5, 6, 7, 8]:
    base_idx = macro_idx * J
    print(f"\n--- macro={macro_idx} (recession state) ---")
    print(f"{'state':>6} {'m':>6} {'c_pol':>10} {'c_none':>10} {'pol-none':>10}")
    for j in range(J):
        sname = state_names[j] if j < len(state_names) else f'j{j}'
        cFunc_pol = agent_pol.solution[0].cFunc[base_idx + j]
        cFunc_none = agent_none.solution[0].cFunc[base_idx + j]
        for m in m_grid:
            try:
                cp = float(cFunc_pol(np.array([m]), np.array([1.0]))[0])
                cn = float(cFunc_none(np.array([m]), np.array([1.0]))[0])
                print(f"{sname:>6} {m:>6.1f} {cp:>10.4f} {cn:>10.4f} {cp-cn:>+10.4f}")
            except Exception as e:
                print(f"{sname:>6} {m:>6.1f} ERROR: {e}")
        print()
