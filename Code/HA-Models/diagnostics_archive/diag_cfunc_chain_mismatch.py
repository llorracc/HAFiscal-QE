"""
Diagnostic: does cFunc from the BASE 4-state chain differ from cFunc in the
TaxCut 88-state chain at "equivalent" macro states?

Hypothesis (history/20260406-TaxCut-MC-vs-TM-discrepancy.md): the ~1.3% TaxCut
TM bias arises because run_experiment_tm's baseline uses compute_type_aggregates_tm
(cFunc from base chain), while the experiment loop uses compute_period_aggregates_tm
(cFunc from TaxCut chain). If cFunc_base[j] != cFunc_taxCut[2*J+j] (stationary
post-tax-cut macros), the dC = exp - base subtraction is comparing apples to oranges.

Compares cFunc at equivalent micro states j over a fine m-grid.
"""
import sys, os
import numpy as np
from copy import deepcopy

_THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS)
sys.path.insert(0, os.path.dirname(_THIS))

from parity_solo_pol_linear import build_solo_pol_economy
from AggFiscalModel import DualAggFiscalType


def main():
    eco_base, _ = build_solo_pol_economy(DualAggFiscalType, 1, 0)
    a_base = eco_base.agents[0]
    cF_base = a_base.solution[0].cFunc  # length J=4

    eco_tc, _ = build_solo_pol_economy(DualAggFiscalType, 1, 0)
    eco_tc.switch_shock_type("TaxCut")
    eco_tc.solve()
    a_tc = eco_tc.agents[0]
    cF_tc = a_tc.solution[0].cFunc  # length 88

    J = 4  # micro states per macro
    m_grid = np.linspace(0.1, 20.0, 50)
    p_val = np.ones_like(m_grid)  # cFunc is 2D in (m, p)

    print(f"len(cF_base)={len(cF_base)}, len(cF_tc)={len(cF_tc)}")
    print(f"\nCompare cF_base[j] vs cF_tc[macro*J+j] across macro indices:")
    print(f"{'macro':>6} {'j':>3} {'max|dc|':>12} {'rel@m=2':>12} {'rel@m=10':>12}")
    print("-" * 55)

    n_macro = len(cF_tc) // J
    for macro in range(n_macro):
        for j in range(J):
            idx_tc = macro * J + j
            cb = cF_base[j](m_grid, p_val)
            ct = cF_tc[idx_tc](m_grid, p_val)
            diff = ct - cb
            max_abs = np.max(np.abs(diff))
            if max_abs < 1e-8:
                continue
            i2 = np.argmin(np.abs(m_grid - 2.0))
            i10 = np.argmin(np.abs(m_grid - 10.0))
            rel2 = (ct[i2] - cb[i2]) / cb[i2] if cb[i2] != 0 else 0
            rel10 = (ct[i10] - cb[i10]) / cb[i10] if cb[i10] != 0 else 0
            print(f"{macro:>6} {j:>3} {max_abs:12.6f} {rel2:12.4%} {rel10:12.4%}")

    print(f"\n(Macros 2..17 are the TaxCut window; 18+ are post-cut stationary)")
    print(f"(If macros 18+ show ~0 diff, base and post-cut chains agree there.)")
    print(f"(If they differ ~1%, that is the cFunc-mismatch bug.)")


if __name__ == "__main__":
    main()
