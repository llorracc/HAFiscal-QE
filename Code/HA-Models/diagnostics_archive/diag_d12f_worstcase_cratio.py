"""D-12f: Compare MC vs TM-a empirical Cratio for the WORST-CASE Check experiment.
This tells us whether the Phase 1 CFunc training receives different intercepts."""
import pickle, numpy as np

DIR = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Figures/Reduced_Run_diag_bug040_off'

def load(name):
    return pickle.load(open(f'{DIR}/{name}', 'rb'))

# all_results = list of dicts, one per recession duration (1q, 2q, ..., maxq)
rec_chk_all_mc = load('recessionCheck_all_results_MC.csv')
rec_chk_all_tm = load('recessionCheck_all_results_TM.csv')
rec_all_mc = load('recession_all_results_MC.csv')
rec_all_tm = load('recession_all_results_TM.csv')

print(f"Number of recession-duration variants in MC: {len(rec_chk_all_mc)}")
print(f"Number of recession-duration variants in TM: {len(rec_chk_all_tm)}")

# Worst case = last (longest recession)
worst_mc_chk = rec_chk_all_mc[-1]
worst_mc_rec = rec_all_mc[-1]
worst_tm_chk = rec_chk_all_tm[-1]
worst_tm_rec = rec_all_tm[-1]

# We need base_AggCons too (per-period MC base cons)
base_mc = load('base_results.csv')
base_tm = load('base_results_TM.csv')

print("\n=== WORST-CASE recessionCheck Cratio (= empirical AggCons / base_AggCons) ===")
print("This is what would set MacroCFunc intercepts in 1st-round CFunc training.\n")
print(f"{'t':<3} {'MC AggCons':<12} {'MC base':<10} {'MC Cratio':<10}  {'TM AggCons':<12} {'TM base':<10} {'TM Cratio':<10}  {'Δ Cratio':<10}")

base_c_mc_arr = np.asarray(base_mc['AggCons']).flatten()
base_c_tm_arr = np.asarray(base_tm['AggCons']).flatten()

mc_chk = np.asarray(worst_mc_chk['AggCons']).flatten()
tm_chk = np.asarray(worst_tm_chk['AggCons']).flatten()

for t in range(min(15, len(mc_chk))):
    mc_cratio = mc_chk[t] / base_c_mc_arr[t]
    tm_cratio = tm_chk[t] / base_c_tm_arr[t]
    print(f"{t:<3} {mc_chk[t]:<12.0f} {base_c_mc_arr[t]:<10.0f} {mc_cratio:<10.4f}  "
          f"{tm_chk[t]:<12.0f} {base_c_tm_arr[t]:<10.0f} {tm_cratio:<10.4f}  {mc_cratio-tm_cratio:<+10.4f}")

print("\n=== WORST-CASE recession-only Cratio ===\n")
print(f"{'t':<3} {'MC Cratio':<10} {'TM Cratio':<10} {'Δ':<10}")
mc_rec = np.asarray(worst_mc_rec['AggCons']).flatten()
tm_rec = np.asarray(worst_tm_rec['AggCons']).flatten()
for t in range(min(15, len(mc_rec))):
    mc_cratio = mc_rec[t] / base_c_mc_arr[t]
    tm_cratio = tm_rec[t] / base_c_tm_arr[t]
    print(f"{t:<3} {mc_cratio:<10.4f} {tm_cratio:<10.4f} {mc_cratio-tm_cratio:<+10.4f}")

print("\n=== Difference: recessionCheck - recession Cratio (= 'check effect on Cratio') ===\n")
print(f"{'t':<3} {'MC ΔCratio':<12} {'TM ΔCratio':<12} {'MC/TM':<8}")
for t in range(min(15, len(mc_chk))):
    mc_dC = (mc_chk[t] - mc_rec[t]) / base_c_mc_arr[t]
    tm_dC = (tm_chk[t] - tm_rec[t]) / base_c_tm_arr[t]
    ratio = mc_dC / tm_dC if abs(tm_dC) > 1e-9 else float('nan')
    print(f"{t:<3} {mc_dC:<12.6f} {tm_dC:<12.6f} {ratio:<8.3f}")

print("\n=== INTERPRETATION ===")
print("If MC's ΔCratio[t≥1] (Check propagation effect) >> TM's ΔCratio[t≥1]:")
print("  → MC's worst-case CFunc intercepts will be higher than TM's for Check")
print("  → MC's 1st-round AD ADF will amplify income more")
print("  → MC's 1st-round AD multiplier > TM's (matches the +11% residual)")
