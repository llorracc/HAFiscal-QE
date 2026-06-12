"""
Test whether MC's mean(pLvl) converges to TM analytical value with longer burn-in.
If yes -> non-ergodic init theory holds.
If no  -> mean(pLvl) excess is genuine, not a transient.
"""
import sys, os, numpy as np
_T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, _T); sys.path.insert(0, os.path.dirname(_T))
from parity_solo_pol_linear import build_solo_pol_economy
from AggFiscalModel import DualAggFiscalType
from tm_methods import compute_baseline_tm_data, compute_analytical_mean_pLvl
from test_asymptotic_equality_revised import mc_burnin


def main():
    eco_ref, _ = build_solo_pol_economy(DualAggFiscalType, 1, 0)
    a_ref = eco_ref.agents[0]
    u = float(getattr(a_ref, 'Urate_normal', 0.044))
    tm_Ep = float(compute_analytical_mean_pLvl(a_ref, unemployment_rate=u))
    print(f"TM analytical E_pLvl = {tm_Ep:.6f}\n")

    print(f"{'warmup':>8} {'seed':>5} {'mean(pLvl)':>12} {'rel to TM':>11}")
    print("-" * 45)
    for warmup in [None, 500, 2000, 5000]:
        for seed in [0, 100, 200]:
            eco, _ = build_solo_pol_economy(DualAggFiscalType, 8000, seed,
                                            variance_reduction=True)
            bl = compute_baseline_tm_data(eco, mCount=50, neutral_measure=True, verbose=False)
            mc_burnin(eco, warmup=warmup, tm_data=bl, use_dual=True)
            pLvl = eco.agents[0].state_now['pLvl']
            mp = float(np.mean(pLvl[np.isfinite(pLvl)]))
            print(f"{str(warmup):>8} {seed:>5} {mp:12.6f} {(mp - tm_Ep)/tm_Ep*100:+10.3f}%")


if __name__ == "__main__":
    main()
