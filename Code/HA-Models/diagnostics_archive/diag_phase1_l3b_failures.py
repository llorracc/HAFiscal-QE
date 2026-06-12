"""
Diagnostic for L3b cross-method failures: investigates options 1-3 from
the L3b-HALT report.

Purpose: identify the source of the ~14× gap/SE between MC and TM mean
K/Y for HS at finer config.

Per user direction: TM stays at a-grid=200 (we know 200→1000 only shifts
K/Y by <0.2%, so TM-side residual is small).

Three investigations bundled:

  Option 1: T_burnin sweep at fixed N=25k × 5 seeds.
    Vary T_burnin ∈ {100, 200, 400, 800}; report MC mean(K/Y) at each.
    If mean drifts substantially as burnin grows → MC has burn-in bias
    that doesn't shrink with N. Fix: use larger T_burnin in L3b.

  Option 2: Add intermediate N values for cleaner asymptotic-rate slope.
    N ∈ {5k, 10k, 25k, 50k} × 5 seeds at T_burnin=400 (best from option 1
    or default if option 1 inconclusive).
    Fit log(std) vs log(N) using all 4 points; report slope.
    Target: slope ∈ [-0.6, -0.4]; deviations indicate test-design issue.

  Option 3: Harmenberg neutral-measure on TM.
    Compute TM K/Y under both measure conventions; report both.
    If neutral-measure TM matches MC better than non-neutral → MC
    convention is implicitly neutral-measure (or vice versa); use the
    matching one in L3b.

Total compute estimate: ~30-50 min.
Output: results printed to stdout + JSON dump for post-analysis.

Run via:
  PYTHONUNBUFFERED=1 nohup python diag_phase1_l3b_failures.py > /tmp/diag.log 2>&1 &
"""

import os
import sys
import json
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# CLAUDE.md: patch sys.argv before importing EstimParameters.
sys.argv = ['diag_phase1_l3b_failures']

from EstimParameters import init_highschool, init_ADEconomy, UBspell_normal
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from tm_methods import (
    build_tm_agg_fiscal_a,
    compute_type_aggregates_tm_a,
    find_ergodic_distribution,
)
from HARK.distributions import DiscreteDistribution


def build_and_solve_HS():
    """Build + solve a Highschool AggFiscalType (matches L3a/L3b fixture)."""
    init = deepcopy(init_highschool)
    agent = AggFiscalType(**init)
    agent.cycles = 0
    economy = AggregateDemandEconomy(**init_ADEconomy)
    agent.get_economy_data(economy)
    IncomeDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnemp])]
    )
    IncomeDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnempNoBenefits])]
    )
    agent.IncShkDstn = [
        [agent.IncShkDstn[0]]
        + [IncomeDstn_unemp] * UBspell_normal
        + [IncomeDstn_unemp_nobenefits]
    ]
    agent.IncShkDstn_base = agent.IncShkDstn
    economy.agents = [agent]
    economy.solve()
    return agent


def run_mc(agent_template, N, seed, T_sim, T_burnin):
    """Run MC and compute normalized K/Y (mean(aNrm)/mean(TranShk))."""
    agent = deepcopy(agent_template)
    agent.AgentCount = N
    agent.seed = seed
    agent.T_sim = T_sim
    agent.track_vars = ['aNrm', 'TranShk']
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0
    agent.Cratio = 1.0
    agent.EconomyMrkvNow_hist = [0] * T_sim
    agent.simulate()
    aNrm_post = agent.history['aNrm'][T_burnin:]
    tran_post = agent.history['TranShk'][T_burnin:]
    mean_aNrm = float(np.mean(aNrm_post))
    mean_TranShk = float(np.mean(tran_post))
    return mean_aNrm / mean_TranShk if mean_TranShk > 0 else float('nan')


def compute_tm_KY(agent, a_grid_size=200, neutral_measure=False):
    """Run TM-a chain and return K/Y."""
    tm_data = build_tm_agg_fiscal_a(
        agent, aCount=a_grid_size, neutral_measure=neutral_measure,
    )
    ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
    agg = compute_type_aggregates_tm_a(
        agent, tm_data, ergodic, neutral_measure=neutral_measure,
    )
    return agg['A_nrm'] / agg['Income_nrm'] if agg['Income_nrm'] > 0 else float('nan')


# =====================================================================

print("="*72)
print("L3b-failure diagnostic — options 1+2+3")
print("="*72)

print("\nBuilding + solving HS agent...")
t0 = time.time()
agent = build_and_solve_HS()
print(f"  agent setup: {time.time()-t0:.1f}s")

# ---------------------------------------------------------------------
# Option 3: Harmenberg neutral-measure on TM (cheapest; do first)
# ---------------------------------------------------------------------
print("\n" + "="*72)
print("OPTION 3: Harmenberg neutral measure (TM-side)")
print("="*72)
tm_default = compute_tm_KY(agent, a_grid_size=200, neutral_measure=False)
tm_neutral = compute_tm_KY(agent, a_grid_size=200, neutral_measure=True)
print(f"  TM K/Y (default measure)        = {tm_default:.6f}")
print(f"  TM K/Y (neutral measure)        = {tm_neutral:.6f}")
print(f"  diff (neutral - default)        = {tm_neutral - tm_default:.6f}")

