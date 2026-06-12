"""Paper-formula W_6 side-by-side comparison: HAFiscal-QE vs current vs splurge_old.

Reads from two pickle directories (current + splurge_old) and writes a
comparison table to history/20260420_ui_recession_gap/splurge_comparison.md
with per-cell gap attribution.

Usage:
    python compare_splurge_old_vs_current.py \\
        --current welfare6_scenario_results_Baseline_seed0 \\
        --splurge_old welfare6_scenario_results_Baseline_splurge_old \\
        [--label "Track A"]
"""
import argparse
import pickle
from pathlib import Path
import numpy as np

R, T, CRRA = 1.01, 40, 2.0
DISC = R ** (-np.arange(T))

CELLS = [
    # (label, pol, none, base, pol_cost, none_cost, HAFiscal_QE)
    ("Check,  Rec=0, AD=0 ", "Check",              "base",          "base", "Check",              "base",       0.96),
    ("UI,     Rec=0, AD=0 ", "UI",                 "base",          "base", "UI",                 "base",       0.85),
    ("TaxCut, Rec=0, AD=0 ", "TaxCut",             "base",          "base", "TaxCut",             "base",       0.99),
    ("Check,  Rec=1, AD=0 ", "recessionCheck",     "recession",     "base", "recessionCheck",     "recession",  1.00),
    ("UI,     Rec=1, AD=0 ", "recessionUI",        "recession",     "base", "recessionUI",        "recession",  1.82),
    ("TaxCut, Rec=1, AD=0 ", "recessionTaxCut",    "recession",     "base", "recessionTaxCut",    "recession",  0.98),
    ("Check,  Rec=1, AD=1 ", "recessionCheck_AD",  "recession_AD",  "base", "recessionCheck",     "recession",  1.35),
    ("UI,     Rec=1, AD=1 ", "recessionUI_AD",     "recession_AD",  "base", "recessionUI",        "recession",  2.13),
    ("TaxCut, Rec=1, AD=1 ", "recessionTaxCut_AD", "recession_AD",  "base", "recessionTaxCut",    "recession",  1.11),
]


def compute_w6(d_pol, d_none, d_base, d_pol_cost, d_none_cost):
    c_p = np.asarray(d_pol["cLvl_all_splurge"])
    c_n = np.asarray(d_none["cLvl_all_splurge"])
    c_b = np.asarray(d_base["cLvl_all_splurge"])
    ip  = np.asarray(d_pol_cost["AggIncome"])
    i_n = np.asarray(d_none_cost["AggIncome"])
    cp  = np.asarray(d_pol_cost["AggCons"])
    cn  = np.asarray(d_none_cost["AggCons"])
    N = min(c_p.shape[1], c_n.shape[1], c_b.shape[1])
    du = (c_p[:, :N]**(1 - CRRA) - c_n[:, :N]**(1 - CRRA)) / (1 - CRRA)
    mu = c_b[:, :N]**(-CRRA)
    A = ((du / mu) * DISC[:, None]).sum(axis=0)
    NPV_c = float(((ip - i_n) * DISC).sum())
    NPV_dc = float(((cp - cn) * DISC).sum())
    if NPV_c == 0:
        return float("nan"), float("nan"), float("nan")
    W_U = A.sum() / NPV_c
    W_B = (NPV_c - NPV_dc) / NPV_c
    return W_U + W_B, W_U, W_B


def load_dir(path):
    scen = {}
    for f in Path(path).glob("*.pkl"):
        scen[f.stem] = pickle.load(open(f, "rb"))
    return scen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", required=True)
    ap.add_argument("--splurge_old", required=True)
    ap.add_argument("--label", default="Track A")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    sc_cur = load_dir(args.current)
    sc_old = load_dir(args.splurge_old)

    lines = [f"# Splurge formulation comparison ({args.label})",
             "",
             f"Current: `{args.current}`",
             f"splurge_old (HAFISCAL_SPLURGE_OLD=1): `{args.splurge_old}`",
             "",
             f"Paper-formula W_6 (Welfare.py:277/284 convention, fixed AD=0 NPV_AddInc).",
             "",
             f"| Cell | HAFiscal-QE | Current | splurge_old | Δ (old − cur) | Gap closed |",
             f"|---|---:|---:|---:|---:|---:|"]

    rows = []
    for label, pol_k, none_k, base_k, pol_cost_k, none_cost_k, qe in CELLS:
        cur_ok  = all(k in sc_cur for k in (pol_k, none_k, base_k, pol_cost_k, none_cost_k))
        old_ok  = all(k in sc_old for k in (pol_k, none_k, base_k, pol_cost_k, none_cost_k))
        if not cur_ok or not old_ok:
            lines.append(f"| {label} | {qe:.2f} | — | — | — | — |")
            continue
        w6_cur, _, _ = compute_w6(sc_cur[pol_k], sc_cur[none_k], sc_cur[base_k],
                                  sc_cur[pol_cost_k], sc_cur[none_cost_k])
        w6_old, _, _ = compute_w6(sc_old[pol_k], sc_old[none_k], sc_old[base_k],
                                  sc_old[pol_cost_k], sc_old[none_cost_k])
        d = w6_old - w6_cur
        gap_cur = qe - w6_cur
        gap_old = qe - w6_old
        if abs(gap_cur) > 1e-9:
            closed_frac = 1.0 - gap_old / gap_cur
        else:
            closed_frac = float("nan")
        lines.append(f"| {label.strip()} | {qe:.3f} | {w6_cur:.3f} | {w6_old:.3f} | "
                     f"{d:+.3f} | {closed_frac*100:+.0f}% |")
        rows.append({"label": label, "qe": qe, "cur": w6_cur, "old": w6_old, "closed": closed_frac})

    # UI-specific verdict
    ui_cells = [r for r in rows if "UI" in r["label"] and "Rec=1" in r["label"]]
    lines.append("")
    lines.append("## Verdict")
    if ui_cells:
        ui_closed = [r["closed"] for r in ui_cells if not np.isnan(r["closed"])]
        if ui_closed:
            avg_closed = np.mean(ui_closed) * 100
            lines.append(f"- UI recession cells gap closure under splurge_old: "
                         f"{', '.join(f'{c*100:+.0f}%' for c in ui_closed)}  (mean {avg_closed:+.0f}%)")
            if avg_closed > 70:
                lines.append("- **H1 CONFIRMED**: splurge-in-budget is the main driver of the UI-recession gap.")
            elif avg_closed > 40:
                lines.append("- **H1 PARTIALLY CONFIRMED**: splurge-in-budget explains part of the gap.")
                lines.append("  Recommend Track A' (splurge_old + master β) to disambiguate.")
            elif avg_closed > -10:
                lines.append("- **H1 MOSTLY RULED OUT**: gap persists under splurge_old.")
                lines.append("  Proceed to Track C (HARK 0.14.1 → 0.17.0 upgrade investigation).")
            else:
                lines.append("- **H1 STRONGLY RULED OUT**: gap *grew* under splurge_old.")
                lines.append("  Proceed to Track C.")

    out_path = args.out or "/home/shared/github/llorracc/HAFiscal-Latest/history/20260420_ui_recession_gap/splurge_comparison.md"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines))
    print(f"Wrote {out_path}")
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
