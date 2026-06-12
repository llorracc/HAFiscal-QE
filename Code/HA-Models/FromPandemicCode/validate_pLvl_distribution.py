"""
Validate the analytical pLvl distribution against the MC empirical distribution.

Sets up a single highschool-type agent, runs MC to ergodic steady state,
and compares:
  1. CDF at key quantiles
  2. Mean, median, std
  3. E[CheckStimLvl * phase_out(pLvl) / pLvl] (the normalized check amount)
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
    compute_analytical_mean_pLvl, compute_pLvl_distribution, _get_perm_shock_var,
)

N = 100000

print("=" * 60)
print("VALIDATE pLvl DISTRIBUTION: analytical vs MC")
print(f"  1 consumer type (highschool), N={N}")
print("=" * 60)

# ============================================================
# Setup
# ============================================================
t0_total = time()

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
BaseType.AgentCount = N
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

AggDemandEconomy = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggDemandEconomy)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]),
    [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])

BaseType.IncShkDstn[0].seed = 763607780
BaseType.IncShkDstn[0].reset()

EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
BaseType.IncShkDstn = [[BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
BaseType.IncShkDstn_base = BaseType.IncShkDstn

AggDemandEconomy.agents = [BaseType]

t0 = time()
AggDemandEconomy.solve()
t_solve = time() - t0

print(f"\nSetup + solve: {time()-t0_total:.1f}s (solve={t_solve:.1f}s)")

# ============================================================
# Key parameters
# ============================================================
G = BaseType.PermGroFac[0][0]
L = BaseType.LivPrb[0][0]
T_age = BaseType.T_age
pLogInitMean = BaseType.pLogInitMean
pLogInitStd = BaseType.pLogInitStd
sigma_psi_sq = _get_perm_shock_var(BaseType)

print(f"\nAgent parameters:")
print(f"  G (PermGroFac)    = {G}")
print(f"  L (LivPrb)        = {L}")
print(f"  T_age             = {T_age}")
print(f"  pLogInitMean      = {pLogInitMean:.4f} (E[pLvl_init] = {np.exp(pLogInitMean):.2f})")
print(f"  pLogInitStd       = {pLogInitStd:.4f}")
print(f"  sigma_psi^2       = {sigma_psi_sq:.6f} (PermShkStd = {np.sqrt(sigma_psi_sq):.4f})")
print(f"  CheckStimLvl      = {BaseType.CheckStimLvl}")
print(f"  Cutoff start      = {BaseType.CheckStimLvl_PLvl_Cutoff_start}")
print(f"  Cutoff end        = {BaseType.CheckStimLvl_PLvl_Cutoff_end}")

# ============================================================
# Analytical distribution
# ============================================================
print(f"\n{'='*60}")
print("ANALYTICAL pLvl DISTRIBUTION")
print("=" * 60)

pLvl_grid, pLvl_weights = compute_pLvl_distribution(BaseType, n_points=500)
E_pLvl_analytical = compute_analytical_mean_pLvl(BaseType)
E_pLvl_from_dist = np.dot(pLvl_weights, pLvl_grid)

print(f"  E[pLvl] (closed-form)    = {E_pLvl_analytical:.4f}")
print(f"  E[pLvl] (from dist grid) = {E_pLvl_from_dist:.4f}")
print(f"  Grid range: [{pLvl_grid[0]:.2f}, {pLvl_grid[-1]:.2f}]")

# Compute analytical CDF
cdf_analytical = np.cumsum(pLvl_weights)
analytical_quantiles = {}
for q in [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
    idx = np.searchsorted(cdf_analytical, q)
    idx = min(idx, len(pLvl_grid) - 1)
    analytical_quantiles[q] = pLvl_grid[idx]
    print(f"  Q({q:.2f}) = {pLvl_grid[idx]:.4f}")

# Analytical E[check_nrm]
cutoff_start = BaseType.CheckStimLvl_PLvl_Cutoff_start
cutoff_end = BaseType.CheckStimLvl_PLvl_Cutoff_end
CheckStimLvl = BaseType.CheckStimLvl

phase_out = np.ones_like(pLvl_grid)
in_range = (pLvl_grid >= cutoff_start) & (pLvl_grid <= cutoff_end)
above = pLvl_grid > cutoff_end
phase_out[in_range] = 1.0 - (pLvl_grid[in_range] - cutoff_start) / (cutoff_end - cutoff_start)
phase_out[above] = 0.0

check_nrm_grid = CheckStimLvl * phase_out / pLvl_grid
E_check_nrm_analytical = np.dot(pLvl_weights, check_nrm_grid)
frac_full = np.dot(pLvl_weights, (pLvl_grid < cutoff_start).astype(float))
frac_partial = np.dot(pLvl_weights, in_range.astype(float))
frac_none = np.dot(pLvl_weights, above.astype(float))

print(f"\n  E[check_nrm] (analytical)  = {E_check_nrm_analytical:.6f}")
print(f"  Naive check_nrm (E[pLvl]) = {CheckStimLvl / E_pLvl_analytical:.6f}")
print(f"  Fraction full check       = {frac_full:.4f}")
print(f"  Fraction partial phase-out = {frac_partial:.4f}")
print(f"  Fraction fully phased-out = {frac_none:.4f}")

# ============================================================
# MC: run to ergodic steady state
# ============================================================
print(f"\n{'='*60}")
print(f"MC SIMULATION (N={N})")
print("=" * 60)

t0 = time()
eco = AggDemandEconomy
eco.reset()
for a in eco.agents:
    a.initialize_sim()
    a.AggDemandFac = 1.0
    a.RfreeNow = 1.0
    a.CaggNow = 1.0
eco.make_history()

pLvl_mc = eco.agents[0].state_now['pLvl'].copy()
t_mc = time() - t0
print(f"  MC steady-state time: {t_mc:.1f}s")

E_pLvl_mc = np.mean(pLvl_mc)
std_pLvl_mc = np.std(pLvl_mc)
median_pLvl_mc = np.median(pLvl_mc)

print(f"  E[pLvl] (MC)      = {E_pLvl_mc:.4f}")
print(f"  Std[pLvl] (MC)    = {std_pLvl_mc:.4f}")
print(f"  Median pLvl (MC)  = {median_pLvl_mc:.4f}")

mc_quantiles = {}
for q in [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
    mc_quantiles[q] = np.percentile(pLvl_mc, 100 * q)
    print(f"  Q({q:.2f}) = {mc_quantiles[q]:.4f}")

# MC E[check_nrm]
mc_phase_out = np.ones(N)
mc_in_range = (pLvl_mc >= cutoff_start) & (pLvl_mc <= cutoff_end)
mc_above = pLvl_mc > cutoff_end
mc_phase_out[mc_in_range] = 1.0 - (pLvl_mc[mc_in_range] - cutoff_start) / (cutoff_end - cutoff_start)
mc_phase_out[mc_above] = 0.0

mc_check_nrm = CheckStimLvl * mc_phase_out / pLvl_mc
E_check_nrm_mc = np.mean(mc_check_nrm)
mc_frac_full = np.mean(pLvl_mc < cutoff_start)
mc_frac_partial = np.mean(mc_in_range)
mc_frac_none = np.mean(mc_above)

print(f"\n  E[check_nrm] (MC)         = {E_check_nrm_mc:.6f}")
print(f"  Fraction full check       = {mc_frac_full:.4f}")
print(f"  Fraction partial phase-out = {mc_frac_partial:.4f}")
print(f"  Fraction fully phased-out = {mc_frac_none:.4f}")

# ============================================================
# Comparison
# ============================================================
print(f"\n{'='*60}")
print("COMPARISON: analytical vs MC")
print("=" * 60)

e_pct = 100 * (E_pLvl_from_dist - E_pLvl_mc) / E_pLvl_mc
print(f"\n  E[pLvl]:  analytical={E_pLvl_from_dist:.4f}  MC={E_pLvl_mc:.4f}  err={e_pct:+.3f}%")

print(f"\n  Quantile comparison:")
print(f"  {'Q':>6s}  {'Analytical':>12s}  {'MC':>12s}  {'Err%':>8s}")
print(f"  {'-'*42}")
for q in [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]:
    a = analytical_quantiles[q]
    m = mc_quantiles[q]
    err = 100 * (a - m) / m if abs(m) > 1e-12 else 0.0
    print(f"  {q:6.2f}  {a:12.4f}  {m:12.4f}  {err:+8.3f}%")

check_err = 100 * (E_check_nrm_analytical - E_check_nrm_mc) / E_check_nrm_mc
naive_err = 100 * (CheckStimLvl / E_pLvl_analytical - E_check_nrm_mc) / E_check_nrm_mc
print(f"\n  E[check_nrm]:  analytical={E_check_nrm_analytical:.6f}  MC={E_check_nrm_mc:.6f}  err={check_err:+.3f}%")
print(f"  E[check_nrm]:  naive(E[pLvl])={CheckStimLvl / E_pLvl_analytical:.6f}  err={naive_err:+.3f}%")
print(f"  (naive uses CheckStimLvl/{E_pLvl_analytical:.2f} with phase_out at E[pLvl])")

total = time() - t0_total
print(f"\nTotal time: {total:.0f}s ({total/60:.1f} min)")
