"""D-cohort log(p) moments: MC convergence to exact vs (1-u) approx.

Parameterizes a single Dropout (D) education-group agent with the cached
preference parameters, runs MC at progressively larger AgentCount, and
compares MC empirical mean/var of log(pLvl) to:
  (a) the (1-u) lognormal-mixture single-Gaussian-per-cohort approximation
      (compute_pLvl_distribution path)
  (b) the EXACT Markov-chain matrix-iteration formula
      (compute_log_p_moments_exact, added 2026-05-06)

Usage:
  python diag_d_logp_moments_n_sweep.py <N>           # single N value
  ... or launch 5 in parallel via launch_n_sweep.sh
"""

import os, sys, numpy as np
from copy import deepcopy

if len(sys.argv) < 2:
    print("Usage: python diag_d_logp_moments_n_sweep.py <N>")
    sys.exit(1)
N_mc = int(sys.argv[1])

# Reset argv to avoid Parameters.py picking it up.
sys.argv = sys.argv[:1] + ['1.01', '2.0', '0.7', '0.5']

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from income_process_sst import effective_pLvl_growth, effective_perm_shock_periods_for_t_age
from tm_methods import compute_pLvl_distribution, compute_log_p_moments_exact

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

# === Build single Dropout agent with cached β/∇ ===
# Cached values (from DiscFacEstim_CRRA_2.0_R_1.01.txt edType=0):
#   β=0.6631156415667147, ∇=0.38357242126244395
init_dict = init_dropout
agent = AggFiscalType(**init_dict)
agent.cycles = 0
# Use the canonical β atom (DiscFacDstns[0] is the dropout β-distribution)
agent.DiscFac = DiscFacDstns[0].atoms[0][0]

