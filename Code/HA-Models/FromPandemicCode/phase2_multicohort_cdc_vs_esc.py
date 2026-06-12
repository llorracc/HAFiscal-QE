"""
Phase 2 #4 — full multi-cohort × multi-β population.

Extends phase2_multibeta_cdc_vs_esc.py to all 3 education groups
(dropout, HS, college) × DiscFacCount β atoms each = 21 types under
Baseline parametrization.

AgentCount[edu][b] = data_EducShares[edu] × DiscFacDstns[edu].pmv[b]
so the kernel's level outputs are already population per-capita
(sum over all 21 types of AgentCount = sum(EducShares)·sum(pmv) = 1).

Per-cohort init dicts differ (e.g. unemployment rates), so each cohort
needs its own type-construction loop. All 21 types live in
economy.agents and the production wrappers iterate over them.

Per cascade-gating: this is the population-level analog of the prior
single-β / multi-β drivers. Compute scales: 21 types × ~8 scenarios ×
2 interpretations ≈ 21×16 ≈ 340 propagator calls × ~1s/call ≈ 6 min.
"""

import argparse
import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

parser = argparse.ArgumentParser()
parser.add_argument('--duration', type=int, default=3,
                    help='Fixed recession duration (default 3)')
parser.add_argument('--no-recession', action='store_true',
                    help='Skip recession scenarios')
args = parser.parse_args()
sys.argv = ['phase2_multicohort_cdc_vs_esc']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data,
    run_experiment_tm_nonbase,
    propagate_experiment_tm_a,
)


def build_population_economy():
    """Build 3 cohorts × DiscFacCount β atoms. AgentCount per type =
    EducShares[edu] × pmv_edu[b]. tm_a_indexed=True."""
    [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes,
     Check_changes, recession_Check_changes] = return_parameters(
        Parametrization='Baseline', OutputFor='_Main.py')

    inits = [init_dropout, init_highschool, init_college]
    edu_labels = ['DO', 'HS', 'CO']

    print(f"  data_EducShares: {list(data_EducShares)}")
    for e in range(3):
        atoms = np.asarray(DiscFacDstns[e].atoms[0], dtype=np.float64)
        pmv = np.asarray(DiscFacDstns[e].pmv, dtype=np.float64)
        print(f"  {edu_labels[e]}: atoms={atoms.round(4).tolist()}, pmv={pmv.round(4).tolist()}")

    economy = AggregateDemandEconomy(**init_ADEconomy)
    typelist = []
    for e in range(3):
        atoms = np.asarray(DiscFacDstns[e].atoms[0], dtype=np.float64)
        pmv = np.asarray(DiscFacDstns[e].pmv, dtype=np.float64)
        for b_idx in range(DiscFacCount):
            BaseType = AggFiscalType(**inits[e])
            BaseType.cycles = 0
            BaseType.AgentCount = float(data_EducShares[e] * pmv[b_idx])
            BaseType.DiscFac = float(atoms[b_idx])
            BaseType.get_economy_data(economy)

            IncShkDstn_unemp = DiscreteDistribution(
                np.array([1.0]),
                [np.array([1.0]), np.array([BaseType.IncUnemp])])
            IncShkDstn_unemp_nobenefits = DiscreteDistribution(
                np.array([1.0]),
                [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])

            BaseType.IncShkDstn[0].seed = 763607780 + e * 100 + b_idx
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
    print(f"  Total types: {len(typelist)}; "
          f"sum(AgentCount) = {sum(a.AgentCount for a in typelist):.6f}")
    economy.solve()
    return economy, num_experiment_periods, max_recession_duration


def mrkv_path_no_recession(num_experiment_periods, total_T):
    head = list(np.arange(1, num_experiment_periods + 1) * 2)
    return head + [0] * max(0, total_T - len(head))


def mrkv_path_recession_fixed(num_experiment_periods, total_T, duration):
    path = mrkv_path_no_recession(num_experiment_periods, total_T)
    for t in range(min(duration, len(path))):
        path[t] = path[t] + 1
    return path


def run_macro0_baseline(eco_template, interpretation, mCount=50):
    eco = deepcopy(eco_template)
    for agent in eco.agents:
        agent.interpretation = interpretation
    baseline_tm_data = compute_baseline_tm_data(eco, mCount=mCount, verbose=False)
    act_T = eco.act_T
    AggCons = np.zeros(act_T)
    AggIncome = np.zeros(act_T)
    for i, agent in enumerate(eco.agents):
        bd = baseline_tm_data[i]
        res = propagate_experiment_tm_a(
            agent, bd['ergodic'], [0] * act_T,
            bd['dist_aGrid'], bd['E_pLvl'],
            Cratio=1.0, act_T=act_T, neutral_measure=False,
            check_info=None,
            interpretation=interpretation,
        )
        AggCons += np.asarray(res['AggCons'])
        AggIncome += np.asarray(res['AggIncome'])
    return {'AggCons_pc': AggCons, 'AggIncome_pc': AggIncome, 'act_T': act_T}


def run_shock(eco_template, shock_type, interpretation, num_experiment_periods,
              path_or_macro0, mCount=50):
    eco = deepcopy(eco_template)
    for agent in eco.agents:
        agent.interpretation = interpretation
    baseline_tm_data = compute_baseline_tm_data(eco, mCount=mCount, verbose=False)
    eco.switch_shock_type(shock_type)
    eco.solve()
    act_T = eco.act_T
    if path_or_macro0 == 'no_recession':
        path = mrkv_path_no_recession(num_experiment_periods, act_T)
    else:
        path = path_or_macro0
    res = run_experiment_tm_nonbase(
        eco, shock_type, path, baseline_tm_data,
        mCount=mCount, verbose=False)
    return {'AggCons_pc': np.asarray(res['AggCons']),
            'AggIncome_pc': np.asarray(res['AggIncome']),
            'act_T': act_T}


