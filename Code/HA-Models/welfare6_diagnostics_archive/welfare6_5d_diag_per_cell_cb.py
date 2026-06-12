"""
DIRECT per-cell c_b comparison: MC empirical vs 5D analytical.

For each MIXED cell of interest at a given time t, compute:
  - Mean c_b: consumption of agent in base scenario, conditional on being at
    (j_pn, j_b) in joint (pol, base) state
  - Mean (c_p - c_n): consumption difference in pol vs none
  - Welfare contribution: mass × (u(c_p) - u(c_n)) × c_b^rho per cell

Output:
  1. MC empirical per-cell (mass, mean_cb, mean_c_p, mean_c_n)
  2. Same for 5D
  3. Ratio: 5D / MC for each cell's welfare contribution

This DIRECTLY tests the hypothesis that 5D's c_b at MIXED cells is too high.
"""
import pickle, os, sys
import numpy as np

MC_DIR = 'Code/HA-Models/FromPandemicCode/welfare6_BUG043_bugfix_HS_seed0'

print("=== Loading MC pickles ===")
with open(f'{MC_DIR}/recessionUI.pkl', 'rb') as f:
    d_pol = pickle.load(f)
with open(f'{MC_DIR}/recession.pkl', 'rb') as f:
    d_none = pickle.load(f)
with open(f'{MC_DIR}/base.pkl', 'rb') as f:
    d_base = pickle.load(f)

J = 6
Mp = np.asarray(d_pol['Mrkv_hist_bs']).astype(int)
Mn = np.asarray(d_none['Mrkv_hist_bs']).astype(int)
Mb = np.asarray(d_base['Mrkv_hist_bs']).astype(int)

cLvl_p = np.asarray(d_pol['cLvl_all_splurge'])  # (T, N)
cLvl_n = np.asarray(d_none['cLvl_all_splurge'])
cLvl_b = np.asarray(d_base['cLvl_all_splurge'])

pLvl_p = np.asarray(d_pol['pLvl_all_bs'])
pLvl_n = np.asarray(d_none['pLvl_all_bs'])
pLvl_b = np.asarray(d_base['pLvl_all_bs'])

rho = float(d_pol['CRRA'])
Rfree = float(d_pol['Rfree'])

T, N = Mp.shape
jp = Mp % J  # pol micro state
jn = Mn % J  # none micro state
jb = Mb % J  # base micro state

print(f"T={T}, N={N}, rho={rho}")
print(f"Macro path pol: t=0..7 = {[int((Mp[t,0] // J)) for t in range(min(8, T))]}")

# Focus on time periods 0-7 where most welfare happens
# For each (j_p, j_b) cell, compute per-cell statistics
def cell_stats(t, jp_target, jb_target):
    mask = (jp[t] == jp_target) & (jb[t] == jb_target)
    n_in_cell = int(mask.sum())
    if n_in_cell == 0:
        return None
    cp = cLvl_p[t, mask]
    cn = cLvl_n[t, mask]
    cb = cLvl_b[t, mask]
    pb = pLvl_b[t, mask]
    cb_clipped = np.maximum(cb, 1e-12)
    cp_clipped = np.maximum(cp, 1e-12)
    cn_clipped = np.maximum(cn, 1e-12)

    # Per-cell welfare integrand
    if abs(rho - 1.0) < 1e-12:
        u_diff = np.log(cp_clipped) - np.log(cn_clipped)
    else:
        u_diff = (cp_clipped**(1-rho) - cn_clipped**(1-rho)) / (1-rho)
    mu_inv_b = cb_clipped**rho
    welfare_per_agent = u_diff * mu_inv_b

    return {
        'mass_pct': n_in_cell / N * 100,
        'n': n_in_cell,
        'mean_cp': float(cp.mean()),
        'mean_cn': float(cn.mean()),
        'mean_cb': float(cb.mean()),
        'mean_pb': float(pb.mean()),
        'cp_minus_cn': float((cp - cn).mean()),
        'mean_welfare': float(welfare_per_agent.mean()),
        'sum_welfare': float(welfare_per_agent.sum()),
    }

# Print stats for cells of interest at multiple times
cells_of_interest = [
    (0, 0, 'diag emp'),
    (1, 1, 'diag u1Q'),
    (2, 2, 'diag u2Q'),
    (3, 3, 'diag u3Q'),
    (2, 0, 'MIXED u2Q-pol, emp-base'),
    (3, 0, 'MIXED u3Q-pol, emp-base'),
    (4, 0, 'MIXED u4Q-pol, emp-base'),
    (5, 0, 'MIXED noBen-pol, emp-base'),
]

for t in [0, 1, 2, 3, 5, 7]:
    print(f"\n========= t={t} (macro_pol={int(Mp[t,0] // J)}, macro_base={int(Mb[t,0] // J)}) =========")
    print(f"{'cell':<35} {'mass%':>8} {'mean_cp':>9} {'mean_cn':>9} {'mean_cb':>9} {'mean_dW':>10} {'sum_W':>10}")
    for jp_t, jb_t, name in cells_of_interest:
        label = f"({jp_t},{jb_t}) {name}"
        s = cell_stats(t, jp_t, jb_t)
        if s is None:
            print(f"{label:<35} {'(0)':>8}")
        else:
            print(f"{label:<35} {s['mass_pct']:>8.3f} {s['mean_cp']:>9.4f} {s['mean_cn']:>9.4f} {s['mean_cb']:>9.4f} {s['mean_welfare']:>10.4f} {s['sum_welfare']:>10.2e}")
