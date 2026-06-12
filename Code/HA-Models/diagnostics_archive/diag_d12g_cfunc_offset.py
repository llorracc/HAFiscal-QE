"""D-12g: Verify the CFunc cell offset bug.

HYPOTHESIS:
  - MC's mill_rule uses CFunc[hist[t-1]][hist[t]] to determine Cratio that
    drives ADF at period t+1 (one-period lookahead).
  - TM's eval_Cratio uses CFunc[hist[t-1]][hist[t]] to determine Cratio
    used DIRECTLY for ADF at period t (no lookahead).
  - These produce a 1-period TIMING MISMATCH in CFunc cell selection.

For Check experiment with 3-quarter recession path [3, 5, 7, 0, 0, ...]:
  - MC's ADF at t=1 uses CFunc[0][3].intercept = Cratio_chk[0] (LARGE)
  - TM's ADF at t=1 uses CFunc[3][5].intercept = Cratio_chk[1] (small)
  - This explains the 4.5× ΔY[1] amplification we observed.
"""
import pickle, numpy as np

DIR = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Figures/Reduced_Run_diag_bug040_off'

def load(name):
    return pickle.load(open(f'{DIR}/{name}', 'rb'))

# Use worst-case Cratio (TM ≈ MC, from D-12f) as proxy for trained CFunc intercepts
rec_chk_all_mc = load('recessionCheck_all_results_MC.csv')
rec_chk_all_tm = load('recessionCheck_all_results_TM.csv')
rec_all_mc = load('recession_all_results_MC.csv')
rec_all_tm = load('recession_all_results_TM.csv')
base_mc = load('base_results.csv')
base_tm = load('base_results_TM.csv')

worst_chk_mc = rec_chk_all_mc[-1]
worst_rec_mc = rec_all_mc[-1]
worst_chk_tm = rec_chk_all_tm[-1]
worst_rec_tm = rec_all_tm[-1]

base_c_mc = np.asarray(base_mc['AggCons']).flatten()
base_c_tm = np.asarray(base_tm['AggCons']).flatten()

# Trained intercepts for CFunc[0][3], [3][5], [5][7], [7][9], etc.
# Index t in worst-case = trained CFunc cell at "period t" of the worst case.
chk_cratio_mc = np.asarray(worst_chk_mc['AggCons']).flatten() / base_c_mc
chk_cratio_tm = np.asarray(worst_chk_tm['AggCons']).flatten() / base_c_tm
rec_cratio_mc = np.asarray(worst_rec_mc['AggCons']).flatten() / base_c_mc
rec_cratio_tm = np.asarray(worst_rec_tm['AggCons']).flatten() / base_c_tm

print("Trained MacroCFunc intercepts (worst-case Cratio_hist[t]):")
print(f"{'t':<3} {'cell':<10} {'MC chk':<10} {'MC rec':<10} {'MC Δ':<10} {'TM chk':<10} {'TM rec':<10} {'TM Δ':<10}")
for t in range(8):
    cell = f"[{2*t-1 if t>0 else 0}][{2*t+1}]"
    print(f"{t:<3} {cell:<10} {chk_cratio_mc[t]:<10.4f} {rec_cratio_mc[t]:<10.4f} {chk_cratio_mc[t]-rec_cratio_mc[t]:<+10.4f} "
          f"{chk_cratio_tm[t]:<10.4f} {rec_cratio_tm[t]:<10.4f} {chk_cratio_tm[t]-rec_cratio_tm[t]:<+10.4f}")

# Compute predicted ADF profile for the actual 3-quarter recession scenario
# 3-quarter recession path: [3, 5, 7, 0, 0, ...]
print("\n\nPredicted ΔADF (chk-rec) for 3-quarter recession scenario:")
print("Conventional: ADF[t] = (Cratio[t-1])^(0.3) for t with RecState[t-1]=1")
print()

# MC convention (CFunc cell offset):
# ADF[1] uses CFunc[0][3].intercept = Cratio[0] of worst case
# ADF[2] uses CFunc[3][5].intercept = Cratio[1]
# ADF[3] uses CFunc[5][7].intercept = Cratio[2]
# ADF[4] uses CFunc[7][9].intercept = Cratio[3] BUT in 3-quarter recession,
#   the actual path is [3, 5, 7, 0, ...], so ADF[4] uses CFunc[7][0].intercept = 1.0 (default)

# TM convention:
# ADF[1] uses CFunc[3][5].intercept = Cratio[1] of worst case
# ADF[2] uses CFunc[5][7].intercept = Cratio[2]
# ADF[3] uses CFunc[7][0].intercept = 1.0 (default, never trained)
# ADF[4+] = 1

print(f"{'period':<8} {'MC interpretation':<35} {'MC ΔADF est':<15} {'TM interpretation':<35} {'TM ΔADF est':<15}")
ADel = 0.3

# 3-quarter recession path [3, 5, 7, 0, 0, ...] - CFunc cells used:
# Index t = the period at which ADF[t] applies (income at period t)
# MC: at mill_rule(t-1) computes ADF for period t, using CFunc[hist[t-2]][hist[t-1]]
# TM: at period t computes AggDemandFac_t = eval_Cratio[t]^(...) where eval_Cratio[t] = CFunc[hist[t-1]][hist[t]]

# Trained worst-case Cratio_hist (proxy for MacroCFunc intercepts):
# Cratio[t] in worst case is the empirical Cratio at period t of the all-recession path
# This becomes MacroCFunc intercept at cell:
#   CFunc[0][3] = Cratio[0]  (entry: 0 → 3)
#   CFunc[3][5] = Cratio[1]  (3 → 5)
#   CFunc[5][7] = Cratio[2]  (5 → 7)
#   CFunc[7][9] = Cratio[3]  (7 → 9)
#   ...