# Build IncShkDstn manually (HAFiscal pattern; see EstimAggFiscalMAIN.py)
AggEco = AggregateDemandEconomy(**init_ADEconomy)
agent.get_economy_data(AggEco)
IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnempNoBenefits])])
agent.IncShkDstn[0].seed = 763607780
agent.IncShkDstn[0].reset()
agent.IncShkDstn = [[agent.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
agent.IncShkDstn_base = agent.IncShkDstn

AggEco.agents = [agent]
agent.AgentCount = N_mc
agent.seed = 42000 + N_mc  # seed varies with N to avoid coincident streams
agent.get_economy_data(AggEco)

print(f"=== D-cohort log(p) moments | N={N_mc} ===")
print(f"DiscFac={agent.DiscFac:.6f}  Urate_normal={agent.Urate_normal}")

# === Analytical moments (both approx and exact) ===
u = float(getattr(agent, 'Urate_normal', 0.0))
pLvl_grid, p_weights = compute_pLvl_distribution(agent, n_points=2000, unemployment_rate=u)
log_p_grid = np.log(pLvl_grid)
mean_lp_approx = float(np.dot(p_weights, log_p_grid))
var_lp_approx = float(np.dot(p_weights, log_p_grid ** 2) - mean_lp_approx ** 2)

exact = compute_log_p_moments_exact(agent, unemployment_rate=u)
mean_lp_exact = exact['mean_log_p_exact']
var_lp_exact = exact['var_log_p_exact']

print(f"(1-u) approx:  mean log(p) = {mean_lp_approx:+.6f}  var log(p) = {var_lp_approx:.6f}")
print(f"EXACT Markov:  mean log(p) = {mean_lp_exact:+.6f}  var log(p) = {var_lp_exact:.6f}")
print(f"approx - exact: mean Δ = {mean_lp_approx - mean_lp_exact:+.6e}  var Δ = {var_lp_approx - var_lp_exact:+.6e}")

# === MC empirical moments ===
# Solve agent so we can simulate
AggEco.solve()

# Initialize MC: sample ages from ergodic, sample pLvl from (1-u)-approx age-conditional.
agent.initialize_sim()
T_age = int(getattr(agent, 'T_age', 400))
LivPrb = float(agent.LivPrb[0][0])
ages = np.arange(T_age)
age_probs = (LivPrb ** ages) * (1.0 - LivPrb) / (1.0 - LivPrb ** T_age)
age_probs /= age_probs.sum()
rng = np.random.default_rng(seed=42000 + N_mc)
sampled_ages = rng.choice(T_age, size=N_mc, replace=True, p=age_probs)
agent.t_age = sampled_ages.copy()
agent.state_now['t_age'] = sampled_ages.copy()

# pLvl init from (1-u) approx age-conditional lognormal:
#   log p | age=k ~ N((k+1)*log g_eff - eff_emp_periods*sigma^2/2, eff_emp_periods*sigma^2)
g_eff = effective_pLvl_growth(agent, u)
eff_emp_periods = effective_perm_shock_periods_for_t_age(sampled_ages + 1, agent, u)
ps_var = float(np.var(np.log(agent.IncShkDstn[0][0].atoms[0])))
mu_lp = (sampled_ages + 1) * np.log(g_eff) - eff_emp_periods * ps_var / 2.0
sigma_lp = np.sqrt(eff_emp_periods * ps_var)
log_pLvl_init = rng.normal(mu_lp, sigma_lp)
agent.state_now['pLvl'] = np.exp(log_pLvl_init)

# Initialize Markov state at ergodic
J = int(agent.num_base_MrkvStates)
M = np.asarray(agent.MrkvArray[0], dtype=float)[:J, :J]
eigvals, eigvecs = np.linalg.eig(M.T)
idx = int(np.argmin(np.abs(eigvals - 1.0)))
ergodic = np.abs(eigvecs[:, idx].real); ergodic /= ergodic.sum()
agent.state_now['MrkvNow'] = rng.choice(J, size=N_mc, replace=True, p=ergodic).astype(int)

# Bypass the AD machinery: pin AD factor to 1 (no demand amplification) and
# Cratio to 1 (no consumption-vs-baseline ratio) so sim_one_period runs without
# requiring the economy-level AD loop. We only care about pLvl evolution.
agent.AggDemandFac = np.ones(N_mc)
agent.AggDemandFacNext = 1.0
agent.Cratio = 1.0

# Simulate enough periods for cross-section to mix to true ergodic
T_warmup = 150
print(f"Simulating T_warmup={T_warmup} periods to allow mixing to MC ergodic...")
for t in range(T_warmup):
    # Re-pin AD-related state each period to be safe
    agent.AggDemandFac = np.ones(N_mc)
    agent.AggDemandFacNext = 1.0
    agent.Cratio = 1.0
    agent.sim_one_period()

# Empirical moments
log_pLvl_mc = np.log(agent.state_now['pLvl'][agent.state_now['pLvl'] > 0])
mean_lp_mc = float(np.mean(log_pLvl_mc))
var_lp_mc = float(np.var(log_pLvl_mc))

# Standard errors of MC moment estimates (using sample variance of log p):
n_eff = len(log_pLvl_mc)
mc_se_mean = np.sqrt(var_lp_mc / n_eff)
# SE of variance estimate ≈ sqrt(2*var^2/(n-1)) for normal; use conservatively
mc_se_var = np.sqrt(2.0 * var_lp_mc ** 2 / max(n_eff - 1, 1))

print()
print(f"MC empirical (N_eff={n_eff}):")
print(f"  mean log(p) = {mean_lp_mc:+.6f} ± {mc_se_mean:.6f}")
print(f"  var  log(p) = {var_lp_mc:.6f} ± {mc_se_var:.6f}")
print()
print(f"MC vs APPROX:  mean Δ = {mean_lp_mc - mean_lp_approx:+.6e}  ({(mean_lp_mc - mean_lp_approx)/mc_se_mean:+.2f}σ)")
print(f"               var  Δ = {var_lp_mc - var_lp_approx:+.6e}  rel = {(var_lp_mc - var_lp_approx)/var_lp_approx*100:+.3f}%")
print(f"MC vs EXACT:   mean Δ = {mean_lp_mc - mean_lp_exact:+.6e}  ({(mean_lp_mc - mean_lp_exact)/mc_se_mean:+.2f}σ)")
print(f"               var  Δ = {var_lp_mc - var_lp_exact:+.6e}  rel = {(var_lp_mc - var_lp_exact)/var_lp_exact*100:+.3f}%")

# Save results for downstream aggregation
import json
out = {
    'N': N_mc,
    'mean_lp_approx': mean_lp_approx, 'var_lp_approx': var_lp_approx,
    'mean_lp_exact': mean_lp_exact, 'var_lp_exact': var_lp_exact,
    'mean_lp_mc': mean_lp_mc, 'var_lp_mc': var_lp_mc,
    'mc_se_mean': mc_se_mean, 'mc_se_var': mc_se_var,
    'n_eff': n_eff, 'T_warmup': T_warmup,
}
out_path = f'/tmp/d_logp_n{N_mc}.json'
with open(out_path, 'w') as f:
    json.dump(out, f, indent=2)
print(f"saved {out_path}")
