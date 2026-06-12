"""
Quick diagnostic: Compare Phase 0 TM NPV with and without E_pLvl correction,
and with MC-derived E_pLvl override. Confirms whether the 23% error is
pre-existing vs caused by our fix.
"""

# Math reference: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")

import os, sys
import numpy as np
from time import time
from copy import deepcopy

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())
os.environ['MPLBACKEND'] = 'Agg'

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data, run_experiment_tm, run_experiment_tm_nonbase,
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

AggEco = AggregateDemandEconomy(**init_ADEconomy)
bt = AggFiscalType(**init_highschool)
bt.cycles = 0
bt.get_economy_data(AggEco)
IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([bt.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([bt.IncUnempNoBenefits])])
EmployedIncShkDstn = deepcopy(bt.IncShkDstn[0])
bt.IncShkDstn = [[bt.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
bt.IncShkDstn_base = bt.IncShkDstn
IncShkDstn_recession = [bt.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
bt.IncShkDstn_recession = IncShkDstn_recession
bt.DiscFac = DiscFacDstns[1].atoms[0][0]
TypeList = [deepcopy(bt)]
TypeList[0].seed = 0
AggEco.agents = TypeList
AggEco.solve()
act_T = AggEco.act_T
Rfree = TypeList[0].Rfree[0]
disc = np.array([1.0 / Rfree**t for t in range(act_T)])

rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
for t in range(3):
    rec_path[t] = rec_path[t] + 1
rec_path = rec_path[:act_T]

base_dict_agg = deepcopy(base_dict)

# Get MC E[pLvl] from burn-in
eco_mc = deepcopy(AggEco)
for a in eco_mc.agents:
    a.AgentCount = 100000
    a.seed = 0
    a.get_economy_data(eco_mc)
eco_mc.solve()
eco_mc.reset()
for a in eco_mc.agents:
    a.initialize_sim()
    a.AggDemandFac = 1.0
    a.RfreeNow = 1.0
    a.CaggNow = 1.0
eco_mc.make_history()
mc_E_pLvl_val = np.mean(eco_mc.agents[0].state_now['pLvl'])

E_pLvl_old = compute_analytical_mean_pLvl(AggEco.agents[0], unemployment_rate=None)
E_pLvl_new = compute_analytical_mean_pLvl(AggEco.agents[0], unemployment_rate=0.044)

print(f"E[pLvl] comparison:")
print(f"  Old analytical (G):     {E_pLvl_old:.4f}")
print(f"  New analytical (g):     {E_pLvl_new:.4f}")
print(f"  MC burn-in:             {mc_E_pLvl_val:.4f}")
print()


def run_tm_recession(eco, mCount, mc_E_pLvl=None, label=""):
    eco_tm = deepcopy(eco)
    TM_N = sum(a.AgentCount for a in eco_tm.agents)
    bl = compute_baseline_tm_data(eco_tm, mCount=mCount, mc_E_pLvl=mc_E_pLvl, verbose=False)
    tm_base = run_experiment_tm(eco_tm, shock_type='base', mCount=mCount, verbose=False)
    tm_base_cons = np.array(tm_base['AggCons']) / TM_N

    eco2 = deepcopy(eco)
    eco2.switch_shock_type("recession")
    eco2.solve()
    tm_rec = run_experiment_tm_nonbase(eco2, "recession", rec_path, bl, mCount=mCount, verbose=False)
    tm_rec_cons = np.array(tm_rec['AggCons']) / TM_N

    T_out = len(tm_base_cons)
    te = tm_rec_cons - tm_base_cons
    npv = np.sum(te * disc[:T_out])
    print(f"  {label:<35s} E_pLvl={bl[0]['E_pLvl']:.4f}  NPV={npv:.4f}")
    return npv


# Run MC recession (3 seeds, 100K)
print("MC recession (100K × 3 seeds):")
mc_npvs = []
for seed in range(3):
    eco_mc2 = deepcopy(AggEco)
    for a in eco_mc2.agents:
        a.AgentCount = 100000
        a.seed = seed * 1000
        a.get_economy_data(eco_mc2)
    eco_mc2.solve()
    eco_mc2.reset()
    for a in eco_mc2.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    eco_mc2.make_history()
    eco_mc2.save_state()
    eco_mc2.switch_to_counterfactual_mode("base")
    eco_mc2.make_idiosyncratic_shock_histories()
    mc_base = eco_mc2.run_experiment(**base_dict_agg, Full_Output=True)
    N_actual = sum(a.AgentCount for a in eco_mc2.agents)
    T_out = min(len(mc_base['AggCons']), act_T)
    mc_base_cons = np.array(mc_base['AggCons'][:T_out]) / N_actual

    eco_rec = deepcopy(eco_mc2)
    eco_rec.switch_shock_type("recession")
    eco_rec.solve()
    rec_d = base_dict_agg.copy()
    rec_d.update(recession_changes)
    rec_d['EconomyMrkv_init'] = rec_path
    mc_rec = eco_rec.run_experiment(**rec_d, Full_Output=True)
    mc_rec_cons = np.array(mc_rec['AggCons'][:T_out]) / N_actual
    te = mc_rec_cons - mc_base_cons
    npv = np.sum(te * disc[:T_out])
    mc_npvs.append(npv)
    print(f"  seed {seed}: NPV={npv:.4f}")

mc_mean = np.mean(mc_npvs)
print(f"  MC mean: {mc_mean:.4f}")
print()

print("TM recession (mCount=100):")
npv_new = run_tm_recession(AggEco, 100, label="New code (g_base E_pLvl)")
npv_mc_override = run_tm_recession(AggEco, 100, mc_E_pLvl=[mc_E_pLvl_val],
                                    label="MC E_pLvl override")
npv_old_override = run_tm_recession(AggEco, 100, mc_E_pLvl=[E_pLvl_old],
                                     label="Old E_pLvl override")
print()
print(f"Relative errors vs MC mean ({mc_mean:.4f}):")
for label, npv in [("New code", npv_new), ("MC E_pLvl", npv_mc_override),
                    ("Old E_pLvl", npv_old_override)]:
    rel = (npv - mc_mean) / abs(mc_mean) * 100
    print(f"  {label:<20s}: NPV={npv:.4f}, rel-err={rel:+.2f}%")
