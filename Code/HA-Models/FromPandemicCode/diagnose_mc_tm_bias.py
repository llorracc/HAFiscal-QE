#!/usr/bin/env python
"""diagnose_mc_tm_bias.py — D-1 + D-1.5 of MC-vs-TM-a bias mechanism inquiry.

D-1: compare base-period (no shock, no recession) MC vs TM-a aggregates.
     If they match, bias is in shock RESPONSE only. If they differ, even
     the steady states disagree.

D-1.5: compare MC-vs-TM-a residuals at 1st-round-AD vs full-AD. If the
     1st-round residual is small but full-AD residual is 13%, the AD
     fixed-point loop is amplifying small per-iteration discrepancies.

Reads pickles from H-0 treatment runs (Reduced_Run_h0_treat_seed{0,100,200}/).
"""

from __future__ import annotations

import pickle
import numpy as np
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM = "treat"
SEEDS = [0, 100, 200]
SHOCKS = ["Check", "TaxCut"]


def load(seed, name):
    fn = HERE / "Figures" / f"Reduced_Run_h0_{ARM}_seed{seed}" / f"{name}.csv"
    if not fn.exists():
        return None
    with open(fn, "rb") as f:
        return pickle.load(f)


def field_or_nan(d, k):
    if d is None or k not in d:
        return float("nan")
    v = d[k]
    if hasattr(v, "__len__") and len(v) > 0:
        return float(v[-1])
    return float(v)


def compare_d1():
    """D-1: base-period levels MC vs TM-a."""
    print("=" * 78)
    print("D-1: BASE-PERIOD LEVELS (no shock, no recession)")
    print("=" * 78)
    print()

    base_mc = load(0, "base_results")
    base_tm = load(0, "base_results_TM")
    if base_mc is None or base_tm is None:
        print("ERROR: base pickles missing"); return
    print(f"Pickle keys (base_MC): {sorted(base_mc.keys())[:8]}…")
    print(f"Pickle keys (base_TM): {sorted(base_tm.keys())[:8]}…")
    print()

    # Find shared scalar fields
    shared = sorted(set(base_mc.keys()) & set(base_tm.keys()))
    print(f"{'Field':<25} {'MC last':>14} {'TM-a last':>14} {'rel diff %':>12}")
    print("-" * 70)
    for k in shared:
        mc_v = field_or_nan(base_mc, k)
        tm_v = field_or_nan(base_tm, k)
        if not (np.isfinite(mc_v) and np.isfinite(tm_v)):
            continue
        if abs(mc_v) > 1e-9:
            rel = 100.0 * (mc_v - tm_v) / mc_v
        else:
            rel = float("nan") if abs(tm_v) > 1e-9 else 0.0
        flag = " ←" if abs(rel) > 1.0 else ""
        print(f"{k:<25} {mc_v:>14.6g} {tm_v:>14.6g} {rel:>+12.4f}%{flag}")
    print()


def npv_mult(base, alt, gov):
    if base is None or alt is None or gov is None:
        return float("nan")
    add_cons = alt["NPV_AggCons"] - base["NPV_AggCons"]
    arr = add_cons / gov
    return float(arr[-1])


def npv_addinc(base, alt):
    if base is None or alt is None:
        return None
    return alt["NPV_AggIncome"] - base["NPV_AggIncome"]


