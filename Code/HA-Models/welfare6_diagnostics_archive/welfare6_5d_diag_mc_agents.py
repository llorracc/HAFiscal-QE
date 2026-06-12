"""
Examine individual MC agents at MIXED (j_pn=3, j_b=0) at t=1.
Want to understand: WHY mean_cp (9.66) > mean_cn (7.92) when both at u3Q recovery
with same income shock 0.5?

Hypothesis: pLvl_p differs from pLvl_n. Or maybe macros differ. Or shocks differ.
"""
import pickle, numpy as np

MC_DIR = 'Code/HA-Models/FromPandemicCode/welfare6_BUG043_bugfix_HS_seed0'

with open(f'{MC_DIR}/recessionUI.pkl', 'rb') as f:
    d_pol = pickle.load(f)
with open(f'{MC_DIR}/recession.pkl', 'rb') as f:
    d_none = pickle.load(f)
with open(f'{MC_DIR}/base.pkl', 'rb') as f:
    d_base = pickle.load(f)

J = 6
Mp = np.asarray(d_pol['Mrkv_hist_bs']).astype(int)
Mn = np.asarray(d_none['Mrkv_hist_bs']).astype(int)
Mb = np.asarray(d_base['Mrkv_hist_bs']).astype(int)
cLvl_p = np.asarray(d_pol['cLvl_all_splurge'])
cLvl_n = np.asarray(d_none['cLvl_all_splurge'])
cLvl_b = np.asarray(d_base['cLvl_all_splurge'])
pLvl_p = np.asarray(d_pol['pLvl_all_bs'])
pLvl_n = np.asarray(d_none['pLvl_all_bs'])
pLvl_b = np.asarray(d_base['pLvl_all_bs'])

jp = Mp % J
jn = Mn % J
jb = Mb % J
mp_macro = Mp // J
mn_macro = Mn // J

T, N = Mp.shape
t = 1
# MIXED cell (j_p=3, j_b=0) at t=1
mask = (jp[t] == 3) & (jb[t] == 0)
idx = np.where(mask)[0]
print(f"At t={t}, MIXED (j_p=3, j_b=0): {len(idx)} agents")
print(f"  macro_pol at t=1: {set(mp_macro[t, idx])}")
print(f"  macro_base at t=1: {set(mb_macro := mn_macro[t, idx]) if False else set(mp_macro[t, idx])}")
print(f"  j_n at t=1 for these agents: {dict(zip(*np.unique(jn[t, idx], return_counts=True)))}")
print()
print(f"  mean(cLvl_p) = {cLvl_p[t, idx].mean():.4f}")
print(f"  mean(cLvl_n) = {cLvl_n[t, idx].mean():.4f}")
print(f"  mean(cLvl_b) = {cLvl_b[t, idx].mean():.4f}")
print(f"  mean(pLvl_p) = {pLvl_p[t, idx].mean():.4f}")
print(f"  mean(pLvl_n) = {pLvl_n[t, idx].mean():.4f}")
print(f"  mean(pLvl_b) = {pLvl_b[t, idx].mean():.4f}")
print()
print(f"  mean(c_p / pLvl_p) = {(cLvl_p[t, idx] / pLvl_p[t, idx]).mean():.4f}  (= c_p_norm)")
print(f"  mean(c_n / pLvl_n) = {(cLvl_n[t, idx] / pLvl_n[t, idx]).mean():.4f}  (= c_n_norm)")
print(f"  mean(c_b / pLvl_b) = {(cLvl_b[t, idx] / pLvl_b[t, idx]).mean():.4f}  (= c_b_norm)")

print()
print("Histogram of agent paths from t-1 to t:")
print(f"  agents at t=0 jp, jn, jb:")
for jp0, jn0, jb0 in [(2, 2, 0), (1, 1, 0), (3, 3, 0)]:
    sub = idx[(jp[t-1, idx] == jp0) & (jn[t-1, idx] == jn0) & (jb[t-1, idx] == jb0)]
    if len(sub) > 0:
        print(f"    {len(sub):>4} agents at (jp={jp0}, jn={jn0}, jb={jb0}) at t=0")
        print(f"      mean cp/cn/cb: {cLvl_p[t, sub].mean():.4f} / {cLvl_n[t, sub].mean():.4f} / {cLvl_b[t, sub].mean():.4f}")

# Sample 5 individual agents
print()
print("Sample 5 individual agents at MIXED (3,0) at t=1:")
for i in idx[:5]:
    print(f"  agent {i}: pol cLvl={cLvl_p[t, i]:.4f}, none cLvl={cLvl_n[t, i]:.4f}, base cLvl={cLvl_b[t, i]:.4f}")
    print(f"    pLvl: pol={pLvl_p[t, i]:.4f}, none={pLvl_n[t, i]:.4f}, base={pLvl_b[t, i]:.4f}")
    print(f"    Mrkv hist: pol[0:3]={Mp[0:3, i]}, none[0:3]={Mn[0:3, i]}, base[0:3]={Mb[0:3, i]}")
    print(f"    j_p hist: {jp[0:3, i]}, j_n hist: {jn[0:3, i]}, j_b hist: {jb[0:3, i]}")
