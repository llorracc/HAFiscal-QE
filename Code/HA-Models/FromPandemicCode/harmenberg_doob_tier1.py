"""
Cascade-gate Tier 1 (production): 3 cohorts (DO+HS+CO) × 1 β each.

Reduced_Run parametrization (Phase 2 production calibration). For each
(cohort, beta) type:
  - Build TM-P, ergodic_P
  - Compute pi_Q^doob via tm_methods.compute_doob_pi_q_a (Fix 4)
  - Build TM-Q (existing BST), find ergodic
  - Run MC at N=200,000

Then aggregate over types weighted by data_EducShares × DiscFacDstn.pmv.
Compare population E_Q[a] under TM-Q vs Doob vs MC.

OUTCOME (2026-06-05, BUG-051 investigation): Doob was NOT adopted — the
MC<->TM wealth gap that motivated it was TM-a's missing (1-varsigma) ESC
splurge correction
(BUGS_private/HAFiscal_BUG-051_tm_a_ESC_missing_splurge_correction.md).
"""

import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['harmenberg_doob_tier1']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import (
    build_tm_agg_fiscal_a,
    find_ergodic_distribution,
    compute_doob_pi_q_a,
)


def setup_context(parametrization='Reduced_Run'):
    [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes,
     Check_changes, recession_Check_changes] = return_parameters(
        Parametrization=parametrization, OutputFor='_Main.py')
    return {
        'init_by_edType': [init_dropout, init_highschool, init_college],
        'init_ADEconomy': init_ADEconomy,
        'DiscFacDstns': DiscFacDstns,
        'data_EducShares': data_EducShares,
        'UBspell_normal': UBspell_normal,
    }


