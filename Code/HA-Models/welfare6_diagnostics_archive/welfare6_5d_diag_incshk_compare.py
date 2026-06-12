"""
Compare IncShk (xi atoms) for pol vs none scenarios at each (macro, j) state.
If atoms differ in a way I'm misinterpreting, that could flip the welfare sign.
"""
import os, sys
os.environ.setdefault('HAFISCAL_UI_STATE_ENCODING', 'bug_fix')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve

print("=== Compare IncShk pol vs none ===")
ctx = build_and_solve('HS_Only')
AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()

agent_pol = AggEco_pol.agents[0]
agent_none = AggEco_none.agents[0]
J = agent_pol.num_base_MrkvStates
print(f"\nJ = {J}")

IncShk_pol = agent_pol.IncShkDstn_recessionUI[0] if hasattr(agent_pol, 'IncShkDstn_recessionUI') else agent_pol.IncShkDstn[0]
IncShk_none = agent_none.IncShkDstn_recession[0] if hasattr(agent_none, 'IncShkDstn_recession') else agent_none.IncShkDstn[0]

print(f"len(IncShk_pol) = {len(IncShk_pol)}")
print(f"len(IncShk_none) = {len(IncShk_none)}")

# For each (macro, j), compare atoms
state_names = ['e', 'u1Q', 'u2Q', 'u3Q', 'u4Q', 'noBen']
for macro_idx in [3, 4, 5, 6, 7]:
    print(f"\n--- macro={macro_idx} ---")
    for j in range(J):
        sname = state_names[j] if j < len(state_names) else f'j{j}'
        idx = macro_idx * J + j
        if idx >= len(IncShk_pol):
            continue
        dp = IncShk_pol[idx]
        dn = IncShk_none[idx]
        psi_p = np.asarray(dp.atoms[0])
        xi_p = np.asarray(dp.atoms[1])
        pmv_p = np.asarray(dp.pmv)
        psi_n = np.asarray(dn.atoms[0])
        xi_n = np.asarray(dn.atoms[1])
        pmv_n = np.asarray(dn.pmv)

        # Mean xi (= mean transitory income)
        mean_xi_p = float(np.dot(pmv_p, xi_p))
        mean_xi_n = float(np.dot(pmv_n, xi_n))

        same = np.allclose(xi_p, xi_n) and np.allclose(psi_p, psi_n)
        if not same or abs(mean_xi_p - mean_xi_n) > 1e-6:
            print(f"  {sname:>6}: pol xi={xi_p}, pmv={pmv_p}, mean={mean_xi_p:.4f}")
            print(f"  {sname:>6}: none xi={xi_n}, pmv={pmv_n}, mean={mean_xi_n:.4f}")
            print(f"  {sname:>6}: DIFFERENCE mean_xi: pol-none = {mean_xi_p - mean_xi_n:+.4f}")
        else:
            print(f"  {sname:>6}: IDENTICAL (xi[0]={xi_p[0]:.4f})")

# Also check TranShk_addition arrays
print(f"\n--- TranShk_addition (per (t, j_pn)) ---")
print(f"TranShk_addition_recessionUI shape: {np.asarray(agent_pol.TranShk_addition_recessionUI).shape if hasattr(agent_pol, 'TranShk_addition_recessionUI') else 'N/A'}")
print(f"TranShk_addition_recession shape: {np.asarray(agent_none.TranShk_addition_recession).shape if hasattr(agent_none, 'TranShk_addition_recession') else 'N/A'}")

if hasattr(agent_pol, 'TranShk_addition_recessionUI') and hasattr(agent_none, 'TranShk_addition_recession'):
    ta_p = np.asarray(agent_pol.TranShk_addition_recessionUI)
    ta_n = np.asarray(agent_none.TranShk_addition_recession)
    print(f"TranShk_addition pol[t=0..7, j=0..5]:")
    for t in range(min(8, ta_p.shape[0])):
        print(f"  t={t}: pol={ta_p[t]}")
        print(f"  t={t}: none={ta_n[t]}")
        print(f"  t={t}: diff={ta_p[t] - ta_n[t]}")
