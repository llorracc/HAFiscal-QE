"""Generate the paper's welfare6.tex by combining TM-a values (Check, TaxCut)
and MC values (UI) — the hybrid configuration directed 2026-05-10.

Outputs:
- Tables/<param>/welfare6.tex: 3-column (Check, UI, TaxCut) hybrid table
- Tables/<param>/welfare6_source_audit.txt: which source each cell came from

Usage:
    python welfare6_hybrid_table.py \
        --tm-figs-dir <Figures/Baseline> \
        --mc-pickles-dir <welfare6_optionB_1x> \
        --out-tex <Tables/Baseline/welfare6.tex>
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
        return ""
    return f"{x:.2f}"


def write_hybrid_welfare6_tex(tm_cells, mc_cells, out_path):
    """Mirror the paper's existing welfare6.tex structure exactly.

    TM-a values for Check + TaxCut (per user directive 2026-05-10).
    MC values for UI (must remain — published paper has them).
    """
    # ui_norec from MC is structurally undefined (0/0 — UI extension does not
    # activate in non-recession). MC value swings chaotically (-33 to +74).
    # Use TM-a value (~1.0, close to published paper's 0.85) for this cell.
    mc_ui_norec = mc_cells.get('ui_norec')
    use_tm_for_ui_norec = (
        mc_ui_norec is None or np.isnan(mc_ui_norec) or
        abs(mc_ui_norec) > 5.0  # |W| > 5 indicates 0/0 chaos
    )

    cells = {
        # Check column: TM-a
        'check_norec': tm_cells.get('check_norec'),
        'check_rec': tm_cells.get('check_rec'),
        'check_rec_AD': tm_cells.get('check_rec_AD'),
        # UI column: MC for rec/rec_AD (paper compares to it), TM-a for norec
        # (where MC is structurally undefined).
        'ui_norec': (tm_cells.get('ui_norec') if use_tm_for_ui_norec
                      else mc_ui_norec),
        'ui_rec': mc_cells.get('ui_rec'),
        'ui_rec_AD': mc_cells.get('ui_rec_AD'),
        # TaxCut column: TM-a
        'taxcut_norec': tm_cells.get('taxcut_norec'),
        'taxcut_rec': tm_cells.get('taxcut_rec'),
        'taxcut_rec_AD': tm_cells.get('taxcut_rec_AD'),
    }
    cells['_use_tm_for_ui_norec'] = use_tm_for_ui_norec

    out = []
    out.append("\\begin{tabular}{@{}lccc@{}} ")
    out.append("\\toprule ")
    out.append("                          & Stimulus check      & UI extension    & Tax cut    \\\\  \\midrule ")
    out.append(f"$\\mathcal{{W}}(\\text{{policy}}, Rec=0, AD=0)$ & "
               f"{_fmt(cells['check_norec']):<6} & {_fmt(cells['ui_norec']):<6} & "
               f"{_fmt(cells['taxcut_norec']):<8}\\\\ ")
    out.append(f"$\\mathcal{{W}}(\\text{{policy}}, Rec=1, AD=0)$ & "
               f"{_fmt(cells['check_rec']):<6} & {_fmt(cells['ui_rec']):<6} & "
               f"{_fmt(cells['taxcut_rec']):<8}\\\\ ")
    out.append(f"$\\mathcal{{W}}(\\text{{policy}}, Rec=1, AD=1)$ & "
               f"{_fmt(cells['check_rec_AD']):<6} & {_fmt(cells['ui_rec_AD']):<6} & "
               f"{_fmt(cells['taxcut_rec_AD']):<8}\\\\ \\bottomrule ")
    out.append("\\end{tabular}  ")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".",
                exist_ok=True)
    # Candidate-routing (QE-baseline freeze): writes `_candidate` sibling
    # unless HAFISCAL_PROMOTE=1. See generated_output.py.
    from generated_output import open_generated
    with open_generated(out_path) as f:
        f.write("\n".join(out) + "\n")

    return cells


def write_source_audit(out_dir, tm_cells, mc_cells, hybrid_cells, tm_source,
                        mc_source):
    """Audit file documenting per-cell source. The hybrid logic is:
    - Check + TaxCut cells: always TM-a (rep-agent matches MC <5%)
    - UI rec/rec_AD: MC (paper has these; can't drop)
    - UI norec: TM-a if MC is structurally undefined (|W|>5), else MC.
    """
    use_tm_for_ui_norec = hybrid_cells.get('_use_tm_for_ui_norec', False)
    audit_path = os.path.join(out_dir, "welfare6_source_audit.txt")
    with open(audit_path, "w") as f:
        f.write("Hybrid welfare6 table — source audit (per user directive 2026-05-10)\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"TM-a source: {tm_source}\n")
        f.write(f"MC source: {mc_source}\n\n")
        f.write(f"{'Cell':<22} {'Used':>10} {'Source':>14}  "
                f"{'TM-a':>8} {'MC':>10}\n")
        f.write("-" * 75 + "\n")
        for k in ['check_norec', 'check_rec', 'check_rec_AD',
                  'ui_norec', 'ui_rec', 'ui_rec_AD',
                  'taxcut_norec', 'taxcut_rec', 'taxcut_rec_AD']:
            tm = tm_cells.get(k, float('nan'))
            mc = mc_cells.get(k, float('nan'))
            used = hybrid_cells.get(k, float('nan'))
            if k.startswith(('check_', 'taxcut_')):
                src = 'TM-a'
            elif k == 'ui_norec':
                src = 'TM-a (MC undef)' if use_tm_for_ui_norec else 'MC'
            else:
                src = 'MC'
            tm_s = 'NaN' if np.isnan(tm) else f"{tm:.4f}"
            mc_s = 'NaN' if np.isnan(mc) else f"{mc:.4f}"
            used_s = 'NaN' if np.isnan(used) else f"{used:.4f}"
            f.write(f"{k:<22} {used_s:>10} {src:>14}  {tm_s:>8} {mc_s:>10}\n")
    print(f"  Wrote audit: {audit_path}")


# ===========================================================================
# Phase C.1 — unified TM-vs-MC welfare comparison: bias/SE columns + the
# matched-pair guard (BUG-051). The hybrid table above PICKS one source per
# cell (the paper's final values); the comparison below shows BOTH arms
# side-by-side with bias and SE (the cross-check).
# ===========================================================================

def capture_welfare6_regime():
    """The matched-pair regime {PermGroFac fix, UI-state encoding, interpretation}
    the current process runs under. Stamp it into each arm's output so the
    comparison can refuse to compare mismatched regimes (the BUG-051 hazard).
    Pure env-reads — mirrors _permgrofac.py:28, EstimParameters.py:191, and the
    _interpretation.py default; no heavy imports, safe to call anywhere.
    """
    return {
        "permgrofac_fix": os.environ.get("HAFISCAL_PERMGROFAC_FIX", "1") != "0",
        "ui_state_encoding": os.environ.get("HAFISCAL_UI_STATE_ENCODING", "bug_fix"),
        "interpretation": (os.environ.get("HAFISCAL_INTERPRETATION") or "CDC").upper(),
    }


def assert_welfare6_regimes_match(tm_regime, mc_regime,
                                  context="TM-vs-MC welfare comparison"):
    """Matched-pair GUARD (BUG-051): raise if the TM and MC arms ran under
    DIFFERENT {PermGroFac, UI-encoding, interpretation} regimes — comparing them
    is meaningless. Soft by design (same as _permgrofac.assert_regime): a
    missing/None stamp passes (legacy pickles); only an EXPLICIT mismatch blocks.
    """
    if not tm_regime or not mc_regime:
        return
    if tm_regime != mc_regime:
        diffs = sorted(k for k in set(tm_regime) | set(mc_regime)
                       if tm_regime.get(k) != mc_regime.get(k))
        raise RuntimeError(
            f"[welfare6 matched-pair] {context}: the TM and MC arms ran under "
            f"DIFFERENT regimes; comparing them is meaningless. Mismatch on "
            f"{diffs}:\n  TM regime: {tm_regime}\n  MC regime: {mc_regime}\n"
            "Re-run BOTH arms under the same HAFISCAL_PERMGROFAC_FIX / "
            "HAFISCAL_UI_STATE_ENCODING / HAFISCAL_INTERPRETATION.")


_WELFARE6_CELLS = ['check_norec', 'check_rec', 'check_rec_AD',
                   'ui_norec', 'ui_rec', 'ui_rec_AD',
                   'taxcut_norec', 'taxcut_rec', 'taxcut_rec_AD']


def write_tm_vs_mc_comparison(tm_cells, mc_cells, out_path,
                              tm_regime=None, mc_regime=None, mc_se=None):
    """Unified TM-vs-MC welfare-6 comparison: per cell, TM | MC | bias(MC-TM) |
    %bias | SE(MC). The Phase C.1 cross-check deliverable.

    - Matched-pair GUARD: refuses to compare if tm_regime != mc_regime (BUG-051).
    - EXCLUDES ui_norec (0/0 by construction — never report; project memory).
    - FLAGS ui_rec / ui_rec_AD 'UI*' (UI welfare unreliable; Check + TaxCut are
      the decisive metrics; project memory).
    - mc_se: optional {cell: SE} from MC multi-seed runs; blank if absent.
    Writes a text report to out_path and returns the per-cell row dicts.
    """
    assert_welfare6_regimes_match(tm_regime, mc_regime)
    EXCLUDE = {'ui_norec'}
    UI_FLAG = {'ui_rec', 'ui_rec_AD'}
    mc_se = mc_se or {}

    def _num(x):
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return None
        return float(x)

    rows = []
    for k in _WELFARE6_CELLS:
        if k in EXCLUDE:
            continue
        tm = _num(tm_cells.get(k))
        mc = _num(mc_cells.get(k))
        se = _num(mc_se.get(k))
        bias = (mc - tm) if (tm is not None and mc is not None) else None
        pct = (100.0 * bias / tm) if (bias is not None and tm not in (None, 0.0)) else None
        rows.append({'cell': k, 'TM': tm, 'MC': mc, 'bias': bias,
                     'pct': pct, 'SE': se, 'flag': 'UI*' if k in UI_FLAG else ''})

    def _f(x, nd=4):
        return '' if x is None else f"{x:.{nd}f}"

    L = ["TM-vs-MC welfare-6 comparison (Phase C.1)",
         "=" * 80,
         f"  TM regime: {tm_regime or '(untagged)'}",
         f"  MC regime: {mc_regime or '(untagged)'}",
         "  ui_norec EXCLUDED (0/0 by construction). UI* rows unreliable "
         "(use Check + TaxCut).",
         "",
         f"  {'cell':<15}{'TM':>10}{'MC':>10}{'bias(MC-TM)':>13}"
         f"{'%bias':>8}{'SE(MC)':>9}  flag",
         "  " + "-" * 76]
    for r in rows:
        L.append(f"  {r['cell']:<15}{_f(r['TM']):>10}{_f(r['MC']):>10}"
                 f"{_f(r['bias']):>13}{_f(r['pct'], 1):>8}{_f(r['SE']):>9}  {r['flag']}")
    text = "\n".join(L) + "\n"

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w") as fh:
        fh.write(text)
    print(text)
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tm-figs-dir", required=True)
    p.add_argument("--mc-pickles-dir", required=True)
    p.add_argument("--out-tex", required=True)
    args = p.parse_args()

    print(f"Computing TM-a rep-agent from {args.tm_figs_dir} ...")
    tm_cells = compute_welfare6_repagent_from_csvs(args.tm_figs_dir)

    print(f"Loading MC welfare from {args.mc_pickles_dir} ...")
    mc_cells, _ = _try_mc(args.mc_pickles_dir)

    hybrid = write_hybrid_welfare6_tex(tm_cells, mc_cells, args.out_tex)
    print(f"  Wrote: {args.out_tex}")

    out_dir = os.path.dirname(os.path.abspath(args.out_tex))
    write_source_audit(out_dir, tm_cells, mc_cells, hybrid,
                        args.tm_figs_dir, args.mc_pickles_dir)

    print(f"\n=== Hybrid welfare6 table ===")
    print(f"{'Cell':<22} {'Value':>10} {'Source':>10}")
    print("-" * 45)
    for k in ['check_norec', 'check_rec', 'check_rec_AD',
              'ui_norec', 'ui_rec', 'ui_rec_AD',
              'taxcut_norec', 'taxcut_rec', 'taxcut_rec_AD']:
        v = hybrid.get(k, float('nan'))
        src = 'TM-a' if k.startswith(('check_', 'taxcut_')) else 'MC'
        v_s = 'NaN' if np.isnan(v) else f"{v:.4f}"
        print(f"{k:<22} {v_s:>10} {src:>10}")


if __name__ == "__main__":
    main()
