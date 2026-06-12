#!/usr/bin/env python3
"""Diff two experiments by id. Shows config delta, timing delta, and
correctness comparison side-by-side.

Usage:
    python cross.py <baseline_id> <new_id>
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "registry.jsonl"


def load_records() -> dict:
    out = {}
    if not REGISTRY.exists():
        return out
    for line in REGISTRY.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            out[rec["id"]] = rec
        except Exception:
            continue
    return out


def flatten(d, prefix=""):
    out = {}
    for k, v in (d or {}).items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(flatten(v, key))
        else:
            out[key] = v
    return out


def pct(a, b):
    if a is None or b is None:
        return None
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    if a == 0:
        return None
    return 100.0 * (b - a) / a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline_id")
    ap.add_argument("new_id")
    args = ap.parse_args()

    recs = load_records()
    if args.baseline_id not in recs:
        raise SystemExit(f"baseline_id not found: {args.baseline_id}")
    if args.new_id not in recs:
        raise SystemExit(f"new_id not found: {args.new_id}")
    base = recs[args.baseline_id]
    new = recs[args.new_id]

    print(f"# {args.baseline_id}  →  {args.new_id}")
    print()
    print(f"- baseline git_sha: {base.get('git_sha')}")
    print(f"- new      git_sha: {new.get('git_sha')}")
    print()
    print("## Config delta")
    bc = flatten(base.get("config", {}), "config")
    nc = flatten(new.get("config", {}), "config")
    keys = sorted(set(bc) | set(nc))
    for k in keys:
        if bc.get(k) != nc.get(k):
            print(f"- {k}: {bc.get(k)} → {nc.get(k)}")
    print()
    print("## Timing delta")
    bt = flatten(base.get("timing", {}), "timing")
    nt = flatten(new.get("timing", {}), "timing")
    keys = sorted(set(bt) | set(nt))
    print("| metric | baseline | new | Δ% |")
    print("| --- | --- | --- | --- |")
    for k in keys:
        a = bt.get(k); b = nt.get(k)
        d = pct(a, b)
        d_s = f"{d:+.1f}%" if d is not None else "—"
        print(f"| {k} | {a} | {b} | {d_s} |")
    print()
    print("## Correctness")
    for k in ("Cratio_0", "Total_Diff_final", "has_error"):
        print(f"- {k}: {base.get('correctness',{}).get(k)} vs {new.get('correctness',{}).get(k)}")
    print()
    print("## Hypothesis / outcome")
    print(f"- baseline outcome: {base.get('outcome', '—')}")
    print(f"- new hypothesis : {new.get('hypothesis', '—')}")
    print(f"- new outcome   : {new.get('outcome', '—')}")


if __name__ == "__main__":
    main()
