"""Compare step-2 with default loky idle-timeout vs LOKY_IDLE_WORKER_TIMEOUT=3600.

Tests whether keeping loky workers alive longer reduces the ~1.15 s cold-
import cost per respawn. Matched N=10 per mode, HAFISCAL_NM_IN_PLACE=1 both.

Usage:
    cd Code/HA-Models/FromPandemicCode
    python validate_nm_loky_timeout.py --edtype 1 --n-iters 10
"""
import argparse, json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
RESULTS_DIR = ROOT / "plans" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def run_one_mode(mode, edtype, n_iters):
    env = os.environ.copy()
    if mode == "long_timeout":
        env["LOKY_IDLE_WORKER_TIMEOUT"] = "3600"
    env["HAFISCAL_NM_IN_PLACE"] = "1"
    env["HAFISCAL_EDTYPES"] = str(edtype)
    env["HAFISCAL_NM_VALIDATE_N_ITERS"] = str(n_iters)
    env["MPLBACKEND"] = "Agg"
    traj = RESULTS_DIR / f"nm_loky_{mode}_ed{edtype}.jsonl"
    if traj.exists():
        traj.unlink()
    env["HAFISCAL_NM_TRAJECTORY"] = str(traj)
    log = RESULTS_DIR / f"nm_loky_{mode}_ed{edtype}.log"
    print(f"[loky-test] mode={mode} edtype={edtype} n_iters={n_iters}")
    t0 = time.time()
    with open(log, "w") as logf:
        rc = subprocess.call([sys.executable, "EstimAggFiscalMAIN.py"],
                             cwd=str(HERE), env=env,
                             stdout=logf, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    print(f"[loky-test]   wall={wall:.0f}s rc={rc}")
    return traj, rc, wall


def load_traj(p):
    recs = []
    if p.exists():
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edtype", type=int, default=1)
    ap.add_argument("--n-iters", type=int, default=10)
    args = ap.parse_args()

    def_traj, def_rc, def_wall = run_one_mode("default", args.edtype, args.n_iters)
    long_traj, long_rc, long_wall = run_one_mode("long_timeout", args.edtype, args.n_iters)

    d = load_traj(def_traj)
    l_ = load_traj(long_traj)
    n = min(len(d), len(l_))
    if n == 0:
        print("[loky-test] no trajectory data — see logs")
        sys.exit(1)

    print()
    print("=" * 72)
    print(f"{'iter':>4} {'β_def':>10} {'β_long':>10} {'d_def':>10} {'d_long':>10}"
          f" {'t_def':>8} {'t_long':>8}")
    print("-" * 72)
    for i in range(n):
        a, b = d[i], l_[i]
        print(f"{i:>4} {a['beta']:>10.6f} {b['beta']:>10.6f}"
              f" {a['distance']:>10.6f} {b['distance']:>10.6f}"
              f" {a['iter_sec']:>8.2f} {b['iter_sec']:>8.2f}")
    print("-" * 72)
    import numpy as np
    t_d = np.array([r['iter_sec'] for r in d[:n]])
    t_l = np.array([r['iter_sec'] for r in l_[:n]])
    d_d = np.array([r['distance'] for r in d[:n]])
    d_l = np.array([r['distance'] for r in l_[:n]])
    b_d = np.array([r['beta'] for r in d[:n]])
    b_l = np.array([r['beta'] for r in l_[:n]])
    speedup = t_d.mean() / t_l.mean()
    print(f"  per-iter mean: default {t_d.mean():.1f}s vs long-timeout {t_l.mean():.1f}s"
          f" — ratio {speedup:.2f}× ({'long faster' if speedup>1 else 'default faster'})")
    print(f"  total wall:    default {def_wall:.0f}s vs long-timeout {long_wall:.0f}s"
          f" — ratio {def_wall/long_wall:.2f}×")
    print(f"  max |Δβ|:      {np.abs(b_d - b_l).max():.6f}")
    print(f"  max |Δd|:      {np.abs(d_d - d_l).max():.6f}")


if __name__ == "__main__":
    main()
