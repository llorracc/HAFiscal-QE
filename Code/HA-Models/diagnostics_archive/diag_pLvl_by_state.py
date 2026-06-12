"""
Test the hypothesis: TM uses a single E_pLvl scalar for ALL micro states, but
in reality E[pLvl | employed] > E[pLvl] because employed agents grow pLvl
(PermGroFac > 1) while unemployed don't.

This violates the implicit independence assumption in TM's aggregation:
  AggIncome_TM = N * E_pLvl * sum_j frac_j * E[TranShk_j]
                = N * E_pLvl * frac_emp * E[TranShk_emp] + ...

The correct (MC-equivalent) formula is:
  AggIncome_correct = N * sum_j frac_j * E[pLvl|j] * E[TranShk_j]

If E[pLvl|emp] / E[pLvl] = 1 + delta, then TM undercounts dY by delta on
the employed-driven response (which is essentially all of dY for TaxCut).
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

    # Multiple seeds to reduce noise
    print(f"TM E_pLvl (scalar)        = {tm_Ep:.6f}\n")
    print(f"{'seed':>5} {'E[p]':>10} {'E[p|emp]':>10} {'E[p|unemp]':>11} {'ratio':>10}")
    print("-" * 55)
    Ep_all, Ep_emp_all, Ep_unemp_all = [], [], []
    for s in [0, 100, 200, 300, 400, 500, 600, 700]:
        eco, _ = build_solo_pol_economy(DualAggFiscalType, 8000, s,
                                        variance_reduction=True)
        bl = compute_baseline_tm_data(eco, mCount=50, neutral_measure=True, verbose=False)
        mc_burnin(eco, warmup=None, tm_data=bl, use_dual=True)
        a = eco.agents[0]
        pLvl = a.state_now['pLvl']
        micro = np.asarray(a.MicroMrkvNow if hasattr(a, 'MicroMrkvNow') else a.shocks['Mrkv'] % 4)
        finite = np.isfinite(pLvl)
        emp = (micro == 0) & finite
        unemp = (micro != 0) & finite
        Ep = float(np.mean(pLvl[finite]))
        Ep_emp = float(np.mean(pLvl[emp])) if emp.sum() > 0 else float('nan')
        Ep_unemp = float(np.mean(pLvl[unemp])) if unemp.sum() > 0 else float('nan')
        Ep_all.append(Ep); Ep_emp_all.append(Ep_emp); Ep_unemp_all.append(Ep_unemp)
        ratio = Ep_emp / Ep if Ep > 0 else float('nan')
        print(f"{s:>5d} {Ep:10.4f} {Ep_emp:10.4f} {Ep_unemp:11.4f} {ratio:10.6f}")

    Ep_m = np.mean(Ep_all)
    Ep_emp_m = np.mean(Ep_emp_all)
    Ep_unemp_m = np.mean(Ep_unemp_all)
    print(f"\n  mean E[p]      = {Ep_m:.6f}")
    print(f"  mean E[p|emp]  = {Ep_emp_m:.6f}")
    print(f"  mean E[p|unemp]= {Ep_unemp_m:.6f}")
    print(f"  E[p|emp]/E[p]  = {Ep_emp_m/Ep_m:.6f}  (excess: {(Ep_emp_m/Ep_m-1)*100:+.3f}%)")
    print(f"  E[p|emp]/TM_Ep = {Ep_emp_m/tm_Ep:.6f}  (excess: {(Ep_emp_m/tm_Ep-1)*100:+.3f}%)")
    print(f"\n  Predicted dY bias if TM uses E_p × frac_emp instead of E[p|emp] × frac_emp:")
    print(f"    = (E[p|emp]/E[p] - 1) × 100 = {(Ep_emp_m/Ep_m - 1)*100:+.3f}%")
    print(f"    Observed dY bias was +0.55% — match if these agree.")


if __name__ == "__main__":
    main()
