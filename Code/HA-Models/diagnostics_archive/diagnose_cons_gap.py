"""
Definitive test of the consumption TE gap hypothesis.

Hypothesis: The gap comes from _apply_micro_transition preserving mNrm
when agents change states, while MC agents get new TranShk.

Test approach:
1. Decompose TM consumption into splurge + non-splurge components
2. Compare each component with MC
3. Build a modified micro transition that shifts mNrm by the TranShk
   differential and see if it closes the gap
4. Also test alternative hypotheses:
   a. Is the gap from cFunc differences (base vs UI solution)?
   b. Is the gap from grid evaluation vs exact mNrm?
"""

import os
import sys
import numpy as np
from time import time
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
    compute_baseline_tm_data,
    propagate_experiment_tm,
    compute_analytical_mean_pLvl,
    build_tm_agg_fiscal,
    find_ergodic_distribution,
    _apply_micro_transition,
    adapt_initial_distribution,
    compute_period_aggregates_tm,
    build_experiment_period_tm,
)

# ============================================================
# Setup
# ============================================================
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

N = 500000  # large N for precise MC reference
J = num_base_MrkvStates
MCOUNT = 200  # converged grid
Splurge_val = None  # will extract from agent

BaseType = AggFiscalType(**init_highschool)
BaseType.cycles = 0
BaseType.AgentCount = N
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
base_dict_agg = deepcopy(base_dict)
Splurge_val = BaseType.Splurge

ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

E_pLvl = compute_analytical_mean_pLvl(BaseType)
E_TranShk = np.array([1.0, 0.7, 0.7, 0.5])

print(f"J={J}, Splurge={Splurge_val:.4f}, E_pLvl={E_pLvl:.4f}, N={N}")
print(f"E[TranShk] per state: {E_TranShk}")

# ============================================================
# TEST A: Decompose TM consumption into splurge + non-splurge
# ============================================================
print("\n" + "=" * 70)
print("TEST A: Decompose TM period-0 consumption")
print("=" * 70)

# Build baseline ergodic
tm_base_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_base_data['TranMatrix'])
dist_mGrid = tm_base_data['dist_mGrid']
M = len(dist_mGrid)

# Get base and UI CondMrkvArrays
BaseType_base = deepcopy(BaseType)
BaseType_base.update_mrkv_array("base")
micro_normal = BaseType_base.CondMrkvArrays[0]

eco_ui = deepcopy(AggEco)
eco_ui.switch_shock_type("UI")
eco_ui.solve()
ui_agent = eco_ui.agents[0]
micro_ui = ui_agent.CondMrkvArrays[ui_path[0]]

# Apply micro transitions
dist_base = _apply_micro_transition(ergodic.copy(), micro_normal, M)
dist_ui = _apply_micro_transition(ergodic.copy(), micro_ui, M)

# Get micro fractions
fracs_base = np.array([np.sum(dist_base[j*M:(j+1)*M]) for j in range(J)])
fracs_ui = np.array([np.sum(dist_ui[j*M:(j+1)*M]) for j in range(J)])

# Splurge component: S * dot(fracs, E_TranShk)
splurge_base = Splurge_val * np.dot(fracs_base, E_TranShk)
splurge_ui = Splurge_val * np.dot(fracs_ui, E_TranShk)
splurge_TE = splurge_ui - splurge_base

# Non-splurge: need cPol from build_experiment_period_tm
# Baseline: use base agent, macro_t=0
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
_, cPol_base = build_experiment_period_tm(
    base_agent, 0, 0, dist_mGrid, Cratio=1.0)
C_nrm_base = sum(np.dot(cPol_base[j], dist_base[j*M:(j+1)*M]) for j in range(J))
nonsplurge_base = (1 - Splurge_val) * C_nrm_base

# UI: use UI agent, macro_t = ui_path[0] = 2
_, cPol_ui = build_experiment_period_tm(
    ui_agent, ui_path[0], ui_path[1], dist_mGrid, Cratio=1.0)
C_nrm_ui = sum(np.dot(cPol_ui[j], dist_ui[j*M:(j+1)*M]) for j in range(J))
nonsplurge_ui = (1 - Splurge_val) * C_nrm_ui

nonsplurge_TE = nonsplurge_ui - nonsplurge_base