# ---------------------------------------------------------------------
# Option 1: T_burnin sweep at fixed N=25k × 5 seeds
# ---------------------------------------------------------------------
print("\n" + "="*72)
print("OPTION 1: T_burnin sweep (MC, N=25k, 5 seeds)")
print("="*72)
burnin_sweep = {}
for T_burnin in [100, 200, 400, 800]:
    T_sim = T_burnin + 200  # ensure post-burnin window of 200 periods
    t0 = time.time()
    Ks = []
    for s in range(5):
        Ks.append(run_mc(agent, N=25000, seed=s, T_sim=T_sim, T_burnin=T_burnin))
    elapsed = time.time() - t0
    burnin_sweep[T_burnin] = {
        'mean': float(np.mean(Ks)),
        'std':  float(np.std(Ks)),
        'all':  Ks,
        'elapsed_sec': elapsed,
    }
    print(f"  T_burnin={T_burnin:>3d}  mean(K/Y)={np.mean(Ks):.6f}  std={np.std(Ks):.6f}  ({elapsed:.0f}s)")

burnin_means = [burnin_sweep[b]['mean'] for b in [100, 200, 400, 800]]
burnin_drift = max(burnin_means) - min(burnin_means)
print(f"  drift across T_burnin: {burnin_drift:.6f}  (relative: {burnin_drift/np.mean(burnin_means):.4%})")
if burnin_drift / np.mean(burnin_means) > 0.005:
    print(f"  ⚠ DRIFT > 0.5%: burn-in bias is a likely contributor to L3b cross-method gap")
else:
    print(f"  ✓ DRIFT < 0.5%: burn-in bias is NOT the dominant source")

# ---------------------------------------------------------------------
# Option 2: Intermediate N values for cleaner asymptotic-rate slope
# ---------------------------------------------------------------------
print("\n" + "="*72)
print("OPTION 2: N sweep for asymptotic-rate slope (5 seeds each)")
print("="*72)
T_burnin_use = 400  # use a generous burnin to remove that as a confounder
T_sim_use = T_burnin_use + 200
N_sweep = {}
for N in [2000, 5000, 10000, 25000, 50000]:
    t0 = time.time()
    Ks = []
    for s in range(5):
        Ks.append(run_mc(agent, N=N, seed=s, T_sim=T_sim_use, T_burnin=T_burnin_use))
    elapsed = time.time() - t0
    N_sweep[N] = {
        'mean': float(np.mean(Ks)),
        'std':  float(np.std(Ks)),
        'all':  Ks,
        'elapsed_sec': elapsed,
    }
    print(f"  N={N:>5d}  mean(K/Y)={np.mean(Ks):.6f}  std={np.std(Ks):.6f}  ({elapsed:.0f}s)")

# Fit log-std vs log-N over all 5 N values
Ns = sorted(N_sweep.keys())
log_Ns = np.log(Ns)
log_stds = np.array([np.log(N_sweep[N]['std']) for N in Ns])
slope, intercept = np.polyfit(log_Ns, log_stds, 1)
print(f"\n  Fitted log-std vs log-N:  slope = {slope:.3f} (target -0.5 ± 0.1)")
print(f"  Per-N residuals from fit:")
for N in Ns:
    pred = intercept + slope * np.log(N)
    actual = np.log(N_sweep[N]['std'])
    print(f"    N={N:>5d}  log-std actual={actual:.3f}  predicted={pred:.3f}  resid={actual-pred:+.3f}")

# ---------------------------------------------------------------------
# Cross-method gap with the best-burnin config + N=50k
# ---------------------------------------------------------------------
print("\n" + "="*72)
print("CROSS-METHOD GAP at best config (T_burnin=400, N=50k, 5 seeds, TM grid=200)")
print("="*72)
mc_50k = N_sweep[50000]['mean']
mc_se_50k = N_sweep[50000]['std'] / np.sqrt(5)
print(f"  MC mean K/Y       = {mc_50k:.6f}  (SE={mc_se_50k:.6f})")
print(f"  TM default K/Y    = {tm_default:.6f}")
print(f"  TM neutral K/Y    = {tm_neutral:.6f}")
print(f"  gap (MC - TM_def) = {mc_50k - tm_default:+.6f}  rel={abs(mc_50k - tm_default)/abs(mc_50k):.4%}  gap/SE={(mc_50k - tm_default)/mc_se_50k:.2f}")
print(f"  gap (MC - TM_neu) = {mc_50k - tm_neutral:+.6f}  rel={abs(mc_50k - tm_neutral)/abs(mc_50k):.4%}  gap/SE={(mc_50k - tm_neutral)/mc_se_50k:.2f}")

# Save to JSON for post-analysis
output = {
    'option_3_neutral_measure': {
        'tm_default': tm_default,
        'tm_neutral': tm_neutral,
        'tm_grid_size': 200,
    },
    'option_1_burnin_sweep': burnin_sweep,
    'option_2_N_sweep': N_sweep,
    'option_2_slope': float(slope),
    'option_2_intercept': float(intercept),
    'cross_method_summary': {
        'mc_mean_50k': mc_50k,
        'mc_se_50k': mc_se_50k,
        'gap_default_TM': mc_50k - tm_default,
        'gap_neutral_TM': mc_50k - tm_neutral,
    },
}
with open('/tmp/diag_phase1_l3b_failures_results.json', 'w') as f:
    json.dump(output, f, indent=2, default=float)
print("\nResults saved to /tmp/diag_phase1_l3b_failures_results.json")
print("="*72)
print("DIAGNOSTIC COMPLETE")
print("="*72)
