"""
Diagnostic: Compare pLvl_factor trajectory (old vs new formula)
against MC's actual E[pLvl] ratio during a recession.
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
from tm_methods import compute_analytical_mean_pLvl

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
AggEco.agents = [bt]
AggEco.solve()

G = bt.PermGroFac[0][0]
LivPrb = bt.LivPrb[0][0]
T_age = bt.T_age

# Effective delta
from tm_methods import _effective_LivPrb
J_micro = bt.num_base_MrkvStates
_LivPrb_eff = _effective_LivPrb(
    np.asarray(bt.LivPrb[0][:J_micro], dtype=np.float64), T_age)
delta_eff = 1.0 - np.mean(_LivPrb_eff)

u_ergodic = 0.044  # from Phase 0 output
g_base = (1.0 - u_ergodic) * G + u_ergodic

# Recession path: 3 quarters of higher unemployment
# During recession quarters, u_rec is higher
# The Mrkv recession states have different transition matrices
# For simplicity, use the unemployment rates from the Mrkv array
u_recession = 0.10  # approximate recession unemployment

print(f"Parameters:")
print(f"  G = {G:.6f}")
print(f"  g_base = {g_base:.6f}")
print(f"  delta_eff = {delta_eff:.6f}")
print(f"  u_ergodic = {u_ergodic:.4f}")
print(f"  u_recession = {u_recession:.4f}")
print(f"  (1-delta_eff) = {1-delta_eff:.6f}")
print(f"  (1-delta_eff)*g_base = {(1-delta_eff)*g_base:.6f}")
print(f"  AR(1) old = {1-delta_eff:.6f}, half-life = {np.log(2)/np.log(1/(1-delta_eff)):.0f}q")
print(f"  AR(1) new = {(1-delta_eff)*g_base:.6f}, half-life = {np.log(2)/np.log(1/((1-delta_eff)*g_base)):.0f}q")
print()

E_pLvl_old = compute_analytical_mean_pLvl(bt, unemployment_rate=None)
E_pLvl_new = compute_analytical_mean_pLvl(bt, unemployment_rate=u_ergodic)
print(f"E[pLvl] old (G):       {E_pLvl_old:.6f}")
print(f"E[pLvl] new (g_base):  {E_pLvl_new:.6f}")
print(f"Ratio new/old:         {E_pLvl_new/E_pLvl_old:.6f}")
print()

# Simulate pLvl_factor trajectories for 40 periods
# 3 recession periods, then recovery
act_T = 40
rec_dur = 3

print(f"{'t':>4s} {'u_t':>8s} {'g_rec':>8s} {'F_old':>10s} {'F_new':>10s} "
      f"{'scale_old':>12s} {'scale_new':>12s} {'ratio':>8s}")
print("-" * 80)

F_old = 1.0
F_new = 1.0
for t in range(act_T):
    u_t = u_recession if t < rec_dur else u_ergodic
    g_rec_t = (1.0 - u_t) * G + u_t

    # Compute level scales BEFORE updating pLvl_factor
    scale_old = E_pLvl_old * F_old
    scale_new = E_pLvl_new * F_new
    ratio = scale_new / scale_old

    print(f"{t:>4d} {u_t:>8.4f} {g_rec_t:>8.6f} {F_old:>10.6f} {F_new:>10.6f} "
          f"{scale_old:>12.6f} {scale_new:>12.6f} {ratio:>8.6f}")

    # Old formula: F' = (1-d)*F*(g_rec/g_base) + d
    F_old = (1.0 - delta_eff) * F_old * (g_rec_t / g_base) + delta_eff
    # New formula: F' = (1-d)*g_rec*F + [1-(1-d)*g_base]
    F_new = (1.0 - delta_eff) * g_rec_t * F_new + (1.0 - (1.0 - delta_eff) * g_base)

print()
print(f"At t=39: F_old={F_old:.6f}, F_new={F_new:.6f}")
print(f"scale_old = {E_pLvl_old * F_old:.6f}")
print(f"scale_new = {E_pLvl_new * F_new:.6f}")
print(f"NPV effect: the per-period C is proportional to scale.")
print(f"If scale_new < scale_old during recovery, TM recession is MORE negative,")
print(f"which matches the ~23% overcorrection observed in Phase 0.")
