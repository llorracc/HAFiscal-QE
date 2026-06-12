"""
Complete decomposition: all TM approaches vs MC, broken into
non-splurge and splurge components.
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
    build_experiment_period_tm, compute_analytical_mean_pLvl,
    _apply_micro_transition,
)
import scipy.sparse as sp

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
Splurge = BaseType.Splurge
E_pLvl = compute_analytical_mean_pLvl(BaseType)
E_TranShk = np.array([1.0, 0.7, 0.7, 0.5])
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20
base_dict_agg = deepcopy(base_dict)

# Build ergodic
tm_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
dist_mGrid = tm_data['dist_mGrid']
M = len(dist_mGrid)

# Agents
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
_, cPol_base = build_experiment_period_tm(base_agent, 0, 0, dist_mGrid, Cratio=1.0)

eco_ui = deepcopy(AggEco)
eco_ui.switch_shock_type("UI")
eco_ui.solve()
ui_agent = eco_ui.agents[0]
_, cPol_ui = build_experiment_period_tm(ui_agent, ui_path[0], ui_path[1], dist_mGrid, Cratio=1.0)

micro_normal = base_agent.CondMrkvArrays[0]
micro_ui_mat = ui_agent.CondMrkvArrays[ui_path[0]]

# ============================================================
# Helper: compute decomposed consumption from a distribution
# ============================================================
def decompose(dist, cPol, E_TranShk, Splurge, J, M):
    fracs = np.array([np.sum(dist[j*M:(j+1)*M]) for j in range(J)])
    C_nrm = sum(np.dot(cPol[j], dist[j*M:(j+1)*M]) for j in range(J))
    income_nrm = np.dot(fracs, E_TranShk)
    nonsplurge = (1 - Splurge) * C_nrm
    splurge = Splurge * income_nrm
    return {'nonsplurge': nonsplurge, 'splurge': splurge,
            'total': nonsplurge + splurge, 'fracs': fracs,
            'C_nrm': C_nrm, 'income_nrm': income_nrm}

# ============================================================
# All TM approaches
# ============================================================

# 1. No micro transition: ergodic with base/UI cPol
d_base_none = decompose(ergodic, cPol_base, E_TranShk, Splurge, J, M)
d_ui_none = decompose(ergodic, cPol_ui, E_TranShk, Splurge, J, M)

# 2. Mixing micro transition
dist_base_mix = _apply_micro_transition(ergodic.copy(), micro_normal, M)
dist_ui_mix = _apply_micro_transition(ergodic.copy(), micro_ui_mat, M)
d_base_mix = decompose(dist_base_mix, cPol_base, E_TranShk, Splurge, J, M)
d_ui_mix = decompose(dist_ui_mix, cPol_ui, E_TranShk, Splurge, J, M)

# 3. Fraction-only micro transition
def fraction_only(dist, micro_trans, M):
    J_loc = micro_trans.shape[0]
    old_fracs = np.array([np.sum(dist[j*M:(j+1)*M]) for j in range(J_loc)])
    new_fracs = micro_trans.T @ old_fracs
    new_dist = dist.copy()
    for j in range(J_loc):
        if old_fracs[j] > 1e-30:
            new_dist[j*M:(j+1)*M] *= new_fracs[j] / old_fracs[j]
    s = np.sum(new_dist)
    if s > 0: new_dist /= s
    return new_dist

dist_base_frac = fraction_only(ergodic.copy(), micro_normal, M)
dist_ui_frac = fraction_only(ergodic.copy(), micro_ui_mat, M)
d_base_frac = decompose(dist_base_frac, cPol_base, E_TranShk, Splurge, J, M)
d_ui_frac = decompose(dist_ui_frac, cPol_ui, E_TranShk, Splurge, J, M)

# 4. One full TM period
TM_base_full, _ = build_experiment_period_tm(base_agent, 0, 0, dist_mGrid, Cratio=1.0)
TM_ui_full, _ = build_experiment_period_tm(ui_agent, ui_path[0], ui_path[1], dist_mGrid, Cratio=1.0)
dist_base_full = TM_base_full @ ergodic
dist_ui_full = TM_ui_full @ ergodic
for d in [dist_base_full, dist_ui_full]:
    if sp.issparse(d): d = np.asarray(d).flatten()
dist_base_full = np.maximum(np.asarray(dist_base_full).flatten(), 0.0)
dist_ui_full = np.maximum(np.asarray(dist_ui_full).flatten(), 0.0)
dist_base_full /= np.sum(dist_base_full)
dist_ui_full /= np.sum(dist_ui_full)
d_base_full = decompose(dist_base_full, cPol_base, E_TranShk, Splurge, J, M)
d_ui_full = decompose(dist_ui_full, cPol_ui, E_TranShk, Splurge, J, M)

# ============================================================
# MC reference
# ============================================================
from time import time
print("Running MC...")
t0 = time()

def setup_and_run(shock_type, changes, path):
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N; a.seed = 42000; a.get_economy_data(eco)
    eco.solve(); eco.reset()
    for a in eco.agents:
        a.initialize_sim(); a.AggDemandFac = 1.0; a.RfreeNow = 1.0; a.CaggNow = 1.0
    eco.make_history(); eco.save_state()
    eco.switch_to_counterfactual_mode("base")
    eco.act_T = act_T
    for a in eco.agents:
        a.T_sim = act_T; a.EconomyMrkvNow_hist = [0] * act_T
    eco.make_idiosyncratic_shock_histories()
    base_r = eco.run_experiment(**base_dict_agg, Full_Output=True)
    eco.store_baseline(base_r['AggCons'])
    if shock_type == 'base':
        return base_r
    eco_x = deepcopy(eco); eco_x.switch_shock_type(shock_type); eco_x.solve()
    d = base_dict_agg.copy(); d.update(changes); d['EconomyMrkv_init'] = path
    return eco_x.run_experiment(**d, Full_Output=True)

mc_base_r = setup_and_run('base', {}, [0]*act_T)
mc_ui_r = setup_and_run('UI', UI_changes, ui_path)
print(f"MC done in {time()-t0:.0f}s")

# MC decomposition
mc_base_cNrm = mc_base_r['cNrm_all'][0]
mc_base_TranShk = mc_base_r['TranShk_all'][0]
mc_ui_cNrm = mc_ui_r['cNrm_all'][0]
mc_ui_TranShk = mc_ui_r['TranShk_all'][0]

mc_base_nonsplurge = (1-Splurge) * np.mean(mc_base_cNrm)
mc_base_splurge = Splurge * np.mean(mc_base_TranShk)
mc_ui_nonsplurge = (1-Splurge) * np.mean(mc_ui_cNrm)
mc_ui_splurge = Splurge * np.mean(mc_ui_TranShk)

# ============================================================
# Print everything
# ============================================================
print(f"\n{'='*80}")
print(f"COMPLETE DECOMPOSITION: All approaches (normalized, per-agent)")
print(f"{'='*80}")

approaches = [
    ("MC", mc_base_nonsplurge, mc_base_splurge, mc_ui_nonsplurge, mc_ui_splurge),
    ("TM no micro", d_base_none['nonsplurge'], d_base_none['splurge'],
     d_ui_none['nonsplurge'], d_ui_none['splurge']),
    ("TM mixing μ", d_base_mix['nonsplurge'], d_base_mix['splurge'],
     d_ui_mix['nonsplurge'], d_ui_mix['splurge']),
    ("TM frac-only μ", d_base_frac['nonsplurge'], d_base_frac['splurge'],
     d_ui_frac['nonsplurge'], d_ui_frac['splurge']),
    ("TM full period", d_base_full['nonsplurge'], d_base_full['splurge'],
     d_ui_full['nonsplurge'], d_ui_full['splurge']),
]

mc_total_te = (mc_ui_nonsplurge + mc_ui_splurge) - (mc_base_nonsplurge + mc_base_splurge)

print(f"\n{'Approach':<18s}  {'base_nonspl':>12s}  {'base_spl':>10s}  "
      f"{'UI_nonspl':>12s}  {'UI_spl':>10s}  "
      f"{'TE_nonspl':>12s}  {'TE_spl':>10s}  {'TE_total':>10s}  {'err%':>7s}")
print("-" * 120)

for name, b_ns, b_s, u_ns, u_s in approaches:
    te_ns = u_ns - b_ns
    te_s = u_s - b_s
    te_tot = te_ns + te_s
    te_tot_lvl = te_tot * E_pLvl
    err = (te_tot - mc_total_te) / mc_total_te * 100 if name != "MC" else 0.0
    print(f"{name:<18s}  {b_ns:12.8f}  {b_s:10.8f}  "
          f"{u_ns:12.8f}  {u_s:10.8f}  "
          f"{te_ns:12.8f}  {te_s:10.8f}  {te_tot:10.8f}  {err:+6.1f}%")

# Per-state fractions for each approach
print(f"\n{'='*80}")
print(f"MICRO STATE FRACTIONS")
print(f"{'='*80}")

mc_base_micro = mc_base_r['Mrkv_hist'][0] % J
mc_ui_micro = mc_ui_r['Mrkv_hist'][0] % J
mc_base_fracs = np.array([np.mean(mc_base_micro == j) for j in range(J)])
mc_ui_fracs = np.array([np.mean(mc_ui_micro == j) for j in range(J)])

print(f"\n{'Approach':<18s}  {'base fracs':>40s}  {'UI fracs':>40s}")
for name, b_fracs, u_fracs in [
    ("MC", mc_base_fracs, mc_ui_fracs),
    ("TM ergodic", d_base_none['fracs'], d_ui_none['fracs']),
    ("TM mixing μ", d_base_mix['fracs'], d_ui_mix['fracs']),
    ("TM frac-only μ", d_base_frac['fracs'], d_ui_frac['fracs']),
    ("TM full period", d_base_full['fracs'], d_ui_full['fracs']),
]:
    b_str = "[" + ", ".join(f"{f:.6f}" for f in b_fracs) + "]"
    u_str = "[" + ", ".join(f"{f:.6f}" for f in u_fracs) + "]"
    print(f"{name:<18s}  {b_str:>40s}  {u_str:>40s}")

# Per-state mean mNrm
print(f"\n{'='*80}")
print(f"PER-STATE MEAN mNrm")
print(f"{'='*80}")

def mean_mNrm_per_state(dist, dist_mGrid, J, M):
    return [np.dot(dist_mGrid, dist[j*M:(j+1)*M]) / max(np.sum(dist[j*M:(j+1)*M]), 1e-30)
            for j in range(J)]

mc_base_mNrm_ps = [np.mean(mc_base_r['mNrm_all'][0][mc_base_micro == j])
                    for j in range(J)]
mc_ui_mNrm_ps = [np.mean(mc_ui_r['mNrm_all'][0][mc_ui_micro == j])
                  if np.sum(mc_ui_micro == j) > 0 else 0.0
                  for j in range(J)]

print(f"\n{'Approach':<18s}  {'base [state 0, 1, 2, 3]':>50s}  {'UI [state 0, 1, 2, 3]':>50s}")
for name, b_dist, u_dist in [
    ("MC", None, None),
    ("TM ergodic", ergodic, ergodic),
    ("TM mixing μ", dist_base_mix, dist_ui_mix),
    ("TM frac-only μ", dist_base_frac, dist_ui_frac),
    ("TM full period", dist_base_full, dist_ui_full),
]:
    if name == "MC":
        b_vals = mc_base_mNrm_ps
        u_vals = mc_ui_mNrm_ps
    else:
        b_vals = mean_mNrm_per_state(b_dist, dist_mGrid, J, M)
        u_vals = mean_mNrm_per_state(u_dist, dist_mGrid, J, M)
    b_str = "[" + ", ".join(f"{v:.4f}" for v in b_vals) + "]"
    u_str = "[" + ", ".join(f"{v:.4f}" for v in u_vals) + "]"
    print(f"{name:<18s}  {b_str:>50s}  {u_str:>50s}")
