"""
Minimal diagnostic: Verify whether HARK's IncShkDstn draw method
produces biased PermShk samples (E[PermShk] != 1.0).
"""

# Math reference: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")

import os, sys
import numpy as np
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

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

BaseType = AggFiscalType(**init_highschool)
BaseType.cycles = 0
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

# The original IncShkDstn[0] before any modifications
orig_IncShkDstn = deepcopy(BaseType.IncShkDstn[0])

print("=" * 70)
print("DIAGNOSTIC: PermShk draw bias investigation")
print("=" * 70)

# Check 1: Distribution properties
print(f"\nOriginal IncShkDstn[0] type: {type(orig_IncShkDstn)}")
print(f"  atoms[0] (PermShk): {orig_IncShkDstn.atoms[0]}")
print(f"  E[PermShk] (theoretical) = {np.sum(orig_IncShkDstn.pmv * orig_IncShkDstn.atoms[0]):.15f}")

# Check 2: Direct draws from the IndexDistribution
N_draws = 1000000
print(f"\n--- Direct draws from IndexDistribution ({N_draws:,d}) ---")
for seed in [42, 123, 999, 763607780]:
    orig_IncShkDstn.seed = seed
    orig_IncShkDstn.reset()
    sample = orig_IncShkDstn.draw(N_draws)
    perm_shk = sample[0] if isinstance(sample, (list, tuple)) else sample
    print(f"  seed={seed:>10d}: E[PermShk]={np.mean(perm_shk):.10f}, "
          f"std={np.std(perm_shk):.6f}, N={len(perm_shk)}")

# Check 3: Using DiscreteDistribution directly
print(f"\n--- Direct draws from DiscreteDistribution ---")
emp_dd = DiscreteDistribution(orig_IncShkDstn.pmv, orig_IncShkDstn.atoms)
for seed in [42, 123, 999]:
    np.random.seed(seed)
    indices = np.random.choice(len(emp_dd.pmv), size=N_draws, p=emp_dd.pmv)
    perm_shk_dd = emp_dd.atoms[0][indices]
    print(f"  seed={seed:>10d}: E[PermShk]={np.mean(perm_shk_dd):.10f}")

# Check 4: Simulate make_shock_history to see what happens
print(f"\n--- Via make_shock_history (Mrkv_univ=0) ---")
IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])
BaseType.IncShkDstn[0].seed = 763607780
BaseType.IncShkDstn[0].reset()
BaseType.IncShkDstn = [[BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
BaseType.IncShkDstn_base = BaseType.IncShkDstn

AggEco.agents = [BaseType]
BaseType.AgentCount = 1
AggEco.solve()

for N_agents in [10000, 50000, 200000]:
    eco = deepcopy(AggEco)
    agent = eco.agents[0]
    agent.AgentCount = N_agents
    agent.seed = 42000
    agent.get_economy_data(eco)
    eco.solve()
    eco.reset()
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0

    agent.Mrkv_univ = 0
    agent.read_shocks = False
    agent.T_sim = 100
    agent.make_shock_history()

    psh = agent.shock_history['PermShk']
    print(f"  N={N_agents:>7d}: shape={psh.shape}, E[PermShk[0]]={np.mean(psh[0]):.10f}, "
          f"E[PermShk[all]]={np.mean(psh):.10f}")
    agent.Mrkv_univ = None

# Check 5: What does make_shock_history actually draw from?
print(f"\n--- Detailed make_shock_history investigation ---")
eco2 = deepcopy(AggEco)
agent2 = eco2.agents[0]
agent2.AgentCount = 200000
agent2.seed = 42000
agent2.get_economy_data(eco2)
eco2.solve()
eco2.reset()
agent2.initialize_sim()
agent2.AggDemandFac = 1.0
agent2.RfreeNow = 1.0
agent2.CaggNow = 1.0
agent2.Mrkv_univ = 0
agent2.read_shocks = False
agent2.T_sim = 100
agent2.make_shock_history()

psh2 = agent2.shock_history['PermShk']
tsh2 = agent2.shock_history['TranShk']

print(f"  PermShk unique values at t=0: {np.unique(psh2[0])[:10]}...")
print(f"  TranShk unique values at t=0: {np.unique(tsh2[0])[:10]}...")

# Check how many agents got each PermShk value
uniq_p, counts_p = np.unique(psh2[0], return_counts=True)
expected_count = 200000 / len(uniq_p) if len(uniq_p) > 0 else 0
print(f"  Number of unique PermShk values: {len(uniq_p)}")
print(f"  Expected count per value: {expected_count:.0f}")
for i, (v, c) in enumerate(zip(uniq_p, counts_p)):
    if i < 10:
        print(f"    PermShk={v:.8f}: count={c}, excess={c-expected_count:.0f}")
