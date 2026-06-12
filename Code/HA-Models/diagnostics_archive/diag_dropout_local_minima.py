#!/usr/bin/env python
"""Diagnostic: re-run TM-a CDC dropout (edType=0) from multiple starting points.

Question: does the dropout TM-a estimation always converge to the Apr 18
result (β=0.715, ∇=0.323, GICx=4.43), or are there local minima?

Method: import the objective function from estim_phase2_tm_a.py, run
Nelder-Mead from 4 starting points (the script's default + 3 alternates
near the ESC dropout result and at extreme corners). Report final
parameters + objective value + iter count for each.

This is purely diagnostic; does NOT overwrite the official _TM_a output.
"""

import os
import sys
import time
import numpy as np

os.environ['HAFISCAL_EDTYPES'] = '0'  # ensure parent script only sets up dropout
os.environ['MPLBACKEND'] = 'Agg'

# Add this directory to path
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
sys.path.insert(0, os.path.dirname(THIS_DIR))

# Suppress writes by patching out the file-write step (we don't want to
# overwrite DiscFacEstim_*_TM_a.txt). Easiest way: monkey-patch builtins.open
# inside the loop section. Instead, just import what we need before the
# script runs its own loop.

# The script runs its estimation loop at import time, so we can't import
# it directly. Instead, replicate the setup here.

print("=" * 60)
print("Diagnostic: TM-a CDC dropout from multiple starting points")
print("=" * 60)

# --- Setup mirrors estim_phase2_tm_a.py exactly (incl. IncShkDstn rebuild) ---
import EstimParameters as ep
from EstimParameters import (
    init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
    DiscFacCount, CRRA, AgentCountTotal, Rfree_base,
    data_LorenzPts, data_medianLWPI, data_EducShares,
    GICmaxBetas, theGICfactor, minBeta,
)
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from copy import deepcopy
from HARK.distributions import Uniform, DiscreteDistribution
from HARK.utilities import get_percentiles, get_lorenz_shares
from HARK.estimation import minimize_nelder_mead
from tm_methods import build_tm_agg_fiscal_a, find_ergodic_distribution

Splurge = ep.Splurge
UBspell_normal = ep.UBspell_normal
num_types = 3
print(f"Splurge={Splurge:.6f}  CRRA={CRRA}  Rfree={Rfree_base[0]}  DiscFacCount={DiscFacCount}")

# Build economy + base agents (replicates estim_phase2_tm_a.py:51-87)
InfHorizonTypeAgg_d = AggFiscalType(**init_dropout); InfHorizonTypeAgg_d.cycles = 0
InfHorizonTypeAgg_h = AggFiscalType(**init_highschool); InfHorizonTypeAgg_h.cycles = 0
InfHorizonTypeAgg_c = AggFiscalType(**init_college); InfHorizonTypeAgg_c.cycles = 0
AggDemandEcon = AggregateDemandEconomy(**init_ADEconomy)
InfHorizonTypeAgg_d.get_economy_data(AggDemandEcon)
InfHorizonTypeAgg_h.get_economy_data(AggDemandEcon)
InfHorizonTypeAgg_c.get_economy_data(AggDemandEcon)
BaseTypeList = [InfHorizonTypeAgg_d, InfHorizonTypeAgg_h, InfHorizonTypeAgg_c]

IncomeDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([InfHorizonTypeAgg_d.IncUnemp])])
IncomeDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([InfHorizonTypeAgg_d.IncUnempNoBenefits])])

for ThisType in BaseTypeList:
    ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncomeDstn_unemp]*UBspell_normal + [IncomeDstn_unemp_nobenefits]]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn

TypeList = []
n = 0
for e in range(num_types):
    for b in range(DiscFacCount):
        DiscFac = DiscFacDstns[e].atoms[0][b]
        AgentCount = int(np.floor(AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[b]))
        ThisType = deepcopy(BaseTypeList[e])
        ThisType.AgentCount = AgentCount
        ThisType.DiscFac = DiscFac
        ThisType.seed = n
        TypeList.append(ThisType)
        n += 1

AggDemandEcon.agents = TypeList
AggDemandEcon.solve()
print(f"Economy setup + initial solve done.")


