"""Minimal diagnostic: compare P-MC vs Q-MC per-period AggCons for base (no recession)."""

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
from tm_methods import compute_baseline_tm_data

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

Splurge = base_dict['Splurge']
edu_inits = [init_dropout, init_highschool, init_college]


def make_q_measure_dstn(dstn):
    perm_atoms = dstn.atoms[0]
    E_perm = np.dot(dstn.pmv, perm_atoms)
    Q_pmv = dstn.pmv * perm_atoms / E_perm
    Q_pmv = Q_pmv / np.sum(Q_pmv)
    return DiscreteDistribution(Q_pmv, dstn.atoms, seed=dstn.seed)


# Build single-type economy (simplest case)
AggEco = AggregateDemandEconomy(**init_ADEconomy)
B = AggFiscalType(**init_college)
B.cycles = 0
B.get_economy_data(AggEco)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([B.IncUnemp])])
IncShkDstn_unemp_nb = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([B.IncUnempNoBenefits])])

B.IncShkDstn = [[B.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nb]]
B.IncShkDstn_base = B.IncShkDstn

df = DiscFacDstns[2].atoms[0][0]
B.DiscFac = df
B.AgentCount = 20000
B.seed = 42

AggEco.agents = [B]
AggEco.solve()
AggEco.act_T = 10

bl_P = compute_baseline_tm_data(AggEco, mCount=50, neutral_measure=False, verbose=False)
bl_Q = compute_baseline_tm_data(AggEco, mCount=50, neutral_measure=True, verbose=False)

# Employed PermShk distribution statistics
emp_dstn = B.IncShkDstn_base[0][0]
perm_atoms = emp_dstn.atoms[0]
E_perm_P = np.dot(emp_dstn.pmv, perm_atoms)
E_perm2_P = np.dot(emp_dstn.pmv, perm_atoms**2)
Q_dstn = make_q_measure_dstn(emp_dstn)
E_perm_Q = np.dot(Q_dstn.pmv, Q_dstn.atoms[0])
print(f"E_P[psi] = {E_perm_P:.6f}")
print(f"E_P[psi^2] = {E_perm2_P:.6f}")
print(f"E_Q[psi] = {E_perm_Q:.6f}")
print(f"PermGroFac = {B.PermGroFac[0][0]:.6f}")
print()

# Run P-MC and Q-MC BASE ONLY (no recession)
base_dict_mc = deepcopy(base_dict)


def run_base(economy, bl_init, N, seed_idx, neutral_measure=False, label="MC"):
    eco = deepcopy(economy)
    agent = eco.agents[0]
    agent.AgentCount = N
    agent.seed = (seed_idx + 1) * 1000
    agent.get_economy_data(eco)

    eco.reset()
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0

    bd = bl_init[0]
    erg = bd.get('cohort_ergodic')
    if erg is None:
        erg = bd['ergodic']
    grid = bd['dist_mGrid']
    M = len(grid)
    J = agent.num_base_MrkvStates
    rng = np.random.RandomState(agent.seed)
    flat_probs = erg / np.sum(erg)
    bins = rng.choice(len(flat_probs), size=N, p=flat_probs)
    agent_j = bins // M
    agent_mNrm = grid[bins % M]
    sol = agent.solution[0]
    agent_aNrm = np.zeros(N)
    for j in range(J):
        mask = agent_j == j
        if np.any(mask):
            c = sol.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
            agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)
    L = agent.LivPrb[0][0]
    T_ag = agent.T_age
    age_probs = np.array([L**(k-1) for k in range(1, T_ag + 1)])
    age_probs /= np.sum(age_probs)
    agent_ages = rng.choice(T_ag, size=N, p=age_probs) + 1
    pLogMean = agent.pLogInitMean
    pLogStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))
    PermShkDstn_0 = agent.IncShkDstn_base[0][0]
    log_ps = np.log(PermShkDstn_0.atoms[0])
    ps_var = np.dot(PermShkDstn_0.pmv, log_ps**2) - np.dot(PermShkDstn_0.pmv, log_ps)**2
    g_lvl = effective_pLvl_growth(agent, getattr(agent, 'Urate_normal', 0.0))
    effective_emp_periods = effective_perm_shock_periods_for_t_age(
        agent_ages, agent, getattr(agent, 'Urate_normal', 0.0))
    log_pLvl = rng.normal(pLogMean, pLogStd, N)
    log_pLvl += agent_ages * np.log(g_lvl)
    log_pLvl += effective_emp_periods * (-ps_var / 2.0)
    log_pLvl += rng.normal(0, np.sqrt(ps_var * effective_emp_periods))
    agent.state_now['aNrm'][:] = agent_aNrm
    agent.state_now['pLvl'][:] = np.exp(log_pLvl)
    agent.shocks['Mrkv'][:] = agent_j
    if hasattr(agent, 't_age') and agent.t_age is not None:
        agent.t_age[:] = agent_ages
    agent.Cratio = 1.0
    agent.state_now['PlvlAgg'] = 1.0

    if neutral_measure:
        agent.IncShkDstn = deepcopy(agent.IncShkDstn_base)
        agent.IncShkDstn[0][0] = make_q_measure_dstn(agent.IncShkDstn[0][0])

    for t in range(24):
        agent.sim_one_period()

    eco.save_state()
    eco.switch_to_counterfactual_mode("base")

    if neutral_measure:
        agent.IncShkDstn = deepcopy(agent.IncShkDstn_base)
        agent.IncShkDstn[0][0] = make_q_measure_dstn(agent.IncShkDstn[0][0])

    eco.make_idiosyncratic_shock_histories()
    r = eco.run_experiment(**base_dict_mc, Full_Output=True)
    return r


