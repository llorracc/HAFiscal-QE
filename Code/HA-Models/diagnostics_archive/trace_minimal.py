"""
Minimal diagnostic: 1 education group, 1 beta, no recession.
Trace exactly what MC and TM do at period 0 for the UI experiment.

Goal: understand WHY the consumption TE differs by comparing
the actual per-agent MC computation with the TM computation
on the same distribution.
"""

import os
import sys
import numpy as np
from copy import deepcopy

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import (
    build_tm_agg_fiscal, find_ergodic_distribution,
    build_experiment_period_tm, compute_period_aggregates_tm,
    compute_analytical_mean_pLvl, _apply_micro_transition,
)

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

J = num_base_MrkvStates
N = 500000
MCOUNT = 200

# Single education group (highschool), single beta
BaseType = AggFiscalType(**init_highschool)
BaseType.cycles = 0
BaseType.AgentCount = N
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]  # single beta point

AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

# Set up IncShkDstn (same as all other scripts)
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
AggEco.solve()
act_T = AggEco.act_T
Splurge = BaseType.Splurge
Rfree = BaseType.Rfree[0]
PermGroFac = BaseType.PermGroFac[0][0]
E_pLvl = compute_analytical_mean_pLvl(BaseType)
sol = BaseType.solution[0]

# UI path: no recession, just the experiment macro states
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

print(f"Setup: 1 type, 1 beta={BaseType.DiscFac:.4f}, N={N}")
print(f"J={J}, Splurge={Splurge:.4f}, Rfree={Rfree}, PermGroFac={PermGroFac:.5f}")
print(f"IncUnemp={BaseType.IncUnemp}, IncUnempNoBenefits={BaseType.IncUnempNoBenefits}")
print(f"E_pLvl={E_pLvl:.4f}")

# ============================================================
# MC: Run baseline and UI, extract EVERYTHING at period 0
# ============================================================
print(f"\n{'='*70}")
print("MC: Running baseline and UI experiments")
print("="*70)

base_dict_agg = deepcopy(base_dict)

def setup_mc():
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N
        a.seed = 42000
        a.get_economy_data(eco)
    eco.solve()
    eco.reset()
    for a in eco.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    eco.make_history()
    eco.save_state()
    eco.switch_to_counterfactual_mode("base")
    eco.act_T = act_T
    for a in eco.agents:
        a.T_sim = act_T
        a.EconomyMrkvNow_hist = [0] * act_T
    eco.make_idiosyncratic_shock_histories()
    return eco

from time import time
t0 = time()
eco_mc = setup_mc()

# Baseline experiment
base_r = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
eco_mc.store_baseline(base_r['AggCons'])

# UI experiment
eco_ui_mc = deepcopy(eco_mc)
eco_ui_mc.switch_shock_type('UI')
eco_ui_mc.solve()
d_ui = base_dict_agg.copy()
d_ui.update(UI_changes)
d_ui['EconomyMrkv_init'] = ui_path
ui_r = eco_ui_mc.run_experiment(**d_ui, Full_Output=True)
print(f"MC done in {time()-t0:.0f}s")

# Extract period 0 agent-level data
mc_base_mNrm = base_r['mNrm_all'][0]
mc_base_cNrm = base_r['cNrm_all'][0]
mc_base_TranShk = base_r['TranShk_all'][0]
mc_base_pLvl = base_r['pLvl_all'][0]
mc_base_Mrkv = base_r['Mrkv_hist'][0]
mc_base_micro = mc_base_Mrkv % J

mc_ui_mNrm = ui_r['mNrm_all'][0]
mc_ui_cNrm = ui_r['cNrm_all'][0]
mc_ui_TranShk = ui_r['TranShk_all'][0]
mc_ui_pLvl = ui_r['pLvl_all'][0]
mc_ui_Mrkv = ui_r['Mrkv_hist'][0]
mc_ui_micro = mc_ui_Mrkv % J

# ============================================================
# Basic MC period-0 summary
# ============================================================
print(f"\n{'='*70}")
print("MC Period-0 Summary")
print("="*70)

