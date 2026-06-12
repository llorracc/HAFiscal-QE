"""
SOLO-pol TaxCut with a SHORT 2-quarter tax cut window (instead of 8q).
For faster bug-hunting on the TM vs MC discrepancy.

Tax cut applies to macros 2..5 only (2 expansion+recession pairs = 2 quarters).
EconomyMrkv_init walks macros 2, 4, then 0, 0, ... (post-cut stationary).
"""
import sys, os
import numpy as np
from copy import deepcopy

_THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS)
sys.path.insert(0, os.path.dirname(_THIS))

_orig_argv = sys.argv[:]
sys.argv = [sys.argv[0], "1.01", "2.0", "0.7"]
from Parameters import return_parameters
from AggFiscalModel import DualAggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from tm_methods import (
    calculate_NPV, compute_baseline_tm_data, compute_pLvl_distribution,
    run_experiment_tm, run_experiment_tm_nonbase,
)
sys.argv = _orig_argv

TAX_CUT_QUARTERS = 2  # was 8 in original


def build_eco_with_N(N=1, seed=0):
    params = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
    (init_d, init_h, init_c, init_ADE, DiscFacDstns, DiscFacCount, _N,
     base_dict, _nmi, _ct, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_rec, num_exp,
     rec_ch, UI_ch, rec_UI_ch, TC_ch, rec_TC_ch, Ck_ch, rec_Ck_ch) = params

    init_ADE["act_T"] = 200
    eco = AggregateDemandEconomy(**init_ADE)
    a = DualAggFiscalType(**init_h)
    a.cycles = 0
    a.AgentCount = int(N)
    a.seed = int(seed)
    a.DiscFac = DiscFacDstns[1].atoms[0][0]
    a.get_economy_data(eco)

    iu = DiscreteDistribution(np.array([1.0]),
        [np.array([1.0]), np.array([a.IncUnemp])])
    iunb = DiscreteDistribution(np.array([1.0]),
        [np.array([1.0]), np.array([a.IncUnempNoBenefits])])
    a.IncShkDstn = [[a.IncShkDstn[0]] + [iu] * UBspell_normal + [iunb]]
    a.IncShkDstn_base = a.IncShkDstn

    EmployedIncShkDstn = deepcopy(a.IncShkDstn[0][0])
    # Typo removed; tax cut applied elsewhere (MC sim-time, TM per-period TM build).
    TaxCutStatesIncShkDstn = [EmployedIncShkDstn] + [iu] * UBspell_normal + [iunb]

    rec = [a.IncShkDstn[0] * (2 * (num_exp + 1))]
    a.IncShkDstn_recession = rec
    a.IncShkDstn_recessionUI = rec
    a.IncShkDstn_recessionTaxCut = deepcopy(rec)
    # SHORT WINDOW: only macros 2..(2+2*TAX_CUT_QUARTERS-1)
    end_macro = 2 + 2 * TAX_CUT_QUARTERS
    for i in range(2 * num_base_MrkvStates, end_macro * num_base_MrkvStates):
        a.IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
    a.IncShkDstn_recessionCheck = deepcopy(rec)

    a.setup_Q_measure()
    eco.agents = [a]
    a.income_shuffle = True
    a.markov_shuffle = True
    a.normalize_pLvl = True
    eco.solve()

    return eco, base_dict, num_exp


def tm_q(eco_ref, base_dict, num_exp, mCount=100):
    bl = compute_baseline_tm_data(eco_ref, mCount=mCount, neutral_measure=True, verbose=False)
    base = run_experiment_tm(eco_ref, "base", mCount=mCount, neutral_measure=True, verbose=False)
    eco = deepcopy(eco_ref)
    eco.switch_shock_type("TaxCut")
    eco.solve()
    # SHORT EM_init: only TAX_CUT_QUARTERS expansion macros, then 0
    EM = list(np.arange(1, TAX_CUT_QUARTERS + 1) * 2) + [0] * (200 - TAX_CUT_QUARTERS)
    exp = run_experiment_tm_nonbase(eco, "TaxCut", EM, bl,
                                    mCount=mCount, neutral_measure=True, verbose=False)
    Rfree = eco_ref.agents[0].Rfree[0]
    act_T = eco_ref.act_T
    dc = np.array(exp["AggCons"]) - np.array(base["AggCons"])
    dy = np.array(exp["AggIncome"]) - np.array(base["AggIncome"])
    npv_c = calculate_NPV(dc, act_T, Rfree)[-1]
    npv_y = calculate_NPV(dy, act_T, Rfree)[-1]
    return npv_c / npv_y, npv_c, npv_y, dc, dy


