"""
Full Baseline run with TM only (no MC), including AD effects.
Writes to Figures/CRRA2_TM/ to avoid overwriting MC results.
Compares TM multipliers against published HAFiscal-QE values.
"""
import os, sys
from time import time

cwd = os.getcwd()
folders = cwd.split(os.path.sep)
top_most_folder = folders[-1]
if top_most_folder == 'FromPandemicCode':
    Abs_Path = cwd
else:
    Abs_Path = cwd + '/Code/HA-Models/FromPandemicCode'
    os.chdir(Abs_Path)
sys.path.append(Abs_Path)

from Simulate import Simulate

Run_Dict = dict()
Run_Dict['Run_Baseline']            = True
Run_Dict['Run_Recession ']          = True
Run_Dict['Run_Check_Recession']     = True
Run_Dict['Run_UB_Ext_Recession']    = True
Run_Dict['Run_TaxCut_Recession']    = True
Run_Dict['Run_Check']               = True
Run_Dict['Run_UB_Ext']              = True
Run_Dict['Run_TaxCut']              = True
Run_Dict['Run_AD ']                 = True
Run_Dict['Run_1stRoundAD']          = True
Run_Dict['Run_NonAD']               = True
Run_Dict['sim_method']              = 'TM'

figs_dir = Abs_Path + '/Figures/CRRA2_TM/'
os.makedirs(figs_dir, exist_ok=True)

t0 = time()
Simulate(Run_Dict, figs_dir, Parametrization='Baseline')
t1 = time()
print(f'\n=== Full TM run took {(t1-t0)/60:.1f} min ===\n')

# ---------- Compare TM vs published HAFiscal-QE multipliers ----------
import pickle, numpy as np

def load_pkl(name):
    with open(figs_dir + name + '.csv', 'rb') as f:
        return pickle.load(f)

# Published CRRA2 Baseline multipliers (from Tables/CRRA2/Multiplier.tex)
published = {
    'Check':    {'noAD': 0.878, 'AD': 1.228, '1stAD': 1.153},
    'UI':       {'noAD': 0.906, 'AD': 1.209, '1stAD': 1.147},
    'TaxCut':   {'noAD': 0.846, 'AD': 0.975, '1stAD': 0.949},
}

from tm_methods import calculate_NPV

try:
    base = load_pkl('base_results')
    base_rec = load_pkl('recession_results')
    Rfree_q = base['AggCons'][0] / base['AggCons'][0]  # placeholder
    # Get Rfree from parameters
    from Parameters import return_parameters
    params = return_parameters(Parametrization='Baseline', OutputFor='_Main.py')
    # Rfree is in the init_consumer dict
    init_consumer = params[1]
    Rfree = init_consumer['Rfree']
    if hasattr(Rfree, '__len__'):
        Rfree = Rfree[0]
    act_T = len(base['AggCons'])
except Exception as e:
    print(f"Error loading baseline: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

def npv_multiplier(shock_result, baseline_result, Rfree, act_T):
    dC = np.array(shock_result['AggCons']) - np.array(baseline_result['AggCons'])
    dY = np.array(shock_result['AggIncome']) - np.array(baseline_result['AggIncome'])
    npv_c = calculate_NPV(dC, act_T, Rfree)
    npv_y = calculate_NPV(dY, act_T, Rfree)
    return npv_c / npv_y if abs(npv_y) > 1e-10 else float('nan')

print("=" * 80)
print("TM vs Published HAFiscal-QE Multipliers (Baseline / CRRA2)")
print("=" * 80)
print(f"{'Policy':20s} {'Variant':12s} {'TM':>8s} {'Published':>10s} {'Diff':>8s} {'%Err':>7s}")
print("-" * 80)

for policy, pub_vals in published.items():
    # No-recession variant
    try:
        res = load_pkl(policy + '_results')
        mult = npv_multiplier(res, base, Rfree, act_T)
        print(f"  {policy:18s} {'noRec':12s} {mult:8.4f} {'':>10s} {'':>8s} {'':>7s}")
    except Exception as e:
        print(f"  {policy:18s} {'noRec':12s} ERROR: {e}")

    # Recession non-AD
    shock_name = 'recession' + policy
    try:
        res = load_pkl(shock_name + '_results')
        mult = npv_multiplier(res, base_rec, Rfree, act_T)
        diff = mult - pub_vals['noAD']
        pct = 100 * diff / pub_vals['noAD']
        print(f"  {policy:18s} {'rec noAD':12s} {mult:8.4f} {pub_vals['noAD']:10.3f} {diff:+8.4f} {pct:+6.1f}%")
    except Exception as e:
        print(f"  {policy:18s} {'rec noAD':12s} ERROR: {e}")

    # Recession AD
    try:
        res_ad = load_pkl(shock_name + '_results_AD')
        mult_ad = npv_multiplier(res_ad, base_rec, Rfree, act_T)
        diff = mult_ad - pub_vals['AD']
        pct = 100 * diff / pub_vals['AD']
        print(f"  {policy:18s} {'rec AD':12s} {mult_ad:8.4f} {pub_vals['AD']:10.3f} {diff:+8.4f} {pct:+6.1f}%")
    except Exception as e:
        print(f"  {policy:18s} {'rec AD':12s} ERROR: {e}")

    # Recession 1st round AD
    try:
        res_1st = load_pkl(shock_name + '_results_firstRoundAD')
        mult_1st = npv_multiplier(res_1st, base_rec, Rfree, act_T)
        diff = mult_1st - pub_vals['1stAD']
        pct = 100 * diff / pub_vals['1stAD']
        print(f"  {policy:18s} {'rec 1stAD':12s} {mult_1st:8.4f} {pub_vals['1stAD']:10.3f} {diff:+8.4f} {pct:+6.1f}%")
    except Exception as e:
        print(f"  {policy:18s} {'rec 1stAD':12s} ERROR: {e}")

    print()

print("=" * 80)
print("Notes:")
print("  - Published values from Tables/CRRA2/Multiplier.tex (MC-based)")
print("  - TM values computed with mCount=100 default grid")
print("  - AD computed via run_ad_tm (Cratio iteration on 2D cFunc)")
print("=" * 80)