def betas_obj_func_educ_tm_a(beta, spread, GICx, educ_type=0, print_mode=False):
    """Objective function: replicated from estim_phase2_tm_a.py for diagnostic use."""
    dfs = Uniform(beta - spread, beta + spread).discretize(DiscFacCount)
    for thedf in range(DiscFacCount):
        if dfs.atoms[0][thedf] > GICmaxBetas[educ_type] * np.exp(GICx) / (1 + np.exp(GICx)):
            dfs.atoms[0][thedf] = GICmaxBetas[educ_type] * (np.exp(GICx) / (1 + np.exp(GICx)))
        elif dfs.atoms[0][thedf] < minBeta:
            dfs.atoms[0][thedf] = minBeta

    TypeListNewEduc = []
    for b_idx in range(DiscFacCount):
        AgentCount = int(np.floor(AgentCountTotal * data_EducShares[educ_type] * dfs.pmv[b_idx]))
        ThisType = deepcopy(BaseTypeList[educ_type])
        ThisType.AgentCount = AgentCount
        ThisType.DiscFac = dfs.atoms[0][b_idx]
        TypeListNewEduc.append(ThisType)

    TypeListAll = AggDemandEcon.agents
    TypeListAll[educ_type * DiscFacCount:(educ_type + 1) * DiscFacCount] = TypeListNewEduc
    AggDemandEcon.agents = TypeListAll
    AggDemandEcon.solve()

    total_weight = sum(t.AgentCount for t in TypeListNewEduc)
    a_vals_list, w_vals_list = [], []
    for agent in TypeListNewEduc:
        agent_w = agent.AgentCount / total_weight if total_weight > 0 else 1.0 / DiscFacCount
        tm_data = build_tm_agg_fiscal_a(agent, aCount=100)
        ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
        dist_aGrid = tm_data['dist_aGrid']
        J = agent.MrkvArray[0].shape[0]
        A = len(dist_aGrid)
        erg = np.asarray(ergodic).reshape(J, A)
        for j in range(J):
            dstn_j = erg[j, :]
            mask = dstn_j > 1e-15
            if np.any(mask):
                aNrm_vals = dist_aGrid[mask]
                weights = dstn_j[mask] * agent_w
                a_vals_list.append(aNrm_vals)
                w_vals_list.append(weights)
    a_array = np.concatenate(a_vals_list)
    w_array = np.concatenate(w_vals_list)
    w_array /= np.sum(w_array)
    medianLWPI = 100.0 * get_percentiles(a_array, weights=w_array, percentiles=[0.5])
    LorenzPts = 100.0 * get_lorenz_shares(a_array, weights=w_array,
                                          percentiles=[0.2, 0.4, 0.6, 0.8])
    sumSquares = np.sum((medianLWPI - data_medianLWPI[educ_type]) ** 2)
    sumSquares += np.sum((np.array(LorenzPts) - data_LorenzPts[educ_type]) ** 2)
    distance = np.sqrt(sumSquares)
    return distance


# Define starting points: script default + 3 alternates
starting_points = [
    ('script_default',  [0.75,  0.30, 6.0]),
    ('near_ESC',        [0.70,  0.34, 6.07]),  # Edmund's ESC dropout result
    ('near_Apr18',      [0.715, 0.323, 4.43]), # Apr 18 TM-a result (stability check)
    ('low_beta_high_n', [0.65,  0.40, 5.0]),   # different basin probe
]

results = []
for name, x0 in starting_points:
    print(f"\n--- Starting point '{name}': β={x0[0]}, ∇={x0[1]}, GICx={x0[2]} ---")
    f_temp = lambda x: betas_obj_func_educ_tm_a(x[0], x[1], x[2], educ_type=0)
    t0 = time.time()
    opt = minimize_nelder_mead(f_temp, x0, verbose=False)
    elapsed = time.time() - t0
    final_dist = betas_obj_func_educ_tm_a(opt[0], opt[1], opt[2], educ_type=0)
    GICfactor = np.exp(opt[2]) / (1 + np.exp(opt[2]))
    print(f"  β={opt[0]:.5f}  ∇={opt[1]:.5f}  GICx={opt[2]:.4f} (GICfactor={GICfactor:.4f})")
    print(f"  final distance = {final_dist:.6f}    elapsed = {elapsed/60:.1f} min")
    results.append((name, x0, opt.tolist(), final_dist, elapsed))

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"{'Start':<18} {'β_init':>7} {'β_opt':>9} {'∇_opt':>9} {'GICx':>7} {'distance':>11}")
print("-" * 70)
for name, x0, opt, dist, _ in results:
    print(f"{name:<18} {x0[0]:>7.3f} {opt[0]:>9.5f} {opt[1]:>9.5f} {opt[2]:>7.3f} {dist:>11.6f}")

# Decision: are any results materially different?
betas = [r[2][0] for r in results]
beta_range = max(betas) - min(betas)
print(f"\nβ range across starts: {beta_range:.5f}")
print("Interpretation:")
if beta_range < 0.005:
    print("  Convergence is robust — all starts land in the same basin.")
    print("  Dropout β=0.715 is the unique TM-a CDC fit; anomaly is structural, not a local-min artifact.")
elif beta_range < 0.02:
    print("  Mild basin variation — multiple weak local minima but answers within ~2% of each other.")
else:
    print("  STRONG basin variation — distinct local minima found. Apr 18 result was basin-dependent.")
