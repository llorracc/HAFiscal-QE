"""
A.1: per-period welfare comparison between MC (computed from saved pickles)
and my 5D joint kernel.

For each period t, compute:
  W_num_MC[t] = sum over agents i of (u(c_p_it) - u(c_n_it)) / u'(c_b_it)
  W_num_5D[t] = my 5D's per-period welfare numerator

Compare periods where the gap is concentrated. This localizes WHERE in time
the +27% bug accumulates.
"""
import os, sys, pickle
import numpy as np

# Load MC pickles for HS_Only bug_fix seed 0 (only single seed needed for trace)
MC_DIR = 'Code/HA-Models/FromPandemicCode/welfare6_BUG043_bugfix_HS_seed0'
SCEN = ['recessionUI', 'recession', 'base']

print("=== Loading MC pickles ===")
mc = {}
for sc in SCEN:
    with open(f'{MC_DIR}/{sc}.pkl', 'rb') as f:
        d = pickle.load(f)
    mc[sc] = {
        'cLvl': np.asarray(d['cLvl_all_splurge']),  # (T, N)
        'AggCons': np.asarray(d['AggCons']),
        'AggIncome': np.asarray(d['AggIncome']),
        'CRRA': float(d['CRRA']),
        'Rfree': float(d['Rfree']),
    }
    print(f"  {sc}: cLvl shape={mc[sc]['cLvl'].shape}, CRRA={mc[sc]['CRRA']}")

T, N = mc['recessionUI']['cLvl'].shape
rho = mc['recessionUI']['CRRA']
print(f"\nT={T}, N={N}, rho={rho}")

# Per-period MC welfare numerator (level)
print("\n=== MC per-period welfare numerator (level) ===")
W_mc = np.zeros(T)
for t in range(T):
    c_p = np.maximum(mc['recessionUI']['cLvl'][t], 1e-12)
    c_n = np.maximum(mc['recession']['cLvl'][t], 1e-12)
    c_b = np.maximum(mc['base']['cLvl'][t], 1e-12)
    # CRRA: u(c) = c^(1-rho)/(1-rho); u'(c) = c^(-rho); 1/u'(c) = c^rho
    if abs(rho - 1.0) < 1e-12:
        u_diff = np.log(c_p) - np.log(c_n)
    else:
        u_diff = (c_p**(1-rho) - c_n**(1-rho)) / (1-rho)
    mu_inv = c_b**rho
    W_mc[t] = float(np.sum(u_diff * mu_inv))

print(f"{'t':>3} {'W_MC_per_period':>15}  {'cumulative':>12}")
cum = 0.0
for t in range(min(15, T)):
    cum += W_mc[t]
    print(f"{t:>3} {W_mc[t]:>15.4e}  {cum:>12.4e}")

print(f"\nNPV(W_mc) at R=1.01: {sum(W_mc[t]/1.01**t for t in range(T)):.4e}")

# Load my 5D's per-period welfare numerator (from latest run)
print("\n=== Compare to my 5D per-period sum ===")
print("5D per-period (HS_Only A=20 dur-weighted, sum_w_num across durations):")

# These are from the latest 5D run output (newborn V2 + all fixes)
durations_w = [
    (1, 0.1667, 451.5),
    (2, 0.1389, 2956),
    (3, 0.1157, 5814),
    (4, 0.0965, 7484),
    (5, 0.0804, 9011),
    (6, 0.0670, 10500),
    (7, 0.0558, 11790),
    (8, 0.0465, 13220),
    (9, 0.0388, 14650),
    (10, 0.0323, 16080),
    (11, 0.1615, 17510),
]
# These are per-duration sum across periods, not per-period
print("  (per-duration sum_w_num - need per-period series for true comparison)")
print()
print(f"NPV(W_5D) was 8161 (from postpLvl run); NPV(W_MC) above = {sum(W_mc[t]/1.01**t for t in range(T)):.4e}")
ratio = 8161 / sum(W_mc[t]/1.01**t for t in range(T))
print(f"\nRatio W_5D / W_MC = {ratio:.3f}")
