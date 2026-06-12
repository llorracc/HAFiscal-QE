"""
Diagnostic: What is the TM vs MC error by period?
Is the 3% "max-rel-error" just the worst period, with most periods much better?
"""

# Math reference: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")

import os, sys, numpy as np
from copy import deepcopy
from time import time

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
from tm_methods import compute_baseline_tm_data, run_experiment_tm

# Setup (same as validate_tm_check.py)
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
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

N = 200000
MCOUNT = 100

AggDemandEconomy = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggDemandEconomy)

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

AggDemandEconomy.agents = [BaseType]
BaseType.AgentCount = 1
AggDemandEconomy.solve()

act_T = AggDemandEconomy.act_T
base_dict_agg = deepcopy(base_dict)

# TM baseline (AgentCount=1, so already per-capita)
baseline_tm_data = compute_baseline_tm_data(AggDemandEconomy, mCount=MCOUNT, verbose=False)
tm_base = run_experiment_tm(AggDemandEconomy, shock_type="base", mCount=MCOUNT, verbose=False)
tm_AggCons_pc = np.array(tm_base['AggCons'])  # per-capita since AgentCount=1

# MC baseline with TM ergodic init
def run_mc_baseline(seed):
    eco = deepcopy(AggDemandEconomy)
    for a in eco.agents:
        a.AgentCount = N
        a.seed = seed
        a.get_economy_data(eco)
    eco.solve()
    eco.reset()
    for a in eco.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0

    # TM ergodic init
    bd = baseline_tm_data[0]
    agent = eco.agents[0]
    erg = bd['ergodic']
    grid = bd['dist_mGrid']
    M = len(grid)
    J = agent.num_base_MrkvStates

    rng = np.random.RandomState(seed)
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
    agent_pLvl = np.exp(log_pLvl)

    agent.state_now['aNrm'][:] = agent_aNrm
    agent.state_now['pLvl'][:] = agent_pLvl
    agent.shocks['Mrkv'][:] = agent_j
    agent.t_age[:] = agent_ages
    agent.Cratio = 1.0
    agent.state_now['PlvlAgg'] = 1.0

    for t in range(24):
        agent.sim_one_period()

    eco.save_state()
    eco.switch_to_counterfactual_mode("base")
    eco.act_T = act_T
    for a in eco.agents:
        a.T_sim = act_T
        a.EconomyMrkvNow_hist = [0] * act_T
    eco.make_idiosyncratic_shock_histories()

    base_r = eco.run_experiment(**base_dict_agg, Full_Output=True)
    return np.array(base_r['AggCons'])

print("=" * 70)
print(f"ERROR BY PERIOD (N={N}, mCount={MCOUNT})")
print("=" * 70)

# Run MC with 3 seeds
mc_results = []
for seed in [42000, 42001, 42002]:
    print(f"Running seed {seed}...", flush=True)
    mc_results.append(run_mc_baseline(seed))

mc_AggCons_mean = np.mean(mc_results, axis=0)
mc_AggCons_std = np.std(mc_results, axis=0)

# Per-period relative error
# MC results are already per-capita (divided by N in run_mc_baseline)
# TM results are per-capita since AgentCount=1
mc_AggCons_pc = mc_AggCons_mean / N  # convert to per-capita
mc_AggCons_std_pc = mc_AggCons_std / N

rel_error = (mc_AggCons_pc - tm_AggCons_pc) / tm_AggCons_pc * 100

print(f"\n{'Period':>6s} {'TM/cap':>12s} {'MC/cap':>12s} {'MC std':>10s} {'Rel Err %':>10s}")
print("-" * 55)
for t in range(min(20, act_T)):
    print(f"{t:>6d} {tm_AggCons_pc[t]:>12.4f} {mc_AggCons_pc[t]:>12.4f} {mc_AggCons_std_pc[t]:>10.4f} {rel_error[t]:>+10.3f}")

print(f"\n{'...':>6s}")
for t in range(act_T - 5, act_T):
    print(f"{t:>6d} {tm_AggCons_pc[t]:>12.4f} {mc_AggCons_pc[t]:>12.4f} {mc_AggCons_std_pc[t]:>10.4f} {rel_error[t]:>+10.3f}")

print(f"\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  Mean relative error:   {np.mean(rel_error):+.3f}%")
print(f"  Std of relative error: {np.std(rel_error):.3f}%")
print(f"  Max relative error:    {np.max(np.abs(rel_error)):+.3f}% (period {np.argmax(np.abs(rel_error))})")
print(f"  Period 0 error:        {rel_error[0]:+.3f}%")
print(f"  Period 1-10 mean:      {np.mean(rel_error[1:11]):+.3f}%")
print(f"  Period 11-20 mean:     {np.mean(rel_error[11:21]):+.3f}%")
print(f"  Period 21-40 mean:     {np.mean(rel_error[21:]):+.3f}%")

# MC sampling noise estimate
mc_se = mc_AggCons_std_pc / np.sqrt(3)  # std error of mean across 3 seeds
print(f"\n  MC sampling SE (period 0): {mc_se[0] / tm_AggCons_pc[0] * 100:.3f}%")
print(f"  MC sampling SE (mean):     {np.mean(mc_se / tm_AggCons_pc) * 100:.3f}%")
