"""Reproduce qe_fidelity_full's per-cohort drift at the SAME per-cohort N.

qe_fidelity_full Baseline uses N=10000 total split as:
  D  cohort: 132 agents per (edu, β-atom)
  HS cohort: 752 agents per (edu, β-atom)
  C  cohort: 542 agents per (edu, β-atom)

If the residual drift in qe_fidelity_full is MC sampling noise at small N,
running this script at those N's should reproduce the magnitude.

Usage:
  python diag_qe_per_cohort_drift.py <edu_idx> <seed>
    edu_idx: 0=D, 1=HS, 2=C
"""
import os, sys, numpy as np
from copy import deepcopy

if len(sys.argv) < 3:
    print("Usage: python diag_qe_per_cohort_drift.py <edu_idx 0..2> <seed>")
    sys.exit(1)
edu_idx = int(sys.argv[1])
seed = int(sys.argv[2])

# Per-cohort N from qe_fidelity_full Baseline (10000 × edu_share / 7 β-atoms)
PER_COHORT_N = {0: 132, 1: 752, 2: 542}
EDU_LABEL = {0: 'D', 1: 'HS', 2: 'C'}
N_mc = PER_COHORT_N[edu_idx]

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

init_dicts = [init_dropout, init_highschool, init_college]
init_dict = init_dicts[edu_idx]
agent = AggFiscalType(**init_dict)
agent.cycles = 0
# Center β atom (β=0.6631 for D, 0.9001 for HS, 0.9783 for C — atom index 3 of 7)
agent.DiscFac = DiscFacDstns[edu_idx].atoms[0][min(3, len(DiscFacDstns[edu_idx].atoms[0])-1)]

AggEco = AggregateDemandEconomy(**init_ADEconomy)
agent.get_economy_data(AggEco)
IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnempNoBenefits])])
agent.IncShkDstn[0].seed = 763607780 + seed
agent.IncShkDstn[0].reset()
agent.IncShkDstn = [[agent.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
agent.IncShkDstn_base = agent.IncShkDstn

AggEco.agents = [agent]
agent.AgentCount = N_mc
agent.seed = 42000 + seed * 1000 + edu_idx
agent.get_economy_data(AggEco)

print(f"=== {EDU_LABEL[edu_idx]} cohort | N={N_mc} | seed={seed} ===")

u = float(getattr(agent, 'Urate_normal', 0.0))
exact = compute_log_p_moments_exact(agent, unemployment_rate=u)
print(f"EXACT: mean log(p) = {exact['mean_log_p_exact']:+.6f}  var log(p) = {exact['var_log_p_exact']:.6f}")

AggEco.solve()

agent.initialize_sim()
T_age = int(getattr(agent, 'T_age', 400))
LivPrb = float(agent.LivPrb[0][0])
ages = np.arange(T_age)
age_probs = (LivPrb ** ages) * (1.0 - LivPrb) / (1.0 - LivPrb ** T_age)
age_probs /= age_probs.sum()
rng = np.random.default_rng(seed=42000 + seed * 1000 + edu_idx)
sampled_ages = rng.choice(T_age, size=N_mc, replace=True, p=age_probs)
agent.t_age = sampled_ages.copy()
agent.state_now['t_age'] = sampled_ages.copy()

# Init pLvl from EXACT analytical (sample from per-cohort lognormal with exact moments).
# Use the (1-u) form for per-cohort sampling but rescale to hit exact aggregate moments.
g_eff = effective_pLvl_growth(agent, u)
eff_emp_periods = effective_perm_shock_periods_for_t_age(sampled_ages + 1, agent, u)
ps_var = float(np.var(np.log(agent.IncShkDstn[0][0].atoms[0])))
mu_lp = (sampled_ages + 1) * np.log(g_eff) - eff_emp_periods * ps_var / 2.0
sigma_lp = np.sqrt(eff_emp_periods * ps_var)
log_pLvl_init = rng.normal(mu_lp, sigma_lp)
agent.state_now['pLvl'] = np.exp(log_pLvl_init)

J = int(agent.num_base_MrkvStates)
M = np.asarray(agent.MrkvArray[0], dtype=float)[:J, :J]
eigvals, eigvecs = np.linalg.eig(M.T)
idx = int(np.argmin(np.abs(eigvals - 1.0)))
ergodic = np.abs(eigvecs[:, idx].real); ergodic /= ergodic.sum()
agent.state_now['MrkvNow'] = rng.choice(J, size=N_mc, replace=True, p=ergodic).astype(int)

agent.AggDemandFac = np.ones(N_mc)
agent.AggDemandFacNext = 1.0
agent.Cratio = 1.0

T_warmup = 150
for t in range(T_warmup):
    agent.AggDemandFac = np.ones(N_mc)
    agent.AggDemandFacNext = 1.0
    agent.Cratio = 1.0
    agent.sim_one_period()

log_pLvl_mc = np.log(agent.state_now['pLvl'][agent.state_now['pLvl'] > 0])
mean_lp_mc = float(np.mean(log_pLvl_mc))
var_lp_mc = float(np.var(log_pLvl_mc))
n_eff = len(log_pLvl_mc)

# Residuals vs EXACT
mean_lp_exact = exact['mean_log_p_exact']; var_lp_exact = exact['var_log_p_exact']
mean_resid_abs = mean_lp_mc - mean_lp_exact
var_resid_rel = (var_lp_mc - var_lp_exact) / var_lp_exact

print(f"MC: mean log(p) = {mean_lp_mc:+.6f}  var log(p) = {var_lp_mc:.6f}  N_eff = {n_eff}")
print(f"residuals vs EXACT: mean abs = {mean_resid_abs:+.6f}  var rel = {var_resid_rel:+.4f} ({var_resid_rel*100:+.2f}%)")

import json
out = {
    'edu_idx': edu_idx, 'edu': EDU_LABEL[edu_idx],
    'N_mc': N_mc, 'seed': seed,
    'mean_lp_exact': mean_lp_exact, 'var_lp_exact': var_lp_exact,
    'mean_lp_mc': mean_lp_mc, 'var_lp_mc': var_lp_mc,
    'mean_resid_abs': mean_resid_abs, 'var_resid_rel': var_resid_rel,
    'n_eff': n_eff,
}
out_path = f'/tmp/qe_drift_edu{edu_idx}_seed{seed}.json'
with open(out_path, 'w') as f:
    json.dump(out, f, indent=2)
print(f"saved {out_path}")