N_agents = 20000
print(f"Running P-MC and Q-MC base experiment with N={N_agents}...")
r_P = run_base(AggEco, bl_P, N_agents, seed_idx=0, neutral_measure=False, label="P-MC")
r_Q = run_base(AggEco, bl_Q, N_agents, seed_idx=0, neutral_measure=True, label="Q-MC")

T = 10
print(f"\n{'='*80}")
print(f"  Period |  AggCons_P |  E_P[p]*ΣcNrm_Q |    Ratio |  E_P[p] |  mean_Q(f)")
print(f"{'='*80}")

for t in range(T):
    AggCons_P = r_P['AggCons'][t]
    E_pLvl_P = np.mean(r_P['pLvl_all'][t])
    cNrm_splurge_Q = r_Q['cLvl_all_splurge'][t] / r_Q['pLvl_all'][t]
    sum_cNrm_Q = np.sum(cNrm_splurge_Q)
    AggCons_Q = E_pLvl_P * sum_cNrm_Q
    ratio = AggCons_Q / AggCons_P if AggCons_P != 0 else float('nan')
    mean_f_Q = np.mean(cNrm_splurge_Q)
    print(f"  {t:>4d}   | {AggCons_P:>10.2f} | {AggCons_Q:>16.2f} | {ratio:>8.4f} | {E_pLvl_P:>7.4f} | {mean_f_Q:>9.6f}")

# Also check: does dividing AggCons_P by pLvl give the "right" cNrm_splurge?
print(f"\n{'='*80}")
print(f"Checking f(m) = cLvl_splurge / pLvl")
print(f"  Period |  mean_P(f) |  mean_Q(f) |  E_P[p*f]/E_P[p] |  E_P[p*f]")
print(f"{'='*80}")
for t in range(T):
    f_P = r_P['cLvl_all_splurge'][t] / r_P['pLvl_all'][t]
    f_Q = r_Q['cLvl_all_splurge'][t] / r_Q['pLvl_all'][t]
    E_pf_P = np.mean(r_P['pLvl_all'][t] * f_P)  # = mean(cLvl_splurge_P) = AggCons_P / N
    E_p_P = np.mean(r_P['pLvl_all'][t])
    print(f"  {t:>4d}   | {np.mean(f_P):>10.6f} | {np.mean(f_Q):>10.6f} | {E_pf_P/E_p_P:>17.6f} | {E_pf_P:>9.4f}")

# Check NaN/Inf/zero in Q-MC pLvl
print(f"\nQ-MC pLvl stats:")
for t in [0, 4, 9]:
    p = r_Q['pLvl_all'][t]
    print(f"  t={t}: min={np.min(p):.6f} max={np.max(p):.6f} mean={np.mean(p):.6f} "
          f"nan={np.sum(np.isnan(p))} inf={np.sum(np.isinf(p))} zero={np.sum(p==0)}")

# ============================================================
# Part 2: Recession experiment
# ============================================================
print(f"\n\n{'#'*80}")
print("Part 2: RECESSION EXPERIMENT")
print(f"{'#'*80}")

