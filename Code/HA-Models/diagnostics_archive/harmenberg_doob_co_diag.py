"""
Diagnostic for CO β=0.988 atom (the +11% Doob residual in v5 cascade-gate).

Two tests in one:
  (a) Wide-grid Doob: A=500/aMax=5000 vs default A=200/aMax=500, to confirm
      Doob has converged and the residual is NOT a grid-coverage issue.
  (b) Long-T_sim MC: T_sim ∈ {350, 1000, 2000, 4000}, to confirm MC at
      finite T_sim is the under-counter (climbs toward Doob as T_sim grows).
"""
import os
import sys
import time
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['harmenberg_doob_co_diag']

from harmenberg_doob_tier1 import (
    setup_context, build_agent_for, run_mc_capture_aj
)
from tm_methods import (
    build_tm_agg_fiscal_a,
    find_ergodic_distribution,
    compute_doob_pi_q_a,
)


def doob_E_a(agent, aCount, aMax):
    tm_data_P = build_tm_agg_fiscal_a(
        agent, aCount=aCount, aMax=aMax, aFac=3,
        neutral_measure=False, interpretation='CDC')
    pi_P = find_ergodic_distribution(tm_data_P['TranMatrix'])
    out = compute_doob_pi_q_a(agent, tm_data_P, pi_P, interpretation='CDC')
    pi_Q = out['pi_Q_doob']
    dist_aGrid = tm_data_P['dist_aGrid']
    J = pi_P.shape[0] // len(dist_aGrid)
    A = len(dist_aGrid)
    return float(np.sum(pi_Q.reshape(J, A) * dist_aGrid[None, :]))


def main():
    print("=" * 78)
    print("CO β=0.988 — wide-grid Doob + long-T_sim MC")
    print("=" * 78)
    ctx = setup_context('Baseline')
    DFD_CO = ctx['DiscFacDstns'][2]
    # CO atom 5 = β=0.988 (the un-clipped slow-mixing atom)
    beta = float(DFD_CO.atoms[0][5])
    print(f"β={beta:.6f}\n")

    agent = build_agent_for(2, beta, ctx)

    # (a) Wide-grid Doob test
    print("--- (a) Doob grid-convergence ---")
    for aCount, aMax in [(200, 500), (500, 5000), (1000, 20000)]:
        t0 = time.time()
        E_a = doob_E_a(agent, aCount, aMax)
        print(f"  A={aCount:5d}, aMax={aMax:6d}: Doob E_Q[a] = {E_a:.4f}  ({time.time()-t0:.1f}s)")

    # (b) Long-T_sim MC test (uses default grid)
    print("\n--- (b) MC convergence as T_sim grows (N=200k, default grid) ---")
    print(f"  {'T_sim':>6}  {'E_Q[a]':>10}  {'p_max':>10}  {'a_max':>10}  {'time':>8}")
    for T_sim in [350, 1000, 2000, 4000]:
        capture_T = T_sim - 50
        t0 = time.time()
        aNrm_arr, j_arr, pLvl_arr = run_mc_capture_aj(
            agent, 200_000, seed=30000, T_sim=T_sim, capture_T=capture_T)
        t = time.time() - t0
        E_a_MC = float(np.average(aNrm_arr, weights=pLvl_arr))
        print(f"  {T_sim:>6}  {E_a_MC:>10.4f}  {pLvl_arr.max():>10.2f}  {aNrm_arr.max():>10.2f}  {t:>6.1f}s")


if __name__ == "__main__":
    main()
