"""
Diagnostic: How much does the MC distribution drift during the 24-period warmup
after TM ergodic initialization?

Tracks E[pLvl], E[mNrm], E[aNrm], state fractions over warmup periods.
"""

# Math reference: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")

import os, sys, numpy as np
from copy import deepcopy

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())

os.environ['MPLBACKEND'] = 'Agg'
import matplotlib; matplotlib.use('Agg')

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from income_process_sst import effective_perm_shock_periods_for_t_age, effective_pLvl_growth, effective_perm_shock_variance_periods
from tm_methods import compute_baseline_tm_data, compute_analytical_mean_pLvl

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

J = num_base_MrkvStates

init_dict = init_highschool
BaseType = AggFiscalType(**init_dict)
BaseType.cycles = 0
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

N_mc = 200000

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
for a in AggEco.agents:
    a.AgentCount = N_mc
    a.seed = 42000
    a.get_economy_data(AggEco)

AggEco.solve()

print("=" * 70)
print(f"WARMUP DRIFT DIAGNOSTIC (N={N_mc})")
print("=" * 70)

# Compute TM baseline data
mCount = 100
baseline_tm_data = compute_baseline_tm_data(AggEco, mCount=mCount, verbose=False)
bd = baseline_tm_data[0]

E_pLvl_analytical = compute_analytical_mean_pLvl(BaseType)
print(f"\nTM analytical E[pLvl] = {E_pLvl_analytical:.4f}")

# TM ergodic state fractions
ergodic = bd['ergodic']
M = mCount
tm_state_fracs = np.array([np.sum(ergodic[j*M:(j+1)*M]) for j in range(J)])
print(f"TM ergodic state fractions: {tm_state_fracs}")

# TM ergodic E[mNrm] per state
grid = bd['dist_mGrid']
tm_mNrm_by_state = []
for j in range(J):
    dstn_j = ergodic[j*M:(j+1)*M]
    if np.sum(dstn_j) > 0:
        tm_mNrm_by_state.append(np.dot(grid, dstn_j) / np.sum(dstn_j))
    else:
        tm_mNrm_by_state.append(0.0)
tm_E_mNrm = np.dot(tm_state_fracs, tm_mNrm_by_state)
print(f"TM ergodic E[mNrm] = {tm_E_mNrm:.4f}")

# Initialize MC from TM ergodic
AggEco.reset()
for a in AggEco.agents:
    a.initialize_sim()
    a.AggDemandFac = 1.0
    a.RfreeNow = 1.0
    a.CaggNow = 1.0

agent = AggEco.agents[0]

# TM ergodic initialization (matching Simulate.py)
rng = np.random.RandomState(42000)
flat_probs = ergodic / np.sum(ergodic)
bins = rng.choice(len(flat_probs), size=N_mc, p=flat_probs)
agent_j = bins // M
agent_mNrm = grid[bins % M]

# Convert mNrm -> aNrm
sol = agent.solution[0]
agent_aNrm = np.zeros(N_mc)
for j in range(J):
    mask = agent_j == j
    if np.any(mask):
        c = sol.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
        agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)

# Ages from ergodic
L = agent.LivPrb[0][0]
T_ag = agent.T_age
age_probs = np.array([L**(k-1) for k in range(1, T_ag + 1)])
age_probs /= np.sum(age_probs)
agent_ages = rng.choice(T_ag, size=N_mc, p=age_probs) + 1

# pLvl with age-dependent growth and PermShk variance
pLogMean = agent.pLogInitMean
pLogStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))
PermShkDstn_0 = agent.IncShkDstn_base[0][0]
log_ps = np.log(PermShkDstn_0.atoms[0])
ps_var = np.dot(PermShkDstn_0.pmv, log_ps**2) - np.dot(PermShkDstn_0.pmv, log_ps)**2
g_lvl = effective_pLvl_growth(agent, getattr(agent, 'Urate_normal', 0.0))
effective_emp_periods = effective_perm_shock_periods_for_t_age(
    agent_ages, agent, getattr(agent, 'Urate_normal', 0.0))
log_pLvl = rng.normal(pLogMean, pLogStd, N_mc)
log_pLvl += agent_ages * np.log(g_lvl)
log_pLvl += effective_emp_periods * (-ps_var / 2.0)
log_pLvl += rng.normal(0, np.sqrt(ps_var * effective_emp_periods))
agent_pLvl = np.exp(log_pLvl)

# Inject
agent.state_now['aNrm'][:] = agent_aNrm
agent.state_now['pLvl'][:] = agent_pLvl
agent.shocks['Mrkv'][:] = agent_j
agent.t_age[:] = agent_ages
agent.Cratio = 1.0
agent.state_now['PlvlAgg'] = 1.0

