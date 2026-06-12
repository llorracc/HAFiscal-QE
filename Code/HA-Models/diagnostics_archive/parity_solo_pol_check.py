"""
SOLO-pol Check policy: stimulus check on a single high school type.

Companion to ``parity_solo_pol_linear.py`` (for UI extension and TaxCut,
which are p-linear and need only TM-1D).

The Check stimulus has an income-dependent phase-out, making it Class D
(non-p-separable).  TM-1D is inapplicable; TM-2D with p-buckets is required
to integrate over the joint (m, p) distribution.

  Single high school type, point beta, no recession, no AD.
  TM-2D with p-buckets (TM-Q with check_use_p_buckets=True).

Usage:
    PYTHONPATH=/path/to/HARK:$PYTHONPATH python parity_solo_pol_check.py
    PYTHONPATH=... python parity_solo_pol_check.py --agents 4000 --seeds 5

References:
    plans/method-parity-map.md (Class D)
    history/20260331-mathematical-derivations-harmenberg.md §14.5
"""

import sys
import os
import time
import argparse
import numpy as np
from copy import deepcopy

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_HA = os.path.dirname(_THIS_DIR)
if _HA not in sys.path:
    sys.path.insert(0, _HA)

_orig_argv = sys.argv[:]
sys.argv = [sys.argv[0], "1.01", "2.0", "0.7"]

from parity_solo_pol_linear import build_solo_pol_economy, mc_multiplier
from AggFiscalModel import DualAggFiscalType
try:
    from AggFiscalModel import NormalizedDualAggFiscalType
    HAS_NORM = True
except ImportError:
    HAS_NORM = False
from tm_methods import (
    calculate_NPV,
    compute_baseline_tm_data,
    compute_pLvl_distribution,
    run_experiment_tm,
    run_experiment_tm_nonbase,
)

sys.argv = _orig_argv


def tm_q_2d_check_multiplier(economy, meta, mCount, n_buckets=5):
    """Compute TM-Q-2D Check multiplier (with p-buckets, required for Class D)."""
    bl = compute_baseline_tm_data(economy, mCount=mCount, neutral_measure=True, verbose=False)
    base = run_experiment_tm(economy, "base", mCount=mCount, neutral_measure=True, verbose=False)

    eco = deepcopy(economy)
    eco.switch_shock_type("Check")
    eco.solve()
    EconomyMrkv_init = list(np.arange(1, meta["num_exp"] + 1) * 2) + [0] * 20
    exp = run_experiment_tm_nonbase(
        eco, "Check", EconomyMrkv_init, bl,
        mCount=mCount, neutral_measure=True, verbose=False,
        check_use_p_buckets=True, check_n_buckets=n_buckets,
    )

    Rfree = economy.agents[0].Rfree[0]
    act_T = economy.act_T
    delta_c = np.array(exp["AggCons"]) - np.array(base["AggCons"])
    delta_y = np.array(exp["AggIncome"]) - np.array(base["AggIncome"])
    npv_c = calculate_NPV(delta_c, act_T, Rfree)[-1]
    npv_y = calculate_NPV(delta_y, act_T, Rfree)[-1]
    return npv_c / npv_y if abs(npv_y) > 1e-10 else float("nan")


def main():
    parser = argparse.ArgumentParser(description="SOLO-pol Check policy (Class D, TM-2D)")
    parser.add_argument("--agents", type=int, nargs="+", default=[500, 2000])
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--mcount", type=int, default=100)
    parser.add_argument("--n-buckets", type=int, default=5)
    parser.add_argument("--variance-reduction", action="store_true", default=True)
    parser.add_argument("--no-variance-reduction", dest="variance_reduction", action="store_false")
    args = parser.parse_args()

    seeds = list(range(args.seeds))
    mCount = args.mcount
    n_buckets = args.n_buckets
    vr = args.variance_reduction

    print(f"SOLO-pol Check policy (Class D, p-buckets required)")
    print(f"  Single HS type, point beta, no recession, TM-Q-2D with {n_buckets} p-buckets")
    print(f"  Agent counts: {args.agents}, seeds={len(seeds)}, mCount={mCount}, "
          f"variance_reduction={vr}\n")

    # TM reference (deterministic)
    eco_ref, meta = build_solo_pol_economy(DualAggFiscalType, 1, 0)
    u = getattr(eco_ref.agents[0], 'Urate_normal', 0.044)
    g, p = compute_pLvl_distribution(eco_ref.agents[0], n_points=200, unemployment_rate=u)
    tm_Ep = float(np.dot(p, g))

    print("=" * 75)
    print("  TM-Q-2D (deterministic, with p-buckets)")
    print("=" * 75)
    t0 = time.time()
    tm_mult = tm_q_2d_check_multiplier(eco_ref, meta, mCount, n_buckets=n_buckets)
    print(f"  Check: TM-Q-2D={tm_mult:.4f}  ({time.time()-t0:.1f}s)")

    print(f"\n{'=' * 75}")
    print(f"  MC-P (variance_reduction={vr})")
    print(f"{'=' * 75}")
    print(f"\n{'N':>6} {'MC-P mean':>10} {'MC-P SE':>10} "
          f"{'TM-Q-2D':>10} {'|MC-TM|/SE':>11} {'time':>6}")
    print("-" * 60)

    for N in args.agents:
        seed_P = []
        t0 = time.time()
        for s in seeds:
            mP = mc_multiplier(eco_ref, "Check", meta, s * 100, N, vr, tm_Ep)
            seed_P.append(mP)
        elapsed = time.time() - t0

        n = len(seeds)
        mean_P = float(np.mean(seed_P))
        se_P = float(np.std(seed_P) / np.sqrt(n))
        gap_se = abs(mean_P - tm_mult) / se_P if se_P > 1e-16 else float("nan")
        ok = "PASS" if gap_se <= 3.0 else "FAIL"
        print(f"{N:>6d} {mean_P:10.4f} {se_P:10.4f} "
              f"{tm_mult:10.4f} {gap_se:11.2f} {elapsed:5.0f}s  {ok}")

    print(f"\n  Pass criterion: |MC-P mean - TM-Q-2D| <= 3 * MC-P SE")
    print(f"  Reference: method-parity-map.md (Class D)")


if __name__ == "__main__":
    main()
