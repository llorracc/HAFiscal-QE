"""
Diagnostic: Decompose the TM-MC discrepancy into per-employment-state E[p|z].

Math-derive (TM-agg) uses: C = N * E[p] * F_t * c_nrm
True aggregate (MC-agg):   C = sum_i p_i * c(m_i, z_i)

The factored form ignores Cov(p, c(m,z)) driven by employment-state-dependent
growth (p-transition): employed grow at G, unemployed at 1.0.

This script:
  1. Runs MC recession (Config A: both small) and decomposes aggregate C into
     per-state contributions: C_emp = sum_{i: emp} p_i * c(m_i) and C_unemp.
  2. Computes E[p|emp] and E[p|unemp] from MC at each period.
  3. Computes what the TM *would* give using per-state E[p|z] instead of global E[p].
  4. Shows the correction needed.
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
    _effective_LivPrb,
)

NEAR_ZERO = 0.001
N_MC = 100000

t0_global = time()

# Load parameters
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

DiscFac = DiscFacDstns[1].atoms[0][0]

# Build economy with NEAR-ZERO variances (Config A) to isolate the p-z covariance
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
Rfree = agent.Rfree[0]
disc = np.array([1.0 / Rfree**t for t in range(act_T)])

rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
for t in range(3):
    rec_path[t] = rec_path[t] + 1
rec_path = rec_path[:act_T]

# ============================================================
# Step 1: Run TM experiments
# ============================================================
print("=" * 78)
print("DIAGNOSTIC: Per-state E[pLvl] decomposition (Config A: both_small)")
print("=" * 78)
print(f"\n--- Step 1: TM experiments ---")

tm_base = run_experiment_tm(AggEco, shock_type='base', mCount=100, verbose=False)
bl_data = compute_baseline_tm_data(AggEco, mCount=100, verbose=False)

E_pLvl_tm = bl_data[0]['E_pLvl']
u_erg = bl_data[0]['u_ergodic']
print(f"  E[pLvl] (TM, g-corrected): {E_pLvl_tm:.4f}")
print(f"  u_ergodic: {u_erg:.4f}")

eco_tm2 = deepcopy(AggEco)
eco_tm2.switch_shock_type("recession")
eco_tm2.solve()
tm_rec = run_experiment_tm_nonbase(eco_tm2, "recession", rec_path, bl_data, mCount=100, verbose=False)

TM_N = agent.AgentCount
tm_base_cons = np.array(tm_base['AggCons']) / TM_N
tm_rec_cons = np.array(tm_rec['AggCons']) / TM_N
tm_te = tm_rec_cons - tm_base_cons
tm_npv = np.sum(tm_te * disc)
print(f"  TM recession TE NPV: {tm_npv:.6f}")

# ============================================================
# Step 2: Run MC (single seed for detailed decomposition)
# ============================================================
print(f"\n--- Step 2: MC recession (seed=0, N={N_MC}) ---")

# Init from ergodic
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
N = eco_mc.agents[0].AgentCount
a0 = eco_mc.agents[0]

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

# Run base
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

# Run recession
eco_rec = deepcopy(eco_mc)
eco_rec.switch_shock_type("recession")
eco_rec.solve()
rec_dict = base_dict_agg.copy()
rec_dict.update(recession_changes)
rec_dict['EconomyMrkv_init'] = rec_path
mc_rec = eco_rec.run_experiment(**rec_dict, Full_Output=True)

# ============================================================
# Step 3: Per-state decomposition
# ============================================================
print(f"\n--- Step 3: Per-state E[pLvl] decomposition ---")
print(f"\n  Micro states: 0=emp_normal, 1=unemp_normal, 2=emp_deep, 3=unemp_deep")

pLvl_rec = mc_rec['pLvl_all'][:T_out]
pLvl_base = mc_base['pLvl_all'][:T_out]
cLvl_rec = mc_rec['cLvl_all_splurge'][:T_out]
cLvl_base = mc_base['cLvl_all_splurge'][:T_out]
Mrkv_rec = mc_rec['Mrkv_hist'][:T_out]
Mrkv_base = mc_base['Mrkv_hist'][:T_out]

T_show = 12

# Table 1: Per-state E[p] in recession vs base
print(f"\n  Table 1: E[pLvl | z] for recession vs base (first {T_show} periods)")
print(f"  {'t':>4s}  {'E[p]_all':>10s}  {'E[p|emp]':>10s}  {'E[p|une]':>10s}  {'E[p|emp]/E[p|une]':>18s}  {'frac_emp':>10s}")
print(f"  {'----':>4s}  {'----------':>10s}  {'----------':>10s}  {'----------':>10s}  {'------------------':>18s}  {'----------':>10s}")
for t in range(T_show):
    p = pLvl_rec[t]
    z = Mrkv_rec[t]
    emp_mask = (z == 0) | (z == 2)
    unemp_mask = (z == 1) | (z == 3)
    Ep_all = np.mean(p)
    Ep_emp = np.mean(p[emp_mask]) if np.any(emp_mask) else 0
    Ep_une = np.mean(p[unemp_mask]) if np.any(unemp_mask) else 0
    ratio = Ep_emp / Ep_une if Ep_une > 0 else float('nan')
    frac_emp = np.mean(emp_mask)
    print(f"  {t:>4d}  {Ep_all:>10.4f}  {Ep_emp:>10.4f}  {Ep_une:>10.4f}  {ratio:>18.6f}  {frac_emp:>10.4f}")

# Table 2: Per-state c_nrm in recession vs base
print(f"\n  Table 2: E[c_nrm | z] for recession (first {T_show} periods)")
print(f"  {'t':>4s}  {'E[c_nrm]_all':>14s}  {'E[c|emp]':>10s}  {'E[c|une]':>10s}  {'E[c|emp]/E[c|une]':>18s}")
print(f"  {'----':>4s}  {'--------------':>14s}  {'----------':>10s}  {'----------':>10s}  {'------------------':>18s}")
for t in range(T_show):
    p = pLvl_rec[t]
    c_lvl = cLvl_rec[t]
    c_nrm = c_lvl / np.maximum(p, 1e-15)
    z = Mrkv_rec[t]
    emp_mask = (z == 0) | (z == 2)
    unemp_mask = (z == 1) | (z == 3)
    Ec_all = np.mean(c_nrm)
    Ec_emp = np.mean(c_nrm[emp_mask]) if np.any(emp_mask) else 0
    Ec_une = np.mean(c_nrm[unemp_mask]) if np.any(unemp_mask) else 0
    ratio = Ec_emp / Ec_une if Ec_une > 0 else float('nan')
    print(f"  {t:>4d}  {Ec_all:>14.6f}  {Ec_emp:>10.6f}  {Ec_une:>10.6f}  {ratio:>18.6f}")

# Table 3: The covariance decomposition
# MC: C = sum_i p_i * c_nrm_i = N * (E[p|emp]*E[c|emp]*P(emp) + E[p|une]*E[c|une]*P(une) + within-state cov terms)
# TM: C = N * E[p] * E[c_nrm]
# Error = N * (Cov(p, c_nrm)) = N * (E[p*c_nrm] - E[p]*E[c_nrm])
print(f"\n  Table 3: Covariance decomposition — recession treatment effect error")
print(f"  {'t':>4s}  {'MC_TE':>10s}  {'E[p]*E[c]_TE':>14s}  {'MC-factored':>12s}  {'%err':>8s}  {'Cov_rec':>10s}  {'Cov_base':>10s}  {'dCov':>10s}")
print(f"  {'----':>4s}  {'----------':>10s}  {'--------------':>14s}  {'------------':>12s}  {'--------':>8s}  {'----------':>10s}  {'----------':>10s}  {'----------':>10s}")
mc_te_actual = np.array(mc_rec['AggCons'][:T_out]) / N_MC - np.array(mc_base['AggCons'][:T_out]) / N_MC
for t in range(T_show):
    # Recession
    p_r = pLvl_rec[t]
    c_r = cLvl_rec[t] / np.maximum(p_r, 1e-15)
    Epc_r = np.mean(p_r * c_r)
    Ep_r = np.mean(p_r)
    Ec_r = np.mean(c_r)
    cov_r = Epc_r - Ep_r * Ec_r

    # Base
    p_b = pLvl_base[t]
    c_b = cLvl_base[t] / np.maximum(p_b, 1e-15)
    Epc_b = np.mean(p_b * c_b)
    Ep_b = np.mean(p_b)
    Ec_b = np.mean(c_b)
    cov_b = Epc_b - Ep_b * Ec_b

    # TE from factored form: N * (Ep_r * Ec_r - Ep_b * Ec_b)
    factored_te = Ep_r * Ec_r - Ep_b * Ec_b
    mc_te_t = mc_te_actual[t]
    diff = mc_te_t - factored_te
    pct = diff / abs(mc_te_t) * 100 if abs(mc_te_t) > 1e-12 else 0
    d_cov = cov_r - cov_b
    print(f"  {t:>4d}  {mc_te_t:>10.6f}  {factored_te:>14.6f}  {diff:>+12.6f}  {pct:>+7.2f}%  {cov_r:>+10.6f}  {cov_b:>+10.6f}  {d_cov:>+10.6f}")

# Table 4: What if TM used per-state E[p|z] instead of global E[p]?
print(f"\n  Table 4: State-corrected TM aggregation vs actual MC")
print(f"  (Uses MC-measured E[p|z] with TM c_nrm distribution)")
print(f"  {'t':>4s}  {'TM_TE':>10s}  {'MC_TE':>10s}  {'TM-MC':>10s}  {'corr_TE':>10s}  {'corr-MC':>10s}  {'improv?':>8s}")
print(f"  {'----':>4s}  {'----------':>10s}  {'----------':>10s}  {'----------':>10s}  {'----------':>10s}  {'----------':>10s}  {'--------':>8s}")

# For this we'd need TM per-state c_nrm, which we can estimate from the MC
for t in range(T_show):
    # Get per-state stats from MC
    p_r = pLvl_rec[t]; c_r_lvl = cLvl_rec[t]; z_r = Mrkv_rec[t]
    p_b = pLvl_base[t]; c_b_lvl = cLvl_base[t]; z_b = Mrkv_base[t]

    # State-corrected: sum_z E[p|z] * E[c_nrm|z] * P(z) for rec and base
    corr_rec = 0.0
    corr_base = 0.0
    for z in range(J):
        mask_r = (z_r == z)
        mask_b = (z_b == z)
        if np.any(mask_r):
            Ep_z_r = np.mean(p_r[mask_r])
            Ec_z_r = np.mean(c_r_lvl[mask_r] / np.maximum(p_r[mask_r], 1e-15))
            corr_rec += Ep_z_r * Ec_z_r * np.mean(mask_r)
        if np.any(mask_b):
            Ep_z_b = np.mean(p_b[mask_b])
            Ec_z_b = np.mean(c_b_lvl[mask_b] / np.maximum(p_b[mask_b], 1e-15))
            corr_base += Ep_z_b * Ec_z_b * np.mean(mask_b)

    corr_te = corr_rec - corr_base
    mc_te_t = mc_te_actual[t]
    tm_te_t = tm_te[t]
    orig_err = tm_te_t - mc_te_t
    corr_err = corr_te - mc_te_t
    improved = "YES" if abs(corr_err) < abs(orig_err) else "no"
    print(f"  {t:>4d}  {tm_te_t:>10.6f}  {mc_te_t:>10.6f}  {orig_err:>+10.6f}  {corr_te:>10.6f}  {corr_err:>+10.6f}  {improved:>8s}")

# NPV comparison
mc_base_c = np.array(mc_base['AggCons'][:T_out]) / N_MC
mc_rec_c = np.array(mc_rec['AggCons'][:T_out]) / N_MC
mc_npv = np.sum((mc_rec_c - mc_base_c) * disc[:T_out])
print(f"\n  NPV Summary:")
print(f"    TM NPV:  {tm_npv:.6f}")
print(f"    MC NPV:  {mc_npv:.6f}")
print(f"    Rel err: {(tm_npv - mc_npv)/abs(mc_npv)*100:+.2f}%")

print(f"\nTotal time: {time()-t0_global:.0f}s")
