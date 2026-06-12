"""
Quick diagnostic: compare consumption LEVELS (not just TE) between
standard TM, neutral-measure TM, and MC.

If the neutral measure changes levels (closer to MC) but TE is unchanged,
it confirms that the covariance error cancels in differencing.
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
from tm_methods import (
    compute_baseline_tm_data, run_experiment_tm, run_experiment_tm_nonbase,
    build_tm_agg_fiscal, find_ergodic_distribution,
    compute_type_aggregates_tm, compute_analytical_mean_pLvl,
)

t0_global = time()

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

edu_inits = [init_highschool]
AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseTypeList = []
for init_params in edu_inits:
    bt = AggFiscalType(**init_params)
    bt.cycles = 0
    BaseTypeList.append(bt)
for bt in BaseTypeList:
    bt.get_economy_data(AggEco)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseTypeList[0].IncUnemp])]
)
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseTypeList[0].IncUnempNoBenefits])]
)
for ThisType in BaseTypeList:
    ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn
    ThisType.IncShkDstn_recession = [ThisType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]

DiscFac = DiscFacDstns[1].atoms[0][0]
TypeList = [deepcopy(BaseTypeList[0])]
TypeList[0].DiscFac = DiscFac
TypeList[0].seed = 0
AggEco.agents = TypeList
AggEco.solve()

agent = TypeList[0]
mCount = 100

print("=" * 70)
print("NEUTRAL MEASURE: ERGODIC DISTRIBUTION COMPARISON")
print("=" * 70)

# Standard ergodic
tm_std = build_tm_agg_fiscal(agent, mCount=mCount, neutral_measure=False)
erg_std = find_ergodic_distribution(tm_std['TranMatrix'])
grid = tm_std['dist_mGrid']
M = len(grid)
J = agent.num_base_MrkvStates

# Neutral ergodic
tm_nm = build_tm_agg_fiscal(agent, mCount=mCount, neutral_measure=True)
erg_nm = find_ergodic_distribution(tm_nm['TranMatrix'])

# Compare state fractions
print(f"\n  State fractions (J={J} micro states):")
print(f"  {'State':>6s} {'Std':>10s} {'Neutral':>10s} {'Ratio':>10s}")
for j in range(J):
    std_frac = np.sum(erg_std[j*M:(j+1)*M])
    nm_frac = np.sum(erg_nm[j*M:(j+1)*M])
    ratio = nm_frac / std_frac if std_frac > 0 else float('nan')
    print(f"  {j:>6d} {std_frac:>10.6f} {nm_frac:>10.6f} {ratio:>10.6f}")

# Compare c_nrm from ergodic
agg_std = compute_type_aggregates_tm(agent, tm_std, erg_std)
agg_nm = compute_type_aggregates_tm(agent, tm_nm, erg_nm)
print(f"\n  c_nrm (ergodic):")
print(f"    Standard:  {agg_std['C_nrm_splurge']:.8f}")
print(f"    Neutral:   {agg_nm['C_nrm_splurge']:.8f}")
print(f"    Ratio:     {agg_nm['C_nrm_splurge'] / agg_std['C_nrm_splurge']:.8f}")

# E[pLvl] for levels
u_erg_std = 1.0 - np.sum(erg_std[:M])
u_erg_nm = 1.0 - np.sum(erg_nm[:M])
E_pLvl_std = compute_analytical_mean_pLvl(agent, unemployment_rate=u_erg_std)
E_pLvl_nm = compute_analytical_mean_pLvl(agent, unemployment_rate=u_erg_nm)
print(f"\n  u_ergodic:   std={u_erg_std:.6f}  nm={u_erg_nm:.6f}")
print(f"  E[pLvl]:     std={E_pLvl_std:.4f}  nm={E_pLvl_nm:.4f}")

C_level_std = agent.AgentCount * E_pLvl_std * agg_std['C_nrm_splurge']
C_level_nm = agent.AgentCount * E_pLvl_nm * agg_nm['C_nrm_splurge']
print(f"  C_level (base): std={C_level_std:.2f}  nm={C_level_nm:.2f}")
print(f"  Ratio:          {C_level_nm / C_level_std:.8f}")

# Run full recession to check levels
print(f"\n{'='*70}")
print("RECESSION CONSUMPTION LEVELS (per-capita, first 10 periods)")
print(f"{'='*70}")

act_T = AggEco.act_T
rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
for t in range(3):
    rec_path[t] = rec_path[t] + 1
rec_path = rec_path[:act_T]
TM_N = sum(a.AgentCount for a in AggEco.agents)

# Standard TM: base + recession
bl_std = compute_baseline_tm_data(AggEco, mCount=mCount, neutral_measure=False, verbose=False)
tm_base_std = run_experiment_tm(AggEco, shock_type='base', mCount=mCount, verbose=False, neutral_measure=False)

eco_rec = deepcopy(AggEco)
eco_rec.switch_shock_type("recession")
eco_rec.solve()
tm_rec_std = run_experiment_tm_nonbase(eco_rec, "recession", rec_path, bl_std, mCount=mCount, verbose=False, neutral_measure=False)

# Neutral TM: base + recession
bl_nm = compute_baseline_tm_data(AggEco, mCount=mCount, neutral_measure=True, verbose=False)
tm_base_nm = run_experiment_tm(AggEco, shock_type='base', mCount=mCount, verbose=False, neutral_measure=True)

eco_rec2 = deepcopy(AggEco)
eco_rec2.switch_shock_type("recession")
eco_rec2.solve()
tm_rec_nm = run_experiment_tm_nonbase(eco_rec2, "recession", rec_path, bl_nm, mCount=mCount, verbose=False, neutral_measure=True)

base_std = np.array(tm_base_std['AggCons']) / TM_N
base_nm = np.array(tm_base_nm['AggCons']) / TM_N
rec_std = np.array(tm_rec_std['AggCons']) / TM_N
rec_nm = np.array(tm_rec_nm['AggCons']) / TM_N
te_std = rec_std - base_std
te_nm = rec_nm - base_nm

print(f"\n  {'t':>3s} {'base_std':>10s} {'base_nm':>10s} {'nm/std':>10s}"
      f" {'rec_std':>10s} {'rec_nm':>10s} {'nm/std':>10s}"
      f" {'TE_std':>10s} {'TE_nm':>10s} {'TE nm/std':>10s}")
for t in range(min(15, len(te_std))):
    b_ratio = base_nm[t] / base_std[t]
    r_ratio = rec_nm[t] / rec_std[t]
    te_ratio = te_nm[t] / te_std[t] if abs(te_std[t]) > 1e-12 else float('nan')
    print(f"  {t:>3d} {base_std[t]:>10.4f} {base_nm[t]:>10.4f} {b_ratio:>10.6f}"
          f" {rec_std[t]:>10.4f} {rec_nm[t]:>10.4f} {r_ratio:>10.6f}"
          f" {te_std[t]:>10.4f} {te_nm[t]:>10.4f} {te_ratio:>10.6f}")

print(f"\nTotal time: {time()-t0_global:.0f}s")
