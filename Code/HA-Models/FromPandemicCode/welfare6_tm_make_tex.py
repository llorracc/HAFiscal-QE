"""Generate a paper-ready LaTeX welfare-6 table comparing TM-a (analytical
representative-agent) and MC (Baseline 1×).

Output:
    Tables/welfare6_tm_repagent/welfare6_tm_vs_mc.tex
    Tables/welfare6_tm_repagent/welfare6_tm_only.tex (TM-a values only,
        for paper if MC is dropped)

Usage:
    python welfare6_tm_make_tex.py \
        --tm-figs-dir Code/HA-Models/FromPandemicCode/Figures/Baseline \
        --mc-pickles-dir Code/HA-Models/FromPandemicCode/welfare6_optionB_1x \
        --out-dir Tables/welfare6_tm_repagent
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from welfare6_tm_repagent_from_csvs import compute_welfare6_repagent_from_csvs


def _try_mc(mc_pickles_dir):
    try:
        from run_welfare6_parallel import compute_welfare6_table
        return compute_welfare6_table(mc_pickles_dir)
    except Exception as e:
        print(f"[warn] MC pickles unavailable: {e}")
        return ({}, None)


def _fmt(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "---"
    return f"{x:.2f}"


def write_tm_only_tex(cells, path):
    """Welfare-6 table with TM-a values only (no UI rows; UI excluded)."""
    out = []
    out.append("\\begin{tabular}{@{}lccc@{}}")
    out.append("\\toprule")
    out.append("                          & Stimulus check & Tax cut \\\\ \\midrule")
    out.append(f"$\\mathcal{{W}}(\\text{{policy}}, Rec=0, AD=0)$ & {_fmt(cells.get('check_norec'))} & {_fmt(cells.get('taxcut_norec'))} \\\\")
    out.append(f"$\\mathcal{{W}}(\\text{{policy}}, Rec=1, AD=0)$ & {_fmt(cells.get('check_rec'))}  & {_fmt(cells.get('taxcut_rec'))} \\\\")
    out.append(f"$\\mathcal{{W}}(\\text{{policy}}, Rec=1, AD=1)$ & {_fmt(cells.get('check_rec_AD'))} & {_fmt(cells.get('taxcut_rec_AD'))} \\\\ \\bottomrule")
    out.append("\\end{tabular}")
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")


def write_tm_vs_mc_tex(tm_cells, mc_cells, path):
    """Side-by-side TM-a vs MC welfare table for validation."""
    out = []
    out.append("\\begin{tabular}{@{}lcccccccc@{}}")
    out.append("\\toprule")
    out.append("& \\multicolumn{2}{c}{Stimulus check} & \\multicolumn{2}{c}{UI ext.} & \\multicolumn{2}{c}{Tax cut} \\\\")
    out.append("\\cmidrule(lr){2-3} \\cmidrule(lr){4-5} \\cmidrule(lr){6-7}")
    out.append("Welfare cell & TM-a & MC & TM-a & MC & TM-a & MC \\\\ \\midrule")
    out.append(f"$\\mathcal{{W}}(Rec=0, AD=0)$ & "
               f"{_fmt(tm_cells.get('check_norec'))} & {_fmt(mc_cells.get('check_norec'))} & "
               f"{_fmt(tm_cells.get('ui_norec'))} & {_fmt(mc_cells.get('ui_norec'))} & "
               f"{_fmt(tm_cells.get('taxcut_norec'))} & {_fmt(mc_cells.get('taxcut_norec'))} \\\\")
    out.append(f"$\\mathcal{{W}}(Rec=1, AD=0)$ & "
               f"{_fmt(tm_cells.get('check_rec'))} & {_fmt(mc_cells.get('check_rec'))} & "
               f"{_fmt(tm_cells.get('ui_rec'))} & {_fmt(mc_cells.get('ui_rec'))} & "
               f"{_fmt(tm_cells.get('taxcut_rec'))} & {_fmt(mc_cells.get('taxcut_rec'))} \\\\")
    out.append(f"$\\mathcal{{W}}(Rec=1, AD=1)$ & "
               f"{_fmt(tm_cells.get('check_rec_AD'))} & {_fmt(mc_cells.get('check_rec_AD'))} & "
               f"{_fmt(tm_cells.get('ui_rec_AD'))} & {_fmt(mc_cells.get('ui_rec_AD'))} & "
               f"{_fmt(tm_cells.get('taxcut_rec_AD'))} & {_fmt(mc_cells.get('taxcut_rec_AD'))} \\\\ \\bottomrule")
    out.append("\\end{tabular}")
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")


def write_full_csv(tm_cells, mc_cells_1x, mc_cells_2x, path):
    """CSV with TM-a, MC 1×, MC 2× side-by-side."""
    keys = ['check_norec', 'ui_norec', 'taxcut_norec',
            'check_rec', 'ui_rec', 'taxcut_rec',
            'check_rec_AD', 'ui_rec_AD', 'taxcut_rec_AD']
    with open(path, "w") as f:
        f.write("cell,tm_repagent,mc_baseline_1x,mc_baseline_2x,delta_pct_tm_vs_mc1x\n")
        for k in keys:
            tm = tm_cells.get(k, float('nan'))
            m1 = mc_cells_1x.get(k, float('nan'))
            m2 = mc_cells_2x.get(k, float('nan'))
            if np.isnan(m1) or abs(m1) < 0.05:
                d = ''
            else:
                d = f"{(tm-m1)/m1*100:+.2f}"
            f.write(f"{k},{tm if not np.isnan(tm) else ''},"
                    f"{m1 if not np.isnan(m1) else ''},"
                    f"{m2 if not np.isnan(m2) else ''},{d}\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tm-figs-dir", required=True)
    p.add_argument("--mc-pickles-dir", default=None,
                   help="MC welfare pickles directory (e.g. welfare6_optionB_1x)")
    p.add_argument("--mc-pickles-dir-2x", default=None,
                   help="Optional second MC pickles dir for convergence column")
    p.add_argument("--out-dir", required=True)
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    print(f"Computing TM-a rep-agent welfare from {args.tm_figs_dir} ...")
    tm_cells = compute_welfare6_repagent_from_csvs(args.tm_figs_dir)

    mc_cells_1x = {}
    mc_cells_2x = {}
    if args.mc_pickles_dir:
        print(f"Loading MC welfare from {args.mc_pickles_dir} ...")
        mc_cells_1x, _ = _try_mc(args.mc_pickles_dir)
    if args.mc_pickles_dir_2x:
        print(f"Loading MC 2× welfare from {args.mc_pickles_dir_2x} ...")
        mc_cells_2x, _ = _try_mc(args.mc_pickles_dir_2x)

    # Write outputs
    tm_only_path = os.path.join(args.out_dir, "welfare6_tm_only.tex")
    write_tm_only_tex(tm_cells, tm_only_path)
    print(f"  Wrote: {tm_only_path}")

    if mc_cells_1x:
        side_path = os.path.join(args.out_dir, "welfare6_tm_vs_mc.tex")
        write_tm_vs_mc_tex(tm_cells, mc_cells_1x, side_path)
        print(f"  Wrote: {side_path}")

        csv_path = os.path.join(args.out_dir, "welfare6_tm_vs_mc.csv")
        write_full_csv(tm_cells, mc_cells_1x, mc_cells_2x, csv_path)
        print(f"  Wrote: {csv_path}")

    # Print to stdout
    print(f"\n=== Final TM-a rep-agent welfare-6 ({args.tm_figs_dir}) ===")
    print(f"{'Cell':<22} {'TM-a':>10}")
    print("-" * 35)
    for k in ['check_norec', 'ui_norec', 'taxcut_norec',
              'check_rec', 'ui_rec', 'taxcut_rec',
              'check_rec_AD', 'ui_rec_AD', 'taxcut_rec_AD']:
        v = tm_cells.get(k, float('nan'))
        print(f"{k:<22} {'NaN' if np.isnan(v) else f'{v:.4f}':>10}")


if __name__ == "__main__":
    main()
