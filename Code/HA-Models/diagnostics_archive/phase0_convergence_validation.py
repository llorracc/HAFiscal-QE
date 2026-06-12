"""
Phase 0: Quick validation with convergence diagnostics for the joint
E[pLvl] level bias + pLvl_factor dynamics fix.

Tests a single highschool type with Reduced_Run, recession experiment only.
Uses ergodic TM-based MC initialization (matching Phase 1's approach)
to avoid MC burn-in discrepancies.

Phase 0a: Smoke test (1 seed, 50K agents)
Phase 0b: MC convergence sweep (50K×3, 100K×3, 100K×6)
Phase 0c: TM grid convergence (mCount = 50, 100, 200)
Phase 0d: Diagnostic output if systematic bias detected
"""

# Math reference: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")

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

# ============================================================
# Load parameters (Reduced_Run, single highschool type)
# ============================================================
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

edu_inits = [init_highschool]
edu_names = ['HighSchool']
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

DiscFac = DiscFacDstns[1].atoms[0][0]  # highschool
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

# Pre-compute TM baseline data (shared across MC seeds for init)
bl_for_init = compute_baseline_tm_data(AggEco, mCount=50, verbose=False)

base_dict_agg = deepcopy(base_dict)


def init_mc_from_ergodic(eco_mc, bl_data_init, N_MC, seed):
    """Initialize MC agents from TM ergodic distribution (matching Phase 1)."""
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
    """Run MC recession with ergodic init, return per-seed NPV treatment effects."""
    mc_npvs = []
    mc_te_all = []
    for seed in range(num_seeds):
        t0s = time()
        eco_mc = deepcopy(eco_template)
        print(f"    seed {seed} (N={N_MC})...", end=" ")
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


def run_tm_recession(eco_template, mCount):
    """Run TM recession experiment, return NPV and per-period treatment effect."""
    eco_tm = deepcopy(eco_template)
    TM_N = sum(a.AgentCount for a in eco_tm.agents)
    bl_data = compute_baseline_tm_data(eco_tm, mCount=mCount, verbose=False)
    tm_base = run_experiment_tm(eco_tm, shock_type='base', mCount=mCount, verbose=False)
    tm_base_cons = np.array(tm_base['AggCons']) / TM_N

    eco_tm2 = deepcopy(eco_template)
    eco_tm2.switch_shock_type("recession")
    eco_tm2.solve()
    tm_rec = run_experiment_tm_nonbase(eco_tm2, "recession", rec_path, bl_data, mCount=mCount, verbose=False)
    tm_rec_cons = np.array(tm_rec['AggCons']) / TM_N

    T_out = len(tm_base_cons)
    te = tm_rec_cons - tm_base_cons
    npv = np.sum(te * disc[:T_out])
    return npv, te, bl_data


print(f"Setup time: {time()-t0_global:.0f}s")

# ============================================================
# Phase 0a: Smoke test
# ============================================================
print("=" * 70)
print("PHASE 0a: SMOKE TEST (1 seed, 50K agents, mCount=100)")
print("=" * 70)
t0 = time()

tm_npv, tm_te, bl_data = run_tm_recession(AggEco, mCount=100)
mc_npvs, mc_te_all = run_mc_recession(AggEco, bl_for_init, N_MC=50000, num_seeds=1,
                                       base_dict_agg=base_dict_agg)

rel_err = (tm_npv - mc_npvs[0]) / abs(mc_npvs[0]) * 100
print(f"  TM NPV:  {tm_npv:.4f}")
print(f"  MC NPV:  {mc_npvs[0]:.4f}")
print(f"  rel-err: {rel_err:+.2f}%")

# E[pLvl] diagnostic
agent0 = AggEco.agents[0]
bd0 = bl_data[0]
u_erg = bd0['u_ergodic']
E_pLvl_corrected = bd0['E_pLvl']
E_pLvl_old = compute_analytical_mean_pLvl(agent0, unemployment_rate=None)
print(f"  E[pLvl] old (G):       {E_pLvl_old:.4f}")
print(f"  E[pLvl] corrected (g): {E_pLvl_corrected:.4f}")
print(f"  u_ergodic:             {u_erg:.4f}")
print(f"  correction ratio:      {E_pLvl_corrected/E_pLvl_old:.6f}")

print(f"  Time: {time()-t0:.0f}s")
print(f"  Smoke test: {'PASS' if abs(rel_err) < 20 else 'FAIL (gross regression)'}")

# ============================================================
# Phase 0b: MC convergence sweep
# ============================================================
print(f"\n{'='*70}")
print("PHASE 0b: MC CONVERGENCE SWEEP (mCount=100 fixed)")
print("=" * 70)

tm_npv_ref = tm_npv

mc_configs = [
    (50000,  3, "50K×3"),
    (100000, 3, "100K×3"),
    (100000, 6, "100K×6 (robustness)"),
]

print(f"\n  TM NPV (mCount=100): {tm_npv_ref:.4f}")
print(f"\n  {'Config':<22s} {'MC mean':>10s} {'MC std':>10s} {'|TM-MC|/|MC|':>14s} {'seeds':>6s}")
print(f"  {'-'*22} {'-'*10} {'-'*10} {'-'*14} {'-'*6}")

