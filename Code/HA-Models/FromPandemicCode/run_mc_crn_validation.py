"""Driver for validate_mc_crn.py.

Launches validate_mc_crn.py in two independent Python subprocesses (and
optionally a third sequential run in the parent process as a sanity
anchor), then compares the pickled outputs element-wise. Reports
whether CRN determinism holds across subprocess boundaries.

Usage:
    python run_mc_crn_validation.py              # two parallel subprocesses
    python run_mc_crn_validation.py --serial     # two sequential subprocesses
    python run_mc_crn_validation.py --parametrization Reduced_Run
"""

import argparse
import os
import pickle
import subprocess
import sys
from time import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "validate_mc_crn.py")


def _load(tag):
    path = os.path.join(HERE, f"validation_mc_crn_{tag}.pkl")
    with open(path, "rb") as f:
        return pickle.load(f)


def _compare(a, b, name, tol_exact=True):
    """Element-wise compare. Return (is_equal, max_abs_diff, max_rel_diff)."""
    if a.shape != b.shape:
        return (False, np.inf, np.inf, f"shape mismatch: {a.shape} vs {b.shape}")
    equal = np.array_equal(a, b)
    if a.dtype == np.bool_:
        # Bool arrays: diff = number of mismatches
        mism = int(np.count_nonzero(a != b))
        return (equal, float(mism), float(mism) / max(a.size, 1), "")
    a_f = a.astype(np.float64, copy=False)
    b_f = b.astype(np.float64, copy=False)
    max_abs = float(np.max(np.abs(a_f - b_f))) if a.size > 0 else 0.0
    denom = np.maximum(np.abs(a_f), 1e-300)
    max_rel = float(np.max(np.abs(a_f - b_f) / denom)) if a.size > 0 else 0.0
    return (equal, max_abs, max_rel, "")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parametrization", default="HS_Only",
                   choices=("HS_Only", "Reduced_Run"))
    p.add_argument("--with-ad", action="store_true",
                   help="Run the recessionUI scenario with AD convergence.")
    p.add_argument("--serial", action="store_true",
                   help="Run subprocesses sequentially (default: parallel).")
    args = p.parse_args()

    python = sys.executable
    logs = {}
    procs = {}
    t0 = time()

    for tag in ("A", "B"):
        log_path = os.path.join(HERE, f"validation_mc_crn_{tag}.log")
        logs[tag] = open(log_path, "w")
        cmd = [python, SCRIPT, "--run-tag", tag,
               "--parametrization", args.parametrization]
        if args.with_ad:
            cmd.append("--with-ad")
        print(f"Launching {tag}: {' '.join(cmd)}  → {log_path}")
        procs[tag] = subprocess.Popen(cmd, cwd=HERE, stdout=logs[tag],
                                      stderr=subprocess.STDOUT)
        if args.serial:
            # Wait for this subprocess before launching the next.
            procs[tag].wait()

    # Wait for all
    for tag in ("A", "B"):
        rc = procs[tag].wait()
        logs[tag].close()
        status = "OK" if rc == 0 else f"FAIL rc={rc}"
        print(f"  {tag}: {status} ({time() - t0:.0f}s elapsed)")
        if rc != 0:
            print(f"    See: {os.path.join(HERE, f'validation_mc_crn_{tag}.log')}")
            return 1

    print(f"\nBoth subprocesses done in {time() - t0:.0f}s wall clock.\n")

    A = _load("A")
    B = _load("B")

    # Note: whole-pickle byte comparison is not meaningful because the
    # pickle includes per-run fields like `total_runtime_s` that will
    # always differ. What matters is whether the numerical arrays are
    # identical; that's what the element-wise comparison below tests.
    print()

    # Element-wise compare on the structured data
    print(f"{'Field':<30}  {'Equal':>6}  {'max|Δ|':>12}  {'max rel Δ':>10}")
    print("-" * 68)

    overall_equal = True
    for section, keys in (("shocks", ("PermShk", "TranShk", "who_dies",
                                       "unemployment_draw", "Mrkv")),
                          ("base", ("cLvl_all_splurge", "AggCons", "AggIncome")),
                          ("ui",   ("cLvl_all_splurge", "AggCons", "AggIncome"))):
        for key in keys:
            a_arr = A[section][key]
            b_arr = B[section][key]
            eq, max_abs, max_rel, err = _compare(a_arr, b_arr, f"{section}.{key}")
            overall_equal = overall_equal and eq
            tag = "✓" if eq else "✗"
            print(f"{section}.{key:<22}  {tag:>6}  {max_abs:>12.2e}  {max_rel:>10.2e}"
                  + (f"  [{err}]" if err else ""))

    print()
    if overall_equal:
        print("VERDICT: CRN preserved across subprocess boundaries. "
              "Subprocess-level parallelism is safe.")
        return 0
    else:
        print("VERDICT: Differences detected. Subprocess-level "
              "parallelism would BREAK CRN for welfare-6.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