total_cons_base = nonsplurge_base + splurge_base
total_cons_ui = nonsplurge_ui + splurge_ui
total_TE = total_cons_ui - total_cons_base

print(f"\nTM decomposition (normalized, per-agent):")
print(f"  Component        Base         UI          TE")
print(f"  Splurge:    {splurge_base:.8f}  {splurge_ui:.8f}  {splurge_TE:.8f}")
print(f"  Non-splurge:{nonsplurge_base:.8f}  {nonsplurge_ui:.8f}  {nonsplurge_TE:.8f}")
print(f"  Total:      {total_cons_base:.8f}  {total_cons_ui:.8f}  {total_TE:.8f}")
print(f"\nIn levels (per-cap): total TE = {total_TE * E_pLvl:.8f}")

# ============================================================
# TEST B: MC decomposition (single large seed)
# ============================================================
print("\n" + "=" * 70)
print("TEST B: MC period-0 consumption decomposition")
print("=" * 70)

def run_mc_decomposed(shock_type, changes_dict, path, seed=0):
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N
        a.seed = seed * 1000
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
    base_r = eco.run_experiment(**base_dict_agg, Full_Output=True)
    eco.store_baseline(base_r['AggCons'])

    if shock_type == 'base':
        r = base_r
        eco_exp = eco
    else:
        eco_exp = deepcopy(eco)
        eco_exp.switch_shock_type(shock_type)
        eco_exp.solve()
        d = base_dict_agg.copy()
        d.update(changes_dict)
        d['EconomyMrkv_init'] = path
        r = eco_exp.run_experiment(**d, Full_Output=True)

    agent = eco_exp.agents[0]
    N_act = sum(a.AgentCount for a in eco_exp.agents)

    # Period 0 data
    mrkv_0 = agent.shock_history['Mrkv'][0]
    micro_0 = mrkv_0 % J
    transhk_0 = agent.shock_history['TranShk'][0]
    pLvl_0 = r['pLvl_all'][0]
    cNrm_0 = r['cNrm_all'][0]
    mNrm_0 = r['mNrm_all'][0]

    # Splurge: S * TranShk * pLvl * AggDemandFac (per agent, then sum)
    # From AggFiscalModel get_states, cLvl_splurge = (1-S)*cFunc(mNrm)*pLvl + S*TranShk*pLvl*AggDemandFac
    AggDemandFac_0 = 1.0  # for non-AD experiment
    splurge_total = np.sum(Splurge_val * transhk_0 * pLvl_0 * AggDemandFac_0)
    nonsplurge_total = np.sum((1 - Splurge_val) * cNrm_0 * pLvl_0)

    fracs = np.array([np.mean(micro_0 == j) for j in range(J)])
    mean_mNrm_by_state = np.array([
        np.mean(mNrm_0[micro_0 == j]) if np.sum(micro_0 == j) > 0 else 0.0
        for j in range(J)])
    mean_cNrm_by_state = np.array([
        np.mean(cNrm_0[micro_0 == j]) if np.sum(micro_0 == j) > 0 else 0.0
        for j in range(J)])
    mean_transhk_by_state = np.array([
        np.mean(transhk_0[micro_0 == j]) if np.sum(micro_0 == j) > 0 else 0.0
        for j in range(J)])

    return {
        'splurge_total': splurge_total / N_act,
        'nonsplurge_total': nonsplurge_total / N_act,
        'fracs': fracs,
        'mean_mNrm': mean_mNrm_by_state,
        'mean_cNrm': mean_cNrm_by_state,
        'mean_transhk': mean_transhk_by_state,
        'AggCons_0': r['AggCons'][0] / N_act,
        'AggIncome_0': r['AggIncome'][0] / N_act,
    }

NUM_SEEDS = 3
print(f"Running MC with {NUM_SEEDS} seeds, N={N}...")

mc_base_runs = []
mc_ui_runs = []
for s in range(NUM_SEEDS):
    t0 = time()
    mc_base_runs.append(run_mc_decomposed('base', base_dict, [0]*act_T, seed=s))
    mc_ui_runs.append(run_mc_decomposed('UI', UI_changes, ui_path, seed=s))
    print(f"  Seed {s}: {time()-t0:.0f}s")

# Average MC results
def avg_dict(runs, key):
    return np.mean([r[key] for r in runs], axis=0)

