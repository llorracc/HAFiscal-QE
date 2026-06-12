"""
Direct comparison of TM and MC within-state mNrm distributions.

Instead of comparing means (which can be misleading), compare the
actual probability distributions by computing MC histograms on the
TM grid and checking if they match.

Also: decompose the consumption TE to identify which component
is responsible for the gap.
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
    build_tm_agg_fiscal,
    find_ergodic_distribution,
    _apply_micro_transition,
    build_experiment_period_tm,
    compute_analytical_mean_pLvl,
)

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

N = 500000
J = num_base_MrkvStates
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
base_dict_agg = deepcopy(base_dict)
Splurge = BaseType.Splurge
E_pLvl = compute_analytical_mean_pLvl(BaseType)
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

# ============================================================
# TM: Get ergodic distribution and cPol
# ============================================================
print("Building TM ergodic...")
tm_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
dist_mGrid = tm_data['dist_mGrid']
M = len(dist_mGrid)

micro_normal = deepcopy(BaseType)
micro_normal.update_mrkv_array("base")
micro_normal_mat = micro_normal.CondMrkvArrays[0]

# TM baseline distribution (after initial micro transition)
dist_tm_base = _apply_micro_transition(ergodic.copy(), micro_normal_mat, M)

# TM UI distribution
eco_ui = deepcopy(AggEco)
eco_ui.switch_shock_type("UI")
eco_ui.solve()
ui_agent = eco_ui.agents[0]
micro_ui_mat = ui_agent.CondMrkvArrays[ui_path[0]]
dist_tm_ui = _apply_micro_transition(ergodic.copy(), micro_ui_mat, M)

# cPol for base and UI
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
_, cPol_base = build_experiment_period_tm(base_agent, 0, 0, dist_mGrid, Cratio=1.0)
_, cPol_ui = build_experiment_period_tm(ui_agent, ui_path[0], ui_path[1], dist_mGrid, Cratio=1.0)

# ============================================================
# MC: Get period-0 mNrm distributions per state
# ============================================================
print(f"Running MC (N={N}, 1 seed)...")

def run_mc_get_period0(shock_type, changes_dict, path, seed=0):
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
    else:
        eco_x = deepcopy(eco)
        eco_x.switch_shock_type(shock_type)
        eco_x.solve()
        d = base_dict_agg.copy()
        d.update(changes_dict)
        d['EconomyMrkv_init'] = path
        r = eco_x.run_experiment(**d, Full_Output=True)

    return r

t0 = time()
mc_base_r = run_mc_get_period0('base', base_dict, [0]*act_T, seed=42)
mc_ui_r = run_mc_get_period0('UI', UI_changes, ui_path, seed=42)
print(f"MC done in {time()-t0:.0f}s")

# ============================================================
# COMPARISON 1: Histogram MC mNrm onto TM grid
# ============================================================
print("\n" + "=" * 70)
print("COMPARISON 1: Within-state mNrm distributions (TM vs MC)")
print("=" * 70)

def histogram_on_grid(values, weights, grid):
    """Bin values onto grid using nearest-neighbor, return normalized histogram."""
    hist = np.zeros(len(grid))
    # Find nearest grid point for each value
    indices = np.searchsorted(grid, values)
    indices = np.clip(indices, 0, len(grid) - 1)
    # Also check if the previous index is closer
    for i in range(len(values)):
        idx = indices[i]
        if idx > 0 and abs(values[i] - grid[idx-1]) < abs(values[i] - grid[idx]):
            indices[i] = idx - 1
    for i in range(len(values)):
        hist[indices[i]] += weights[i] if weights is not None else 1.0
    total = np.sum(hist)
    if total > 0:
        hist /= total
    return hist

for label, mc_r, tm_dist in [("Baseline", mc_base_r, dist_tm_base),
                               ("UI", mc_ui_r, dist_tm_ui)]:
    mc_mNrm = mc_r['mNrm_all'][0]
    mc_Mrkv = mc_r['Mrkv_hist'][0]
    mc_micro = mc_Mrkv % J
    N_act = len(mc_mNrm)

    print(f"\n--- {label} ---")
    for j in range(J):
        # MC distribution for state j
        mask = mc_micro == j
        mc_mNrm_j = mc_mNrm[mask]
        n_j = np.sum(mask)
        mc_frac = n_j / N_act

        # TM distribution for state j
        tm_dist_j = tm_dist[j*M:(j+1)*M]
        tm_frac = np.sum(tm_dist_j)

        if n_j == 0:
            print(f"  State {j}: MC frac={mc_frac:.6f}, TM frac={tm_frac:.6f} (no MC agents)")
            continue

        # Compare mean mNrm
        mc_mean = np.mean(mc_mNrm_j)
        tm_mean = np.dot(dist_mGrid, tm_dist_j) / tm_frac if tm_frac > 0 else 0.0

        # Histogram MC onto TM grid
        mc_hist = histogram_on_grid(mc_mNrm_j, None, dist_mGrid)

        # Normalize TM distribution for this state
        tm_hist = tm_dist_j / tm_frac if tm_frac > 0 else tm_dist_j

        # Compare distributions: L1 distance
        l1_dist = np.sum(np.abs(mc_hist - tm_hist))

        # Compare at key percentiles
        mc_p25 = np.percentile(mc_mNrm_j, 25)
        mc_p50 = np.percentile(mc_mNrm_j, 50)
        mc_p75 = np.percentile(mc_mNrm_j, 75)

        # TM CDF
        tm_cdf = np.cumsum(tm_hist)
        tm_p25 = dist_mGrid[np.searchsorted(tm_cdf, 0.25)]
        tm_p50 = dist_mGrid[np.searchsorted(tm_cdf, 0.50)]
        tm_p75 = dist_mGrid[np.searchsorted(tm_cdf, 0.75)]

        print(f"  State {j} (n={n_j}): frac MC={mc_frac:.6f} TM={tm_frac:.6f}")
        print(f"    Mean mNrm:  MC={mc_mean:.4f}  TM={tm_mean:.4f}  diff={tm_mean-mc_mean:+.4f}")
        print(f"    p25:        MC={mc_p25:.4f}  TM={tm_p25:.4f}")
        print(f"    p50:        MC={mc_p50:.4f}  TM={tm_p50:.4f}")
        print(f"    p75:        MC={mc_p75:.4f}  TM={tm_p75:.4f}")
        print(f"    L1 dist:    {l1_dist:.4f}")

# ============================================================
# COMPARISON 2: Use MC's mNrm distribution with TM's cFunc
# ============================================================
print("\n" + "=" * 70)
print("COMPARISON 2: Evaluate TM cFunc at MC's mNrm values")
print("=" * 70)
print("(Tests whether cFunc or distribution is responsible for the gap)")

# If we evaluate the SAME cFunc at MC's actual mNrm values,
# does it match MC's consumption?

for label, mc_r, cPol, macro_t in [
    ("Baseline (base cFunc)", mc_base_r, cPol_base, 0),
    ("UI (UI cFunc)", mc_ui_r, cPol_ui, ui_path[0])]:

    mc_mNrm = mc_r['mNrm_all'][0]
    mc_cNrm = mc_r['cNrm_all'][0]
    mc_Mrkv = mc_r['Mrkv_hist'][0]
    mc_micro = mc_Mrkv % J
    N_act = len(mc_mNrm)

    # For each MC agent, evaluate the TM's cFunc at their mNrm
    cNrm_from_tm_cFunc = np.zeros(N_act)
    for j in range(J):
        mask = mc_micro == j
        if not np.any(mask):
            continue
        # Interpolate cPol[j] (on dist_mGrid) at MC's mNrm values
        cNrm_from_tm_cFunc[mask] = np.interp(
            mc_mNrm[mask], dist_mGrid, cPol[j],
            left=cPol[j][0], right=cPol[j][-1])

    # Compare
    mc_total_cNrm = np.mean(mc_cNrm)
    tm_at_mc_total_cNrm = np.mean(cNrm_from_tm_cFunc)

    print(f"\n  {label}:")
    print(f"    MC mean cNrm:                    {mc_total_cNrm:.6f}")
    print(f"    TM cFunc evaluated at MC mNrm:   {tm_at_mc_total_cNrm:.6f}")
    print(f"    Diff:                            {tm_at_mc_total_cNrm - mc_total_cNrm:+.6f}")

    # Per-state comparison
    for j in range(J):
        mask = mc_micro == j
        if np.sum(mask) < 10:
            continue
        mc_mean = np.mean(mc_cNrm[mask])
        tm_mean = np.mean(cNrm_from_tm_cFunc[mask])
        print(f"    State {j}: MC cNrm={mc_mean:.6f}, TM cFunc(MC mNrm)={tm_mean:.6f}, diff={tm_mean-mc_mean:+.6f}")

# Now compute the consumption TE using TM cFunc at MC mNrm
mc_base_mNrm = mc_base_r['mNrm_all'][0]
mc_base_micro = mc_base_r['Mrkv_hist'][0] % J
mc_ui_mNrm = mc_ui_r['mNrm_all'][0]
mc_ui_micro = mc_ui_r['Mrkv_hist'][0] % J

# TM cFunc at MC base mNrm
cNrm_tm_at_mc_base = np.zeros(len(mc_base_mNrm))
for j in range(J):
    mask = mc_base_micro == j
    if np.any(mask):
        cNrm_tm_at_mc_base[mask] = np.interp(
            mc_base_mNrm[mask], dist_mGrid, cPol_base[j],
            left=cPol_base[j][0], right=cPol_base[j][-1])

# TM cFunc at MC UI mNrm
cNrm_tm_at_mc_ui = np.zeros(len(mc_ui_mNrm))
for j in range(J):
    mask = mc_ui_micro == j
    if np.any(mask):
        cNrm_tm_at_mc_ui[mask] = np.interp(
            mc_ui_mNrm[mask], dist_mGrid, cPol_ui[j],
            left=cPol_ui[j][0], right=cPol_ui[j][-1])

# Get pLvl for scaling
mc_base_pLvl = mc_base_r['pLvl_all'][0]
mc_ui_pLvl = mc_ui_r['pLvl_all'][0]
mc_base_TranShk = mc_base_r['TranShk_all'][0]
mc_ui_TranShk = mc_ui_r['TranShk_all'][0]

# Full consumption with splurge
cons_base_hybrid = np.mean((1-Splurge) * cNrm_tm_at_mc_base * mc_base_pLvl + Splurge * mc_base_TranShk * mc_base_pLvl)
cons_ui_hybrid = np.mean((1-Splurge) * cNrm_tm_at_mc_ui * mc_ui_pLvl + Splurge * mc_ui_TranShk * mc_ui_pLvl)
hybrid_cons_TE = cons_ui_hybrid - cons_base_hybrid

# Reference values
mc_cons_TE = np.mean(mc_ui_r['cLvl_all_splurge'][0]) - np.mean(mc_base_r['cLvl_all_splurge'][0])
tm_cons_TE = 0.015401  # from earlier diagnostic

print(f"\n--- Consumption TE decomposition ---")
print(f"  Pure MC (MC cFunc, MC dist):          {mc_cons_TE:.6f}")
print(f"  Hybrid (TM cFunc, MC dist):           {hybrid_cons_TE:.6f}")
print(f"  Pure TM (TM cFunc, TM dist):          {tm_cons_TE:.6f}")
print(f"\n  If Hybrid ≈ MC:  cFunc is the same, dist causes the gap")
print(f"  If Hybrid ≈ TM:  dist is the same, cFunc causes the gap")
print(f"  If neither:       both contribute")

print("\nDone.")
