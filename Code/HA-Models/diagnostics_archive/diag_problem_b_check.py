"""
Diagnose Problem B: isolated check effect (recessionCheck - recession).

Hypothesis: the 11% error in investigate_recession_check.py was caused by
asymmetric initialization -- the recession arm used base_aPol (via
run_experiment_tm_nonbase) but the recessionCheck arm called
propagate_experiment_tm directly without base_aPol.

This script runs BOTH arms through run_experiment_tm_nonbase for
consistent treatment, then compares the isolated check effect to MC.
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

print("=" * 70)
print("PROBLEM B DIAGNOSIS: isolated check (recessionCheck - recession)")
print("  Both TM arms via run_experiment_tm_nonbase (consistent base_aPol)")
print("=" * 70)

# ============================================================
# TM: both arms through run_experiment_tm_nonbase
# ============================================================
MCOUNT = 100
t0 = time()

bl_data = compute_baseline_tm_data(AggEco, mCount=MCOUNT, verbose=False)
tm_base = run_experiment_tm(AggEco, shock_type='base', mCount=MCOUNT, verbose=False)

# TM recession
eco_rec = deepcopy(AggEco)
eco_rec.switch_shock_type('recession')
eco_rec.solve()
tm_rec = run_experiment_tm_nonbase(
    eco_rec, 'recession', rec_path, bl_data, mCount=MCOUNT, verbose=False)

# TM recessionCheck -- ALSO through run_experiment_tm_nonbase
eco_rc = deepcopy(AggEco)
eco_rc.switch_shock_type('recessionCheck')
eco_rc.solve()
tm_rc = run_experiment_tm_nonbase(
    eco_rc, 'recessionCheck', rec_path, bl_data, mCount=MCOUNT, verbose=False)

t_tm = time() - t0

tm_base_cons = np.array(tm_base['AggCons'])
tm_rec_cons = np.array(tm_rec['AggCons'])
tm_rc_cons = np.array(tm_rc['AggCons'])

tm_te_rec = tm_rec_cons - tm_base_cons
tm_te_rc = tm_rc_cons - tm_base_cons
tm_te_iso = tm_rc_cons - tm_rec_cons

print(f"\nTM completed in {t_tm:.0f}s")
print(f"  recession NPV TE:      {np.sum(tm_te_rec * disc):.4f}")
print(f"  recessionCheck NPV TE: {np.sum(tm_te_rc * disc):.4f}")
print(f"  isolated check NPV:    {np.sum(tm_te_iso * disc):.4f}")

# ============================================================
# MC: 200K agents, 5 seeds
# ============================================================
N_MC = 200000
NUM_SEEDS = 5

print(f"\nRunning MC: {N_MC} agents, {NUM_SEEDS} seeds...")

mc_base_all = []
mc_rec_all = []
mc_rc_all = []

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

    bl_std = compute_baseline_tm_data(AggEco, mCount=50, verbose=False)
    for i, agent in enumerate(eco_mc.agents):
        bd_i = bl_std[i]
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
    print(f"{time()-t0s:.0f}s")

mc_base_mean = np.mean(mc_base_all, axis=0)
mc_rec_mean = np.mean(mc_rec_all, axis=0)
mc_rc_mean = np.mean(mc_rc_all, axis=0)

mc_te_rec = mc_rec_mean - mc_base_mean
mc_te_rc = mc_rc_mean - mc_base_mean
mc_te_iso = mc_rc_mean - mc_rec_mean

mc_npv_rec_seeds = [np.sum((mc_rec_all[s] - mc_base_all[s]) * disc) for s in range(NUM_SEEDS)]
mc_npv_rc_seeds = [np.sum((mc_rc_all[s] - mc_base_all[s]) * disc) for s in range(NUM_SEEDS)]
mc_npv_iso_seeds = [np.sum((mc_rc_all[s] - mc_rec_all[s]) * disc) for s in range(NUM_SEEDS)]

# ============================================================
# RESULTS
# ============================================================
print(f"\n{'='*70}")
print("RESULTS")
print("=" * 70)

def report(label, tm_te, mc_te, mc_seeds, disc):
    tm_npv = np.sum(tm_te * disc)
    mc_npv = np.sum(mc_te * disc)
    mc_std = np.std(mc_seeds)
    rel = (tm_npv - mc_npv) / abs(mc_npv) * 100 if abs(mc_npv) > 1e-10 else float('nan')
    print(f"\n  {label}:")
    print(f"    NPV:  TM = {tm_npv:>10.4f}   MC = {mc_npv:>10.4f}   rel-err = {rel:>+.2f}%")
    print(f"    MC seeds: {['%.4f' % x for x in mc_seeds]}  std={mc_std:.4f}")
    print(f"    Per-period (first 15):")
    print(f"    {'t':>4s} {'TM':>12s} {'MC':>12s} {'rel_err':>10s}")
    for t in range(min(15, len(tm_te))):
        re = (tm_te[t] - mc_te[t]) / mc_te[t] * 100 if abs(mc_te[t]) > 1e-8 else float('nan')
        print(f"    {t:>4d} {tm_te[t]:>12.4f} {mc_te[t]:>12.4f} {re:>+10.1f}%")

report("recession - base", tm_te_rec, mc_te_rec, mc_npv_rec_seeds, disc)
report("recessionCheck - base", tm_te_rc, mc_te_rc, mc_npv_rc_seeds, disc)
report("ISOLATED CHECK (recessionCheck - recession)", tm_te_iso, mc_te_iso, mc_npv_iso_seeds, disc)

total = time() - t0_total
print(f"\nTotal time: {total:.0f}s ({total/60:.1f} min)")
