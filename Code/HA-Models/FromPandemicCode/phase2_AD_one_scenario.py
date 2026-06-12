"""
Phase 2 AD: single-scenario AD-amplified driver.

Runs ONE (shock_type × interpretation × parametrization) AD scenario via
run_ad_tm (Phase 1 CFunc training + Phase 2 final eval). Designed to be
launched in parallel — 6 scenarios at once (3 rec policies × 2 interps).

Outputs are appended to /tmp/phase2_AD_results.json so the launcher can
stitch the multiplier table together after all runs complete.

Usage:
  python phase2_AD_one_scenario.py \
      --shock_type recessionCheck --interpretation CDC \
      --duration 3 --parametrization Baseline \
      --output_path /tmp/phase2_AD_results.json
"""

import argparse
import json
import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

parser = argparse.ArgumentParser()
parser.add_argument('--shock_type', required=True,
                    choices=['recessionCheck', 'recessionTaxCut', 'recessionUI'])
parser.add_argument('--interpretation', required=True,
                    choices=['CDC', 'ESC'])
parser.add_argument('--duration', type=int, default=3)
parser.add_argument('--full_averaging', action='store_true',
                    help='Average across all recession durations weighted by geometric prob')
parser.add_argument('--parametrization', default='Baseline',
                    choices=['Baseline', 'Reduced_Run'])
parser.add_argument('--output_path', default='/tmp/phase2_AD_results.json')
parser.add_argument('--ad_max_iter', type=int, default=10)
parser.add_argument('--ad_tol', type=float, default=0.004)
parser.add_argument('--no_ad', action='store_true',
                    help='Skip AD machinery; use propagate_experiment_tm_a directly with Cratio=1')
parser.add_argument('--n_workers', type=int, default=1,
                    help='Number of worker processes for within-scenario duration parallelism. '
                         'Default 1 = sequential. Linux fork-based; uses globals (no pickling cost).')
args = parser.parse_args()
sys.argv = ['phase2_AD_one_scenario']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data,
    propagate_experiment_tm_a,
    run_ad_tm,
)


def build_population_economy(parametrization):
    """Build all (cohort × β-atom) types per Baseline (21 types) or
    Reduced_Run (3 types — 1 atom per cohort)."""
    [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes,
     Check_changes, recession_Check_changes] = return_parameters(
        Parametrization=parametrization, OutputFor='_Main.py')

    inits = [init_dropout, init_highschool, init_college]

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


def macro0_baseline_aggcons(eco_template, interpretation, mCount=50):
    """Returns AggCons trajectory under macro-0-everywhere, for AD's
    Cratio computation."""
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
    return AggCons, AggIncome, act_T


def npv(arr, Rfree):
    disc = np.array([Rfree ** (-t) for t in range(len(arr))])
    return float(np.sum(disc * arr))


# ---------------------------------------------------------------------------
# Module-level globals for worker access via Linux-fork inheritance.
# Set in main() before the Pool is created.
# ---------------------------------------------------------------------------
_eco_rec_g = None
_eco_pol_g = None
_rec_baseline_tm_data_g = None
_pol_baseline_tm_data_g = None
_macro0_C_g = None
_act_T_g = None
_num_experiment_periods_g = None


def _worker_no_ad(d):
    """Worker for one duration (no-AD path). Returns (d, rec_C, rec_Y, pol_C, pol_Y)."""
    duration = d + 1
    this_path = mrkv_path_recession_fixed(_num_experiment_periods_g,
                                           _act_T_g, duration)
    is_check_pol = args.shock_type in ('Check', 'recessionCheck')
    rec_C = np.zeros(_act_T_g)
    rec_Y = np.zeros(_act_T_g)
    pol_C = np.zeros(_act_T_g)
    pol_Y = np.zeros(_act_T_g)
    for i in range(len(_eco_rec_g.agents)):
        cR, yR = run_one_propagator_path(
            _eco_rec_g.agents[i], _rec_baseline_tm_data_g[i],
            this_path, args.interpretation, 'recession', False, _act_T_g)
        cP, yP = run_one_propagator_path(
            _eco_pol_g.agents[i], _pol_baseline_tm_data_g[i],
            this_path, args.interpretation, args.shock_type, is_check_pol, _act_T_g)
        rec_C += cR
        rec_Y += yR
        pol_C += cP
        pol_Y += yP
    return d, rec_C, rec_Y, pol_C, pol_Y


