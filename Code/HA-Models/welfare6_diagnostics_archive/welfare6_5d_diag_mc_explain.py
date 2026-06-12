"""
Try to explain MC's c_p > c_n at MIXED (3,0) t=1 in DETAIL.
Agent at u3Q in both pol AND none scenarios, macro=4 recovery in both.
xi = 0.5 in both, cFunc identical at macro=4.

Yet pol c > none c by 22%. Why?

Hypothesis: cFunc is solved with FORWARD-LOOKING expectations.
The pol scenario's solve assumes the agent CAN reach noBen via UI extension path.
The none scenario's solve does NOT have UI extension. So even at recovery,
the cFunc may differ because of different expected forward trajectories.

Wait but cFunc_compare at macro=4 showed IDENTICAL pol vs none. So same cFunc.

Then c_p > c_n only if m_p > m_n => a_p > a_n.

For a_p > a_n at t=1: pol agent saved MORE in prior period.
But cFunc_pol > cFunc_none at u2Q recession => pol consumed MORE => saved LESS.

CONTRADICTION. Need to actually trace MC's logic.

This script attempts to back out a from c, m, etc.
"""
import pickle, numpy as np

MC_DIR = 'Code/HA-Models/FromPandemicCode/welfare6_BUG043_bugfix_HS_seed0'

with open(f'{MC_DIR}/recessionUI.pkl', 'rb') as f:
    d_pol = pickle.load(f)
with open(f'{MC_DIR}/recession.pkl', 'rb') as f:
    d_none = pickle.load(f)

print(f"pol keys: {[k for k in d_pol.keys()]}")
print(f"recessionUI shock_type from MC pickle: {d_pol.get('scenario', '?')}")

# Check if there's any way to access a or m
for k in d_pol.keys():
    print(f"  {k}: type={type(d_pol[k]).__name__}, shape={getattr(np.asarray(d_pol[k]), 'shape', '-') if not isinstance(d_pol[k], (int, float, str)) else '-'}")
