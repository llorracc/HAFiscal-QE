#!/usr/bin/env python3
"""Read registry.jsonl and emit a markdown table.

Usage:
    python summarize.py                          # all experiments
    python summarize.py --tag option-E.1         # filter by tag
    python summarize.py --tag 2B,parallel_solve  # AND of tags
    python summarize.py --cols id,timing.wall_total_s,outcome
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "registry.jsonl"

DEFAULT_COLS = [
    "id",
    "config.backend",
    "config.n_threads",
    "config.n_workers",
    "config.num_iter",
    "timing.wall_total_s",
    "timing.wall_ref_sim_s",
    "timing.wall_iter_s",
    "correctness.Cratio_0",
    "memory.peak_rss_parent_mb",
    "memory.peak_vram_mb",
    "outcome",
]


def get(d: dict, dotted: str):
    cur = d
    for k in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        if abs(v) >= 1000 or abs(v) < 0.001:
            return f"{v:.2e}"
        return f"{v:.3g}"
    if isinstance(v, list):
        return "[" + ",".join(fmt(x) for x in v) + "]"
    if isinstance(v, str) and len(v) > 60:
        return v[:57] + "..."
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="",
                    help="Comma-separated tags (AND filter)")
    ap.add_argument("--cols", default=",".join(DEFAULT_COLS),
                    help="Comma-separated dotted column paths")
    ap.add_argument("--registry", default=str(REGISTRY))
    args = ap.parse_args()

    if not Path(args.registry).exists():
        print(f"(no registry at {args.registry})")
        return

    needed_tags = set(t for t in args.tag.split(",") if t.strip())
    rows = []
    for line in Path(args.registry).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if needed_tags and not needed_tags.issubset(set(rec.get("tags", []))):
            continue
        rows.append(rec)

    cols = [c.strip() for c in args.cols.split(",") if c.strip()]
    print("| " + " | ".join(cols) + " |")
    print("| " + " | ".join("---" for _ in cols) + " |")
    for r in rows:
        cells = [fmt(get(r, c)) for c in cols]
        print("| " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