def _worker_ad(d):
    """Worker for one duration (AD path; assumes CFunc already trained
    in parent). Returns (d, rec_C, rec_Y, pol_C, pol_Y)."""
    duration = d + 1
    this_path = mrkv_path_recession_fixed(_num_experiment_periods_g,
                                           _act_T_g, duration)
    rec_d = run_ad_tm(
        _eco_rec_g, 'recession', this_path,
        _rec_baseline_tm_data_g, AggCons_baseline=_macro0_C_g,
        ADelasticity=0.3, num_max_iterations=args.ad_max_iter,
        convergence_tol=args.ad_tol, mCount=50,
        neutral_measure=False, verbose=False,
        skip_training=True,
    )
    pol_d = run_ad_tm(
        _eco_pol_g, args.shock_type, this_path,
        _pol_baseline_tm_data_g, AggCons_baseline=_macro0_C_g,
        ADelasticity=0.3, num_max_iterations=args.ad_max_iter,
        convergence_tol=args.ad_tol, mCount=50,
        neutral_measure=False, verbose=False,
        skip_training=True,
    )
    return (d, np.asarray(rec_d['AggCons']), np.asarray(rec_d['AggIncome']),
            np.asarray(pol_d['AggCons']), np.asarray(pol_d['AggIncome']))


def run_one_propagator_path(agent, bd, path, interpretation,
                            shock_type, is_check, act_T):
    """Single per-type propagator call, no AD (Cratio=1)."""
    check_info_i = None
    if is_check:
        from tm_methods import _compute_check_buckets
        buckets = _compute_check_buckets(agent, bd['E_pLvl'],
                                         unemployment_rate=bd.get('u_ergodic'))
        check_info_i = {'period': 0, 'buckets': buckets}
    res = propagate_experiment_tm_a(
        agent, bd['ergodic'], path,
        bd['dist_aGrid'], bd['E_pLvl'],
        Cratio=1.0, act_T=act_T, neutral_measure=False,
        check_info=check_info_i,
        shock_type=shock_type,
        interpretation=interpretation,
    )
    return np.asarray(res['AggCons']), np.asarray(res['AggIncome'])


