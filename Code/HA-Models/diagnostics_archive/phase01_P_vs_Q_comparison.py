"""
Phase 0–1 revalidation: TM P-measure vs Q-measure (Harmenberg neutral).

No MC — just compares TM(neutral_measure=False) vs TM(neutral_measure=True)
at mCount=40. Reference MC values from plans/20260330-0812h_tm_scaleup_status.md.

See plans/20260403-1253h_phase0-1-revalidation-plan.md for rationale and expected results.
Math: history/20260331-mathematical-derivations-harmenberg.md §11 (NM-error-decomp)
      BST ApndxHarKmenberg, Theorem 1
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
)

MCOUNT = 40

t0_global = time()

# ============================================================
# Load parameters
# ============================================================
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

rec_path_template = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 80


def make_rec_path(act_T, dur=3):
    rp = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
    for t in range(dur):
        rp[t] = rp[t] + 1
    return rp[:act_T]


def run_tm_experiments(economy, experiments, bl_data_cache, mCount, neutral_measure, label):
    """Run base + list of experiments under one measure setting. Return dict of NPVs."""
    act_T = economy.act_T
    Rfree = economy.agents[0].Rfree[0]
    disc = np.array([1.0 / Rfree**t for t in range(act_T)])
    TM_N = sum(a.AgentCount for a in economy.agents)
    rec_path = make_rec_path(act_T)

    t0 = time()
    if bl_data_cache[neutral_measure] is None:
        bl = compute_baseline_tm_data(economy, mCount=mCount,
                                      neutral_measure=neutral_measure, verbose=False)
        bl_data_cache[neutral_measure] = bl
    else:
        bl = bl_data_cache[neutral_measure]

    base = run_experiment_tm(economy, shock_type='base', mCount=mCount,
                             neutral_measure=neutral_measure, verbose=False)
    base_cons = np.array(base['AggCons']) / TM_N

    results = {}
    for name, shock_type, changes in experiments:
        eco = deepcopy(economy)
        eco.switch_shock_type(shock_type)
        eco.solve()
        r = run_experiment_tm_nonbase(eco, shock_type, rec_path, bl,
                                      mCount=mCount, neutral_measure=neutral_measure,
                                      verbose=False)
        cons = np.array(r['AggCons']) / TM_N
        te = cons - base_cons
        npv = np.sum(te * disc)
        results[name] = {'npv': npv, 'te': te, 'cons': cons}

    elapsed = time() - t0
    print(f"  [{label}] {len(experiments)} experiments in {elapsed:.1f}s")
    return results, base_cons


# ============================================================
# PHASE 0: Single highschool type, recession only
# ============================================================
print("=" * 70)
print(f"PHASE 0: 1 highschool type, recession, mCount={MCOUNT}")
print("=" * 70)

AggEco0 = AggregateDemandEconomy(**init_ADEconomy)
bt = AggFiscalType(**init_highschool)
bt.cycles = 0
bt.get_economy_data(AggEco0)

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
bt.seed = 0
AggEco0.agents = [bt]
AggEco0.solve()

phase0_experiments = [
    ('recession', 'recession', recession_changes),
]

bl_cache_0 = {False: None, True: None}
p0_P, p0_base_P = run_tm_experiments(AggEco0, phase0_experiments, bl_cache_0, MCOUNT, False, "P-measure")
p0_Q, p0_base_Q = run_tm_experiments(AggEco0, phase0_experiments, bl_cache_0, MCOUNT, True,  "Q-measure")

print(f"\n  {'Measure':<12s} {'recession NPV':>15s}")
print(f"  {'-'*12} {'-'*15}")
for lbl, res in [("P", p0_P), ("Q", p0_Q)]:
    print(f"  {lbl:<12s} {res['recession']['npv']:>15.6f}")

diff_0 = p0_Q['recession']['npv'] - p0_P['recession']['npv']
rel_0 = diff_0 / abs(p0_P['recession']['npv']) * 100
print(f"\n  Δ(Q−P) = {diff_0:+.6f}  ({rel_0:+.3f}%)")
print(f"  [Reference: P at mCount=100 was −1.3956, MC 100K×6 was −1.2851]")


# ============================================================
# PHASE 1: 3 education types, 4 recession experiments
# ============================================================
print(f"\n{'='*70}")
print(f"PHASE 1: 3 edu types, 4 experiments, mCount={MCOUNT}")
print("=" * 70)

edu_names = ['Dropout', 'HighSchool', 'College']
edu_inits = [init_dropout, init_highschool, init_college]

AggEco1 = AggregateDemandEconomy(**init_ADEconomy)
BaseTypeList = []
for init_params in edu_inits:
    b = AggFiscalType(**init_params)
    b.cycles = 0
    BaseTypeList.append(b)

for b in BaseTypeList:
    b.get_economy_data(AggEco1)

IncShkDstn_unemp1 = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseTypeList[0].IncUnemp])])
IncShkDstn_unemp_nb1 = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseTypeList[0].IncUnempNoBenefits])])

for b in BaseTypeList:
    b.IncShkDstn[0].seed = 763607780
    b.IncShkDstn[0].reset()

for ThisType in BaseTypeList:
    Emp = deepcopy(ThisType.IncShkDstn[0])
    ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncShkDstn_unemp1] * UBspell_normal + [IncShkDstn_unemp_nb1]]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn
    rec_dstn = [ThisType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
    ThisType.IncShkDstn_recession = rec_dstn
    ThisType.IncShkDstn_recessionUI = rec_dstn
    TaxCutStates = [Emp] + [IncShkDstn_unemp1] * UBspell_normal + [IncShkDstn_unemp_nb1]
    rec_tc = deepcopy(rec_dstn)
    for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates):
        rec_tc[0][i] = TaxCutStates[np.mod(i, 4)]
    ThisType.IncShkDstn_recessionTaxCut = rec_tc
    ThisType.IncShkDstn_recessionCheck = deepcopy(rec_dstn)

TypeList = []
for e in range(3):
    df = DiscFacDstns[e].atoms[0][0]
    T = deepcopy(BaseTypeList[e])
    T.AgentCount = max(int(np.floor(AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[0])), 1)
    T.DiscFac = df
    T.seed = e
    TypeList.append(T)

AggEco1.agents = TypeList
AggEco1.solve()

for e, a in enumerate(TypeList):
    print(f"  {edu_names[e]:>12s}: β={a.DiscFac:.4f}, G={a.PermGroFac[0][0]:.4f}, N={a.AgentCount}")

phase1_experiments = [
    ('recession',       'recession',       recession_changes),
    ('recessionUI',     'recessionUI',     recession_UI_changes),
    ('recessionTaxCut', 'recessionTaxCut', recession_TaxCut_changes),
    ('recessionCheck',  'recessionCheck',  recession_Check_changes),
]

bl_cache_1 = {False: None, True: None}
p1_P, p1_base_P = run_tm_experiments(AggEco1, phase1_experiments, bl_cache_1, MCOUNT, False, "P-measure")
p1_Q, p1_base_Q = run_tm_experiments(AggEco1, phase1_experiments, bl_cache_1, MCOUNT, True,  "Q-measure")

# Raw experiment NPVs
print(f"\n  RAW EXPERIMENT NPVs (treatment effect = experiment − base):")
print(f"  {'Experiment':<20s} {'TM-P':>12s} {'TM-Q':>12s} {'Δ(Q−P)':>12s} {'Δ/|P|':>8s}")
print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12} {'-'*8}")
for name, _, _ in phase1_experiments:
    npv_P = p1_P[name]['npv']
    npv_Q = p1_Q[name]['npv']
    d = npv_Q - npv_P
    r = d / abs(npv_P) * 100 if abs(npv_P) > 1e-10 else float('nan')
    print(f"  {name:<20s} {npv_P:>12.6f} {npv_Q:>12.6f} {d:>+12.6f} {r:>+7.3f}%")

# Differenced policy effects
print(f"\n  DIFFERENCED POLICY EFFECTS (vs recession):")
print(f"  {'Policy':<20s} {'TM-P':>12s} {'TM-Q':>12s} {'Δ(Q−P)':>12s} {'Δ/|P|':>8s}")
print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*12} {'-'*8}")

diff_names = {
    'recessionUI':      'UI extension',
    'recessionTaxCut':  'Tax cut',
    'recessionCheck':   'Stimulus check',
}
for name in ['recessionUI', 'recessionTaxCut', 'recessionCheck']:
    diff_P = p1_P[name]['npv'] - p1_P['recession']['npv']
    diff_Q = p1_Q[name]['npv'] - p1_Q['recession']['npv']
    d = diff_Q - diff_P
    r = d / abs(diff_P) * 100 if abs(diff_P) > 1e-10 else float('nan')
    print(f"  {diff_names[name]:<20s} {diff_P:>12.6f} {diff_Q:>12.6f} {d:>+12.6f} {r:>+7.3f}%")

# Per-period comparison for recession (first 15 periods)
print(f"\n  PER-PERIOD RECESSION TE (first 15 periods):")
print(f"  {'t':>4s} {'TM-P':>12s} {'TM-Q':>12s} {'Δ(Q−P)':>12s}")
print(f"  {'-'*4} {'-'*12} {'-'*12} {'-'*12}")
te_P = p1_P['recession']['te']
te_Q = p1_Q['recession']['te']
for t in range(min(15, len(te_P))):
    d = te_Q[t] - te_P[t]
    print(f"  {t:>4d} {te_P[t]:>12.6f} {te_Q[t]:>12.6f} {d:>+12.6f}")

# Summary
total = time() - t0_global
print(f"\n{'='*70}")
print("SUMMARY")
print("=" * 70)

max_raw_delta = max(
    abs(p1_Q[n]['npv'] - p1_P[n]['npv']) / abs(p1_P[n]['npv']) * 100
    for n, _, _ in phase1_experiments
    if abs(p1_P[n]['npv']) > 1e-10
)
max_diff_delta = max(
    abs((p1_Q[n]['npv'] - p1_Q['recession']['npv']) -
        (p1_P[n]['npv'] - p1_P['recession']['npv']))
    / abs(p1_P[n]['npv'] - p1_P['recession']['npv']) * 100
    for n in ['recessionUI', 'recessionTaxCut', 'recessionCheck']
    if abs(p1_P[n]['npv'] - p1_P['recession']['npv']) > 1e-10
)

print(f"  mCount = {MCOUNT}")
print(f"  Max |Δ(Q−P)/P| on raw experiments:       {max_raw_delta:.3f}%")
print(f"  Max |Δ(Q−P)/P| on differenced effects:   {max_diff_delta:.3f}%")
print(f"  Total wall time:                          {total:.1f}s")

if max_diff_delta < 0.5:
    print(f"\n  CONCLUSION: Q and P produce nearly identical differenced policy effects.")
    print(f"  Consistent with math-derive-harm §11.2: ε_cov cancels in differencing.")
elif max_diff_delta < 2.0:
    print(f"\n  CONCLUSION: Q shows a measurable but small improvement on diffs.")
    print(f"  ε_cov terms are slightly larger than the §11 estimate.")
else:
    print(f"\n  CONCLUSION: Q produces materially different results — investigate.")
    print(f"  The covariance terms may be non-negligible for this calibration.")
