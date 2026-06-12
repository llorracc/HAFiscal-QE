"""
MC vs TM-P vs TM-Q comparison for 1-agent baseline.

Confirms the analytical claim of math-derive-harm §14.5:
  - MC tracks (p_i, m_i, j_i) jointly per agent → exact aggregate (modulo MC noise)
  - TM-Q is exact by neutral-measure construction
  - TM-P has a systematic upward bias of −N·Cov_P(p, c(m,j))

Test: build 1 agent (CO cohort, β=0.984; high β so the bias is largest),
run MC at N=100k for several seeds, compute level AggCons including
splurge (1-ς)·cNrm·pLvl + ς·TranShk·pLvl. Compare to TM-P and TM-Q
already measured by harmenberg_grid_sweep.py:
  CO TM-P: 34.829104
  CO TM-Q: 34.690189
  rel diff: 0.40%

Prediction: MC ≈ TM-Q (within MC SE), and TM-P > MC by ~0.4%.

For HS (β=0.93): TM-P=23.539, TM-Q=23.512, predicted bias 0.114%.
For DO (β=0.70): TM-P=10.577, TM-Q=10.574, predicted bias 0.025%.

Cost: ~10-30 sec per seed at N=100k for 1 agent. ~5 seeds × 3 cohorts ≈ 5 min.
"""

import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['harmenberg_mc_vs_tm']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters

# Reference values from harmenberg_grid_sweep.py (current calibration ς=0.2571):
TM_REFERENCE = {
    'DO': {'TM_P': 10.576912, 'TM_Q': 10.574294, 'beta': 0.6995},
    'HS': {'TM_P': 23.538838, 'TM_Q': 23.512063, 'beta': 0.9302},
    'CO': {'TM_P': 34.829104, 'TM_Q': 34.690189, 'beta': 0.9835},
}


def build_agent(cohort_idx):
    [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes,
     Check_changes, recession_Check_changes] = return_parameters(
        Parametrization='Reduced_Run', OutputFor='_Main.py')

    inits = [init_dropout, init_highschool, init_college]
    init = inits[cohort_idx]

    BaseType = AggFiscalType(**init)
    BaseType.cycles = 0
    BaseType.DiscFac = float(DiscFacDstns[cohort_idx].atoms[0][0])

    economy = AggregateDemandEconomy(**init_ADEconomy)
    BaseType.get_economy_data(economy)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]),
                          np.array([BaseType.IncUnempNoBenefits])])

    BaseType.IncShkDstn[0].seed = 763607780 + cohort_idx
    BaseType.IncShkDstn[0].reset()
    BaseType.IncShkDstn = [
        [BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]]
    BaseType.IncShkDstn_base = BaseType.IncShkDstn

    economy.agents = [BaseType]
    economy.solve()
    return economy.agents[0], BaseType.Splurge


def run_mc_one_seed(agent_template, N, seed, T_sim=400, T_burnin=200):
    """Run MC at given N, seed; return AggCons_level (post-burnin mean)."""
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

    burnin_idx = T_burnin if T_burnin < T_sim else T_sim // 2
    cNrm_post = agent.history['cNrm'][burnin_idx:]      # (T-burnin, N)
    TranShk_post = agent.history['TranShk'][burnin_idx:] # (T-burnin, N)
    pLvl_post = agent.history['pLvl'][burnin_idx:]       # (T-burnin, N)

    # Splurge consumption per agent per period:
    # c_actual_lvl = (1-ς)·cNrm·pLvl + ς·TranShk·pLvl
    splurge = agent.Splurge
    c_actual_lvl = (1 - splurge) * cNrm_post * pLvl_post + splurge * TranShk_post * pLvl_post

    # Cross-sectional + time mean of LEVEL consumption
    AggCons_per_capita_lvl = float(np.nanmean(c_actual_lvl))
    # Mean pLvl over same window (for normalization to compare with TM at t=0)
    mean_pLvl = float(np.nanmean(pLvl_post))
    # Normalized: AggCons_lvl / mean_pLvl — apples-to-apples with TM at t=0
    # (where TM's pLvl_factor=1 and E[pLvl]_analytical is the per-cap p-scale)
    AggCons_per_pLvl = AggCons_per_capita_lvl / mean_pLvl

    return {
        'AggCons_lvl': AggCons_per_capita_lvl,
        'mean_pLvl': mean_pLvl,
        'AggCons_per_pLvl': AggCons_per_pLvl,
    }