mc_convergence_results = {}
for N_MC, n_seeds, label in mc_configs:
    t0 = time()
    mc_npvs, mc_te_all = run_mc_recession(AggEco, bl_for_init, N_MC=N_MC,
                                           num_seeds=n_seeds, base_dict_agg=base_dict_agg)
    mc_mean = np.mean(mc_npvs)
    mc_std = np.std(mc_npvs)
    rel_err = abs(tm_npv_ref - mc_mean) / abs(mc_mean) * 100
    print(f"  {label:<22s} {mc_mean:>10.4f} {mc_std:>10.4f} {rel_err:>13.2f}% {n_seeds:>6d}  ({time()-t0:.0f}s)")
    mc_convergence_results[label] = {
        'mc_mean': mc_mean, 'mc_std': mc_std, 'rel_err': rel_err,
        'mc_npvs': mc_npvs, 'mc_te_all': mc_te_all,
    }

r50 = mc_convergence_results["50K×3"]
r100 = mc_convergence_results["100K×3"]
mc_std_ratio = r50['mc_std'] / max(r100['mc_std'], 1e-10)
print(f"\n  MC std ratio (50K/100K): {mc_std_ratio:.2f} (expect ~sqrt(2)≈1.41)")
print(f"  |TM-MC| 50K: {r50['rel_err']:.2f}%  →  100K: {r100['rel_err']:.2f}%")

systematic_bias_detected = (r100['rel_err'] > 3.0 and
                            abs(r100['rel_err'] - r50['rel_err']) < 1.5)

# ============================================================
# Phase 0c: TM grid convergence
# ============================================================
print(f"\n{'='*70}")
print("PHASE 0c: TM GRID CONVERGENCE (100K×3 MC reference)")
print("=" * 70)

mc_ref_mean = r100['mc_mean']

tm_mcount_configs = [50, 100, 200]
print(f"\n  MC reference NPV (100K×3): {mc_ref_mean:.4f}")
print(f"\n  {'mCount':>8s} {'TM NPV':>10s} {'|TM-MC|/|MC|':>14s}")
print(f"  {'-'*8} {'-'*10} {'-'*14}")

tm_npvs_grid = {}
tm_te_best = None
for mc in tm_mcount_configs:
    t0 = time()
    tm_npv_mc, tm_te_mc, _ = run_tm_recession(AggEco, mCount=mc)
    rel = abs(tm_npv_mc - mc_ref_mean) / abs(mc_ref_mean) * 100
    print(f"  {mc:>8d} {tm_npv_mc:>10.4f} {rel:>13.2f}%  ({time()-t0:.0f}s)")
    tm_npvs_grid[mc] = tm_npv_mc
    if mc == 200:
        tm_te_best = tm_te_mc

tm_change_100_200 = abs(tm_npvs_grid[200] - tm_npvs_grid[100]) / abs(tm_npvs_grid[100]) * 100
print(f"\n  TM change 100→200: {tm_change_100_200:.3f}%")
tm_converged = tm_change_100_200 < 0.5

# ============================================================
# Phase 0 Summary + Diagnostics
# ============================================================
best_mc = mc_convergence_results["100K×6 (robustness)"]
best_rel_err = abs(tm_npvs_grid[200] - best_mc['mc_mean']) / abs(best_mc['mc_mean']) * 100

print(f"\n{'='*70}")
print("PHASE 0 SUMMARY")
print("=" * 70)
print(f"  Best TM NPV (mCount=200):       {tm_npvs_grid[200]:.4f}")
print(f"  Best MC NPV (100K×6):            {best_mc['mc_mean']:.4f} ± {best_mc['mc_std']:.4f}")
print(f"  Residual |TM-MC|/|MC|:           {best_rel_err:.2f}%")
print(f"  TM grid converged (100→200):     {'YES' if tm_converged else 'NO'}")
print(f"  MC std shrinking with N:         {'YES' if mc_std_ratio > 1.2 else 'NO'}")

if systematic_bias_detected:
    print(f"\n  *** SYSTEMATIC BIAS DETECTED ***")
    print(f"  Discrepancy did not shrink from 50K to 100K agents.")

if best_rel_err < 3.0 and tm_converged:
    print(f"\n  PHASE 0: PASS — residual {best_rel_err:.2f}% is within tolerance.")
    print(f"  Safe to proceed to Phase 1.")
elif best_rel_err < 5.0:
    print(f"\n  PHASE 0: MARGINAL — residual {best_rel_err:.2f}%. Check per-period decomposition below.")
else:
    print(f"\n  PHASE 0: NEEDS INVESTIGATION — residual {best_rel_err:.2f}%.")

# Per-period decomposition
print(f"\n  Per-period TE decomposition (TM mCount=200 vs MC 100K×6 mean):")
mc_te_best_mean = np.mean(best_mc['mc_te_all'], axis=0)
n_seeds_best = best_mc['mc_te_all'].shape[0]
mc_te_best_std = np.std(best_mc['mc_te_all'], axis=0) / np.sqrt(n_seeds_best)
T_diag = min(len(tm_te_best), len(mc_te_best_mean))

print(f"  {'t':>4s} {'TM':>10s} {'MC mean':>10s} {'MC SE':>10s} {'TM-MC':>10s} {'|err|/SE':>10s}")
print(f"  {'-'*4} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
for t in range(min(T_diag, 30)):
    diff = tm_te_best[t] - mc_te_best_mean[t]
    se = mc_te_best_std[t] if mc_te_best_std[t] > 1e-12 else float('nan')
    z = abs(diff) / se if se > 1e-12 else float('nan')
    flag = " ***" if z > 3.0 else ""
    print(f"  {t:>4d} {tm_te_best[t]:>10.4f} {mc_te_best_mean[t]:>10.4f} "
          f"{se:>10.4f} {diff:>+10.4f} {z:>10.2f}{flag}")

total_time = time() - t0_global
print(f"\nTotal Phase 0 time: {total_time:.0f}s ({total_time/60:.1f} min)")
