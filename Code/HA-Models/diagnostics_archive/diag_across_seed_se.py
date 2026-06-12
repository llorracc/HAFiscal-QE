"""Compare two SE estimators for multi-seed combined welfare6:

(A) Pooled bootstrap: resample agents from the combined N=S·N_per_seed panel
    with replacement, recompute W^U per resample, take SD.  This is what
    diag_welfare6_se.py and compute_welfare6_control_variate.py use.

(B) Across-seed SD: compute W^U separately from each seed's 12-scenario
    panels, take the SD of the S per-seed W^U values, divide by √S.

For iid agents with deterministic NPV_cost, (A) and (B) agree.  For
rare-event cells where NPV_cost and Σ_i A_i covary (e.g., UI Rec=0,
where one extreme-pLvl agent can drive 40% of |ΣA_i|), (A) is inflated
while (B) reflects the true run-to-run variability of the estimator.

Usage:
    python diag_across_seed_se.py --seed-dirs welfare6_scenario_results_Baseline_seed0 \\
                                               welfare6_scenario_results_Baseline_seed1 \\
                                               welfare6_scenario_results_Baseline_seed2 \\
                                               welfare6_scenario_results_Baseline_seed3
"""
import argparse
import pickle
from pathlib import Path
import numpy as np

R, T, CRRA = 1.01, 40, 2.0
discount = R ** (-np.arange(T))

CELLS = [
    ("Check,  Rec=0, AD=0 ", "Check",              "base",          "base", "Check",              "base"),
    ("UI,     Rec=0, AD=0 ", "UI",                 "base",          "base", "UI",                 "base"),
    ("TaxCut, Rec=0, AD=0 ", "TaxCut",             "base",          "base", "TaxCut",             "base"),
    ("Check,  Rec=1, AD=0 ", "recessionCheck",     "recession",     "base", "recessionCheck",     "recession"),
    ("UI,     Rec=1, AD=0 ", "recessionUI",        "recession",     "base", "recessionUI",        "recession"),
    ("TaxCut, Rec=1, AD=0 ", "recessionTaxCut",    "recession",     "base", "recessionTaxCut",    "recession"),
    ("Check,  Rec=1, AD=1 ", "recessionCheck_AD",  "recession_AD",  "base", "recessionCheck",     "recession"),
    ("UI,     Rec=1, AD=1 ", "recessionUI_AD",     "recession_AD",  "base", "recessionUI",        "recession"),
    ("TaxCut, Rec=1, AD=1 ", "recessionTaxCut_AD", "recession_AD",  "base", "recessionTaxCut",    "recession"),
]


def compute_cell_WU(pol, none, base, pol_cost, none_cost):
    """Paper-consistent W_6 (Welfare.py:277/284): fixed AD=0 NPV denom."""
    c_p = np.asarray(pol["cLvl_all_splurge"])
    c_n = np.asarray(none["cLvl_all_splurge"])
    c_b = np.asarray(base["cLvl_all_splurge"])
    ap  = np.asarray(pol_cost["AggIncome"])
    an  = np.asarray(none_cost["AggIncome"])
    acp = np.asarray(pol_cost["AggCons"])
    acn = np.asarray(none_cost["AggCons"])
    N = min(c_p.shape[1], c_n.shape[1], c_b.shape[1])
    du = (c_p[:, :N]**(1-CRRA) - c_n[:, :N]**(1-CRRA))/(1-CRRA)
    mu = c_b[:, :N]**(-CRRA)
    A = ((du / mu) * discount[:, None]).sum(axis=0)
    NPV_cost = float(((ap - an) * discount).sum())
    NPV_dc   = float(((acp - acn) * discount).sum())
    if NPV_cost == 0:
        return float("nan"), 0, N
    W_U = float(A.sum() / NPV_cost)
    W_B = (NPV_cost - NPV_dc) / NPV_cost
    return W_U + W_B, NPV_cost, N


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-dirs", nargs="+", required=True,
                    help="Per-seed pickle directories.")
    args = ap.parse_args()
    S = len(args.seed_dirs)

    # Per-seed scenarios
    per_seed = []
    for d in args.seed_dirs:
        scen = {}
        for p in Path(d).glob("*.pkl"):
            with open(p, "rb") as f:
                scen[p.stem] = pickle.load(f)
        per_seed.append(scen)

    print(f"Across-seed W_6 analysis (S={S} seeds, paper formula Welfare.py:277/284)")
    print()
    print(f"{'cell':22s} {'W_6_mean':>9s} {'per-seed W_6':>36s}  "
          f"{'SD':>7s} {'SE':>7s} {'rel.SE':>7s}")
    print("-" * 95)
    for label, pol_k, none_k, base_k, pol_cost_k, none_cost_k in CELLS:
        per_seed_WU = []
        for seed_scen in per_seed:
            if not all(k in seed_scen for k in (pol_k, none_k, base_k, pol_cost_k, none_cost_k)):
                per_seed_WU.append(float("nan"))
                continue
            WU, _, _ = compute_cell_WU(seed_scen[pol_k], seed_scen[none_k], seed_scen[base_k],
                                       seed_scen[pol_cost_k], seed_scen[none_cost_k])
            per_seed_WU.append(WU)
        arr = np.array(per_seed_WU)
        mean_WU = arr.mean()
        sd_WU   = arr.std(ddof=1) if S > 1 else 0.0
        se_mean = sd_WU / np.sqrt(S) if S > 1 else float("nan")
        rel_se  = se_mean / abs(mean_WU) if mean_WU else float("nan")
        vals_str = " ".join(f"{v:7.4f}" for v in arr[:5])  # show up to 5 per-seed
        if S > 5:
            vals_str += " ..."
        print(f"{label:22s} {mean_WU:9.4f}  {vals_str:>35s}  "
              f"{sd_WU:7.4f} {se_mean:7.4f} {rel_se*100:6.2f}%")

    print()
    print("SD  = unbiased SD across the S per-seed W^U values")
    print("SE  = SD / √S = standard error of the across-seed mean")
    print("rel.SE = SE / |mean W^U|")


if __name__ == "__main__":
    main()
