"""
Definitive test: is MC's joint distribution closer to SHARED-DRAW or INDEPENDENT?

Compare 3 joint distributions at the same time point t:
1. MC empirical: count joint (j_pol, j_base) over agents
2. Shared-draw analytical: integrate min/max overlap of CDFs at each source
3. Independent analytical: marginal_pol × marginal_base

If MC ≈ independent, my joint Markov "shared-draw overlap" formula is wrong.
If MC ≈ shared-draw, the bug is elsewhere (e.g., spike implementation).
"""
import pickle, numpy as np

MC_DIR = 'Code/HA-Models/FromPandemicCode/welfare6_BUG043_bugfix_HS_seed0'

# Load Mrkv histories from MC pickles
with open(f'{MC_DIR}/recessionUI.pkl', 'rb') as f:
    d_pol = pickle.load(f)
with open(f'{MC_DIR}/recession.pkl', 'rb') as f:
    d_none = pickle.load(f)
with open(f'{MC_DIR}/base.pkl', 'rb') as f:
    d_base = pickle.load(f)

# Mrkv shape (T, N) — combined macro × J + micro
Mp = np.asarray(d_pol['Mrkv_hist_bs'])
Mn = np.asarray(d_none['Mrkv_hist_bs'])
Mb = np.asarray(d_base['Mrkv_hist_bs'])

J = 6  # bug_fix encoding: e, u1Q, u2Q, u3Q, u4Q, noBen
T, N = Mp.shape
print(f"=== MC histories ===")
print(f"T={T}, N={N}, J={J}")

# Extract micro state (j) from combined Mrkv
jp = (Mp.astype(int) % J)
jn = (Mn.astype(int) % J)
jb = (Mb.astype(int) % J)

# Extract macro state
Mp_macro = (Mp.astype(int) // J)
Mn_macro = (Mn.astype(int) // J)
Mb_macro = (Mb.astype(int) // J)

print(f"\nMacro state at t=0: pol={np.unique(Mp_macro[0])}, none={np.unique(Mn_macro[0])}, base={np.unique(Mb_macro[0])}")
print(f"Macro state at t=1: pol={np.unique(Mp_macro[1])}, none={np.unique(Mn_macro[1])}, base={np.unique(Mb_macro[1])}")

# Joint distribution check at t=1
print("\n=== Joint MC empirical (j_pol, j_base) at t=1 ===")
hdr = 'jp/jb'
print(f"{hdr:>5}", end='')
for k in range(J):
    print(f"  {k:>8d}", end='')
print(f"  {'marg_p':>8}")
for kp in range(J):
    print(f"{kp:>5d}", end='')
    for kb in range(J):
        cnt = float(np.sum((jp[1] == kp) & (jb[1] == kb))) / N
        print(f"  {cnt*100:>7.3f}%", end='')
    margp = float(np.sum(jp[1] == kp)) / N
    print(f"  {margp*100:>7.3f}%")
print(f"{'marg_b':>5}", end='')
for kb in range(J):
    margb = float(np.sum(jb[1] == kb)) / N
    print(f"  {margb*100:>7.3f}%", end='')
print()

# Independent prediction
print("\n=== Independent prediction: marg_p × marg_b at t=1 ===")
margp_arr = np.array([float(np.sum(jp[1] == k)) / N for k in range(J)])
margb_arr = np.array([float(np.sum(jb[1] == k)) / N for k in range(J)])
joint_indep = np.outer(margp_arr, margb_arr)
print(f"{hdr:>5}", end='')
for k in range(J):
    print(f"  {k:>8d}", end='')
print()
for kp in range(J):
    print(f"{kp:>5d}", end='')
    for kb in range(J):
        print(f"  {joint_indep[kp,kb]*100:>7.3f}%", end='')
    print()

# Difference
print("\n=== Difference: MC empirical - Independent ===")
print(f"{hdr:>5}", end='')
for k in range(J):
    print(f"  {k:>8d}", end='')
print()
for kp in range(J):
    print(f"{kp:>5d}", end='')
    for kb in range(J):
        emp = float(np.sum((jp[1] == kp) & (jb[1] == kb))) / N
        diff = emp - joint_indep[kp, kb]
        print(f"  {diff*100:>+7.3f}%", end='')
    print()

# Now test: shared-draw overlap from t=0 source
print("\n=== Shared-draw analytical from t=0 source distribution ===")
# t=0 source joint (jp[0], jb[0]) — should be diagonal if RNG fully shared
src_joint = np.zeros((J, J))
for kp in range(J):
    for kb in range(J):
        src_joint[kp, kb] = float(np.sum((jp[0] == kp) & (jb[0] == kb))) / N
print(f"t=0 source joint (jp, jb):")
print(f"{hdr:>5}", end='')
for k in range(J):
    print(f"  {k:>8d}", end='')
print()
for kp in range(J):
    print(f"{kp:>5d}", end='')
    for kb in range(J):
        print(f"  {src_joint[kp,kb]*100:>7.3f}%", end='')
    print()

# Diagonal mass at t=0
diag_t0 = sum(src_joint[k, k] for k in range(J))
print(f"\nDiagonal mass at t=0: {diag_t0*100:.2f}%")
print(f"Off-diagonal mass at t=0: {(1-diag_t0)*100:.2f}%")
