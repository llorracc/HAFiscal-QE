"""
Deep investigation of recessionCheck TM-vs-MC discrepancy.

Runs three experiments:
  A) High-res TM: mCount=200, n_buckets=40
  B) Large MC: 200K agents, 5 seeds (recessionCheck AND plain recession)
  C) Differencing: (recessionCheck - recession) to isolate check effect

Reports per-period and NPV treatment effects for:
  - recessionCheck - base  (the standard TE)
  - recession - base       (recession-only effect)
  - recessionCheck - recession  (isolated check effect within recession)
"""

import os
import sys
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

# --- Setup ---
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
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])
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

AggEco.agents = [BaseType]
BaseType.AgentCount = 1
AggEco.solve()
act_T = AggEco.act_T
base_dict_agg = deepcopy(base_dict)
Rfree = BaseType.Rfree[0]

# Recession path: 3 quarters recession, then expansion
rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
for t in range(3):
    rec_path[t] = rec_path[t] + 1  # odd = recession active
rec_path = rec_path[:act_T]

disc = np.array([1.0 / Rfree**t for t in range(act_T)])

print("=" * 70)
print("DEEP INVESTIGATION: recessionCheck TM-vs-MC")
print(f"  1 highschool type, Reduced_Run, 3-quarter recession")
print(f"  rec_path first 10: {rec_path[:10]}")
print(f"  act_T = {act_T}")
print("=" * 70)

# ============================================================
# EXPERIMENT A: High-resolution TM
# ============================================================
print(f"\n{'='*70}")
print("EXPERIMENT A: High-resolution TM (mCount=200)")
print("=" * 70)

MCOUNT_HI = 200

t0 = time()
bl_data_hi = compute_baseline_tm_data(AggEco, mCount=MCOUNT_HI, verbose=False)

# TM baseline
tm_base_hi = run_experiment_tm(AggEco, shock_type='base', mCount=MCOUNT_HI, verbose=False)

# TM recession (for differencing)
eco_rec_tm = deepcopy(AggEco)
eco_rec_tm.switch_shock_type('recession')
eco_rec_tm.solve()
tm_rec_hi = run_experiment_tm_nonbase(
    eco_rec_tm, 'recession', rec_path, bl_data_hi, mCount=MCOUNT_HI, verbose=False)

# TM recessionCheck — use run_experiment_tm_nonbase for consistent
# base_aPol handling (matching the recession arm).
eco_rc_tm = deepcopy(AggEco)
eco_rc_tm.switch_shock_type('recessionCheck')
eco_rc_tm.solve()

tm_rc_hi = run_experiment_tm_nonbase(
    eco_rc_tm, 'recessionCheck', rec_path, bl_data_hi, mCount=MCOUNT_HI, verbose=False)
result_rc_hi = tm_rc_hi

# Also run standard resolution for comparison
MCOUNT_STD = 50
bl_data_std = compute_baseline_tm_data(AggEco, mCount=MCOUNT_STD, verbose=False)
tm_base_std = run_experiment_tm(AggEco, shock_type='base', mCount=MCOUNT_STD, verbose=False)

eco_rec_tm_std = deepcopy(AggEco)
eco_rec_tm_std.switch_shock_type('recession')
eco_rec_tm_std.solve()
tm_rec_std = run_experiment_tm_nonbase(
    eco_rec_tm_std, 'recession', rec_path, bl_data_std, mCount=MCOUNT_STD, verbose=False)

eco_rc_tm_std = deepcopy(AggEco)
eco_rc_tm_std.switch_shock_type('recessionCheck')
eco_rc_tm_std.solve()
tm_rc_std_r = run_experiment_tm_nonbase(
    eco_rc_tm_std, 'recessionCheck', rec_path, bl_data_std, mCount=MCOUNT_STD, verbose=False)
result_rc_std = tm_rc_std_r

t_tm = time() - t0