mc_base_splurge = avg_dict(mc_base_runs, 'splurge_total')
mc_ui_splurge = avg_dict(mc_ui_runs, 'splurge_total')
mc_base_nonsplurge = avg_dict(mc_base_runs, 'nonsplurge_total')
mc_ui_nonsplurge = avg_dict(mc_ui_runs, 'nonsplurge_total')
mc_base_mNrm = avg_dict(mc_base_runs, 'mean_mNrm')
mc_ui_mNrm = avg_dict(mc_ui_runs, 'mean_mNrm')
mc_base_cNrm = avg_dict(mc_base_runs, 'mean_cNrm')
mc_ui_cNrm = avg_dict(mc_ui_runs, 'mean_cNrm')
mc_base_transhk = avg_dict(mc_base_runs, 'mean_transhk')
mc_ui_transhk = avg_dict(mc_ui_runs, 'mean_transhk')
mc_base_fracs = avg_dict(mc_base_runs, 'fracs')
mc_ui_fracs = avg_dict(mc_ui_runs, 'fracs')

mc_splurge_TE = mc_ui_splurge - mc_base_splurge
mc_nonsplurge_TE = mc_ui_nonsplurge - mc_base_nonsplurge
mc_total_TE = mc_splurge_TE + mc_nonsplurge_TE

print(f"\nMC decomposition (per-cap, levels):")
print(f"  Component        Base           UI            TE")
print(f"  Splurge:    {mc_base_splurge:12.6f}  {mc_ui_splurge:12.6f}  {mc_splurge_TE:12.6f}")
print(f"  Non-splurge:{mc_base_nonsplurge:12.6f}  {mc_ui_nonsplurge:12.6f}  {mc_nonsplurge_TE:12.6f}")
print(f"  Total:      {mc_base_splurge+mc_base_nonsplurge:12.6f}  {mc_ui_splurge+mc_ui_nonsplurge:12.6f}  {mc_total_TE:12.6f}")

# Convert TM to levels for comparison
tm_splurge_TE_lvl = splurge_TE * E_pLvl
tm_nonsplurge_TE_lvl = nonsplurge_TE * E_pLvl
tm_total_TE_lvl = total_TE * E_pLvl

print(f"\n--- TM vs MC treatment effect comparison (levels, per-cap) ---")
print(f"  Component      TM            MC          Diff       Rel err")
print(f"  Splurge:    {tm_splurge_TE_lvl:10.6f}  {mc_splurge_TE:10.6f}  {tm_splurge_TE_lvl-mc_splurge_TE:10.6f}  {(tm_splurge_TE_lvl-mc_splurge_TE)/max(abs(mc_splurge_TE),1e-15)*100:+.1f}%")
print(f"  Non-splurge:{tm_nonsplurge_TE_lvl:10.6f}  {mc_nonsplurge_TE:10.6f}  {tm_nonsplurge_TE_lvl-mc_nonsplurge_TE:10.6f}  {(tm_nonsplurge_TE_lvl-mc_nonsplurge_TE)/max(abs(mc_nonsplurge_TE),1e-15)*100:+.1f}%")
print(f"  Total:      {tm_total_TE_lvl:10.6f}  {mc_total_TE:10.6f}  {tm_total_TE_lvl-mc_total_TE:10.6f}  {(tm_total_TE_lvl-mc_total_TE)/max(abs(mc_total_TE),1e-15)*100:+.1f}%")

# ============================================================
# TEST C: Per-state mNrm and cNrm comparison
# ============================================================
print("\n" + "=" * 70)
print("TEST C: Per-state mean mNrm and cNrm")
print("=" * 70)

# TM per-state mean mNrm
tm_base_mean_mNrm = np.array([
    np.dot(dist_mGrid, dist_base[j*M:(j+1)*M]) / max(np.sum(dist_base[j*M:(j+1)*M]), 1e-30)
    for j in range(J)])
tm_ui_mean_mNrm = np.array([
    np.dot(dist_mGrid, dist_ui[j*M:(j+1)*M]) / max(np.sum(dist_ui[j*M:(j+1)*M]), 1e-30)
    for j in range(J)])

# TM per-state mean cNrm
tm_base_mean_cNrm = np.array([
    np.dot(cPol_base[j], dist_base[j*M:(j+1)*M]) / max(np.sum(dist_base[j*M:(j+1)*M]), 1e-30)
    for j in range(J)])
