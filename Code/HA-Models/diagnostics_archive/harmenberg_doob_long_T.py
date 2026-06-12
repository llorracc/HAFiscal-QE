"""
Diagnostic: HS β=0.9905 with EXTENDED T_sim to test the finite-time
vs infinite-time hypothesis for the Doob over-prediction.

If MC E_Q[a] climbs from ~9.40 (T_sim=350) toward Doob's 13.99 as
T_sim grows → confirms the hypothesis.

T_sim values: 350 (baseline), 1000, 2000, 4000.
N_MC=200k throughout (already shown to converge at this N).
"""
import os
import sys
import time
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['harmenberg_doob_long_T']

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
    print("HS β=0.9905 — T_sim sweep (test finite-time vs ∞-time hypothesis)")
    print("=" * 78)
    ctx = setup_context('Baseline')
    DFD_HS = ctx['DiscFacDstns'][1]
    beta = float(DFD_HS.atoms[0][6])  # β6 = 0.9905
    print(f"β={beta:.6f}")

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
    print(f"  TM-Q E_Q[a]  = {E_a_TM_Q:.4f}")
    print(f"  Doob E_Q[a] = {E_a_doob:.4f}")

    print("\nMC sweep over T_sim (N=200k, seed=30000):")
    print(f"  {'T_sim':>6}  {'E_Q[a]':>10}  {'E_P[a]':>10}  {'E_P[p]':>10}  {'p_max':>10}  {'a_max':>10}  {'time':>8}")
    for T_sim in [350, 1000, 2000, 4000]:
        capture_T = T_sim - 50
        t0 = time.time()
        aNrm_arr, j_arr, pLvl_arr = run_mc_capture_aj(
            agent, 200_000, seed=30000, T_sim=T_sim, capture_T=capture_T)
        t = time.time() - t0
        E_a_MC = float(np.average(aNrm_arr, weights=pLvl_arr))
        E_a_P = float(aNrm_arr.mean())
        E_p = float(pLvl_arr.mean())
        print(f"  {T_sim:>6}  {E_a_MC:>10.4f}  {E_a_P:>10.4f}  {E_p:>10.4f}  {pLvl_arr.max():>10.2f}  {aNrm_arr.max():>10.2f}  {t:>6.1f}s")


if __name__ == "__main__":
    main()
