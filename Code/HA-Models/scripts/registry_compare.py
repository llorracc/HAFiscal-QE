#!/usr/bin/env python
"""Compare two registered runs side-by-side.

Pulls config + metrics from the SQLite registry. Useful for QE comparisons
and for spotting cross-config drift.

Usage:
    python registry_compare.py <run_id_a> <run_id_b>
    python registry_compare.py latest_by_config <bucket_a> <bucket_b>

The first form takes two specific run_ids.
The second form looks up the latest run in each named bucket (the symlink
directory under views/latest_by_config/).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_HA_ROOT = _HERE.parent
sys.path.insert(0, str(_HA_ROOT))
import _registry  # noqa: E402


def _connect():
    return sqlite3.connect(str(_registry._DB_PATH))


def _fetch_run(conn, run_id: str) -> dict | None:
    cur = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def _fetch_metrics(conn, run_id: str) -> dict[str, object]:
    cur = conn.execute(
        "SELECT metric_name, metric_value, metric_json FROM metrics WHERE run_id = ?",
        (run_id,),
    )
    out = {}
    for name, value, js in cur:
        if value is not None:
            out[name] = value
        elif js is not None:
            try:
                out[name] = json.loads(js)
            except Exception:
                out[name] = js
    return out


def _fetch_outputs(conn, run_id: str) -> list[dict]:
    cur = conn.execute(
        "SELECT output_type, cohort, start_idx, path, content_hash, size_bytes FROM outputs WHERE run_id = ?",
        (run_id,),
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _fetch_bug_fixes(conn, run_id: str) -> list[str]:
    cur = conn.execute("SELECT bug_id FROM run_bug_fixes WHERE run_id = ?", (run_id,))
    return [row[0] for row in cur.fetchall()]


def _resolve_latest_by_config(bucket: str) -> str | None:
    """Resolve a config-bucket name (under views/latest_by_config/) to a run_id."""
    bucket_dir = _registry._VIEWS_ROOT / "latest_by_config" / bucket
    if not bucket_dir.exists():
        return None
    # All symlinks in this dir point to outputs/<type>/<run_id>.<ext>
    # Take any one and parse the run_id from its target
    for child in bucket_dir.iterdir():
        if child.is_symlink():
            target = os.readlink(str(child))
            # Target like ../../../outputs/step2_cal/<run_id>.txt
            run_id = Path(target).stem
            return run_id
    return None


def compare(run_id_a: str, run_id_b: str) -> int:
    conn = _connect()
    try:
        a = _fetch_run(conn, run_id_a)
        b = _fetch_run(conn, run_id_b)
        if a is None:
            print(f"ERROR: run not found: {run_id_a}")
            return 1
        if b is None:
            print(f"ERROR: run not found: {run_id_b}")
            return 1

        cfg_a = json.loads(a["config_json"])
        cfg_b = json.loads(b["config_json"])
        metrics_a = _fetch_metrics(conn, run_id_a)
        metrics_b = _fetch_metrics(conn, run_id_b)
        bugs_a = _fetch_bug_fixes(conn, run_id_a)
        bugs_b = _fetch_bug_fixes(conn, run_id_b)

        print("=" * 100)
        print(f"  A: {run_id_a}")
        print(f"     {a['date_local']}  commit={a['commit_sha'][:8]}  status={a['status']}")
        print(f"     config_summary: {_registry.config_summary(cfg_a)}")
        print(f"  B: {run_id_b}")
        print(f"     {b['date_local']}  commit={b['commit_sha'][:8]}  status={b['status']}")
        print(f"     config_summary: {_registry.config_summary(cfg_b)}")
        print("=" * 100)

        # Config diff
        print("\nCONFIG DIFFERENCES:")
        all_dims = sorted(set(cfg_a.keys()) | set(cfg_b.keys()))
        any_diff = False
        for dim in all_dims:
            va = cfg_a.get(dim, "<missing>")
            vb = cfg_b.get(dim, "<missing>")
            if va != vb:
                print(f"  {dim:30}: A={va!r:30}  B={vb!r}")
                any_diff = True
        if not any_diff:
            print("  (configs identical)")

        # Bug-fix diff
        a_only = sorted(set(bugs_a) - set(bugs_b))
        b_only = sorted(set(bugs_b) - set(bugs_a))
        if a_only or b_only:
            print(f"\nBUG-FIX DIFFERENCES:")
            if a_only:
                print(f"  Only in A: {a_only}")
            if b_only:
                print(f"  Only in B: {b_only}")

        # Scalar metric diff
        print("\nSCALAR METRIC DIFFERENCES:")
        all_metrics = sorted(set(metrics_a.keys()) | set(metrics_b.keys()))
        diffs = []
        for name in all_metrics:
            va = metrics_a.get(name)
            vb = metrics_b.get(name)
            if isinstance(va, (int, float)) or isinstance(vb, (int, float)):
                if va != vb:
                    delta = (vb - va) if (isinstance(va, (int, float)) and isinstance(vb, (int, float))) else None
                    diffs.append((name, va, vb, delta))
        if diffs:
            print(f"  {'metric':<45}  {'A':>15}  {'B':>15}  {'B-A':>15}")
            for name, va, vb, delta in diffs:
                va_s = f"{va:.6g}" if isinstance(va, (int, float)) else "—"
                vb_s = f"{vb:.6g}" if isinstance(vb, (int, float)) else "—"
                d_s = f"{delta:+.6g}" if delta is not None else "—"
                print(f"  {name:<45}  {va_s:>15}  {vb_s:>15}  {d_s:>15}")
        else:
            print("  (no scalar metric differences)")

        # Output type coverage
        outputs_a = {o["output_type"] for o in _fetch_outputs(conn, run_id_a)}
        outputs_b = {o["output_type"] for o in _fetch_outputs(conn, run_id_b)}
        a_only_o = sorted(outputs_a - outputs_b)
        b_only_o = sorted(outputs_b - outputs_a)
        if a_only_o or b_only_o:
            print("\nOUTPUT-TYPE COVERAGE DIFFERENCES:")
            if a_only_o:
                print(f"  Only in A: {a_only_o}")
            if b_only_o:
                print(f"  Only in B: {b_only_o}")

        return 0
    finally:
        conn.close()


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 1
    if argv[1] == "latest_by_config":
        if len(argv) < 4:
            print(__doc__)
            return 1
        bucket_a = argv[2]
        bucket_b = argv[3]
        run_id_a = _resolve_latest_by_config(bucket_a)
        run_id_b = _resolve_latest_by_config(bucket_b)
        if run_id_a is None:
            print(f"ERROR: bucket not found: {bucket_a}")
            print("Available buckets:")
            for d in sorted((_registry._VIEWS_ROOT / "latest_by_config").iterdir()):
                if d.is_dir():
                    print(f"  {d.name}")
            return 1
        if run_id_b is None:
            print(f"ERROR: bucket not found: {bucket_b}")
            return 1
        return compare(run_id_a, run_id_b)
    return compare(argv[1], argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
