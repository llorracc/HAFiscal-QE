"""
Test: Is the MC consumption gap from insufficient burn-in?

Compare MC per-state mean mNrm with different burn-in lengths.
If MC approaches TM ergodic with longer burn-in, the gap is
burn-in convergence. If not, something else is wrong.
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
    build_tm_agg_fiscal,
    find_ergodic_distribution,
    _apply_micro_transition,
)

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

N = 200000
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

# TM reference: ergodic per-state mean mNrm
tm_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
dist_mGrid = tm_data['dist_mGrid']
M = len(dist_mGrid)

# Apply one normal micro transition (same as what propagate_experiment_tm does)
micro_normal = BaseType.CondMrkvArrays[0]
dist = _apply_micro_transition(ergodic.copy(), micro_normal, M)
tm_fracs = np.array([np.sum(dist[j*M:(j+1)*M]) for j in range(J)])
tm_mean_mNrm = np.array([
    np.dot(dist_mGrid, dist[j*M:(j+1)*M]) / max(np.sum(dist[j*M:(j+1)*M]), 1e-30)
    for j in range(J)])

print(f"TM ergodic per-state mean mNrm: {tm_mean_mNrm}")
print(f"TM ergodic micro fracs:         {tm_fracs}")
print()

# MC: vary burn-in length
print(f"{'burn_in':>8s}  {'state0_mNrm':>12s}  {'state1_mNrm':>12s}  "
      f"{'state2_mNrm':>12s}  {'state3_mNrm':>12s}  {'time':>8s}")
print("-" * 80)

base_dict_agg = deepcopy(base_dict)

for burn_in in [50, 100, 200, 400, 800]:
    t0 = time()

    # Override act_T to control burn-in length
    init_ADEconomy_mod = deepcopy(init_ADEconomy)
    init_ADEconomy_mod['act_T'] = burn_in

    eco = AggregateDemandEconomy(**init_ADEconomy_mod)
    agent = deepcopy(BaseType)
    agent.AgentCount = N
    agent.seed = 0
    agent.get_economy_data(eco)
    eco.agents = [agent]
    eco.solve()
    eco.reset()
    for a in eco.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    eco.make_history()
    eco.save_state()

    # Extract per-state mean mNrm from saved state
    a = eco.agents[0]
    micro = a.shocks['Mrkv'] % J
    mNrm = a.state_now['bNrm']  # end-of-period bank balance (pre-income)
    # Actually we want the beginning-of-period mNrm including income.
    # After burn-in, state_now has the last period's state.
    # Let's look at what state_now contains.

    # To get mNrm = bNrm + TranShk, we need the current period's TranShk.
    # But after make_history(), the state reflects the end of the last period.
    # The cleanest way: run one more period and extract.

    # Actually, let's just use state_now['aNrm'] (end-of-period savings)
    # and the micro state fractions as a proxy.
    aNrm = a.state_now['aNrm']

    fracs = np.array([np.mean(micro == j) for j in range(J)])
    mean_aNrm = np.array([
        np.mean(aNrm[micro == j]) if np.sum(micro == j) > 0 else 0.0
        for j in range(J)])

    elapsed = time() - t0
    print(f"{burn_in:8d}  {mean_aNrm[0]:12.4f}  {mean_aNrm[1]:12.4f}  "
          f"{mean_aNrm[2]:12.4f}  {mean_aNrm[3]:12.4f}  {elapsed:7.1f}s")

# Also print TM ergodic mean aNrm for comparison
# In TM, aNrm = mNrm - cNrm. We can approximate from the ergodic distribution.
# But actually the key comparison is whether MC values CONVERGE as burn-in grows.

print()
print(f"TM reference (mNrm, not aNrm): {tm_mean_mNrm}")
print(f"\nIf MC aNrm converges as burn-in grows, the consumption gap is")
print(f"from insufficient burn-in. If it plateaus early, something else is wrong.")

# Now run the full experiment comparison at different burn-in lengths
print("\n" + "=" * 70)
print("EXPERIMENT: Consumption TE at different burn-in lengths")
print("=" * 70)

ui_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 20

for burn_in in [100, 200, 400, 800]:
    t0 = time()

    init_ADEconomy_mod = deepcopy(init_ADEconomy)
    init_ADEconomy_mod['act_T'] = burn_in

    eco = AggregateDemandEconomy(**init_ADEconomy_mod)
    agent = deepcopy(BaseType)
    agent.AgentCount = N
    agent.seed = 42000
    agent.get_economy_data(eco)
    eco.agents = [agent]
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
    # Override act_T for the experiment phase
    eco.act_T = 100
    for a in eco.agents:
        a.T_sim = 100
        a.EconomyMrkvNow_hist = [0] * 100
    eco.make_idiosyncratic_shock_histories()

    # Baseline
    base_r = eco.run_experiment(**base_dict_agg, Full_Output=True)
    eco.store_baseline(base_r['AggCons'])

    # UI
    eco_ui = deepcopy(eco)
    eco_ui.switch_shock_type('UI')
    eco_ui.solve()
    d = base_dict_agg.copy()
    d.update(UI_changes)
    d['EconomyMrkv_init'] = ui_path
    ui_r = eco_ui.run_experiment(**d, Full_Output=True)

    N_act = sum(a.AgentCount for a in eco.agents)
    income_te = (ui_r['AggIncome'][0] - base_r['AggIncome'][0]) / N_act
    cons_te = (ui_r['AggCons'][0] - base_r['AggCons'][0]) / N_act

    elapsed = time() - t0
    print(f"  burn_in={burn_in:4d}: income_TE={income_te:.6f}, cons_TE={cons_te:.6f}  ({elapsed:.0f}s)")

print(f"\n  TM reference:       income_TE=0.009781, cons_TE=0.015401")
print(f"  (TM uses exact ergodic, no burn-in needed)")
