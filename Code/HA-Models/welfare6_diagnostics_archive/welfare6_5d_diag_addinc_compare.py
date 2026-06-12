"""
Compare TM-a's AddInc/AddCons (used as 5D denominator) vs MC's AddInc/AddCons.
If TM-a has a smaller AddInc, that explains a portion of 5D's +25% over-count.
"""
import pickle, numpy as np

MC_DIR = 'Code/HA-Models/FromPandemicCode/welfare6_BUG043_bugfix_HS_seed0'
T2_PKL = "Code/HA-Models/FromPandemicCode/reproduce/logs/tm_a_phase3/A1_HS_Only_bugfix_A50.pkl"

# MC AddInc
with open(f'{MC_DIR}/recessionUI.pkl', 'rb') as f:
    d_pol = pickle.load(f)
with open(f'{MC_DIR}/recession.pkl', 'rb') as f:
    d_none = pickle.load(f)

mc_AggInc_pol = np.asarray(d_pol['AggIncome'])
mc_AggInc_none = np.asarray(d_none['AggIncome'])
mc_AggCons_pol = np.asarray(d_pol['AggCons'])
mc_AggCons_none = np.asarray(d_none['AggCons'])
Rfree = float(d_pol['Rfree'])
T = len(mc_AggInc_pol)

mc_AddInc = mc_AggInc_pol - mc_AggInc_none
mc_AddCons = mc_AggCons_pol - mc_AggCons_none

# TM-a AddInc
with open(T2_PKL, 'rb') as f:
    t2 = pickle.load(f)
t2_AC_pol = np.asarray(t2['results_summary']['recessionUI']['AggCons'])
t2_AC_none = np.asarray(t2['results_summary']['recession']['AggCons'])
t2_AI_pol = np.asarray(t2['results_summary']['recessionUI']['AggIncome'])
t2_AI_none = np.asarray(t2['results_summary']['recession']['AggIncome'])
t2_AddInc = t2_AI_pol - t2_AI_none
t2_AddCons = t2_AC_pol - t2_AC_none

print(f"=== AddInc (per-period) ===")
print(f"{'t':>3} {'MC AddInc':>12} {'TM-a AddInc':>12} {'ratio':>8}")
for t in range(min(15, T)):
    r = t2_AddInc[t] / mc_AddInc[t] if abs(mc_AddInc[t]) > 1e-10 else float('nan')
    print(f"{t:>3} {mc_AddInc[t]:>12.4f} {t2_AddInc[t]:>12.4f} {r:>8.4f}")

# NPV
def npv(s, R, T):
    return sum(s[t] / R**t for t in range(T))

print(f"\n=== NPV comparison ===")
print(f"  NPV(MC AddInc):  {npv(mc_AddInc, Rfree, T):.4e}")
print(f"  NPV(TM-a AddInc): {npv(t2_AddInc, Rfree, T):.4e}")
print(f"  Ratio: {npv(t2_AddInc, Rfree, T) / npv(mc_AddInc, Rfree, T):.4f}")
print()
print(f"  NPV(MC AddCons):  {npv(mc_AddCons, Rfree, T):.4e}")
print(f"  NPV(TM-a AddCons): {npv(t2_AddCons, Rfree, T):.4e}")
print(f"  Ratio: {npv(t2_AddCons, Rfree, T) / npv(mc_AddCons, Rfree, T):.4f}")
