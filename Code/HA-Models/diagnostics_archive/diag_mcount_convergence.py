"""
Test whether TM-Q multiplier converges to MC-P as mCount grows.
If yes -> residual is the math-derive-harm §14.5 finite-grid Cov(p,c) residual.
"""
import sys, os, numpy as np
from copy import deepcopy
_T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, _T); sys.path.insert(0, os.path.dirname(_T))

from parity_solo_pol_linear import build_solo_pol_economy
from AggFiscalModel import DualAggFiscalType
from tm_methods import (calculate_NPV, compute_baseline_tm_data,
                        run_experiment_tm, run_experiment_tm_nonbase)


def tm_mult(eco_ref, num_exp, mCount):
    bl = compute_baseline_tm_data(eco_ref, mCount=mCount, neutral_measure=True, verbose=False)
    base = run_experiment_tm(eco_ref, "base", mCount=mCount, neutral_measure=True, verbose=False)
    eco = deepcopy(eco_ref)
    eco.switch_shock_type("TaxCut")
    eco.solve()
    EM = list(np.arange(1, num_exp + 1) * 2) + [0] * 20
    exp = run_experiment_tm_nonbase(eco, "TaxCut", EM, bl,
                                    mCount=mCount, neutral_measure=True, verbose=False)
    Rfree = eco_ref.agents[0].Rfree[0]
    act_T = eco_ref.act_T
    dc = np.array(exp["AggCons"]) - np.array(base["AggCons"])
    dy = np.array(exp["AggIncome"]) - np.array(base["AggIncome"])
    return calculate_NPV(dc, act_T, Rfree)[-1] / calculate_NPV(dy, act_T, Rfree)[-1]


def main():
    eco_ref, meta = build_solo_pol_economy(DualAggFiscalType, 1, 0)
    print(f"{'mCount':>7} {'TM-Q mult':>12}")
    print("-" * 22)
    for mC in [50, 100, 200, 400, 800]:
        m = tm_mult(eco_ref, meta["num_exp"], mC)
        print(f"{mC:>7d} {m:12.6f}")
    print("\nMC-P @ N=8000, 5 seeds: 0.97424 ± 0.00077 (target)")


if __name__ == "__main__":
    main()
