"""
Compare 5D's pLvl_factor evolution vs MC's mean(pLvl) per period.

If 5D's pLvl_factor[t] grows more than MC's mean(pLvl[t]) / mean(pLvl[0]),
the welfare scaling = w_num × E_pLvl × pLvl_factor over-amplifies welfare.
"""
import pickle, numpy as np

MC_DIR = 'Code/HA-Models/FromPandemicCode/welfare6_BUG043_bugfix_HS_seed0'

with open(f'{MC_DIR}/recessionUI.pkl', 'rb') as f:
    d_pol = pickle.load(f)
with open(f'{MC_DIR}/base.pkl', 'rb') as f:
    d_base = pickle.load(f)

pLvl_pol = np.asarray(d_pol['pLvl_all_bs'])  # (T, N)
pLvl_base = np.asarray(d_base['pLvl_all_bs'])

T, N = pLvl_pol.shape
print(f"=== MC pLvl: T={T}, N={N} ===")

print(f"\n{'t':>3} {'mean(pLvl_pol)':>15} {'mean(pLvl_base)':>15} "
      f"{'ratio':>8} {'cum_ratio':>10}")
mean_pLvl_pol = pLvl_pol.mean(axis=1)
mean_pLvl_base = pLvl_base.mean(axis=1)
mean_pLvl_pol_t0 = mean_pLvl_pol[0]
mean_pLvl_base_t0 = mean_pLvl_base[0]

print(f"  Initial t=0 means: pol={mean_pLvl_pol_t0:.4f}, base={mean_pLvl_base_t0:.4f}")

# pLvl_factor would track ratio of mean_pLvl[t] / mean_pLvl[0] (= base ergodic at recession start)
for t in range(0, min(15, T)):
    rt_pol = mean_pLvl_pol[t] / mean_pLvl_base_t0
    rt_base = mean_pLvl_base[t] / mean_pLvl_base_t0
    print(f"{t:>3} {mean_pLvl_pol[t]:>15.4f} {mean_pLvl_base[t]:>15.4f} "
          f"{mean_pLvl_pol[t]/mean_pLvl_base[t]:>8.4f} {rt_pol:>10.4f}")

# Now compute MC's per-period welfare numerator INCLUDING the pLvl scaling
# MC formula: W = sum_i (u(c_p_it) - u(c_n_it)) * c_b_it^rho
# This already includes per-agent pLvl info implicitly through cLvl
print("\n=== MC per-period welfare numerator (raw) ===")
with open(f'{MC_DIR}/recession.pkl', 'rb') as f:
    d_none = pickle.load(f)
cLvl_p = np.asarray(d_pol['cLvl_all_splurge'])
cLvl_n = np.asarray(d_none['cLvl_all_splurge'])
cLvl_b = np.asarray(d_base['cLvl_all_splurge'])
rho = float(d_pol['CRRA'])

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

print(f"{'t':>3} {'W_MC':>15} {'cum_W_MC':>15}")
cum = 0.0
for t in range(min(15, T)):
    cum += W_per_t[t]
    print(f"{t:>3} {W_per_t[t]:>15.4e} {cum:>15.4e}")

# Compare to 5D's per-period welfare_num (manual transcription from prior run)
# From welfare6_tm_joint5d_full.py output at A=20, post-pLvl-recurrence:
# Per-duration sums were given but not per-period series
# Going to print the t=0..7 figures from the per-period diagnostic
print("\n=== 5D per-period (multiplied by E_pLvl × pLvl_factor) ===")
print("These need to be computed from a fresh 5D run with verbose hook")
print("Per-agent values from earlier diagnostic:")
five_d_per_agent = [0.036, 0.171, 0.177, 0.113, 0.083, 0.065, 0.053, 0.044, None, None, 0.025]
mc_per_agent     = [0.107, 0.187, 0.133, 0.065, 0.041, 0.030, 0.022, 0.017, None, None, 0.008]
print(f"{'t':>3} {'5D/agent':>10} {'MC/agent':>10} {'ratio':>8}")
for t in range(11):
    if five_d_per_agent[t] is not None and mc_per_agent[t] is not None:
        ratio = five_d_per_agent[t] / mc_per_agent[t] if mc_per_agent[t] != 0 else float('nan')
        print(f"{t:>3} {five_d_per_agent[t]:>10.4f} {mc_per_agent[t]:>10.4f} {ratio:>8.4f}")