# Build TM series
tm_base_cons_hi = np.array(tm_base_hi['AggCons'])
tm_rec_cons_hi = np.array(tm_rec_hi['AggCons'])
tm_rc_cons_hi = np.array(result_rc_hi['AggCons'])
tm_te_rc_hi = tm_rc_cons_hi - tm_base_cons_hi
tm_te_rec_hi = tm_rec_cons_hi - tm_base_cons_hi
tm_te_check_iso_hi = tm_rc_cons_hi - tm_rec_cons_hi

tm_base_cons_std = np.array(tm_base_std['AggCons'])
tm_rec_cons_std = np.array(tm_rec_std['AggCons'])
tm_rc_cons_std = np.array(result_rc_std['AggCons'])
tm_te_rc_std = tm_rc_cons_std - tm_base_cons_std
tm_te_rec_std = tm_rec_cons_std - tm_base_cons_std
tm_te_check_iso_std = tm_rc_cons_std - tm_rec_cons_std

print(f"  TM total time: {t_tm:.0f}s")
print(f"\n  TM convergence check (std vs hi-res):")
print(f"    recessionCheck NPV TE: std={np.sum(tm_te_rc_std*disc):.4f}, hi={np.sum(tm_te_rc_hi*disc):.4f}, diff={np.sum((tm_te_rc_hi-tm_te_rc_std)*disc):.4f}")
print(f"    recession NPV TE:      std={np.sum(tm_te_rec_std*disc):.4f}, hi={np.sum(tm_te_rec_hi*disc):.4f}")
print(f"    isolated check NPV:    std={np.sum(tm_te_check_iso_std*disc):.4f}, hi={np.sum(tm_te_check_iso_hi*disc):.4f}")

# ============================================================
# EXPERIMENT B: Large MC (200K agents, 5 seeds)
# ============================================================
print(f"\n{'='*70}")
print("EXPERIMENT B: Large MC (200K agents, 5 seeds)")
print("=" * 70)

N_MC = 200000
NUM_SEEDS = 5

mc_base_all = []
mc_rec_all = []
mc_rc_all = []

for seed in range(NUM_SEEDS):
    t0s = time()
    print(f"  Seed {seed}/{NUM_SEEDS}...", end=" ", flush=True)

    eco_mc = deepcopy(AggEco)
    for a in eco_mc.agents:
        a.AgentCount = N_MC
        a.seed = seed * 1000
        a.get_economy_data(eco_mc)
    eco_mc.solve()
    eco_mc.reset()
    for a in eco_mc.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0

    # TM-ergodic initialization + warmup
    for i, agent in enumerate(eco_mc.agents):
        bd_i = bl_data_std[i]
        erg = bd_i.get('cohort_ergodic')
        if erg is None:
            erg = bd_i['ergodic']
        grid = bd_i['dist_mGrid']
        M_i = len(grid)
        J_i = agent.num_base_MrkvStates
        rng_i = np.random.RandomState(agent.seed)
        N_i = agent.AgentCount
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

    # MC baseline
    mc_base_r = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
    eco_mc.store_baseline(mc_base_r['AggCons'])

    # MC recession (for differencing)
    eco_mc_rec = deepcopy(eco_mc)
    eco_mc_rec.switch_shock_type('recession')
    eco_mc_rec.solve()
    rec_d = base_dict_agg.copy()
    rec_d.update(recession_changes)
    rec_d['EconomyMrkv_init'] = rec_path
    mc_rec_r = eco_mc_rec.run_experiment(**rec_d, Full_Output=True)

    # MC recessionCheck
    eco_mc_rc = deepcopy(eco_mc)
    eco_mc_rc.switch_shock_type('recessionCheck')
    eco_mc_rc.solve()
    rc_d = base_dict_agg.copy()
    rc_d.update(recession_Check_changes)
    rc_d['EconomyMrkv_init'] = rec_path
    mc_rc_r = eco_mc_rc.run_experiment(**rc_d, Full_Output=True)

    N_actual = sum(a.AgentCount for a in eco_mc.agents)
    mc_base_all.append(np.array(mc_base_r['AggCons']) / N_actual)
    mc_rec_all.append(np.array(mc_rec_r['AggCons']) / N_actual)
    mc_rc_all.append(np.array(mc_rc_r['AggCons']) / N_actual)
    print(f"{time()-t0s:.0f}s (N={N_actual})")

