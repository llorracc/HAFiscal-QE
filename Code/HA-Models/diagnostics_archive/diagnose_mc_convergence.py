"""
MC convergence test: verify that MC income and consumption TEs converge
toward the analytical/TM values as N increases.

The UI treatment effect operates on ~1% of the population (UB state 2
agents who would lose benefits). MC noise on this subpopulation should
scale as 1/sqrt(N).
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
    run_experiment_tm_nonbase,
    compute_analytical_mean_pLvl,
)

# ============================================================
# Setup (same as diagnostic)
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

ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

# ============================================================
# Analytical / TM reference values
# ============================================================
E_pLvl = compute_analytical_mean_pLvl(BaseType)

# Analytical income TE from micro fractions
base_fracs = np.array([0.956, 0.02933333, 0.00977778, 0.00488889])
micro_normal = np.array([
    [0.9693166, 0.0306834, 0., 0.],
    [0.66666667, 0., 0.33333333, 0.],
    [0.66666667, 0., 0., 0.33333333],
    [0.66666667, 0., 0., 0.33333333]])
micro_ui = np.array([
    [0.9693166, 0.0306834, 0., 0.],
    [0.66666667, 0.33333333, 0., 0.],
    [0.66666667, 0., 0.33333333, 0.],
    [0.66666667, 0., 0., 0.33333333]])
E_TranShk = np.array([1.0, 0.7, 0.7, 0.5])

fracs_normal = micro_normal.T @ base_fracs
fracs_ui = micro_ui.T @ base_fracs
analytical_income_TE_nrm = np.dot(fracs_ui, E_TranShk) - np.dot(fracs_normal, E_TranShk)
analytical_income_TE = analytical_income_TE_nrm * E_pLvl

# TM consumption TE (converged at mCount=200)
MCOUNT = 200
baseline_tm_data = compute_baseline_tm_data(AggEco, mCount=MCOUNT, verbose=False)
bd0 = baseline_tm_data[0]

base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
tm_base = propagate_experiment_tm(
    base_agent, bd0['ergodic'], [0]*act_T, bd0['dist_mGrid'],
    bd0['E_pLvl'], Cratio=1.0, act_T=act_T)

eco_ui_tm = deepcopy(AggEco)
eco_ui_tm.switch_shock_type("UI")
eco_ui_tm.solve()
tm_ui = propagate_experiment_tm(
    eco_ui_tm.agents[0], bd0['ergodic'], ui_path, bd0['dist_mGrid'],
    bd0['E_pLvl'], Cratio=1.0, act_T=act_T, shock_type='UI')

# Reference: use N=1 as placeholder, actual N will vary
tm_income_TE_per_agent = (tm_ui['AggIncome'][0] - tm_base['AggIncome'][0])
tm_cons_TE_per_agent = (tm_ui['AggCons'][0] - tm_base['AggCons'][0])

print("=" * 70)
print("MC CONVERGENCE TEST: UI Income & Consumption Treatment Effects")
print("=" * 70)
print(f"Analytical income TE (nrm): {analytical_income_TE_nrm:.8f}")
print(f"Analytical income TE (levels, per agent): {analytical_income_TE:.8f}")
print(f"TM income TE (levels, per agent): {tm_income_TE_per_agent:.8f}")
print(f"TM cons TE (levels, per agent):   {tm_cons_TE_per_agent:.8f}")
print(f"E[pLvl] = {E_pLvl:.4f}")
print(f"Affected subpopulation (state 2): ~{base_fracs[2]*100:.1f}% of agents")
print()

# ============================================================
# MC convergence sweep
# ============================================================
N_values = [10000, 50000, 100000, 500000, 1000000]
NUM_SEEDS = 5

def run_mc_ui_experiment(N_agents, seed):
    """Run one MC seed at given N, return per-agent income and cons TEs."""
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N_agents
        a.seed = seed * 1000
    for a in eco.agents:
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

    # Baseline
    base_r = eco.run_experiment(**base_dict_agg, Full_Output=True)
    eco.store_baseline(base_r['AggCons'])

    # UI experiment
    eco_x = deepcopy(eco)
    eco_x.switch_shock_type('UI')
    eco_x.solve()
    d = base_dict_agg.copy()
    d.update(UI_changes)
    d['EconomyMrkv_init'] = ui_path
    ui_r = eco_x.run_experiment(**d, Full_Output=True)

    N_act = sum(a.AgentCount for a in eco.agents)
    income_te = (ui_r['AggIncome'][0] - base_r['AggIncome'][0]) / N_act
    cons_te = (ui_r['AggCons'][0] - base_r['AggCons'][0]) / N_act

    # Also get period-0 micro fracs for UI
    agent = eco_x.agents[0]
    mrkv_0 = agent.shock_history['Mrkv'][0]
    micro_0 = mrkv_0 % J
    fracs = np.array([np.mean(micro_0 == j) for j in range(J)])

    return income_te, cons_te, fracs

print(f"{'N':>10s}  {'Seeds':>5s}  {'Income TE':>12s}  {'err vs anal':>12s}  "
      f"{'Cons TE':>12s}  {'State2 frac':>12s}  {'Time':>8s}")
print("-" * 90)

# Reference per-agent values
ref_N = BaseType.AgentCount  # used in TM computation
tm_income_ref = tm_income_TE_per_agent / ref_N
tm_cons_ref = tm_cons_TE_per_agent / ref_N

results = []
for N_agents in N_values:
    t0 = time()
    income_tes = []
    cons_tes = []
    state2_fracs = []
    for s in range(NUM_SEEDS):
        ite, cte, fracs = run_mc_ui_experiment(N_agents, seed=s)
        income_tes.append(ite)
        cons_tes.append(cte)
        state2_fracs.append(fracs[2])
    elapsed = time() - t0

    mean_income_te = np.mean(income_tes)
    std_income_te = np.std(income_tes)
    mean_cons_te = np.mean(cons_tes)
    std_cons_te = np.std(cons_tes)
    mean_state2 = np.mean(state2_fracs)
    std_state2 = np.std(state2_fracs)

    income_err = (mean_income_te - analytical_income_TE) / analytical_income_TE * 100
    cons_err = (mean_cons_te - tm_cons_ref) / tm_cons_ref * 100 if abs(tm_cons_ref) > 1e-15 else float('nan')

    print(f"{N_agents:10d}  {NUM_SEEDS:5d}  "
          f"{mean_income_te:12.6f}  {income_err:+10.2f}%  "
          f"{mean_cons_te:12.6f}  "
          f"{mean_state2:.6f}  "
          f"{elapsed:7.1f}s")
    print(f"{'':10s}  {'(std)':>5s}  "
          f"{std_income_te:12.6f}  {'':>12s}  "
          f"{std_cons_te:12.6f}  "
          f"{std_state2:.6f}")

    results.append({
        'N': N_agents,
        'income_te_mean': mean_income_te,
        'income_te_std': std_income_te,
        'cons_te_mean': mean_cons_te,
        'cons_te_std': std_cons_te,
    })

print()
print(f"Reference values:")
print(f"  Analytical income TE: {analytical_income_TE:.6f}")
print(f"  TM income TE:         {tm_income_ref:.6f}")
print(f"  TM cons TE:           {tm_cons_ref:.6f}")

# Check 1/sqrt(N) scaling
print()
print("1/sqrt(N) scaling check (income TE std):")
if len(results) >= 2:
    for i in range(1, len(results)):
        r0, r1 = results[0], results[i]
        predicted_ratio = np.sqrt(r0['N'] / r1['N'])
        actual_ratio = r0['income_te_std'] / r1['income_te_std'] if r1['income_te_std'] > 0 else float('nan')
        print(f"  N={r0['N']}→{r1['N']}: predicted std ratio={predicted_ratio:.2f}, actual={actual_ratio:.2f}")
