"""
Verify the Jensen bug in MC welfare-6 computation.

MC computes:
  cLvl_avg = E_dur[cLvl_per_dur]  (weighted average across recession durations)
  welfare = sum_i (u(cLvl_pol_avg) - u(cLvl_none_avg)) / u'(cLvl_base_avg)

This is wrong by Jensen's inequality for concave u.

CORRECT:
  per_dur_welfare = sum_i (u(cLvl_pol_at_dur) - u(cLvl_none_at_dur)) / u'(cLvl_base_at_dur)
  welfare = E_dur[per_dur_welfare]  (weighted avg of per-dur welfare)

These differ. This script runs MC for ALL 11 durations and computes
welfare BOTH ways to demonstrate the bias.
"""
import os, sys, pickle, time
os.environ.setdefault('HAFISCAL_UI_STATE_ENCODING', 'bug_fix')
os.environ.setdefault('HAFISCAL_AGENTCOUNT_H', '49000')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve

print("=== Building economy (HS_Only N=49000 bug_fix) ===")
ctx = build_and_solve('HS_Only')

# Solve scenarios
AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()

act_T = ctx.get('act_T', 40)
nep = ctx['num_experiment_periods']
Rspell = ctx.get('Rspell', 6.0)
max_dur = ctx.get('max_recession_duration', nep)