# Track drift over warmup periods
max_warmup = 48  # Track beyond 24 to see if drift continues
print(f"\n{'Period':>6s} {'E[pLvl]':>10s} {'E[mNrm]':>10s} {'E[aNrm]':>10s} {'E[age]':>8s} {'State0':>8s} {'State1':>8s}")
print("-" * 70)

# Period 0 (right after TM init, before any sim)
E_pLvl_0 = np.mean(agent.state_now['pLvl'])
E_mNrm_0 = np.mean(agent_mNrm)  # mNrm from init, before sim updates it
E_aNrm_0 = np.mean(agent.state_now['aNrm'])
E_age_0 = np.mean(agent.t_age)
fracs_0 = [np.mean(agent.shocks['Mrkv'] == j) for j in range(J)]
print(f"{0:>6d} {E_pLvl_0:>10.4f} {E_mNrm_0:>10.4f} {E_aNrm_0:>10.4f} {E_age_0:>8.2f} {fracs_0[0]:>8.4f} {fracs_0[1]:>8.4f}")

# Store period 0 values for drift calculation
init_pLvl = E_pLvl_0
init_mNrm = E_mNrm_0
init_aNrm = E_aNrm_0
init_fracs = fracs_0.copy()

drift_data = []

for t in range(1, max_warmup + 1):
    agent.sim_one_period()

    E_pLvl = np.mean(agent.state_now['pLvl'])
    E_mNrm = np.mean(agent.state_now['mNrm'])
    E_aNrm = np.mean(agent.state_now['aNrm'])
    E_age = np.mean(agent.t_age)
    fracs = [np.mean(agent.shocks['Mrkv'] == j) for j in range(J)]

    drift_data.append({
        't': t,
        'E_pLvl': E_pLvl,
        'E_mNrm': E_mNrm,
        'E_aNrm': E_aNrm,
        'E_age': E_age,
        'fracs': fracs,
    })

    if t <= 10 or t % 6 == 0:
        print(f"{t:>6d} {E_pLvl:>10.4f} {E_mNrm:>10.4f} {E_aNrm:>10.4f} {E_age:>8.2f} {fracs[0]:>8.4f} {fracs[1]:>8.4f}")

# Summary
print("\n" + "=" * 70)
print("DRIFT SUMMARY")
print("=" * 70)

d24 = drift_data[23]  # Period 24
d48 = drift_data[47]  # Period 48

print(f"\n{'Metric':<15s} {'TM Target':>12s} {'Period 0':>12s} {'Period 24':>12s} {'Period 48':>12s}")
print("-" * 55)

print(f"{'E[pLvl]':<15s} {E_pLvl_analytical:>12.4f} {init_pLvl:>12.4f} {d24['E_pLvl']:>12.4f} {d48['E_pLvl']:>12.4f}")
print(f"{'E[mNrm]':<15s} {tm_E_mNrm:>12.4f} {init_mNrm:>12.4f} {d24['E_mNrm']:>12.4f} {d48['E_mNrm']:>12.4f}")
print(f"{'State 0 frac':<15s} {tm_state_fracs[0]:>12.4f} {init_fracs[0]:>12.4f} {d24['fracs'][0]:>12.4f} {d48['fracs'][0]:>12.4f}")
print(f"{'State 1 frac':<15s} {tm_state_fracs[1]:>12.4f} {init_fracs[1]:>12.4f} {d24['fracs'][1]:>12.4f} {d48['fracs'][1]:>12.4f}")

print(f"\nDrift from period 0 to 24:")
pLvl_drift_24 = (d24['E_pLvl'] / init_pLvl - 1) * 100
mNrm_drift_24 = (d24['E_mNrm'] / init_mNrm - 1) * 100
print(f"  E[pLvl]: {pLvl_drift_24:+.3f}%")
print(f"  E[mNrm]: {mNrm_drift_24:+.3f}%")
print(f"  State 0: {(d24['fracs'][0] - init_fracs[0])*100:+.4f} pp")

print(f"\nDrift from period 24 to 48:")
pLvl_drift_48 = (d48['E_pLvl'] / d24['E_pLvl'] - 1) * 100
mNrm_drift_48 = (d48['E_mNrm'] / d24['E_mNrm'] - 1) * 100
print(f"  E[pLvl]: {pLvl_drift_48:+.3f}%")
print(f"  E[mNrm]: {mNrm_drift_48:+.3f}%")
print(f"  State 0: {(d48['fracs'][0] - d24['fracs'][0])*100:+.4f} pp")

# Compare to TM target
print(f"\nDeviation from TM target at period 24:")
print(f"  E[pLvl]: {(d24['E_pLvl'] / E_pLvl_analytical - 1) * 100:+.3f}%")
print(f"  E[mNrm]: {(d24['E_mNrm'] / tm_E_mNrm - 1) * 100:+.3f}%")
print(f"  State 0: {(d24['fracs'][0] - tm_state_fracs[0])*100:+.4f} pp")
