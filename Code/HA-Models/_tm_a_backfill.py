"""Backfill TM-a analytical moments for existing registered runs.

Per plan 20260503-1437h_mc_tma_companion_and_drift.md Phase 5.

For every registry run with status='complete' (skipping 'complete-backfilled'
legacy entries which lack full config info), this script:

  1. Reads the run's step2_cal output (if present)
  2. Builds the agents at that cal under the run's recorded interpretation
  3. Computes TM-a analytical moments (mean/var log_a, mean/var log_p)
  4. Records them in the registry's `metrics` table as
     `tma_analytical_mean_log_a`, etc.

This establishes a per-run TM-a baseline that future drift-aware MC runs
at the same configuration can compare against.

Limitations:
  - Backfill is best-effort. Runs with incomplete config info ('legacy_unknown'
    markers from the suffix-name backfill) are skipped.
  - Each backfilled run requires a TM-a build (~10-30 sec/cohort × 3 cohorts);
    20 runs ≈ 10-30 min total. Cache (HAFISCAL_TM_A_CACHE=1) speeds repeats.

Usage:
    python Code/HA-Models/_tm_a_backfill.py [--dry-run] [--commit <commit_sha>]

  --dry-run: print what would be done without writing
  --commit:  only backfill runs at this commit_sha (e.g. 'b748db35')
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE / "FromPandemicCode"))

import _registry  # noqa: E402


def _load_cal(cal_path: Path) -> list[dict] | None:
    """Read a saved cal file and return list of cohort dicts."""
    if not cal_path.exists():
        return None
    import ast as _ast
    rows = []
    for line in cal_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                rows.append(_ast.literal_eval(line))
            except Exception:
                pass
    return rows if rows else None


def _build_agents_and_compute_tma_moments(cal_rows: list[dict], interp: str) -> dict | None:
    """Build the 3 cohort BaseTypes at the given cal, then compute TM-a analytical moments.

    Returns a dict keyed by cohort label (D, HS, C) with mean/var log_a/log_p.
    """
    try:
        # Defer heavy imports (HARK setup) until actually needed
        os.environ["HAFISCAL_INTERPRETATION"] = interp
        import importlib
        import EstimParameters as _ep_mod
        importlib.reload(_ep_mod)
        # Build the BaseType list per cohort using existing Estimation_BetaNablaSplurge style
        from copy import deepcopy
        from HARK.distributions import Uniform
        from EstimParameters import (
            DiscFacCount, GICmaxBetas, minBeta, theGICfactor, gic_capped_beta,
        )
        # Need a BaseType per cohort. Easiest path: import from the
        # estim_phase2_tm_a module which already constructs them at module load.
        # Importing it executes top-level estimation logic, so guard with the
        # SKIP env var to avoid running NM.
        os.environ["HAFISCAL_SKIP_ESTIMATION"] = "1"
        os.environ["HAFISCAL_EDTYPES"] = ""  # signal "import only, don't estimate"
        import estim_phase2_tm_a as _ept
        BaseTypeList = _ept.BaseTypeList

        from tm_methods import build_tm_agg_fiscal_a, find_ergodic_distribution
        from _tm_a_drift import compute_tma_analytical_moments

        out = {}
        for row in cal_rows:
            ed = row.get("EducationGroup")
            if ed is None or ed not in (0, 1, 2):
                continue
            beta = float(row["beta"])
            spread = float(row["nabla"])
            GICx = float(row["GICx"])

            # Build the 7 atoms
            dfs = Uniform(beta - spread, beta + spread).discretize(DiscFacCount)
            # BUG-053: impose the cap on the GROWTH PATIENCE FACTOR via gic_capped_beta (shave**CRRA),
            # not the old raw beta-shave GICmaxBetas[ed]*exp(GICx)/(1+exp(GICx)). Mirrors
            # estim_phase2_tm_a.py:108. (Latent — this backfill util is off the active estimation path.)
            import numpy as _np
            cap = gic_capped_beta(ed, _np.exp(GICx) / (1.0 + _np.exp(GICx)))
            for k in range(DiscFacCount):
                if dfs.atoms[0][k] > cap:
                    dfs.atoms[0][k] = cap
                elif dfs.atoms[0][k] < minBeta:
                    dfs.atoms[0][k] = minBeta

            # Compute TM-a ergodic for the highest-weight (median) atom — proxy for cohort
            # (Computing for all 7 atoms then weighted-averaging is more accurate but
            # slower; for backfill purposes the median atom is a reasonable proxy.)
            mid_atom = DiscFacCount // 2
            agent = deepcopy(BaseTypeList[ed])
            agent.DiscFac = dfs.atoms[0][mid_atom]
            agent.AgentCount = 1000
            agent.solve()

            tm_data = build_tm_agg_fiscal_a(agent, aCount=200)
            ergodic = find_ergodic_distribution(tm_data["TranMatrix"])
            J = agent.MrkvArray[0].shape[0]

            moments = compute_tma_analytical_moments(
                ergodic, tm_data["dist_aGrid"], J,
                agent=agent, unemployment_rate=None,
            )
            label = ("d", "h", "c")[ed]
            out[label] = moments

        return out
    except Exception as e:
        print(f"  ERROR building TM-a for cal: {e!r}")
        return None


def backfill(*, dry_run: bool = False, only_commit: str | None = None) -> dict:
    _registry.ensure_db()
    conn = _registry._connect()
    try:
        if only_commit:
            cur = conn.execute(
                "SELECT run_id, config_json, commit_sha FROM runs "
                "WHERE status = 'complete' AND commit_sha LIKE ?",
                (f"{only_commit}%",),
            )
        else:
            cur = conn.execute(
                "SELECT run_id, config_json, commit_sha FROM runs "
                "WHERE status = 'complete'"
            )
        runs = cur.fetchall()
    finally:
        conn.close()

    print(f"Found {len(runs)} runs with status='complete' to backfill")
    n_done = 0
    n_skipped = 0
    for run_id, cfg_json, commit_sha in runs:
        cfg = json.loads(cfg_json)
        if cfg.get("step2_method") == "legacy_unknown":
            n_skipped += 1
            continue

        # Find the run's step2_cal output
        cal_path = _registry.find_output_path(run_id, "step2_cal")
        if cal_path is None:
            n_skipped += 1
            print(f"  {run_id}: SKIP (no step2_cal output)")
            continue

        cal_rows = _load_cal(cal_path)
        if cal_rows is None or len(cal_rows) < 3:
            n_skipped += 1
            print(f"  {run_id}: SKIP (cal file missing or incomplete)")
            continue

        interp = cfg.get("interpretation", "CDC")
        print(f"  {run_id}: building TM-a for {interp}, cal from {cal_path.name}")
        if dry_run:
            n_done += 1
            continue

        moments_by_cohort = _build_agents_and_compute_tma_moments(cal_rows, interp)
        if moments_by_cohort is None:
            n_skipped += 1
            continue

        # Record metrics
        flat_metrics = {}
        for cohort, moments in moments_by_cohort.items():
            for k, v in moments.items():
                flat_metrics[f"tma_analytical_{k}_{cohort}"] = float(v)
        _registry.record_metrics(run_id, flat_metrics)
        n_done += 1
        print(f"    recorded {len(flat_metrics)} TM-a analytical metrics")

    print(f"\nBackfill: {n_done} runs processed, {n_skipped} skipped.")
    return {"n_done": n_done, "n_skipped": n_skipped}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--commit", default=None,
                   help="Only backfill runs at this commit_sha prefix")
    args = p.parse_args()
    backfill(dry_run=args.dry_run, only_commit=args.commit)
