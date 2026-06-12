#!/usr/bin/env python
"""extract_mc_tm_multipliers.py — Extract MC and TM-a NPV multipliers from
sim_method='both' pickled results, side-by-side.

Used for Phase F-0 of plans/20260504-1700h_phase_F_mfmc_tm_a_control_variate.md
to measure G_MC,shock vs G_TM,shock and the bias structure.

Reads pickled results from Tables/<Parametrization>/Figures/<Parametrization>/
(written by Simulate.py with _MC and _TM suffixes when sim_method='both').

Usage:
    python extract_mc_tm_multipliers.py [Reduced_Run|Baseline|Smoke_Test]
"""

from __future__ import annotations

import os
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARAM = sys.argv[1] if len(sys.argv) > 1 else "Reduced_Run"
FIGS = HERE / "Figures" / PARAM


def load(name):
    """Load a pickle saved by save_as_pickle (which uses .csv extension)."""
    fn = FIGS / f"{name}.csv"
    if not fn.exists():
        return None
    with open(fn, "rb") as f:
        return pickle.load(f)


def npv_multiplier(base, alt, gov_spending):
    """NPV multiplier = ΔNPV_AggCons / Gov_Spending (passed in pre-computed,
    typically from the NON-AD pair — the policy expenditure is fixed to the
    no-AD spending baseline per Output_Results convention)."""
    if base is None or alt is None or gov_spending is None:
        return None
    add_cons = alt["NPV_AggCons"] - base["NPV_AggCons"]
    return add_cons / gov_spending


def npv_addinc(base, alt):
    """Compute policy expenditure = ΔNPV_AggIncome from base and alternative
    (typically NON-AD versions, used as the multiplier denominator)."""
    if base is None or alt is None:
        return None
    return alt["NPV_AggIncome"] - base["NPV_AggIncome"]


def main():
    print(f"# MC vs TM-a NPV Multipliers — {PARAM} scope")
    print(f"# Pickle dir: {FIGS}")
    print()

    # Note: base MC is saved as 'base_results' (no _MC suffix per Simulate.py:612);
    # base TM gets '_TM' suffix when sim_method='both' (line 631).
    base_mc = load("base_results")
    base_tm = load("base_results_TM")
    if base_mc is None or base_tm is None:
        print(f"ERROR: missing base_results_MC ({base_mc is not None}) or "
              f"base_results_TM ({base_tm is not None}). Did the run use "
              f"sim_method='both'?")
        return 1

    rec_mc = load("recession_results_MC")
    rec_tm = load("recession_results_TM")
    rec_ad_mc = load("recession_results_AD_MC")
    rec_ad_tm = load("recession_results_AD_TM")
    rec_1ad_mc = load("recession_results_firstRoundAD_MC")
    rec_1ad_tm = load("recession_results_firstRoundAD_TM")

    # Per-shock-type alternatives
    shocks = ["Check", "UI", "TaxCut"]

    print(f"{'Shock':<10} {'MC NPV (with AD)':>18} {'TM NPV (with AD)':>18} "
          f"{'b = MC − TM':>14} {'b/MC %':>10}")
    print("-" * 76)

    bias_data = {}

    for shock in shocks:
        # recession + shock: need recession_<Shock>_results_AD_*
        # The shock_type for recession variants is e.g. 'recessionCheck'
        rs_alt_mc = load(f"recession{shock}_results_MC") or load(f"recession_{shock}_results_MC")
        rs_alt_tm = load(f"recession{shock}_results_TM") or load(f"recession_{shock}_results_TM")
        rs_alt_ad_mc = load(f"recession{shock}_results_AD_MC") or load(f"recession_{shock}_results_AD_MC")
        rs_alt_ad_tm = load(f"recession{shock}_results_AD_TM") or load(f"recession_{shock}_results_AD_TM")

        if rs_alt_ad_mc is None or rs_alt_ad_tm is None or rec_ad_mc is None or rec_ad_tm is None:
            print(f"{shock:<10}  (missing AD pickles for {shock} - skipping)")
            continue

        # Gov spending = ΔNPV_AggIncome from NON-AD (fixed policy budget)
        gov_mc = npv_addinc(rec_mc, rs_alt_mc)
        gov_tm = npv_addinc(rec_tm, rs_alt_tm)
        if gov_mc is None or gov_tm is None:
            print(f"{shock:<10}  (missing non-AD income arrays for spending baseline)")
            continue

        # NPV multiplier returns a per-period array; take last period (10y horizon)
        # per Output_Results.py convention.
        m_mc_arr = npv_multiplier(rec_ad_mc, rs_alt_ad_mc, gov_mc)
        m_tm_arr = npv_multiplier(rec_ad_tm, rs_alt_ad_tm, gov_tm)
        if m_mc_arr is None or m_tm_arr is None:
            print(f"{shock:<10}  (NPV_AggCons missing)")
            continue
        m_mc = float(m_mc_arr[-1])
        m_tm = float(m_tm_arr[-1])

        b = m_mc - m_tm
        b_pct = 100.0 * b / m_mc if abs(m_mc) > 1e-9 else float("nan")
        print(f"{shock:<10} {m_mc:>18.4f} {m_tm:>18.4f} {b:>+14.4f} {b_pct:>+10.2f}")
        bias_data[shock] = (m_mc, m_tm, b, b_pct)

    print()
    if bias_data:
        biases = [b for _, _, b, _ in bias_data.values()]
        print(f"Bias summary: range = [{min(biases):+.4f}, {max(biases):+.4f}], "
              f"spread = {max(biases) - min(biases):.4f}")
        if max(biases) - min(biases) < 0.05:
            print("  → Bias is STABLE across shock_types (spread < 0.05). "
                  "Adaptation B (cross-shock-type bias borrowing) is VIABLE.")
        else:
            print("  → Bias is UNSTABLE across shock_types (spread ≥ 0.05). "
                  "Adaptation B is RISKY; consider Adaptation C (antithetic) instead.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