def mc_one(eco_ref, base_dict, num_exp, seed, N, tm_Ep):
    from test_asymptotic_equality_revised import (
        mc_burnin, restore_intended_act_T_after_counterfactual_switch
    )
    eco, _, _ = build_eco_with_N(N, seed)

    bl = compute_baseline_tm_data(eco, mCount=50, neutral_measure=True, verbose=False)
    mc_burnin(eco, warmup=None, tm_data=bl, use_dual=True)
    eco.agents[0]._pLvl_norm_target = tm_Ep

    intended_T = int(eco.act_T)
    eco.save_state()
    eco.switch_to_counterfactual_mode("base")
    restore_intended_act_T_after_counterfactual_switch(eco, intended_T)
    eco.make_idiosyncratic_shock_histories()
    base_r = eco.run_experiment(**deepcopy(base_dict), Full_Output=True)
    eco.store_baseline(base_r["AggCons"])

    eco2 = deepcopy(eco)
    eco2.switch_shock_type("TaxCut")
    eco2.solve()
    # Get TC_changes from full params (need this for run_experiment to know shock type)
    params = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
    TC_ch = params[16]
    dictt = deepcopy(base_dict)
    dictt.update(**TC_ch)
    EM = list(np.arange(1, TAX_CUT_QUARTERS + 1) * 2) + [0] * (200 - TAX_CUT_QUARTERS)
    dictt["EconomyMrkv_init"] = EM
    exp_r = eco2.run_experiment(**dictt, Full_Output=True)

    Rfree = eco.agents[0].Rfree[0]
    act_T = eco.act_T
    dc = np.array(exp_r["AggCons"]) - np.array(base_r["AggCons"])
    dy = np.array(exp_r["AggIncome"]) - np.array(base_r["AggIncome"])
    npv_c = calculate_NPV(dc, act_T, Rfree)[-1]
    npv_y = calculate_NPV(dy, act_T, Rfree)[-1]
    return npv_c / npv_y, npv_c, npv_y, dc, dy


def main():
    eco_ref, base_dict, num_exp = build_eco_with_N(1, 0)
    u = getattr(eco_ref.agents[0], 'Urate_normal', 0.044)
    g, p = compute_pLvl_distribution(eco_ref.agents[0], n_points=200, unemployment_rate=u)
    tm_Ep = float(np.dot(p, g))

    print(f"=== {TAX_CUT_QUARTERS}-quarter TaxCut SOLO-pol ===\n")
    print("TM-Q:")
    mult_tm, npvc_tm, npvy_tm, dc_tm, dy_tm = tm_q(eco_ref, base_dict, num_exp)
    print(f"  multiplier = {mult_tm:.6f}")
    print(f"  NPV(dC)    = {npvc_tm:.6f}")
    print(f"  NPV(dY)    = {npvy_tm:.6f}")
    print(f"  dC[0..5]   = {dc_tm[:6]}")
    print(f"  dY[0..5]   = {dy_tm[:6]}")

    print("\nMC-P (3 seeds, N=4000):")
    npvc_mc, npvy_mc, mults = [], [], []
    for s in range(3):
        m, c, y, dc_mc, dy_mc = mc_one(eco_ref, base_dict, num_exp, s * 100, 4000, tm_Ep)
        mults.append(m); npvc_mc.append(c); npvy_mc.append(y)
        print(f"  seed {s}: mult={m:.6f}  NPV(dC)={c:.6f}  NPV(dY)={y:.6f}")
        if s == 0:
            print(f"    dC[0..5] = {dc_mc[:6]}")
            print(f"    dY[0..5] = {dy_mc[:6]}")
    print(f"\n  mean mult     = {np.mean(mults):.6f}")
    print(f"  mean NPV(dC)  = {np.mean(npvc_mc):.6f}  (TM: {npvc_tm:.6f}, "
          f"diff {np.mean(npvc_mc)-npvc_tm:+.6f}, "
          f"{(np.mean(npvc_mc)-npvc_tm)/npvc_tm*100:+.3f}%)")
    print(f"  mean NPV(dY)  = {np.mean(npvy_mc):.6f}  (TM: {npvy_tm:.6f}, "
          f"diff {np.mean(npvy_mc)-npvy_tm:+.6f}, "
          f"{(np.mean(npvy_mc)-npvy_tm)/npvy_tm*100:+.3f}%)")


if __name__ == "__main__":
    main()
