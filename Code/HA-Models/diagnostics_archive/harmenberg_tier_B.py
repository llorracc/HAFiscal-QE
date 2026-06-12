"""
Harmenberg P↔Q comparison — Tier B: 7-atom HS + no-rec Check.

Per `plans/20260428-1252h_harmenberg-vs-p-measure-tm-a-comparison.md` §5.
Single HS cohort (Baseline parametrization → 7 β atoms), macro-0 baseline +
no-recession Check policy. Tests β heterogeneity interaction with Q reweighting.

Gate (loose):
  - Per-period rel diff < 1% for AggCons (and AggIncome for sanity)
  - Multiplier abs diff < 1pp

If pass: escalate to Tier C (full 21-type Baseline, 3 no-rec policies).
If fail: see §6.B of the plan (likely β-atom-specific issue).
"""

import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['harmenberg_tier_B']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data,
    propagate_experiment_tm_a,
    run_experiment_tm_nonbase,
)


def build_HS_7beta_economy():
    """7 HS β atoms (Baseline parametrization), AgentCount=pmv per type."""
    [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes,
     Check_changes, recession_Check_changes] = return_parameters(
        Parametrization='Baseline', OutputFor='_Main.py')

    discfac_dstn = DiscFacDstns[1]  # HS
    pmv = np.asarray(discfac_dstn.pmv, dtype=np.float64)
    atoms = np.asarray(discfac_dstn.atoms[0], dtype=np.float64)

    economy = AggregateDemandEconomy(**init_ADEconomy)
    typelist = []
    for b_idx in range(DiscFacCount):
        BaseType = AggFiscalType(**init_highschool)
        BaseType.cycles = 0
        BaseType.AgentCount = float(pmv[b_idx])
        BaseType.DiscFac = float(atoms[b_idx])
        BaseType.get_economy_data(economy)

        IncShkDstn_unemp = DiscreteDistribution(
            np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
        IncShkDstn_unemp_nobenefits = DiscreteDistribution(
            np.array([1.0]), [np.array([1.0]),
                              np.array([BaseType.IncUnempNoBenefits])])

        BaseType.IncShkDstn[0].seed = 763607780 + b_idx
        BaseType.IncShkDstn[0].reset()
        EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
        BaseType.IncShkDstn = [
            [BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal
            + [IncShkDstn_unemp_nobenefits]]
        BaseType.IncShkDstn_base = BaseType.IncShkDstn

        IncShkDstn_recession = [
            BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
        BaseType.IncShkDstn_recession = IncShkDstn_recession
        BaseType.IncShkDstn_recessionUI = IncShkDstn_recession

        EmployedIncShkDstn_TC = deepcopy(EmployedIncShkDstn)
        EmployedIncShkDstn_TC.atoms = (
            np.asarray(EmployedIncShkDstn_TC.atoms[0], dtype=np.float64),
            np.asarray(EmployedIncShkDstn_TC.atoms[1], dtype=np.float64)
            * BaseType.TaxCutIncFactor,
        )
        TaxCutStatesIncShkDstn = (
            [EmployedIncShkDstn_TC] + [IncShkDstn_unemp] * UBspell_normal
            + [IncShkDstn_unemp_nobenefits])
        IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
        for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
            IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
        BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
        BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

        BaseType.tm_a_indexed = True
        typelist.append(BaseType)

    economy.agents = typelist
    economy.solve()
    print(f"  N types: {len(typelist)}; "
          f"sum(AgentCount) = {sum(a.AgentCount for a in typelist):.6f}")
    return economy, num_experiment_periods


def macro0_baseline(eco_template, interpretation, neutral_measure):
    eco = deepcopy(eco_template)
    for agent in eco.agents:
        agent.interpretation = interpretation
    baseline_tm_data = compute_baseline_tm_data(
        eco, mCount=50, neutral_measure=neutral_measure, verbose=False)
    act_T = eco.act_T
    AggCons = np.zeros(act_T)
    AggIncome = np.zeros(act_T)
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
        AggCons += np.asarray(res['AggCons'])
        AggIncome += np.asarray(res['AggIncome'])
    return {'AggCons': AggCons, 'AggIncome': AggIncome, 'act_T': act_T}


def check_norec(eco_template, interpretation, neutral_measure, num_experiment_periods):
    eco = deepcopy(eco_template)
    for agent in eco.agents:
        agent.interpretation = interpretation
    baseline_tm_data = compute_baseline_tm_data(
        eco, mCount=50, neutral_measure=neutral_measure, verbose=False)
    eco.switch_shock_type('Check')
    eco.solve()
    act_T = eco.act_T
    EconomyMrkv_init = (list(np.arange(1, num_experiment_periods + 1) * 2)
                        + [0] * max(0, act_T - num_experiment_periods))
    res = run_experiment_tm_nonbase(
        eco, 'Check', EconomyMrkv_init, baseline_tm_data,
        mCount=50, neutral_measure=neutral_measure, verbose=False)
    return {'AggCons': np.asarray(res['AggCons']),
            'AggIncome': np.asarray(res['AggIncome']),
            'act_T': act_T}


def compare(P, Q):
    eps = 1e-15
    rel_diff = np.abs(P - Q) / np.maximum(np.abs(P), eps)
    return float(np.max(rel_diff)), float(np.mean(rel_diff))


def npv(arr, Rfree):
    disc = np.array([Rfree ** (-t) for t in range(len(arr))])
    return float(np.sum(disc * arr))


def main():
    print("=" * 72)
    print("Harmenberg Tier B — 7-atom HS / Baseline / baseline + no-rec Check")
    print("=" * 72)

    GATE_REL = 0.01
    GATE_MULT_PP = 0.01  # 1pp absolute on a multiplier of order 1

    print("\nBuilding 7-atom HS economy (Baseline)...")
    t0 = time.time()
    eco, num_experiment_periods = build_HS_7beta_economy()
    print(f"  setup + solve: {time.time()-t0:.1f}s")
    print(f"  act_T = {eco.act_T}, num_experiment_periods = {num_experiment_periods}")

    Rfree = eco.agents[0].Rfree[0]
    results = {}
    for interp in ['CDC', 'ESC']:
        for measure_name, neutral_measure in [('P', False), ('Q', True)]:
            t0 = time.time()
            base = macro0_baseline(eco, interp, neutral_measure)
            chk = check_norec(eco, interp, neutral_measure, num_experiment_periods)
            results[(interp, measure_name)] = {'base': base, 'check': chk}
            print(f"  {interp} × {measure_name}: base={time.time()-t0:.1f}s + check; "
                  f"base AggCons[0]={base['AggCons'][0]:.4f}, "
                  f"check AggCons[0]={chk['AggCons'][0]:.4f}")

    print("\n" + "=" * 72)
    print(f"  P↔Q rel-diff comparison (gate: < {GATE_REL:.0%})")
    print("=" * 72)
    print(f"  {'Interp':<6} {'Scenario':<10} {'Series':<10} {'max rel diff':>14} {'verdict':>10}")
    print("  " + "-" * 60)
    all_pass = True
    for interp in ['CDC', 'ESC']:
        P = results[(interp, 'P')]
        Q = results[(interp, 'Q')]
        for scen in ['base', 'check']:
            for series in ['AggCons', 'AggIncome']:
                max_rel, _ = compare(P[scen][series], Q[scen][series])
                verdict = 'PASS' if max_rel < GATE_REL else 'FAIL'
                if max_rel >= GATE_REL:
                    all_pass = False
                print(f"  {interp:<6} {scen:<10} {series:<10} {max_rel:>13.4%} {verdict:>10}")

    # Multiplier comparison
    print("\n" + "=" * 72)
    print(f"  Check multiplier P↔Q comparison (gate: |Δmult| < {GATE_MULT_PP*100:.1f}pp)")
    print("=" * 72)
    print(f"  {'Interp':<6} {'P mult':>10} {'Q mult':>10} {'|Δmult|':>10} {'verdict':>10}")
    print("  " + "-" * 50)
    for interp in ['CDC', 'ESC']:
        mults = {}
        for measure_name in ['P', 'Q']:
            r = results[(interp, measure_name)]
            cdiff = r['check']['AggCons'] - r['base']['AggCons']
            ydiff = r['check']['AggIncome'] - r['base']['AggIncome']
            npv_y = npv(ydiff, Rfree)
            mults[measure_name] = npv(cdiff, Rfree) / max(abs(npv_y), 1e-12) * np.sign(npv_y)
        diff_pp = abs(mults['P'] - mults['Q'])
        verdict = 'PASS' if diff_pp < GATE_MULT_PP else 'FAIL'
        if diff_pp >= GATE_MULT_PP:
            all_pass = False
        print(f"  {interp:<6} {mults['P']:>10.4f} {mults['Q']:>10.4f} {diff_pp*100:>9.4f}pp {verdict:>10}")

    print("=" * 72)
    if all_pass:
        print("\n✓ Tier B PASSED. Escalate to Tier C (full 21-type, 3 no-rec policies).")
    else:
        print("\n✗ Tier B FAILED. Halt; investigate per §6.B of plan.")


if __name__ == "__main__":
    main()
