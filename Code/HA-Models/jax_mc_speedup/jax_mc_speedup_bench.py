"""Benchmark harness for JAX MC speedup work.

Runs solve_ad_recession_jax_multicohort at HS_Only scale (small, fast),
records:
  - wall time per AD iter (and total)
  - final Cratio_hist (for parity vs other implementations)
  - AggCons sum, AggInc sum (for parity sanity)
  - per-cohort cLvl panel checksum (for kernel parity)

Save outputs to a .npz file named by --label so successive runs can be
compared.

Usage:
  python jax_mc_speedup_bench.py --label baseline_v0
  # ... edit code ...
  python jax_mc_speedup_bench.py --label 1A_lift_cFunc_2D
  # compare:
  python jax_mc_speedup_bench.py --compare baseline_v0 1A_lift_cFunc_2D
"""
from __future__ import annotations
import argparse
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
# After moving out of FromPandemicCode/, still need to find welfare6_scenario etc.
sys.path.insert(0, os.path.join(_HERE, "..", "FromPandemicCode"))


def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=False, default=None,
                   help="Label for this run; saves to RESULTS_DIR/<label>.npz")
    p.add_argument("--compare", nargs="+", default=None,
                   help="Compare two saved labels: --compare A B")
    p.add_argument("--parametrization", default="HS_Only",
                   choices=["HS_Only", "Reduced_Run", "Baseline"])
    p.add_argument("--num-iter", type=int, default=4)
    return p.parse_args()


_ARGS = _parse_args()
# Clear sys.argv before downstream imports (Parameters.py reads it).
sys.argv = [sys.argv[0]]

# Use CPU JAX by default for stable timing (GPU dispatch noise is large at
# this scale; CPU JIT throughput is what we're optimizing for here).
os.environ.setdefault("JAX_ENABLE_X64", "True")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import jax

jax.config.update("jax_enable_x64", True)
import numpy as np

RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "speedup_bench_results"
)
os.makedirs(RESULTS_DIR, exist_ok=True)


def run_one(parametrization="HS_Only", num_iter=4):
    """Build + solve + run JAX MC AD; return a dict of timings + outputs."""
    from welfare6_scenario import build_and_solve, run_base

    t_build_start = time.time()
    ctx = build_and_solve(parametrization)
    AggEco = ctx["AggEco"]
    print(f"[bench] built in {time.time()-t_build_start:.1f}s, "
          f"{len(AggEco.agents)} cohorts", flush=True)

    # run_base populates AggEco.base_AggCons in-place
    _ = run_base(ctx)
    base_AggCons = AggEco.base_AggCons
    print(f"[bench] base_AggCons: shape={base_AggCons.shape}, "
          f"sum={float(np.sum(base_AggCons)):.4f}", flush=True)

    print(f"[bench] launching JAX MC AD ({num_iter} iters)...", flush=True)
    t_jax_start = time.time()
    # Route through cached_solve_ad_recession when cache env is on so the
    # bench actually exercises the cache. Falls through to direct call when
    # off — preserves prior measurement semantics.
    use_cache = os.environ.get("HAFISCAL_USE_SOLUTION_CACHE", "0") == "1"
    if use_cache:
        # Find solution_cache package
        _scache_parent = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        if _scache_parent not in sys.path:
            sys.path.insert(0, _scache_parent)
        from solution_cache import cached_solve_ad_recession
        res = cached_solve_ad_recession(
            {"AggEco": AggEco}, base_AggCons,
            num_max_iterations=num_iter,
            convergence_cutoff=1e-9,
            shock_type="recession",
            seeds=(0, 1),
            verbose=True,
        )
    else:
        from jax_mc_ad_multicohort import solve_ad_recession_jax_multicohort
        res = solve_ad_recession_jax_multicohort(
            AggEco, base_AggCons,
            num_max_iterations=num_iter,
            convergence_cutoff=1e-9,
            shock_type="recession",
            seeds=(0, 1),
            verbose=True,
        )
    wall_jax = time.time() - t_jax_start

    out = {
        "wall_jax_total": wall_jax,
        "n_iters": len(res["iter_history"]),
        "per_iter_wall": [it["wall"] for it in res["iter_history"]],
        "Cratio_hist": np.asarray(res["final_Cratio_hist"]),
        "AggCons_sum": float(np.sum(res["final_AggCons"])),
        "AggIncome_sum": float(np.sum(res.get("final_AggIncome", np.zeros(1)))),
        "cLvl_panel_sum": float(np.sum(res["final_cLvl_all_splurge"])
                                 if res.get("final_cLvl_all_splurge") is not None
                                 else 0.0),
        "cLvl_panel_shape": (res["final_cLvl_all_splurge"].shape
                              if res.get("final_cLvl_all_splurge") is not None
                              else None),
        "cohort_weights": list(res.get("cohort_weights", [])),
    }
    return out


def main():
    args = _ARGS

    if args.compare is not None:
        if len(args.compare) != 2:
            raise SystemExit("--compare needs exactly 2 labels")
        compare(args.compare[0], args.compare[1])
        return

    if args.label is None:
        raise SystemExit("--label is required for a run (unless --compare)")

    out = run_one(args.parametrization, args.num_iter)
    out_path = os.path.join(RESULTS_DIR, f"{args.label}.npz")
    np.savez(out_path, **{k: np.asarray(v) if not callable(v) else v
                          for k, v in out.items() if v is not None})
    print(f"[bench] saved {out_path}")
    print(f"[bench] wall_jax_total: {out['wall_jax_total']:.2f}s")
    print(f"[bench] per-iter walls: "
          f"{[f'{t:.2f}' for t in out['per_iter_wall']]}")
    print(f"[bench] Cratio_hist[0]: {out['Cratio_hist'][0]:.6f}")
    print(f"[bench] cLvl_panel_sum: {out['cLvl_panel_sum']:.4f}")


def compare(label_a, label_b):
    a = np.load(os.path.join(RESULTS_DIR, f"{label_a}.npz"), allow_pickle=True)
    b = np.load(os.path.join(RESULTS_DIR, f"{label_b}.npz"), allow_pickle=True)

    print(f"=== Comparing {label_a} vs {label_b} ===")
    wa, wb = float(a["wall_jax_total"]), float(b["wall_jax_total"])
    print(f"  Wall: {wa:.2f}s -> {wb:.2f}s ({wa/wb:.2f}x speedup)")

    cr_a, cr_b = np.asarray(a["Cratio_hist"]), np.asarray(b["Cratio_hist"])
    if cr_a.shape == cr_b.shape:
        max_diff = float(np.max(np.abs(cr_a - cr_b)))
        rel_diff = float(np.max(np.abs((cr_a - cr_b) / np.maximum(np.abs(cr_a), 1e-12))))
        print(f"  Cratio_hist: max abs diff = {max_diff:.2e}, "
              f"max rel diff = {rel_diff:.2e}")
    else:
        print(f"  Cratio_hist shape mismatch: {cr_a.shape} vs {cr_b.shape}")

    for k in ("AggCons_sum", "AggIncome_sum", "cLvl_panel_sum"):
        va, vb = float(a[k]), float(b[k])
        if va != 0:
            rel = abs(va - vb) / abs(va)
            print(f"  {k}: {va:.4f} -> {vb:.4f} (rel diff {rel:.2e})")
        else:
            print(f"  {k}: {va:.4f} -> {vb:.4f}")


if __name__ == "__main__":
    main()
