"""Generate LaTeX table of MC welfare6 standard errors (separate from welfare6.tex).

Uses across-seed SE — treats each seed's W_6 as a replicate experiment,
computes SD across seeds and SE = SD/√S.  Paper-consistent formula from
Welfare.py:277/284 (fixed AD=0 NPV_AddInc denominator).

The pooled-bootstrap SE from diag_welfare6_se.py is inflated on rare-
event cells (UI Rec=0 in particular) by individual high-pLvl outliers
appearing in bootstrap resamples with variable multiplicity; the
across-seed SE reflects actual run-to-run variability of the W_6
estimator and is the right number for paper-grade uncertainty.

Usage:
    python compute_welfare6_se_table.py \\
        --seed-dirs welfare6_scenario_results_Baseline_seed{0,1,2,3} \\
        --out Tables/Baseline_parallel/welfare6_SE.tex
"""
import argparse
import pickle
from pathlib import Path
import numpy as np

R, T, CRRA = 1.01, 40, 2.0
DISC = R ** (-np.arange(T))

# Paper formula: (pol, none, base, pol_cost, none_cost) — pol_cost/none_cost
# always AD=0 pair (Welfare.py:277/284).
CELLS = [
    ("Rec=0, AD=0", "Check",
     [("Check", "Check", "base",        "base", "Check",           "base"),
      ("UI",    "UI",    "base",        "base", "UI",              "base"),
      ("TaxCut","TaxCut","base",        "base", "TaxCut",          "base")]),
    ("Rec=1, AD=0", "Check",
     [("Check", "recessionCheck",  "recession",    "base", "recessionCheck",  "recession"),
      ("UI",    "recessionUI",     "recession",    "base", "recessionUI",     "recession"),
      ("TaxCut","recessionTaxCut", "recession",    "base", "recessionTaxCut", "recession")]),
    ("Rec=1, AD=1", "Check",
     [("Check", "recessionCheck_AD",  "recession_AD", "base", "recessionCheck",  "recession"),
      ("UI",    "recessionUI_AD",     "recession_AD", "base", "recessionUI",     "recession"),
      ("TaxCut","recessionTaxCut_AD", "recession_AD", "base", "recessionTaxCut", "recession")]),
]


def compute_cell_W6(pol, none, base, pol_cost, none_cost):
    c_p = np.asarray(pol["cLvl_all_splurge"])
    c_n = np.asarray(none["cLvl_all_splurge"])
    c_b = np.asarray(base["cLvl_all_splurge"])
    ip  = np.asarray(pol_cost["AggIncome"])
    i_n = np.asarray(none_cost["AggIncome"])
    cp  = np.asarray(pol_cost["AggCons"])
    cn  = np.asarray(none_cost["AggCons"])
    N = min(c_p.shape[1], c_n.shape[1], c_b.shape[1])
    du = (c_p[:, :N]**(1-CRRA) - c_n[:, :N]**(1-CRRA)) / (1-CRRA)
    mu = c_b[:, :N]**(-CRRA)
    A = ((du / mu) * DISC[:, None]).sum(axis=0)
    NPV_cost = float(((ip - i_n) * DISC).sum())
    NPV_dc   = float(((cp - cn) * DISC).sum())
    if NPV_cost == 0:
        return float("nan")
    return float(A.sum() / NPV_cost + (NPV_cost - NPV_dc) / NPV_cost)


def load_seed(seed_dir):
    """Return dict scenario → pickle contents for one seed directory."""
    return {p.stem: pickle.load(open(p, "rb"))
            for p in Path(seed_dir).glob("*.pkl")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-dirs", nargs="+", required=True)
    ap.add_argument("--out", required=True,
                    help="Output .tex file path.")
    ap.add_argument("--format", choices=("abs", "pct", "both"), default="both",
                    help="Report absolute SE, relative SE (%% of W_6), or both.")
    args = ap.parse_args()
    S = len(args.seed_dirs)
    if S < 2:
        raise SystemExit("Need at least 2 seed directories for across-seed SE.")

    # Load all seeds
    per_seed = [load_seed(d) for d in args.seed_dirs]

    # Per-cell: compute per-seed W_6, then mean/SD/SE
    row_data = []  # list of (row_label, {policy: (mean, SE, rel_SE)})
    for row_label, _, cells in CELLS:
        cell_results = {}
        for policy, pol_k, none_k, base_k, pol_cost_k, none_cost_k in cells:
            per_seed_W6 = []
            for seed_sc in per_seed:
                if not all(k in seed_sc for k in (pol_k, none_k, base_k, pol_cost_k, none_cost_k)):
                    per_seed_W6.append(float("nan"))
                    continue
                w6 = compute_cell_W6(seed_sc[pol_k], seed_sc[none_k], seed_sc[base_k],
                                     seed_sc[pol_cost_k], seed_sc[none_cost_k])
                per_seed_W6.append(w6)
            arr = np.array(per_seed_W6)
            mean = float(np.nanmean(arr))
            sd   = float(np.nanstd(arr, ddof=1))
            se   = sd / np.sqrt(np.sum(~np.isnan(arr)))
            rel_se = se / abs(mean) if mean else float("nan")
            cell_results[policy] = (mean, se, rel_se)
        row_data.append((row_label, cell_results))

    # Emit LaTeX
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(r"\begin{tabular}{@{}lccc@{}}")
    lines.append(r"\toprule")
    lines.append(r"                          & Stimulus check      & UI extension    & Tax cut    \\  \midrule")

    def _cell_str(mean, se, rel_se):
        if args.format == "abs":
            return f"{se:.3f}"
        if args.format == "pct":
            return f"{rel_se*100:.2f}\\%"
        return f"{se:.3f} ({rel_se*100:.2f}\\%)"

    for row_label, cell_results in row_data:
        c = cell_results
        line = (f"$\\mathrm{{SE}}(\\mathcal{{W}}, \\text{{{row_label}}})$ "
                f"& {_cell_str(*c['Check'])}  "
                f"& {_cell_str(*c['UI'])}  "
                f"& {_cell_str(*c['TaxCut'])}     \\\\")
        lines.append(line)
    lines[-1] = lines[-1].replace(r"\\", r"\\ \bottomrule")
    lines.append(r"\end{tabular}")

    out_path.write_text("\n".join(lines) + "\n")

    # Also print a human-readable summary
    print(f"Wrote {out_path}")
    print(f"Seeds used: S = {S}")
    print(f"Format: {args.format}")
    print()
    print(f"{'row':20s} {'policy':8s} {'mean':>8s} {'SE':>8s} {'rel SE':>8s}")
    for row_label, cell_results in row_data:
        for policy, (mean, se, rel_se) in cell_results.items():
            print(f"{row_label:20s} {policy:8s} {mean:8.4f} {se:8.4f} {rel_se*100:7.2f}%")


if __name__ == "__main__":
    main()
