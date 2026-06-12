"""
Diagnostic: isolate pLvl variance effects on TM-MC discrepancy.

Four configurations varying PermShkStd and pLogInitStd between
"near-zero" and calibrated values. For each, compare TM vs MC
recession treatment-effect NPV and per-period decomposition.

Math references: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")
  (error-decomp): V^TM - V^true = eps_grid + eps_level + eps_dyn + eps_cov_ss + eps_cov_trans
  (TM-agg):       C_t = N * E[p] * F_t * c_nrm_t
  (MC-agg):       C_t = sum_i p_i * c(m_i, z_i)
  (p-transition): p_{t+1} = G*psi*p_t (employed) or p_t (unemployed)
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
from HARK.distributions import DiscreteDistribution, Lognormal
from Parameters import return_parameters
from income_process_sst import effective_perm_shock_periods_for_t_age, effective_pLvl_growth, effective_perm_shock_variance_periods
from tm_methods import (
    compute_baseline_tm_data, run_experiment_tm, run_experiment_tm_nonbase,
    compute_analytical_mean_pLvl,
)

NEAR_ZERO = 0.001
N_MC = 100000
N_SEEDS = 3

t0_global = time()

# ============================================================
# Load base parameters
# ============================================================
[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

DiscFac = DiscFacDstns[1].atoms[0][0]

# Calibrated values for reference
PERMSHKSTD_CALIB = init_highschool['PermShkStd']  # [sqrt(0.003)]
PLOGINITSD_CALIB = init_highschool['pLogInitStd']  # 0.42


def build_economy(perm_shk_std, plog_init_std):
    """Build a fresh economy with specified shock/init parameters."""
    init_hs = deepcopy(init_highschool)
    init_hs['PermShkStd'] = [perm_shk_std]
    init_hs['pLogInitStd'] = plog_init_std

    eco = AggregateDemandEconomy(**init_ADEconomy)
    bt = AggFiscalType(**init_hs)
    bt.cycles = 0
    bt.get_economy_data(eco)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([bt.IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([bt.IncUnempNoBenefits])])
    bt.IncShkDstn = [[bt.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
    bt.IncShkDstn_base = bt.IncShkDstn
    bt.IncShkDstn_recession = [bt.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]

    agent = deepcopy(bt)
    agent.DiscFac = DiscFac
    agent.seed = 0
    eco.agents = [agent]
    eco.solve()
    return eco


def run_tm_recession(eco):
    """Run TM base + recession, return treatment-effect per period and NPV."""
    act_T = eco.act_T
    agent = eco.agents[0]
    Rfree = agent.Rfree[0]
    disc = np.array([1.0 / Rfree**t for t in range(act_T)])
    TM_N = agent.AgentCount

    rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
    for t in range(3):
        rec_path[t] = rec_path[t] + 1
    rec_path = rec_path[:act_T]

    tm_base = run_experiment_tm(eco, shock_type='base', mCount=100, verbose=False)
    bl_data = compute_baseline_tm_data(eco, mCount=100, verbose=False)

    eco2 = deepcopy(eco)
    eco2.switch_shock_type("recession")
    eco2.solve()
    tm_rec = run_experiment_tm_nonbase(eco2, "recession", rec_path, bl_data, mCount=100, verbose=False)

    tm_base_cons = np.array(tm_base['AggCons']) / TM_N
    tm_rec_cons = np.array(tm_rec['AggCons']) / TM_N
    te = tm_rec_cons - tm_base_cons
    npv = np.sum(te * disc)
    E_pLvl = bl_data[0]['E_pLvl']
    u_erg = bl_data[0]['u_ergodic']
    return npv, te, E_pLvl, u_erg, disc


def init_mc_from_ergodic(eco_mc, bl_data_init, N_MC_i, seed):
    """Initialize MC agents from TM ergodic distribution (mirrors phase0 script)."""
    for i, agent in enumerate(eco_mc.agents):
        agent.AgentCount = N_MC_i
        agent.seed = seed * 1000 + i
        agent.get_economy_data(eco_mc)

    eco_mc.solve()
    eco_mc.reset()
    for a in eco_mc.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0

    for i, agent in enumerate(eco_mc.agents):
        bd_i = bl_data_init[i]
        erg = bd_i.get('cohort_ergodic', bd_i['ergodic'])
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
        log_pLvl = rng_i.normal(pLogMean, max(pLogStd, 1e-12), N_i)
        log_pLvl += agent_ages * np.log(g_lvl)
        log_pLvl += effective_emp_periods * (-ps_var / 2.0)
        log_pLvl += rng_i.normal(0, np.sqrt(max(ps_var, 1e-24) * effective_emp_periods))
        agent_pLvl = np.exp(log_pLvl)

        agent.state_now['aNrm'][:] = agent_aNrm
        agent.state_now['pLvl'][:] = agent_pLvl
        agent.shocks['Mrkv'][:] = agent_j
        if hasattr(agent, 't_age') and agent.t_age is not None:
            agent.t_age[:] = agent_ages
        agent.Cratio = 1.0
        agent.state_now['PlvlAgg'] = 1.0

    for t in range(24):
        for agent in eco_mc.agents:
            agent.sim_one_period()


def run_mc_recession(eco_template, bl_data_init, N_MC_i, num_seeds):
    """Run MC recession with ergodic init, return per-seed NPVs and per-period TEs."""
    act_T = eco_template.act_T
    agent0 = eco_template.agents[0]
    Rfree = agent0.Rfree[0]
    disc = np.array([1.0 / Rfree**t for t in range(act_T)])
    rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
    for t in range(3):
        rec_path[t] = rec_path[t] + 1
    rec_path = rec_path[:act_T]

    base_dict_agg = deepcopy(base_dict)
    base_dict_agg['Splurge'] = agent0.Splurge

    mc_npvs = []
    mc_te_all = []
    mc_pLvl_means = []

    for seed in range(num_seeds):
        eco_mc = deepcopy(eco_template)
        init_mc_from_ergodic(eco_mc, bl_data_init, N_MC_i, seed)

        eco_mc.save_state()
        eco_mc.switch_to_counterfactual_mode("base")
        eco_mc.act_T = act_T
        for a in eco_mc.agents:
            a.T_sim = act_T
            a.EconomyMrkvNow_hist = [0] * act_T
        eco_mc.make_idiosyncratic_shock_histories()

        mc_base = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
        N_actual = sum(a.AgentCount for a in eco_mc.agents)
        T_out = min(len(mc_base['AggCons']), act_T)
        mc_base_cons = np.array(mc_base['AggCons'][:T_out]) / N_actual
        eco_mc.store_baseline(mc_base['AggCons'])

        eco_rec = deepcopy(eco_mc)
        eco_rec.switch_shock_type("recession")
        eco_rec.solve()
        rec_dict = base_dict_agg.copy()
        rec_dict.update(recession_changes)
        rec_dict['EconomyMrkv_init'] = rec_path
        mc_rec = eco_rec.run_experiment(**rec_dict, Full_Output=True)
        mc_rec_cons = np.array(mc_rec['AggCons'][:T_out]) / N_actual

        # Per-period E[pLvl] from MC recession
        mc_pLvl_rec = np.mean(mc_rec['pLvl_all'][:T_out], axis=1)
        mc_pLvl_base = np.mean(mc_base['pLvl_all'][:T_out], axis=1)

        te = mc_rec_cons - mc_base_cons
        npv = np.sum(te * disc[:T_out])
        mc_npvs.append(npv)
        mc_te_all.append(te)
        mc_pLvl_means.append({'rec': mc_pLvl_rec, 'base': mc_pLvl_base})
        print(f"      seed {seed}: NPV={npv:.6f}")

    return np.array(mc_npvs), np.array(mc_te_all), mc_pLvl_means


# ============================================================
# Configurations
# ============================================================
configs = [
    ('A: both_small',    NEAR_ZERO,         NEAR_ZERO),
    ('B: perm_small',    NEAR_ZERO,         PLOGINITSD_CALIB),
    ('C: init_small',    PERMSHKSTD_CALIB[0], NEAR_ZERO),
    ('D: both_normal',   PERMSHKSTD_CALIB[0], PLOGINITSD_CALIB),
]

print("=" * 78)
print("DIAGNOSTIC: Variance Knockdown Analysis")
print("=" * 78)
print(f"  PermShkStd calibrated: {PERMSHKSTD_CALIB[0]:.6f}")
print(f"  pLogInitStd calibrated: {PLOGINITSD_CALIB:.6f}")
print(f"  Near-zero value: {NEAR_ZERO}")
print(f"  MC: N={N_MC}, seeds={N_SEEDS}")
print(f"  TM: mCount=100")
print()

results = {}

for label, perm_std, init_std in configs:
    print(f"\n{'='*78}")
    print(f"CONFIG {label}  (PermShkStd={perm_std:.4f}, pLogInitStd={init_std:.4f})")
    print(f"{'='*78}")
    t0 = time()

    # Build economy with modified parameters
    print(f"  Building economy...", flush=True)
    eco = build_economy(perm_std, init_std)
    agent = eco.agents[0]
    act_T = eco.act_T

    # Verify the PermShk distribution
    d0 = agent.IncShkDstn[0][0]
    perm_atoms = d0.atoms[0]
    perm_var = np.dot(d0.pmv, np.log(perm_atoms)**2) - np.dot(d0.pmv, np.log(perm_atoms))**2
    print(f"  Actual PermShk log-variance: {perm_var:.8f} (target: {perm_std**2:.8f})")
    print(f"  pLogInitMean: {agent.pLogInitMean:.4f}, pLogInitStd: {agent.pLogInitStd:.4f}")

    # TM experiment
    print(f"  Running TM recession...", flush=True)
    tm_npv, tm_te, E_pLvl_tm, u_erg, disc = run_tm_recession(eco)
    print(f"  TM NPV: {tm_npv:.6f}, E[pLvl]={E_pLvl_tm:.4f}, u_erg={u_erg:.4f}")

    # MC experiment
    print(f"  Running MC recession ({N_SEEDS} seeds)...", flush=True)
    eco_for_mc = deepcopy(eco)
    bl_data = compute_baseline_tm_data(eco, mCount=100, verbose=False)

    # Ensure bl_data has ergodic distribution for MC init
    if 'ergodic' not in bl_data[0]:
        from tm_methods import build_tm_agg_fiscal, find_ergodic_distribution
        agent_base = eco.agents[0]
        agent_base.update_mrkv_array('base')
        agent_base.solve()
        tm_data_for_init = build_tm_agg_fiscal(agent_base, mCount=100)
        erg = find_ergodic_distribution(tm_data_for_init['TranMatrix'])
        bl_data[0]['ergodic'] = erg
        bl_data[0]['dist_mGrid'] = tm_data_for_init['dist_mGrid']

    mc_npvs, mc_te_all, mc_pLvl = run_mc_recession(eco_for_mc, bl_data, N_MC, N_SEEDS)
    mc_mean = np.mean(mc_npvs)
    mc_std = np.std(mc_npvs)
    rel_err = (tm_npv - mc_mean) / abs(mc_mean) * 100 if abs(mc_mean) > 1e-12 else float('nan')

    print(f"\n  --- Results ---")
    print(f"  TM NPV:      {tm_npv:.6f}")
    print(f"  MC mean NPV: {mc_mean:.6f} ± {mc_std:.6f}")
    print(f"  Rel error:    {rel_err:+.2f}%")

    # Per-period decomposition (first 15 periods)
    mc_te_mean = np.mean(mc_te_all, axis=0)
    mc_te_se = np.std(mc_te_all, axis=0) / np.sqrt(N_SEEDS)
    mc_pLvl_rec_mean = np.mean([p['rec'] for p in mc_pLvl], axis=0)
    mc_pLvl_base_mean = np.mean([p['base'] for p in mc_pLvl], axis=0)

    # Reconstruct TM pLvl_factor trajectory
    from tm_methods import _effective_LivPrb
    G_perm = agent.PermGroFac[0][0]
    g_base = (1.0 - u_erg) * G_perm + u_erg
    J_micro = 4
    _LivPrb_eff = _effective_LivPrb(
        np.asarray(agent.LivPrb[0][:J_micro], dtype=np.float64),
        getattr(agent, 'T_age', None))
    delta_eff = 1.0 - np.mean(_LivPrb_eff)

    rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
    for ti in range(3):
        rec_path[ti] = rec_path[ti] + 1
    rec_path = rec_path[:act_T]

    # Unemployment rates from rec_path macro states
    from Parameters import return_parameters as _rp
    # The micro Mrkv states within each macro state determine u
    # For simplicity, track F_t analytically
    pLvl_factors = np.zeros(act_T)
    F = 1.0
    for ti in range(act_T):
        pLvl_factors[ti] = F
        # Approximate u_rec_t from the TM distribution
        # (would need actual dist; use the recession u schedule instead)
        macro = rec_path[ti]
        if macro == 0:
            u_t = u_erg
        else:
            # During recession, u is elevated; use a rough estimate
            # from the Markov structure. For now, just note the macro state.
            u_t = u_erg  # placeholder; actual u comes from TM dist
        g_rec_t = (1.0 - u_t) * G_perm + u_t
        F = (1.0 - delta_eff) * g_rec_t * F + (1.0 - (1.0 - delta_eff) * g_base)

    T_show = min(15, act_T)
    print(f"\n  Per-period decomposition (first {T_show} periods):")
    print(f"  {'t':>4s}  {'TM_TE':>10s}  {'MC_TE':>10s}  {'MC_SE':>10s}  {'TM-MC':>10s}  {'|e|/SE':>8s}  {'MC_E[p]_rec':>12s}  {'MC_E[p]_base':>13s}  {'MC_F_t':>8s}  {'TM_F_t':>8s}")
    print(f"  {'----':>4s}  {'----------':>10s}  {'----------':>10s}  {'----------':>10s}  {'----------':>10s}  {'--------':>8s}  {'------------':>12s}  {'-------------':>13s}  {'--------':>8s}  {'--------':>8s}")
    for ti in range(T_show):
        mc_te_i = mc_te_mean[ti]
        mc_se_i = mc_te_se[ti]
        tm_te_i = tm_te[ti]
        diff = tm_te_i - mc_te_i
        se_ratio = abs(diff) / max(mc_se_i, 1e-15)
        flag = ' ***' if se_ratio > 3 else ''
        mc_p_rec = mc_pLvl_rec_mean[ti]
        mc_p_base = mc_pLvl_base_mean[ti]
        mc_F = mc_p_rec / mc_p_base if mc_p_base > 0 else float('nan')
        tm_F = pLvl_factors[ti]
        print(f"  {ti:>4d}  {tm_te_i:>10.6f}  {mc_te_i:>10.6f}  {mc_se_i:>10.6f}  {diff:>+10.6f}  {se_ratio:>8.2f}  {mc_p_rec:>12.4f}  {mc_p_base:>13.4f}  {mc_F:>8.6f}  {tm_F:>8.6f}{flag}")

    # Covariance diagnostic: run one extra MC seed with full output
    # to measure Cov(p, c_nrm) = E[p*c_nrm] - E[p]*E[c_nrm]
    print(f"\n  Covariance diagnostic (MC recession, extra seed, first {T_show} periods):")
    print(f"  {'t':>4s}  {'E[p*c_nrm]':>12s}  {'E[p]*E[c]':>12s}  {'Cov/E[pc]':>10s}  {'E[pLvl]':>10s}")
    print(f"  {'----':>4s}  {'------------':>12s}  {'------------':>12s}  {'----------':>10s}  {'----------':>10s}")
    try:
        eco_cov = deepcopy(eco_for_mc)
        init_mc_from_ergodic(eco_cov, bl_data, N_MC, 99)
        eco_cov.save_state()
        eco_cov.switch_to_counterfactual_mode("base")
        eco_cov.act_T = act_T
        for a in eco_cov.agents:
            a.T_sim = act_T
            a.EconomyMrkvNow_hist = [0] * act_T
        eco_cov.make_idiosyncratic_shock_histories()

        cov_base_dict = deepcopy(base_dict)
        cov_base_dict['Splurge'] = agent.Splurge
        mc_base_cov = eco_cov.run_experiment(**cov_base_dict, Full_Output=True)
        eco_cov.store_baseline(mc_base_cov['AggCons'])

        eco_rec_cov = deepcopy(eco_cov)
        eco_rec_cov.switch_shock_type("recession")
        eco_rec_cov.solve()
        rec_dict_cov = deepcopy(base_dict)
        rec_dict_cov['Splurge'] = agent.Splurge
        rec_dict_cov.update(recession_changes)
        rec_dict_cov['EconomyMrkv_init'] = rec_path
        mc_rec_full = eco_rec_cov.run_experiment(**rec_dict_cov, Full_Output=True)

        pLvl_all = mc_rec_full['pLvl_all']
        cLvl_splurge_all = mc_rec_full['cLvl_all_splurge']
        for ti in range(min(T_show, pLvl_all.shape[0])):
            p = pLvl_all[ti]
            c_lvl = cLvl_splurge_all[ti]
            c_nrm = c_lvl / np.maximum(p, 1e-15)
            Epc = np.mean(p * c_nrm)
            Ep = np.mean(p)
            Ec = np.mean(c_nrm)
            cov_pc = Epc - Ep * Ec
            frac = cov_pc / Epc if abs(Epc) > 1e-15 else 0
            print(f"  {ti:>4d}  {Epc:>12.6f}  {Ep*Ec:>12.6f}  {frac:>+10.4%}  {Ep:>10.4f}")
    except Exception as ex:
        print(f"  Covariance diagnostic failed: {ex}")

    elapsed = time() - t0
    print(f"\n  Config {label} time: {elapsed:.0f}s")

    results[label] = {
        'tm_npv': tm_npv, 'mc_mean': mc_mean, 'mc_std': mc_std,
        'rel_err': rel_err, 'perm_std': perm_std, 'init_std': init_std,
    }

# ============================================================
# Summary
# ============================================================
print(f"\n\n{'='*78}")
print("SUMMARY")
print(f"{'='*78}")
print(f"{'Config':<25s}  {'PermShk':>8s}  {'pLogInit':>8s}  {'TM NPV':>10s}  {'MC mean':>10s}  {'rel err':>8s}")
print(f"{'-'*25}  {'-'*8}  {'-'*8}  {'-'*10}  {'-'*10}  {'-'*8}")
for label, r in results.items():
    print(f"{label:<25s}  {r['perm_std']:>8.4f}  {r['init_std']:>8.4f}  {r['tm_npv']:>10.6f}  {r['mc_mean']:>10.6f}  {r['rel_err']:>+7.2f}%")

print(f"\nTotal time: {time()-t0_global:.0f}s ({(time()-t0_global)/60:.1f} min)")