for label, mNrm, cNrm, TranShk, pLvl, micro in [
    ("Base", mc_base_mNrm, mc_base_cNrm, mc_base_TranShk, mc_base_pLvl, mc_base_micro),
    ("UI", mc_ui_mNrm, mc_ui_cNrm, mc_ui_TranShk, mc_ui_pLvl, mc_ui_micro)]:
    print(f"\n  {label}:")
    print(f"    Per-state fracs: {[np.mean(micro==j) for j in range(J)]}")
    for j in range(J):
        mask = micro == j
        n_j = np.sum(mask)
        if n_j > 0:
            print(f"    State {j} (n={n_j}):")
            print(f"      E[mNrm]={np.mean(mNrm[mask]):.6f}  E[cNrm]={np.mean(cNrm[mask]):.6f}  "
                  f"E[TranShk]={np.mean(TranShk[mask]):.6f}  E[pLvl]={np.mean(pLvl[mask]):.4f}")

# MC consumption TE
mc_base_cons_nrm = np.mean((1-Splurge)*mc_base_cNrm + Splurge*mc_base_TranShk)
mc_ui_cons_nrm = np.mean((1-Splurge)*mc_ui_cNrm + Splurge*mc_ui_TranShk)
mc_cons_te_nrm = mc_ui_cons_nrm - mc_base_cons_nrm
mc_cons_te_lvl = mc_cons_te_nrm * E_pLvl

print(f"\n  MC cons (nrm): base={mc_base_cons_nrm:.8f}, UI={mc_ui_cons_nrm:.8f}")
print(f"  MC cons TE (nrm): {mc_cons_te_nrm:.8f}")
print(f"  MC cons TE (levels): {mc_cons_te_lvl:.8f}")

# ============================================================
# TM: Build ergodic and compute period-0 the same way
# ============================================================
print(f"\n{'='*70}")
print("TM Period-0 Computation")
print("="*70)

# Ergodic under base config
tm_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
dist_mGrid = tm_data['dist_mGrid']
M = len(dist_mGrid)

# Base agent and cPol
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
_, cPol_base = build_experiment_period_tm(base_agent, 0, 0, dist_mGrid, Cratio=1.0)

# UI agent and cPol
eco_ui_tm = deepcopy(AggEco)
eco_ui_tm.switch_shock_type("UI")
eco_ui_tm.solve()
ui_agent = eco_ui_tm.agents[0]
_, cPol_ui = build_experiment_period_tm(ui_agent, ui_path[0], ui_path[1], dist_mGrid, Cratio=1.0)

# Per-state ergodic summary
print(f"\n  TM ergodic per-state:")
for j in range(J):
    dist_j = ergodic[j*M:(j+1)*M]
    frac_j = np.sum(dist_j)
    mean_mNrm = np.dot(dist_mGrid, dist_j) / frac_j if frac_j > 0 else 0
    mean_cNrm_base = np.dot(cPol_base[j], dist_j) / frac_j if frac_j > 0 else 0
    mean_cNrm_ui = np.dot(cPol_ui[j], dist_j) / frac_j if frac_j > 0 else 0
    print(f"    State {j}: frac={frac_j:.6f}, E[mNrm]={mean_mNrm:.6f}, "
          f"E[cNrm_base]={mean_cNrm_base:.6f}, E[cNrm_ui]={mean_cNrm_ui:.6f}")

# TM consumption from ergodic (no micro transition)
E_TranShk = np.array([1.0, 0.7, 0.7, 0.5])
erg_fracs = np.array([np.sum(ergodic[j*M:(j+1)*M]) for j in range(J)])
C_nrm_base_erg = sum(np.dot(cPol_base[j], ergodic[j*M:(j+1)*M]) for j in range(J))
C_nrm_ui_erg = sum(np.dot(cPol_ui[j], ergodic[j*M:(j+1)*M]) for j in range(J))

tm_base_cons_nrm = (1-Splurge)*C_nrm_base_erg + Splurge*np.dot(erg_fracs, E_TranShk)
tm_ui_cons_nrm_no_micro = (1-Splurge)*C_nrm_ui_erg + Splurge*np.dot(erg_fracs, E_TranShk)

print(f"\n  TM cons from ergodic (no micro transition):")
print(f"    base: {tm_base_cons_nrm:.8f}")
print(f"    UI (same dist, UI cPol): {tm_ui_cons_nrm_no_micro:.8f}")
print(f"    TE (policy effect only): {(tm_ui_cons_nrm_no_micro - tm_base_cons_nrm)*E_pLvl:.8f}")