def build_agent_for(edType, beta, ctx, interpretation='CDC'):
    init_dict = dict(ctx['init_by_edType'][edType])
    init_dict['interpretation'] = interpretation
    BaseType = AggFiscalType(**init_dict)
    BaseType.cycles = 0
    BaseType.DiscFac = float(beta)
    economy = AggregateDemandEconomy(**ctx['init_ADEconomy'])
    BaseType.get_economy_data(economy)
    UBspell = ctx['UBspell_normal']
    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]),
                          np.array([BaseType.IncUnempNoBenefits])])
    BaseType.IncShkDstn[0].seed = 763607781
    BaseType.IncShkDstn[0].reset()
    BaseType.IncShkDstn = [
        [BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell
        + [IncShkDstn_unemp_nobenefits]]
    BaseType.IncShkDstn_base = BaseType.IncShkDstn
    economy.agents = [BaseType]
    economy.solve()
    return economy.agents[0]


def run_mc_capture_aj(agent_template, N, seed, T_sim=400, capture_T=350):
    agent = deepcopy(agent_template)
    agent.AgentCount = N
    agent.seed = seed
    agent.T_sim = T_sim
    agent.track_vars = ['aNrm', 'MrkvNowPcvd', 'pLvl']
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0
    agent.Cratio = 1.0
    agent.EconomyMrkvNow_hist = [0] * T_sim
    agent.simulate()
    aNrm_t = np.asarray(agent.history['aNrm'][capture_T])
    j_t = np.asarray(agent.history['MrkvNowPcvd'][capture_T]).astype(int)
    pLvl_t = np.asarray(agent.history['pLvl'][capture_T])
    return aNrm_t, j_t, pLvl_t


def build_pi_marginals(aNrm_arr, j_arr, pLvl_arr, dist_aGrid, J=None):
    if J is None:
        J = int(j_arr.max() + 1)
    A = len(dist_aGrid)
    a_idx = np.searchsorted(dist_aGrid, aNrm_arr, side='left').clip(0, A - 1)
    for k in range(len(aNrm_arr)):
        i = a_idx[k]
        if 0 < i < A:
            if abs(aNrm_arr[k] - dist_aGrid[i - 1]) < abs(aNrm_arr[k] - dist_aGrid[i]):
                a_idx[k] = i - 1
    pi_Q = np.zeros((J, A))
    p_mean = float(np.mean(pLvl_arr))
    weights_Q = (pLvl_arr / p_mean) / len(aNrm_arr)
    for k in range(len(aNrm_arr)):
        pi_Q[j_arr[k], a_idx[k]] += weights_Q[k]
    return pi_Q


def main(parametrization='Reduced_Run', edTypes=(0, 1, 2),
         N_MC=200_000, T_sim=400, capture_T=350, aCount=200, aMax=500,
         interpretation='CDC'):
    title = f"Tier ({parametrization}, edTypes={edTypes}, N_MC={N_MC}, interp={interpretation})"
    print("=" * 78)
    print(title)
    print("=" * 78)

    ctx = setup_context(parametrization)
    edu_names = ['Dropout', 'HighSchool', 'College']

    # Build (cohort × beta) type list with population weights
    types = []
    for edType in edTypes:
        share = float(ctx['data_EducShares'][edType])
        DFD = ctx['DiscFacDstns'][edType]
        for ib, beta in enumerate(DFD.atoms[0]):
            w = share * float(DFD.pmv[ib])
            types.append({'edType': edType, 'beta': float(beta), 'pop_weight': w,
                          'label': f"{edu_names[edType][:2]}-β{ib}"})
    print(f"\n{len(types)} (cohort × beta) types:")
    for t in types:
        print(f"  {t['label']}: edType={t['edType']}, β={t['beta']:.4f}, pop_w={t['pop_weight']:.4f}")

    seed_base = 30000
    pop_E_a_TM_Q = 0.0
    pop_E_a_doob = 0.0
    pop_E_a_MC = 0.0
    by_type = []

    for i_t, t in enumerate(types):
        print(f"\n--- {i_t+1}/{len(types)}: {t['label']} (edType={t['edType']}, β={t['beta']:.4f}, pop_w={t['pop_weight']:.4f}) ---")
        agent = build_agent_for(t['edType'], t['beta'], ctx, interpretation=interpretation)
        tm_data_P = build_tm_agg_fiscal_a(agent, aCount=aCount, aMax=aMax, aFac=3,
                                           neutral_measure=False, interpretation=interpretation)
        pi_P = find_ergodic_distribution(tm_data_P['TranMatrix'])
        tm_data_Q = build_tm_agg_fiscal_a(agent, aCount=aCount, aMax=aMax, aFac=3,
                                           neutral_measure=True, interpretation=interpretation)
        pi_Q_TM = find_ergodic_distribution(tm_data_Q['TranMatrix'])

        t0 = time.time()
        doob_out = compute_doob_pi_q_a(agent, tm_data_P, pi_P, interpretation=interpretation)
        t_doob = time.time() - t0
        pi_Q_doob = doob_out['pi_Q_doob']

        t0 = time.time()
        aNrm_arr, j_arr, pLvl_arr = run_mc_capture_aj(
            agent, N_MC, seed=seed_base + i_t, T_sim=T_sim, capture_T=capture_T)
        t_mc = time.time() - t0

        dist_aGrid = tm_data_P['dist_aGrid']
        J = pi_P.shape[0] // len(dist_aGrid)
        A = len(dist_aGrid)
        pi_Q_MC = build_pi_marginals(aNrm_arr, j_arr, pLvl_arr, dist_aGrid, J=J)

        E_a_TM_Q = float(np.sum(pi_Q_TM.reshape(J, A) * dist_aGrid[None, :]))
        E_a_doob = float(np.sum(pi_Q_doob.reshape(J, A) * dist_aGrid[None, :]))
        E_a_MC = float(np.average(aNrm_arr, weights=pLvl_arr))

        print(f"  Doob: {t_doob:.2f}s | MC: {t_mc:.1f}s")
        print(f"  E_Q[a]: TM-Q={E_a_TM_Q:.4f}, Doob={E_a_doob:.4f}, MC={E_a_MC:.4f}")
        print(f"  rel gap to MC: TM-Q={(E_a_TM_Q-E_a_MC)/E_a_MC*100:+.3f}%, Doob={(E_a_doob-E_a_MC)/E_a_MC*100:+.3f}%")

        pop_E_a_TM_Q += t['pop_weight'] * E_a_TM_Q
        pop_E_a_doob += t['pop_weight'] * E_a_doob
        pop_E_a_MC += t['pop_weight'] * E_a_MC
        by_type.append({**t, 'E_a_TM_Q': E_a_TM_Q, 'E_a_doob': E_a_doob, 'E_a_MC': E_a_MC})

    print("\n" + "=" * 78)
    print("Population-weighted aggregate")
    print("=" * 78)
    print(f"  E_Q[a] (population):")
    print(f"    TM-Q (BST):   {pop_E_a_TM_Q:.6f}")
    print(f"    Doob (Fix 4): {pop_E_a_doob:.6f}")
    print(f"    MC truth:     {pop_E_a_MC:.6f}")
    gap_TM_Q = pop_E_a_TM_Q - pop_E_a_MC
    gap_doob = pop_E_a_doob - pop_E_a_MC
    rel_gap_TM_Q = gap_TM_Q / pop_E_a_MC if pop_E_a_MC != 0 else float('nan')
    rel_gap_doob = gap_doob / pop_E_a_MC if pop_E_a_MC != 0 else float('nan')
    print(f"  abs gap to MC:  TM-Q={gap_TM_Q:+.6f} | Doob={gap_doob:+.6f}")
    print(f"  rel gap to MC:  TM-Q={rel_gap_TM_Q:+.4%} | Doob={rel_gap_doob:+.4%}")

    print("\n--- verdict ---")
    if abs(gap_doob) < abs(gap_TM_Q):
        print(f"  PASS: Doob's |gap to MC| ({abs(gap_doob):.6f}) < TM-Q's ({abs(gap_TM_Q):.6f})")
    else:
        print(f"  FAIL: Doob's |gap to MC| ({abs(gap_doob):.6f}) >= TM-Q's ({abs(gap_TM_Q):.6f})")


if __name__ == "__main__":
    # (b): Tier 1 = 3 cohorts × 1 β each, Reduced_Run (production)
    main(parametrization='Reduced_Run', edTypes=(0, 1, 2))
