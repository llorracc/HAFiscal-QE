#!/usr/bin/env python
"""TM-based Step-2 (β/∇) estimation — noise-free alternative to EstimAggFiscalMAIN.py.

The MC-based estimation in EstimAggFiscalMAIN suffers from simulation noise,
causing Nelder-Mead to need 100+ iterations (hours of wall clock). The TM
approach computes the ergodic wealth distribution analytically → zero noise →
the optimizer converges in ~20 iterations (minutes).

NOTE (as of BUG-033): production Step-2 uses the a-indexed analogue
estim_phase2_tm_a.py — the m-indexed TM here collapses the ξ-variance under
splurge-in-budget; this path is the legacy/fallback. Production calibration
files are the *_TM_a*.txt.

Usage:
    cd Code/HA-Models/FromPandemicCode
    python estim_phase2_tm.py                    # all 3 edTypes
    HAFISCAL_EDTYPES=1,2 python estim_phase2_tm.py  # subset

Writes results in the same format as EstimAggFiscalMAIN → Results/DiscFacEstim_*.txt
"""

import os, sys, time
import numpy as np
from copy import deepcopy
from HARK.distributions import Uniform
from HARK.utilities import get_percentiles, get_lorenz_shares
from HARK.estimation import minimize_nelder_mead

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import EstimParameters as ep
from EstimParameters import (
    init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
    DiscFacCount, CRRA, AgentCountTotal, Rfree_base,
    data_LorenzPts, data_medianLWPI, data_EducShares,
    GICmaxBetas, gic_capped_beta, minBeta,
)
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from tm_methods import build_tm_agg_fiscal, find_ergodic_distribution

Splurge = ep.Splurge
UBspell_normal = ep.UBspell_normal
num_types = 3

print(f"TM-based Phase 2 estimation")
print(f"Splurge={Splurge:.6f}  CRRA={CRRA}  Rfree={Rfree_base[0]}  DiscFacCount={DiscFacCount}")
print(f"AgentCountTotal={AgentCountTotal} (used for agent weighting, not simulation)")

# ---- Build economy (same as EstimAggFiscalMAIN lines 681-740) ----
t0_setup = time.time()
InfHorizonTypeAgg_d = AggFiscalType(**init_dropout)
InfHorizonTypeAgg_d.cycles = 0
InfHorizonTypeAgg_h = AggFiscalType(**init_highschool)
InfHorizonTypeAgg_h.cycles = 0
InfHorizonTypeAgg_c = AggFiscalType(**init_college)
InfHorizonTypeAgg_c.cycles = 0
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
print(f"Economy setup + initial solve: {time.time()-t0_setup:.1f}s")


# ---- TM-based objective function ----

def betas_obj_func_educ_tm(beta, spread, GICx, educ_type=2, print_mode=False):
    """TM-based objective: same targets as MC betas_obj_func_educ but noise-free."""
    dfs = Uniform(beta - spread, beta + spread).discretize(DiscFacCount)
    for thedf in range(DiscFacCount):
        if dfs.atoms[0][thedf] > gic_capped_beta(educ_type, np.exp(GICx) / (1 + np.exp(GICx))):
            dfs.atoms[0][thedf] = gic_capped_beta(educ_type, np.exp(GICx) / (1 + np.exp(GICx)))
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

    # Build TM + ergodic for this edType's 7 agents
    total_weight = sum(t.AgentCount for t in TypeListNewEduc)
    a_vals_list = []
    w_vals_list = []

    for agent in TypeListNewEduc:
        agent_w = agent.AgentCount / total_weight if total_weight > 0 else 1.0 / DiscFacCount
        tm_data = build_tm_agg_fiscal(agent, mCount=100)
        ergodic = find_ergodic_distribution(tm_data['TranMatrix'])

        dist_mGrid = tm_data['dist_mGrid']
        J = agent.MrkvArray[0].shape[0]
        M = len(dist_mGrid)

        for j in range(J):
            dstn_j = ergodic[j * M:(j + 1) * M]
            mask = dstn_j > 1e-15
            if np.any(mask):
                aNrm_vals = (1.0 - Splurge) * tm_data['aPol'][j][mask]
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

    if print_mode:
        print(f"  beta={beta:.4f} nabla={spread:.4f} GICx={GICx:.4f}")
        print(f"  medianLWPI: model={medianLWPI[0]:.2f}  data={data_medianLWPI[educ_type]:.2f}")
        print(f"  Lorenz: model=[{', '.join(f'{x:.2f}' for x in LorenzPts)}]  "
              f"data=[{', '.join(f'{x:.2f}' for x in data_LorenzPts[educ_type])}]")
        print(f"  distance={distance:.6f}")

    return distance


# ---- Run estimation ----

_edtypes_env = os.environ.get('HAFISCAL_EDTYPES', '0,1,2')
edtypes_to_run = [int(s) for s in _edtypes_env.split(',') if s.strip()]
print(f"\nEdTypes to estimate: {edtypes_to_run}")

res_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Results')
df_base = f"DiscFacEstim_CRRA_{CRRA}_R_{Rfree_base[0]}"
if ep.IncUnemp != 0.7 or ep.IncUnempNoBenefits != 0.5:
    df_base += "_altBenefits"
if Splurge == 0:
    df_base += "_Splurge0"

educ_names = ['Dropout', 'Highschool', 'College']
init_vals = {0: [0.75, 0.3, 6], 1: [0.93, 0.07, 5], 2: [0.98, 0.015, 6]}

for edType in edtypes_to_run:
    print(f"\n{'='*60}")
    print(f"Estimating {educ_names[edType]} (edType={edType}) via TM")
    print(f"{'='*60}")

    f_temp = lambda x, et=edType: betas_obj_func_educ_tm(x[0], x[1], x[2], educ_type=et)

    t0 = time.time()
    opt_params = minimize_nelder_mead(f_temp, init_vals[edType], verbose=True)
    elapsed = time.time() - t0

    GICfactor = np.exp(opt_params[2]) / (1 + np.exp(opt_params[2]))
    print(f"\nFinished {educ_names[edType]} in {elapsed/60:.1f} min")
    print(f"  Beta={opt_params[0]:.4f}  Nabla={opt_params[1]:.4f}  GIC factor={GICfactor:.4f}")

    betas_obj_func_educ_tm(opt_params[0], opt_params[1], opt_params[2],
                           educ_type=edType, print_mode=True)

    suffix = f"_edType{edType}" if len(edtypes_to_run) == 1 else ""
    out_path = os.path.join(res_dir, df_base + suffix + "_TM.txt")
    mode = 'w' if edType == edtypes_to_run[0] and not suffix else 'w'
    with open(out_path, mode) as f:
        f.write(repr({'EducationGroup': edType, 'beta': opt_params[0],
                       'nabla': opt_params[1], 'GICx': opt_params[2]}) + '\n')
    print(f"  Wrote {out_path}")

# Footer
if len(edtypes_to_run) == 3:
    out_path = os.path.join(res_dir, df_base + "_TM.txt")
    with open(out_path, 'a') as f:
        f.write(f"\nParameters: R = {round(Rfree_base[0],2)}, CRRA = {round(CRRA,2)}, "
                f"IncUnemp = {round(ep.IncUnemp,2)}, IncUnempNoBenefits = {round(ep.IncUnempNoBenefits,2)}, "
                f"Splurge = {Splurge}\n")

print(f"\nDone.")
