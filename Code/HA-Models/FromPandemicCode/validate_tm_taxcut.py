"""
Validate TM TaxCut path against MC — minimal 1-type scenario (Reduced_Run).

Compares per-capita AggCons and AggIncome for TaxCut (no recession) and
optionally recessionTaxCut between MC and TM (mCount=50).

TM baseline uses propagate_experiment_tm(..., EconomyMrkv_init=[0]*act_T)
to match MC baseline (default EconomyMrkv_init -> macro 0).  Do not use
run_experiment_tm('base') stationary averages for difference-in-shocks
against MC, which stays at macro 0 in the baseline run.

Interpretation: after BUG-010, AggIncome levels and treatment effects
should track MC closely; AggCons levels should be within usual TM grid
error (~1–2%). The incremental AggCons *effect* may still differ from MC
because policies were solved with unscaled IncShkDstn on the TranShk
margin (see BUGS_private/HARK+HAFiscal_TM_vs_MC_bug_index.md BUG-010).
"""

import os
import sys
import argparse
import numpy as np
from time import time
from copy import deepcopy

parser = argparse.ArgumentParser()
parser.add_argument('--agents', type=int, default=50000)
parser.add_argument('--seeds', type=int, default=3)
parser.add_argument('--mcount', type=int, default=50)
parser.add_argument(
    '--recession', action='store_true',
    help='Also validate recessionTaxCut (slower: extra solve + TM path)')
args = parser.parse_args()
sys.argv = sys.argv[:1]

cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data,
    run_experiment_tm_nonbase,
    propagate_experiment_tm,
)

N = args.agents
NUM_SEEDS = args.seeds
MCOUNT = args.mcount

print("=" * 60)
print("VALIDATE TM TAXCUT")
print(f"  1 consumer type, N={N}, {NUM_SEEDS} seeds, mCount={MCOUNT}")
print("=" * 60)

t0_total = time()

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

init_dict = init_highschool
BaseType = AggFiscalType(**init_dict)
BaseType.cycles = 0
BaseType.AgentCount = N
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

AggDemandEconomy = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggDemandEconomy)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])

BaseType.IncShkDstn[0].seed = 763607780
BaseType.IncShkDstn[0].reset()

EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
BaseType.IncShkDstn = [[BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
BaseType.IncShkDstn_base = BaseType.IncShkDstn
IncShkDstn_recession = [BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
BaseType.IncShkDstn_recession = IncShkDstn_recession
BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
EmployedIncShkDstn.atoms[0][1] = EmployedIncShkDstn.atoms[0][1] * BaseType.TaxCutIncFactor
TaxCutStatesIncShkDstn = [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]
IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
    IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

AggDemandEconomy.agents = [BaseType]

AggDemandEconomy.solve()
act_T = AggDemandEconomy.act_T
base_dict_agg = deepcopy(base_dict)

def mrkv_path_no_recession(eco):
    return list(np.arange(1, eco.num_experiment_periods + 1) * 2) + [0] * 20


def max_rel_error(val, ref):
    val, ref = np.atleast_1d(val), np.atleast_1d(ref)
    mask = np.abs(ref) > 1e-12
    if not np.any(mask):
        return 0.0
    return float(np.max(np.abs(val[mask] - ref[mask]) / np.abs(ref[mask])))


def run_one_scenario(label, shock_type, changes_dict, tm_eco, mc_eco_base):
    """TM + MC for baseline vs shock_type; print comparison."""
    print(f"\n{'='*60}")
    print(f"SCENARIO: {label}")
    print("=" * 60)
    print(f"  TaxCutIncFactor = {BaseType.TaxCutIncFactor}")

    t0 = time()
    baseline_tm_data = compute_baseline_tm_data(
        tm_eco, mCount=MCOUNT, verbose=False)
    bd0 = baseline_tm_data[0]
    base_agent = tm_eco.agents[0]
    # MC baseline uses default EconomyMrkv_init -> macro 0 all periods; match with TM path
    zero_path = [0] * act_T
    tm_base_res = propagate_experiment_tm(
        base_agent, bd0['ergodic'], zero_path, bd0['dist_mGrid'],
        bd0['E_pLvl'], Cratio=1.0, act_T=act_T, neutral_measure=False,
        check_info=None,
        base_aPol=bd0.get('base_aPol'),
    )

    eco_tm = deepcopy(tm_eco)
    eco_tm.switch_shock_type(shock_type)
    eco_tm.solve()
    path = mrkv_path_no_recession(eco_tm)
    tm_shock = run_experiment_tm_nonbase(
        eco_tm, shock_type, path, baseline_tm_data, mCount=MCOUNT, verbose=True)
    print(f"  TM wall time: {time()-t0:.1f}s")

    N_tm = BaseType.AgentCount
    tm_base_pc = {k: np.asarray(tm_base_res[k]) / N_tm for k in ['AggCons', 'AggIncome']}
    tm_shock_pc = {k: np.asarray(tm_shock[k]) / N_tm for k in ['AggCons', 'AggIncome']}

    # Find a period in the tax-cut window (employed + tax cut in MC)
    # For no-recession TaxCut, macro states 2,4,... are "experiment" even periods
    tax_t = 1  # period index 1 often in tax-cut window; also report max error

    print(f"\n  MC ({NUM_SEEDS} seeds)...")

    def run_mc(seed):
        t_mc = time()
        eco = deepcopy(mc_eco_base)
        for a in eco.agents:
            a.AgentCount = N
            a.seed = seed * 1000
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
        base_r = eco.run_experiment(**base_dict_agg, Full_Output=True)
        eco.store_baseline(base_r['AggCons'])
        eco_x = deepcopy(eco)
        eco_x.switch_shock_type(
            'TaxCut' if shock_type == 'TaxCut' else 'recessionTaxCut')
        eco_x.solve()
        d = base_dict_agg.copy()
        d.update(changes_dict)
        d['EconomyMrkv_init'] = path
        shock_r = eco_x.run_experiment(**d, Full_Output=True)
        N_act = sum(a.AgentCount for a in eco.agents)
        base_pc = {k: np.asarray(base_r[k]) / N_act for k in ['AggCons', 'AggIncome']}
        shock_pc = {k: np.asarray(shock_r[k]) / N_act for k in ['AggCons', 'AggIncome']}
        return base_pc, shock_pc, time() - t_mc

    mc_base_all = []
    mc_shock_all = []
    for s in range(NUM_SEEDS):
        print(f"    Seed {s}/{NUM_SEEDS}...", end=" ", flush=True)
        bp, sp, wt = run_mc(s)
        mc_base_all.append(bp)
        mc_shock_all.append(sp)
        print(f"{wt:.1f}s")

    mc_base_m = {k: np.mean([r[k] for r in mc_base_all], axis=0) for k in ['AggCons', 'AggIncome']}
    mc_shock_m = {k: np.mean([r[k] for r in mc_shock_all], axis=0) for k in ['AggCons', 'AggIncome']}

    print(f"\n  --- Levels (period 0) ---")
    print(f"  Baseline AggCons/cap: TM={tm_base_pc['AggCons'][0]:.6f} MC={mc_base_m['AggCons'][0]:.6f}")
    print(f"  Shock    AggCons/cap: TM={tm_shock_pc['AggCons'][0]:.6f} MC={mc_shock_m['AggCons'][0]:.6f}")

    print(f"\n  --- TM vs MC max rel error (full path) ---")
    for name, tm_pc, mc_pc in [
        ("Baseline", tm_base_pc, mc_base_m),
        (label, tm_shock_pc, mc_shock_m),
    ]:
        print(f"    {name}:")
        for k in ['AggCons', 'AggIncome']:
            err = max_rel_error(mc_pc[k], tm_pc[k])
            print(f"      {k}: {err*100:.4f}%")

    tm_fx = {k: tm_shock_pc[k] - tm_base_pc[k] for k in ['AggCons', 'AggIncome']}
    mc_fx = {k: mc_shock_m[k] - mc_base_m[k] for k in ['AggCons', 'AggIncome']}
    print(f"\n  --- Treatment effect (shock - baseline) ---")
    for k in ['AggCons', 'AggIncome']:
        # max rel error on effect vector
        te_tm = tm_fx[k]
        te_mc = mc_fx[k]
        err_fx = max_rel_error(te_mc, te_tm)
        print(f"    {k} effect max-rel vs TM: {err_fx*100:.4f}%")
        if len(te_tm) > 0:
            print(f"    {k}[0]: TM={te_tm[0]:.6f} MC={te_mc[0]:.6f} "
                  f"(rel {abs(te_mc[0]-te_tm[0])/max(abs(te_tm[0]),1e-12)*100:.2f}%)")


# TaxCut (no recession)
run_one_scenario(
    'TaxCut', 'TaxCut', TaxCut_changes,
    deepcopy(AggDemandEconomy), deepcopy(AggDemandEconomy))

if args.recession:
    run_one_scenario(
        'recessionTaxCut', 'recessionTaxCut', recession_TaxCut_changes,
        deepcopy(AggDemandEconomy), deepcopy(AggDemandEconomy))

print(f"\nTotal time: {time()-t0_total:.0f}s ({(time()-t0_total)/60:.1f} min)")
