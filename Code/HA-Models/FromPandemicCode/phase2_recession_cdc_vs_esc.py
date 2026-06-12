"""
Phase 2: recession-variant CDC vs ESC comparison (all three policies).

Per plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md §6
sub-tasks 2.1 + 2.2 (recession variants of Check, TaxCut, UI).

Setup mirrors the no-recession drivers (single HS, mid-β, Reduced_Run,
tm_a_indexed=True, AgentCount=1) but with:
  - shock_type ∈ {'recessionCheck', 'recessionTaxCut', 'recessionUI'}
  - EconomyMrkv_init = fixed-duration recession path: same even-state
    walk as no-recession but the first `duration` entries are +1
    (odd → recession active).

Default fixed_duration=3 matches validate_tm_ui.py.

Optionally pass --full-averaging to average across all
max_recession_duration durations weighted by the geometric
recession_prob_array.
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
parser.add_argument('--full-averaging', action='store_true',
                    help='Average across all recession durations (slower)')
args = parser.parse_args()
sys.argv = ['phase2_recession_cdc_vs_esc']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data,
    run_experiment_tm_nonbase,
    propagate_experiment_tm_a,
)


def build_HS_economy():
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
    BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

    economy = AggregateDemandEconomy(**init_ADEconomy)
    BaseType.get_economy_data(economy)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])

    BaseType.IncShkDstn[0].seed = 763607780
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
        np.asarray(EmployedIncShkDstn_TC.atoms[1], dtype=np.float64) * BaseType.TaxCutIncFactor,
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

    economy.agents = [BaseType]
    economy.solve()
    return economy, num_experiment_periods, max_recession_duration


def mrkv_path_recession_fixed(num_experiment_periods, total_T, duration):
    """First `duration` periods recession (odd macro), then back to non-recession."""
    head = list(np.arange(1, num_experiment_periods + 1) * 2)
    tail_len = max(0, total_T - len(head))
    path = head + [0] * tail_len
    for t in range(min(duration, len(path))):
        path[t] = path[t] + 1
    return path


def recession_prob_array(Rspell, max_recession_duration):
    R_persist = 1.0 - 1.0 / Rspell
    arr = np.array([R_persist**t * (1 - R_persist)
                    for t in range(max_recession_duration)])
    arr[-1] = 1.0 - np.sum(arr[:-1])
    return arr


def run_one(eco_template, shock_type, interpretation, num_experiment_periods,
            duration_or_avg, max_recession_duration, mCount=50):
    """Returns AggCons_pc, AggIncome_pc averaged (or single fixed-duration)."""
    eco = deepcopy(eco_template)
    for agent in eco.agents:
        agent.interpretation = interpretation

    baseline_tm_data = compute_baseline_tm_data(eco, mCount=mCount, verbose=False)

    eco.switch_shock_type(shock_type)
    eco.solve()
    act_T = eco.act_T

    if duration_or_avg == 'avg':
        Rspell = eco.agents[0].Rspell
        rprob = recession_prob_array(Rspell, max_recession_duration)
        agg_C = np.zeros(act_T)
        agg_Y = np.zeros(act_T)
        for d in range(max_recession_duration):
            path = mrkv_path_recession_fixed(num_experiment_periods, act_T, d + 1)
            res = run_experiment_tm_nonbase(
                eco, shock_type, path, baseline_tm_data,
                mCount=mCount, verbose=False)
            agg_C += rprob[d] * np.asarray(res['AggCons'])
            agg_Y += rprob[d] * np.asarray(res['AggIncome'])
        return {'AggCons_pc': agg_C, 'AggIncome_pc': agg_Y, 'act_T': act_T}
    else:
        path = mrkv_path_recession_fixed(num_experiment_periods, act_T,
                                         duration_or_avg)
        res = run_experiment_tm_nonbase(
            eco, shock_type, path, baseline_tm_data,
            mCount=mCount, verbose=False)
        return {'AggCons_pc': np.asarray(res['AggCons']),
                'AggIncome_pc': np.asarray(res['AggIncome']),
                'act_T': act_T}


def run_baseline_macro0(eco_template, interpretation, mCount=50):
    """Baseline trajectory with macro=0 throughout (no recession, no policy).
    Matches validate_tm_ui.py:191-198 — the recession+policy 'shock' is
    compared to the no-recession-no-policy macro-0 baseline. Agent is in
    base-Markov mode (4 micro states), so initial_macro=0 only."""
    eco = deepcopy(eco_template)
    for agent in eco.agents:
        agent.interpretation = interpretation
    baseline_tm_data = compute_baseline_tm_data(eco, mCount=mCount, verbose=False)
    bd0 = baseline_tm_data[0]
    base_agent = eco.agents[0]
    act_T = eco.act_T

    res = propagate_experiment_tm_a(
        base_agent, bd0['ergodic'], [0] * act_T,
        bd0['dist_aGrid'], bd0['E_pLvl'],
        Cratio=1.0, act_T=act_T, neutral_measure=False,
        check_info=None,
        interpretation=interpretation,
    )
    return {'AggCons_pc': np.asarray(res['AggCons']),
            'AggIncome_pc': np.asarray(res['AggIncome']),
            'act_T': act_T}


def main():
    print("=" * 72)
    label = ('avg' if args.full_averaging else f'fixed dur={args.duration}')
    print(f"Phase 2: recession-variant CDC vs ESC  ({label})")
    print("=" * 72)

    print("\nBuilding HS economy...")
    t0 = time.time()
    eco, num_experiment_periods, max_recession_duration = build_HS_economy()
    print(f"  setup + solve: {time.time()-t0:.1f}s")
    print(f"  num_experiment_periods = {num_experiment_periods}")
    print(f"  max_recession_duration = {max_recession_duration}")
    print(f"  Splurge ς = {eco.agents[0].Splurge:.4f}; (1-ς) = {1-eco.agents[0].Splurge:.4f}")

    Rfree = eco.agents[0].Rfree[0]
    duration_or_avg = 'avg' if args.full_averaging else args.duration

    policies = [
        ('recessionCheck',  'Check'),
        ('recessionTaxCut', 'TaxCut'),
        ('recessionUI',     'UI'),
    ]

    # Per-interpretation: compute macro-0 baseline AND recession-only baseline
    # (the latter is `shock_type='recession'` with the same recession path
    # the policies use — denominator becomes pure policy transfer).
    baselines = {}
    rec_baselines = {}
    for interp in ['CDC', 'ESC']:
        print(f"\nBaselines under {interp}...")
        t0 = time.time()
        baselines[interp] = run_baseline_macro0(eco, interp)
        print(f"  macro-0 baseline: {time.time()-t0:.1f}s")
        t0 = time.time()
        rec_baselines[interp] = run_one(eco, 'recession', interp,
                                         num_experiment_periods,
                                         duration_or_avg, max_recession_duration)
        print(f"  recession-only baseline: {time.time()-t0:.1f}s")

    summary = {}
    for shock_type, short in policies:
        print(f"\n{'='*72}\n  Policy: {short}  (shock_type={shock_type})\n{'='*72}")
        summary[short] = {}
        for interp in ['CDC', 'ESC']:
            print(f"\n--- {interp} interpretation ---")
            base = baselines[interp]
            recb = rec_baselines[interp]
            t0 = time.time()
            shk = run_one(eco, shock_type, interp, num_experiment_periods,
                          duration_or_avg, max_recession_duration)
            print(f"  shock experiment: {time.time()-t0:.1f}s")

            T = shk['act_T']
            disc = np.array([Rfree ** (-t) for t in range(T)])

            # Combined-effect multiplier (vs macro-0): denominator absorbs
            # both recession income loss and policy transfer.
            cdiff_combo = shk['AggCons_pc'] - base['AggCons_pc']
            ydiff_combo = shk['AggIncome_pc'] - base['AggIncome_pc']
            npv_c_combo = float(np.sum(disc * cdiff_combo))
            npv_y_combo = float(np.sum(disc * ydiff_combo))
            mult_combo = npv_c_combo / max(abs(npv_y_combo), 1e-12) \
                * np.sign(npv_y_combo)

            # Strict-policy multiplier (vs recession-only): denominator is
            # the pure policy transfer (recession effect cancels).
            cdiff_pol = shk['AggCons_pc'] - recb['AggCons_pc']
            ydiff_pol = shk['AggIncome_pc'] - recb['AggIncome_pc']
            npv_c_pol = float(np.sum(disc * cdiff_pol))
            npv_y_pol = float(np.sum(disc * ydiff_pol))
            mult_pol = npv_c_pol / max(abs(npv_y_pol), 1e-12) \
                * np.sign(npv_y_pol)

            summary[short][interp] = {
                'mult_combo': mult_combo, 'mult_pol': mult_pol,
                'npv_y_combo': npv_y_combo, 'npv_y_pol': npv_y_pol,
            }
            print(f"  combined-effect (vs macro-0): NPV(Y)={npv_y_combo:+.5f}  mult={mult_combo:+.4f}")
            print(f"  strict-policy   (vs recession): NPV(Y)={npv_y_pol:+.5f}  mult={mult_pol:+.4f}")
            print(f"  AggIncome_pc[policy 0..6]: {[f'{x:+.5f}' for x in ydiff_pol[:7]]}")

    print("\n" + "=" * 72)
    print(f"Recession-variant summary  ({label})")
    print("=" * 72)
    print(f"  {'Policy':<8} {'metric':<14} "
          f"{'CDC mult':>10} {'ESC mult':>10} {'Δ (CDC-ESC)':>14}")
    print("  " + "-" * 60)
    for _, short in policies:
        for metric, key in [('combined', 'mult_combo'), ('strict-policy', 'mult_pol')]:
            cdc_m = summary[short]['CDC'][key]
            esc_m = summary[short]['ESC'][key]
            print(f"  {short:<8} {metric:<14} {cdc_m:>10.4f} {esc_m:>10.4f}   "
                  f"{100*(cdc_m-esc_m):>+8.2f}pp")
        print("  " + "-" * 60)
    print("=" * 72)


if __name__ == "__main__":
    main()
