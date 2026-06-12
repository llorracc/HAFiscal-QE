"""
Diagnostic: why is per-capita baseline AggCons 13.7% different between TM and MC?

Tests:
  A. E[pLvl]: analytical (TM) vs empirical (MC burn-in)
  B. E[cNrm * pLvl] vs E[cNrm] * E[pLvl] — factorization assumption
  C. Ergodic mNrm distribution: TM grid vs MC empirical
  D. State fractions: TM ergodic vs MC burn-in
"""

# Math reference: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")

import os, sys, numpy as np
from time import time
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
from tm_methods import (
    compute_baseline_tm_data, compute_analytical_mean_pLvl,
    compute_period_aggregates_tm, propagate_experiment_tm,
    run_experiment_tm,
)

# ============================================================
# Setup: single HighSchool type, point beta
# ============================================================
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
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]  # point estimate

N_mc = 50000

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
BaseType.AgentCount = 1  # for TM solve (placeholder)
AggEco.solve()

act_T = AggEco.act_T

# ============================================================
# A. TM: E[pLvl] analytical
# ============================================================
print("=" * 60)
print("DIAGNOSTIC: BASELINE GAP BETWEEN TM AND MC")
print("=" * 60)

E_pLvl_analytical = compute_analytical_mean_pLvl(BaseType)
print(f"\nA. E[pLvl] COMPARISON")
print(f"   Analytical E[pLvl] = {E_pLvl_analytical:.4f}")
print(f"   LivPrb = {BaseType.LivPrb[0][0]:.4f}")
print(f"   PermGroFac = {BaseType.PermGroFac[0][0]:.6f}")
print(f"   T_age = {BaseType.T_age}")
print(f"   pLogInitMean = {getattr(BaseType, 'pLogInitMean', getattr(BaseType, 'pLvlInitMean', 'N/A'))}")
print(f"   pLogInitStd  = {getattr(BaseType, 'pLogInitStd', getattr(BaseType, 'pLvlInitStd', 'N/A'))}")

# ============================================================
# B. MC: burn-in and empirical stats
# ============================================================
print(f"\nB. MC BURN-IN (N={N_mc})")
t0 = time()

eco_mc = deepcopy(AggEco)
for a in eco_mc.agents:
    a.AgentCount = N_mc
    a.seed = 42000
    a.get_economy_data(eco_mc)
eco_mc.solve()
eco_mc.reset()
for a in eco_mc.agents:
    a.initialize_sim()
    a.AggDemandFac = 1.0
    a.RfreeNow = 1.0
    a.CaggNow = 1.0
eco_mc.make_history()

# After burn-in, look at agent state
agent_mc = eco_mc.agents[0]
pLvl_mc = agent_mc.state_now['pLvl']
mNrm_mc = agent_mc.state_now['mNrm']
Mrkv_mc = agent_mc.shocks['Mrkv']

mc_mean_pLvl = np.mean(pLvl_mc)
mc_median_pLvl = np.median(pLvl_mc)
mc_std_pLvl = np.std(pLvl_mc)

print(f"   MC E[pLvl] (burn-in) = {mc_mean_pLvl:.4f}")
print(f"   MC median(pLvl) = {mc_median_pLvl:.4f}")
print(f"   MC std(pLvl) = {mc_std_pLvl:.4f}")
print(f"   Analytical / MC E[pLvl] = {E_pLvl_analytical / mc_mean_pLvl:.4f}")
print(f"   Gap: {(E_pLvl_analytical / mc_mean_pLvl - 1) * 100:+.2f}%")

# ============================================================
# C. MC baseline experiment (per-agent)
# ============================================================
print(f"\nC. MC BASELINE EXPERIMENT")
eco_mc.save_state()
eco_mc.switch_to_counterfactual_mode("base")
eco_mc.act_T = act_T
for a in eco_mc.agents:
    a.T_sim = act_T
    a.EconomyMrkvNow_hist = [0] * act_T
eco_mc.make_idiosyncratic_shock_histories()

base_dict_agg = deepcopy(base_dict)
mc_base = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)

mc_AggCons = np.array(mc_base['AggCons'])
mc_AggInc = np.array(mc_base['AggIncome'])
mc_AggCons_pc = mc_AggCons / N_mc
mc_AggInc_pc = mc_AggInc / N_mc

print(f"   MC AggCons/cap[0] = {mc_AggCons_pc[0]:.6f}")
print(f"   MC AggInc/cap[0] = {mc_AggInc_pc[0]:.6f}")

# Decompose MC period 0: get cNrm, pLvl, TranShk for each agent
# From history arrays
cLvl_splurge_0 = np.concatenate([a.history['cLvl_splurge'][0] for a in eco_mc.agents])
cLvl_0 = np.concatenate([a.history['cLvl'][0] for a in eco_mc.agents])
cNrm_0 = np.concatenate([a.history['cNrm'][0] for a in eco_mc.agents])
pLvl_0 = np.concatenate([a.history['pLvl'][0] for a in eco_mc.agents])
TranShk_0 = np.concatenate([a.shock_history['TranShk'][0] for a in eco_mc.agents])
mNrm_0 = np.concatenate([a.history['mNrm'][0] for a in eco_mc.agents])
Mrkv_0 = np.concatenate([a.shock_history['Mrkv'][0] for a in eco_mc.agents])

Splurge = BaseType.Splurge