def compare_cohort(cohort_label, cohort_idx, N, n_seeds, T_sim, T_burnin):
    print(f"\n--- {cohort_label} (β={TM_REFERENCE[cohort_label]['beta']}) ---")
    agent, splurge = build_agent(cohort_idx)
    print(f"  Splurge ς = {splurge:.4f}")
    print(f"  Running MC at N={N}, T_sim={T_sim}, T_burnin={T_burnin}, n_seeds={n_seeds}...")

    # Collect both LEVEL and PER-pLvl estimates per seed
    mc_lvl = []
    mc_per_plvl = []
    mc_plvl = []
    for s in range(n_seeds):
        t0 = time.time()
        r = run_mc_one_seed(agent, N, seed=10000 + s, T_sim=T_sim, T_burnin=T_burnin)
        mc_lvl.append(r['AggCons_lvl'])
        mc_per_plvl.append(r['AggCons_per_pLvl'])
        mc_plvl.append(r['mean_pLvl'])
        print(f"    seed {s}: AggCons_lvl={r['AggCons_lvl']:.4f}  "
              f"mean_pLvl={r['mean_pLvl']:.4f}  "
              f"AggCons/pLvl={r['AggCons_per_pLvl']:.4f}  "
              f"({time.time()-t0:.1f}s)")

    mc_lvl_mean = float(np.mean(mc_lvl))
    mc_per_plvl_mean = float(np.mean(mc_per_plvl))
    mc_per_plvl_se = (float(np.std(mc_per_plvl, ddof=1) / np.sqrt(n_seeds))
                     if n_seeds > 1 else float('nan'))
    mean_pLvl_mc = float(np.mean(mc_plvl))

    print(f"  MC mean(pLvl) over post-burnin: {mean_pLvl_mc:.6f}  "
          f"(TM uses E_pLvl_analytical at t=0; pLvl_factor=1)")
    print(f"  MC AggCons LEVEL mean: {mc_lvl_mean:.6f}  "
          f"(MC level grows with t; TM ref is at t=0)")
    print(f"  MC AggCons per pLvl mean ± SE: {mc_per_plvl_mean:.6f} ± {mc_per_plvl_se:.6f}")

    tm_p = TM_REFERENCE[cohort_label]['TM_P']
    tm_q = TM_REFERENCE[cohort_label]['TM_Q']
    print(f"  TM-P (at t=0): {tm_p:.6f}")
    print(f"  TM-Q (at t=0): {tm_q:.6f}")

    # The TM reference values are at t=0 with pLvl_factor=1 and the
    # analytical E_pLvl. So the apples-to-apples MC value is
    # (MC_AggCons_lvl / mean_pLvl_mc) * E_pLvl_TM.
    # But TM also uses E_pLvl in its level scaling, so the ratio
    # MC_AggCons_per_pLvl ≈ TM_AggCons / E_pLvl  (both should equal
    # the exact E_Q[c(m,j)] under Harmenberg). For comparison purposes:
    # divide TM by the analytical E_pLvl to get TM_per_pLvl, OR
    # multiply MC_per_pLvl by E_pLvl. Need E_pLvl_TM. Use the agent's
    # compute_analytical_mean_pLvl with u_ergodic from TM.
    # Easier: compare ratios MC/MC and TM-P/TM-P, TM-Q/TM-Q. The
    # GAP we care about is TM-Q vs TM-P, normalized by E_pLvl somewhere.
    #
    # Actually the cleanest check: compute MC's "per-pLvl" mean and
    # compare to TM's at-t=0 value scaled to the same per-pLvl basis
    # (i.e., divide TM by its E_pLvl_analytical). For HARK normalization
    # E_pLvl ≈ 1 in many setups but not exactly. We need to extract it.

    # Tactic: just report the gap RATIO (MC_per_pLvl) / (TM_X) and see
    # if TM-Q matches MC closer than TM-P does (in proportion).
    ratio_to_p = mc_per_plvl_mean / tm_p
    ratio_to_q = mc_per_plvl_mean / tm_q
    se_ratio = mc_per_plvl_se / tm_p

    print(f"\n  Ratio MC/TM (closer to 1.0 = better TM fit):")
    print(f"    MC/TM-P = {ratio_to_p:.6f}  (deviation {(ratio_to_p-1)*100:+.4f}%)")
    print(f"    MC/TM-Q = {ratio_to_q:.6f}  (deviation {(ratio_to_q-1)*100:+.4f}%)")
    print(f"    MC SE on ratio: ±{se_ratio:.6f} ({se_ratio*100:.4f}%)")

    # The Harmenberg prediction: MC/TM-Q closer to 1 than MC/TM-P.
    # If E_pLvl_analytical is ~1 (HARK convention), then MC_per_pLvl
    # should equal E_Q[c]; TM-X / E_pLvl_X also equals E_X[c]. Without
    # knowing E_pLvl_X exactly, we can't fully compare absolute values
    # — but |TM-P − TM-Q| / |MC| should match the analytical bias gap.

    # Most informative: TM-P vs TM-Q gap (already known: 0.4% for CO).
    # Whichever TM is closer to MC (in proportion) is the more accurate.
    # Since |MC/TM-P - MC/TM-Q| equals the same TM-P/TM-Q gap.

    return {
        'mc_per_plvl': mc_per_plvl_mean, 'mc_se': mc_per_plvl_se,
        'mc_pLvl': mean_pLvl_mc,
        'tm_p': tm_p, 'tm_q': tm_q,
        'ratio_p': ratio_to_p, 'ratio_q': ratio_to_q,
    }


