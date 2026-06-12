"""
Focused diagnostic for recessionTaxCut isolated error.

The isolated tax cut effect (recessionTaxCut - recession) has a -0.91%
NPV error.  This script runs a detailed per-period comparison to
identify which periods contribute and whether TM grid resolution or
the tax cut window boundary matters.
"""

# Math reference: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")

import os, sys
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
    _tax_cut_employed_factor,
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

EmployedIncShkDstn_tc = deepcopy(EmployedIncShkDstn)
# BUG-023 fix: was `EmployedIncShkDstn_tc.atoms[0][1] = EmployedIncShkDstn_tc.atoms[0][1] * BaseType.TaxCutIncFactor`
# which mutated one PermShk atom; the intended behavior is to
# rescale every joint atom's TranShk component (atoms[1]).
# See BUGS_private/HAFiscal_BUG-023_taxcut_atoms_typo.md.
EmployedIncShkDstn_tc.atoms = (
    np.asarray(EmployedIncShkDstn_tc.atoms[0], dtype=np.float64),
    np.asarray(EmployedIncShkDstn_tc.atoms[1], dtype=np.float64) * BaseType.TaxCutIncFactor,
)
TaxCutStatesIncShkDstn = [EmployedIncShkDstn_tc] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]
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

rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
for t in range(3):
    rec_path[t] = rec_path[t] + 1
rec_path = rec_path[:act_T]

disc = np.array([1.0 / Rfree**t for t in range(act_T)])

J = num_base_MrkvStates
print("=" * 70)
print("RECESSION TAX CUT DIAGNOSTIC")
print(f"  J_micro={J}, TaxCutIncFactor={BaseType.TaxCutIncFactor}")
print(f"  rec_path first 12: {rec_path[:12]}")
print("=" * 70)

# Show tax cut window
print(f"\n  Tax cut window per period:")
for t in range(min(12, act_T)):
    macro_t = rec_path[t]
    emp_tc = _tax_cut_employed_factor(BaseType, macro_t, 'recessionTaxCut')
    mrkv_emp = macro_t * J
    print(f"    t={t}: macro={macro_t}, mrkv_emp={mrkv_emp}, "
          f"TaxCut={'ACTIVE' if emp_tc != 1.0 else 'OFF'} (factor={emp_tc:.4f})")

# Check MC tax cut window from IncShkDstn_recessionTaxCut
print(f"\n  MC IncShkDstn_recessionTaxCut: which combined states have TaxCut?")
for i in range(len(IncShkDstn_recessionTaxCut[0])):
    dstn_i = IncShkDstn_recessionTaxCut[0][i]
    E_tran = np.dot(dstn_i.pmv, dstn_i.atoms[1])
    macro_i = i // J
    micro_i = i % J
    if micro_i == 0 and E_tran > 1.01:
        print(f"    combined={i} (macro={macro_i}, micro={micro_i}): E[TranShk]={E_tran:.4f}")
print(f"  (Only showing employed states with elevated E[TranShk])")

# ============================================================
# TM at two resolutions
# ============================================================
for mcount_label, MCOUNT in [("standard (mCount=100)", 100), ("high-res (mCount=200)", 200)]:
    t0 = time()
    bl = compute_baseline_tm_data(AggEco, mCount=MCOUNT, verbose=False)
    tm_base = run_experiment_tm(AggEco, shock_type='base', mCount=MCOUNT, verbose=False)

    eco_rec = deepcopy(AggEco)
    eco_rec.switch_shock_type('recession')
    eco_rec.solve()
    tm_rec = run_experiment_tm_nonbase(eco_rec, 'recession', rec_path, bl, mCount=MCOUNT, verbose=False)

    eco_rtc = deepcopy(AggEco)
    eco_rtc.switch_shock_type('recessionTaxCut')
    eco_rtc.solve()
    tm_rtc = run_experiment_tm_nonbase(eco_rtc, 'recessionTaxCut', rec_path, bl, mCount=MCOUNT, verbose=False)

    tm_iso = np.array(tm_rtc['AggCons']) - np.array(tm_rec['AggCons'])
    tm_iso_inc = np.array(tm_rtc['AggIncome']) - np.array(tm_rec['AggIncome'])
    print(f"\n  TM {mcount_label}: iso-check NPV C={np.sum(tm_iso*disc):.4f}, "
          f"NPV Y={np.sum(tm_iso_inc*disc):.4f} ({time()-t0:.0f}s)")

# ============================================================
# MC
# ============================================================
N_MC = 200000
NUM_SEEDS = 5

print(f"\nRunning MC: {N_MC} agents, {NUM_SEEDS} seeds...")

mc_rec_all = []
mc_rtc_all = []