def main():
    if args.no_ad:
        ad_tag = 'noAD'
    else:
        ad_tag = 'AD'
    suffix = (f'{ad_tag}_avg' if args.full_averaging
              else f'{ad_tag}_dur{args.duration}')
    label = (f"{args.shock_type}_{args.interpretation}_"
             f"{suffix}_{args.parametrization}")
    print("=" * 78)
    print(f"Phase 2 AD scenario: {label}")
    print("=" * 78)

    print("\nBuilding economy...")
    t0 = time.time()
    eco, num_experiment_periods, max_recession_duration = \
        build_population_economy(args.parametrization)
    print(f"  setup + solve: {time.time()-t0:.1f}s")
    print(f"  Total types: {len(eco.agents)}")

    Rfree = eco.agents[0].Rfree[0]
    interp = args.interpretation

    # ---- Macro-0 baseline (per interpretation) ----
    t0 = time.time()
    macro0_C, macro0_Y, act_T = macro0_baseline_aggcons(eco, interp)
    print(f"  macro-0 baseline: {time.time()-t0:.1f}s")

    # ---- Recession-only baseline (no policy, recession path) ----
    eco_rec = deepcopy(eco)
    for agent in eco_rec.agents:
        agent.interpretation = interp
    rec_baseline_tm_data = compute_baseline_tm_data(eco_rec, mCount=50, verbose=False)
    eco_rec.switch_shock_type('recession')
    eco_rec.solve()

    # ---- Policy economy ----
    eco_pol = deepcopy(eco)
    for agent in eco_pol.agents:
        agent.interpretation = interp
    pol_baseline_tm_data = compute_baseline_tm_data(eco_pol, mCount=50, verbose=False)
    eco_pol.switch_shock_type(args.shock_type)
    eco_pol.solve()

    if args.full_averaging:
        # Average across all recession durations weighted by geometric prob.
        # Optimization: train CFunc once (worst-case path is duration-invariant)
        # then evaluate Phase 2 on each duration with skip_training=True.
        Rspell = eco.agents[0].Rspell
        R_persist = 1.0 - 1.0 / Rspell
        rprob = np.array([R_persist**t * (1 - R_persist)
                          for t in range(max_recession_duration)])
        rprob[-1] = 1.0 - np.sum(rprob[:-1])
        print(f"  averaging over {max_recession_duration} durations; "
              f"rprob = {rprob.round(4).tolist()}")

        rec_only_C = np.zeros(act_T)
        rec_only_Y = np.zeros(act_T)
        pol_C = np.zeros(act_T)
        pol_Y = np.zeros(act_T)

        # For AD: train CFunc once in parent (skip_training=False on dur=1),
        # then all workers use skip_training=True via inherited memory.
        if not args.no_ad:
            print(f"  AD: pre-training CFunc (one pass on duration=1) ...")
            t0 = time.time()
            init_path = mrkv_path_recession_fixed(num_experiment_periods,
                                                   act_T, 1)
            _ = run_ad_tm(
                eco_rec, 'recession', init_path,
                rec_baseline_tm_data, AggCons_baseline=macro0_C,
                ADelasticity=0.3, num_max_iterations=args.ad_max_iter,
                convergence_tol=args.ad_tol, mCount=50,
                neutral_measure=False, verbose=True,
                skip_training=False,
            )
            print(f"    eco_rec CFunc training: {time.time()-t0:.1f}s")
            t0 = time.time()
            _ = run_ad_tm(
                eco_pol, args.shock_type, init_path,
                pol_baseline_tm_data, AggCons_baseline=macro0_C,
                ADelasticity=0.3, num_max_iterations=args.ad_max_iter,
                convergence_tol=args.ad_tol, mCount=50,
                neutral_measure=False, verbose=True,
                skip_training=False,
            )
            print(f"    eco_pol CFunc training: {time.time()-t0:.1f}s")

        # Set globals for workers (Linux fork inherits them)
        global _eco_rec_g, _eco_pol_g, _rec_baseline_tm_data_g, \
            _pol_baseline_tm_data_g, _macro0_C_g, _act_T_g, \
            _num_experiment_periods_g
        _eco_rec_g = eco_rec
        _eco_pol_g = eco_pol
        _rec_baseline_tm_data_g = rec_baseline_tm_data
        _pol_baseline_tm_data_g = pol_baseline_tm_data
        _macro0_C_g = macro0_C
        _act_T_g = act_T
        _num_experiment_periods_g = num_experiment_periods

        worker_fn = _worker_no_ad if args.no_ad else _worker_ad
        n_w = max(1, min(args.n_workers, max_recession_duration))
        print(f"  dispatching {max_recession_duration} durations across {n_w} workers...")

        if n_w == 1:
            # Sequential — kept for n_workers=1 (default) to avoid mp overhead
            results = []
            for d in range(max_recession_duration):
                t_d = time.time()
                results.append(worker_fn(d))
                print(f"  dur={d+1}: {time.time()-t_d:.1f}s")
        else:
            import multiprocessing as mp
            t_pool = time.time()
            with mp.get_context('fork').Pool(processes=n_w) as pool:
                results = pool.map(worker_fn, range(max_recession_duration))
            print(f"  pool-parallel total: {time.time()-t_pool:.1f}s")

        # Aggregate weighted sums
        for d, rec_C_d, rec_Y_d, pol_C_d, pol_Y_d in results:
            rec_only_C += rprob[d] * rec_C_d
            rec_only_Y += rprob[d] * rec_Y_d
            pol_C += rprob[d] * pol_C_d
            pol_Y += rprob[d] * pol_Y_d
    else:
        rec_path = mrkv_path_recession_fixed(num_experiment_periods, act_T,
                                              args.duration)
        t0 = time.time()
        rec_only_AD = run_ad_tm(
            eco_rec, 'recession', rec_path,
            rec_baseline_tm_data, AggCons_baseline=macro0_C,
            ADelasticity=0.3, num_max_iterations=args.ad_max_iter,
            convergence_tol=args.ad_tol, mCount=50,
            neutral_measure=False, verbose=True,
        )
        print(f"  recession-only AD: {time.time()-t0:.1f}s")
        rec_only_C = np.asarray(rec_only_AD['AggCons'])
        rec_only_Y = np.asarray(rec_only_AD['AggIncome'])

        t0 = time.time()
        pol_AD = run_ad_tm(
            eco_pol, args.shock_type, rec_path,
            pol_baseline_tm_data, AggCons_baseline=macro0_C,
            ADelasticity=0.3, num_max_iterations=args.ad_max_iter,
            convergence_tol=args.ad_tol, mCount=50,
            neutral_measure=False, verbose=True,
        )
        print(f"  policy AD: {time.time()-t0:.1f}s")
        pol_C = np.asarray(pol_AD['AggCons'])
        pol_Y = np.asarray(pol_AD['AggIncome'])

    # ---- Multipliers ----
    cdiff_combo = pol_C - macro0_C
    ydiff_combo = pol_Y - macro0_Y
    cdiff_pol = pol_C - rec_only_C
    ydiff_pol = pol_Y - rec_only_Y

    npv_y_combo = npv(ydiff_combo, Rfree)
    npv_y_pol = npv(ydiff_pol, Rfree)
    mult_combo = (npv(cdiff_combo, Rfree) / max(abs(npv_y_combo), 1e-12)
                  * np.sign(npv_y_combo))
    mult_pol = (npv(cdiff_pol, Rfree) / max(abs(npv_y_pol), 1e-12)
                * np.sign(npv_y_pol))

    print("\n" + "=" * 78)
    print(f"  shock_type    = {args.shock_type}")
    print(f"  interpretation= {args.interpretation}")
    print(f"  parametriz.   = {args.parametrization}")
    print(f"  combined-effect (vs macro-0): mult = {mult_combo:+.4f}")
    print(f"  strict-policy   (vs recession-AD): mult = {mult_pol:+.4f}")
    print("=" * 78)

    # Append result to JSON
    result = {
        'label': label,
        'shock_type': args.shock_type,
        'interpretation': args.interpretation,
        'duration': args.duration,
        'parametrization': args.parametrization,
        'mult_combo': mult_combo,
        'mult_pol': mult_pol,
        'npv_y_combo': npv_y_combo,
        'npv_y_pol': npv_y_pol,
        'rec_only_AggCons': rec_only_C.tolist(),
        'rec_only_AggIncome': rec_only_Y.tolist(),
        'pol_AggCons': pol_C.tolist(),
        'pol_AggIncome': pol_Y.tolist(),
        'macro0_AggCons': macro0_C.tolist(),
        'macro0_AggIncome': macro0_Y.tolist(),
        'Rfree': float(Rfree),
    }
    # Append (no global lock; fine since each process writes its own key)
    existing = {}
    if os.path.exists(args.output_path):
        try:
            with open(args.output_path) as f:
                existing = json.load(f)
        except Exception:
            existing = {}
    existing[label] = result
    tmp_path = args.output_path + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(existing, f, indent=2)
    os.replace(tmp_path, args.output_path)
    print(f"\n  Result appended to {args.output_path}")


if __name__ == "__main__":
    main()
