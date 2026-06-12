"""
Diagnostic: verify that the MC init growth-rate bug (using G instead of g)
is the root cause of the TM-MC discrepancy.

The MC init computes: log(pLvl) = pLogMean + age * log(G)
But math-derive (g-base) says: E[p | age=k] = E_init * g^(k+1)
where g = (1-u)*G + u < G.

This test compares:
  A) MC init with G (current code — buggy)
  B) MC init with g (corrected)
for Config A (near-zero variances) and Config D (calibrated).
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
    compute_analytical_mean_pLvl, build_tm_agg_fiscal, find_ergodic_distribution,
)

NEAR_ZERO = 0.001
N_MC = 100000
N_SEEDS = 3

t0_global = time()

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

DiscFac = DiscFacDstns[1].atoms[0][0]


def build_economy(perm_shk_std, plog_init_std):
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


def init_mc_from_ergodic(eco_mc, bl_data_init, N_MC_i, seed, use_g=False):
    """
    Initialize MC agents from TM ergodic distribution.
    
    use_g: if True, use g = (1-u)*G + u for pLvl growth (correct).
           if False, use G (current buggy code).
    """
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
        pLogStd = max(getattr(agent, 'pLogInitStd', 0.0), 1e-12)

        PermShkDstn_0 = agent.IncShkDstn_base[0][0]
        log_ps = np.log(PermShkDstn_0.atoms[0])
        ps_var = np.dot(PermShkDstn_0.pmv, log_ps**2) - np.dot(PermShkDstn_0.pmv, log_ps)**2

        u_for_g = float(bd_i['u_ergodic']) if use_g else 0.0
        g_lvl = effective_pLvl_growth(agent, u_for_g)
        effective_emp_periods = effective_perm_shock_periods_for_t_age(
            agent_ages, agent, getattr(agent, 'Urate_normal', 0.0))
        log_pLvl = rng_i.normal(pLogMean, pLogStd, N_i)
        log_pLvl += agent_ages * np.log(g_lvl)
        log_pLvl += effective_emp_periods * (-max(ps_var, 1e-24) / 2.0)
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


def run_mc_recession(eco_template, bl_data_init, N_MC_i, num_seeds, use_g=False):
    act_T = eco_template.act_T
    agent0 = eco_template.agents[0]
    Rfree = agent0.Rfree[0]
    disc_arr = np.array([1.0 / Rfree**t for t in range(act_T)])
    rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
    for t in range(3):
        rec_path[t] = rec_path[t] + 1
    rec_path = rec_path[:act_T]
    base_dict_agg = deepcopy(base_dict)
    base_dict_agg['Splurge'] = agent0.Splurge

    mc_npvs = []
    mc_EpLvl_t0 = []
    for seed in range(num_seeds):
        eco_mc = deepcopy(eco_template)
        init_mc_from_ergodic(eco_mc, bl_data_init, N_MC_i, seed, use_g=use_g)
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

        te = mc_rec_cons - mc_base_cons
        npv = np.sum(te * disc_arr[:T_out])
        mc_npvs.append(npv)
        mc_EpLvl_t0.append(np.mean(mc_base['pLvl_all'][0]))

    return np.array(mc_npvs), np.mean(mc_EpLvl_t0)


# ============================================================
# Run for Config A (both small) and Config D (both normal)
# ============================================================
configs = [
    ('Config A: both small', NEAR_ZERO, NEAR_ZERO),
    ('Config D: both normal', init_highschool['PermShkStd'][0], init_highschool['pLogInitStd']),
]

print("=" * 78)
print("DIAGNOSTIC: MC Init Growth-Rate Bug")
print("  Current: log(pLvl) += age * log(G)     [employed growth only]")
print("  Fixed:   log(pLvl) += age * log(g)     [g = (1-u)*G + u per math-derive (g-base)]")
print("=" * 78)

for label, perm_std, init_std in configs:
    print(f"\n{'='*78}")
    print(f"  {label}  (PermShkStd={perm_std:.4f}, pLogInitStd={init_std:.4f})")
    print(f"{'='*78}")
    
    eco = build_economy(perm_std, init_std)
    agent = eco.agents[0]
    act_T = eco.act_T
    Rfree = agent.Rfree[0]

    # TM reference
    tm_base = run_experiment_tm(eco, shock_type='base', mCount=100, verbose=False)
    bl_data = compute_baseline_tm_data(eco, mCount=100, verbose=False)
    eco_tm2 = deepcopy(eco)
    eco_tm2.switch_shock_type("recession")
    eco_tm2.solve()
    rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
    for t in range(3):
        rec_path[t] = rec_path[t] + 1
    rec_path = rec_path[:act_T]
    tm_rec = run_experiment_tm_nonbase(eco_tm2, "recession", rec_path, bl_data, mCount=100, verbose=False)
    TM_N = agent.AgentCount
    disc_arr = np.array([1.0 / Rfree**t for t in range(act_T)])
    tm_te = np.array(tm_rec['AggCons']) / TM_N - np.array(tm_base['AggCons']) / TM_N
    tm_npv = np.sum(tm_te * disc_arr)

    # Ensure bl_data has ergodic info
    agent_base = eco.agents[0]
    agent_base.update_mrkv_array('base')
    agent_base.solve()
    tm_data = build_tm_agg_fiscal(agent_base, mCount=100)
    erg = find_ergodic_distribution(tm_data['TranMatrix'])
    bl_data[0]['ergodic'] = erg
    bl_data[0]['dist_mGrid'] = tm_data['dist_mGrid']

    E_pLvl_tm = bl_data[0]['E_pLvl']
    u_erg = bl_data[0]['u_ergodic']
    G_emp = float(agent.PermGroFac[0][0])
    g = effective_pLvl_growth(agent, u_erg)
    print(f"  G_emp = {G_emp:.6f}, g = {g:.6f}, u_erg = {u_erg:.4f}")
    print(f"  E[pLvl] analytical (g): {E_pLvl_tm:.4f}")
    print(f"  TM recession TE NPV: {tm_npv:.6f}")

    # MC with G (buggy)
    print(f"\n  --- MC with G (current code) ---")
    t0 = time()
    mc_npvs_G, mc_EpLvl_G = run_mc_recession(eco, bl_data, N_MC, N_SEEDS, use_g=False)
    mc_mean_G = np.mean(mc_npvs_G)
    mc_std_G = np.std(mc_npvs_G)
    rel_G = (tm_npv - mc_mean_G) / abs(mc_mean_G) * 100
    print(f"  MC E[pLvl] (t=0 base): {mc_EpLvl_G:.4f}  (bias vs analytical: {(mc_EpLvl_G-E_pLvl_tm)/E_pLvl_tm*100:+.2f}%)")
    print(f"  MC NPV:  {mc_mean_G:.6f} ± {mc_std_G:.6f}")
    print(f"  TM-MC:   {rel_G:+.2f}%  ({time()-t0:.0f}s)")

    # MC with g (fixed)
    print(f"\n  --- MC with g (fixed) ---")
    t0 = time()
    mc_npvs_g, mc_EpLvl_g = run_mc_recession(eco, bl_data, N_MC, N_SEEDS, use_g=True)
    mc_mean_g = np.mean(mc_npvs_g)
    mc_std_g = np.std(mc_npvs_g)
    rel_g = (tm_npv - mc_mean_g) / abs(mc_mean_g) * 100
    print(f"  MC E[pLvl] (t=0 base): {mc_EpLvl_g:.4f}  (bias vs analytical: {(mc_EpLvl_g-E_pLvl_tm)/E_pLvl_tm*100:+.2f}%)")
    print(f"  MC NPV:  {mc_mean_g:.6f} ± {mc_std_g:.6f}")
    print(f"  TM-MC:   {rel_g:+.2f}%  ({time()-t0:.0f}s)")

    print(f"\n  --- Improvement ---")
    print(f"  Before (G): {rel_G:+.2f}%")
    print(f"  After  (g): {rel_g:+.2f}%")
    print(f"  E[pLvl] bias removed: {(mc_EpLvl_G - mc_EpLvl_g)/mc_EpLvl_G * 100:.2f}%")

print(f"\nTotal time: {time()-t0_global:.0f}s")
