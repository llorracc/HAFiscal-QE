"""
Diagnostic: Test whether Corr(delta_pLvl, cNrm) decays to zero after the
recession ends, as predicted by homotheticity of the consumption model.

For each period t, compute:
  - E[delta_pLvl]  (should be ~0 by E[PermShk]=1)
  - Corr(delta_pLvl, cNrm_rec)
  - E[delta_pLvl * cNrm_rec]  (per-period TE contribution from pLvl channel)
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

# --- Setup (same as investigate_recession_check.py) ---
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

# --- MC setup ---
N_MC = 200000
MCOUNT = 50

print("=" * 70)
print("DIAGNOSTIC: Corr(delta_pLvl, cNrm) per period")
print(f"  {N_MC} agents, 1 highschool type, Reduced_Run")
print(f"  Recession: 3 quarters, rec_path[:10] = {rec_path[:10]}")
print("=" * 70)

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

# TM-ergodic initialization
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

# Warmup
for t in range(24):
    agent.sim_one_period()

eco_mc.save_state()
eco_mc.switch_to_counterfactual_mode("base")
eco_mc.act_T = act_T
agent.T_sim = act_T
agent.EconomyMrkvNow_hist = [0] * act_T
eco_mc.make_idiosyncratic_shock_histories()

# --- Run BASE arm ---
print("\nRunning BASE arm...", flush=True)
t0 = time()
base_r = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
print(f"  done in {time()-t0:.0f}s")

pLvl_base = np.array(base_r['pLvl_all'])      # (T, N)
cNrm_base = np.array(base_r['cNrm_all'])      # (T, N)
mNrm_base = np.array(base_r['mNrm_all'])      # (T, N)
Mrkv_base = np.array(base_r['Mrkv_hist'])      # (T, N)

# --- Run RECESSION arm ---
print("Running RECESSION arm...", flush=True)
t0 = time()
eco_rec = deepcopy(eco_mc)
eco_rec.switch_shock_type('recession')
eco_rec.solve()
rec_d = base_dict_agg.copy()
rec_d.update(recession_changes)
rec_d['EconomyMrkv_init'] = rec_path
rec_r = eco_rec.run_experiment(**rec_d, Full_Output=True)
print(f"  done in {time()-t0:.0f}s")

pLvl_rec = np.array(rec_r['pLvl_all'])
cNrm_rec = np.array(rec_r['cNrm_all'])
mNrm_rec = np.array(rec_r['mNrm_all'])
Mrkv_rec = np.array(rec_r['Mrkv_hist'])

N = pLvl_base.shape[1]
T = pLvl_base.shape[0]

# --- Compute per-period diagnostics ---
delta_pLvl = pLvl_rec - pLvl_base

# Identify agents who were newly-unemployed at t=0
emp_base_0 = (Mrkv_base[0] % num_base_MrkvStates) == 0
unemp_rec_0 = (Mrkv_rec[0] % num_base_MrkvStates) != 0
newly_unemp = emp_base_0 & unemp_rec_0
n_affected = np.sum(newly_unemp)

print(f"\n{'='*70}")
print(f"RESULTS: Per-period Corr(delta_pLvl, cNrm_rec) and E[delta_pLvl * cNrm_rec]")
print(f"  N = {N}, T = {T}, newly_unemp at t=0 = {n_affected} ({100*n_affected/N:.1f}%)")
print(f"{'='*70}")

print(f"\n{'t':>4s} {'E[dpLvl]':>12s} {'E[dpLvl*cNrm]':>14s} {'Corr(dpLvl,cNrm)':>18s} {'Corr(dpLvl,mNrm)':>18s} {'E[dmNrm]':>12s}")
print("-" * 82)

disc = np.array([1.0 / Rfree**t for t in range(T)])
npv_dpLvl_cNrm = 0.0

selected_periods = list(range(15)) + [15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 99]
selected_periods = sorted(set(p for p in selected_periods if p < T))

for t in selected_periods:
    dp = delta_pLvl[t]
    cr = cNrm_rec[t]
    mr = mNrm_rec[t]
    dm = mNrm_rec[t] - mNrm_base[t]

    mean_dp = np.mean(dp)
    mean_dp_cNrm = np.mean(dp * cr)
    mean_dm = np.mean(dm)
    npv_dpLvl_cNrm += disc[t] * np.sum(dp * cr)

    if np.std(dp) > 1e-15 and np.std(cr) > 1e-15:
        corr_dp_cNrm = np.corrcoef(dp, cr)[0, 1]
    else:
        corr_dp_cNrm = 0.0
    if np.std(dp) > 1e-15 and np.std(mr) > 1e-15:
        corr_dp_mNrm = np.corrcoef(dp, mr)[0, 1]
    else:
        corr_dp_mNrm = 0.0

    print(f"{t:>4d} {mean_dp:>12.6f} {mean_dp_cNrm:>14.6f} {corr_dp_cNrm:>18.6f} {corr_dp_mNrm:>18.6f} {mean_dm:>12.6f}")

npv_dpLvl_cNrm /= N
print(f"\nNPV of sum(delta_pLvl * cNrm_rec) / N = {npv_dpLvl_cNrm:.6f}")

# Also compute total MC treatment effects for reference
AggCons_base = np.array(base_r['AggCons'])
AggCons_rec = np.array(rec_r['AggCons'])
te_per_period = AggCons_rec - AggCons_base
npv_te = np.sum(te_per_period * disc)
print(f"Total MC NPV TE (recession - base) = {npv_te:.4f}")

# Decomposition: post-hoc pLvl fix
cLvl_rec = pLvl_rec * cNrm_rec  # simplified (ignoring splurge for now)
cLvl_base = pLvl_base * cNrm_base
cLvl_pLvl_fix = pLvl_base * cNrm_rec

# Per-period check of the user's prediction: does E[dpLvl * cNrm] decay?
print(f"\n--- Focused check: E[dpLvl * cNrm_rec] for AFFECTED agents only ---")
print(f"{'t':>4s} {'E[dpLvl|aff]':>14s} {'E[dpLvl*cNrm|aff]':>18s} {'Corr|aff':>12s} {'n_alive':>8s}")
print("-" * 60)

for t in selected_periods:
    alive_mask = (pLvl_base[t] > 0) & (pLvl_rec[t] > 0)
    affected_alive = newly_unemp & alive_mask
    n_alive = np.sum(affected_alive)
    if n_alive < 10:
        continue
    dp_aff = delta_pLvl[t][affected_alive]
    cr_aff = cNrm_rec[t][affected_alive]
    corr_aff = np.corrcoef(dp_aff, cr_aff)[0, 1] if np.std(dp_aff) > 1e-15 else 0.0
    print(f"{t:>4d} {np.mean(dp_aff):>14.6f} {np.mean(dp_aff*cr_aff):>18.6f} {corr_aff:>12.6f} {n_alive:>8d}")

total = time() - t0_total
print(f"\nTotal time: {total:.0f}s ({total/60:.1f} min)")
