"""
Deeper diagnostic: per-period MC vs TM-P vs TM-Q.

Question: my time-averaged MC matches TM-P, not TM-Q (opposite of Harmenberg
prediction). Is this because:
  (a) Time-averaging across drifting pLvl is biased
  (b) Single-period MC actually matches TM-Q (then time-averaging is the bug)
  (c) Per-period MC also matches TM-P (then there's a real implementation issue)

Test: 1 HS agent at N=200000, 3 seeds. Track and report:
  - Per-period mean(cNrm)              [should ≈ E_P[c]]
  - Per-period mean(cNrm·pLvl)/mean(pLvl) [should ≈ E_Q[c] by Harmenberg]
  - Time-averaged versions of the above
At each, compare to TM-P/E_pLvl and TM-Q/E_pLvl.
"""

import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['harmenberg_mc_diag']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters

# HS reference (Reduced_Run): TM-P=23.539, TM-Q=23.512, E_pLvl_TM=23.859
TM_E_PLVL_HS = 23.858585
TM_P_NORM_HS = 23.538838 / TM_E_PLVL_HS  # 0.98660 — TM's P-normalized agg consumption
TM_Q_NORM_HS = 23.512063 / TM_E_PLVL_HS  # 0.98548


def build_HS_agent():
    [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes,
     Check_changes, recession_Check_changes] = return_parameters(
        Parametrization='Reduced_Run', OutputFor='_Main.py')

    BaseType = AggFiscalType(**init_highschool)
    BaseType.cycles = 0
    BaseType.DiscFac = float(DiscFacDstns[1].atoms[0][0])

    economy = AggregateDemandEconomy(**init_ADEconomy)
    BaseType.get_economy_data(economy)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]),
                          np.array([BaseType.IncUnempNoBenefits])])

    BaseType.IncShkDstn[0].seed = 763607781
    BaseType.IncShkDstn[0].reset()
    BaseType.IncShkDstn = [
        [BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]]
    BaseType.IncShkDstn_base = BaseType.IncShkDstn

    economy.agents = [BaseType]
    economy.solve()
    return economy.agents[0]


def run_mc_diag(agent_template, N, seed, T_sim=400, T_burnin=200):
    agent = deepcopy(agent_template)
    agent.AgentCount = N
    agent.seed = seed
    agent.T_sim = T_sim
    agent.track_vars = ['cNrm', 'TranShk', 'pLvl']
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0
    agent.Cratio = 1.0
    agent.EconomyMrkvNow_hist = [0] * T_sim
    agent.simulate()

    cNrm_hist = np.asarray(agent.history['cNrm'])     # (T, N)
    TranShk_hist = np.asarray(agent.history['TranShk'])
    pLvl_hist = np.asarray(agent.history['pLvl'])
    splurge = agent.Splurge

    # Per-period quantities (post-burnin)
    cNrm_post = cNrm_hist[T_burnin:]
    TranShk_post = TranShk_hist[T_burnin:]
    pLvl_post = pLvl_hist[T_burnin:]

    # Splurge consumption: c_actual_nrm = (1-ς)·cNrm + ς·TranShk (normalized; before pLvl multiplication)
    cActualNrm_post = (1 - splurge) * cNrm_post + splurge * TranShk_post

    # Per-period:
    #   E_P[c] estimate  = cross-sectional mean of cActualNrm at each t
    #   E_Q[c] estimate  = cross-sectional mean(cActualNrm · pLvl) / mean(pLvl) at each t
    T_post = cActualNrm_post.shape[0]
    per_period_EP = np.zeros(T_post)
    per_period_EQ = np.zeros(T_post)
    for t in range(T_post):
        per_period_EP[t] = np.nanmean(cActualNrm_post[t])
        num = np.nanmean(cActualNrm_post[t] * pLvl_post[t])
        den = np.nanmean(pLvl_post[t])
        per_period_EQ[t] = num / den if den > 0 else float('nan')

    return {
        'per_period_EP': per_period_EP,  # (T_post,) cross-sec mean cNrm
        'per_period_EQ': per_period_EQ,  # (T_post,) per-pLvl ratio
        'mean_pLvl_post': float(np.nanmean(pLvl_post)),
    }


