"""Minimal check: verify PermGroFac matches the observed PermShk bias."""

# Math reference: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")

import os, sys
import numpy as np
sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())
os.environ['MPLBACKEND'] = 'Agg'

from Parameters import return_parameters

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, *rest] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

print("PermGroFac values by education type:")
for name, init in [("dropout", init_dropout), ("highschool", init_highschool), ("college", init_college)]:
    G = init['PermGroFac']
    print(f"  {name}: PermGroFac = {G}")
    if isinstance(G, list):
        for i, g in enumerate(G):
            if isinstance(g, (list, np.ndarray)):
                print(f"    state {i}: {g}")
            else:
                print(f"    = {g}")

# Quantify the expected pLvl growth differential
G_hs = init_highschool['PermGroFac']
if isinstance(G_hs, list) and isinstance(G_hs[0], list):
    G_val = G_hs[0][0]
elif isinstance(G_hs, list):
    G_val = G_hs[0]
else:
    G_val = G_hs

print(f"\nPermGroFac (highschool) = {G_val}")
print(f"Observed E[perm_shock_fixed_hist] ≈ 1.0045")
print(f"Ratio: 1.0045 / {G_val} = {1.0045 / G_val:.6f}")

u_base = 0.05
u_rec = 0.10
E_growth_base = (1 - u_base) * G_val + u_base * 1.0
E_growth_rec = (1 - u_rec) * G_val + u_rec * 1.0
growth_deficit = E_growth_rec - E_growth_base

print(f"\nE[pLvl growth|base, u={u_base}] = {E_growth_base:.6f}")
print(f"E[pLvl growth|rec,  u={u_rec}]  = {E_growth_rec:.6f}")
print(f"Growth deficit per period       = {growth_deficit:.6f}")
print(f"After 3 periods of deficit (compounding): {(E_growth_rec/E_growth_base)**3 - 1:.6f}")
print(f"If mean pLvl ≈ 12: absolute deficit ≈ {12 * ((E_growth_rec/E_growth_base)**3 - 1):.4f}")
