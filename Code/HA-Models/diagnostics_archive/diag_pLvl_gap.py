"""
Diagnostic: why does E[pLvl] differ between TM and MC?

Traces pLvl through the MC lifecycle:
  1. After make_history (burn-in)
  2. After save_state
  3. After initialize_sim (experiment start)
  4. During experiment periods 0..4
"""

# Math reference: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")

import os, sys, numpy as np
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
from tm_methods import compute_analytical_mean_pLvl

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

init_dict = init_highschool
BaseType = AggFiscalType(**init_dict)
BaseType.cycles = 0
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

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
for a in AggEco.agents:
    a.AgentCount = N_mc
    a.seed = 42000
    a.get_economy_data(AggEco)

AggEco.solve()

print("=" * 60)
print("TRACING pLvl THROUGH MC LIFECYCLE")
print("=" * 60)

E_pLvl_analytical = compute_analytical_mean_pLvl(BaseType)
print(f"\nAnalytical E[pLvl] = {E_pLvl_analytical:.4f}")

# Step 1: reset + initialize_sim (burn-in start)
AggEco.reset()
for a in AggEco.agents:
    a.initialize_sim()
    a.AggDemandFac = 1.0
    a.RfreeNow = 1.0
    a.CaggNow = 1.0

print(f"\n1. After initialize_sim (before burn-in):")
print(f"   E[pLvl] = {np.mean(BaseType.state_now['pLvl']):.4f}")
print(f"   E[t_age] = {np.mean(BaseType.t_age):.2f}")
print(f"   min/max pLvl = {np.min(BaseType.state_now['pLvl']):.4f} / {np.max(BaseType.state_now['pLvl']):.4f}")

# Step 2: make_history (burn-in)
AggEco.make_history()

print(f"\n2. After make_history (burn-in complete):")
print(f"   E[pLvl] = {np.mean(BaseType.state_now['pLvl']):.4f}")
print(f"   E[t_age] = {np.mean(BaseType.t_age):.2f}")
print(f"   min/max pLvl = {np.min(BaseType.state_now['pLvl']):.4f} / {np.max(BaseType.state_now['pLvl']):.4f}")

# Step 3: save_state
AggEco.save_state()

print(f"\n3. After save_state:")
print(f"   E[pLvl] = {np.mean(BaseType.state_now['pLvl']):.4f}")
if hasattr(BaseType, 'pLvl_base'):
    print(f"   E[pLvl_base] = {np.mean(BaseType.pLvl_base):.4f}")

# Step 4: switch_to_counterfactual_mode
AggEco.switch_to_counterfactual_mode("base")
AggEco.act_T = AggEco.act_T
for a in AggEco.agents:
    a.T_sim = AggEco.act_T
    a.EconomyMrkvNow_hist = [0] * AggEco.act_T

print(f"\n4. After switch_to_counterfactual_mode:")
print(f"   E[pLvl] = {np.mean(BaseType.state_now['pLvl']):.4f}")

# Step 5: make_idiosyncratic_shock_histories
AggEco.make_idiosyncratic_shock_histories()

print(f"\n5. After make_idiosyncratic_shock_histories:")
print(f"   E[pLvl] = {np.mean(BaseType.state_now['pLvl']):.4f}")

# Step 6: run_experiment (the baseline)
base_dict_agg = deepcopy(base_dict)
mc_base = AggEco.run_experiment(**base_dict_agg, Full_Output=True)

print(f"\n6. After run_experiment baseline:")
# pLvl history across experiment periods
pLvl_hist = np.concatenate([a.history['pLvl'] for a in AggEco.agents], axis=1)
for t in range(min(5, pLvl_hist.shape[0])):
    print(f"   Period {t}: E[pLvl] = {np.mean(pLvl_hist[t]):.4f}, "
          f"median = {np.median(pLvl_hist[t]):.4f}")

print(f"\n   MC AggCons/cap[0] = {mc_base['AggCons'][0] / N_mc:.6f}")

# Check: what is PermShk distribution?
PermShk_hist = np.concatenate([a.shock_history['PermShk'] for a in AggEco.agents], axis=1)
print(f"\n   PermShk period 0: E={np.mean(PermShk_hist[0]):.6f}, "
      f"std={np.std(PermShk_hist[0]):.6f}")

# Check: what is PlvlAgg?
if hasattr(AggEco, 'history') and 'PlvlAgg' in AggEco.history:
    print(f"   PlvlAgg history: {AggEco.history['PlvlAgg'][:5]}")

# Check T_sim during burn-in
print(f"\n   BaseType.T_sim = {BaseType.T_sim}")
print(f"   AggEco.act_T = {AggEco.act_T}")

# Check how many burn-in periods
if hasattr(AggEco, 'T_sim'):
    print(f"   AggEco.T_sim = {AggEco.T_sim}")

# Look at age distribution
t_age_0 = BaseType.history.get('t_age', None)
if t_age_0 is not None:
    print(f"\n   Age distribution period 0: E[t_age]={np.mean(t_age_0[0]):.2f}")
else:
    print(f"\n   t_age not in history, checking state_now: E[t_age]={np.mean(BaseType.t_age):.2f}")

# Compare: what if we compute AggCons using analytical E[pLvl]?
cNrm_all = np.concatenate([a.history['cNrm'] for a in AggEco.agents], axis=1)
TranShk_all = np.concatenate([a.shock_history['TranShk'] for a in AggEco.agents], axis=1)
Splurge = BaseType.Splurge

for t in [0, 1, 2]:
    # MC actual
    actual_AggCons = mc_base['AggCons'][t]
    # MC using analytical E[pLvl]
    # cLvl_splurge = (1-S)*cNrm*pLvl + S*pLvl*TranShk
    # If we replace pLvl with E[pLvl]:
    # approx = ((1-S)*cNrm + S*TranShk) * E[pLvl] * N
    approx_analytical = np.sum(
        ((1 - Splurge) * cNrm_all[t] + Splurge * TranShk_all[t])
    ) * E_pLvl_analytical
    approx_mc_pLvl = np.sum(
        ((1 - Splurge) * cNrm_all[t] + Splurge * TranShk_all[t])
    ) * np.mean(pLvl_hist[t])

    print(f"\n   Period {t} AggCons decomposition:")
    print(f"     Actual: {actual_AggCons:.2f}")
    print(f"     Using analytical E[pLvl]={E_pLvl_analytical:.2f}: {approx_analytical:.2f} "
          f"({(approx_analytical/actual_AggCons - 1)*100:+.2f}%)")
    print(f"     Using MC E[pLvl]={np.mean(pLvl_hist[t]):.2f}: {approx_mc_pLvl:.2f} "
          f"({(approx_mc_pLvl/actual_AggCons - 1)*100:+.2f}%)")
