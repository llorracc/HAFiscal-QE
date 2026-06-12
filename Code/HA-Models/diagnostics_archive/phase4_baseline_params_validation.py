"""
Phase 4: TM-vs-MC validation with Baseline parametrization (3 types).

Tests longer horizons (act_T=400, T_age=200) — pLvl_factor drift risk.
Single recession duration, no AD.
"""

# Math reference: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")

import os, sys, gc
import numpy as np
from time import time
from copy import deepcopy

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())
os.environ['MPLBACKEND'] = 'Agg'

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from income_process_sst import effective_perm_shock_periods_for_t_age, effective_pLvl_growth, effective_perm_shock_variance_periods
from tm_methods import (
    compute_baseline_tm_data, run_experiment_tm, run_experiment_tm_nonbase,
)

t0_total = time()

N_MC = 200000
NUM_SEEDS = 3
MCOUNT = 100

# Load Baseline for longer horizons and full parameter set
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Baseline', OutputFor='_Main.py')

edu_names = ['Dropout', 'HighSchool', 'College']
edu_inits = [init_dropout, init_highschool, init_college]

AggEco = AggregateDemandEconomy(**init_ADEconomy)

BaseTypeList = []
for init_params in edu_inits:
    bt = AggFiscalType(**init_params)
    bt.cycles = 0
    BaseTypeList.append(bt)
for bt in BaseTypeList:
    bt.get_economy_data(AggEco)

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
    ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn
    IncShkDstn_recession = [ThisType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
    ThisType.IncShkDstn_recession = IncShkDstn_recession
    ThisType.IncShkDstn_recessionUI = IncShkDstn_recession
    EmployedIncShkDstn_tc = deepcopy(EmployedIncShkDstn)
    EmployedIncShkDstn_tc.atoms[0][1] = EmployedIncShkDstn_tc.atoms[0][1] * ThisType.TaxCutIncFactor
    TaxCutStatesIncShkDstn = [EmployedIncShkDstn_tc] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]
    IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
    for idx in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates):
        IncShkDstn_recessionTaxCut[0][idx] = TaxCutStatesIncShkDstn[np.mod(idx, 4)]
    ThisType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
    ThisType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

# Point beta (DiscFacCount=1), 3 types
TypeList = []
n = 0
for e in range(3):
    DiscFac = DiscFacDstns[e].atoms[0][0]
    AgentCount = int(np.floor(N_MC * data_EducShares[e] * DiscFacDstns[e].pmv[0]))
    ThisType = deepcopy(BaseTypeList[e])
    ThisType.AgentCount = max(AgentCount, 1)
    ThisType.DiscFac = DiscFac
    ThisType.seed = n
    TypeList.append(ThisType)
    n += 1

del BaseTypeList
gc.collect()

AggEco.agents = TypeList
print(f"Solving {len(TypeList)} types (Baseline params)...", flush=True)
t0_s = time()
AggEco.solve()
print(f"  Solved in {time()-t0_s:.0f}s", flush=True)

act_T = AggEco.act_T
base_dict_agg = deepcopy(base_dict)
Rfree = TypeList[0].Rfree[0]
TM_N_total = sum(a.AgentCount for a in TypeList)

rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
for t in range(3):
    rec_path[t] = rec_path[t] + 1
rec_path = rec_path[:act_T]
base_path = [0] * act_T
disc = np.array([1.0 / Rfree**t for t in range(act_T)])

EXPERIMENTS = [
    ('recession',      'recession',      recession_changes,      rec_path),
    ('recessionCheck', 'recessionCheck', recession_Check_changes, rec_path),
    ('Check',          'Check',          Check_changes,           base_path),
]

print("=" * 70)
print("PHASE 4: TM-vs-MC VALIDATION — BASELINE PARAMETRIZATION")
print(f"  Types: 3, Baseline, act_T={act_T}, T_age={TypeList[0].T_age}")
print(f"  num_experiment_periods={num_experiment_periods}")
print(f"  mCount={MCOUNT}, MC agents={N_MC}, seeds={NUM_SEEDS}")
print("=" * 70, flush=True)

# ============================================================
# TM
# ============================================================
print("\n--- TM ---", flush=True)
t0 = time()
bl_data = compute_baseline_tm_data(AggEco, mCount=MCOUNT, verbose=False)
tm_base = run_experiment_tm(AggEco, shock_type='base', mCount=MCOUNT, verbose=False)
tm_base_cons = np.array(tm_base['AggCons']) / TM_N_total
del tm_base
gc.collect()
print(f"  baseline: done", flush=True)

