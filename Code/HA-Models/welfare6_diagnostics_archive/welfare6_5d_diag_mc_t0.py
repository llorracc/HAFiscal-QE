"""Track agent 270 at t=0 to verify cFunc-divergence direction in MC."""
import pickle, numpy as np

MC_DIR = 'Code/HA-Models/FromPandemicCode/welfare6_BUG043_bugfix_HS_seed0'

with open(f'{MC_DIR}/recessionUI.pkl', 'rb') as f: d_pol = pickle.load(f)
with open(f'{MC_DIR}/recession.pkl', 'rb') as f: d_none = pickle.load(f)

cLvl_p = np.asarray(d_pol['cLvl_all_splurge'])
cLvl_n = np.asarray(d_none['cLvl_all_splurge'])
pLvl_p = np.asarray(d_pol['pLvl_all_bs'])
pLvl_n = np.asarray(d_none['pLvl_all_bs'])
Mp = np.asarray(d_pol['Mrkv_hist_bs']).astype(int)
Mn = np.asarray(d_none['Mrkv_hist_bs']).astype(int)

J = 6
jp = Mp % J
jn = Mn % J
macro_p = Mp // J
macro_n = Mn // J

agent = 270
print(f"=== Agent {agent} ===")
for t in range(4):
    print(f"\nt={t}: Mrkv pol={Mp[t,agent]} (macro={macro_p[t,agent]}, j={jp[t,agent]}), "
          f"Mrkv none={Mn[t,agent]} (macro={macro_n[t,agent]}, j={jn[t,agent]})")
    print(f"      cLvl pol={cLvl_p[t,agent]:.4f}, none={cLvl_n[t,agent]:.4f}, diff={cLvl_p[t,agent]-cLvl_n[t,agent]:+.4f}")
    print(f"      pLvl pol={pLvl_p[t,agent]:.4f}, none={pLvl_n[t,agent]:.4f}")
    cp_n = cLvl_p[t,agent] / pLvl_p[t,agent]
    cn_n = cLvl_n[t,agent] / pLvl_n[t,agent]
    print(f"      c_norm pol={cp_n:.4f}, none={cn_n:.4f}, diff={cp_n-cn_n:+.4f}")

# At t=0 if pol c_norm > none c_norm, pol consumes more at u2Q recession (expected from cFunc)
# At t=1 if pol c_norm > none c_norm, that's the puzzle (recovery, same cFunc)
print(f"\n=== Aggregate at MIXED (3,0) at t=1 ===")
mask = (jp[1] == 3) & (jn[1] == 0)  # j_n for "base axis" — but wait, jn is none not base
# Actually let me re-check. For MIXED in MC, j_b uses BASE scenario.
Mb = np.asarray(pickle.load(open(f'{MC_DIR}/base.pkl','rb'))['Mrkv_hist_bs']).astype(int)
jb = Mb % J
mask = (jp[1] == 3) & (jb[1] == 0)
idx = np.where(mask)[0]
print(f"Agents at MIXED (j_p=3, j_b=0) at t=1: {len(idx)}")
# Check if j_n == j_p for these agents (= CRN preserves micro state)
print(f"  Of these, j_n at t=1: {dict(zip(*np.unique(jn[1, idx], return_counts=True)))}")
# At t=0, what were j_p, j_n, j_b for these MIXED-cell agents?
print(f"\nAt t=0 for these agents:")
print(f"  j_p: {dict(zip(*np.unique(jp[0, idx], return_counts=True)))}")
print(f"  j_n: {dict(zip(*np.unique(jn[0, idx], return_counts=True)))}")
print(f"  j_b: {dict(zip(*np.unique(jb[0, idx], return_counts=True)))}")

# AT t=0, mean cLvl and pLvl for pol vs none for these agents
cp0 = cLvl_p[0, idx]
cn0 = cLvl_n[0, idx]
pp0 = pLvl_p[0, idx]
pn0 = pLvl_n[0, idx]
print(f"\nAt t=0 for these MIXED-cell agents:")
print(f"  mean cLvl pol={cp0.mean():.4f}, none={cn0.mean():.4f}, diff={cp0.mean()-cn0.mean():+.4f}")
print(f"  mean pLvl pol={pp0.mean():.4f}, none={pn0.mean():.4f}")
print(f"  mean c_norm pol={(cp0/pp0).mean():.4f}, none={(cn0/pn0).mean():.4f}")
print(f"  mean c_norm diff (pol-none) = {((cp0/pp0) - (cn0/pn0)).mean():+.4f}")

# At t=1 for these
print(f"\nAt t=1 for these MIXED-cell agents:")
cp1 = cLvl_p[1, idx]
cn1 = cLvl_n[1, idx]
pp1 = pLvl_p[1, idx]
pn1 = pLvl_n[1, idx]
print(f"  mean cLvl pol={cp1.mean():.4f}, none={cn1.mean():.4f}, diff={cp1.mean()-cn1.mean():+.4f}")
print(f"  mean c_norm pol={(cp1/pp1).mean():.4f}, none={(cn1/pn1).mean():.4f}")
print(f"  mean c_norm diff (pol-none) = {((cp1/pp1) - (cn1/pn1)).mean():+.4f}")
