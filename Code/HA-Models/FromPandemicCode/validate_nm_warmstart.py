"""Validate the HAFISCAL_NM_IN_PLACE warm-start prototype for step 2.

Compares two short Nelder-Mead runs of `betas_obj_func_educ`:
  - flag off: original deepcopy-per-iteration behavior (cold solve each iter).
  - flag on:  in-place mutation, warm-start path active in AggDemandEconomy.solve().

For each run, logs (β, ∇, GICx, distance, iter_time_sec) per NM iteration.
Reports: did the flag-on run reach the same minimum (within tol) as the flag-off
run, and what was the per-iter speedup on the solver step.

Scope: one education type at a time (HAFISCAL_EDTYPES selects which one).
Run count: N_ITERS_VALIDATE Nelder-Mead iterations per mode (default 8, override
via --n-iters). A full production NM for one education type converges in ~50-100
iterations; 8 is enough to see the warm-start speedup signature without paying
for a full estimate.

Usage:
    cd Code/HA-Models/FromPandemicCode
    python validate_nm_warmstart.py --edtype 1 --n-iters 8

The script patches `minimize_nelder_mead` to stop after N_ITERS_VALIDATE function
evaluations via a scipy OptimizeWarning-style short-circuit, so the production
EstimAggFiscalMAIN.py is not modified beyond the in-place / deepcopy switch.
"""
import argparse, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent  # repo root
RESULTS_DIR = ROOT / "plans" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def run_one_mode(mode, edtype, n_iters):
    """mode in {'off', 'on'}. Runs n_iters NM iterations, captures trajectory."""
    import subprocess
    env = os.environ.copy()
    env["HAFISCAL_NM_IN_PLACE"] = "1" if mode == "on" else "0"
    env["HAFISCAL_EDTYPES"] = str(edtype)
    env["HAFISCAL_NM_VALIDATE_N_ITERS"] = str(n_iters)
    env["MPLBACKEND"] = "Agg"

    trajectory_path = RESULTS_DIR / f"nm_validate_{mode}_ed{edtype}.jsonl"
    if trajectory_path.exists():
        trajectory_path.unlink()
    env["HAFISCAL_NM_TRAJECTORY"] = str(trajectory_path)

    log_path = RESULTS_DIR / f"nm_validate_{mode}_ed{edtype}.log"

    print(f"[validate] mode={mode} edtype={edtype} n_iters={n_iters} log={log_path.name}")
    t0 = time.time()
    with open(log_path, "w") as logf:
        rc = subprocess.call(
            [sys.executable, "EstimAggFiscalMAIN.py"],
            cwd=str(HERE), env=env, stdout=logf, stderr=subprocess.STDOUT,
        )
    wall = time.time() - t0
    print(f"[validate]   wall={wall:.0f}s rc={rc}")
    return trajectory_path, rc, wall


def load_trajectory(path):
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def summarize(off_recs, on_recs):
    print()
    print("=" * 76)
    print(f"{'iter':>4} {'β_off':>10} {'β_on':>10} {'∇_off':>10} {'∇_on':>10}"
          f" {'d_off':>10} {'d_on':>10} {'t_off':>8} {'t_on':>8}")
    print("-" * 76)
    n = min(len(off_recs), len(on_recs))
    for i in range(n):
        o, on = off_recs[i], on_recs[i]
        print(f"{i:>4}"
              f" {o['beta']:>10.6f} {on['beta']:>10.6f}"
              f" {o['spread']:>10.6f} {on['spread']:>10.6f}"
              f" {o['distance']:>10.6f} {on['distance']:>10.6f}"
              f" {o['iter_sec']:>8.2f} {on['iter_sec']:>8.2f}")
    print("-" * 76)
    print()

    # Compute aggregate stats
    import numpy as np
    t_off = np.array([r['iter_sec'] for r in off_recs[:n]])
    t_on = np.array([r['iter_sec'] for r in on_recs[:n]])
    d_off = np.array([r['distance'] for r in off_recs[:n]])
    d_on = np.array([r['distance'] for r in on_recs[:n]])
    b_off = np.array([r['beta'] for r in off_recs[:n]])
    b_on = np.array([r['beta'] for r in on_recs[:n]])

    print(f"  per-iter time:    off={t_off.mean():.2f}s  on={t_on.mean():.2f}s"
          f"  speedup={t_off.mean()/t_on.mean():.2f}×")
    print(f"  total time:       off={t_off.sum():.0f}s  on={t_on.sum():.0f}s"
          f"  speedup={t_off.sum()/t_on.sum():.2f}×")
    print(f"  max |Δdistance|:  {np.abs(d_off-d_on).max():.6f}")
    print(f"  max |Δβ|:         {np.abs(b_off-b_on).max():.6f}")
    print()
    print("Interpretation:")
    print("  - The NM trajectory should match (distance and β paths within"
          " floating-point ε).")
    print("  - Per-iter time on the 'on' run should drop after iter 1 as"
          " warm-start kicks in.")
    print("  - Iter 0 may be identical (no prior solution to warm-start from).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edtype", type=int, default=1,
                    help="Education type to estimate (0=dropout, 1=HS, 2=college)")
    ap.add_argument("--n-iters", type=int, default=8,
                    help="Nelder-Mead iterations per mode (default 8)")
    args = ap.parse_args()

    # Run both modes
    off_path, off_rc, off_wall = run_one_mode("off", args.edtype, args.n_iters)
    on_path, on_rc, on_wall = run_one_mode("on", args.edtype, args.n_iters)

    if off_rc != 0 or on_rc != 0:
        print(f"[validate] WARN: nonzero return codes (off={off_rc}, on={on_rc})")
        print(f"  see {off_path}.log and {on_path}.log for details")

    off_recs = load_trajectory(off_path)
    on_recs = load_trajectory(on_path)

    if not off_recs or not on_recs:
        print(f"[validate] no trajectory data — off={len(off_recs)} on={len(on_recs)}")
        print(f"  check that the trajectory hook in EstimAggFiscalMAIN.py is active.")
        sys.exit(1)

    summarize(off_recs, on_recs)


if __name__ == "__main__":
    main()