# In the actual 3-quarter recession scenario, the path is [3, 5, 7, 0, 0, ...]
# So ALL transitions for t≥3 hit untrained cells (default intercept = 1)

for t in range(1, 6):
    # MC: ADF[t] uses CFunc[hist[t-2]][hist[t-1]].intercept
    # For t=1: hist[-1]=0 (special), hist[0]=3, so CFunc[0][3] = trained Cratio[0]
    # For t=2: hist[0]=3, hist[1]=5, so CFunc[3][5] = trained Cratio[1]
    # For t=3: hist[1]=5, hist[2]=7, so CFunc[5][7] = trained Cratio[2]
    # For t=4: hist[2]=7, hist[3]=0, so CFunc[7][0] = NOT TRAINED = 1.0
    # For t=5: hist[3]=0, hist[4]=0, so CFunc[0][0] = NOT TRAINED = 1.0
    if t == 1:
        mc_intercept_chk = chk_cratio_mc[0]
        mc_intercept_rec = rec_cratio_mc[0]
        mc_label = "CFunc[0][3]=Cratio[0]"
    elif t == 2:
        mc_intercept_chk = chk_cratio_mc[1]
        mc_intercept_rec = rec_cratio_mc[1]
        mc_label = "CFunc[3][5]=Cratio[1]"
    elif t == 3:
        mc_intercept_chk = chk_cratio_mc[2]
        mc_intercept_rec = rec_cratio_mc[2]
        mc_label = "CFunc[5][7]=Cratio[2]"
    else:
        mc_intercept_chk = 1.0
        mc_intercept_rec = 1.0
        mc_label = f"CFunc[..][0]=1 (untrained)"

    # TM: ADF[t] uses CFunc[hist[t-1]][hist[t]].intercept
    # For t=1: hist[0]=3, hist[1]=5, so CFunc[3][5] = trained Cratio[1]
    # For t=2: hist[1]=5, hist[2]=7, so CFunc[5][7] = trained Cratio[2]
    # For t=3: hist[2]=7, hist[3]=0, so CFunc[7][0] = NOT TRAINED = 1.0
    # For t=4+: untrained = 1.0
    if t == 1:
        tm_intercept_chk = chk_cratio_tm[1]
        tm_intercept_rec = rec_cratio_tm[1]
        tm_label = "CFunc[3][5]=Cratio[1]"
    elif t == 2:
        tm_intercept_chk = chk_cratio_tm[2]
        tm_intercept_rec = rec_cratio_tm[2]
        tm_label = "CFunc[5][7]=Cratio[2]"
    else:
        tm_intercept_chk = 1.0
        tm_intercept_rec = 1.0
        tm_label = f"CFunc[..][0]=1 (untrained)"

    # RecState in lagged convention: hist[t-1] for ADF at t
    # 3-quarter rec: hist[0]=3,1=5,2=7,3+=0
    # t=1: hist[0]=3 (rec) → 1
    # t=2: hist[1]=5 (rec) → 1
    # t=3: hist[2]=7 (rec) → 1
    # t=4: hist[3]=0 (recovery) → 0
    rec_state_lagged = 1.0 if t <= 3 else 0.0
    mc_dadf = (mc_intercept_chk ** (ADel * rec_state_lagged)) - (mc_intercept_rec ** (ADel * rec_state_lagged))
    tm_dadf = (tm_intercept_chk ** (ADel * rec_state_lagged)) - (tm_intercept_rec ** (ADel * rec_state_lagged))
    print(f"{t:<8} {mc_label:<35} {mc_dadf:<+15.6f} {tm_label:<35} {tm_dadf:<+15.6f}")

# Predict ΔY using AVG ergodic income
print("\n\nPredicted ΔY[t] = Y_baseline * ΔADF[t]:")
Y_baseline = 545000
print(f"{'period':<8} {'MC pred ΔY':<12} {'TM pred ΔY':<12} {'MC actual':<12} {'TM actual':<12}")
mc_pred = []
tm_pred = []
for t in range(1, 6):
    rec_state = 1.0 if t <= 3 else 0.0
    if t == 1:
        mc_dadf = (chk_cratio_mc[0]**(ADel*rec_state)) - (rec_cratio_mc[0]**(ADel*rec_state))
        tm_dadf = (chk_cratio_tm[1]**(ADel*rec_state)) - (rec_cratio_tm[1]**(ADel*rec_state))
    elif t == 2:
        mc_dadf = (chk_cratio_mc[1]**(ADel*rec_state)) - (rec_cratio_mc[1]**(ADel*rec_state))
        tm_dadf = (chk_cratio_tm[2]**(ADel*rec_state)) - (rec_cratio_tm[2]**(ADel*rec_state))
    elif t == 3:
        mc_dadf = (chk_cratio_mc[2]**(ADel*rec_state)) - (rec_cratio_mc[2]**(ADel*rec_state))
        tm_dadf = 0.0  # CFunc[7][0] untrained
    else:
        mc_dadf = 0.0
        tm_dadf = 0.0
    mc_pred.append(Y_baseline * mc_dadf)
    tm_pred.append(Y_baseline * tm_dadf)

# Actual deltas from D-12c FULL-AD output
mc_actual = [5400.5, 1637.2, 860.7, 530.5, 353.1]
tm_actual = [1189.2, 672.6, 418.9, 277.2, 190.2]

for i, t in enumerate(range(1, 6)):
    print(f"{t:<8} {mc_pred[i]:<12.0f} {tm_pred[i]:<12.0f} {mc_actual[i]:<12.0f} {tm_actual[i]:<12.0f}")

print("\n\nIf MC pred ≈ MC actual AND TM pred ≈ TM actual, hypothesis confirmed.")