def build_path(dur):
    path = list(np.arange(1, nep + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    for t in range(min(dur, len(path))):
        path[t] = path[t] + 1
    return path

# Compute rec_probs (same as in _prob_weighted_rec)
R_persist = 1.0 - 1.0 / Rspell
rec_probs = np.array([R_persist**t * (1 - R_persist) for t in range(max_dur)])
rec_probs[-1] = 1.0 - np.sum(rec_probs[:-1])
print(f"rec_probs: {rec_probs.round(4)}")

# Run pol, none, base for ALL durations
print(f"\nRunning {max_dur} durations for pol, none, base...")
all_res_pol = []
all_res_none = []
# Base is run only once (no recession)
norec_path = list(np.arange(1, nep + 1) * 2) + [0] * 20
try:
    res_base = AggEco_base.run_experiment(
        shock_type='base', UpdatePrb=1.0, Splurge=ctx['base_dict']['Splurge'],
        EconomyMrkv_init=norec_path, Full_Output=True)
    cLvl_b_dur = [np.asarray(res_base['cLvl_all_splurge'])] * max_dur  # base same for all durs
    print("  base: ran successfully")
except Exception as e:
    print(f"  base error: {e}; using saved bs pickle")
    SAVED = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/welfare6_BUG043_bugfix_HS_seed0'
    with open(f'{SAVED}/base.pkl', 'rb') as f: d_base = pickle.load(f)
    cLvl_b_dur = [np.asarray(d_base['cLvl_all_splurge_bs'])] * max_dur

for dur in range(1, max_dur + 1):
    rec_path = build_path(dur)
    t0 = time.time()
    res_p = AggEco_pol.run_experiment(
        shock_type='recessionUI', UpdatePrb=1.0, Splurge=ctx['base_dict']['Splurge'],
        EconomyMrkv_init=rec_path, Full_Output=True)
    res_n = AggEco_none.run_experiment(
        shock_type='recession', UpdatePrb=1.0, Splurge=ctx['base_dict']['Splurge'],
        EconomyMrkv_init=rec_path, Full_Output=True)
    all_res_pol.append({'cLvl': np.asarray(res_p['cLvl_all_splurge']),
                        'AggInc': np.asarray(res_p['AggIncome']),
                        'AggCon': np.asarray(res_p['AggCons'])})
    all_res_none.append({'cLvl': np.asarray(res_n['cLvl_all_splurge']),
                         'AggInc': np.asarray(res_n['AggIncome']),
                         'AggCon': np.asarray(res_n['AggCons'])})
    print(f"  dur={dur:>2}: pol+none ran ({time.time()-t0:.0f}s)")

# Now compute welfare BOTH ways
rho = 2.0
Rfree = 1.01
T, N = all_res_pol[0]['cLvl'].shape

def felicity(c):
    """u(c) = c^(1-rho)/(1-rho), broadcast over (T, N) panel."""
    c_safe = np.maximum(c, 1e-12)
    return (c_safe**(1-rho)) / (1-rho)

# METHOD A: WRONG (= MC's current method): u(avg c)
print("\n=== METHOD A: WRONG — u(avg over durations of cLvl) — what MC currently does ===")
# avg cLvl across durations
avg_pol = sum(rec_probs[d] * all_res_pol[d]['cLvl'] for d in range(max_dur))
avg_none = sum(rec_probs[d] * all_res_none[d]['cLvl'] for d in range(max_dur))
avg_base = cLvl_b_dur[0]  # base same across durs
avg_AggInc_p = sum(rec_probs[d] * all_res_pol[d]['AggInc'] for d in range(max_dur))
avg_AggInc_n = sum(rec_probs[d] * all_res_none[d]['AggInc'] for d in range(max_dur))
avg_AggCon_p = sum(rec_probs[d] * all_res_pol[d]['AggCon'] for d in range(max_dur))
avg_AggCon_n = sum(rec_probs[d] * all_res_none[d]['AggCon'] for d in range(max_dur))

pol_w_avg = felicity(avg_pol)
none_w_avg = felicity(avg_none)
base_MU_avg = np.maximum(avg_base, 1e-12)**(-rho)
NPV_AddInc_avg = sum((avg_AggInc_p[t] - avg_AggInc_n[t]) / Rfree**t for t in range(T))
NPV_AddCon_avg = sum((avg_AggCon_p[t] - avg_AggCon_n[t]) / Rfree**t for t in range(T))
W_per_t_avg = np.zeros(T)
for t in range(T):
    W_per_t_avg[t] = float(np.sum((pol_w_avg[t] - none_w_avg[t]) * (avg_base[t]**rho)))
NPV_W_avg = sum(W_per_t_avg[t] / Rfree**t for t in range(T))

ui_rec_A = NPV_W_avg / NPV_AddInc_avg + (NPV_AddInc_avg - NPV_AddCon_avg) / NPV_AddInc_avg
print(f"  NPV(W) = {NPV_W_avg:.4e}, NPV(AI) = {NPV_AddInc_avg:.4e}")
print(f"  ui_rec_A (= MC current method) = {ui_rec_A:.4f}")

# METHOD B: CORRECT (= compute welfare per dur, then weighted avg)
print("\n=== METHOD B: CORRECT — avg over durations of u(cLvl) per duration ===")
W_per_t_correct = np.zeros(T)
for dur in range(max_dur):
    cp = np.maximum(all_res_pol[dur]['cLvl'], 1e-12)
    cn = np.maximum(all_res_none[dur]['cLvl'], 1e-12)
    cb = np.maximum(cLvl_b_dur[dur], 1e-12)
    u_diff = (cp**(1-rho) - cn**(1-rho)) / (1-rho)
    per_t_per_dur = np.sum(u_diff * cb**rho, axis=1)
    W_per_t_correct += rec_probs[dur] * per_t_per_dur

NPV_W_correct = sum(W_per_t_correct[t] / Rfree**t for t in range(T))
NPV_AddInc_correct = NPV_AddInc_avg  # income aggregation is linear, no Jensen issue
NPV_AddCon_correct = NPV_AddCon_avg

ui_rec_B = NPV_W_correct / NPV_AddInc_correct + (NPV_AddInc_correct - NPV_AddCon_correct) / NPV_AddInc_correct
print(f"  NPV(W) = {NPV_W_correct:.4e}, NPV(AI) = {NPV_AddInc_correct:.4e}")
print(f"  ui_rec_B (= CORRECT method) = {ui_rec_B:.4f}")

print(f"\n=== Difference ===")
print(f"  ui_rec_A (MC current, biased) = {ui_rec_A:.4f}")
print(f"  ui_rec_B (correct)            = {ui_rec_B:.4f}")
print(f"  Gap A-B: {ui_rec_A - ui_rec_B:+.4f} ({(ui_rec_A/ui_rec_B - 1)*100:+.2f}%)")
print(f"  5D ui_rec was 2.04 (close to which?)")
