"""
Print TM and MC dY[t] and dC[t] side-by-side for the first ~12 periods of
the SOLO-pol TaxCut experiment. Localize the residual bias to a period
pattern (uniform → multiplicative; concentrated → discrete bug).
"""
import sys, os, numpy as np
from copy import deepcopy
_T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, _T); sys.path.insert(0, os.path.dirname(_T))

from parity_solo_pol_linear import build_solo_pol_economy
from AggFiscalModel import DualAggFiscalType
from tm_methods import (compute_baseline_tm_data, compute_pLvl_distribution,
                        run_experiment_tm, run_experiment_tm_nonbase)


def tm_per_period(eco_ref, num_exp, mCount=100):
    bl = compute_baseline_tm_data(eco_ref, mCount=mCount, neutral_measure=True, verbose=False)
    base = run_experiment_tm(eco_ref, "base", mCount=mCount, neutral_measure=True, verbose=False)
    eco = deepcopy(eco_ref)
    eco.switch_shock_type("TaxCut")
    eco.solve()
    EM = list(np.arange(1, num_exp + 1) * 2) + [0] * 20
    exp = run_experiment_tm_nonbase(eco, "TaxCut", EM, bl,
                                    mCount=mCount, neutral_measure=True, verbose=False)
    return (np.array(exp["AggCons"]) - np.array(base["AggCons"]),
            np.array(exp["AggIncome"]) - np.array(base["AggIncome"]))


def mc_per_period(eco_ref, meta, n_seeds=5, N=8000, tm_Ep=None):
    from test_asymptotic_equality_revised import (
        mc_burnin, restore_intended_act_T_after_counterfactual_switch
    )
    from parity_solo_pol_linear import HAS_NORM
    if HAS_NORM:
        from AggFiscalModel import NormalizedDualAggFiscalType
        AC = NormalizedDualAggFiscalType
    else:
        AC = DualAggFiscalType
    dcs, dys = [], []
    for s in range(n_seeds):
        eco, _ = build_solo_pol_economy(AC, N, s * 100, variance_reduction=True)
        bl = compute_baseline_tm_data(eco, mCount=50, neutral_measure=True, verbose=False)
        mc_burnin(eco, warmup=None, tm_data=bl, use_dual=True)
        if tm_Ep is not None:
            eco.agents[0]._pLvl_norm_target = tm_Ep
        intended_T = int(eco.act_T)
        eco.save_state()
        eco.switch_to_counterfactual_mode("base")
        restore_intended_act_T_after_counterfactual_switch(eco, intended_T)
        eco.make_idiosyncratic_shock_histories()
        base_r = eco.run_experiment(**deepcopy(meta["base_dict"]), Full_Output=True)
        eco.store_baseline(base_r["AggCons"])
        eco2 = deepcopy(eco)
        eco2.switch_shock_type("TaxCut")
        eco2.solve()
        dictt = deepcopy(meta["base_dict"])
        dictt.update(**meta["TaxCut_changes"])
        dictt["EconomyMrkv_init"] = list(np.arange(1, meta["num_exp"] + 1) * 2) + [0] * 20
        exp_r = eco2.run_experiment(**dictt, Full_Output=True)
        dcs.append(np.array(exp_r["AggCons"]) - np.array(base_r["AggCons"]))
        dys.append(np.array(exp_r["AggIncome"]) - np.array(base_r["AggIncome"]))
    dcs = np.array(dcs); dys = np.array(dys)
    return dcs.mean(0) / N, dys.mean(0) / N, dcs.std(0)/np.sqrt(n_seeds)/N, dys.std(0)/np.sqrt(n_seeds)/N


def main():
    eco_ref, meta = build_solo_pol_economy(DualAggFiscalType, 1, 0)
    a = eco_ref.agents[0]
    u = float(getattr(a, 'Urate_normal', 0.044))
    g, p = compute_pLvl_distribution(a, n_points=200, unemployment_rate=u)
    tm_Ep = float(np.dot(p, g))

    print("TM per-period dY, dC...")
    dC_tm, dY_tm = tm_per_period(eco_ref, meta["num_exp"])

    print("MC per-period dY, dC (5 seeds, N=8000)...")
    dC_mc, dY_mc, dC_se, dY_se = mc_per_period(eco_ref, meta, 5, 8000, tm_Ep)

    print(f"\n{'t':>3} {'dY_TM':>10} {'dY_MC':>10} {'dY_SE':>9} {'dY_diff':>10} {'rel%':>7} "
          f"| {'dC_TM':>10} {'dC_MC':>10} {'dC_SE':>9} {'dC_diff':>10} {'rel%':>7}")
    print("-" * 130)
    for t in range(14):
        rel_y = (dY_mc[t] - dY_tm[t]) / dY_tm[t] * 100 if abs(dY_tm[t]) > 1e-10 else 0.0
        rel_c = (dC_mc[t] - dC_tm[t]) / dC_tm[t] * 100 if abs(dC_tm[t]) > 1e-10 else 0.0
        print(f"{t:>3d} {dY_tm[t]:10.6f} {dY_mc[t]:10.6f} {dY_se[t]:9.6f} "
              f"{dY_mc[t]-dY_tm[t]:+10.6f} {rel_y:+7.2f} | "
              f"{dC_tm[t]:10.6f} {dC_mc[t]:10.6f} {dC_se[t]:9.6f} "
              f"{dC_mc[t]-dC_tm[t]:+10.6f} {rel_c:+7.2f}")


if __name__ == "__main__":
    main()
