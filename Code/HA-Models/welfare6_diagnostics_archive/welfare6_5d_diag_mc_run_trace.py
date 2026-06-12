"""
Actually RUN MC for pol and none scenarios with small N (= 1000 agents)
and dump full aNrm trace. Compare a_p vs a_n at t=0 end.
"""
import os, sys
os.environ.setdefault('HAFISCAL_UI_STATE_ENCODING', 'bug_fix')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve

print("=== Building economy (HS_Only, small N) ===")
# Force small N for fast test
os.environ['HAFISCAL_AGENTCOUNT_H'] = '1000'
ctx = build_and_solve('HS_Only')

AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()

# Build a recession path (dur=1 to match prior diagnostic)
act_T = ctx.get('act_T', 40)
nep = ctx['num_experiment_periods']
def build_path(dur):
    path = list(np.arange(1, nep + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    for t in range(min(dur, len(path))):
        path[t] = path[t] + 1
    return path

rec_path = build_path(1)

print(f"\nRunning pol scenario (recessionUI) dur=1...")
res_pol = AggEco_pol.run_experiment(
    shock_type='recessionUI',
    UpdatePrb=1.0,
    Splurge=ctx['base_dict']['Splurge'],
    EconomyMrkv_init=rec_path,
    Full_Output=True,
)

print(f"Running none scenario (recession) dur=1...")
res_none = AggEco_none.run_experiment(
    shock_type='recession',
    UpdatePrb=1.0,
    Splurge=ctx['base_dict']['Splurge'],
    EconomyMrkv_init=rec_path,
    Full_Output=True,
)

# Inspect keys
print(f"\nres_pol keys: {list(res_pol.keys())[:20]}")

# Get aNrm
for k in ['aNrm_all', 'mNrm_all', 'cNrm_all', 'cLvl_all_splurge', 'pLvl_all', 'Mrkv_hist']:
    if k in res_pol:
        v = np.asarray(res_pol[k])
        print(f"  {k}: shape {v.shape}")

# Find agents at MIXED (j_p=3, j_b=0) at t=1
# But we don't have base scenario yet. Use shared shock history to find equivalent.
# Actually agent at u3Q-pol AND u3Q-none AND emp-base at t=1.
# For simplicity, find agents at u3Q in pol AND u3Q in none at t=1, ignoring base.
J = 6
Mp = np.asarray(res_pol['Mrkv_hist']).astype(int)
Mn = np.asarray(res_none['Mrkv_hist']).astype(int)

jp = Mp % J
jn = Mn % J

# Show t=0, t=1 distribution
print(f"\nAt t=0: jp counts = {dict(zip(*np.unique(jp[0], return_counts=True)))}")
print(f"At t=1: jp counts = {dict(zip(*np.unique(jp[1], return_counts=True)))}")

# Find agents at u3Q in pol at t=1
mask_u3Q = (jp[1] == 3) & (jn[1] == 3)
idx = np.where(mask_u3Q)[0]
print(f"\nAgents at (jp=3, jn=3) at t=1: {len(idx)}")
if len(idx) == 0:
    print("No such agents. Try other cell.")
else:
    # For these agents, trace t=0 to t=1
    cNrm_pol_t0 = np.asarray(res_pol['cNrm_all'])[0, idx]
    cNrm_none_t0 = np.asarray(res_none['cNrm_all'])[0, idx]
    aNrm_pol_t0 = np.asarray(res_pol['aNrm_all'])[0, idx]
    aNrm_none_t0 = np.asarray(res_none['aNrm_all'])[0, idx]
    mNrm_pol_t0 = np.asarray(res_pol['mNrm_all'])[0, idx]
    mNrm_none_t0 = np.asarray(res_none['mNrm_all'])[0, idx]
    cNrm_pol_t1 = np.asarray(res_pol['cNrm_all'])[1, idx]
    cNrm_none_t1 = np.asarray(res_none['cNrm_all'])[1, idx]
    aNrm_pol_t1 = np.asarray(res_pol['aNrm_all'])[1, idx]
    aNrm_none_t1 = np.asarray(res_none['aNrm_all'])[1, idx]
    mNrm_pol_t1 = np.asarray(res_pol['mNrm_all'])[1, idx]
    mNrm_none_t1 = np.asarray(res_none['mNrm_all'])[1, idx]
    pLvl_pol_t0 = np.asarray(res_pol['pLvl_all'])[0, idx]
    pLvl_pol_t1 = np.asarray(res_pol['pLvl_all'])[1, idx]

    print(f"\n=== mean stats for {len(idx)} agents at MIXED (j_p=3) at t=1 ===")
    print(f"At t=0:")
    print(f"  mNrm: pol={mNrm_pol_t0.mean():.4f}, none={mNrm_none_t0.mean():.4f}, diff={(mNrm_pol_t0-mNrm_none_t0).mean():+.4f}")
    print(f"  cNrm: pol={cNrm_pol_t0.mean():.4f}, none={cNrm_none_t0.mean():.4f}, diff={(cNrm_pol_t0-cNrm_none_t0).mean():+.4f}")
    print(f"  aNrm: pol={aNrm_pol_t0.mean():.4f}, none={aNrm_none_t0.mean():.4f}, diff={(aNrm_pol_t0-aNrm_none_t0).mean():+.4f}")
    print(f"  pLvl: pol={pLvl_pol_t0.mean():.4f}")
    print(f"At t=1:")
    print(f"  mNrm: pol={mNrm_pol_t1.mean():.4f}, none={mNrm_none_t1.mean():.4f}, diff={(mNrm_pol_t1-mNrm_none_t1).mean():+.4f}")
    print(f"  cNrm: pol={cNrm_pol_t1.mean():.4f}, none={cNrm_none_t1.mean():.4f}, diff={(cNrm_pol_t1-cNrm_none_t1).mean():+.4f}")
    print(f"  aNrm: pol={aNrm_pol_t1.mean():.4f}, none={aNrm_none_t1.mean():.4f}, diff={(aNrm_pol_t1-aNrm_none_t1).mean():+.4f}")
    print(f"  pLvl: pol={pLvl_pol_t1.mean():.4f}")

    # Verify welfare direction
    cLvl_pol_t1 = np.asarray(res_pol['cLvl_all_splurge'])[1, idx]
    cLvl_none_t1 = np.asarray(res_none['cLvl_all_splurge'])[1, idx]
    print(f"\n  cLvl_splurge: pol={cLvl_pol_t1.mean():.4f}, none={cLvl_none_t1.mean():.4f}, diff={(cLvl_pol_t1-cLvl_none_t1).mean():+.4f}")
    print(f"  u(c_p) - u(c_n) at t=1 (rho=2): sign={'+' if (cLvl_pol_t1.mean()**(1-2) - cLvl_none_t1.mean()**(1-2)) > 0 else '-'}")
    print(f"  (= POSITIVE if c_p > c_n, NEGATIVE if c_p < c_n)")

# Compare to saved STALE pickle direction
print(f"\n=== Saved STALE pickle MC at MIXED (3,0) t=1 had: ===")
print(f"  mean cLvl pol = 9.66 (HIGHER than none)")
print(f"  mean cLvl none = 7.92")
print(f"  c_p > c_n by 22%")
print(f"\n=== Fresh MC just gave: ===")
if len(idx) > 0:
    print(f"  mean cLvl pol = {(cLvl_pol_t1).mean():.4f}")
    print(f"  mean cLvl none = {(cLvl_none_t1).mean():.4f}")
    print(f"  c_p - c_n = {(cLvl_pol_t1 - cLvl_none_t1).mean():+.4f}")

# Also run BASE scenario for full welfare computation
print("\n=== Running BASE scenario ===")
AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
base_path = list(np.arange(1, nep + 1) * 2) + [0] * 20  # no recession
res_base = AggEco_base.run_experiment(
    shock_type='base',
    UpdatePrb=1.0,
    Splurge=ctx['base_dict']['Splurge'],
    EconomyMrkv_init=base_path,
    Full_Output=True,
)

# Per-period welfare numerator (= per-agent sum)
cLvl_p = np.asarray(res_pol['cLvl_all_splurge'])
cLvl_n = np.asarray(res_none['cLvl_all_splurge'])
cLvl_b = np.asarray(res_base['cLvl_all_splurge'])
T = cLvl_p.shape[0]
rho = float(AggEco_pol.agents[0].CRRA)
Rfree = float(AggEco_pol.agents[0].Rfree[0])

W_per_t = np.zeros(T)
for t in range(T):
    cp = np.maximum(cLvl_p[t], 1e-12)
    cn = np.maximum(cLvl_n[t], 1e-12)
    cb = np.maximum(cLvl_b[t], 1e-12)
    if abs(rho - 1.0) < 1e-12:
        u_diff = np.log(cp) - np.log(cn)
    else:
        u_diff = (cp**(1-rho) - cn**(1-rho)) / (1-rho)
    W_per_t[t] = float(np.sum(u_diff * cb**rho))

AggInc_p = np.asarray(res_pol['AggIncome'])
AggInc_n = np.asarray(res_none['AggIncome'])
AggCon_p = np.asarray(res_pol['AggCons'])
AggCon_n = np.asarray(res_none['AggCons'])
AddInc = AggInc_p - AggInc_n
AddCon = AggCon_p - AggCon_n

def npv(s, R, T):
    return sum(s[t] / R**t for t in range(T))

NPV_w = npv(W_per_t, Rfree, T)
NPV_AI = npv(AddInc, Rfree, T)
NPV_AC = npv(AddCon, Rfree, T)
print(f"\n=== Fresh MC welfare-6 computation (HS_Only N=1000, dur=1) ===")
print(f"  NPV(welfare_num) = {NPV_w:.4e}")
print(f"  NPV(AddInc) = {NPV_AI:.4e}")
print(f"  NPV(AddCons) = {NPV_AC:.4e}")
if abs(NPV_AI) > 1e-10:
    ui_rec_dur1 = NPV_w / NPV_AI + (NPV_AI - NPV_AC) / NPV_AI
    print(f"  ui_rec (dur=1 only): {ui_rec_dur1:.4f}")
    print(f"  Compare to saved STALE pickle ui_rec: 1.6168")
    print(f"  Compare to 5D-self ui_rec: ~2.04")

print(f"\nPer-period welfare (first 8):")
for t in range(min(8, T)):
    print(f"  t={t}: W_MC = {W_per_t[t]:+.4e}")
