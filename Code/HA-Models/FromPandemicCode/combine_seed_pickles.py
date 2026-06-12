"""Combine per-seed welfare6 pickle directories into a single concatenated dir.

Each input directory holds one seed's 12 scenario pickles (produced by
run_welfare6_parallel.py with a different --seed-offset). This script
concatenates per-agent panels along the agent axis and sums aggregate
quantities, producing a combined directory with the same 12-scenario
layout but with N_combined = Σ_seeds N_seed agents per pickle.

Existing post-processing scripts (diag_welfare6_se.py, compute_welfare6_*)
operate on the combined directory unchanged — they just see a bigger N.
The welfare6 SE scales as 1/√S where S is the number of seeds combined.

Usage:
    python combine_seed_pickles.py \
        --input welfare6_scenario_results_Baseline_seed0 \
                welfare6_scenario_results_Baseline_seed1 \
                ... \
        --output welfare6_scenario_results_Baseline_combined
"""
import argparse
import os
import pickle
from pathlib import Path

import numpy as np


SCENARIOS = (
    "base",
    "Check", "UI", "TaxCut",
    "recession", "recessionUI", "recessionCheck", "recessionTaxCut",
    "recession_AD", "recessionUI_AD",
    "recessionCheck_AD", "recessionTaxCut_AD",
)

# Per-agent panels — concatenate along axis 1 (agent axis).
PANEL_KEYS = ("cLvl_all_splurge", "cLvl_all_splurge_bs",
              "pLvl_all_bs", "Mrkv_hist_bs")
# Aggregate per-time series — sum across seeds.
AGG_KEYS = ("AggCons", "AggIncome")
# Scalars — must be identical across seeds (sanity-checked).
SCALAR_KEYS = ("act_T", "Rfree", "CRRA", "parametrization", "scenario")


def combine_scenario(scen, input_dirs, output_dir):
    seeds = []
    for d in input_dirs:
        path = Path(d) / f"{scen}.pkl"
        if not path.exists():
            raise FileNotFoundError(f"missing {path}")
        with open(path, "rb") as f:
            seeds.append(pickle.load(f))

    combined = {"scenario": scen}
    # Sanity-check scalars
    for k in SCALAR_KEYS:
        vals = [s.get(k) for s in seeds]
        if not all(v == vals[0] for v in vals):
            print(f"  warning: scenario {scen} key {k!r} differs across seeds: {vals}")
        combined[k] = vals[0]

    # Concatenate panels
    for k in PANEL_KEYS:
        if k not in seeds[0]:
            continue
        arrs = [np.asarray(s[k]) for s in seeds]
        # All seeds must share T (axis 0)
        T0 = arrs[0].shape[0]
        if not all(a.shape[0] == T0 for a in arrs):
            raise ValueError(f"{scen} {k}: T mismatch across seeds: "
                             f"{[a.shape for a in arrs]}")
        combined[k] = np.concatenate(arrs, axis=1)

    # Sum aggregates
    for k in AGG_KEYS:
        if k not in seeds[0]:
            continue
        combined[k] = sum(np.asarray(s[k]) for s in seeds)

    # Combined runtime = sum (informational)
    combined["runtime_s"] = sum(s.get("runtime_s", 0.0) for s in seeds)
    combined["n_seeds_combined"] = len(seeds)

    out_path = Path(output_dir) / f"{scen}.pkl"
    with open(out_path, "wb") as f:
        pickle.dump(combined, f, protocol=pickle.HIGHEST_PROTOCOL)
    N = combined["cLvl_all_splurge"].shape[1]
    return N


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", nargs="+", required=True,
                    help="One or more per-seed pickle directories.")
    ap.add_argument("--output", required=True,
                    help="Combined output directory (created if missing).")
    args = ap.parse_args()

    os.makedirs(args.output, exist_ok=True)

    print(f"Combining {len(args.input)} seed dirs into {args.output}/")
    for d in args.input:
        print(f"  {d}")
    print()

    for scen in SCENARIOS:
        try:
            N = combine_scenario(scen, args.input, args.output)
            print(f"  {scen:25s}  N={N}  ({len(args.input)} seeds)")
        except FileNotFoundError as e:
            print(f"  {scen:25s}  SKIP — {e}")


if __name__ == "__main__":
    main()