def compare_d15():
    """D-1.5: MC vs TM-a residual at 1st-round-AD vs full-AD."""
    print("=" * 78)
    print("D-1.5: 1ST-ROUND-AD vs FULL-AD MC-vs-TM-a RESIDUALS")
    print("=" * 78)
    print()
    print("If 1st-round residual is small but full-AD residual is large (~13%),")
    print("the AD loop amplifies a small per-iteration discrepancy into a big bias.")
    print()

    print(f"{'Seed':>4} {'Shock':<8} "
          f"{'1AD MC':>10} {'1AD TMa':>10} {'1AD resid%':>12} "
          f"{'AD MC':>10} {'AD TMa':>10} {'AD resid%':>12}")
    print("-" * 90)

    summary = {}
    for seed in SEEDS:
        rec_mc = load(seed, "recession_results_MC")
        rec_tm = load(seed, "recession_results_TM")
        rec_1ad_mc = load(seed, "recession_results_firstRoundAD_MC")
        rec_1ad_tm = load(seed, "recession_results_firstRoundAD_TM")
        rec_ad_mc = load(seed, "recession_results_AD_MC")
        rec_ad_tm = load(seed, "recession_results_AD_TM")
        if any(x is None for x in [rec_mc, rec_tm, rec_ad_mc, rec_ad_tm, rec_1ad_mc, rec_1ad_tm]):
            print(f"{seed:>4} (missing recession-base pickles)")
            continue

        for shock in SHOCKS:
            rs_mc = load(seed, f"recession{shock}_results_MC") or load(seed, f"recession_{shock}_results_MC")
            rs_tm = load(seed, f"recession{shock}_results_TM") or load(seed, f"recession_{shock}_results_TM")
            rs_1ad_mc = load(seed, f"recession{shock}_results_firstRoundAD_MC")
            rs_1ad_tm = load(seed, f"recession{shock}_results_firstRoundAD_TM")
            rs_ad_mc = load(seed, f"recession{shock}_results_AD_MC") or load(seed, f"recession_{shock}_results_AD_MC")
            rs_ad_tm = load(seed, f"recession{shock}_results_AD_TM") or load(seed, f"recession_{shock}_results_AD_TM")
            if any(x is None for x in [rs_mc, rs_tm, rs_1ad_mc, rs_1ad_tm, rs_ad_mc, rs_ad_tm]):
                print(f"{seed:>4} {shock:<8} (missing)")
                continue

            gov_mc = npv_addinc(rec_mc, rs_mc)
            gov_tm = npv_addinc(rec_tm, rs_tm)

            # 1st-round-AD multipliers
            m_1ad_mc = npv_mult(rec_1ad_mc, rs_1ad_mc, gov_mc)
            m_1ad_tm = npv_mult(rec_1ad_tm, rs_1ad_tm, gov_tm)
            r_1ad = 100.0 * (m_1ad_mc - m_1ad_tm) / m_1ad_mc if abs(m_1ad_mc) > 1e-9 else float("nan")

            # full-AD multipliers
            m_ad_mc = npv_mult(rec_ad_mc, rs_ad_mc, gov_mc)
            m_ad_tm = npv_mult(rec_ad_tm, rs_ad_tm, gov_tm)
            r_ad = 100.0 * (m_ad_mc - m_ad_tm) / m_ad_mc if abs(m_ad_mc) > 1e-9 else float("nan")

            print(f"{seed:>4} {shock:<8} "
                  f"{m_1ad_mc:>10.4f} {m_1ad_tm:>10.4f} {r_1ad:>+12.3f}% "
                  f"{m_ad_mc:>10.4f} {m_ad_tm:>10.4f} {r_ad:>+12.3f}%")
            summary.setdefault(shock, []).append((r_1ad, r_ad))

    print()
    print("Per-shock residual magnification by AD loop:")
    for shock, vals in summary.items():
        if not vals:
            continue
        r1 = sum(v[0] for v in vals) / len(vals)
        ra = sum(v[1] for v in vals) / len(vals)
        if abs(r1) > 1e-9:
            mag = ra / r1
            print(f"  {shock:<8} mean 1AD resid = {r1:+7.3f}%   "
                  f"mean AD resid = {ra:+7.3f}%   magnification = {mag:.2f}x")
        else:
            print(f"  {shock:<8} mean 1AD resid = {r1:+7.3f}%   "
                  f"mean AD resid = {ra:+7.3f}%   (1AD ~0, no magnification ratio)")
    print()
    print("Interpretation:")
    print("  magnification ≈ 1: AD loop is faithful; bias enters at 1st step")
    print("  magnification >> 1: AD loop amplifies per-iter discrepancy → mechanism C")
    print("  magnification < 0 or weird: more complex non-linear AD dynamics")


if __name__ == "__main__":
    compare_d1()
    compare_d15()
