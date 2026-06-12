"""
Step-by-step diagnostic for TM UI treatment effect.

Tests where we know the exact answer:
1. Micro state fractions after one micro transition (analytical)
2. Income TE from fraction change (analytical)
3. Identity CondMrkvArrays → zero TE (must be exact)
4. Grid convergence (mCount sweep)
5. MC vs TM micro fraction comparison
6. Per-period TE profile
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
    compute_baseline_tm_data,
    run_experiment_tm_nonbase,
    propagate_experiment_tm,
    build_tm_agg_fiscal,
    find_ergodic_distribution,
    compute_analytical_mean_pLvl,
    _apply_micro_transition,
    adapt_initial_distribution,
    compute_period_aggregates_tm,
    build_experiment_period_tm,
)

# ============================================================
# Setup
# ============================================================
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

N = 100000  # large N for low MC noise
MCOUNT = 50

BaseType = AggFiscalType(**init_highschool)
BaseType.cycles = 0
BaseType.AgentCount = N
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])

BaseType.IncShkDstn[0].seed = 763607780
BaseType.IncShkDstn[0].reset()

EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
BaseType.IncShkDstn = [[BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
BaseType.IncShkDstn_base = BaseType.IncShkDstn
IncShkDstn_recession = [BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
BaseType.IncShkDstn_recession = IncShkDstn_recession
BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
# BUG-023 fix: was `EmployedIncShkDstn.atoms[0][1] = EmployedIncShkDstn.atoms[0][1] * BaseType.TaxCutIncFactor`
# which mutated one PermShk atom; the intended behavior is to
# rescale every joint atom's TranShk component (atoms[1]).
# See BUGS_private/HAFiscal_BUG-023_taxcut_atoms_typo.md.
EmployedIncShkDstn.atoms = (
    np.asarray(EmployedIncShkDstn.atoms[0], dtype=np.float64),
    np.asarray(EmployedIncShkDstn.atoms[1], dtype=np.float64) * BaseType.TaxCutIncFactor,
)
TaxCutStatesIncShkDstn = [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]
IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
    IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

AggEco.agents = [BaseType]
AggEco.solve()
act_T = AggEco.act_T

J = num_base_MrkvStates
print(f"num_base_MrkvStates (J) = {J}")
print(f"UBspell_normal = {UBspell_normal}")
print(f"IncUnemp = {BaseType.IncUnemp}")
print(f"IncUnempNoBenefits = {BaseType.IncUnempNoBenefits}")

# ============================================================
# TEST 1: Extract and verify micro transition matrices
# ============================================================
print("\n" + "="*60)
print("TEST 1: Micro transition matrices")
print("="*60)

# Base config
BaseType_base = deepcopy(BaseType)
BaseType_base.update_mrkv_array("base")
cond_base = BaseType_base.CondMrkvArrays
print(f"\nBase CondMrkvArrays: {len(cond_base)} entries")
print(f"CondMrkvArrays[0] (normal micro transition):")
print(cond_base[0])

# UI config
BaseType_ui = deepcopy(BaseType)
BaseType_ui.update_mrkv_array("UI")
cond_ui = BaseType_ui.CondMrkvArrays
print(f"\nUI CondMrkvArrays: {len(cond_ui)} entries")
print(f"CondMrkvArrays[0] (macro 0, normal):")
print(cond_ui[0])
print(f"CondMrkvArrays[2] (macro 2, should be normalUI):")
print(cond_ui[2])
print(f"CondMrkvArrays[4] (macro 4, should be normalUI if ExtraUBperiods >= 2):")
print(cond_ui[4])

# Check: which CondMrkvArrays entries are UI vs normal
print("\nUI vs Normal CondMrkvArrays comparison:")
for idx in range(min(12, len(cond_ui))):
    is_same_as_normal = np.allclose(cond_ui[idx], cond_base[0])
    is_ui = not is_same_as_normal
    label = "UI" if is_ui else "normal"
    # Check if it's a recession variant
    if is_ui:
        # Check diagonal pattern (UI has self-transitions for UB states)
        if cond_ui[idx][1, 1] > 0:  # UB state 1 self-transition
            label = "UI (transition_ub=False)"
        else:
            label = "recession (different rates)"
    print(f"  [{idx}] = {label}")

# ============================================================
# TEST 2: Analytical micro state fractions
# ============================================================
print("\n" + "="*60)
print("TEST 2: Analytical micro state fractions")
print("="*60)

# Build baseline TM and get ergodic
tm_base = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_base['TranMatrix'])
dist_mGrid = tm_base['dist_mGrid']
M = len(dist_mGrid)

# Extract micro fractions from ergodic
base_fracs = np.array([np.sum(ergodic[j*M:(j+1)*M]) for j in range(J)])
print(f"\nBaseline ergodic micro fractions: {base_fracs}")
print(f"  State 0 (employed):     {base_fracs[0]:.6f}")
for j in range(1, J-1):
    print(f"  State {j} (UB period {j}):   {base_fracs[j]:.6f}")
print(f"  State {J-1} (no benefits):  {base_fracs[J-1]:.6f}")
print(f"  Sum: {np.sum(base_fracs):.6f}")

# Analytical: apply one normal micro transition
micro_normal = cond_base[0]  # normal transition (same as CondMrkvArrays[0] for base)
fracs_after_normal = micro_normal.T @ base_fracs
print(f"\nAfter 1 normal micro transition: {fracs_after_normal}")
print(f"  Change from ergodic: {fracs_after_normal - base_fracs}")

# Analytical: apply one UI micro transition (CondMrkvArrays[2] from UI config)
micro_ui = cond_ui[2]  # normalUI transition
fracs_after_ui = micro_ui.T @ base_fracs
print(f"\nAfter 1 UI micro transition: {fracs_after_ui}")
print(f"  Change from ergodic: {fracs_after_ui - base_fracs}")

# The UI treatment effect in fractions:
delta_fracs = fracs_after_ui - fracs_after_normal
print(f"\nUI - Normal fraction change: {delta_fracs}")

# ============================================================
# TEST 3: Analytical income TE from fraction change
# ============================================================
print("\n" + "="*60)
print("TEST 3: Analytical income treatment effect")
print("="*60)

# Get E[TranShk] per micro state
E_TranShk = np.zeros(J)
for j in range(J):
    d = BaseType.IncShkDstn_base[0][j]
    E_TranShk[j] = np.dot(d.pmv, d.atoms[1])
    print(f"  E[TranShk|state {j}] = {E_TranShk[j]:.6f}")

# Analytical income for normal-transitioned dist
income_normal = np.dot(fracs_after_normal, E_TranShk)
# Analytical income for UI-transitioned dist
income_ui = np.dot(fracs_after_ui, E_TranShk)
# Analytical income TE
analytical_income_TE = income_ui - income_normal
print(f"\nIncome (normalized, per-cap):")
print(f"  After normal transition: {income_normal:.8f}")
print(f"  After UI transition:     {income_ui:.8f}")
print(f"  Analytical income TE:    {analytical_income_TE:.8f}")

# Now verify this against TM output
E_pLvl = compute_analytical_mean_pLvl(BaseType)
print(f"\nE[pLvl] = {E_pLvl:.4f}")
print(f"Analytical income TE (levels, per cap): {analytical_income_TE * E_pLvl:.8f}")

# ============================================================
# TEST 4: Compare with actual TM period-0 income TE
# ============================================================
print("\n" + "="*60)
print("TEST 4: TM period-0 output vs analytical")
print("="*60)

# Baseline propagation
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
baseline_tm_data = compute_baseline_tm_data(AggEco, mCount=MCOUNT, verbose=False)
bd0 = baseline_tm_data[0]
zero_path = [0] * act_T

tm_base_res = propagate_experiment_tm(
    base_agent, bd0['ergodic'], zero_path, bd0['dist_mGrid'],
    bd0['E_pLvl'], Cratio=1.0, act_T=act_T, neutral_measure=False,
)

# UI propagation
ui_agent = deepcopy(BaseType)
ui_agent.update_mrkv_array("UI")
# Need to set up CondMrkvArrays properly via switch_shock_type
eco_ui = deepcopy(AggEco)
eco_ui.switch_shock_type("UI")
eco_ui.solve()
ui_agent = eco_ui.agents[0]

ui_path = list(np.arange(1, eco_ui.num_experiment_periods + 1) * 2) + [0] * 20
tm_ui_res = propagate_experiment_tm(
    ui_agent, bd0['ergodic'], ui_path, bd0['dist_mGrid'],
    bd0['E_pLvl'], Cratio=1.0, act_T=act_T, neutral_measure=False,
    shock_type='UI',
)

N_agent = BaseType.AgentCount
tm_base_Y0 = tm_base_res['AggIncome'][0] / N_agent
tm_ui_Y0 = tm_ui_res['AggIncome'][0] / N_agent
tm_income_TE = tm_ui_Y0 - tm_base_Y0

print(f"TM baseline AggIncome/cap [0]:  {tm_base_Y0:.8f}")
print(f"TM UI AggIncome/cap [0]:        {tm_ui_Y0:.8f}")
print(f"TM income TE [0]:               {tm_income_TE:.8f}")
print(f"Analytical income TE (levels):  {analytical_income_TE * E_pLvl:.8f}")
print(f"Ratio TM/analytical:            {tm_income_TE / (analytical_income_TE * E_pLvl):.6f}")

# ============================================================
# TEST 5: Verify micro fractions in TM distributions
# ============================================================
print("\n" + "="*60)
print("TEST 5: TM distribution micro fractions step by step")
print("="*60)

# Step through the TM manually to check each step

# Step 5a: Raw baseline ergodic
raw_ergodic = bd0['ergodic'].copy()
raw_fracs = np.array([np.sum(raw_ergodic[j*M:(j+1)*M]) for j in range(J)])
print(f"Raw ergodic fractions: {raw_fracs}")

# Step 5b: After adapt_initial_distribution (baseline path)
dist_base_adapted = adapt_initial_distribution(
    raw_ergodic, base_agent, 0, bd0['dist_mGrid'], shock_type=None)
adapted_fracs_base = np.array([np.sum(dist_base_adapted[j*M:(j+1)*M]) for j in range(J)])
print(f"After adapt (base):    {adapted_fracs_base}")
print(f"  Change:              {adapted_fracs_base - raw_fracs}")

# Step 5c: After initial micro transition (baseline)
dist_base_micro = _apply_micro_transition(
    dist_base_adapted, base_agent.CondMrkvArrays[0], M)
micro_fracs_base = np.array([np.sum(dist_base_micro[j*M:(j+1)*M]) for j in range(J)])
print(f"After micro trans (base): {micro_fracs_base}")
print(f"  Change from ergodic: {micro_fracs_base - raw_fracs}")

# Step 5d: After adapt_initial_distribution (UI path)
dist_ui_adapted = adapt_initial_distribution(
    raw_ergodic, ui_agent, ui_path[0], bd0['dist_mGrid'], shock_type='UI')
adapted_fracs_ui = np.array([np.sum(dist_ui_adapted[j*M:(j+1)*M]) for j in range(J)])
print(f"\nAfter adapt (UI):      {adapted_fracs_ui}")
print(f"  Change from ergodic: {adapted_fracs_ui - raw_fracs}")

# Step 5e: After initial micro transition (UI)
dist_ui_micro = _apply_micro_transition(
    dist_ui_adapted, ui_agent.CondMrkvArrays[ui_path[0]], M)
micro_fracs_ui = np.array([np.sum(dist_ui_micro[j*M:(j+1)*M]) for j in range(J)])
print(f"After micro trans (UI): {micro_fracs_ui}")
print(f"  Change from ergodic: {micro_fracs_ui - raw_fracs}")

# TM vs analytical fraction comparison
print(f"\n--- Fraction comparison ---")
print(f"Analytical normal fracs: {fracs_after_normal}")
print(f"TM base micro fracs:     {micro_fracs_base}")
print(f"Diff:                    {micro_fracs_base - fracs_after_normal}")

print(f"\nAnalytical UI fracs:     {fracs_after_ui}")
print(f"TM UI micro fracs:       {micro_fracs_ui}")
print(f"Diff:                    {micro_fracs_ui - fracs_after_ui}")

# ============================================================
# TEST 6: Income from TM distributions vs analytical
# ============================================================
print("\n" + "="*60)
print("TEST 6: Income from TM distributions (manual computation)")
print("="*60)

# For the baseline at period 0, income = dot(micro_fracs_base, E_TranShk_base)
# But we need E_TranShk for the correct IncShkDstn
E_TranShk_base_p0 = np.zeros(J)
for j in range(J):
    # Baseline uses IncShkDstn_base[0][j] at macro_t=0
    d = base_agent.IncShkDstn[0][j]
    E_TranShk_base_p0[j] = np.dot(d.pmv, d.atoms[1])
print(f"E[TranShk] base (macro 0): {E_TranShk_base_p0}")

E_TranShk_ui_p0 = np.zeros(J)
for j in range(J):
    # UI uses IncShkDstn[0][macro_t * J + j] where macro_t = ui_path[0] = 2
    macro_t = ui_path[0]
    d = ui_agent.IncShkDstn[0][macro_t * J + j]
    E_TranShk_ui_p0[j] = np.dot(d.pmv, d.atoms[1])
print(f"E[TranShk] UI (macro {ui_path[0]}):  {E_TranShk_ui_p0}")
print(f"Are they identical? {np.allclose(E_TranShk_base_p0, E_TranShk_ui_p0)}")

# Manual income calculation
manual_income_base = np.dot(micro_fracs_base, E_TranShk_base_p0)
manual_income_ui = np.dot(micro_fracs_ui, E_TranShk_ui_p0)
manual_income_TE = manual_income_ui - manual_income_base
print(f"\nManual income (nrm):")
print(f"  Base: {manual_income_base:.8f}")
print(f"  UI:   {manual_income_ui:.8f}")
print(f"  TE:   {manual_income_TE:.8f}")
print(f"Manual income TE (levels/cap): {manual_income_TE * E_pLvl:.8f}")
print(f"TM income TE (levels/cap):     {tm_income_TE:.8f}")
print(f"Ratio:                         {tm_income_TE / (manual_income_TE * E_pLvl):.6f}")

# ============================================================
# TEST 7: MC micro state fractions at period 0 (via run_experiment)
# ============================================================
print("\n" + "="*60)
print("TEST 7: MC micro state fractions at period 0")
print("="*60)

base_dict_agg = deepcopy(base_dict)

def setup_mc_economy(seed=0):
    """Set up an MC economy through burn-in, return ready for experiments."""
    eco = deepcopy(AggEco)
    for a in eco.agents:
        a.AgentCount = N
        a.seed = seed * 1000
    for a in eco.agents:
        a.get_economy_data(eco)
    eco.solve()
    eco.reset()
    for a in eco.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    eco.make_history()
    eco.save_state()
    eco.switch_to_counterfactual_mode("base")
    eco.act_T = act_T
    for a in eco.agents:
        a.T_sim = act_T
        a.EconomyMrkvNow_hist = [0] * act_T
    eco.make_idiosyncratic_shock_histories()
    return eco

def run_mc_and_extract(eco_base, shock_type, changes_dict, path):
    """Run run_experiment and extract period-0 micro fracs, TranShk, income."""
    eco = deepcopy(eco_base)
    d = base_dict_agg.copy()
    d.update(changes_dict)
    d['EconomyMrkv_init'] = path
    # run_experiment calls update_mrkv_array, solve, initialize_sim,
    # sets EconomyMrkvNow_hist, calls hit_with_recession_shock, then simulates
    result = eco.run_experiment(**d, Full_Output=True)

    # Extract period-0 data from shock_history (set by hit_with_recession_shock)
    agent = eco.agents[0]
    mrkv_0 = agent.shock_history['Mrkv'][0]
    micro_0 = mrkv_0 % J
    fracs = np.array([np.mean(micro_0 == j) for j in range(J)])
    transhk_0 = agent.shock_history['TranShk'][0]
    mean_transhk_0 = np.mean(transhk_0)
    # Per-capita AggIncome from run_experiment
    N_act = sum(a.AgentCount for a in eco.agents)
    agg_income_0 = result['AggIncome'][0] / N_act
    agg_cons_0 = result['AggCons'][0] / N_act
    return fracs, mean_transhk_0, agg_income_0, agg_cons_0

NUM_MC_SEEDS = 5
print(f"\nRunning MC with {NUM_MC_SEEDS} seeds, N={N}...")

# MC baseline
mc_base_data = []
for s in range(NUM_MC_SEEDS):
    eco = setup_mc_economy(seed=s)
    eco.store_baseline(eco.run_experiment(**base_dict_agg, Full_Output=True)['AggCons'])
    f, ts, yi, ci = run_mc_and_extract(eco, 'base', base_dict, [0]*act_T)
    mc_base_data.append({'fracs': f, 'transhk': ts, 'income': yi, 'cons': ci})
    print(f"  Base seed {s}: fracs={f}, E[TranShk]={ts:.6f}")

mc_base_fracs = np.mean([d['fracs'] for d in mc_base_data], axis=0)
mc_base_income = np.mean([d['income'] for d in mc_base_data])
mc_base_transhk = np.mean([d['transhk'] for d in mc_base_data])
mc_base_cons = np.mean([d['cons'] for d in mc_base_data])

# MC UI — uses proper EconomyMrkv_init path
# Must switch_shock_type + solve on economy before run_experiment
mc_ui_data = []
for s in range(NUM_MC_SEEDS):
    eco = setup_mc_economy(seed=s)
    eco.store_baseline(eco.run_experiment(**base_dict_agg, Full_Output=True)['AggCons'])
    eco_ui_mc = deepcopy(eco)
    eco_ui_mc.switch_shock_type('UI')
    eco_ui_mc.solve()
    f, ts, yi, ci = run_mc_and_extract(eco_ui_mc, 'UI', UI_changes, ui_path)
    mc_ui_data.append({'fracs': f, 'transhk': ts, 'income': yi, 'cons': ci})
    print(f"  UI seed {s}:   fracs={f}, E[TranShk]={ts:.6f}")

mc_ui_fracs = np.mean([d['fracs'] for d in mc_ui_data], axis=0)
mc_ui_income = np.mean([d['income'] for d in mc_ui_data])
mc_ui_transhk = np.mean([d['transhk'] for d in mc_ui_data])
mc_ui_cons = np.mean([d['cons'] for d in mc_ui_data])

print(f"\n--- MC micro fractions (period 0, {NUM_MC_SEEDS}-seed mean) ---")
print(f"  Base: {mc_base_fracs}")
print(f"  UI:   {mc_ui_fracs}")
print(f"  Diff: {mc_ui_fracs - mc_base_fracs}")

print(f"\n--- MC vs TM micro fraction comparison ---")
print(f"  MC base fracs:    {mc_base_fracs}")
print(f"  TM base fracs:    {micro_fracs_base}")
print(f"  Diff (TM-MC):     {micro_fracs_base - mc_base_fracs}")
print(f"\n  MC UI fracs:      {mc_ui_fracs}")
print(f"  TM UI fracs:      {micro_fracs_ui}")
print(f"  Diff (TM-MC):     {micro_fracs_ui - mc_ui_fracs}")
print(f"\n  Analytical UI:    {fracs_after_ui}")

print(f"\n--- E[TranShk] at period 0 ---")
print(f"  MC base: {mc_base_transhk:.8f}")
print(f"  MC UI:   {mc_ui_transhk:.8f}")

print(f"\n--- Income and Consumption TE (per-capita, levels) ---")
mc_income_TE = mc_ui_income - mc_base_income
mc_cons_TE = mc_ui_cons - mc_base_cons
print(f"  MC income TE:     {mc_income_TE:.8f}")
print(f"  TM income TE:     {tm_income_TE:.8f}")
print(f"  Analytical:       {analytical_income_TE * E_pLvl:.8f}")
print(f"  MC cons TE:       {mc_cons_TE:.8f}")
tm_cons_TE = (tm_ui_res['AggCons'][0] - tm_base_res['AggCons'][0]) / N_agent
print(f"  TM cons TE:       {tm_cons_TE:.8f}")

# ============================================================
# TEST 8: CondMrkvArrays indexing verification
# ============================================================
print("\n" + "="*60)
print("TEST 8: CondMrkvArrays indexing — TM vs MC alignment")
print("="*60)

print(f"\nUI macro path (first 10): {ui_path[:10]}")
print(f"\nIn MC hit_with_recession_shock, t=0:")
print(f"  MacroMrkvNow = EconomyMrkvNow_hist[0] = {ui_path[0]}")
print(f"  get_micro_markv_states_guts uses CondMrkvArrays[{ui_path[0]}]")
print(f"  This is: {'UI (normalUI)' if not np.allclose(cond_ui[ui_path[0]], cond_base[0]) else 'normal'}")

print(f"\nIn TM propagate_experiment_tm:")
print(f"  Initial micro trans uses CondMrkvArrays[{ui_path[0]}]")
print(f"  build_experiment_period_tm at t=0: macro_t={ui_path[0]}, macro_next={ui_path[1]}")
print(f"  micro_trans = CondMrkvArrays[macro_next={ui_path[1]}]")
print(f"  This is: {'UI (normalUI)' if not np.allclose(cond_ui[ui_path[1]], cond_base[0]) else 'normal'}")

print(f"\nIn MC hit_with_recession_shock, t=1:")
print(f"  MacroMrkvNow = EconomyMrkvNow_hist[1] = {ui_path[1]}")
print(f"  get_micro_markv_states_guts uses CondMrkvArrays[{ui_path[1]}]")

print(f"\n→ For t=0 to t=1 transition:")
print(f"  MC uses CondMrkvArrays[{ui_path[1]}] at t=1 (current period)")
print(f"  TM uses CondMrkvArrays[{ui_path[1]}] as macro_next in t=0 TM")
print(f"  These MATCH: both use CondMrkvArrays[{ui_path[1]}] for the micro transition")

# ============================================================
# TEST 9: Grid convergence
# ============================================================
print("\n" + "="*60)
print("TEST 9: Grid convergence (mCount sweep)")
print("="*60)

for mcount in [25, 50, 100, 200]:
    bl_data = compute_baseline_tm_data(
        AggEco, mCount=mcount, verbose=False)
    bd = bl_data[0]

    # Baseline
    base_a = deepcopy(BaseType)
    base_a.update_mrkv_array("base")
    base_a.solve()
    r_base = propagate_experiment_tm(
        base_a, bd['ergodic'], [0]*act_T, bd['dist_mGrid'],
        bd['E_pLvl'], Cratio=1.0, act_T=act_T)

    # UI
    eco_u = deepcopy(AggEco)
    eco_u.switch_shock_type("UI")
    eco_u.solve()
    r_ui = propagate_experiment_tm(
        eco_u.agents[0], bd['ergodic'], ui_path, bd['dist_mGrid'],
        bd['E_pLvl'], Cratio=1.0, act_T=act_T,
        shock_type='UI')

    te_y = (r_ui['AggIncome'][0] - r_base['AggIncome'][0]) / N
    te_c = (r_ui['AggCons'][0] - r_base['AggCons'][0]) / N
    print(f"  mCount={mcount:4d}: Income TE={te_y:.6f}, Cons TE={te_c:.6f}")

# ============================================================
# TEST 10: Per-period TE profile (first 15 periods)
# ============================================================
print("\n" + "="*60)
print("TEST 10: Per-period treatment effect profile")
print("="*60)

# Use the already-computed TM results
print(f"{'t':>3s}  {'TM_Income_TE':>14s}  {'TM_Cons_TE':>14s}")
for t in range(min(15, act_T)):
    te_y = (tm_ui_res['AggIncome'][t] - tm_base_res['AggIncome'][t]) / N
    te_c = (tm_ui_res['AggCons'][t] - tm_base_res['AggCons'][t]) / N
    print(f"{t:3d}  {te_y:14.6f}  {te_c:14.6f}")

print("\nDone.")
