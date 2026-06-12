"""
Minimal diagnostic: UI multiplier no-AD vs AD on HS_Only with a single
recession duration of 4 quarters. Use the test driver's setup_economy
to avoid duplicating the setup-time bug fixes.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copy import deepcopy
import numpy as np

from test_asymptotic_equality_revised import setup_economy

RECDUR = 4
print(f"=== diag_ui_ad_min: HS_Only, single recession duration={RECDUR} ===\n")

eco0, meta = setup_economy(Parametrization="HS_Only")
ADelas = float(getattr(eco0, "demand_ADelasticity", 0.3))
num_iter_ad = int(meta["num_max_iterations_solvingAD"])
conv_tol_ad = float(meta["convergence_tol_solvingAD"])
num_exp = meta["num_experiment_periods"]
base_dict = meta["base_dict"]
recession_changes = meta["recession_changes"]
recession_UI_changes = meta["recession_UI_changes"]

# Standard MC burn-in (matches Phase 7 / Simulate.py)
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

# Baseline (non-recession) — needed for AD Cratio reference
base_results = eco0.run_experiment(**deepcopy(base_dict), Full_Output=True)
eco0.store_baseline(base_results['AggCons'])
print(f"non-recession baseline NPV_C={float(np.sum(base_results['AggCons'])):.2f}")

def rec_path():
    p = list(np.arange(1, num_exp+1)*2) + [0]*20
    p[0:RECDUR] = (np.array(p[0:RECDUR]) + 1).tolist()
    return p[:act_T]

print(f"recession path (first 10): {rec_path()[:10]}")

def run_one(eco_in, shock_type, changes, label):
    eco = deepcopy(eco_in)
    eco.switch_shock_type(shock_type)
    eco.solve()
    d = deepcopy(base_dict); d.update(changes); d['EconomyMrkv_init'] = rec_path()
    r = eco.run_experiment(**d, Full_Output=True)
    npv_c = float(np.sum(r['AggCons'])); npv_y = float(np.sum(r['AggIncome']))
    print(f"  {label}: NPV_C={npv_c:.2f}  NPV_Y={npv_y:.2f}")
    return npv_c, npv_y, r

print("\n--- NO-AD ---")
rec_c, rec_y, _ = run_one(eco0, "recession", recession_changes, "recession")
ui_c, ui_y, _ = run_one(eco0, "recessionUI", recession_UI_changes, "recessionUI")
mult_noAD = (ui_c - rec_c) / (ui_y - rec_y) if abs(ui_y - rec_y) > 1e-10 else float('nan')
print(f"  UI no-AD multiplier = ({ui_c-rec_c:.4f}) / ({ui_y-rec_y:.4f}) = {mult_noAD:.4f}")

def ad_run(shock_type, changes, label):
    print(f"\n--- AD: solve_ad_recession({shock_type}) ---")
    eco = deepcopy(eco0)
    eco.switch_shock_type(shock_type)
    eco.solve_ad_recession(
        num_max_iterations=num_iter_ad,
        convergence_cutoff=conv_tol_ad,
        shock_type=shock_type,
    )
    d = deepcopy(base_dict); d.update(changes); d['EconomyMrkv_init'] = rec_path()
    r = eco.run_experiment(**d, Full_Output=True)
    cr = np.array(r.get('Cratio_hist', [1.]*5))
    print(f"  {label} AD: NPV_C={float(np.sum(r['AggCons'])):.2f}  NPV_Y={float(np.sum(r['AggIncome'])):.2f}")
    print(f"  {label} Cratio_hist (first 10): {cr[:10]}  mean={cr.mean():.4f}  min={cr.min():.4f}")
    return float(np.sum(r['AggCons'])), float(np.sum(r['AggIncome']))

rec_c_ad, rec_y_ad = ad_run("recession", recession_changes, "recession")
ui_c_ad, ui_y_ad = ad_run("recessionUI", recession_UI_changes, "recessionUI")
mult_AD = (ui_c_ad - rec_c_ad) / (ui_y_ad - rec_y_ad) if abs(ui_y_ad - rec_y_ad) > 1e-10 else float('nan')

print("\n=" * 60)
print(f"  UI multiplier no AD : {mult_noAD:.4f}")
print(f"  UI multiplier with AD: {mult_AD:.4f}")
print(f"  AD/noAD ratio       : {mult_AD/mult_noAD:.4f}   (paper: 1.258)")
print("=" * 60)
