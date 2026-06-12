"""
Step-by-step trace of what happens to an employed agent who becomes
unemployed, in both TM and MC, starting from mNrm ≈ 2.0.

No full simulations needed — just trace through the code logic.
"""

import os
import sys
import numpy as np
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
    build_tm_agg_fiscal,
    find_ergodic_distribution,
)

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

J = num_base_MrkvStates

BaseType = AggFiscalType(**init_highschool)
BaseType.cycles = 0
BaseType.AgentCount = 1000
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])

BaseType.IncShkDstn[0].seed = 763607780
BaseType.IncShkDstn[0].reset()

BaseType.IncShkDstn = [[BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
BaseType.IncShkDstn_base = BaseType.IncShkDstn
IncShkDstn_recession = [BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
BaseType.IncShkDstn_recession = IncShkDstn_recession
BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
BaseType.IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

AggEco.agents = [BaseType]
AggEco.solve()

sol = BaseType.solution[0]

# ============================================================
# Extract parameters
# ============================================================
Rfree = BaseType.Rfree[0]  # same for all states
PermGroFac = BaseType.PermGroFac[0][0]  # same for all states
Splurge = BaseType.Splurge

print(f"J = {J}")
print(f"Rfree = {Rfree}")
print(f"PermGroFac = {PermGroFac}")
print(f"Splurge = {Splurge}")
print(f"IncUnemp = {BaseType.IncUnemp}")
print(f"IncUnempNoBenefits = {BaseType.IncUnempNoBenefits}")

# IncShkDstn per state
print(f"\nIncShkDstn per micro state:")
for j in range(J):
    d = BaseType.IncShkDstn_base[0][j]
    print(f"  State {j}: pmv={d.pmv[:3]}... atoms[0][:3]={d.atoms[0][:3]}... atoms[1][:3]={d.atoms[1][:3]}...")
    print(f"           E[PermShk]={np.dot(d.pmv, d.atoms[0]):.6f}, E[TranShk]={np.dot(d.pmv, d.atoms[1]):.6f}")
    print(f"           n_shocks={len(d.pmv)}")

# Micro transition matrix
micro = BaseType.CondMrkvArrays[0]
print(f"\nMicro transition matrix:")
print(micro)

# ============================================================
# TRACE: Manual calculation for an agent at mNrm = 2.0
# ============================================================
mNrm_start = 2.0
print(f"\n{'='*70}")
print(f"TRACE: Agent starting at mNrm = {mNrm_start} in state 0 (employed)")
print(f"{'='*70}")

# Period 0: employed, mNrm = 2.0
print(f"\n--- Period 0: State 0 (employed), mNrm = {mNrm_start} ---")
cFunc_0 = sol.cFunc[0]
cNrm_0 = float(cFunc_0(mNrm_start, 1.0))
aNrm_0 = mNrm_start - cNrm_0
print(f"  cFunc_0({mNrm_start}) = {cNrm_0:.6f}")
print(f"  aNrm_0 = {mNrm_start} - {cNrm_0:.6f} = {aNrm_0:.6f}")

# Transition to state 1 (UB period 1)
# MC: bNrm = aNrm * Rfree / (PermGroFac * PermShk)
# For unemployed: PermShk = 1.0, TranShk = 0.7
PermShk_unemp = 1.0
TranShk_UB = BaseType.IncUnemp  # 0.7
TranShk_noBen = BaseType.IncUnempNoBenefits  # 0.5

bNrm_1_mc = aNrm_0 * Rfree / (PermGroFac * PermShk_unemp)
mNrm_1_mc = bNrm_1_mc + TranShk_UB

print(f"\n--- Period 1: State 1 (UB period 1) ---")
print(f"  MC: bNrm = {aNrm_0:.6f} * {Rfree} / ({PermGroFac} * {PermShk_unemp}) = {bNrm_1_mc:.6f}")
print(f"  MC: mNrm = {bNrm_1_mc:.6f} + {TranShk_UB} = {mNrm_1_mc:.6f}")

# TM: same calculation from _build_period_tm
# bNext = Rfree_arr[jp] * aPol_2d[j, :]  (line 348)
# where jp=1 (destination), j=0 (source)
bNext_1_tm = Rfree * aNrm_0  # Note: Rfree_arr[jp], NOT aNrm * Rfree / PermGroFac!
print(f"\n  TM: bNext = Rfree_arr[jp=1] * aPol[j=0] = {Rfree} * {aNrm_0:.6f} = {bNext_1_tm:.6f}")

# inv_pG = 1.0 / (perm_shks * PermGroFac_arr[jp])  (line 349)
# For UB state, PermShk = 1.0 (single atom)
inv_pG_1 = 1.0 / (PermShk_unemp * PermGroFac)
print(f"  TM: inv_pG = 1/({PermShk_unemp} * {PermGroFac}) = {inv_pG_1:.6f}")

# mNext = bNext * inv_pG + tran_shks  (line 350)
mNrm_1_tm = bNext_1_tm * inv_pG_1 + TranShk_UB
print(f"  TM: mNrm = {bNext_1_tm:.6f} * {inv_pG_1:.6f} + {TranShk_UB} = {mNrm_1_tm:.6f}")

print(f"\n  *** MC mNrm_1 = {mNrm_1_mc:.6f}")
print(f"  *** TM mNrm_1 = {mNrm_1_tm:.6f}")
print(f"  *** MATCH: {np.isclose(mNrm_1_mc, mNrm_1_tm)}")

# Period 1 consumption (state 1)
cFunc_1 = sol.cFunc[1]
cNrm_1 = float(cFunc_1(mNrm_1_mc, 1.0))
aNrm_1 = mNrm_1_mc - cNrm_1
print(f"\n  cFunc_1({mNrm_1_mc:.6f}) = {cNrm_1:.6f}")
print(f"  aNrm_1 = {aNrm_1:.6f}")

# Period 2: State 2 (UB period 2)
bNrm_2_mc = aNrm_1 * Rfree / (PermGroFac * PermShk_unemp)
mNrm_2_mc = bNrm_2_mc + TranShk_UB
bNext_2_tm = Rfree * aNrm_1
mNrm_2_tm = bNext_2_tm * inv_pG_1 + TranShk_UB

print(f"\n--- Period 2: State 2 (UB period 2) ---")
print(f"  MC: mNrm = {aNrm_1:.6f} * {Rfree}/{PermGroFac} + {TranShk_UB} = {mNrm_2_mc:.6f}")
print(f"  TM: mNrm = {Rfree} * {aNrm_1:.6f} / ({PermShk_unemp}*{PermGroFac}) + {TranShk_UB} = {mNrm_2_tm:.6f}")
print(f"  MATCH: {np.isclose(mNrm_2_mc, mNrm_2_tm)}")

cFunc_2 = sol.cFunc[2]
cNrm_2 = float(cFunc_2(mNrm_2_mc, 1.0))
aNrm_2 = mNrm_2_mc - cNrm_2
print(f"  cFunc_2({mNrm_2_mc:.6f}) = {cNrm_2:.6f}")
print(f"  aNrm_2 = {aNrm_2:.6f}")

# Period 3: State 3 (no benefits)
bNrm_3_mc = aNrm_2 * Rfree / (PermGroFac * PermShk_unemp)
mNrm_3_mc = bNrm_3_mc + TranShk_noBen
mNrm_3_tm = Rfree * aNrm_2 / (PermShk_unemp * PermGroFac) + TranShk_noBen

print(f"\n--- Period 3: State 3 (no benefits) ---")
print(f"  MC: mNrm = {aNrm_2:.6f} * {Rfree}/{PermGroFac} + {TranShk_noBen} = {mNrm_3_mc:.6f}")
print(f"  TM: mNrm = {mNrm_3_tm:.6f}")
print(f"  MATCH: {np.isclose(mNrm_3_mc, mNrm_3_tm)}")

# ============================================================
# Now check: what does the TM ergodic actually have for state 1?
# ============================================================
print(f"\n{'='*70}")
print(f"ERGODIC CHECK: What mNrm does the TM put in state 1?")
print(f"{'='*70}")

MCOUNT = 200
tm_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
dist_mGrid = tm_data['dist_mGrid']
M = len(dist_mGrid)

print(f"\nGrid range: [{dist_mGrid[0]:.4f}, {dist_mGrid[-1]:.4f}], M={M}")

for j in range(J):
    dist_j = ergodic[j*M:(j+1)*M]
    frac_j = np.sum(dist_j)
    if frac_j > 1e-10:
        mean_j = np.dot(dist_mGrid, dist_j) / frac_j
        # Conditional CDF
        cdf_j = np.cumsum(dist_j / frac_j)
        p25 = dist_mGrid[np.searchsorted(cdf_j, 0.25)]
        p50 = dist_mGrid[np.searchsorted(cdf_j, 0.50)]
        p75 = dist_mGrid[np.searchsorted(cdf_j, 0.75)]
        print(f"  State {j}: frac={frac_j:.6f}, mean_mNrm={mean_j:.4f}, "
              f"p25={p25:.4f}, p50={p50:.4f}, p75={p75:.4f}")

print(f"\nExpected mNrm for newly unemployed (from employed, mNrm≈1.39):")
# Use the ergodic mean mNrm for employed
dist_0 = ergodic[0*M:1*M]
frac_0 = np.sum(dist_0)
mean_mNrm_0 = np.dot(dist_mGrid, dist_0) / frac_0

# Compute cFunc at each grid point for state 0
cPol_0 = np.array([float(sol.cFunc[0](m, 1.0)) for m in dist_mGrid])
# Expected savings for state 0 agents
aPol_0 = dist_mGrid - cPol_0
aPol_0 = np.maximum(aPol_0, 0.0)

# Expected aNrm for state 0
mean_aNrm_0 = np.dot(aPol_0, dist_0) / frac_0
print(f"  E[mNrm|state 0] = {mean_mNrm_0:.4f}")
print(f"  E[aNrm|state 0] = {mean_aNrm_0:.4f}")
print(f"  E[mNrm|new UB1] = E[aNrm|0] * R/G + 0.7 = {mean_aNrm_0 * Rfree / PermGroFac + 0.7:.4f}")
print(f"  Actual E[mNrm|state 1 ergodic] = {np.dot(dist_mGrid, ergodic[1*M:2*M]) / np.sum(ergodic[1*M:2*M]):.4f}")

# ============================================================
# Check: where does the TM get state 1 mass from?
# ============================================================
print(f"\n{'='*70}")
print(f"TM TRANSITION MATRIX: Where does state 1 mass come from?")
print(f"{'='*70}")

# The TM transition matrix maps (mNrm, state) -> (mNrm, state)
# State 1 has M grid points: rows [1*M : 2*M]
# Check which source states contribute to state 1

TM = tm_data['TranMatrix']
if hasattr(TM, 'toarray'):
    TM_dense = TM.toarray()
else:
    TM_dense = np.array(TM)

# For each source state j, what fraction of mass goes to state 1?
print(f"\nMass flow INTO state 1:")
for j_src in range(J):
    # Sum of TM[state1_rows, state_j_cols] over all mNrm grid points
    flow = np.sum(TM_dense[1*M:2*M, j_src*M:(j_src+1)*M])
    print(f"  From state {j_src}: total flow = {flow:.6f}")

# The micro transition says only state 0 -> state 1 is possible
# (prob 0.0307). So state 1 mass should come only from state 0.
# But also from newborn distribution!

print(f"\nMicro transition into state 1:")
for j_src in range(J):
    print(f"  P(state {j_src} -> state 1) = {micro[j_src, 1]:.6f}")

# Check: does the newborn distribution contribute to state 1?
# In _build_period_tm, death/rebirth creates mass in state 1
# from the NewBornDist weighted by death_prb.
# NewBornDist is based on markov_ergodic_micro[1] (prob of being in state 1 at birth)
print(f"\nErgodic micro fracs (= newborn state probs):")
micro_ergodic = np.linalg.lstsq(
    np.vstack([micro.T - np.eye(J), np.ones(J)]),
    np.concatenate([np.zeros(J), [1.0]]), rcond=None)[0]
print(f"  {micro_ergodic}")
print(f"  Newborn prob of state 1 = {micro_ergodic[1]:.6f}")

# For state 1 in the ergodic, mass comes from:
# 1. Employed agents (state 0) who become unemployed: prob 0.0307
# 2. Newborn agents assigned to state 1: prob = death_rate * ergodic_micro[1]
# The newborn mNrm is based on IncShkDstn[1] (UB income), starting from
# the initial asset distribution (kNrmInitDstn).

# Check what the newborn mNrm looks like
from tm_methods import _make_newborn_dist, _solve_markov_ergodic, _effective_LivPrb
LivPrb_arr = np.asarray(BaseType.LivPrb[0][:J], dtype=np.float64)
T_age = getattr(BaseType, 'T_age', None)
LivPrb_eff = _effective_LivPrb(LivPrb_arr, T_age)
death_prb = 1.0 - LivPrb_eff[0]

IncShkDstn_list = [BaseType.IncShkDstn_base[0][j] for j in range(J)]
markov_ergodic_micro = _solve_markov_ergodic(micro)
nb_dist = _make_newborn_dist(dist_mGrid, IncShkDstn_list, markov_ergodic_micro)

print(f"\nDeath prob (effective) = {death_prb:.6f}")
print(f"Newborn distribution for state 1:")
nb_state1 = nb_dist[1*M:2*M]
nb_state1_mass = np.sum(nb_state1)
if nb_state1_mass > 1e-10:
    nb_state1_mean_mNrm = np.dot(dist_mGrid, nb_state1) / nb_state1_mass
    print(f"  Total mass = {nb_state1_mass:.6f}")
    print(f"  Mean mNrm = {nb_state1_mean_mNrm:.4f}")
else:
    print(f"  Total mass = {nb_state1_mass:.6f} (negligible)")

print(f"\nNewborn distribution for state 0:")
nb_state0 = nb_dist[0*M:1*M]
nb_state0_mass = np.sum(nb_state0)
nb_state0_mean = np.dot(dist_mGrid, nb_state0) / nb_state0_mass
print(f"  Total mass = {nb_state0_mass:.6f}")
print(f"  Mean mNrm = {nb_state0_mean:.4f}")

# ============================================================
# Verify: manually compute expected mNrm for state 1 in ergodic
# ============================================================
print(f"\n{'='*70}")
print(f"VERIFY: Expected mNrm for state 1 from two sources")
print(f"{'='*70}")

# Source 1: Surviving state 0 agents who transition to state 1
# For each mNrm grid point m in state 0:
#   aNrm = m - cFunc_0(m)
#   bNext = Rfree * aNrm
#   mNext = bNext / (PermShk * PermGroFac) + TranShk
#   weight = micro[0,1] * LivPrb * ergodic[0*M + i] * P(shock)
# Expected mNrm from this source:
surv_mass_in_state1 = 0.0
surv_mNrm_weighted = 0.0
for i in range(M):
    m = dist_mGrid[i]
    c = float(sol.cFunc[0](m, 1.0))
    a = max(m - c, 0.0)
    # Income shocks for state 1 (destination)
    d1 = IncShkDstn_list[1]
    for k in range(len(d1.pmv)):
        perm_s = d1.atoms[0][k]
        tran_s = d1.atoms[1][k]
        prob_s = d1.pmv[k]
        m_new = Rfree * a / (perm_s * PermGroFac) + tran_s
        wt = micro[0, 1] * LivPrb_eff[0] * prob_s * ergodic[0*M + i]
        surv_mass_in_state1 += wt
        surv_mNrm_weighted += wt * m_new

if surv_mass_in_state1 > 0:
    surv_mean_mNrm = surv_mNrm_weighted / surv_mass_in_state1
else:
    surv_mean_mNrm = 0

# Source 2: Newborn agents in state 1
# death_prb * newborn_dist[state1]
newborn_mass_state1 = death_prb * nb_state1_mass  # already weighted?
# Actually, newborn dist is already normalized to sum to 1 and
# weighted by ergodic micro fracs. Let me re-read _make_newborn_dist.

# The total mass in state 1 in the TM transition:
# (surviving from state 0->1) + (newborns in state 1)
# where newborn mass = death_prb * nb_dist[state1 portion]
# Actually nb_dist already represents the distribution of newborns

# Let me just check: does the ergodic make sense?
print(f"  Survivors state 0→1:")
print(f"    Mass = {surv_mass_in_state1:.6f}")
print(f"    Mean mNrm = {surv_mean_mNrm:.4f}")

# Compare with the analytical calculation
print(f"\n  Analytical from E[aNrm|state 0]:")
print(f"    = E[aNrm|0] * R/(PermShk*G) + E[TranShk|1]")
print(f"    = {mean_aNrm_0:.4f} * {Rfree}/({PermShk_unemp}*{PermGroFac}) + 0.7")
print(f"    = {mean_aNrm_0 * Rfree / (PermShk_unemp * PermGroFac) + 0.7:.4f}")

print(f"\n  TM ergodic E[mNrm|state 1] = {np.dot(dist_mGrid, ergodic[1*M:2*M]) / np.sum(ergodic[1*M:2*M]):.4f}")

newborn_mean_state1 = nb_state1_mean_mNrm if nb_state1_mass > 1e-10 else 0.0
total_state1_mass = surv_mass_in_state1 + death_prb * nb_state1_mass
contrib_surv = surv_mass_in_state1 / total_state1_mass if total_state1_mass > 0 else 0
contrib_nb = (death_prb * nb_state1_mass) / total_state1_mass if total_state1_mass > 0 else 0

print(f"\n  Composition of state 1 in ergodic:")
print(f"    Survivors (from state 0):  {contrib_surv*100:.1f}% (mean mNrm={surv_mean_mNrm:.4f})")
print(f"    Newborns:                  {contrib_nb*100:.1f}% (mean mNrm={newborn_mean_state1:.4f})")
weighted_mean = contrib_surv * surv_mean_mNrm + contrib_nb * newborn_mean_state1
print(f"    Weighted mean:             {weighted_mean:.4f}")

print("\nDone.")
