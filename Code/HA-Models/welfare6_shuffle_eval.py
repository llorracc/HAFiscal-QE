#!/usr/bin/env python
"""Evaluate the --shuffle MC variance-reduction (HAFISCAL_MARKOV_SHUFFLE +
HAFISCAL_INCOME_SHUFFLE): shuffle vs no-shuffle, multi-seed, per-cell bias + SE
vs the converged TM (aCount=200). Reports the SE ratio (variance reduction) and
whether shuffle reaches SE<0.25% AND |bias|<0.25% (the canonical-spec criterion).

Reads Results/tmp/shuffle/{shuf,noshuf}_s{0..3} + tm_HS_a200.pkl.
"""
import os
import sys
import statistics

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from welfare6_tm_vs_mc import read_mc_cells, read_tm_cells  # noqa: E402

SW = os.path.join(_HERE, "Results", "tmp", "shuffle")
CELLS = ['check_norec', 'check_rec', 'check_rec_AD',
         'taxcut_norec', 'taxcut_rec', 'taxcut_rec_AD']


def aggregate(mode, seeds=(0, 1, 2, 3)):
    """Per-cell (mean, SE=SD/sqrt(S), n_seeds) across the CRN replicas."""
    per = {c: [] for c in CELLS}
    for s in seeds:
        d = os.path.join(SW, f"{mode}_s{s}")
        if not os.path.isdir(d):
            continue
        cells, _, _ = read_mc_cells(d)
        for c in CELLS:
            v = cells.get(c)
            if v is not None and v == v:  # exclude NaN
                per[c].append(float(v))
    out = {}
    for c in CELLS:
        xs = per[c]
        if len(xs) >= 2:
            out[c] = (statistics.mean(xs), statistics.stdev(xs) / len(xs) ** 0.5, len(xs))
        elif xs:
            out[c] = (xs[0], None, 1)
        else:
            out[c] = (None, None, 0)
    return out


def main():
    tm, tm_key, _ = read_tm_cells(os.path.join(SW, "tm_HS_a200.pkl"))
    print(f"TM key '{tm_key}' (aCount=200)\n")
    shuf = aggregate("shuf")
    nosh = aggregate("noshuf")

    def f(x, nd=3):
        return '' if x is None else f"{x:.{nd}f}"

    hdr = (f"{'cell':<14}{'TM':>8} |{'shuf:bias%':>11}{'SE%':>8} |"
           f"{'noshuf:bias%':>13}{'SE%':>8} |{'SE ratio':>9}{'  <0.25%?':>9}")
    print(hdr)
    print("-" * len(hdr))
    for c in CELLS:
        t = tm.get(c)
        sm, sse, sn = shuf[c]
        nm, nse, nn = nosh[c]

        def bp(m):
            return 100.0 * (m - t) / t if (m is not None and t not in (None, 0)) else None

        def sp(se):
            return 100.0 * se / t if (se is not None and t not in (None, 0)) else None

        ratio = (nse / sse) if (sse and nse and sse > 0) else None
        s_bias, s_se = bp(sm), sp(sse)
        ok = (s_bias is not None and s_se is not None
              and abs(s_bias) < 0.25 and s_se < 0.25)
        print(f"{c:<14}{f(t):>8} |{f(s_bias, 2):>11}{f(s_se, 3):>8} |"
              f"{f(bp(nm), 2):>13}{f(sp(nse), 3):>8} |{f(ratio, 1):>9}"
              f"{('  PASS' if ok else '  --'):>9}")
    print("\nPASS = shuffle achieves |bias|<0.25% AND SE<0.25% (canonical-spec criterion).")
    print("SE ratio = noshuf SE / shuf SE (the variance-reduction factor).")


if __name__ == "__main__":
    main()