rec_dstn = [B.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
B.IncShkDstn_recession = rec_dstn
B.IncShkDstn_recessionUI = rec_dstn

rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (AggEco.act_T - num_experiment_periods)
for t in range(3):
    rec_path[t] = rec_path[t] + 1
rec_path = rec_path[:AggEco.act_T]


def run_recession(economy, bl_init, N, seed_idx, neutral_measure=False):
    eco = deepcopy(economy)
    agent = eco.agents[0]
    agent.AgentCount = N
    agent.seed = (seed_idx + 1) * 1000
    agent.get_economy_data(eco)

    eco.reset()
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0

    bd = bl_init[0]
    erg = bd.get('cohort_ergodic')
    if erg is None:
        erg = bd['ergodic']
    grid = bd['dist_mGrid']
    M = len(grid)
    J = agent.num_base_MrkvStates
    rng = np.random.RandomState(agent.seed)
    flat_probs = erg / np.sum(erg)
    bins = rng.choice(len(flat_probs), size=N, p=flat_probs)
    agent_j = bins // M
    agent_mNrm = grid[bins % M]
    sol = agent.solution[0]
    agent_aNrm = np.zeros(N)
    for j in range(J):
        mask = agent_j == j
        if np.any(mask):
            c = sol.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
            agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)
    L = agent.LivPrb[0][0]
    T_ag = agent.T_age
    age_probs = np.array([L**(k-1) for k in range(1, T_ag + 1)])
    age_probs /= np.sum(age_probs)
    agent_ages = rng.choice(T_ag, size=N, p=age_probs) + 1
    pLogMean = agent.pLogInitMean
    pLogStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))
    PermShkDstn_0 = agent.IncShkDstn_base[0][0]
    log_ps = np.log(PermShkDstn_0.atoms[0])
    ps_var = np.dot(PermShkDstn_0.pmv, log_ps**2) - np.dot(PermShkDstn_0.pmv, log_ps)**2
    g_lvl = effective_pLvl_growth(agent, getattr(agent, 'Urate_normal', 0.0))
    effective_emp_periods = effective_perm_shock_periods_for_t_age(
        agent_ages, agent, getattr(agent, 'Urate_normal', 0.0))
    log_pLvl = rng.normal(pLogMean, pLogStd, N)
    log_pLvl += agent_ages * np.log(g_lvl)
    log_pLvl += effective_emp_periods * (-ps_var / 2.0)
    log_pLvl += rng.normal(0, np.sqrt(ps_var * effective_emp_periods))
    agent.state_now['aNrm'][:] = agent_aNrm
    agent.state_now['pLvl'][:] = np.exp(log_pLvl)
    agent.shocks['Mrkv'][:] = agent_j
    if hasattr(agent, 't_age') and agent.t_age is not None:
        agent.t_age[:] = agent_ages
    agent.Cratio = 1.0
    agent.state_now['PlvlAgg'] = 1.0

    if neutral_measure:
        agent.IncShkDstn = deepcopy(agent.IncShkDstn_base)
        agent.IncShkDstn[0][0] = make_q_measure_dstn(agent.IncShkDstn[0][0])

    for t in range(24):
        agent.sim_one_period()

    eco.save_state()
    eco.switch_to_counterfactual_mode("base")

    if neutral_measure:
        agent.IncShkDstn = deepcopy(agent.IncShkDstn_base)
        agent.IncShkDstn[0][0] = make_q_measure_dstn(agent.IncShkDstn[0][0])

    eco.make_idiosyncratic_shock_histories()

    base_r = eco.run_experiment(**base_dict_mc, Full_Output=True)
    eco.store_baseline(base_r['AggCons'])

    eco.switch_shock_type("recession")
    rec_dict = base_dict_mc.copy()
    rec_dict.update(recession_changes)
    rec_dict['EconomyMrkv_init'] = rec_path
    exp_r = eco.run_experiment(**rec_dict, Full_Output=True)

    return base_r, exp_r


print(f"\nRunning P-MC and Q-MC recession (N={N_agents})...")
base_P, exp_P = run_recession(AggEco, bl_P, N_agents, seed_idx=0, neutral_measure=False)
base_Q, exp_Q = run_recession(AggEco, bl_Q, N_agents, seed_idx=0, neutral_measure=True)

print(f"\n{'='*100}")
print(f"Per-period treatment effect comparison (recession)")
print(f"{'='*100}")
print(f"  t | AggC_P_base | AggC_P_exp |   TE_P  | E_P[p]*cNrm_Q_base | E_P[p]*cNrm_Q_exp |  TE_Q   | TE_Q/TE_P")
print(f"{'='*100}")

Rfree = B.Rfree[0]
disc = np.array([1.0 / Rfree**t for t in range(AggEco.act_T)])
npv_P = 0.0
npv_Q = 0.0

for t in range(AggEco.act_T):
    AC_P_base = base_P['AggCons'][t]
    AC_P_exp = exp_P['AggCons'][t]
    TE_P = (AC_P_exp - AC_P_base) / N_agents

    E_pLvl_base_P = np.mean(base_P['pLvl_all'][t])
    E_pLvl_exp_P = np.mean(exp_P['pLvl_all'][t])

    cNrm_Q_base = np.sum(base_Q['cLvl_all_splurge'][t] / base_Q['pLvl_all'][t])
    cNrm_Q_exp = np.sum(exp_Q['cLvl_all_splurge'][t] / exp_Q['pLvl_all'][t])

    AC_Q_base = E_pLvl_base_P * cNrm_Q_base
    AC_Q_exp = E_pLvl_exp_P * cNrm_Q_exp
    TE_Q = (AC_Q_exp - AC_Q_base) / N_agents

    npv_P += disc[t] * TE_P
    npv_Q += disc[t] * TE_Q

    ratio = TE_Q / TE_P if abs(TE_P) > 1e-10 else float('nan')
    if t < 12 or t % 5 == 0:
        print(f"  {t:>2d} | {AC_P_base:>11.1f} | {AC_P_exp:>10.1f} | {TE_P:>7.4f} | {AC_Q_base:>19.1f} | {AC_Q_exp:>17.1f} | {TE_Q:>7.4f} | {ratio:>9.4f}")

print(f"\n  NPV:  P-MC = {npv_P:.4f}   Q-MC = {npv_Q:.4f}   ratio = {npv_Q/npv_P:.4f}")
