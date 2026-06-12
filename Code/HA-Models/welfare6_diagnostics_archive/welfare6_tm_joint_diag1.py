"""
Diagnostic 1 for joint kernel: check that switch_shock_type actually produces
different cFuncs for recessionUI vs recession. If they're the same, the joint
kernel test isn't valid.
"""
from __future__ import annotations
import os, sys
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve

print("Building HS_Only context...")
ctx = build_and_solve('HS_Only')
print(f"num_base_MrkvStates: {ctx['AggEco'].agents[0].num_base_MrkvStates}")

# Solve under three shock types.
print("Solving three shock types...")
AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()

ag_pol  = AggEco_pol.agents[0]
ag_none = AggEco_none.agents[0]
ag_base = AggEco_base.agents[0]

print(f"\n=== Compare cFuncs at noBen state (j=5) ===")
m_test = np.array([0.5, 1.0, 2.0, 5.0, 10.0])
Cratio = np.ones_like(m_test)
c_pol  = ag_pol.solution[0].cFunc[5](m_test, Cratio)
c_none = ag_none.solution[0].cFunc[5](m_test, Cratio)
c_base = ag_base.solution[0].cFunc[5](m_test, Cratio)
print(f"m       : {m_test}")
print(f"c_pol   : {c_pol}")
print(f"c_none  : {c_none}")
print(f"c_base  : {c_base}")
print(f"diff (pol-none): {c_pol - c_none}")
print(f"diff (none-base): {c_none - c_base}")

print(f"\n=== Compare IncShkDstn at noBen state (j=5) ===")
print(f"pol  IncShkDstn[5].atoms[1] (xi): {ag_pol.IncShkDstn[0][5].atoms[1]}")
print(f"none IncShkDstn[5].atoms[1] (xi): {ag_none.IncShkDstn[0][5].atoms[1]}")
print(f"base IncShkDstn[5].atoms[1] (xi): {ag_base.IncShkDstn[0][5].atoms[1]}")
print(f"pol  IncShkDstn[5].pmv: {ag_pol.IncShkDstn[0][5].pmv}")
print(f"none IncShkDstn[5].pmv: {ag_none.IncShkDstn[0][5].pmv}")

print(f"\n=== Compare cFuncs at employed state (j=0) ===")
c_pol_e  = ag_pol.solution[0].cFunc[0](m_test, Cratio)
c_none_e = ag_none.solution[0].cFunc[0](m_test, Cratio)
print(f"c_pol[e]   : {c_pol_e}")
print(f"c_none[e]  : {c_none_e}")
print(f"diff       : {c_pol_e - c_none_e}")
