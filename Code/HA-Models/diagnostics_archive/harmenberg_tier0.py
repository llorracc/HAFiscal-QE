"""
Harmenberg P↔Q comparison — Tier 0: 1 HS agent, baseline only.

Per `plans/20260428-1252h_harmenberg-vs-p-measure-tm-a-comparison.md` §4.
Smallest possible kernel-correctness check: build 1 HS agent (mid-β),
run macro-0 baseline propagation under both interpretations × both
measures (4 runs total), compare trajectories per period.

Gate (initial loose pass): per-period rel diff `|P − Q| / |P|` < 1%
for AggCons and AggIncome, ALL t, both interpretations.

If pass: escalate to Tier A (Reduced_Run 3-cohort).
If fail: see §6.0 of the plan for diagnostic steps.
"""

import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['harmenberg_tier0']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import compute_baseline_tm_data, propagate_experiment_tm_a


def build_HS_economy_1agent():
    """Single HS agent at mid-β atom, AgentCount=1, tm_a_indexed=True."""
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
    BaseType.AgentCount = 1
    BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]  # mid β atom (Reduced_Run = single atom)

    economy = AggregateDemandEconomy(**init_ADEconomy)
    BaseType.get_economy_data(economy)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])

    BaseType.IncShkDstn[0].seed = 763607780
    BaseType.IncShkDstn[0].reset()
    BaseType.IncShkDstn = [
        [BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]]
    BaseType.IncShkDstn_base = BaseType.IncShkDstn

    BaseType.tm_a_indexed = True

    economy.agents = [BaseType]
    economy.solve()
    return economy


def run_baseline(eco_template, interpretation, neutral_measure):
    """Macro-0 baseline trajectory under given (interpretation, measure)."""
    eco = deepcopy(eco_template)
    for agent in eco.agents:
        agent.interpretation = interpretation

    baseline_tm_data = compute_baseline_tm_data(
        eco, mCount=50, neutral_measure=neutral_measure, verbose=False)
    bd0 = baseline_tm_data[0]
    base_agent = eco.agents[0]
    act_T = eco.act_T

    res = propagate_experiment_tm_a(
        base_agent, bd0['ergodic'], [0] * act_T,
        bd0['dist_aGrid'], bd0['E_pLvl'],
        Cratio=1.0, act_T=act_T,
        neutral_measure=neutral_measure,
        check_info=None,
        interpretation=interpretation,
    )
    return {
        'AggCons': np.asarray(res['AggCons']),
        'AggIncome': np.asarray(res['AggIncome']),
        'act_T': act_T,
    }


def compare(P, Q, label):
    """Compare two trajectories; return (max_rel_diff, summary string)."""
    eps = 1e-15
    rel_diff = np.abs(P - Q) / np.maximum(np.abs(P), eps)
    return float(np.max(rel_diff)), float(np.mean(rel_diff)), float(rel_diff[0])


def main():
    print("=" * 72)
    print("Harmenberg Tier 0 — 1 HS agent, baseline P↔Q comparison")
    print("=" * 72)

    GATE_REL = 0.01  # 1% per the loose initial gate

    print("\nBuilding 1-HS-agent economy (Reduced_Run)...")
    t0 = time.time()
    eco = build_HS_economy_1agent()
    print(f"  setup + solve: {time.time()-t0:.1f}s")
    print(f"  agent: AgentCount={eco.agents[0].AgentCount}, "
          f"DiscFac={eco.agents[0].DiscFac:.4f}, tm_a_indexed=True")
    print(f"  act_T = {eco.act_T}")

    results = {}
    for interp in ['CDC', 'ESC']:
        for measure_name, neutral_measure in [('P', False), ('Q', True)]:
            t0 = time.time()
            res = run_baseline(eco, interp, neutral_measure)
            print(f"  {interp} × {measure_name}-measure: "
                  f"AggCons[0]={res['AggCons'][0]:.6f}  "
                  f"AggIncome[0]={res['AggIncome'][0]:.6f}  "
                  f"({time.time()-t0:.1f}s)")
            results[(interp, measure_name)] = res

    print("\n" + "=" * 72)
    print(f"  P↔Q comparison (gate: max rel diff < {GATE_REL:.0%} for ALL t)")
    print("=" * 72)
    print(f"  {'Interp':<6} {'Series':<10} {'max rel diff':>15} {'mean rel diff':>15} {'rel diff[0]':>15} {'verdict':>10}")
    print("  " + "-" * 78)

    all_pass = True
    for interp in ['CDC', 'ESC']:
        P = results[(interp, 'P')]
        Q = results[(interp, 'Q')]
        for series in ['AggCons', 'AggIncome']:
            max_rel, mean_rel, rel_0 = compare(P[series], Q[series], series)
            verdict = 'PASS' if max_rel < GATE_REL else 'FAIL'
            if max_rel >= GATE_REL:
                all_pass = False
            print(f"  {interp:<6} {series:<10} {max_rel:>14.4%} {mean_rel:>14.4%} {rel_0:>14.4%} {verdict:>10}")

    print("=" * 72)
    if all_pass:
        print("\n✓ Tier 0 PASSED. Escalate to Tier A (Reduced_Run 3-cohort).")
    else:
        print("\n✗ Tier 0 FAILED. Halt cascade; investigate per §6.0 of plan.")
        # Print full trajectory comparison for diagnosis
        print("\nDiagnostic: full P vs Q trajectories")
        for interp in ['CDC', 'ESC']:
            P = results[(interp, 'P')]
            Q = results[(interp, 'Q')]
            print(f"\n  {interp}:")
            print(f"    AggCons P[0:5] : {P['AggCons'][:5].tolist()}")
            print(f"    AggCons Q[0:5] : {Q['AggCons'][:5].tolist()}")
            print(f"    AggCons rel[0:5]: {(np.abs(P['AggCons']-Q['AggCons'])/np.maximum(np.abs(P['AggCons']),1e-15))[:5].tolist()}")
            print(f"    AggIncome P[0:5]: {P['AggIncome'][:5].tolist()}")
            print(f"    AggIncome Q[0:5]: {Q['AggIncome'][:5].tolist()}")


if __name__ == "__main__":
    main()
