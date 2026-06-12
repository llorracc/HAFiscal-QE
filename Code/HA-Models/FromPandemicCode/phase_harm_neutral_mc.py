"""
Harmenberg-neutral MC vs standard MC comparison.

Under the Harmenberg neutral measure Q, the employed IncShkDstn probabilities
are reweighted by psi/E[psi], so high-permanent-shock states are upweighted.
This concentrates the m-distribution, reducing MC sampling variance.

Aggregation uses a population-level scalar pLvl_factor(t) from the TM code:
    C(t) = sum_types E_pLvl * pLvl_factor(t) * sum_agents f_Q(m_i(t))
where f_Q = cLvl_splurge / pLvl_Q is the normalized consumption function.

Math: E_P[p * f(m)] = E_P[p] * E_Q[f(m)]   (Harmenberg 2021, Theorem 1)
      pLvl_factor(t) = E_P[p_t] / E_P[p_ss]  (tm_methods pLvl-recurrence)
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
from tm_methods import compute_baseline_tm_data, _effective_LivPrb

# ============================================================
# Configuration
# ============================================================
MC_N_TOTAL = 200_000
MC_NUM_SEEDS = 3
REC_DUR = 3
EXP_HORIZON = 40

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

Splurge = base_dict['Splurge']
edu_names = ['Dropout', 'HighSchool', 'College']
edu_inits = [init_dropout, init_highschool, init_college]


def make_rec_path(act_T, dur=REC_DUR):
    rp = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
    for t in range(dur):
        rp[t] = rp[t] + 1
    return rp[:act_T]


def make_q_measure_dstn(dstn):
    """Reweight a joint (PermShk, TranShk) DiscreteDistribution by psi/E[psi].

    See math-derive-harm §2 (Q-reweight-emp).
    """
    perm_atoms = dstn.atoms[0]
    E_perm = np.dot(dstn.pmv, perm_atoms)
    Q_pmv = dstn.pmv * perm_atoms / E_perm
    Q_pmv = Q_pmv / np.sum(Q_pmv)
    return DiscreteDistribution(Q_pmv, dstn.atoms, seed=dstn.seed)


def _set_q_incshkdstn(agents):
    """Replace employed IncShkDstn with Q-reweighted version for all agents.

    See math-derive-harm §17.1.  Must be called before warmup AND after
    switch_to_counterfactual_mode (which resets IncShkDstn).
    """
    for agent in agents:
        agent.IncShkDstn = deepcopy(agent.IncShkDstn_base)
        agent.IncShkDstn[0][0] = make_q_measure_dstn(agent.IncShkDstn[0][0])


# ============================================================
# Build economy
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
AggEco.solve()
AggEco.act_T = EXP_HORIZON

bl_P = compute_baseline_tm_data(AggEco, mCount=50, neutral_measure=False, verbose=False)
bl_Q = compute_baseline_tm_data(AggEco, mCount=50, neutral_measure=True, verbose=False)

print(f"  Solve + TM baseline: {time()-t0_global:.0f}s")
for e, a in enumerate(TypeList):
    print(f"    {edu_names[e]:>12s}: beta={a.DiscFac:.4f}, G={a.PermGroFac[0][0]:.6f}")

# ============================================================
# Experiments & shared config
# ============================================================
experiments = [
    ('recession',       'recession',       recession_changes),
    ('recessionUI',     'recessionUI',     recession_UI_changes),
    ('recessionTaxCut', 'recessionTaxCut', recession_TaxCut_changes),
    ('recessionCheck',  'recessionCheck',  recession_Check_changes),
]
rec_path = make_rec_path(EXP_HORIZON, dur=REC_DUR)
base_dict_mc = deepcopy(base_dict)
Rfree = TypeList[0].Rfree[0]
disc = np.array([1.0 / Rfree**t for t in range(EXP_HORIZON)])


# ============================================================
# Scalar pLvl_factor aggregation (matches TM math)
# ============================================================
def compute_scalar_AggCons(eco, bl_P_data):
    """Compute AggCons using population-level pLvl_factor per type.

    See math-derive-harm §15 (Q-MC-agg-multi):
        C(t) = sum_types E_pLvl * F(t) * sum_agents f_Q(m_i(t))
    where f_Q = cLvl_splurge / pLvl_Q is the normalized consumption.

    pLvl_factor F(t) evolves via math-derive (pLvl-recurrence):
        F' = (1-delta)*g_rec*F + [1-(1-delta)*g_base]

    The scalar (population-level) E_P[p] avoids the correlation bias
    of agent-specific shadow pLvl; see math-derive-harm §16 (shadow-bias).
    """
    T = eco.act_T
    C_scalar = np.zeros(T)

    for type_idx, agent in enumerate(eco.agents):
        bd = bl_P_data[type_idx]
        E_pLvl = bd['E_pLvl']
        G_perm = agent.PermGroFac[0][0]
        u_ergodic = bd['u_ergodic']
        g_base_pLvl = (1.0 - u_ergodic) * G_perm + u_ergodic

        J_micro = agent.num_base_MrkvStates
        LivPrb_arr = np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64)
        T_age = getattr(agent, 'T_age', None)
        L_eff = _effective_LivPrb(LivPrb_arr, T_age)
        delta_eff = 1.0 - np.mean(L_eff)

        cLvl_splurge = agent.history['cLvl_splurge'][:T]
        pLvl_Q = agent.history['pLvl'][:T]
        f_Q = cLvl_splurge / pLvl_Q
        nrm_sum = np.sum(f_Q, axis=1)

        micro_mrkv = agent.history['MicroMrkvNow'][:T]

        F = 1.0
        for t in range(T):
            C_scalar[t] += E_pLvl * F * nrm_sum[t]
            u_t = 1.0 - np.mean(micro_mrkv[t] == 0)
            g_rec_t = (1.0 - u_t) * G_perm + u_t
            F = (1.0 - delta_eff) * g_rec_t * F + (1.0 - (1.0 - delta_eff) * g_base_pLvl)

    return C_scalar


# ============================================================
# MC runner
# ============================================================
def run_mc_seed(economy, bl_init, N_total, seed_idx, neutral_measure=False, label="MC", bl_P_data=None):
    t0_seed = time()
    eco_mc = deepcopy(economy)

    for i, agent in enumerate(eco_mc.agents):
        agent.AgentCount = max(int(np.floor(N_total * data_EducShares[i])), 10)
        agent.seed = (seed_idx + 1) * 1000 + i
        agent.get_economy_data(eco_mc)

    N_mc = sum(a.AgentCount for a in eco_mc.agents)

    eco_mc.reset()
    for agent in eco_mc.agents:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0

    for i, agent in enumerate(eco_mc.agents):
        bd_i = bl_init[i]
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

    # For Q-MC: set Q-IncShkDstn before warmup
    if neutral_measure:
        _set_q_incshkdstn(eco_mc.agents)

    for t in range(24):
        for agent in eco_mc.agents:
            agent.sim_one_period()

    eco_mc.save_state()
    eco_mc.switch_to_counterfactual_mode("base")

    if neutral_measure:
        _set_q_incshkdstn(eco_mc.agents)

    eco_mc.make_idiosyncratic_shock_histories()

    # Base experiment
    base_r = eco_mc.run_experiment(**base_dict_mc, Full_Output=True)
    eco_mc.store_baseline(base_r['AggCons'])

    if neutral_measure:
        base_AggCons_scalar = compute_scalar_AggCons(eco_mc, bl_P_data)

    results = {}
    for name, shock_type, changes in experiments:
        eco_mc.switch_shock_type(shock_type)
        dictt = base_dict_mc.copy()
        dictt.update(changes)
        dictt['EconomyMrkv_init'] = rec_path
        exp_r = eco_mc.run_experiment(**dictt, Full_Output=True)

        if neutral_measure:
            exp_AggCons_scalar = compute_scalar_AggCons(eco_mc, bl_P_data)
            te_scalar = (exp_AggCons_scalar - base_AggCons_scalar) / N_mc
            npv_scalar = np.sum(te_scalar * disc[:len(te_scalar)])
            results[name] = {'npv': npv_scalar, 'te': te_scalar}
        else:
            base_cons = np.array(base_r['AggCons']) / N_mc
            exp_cons = np.array(exp_r['AggCons']) / N_mc
            te = exp_cons - base_cons
            npv = np.sum(te * disc[:len(te)])
            results[name] = {'npv': npv, 'te': te}

    results['_meta'] = {'N_mc': N_mc, 'time': time() - t0_seed}
    print(f"    [{label} seed {seed_idx}] {time()-t0_seed:.0f}s (N={N_mc:,})")
    return results


# ============================================================
# Run P-MC and Q-MC
# ============================================================
print(f"\n{'='*76}")
print(f"MC EXPERIMENTS: {MC_N_TOTAL:,} agents x {MC_NUM_SEEDS} seeds")
print("=" * 76)

P_seeds = []
Q_seeds = []

for seed_idx in range(MC_NUM_SEEDS):
    print(f"\n  --- Seed {seed_idx} ---")
    P_seeds.append(run_mc_seed(AggEco, bl_P, MC_N_TOTAL, seed_idx,
                               neutral_measure=False, label="P-MC"))
    Q_seeds.append(run_mc_seed(AggEco, bl_Q, MC_N_TOTAL, seed_idx,
                               neutral_measure=True, label="Q-MC",
                               bl_P_data=bl_P))


# ============================================================
# Results tables
# ============================================================
def se(arr):
    return np.std(arr) / np.sqrt(len(arr)) if len(arr) > 1 else float('nan')


print(f"\n{'='*76}")
print("RAW EXPERIMENT NPVs (treatment effect = experiment - base)")
print("=" * 76)

header = f"  {'Experiment':<20s} {'P-MC mean':>10s} {'P-MC SE':>9s} {'Q-MC mean':>10s} {'Q-MC SE':>9s} {'Q/P SE':>7s}"
print(header)
print(f"  {'-'*20} {'-'*10} {'-'*9} {'-'*10} {'-'*9} {'-'*7}")

for name, _, _ in experiments:
    P_npvs = np.array([s[name]['npv'] for s in P_seeds])
    Q_npvs = np.array([s[name]['npv'] for s in Q_seeds])
    P_m, P_s = np.mean(P_npvs), se(P_npvs)
    Q_m, Q_s = np.mean(Q_npvs), se(Q_npvs)
    ratio = Q_s / P_s if P_s > 0 else float('nan')
    print(f"  {name:<20s} {P_m:>10.4f} {P_s:>9.4f} {Q_m:>10.4f} {Q_s:>9.4f} {ratio:>7.2f}")


print(f"\n{'='*76}")
print("DIFFERENCED POLICY EFFECTS (vs recession)")
print("=" * 76)
print(header)
print(f"  {'-'*20} {'-'*10} {'-'*9} {'-'*10} {'-'*9} {'-'*7}")

diff_labels = {
    'recessionUI': 'UI extension',
    'recessionTaxCut': 'Tax cut',
    'recessionCheck': 'Stimulus check',
}
for name in ['recessionUI', 'recessionTaxCut', 'recessionCheck']:
    P_d = np.array([s[name]['npv'] - s['recession']['npv'] for s in P_seeds])
    Q_d = np.array([s[name]['npv'] - s['recession']['npv'] for s in Q_seeds])
    P_m, P_s = np.mean(P_d), se(P_d)
    Q_m, Q_s = np.mean(Q_d), se(Q_d)
    ratio = Q_s / P_s if P_s > 0 else float('nan')
    print(f"  {diff_labels[name]:<20s} {P_m:>10.4f} {P_s:>9.4f} {Q_m:>10.4f} {Q_s:>9.4f} {ratio:>7.2f}")

# Relative SE
print(f"\n{'='*76}")
print("RELATIVE STANDARD ERRORS (SE / |mean|)")
print("=" * 76)
print(f"  {'Experiment':<20s} {'P-MC relSE':>10s} {'Q-MC relSE':>10s}")
print(f"  {'-'*20} {'-'*10} {'-'*10}")
for name, _, _ in experiments:
    P_npvs = np.array([s[name]['npv'] for s in P_seeds])
    Q_npvs = np.array([s[name]['npv'] for s in Q_seeds])
    P_rel = se(P_npvs) / abs(np.mean(P_npvs)) * 100 if abs(np.mean(P_npvs)) > 0 else float('nan')
    Q_rel = se(Q_npvs) / abs(np.mean(Q_npvs)) * 100 if abs(np.mean(Q_npvs)) > 0 else float('nan')
    print(f"  {name:<20s} {P_rel:>9.2f}% {Q_rel:>9.2f}%")


# ============================================================
# Summary
# ============================================================
total = time() - t0_global
print(f"\n{'='*76}")
print("SUMMARY")
print("=" * 76)
print(f"  MC sample:  {MC_N_TOTAL:,} agents x {MC_NUM_SEEDS} seeds")
print(f"  Horizon:    {EXP_HORIZON} periods, recession dur = {REC_DUR}")
print(f"  Wall time:  {total:.0f}s ({total/60:.1f} min)")
print()
if MC_NUM_SEEDS > 1:
    print("  Variance reduction (Q-MC SE / P-MC SE, lower is better):")
    for name, _, _ in experiments:
        P_npvs = np.array([s[name]['npv'] for s in P_seeds])
        Q_npvs = np.array([s[name]['npv'] for s in Q_seeds])
        ratio = se(Q_npvs) / se(P_npvs) if se(P_npvs) > 0 else float('nan')
        print(f"    {name:<20s}:  {ratio:.3f}")