# ============================================================
# KEY TEST: Evaluate TM cFunc at MC's actual mNrm, per agent
# ============================================================
print(f"\n{'='*70}")
print("KEY TEST: TM cFunc evaluated at MC agents' actual mNrm")
print("="*70)

# For each MC agent, evaluate TM's cFunc at their mNrm
# This isolates the distribution effect from the cFunc effect

def eval_cPol_at_mNrm(cPol, dist_mGrid, mNrm_values, micro_states, J):
    """Evaluate TM cPol at specific mNrm values for each agent."""
    cNrm_out = np.zeros_like(mNrm_values)
    for j in range(J):
        mask = micro_states == j
        if np.any(mask):
            cNrm_out[mask] = np.interp(mNrm_values[mask], dist_mGrid, cPol[j])
    return cNrm_out

# Baseline: TM base cPol at MC base mNrm
tm_cNrm_at_mc_base = eval_cPol_at_mNrm(cPol_base, dist_mGrid, mc_base_mNrm, mc_base_micro, J)
# UI: TM UI cPol at MC UI mNrm
tm_cNrm_at_mc_ui = eval_cPol_at_mNrm(cPol_ui, dist_mGrid, mc_ui_mNrm, mc_ui_micro, J)

hybrid_base_cons_nrm = np.mean((1-Splurge)*tm_cNrm_at_mc_base + Splurge*mc_base_TranShk)
hybrid_ui_cons_nrm = np.mean((1-Splurge)*tm_cNrm_at_mc_ui + Splurge*mc_ui_TranShk)
hybrid_te_nrm = hybrid_ui_cons_nrm - hybrid_base_cons_nrm

print(f"  Hybrid (TM cFunc, MC dist):")
print(f"    base cons (nrm): {hybrid_base_cons_nrm:.8f}")
print(f"    UI cons (nrm):   {hybrid_ui_cons_nrm:.8f}")
print(f"    TE (nrm):        {hybrid_te_nrm:.8f}")
print(f"    TE (levels):     {hybrid_te_nrm * E_pLvl:.8f}")

print(f"\n  Per-agent cNrm comparison (MC vs TM cFunc at MC mNrm):")
for j in range(J):
    mask_b = mc_base_micro == j
    mask_u = mc_ui_micro == j
    if np.sum(mask_b) > 10:
        mc_mean = np.mean(mc_base_cNrm[mask_b])
        tm_mean = np.mean(tm_cNrm_at_mc_base[mask_b])
        print(f"    Base state {j}: MC cNrm={mc_mean:.6f}, TM cFunc(MC mNrm)={tm_mean:.6f}, diff={tm_mean-mc_mean:+.2e}")
    if np.sum(mask_u) > 10:
        mc_mean = np.mean(mc_ui_cNrm[mask_u])
        tm_mean = np.mean(tm_cNrm_at_mc_ui[mask_u])
        print(f"    UI   state {j}: MC cNrm={mc_mean:.6f}, TM cFunc(MC mNrm)={tm_mean:.6f}, diff={tm_mean-mc_mean:+.2e}")

# ============================================================
# DECOMPOSITION: What produces the MC consumption at period 0?
# ============================================================
print(f"\n{'='*70}")
print("DECOMPOSITION: MC consumption = non-splurge + splurge")
print("="*70)

# Non-splurge = (1-S) * E[cNrm]
# Splurge = S * E[TranShk]
# Note: in levels, both are multiplied by pLvl per agent.
# But since we showed pLvl doesn't matter (uniform pLvl test), use nrm.

mc_base_nonsplurge = (1-Splurge) * np.mean(mc_base_cNrm)
mc_base_splurge = Splurge * np.mean(mc_base_TranShk)
mc_ui_nonsplurge = (1-Splurge) * np.mean(mc_ui_cNrm)
mc_ui_splurge = Splurge * np.mean(mc_ui_TranShk)

print(f"              nonsplurge    splurge      total")
print(f"  MC base:    {mc_base_nonsplurge:.8f}  {mc_base_splurge:.8f}  {mc_base_nonsplurge+mc_base_splurge:.8f}")
print(f"  MC UI:      {mc_ui_nonsplurge:.8f}  {mc_ui_splurge:.8f}  {mc_ui_nonsplurge+mc_ui_splurge:.8f}")
print(f"  MC TE:      {mc_ui_nonsplurge-mc_base_nonsplurge:.8f}  {mc_ui_splurge-mc_base_splurge:.8f}  {mc_cons_te_nrm:.8f}")

