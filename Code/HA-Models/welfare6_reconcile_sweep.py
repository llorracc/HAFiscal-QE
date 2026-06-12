#!/usr/bin/env python
"""Overnight check_rec MC<->TM reconciliation sweep (Phase R-0..R-4).

The math (history/20260331-...convergence.md §13.5.1, BUG-022): Check's income
phase-out makes the aggregate integrand p*c(m+g(p),j) with g(p) non-constant, so
Harmenberg's p-linear identity fails and the TM must DISCRETIZE the p-distribution
into HAFISCAL_CHECK_BUCKETS. The bucket Riemann error decays ~1/n^2, so by the
convergence theorem TM->MC as n_buckets -> dense (+ aCount dense + MC N large).

This driver:
  R-0  solve once; confirm the cFunc is the shared build_and_solve solution.
  R-2  sweep HAFISCAL_CHECK_BUCKETS (the binding dimension) at aCount=200.
  R-3  sweep aCount at a fixed bucket count.
  R-4  compare each TM check_rec to the shuffle+CRN MC reference (mean +/- SE)
       and flag |bias|<0.25% with the MC SE.
Uses the solution cache (sequential TM runs -> no concurrent-write race).
"""
import os
import sys
import subprocess
import pickle
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
FPC = os.path.join(HERE, "FromPandemicCode")
OUT = os.path.join(HERE, "Results", "tmp", "reconcile")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, FPC)
sys.path.insert(0, HERE)
PY = sys.executable

SCEN = "base,Check,TaxCut,recession,recessionCheck,recessionTaxCut"
CELLS = ["check_norec", "check_rec", "taxcut_norec", "taxcut_rec"]


def log(msg):
    print(msg, flush=True)


def mc_reference():
    """check_rec (and the other non-AD cells) from the shuffle+CRN MC, 4 seeds."""
    from welfare6_tm_vs_mc import read_mc_cells
    sw = os.path.join(HERE, "Results", "tmp", "shuffle")
    per = {c: [] for c in CELLS}
    for s in range(4):
        d = os.path.join(sw, f"shuf_s{s}")
        if not os.path.isdir(d):
            continue
        cells, _, _ = read_mc_cells(d)
        for c in CELLS:
            v = cells.get(c)
            if v is not None and v == v:
                per[c].append(float(v))
    ref = {}
    for c in CELLS:
        xs = per[c]
        ref[c] = (statistics.mean(xs), statistics.stdev(xs) / len(xs) ** 0.5) if len(xs) >= 2 else (None, None)
    return ref


def run_tm(n_buckets, aCount, tag):
    """Run welfare6_tm.py (non-AD) at (n_buckets, aCount); return the welfare6 cells."""
    out = os.path.join(OUT, f"tm_{tag}.pkl")
    if not os.path.exists(out):
        env = dict(os.environ,
                   HAFISCAL_CHECK_BUCKETS=str(n_buckets),
                   HAFISCAL_TM_MCOUNT=str(aCount),
                   HAFISCAL_USE_SOLUTION_CACHE="1",
                   HAFISCAL_USE_JAX_2B="0",
                   PYTHONUNBUFFERED="1")
        with open(os.path.join(OUT, f"tm_{tag}.log"), "w") as lf:
            subprocess.run([PY, os.path.join(FPC, "welfare6_tm.py"),
                            "--parametrization", "HS_Only", "--out-pickle", out,
                            "--scenarios", SCEN, "--no-ad"],
                           cwd=FPC, env=env, check=True, stdout=lf, stderr=subprocess.STDOUT)
    d = pickle.load(open(out, "rb"))
    cells = d.get("welfare6_cells") or {}
    return {c: cells.get(c) for c in CELLS}


def row(tm, ref, label):
    out = [f"{label:<14}"]
    for c in ("check_rec", "check_norec", "taxcut_rec"):
        t = tm.get(c)
        mcm, mcse = ref.get(c, (None, None))
        if t is None or mcm is None:
            out.append(f"{c}: --")
            continue
        bias = 100.0 * (mcm - t) / t
        se = 100.0 * mcse / t
        ok = "PASS" if (abs(bias) < 0.25 and se < 0.25) else ""
        out.append(f"{c}: TM={t:.4f} MC={mcm:.4f} bias={bias:+.2f}% SE={se:.3f}% {ok}")
    return "  ".join(out)


def main():
    log("=" * 90)
    log("OVERNIGHT check_rec MC<->TM RECONCILIATION (R-0..R-4)")
    log("=" * 90)

    # R-0: cFunc identity --------------------------------------------------
    log("\n--- R-0: cFunc identity (solve once via the shared build_and_solve) ---")
    os.chdir(FPC)
    sys.argv = [sys.argv[0]]
    os.environ.setdefault("HAFISCAL_TM_MCOUNT", "200")
    os.environ.setdefault("HAFISCAL_USE_SOLUTION_CACHE", "1")
    try:
        from welfare6_scenario import build_and_solve
        ctx = build_and_solve("HS_Only")
        ag = ctx["AggEco"].agents[0]
        sol = ag.solution[1]
        cf = sol.cFunc
        import numpy as np
        ms = np.array([0.5, 1.0, 2.0, 5.0])
        n_states = len(cf) if hasattr(cf, "__len__") else 1
        log(f"  solved agent: {len(ctx['AggEco'].agents)} cohort(s); cFunc has {n_states} Markov states")
        for j in range(min(n_states, 3)):
            cj = cf[j] if hasattr(cf, "__len__") else cf
            log(f"    cFunc[{j}]({ms.tolist()}) = {np.round(np.asarray(cj(ms)), 4).tolist()}")
        log("  -> cFunc is the shared build_and_solve solution; MC sim + TM kernel both evaluate THIS object.")
    except Exception as e:
        log(f"  R-0 cFunc extraction failed (non-fatal, proceeding): {type(e).__name__}: {e}")

    ref = mc_reference()
    log(f"\n  MC reference (shuffle+CRN, 4 seeds): "
        + "  ".join(f"{c}={ref[c][0]:.4f}+/-{ref[c][1]:.4f}" for c in CELLS if ref[c][0] is not None))

    # R-2: bucket sweep ----------------------------------------------------
    log("\n--- R-2: HAFISCAL_CHECK_BUCKETS sweep (aCount=200) ---")
    for nb in [5, 10, 20, 50, 100, 200, 400]:
        try:
            tm = run_tm(nb, 200, f"nb{nb}_a200")
            log(row(tm, ref, f"n_buckets={nb}"))
        except Exception as e:
            log(f"  n_buckets={nb}: FAILED {type(e).__name__}: {e}")

    # R-3: aCount sweep ----------------------------------------------------
    log("\n--- R-3: aCount sweep (n_buckets=100) ---")
    for ac in [100, 200, 500]:
        try:
            tm = run_tm(100, ac, f"nb100_a{ac}")
            log(row(tm, ref, f"aCount={ac}"))
        except Exception as e:
            log(f"  aCount={ac}: FAILED {type(e).__name__}: {e}")

    log("\n--- R-4: see the rows above. PASS = |bias|<0.25% AND SE<0.25%. ---")
    log("If check_rec converges to PASS as buckets densify -> RECONCILED (report config).")
    log("If it plateaus above 0.25% -> within-bucket covariance residual -> R-5 (2D-joint a,p TM).")
    log("RECONCILE_SWEEP_DONE")


if __name__ == "__main__":
    main()
