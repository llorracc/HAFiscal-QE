"""Compare default joblib-parallel step-2 vs HAFISCAL_SERIAL=1 (multi_thread_commands_fake).

Runs EstimAggFiscalMAIN.py twice with N=10 NM iterations each:
  - mode 'parallel': default (joblib backend, workers respawn → ~1.15 s overhead each)
  - mode 'serial':   HAFISCAL_SERIAL=1 (multi_thread_commands_fake runs agents serially)

Both modes use HAFISCAL_NM_IN_PLACE=1 (current default). Compares per-iter wall
time + total wall time, and checks numerical equivalence on (β, ∇, distance).

Rationale (see plans/results/20260418-2148h_A-weirdness-investigation.md): joblib
workers pay ~1.15 s each on import of AggFiscalModel.py. If per-agent work is
short relative to that, skipping joblib (→ serial) may be faster overall.

Usage:
    cd Code/HA-Models/FromPandemicCode
    python validate_nm_serial.py --edtype 1 --n-iters 10
"""
import argparse, json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
RESULTS_DIR = ROOT / "plans" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def run_one_mode(mode, edtype, n_iters):
    env = os.environ.copy()
    if mode == "serial":
        env["HAFISCAL_SERIAL"] = "1"
    env["HAFISCAL_NM_IN_PLACE"] = "1"
    env["HAFISCAL_EDTYPES"] = str(edtype)
    env["HAFISCAL_NM_VALIDATE_N_ITERS"] = str(n_iters)
    env["MPLBACKEND"] = "Agg"
    traj = RESULTS_DIR / f"nm_serial_{mode}_ed{edtype}.jsonl"
    if traj.exists():
        traj.unlink()
    env["HAFISCAL_NM_TRAJECTORY"] = str(traj)
    log = RESULTS_DIR / f"nm_serial_{mode}_ed{edtype}.log"
    print(f"[serial-test] mode={mode} edtype={edtype} n_iters={n_iters}")
    t0 = time.time()
    with open(log, "w") as logf:
        rc = subprocess.call([sys.executable, "EstimAggFiscalMAIN.py"],
                             cwd=str(HERE), env=env,
                             stdout=logf, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    print(f"[serial-test]   wall={wall:.0f}s rc={rc}")
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

    par_traj, par_rc, par_wall = run_one_mode("parallel", args.edtype, args.n_iters)
    ser_traj, ser_rc, ser_wall = run_one_mode("serial", args.edtype, args.n_iters)

    par = load_traj(par_traj)
    ser = load_traj(ser_traj)
    n = min(len(par), len(ser))

    if n == 0:
        print("[serial-test] no trajectory data — see logs")
        sys.exit(1)

    print()
    print("=" * 72)
    print(f"{'iter':>4} {'β_par':>10} {'β_ser':>10} {'d_par':>10} {'d_ser':>10}"
          f" {'t_par':>8} {'t_ser':>8}")
    print("-" * 72)
    for i in range(n):
        p_, s = par[i], ser[i]
        print(f"{i:>4} {p_['beta']:>10.6f} {s['beta']:>10.6f}"
              f" {p_['distance']:>10.6f} {s['distance']:>10.6f}"
              f" {p_['iter_sec']:>8.2f} {s['iter_sec']:>8.2f}")
    print("-" * 72)
    import numpy as np
    t_par = np.array([r['iter_sec'] for r in par[:n]])
    t_ser = np.array([r['iter_sec'] for r in ser[:n]])
    d_par = np.array([r['distance'] for r in par[:n]])
    d_ser = np.array([r['distance'] for r in ser[:n]])
    b_par = np.array([r['beta'] for r in par[:n]])
    b_ser = np.array([r['beta'] for r in ser[:n]])
    print(f"  per-iter mean: parallel {t_par.mean():.1f}s vs serial {t_ser.mean():.1f}s"
          f" — ratio {t_par.mean()/t_ser.mean():.2f}× ({'serial faster' if t_ser.mean()<t_par.mean() else 'parallel faster'})")
    print(f"  total wall:    parallel {par_wall:.0f}s vs serial {ser_wall:.0f}s"
          f" — ratio {par_wall/ser_wall:.2f}×")
    print(f"  max |Δβ|:      {np.abs(b_par - b_ser).max():.6f}")
    print(f"  max |Δd|:      {np.abs(d_par - d_ser).max():.6f}")


if __name__ == "__main__":
    main()
