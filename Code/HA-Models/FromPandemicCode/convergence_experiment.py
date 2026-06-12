"""
MC/TM Convergence Experiment — Simplified

TM (mCount=50) is ground truth. Sweep MC agent counts to find the
minimum N where max relative error is <1% across key metrics.

Usage:
    python convergence_experiment.py [N1 N2 ...] [--seeds S]

Default: N=5000 with 5 seeds. Pass agent counts as positional args.
"""

import os
import sys
import json
import argparse
import numpy as np
from time import time
from copy import deepcopy

# Parse OUR args before importing HAFiscal modules, because
# EstimParameters.py reads sys.argv[1] as Rfree_base if present.
parser = argparse.ArgumentParser()
parser.add_argument('agent_counts', nargs='*', type=int, default=[5000])
parser.add_argument('--seeds', type=int, default=5)
args = parser.parse_args()
sys.argv = sys.argv[:1]  # clear args so EstimParameters doesn't misinterpret them

cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data, run_experiment_tm, run_experiment_tm_nonbase,
)

OUTPUT_KEYS = ['AggCons', 'AggIncome', 'NPV_AggCons', 'NPV_AggIncome']


def max_rel_error(val, ref):
    val, ref = np.atleast_1d(val), np.atleast_1d(ref)
    mask = np.abs(ref) > 1e-12
    if not np.any(mask):
        return 0.0
    return float(np.max(np.abs(val[mask] - ref[mask]) / np.abs(ref[mask])))


def normalize_results(result, N, keys=OUTPUT_KEYS):
    """Scale aggregate results to per-capita."""
    return {k: np.asarray(result[k]) / N for k in keys}


def compare_results(result, ref, keys=OUTPUT_KEYS):
    return {k: max_rel_error(result[k], ref[k]) for k in keys}


def worst_error(err_dict):
    return max(err_dict.values())


def total_agents(type_list):
    return sum(a.AgentCount for a in type_list)


AGENT_COUNTS = args.agent_counts
NUM_SEEDS = args.seeds

print("=" * 60)
print("TM-vs-MC CONVERGENCE EXPERIMENT")
print(f"  Agent counts: {AGENT_COUNTS}")
print(f"  Seeds per count: {NUM_SEEDS}")
print("=" * 60)

# ============================================================
# Setup: Build Reduced_Run economy, solve once
# ============================================================
t_total_start = time()

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

num_types = 3
BaseTypeList = []
for init_dict in [init_dropout, init_highschool, init_college]:
    t = AggFiscalType(**init_dict)
    t.cycles = 0
    BaseTypeList.append(t)

AggDemandEconomy = AggregateDemandEconomy(**init_ADEconomy)
for t in BaseTypeList:
    t.get_economy_data(AggDemandEconomy)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseTypeList[0].IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseTypeList[0].IncUnempNoBenefits])])

for bt in BaseTypeList:
    bt.IncShkDstn[0].seed = 763607780
    bt.IncShkDstn[0].reset()

for ThisType in BaseTypeList:
    EmployedIncShkDstn = deepcopy(ThisType.IncShkDstn[0])
    # bug_fix (6-state): U3/U4 extension slots pay no-benefits income in non-UI scenarios.
    # (num_base_MrkvStates-2-UBspell_normal) == Policy_ExtraBenefitQuarters (=2 bug_fix, 0 legacy
    # -> byte-identical legacy). Mirrors the validated Simulate.py construction.
    ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits] * (num_base_MrkvStates - 2 - UBspell_normal) + [IncShkDstn_unemp_nobenefits]]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn
    IncShkDstn_recession = [ThisType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
    ThisType.IncShkDstn_recession = IncShkDstn_recession
    ThisType.IncShkDstn_recessionUI = IncShkDstn_recession
    # BUG-023 fix: was `atoms[0][1] *= TaxCutIncFactor`, which mutated ONE element
    # of the PermShk atom array (atoms[0]=PermShk, atoms[1]=TranShk per HARK
    # convention). Intended behavior is to scale every joint atom's TranShk by
    # TaxCutIncFactor. See BUGS_private/HAFiscal_BUG-023_taxcut_atoms_typo.md
    EmployedIncShkDstn.atoms = (
        np.asarray(EmployedIncShkDstn.atoms[0], dtype=np.float64),
        np.asarray(EmployedIncShkDstn.atoms[1], dtype=np.float64) * ThisType.TaxCutIncFactor,
    )
    TaxCutStatesIncShkDstn = [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits] * (num_base_MrkvStates - 2 - UBspell_normal) + [IncShkDstn_unemp_nobenefits]
    IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
    for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
        IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, num_base_MrkvStates)]
    ThisType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
    ThisType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)


