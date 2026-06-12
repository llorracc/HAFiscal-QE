"""
DUR=1 ONLY comparison: 5D vs fresh MC, per period.

Both use:
- HS_Only bug_fix
- dur=1 (only) realization
- Same recession path [3, 4, 6, 8, ...]
- Same agent count (49000)

Compare:
- Per-period AddInc
- Per-period AddCons
- Per-period welfare numerator (with c_b)

If they match per-period → 5D logic is fine for single dur
If they DON'T → find where they diverge
"""
import os, sys, pickle
os.environ.setdefault('HAFISCAL_UI_STATE_ENCODING', 'bug_fix')
os.environ.setdefault('HAFISCAL_AGENTCOUNT_H', '49000')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve

print("=== Building economy (HS_Only N=49000 bug_fix) ===")
ctx = build_and_solve('HS_Only')

# Solve all 3 scenarios
AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()

act_T = ctx.get('act_T', 40)
nep = ctx['num_experiment_periods']

# DUR=1 recession path
def build_path(dur):
    path = list(np.arange(1, nep + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    for t in range(min(dur, len(path))):
        path[t] = path[t] + 1
    return path

rec_path = build_path(1)
norec_path = list(np.arange(1, nep + 1) * 2) + [0] * 20  # all base

print(f"\nRunning pol (recessionUI dur=1)...")
res_pol = AggEco_pol.run_experiment(
    shock_type='recessionUI',
    UpdatePrb=1.0,
    Splurge=ctx['base_dict']['Splurge'],
    EconomyMrkv_init=rec_path,
    Full_Output=True,
)
print(f"Running none (recession dur=1)...")
res_none = AggEco_none.run_experiment(
    shock_type='recession',
    UpdatePrb=1.0,
    Splurge=ctx['base_dict']['Splurge'],
    EconomyMrkv_init=rec_path,
    Full_Output=True,
)

# For base, use base macro path
try:
    print(f"Running base (no recession)...")
    res_base = AggEco_base.run_experiment(
        shock_type='base',
        UpdatePrb=1.0,
        Splurge=ctx['base_dict']['Splurge'],
        EconomyMrkv_init=norec_path,
        Full_Output=True,
    )
except Exception as e:
    print(f"base run failed: {e}; using saved base pickle")
    res_base = None

# Per-period welfare numerator computation
cLvl_p = np.asarray(res_pol['cLvl_all_splurge'])
cLvl_n = np.asarray(res_none['cLvl_all_splurge'])
if res_base is not None:
    cLvl_b = np.asarray(res_base['cLvl_all_splurge'])
else:
    # Try to load saved base if available
    SAVED = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/welfare6_BUG043_bugfix_HS_seed0'
    with open(f'{SAVED}/base.pkl', 'rb') as f: d_base = pickle.load(f)
    cLvl_b = np.asarray(d_base['cLvl_all_splurge_bs'])  # bs = dur=1

T, N = cLvl_p.shape
rho = float(AggEco_pol.agents[0].CRRA)
Rfree = float(AggEco_pol.agents[0].Rfree[0])

# Per-period welfare numerator (per-agent sum)
print("\n=== Per-period MC welfare numerator (dur=1) ===")
W_mc_per_t = np.zeros(T)
for t in range(T):
    cp = np.maximum(cLvl_p[t], 1e-12)
    cn = np.maximum(cLvl_n[t], 1e-12)
    cb = np.maximum(cLvl_b[t], 1e-12)
    if abs(rho - 1.0) < 1e-12:
        u_diff = np.log(cp) - np.log(cn)
    else:
        u_diff = (cp**(1-rho) - cn**(1-rho)) / (1-rho)
    W_mc_per_t[t] = float(np.sum(u_diff * cb**rho))

# Per-period AddInc, AddCons
AggInc_p = np.asarray(res_pol['AggIncome'])
AggInc_n = np.asarray(res_none['AggIncome'])
AggCon_p = np.asarray(res_pol['AggCons'])
AggCon_n = np.asarray(res_none['AggCons'])
AddInc_mc = AggInc_p - AggInc_n
AddCon_mc = AggCon_p - AggCon_n

print(f"{'t':>3} {'W_MC':>14} {'AddInc_MC':>14} {'AddCon_MC':>14}")
for t in range(min(15, T)):
    print(f"{t:>3} {W_mc_per_t[t]:>+14.4e} {AddInc_mc[t]:>+14.4e} {AddCon_mc[t]:>+14.4e}")

def npv(s, R, T):
    return sum(s[t] / R**t for t in range(T))

NPV_w_mc = npv(W_mc_per_t, Rfree, T)
NPV_AI_mc = npv(AddInc_mc, Rfree, T)
NPV_AC_mc = npv(AddCon_mc, Rfree, T)
print(f"\n=== MC NPVs (dur=1) ===")
print(f"  NPV(welfare_num) = {NPV_w_mc:.4e}")
print(f"  NPV(AddInc) = {NPV_AI_mc:.4e}")
print(f"  NPV(AddCons) = {NPV_AC_mc:.4e}")
if abs(NPV_AI_mc) > 1e-10:
    ui_rec_mc_dur1 = NPV_w_mc / NPV_AI_mc + (NPV_AI_mc - NPV_AC_mc) / NPV_AI_mc
    print(f"  ui_rec (MC dur=1 only) = {ui_rec_mc_dur1:.4f}")

# Save MC per-period for later 5D comparison
np.savez('/tmp/mc_dur1_per_t.npz',
         W=W_mc_per_t, AI=AddInc_mc, AC=AddCon_mc,
         NPV_w=NPV_w_mc, NPV_AI=NPV_AI_mc, NPV_AC=NPV_AC_mc,
         Rfree=Rfree, rho=rho)
print(f"\nSaved MC per-period data to /tmp/mc_dur1_per_t.npz")

# Run 5D for dur=1
print(f"\n=== Now running 5D for dur=1 ONLY ===")
from welfare6_tm_joint5d import compute_joint_welfare5d
from tm_methods import compute_baseline_tm_data, calculate_NPV

for ag in AggEco_base.agents: ag.tm_a_indexed = True
for ag in AggEco_pol.agents: ag.tm_a_indexed = True
for ag in AggEco_none.agents: ag.tm_a_indexed = True

bd_list = compute_baseline_tm_data(AggEco_base, mCount=20, neutral_measure=True)
bd = bd_list[0]

agent_pol = AggEco_pol.agents[0]
agent_none = AggEco_none.agents[0]
agent_base = AggEco_base.agents[0]

res_5d = compute_joint_welfare5d(
    agent_pol, agent_none, agent_base, bd,
    EconomyMrkv_path_pn=rec_path, act_T=act_T, verbose=False,
)
W_5d_per_t = res_5d['welfare_num_series']
AddInc_5d = res_5d['AggInc_pol_series'] - res_5d['AggInc_none_series']
AddCon_5d = res_5d['AggCons_pol_series'] - res_5d['AggCons_none_series']

print("\n=== 5D per-period (dur=1) vs MC ===")
print(f"{'t':>3} {'W_5D':>14} {'W_MC':>14} {'5D/MC':>8}  {'AI_5D':>14} {'AI_MC':>14} {'5D/MC':>8}")
for t in range(min(15, T)):
    ratio_w = W_5d_per_t[t] / W_mc_per_t[t] if abs(W_mc_per_t[t]) > 1e-10 else float('nan')
    ratio_ai = AddInc_5d[t] / AddInc_mc[t] if abs(AddInc_mc[t]) > 1e-10 else float('nan')
    print(f"{t:>3} {W_5d_per_t[t]:>+14.4e} {W_mc_per_t[t]:>+14.4e} {ratio_w:>8.3f}  {AddInc_5d[t]:>+14.4e} {AddInc_mc[t]:>+14.4e} {ratio_ai:>8.3f}")

NPV_w_5d = npv(W_5d_per_t, Rfree, T)
NPV_AI_5d = npv(AddInc_5d, Rfree, T)
NPV_AC_5d = npv(AddCon_5d, Rfree, T)
print(f"\n=== 5D NPVs (dur=1) ===")
print(f"  NPV(welfare_num) = {NPV_w_5d:.4e}  vs MC: {NPV_w_mc:.4e}  ratio: {NPV_w_5d/NPV_w_mc:.3f}")
print(f"  NPV(AddInc) = {NPV_AI_5d:.4e}  vs MC: {NPV_AI_mc:.4e}  ratio: {NPV_AI_5d/NPV_AI_mc:.3f}")
print(f"  NPV(AddCons) = {NPV_AC_5d:.4e}  vs MC: {NPV_AC_mc:.4e}  ratio: {NPV_AC_5d/NPV_AC_mc:.3f}")
if abs(NPV_AI_5d) > 1e-10:
    ui_rec_5d_dur1 = NPV_w_5d / NPV_AI_5d + (NPV_AI_5d - NPV_AC_5d) / NPV_AI_5d
    print(f"  ui_rec (5D dur=1) = {ui_rec_5d_dur1:.4f}")
    print(f"  ui_rec (MC dur=1) = {ui_rec_mc_dur1:.4f}")
    print(f"  Gap: {(ui_rec_5d_dur1 - ui_rec_mc_dur1):+.4f} ({(ui_rec_5d_dur1/ui_rec_mc_dur1 - 1)*100:+.1f}%)")
