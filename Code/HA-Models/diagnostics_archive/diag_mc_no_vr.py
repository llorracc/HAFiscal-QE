"""
Test whether MC's variance reduction (income_shuffle, markov_shuffle,
normalize_pLvl) biases the TaxCut multiplier. If MC without VR converges to
TM (0.97189), then VR is the bug. If MC without VR also gives 0.97424,
then VR is not at fault and the bug is on the TM side.
"""
import sys, os, numpy as np
_T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, _T); sys.path.insert(0, os.path.dirname(_T))

from parity_solo_pol_linear import build_solo_pol_economy, mc_multiplier
from AggFiscalModel import DualAggFiscalType
from tm_methods import compute_pLvl_distribution


def main():
    eco_ref, meta = build_solo_pol_economy(DualAggFiscalType, 1, 0)
    a = eco_ref.agents[0]
    u = float(getattr(a, 'Urate_normal', 0.044))
    g, p = compute_pLvl_distribution(a, n_points=200, unemployment_rate=u)
    tm_Ep = float(np.dot(p, g))

    print("MC TaxCut multiplier WITH variance reduction (5 seeds, N=8000):")
    vals = [mc_multiplier(eco_ref, "TaxCut", meta, s * 100, 8000, True, tm_Ep)
            for s in range(5)]
    print(f"  mean = {np.mean(vals):.6f}  SE = {np.std(vals)/np.sqrt(5):.6f}")
    for s, v in enumerate(vals):
        print(f"    seed {s}: {v:.6f}")

    print("\nMC TaxCut multiplier WITHOUT variance reduction (5 seeds, N=8000):")
    vals2 = [mc_multiplier(eco_ref, "TaxCut", meta, s * 100, 8000, False, tm_Ep)
             for s in range(5)]
    print(f"  mean = {np.mean(vals2):.6f}  SE = {np.std(vals2)/np.sqrt(5):.6f}")
    for s, v in enumerate(vals2):
        print(f"    seed {s}: {v:.6f}")

    print(f"\nTM-Q (target): 0.971864")
    print(f"diff WITH VR : {np.mean(vals) - 0.971864:+.6f}")
    print(f"diff WO VR   : {np.mean(vals2) - 0.971864:+.6f}")


if __name__ == "__main__":
    main()
