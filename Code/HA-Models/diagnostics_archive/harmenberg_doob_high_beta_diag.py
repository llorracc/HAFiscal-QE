"""
Diagnostic: HS β=0.9905 alone at N=1M and N=4M (with multiple seeds), vs
Doob and TM-Q. Tests whether MC undersampling at the high-asset tail is
the source of the +48% Doob 'bias' at β=0.99.

If MC E_Q[a] grows substantially with N → MC was undersampling, and Doob's
13.95 prediction may be closer to truth than the N=200k MC's 9.40.
If MC E_Q[a] stays at 9.4 → Doob is really overcorrecting.
"""
import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['harmenberg_doob_high_beta_diag']

from harmenberg_doob_tier1 import (
    setup_context, build_agent_for, run_mc_capture_aj
)
from tm_methods import (
    build_tm_agg_fiscal_a,
    find_ergodic_distribution,
    compute_doob_pi_q_a,
)


def main():
    print("=" * 78)
    print("HS β=0.9905 — MC sample-size sweep")
    print("=" * 78)
    ctx = setup_context('Baseline')
    DFD_HS = ctx['DiscFacDstns'][1]
    beta_target = 0.9905
    # Find the closest atom
    idx = int(np.argmin(np.abs(DFD_HS.atoms[0] - beta_target)))
    beta = float(DFD_HS.atoms[0][idx])
    print(f"Using β={beta:.6f} (atom {idx})")

    agent = build_agent_for(1, beta, ctx)
    tm_data_P = build_tm_agg_fiscal_a(agent, aCount=500, aMax=5000, aFac=3,
                                       neutral_measure=False, interpretation='CDC')
    pi_P = find_ergodic_distribution(tm_data_P['TranMatrix'])
    tm_data_Q = build_tm_agg_fiscal_a(agent, aCount=500, aMax=5000, aFac=3,
                                       neutral_measure=True, interpretation='CDC')
    pi_Q_TM = find_ergodic_distribution(tm_data_Q['TranMatrix'])
    doob_out = compute_doob_pi_q_a(agent, tm_data_P, pi_P, interpretation='CDC')
    pi_Q_doob = doob_out['pi_Q_doob']
    dist_aGrid = tm_data_P['dist_aGrid']
    J = pi_P.shape[0] // len(dist_aGrid)
    A = len(dist_aGrid)
    E_a_TM_Q = float(np.sum(pi_Q_TM.reshape(J, A) * dist_aGrid[None, :]))
    E_a_doob = float(np.sum(pi_Q_doob.reshape(J, A) * dist_aGrid[None, :]))
    print(f"\nTM (A=500, aMax=5000):")
    print(f"  TM-Q E_Q[a] = {E_a_TM_Q:.4f}")
    print(f"  Doob E_Q[a] = {E_a_doob:.4f}")

    # MC sweep with multiple sample sizes / seeds
    print("\nMC sweep:")
    print(f"  {'N':>10}  {'seed':>6}  {'E_Q[a]':>10}  {'p_max':>10}  {'a_max':>10}")
    for N in [200_000, 500_000, 1_000_000]:
        for seed_offset in [0, 1, 2]:
            t0 = time.time()
            aNrm_arr, j_arr, pLvl_arr = run_mc_capture_aj(
                agent, N, seed=30000 + seed_offset, T_sim=400, capture_T=350)
            E_a_MC = float(np.average(aNrm_arr, weights=pLvl_arr))
            t = time.time() - t0
            print(f"  {N:>10}  {seed_offset:>6}  {E_a_MC:>10.4f}  {pLvl_arr.max():>10.2f}  {aNrm_arr.max():>10.2f}  ({t:.1f}s)")


if __name__ == "__main__":
    main()