def npv(arr, Rfree):
    disc = np.array([Rfree ** (-t) for t in range(len(arr))])
    return float(np.sum(disc * arr))


def main():
    print("=" * 78)
    print("Phase 2 #4 — multi-cohort × multi-β population, CDC vs ESC")
    print("=" * 78)

    print("\nBuilding 21-type population economy...")
    t0 = time.time()
    eco, num_experiment_periods, max_recession_duration = build_population_economy()
    print(f"  setup + solve: {time.time()-t0:.1f}s")

    Rfree = eco.agents[0].Rfree[0]
    do_recession = not args.no_recession
    rec_path = (mrkv_path_recession_fixed(num_experiment_periods, eco.act_T,
                                          args.duration)
                if do_recession else None)

    no_rec_policies = [('Check', 'Check'), ('TaxCut', 'TaxCut'), ('UI', 'UI')]
    rec_policies = [('recessionCheck', 'Check'),
                    ('recessionTaxCut', 'TaxCut'),
                    ('recessionUI', 'UI')]

    out = {}
    for interp in ['CDC', 'ESC']:
        print(f"\n--- {interp} ---")
        out[interp] = {}

        t0 = time.time()
        out[interp]['macro0'] = run_macro0_baseline(eco, interp)
        print(f"  macro-0 baseline:        {time.time()-t0:.1f}s")

        for shock_type, short in no_rec_policies:
            t0 = time.time()
            out[interp][f'norec_{short}'] = run_shock(
                eco, shock_type, interp, num_experiment_periods, 'no_recession')
            print(f"  no-rec {short:<7} shock:    {time.time()-t0:.1f}s")

        if do_recession:
            t0 = time.time()
            out[interp]['recession'] = run_shock(
                eco, 'recession', interp, num_experiment_periods, rec_path)
            print(f"  recession-only baseline: {time.time()-t0:.1f}s")
            for shock_type, short in rec_policies:
                t0 = time.time()
                out[interp][f'rec_{short}'] = run_shock(
                    eco, shock_type, interp, num_experiment_periods, rec_path)
                print(f"  rec {short:<7} shock:        {time.time()-t0:.1f}s")

    # ---- Summary table ----
    print("\n" + "=" * 78)
    print(f"Multi-cohort × multi-β population summary — Rfree={Rfree:.4f}, "
          f"{'no-rec only' if not do_recession else f'rec dur={args.duration}'}")
    print("=" * 78)
    print(f"  {'Scenario':<24} {'CDC mult':>10} {'ESC mult':>10} "
          f"{'Δ (CDC-ESC)':>14}")
    print("  " + "-" * 60)

    for short in ['Check', 'TaxCut', 'UI']:
        mults = {}
        for interp in ['CDC', 'ESC']:
            base = out[interp]['macro0']
            shk = out[interp][f'norec_{short}']
            cdiff = shk['AggCons_pc'] - base['AggCons_pc']
            ydiff = shk['AggIncome_pc'] - base['AggIncome_pc']
            npv_y = npv(ydiff, Rfree)
            mults[interp] = npv(cdiff, Rfree) / max(abs(npv_y), 1e-12) * np.sign(npv_y)
        print(f"  {short + ' (no-rec)':<24} {mults['CDC']:>10.4f} {mults['ESC']:>10.4f}"
              f"   {100*(mults['CDC']-mults['ESC']):>+8.2f}pp")

    if do_recession:
        print("  " + "-" * 60)
        for short in ['Check', 'TaxCut', 'UI']:
            mults_combo = {}
            mults_pol = {}
            for interp in ['CDC', 'ESC']:
                base0 = out[interp]['macro0']
                rec = out[interp]['recession']
                shk = out[interp][f'rec_{short}']
                cdiff_combo = shk['AggCons_pc'] - base0['AggCons_pc']
                ydiff_combo = shk['AggIncome_pc'] - base0['AggIncome_pc']
                cdiff_pol = shk['AggCons_pc'] - rec['AggCons_pc']
                ydiff_pol = shk['AggIncome_pc'] - rec['AggIncome_pc']
                npv_y_combo = npv(ydiff_combo, Rfree)
                npv_y_pol = npv(ydiff_pol, Rfree)
                mults_combo[interp] = npv(cdiff_combo, Rfree) / \
                    max(abs(npv_y_combo), 1e-12) * np.sign(npv_y_combo)
                mults_pol[interp] = npv(cdiff_pol, Rfree) / \
                    max(abs(npv_y_pol), 1e-12) * np.sign(npv_y_pol)
            print(f"  {short + ' (rec, combo)':<24} {mults_combo['CDC']:>10.4f}"
                  f" {mults_combo['ESC']:>10.4f}"
                  f"   {100*(mults_combo['CDC']-mults_combo['ESC']):>+8.2f}pp")
            print(f"  {short + ' (rec, strict)':<24} {mults_pol['CDC']:>10.4f}"
                  f" {mults_pol['ESC']:>10.4f}"
                  f"   {100*(mults_pol['CDC']-mults_pol['ESC']):>+8.2f}pp")
    print("=" * 78)


if __name__ == "__main__":
    main()
