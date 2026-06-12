"""
Validate Harmenberg neutral measure for TM aggregation.

Compares three approaches for recession treatment effect NPV:
  1. Standard TM (neutral_measure=False)
  2. Neutral-measure TM (neutral_measure=True)
  3. MC (100K agents × 3 seeds)

Under the neutral measure Q, the distribution tracks E_Q[c_nrm] such that
  E_P[p * c_nrm] = E_Q[c_nrm] * E_P[p]
exactly at every period (no covariance error). This eliminates ε_cov,ss and
ε_cov,trans that cause the ~5% raw recession TE error in the standard TM.

See math-derive Section 15.2 and history/20260331-variance-knockdown-diagnosis.md.
"""

import os, sys
import numpy as np
from time import time
from copy import deepcopy

sys.stdout.reconfigure(line_buffering=True)

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
    compute_analytical_mean_pLvl,
)

t0_global = time()

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

edu_inits = [init_highschool]
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
    [np.array([1.0]), np.array([BaseTypeList[0].IncUnemp])]
)
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseTypeList[0].IncUnempNoBenefits])]
)
for ThisType in BaseTypeList:
    EmployedIncShkDstn = deepcopy(ThisType.IncShkDstn[0])
    ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn
    IncShkDstn_recession = [ThisType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
    ThisType.IncShkDstn_recession = IncShkDstn_recession

DiscFac = DiscFacDstns[1].atoms[0][0]
TypeList = [deepcopy(BaseTypeList[0])]
TypeList[0].DiscFac = DiscFac
TypeList[0].seed = 0

AggEco.agents = TypeList
AggEco.solve()
act_T = AggEco.act_T
Rfree = TypeList[0].Rfree[0]
disc = np.array([1.0 / Rfree**t for t in range(act_T)])

rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
for t in range(3):
    rec_path[t] = rec_path[t] + 1
rec_path = rec_path[:act_T]
base_path = [0] * act_T

base_dict_agg = deepcopy(base_dict)

# ---- MC initialization (same as phase0) ----
bl_for_init = compute_baseline_tm_data(AggEco, mCount=50, verbose=False)


def init_mc_from_ergodic(eco_mc, bl_data_init, N_MC, seed):
    for i, agent in enumerate(eco_mc.agents):
        agent.AgentCount = N_MC
        agent.seed = seed * 1000 + i
        agent.get_economy_data(eco_mc)
    eco_mc.solve()
    eco_mc.reset()
    for a in eco_mc.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    for i, agent in enumerate(eco_mc.agents):
        bd_i = bl_data_init[i]
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


def run_mc_recession(eco_template, bl_data_init, N_MC, num_seeds, base_dict_agg):
    mc_npvs = []
    mc_te_all = []
    for seed in range(num_seeds):
        t0s = time()
        eco_mc = deepcopy(eco_template)
        print(f"    seed {seed} (N={N_MC})...", end=" ", flush=True)
        init_mc_from_ergodic(eco_mc, bl_data_init, N_MC, seed)
        eco_mc.save_state()
        eco_mc.switch_to_counterfactual_mode("base")
        eco_mc.act_T = act_T
        for a in eco_mc.agents:
            a.T_sim = act_T
            a.EconomyMrkvNow_hist = [0] * act_T
        eco_mc.make_idiosyncratic_shock_histories()
        mc_base = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
        N_actual = sum(a.AgentCount for a in eco_mc.agents)
        T_out = min(len(mc_base['AggCons']), act_T)
        mc_base_cons = np.array(mc_base['AggCons'][:T_out]) / N_actual
        eco_mc.store_baseline(mc_base['AggCons'])

        eco_rec = deepcopy(eco_mc)
        eco_rec.switch_shock_type("recession")
        eco_rec.solve()
        rec_dict = base_dict_agg.copy()
        rec_dict.update(recession_changes)
        rec_dict['EconomyMrkv_init'] = rec_path
        mc_rec = eco_rec.run_experiment(**rec_dict, Full_Output=True)
        mc_rec_cons = np.array(mc_rec['AggCons'][:T_out]) / N_actual

        te = mc_rec_cons - mc_base_cons
        npv = np.sum(te * disc[:T_out])
        mc_npvs.append(npv)
        mc_te_all.append(te)
        print(f"NPV={npv:.4f}  ({time()-t0s:.0f}s)")
    return np.array(mc_npvs), np.array(mc_te_all)


def run_tm_recession(eco_template, mCount, neutral_measure=False):
    eco_tm = deepcopy(eco_template)
    TM_N = sum(a.AgentCount for a in eco_tm.agents)
    bl_data = compute_baseline_tm_data(eco_tm, mCount=mCount, verbose=False,
                                        neutral_measure=neutral_measure)
    tm_base = run_experiment_tm(eco_tm, shock_type='base', mCount=mCount,
                                verbose=False, neutral_measure=neutral_measure)
    tm_base_cons = np.array(tm_base['AggCons']) / TM_N

    eco_tm2 = deepcopy(eco_template)
    eco_tm2.switch_shock_type("recession")
    eco_tm2.solve()
    tm_rec = run_experiment_tm_nonbase(eco_tm2, "recession", rec_path, bl_data,
                                       mCount=mCount, verbose=False,
                                       neutral_measure=neutral_measure)
    tm_rec_cons = np.array(tm_rec['AggCons']) / TM_N

    T_out = len(tm_base_cons)
    te = tm_rec_cons - tm_base_cons
    npv = np.sum(te * disc[:T_out])
    return npv, te, bl_data


print(f"Setup time: {time()-t0_global:.0f}s")

# ============================================================
# TM: Standard vs Neutral Measure
# ============================================================
print("=" * 70)
print("STANDARD TM vs NEUTRAL MEASURE TM vs MC (100K×3)")
print("=" * 70)

mCount = 100

print("\n[1/3] Standard TM (neutral_measure=False)...")
t0 = time()
tm_std_npv, tm_std_te, _ = run_tm_recession(AggEco, mCount=mCount, neutral_measure=False)
print(f"  NPV = {tm_std_npv:.4f}  ({time()-t0:.0f}s)")

print("\n[2/3] Neutral-measure TM (neutral_measure=True)...")
t0 = time()
tm_nm_npv, tm_nm_te, _ = run_tm_recession(AggEco, mCount=mCount, neutral_measure=True)
print(f"  NPV = {tm_nm_npv:.4f}  ({time()-t0:.0f}s)")

print("\n[3/3] MC (100K × 3 seeds)...")
t0 = time()
mc_npvs, mc_te_all = run_mc_recession(AggEco, bl_for_init, N_MC=100000, num_seeds=3,
                                       base_dict_agg=base_dict_agg)
mc_mean_npv = np.mean(mc_npvs)
mc_std_npv = np.std(mc_npvs)
print(f"  MC mean NPV = {mc_mean_npv:.4f} ± {mc_std_npv:.4f}  ({time()-t0:.0f}s)")

# ============================================================
# Comparison
# ============================================================
rel_err_std = (tm_std_npv - mc_mean_npv) / abs(mc_mean_npv) * 100
rel_err_nm = (tm_nm_npv - mc_mean_npv) / abs(mc_mean_npv) * 100

print(f"\n{'='*70}")
print("NPV COMPARISON")
print(f"{'='*70}")
print(f"  {'Method':<28s} {'NPV':>10s} {'vs MC mean':>12s} {'rel err':>10s}")
print(f"  {'-'*28} {'-'*10} {'-'*12} {'-'*10}")
print(f"  {'Standard TM':<28s} {tm_std_npv:>10.4f} {tm_std_npv - mc_mean_npv:>+12.4f} {rel_err_std:>+9.2f}%")
print(f"  {'Neutral-measure TM':<28s} {tm_nm_npv:>10.4f} {tm_nm_npv - mc_mean_npv:>+12.4f} {rel_err_nm:>+9.2f}%")
print(f"  {'MC mean (100K×3)':<28s} {mc_mean_npv:>10.4f} {'—':>12s} {'—':>10s}")
print(f"  MC std across seeds:  {mc_std_npv:.4f}")

improvement = abs(rel_err_std) - abs(rel_err_nm)
print(f"\n  Improvement: {abs(rel_err_std):.2f}% → {abs(rel_err_nm):.2f}% ({improvement:+.2f}pp)")

# ============================================================
# Per-period decomposition
# ============================================================
mc_te_mean = np.mean(mc_te_all, axis=0)
T_diag = min(len(tm_std_te), len(tm_nm_te), len(mc_te_mean))

print(f"\n{'='*70}")
print("PER-PERIOD TE DECOMPOSITION (first 25 periods)")
print(f"{'='*70}")
print(f"  {'t':>3s} {'TM_std':>10s} {'TM_nm':>10s} {'MC':>10s} {'std-MC':>10s} {'nm-MC':>10s} {'std%':>8s} {'nm%':>8s}")
print(f"  {'-'*3} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
for t in range(min(T_diag, 25)):
    d_std = tm_std_te[t] - mc_te_mean[t]
    d_nm = tm_nm_te[t] - mc_te_mean[t]
    pct_std = d_std / abs(mc_te_mean[t]) * 100 if abs(mc_te_mean[t]) > 1e-10 else float('nan')
    pct_nm = d_nm / abs(mc_te_mean[t]) * 100 if abs(mc_te_mean[t]) > 1e-10 else float('nan')
    print(f"  {t:>3d} {tm_std_te[t]:>10.4f} {tm_nm_te[t]:>10.4f} {mc_te_mean[t]:>10.4f} "
          f"{d_std:>+10.4f} {d_nm:>+10.4f} {pct_std:>+7.1f}% {pct_nm:>+7.1f}%")

if abs(rel_err_nm) < 2.0:
    print(f"\n  RESULT: PASS — neutral measure reduces error to {abs(rel_err_nm):.2f}%")
elif abs(rel_err_nm) < abs(rel_err_std):
    print(f"\n  RESULT: IMPROVED — {abs(rel_err_std):.2f}% → {abs(rel_err_nm):.2f}%")
else:
    print(f"\n  RESULT: NO IMPROVEMENT — neutral measure did not help")

print(f"\nTotal time: {time()-t0_global:.0f}s ({(time()-t0_global)/60:.1f} min)")