tm_results = {}
for name, shock_type, changes, path in EXPERIMENTS:
    eco_tm = deepcopy(AggEco)
    eco_tm.switch_shock_type(shock_type)
    eco_tm.solve()
    r = run_experiment_tm_nonbase(
        eco_tm, shock_type, path, bl_data, mCount=MCOUNT, verbose=False)
    tm_results[name] = np.array(r['AggCons']) / TM_N_total
    del eco_tm, r
    gc.collect()
    print(f"  {name}: done", flush=True)

t_tm = time() - t0
print(f"TM completed in {t_tm:.0f}s", flush=True)
del bl_data
gc.collect()

# ============================================================
# MC
# ============================================================
print(f"\n--- MC: {N_MC} agents, {NUM_SEEDS} seeds ---", flush=True)

mc_results = {name: [] for name, _, _, _ in EXPERIMENTS}
mc_base_cons_all = []

for seed in range(NUM_SEEDS):
    t0s = time()
    print(f"\n  Seed {seed}:", flush=True)

    eco_mc = deepcopy(AggEco)
    for a in eco_mc.agents:
        a.get_economy_data(eco_mc)
    eco_mc.solve()
    eco_mc.reset()
    for a in eco_mc.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0

    bl_std = compute_baseline_tm_data(AggEco, mCount=50, verbose=False)
    for i, agent in enumerate(eco_mc.agents):
        bd_i = bl_std[i]
        erg = bd_i.get('cohort_ergodic', bd_i['ergodic'])
        grid = bd_i['dist_mGrid']
        M_i = len(grid)
        J_i = agent.num_base_MrkvStates
        rng_i = np.random.RandomState(agent.seed + seed * 10000)
        N_i = agent.AgentCount
        if N_i == 0:
            continue
        flat_probs = erg / np.sum(erg)
        bins = rng_i.choice(len(flat_probs), size=N_i, p=flat_probs)
        agent_j = bins // M_i
        agent_mNrm = grid[bins % M_i]
        sol_i = agent.solution[0]
        agent_aNrm = np.zeros(N_i)
        for j in range(J_i):
            mask = agent_j == j
            if np.any(mask):
                c = sol_i.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
                agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)
        L = agent.LivPrb[0][0]
        T_ag = agent.T_age
        age_probs = np.array([L**(k-1) for k in range(1, T_ag + 1)])
        age_probs /= np.sum(age_probs)
        agent_ages = rng_i.choice(T_ag, size=N_i, p=age_probs) + 1
        pLogMean = agent.pLogInitMean
        pLogStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))
        PermShkDstn_0 = agent.IncShkDstn_base[0][0]
        log_ps = np.log(PermShkDstn_0.atoms[0])
        ps_var = np.dot(PermShkDstn_0.pmv, log_ps**2) - np.dot(PermShkDstn_0.pmv, log_ps)**2
        g_lvl = effective_pLvl_growth(agent, getattr(agent, 'Urate_normal', 0.0))
        effective_emp_periods = effective_perm_shock_periods_for_t_age(
            agent_ages, agent, getattr(agent, 'Urate_normal', 0.0))
        log_pLvl = rng_i.normal(pLogMean, pLogStd, N_i)
        log_pLvl += agent_ages * np.log(g_lvl)
        log_pLvl += effective_emp_periods * (-ps_var / 2.0)
        log_pLvl += rng_i.normal(0, np.sqrt(ps_var * effective_emp_periods))
        agent_pLvl = np.exp(log_pLvl)
        agent.state_now['aNrm'][:] = agent_aNrm
        agent.state_now['pLvl'][:] = agent_pLvl
        agent.shocks['Mrkv'][:] = agent_j
        if hasattr(agent, 't_age') and agent.t_age is not None:
            agent.t_age[:] = agent_ages
        agent.Cratio = 1.0
        agent.state_now['PlvlAgg'] = 1.0
    del bl_std
    gc.collect()

    for t in range(24):
        for agent in eco_mc.agents:
            agent.sim_one_period()

    eco_mc.save_state()
    eco_mc.switch_to_counterfactual_mode("base")
    eco_mc.act_T = act_T
    for a in eco_mc.agents:
        a.T_sim = act_T
        a.EconomyMrkvNow_hist = [0] * act_T
    eco_mc.make_idiosyncratic_shock_histories()

    t0e = time()
    mc_base_r = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
    eco_mc.store_baseline(mc_base_r['AggCons'])
    N_actual = sum(a.AgentCount for a in eco_mc.agents)
    mc_base_cons_all.append(np.array(mc_base_r['AggCons']) / N_actual)
    del mc_base_r
    print(f"    base: {time()-t0e:.0f}s", flush=True)

    for name, shock_type, changes, path in EXPERIMENTS:
        t0e = time()
        eco_mc.switch_shock_type(shock_type)
        exp_d = base_dict_agg.copy()
        exp_d.update(changes)
        exp_d['EconomyMrkv_init'] = path
        mc_r = eco_mc.run_experiment(**exp_d, Full_Output=True)
        mc_results[name].append(np.array(mc_r['AggCons']) / N_actual)
        del mc_r
        gc.collect()
        print(f"    {name}: {time()-t0e:.0f}s", flush=True)

    del eco_mc
    gc.collect()
    print(f"    seed total: {time()-t0s:.0f}s", flush=True)