def build_type_list(N, seed_offset=0):
    tl = []
    n = 0
    for e in range(num_types):
        for b in range(DiscFacCount):
            DiscFac = DiscFacDstns[e].atoms[0][b]
            AgentCount = int(np.floor(N * data_EducShares[e] * DiscFacDstns[e].pmv[b]))
            tt = deepcopy(BaseTypeList[e])
            tt.AgentCount = AgentCount
            tt.DiscFac = DiscFac
            tt.seed = n + seed_offset
            tl.append(tt)
            n += 1
    return tl


TypeList_init = build_type_list(5000)
AggDemandEconomy.agents = TypeList_init

t0 = time()
AggDemandEconomy.solve()
t_solve = time() - t0
print(f"\nSetup + solve: {time() - t_total_start:.1f}s (solve={t_solve:.1f}s)")

base_dict_agg = deepcopy(base_dict)
act_T = AggDemandEconomy.act_T

# ============================================================
# TM Ground Truth (mCount=50)
# ============================================================
print(f"\n{'=' * 60}")
print("TM GROUND TRUTH (mCount=50)")
print("=" * 60)

N_tm = total_agents(AggDemandEconomy.agents)
print(f"  TM economy total agents: {N_tm}")

t0 = time()
tm_base_raw = run_experiment_tm(AggDemandEconomy, shock_type="base", mCount=50, verbose=False)

eco_check_tm = deepcopy(AggDemandEconomy)
eco_check_tm.switch_shock_type('Check')
eco_check_tm.solve()
baseline_tm_data = compute_baseline_tm_data(AggDemandEconomy, mCount=50, verbose=False)
check_mrkv = list(np.arange(1, eco_check_tm.num_experiment_periods + 1) * 2) + [0] * 20
tm_check_raw = run_experiment_tm_nonbase(
    eco_check_tm, 'Check', check_mrkv, baseline_tm_data, mCount=50, verbose=False)
t_tm = time() - t0

tm_base = normalize_results(tm_base_raw, N_tm)
tm_check = normalize_results(tm_check_raw, N_tm)

print(f"  Time: {t_tm:.1f}s")
print(f"  Baseline AggCons/cap[0] = {tm_base['AggCons'][0]:.4f}")
print(f"  Check AggCons/cap[0] = {tm_check['AggCons'][0]:.4f}")


# ============================================================
# MC Sweep
# ============================================================
def run_mc_single(N, seed):
    """Run one MC realization: burn-in + baseline + Check. Return per-capita results + wall time."""
    t0 = time()
    eco = deepcopy(AggDemandEconomy)
    tl = build_type_list(N, seed_offset=seed * 1000)
    eco.agents = tl
    N_actual = total_agents(tl)
    for a in eco.agents:
        a.get_economy_data(eco)
    eco.solve()

    eco.reset()
    for a in eco.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    eco.make_history()
    eco.save_state()
    eco.switch_to_counterfactual_mode("base")
    eco.act_T = act_T
    for a in eco.agents:
        a.T_sim = act_T
        a.EconomyMrkvNow_hist = [0] * act_T
    eco.make_idiosyncratic_shock_histories()

    base_r_raw = eco.run_experiment(**base_dict_agg, Full_Output=True)
    eco.store_baseline(base_r_raw['AggCons'])

    eco_c = deepcopy(eco)
    eco_c.switch_shock_type('Check')
    eco_c.solve()
    check_d = base_dict_agg.copy()
    check_d.update(Check_changes)
    check_d['EconomyMrkv_init'] = list(np.arange(1, eco_c.num_experiment_periods + 1) * 2) + [0] * 20
    check_r_raw = eco_c.run_experiment(**check_d, Full_Output=True)

    base_r = normalize_results(base_r_raw, N_actual)
    check_r = normalize_results(check_r_raw, N_actual)
    return base_r, check_r, time() - t0


all_results = {}