tm_ui_mean_cNrm = np.array([
    np.dot(cPol_ui[j], dist_ui[j*M:(j+1)*M]) / max(np.sum(dist_ui[j*M:(j+1)*M]), 1e-30)
    for j in range(J)])

print(f"\nMean mNrm by state:")
print(f"  State  TM_base      TM_UI      MC_base      MC_UI      TM_UI-TM_base  MC_UI-MC_base")
for j in range(J):
    print(f"  [{j}]  {tm_base_mean_mNrm[j]:10.4f}  {tm_ui_mean_mNrm[j]:10.4f}  "
          f"{mc_base_mNrm[j]:10.4f}  {mc_ui_mNrm[j]:10.4f}  "
          f"{tm_ui_mean_mNrm[j]-tm_base_mean_mNrm[j]:+12.6f}  "
          f"{mc_ui_mNrm[j]-mc_base_mNrm[j]:+12.6f}")

print(f"\nMean cNrm by state:")
print(f"  State  TM_base      TM_UI      MC_base      MC_UI      TM_UI-TM_base  MC_UI-MC_base")
for j in range(J):
    print(f"  [{j}]  {tm_base_mean_cNrm[j]:10.4f}  {tm_ui_mean_cNrm[j]:10.4f}  "
          f"{mc_base_cNrm[j]:10.4f}  {mc_ui_cNrm[j]:10.4f}  "
          f"{tm_ui_mean_cNrm[j]-tm_base_mean_cNrm[j]:+12.6f}  "
          f"{mc_ui_cNrm[j]-mc_base_cNrm[j]:+12.6f}")

print(f"\nMean TranShk by state (MC only):")
for j in range(J):
    print(f"  [{j}]  base={mc_base_transhk[j]:.6f}  UI={mc_ui_transhk[j]:.6f}  "
          f"diff={mc_ui_transhk[j]-mc_base_transhk[j]:+.6f}")

# ============================================================
# TEST D: Modified micro transition with mNrm shift
# ============================================================
print("\n" + "=" * 70)
print("TEST D: Micro transition with mNrm shift (hypothesis test)")
print("=" * 70)

def apply_micro_transition_with_mNrm_shift(dist, micro_trans_new, micro_trans_old,
                                             M, dist_mGrid, E_TranShk):
    """
    Apply micro transition AND shift mNrm for income differential.

    For mass moving from state j to state j', shift mNrm by
    E_TranShk[j'] - E_TranShk[j] (the income change from switching states).

    This is done by interpolating onto the shifted grid.
    """
    J_loc = micro_trans_new.shape[0]
    new_dist = np.zeros_like(dist)

    for j_src in range(J_loc):
        src_slice = dist[j_src * M: (j_src + 1) * M]
        if np.sum(src_slice) < 1e-30:
            continue

        for j_dst in range(J_loc):
            prob_new = micro_trans_new[j_src, j_dst]
            prob_old = micro_trans_old[j_src, j_dst]

            if prob_new < 1e-15 and prob_old < 1e-15:
                continue

            # Mass that moves under the new transition but not the old
            # (or vice versa). The "extra" mass that stays due to UI.
            # Actually, just apply the new transition with mNrm shift.
            if prob_new < 1e-15:
                continue

            delta_TranShk = E_TranShk[j_dst] - E_TranShk[j_src]
            contributing_mass = prob_new * src_slice

            if abs(delta_TranShk) < 1e-12:
                # No shift needed
                new_dist[j_dst * M: (j_dst + 1) * M] += contributing_mass
            else:
                # Shift mNrm by delta_TranShk via interpolation
                shifted_grid = dist_mGrid + delta_TranShk
                # Interpolate contributing_mass from shifted_grid onto dist_mGrid
                shifted_mass = np.interp(dist_mGrid, shifted_grid, contributing_mass,
                                          left=0.0, right=0.0)
                # Preserve total mass
                total_orig = np.sum(contributing_mass)
                total_shifted = np.sum(shifted_mass)
                if total_shifted > 1e-30:
                    shifted_mass *= total_orig / total_shifted
                new_dist[j_dst * M: (j_dst + 1) * M] += shifted_mass

    s = np.sum(new_dist)
    if s > 0:
        new_dist /= s
    return new_dist

# Apply modified UI micro transition with mNrm shift
dist_ui_shifted = apply_micro_transition_with_mNrm_shift(
    ergodic.copy(), micro_ui, micro_normal, M, dist_mGrid, E_TranShk)

