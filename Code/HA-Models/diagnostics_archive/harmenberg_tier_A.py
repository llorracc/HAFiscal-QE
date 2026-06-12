"""
Harmenberg P↔Q comparison — Tier A: 3 cohorts (Reduced_Run), baseline only.

Per `plans/20260428-1252h_harmenberg-vs-p-measure-tm-a-comparison.md` §5.
Extends Tier 0 to all 3 cohorts (DO + HS + CO) at Reduced_Run (1 atom each),
weighted by data_EducShares. Tests cross-cohort interaction with Q reweighting.

Gate (loose): per-period rel diff < 1% for both AggCons and AggIncome,
both per-cohort AND population-aggregate, both interpretations.

If pass: escalate to Tier B (7-atom HS + no-rec Check).
If fail: see §6.A of the plan (likely cross-cohort interaction).
"""

import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['harmenberg_tier_A']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import compute_baseline_tm_data, propagate_experiment_tm_a


def build_3cohort_economy():
    """3 cohorts (DO, HS, CO) at Reduced_Run (1 β atom each), AgentCount=EducShares."""
    [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes,
     Check_changes, recession_Check_changes] = return_parameters(
        Parametrization='Reduced_Run', OutputFor='_Main.py')

    inits = [init_dropout, init_highschool, init_college]
    edu_labels = ['DO', 'HS', 'CO']

    economy = AggregateDemandEconomy(**init_ADEconomy)
    typelist = []
    for e in range(3):
        atoms = np.asarray(DiscFacDstns[e].atoms[0], dtype=np.float64)
        BaseType = AggFiscalType(**inits[e])
        BaseType.cycles = 0
        BaseType.AgentCount = float(data_EducShares[e])
        BaseType.DiscFac = float(atoms[0])  # Reduced_Run = 1 atom
        BaseType.get_economy_data(economy)

        IncShkDstn_unemp = DiscreteDistribution(
            np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
        IncShkDstn_unemp_nobenefits = DiscreteDistribution(
            np.array([1.0]), [np.array([1.0]),
                              np.array([BaseType.IncUnempNoBenefits])])

        BaseType.IncShkDstn[0].seed = 763607780 + e * 100
        BaseType.IncShkDstn[0].reset()
        BaseType.IncShkDstn = [
            [BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal
            + [IncShkDstn_unemp_nobenefits]]
        BaseType.IncShkDstn_base = BaseType.IncShkDstn

        BaseType.tm_a_indexed = True
        typelist.append(BaseType)

    economy.agents = typelist
    economy.solve()
    print(f"  Total types: {len(typelist)}; "
          f"sum(AgentCount) = {sum(a.AgentCount for a in typelist):.6f}; "
          f"β = {[round(a.DiscFac, 4) for a in typelist]}")
    return economy, edu_labels


def run_baseline_per_cohort(eco_template, interpretation, neutral_measure):
    """Returns per-cohort and total AggCons/AggIncome trajectories."""
    eco = deepcopy(eco_template)
    for agent in eco.agents:
        agent.interpretation = interpretation
    baseline_tm_data = compute_baseline_tm_data(
        eco, mCount=50, neutral_measure=neutral_measure, verbose=False)
    act_T = eco.act_T

    per_cohort = []
    AggCons_total = np.zeros(act_T)
    AggIncome_total = np.zeros(act_T)
    for i, agent in enumerate(eco.agents):
        bd = baseline_tm_data[i]
        res = propagate_experiment_tm_a(
            agent, bd['ergodic'], [0] * act_T,
            bd['dist_aGrid'], bd['E_pLvl'],
            Cratio=1.0, act_T=act_T,
            neutral_measure=neutral_measure,
            check_info=None,
            interpretation=interpretation,
        )
        AggCons_i = np.asarray(res['AggCons'])
        AggIncome_i = np.asarray(res['AggIncome'])
        per_cohort.append({'AggCons': AggCons_i, 'AggIncome': AggIncome_i})
        AggCons_total += AggCons_i
        AggIncome_total += AggIncome_i

    return {
        'per_cohort': per_cohort,
        'total_AggCons': AggCons_total,
        'total_AggIncome': AggIncome_total,
        'act_T': act_T,
    }


def compare(P, Q):
    eps = 1e-15
    rel_diff = np.abs(P - Q) / np.maximum(np.abs(P), eps)
    return float(np.max(rel_diff)), float(np.mean(rel_diff))


def main():
    print("=" * 72)
    print("Harmenberg Tier A — 3-cohort Reduced_Run baseline P↔Q comparison")
    print("=" * 72)

    GATE_REL = 0.01

    print("\nBuilding 3-cohort Reduced_Run economy...")
    t0 = time.time()
    eco, edu_labels = build_3cohort_economy()
    print(f"  setup + solve: {time.time()-t0:.1f}s")
    print(f"  act_T = {eco.act_T}")

    results = {}
    for interp in ['CDC', 'ESC']:
        for measure_name, neutral_measure in [('P', False), ('Q', True)]:
            t0 = time.time()
            res = run_baseline_per_cohort(eco, interp, neutral_measure)
            print(f"  {interp} × {measure_name}: total AggCons[0]={res['total_AggCons'][0]:.4f} ({time.time()-t0:.1f}s)")
            results[(interp, measure_name)] = res

    print("\n" + "=" * 72)
    print(f"  Per-cohort + population P↔Q comparison (gate: max rel diff < {GATE_REL:.0%})")
    print("=" * 72)
    print(f"  {'Interp':<6} {'Scope':<10} {'Series':<12} {'max rel diff':>15} {'mean rel diff':>15} {'verdict':>10}")
    print("  " + "-" * 76)

    all_pass = True
    for interp in ['CDC', 'ESC']:
        P = results[(interp, 'P')]
        Q = results[(interp, 'Q')]
        # Per-cohort
        for c_idx, label in enumerate(edu_labels):
            for series in ['AggCons', 'AggIncome']:
                P_c = P['per_cohort'][c_idx][series]
                Q_c = Q['per_cohort'][c_idx][series]
                max_rel, mean_rel = compare(P_c, Q_c)
                verdict = 'PASS' if max_rel < GATE_REL else 'FAIL'
                if max_rel >= GATE_REL:
                    all_pass = False
                print(f"  {interp:<6} {label:<10} {series:<12} {max_rel:>14.4%} {mean_rel:>14.4%} {verdict:>10}")
        # Population total
        for series_key in ['total_AggCons', 'total_AggIncome']:
            P_t = P[series_key]
            Q_t = Q[series_key]
            max_rel, mean_rel = compare(P_t, Q_t)
            verdict = 'PASS' if max_rel < GATE_REL else 'FAIL'
            if max_rel >= GATE_REL:
                all_pass = False
            display = series_key.replace('total_', '')
            print(f"  {interp:<6} {'POP':<10} {display:<12} {max_rel:>14.4%} {mean_rel:>14.4%} {verdict:>10}")
        print("  " + "-" * 76)

    print("=" * 72)
    if all_pass:
        print("\n✓ Tier A PASSED. Escalate to Tier B (7-atom HS + no-rec Check).")
    else:
        print("\n✗ Tier A FAILED. Halt; investigate per §6.A of plan.")


if __name__ == "__main__":
    main()