# TM from ergodic
tm_base_nonsplurge = (1-Splurge) * C_nrm_base_erg
tm_base_splurge = Splurge * np.dot(erg_fracs, E_TranShk)
tm_ui_nonsplurge_no_micro = (1-Splurge) * C_nrm_ui_erg
tm_ui_splurge_no_micro = Splurge * np.dot(erg_fracs, E_TranShk)

print(f"\n  TM base:    {tm_base_nonsplurge:.8f}  {tm_base_splurge:.8f}  {tm_base_cons_nrm:.8f}")
print(f"  TM UI(no μ):{tm_ui_nonsplurge_no_micro:.8f}  {tm_ui_splurge_no_micro:.8f}  {tm_ui_cons_nrm_no_micro:.8f}")
print(f"  TM TE(no μ):{tm_ui_nonsplurge_no_micro-tm_base_nonsplurge:.8f}  "
      f"{tm_ui_splurge_no_micro-tm_base_splurge:.8f}  "
      f"{tm_ui_cons_nrm_no_micro-tm_base_cons_nrm:.8f}")

# Difference between MC and TM at the component level
print(f"\n  Diff (MC - TM):")
print(f"    base nonsplurge: {mc_base_nonsplurge - tm_base_nonsplurge:+.8f}")
print(f"    base splurge:    {mc_base_splurge - tm_base_splurge:+.8f}")
print(f"    UI nonsplurge:   {mc_ui_nonsplurge - tm_ui_nonsplurge_no_micro:+.8f}")
print(f"    UI splurge:      {mc_ui_splurge - tm_ui_splurge_no_micro:+.8f}")

# ============================================================
# WHAT DIFFERS: MC baseline vs TM ergodic mNrm distributions
# ============================================================
print(f"\n{'='*70}")
print("MC vs TM: Baseline mNrm distribution comparison")
print("="*70)

# For each MC agent, which TM grid bin would they fall in?
# Compare MC histogram with TM ergodic
for j in range(J):
    mask = mc_base_micro == j
    n_j = np.sum(mask)
    if n_j < 10:
        continue
    mc_vals = mc_base_mNrm[mask]

    # MC statistics
    mc_mean = np.mean(mc_vals)
    mc_std = np.std(mc_vals)
    mc_p10 = np.percentile(mc_vals, 10)
    mc_p50 = np.percentile(mc_vals, 50)
    mc_p90 = np.percentile(mc_vals, 90)

    # TM statistics
    tm_dist_j = ergodic[j*M:(j+1)*M]
    tm_frac = np.sum(tm_dist_j)
    tm_pdf = tm_dist_j / tm_frac
    tm_mean = np.dot(dist_mGrid, tm_pdf)
    tm_cdf = np.cumsum(tm_pdf)
    tm_p10 = dist_mGrid[np.searchsorted(tm_cdf, 0.10)]
    tm_p50 = dist_mGrid[np.searchsorted(tm_cdf, 0.50)]
    tm_p90 = dist_mGrid[np.searchsorted(tm_cdf, 0.90)]

    print(f"\n  State {j} (MC n={n_j}, frac MC={n_j/N:.6f}, TM={tm_frac:.6f}):")
    print(f"    Mean mNrm:  MC={mc_mean:.6f}  TM={tm_mean:.6f}  diff={tm_mean-mc_mean:+.6f}")
    print(f"    p10:        MC={mc_p10:.4f}    TM={tm_p10:.4f}")
    print(f"    p50:        MC={mc_p50:.4f}    TM={tm_p50:.4f}")
    print(f"    p90:        MC={mc_p90:.4f}    TM={tm_p90:.4f}")

    # E[cFunc(mNrm)] comparison
    mc_mean_c = np.mean(mc_base_cNrm[mask])
    tm_mean_c = np.dot(cPol_base[j], tm_dist_j) / tm_frac
    print(f"    E[cNrm]:    MC={mc_mean_c:.6f}  TM={tm_mean_c:.6f}  diff={tm_mean_c-mc_mean_c:+.6f}")

print("\nDone.")