# Compute consumption from shifted distribution
fracs_ui_shifted = np.array([np.sum(dist_ui_shifted[j*M:(j+1)*M]) for j in range(J)])
C_nrm_ui_shifted = sum(np.dot(cPol_ui[j], dist_ui_shifted[j*M:(j+1)*M]) for j in range(J))
nonsplurge_ui_shifted = (1 - Splurge_val) * C_nrm_ui_shifted

# Splurge is the same (depends on fracs and E_TranShk, not mNrm)
splurge_ui_shifted = Splurge_val * np.dot(fracs_ui_shifted, E_TranShk)
total_ui_shifted = nonsplurge_ui_shifted + splurge_ui_shifted

TE_shifted = (total_ui_shifted - total_cons_base) * E_pLvl

# Also compute: what if we use the ORIGINAL micro transition (no shift)?
TE_no_shift = total_TE * E_pLvl

print(f"\nConsumption TE comparison (levels, per-cap):")
print(f"  MC reference:               {mc_total_TE:.8f}")
print(f"  TM (no mNrm shift):         {TE_no_shift:.8f}  (err: {(TE_no_shift-mc_total_TE)/mc_total_TE*100:+.1f}%)")
print(f"  TM (with mNrm shift):       {TE_shifted:.8f}  (err: {(TE_shifted-mc_total_TE)/mc_total_TE*100:+.1f}%)")

print(f"\nFraction check (should be same with and without shift):")
print(f"  No shift:   {fracs_ui}")
print(f"  With shift: {fracs_ui_shifted}")

# Per-state mean mNrm with shift
tm_ui_shifted_mean_mNrm = np.array([
    np.dot(dist_mGrid, dist_ui_shifted[j*M:(j+1)*M]) / max(np.sum(dist_ui_shifted[j*M:(j+1)*M]), 1e-30)
    for j in range(J)])
print(f"\nMean mNrm after shift:")
print(f"  State  No_shift     Shifted      MC_UI        Diff(shift-MC)")
for j in range(J):
    print(f"  [{j}]  {tm_ui_mean_mNrm[j]:10.4f}  {tm_ui_shifted_mean_mNrm[j]:10.4f}  "
          f"{mc_ui_mNrm[j]:10.4f}  {tm_ui_shifted_mean_mNrm[j]-mc_ui_mNrm[j]:+10.4f}")

# ============================================================
# TEST E: Alternative hypothesis — is it the cFunc difference?
# ============================================================
print("\n" + "=" * 70)
print("TEST E: cFunc difference test")
print("=" * 70)

# What if we use the BASE cFunc for both? Then the consumption TE
# comes only from the distribution change, not policy change.
C_nrm_ui_with_base_cFunc = sum(np.dot(cPol_base[j], dist_ui[j*M:(j+1)*M]) for j in range(J))
nonsplurge_ui_basecFunc = (1 - Splurge_val) * C_nrm_ui_with_base_cFunc
total_ui_basecFunc = nonsplurge_ui_basecFunc + splurge_ui
TE_basecFunc = (total_ui_basecFunc - total_cons_base) * E_pLvl

# What if we use the UI cFunc for both? Then the consumption TE
# comes only from the distribution change under UI policy.
C_nrm_base_with_ui_cFunc = sum(np.dot(cPol_ui[j], dist_base[j*M:(j+1)*M]) for j in range(J))
nonsplurge_base_uicFunc = (1 - Splurge_val) * C_nrm_base_with_ui_cFunc
total_base_uicFunc = nonsplurge_base_uicFunc + splurge_base
TE_uicFunc = (total_ui - total_base_uicFunc) * E_pLvl

print(f"  TE with base cFunc for both:  {TE_basecFunc:.8f}  (distribution effect only)")
print(f"  TE with UI cFunc for both:    {TE_uicFunc:.8f}  (distribution effect under UI policy)")
print(f"  TE with correct cFuncs:       {TE_no_shift:.8f}  (distribution + policy effect)")
print(f"  MC reference:                 {mc_total_TE:.8f}")
print(f"\n  Policy effect (correct - base cFunc): {(TE_no_shift - TE_basecFunc):.8f}")
print(f"  Distribution effect (base cFunc):     {TE_basecFunc:.8f}")

print("\nDone.")