print(f"\n   MC period 0 agent-level stats:")
print(f"     E[pLvl]       = {np.mean(pLvl_0):.4f}")
print(f"     E[cNrm]       = {np.mean(cNrm_0):.6f}")
print(f"     E[mNrm]       = {np.mean(mNrm_0):.6f}")
print(f"     E[TranShk]    = {np.mean(TranShk_0):.6f}")
print(f"     E[cNrm*pLvl]  = {np.mean(cNrm_0 * pLvl_0):.6f}")
print(f"     E[cNrm]*E[pLvl] = {np.mean(cNrm_0) * np.mean(pLvl_0):.6f}")
print(f"     Corr(cNrm, pLvl) = {np.corrcoef(cNrm_0, pLvl_0)[0,1]:.6f}")
print(f"     Factorization ratio E[cNrm*pLvl]/(E[cNrm]*E[pLvl]) = "
      f"{np.mean(cNrm_0 * pLvl_0) / (np.mean(cNrm_0) * np.mean(pLvl_0)):.6f}")

# Verify: cLvl_splurge = (1-S)*cNrm*pLvl + S*pLvl*TranShk*AggDemandFac
verify = (1 - Splurge) * cNrm_0 * pLvl_0 + Splurge * pLvl_0 * TranShk_0 * 1.0
print(f"     Verify cLvl_splurge: sum={np.sum(verify):.2f} vs recorded={np.sum(cLvl_splurge_0):.2f}")

# Micro state fractions
for j in range(J):
    frac = np.mean(Mrkv_0 == j)
    print(f"     State {j} fraction: {frac:.4f}")

# ============================================================
# D. TM baseline
# ============================================================
print(f"\nD. TM BASELINE")
BaseType.AgentCount = N_mc  # match MC for comparison
mCount = 50
bl_data = compute_baseline_tm_data(AggEco, mCount=mCount, verbose=False)
bd = bl_data[0]

print(f"   TM E[pLvl] = {bd['E_pLvl']:.4f}")

# Run TM baseline propagation
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
tm_base = propagate_experiment_tm(
    base_agent, bd['ergodic'], [0] * act_T, bd['dist_mGrid'],
    bd['E_pLvl'], act_T=act_T, base_aPol=bd['base_aPol'])

tm_AggCons = np.array(tm_base['AggCons'])
tm_AggCons_pc = tm_AggCons / N_mc

print(f"   TM AggCons/cap[0] = {tm_AggCons_pc[0]:.6f}")

# What is TM's C_splurge_nrm?
# AggCons = AgentCount * E_pLvl * C_splurge_nrm
tm_C_splurge_nrm = tm_AggCons[0] / (N_mc * bd['E_pLvl'])
print(f"   TM C_splurge_nrm[0] = {tm_C_splurge_nrm:.6f}")

# MC's effective C_splurge_nrm
mc_C_splurge_nrm_via_mc_pLvl = mc_AggCons[0] / (N_mc * np.mean(pLvl_0))
print(f"   MC C_splurge_nrm (using MC E[pLvl]) = {mc_C_splurge_nrm_via_mc_pLvl:.6f}")

# What if TM used MC's E[pLvl]?
tm_AggCons_with_mc_pLvl = N_mc * np.mean(pLvl_0) * tm_C_splurge_nrm
print(f"\n   TM AggCons/cap using MC E[pLvl] = {tm_AggCons_with_mc_pLvl / N_mc:.6f}")
print(f"   MC AggCons/cap                  = {mc_AggCons_pc[0]:.6f}")
print(f"   Gap with matched E[pLvl]: {(tm_AggCons_with_mc_pLvl / N_mc / mc_AggCons_pc[0] - 1) * 100:+.2f}%")

# Ergodic distribution state fractions
ergodic = bd['ergodic']
M = mCount
for j in range(J):
    tm_frac = np.sum(ergodic[j * M:(j + 1) * M])
    print(f"   TM state {j} fraction: {tm_frac:.4f}")

# ============================================================
# E. Summary
# ============================================================
print(f"\n{'='*60}")
print("SUMMARY")
print("=" * 60)
gap_pLvl = (bd['E_pLvl'] / np.mean(pLvl_0) - 1) * 100
gap_cNrm = (tm_C_splurge_nrm / mc_C_splurge_nrm_via_mc_pLvl - 1) * 100
gap_total = (tm_AggCons_pc[0] / mc_AggCons_pc[0] - 1) * 100
gap_factor = (np.mean(cNrm_0 * pLvl_0) / (np.mean(cNrm_0) * np.mean(pLvl_0)) - 1) * 100

print(f"  E[pLvl] gap (TM analytical vs MC):       {gap_pLvl:+.2f}%")
print(f"  C_splurge_nrm gap (TM vs MC):             {gap_cNrm:+.2f}%")
print(f"  Factorization error E[c*p]/(E[c]*E[p])-1: {gap_factor:+.2f}%")
print(f"  Total AggCons/cap gap:                     {gap_total:+.2f}%")
print(f"  Expected gap from E[pLvl] + C_nrm:         {gap_pLvl + gap_cNrm:+.2f}%")
print(f"  Factorization contributes:                  {gap_factor:+.2f}%")
print(f"  Total ≈ E[pLvl] gap + C_nrm gap - factor:  {gap_pLvl + gap_cNrm - gap_factor:+.2f}%")
print(f"\n  Time: {time() - t0:.1f}s")
