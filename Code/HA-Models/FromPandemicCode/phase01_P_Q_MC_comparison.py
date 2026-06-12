"""
TM P-measure vs Q-measure (Harmenberg) vs large Monte Carlo comparison.

Runs all three methods on the same 3-education-type Reduced_Run economy:
  TM-P:  Transition matrix, physical measure (neutral_measure=False)
  TM-Q:  Transition matrix, Harmenberg neutral measure (neutral_measure=True)
  MC:    Monte Carlo, 200K agents x 3 seeds, TM-ergodic init + 24-period warmup

Uses a single fixed 3-quarter recession (no duration averaging) with act_T=40
periods for all methods.

Math reference: history/20260331-mathematical-derivations-harmenberg.md
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
from income_process_sst import effective_perm_shock_periods_for_t_age, effective_pLvl_growth, effective_perm_shock_variance_periods
from tm_methods import (
    compute_baseline_tm_data, run_experiment_tm, run_experiment_tm_nonbase,
)

# ============================================================
# Configuration
# ============================================================
TM_MCOUNT = 40
MC_N_TOTAL = 200_000
MC_NUM_SEEDS = 3
MC_WARMUP = 24
REC_DUR = 3
EXP_HORIZON = 40         # periods for all experiments (matches module-level T_sim)

t0_global = time()

# ============================================================
# Load parameters (Reduced_Run)
# ============================================================
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

edu_names = ['Dropout', 'HighSchool', 'College']
edu_inits = [init_dropout, init_highschool, init_college]


def make_rec_path(act_T, dur=REC_DUR):
    """Macro Markov path: dur quarters recession, then recovery, then baseline."""
    rp = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
    for t in range(dur):
        rp[t] = rp[t] + 1
    return rp[:act_T]


# ============================================================
# Build economy: 3 education types, 1 discount factor each
# ============================================================
print("=" * 76)
print("SETUP: 3 education types (Reduced_Run)")
print("=" * 76)

AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseTypeList = []
for init_params in edu_inits:
    b = AggFiscalType(**init_params)
    b.cycles = 0
    BaseTypeList.append(b)
for b in BaseTypeList:
    b.get_economy_data(AggEco)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseTypeList[0].IncUnemp])])
IncShkDstn_unemp_nb = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseTypeList[0].IncUnempNoBenefits])])

for BaseType in BaseTypeList:
    BaseType.IncShkDstn[0].seed = 763607780
    BaseType.IncShkDstn[0].reset()

for ThisType in BaseTypeList:
    Emp = deepcopy(ThisType.IncShkDstn[0])
    ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nb]]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn
    rec_dstn = [ThisType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
    ThisType.IncShkDstn_recession = rec_dstn
    ThisType.IncShkDstn_recessionUI = rec_dstn
    TaxCutStates = [Emp] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nb]
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

AggEco.agents = TypeList

t0_solve = time()
AggEco.solve()
print(f"  Solve time: {time()-t0_solve:.1f}s")
for e, a in enumerate(TypeList):
    print(f"    {edu_names[e]:>12s}: beta={a.DiscFac:.4f}, G={a.PermGroFac[0][0]:.4f}, N_base={a.AgentCount}")

# Set experiment horizon for TM experiments
AggEco.act_T = EXP_HORIZON

# ============================================================
# TM EXPERIMENTS
# ============================================================
rec_path = make_rec_path(EXP_HORIZON, dur=REC_DUR)
Rfree = TypeList[0].Rfree[0]
disc = np.array([1.0 / Rfree**t for t in range(EXP_HORIZON)])
TM_N = sum(a.AgentCount for a in TypeList)

experiments = [
    ('recession',       'recession',       recession_changes),
    ('recessionUI',     'recessionUI',     recession_UI_changes),
    ('recessionTaxCut', 'recessionTaxCut', recession_TaxCut_changes),
    ('recessionCheck',  'recessionCheck',  recession_Check_changes),
]


def run_all_tm(economy, mCount, neutral_measure, label):
    """Run base + all experiments, return dict of NPVs and TE series."""
    t0 = time()

    bl_data = compute_baseline_tm_data(economy, mCount=mCount,
                                       neutral_measure=neutral_measure, verbose=False)
    base = run_experiment_tm(economy, shock_type='base', mCount=mCount,
                             neutral_measure=neutral_measure, verbose=False)
    base_cons = np.array(base['AggCons']) / TM_N

    results = {}
    for name, shock_type, _ in experiments:
        eco = deepcopy(economy)
        eco.switch_shock_type(shock_type)
        eco.solve()
        r = run_experiment_tm_nonbase(eco, shock_type, rec_path, bl_data,
                                      mCount=mCount, neutral_measure=neutral_measure,
                                      verbose=False)
        cons = np.array(r['AggCons']) / TM_N
        te = cons - base_cons
        npv = np.sum(te * disc)
        results[name] = {'npv': npv, 'te': te}

    print(f"  [{label}] done in {time()-t0:.1f}s")
    return results, bl_data


print(f"\n{'='*76}")
print(f"TM EXPERIMENTS (mCount={TM_MCOUNT}, {EXP_HORIZON} periods)")
print("=" * 76)

tm_P, bl_P = run_all_tm(AggEco, TM_MCOUNT, neutral_measure=False, label="TM-P")
tm_Q, bl_Q = run_all_tm(AggEco, TM_MCOUNT, neutral_measure=True,  label="TM-Q")


# ============================================================
# MC EXPERIMENTS
# ============================================================
print(f"\n{'='*76}")
print(f"MC EXPERIMENTS ({MC_N_TOTAL:,} agents x {MC_NUM_SEEDS} seeds, "
      f"TM-init + {MC_WARMUP}-period warmup)")
print("=" * 76)

# Use P-measure ergodic for MC init (physical measure)
bl_for_mc_init = bl_P

base_dict_mc = deepcopy(base_dict)

mc_seed_results = {name: [] for name, _, _ in experiments}
mc_seed_base_cons = []

for seed_idx in range(MC_NUM_SEEDS):
    t0_seed = time()
    print(f"\n  --- Seed {seed_idx} ---")

    # Deep-copy the solved economy
    eco_mc = deepcopy(AggEco)

    # Set large AgentCount proportional to education shares
    for i, agent in enumerate(eco_mc.agents):
        agent.AgentCount = max(int(np.floor(MC_N_TOTAL * data_EducShares[i])), 10)
        agent.seed = (seed_idx + 1) * 1000 + i
        agent.get_economy_data(eco_mc)

    N_mc = sum(a.AgentCount for a in eco_mc.agents)
    print(f"    Total agents: {N_mc:,}")

    # Reset + initialize
    eco_mc.reset()
    for agent in eco_mc.agents:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0

    # TM-ergodic initialization (follows Simulate.py lines 249-313)
    for i, agent in enumerate(eco_mc.agents):
        bd_i = bl_for_mc_init[i]
        erg = bd_i.get('cohort_ergodic')
        if erg is None:
            erg = bd_i['ergodic']
        grid = bd_i['dist_mGrid']
        M_i = len(grid)
        J_i = agent.num_base_MrkvStates

        rng_i = np.random.RandomState(agent.seed)
        N_i = agent.AgentCount
        flat_probs = erg / np.sum(erg)

        bins = rng_i.choice(len(flat_probs), size=N_i, p=flat_probs)
        agent_j = bins // M_i
        agent_mNrm = grid[bins % M_i]

        sol_i = agent.solution[0]
        agent_aNrm = np.zeros(N_i)
        for j in range(J_i):
            mask = agent_j == j
            if np.any(mask):
                c = sol_i.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
                agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)

        L = agent.LivPrb[0][0]
        T_ag = agent.T_age
        age_probs = np.array([L**(k-1) for k in range(1, T_ag + 1)])
        age_probs /= np.sum(age_probs)
        agent_ages = rng_i.choice(T_ag, size=N_i, p=age_probs) + 1

        pLogMean = agent.pLogInitMean
        pLogStd = getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0))
        PermShkDstn_0 = agent.IncShkDstn_base[0][0]
        log_ps = np.log(PermShkDstn_0.atoms[0])
        ps_var = np.dot(PermShkDstn_0.pmv, log_ps**2) - np.dot(PermShkDstn_0.pmv, log_ps)**2
        g_lvl = effective_pLvl_growth(agent, getattr(agent, 'Urate_normal', 0.0))
        effective_emp_periods = effective_perm_shock_periods_for_t_age(
            agent_ages, agent, getattr(agent, 'Urate_normal', 0.0))
        log_pLvl = rng_i.normal(pLogMean, pLogStd, N_i)
        log_pLvl += agent_ages * np.log(g_lvl)
        log_pLvl += effective_emp_periods * (-ps_var / 2.0)
        log_pLvl += rng_i.normal(0, np.sqrt(ps_var * effective_emp_periods))

        agent.state_now['aNrm'][:] = agent_aNrm
        agent.state_now['pLvl'][:] = np.exp(log_pLvl)
        agent.shocks['Mrkv'][:] = agent_j
        if hasattr(agent, 't_age') and agent.t_age is not None:
            agent.t_age[:] = agent_ages
        agent.Cratio = 1.0
        agent.state_now['PlvlAgg'] = 1.0

    # Short warmup
    for t in range(MC_WARMUP):
        for agent in eco_mc.agents:
            agent.sim_one_period()
    print(f"    TM-init + {MC_WARMUP}-period warmup done in {time()-t0_seed:.0f}s")

    # Standard MC experiment flow (mirrors Run_FullRoutine in Simulate.py)
    eco_mc.save_state()
    eco_mc.switch_to_counterfactual_mode("base")
    eco_mc.make_idiosyncratic_shock_histories()

    # Base experiment (economy already in "base" config — CFunc matches)
    t0_base = time()
    base_r = eco_mc.run_experiment(**base_dict_mc, Full_Output=True)
    eco_mc.store_baseline(base_r['AggCons'])
    base_cons = np.array(base_r['AggCons']) / N_mc
    mc_seed_base_cons.append(base_cons)
    print(f"    Base experiment done in {time()-t0_base:.0f}s")

    # Policy experiments: switch economy shock type before each run_experiment
    # so that CFunc matches the experiment's macro Markov states.
    # run_experiment() restores agent state from saved copies, re-solves via
    # solve_if_changed(), and re-derives shock histories from fixed copies.
    for name, shock_type, changes in experiments:
        t0_exp = time()
        eco_mc.switch_shock_type(shock_type)
        dictt = base_dict_mc.copy()
        dictt.update(changes)
        dictt['EconomyMrkv_init'] = rec_path
        exp_r = eco_mc.run_experiment(**dictt, Full_Output=True)
        exp_cons = np.array(exp_r['AggCons']) / N_mc
        te = exp_cons - base_cons
        npv = np.sum(te * disc[:len(te)])
        mc_seed_results[name].append({'npv': npv, 'te': te})
        print(f"    {name}: NPV={npv:.4f} ({time()-t0_exp:.0f}s)")

    print(f"  Seed {seed_idx} total: {time()-t0_seed:.0f}s")


# ============================================================
# Aggregate MC results across seeds
# ============================================================
mc_results = {}
for name, _, _ in experiments:
    npvs = np.array([s['npv'] for s in mc_seed_results[name]])
    mc_results[name] = {'npv_mean': np.mean(npvs), 'npv_std': np.std(npvs), 'npv_all': npvs}


# ============================================================
# RESULTS
# ============================================================
print(f"\n{'='*76}")
print("RAW EXPERIMENT NPVs (treatment effect = experiment - base)")
print(f"  mCount={TM_MCOUNT}, MC N={MC_N_TOTAL:,} x {MC_NUM_SEEDS} seeds, "
      f"{EXP_HORIZON} periods, recession dur={REC_DUR}")
print("=" * 76)

header = f"  {'Experiment':<20s} {'TM-P':>10s} {'TM-Q':>10s} {'MC mean':>10s} {'MC std':>8s} {'P vs MC':>9s} {'Q vs MC':>9s}"
print(header)
print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*9} {'-'*9}")
for name, _, _ in experiments:
    npv_P = tm_P[name]['npv']
    npv_Q = tm_Q[name]['npv']
    mc_m = mc_results[name]['npv_mean']
    mc_s = mc_results[name]['npv_std']
    err_P = (npv_P - mc_m) / abs(mc_m) * 100 if abs(mc_m) > 1e-10 else float('nan')
    err_Q = (npv_Q - mc_m) / abs(mc_m) * 100 if abs(mc_m) > 1e-10 else float('nan')
    print(f"  {name:<20s} {npv_P:>10.4f} {npv_Q:>10.4f} {mc_m:>10.4f} {mc_s:>8.4f} {err_P:>+8.2f}% {err_Q:>+8.2f}%")


print(f"\n{'='*76}")
print("DIFFERENCED POLICY EFFECTS (vs recession)")
print("=" * 76)

header2 = f"  {'Policy':<20s} {'TM-P':>10s} {'TM-Q':>10s} {'MC mean':>10s} {'MC std':>8s} {'P vs MC':>9s} {'Q vs MC':>9s} {'closer':>7s}"
print(header2)
print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*9} {'-'*9} {'-'*7}")

diff_labels = {
    'recessionUI':      'UI extension',
    'recessionTaxCut':  'Tax cut',
    'recessionCheck':   'Stimulus check',
}

q_closer_count = 0
p_closer_count = 0

for name in ['recessionUI', 'recessionTaxCut', 'recessionCheck']:
    diff_P = tm_P[name]['npv'] - tm_P['recession']['npv']
    diff_Q = tm_Q[name]['npv'] - tm_Q['recession']['npv']
    mc_diffs = mc_results[name]['npv_all'] - mc_results['recession']['npv_all']
    mc_diff_m = np.mean(mc_diffs)
    mc_diff_s = np.std(mc_diffs)

    err_P = (diff_P - mc_diff_m) / abs(mc_diff_m) * 100 if abs(mc_diff_m) > 1e-10 else float('nan')
    err_Q = (diff_Q - mc_diff_m) / abs(mc_diff_m) * 100 if abs(mc_diff_m) > 1e-10 else float('nan')

    if abs(err_Q) < abs(err_P):
        closer = "Q"
        q_closer_count += 1
    else:
        closer = "P"
        p_closer_count += 1

    print(f"  {diff_labels[name]:<20s} {diff_P:>10.4f} {diff_Q:>10.4f} {mc_diff_m:>10.4f} {mc_diff_s:>8.4f} {err_P:>+8.2f}% {err_Q:>+8.2f}% {closer:>7s}")


# Per-period comparison: recession treatment effect
print(f"\n{'='*76}")
print(f"PER-PERIOD RECESSION TE (first 15 periods)")
print("=" * 76)

mc_rec_te_mean = np.mean([s['te'] for s in mc_seed_results['recession']], axis=0)
print(f"  {'t':>4s} {'TM-P':>12s} {'TM-Q':>12s} {'MC mean':>12s} {'P-MC':>12s} {'Q-MC':>12s}")
print(f"  {'-'*4} {'-'*12} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")
for t in range(min(15, EXP_HORIZON)):
    te_P = tm_P['recession']['te'][t]
    te_Q = tm_Q['recession']['te'][t]
    te_MC = mc_rec_te_mean[t]
    print(f"  {t:>4d} {te_P:>12.6f} {te_Q:>12.6f} {te_MC:>12.6f} {te_P-te_MC:>+12.6f} {te_Q-te_MC:>+12.6f}")


# ============================================================
# SUMMARY
# ============================================================
total = time() - t0_global
print(f"\n{'='*76}")
print("SUMMARY")
print("=" * 76)
print(f"  TM grid:    mCount = {TM_MCOUNT}")
print(f"  MC sample:  {MC_N_TOTAL:,} agents x {MC_NUM_SEEDS} seeds")
print(f"  Horizon:    {EXP_HORIZON} periods, recession dur = {REC_DUR}")
print(f"  Wall time:  {total:.0f}s ({total/60:.1f} min)")
print()
print(f"  Differenced effects closer to MC:  Q wins {q_closer_count}/3,  P wins {p_closer_count}/3")

if q_closer_count > p_closer_count:
    print("  -> Harmenberg neutral measure (Q) improves TM accuracy vs MC ground truth.")
elif q_closer_count == p_closer_count:
    print("  -> Mixed results; Q and P are comparably accurate relative to MC.")
else:
    print("  -> Physical measure (P) is closer to MC; Q may overcorrect or MC noise dominates.")

# Overall RMSE comparison
rms_P = np.sqrt(np.mean([(tm_P[n]['npv'] - mc_results[n]['npv_mean'])**2 for n, _, _ in experiments]))
rms_Q = np.sqrt(np.mean([(tm_Q[n]['npv'] - mc_results[n]['npv_mean'])**2 for n, _, _ in experiments]))
print(f"\n  RMS error vs MC (raw NPVs):  TM-P = {rms_P:.4f},  TM-Q = {rms_Q:.4f}")
if rms_Q < rms_P:
    print(f"    Q reduces RMS by {(1 - rms_Q/rms_P)*100:.1f}%")
else:
    print(f"    P has lower RMS by {(1 - rms_P/rms_Q)*100:.1f}%")
