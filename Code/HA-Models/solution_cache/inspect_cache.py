"""Print a summary of what's in the on-disk solution cache.

Usage:
    .venv-linux-x86_64/bin/python Code/HA-Models/solution_cache/inspect_cache.py
    .venv-linux-x86_64/bin/python Code/HA-Models/solution_cache/inspect_cache.py --detail
    .venv-linux-x86_64/bin/python Code/HA-Models/solution_cache/inspect_cache.py --filter Baseline
"""
import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))


def _human(n_bytes):
    for unit in ("B", "K", "M", "G", "T"):
        if n_bytes < 1024:
            return f"{n_bytes:6.1f}{unit}"
        n_bytes /= 1024
    return f"{n_bytes:6.1f}P"


def _age(saved_at):
    """Format saved_at as "1h 23m ago", etc."""
    if not saved_at:
        return "unknown"
    age_sec = time.time() - saved_at
    if age_sec < 60:
        return f"{int(age_sec)}s ago"
    if age_sec < 3600:
        return f"{int(age_sec / 60)}m ago"
    if age_sec < 86400:
        return f"{age_sec / 3600:.1f}h ago"
    return f"{age_sec / 86400:.1f}d ago"


def _list_entries(filter_str=None):
    """Walk the cache dir and yield (parametrization, shock_type, pkl_path, meta_path)."""
    for parametrization in sorted(os.listdir(_HERE)):
        full = os.path.join(_HERE, parametrization)
        if not os.path.isdir(full) or parametrization.startswith("_"):
            continue
        if parametrization in ("__pycache__",):
            continue
        if filter_str and filter_str.lower() not in parametrization.lower():
            continue
        for shock_type in sorted(os.listdir(full)):
            sub = os.path.join(full, shock_type)
            if not os.path.isdir(sub):
                continue
            for f in sorted(os.listdir(sub)):
                if not f.endswith(".pkl"):
                    continue
                pkl_path = os.path.join(sub, f)
                meta_path = pkl_path[:-len(".pkl")] + ".meta.json"
                yield parametrization, shock_type, pkl_path, meta_path


def _summary(filter_str=None):
    """Top-level summary: per-parametrization × shock_type entry counts and sizes."""
    per_dir = {}
    for parametrization, shock_type, pkl_path, _ in _list_entries(filter_str):
        key = (parametrization, shock_type)
        d = per_dir.setdefault(key, {"count": 0, "bytes": 0})
        d["count"] += 1
        try:
            d["bytes"] += os.path.getsize(pkl_path)
        except OSError:
            pass

    total_count = 0
    total_bytes = 0
    print(f"{'Parametrization':22s} {'shock_type':22s} {'entries':>8s}  {'size':>8s}")
    print("-" * 70)
    cur_p = None
    for (parametrization, shock_type) in sorted(per_dir):
        d = per_dir[(parametrization, shock_type)]
        p_str = parametrization if parametrization != cur_p else ""
        cur_p = parametrization
        print(f"{p_str:22s} {shock_type:22s} {d['count']:8d}  {_human(d['bytes'])}")
        total_count += d["count"]
        total_bytes += d["bytes"]
    print("-" * 70)
    print(f"{'TOTAL':22s} {'':22s} {total_count:8d}  {_human(total_bytes)}")


def _detail(filter_str=None):
    """Per-entry: pkl, size, age, mc_method, AD result_type."""
    print(f"{'parametrization':18s} {'shock_type':22s} {'mc_method':22s} "
          f"{'result_type':18s} {'size':>8s}  {'age':>10s}  {'tag':28s}")
    print("-" * 145)
    for parametrization, shock_type, pkl_path, meta_path in _list_entries(filter_str):
        try:
            sz = os.path.getsize(pkl_path)
        except OSError:
            sz = 0
        mc_method = "?"
        result_type = "?"
        saved_at = None
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                inputs = meta.get("inputs") or {}
                mc_method = inputs.get("mc_method", "?")
                result_type = meta.get("result_type", "single-solve")
                saved_at = meta.get("saved_at")
            except (OSError, ValueError):
                pass
        tag = os.path.basename(pkl_path)
        # Truncate the short-hash trailing chunk for readability
        if len(tag) > 28:
            tag = tag[:25] + "..."
        print(f"{parametrization:18s} {shock_type:22s} {mc_method:22s} "
              f"{result_type:18s} {_human(sz):>8s}  {_age(saved_at):>10s}  {tag:28s}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--detail", action="store_true",
                   help="Per-entry detail with mc_method, result_type, age")
    p.add_argument("--filter", default=None,
                   help="Substring filter on parametrization name")
    args = p.parse_args()

    if args.detail:
        _detail(args.filter)
    else:
        _summary(args.filter)


if __name__ == "__main__":
    main()