# ============================================================
# RESULTS
# ============================================================
print(f"\n{'='*70}")
print("PHASE 4 RESULTS: NPV Treatment Effects (Baseline params)")
print(f"  3 types, act_T={act_T}, T_age={TypeList[0].T_age}")
print(f"  N_MC={N_MC}×{NUM_SEEDS} seeds")
print("=" * 70)

print(f"\n  {'Experiment':<20s} {'TM NPV':>10s} {'MC NPV':>10s} {'rel-err':>10s} {'MC std':>10s}")
print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")

for name, shock_type, changes, path in EXPERIMENTS:
    tm_te = tm_results[name] - tm_base_cons
    tm_npv = np.sum(tm_te * disc)
    mc_te_seeds = [mc_results[name][s] - mc_base_cons_all[s] for s in range(NUM_SEEDS)]
    mc_te_mean = np.mean(mc_te_seeds, axis=0)
    mc_npv = np.sum(mc_te_mean * disc)
    mc_npv_seeds = [np.sum(mc_te_seeds[s] * disc) for s in range(NUM_SEEDS)]
    mc_std = np.std(mc_npv_seeds)
    rel = (tm_npv - mc_npv) / abs(mc_npv) * 100 if abs(mc_npv) > 1e-10 else float('nan')
    print(f"  {name:<20s} {tm_npv:>10.4f} {mc_npv:>10.4f} {rel:>+10.2f}% {mc_std:>10.4f}")

# Differenced
if 'recessionCheck' in tm_results and 'recession' in tm_results:
    tm_iso = tm_results['recessionCheck'] - tm_results['recession']
    tm_iso_npv = np.sum(tm_iso * disc)
    mc_iso_seeds = [mc_results['recessionCheck'][s] - mc_results['recession'][s] for s in range(NUM_SEEDS)]
    mc_iso_mean = np.mean(mc_iso_seeds, axis=0)
    mc_iso_npv = np.sum(mc_iso_mean * disc)
    mc_iso_npv_seeds = [np.sum(mc_iso_seeds[s] * disc) for s in range(NUM_SEEDS)]
    mc_iso_std = np.std(mc_iso_npv_seeds)
    rel = (tm_iso_npv - mc_iso_npv) / abs(mc_iso_npv) * 100 if abs(mc_iso_npv) > 1e-10 else float('nan')
    print(f"\n  --- Differenced ---")
    print(f"  {'recCheck-rec':<20s} {tm_iso_npv:>10.4f} {mc_iso_npv:>10.4f} {rel:>+10.2f}% {mc_iso_std:>10.4f}")

# Per-period error at key horizons
print(f"\n  --- Per-period TM-MC error (recession) at key horizons ---")
tm_te_rec = tm_results['recession'] - tm_base_cons
mc_te_rec_mean = np.mean([mc_results['recession'][s] - mc_base_cons_all[s] for s in range(NUM_SEEDS)], axis=0)
for t_check in [0, 10, 50, 100, 200, 300, act_T - 1]:
    if t_check < act_T:
        err = (tm_te_rec[t_check] - mc_te_rec_mean[t_check])
        rel_t = err / abs(mc_te_rec_mean[t_check]) * 100 if abs(mc_te_rec_mean[t_check]) > 1e-12 else float('nan')
        print(f"    t={t_check:3d}: TM={tm_te_rec[t_check]:+.6f}, MC={mc_te_rec_mean[t_check]:+.6f}, err={err:+.6f} ({rel_t:+.1f}%)")

total = time() - t0_total
print(f"\nTotal time: {total:.0f}s ({total/60:.1f} min)")