def main():
    print("=" * 78)
    print("MC vs TM-P vs TM-Q — confirm TM-Q exact, TM-P biased (1-agent baseline)")
    print("=" * 78)

    # Conservative settings: N=100k, 5 seeds, T_sim=400 (matches act_T), burnin=200
    N = 100000
    n_seeds = 5
    T_sim = 400
    T_burnin = 200

    print(f"\nSettings: N={N}, n_seeds={n_seeds}, T_sim={T_sim}, T_burnin={T_burnin}")

    results = {}
    # Start with CO (largest predicted bias, easiest to detect)
    for cohort in ['CO', 'HS', 'DO']:
        cohort_idx = {'DO': 0, 'HS': 1, 'CO': 2}[cohort]
        results[cohort] = compare_cohort(cohort, cohort_idx, N, n_seeds, T_sim, T_burnin)

    print("\n" + "=" * 78)
    print("Summary table (ratios MC/TM closer to 1 = better TM accuracy):")
    print(f"  {'Cohort':<6} {'MC/pLvl ± SE':<22} {'MC/TM-P':<14} {'MC/TM-Q':<14} {'(P-Q gap)':<14}")
    print("  " + "-" * 80)
    for cohort, r in results.items():
        gap_pq = (r['ratio_q'] - r['ratio_p']) * 100
        print(f"  {cohort:<6} {r['mc_per_plvl']:.4f} ± {r['mc_se']:.4f}    "
              f"{r['ratio_p']:.6f}  {r['ratio_q']:.6f}  {gap_pq:+.4f}pp")
    print("=" * 78)


if __name__ == "__main__":
    main()
