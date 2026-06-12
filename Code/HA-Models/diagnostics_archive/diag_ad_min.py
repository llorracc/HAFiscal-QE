"""
Minimal diagnostic: no-AD vs AD multipliers on HS_Only with a single
recession duration of 4 quarters, for all three policies.

Uses the canonical fixed no-AD policy-cost denominator
NPV(ΔY_noAD) for both no-AD and AD multipliers (Output_Results.py:210).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copy import deepcopy
import numpy as np

from test_asymptotic_equality_revised import setup_economy

RECDUR = 4
print(f"=== diag_ad_min: HS_Only, single recession duration={RECDUR} ===\n")

eco0, meta = setup_economy(Parametrization="HS_Only")
num_iter_ad = int(meta["num_max_iterations_solvingAD"])
conv_tol_ad = float(meta["convergence_tol_solvingAD"])
num_exp = meta["num_experiment_periods"]
base_dict = meta["base_dict"]

POLICIES = [
    ("recessionUI", "recession_UI_changes", "UI"),
    ("recessionTaxCut", "recession_TaxCut_changes", "TaxCut"),
    ("recessionCheck", "recession_Check_changes", "Check"),
]

# Standard MC burn-in
eco0.reset()
for a in eco0.agents:
    a.initialize_sim()
    a.AggDemandFac = 1.0; a.RfreeNow = 1.0; a.CaggNow = 1.0
eco0.make_history()
eco0.save_state()
eco0.switch_to_counterfactual_mode("base")
act_T = eco0.act_T
for a in eco0.agents:
    a.T_sim = act_T
    a.EconomyMrkvNow_hist = [0]*act_T
eco0.make_idiosyncratic_shock_histories()

base_results = eco0.run_experiment(**deepcopy(base_dict), Full_Output=True)
eco0.store_baseline(base_results['AggCons'])

def rec_path():
    p = list(np.arange(1, num_exp+1)*2) + [0]*20
    p[0:RECDUR] = (np.array(p[0:RECDUR]) + 1).tolist()
    return p[:act_T]

def run_one(eco_in, shock_type, changes, do_AD):
    eco = deepcopy(eco_in)
    eco.switch_shock_type(shock_type)
    if do_AD:
        eco.solve_ad_recession(
            num_max_iterations=num_iter_ad,
            convergence_cutoff=conv_tol_ad,
            shock_type=shock_type,
        )
    else:
        eco.solve()
    d = deepcopy(base_dict); d.update(changes); d['EconomyMrkv_init'] = rec_path()
    r = eco.run_experiment(**d, Full_Output=True)
    return float(np.sum(r['AggCons'])), float(np.sum(r['AggIncome']))

# Compute recession baseline (no-AD and AD) ONCE.
print("--- recession baseline ---")
rec_c_noAD, rec_y_noAD = run_one(eco0, "recession", meta["recession_changes"], do_AD=False)
print(f"  no-AD: NPV_C={rec_c_noAD:.2f}  NPV_Y={rec_y_noAD:.2f}")
rec_c_AD, rec_y_AD = run_one(eco0, "recession", meta["recession_changes"], do_AD=True)
print(f"  AD   : NPV_C={rec_c_AD:.2f}  NPV_Y={rec_y_AD:.2f}")

results = []
PAPER = {"UI": 1.258, "TaxCut": 1.124, "Check": 1.221}
for shock_type, ckey, label in POLICIES:
    print(f"\n--- {label} ({shock_type}) ---")
    c_noAD, y_noAD = run_one(eco0, shock_type, meta[ckey], do_AD=False)
    c_AD, y_AD = run_one(eco0, shock_type, meta[ckey], do_AD=True)
    print(f"  no-AD: NPV_C={c_noAD:.2f}  NPV_Y={y_noAD:.2f}")
    print(f"  AD   : NPV_C={c_AD:.2f}  NPV_Y={y_AD:.2f}")
    npv_y_denom = y_noAD - rec_y_noAD  # canonical fixed denominator
    m_noAD = (c_noAD - rec_c_noAD) / npv_y_denom if abs(npv_y_denom) > 1e-10 else float('nan')
    m_AD = (c_AD - rec_c_AD) / npv_y_denom if abs(npv_y_denom) > 1e-10 else float('nan')
    ratio = m_AD / m_noAD if m_noAD else float('nan')
    print(f"  fixed denom NPV_ΔY_noAD={npv_y_denom:.4f}")
    print(f"  M no-AD={m_noAD:.4f}  M AD={m_AD:.4f}  ratio={ratio:.3f}x  (paper {label}: {PAPER[label]}x)")
    results.append((label, m_noAD, m_AD, ratio))

print("\n" + "=" * 64)
print(f"  {'Policy':<10} {'no-AD':>10} {'AD':>10} {'AD/noAD':>10} {'paper':>10}")
print("=" * 64)
for label, m_noAD, m_AD, ratio in results:
    print(f"  {label:<10} {m_noAD:>10.4f} {m_AD:>10.4f} {ratio:>9.3f}x {PAPER[label]:>9.3f}x")
print("=" * 64)
