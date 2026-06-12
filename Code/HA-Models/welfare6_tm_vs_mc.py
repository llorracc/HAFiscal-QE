#!/usr/bin/env python
"""Phase C.1 — unified TM-vs-MC welfare-6 comparison driver.

Reads a TM-arm pickle (welfare6_tm.py output) and an MC-arm scenario directory
(run_welfare6_parallel.py output), enforces the matched-pair guard, and emits the
9-cell TM | MC | bias(MC-TM) | %bias | SE(MC) comparison (the cross-check) via
welfare6_hybrid_table.write_tm_vs_mc_comparison.

Robust to a partial MC set (e.g. --skip-ui): a missing scenario -> NaN cell, not a
crash. The MC arm self-stamps its regime in each pickle; the TM regime is the
process regime (the driver runs under the same flags the TM arm did, in the common
one-regime case). The guard refuses to compare mismatched regimes (BUG-051).

Usage:
  python welfare6_tm_vs_mc.py --tm-pickle <tm.pkl> --mc-dir <mc_scenario_dir> \
      --out <comparison.txt>
"""
import argparse
import os
import pickle
import sys

_FPC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FromPandemicCode")
sys.path.insert(0, _FPC)

from welfare6_hybrid_table import (write_tm_vs_mc_comparison,   # noqa: E402
                                   capture_welfare6_regime)


def read_tm_cells(tm_pickle):
    """The 9-cell dict from a welfare6_tm.py pickle (per-cell analytical TM)."""
    with open(tm_pickle, "rb") as f:
        d = pickle.load(f)
    # 'welfare6_cells' is the canonical primary (= the bucket-aware aggregator,
    # which Check REQUIRES — Check is income-dependent, so the per-cell formula
    # is wrong for it). Prefer it; fall back to per-cell only if absent.
    for key in ("welfare6_cells", "welfare6_cells_bucket", "welfare6_cells_percell"):
        if isinstance(d.get(key), dict) and d[key]:
            return d[key], key, d.get("regime")
    raise KeyError(f"no welfare6 cells in {tm_pickle}; top-level keys={list(d)}")


def read_mc_cells(mc_dir):
    """The 9-cell dict from an MC scenario directory. Reuses the canonical
    welfare6_mc per-cell formula (run_welfare6_parallel.compute_welfare6_table),
    but tolerates missing scenario pickles (-> NaN) so --skip-ui dirs work."""
    from run_welfare6_parallel import welfare6_mc, ALL_SCENARIOS
    loaded = {}
    for s in ALL_SCENARIOS:
        p = os.path.join(mc_dir, f"{s}.pkl")
        if os.path.exists(p):
            with open(p, "rb") as f:
                loaded[s] = pickle.load(f)
    if "base" not in loaded:
        raise FileNotFoundError(f"MC dir {mc_dir} has no base.pkl")
    base = loaded["base"]
    act_T, Rfree, CRRA = base["act_T"], base["Rfree"], base["CRRA"]
    regime = base.get("regime")
    nan = float("nan")

    def w6(pol, none, cost_pol=None, cost_none=None):
        if pol not in loaded or none not in loaded:
            return nan
        if (cost_pol and cost_pol not in loaded) or (cost_none and cost_none not in loaded):
            return nan
        return welfare6_mc(loaded[pol], loaded[none], base, act_T, Rfree, CRRA,
                           cost_pol_r=loaded.get(cost_pol),
                           cost_none_r=loaded.get(cost_none))

    cells = {
        "check_norec": w6("Check", "base"),
        "ui_norec": w6("UI", "base"),
        "taxcut_norec": w6("TaxCut", "base"),
        "check_rec": w6("recessionCheck", "recession"),
        "ui_rec": w6("recessionUI", "recession"),
        "taxcut_rec": w6("recessionTaxCut", "recession"),
        "check_rec_AD": w6("recessionCheck_AD", "recession_AD",
                           "recessionCheck", "recession"),
        "ui_rec_AD": w6("recessionUI_AD", "recession_AD",
                        "recessionUI", "recession"),
        "taxcut_rec_AD": w6("recessionTaxCut_AD", "recession_AD",
                            "recessionTaxCut", "recession"),
    }
    return cells, regime, sorted(loaded)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tm-pickle", required=True)
    p.add_argument("--mc-dir", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    tm_cells, tm_key, tm_stamp = read_tm_cells(os.path.abspath(args.tm_pickle))
    print(f"TM cells from key '{tm_key}' ({len(tm_cells)} cells)")
    mc_cells, mc_regime, mc_have = read_mc_cells(os.path.abspath(args.mc_dir))
    print(f"MC scenarios present: {mc_have}")

    # TM regime: the stamp if welfare6_tm.py wrote one, else the process regime
    # (the driver runs under the same flags the TM arm did, one-regime case).
    tm_regime = tm_stamp or capture_welfare6_regime()
    write_tm_vs_mc_comparison(tm_cells, mc_cells, os.path.abspath(args.out),
                              tm_regime=tm_regime, mc_regime=mc_regime, mc_se=None)


if __name__ == "__main__":
    main()
