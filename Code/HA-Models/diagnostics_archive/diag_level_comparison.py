"""
Diagnostic: compare TM vs MC per-period LEVEL consumption for base and recession.

The TE = C_rec - C_base. If both levels are off by the same factor k:
  TE_TM = k * C_rec_true - k * C_base_true = k * TE_true
So a uniform k% level error gives k% TE error. But if the level error
differs between base and recession, the TE error amplifies.

Config A (near-zero variances) to isolate from covariance effects.
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
    compute_analytical_mean_pLvl, build_tm_agg_fiscal, find_ergodic_distribution,
)

NEAR_ZERO = 0.001
N_MC = 100000

t0_global = time()

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

DiscFac = DiscFacDstns[1].atoms[0][0]

init_hs = deepcopy(init_highschool)
init_hs['PermShkStd'] = [NEAR_ZERO]
init_hs['pLogInitStd'] = NEAR_ZERO

AggEco = AggregateDemandEconomy(**init_ADEconomy)
bt = AggFiscalType(**init_hs)
bt.cycles = 0
bt.get_economy_data(AggEco)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([bt.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([bt.IncUnempNoBenefits])])
bt.IncShkDstn = [[bt.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
bt.IncShkDstn_base = bt.IncShkDstn
bt.IncShkDstn_recession = [bt.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]

agent = deepcopy(bt)
agent.DiscFac = DiscFac
agent.seed = 0
AggEco.agents = [agent]
AggEco.solve()
act_T = AggEco.act_T
TM_N = agent.AgentCount
Rfree = agent.Rfree[0]
disc = np.array([1.0 / Rfree**t for t in range(act_T)])

rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
for t in range(3):
    rec_path[t] = rec_path[t] + 1
rec_path = rec_path[:act_T]

# ============================================================
# TM experiments
# ============================================================
print("=" * 78)
print("DIAGNOSTIC: Level Consumption Comparison (Config A: both_small)")
print("=" * 78)
print(f"\n--- TM ---")
tm_base = run_experiment_tm(AggEco, shock_type='base', mCount=100, verbose=False)
bl_data = compute_baseline_tm_data(AggEco, mCount=100, verbose=False)
E_pLvl_tm = bl_data[0]['E_pLvl']
u_erg = bl_data[0]['u_ergodic']

eco_tm2 = deepcopy(AggEco)
eco_tm2.switch_shock_type("recession")
eco_tm2.solve()
tm_rec = run_experiment_tm_nonbase(eco_tm2, "recession", rec_path, bl_data, mCount=100, verbose=False)

tm_base_pc = np.array(tm_base['AggCons']) / TM_N
tm_rec_pc = np.array(tm_rec['AggCons']) / TM_N
tm_te = tm_rec_pc - tm_base_pc
print(f"  E[pLvl] (TM): {E_pLvl_tm:.4f}")
print(f"  TM base per-capita (constant): {tm_base_pc[0]:.6f}")
print(f"  TM rec per-capita [0]: {tm_rec_pc[0]:.6f}")

# ============================================================
# MC experiment (single seed)
# ============================================================
print(f"\n--- MC (seed=0, N={N_MC}) ---")

# Ergodic init
agent_base = AggEco.agents[0]
agent_base.update_mrkv_array('base')
agent_base.solve()
tm_data = build_tm_agg_fiscal(agent_base, mCount=100)
erg = find_ergodic_distribution(tm_data['TranMatrix'])
bl_data[0]['ergodic'] = erg
bl_data[0]['dist_mGrid'] = tm_data['dist_mGrid']

eco_mc = deepcopy(AggEco)
for a in eco_mc.agents:
    a.AgentCount = N_MC
    a.seed = 0
    a.get_economy_data(eco_mc)
eco_mc.solve()
eco_mc.reset()
for a in eco_mc.agents:
    a.initialize_sim()
    a.AggDemandFac = 1.0
    a.RfreeNow = 1.0
    a.CaggNow = 1.0

bd = bl_data[0]
grid = bd['dist_mGrid']
M = len(grid)
J = agent.num_base_MrkvStates
rng = np.random.RandomState(1000)
a0 = eco_mc.agents[0]
N = a0.AgentCount

flat_probs = erg / np.sum(erg)
bins = rng.choice(len(flat_probs), size=N, p=flat_probs)
agent_j = bins // M
agent_mNrm = grid[bins % M]

sol = a0.solution[0]
agent_aNrm = np.zeros(N)
for j in range(J):
    mask = agent_j == j
    if np.any(mask):
        c = sol.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
        agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)

L = a0.LivPrb[0][0]
T_ag = a0.T_age
age_probs = np.array([L**(k-1) for k in range(1, T_ag + 1)])
age_probs /= np.sum(age_probs)
agent_ages = rng.choice(T_ag, size=N, p=age_probs) + 1

pLogMean = a0.pLogInitMean
pLogStd = max(getattr(a0, 'pLogInitStd', 0.0), 1e-12)
PermShkDstn_0 = a0.IncShkDstn_base[0][0]
log_ps = np.log(PermShkDstn_0.atoms[0])
ps_var = np.dot(PermShkDstn_0.pmv, log_ps**2) - np.dot(PermShkDstn_0.pmv, log_ps)**2

g_lvl = effective_pLvl_growth(a0, getattr(a0, 'Urate_normal', 0.0))
effective_emp_periods = effective_perm_shock_periods_for_t_age(
    agent_ages, a0, getattr(a0, 'Urate_normal', 0.0))
log_pLvl = rng.normal(pLogMean, pLogStd, N)
log_pLvl += agent_ages * np.log(g_lvl)
log_pLvl += effective_emp_periods * (-max(ps_var, 1e-24) / 2.0)
log_pLvl += rng.normal(0, np.sqrt(max(ps_var, 1e-24) * effective_emp_periods))

a0.state_now['aNrm'][:] = agent_aNrm
a0.state_now['pLvl'][:] = np.exp(log_pLvl)
a0.shocks['Mrkv'][:] = agent_j
if hasattr(a0, 't_age') and a0.t_age is not None:
    a0.t_age[:] = agent_ages
a0.Cratio = 1.0
a0.state_now['PlvlAgg'] = 1.0

for t in range(24):
    a0.sim_one_period()

eco_mc.save_state()
eco_mc.switch_to_counterfactual_mode("base")
eco_mc.act_T = act_T
for a in eco_mc.agents:
    a.T_sim = act_T
    a.EconomyMrkvNow_hist = [0] * act_T
eco_mc.make_idiosyncratic_shock_histories()

base_dict_agg = deepcopy(base_dict)
base_dict_agg['Splurge'] = a0.Splurge
mc_base = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
T_out = min(len(mc_base['AggCons']), act_T)
eco_mc.store_baseline(mc_base['AggCons'])

eco_rec = deepcopy(eco_mc)
eco_rec.switch_shock_type("recession")
eco_rec.solve()
rec_dict = base_dict_agg.copy()
rec_dict.update(recession_changes)
rec_dict['EconomyMrkv_init'] = rec_path
mc_rec = eco_rec.run_experiment(**rec_dict, Full_Output=True)

mc_base_pc = np.array(mc_base['AggCons'][:T_out]) / N_MC
mc_rec_pc = np.array(mc_rec['AggCons'][:T_out]) / N_MC
mc_te = mc_rec_pc - mc_base_pc

mc_EpLvl_base = np.mean(mc_base['pLvl_all'], axis=1)[:T_out]
mc_EpLvl_rec = np.mean(mc_rec['pLvl_all'], axis=1)[:T_out]

print(f"  MC E[pLvl] (t=0 base): {mc_EpLvl_base[0]:.4f}")
print(f"  MC base per-capita [0]: {mc_base_pc[0]:.6f}")
print(f"  MC rec per-capita [0]: {mc_rec_pc[0]:.6f}")

# ============================================================
# Level comparison
# ============================================================
T_show = 20
print(f"\n--- Per-period level comparison (first {T_show} periods) ---")
print(f"  {'t':>4s}  {'TM_base':>10s}  {'MC_base':>10s}  {'TM/MC_b':>8s}  {'TM_rec':>10s}  {'MC_rec':>10s}  {'TM/MC_r':>8s}  {'TM_TE':>10s}  {'MC_TE':>10s}  {'TE_rat':>8s}")
print(f"  {'----':>4s}  {'----------':>10s}  {'----------':>10s}  {'--------':>8s}  {'----------':>10s}  {'----------':>10s}  {'--------':>8s}  {'----------':>10s}  {'----------':>10s}  {'--------':>8s}")
for t in range(T_show):
    tb = tm_base_pc[t]
    mb = mc_base_pc[t]
    rat_b = tb / mb if mb > 0 else float('nan')
    tr = tm_rec_pc[t]
    mr = mc_rec_pc[t]
    rat_r = tr / mr if mr > 0 else float('nan')
    tte = tm_te[t]
    mte = mc_te[t]
    te_rat = tte / mte if abs(mte) > 1e-12 else float('nan')
    print(f"  {t:>4d}  {tb:>10.6f}  {mb:>10.6f}  {rat_b:>8.6f}  {tr:>10.6f}  {mr:>10.6f}  {rat_r:>8.6f}  {tte:>+10.6f}  {mte:>+10.6f}  {te_rat:>8.4f}")

# Also compute c_nrm = C / E[pLvl] to separate level scaling from normalized response
print(f"\n--- Normalized consumption comparison (first {T_show} periods) ---")
print(f"  (c_nrm = AggCons / (N * E[pLvl]_respective)")
print(f"  {'t':>4s}  {'TM_c_nrm_b':>12s}  {'MC_c_nrm_b':>12s}  {'ratio':>8s}  {'TM_c_nrm_r':>12s}  {'MC_c_nrm_r':>12s}  {'ratio':>8s}  {'TM_dc':>10s}  {'MC_dc':>10s}  {'dc_rat':>8s}")
print(f"  {'----':>4s}  {'------------':>12s}  {'------------':>12s}  {'--------':>8s}  {'------------':>12s}  {'------------':>12s}  {'--------':>8s}  {'----------':>10s}  {'----------':>10s}  {'--------':>8s}")
for t in range(T_show):
    tm_cnrm_b = tm_base_pc[t] / E_pLvl_tm
    mc_cnrm_b = mc_base_pc[t] / mc_EpLvl_base[t]
    rat_b = tm_cnrm_b / mc_cnrm_b if mc_cnrm_b > 0 else float('nan')

    # For TM recession, we need to divide by E_pLvl * pLvl_factor,
    # but we don't have pLvl_factor. Use: TM_rec_pc / E_pLvl gives c_nrm * F_t.
    # Instead, compute the "effective" c_nrm as C_rec / (E_pLvl * F_t).
    # We can estimate F_t from the MC: F_t ≈ mc_EpLvl_rec / mc_EpLvl_base.
    # Or more directly, just compare the consumption per E[p]:
    tm_c_over_p_r = tm_rec_pc[t] / E_pLvl_tm  # = c_nrm * F_t
    mc_c_over_p_r = mc_rec_pc[t] / mc_EpLvl_rec[t]  # ≈ c_nrm
    rat_r = tm_c_over_p_r / mc_c_over_p_r if mc_c_over_p_r > 0 else float('nan')

    tm_dc = tm_c_over_p_r - tm_cnrm_b
    mc_dc = mc_c_over_p_r - mc_cnrm_b
    dc_rat = tm_dc / mc_dc if abs(mc_dc) > 1e-12 else float('nan')
    print(f"  {t:>4d}  {tm_cnrm_b:>12.8f}  {mc_cnrm_b:>12.8f}  {rat_b:>8.6f}  {tm_c_over_p_r:>12.8f}  {mc_c_over_p_r:>12.8f}  {rat_r:>8.6f}  {tm_dc:>+10.6f}  {mc_dc:>+10.6f}  {dc_rat:>8.4f}")

# NPV summary
tm_npv = np.sum(tm_te * disc)
mc_npv = np.sum(mc_te * disc[:T_out])
print(f"\n--- NPV ---")
print(f"  TM:  {tm_npv:.6f}")
print(f"  MC:  {mc_npv:.6f}")
print(f"  err: {(tm_npv-mc_npv)/abs(mc_npv)*100:+.2f}%")
print(f"\nTotal time: {time()-t0_global:.0f}s")