for N in AGENT_COUNTS:
    print(f"\n{'=' * 60}")
    print(f"MC SWEEP: N={N}, {NUM_SEEDS} seeds")
    print("=" * 60)

    seed_base = []
    seed_check = []
    seed_times = []

    for s in range(NUM_SEEDS):
        print(f"  Seed {s}/{NUM_SEEDS}...", end=" ", flush=True)
        br, cr, wt = run_mc_single(N, s)
        seed_base.append(br)
        seed_check.append(cr)
        seed_times.append(wt)
        print(f"{wt:.1f}s")

    # Mean across seeds
    mc_base_mean = {k: np.mean([r[k] for r in seed_base], axis=0) for k in OUTPUT_KEYS}
    mc_check_mean = {k: np.mean([r[k] for r in seed_check], axis=0) for k in OUTPUT_KEYS}
    mc_base_stderr = {k: np.std([r[k] for r in seed_base], axis=0) / np.sqrt(NUM_SEEDS) for k in OUTPUT_KEYS}
    mc_check_stderr = {k: np.std([r[k] for r in seed_check], axis=0) / np.sqrt(NUM_SEEDS) for k in OUTPUT_KEYS}

    base_err = compare_results(mc_base_mean, tm_base)
    check_err = compare_results(mc_check_mean, tm_check)

    mean_wall = np.mean(seed_times)
    print(f"\n  Results for N={N} ({NUM_SEEDS}-seed mean, {mean_wall:.1f}s/seed):")
    print(f"    Baseline max-rel-errors vs TM:")
    for k, v in base_err.items():
        print(f"      {k}: {v*100:.4f}%")
    print(f"    Check max-rel-errors vs TM:")
    for k, v in check_err.items():
        print(f"      {k}: {v*100:.4f}%")
    print(f"    WORST error (baseline): {worst_error(base_err)*100:.4f}%")
    print(f"    WORST error (check):    {worst_error(check_err)*100:.4f}%")
    print(f"    WORST error (overall):  {max(worst_error(base_err), worst_error(check_err))*100:.4f}%")

    all_results[N] = {
        'seeds': NUM_SEEDS,
        'mean_wall_per_seed': mean_wall,
        'wall_times': seed_times,
        'base_error_vs_tm': base_err,
        'check_error_vs_tm': check_err,
        'worst_overall': max(worst_error(base_err), worst_error(check_err)),
        'base_mean': {k: np.atleast_1d(mc_base_mean[k]).tolist() for k in OUTPUT_KEYS},
        'check_mean': {k: np.atleast_1d(mc_check_mean[k]).tolist() for k in OUTPUT_KEYS},
    }

# ============================================================
# Summary + timing predictions
# ============================================================
print(f"\n{'=' * 60}")
print("SUMMARY")
print("=" * 60)

for N, r in sorted(all_results.items()):
    status = "PASS" if r['worst_overall'] < 0.01 else "FAIL"
    print(f"  N={N:>6d}: worst error = {r['worst_overall']*100:.4f}%  [{status}]  "
          f"({r['mean_wall_per_seed']:.0f}s/seed)")

if all_results:
    anchor_N = min(all_results.keys())
    anchor_time = all_results[anchor_N]['mean_wall_per_seed']
    per_agent = anchor_time / anchor_N
    print(f"\n  Timing model: {per_agent*1000:.2f}ms per agent (from N={anchor_N} anchor)")
    for N_pred in [5000, 20000, 50000]:
        if N_pred not in all_results:
            t_pred = per_agent * N_pred
            print(f"  Predicted N={N_pred:>6d}: ~{t_pred:.0f}s/seed × 5 seeds = ~{t_pred*5/60:.1f} min")

# Save
out = {
    'tm_reference': {
        'mCount': 50,
        'time': t_tm,
        'N_tm': N_tm,
        'base_per_capita': {k: np.atleast_1d(tm_base[k]).tolist() for k in OUTPUT_KEYS},
        'check_per_capita': {k: np.atleast_1d(tm_check[k]).tolist() for k in OUTPUT_KEYS},
    },
    'mc_results': {str(k): v for k, v in all_results.items()},
}
out_path = os.path.join(os.getcwd(), 'convergence_results.json')
with open(out_path, 'w') as f:
    json.dump(out, f, indent=2)

total = time() - t_total_start
print(f"\nTotal time: {total:.0f}s ({total/60:.1f} min)")
print(f"Results saved to {out_path}")
