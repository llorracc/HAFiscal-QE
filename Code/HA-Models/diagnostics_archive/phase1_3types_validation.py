"""
Phase 1: Full 3-type TM-vs-MC validation (Reduced_Run).

Extends Phase 0 (single highschool type, recession only) to all 3 education
types (dropout, highschool, college) with point discount factors, testing
4 recession experiments and 3 differenced policy effects.

Experiments:
  - recession (reference)
  - recessionUI (UI extension)
  - recessionTaxCut (tax cut)
  - recessionCheck (stimulus check)

Differenced policy effects (isolating the policy within the recession):
  - UI extension   = recessionUI NPV - recession NPV
  - Tax cut        = recessionTaxCut NPV - recession NPV
  - Check          = recessionCheck NPV - recession NPV

MC: 100K agents × 3 seeds (ergodic TM init + 24-period burn-in)
TM: mCount=100
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
)

t0_total = time()

# ============================================================
# Configuration
# ============================================================
N_MC = 100000
NUM_SEEDS = 3
MCOUNT = 100

# ============================================================
# Load parameters (Reduced_Run, all 3 education types)
# ============================================================
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

edu_names = ['Dropout', 'HighSchool', 'College']
edu_inits = [init_dropout, init_highschool, init_college]

# ============================================================
# Build 3 education types (mirrors Simulate.py)
# ============================================================
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

    TaxCutStatesIncShkDstn = [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]
    IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
    for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
        IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
    ThisType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut

    ThisType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

# Point discount factor per education type
num_types = 3
TypeList = []
for e in range(num_types):
    disc_fac_atoms = DiscFacDstns[e].atoms[0]
    df = disc_fac_atoms[0]
    ThisType = deepcopy(BaseTypeList[e])
    ThisType.AgentCount = int(np.floor(AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[0]))
    ThisType.AgentCount = max(ThisType.AgentCount, 1)
    ThisType.DiscFac = df
    ThisType.seed = e
    TypeList.append(ThisType)

AggEco.agents = TypeList
AggEco.solve()

act_T = AggEco.act_T
base_dict_agg = deepcopy(base_dict)
Rfree = TypeList[0].Rfree[0]
disc = np.array([1.0 / Rfree**t for t in range(act_T)])
TM_N_total = sum(a.AgentCount for a in TypeList)

rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
for t in range(3):
    rec_path[t] = rec_path[t] + 1
rec_path = rec_path[:act_T]

EXPERIMENTS = [
    ('recession',       'recession',       recession_changes),
    ('recessionUI',     'recessionUI',     recession_UI_changes),
    ('recessionTaxCut', 'recessionTaxCut', recession_TaxCut_changes),
    ('recessionCheck',  'recessionCheck',  recession_Check_changes),
]

print("=" * 70)
print("PHASE 1: FULL 3-TYPE VALIDATION")
print(f"  Types: {num_types} ({', '.join(edu_names)}), point beta, Reduced_Run")
print(f"  act_T={act_T}, mCount={MCOUNT}, MC agents={N_MC}, seeds={NUM_SEEDS}")
for e, agent in enumerate(TypeList):
    share = data_EducShares[e]
    print(f"    {edu_names[e]:>12s}: beta={agent.DiscFac:.4f}, "
          f"PermGroFac={agent.PermGroFac[0][0]:.4f}, "
          f"share={share:.3f}, N={agent.AgentCount}")
print(f"  Experiments: {[e[0] for e in EXPERIMENTS]}")
print(f"  Setup time: {time()-t0_total:.0f}s")
print("=" * 70)


# ============================================================
# TM experiments
# ============================================================
print("\n--- TM (mCount=%d) ---" % MCOUNT)
t0_tm = time()

bl_data = compute_baseline_tm_data(AggEco, mCount=MCOUNT, verbose=False)
tm_base = run_experiment_tm(AggEco, shock_type='base', mCount=MCOUNT, verbose=False)
tm_base_cons = np.array(tm_base['AggCons']) / TM_N_total

tm_results = {}
for name, shock_type, changes in EXPERIMENTS:
    t0e = time()
    eco_tm = deepcopy(AggEco)
    eco_tm.switch_shock_type(shock_type)
    eco_tm.solve()
    r = run_experiment_tm_nonbase(
        eco_tm, shock_type, rec_path, bl_data, mCount=MCOUNT, verbose=False)
    cons = np.array(r['AggCons']) / TM_N_total
    te = cons - tm_base_cons
    npv = np.sum(te * disc)
    tm_results[name] = {'AggCons': cons, 'te': te, 'npv': npv}
    print(f"  {name:<20s} NPV={npv:+.4f}  ({time()-t0e:.0f}s)")

t_tm = time() - t0_tm
print(f"TM total: {t_tm:.0f}s")


# ============================================================
# MC experiments (ergodic TM init + burn-in)
# ============================================================
print(f"\n--- MC: {N_MC} agents × {NUM_SEEDS} seeds ---")

bl_for_init = compute_baseline_tm_data(AggEco, mCount=50, verbose=False)

mc_results = {name: [] for name, _, _ in EXPERIMENTS}
mc_base_cons_all = []

for seed in range(NUM_SEEDS):
    t0s = time()
    print(f"  Seed {seed}:", flush=True)

    eco_mc = deepcopy(AggEco)

    # Set per-type agent counts proportional to education shares
    for e_idx, a in enumerate(eco_mc.agents):
        mc_n = int(np.floor(N_MC * data_EducShares[e_idx]))
        a.AgentCount = max(mc_n, 10)
        a.seed = seed * 1000 + e_idx
        a.get_economy_data(eco_mc)

    eco_mc.solve()
    eco_mc.reset()
    for a in eco_mc.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0

    # Initialize from TM ergodic distribution
    for i, agent in enumerate(eco_mc.agents):
        bd_i = bl_for_init[i]
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
        age_probs = np.array([L**(k - 1) for k in range(1, T_ag + 1)])
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

    # 24-period burn-in
    for t in range(24):
        for agent in eco_mc.agents:
            agent.sim_one_period()

    # Save state, switch to base for counterfactual
    eco_mc.save_state()
    eco_mc.switch_to_counterfactual_mode("base")
    eco_mc.act_T = act_T
    for a in eco_mc.agents:
        a.T_sim = act_T
        a.EconomyMrkvNow_hist = [0] * act_T
    eco_mc.make_idiosyncratic_shock_histories()

    # Run base experiment
    mc_base_r = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
    N_actual = sum(a.AgentCount for a in eco_mc.agents)
    T_out = min(len(mc_base_r['AggCons']), act_T)
    mc_base_cons = np.array(mc_base_r['AggCons'][:T_out]) / N_actual
    eco_mc.store_baseline(mc_base_r['AggCons'])
    mc_base_cons_all.append(mc_base_cons)

    # Run each recession experiment
    for name, shock_type, changes in EXPERIMENTS:
        t0e = time()
        eco_exp = deepcopy(eco_mc)
        eco_exp.switch_shock_type(shock_type)
        eco_exp.solve()
        exp_d = base_dict_agg.copy()
        exp_d.update(changes)
        exp_d['EconomyMrkv_init'] = rec_path
        mc_r = eco_exp.run_experiment(**exp_d, Full_Output=True)
        mc_exp_cons = np.array(mc_r['AggCons'][:T_out]) / N_actual
        te = mc_exp_cons - mc_base_cons
        npv = np.sum(te * disc[:T_out])
        mc_results[name].append({'cons': mc_exp_cons, 'te': te, 'npv': npv})
        print(f"    {name:<20s} NPV={npv:+.4f}  ({time()-t0e:.0f}s)")

    print(f"    Seed {seed} total: {time()-t0s:.0f}s")


# ============================================================
# Results: Raw experiments (treatment effect = experiment - base)
# ============================================================
print(f"\n{'='*70}")
print("PHASE 1: FULL 3-TYPE VALIDATION")
print("=" * 70)
print(f"\n  {'Experiment':<20s} {'TM NPV':>10s} {'MC mean':>10s} {'MC std':>10s} {'|TM-MC|/|MC|':>14s}")
print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*14}")

raw_pass = True
for name, shock_type, changes in EXPERIMENTS:
    tm_npv = tm_results[name]['npv']
    mc_npvs = [mc_results[name][s]['npv'] for s in range(NUM_SEEDS)]
    mc_mean = np.mean(mc_npvs)
    mc_std = np.std(mc_npvs)
    rel_err = abs(tm_npv - mc_mean) / abs(mc_mean) * 100 if abs(mc_mean) > 1e-10 else float('nan')
    flag = ""
    if rel_err > 10:
        flag = " ***FAIL***"
        raw_pass = False
    print(f"  {name:<20s} {tm_npv:>10.4f} {mc_mean:>10.4f} {mc_std:>10.4f} {rel_err:>13.2f}%{flag}")


# ============================================================
# Results: Differenced policy effects (vs recession)
# ============================================================
print(f"\nDIFFERENCED POLICY EFFECTS (vs recession):")
print(f"  {'Policy':<20s} {'TM NPV':>10s} {'MC mean':>10s} {'MC std':>10s} {'|TM-MC|/|MC|':>14s}")
print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*14}")

diff_labels = {
    'recessionUI':      'UI extension',
    'recessionTaxCut':  'Tax cut',
    'recessionCheck':   'Check',
}

diff_pass = True
diff_marginal = False
for name, shock_type, changes in EXPERIMENTS:
    if name == 'recession':
        continue

    tm_diff_npv = tm_results[name]['npv'] - tm_results['recession']['npv']

    mc_diff_npvs = []
    for s in range(NUM_SEEDS):
        mc_diff = mc_results[name][s]['npv'] - mc_results['recession'][s]['npv']
        mc_diff_npvs.append(mc_diff)
    mc_diff_mean = np.mean(mc_diff_npvs)
    mc_diff_std = np.std(mc_diff_npvs)
    rel_err = abs(tm_diff_npv - mc_diff_mean) / abs(mc_diff_mean) * 100 if abs(mc_diff_mean) > 1e-10 else float('nan')

    label = diff_labels.get(name, name)
    flag = ""
    if rel_err > 5:
        flag = " ***FAIL***"
        diff_pass = False
    elif rel_err > 3:
        flag = " (MARGINAL)"
        diff_marginal = True
    print(f"  {label:<20s} {tm_diff_npv:>10.4f} {mc_diff_mean:>10.4f} {mc_diff_std:>10.4f} {rel_err:>13.2f}%{flag}")


# ============================================================
# Summary
# ============================================================
total_time = time() - t0_total
print(f"\n{'='*70}")
print("PHASE 1 SUMMARY")
print("=" * 70)
print(f"  Raw experiments (< 10% = PASS):        {'PASS' if raw_pass else 'FAIL'}")
print(f"  Differenced effects (< 3% = PASS):     ", end="")
if diff_pass and not diff_marginal:
    print("PASS")
elif diff_pass and diff_marginal:
    print("MARGINAL (< 5% but > 3%)")
else:
    print("FAIL (> 5%)")

overall = raw_pass and diff_pass
print(f"  Overall:                               {'PASS' if overall else 'FAIL'}")
print(f"\nTotal time: {total_time:.0f}s ({total_time/60:.1f} min)")
