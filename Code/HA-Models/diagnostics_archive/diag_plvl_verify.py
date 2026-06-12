"""
Extended diagnostic: WHY is E[delta_pLvl] non-zero when E[PermShk]=1.0?

Verify:
1. E[perm_shock_fixed_hist] for the affected agents
2. Whether the selection into newly-unemployed correlates with PermShk
3. Reconstruct dpLvl from first principles
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
from tm_methods import compute_baseline_tm_data

t0_total = time()

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

N_MC = 200000
MCOUNT = 50

print("=" * 70)
print("EXTENDED DIAGNOSTIC: Why is E[delta_pLvl] non-zero?")
print(f"  {N_MC} agents, 1 highschool type, Reduced_Run")
print("=" * 70)

# Verify the employed PermShk distribution
emp_dist = BaseType.IncShkDstn_base[0][0]
print(f"\n--- PermShk distribution check ---")
print(f"  E[PermShk] from distribution: {np.dot(emp_dist.pmv, emp_dist.atoms[0]):.10f}")
print(f"  atoms[0] (PermShk values): {emp_dist.atoms[0]}")
print(f"  pmv (probabilities): {emp_dist.pmv}")
print(f"  E[PermShk] (weighted): {np.sum(emp_dist.pmv * emp_dist.atoms[0]):.10f}")

bl_data = compute_baseline_tm_data(AggEco, mCount=MCOUNT, verbose=False)

eco_mc = deepcopy(AggEco)
agent = eco_mc.agents[0]
agent.AgentCount = N_MC
agent.seed = 42000
agent.get_economy_data(eco_mc)
eco_mc.solve()
eco_mc.reset()
agent.initialize_sim()
agent.AggDemandFac = 1.0
agent.RfreeNow = 1.0
agent.CaggNow = 1.0

# TM-ergodic initialization (same as before)
bd = bl_data[0]
erg = bd.get('cohort_ergodic', bd['ergodic'])
grid = bd['dist_mGrid']
M = len(grid)
J = agent.num_base_MrkvStates
rng = np.random.RandomState(agent.seed)
flat_probs = erg / np.sum(erg)
bins = rng.choice(len(flat_probs), size=N_MC, p=flat_probs)
agent_j = bins // M
agent_mNrm = grid[bins % M]
sol = agent.solution[0]
agent_aNrm = np.zeros(N_MC)
for j in range(J):
    mask = agent_j == j
    if np.any(mask):
        c = sol.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
        agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)
L = agent.LivPrb[0][0]
T_ag = agent.T_age
age_probs = np.array([L**(k-1) for k in range(1, T_ag + 1)])
age_probs /= np.sum(age_probs)
agent_ages = rng.choice(T_ag, size=N_MC, p=age_probs) + 1
pLogMean = agent.pLogInitMean
pLogStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))
PermShkDstn_0 = agent.IncShkDstn_base[0][0]
log_ps = np.log(PermShkDstn_0.atoms[0])
ps_var = np.dot(PermShkDstn_0.pmv, log_ps**2) - np.dot(PermShkDstn_0.pmv, log_ps)**2
g_lvl = effective_pLvl_growth(agent, getattr(agent, 'Urate_normal', 0.0))
effective_emp_periods = effective_perm_shock_periods_for_t_age(
    agent_ages, agent, getattr(agent, 'Urate_normal', 0.0))
log_pLvl = rng.normal(pLogMean, pLogStd, N_MC)
log_pLvl += agent_ages * np.log(g_lvl)
log_pLvl += effective_emp_periods * (-ps_var / 2.0)
log_pLvl += rng.normal(0, np.sqrt(ps_var * effective_emp_periods))
agent_pLvl = np.exp(log_pLvl)

agent.state_now['aNrm'][:] = agent_aNrm
agent.state_now['pLvl'][:] = agent_pLvl
agent.shocks['Mrkv'][:] = agent_j
if hasattr(agent, 't_age') and agent.t_age is not None:
    agent.t_age[:] = agent_ages
agent.Cratio = 1.0
agent.state_now['PlvlAgg'] = 1.0

for t in range(24):
    agent.sim_one_period()

eco_mc.save_state()
eco_mc.switch_to_counterfactual_mode("base")
eco_mc.act_T = act_T
agent.T_sim = act_T
agent.EconomyMrkvNow_hist = [0] * act_T
eco_mc.make_idiosyncratic_shock_histories()

# Save key data for analysis
pLvl_init = agent.state_now['pLvl'].copy()
perm_shock_fixed = agent.perm_shock_fixed_hist.copy()

print(f"\n--- perm_shock_fixed_hist check ---")
print(f"  Shape: {perm_shock_fixed.shape}")
print(f"  E[PermShk] at t=0: {np.mean(perm_shock_fixed[0]):.10f}")
print(f"  E[PermShk] at t=1: {np.mean(perm_shock_fixed[1]):.10f}")
print(f"  std(PermShk) at t=0: {np.std(perm_shock_fixed[0]):.6f}")

# --- Run BASE arm ---
print("\nRunning BASE arm...", flush=True)
base_r = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)

pLvl_base = np.array(base_r['pLvl_all'])
cNrm_base = np.array(base_r['cNrm_all'])
Mrkv_base = np.array(base_r['Mrkv_hist'])

# Save the actual PermShk history used in the base
PermShk_base = agent.shock_history['PermShk'].copy()

# --- Run RECESSION arm ---
eco_rec = deepcopy(eco_mc)
eco_rec.switch_shock_type('recession')
eco_rec.solve()
rec_d = base_dict_agg.copy()
rec_d.update(recession_changes)
rec_d['EconomyMrkv_init'] = rec_path
rec_r = eco_rec.run_experiment(**rec_d, Full_Output=True)

pLvl_rec = np.array(rec_r['pLvl_all'])
cNrm_rec = np.array(rec_r['cNrm_all'])
Mrkv_rec = np.array(rec_r['Mrkv_hist'])

rec_agent = eco_rec.agents[0]
PermShk_rec = rec_agent.shock_history['PermShk'].copy()

N = pLvl_base.shape[1]
T = pLvl_base.shape[0]

# Identify newly-unemployed at t=0
emp_base_0 = (Mrkv_base[0] % num_base_MrkvStates) == 0
unemp_rec_0 = (Mrkv_rec[0] % num_base_MrkvStates) != 0
newly_unemp = emp_base_0 & unemp_rec_0
n_affected = np.sum(newly_unemp)

# Also identify agents with different employment status at ANY period
any_diff = np.any(
    (Mrkv_base % num_base_MrkvStates == 0) != (Mrkv_rec % num_base_MrkvStates == 0),
    axis=0
)

print(f"\n{'='*70}")
print(f"VERIFICATION RESULTS")
print(f"{'='*70}")

print(f"\n  Total agents: {N}")
print(f"  Newly unemployed at t=0: {n_affected} ({100*n_affected/N:.1f}%)")
print(f"  Agents with ANY employment-status diff: {np.sum(any_diff)} ({100*np.sum(any_diff)/N:.1f}%)")

# Check E[PermShk] for the actually-used values
print(f"\n--- PermShk values actually used (from shock_history) ---")
for t in range(6):
    emp_b = (Mrkv_base[t] % num_base_MrkvStates) == 0
    emp_r = (Mrkv_rec[t] % num_base_MrkvStates) == 0
    print(f"  t={t}: E[PermShk_base|emp]={np.mean(PermShk_base[t][emp_b]):.8f}  "
          f"E[PermShk_rec|emp]={np.mean(PermShk_rec[t][emp_r]):.8f}  "
          f"E[PermShk_base|unemp]={np.mean(PermShk_base[t][~emp_b]):.4f}  "
          f"E[PermShk_rec|unemp]={np.mean(PermShk_rec[t][~emp_r]):.4f}")

# For affected agents: what are their PermShk values?
print(f"\n--- For NEWLY UNEMPLOYED at t=0 ---")
aff_PermShk_base_0 = PermShk_base[0][newly_unemp]
aff_PermShk_rec_0 = PermShk_rec[0][newly_unemp]
aff_pLvl_init = pLvl_init[newly_unemp]
aff_pLvl_base_0 = pLvl_base[0][newly_unemp]
aff_pLvl_rec_0 = pLvl_rec[0][newly_unemp]

print(f"  E[PermShk_base[0]|aff] = {np.mean(aff_PermShk_base_0):.10f}")
print(f"  E[PermShk_rec[0]|aff]  = {np.mean(aff_PermShk_rec_0):.10f}")
print(f"  E[pLvl_init|aff]       = {np.mean(aff_pLvl_init):.6f}")
print(f"  E[pLvl_init|all]       = {np.mean(pLvl_init):.6f}")
print(f"  E[pLvl_base[0]|aff]    = {np.mean(aff_pLvl_base_0):.6f}")
print(f"  E[pLvl_rec[0]|aff]     = {np.mean(aff_pLvl_rec_0):.6f}")
print(f"  E[dpLvl[0]|aff]        = {np.mean(aff_pLvl_rec_0 - aff_pLvl_base_0):.6f}")

# Reconstruct dpLvl from first principles
G_val = G
dpLvl_reconstructed = aff_pLvl_init * G_val * (1.0 - aff_PermShk_base_0)
print(f"\n  Reconstructed dpLvl[0] = pLvl_init * G * (1 - PermShk_base):")
print(f"    E[reconstructed dpLvl]  = {np.mean(dpLvl_reconstructed):.6f}")
print(f"    E[observed dpLvl]       = {np.mean(aff_pLvl_rec_0 - aff_pLvl_base_0):.6f}")

# Check: is pLvl_init correlated with the affected selection?
all_PermShk_0 = perm_shock_fixed[0]
print(f"\n--- Selection bias check ---")
print(f"  E[perm_shock_fixed[0]|all]      = {np.mean(all_PermShk_0):.10f}")
print(f"  E[perm_shock_fixed[0]|affected] = {np.mean(all_PermShk_0[newly_unemp]):.10f}")
print(f"  E[perm_shock_fixed[0]|NOT aff]  = {np.mean(all_PermShk_0[~newly_unemp]):.10f}")

# Check if the Mrkv states are the same at the start
print(f"\n--- Initial Mrkv states ---")
for j in range(num_base_MrkvStates):
    n_base = np.sum(Mrkv_base[0] % num_base_MrkvStates == j)
    n_rec = np.sum(Mrkv_rec[0] % num_base_MrkvStates == j)
    print(f"  State {j}: base={n_base} ({100*n_base/N:.1f}%), rec={n_rec} ({100*n_rec/N:.1f}%)")

# Check employment status differences per period
print(f"\n--- Employment status differences per period ---")
for t in [0, 1, 2, 3, 5, 10, 20, 50, 99]:
    emp_b = (Mrkv_base[t] % num_base_MrkvStates) == 0
    emp_r = (Mrkv_rec[t] % num_base_MrkvStates) == 0
    n_b2u = np.sum(emp_b & ~emp_r)  # employed in base, unemployed in rec
    n_u2b = np.sum(~emp_b & emp_r)  # unemployed in base, employed in rec
    n_same = np.sum(emp_b == emp_r)
    delta_pLvl_t = pLvl_rec[t] - pLvl_base[t]
    print(f"  t={t:>3d}: base→rec(emp→unemp)={n_b2u:>6d}, rec→base(unemp→emp)={n_u2b:>6d}, "
          f"same={n_same:>6d}, E[dpLvl]={np.mean(delta_pLvl_t):.6f}")

# The crucial decomposition: dpLvl by subpopulation
print(f"\n--- dpLvl decomposition by employment-status group at t=0 ---")
delta_pLvl_0 = pLvl_rec[0] - pLvl_base[0]
emp_b0 = (Mrkv_base[0] % num_base_MrkvStates) == 0
emp_r0 = (Mrkv_rec[0] % num_base_MrkvStates) == 0

groups = {
    'emp_both': emp_b0 & emp_r0,
    'emp_base_unemp_rec': emp_b0 & ~emp_r0,
    'unemp_base_emp_rec': ~emp_b0 & emp_r0,
    'unemp_both': ~emp_b0 & ~emp_r0,
}
for name, mask in groups.items():
    n = np.sum(mask)
    if n > 0:
        E_dp = np.mean(delta_pLvl_0[mask])
        contribution = np.sum(delta_pLvl_0[mask]) / N
        print(f"  {name:>25s}: N={n:>6d}, E[dpLvl]={E_dp:>10.6f}, contribution_to_mean={contribution:>10.6f}")

# What about mortality? Check if the same agents die in both arms
print(f"\n--- Mortality check ---")
who_dies_base = agent.who_dies_fixed_hist
print(f"  who_dies shape: {who_dies_base.shape}")
print(f"  Deaths at t=0: {np.sum(who_dies_base[0])}")
print(f"  Deaths at t=1: {np.sum(who_dies_base[1])}")

total = time() - t0_total
print(f"\nTotal time: {total:.0f}s ({total/60:.1f} min)")
