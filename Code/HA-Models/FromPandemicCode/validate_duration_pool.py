"""Validate that duration-level pool parallelism produces bit-identical
results to the serial recession-duration loop inside welfare6_scenario.py.

Runs the same scenario twice as subprocesses of welfare6_scenario.py:
  A) --duration-workers 1   (serial loop)
  B) --duration-workers N   (forked-pool parallel loop)

Then loads the two output pickles and compares element-wise. If the
arrays are bit-identical the pool path is numerically safe to use on
the full Baseline run.

Usage:
    python validate_duration_pool.py --scenario recessionUI_AD
    python validate_duration_pool.py --scenario recession \\
        --parametrization Baseline --workers 6
"""

import argparse
import os
import pickle
import subprocess
import sys
from time import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIO_SCRIPT = os.path.join(HERE, "welfare6_scenario.py")


def run_one(tag, scenario, parametrization, duration_workers, out_dir):
    log_path = os.path.join(out_dir, f"validate_duration_pool_{tag}.log")
    cmd = [
        sys.executable, SCENARIO_SCRIPT,
        "--scenario", scenario,
        "--parametrization", parametrization,
        "--duration-workers", str(duration_workers),
        "--out-dir", out_dir,
    ]
    print(f"[{tag}] workers={duration_workers}: {' '.join(cmd)}")
    print(f"[{tag}] log: {log_path}")
    with open(log_path, "w") as log_fh:
        rc = subprocess.run(cmd, cwd=HERE, stdout=log_fh,
                            stderr=subprocess.STDOUT).returncode
    return rc


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", default="recessionUI_AD",
                   help="Scenario to run (recession* only; others ignore "
                        "duration-workers).")
    p.add_argument("--parametrization", default="Reduced_Run",
                   choices=("HS_Only", "Reduced_Run", "Baseline"))
    p.add_argument("--workers", type=int, default=4,
                   help="Number of pool workers to use in run B.")
    args = p.parse_args()

    out_dir_A = os.path.join(HERE, "validate_duration_pool_A")
    out_dir_B = os.path.join(HERE, "validate_duration_pool_B")
    os.makedirs(out_dir_A, exist_ok=True)
    os.makedirs(out_dir_B, exist_ok=True)

    t0 = time()
    rc_A = run_one("A", args.scenario, args.parametrization, 1, out_dir_A)
    t_A = time() - t0
    if rc_A != 0:
        print(f"A failed (rc={rc_A}); see log.")
        return 1
    print(f"A done in {t_A:.0f}s\n")

    t1 = time()
    rc_B = run_one("B", args.scenario, args.parametrization,
                   args.workers, out_dir_B)
    t_B = time() - t1
    if rc_B != 0:
        print(f"B failed (rc={rc_B}); see log.")
        return 1
    print(f"B done in {t_B:.0f}s\n")

    pkl_A = os.path.join(out_dir_A, f"{args.scenario}.pkl")
    pkl_B = os.path.join(out_dir_B, f"{args.scenario}.pkl")
    with open(pkl_A, "rb") as f:
        A = pickle.load(f)
    with open(pkl_B, "rb") as f:
        B = pickle.load(f)

    print(f"{'Field':<28}  {'Equal':>6}  {'max|Δ|':>12}  {'max rel Δ':>10}")
    print("-" * 66)
    overall = True
    for key in ("cLvl_all_splurge", "AggCons", "AggIncome"):
        a_arr = np.asarray(A[key])
        b_arr = np.asarray(B[key])
        eq = np.array_equal(a_arr, b_arr)
        overall = overall and eq
        max_abs = float(np.max(np.abs(a_arr - b_arr))) if a_arr.size else 0.0
        denom = np.maximum(np.abs(a_arr), 1e-300)
        max_rel = float(np.max(np.abs(a_arr - b_arr) / denom)) if a_arr.size else 0.0
        tag = "✓" if eq else "✗"
        print(f"{key:<28}  {tag:>6}  {max_abs:>12.2e}  {max_rel:>10.2e}")

    print()
    print(f"A (serial)     wall: {t_A:.0f}s")
    print(f"B (pool x{args.workers:>2}) wall: {t_B:.0f}s")
    if t_B > 0:
        print(f"speedup: {t_A/t_B:.2f}x")

    if overall:
        print("\nVERDICT: Duration-pool parallelism is numerically safe.")
        return 0
    print("\nVERDICT: Pool output differs from serial. DO NOT USE THE POOL PATH.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