# Compute MC means and per-seed NPVs
mc_base_mean = np.mean(mc_base_all, axis=0)
mc_rec_mean = np.mean(mc_rec_all, axis=0)
mc_rc_mean = np.mean(mc_rc_all, axis=0)

mc_te_rc = mc_rc_mean - mc_base_mean       # recessionCheck - base
mc_te_rec = mc_rec_mean - mc_base_mean      # recession - base
mc_te_check_iso = mc_rc_mean - mc_rec_mean  # isolated check effect

# Per-seed NPVs for error bars
mc_npv_rc_seeds = [np.sum((mc_rc_all[s] - mc_base_all[s]) * disc) for s in range(NUM_SEEDS)]
mc_npv_rec_seeds = [np.sum((mc_rec_all[s] - mc_base_all[s]) * disc) for s in range(NUM_SEEDS)]
mc_npv_check_iso_seeds = [np.sum((mc_rc_all[s] - mc_rec_all[s]) * disc) for s in range(NUM_SEEDS)]

# ============================================================
# RESULTS
# ============================================================
print(f"\n{'='*70}")
print("RESULTS SUMMARY")
print("=" * 70)

def report_comparison(label, tm_te, mc_te, mc_npv_seeds, disc):
    tm_npv = np.sum(tm_te * disc)
    mc_npv = np.sum(mc_te * disc)
    mc_std = np.std(mc_npv_seeds)
    rel = (tm_npv - mc_npv) / abs(mc_npv) * 100 if abs(mc_npv) > 1e-10 else float('nan')
    print(f"\n  {label}:")
    print(f"    NPV:  TM = {tm_npv:>12.4f}   MC = {mc_npv:>12.4f}   rel-err = {rel:>+.2f}%")
    print(f"    MC seed NPVs: {['%.4f' % x for x in mc_npv_seeds]}")
    print(f"    MC std = {mc_std:.4f}   (std/|mean| = {mc_std/abs(mc_npv)*100:.1f}%)" if abs(mc_npv)>1e-10 else f"    MC std = {mc_std:.4f}")
    print(f"    Per-period TE (first 12):")
    print(f"    {'t':>4s} {'TM':>12s} {'MC':>12s} {'rel_err':>10s}")
    for t in range(min(12, len(tm_te))):
        re = (tm_te[t] - mc_te[t]) / mc_te[t] * 100 if abs(mc_te[t]) > 1e-8 else float('nan')
        print(f"    {t:>4d} {tm_te[t]:>12.4f} {mc_te[t]:>12.4f} {re:>+10.1f}%")

print("\n--- Using HIGH-RES TM (mCount=200, n_buckets=40) ---")
report_comparison("recessionCheck - base", tm_te_rc_hi, mc_te_rc, mc_npv_rc_seeds, disc)
report_comparison("recession - base", tm_te_rec_hi, mc_te_rec, mc_npv_rec_seeds, disc)
report_comparison("ISOLATED CHECK (recessionCheck - recession)", tm_te_check_iso_hi, mc_te_check_iso, mc_npv_check_iso_seeds, disc)

print("\n--- Using STANDARD TM (mCount=50, n_buckets=10) for comparison ---")
report_comparison("recessionCheck - base", tm_te_rc_std, mc_te_rc, mc_npv_rc_seeds, disc)
report_comparison("ISOLATED CHECK (recessionCheck - recession)", tm_te_check_iso_std, mc_te_check_iso, mc_npv_check_iso_seeds, disc)

total = time() - t0_total
print(f"\n{'='*70}")
print(f"Total time: {total:.0f}s ({total/60:.1f} min)")
print("=" * 70)
