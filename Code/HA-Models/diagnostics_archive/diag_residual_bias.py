"""
Localize the residual dY (0.55%) and dC (0.79%) bias in TM TaxCut.

Steps:
  1. Compute TM E_pLvl (analytical, used as scalar level multiplier).
  2. Compute MC mean(pLvl) after burn-in across multiple seeds, N=8000.
  3. Compute MC frac_employed during tax cut window vs TM state_fracs.
  4. Compute MC E[TranShk | employed] in window vs TM E_TranShk[0]*1.02.

If TM E_pLvl is 0.55% lower than MC mean(pLvl), that explains dY entirely.
"""
import sys, os
import numpy as np
from copy import deepcopy

_THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS)
sys.path.insert(0, os.path.dirname(_THIS))

from parity_solo_pol_linear import build_solo_pol_economy
from AggFiscalModel import DualAggFiscalType
from tm_methods import (
    compute_baseline_tm_data, compute_pLvl_distribution,
    compute_analytical_mean_pLvl,
)


def main():
    eco_ref, meta = build_solo_pol_economy(DualAggFiscalType, 1, 0)
    a = eco_ref.agents[0]
    u = getattr(a, 'Urate_normal', 0.044)

    # TM E_pLvl (analytical)
    g, p = compute_pLvl_distribution(a, n_points=200, unemployment_rate=u)
    tm_Ep_grid = float(np.dot(p, g))
    tm_Ep_func = float(compute_analytical_mean_pLvl(a, unemployment_rate=u))
    bl = compute_baseline_tm_data(eco_ref, mCount=100, neutral_measure=True, verbose=False)
    tm_Ep_baseline = float(bl[0]['E_pLvl'])
    u_erg = float(bl[0]['u_ergodic'])

    print(f"TM analytical E_pLvl:")
    print(f"  via compute_pLvl_distribution(u_normal):  {tm_Ep_grid:.6f}")
    print(f"  via compute_analytical_mean_pLvl(u_norm): {tm_Ep_func:.6f}")
    print(f"  via compute_baseline_tm_data (u_erg):     {tm_Ep_baseline:.6f}")
    print(f"  u_normal = {u:.6f}, u_ergodic = {u_erg:.6f}")
    print()

    # MC mean(pLvl) after burn-in
    from test_asymptotic_equality_revised import (
        mc_burnin, restore_intended_act_T_after_counterfactual_switch
    )
    print("MC mean(pLvl) after burn-in (5 seeds, N=8000):")
    Ep_mc, frac_emp_mc = [], []
    for s in range(5):
        eco, _ = build_solo_pol_economy(DualAggFiscalType, 8000, s * 100,
                                        variance_reduction=True)
        bl_s = compute_baseline_tm_data(eco, mCount=50, neutral_measure=True, verbose=False)
        mc_burnin(eco, warmup=None, tm_data=bl_s, use_dual=True)
        a_s = eco.agents[0]
        pLvl = a_s.state_now['pLvl']
        mNrm = a_s.state_now['mNrm']
        # mrkv state per agent (employment state index)
        mrkv = getattr(a_s, 'MrkvNow', None)
        if mrkv is None:
            mrkv = a_s.shocks.get('Mrkv', None) if hasattr(a_s, 'shocks') else None
        finite = np.isfinite(pLvl)
        Ep = float(np.mean(pLvl[finite]))
        Ep_mc.append(Ep)
        if mrkv is not None:
            mrkv_arr = np.asarray(mrkv)
            mrkv_micro = mrkv_arr % 4 if mrkv_arr.max() >= 4 else mrkv_arr
            frac_e = float(np.mean(mrkv_micro[finite] == 0))
            frac_emp_mc.append(frac_e)
            print(f"  seed {s}: mean(pLvl)={Ep:.6f}  frac_emp={frac_e:.6f}")
        else:
            print(f"  seed {s}: mean(pLvl)={Ep:.6f}  (no mrkv)")
    Ep_mc_mean = float(np.mean(Ep_mc))
    Ep_mc_se = float(np.std(Ep_mc) / np.sqrt(len(Ep_mc)))
    print(f"\n  MC mean E_pLvl  = {Ep_mc_mean:.6f} ± {Ep_mc_se:.6f}")
    print(f"  TM E_pLvl       = {tm_Ep_baseline:.6f}")
    print(f"  diff (MC - TM)  = {Ep_mc_mean - tm_Ep_baseline:+.6f}  "
          f"({(Ep_mc_mean - tm_Ep_baseline) / tm_Ep_baseline * 100:+.3f}%)")
    if frac_emp_mc:
        print(f"\n  MC mean frac_emp = {np.mean(frac_emp_mc):.6f}")
        print(f"  TM frac_emp (1-u_erg) = {1.0 - u_erg:.6f}")
        print(f"  diff = {np.mean(frac_emp_mc) - (1.0 - u_erg):+.6f}")


if __name__ == "__main__":
    main()
