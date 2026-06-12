"""
Harmenberg grid-resolution sweep — investigate whether the P↔Q rel diff
in Tiers 0/A is driven by insufficient aMax or aCount.

For each cohort (DO, HS, CO), build a single agent at the cohort's mid-β,
sweep over (aMax, aCount), and measure the P↔Q rel diff in baseline
AggCons. The hypothesis: rel diff → 0 as grid resolution → ∞; if so, the
0.1% gate failure is just numerical truncation.

Bypasses `compute_baseline_tm_data` and calls `build_tm_agg_fiscal_a`
directly so we can pass `aMax` explicitly.

Per `plans/20260428-1252h_harmenberg-vs-p-measure-tm-a-comparison.md` §6.A
diagnostic — investigating the BST 1D-pitfall under varying grid resolution.
"""

import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['harmenberg_grid_sweep']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import (
    build_tm_agg_fiscal_a,
    find_ergodic_distribution,
    propagate_experiment_tm_a,
    compute_analytical_mean_pLvl,
)


def build_agent(cohort_idx):
    """Single agent for given cohort at Reduced_Run mid-β."""
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
    BaseType.AgentCount = 1
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

    BaseType.tm_a_indexed = True

    economy.agents = [BaseType]
    economy.solve()
    return economy, BaseType.DiscFac


def baseline_one(agent, aCount, aMax, neutral_measure, interpretation, act_T=100):
    """Build TM, find ergodic, propagate baseline; return AggCons[0:T] +
    edge-mass diagnostic for the upper grid edge."""
    tm_data = build_tm_agg_fiscal_a(
        agent, aCount=aCount, aMax=aMax, aFac=3,
        neutral_measure=neutral_measure,
        interpretation=interpretation,
    )
    ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
    dist_aGrid = tm_data['dist_aGrid']
    A = len(dist_aGrid)

    # Edge mass (mass in last 5% of asset grid) — signature of truncation
    J = agent.MrkvArray[0].shape[0]
    erg_2d = np.asarray(ergodic).reshape(J, A)
    last_pct = max(1, int(0.05 * A))
    edge_mass = float(erg_2d[:, -last_pct:].sum())

    # E[pLvl] for level scaling
    u_ergodic = 1.0 - np.sum(ergodic[:A])
    E_pLvl = compute_analytical_mean_pLvl(agent, unemployment_rate=u_ergodic)

    # Propagate baseline (constant macro 0)
    res = propagate_experiment_tm_a(
        agent, ergodic, [0] * act_T, dist_aGrid, E_pLvl,
        Cratio=1.0, act_T=act_T, neutral_measure=neutral_measure,
        check_info=None,
        interpretation=interpretation,
    )
    return {
        'AggCons': np.asarray(res['AggCons']),
        'edge_mass': edge_mass,
        'aMax_used': float(tm_data.get('aMax', aMax)),
    }


def run_sweep(cohort_label, cohort_idx, grid_combos, interpretation='CDC'):
    print(f"\n{'='*78}")
    print(f"Cohort {cohort_label} (idx={cohort_idx})  Interpretation: {interpretation}")
    print(f"{'='*78}")
    eco, beta = build_agent(cohort_idx)
    agent = eco.agents[0]
    print(f"  agent: β={beta:.4f}, AgentCount=1, tm_a_indexed=True")

    print(f"\n  {'aMax':>6} {'aCount':>7} {'edge_mass_P':>12} {'edge_mass_Q':>12} "
          f"{'P AggCons[0]':>14} {'Q AggCons[0]':>14} {'rel_diff':>10} {'wall (s)':>9}")
    print(f"  " + "-" * 100)

    for (aMax, aCount) in grid_combos:
        t0 = time.time()
        try:
            P = baseline_one(agent, aCount, aMax, neutral_measure=False,
                             interpretation=interpretation)
            Q = baseline_one(agent, aCount, aMax, neutral_measure=True,
                             interpretation=interpretation)
            rel = abs(P['AggCons'][0] - Q['AggCons'][0]) / max(abs(P['AggCons'][0]), 1e-15)
            wall = time.time() - t0
            print(f"  {aMax:>6} {aCount:>7} {P['edge_mass']:>12.5f} {Q['edge_mass']:>12.5f} "
                  f"{P['AggCons'][0]:>14.6f} {Q['AggCons'][0]:>14.6f} {rel:>9.5%} {wall:>8.1f}s")
        except Exception as e:
            print(f"  {aMax:>6} {aCount:>7} ERROR: {e}")


def main():
    print("=" * 78)
    print("Harmenberg P↔Q grid-resolution sweep")
    print("=" * 78)

    # Sweep grid: combinations of (aMax, aCount)
    # Start from current default (500, 200) and escalate
    grid_combos = [
        (500, 200),    # current default
        (500, 400),    # 2x aCount
        (500, 800),    # 4x aCount
        (1000, 200),   # 2x aMax
        (1000, 400),
        (1000, 800),
        (2000, 400),   # 4x aMax
        (2000, 800),
        (5000, 800),   # 10x aMax
        (5000, 1600),
    ]

    # Only test CDC (Q ≈ P comparison should be interpretation-shared in mechanism)
    # Test all 3 cohorts (HS and CO are most informative)
    for cohort_label, cohort_idx in [('HS', 1), ('CO', 2), ('DO', 0)]:
        run_sweep(cohort_label, cohort_idx, grid_combos, interpretation='CDC')


if __name__ == "__main__":
    main()
