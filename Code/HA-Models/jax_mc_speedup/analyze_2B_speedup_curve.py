"""Consolidate 2B speedup curve data across phases 2/3/4 into a single table.

Walks the phase logs, extracts the wall_A/wall_B/wall_C numbers per cohort,
and prints a per-cohort speedup table sorted by cohort index.

Usage:
    .venv-linux-x86_64/bin/python \\
      Code/HA-Models/jax_mc_speedup/analyze_2B_speedup_curve.py
    # JSON output (for piping):
    .venv-linux-x86_64/bin/python \\
      Code/HA-Models/jax_mc_speedup/analyze_2B_speedup_curve.py --json
"""
import argparse
import glob
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


_PARITY_RE = re.compile(
    r"\(B\) scan vs \(C\) while_loop:\s+max abs = ([\d.eE+-]+)")
_TIMING_A = re.compile(r"\(A\) HARK native.*?:\s+([\d.]+)s")
_TIMING_B = re.compile(r"\(B\) JAX scan,\s+N=\d+:\s+([\d.]+)s")
_TIMING_C = re.compile(r"\(C\) JAX while_loop,\s+n=(\d+):\s+([\d.]+)s")
_STATE_COUNT = re.compile(r"StateCount = (\d+)")
_CONVERGED = re.compile(r"converged=(True|False)")
_FINAL_DIFF = re.compile(r"final_diff=([\d.eE+-]+),\s+converged=")


def _parse_log(path):
    try:
        with open(path) as f:
            text = f.read()
    except OSError:
        return None
    sc = _STATE_COUNT.search(text)
    a = _TIMING_A.search(text)
    b = _TIMING_B.search(text)
    c = _TIMING_C.search(text)
    p = _PARITY_RE.search(text)
    conv = _CONVERGED.search(text)
    fd = _FINAL_DIFF.search(text)
    if not (a and b and c):
        return None
    return {
        "state_count": int(sc.group(1)) if sc else None,
        "wall_A_hark": float(a.group(1)),
        "wall_B_scan": float(b.group(1)),
        "wall_C_while_n": int(c.group(1)),
        "wall_C_while": float(c.group(2)),
        "parity_BC_abs": float(p.group(1)) if p else None,
        "converged": (conv.group(1) == "True") if conv else None,
        "final_diff": float(fd.group(1)) if fd else None,
    }


_LABEL_COHORT_RE = re.compile(r"2B_Baseline_(?:warmstart_)?cohort(\d+)\.log$")
_WARMSTART_RE = re.compile(r"warmstart")


def _walk(warmstart=False):
    """Walk overnight_phase{2,3,4,6}_logs for 2B_Baseline_cohort*.log entries.

    Args:
        warmstart: if True, return only warmstart logs; if False, only
            cold-start logs.
    """
    out = {}  # cohort_idx -> result dict
    for phase in (2, 3, 4, 6):
        log_dir = os.path.join(_HERE, f"overnight_phase{phase}_logs")
        if not os.path.isdir(log_dir):
            continue
        for path in glob.glob(os.path.join(log_dir, "2B_Baseline_cohort*.log")) + \
                    glob.glob(os.path.join(log_dir, "2B_Baseline_warmstart_cohort*.log")):
            m = _LABEL_COHORT_RE.search(os.path.basename(path))
            if not m:
                continue
            is_warm = bool(_WARMSTART_RE.search(os.path.basename(path)))
            if warmstart != is_warm:
                continue
            idx = int(m.group(1))
            data = _parse_log(path)
            if data is not None:
                data["phase"] = phase
                data["path"] = path
                data["warmstart"] = is_warm
                out[idx] = data
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.add_argument("--warmstart", action="store_true",
                   help="Show warmstart logs instead of cold-start")
    args = p.parse_args()

    results = _walk(warmstart=args.warmstart)
    if not results:
        mode = "warmstart" if args.warmstart else "cold-start"
        print(f"No 2B Baseline {mode} cohort logs found yet.", flush=True)
        return

    if args.json:
        print(json.dumps(results, sort_keys=True, indent=2,
                          default=lambda x: x if isinstance(x, (int, float, str)) else None))
        return

    mode = "warmstart" if args.warmstart else "cold-start"
    print(f"\n=== Baseline 2B {mode} ===\n")
    print(f"{'cohort':>6s} {'states':>7s} {'iters':>6s} {'conv':>5s} "
          f"{'A_hark':>9s} {'B_scan':>9s} {'C_while':>9s} "
          f"{'C/A':>7s} {'C/B':>7s} {'parity':>11s}")
    print("-" * 95)
    for idx in sorted(results):
        r = results[idx]
        sp_CA = r["wall_A_hark"] / max(r["wall_C_while"], 1e-3)
        sp_CB = r["wall_B_scan"] / max(r["wall_C_while"], 1e-3)
        par = r.get("parity_BC_abs") or 0.0
        # Tag converged column: "Y" / "N" / "?"
        conv = r.get("converged")
        conv_str = "Y" if conv else ("N" if conv is False else "?")
        # Flag non-converged rows or bad parity with an asterisk
        flag = ""
        if conv is False:
            flag = " *iter-cap"
        elif par > 1e-3:
            flag = " *parity"
        print(f"{idx:6d} {r['state_count'] or 0:7d} {r['wall_C_while_n']:6d} "
              f"{conv_str:>5s} "
              f"{r['wall_A_hark']:9.2f} {r['wall_B_scan']:9.2f} "
              f"{r['wall_C_while']:9.2f} "
              f"{sp_CA:6.2f}x {sp_CB:6.2f}x  {par:11.2e}{flag}")

    # Summary stats — separate converged vs non-converged
    converged_results = [r for r in results.values() if r.get("converged")]
    nonconv_results = [r for r in results.values() if r.get("converged") is False]
    print("-" * 95)
    if converged_results:
        sp = [r["wall_A_hark"] / max(r["wall_C_while"], 1e-3) for r in converged_results]
        n_wins = sum(1 for x in sp if x > 1.0)
        median_sp = sorted(sp)[len(sp) // 2]
        print(f"Converged ({len(converged_results)}/{len(results)} cohorts): "
              f"C/A median = {median_sp:.2f}x, max = {max(sp):.2f}x, "
              f"min = {min(sp):.2f}x, wins = {n_wins}/{len(sp)}")
    if nonconv_results:
        print(f"Non-converged ({len(nonconv_results)}/{len(results)} cohorts): "
              f"max_iters cap hit — JAX kernel speedup is real but result not"
              f" bit-comparable to HARK without warm_start")


if __name__ == "__main__":
    main()