def main():
    print("=" * 78)
    print("HS MC diagnostic — per-period vs time-averaged comparison")
    print("=" * 78)
    print(f"\nReference:")
    print(f"  TM-P normalized E_P[c] = {TM_P_NORM_HS:.6f}")
    print(f"  TM-Q normalized E_Q[c] = {TM_Q_NORM_HS:.6f}")
    print(f"  TM-P > TM-Q by {(TM_P_NORM_HS-TM_Q_NORM_HS)*100:.4f}pp")
    print(f"  Doc prediction: MC ≈ TM-Q (since MC tracks joint (p,c) exactly)")

    agent = build_HS_agent()

    N = 200000
    n_seeds = 3
    T_sim = 600
    T_burnin = 300
    print(f"\nMC settings: N={N}, n_seeds={n_seeds}, T_sim={T_sim}, T_burnin={T_burnin}")

    EP_seeds = []
    EQ_seeds = []
    for s in range(n_seeds):
        t0 = time.time()
        r = run_mc_diag(agent, N, seed=20000 + s, T_sim=T_sim, T_burnin=T_burnin)
        # Per-period series; report at t-checkpoints
        ep = r['per_period_EP']
        eq = r['per_period_EQ']
        print(f"\n  seed {s}: ({time.time()-t0:.1f}s)")
        for t_check in [0, 50, 100, 150, 199, len(ep)-1]:
            if t_check < len(ep):
                print(f"    t_post={t_check:3d}: E_P[c]_emp={ep[t_check]:.6f}  "
                      f"E_Q[c]_emp={eq[t_check]:.6f}")
        EP_seeds.append(ep.mean())
        EQ_seeds.append(eq.mean())
        print(f"    time-avg over T_post={len(ep)}: "
              f"E_P[c]_emp_mean={ep.mean():.6f}  E_Q[c]_emp_mean={eq.mean():.6f}")

    EP_mean = float(np.mean(EP_seeds))
    EP_se = float(np.std(EP_seeds, ddof=1) / np.sqrt(n_seeds))
    EQ_mean = float(np.mean(EQ_seeds))
    EQ_se = float(np.std(EQ_seeds, ddof=1) / np.sqrt(n_seeds))

    print("\n" + "=" * 78)
    print("Summary across seeds (time-averaged):")
    print(f"  E_P[c] empirical (mean ± SE): {EP_mean:.6f} ± {EP_se:.6f}")
    print(f"  E_Q[c] empirical (mean ± SE): {EQ_mean:.6f} ± {EQ_se:.6f}")
    print(f"  TM-P normalized:              {TM_P_NORM_HS:.6f}")
    print(f"  TM-Q normalized:              {TM_Q_NORM_HS:.6f}")

    diff_EP_TMP = EP_mean - TM_P_NORM_HS
    diff_EP_TMQ = EP_mean - TM_Q_NORM_HS
    diff_EQ_TMP = EQ_mean - TM_P_NORM_HS
    diff_EQ_TMQ = EQ_mean - TM_Q_NORM_HS

    print(f"\n  MC E_P[c] − TM-P = {diff_EP_TMP:+.6f}  ({diff_EP_TMP/EP_se:+.1f}σ MC SE)")
    print(f"  MC E_P[c] − TM-Q = {diff_EP_TMQ:+.6f}  ({diff_EP_TMQ/EP_se:+.1f}σ MC SE)")
    print(f"  MC E_Q[c] − TM-P = {diff_EQ_TMP:+.6f}  ({diff_EQ_TMP/EQ_se:+.1f}σ MC SE)")
    print(f"  MC E_Q[c] − TM-Q = {diff_EQ_TMQ:+.6f}  ({diff_EQ_TMQ/EQ_se:+.1f}σ MC SE)")

    print("\n  Verdict:")
    if abs(diff_EP_TMP) < 2*EP_se and abs(diff_EQ_TMQ) < 2*EQ_se:
        print("    ✓ MC E_P[c] ≈ TM-P AND MC E_Q[c] ≈ TM-Q. Harmenberg identity holds.")
    elif abs(diff_EP_TMP) < 2*EP_se:
        print(f"    ~ MC E_P[c] ≈ TM-P. But MC E_Q[c] ≠ TM-Q ({diff_EQ_TMQ/EQ_se:+.1f}σ).")
        print(f"      This means the Q-marginal in TM is NOT the empirical Q-marginal.")
    elif abs(diff_EQ_TMQ) < 2*EQ_se:
        print(f"    ~ MC E_Q[c] ≈ TM-Q. But MC E_P[c] ≠ TM-P ({diff_EP_TMP/EP_se:+.1f}σ).")
    else:
        print(f"    ! Neither matches; the implementation has a bigger issue.")


if __name__ == "__main__":
    main()