for seed in range(NUM_SEEDS):
    t0s = time()
    print(f"  Seed {seed}...", end=" ", flush=True)

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

    bl_init = compute_baseline_tm_data(AggEco, mCount=50, verbose=False)
    for i, agent in enumerate(eco_mc.agents):
        bd_i = bl_init[i]
        erg = bd_i.get('cohort_ergodic', bd_i['ergodic'])
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
    mc_base_r = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
    eco_mc.store_baseline(mc_base_r['AggCons'])

    eco_mc_rec = deepcopy(eco_mc)
    eco_mc_rec.switch_shock_type('recession')
    eco_mc_rec.solve()
    rec_d = base_dict_agg.copy()
    rec_d.update(recession_changes)
    rec_d['EconomyMrkv_init'] = rec_path
    mc_rec_r = eco_mc_rec.run_experiment(**rec_d, Full_Output=True)

    eco_mc_rtc = deepcopy(eco_mc)
    eco_mc_rtc.switch_shock_type('recessionTaxCut')
    eco_mc_rtc.solve()
    rtc_d = base_dict_agg.copy()
    rtc_d.update(recession_TaxCut_changes)
    rtc_d['EconomyMrkv_init'] = rec_path
    mc_rtc_r = eco_mc_rtc.run_experiment(**rtc_d, Full_Output=True)

    N_actual = sum(a.AgentCount for a in eco_mc.agents)
    mc_rec_all.append(np.array(mc_rec_r['AggCons']) / N_actual)
    mc_rtc_all.append(np.array(mc_rtc_r['AggCons']) / N_actual)
    print(f"{time()-t0s:.0f}s")

# Isolated tax cut effect per-period
mc_iso_seeds = [mc_rtc_all[s] - mc_rec_all[s] for s in range(NUM_SEEDS)]
mc_iso_mean = np.mean(mc_iso_seeds, axis=0)
mc_iso_std_per_t = np.std(mc_iso_seeds, axis=0)

mc_iso_npv_seeds = [np.sum(mc_iso_seeds[s] * disc) for s in range(NUM_SEEDS)]
mc_iso_npv = np.mean(mc_iso_npv_seeds)
mc_iso_std = np.std(mc_iso_npv_seeds)

# Use mCount=100 TM for comparison
bl100 = compute_baseline_tm_data(AggEco, mCount=100, verbose=False)
eco_rec100 = deepcopy(AggEco); eco_rec100.switch_shock_type('recession'); eco_rec100.solve()
tm_rec100 = run_experiment_tm_nonbase(eco_rec100, 'recession', rec_path, bl100, mCount=100, verbose=False)
eco_rtc100 = deepcopy(AggEco); eco_rtc100.switch_shock_type('recessionTaxCut'); eco_rtc100.solve()
tm_rtc100 = run_experiment_tm_nonbase(eco_rtc100, 'recessionTaxCut', rec_path, bl100, mCount=100, verbose=False)
tm_iso100 = np.array(tm_rtc100['AggCons']) - np.array(tm_rec100['AggCons'])

tm_iso_npv = np.sum(tm_iso100 * disc)
rel_err = (tm_iso_npv - mc_iso_npv) / abs(mc_iso_npv) * 100

print(f"\n{'='*70}")
print("ISOLATED TAX CUT EFFECT (recessionTaxCut - recession)")
print(f"  NPV: TM={tm_iso_npv:.4f}, MC={mc_iso_npv:.4f}, rel-err={rel_err:+.2f}%")
print(f"  MC seed NPVs: {['%.4f' % x for x in mc_iso_npv_seeds]}")
print(f"  MC std={mc_iso_std:.4f} ({mc_iso_std/abs(mc_iso_npv)*100:.2f}%)")
print("=" * 70)

print(f"\n  Per-period (first 20):")
print(f"  {'t':>4s} {'macro':>6s} {'tc_on':>6s} {'TM':>12s} {'MC':>12s} {'abs_err':>10s} {'rel_err':>10s} {'MC_std':>10s}")
cum_err = 0.0
for t in range(min(20, act_T)):
    macro_t = rec_path[t]
    tc = _tax_cut_employed_factor(BaseType, macro_t, 'recessionTaxCut')
    tc_on = "YES" if tc != 1.0 else "no"
    ae = tm_iso100[t] - mc_iso_mean[t]
    cum_err += ae * disc[t]
    re = ae / mc_iso_mean[t] * 100 if abs(mc_iso_mean[t]) > 1e-8 else float('nan')
    print(f"  {t:>4d} {macro_t:>6d} {tc_on:>6s} {tm_iso100[t]:>12.4f} {mc_iso_mean[t]:>12.4f} {ae:>+10.4f} {re:>+10.1f}% {mc_iso_std_per_t[t]:>10.4f}")

print(f"\n  Cumulative discounted error after t=19: {cum_err:.4f}")
print(f"  Remaining NPV error (t=20+): {(tm_iso_npv - mc_iso_npv) - cum_err:.4f}")

total = time() - t0_total
print(f"\nTotal time: {total:.0f}s ({total/60:.1f} min)")
