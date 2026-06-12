"""
Compare empirical joint Markov transition kernel vs my analytical predictions.

For each source cell (j_p, j_b) at t=0, count empirical transitions to (k_p, k_b)
at t=1. Then compute analytical predictions using:
  - "Shared-draw" formula: integral overlap of CDFs
  - "Independent" formula: marg_pol(k_p|j_p) * marg_base(k_b|j_b)

Whichever matches better tells us the correct CRN model.
"""
import pickle, numpy as np

MC_DIR = 'Code/HA-Models/FromPandemicCode/welfare6_BUG043_bugfix_HS_seed0'

with open(f'{MC_DIR}/recessionUI.pkl', 'rb') as f:
    d_pol = pickle.load(f)
with open(f'{MC_DIR}/base.pkl', 'rb') as f:
    d_base = pickle.load(f)

J = 6
Mp = np.asarray(d_pol['Mrkv_hist_bs'])
Mb = np.asarray(d_base['Mrkv_hist_bs'])
T, N = Mp.shape

jp = (Mp.astype(int) % J)
jb = (Mb.astype(int) % J)
Mp_macro = (Mp.astype(int) // J)
Mb_macro = (Mb.astype(int) // J)

print(f"Macro at t=0: pol={np.unique(Mp_macro[0])}, base={np.unique(Mb_macro[0])}")
print(f"Macro at t=1: pol={np.unique(Mp_macro[1])}, base={np.unique(Mb_macro[1])}")

# For source (j_p, j_b) at t=0, find empirical transitions to (k_p, k_b) at t=1
# Focus on the cell that drives the over-counting: source (u2Q, emp) = (2, 0)
print("\n=== Source (j_p=2 u2Q, j_b=0 emp) at t=0 → empirical transitions at t=1 ===")
src_idx = np.where((jp[0] == 2) & (jb[0] == 0))[0]
print(f"  Source mass: {len(src_idx)/N*100:.3f}% ({len(src_idx)} agents)")

if len(src_idx) > 0:
    print(f"  Empirical transition kernel:")
    hdr = 'kp/kb'
    print(f"  {hdr:>5}", end='')
    for k in range(J):
        print(f"  {k:>8d}", end='')
    print()
    trans_emp = np.zeros((J, J))
    for kp in range(J):
        for kb in range(J):
            cnt = int(np.sum((jp[1, src_idx] == kp) & (jb[1, src_idx] == kb)))
            trans_emp[kp, kb] = cnt / len(src_idx)
    for kp in range(J):
        print(f"  {kp:>5d}", end='')
        for kb in range(J):
            print(f"  {trans_emp[kp,kb]*100:>7.3f}%", end='')
        print()

    # Marginal pol from this source
    marg_p_from_src = np.array([np.sum(jp[1, src_idx] == kp) / len(src_idx) for kp in range(J)])
    marg_b_from_src = np.array([np.sum(jb[1, src_idx] == kb) / len(src_idx) for kb in range(J)])
    print(f"  Marginal-pol from src: {(marg_p_from_src*100).round(2)}")
    print(f"  Marginal-base from src: {(marg_b_from_src*100).round(2)}")

    print(f"\n  Independent prediction (outer product):")
    indep_pred = np.outer(marg_p_from_src, marg_b_from_src)
    for kp in range(J):
        print(f"  {kp:>5d}", end='')
        for kb in range(J):
            print(f"  {indep_pred[kp,kb]*100:>7.3f}%", end='')
        print()

    print(f"\n  Diff (empirical - independent):")
    for kp in range(J):
        print(f"  {kp:>5d}", end='')
        for kb in range(J):
            print(f"  {(trans_emp[kp,kb] - indep_pred[kp,kb])*100:>+7.3f}%", end='')
        print()

# Now also check source (emp, emp) = (0, 0) — by far the largest source
print("\n=== Source (j_p=0 emp, j_b=0 emp) at t=0 → empirical transitions at t=1 ===")
src_idx = np.where((jp[0] == 0) & (jb[0] == 0))[0]
print(f"  Source mass: {len(src_idx)/N*100:.3f}% ({len(src_idx)} agents)")

if len(src_idx) > 0:
    trans_emp = np.zeros((J, J))
    for kp in range(J):
        for kb in range(J):
            cnt = int(np.sum((jp[1, src_idx] == kp) & (jb[1, src_idx] == kb)))
            trans_emp[kp, kb] = cnt / len(src_idx)
    print(f"  Empirical transition kernel:")
    print(f"  {'kp/kb':>5}", end='')
    for k in range(J):
        print(f"  {k:>8d}", end='')
    print()
    for kp in range(J):
        print(f"  {kp:>5d}", end='')
        for kb in range(J):
            print(f"  {trans_emp[kp,kb]*100:>7.3f}%", end='')
        print()

    marg_p_from_src = np.array([np.sum(jp[1, src_idx] == kp) / len(src_idx) for kp in range(J)])
    marg_b_from_src = np.array([np.sum(jb[1, src_idx] == kb) / len(src_idx) for kb in range(J)])
    indep_pred = np.outer(marg_p_from_src, marg_b_from_src)
    print(f"\n  Independent (outer prod):")
    for kp in range(J):
        print(f"  {kp:>5d}", end='')
        for kb in range(J):
            print(f"  {indep_pred[kp,kb]*100:>7.3f}%", end='')
        print()

    print(f"\n  Diff (empirical - independent):")
    for kp in range(J):
        print(f"  {kp:>5d}", end='')
        for kb in range(J):
            print(f"  {(trans_emp[kp,kb] - indep_pred[kp,kb])*100:>+7.3f}%", end='')
        print()
