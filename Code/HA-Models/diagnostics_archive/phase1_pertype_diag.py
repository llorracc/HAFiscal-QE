"""
Phase 1 diagnostic: per-type recession NPV errors.

Runs each education type individually to see which types contribute
to the ~5.5% aggregate recession NPV error.
"""

# Math reference: see history/20260331-mathematical-derivations-TM-MC-convergence.md ("math-derive")

import os, sys
import numpy as np
from time import time
from copy import deepcopy

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

t0_total = time()

N_MC = 200000
NUM_SEEDS = 3
MCOUNT = 100

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

print("=" * 70)
print("PER-TYPE RECESSION DIAGNOSTIC")
print("=" * 70)

for e_idx in range(3):
    print(f"\n{'='*70}")
    print(f"  Testing: {edu_names[e_idx]}, beta={DiscFacDstns[e_idx].atoms[0][0]:.4f}")
    print(f"{'='*70}")

    AggEco = AggregateDemandEconomy(**init_ADEconomy)
    BaseType = AggFiscalType(**edu_inits[e_idx])
    BaseType.cycles = 0
    BaseType.DiscFac = DiscFacDstns[e_idx].atoms[0][0]
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

    EmployedIncShkDstn_tc = deepcopy(EmployedIncShkDstn)
    # BUG-023 fix: was `EmployedIncShkDstn_tc.atoms[0][1] = EmployedIncShkDstn_tc.atoms[0][1] * BaseType.TaxCutIncFactor`
    # which mutated one PermShk atom; the intended behavior is to
    # rescale every joint atom's TranShk component (atoms[1]).
    # See BUGS_private/HAFiscal_BUG-023_taxcut_atoms_typo.md.
    EmployedIncShkDstn_tc.atoms = (
        np.asarray(EmployedIncShkDstn_tc.atoms[0], dtype=np.float64),
        np.asarray(EmployedIncShkDstn_tc.atoms[1], dtype=np.float64) * BaseType.TaxCutIncFactor,
    )
    TaxCutStatesIncShkDstn = [EmployedIncShkDstn_tc] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]
    IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
    for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates):
        IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
    BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
    BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

    AggEco.agents = [BaseType]
    BaseType.AgentCount = 1
    AggEco.solve()
    act_T = AggEco.act_T
    Rfree = BaseType.Rfree[0]

    rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T - num_experiment_periods)
    for t in range(3):
        rec_path[t] = rec_path[t] + 1
    rec_path = rec_path[:act_T]
    disc = np.array([1.0 / Rfree**t for t in range(act_T)])

    # TM
    bl_data = compute_baseline_tm_data(AggEco, mCount=MCOUNT, verbose=False)
    tm_base = run_experiment_tm(AggEco, shock_type='base', mCount=MCOUNT, verbose=False)
    tm_base_cons = np.array(tm_base['AggCons'])
    eco_tm = deepcopy(AggEco)
    eco_tm.switch_shock_type('recession')
    eco_tm.solve()
    r = run_experiment_tm_nonbase(eco_tm, 'recession', rec_path, bl_data, mCount=MCOUNT, verbose=False)
    tm_rec_cons = np.array(r['AggCons'])
    tm_te = tm_rec_cons - tm_base_cons
    tm_npv = np.sum(tm_te * disc)

    # Also extract pLvl_factor-related info
    print(f"    PermGroFac = {BaseType.PermGroFac[0][0]:.6f}")
    print(f"    TM base AggCons[0] = {tm_base_cons[0]:.6f}")
    print(f"    TM rec  AggCons[0] = {tm_rec_cons[0]:.6f}")

    # MC
    base_dict_agg = deepcopy(base_dict)
    mc_base_all = []
    mc_rec_all = []
    for seed in range(NUM_SEEDS):
        eco_mc = deepcopy(AggEco)
        for a in eco_mc.agents:
            a.AgentCount = N_MC
            a.seed = seed * 1000
            a.get_economy_data(eco_mc)
        eco_mc.solve()
        eco_mc.reset()
        for a in eco_mc.agents:
            a.initialize_sim()
            a.AggDemandFac = 1.0
            a.RfreeNow = 1.0
            a.CaggNow = 1.0

        bl_std = compute_baseline_tm_data(AggEco, mCount=50, verbose=False)
        for i, agent in enumerate(eco_mc.agents):
            bd_i = bl_std[i]
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
            log_pLvl = rng_i.normal(pLogMean, pLogStd, N_i)
            log_pLvl += agent_ages * np.log(g_lvl)
            log_pLvl += effective_emp_periods * (-ps_var / 2.0)
            log_pLvl += rng_i.normal(0, np.sqrt(ps_var * effective_emp_periods))
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

        eco_mc.save_state()
        eco_mc.switch_to_counterfactual_mode("base")
        eco_mc.act_T = act_T
        for a in eco_mc.agents:
            a.T_sim = act_T
            a.EconomyMrkvNow_hist = [0] * act_T
        eco_mc.make_idiosyncratic_shock_histories()

        mc_base_r = eco_mc.run_experiment(**base_dict_agg, Full_Output=True)
        eco_mc.store_baseline(mc_base_r['AggCons'])
        N_actual = sum(a.AgentCount for a in eco_mc.agents)
        mc_base_all.append(np.array(mc_base_r['AggCons']) / N_actual)

        eco_exp = deepcopy(eco_mc)
        eco_exp.switch_shock_type('recession')
        eco_exp.solve()
        exp_d = base_dict_agg.copy()
        exp_d.update(recession_changes)
        exp_d['EconomyMrkv_init'] = rec_path
        mc_r = eco_exp.run_experiment(**exp_d, Full_Output=True)
        mc_rec_all.append(np.array(mc_r['AggCons']) / N_actual)

    mc_te_seeds = [mc_rec_all[s] - mc_base_all[s] for s in range(NUM_SEEDS)]
    mc_te_mean = np.mean(mc_te_seeds, axis=0)
    mc_npv = np.sum(mc_te_mean * disc)
    mc_npv_seeds = [np.sum(mc_te_seeds[s] * disc) for s in range(NUM_SEEDS)]
    mc_std = np.std(mc_npv_seeds)

    rel = (tm_npv - mc_npv) / abs(mc_npv) * 100 if abs(mc_npv) > 1e-10 else float('nan')
    print(f"    TM recession NPV TE = {tm_npv:>10.4f}")
    print(f"    MC recession NPV TE = {mc_npv:>10.4f} (std={mc_std:.4f})")
    print(f"    Relative error:       {rel:>+.2f}%")

total = time() - t0_total
print(f"\nTotal time: {total:.0f}s ({total/60:.1f} min)")
