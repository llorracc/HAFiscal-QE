#!/usr/bin/env python3
"""Append one experiment record to registry.jsonl.

Parses the four artifacts that launch_bench.sh produces (bench.log,
timing.log, mem.csv, launch.meta) and emits one JSON object per line
into registry.jsonl. Hypothesis/outcome/tags/parent_ids must be passed
on the command line (the harness can't infer them).

Usage:
    python append.py --label 1thr_cpu_par2 \\
        --hypothesis "Spawn pool parallelizes ref sim solve" \\
        --outcome "Bit-identical correctness, +15% wall, less than expected 2x" \\
        --tags option-E.1,parallel_solve,2B \\
        --parent-ids 2026-06-01T15:53_baseline_2iter_cpu_1thr \\
        --vs-baseline 2026-06-01T15:53_baseline_2iter_cpu_1thr

Idempotent: if a record with the same id already exists in the
registry, refuses to append unless --force is passed.
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent.parent
THREADS_DIR = REPO_ROOT / "Code" / "HA-Models" / "jax_mc_speedup" / "threads_bench_logs"
REGISTRY = HERE / "registry.jsonl"


def parse_meta(path: Path) -> dict:
    """Parse <LABEL>.launch.meta — simple KEY=VAL lines."""
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k] = v
    return out


def parse_timing(path: Path) -> dict:
    """Parse /usr/bin/time -v output."""
    text = path.read_text()
    out = {}
    m = re.search(r"Maximum resident set size \(kbytes\):\s+(\d+)", text)
    if m:
        out["peak_rss_parent_mb"] = int(m.group(1)) // 1024
    m = re.search(r"Elapsed \(wall clock\) time .*?: ([\d:.]+)", text)
    if m:
        out["elapsed_str"] = m.group(1)
        out["wall_total_s"] = _hms_to_seconds(m.group(1))
    m = re.search(r"Percent of CPU this job got:\s+(\d+)%", text)
    if m:
        out["avg_cpu_pct"] = int(m.group(1))
    m = re.search(r"Exit status:\s+(\d+)", text)
    if m:
        out["exit_status"] = int(m.group(1))
    return out


def _hms_to_seconds(s: str) -> float:
    """Convert "MM:SS.ss" or "H:MM:SS" → seconds."""
    parts = s.split(":")
    if len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return float(s)


def parse_mem_csv(path: Path) -> dict:
    """Find peak RSS and peak GPU usage from poller CSV.

    CSV header: elapsed_s,vmrss_mb,vmsize_mb,nthreads[,gpu_used_mb,gpu_util_pct]
    """
    if not path.exists():
        return {}
    lines = path.read_text().splitlines()
    if len(lines) < 2:
        return {}
    header = lines[0].split(",")
    has_gpu = "gpu_used_mb" in header
    peak_rss = 0
    peak_vram = 0
    for line in lines[1:]:
        cells = line.split(",")
        if len(cells) < 4 or not cells[1].isdigit():
            continue
        peak_rss = max(peak_rss, int(cells[1]))
        if has_gpu and len(cells) >= 5 and cells[4].isdigit():
            peak_vram = max(peak_vram, int(cells[4]))
    out = {"poller_peak_rss_parent_mb": peak_rss}
    if has_gpu:
        out["peak_vram_mb"] = peak_vram if peak_vram > 0 else None
    return out


def parse_bench_log(path: Path) -> dict:
    """Extract wall_jax_total, per-iter walls, Cratio[0], Total_Diff,
    ref-sim wall, and correctness markers from bench stdout."""
    text = path.read_text()
    out = {"iter_walls_s": [], "iter_total_diff": [], "iter_cratio0": []}

    m = re.search(r"wall_jax_total:\s+([\d.]+)\s*s", text)
    if m:
        out["wall_jax_total_s"] = float(m.group(1))
    m = re.search(r"HARK ref done in ([\d.]+)s", text)
    if m:
        out["wall_ref_sim_s"] = float(m.group(1))
    m = re.search(r"Cratio_hist\[0\]:\s+([\d.]+)", text)
    if m:
        out["Cratio_0"] = float(m.group(1))

    # Per-iter completion lines
    for m in re.finditer(
        r"\[jax-ad-mc iter (\d+)\] Total_Diff=([\d.eE+-]+), "
        r"Cratio\[0\]=([\d.eE+-]+), wall=([\d.]+)s",
        text,
    ):
        out["iter_walls_s"].append(float(m.group(4)))
        out["iter_total_diff"].append(float(m.group(2)))
        out["iter_cratio0"].append(float(m.group(3)))
    if out["iter_total_diff"]:
        out["Total_Diff_final"] = out["iter_total_diff"][-1]

    # Errors
    if re.search(r"Traceback|RuntimeError|MemoryError|RESOURCE_EXHAUSTED", text):
        out["has_error"] = True
    return out


def git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT), stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return None


def make_id(timestamp: str, label: str, parametrization: str) -> str:
    # ISO timestamp to minute precision + slug
    ts_min = timestamp[:16].replace(":", "")  # e.g. 2026-06-01T1808
    return f"{ts_min}_{parametrization}_{label}"


def load_existing_ids() -> set[str]:
    if not REGISTRY.exists():
        return set()
    out = set()
    for line in REGISTRY.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.add(json.loads(line)["id"])
        except Exception:
            continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True,
                    help="LABEL from launch_bench.sh (file stems)")
    ap.add_argument("--logs-dir", default=str(THREADS_DIR),
                    help="Directory containing <label>.bench.log etc.")
    ap.add_argument("--hypothesis", default="(not recorded)")
    ap.add_argument("--outcome", default="(not recorded)")
    ap.add_argument("--tags", default="",
                    help="Comma-separated tags, e.g. option-E.1,2B,parallel_solve")
    ap.add_argument("--parent-ids", default="",
                    help="Comma-separated ids of experiments this one builds on")
    ap.add_argument("--vs-baseline", default="",
                    help="Baseline id to compute deltas against")
    ap.add_argument("--shock-type", default="recession")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite/append even if id exists")
    args = ap.parse_args()

    logs_dir = Path(args.logs_dir)
    meta_path = logs_dir / f"{args.label}.launch.meta"
    timing_path = logs_dir / f"{args.label}.timing.log"
    bench_path = logs_dir / f"{args.label}.bench.log"
    mem_path = logs_dir / f"{args.label}.mem.csv"

    if not meta_path.exists():
        sys.exit(f"[append] missing: {meta_path}")
    meta = parse_meta(meta_path)
    timing = parse_timing(timing_path) if timing_path.exists() else {}
    bench = parse_bench_log(bench_path) if bench_path.exists() else {}
    mem = parse_mem_csv(mem_path) if mem_path.exists() else {}

    timestamp = meta.get("LAUNCH_TIME", datetime.datetime.now().astimezone().isoformat())
    parametrization = meta.get("PARAM", "?")
    record_id = make_id(timestamp, args.label, parametrization)

    existing = load_existing_ids()
    if record_id in existing and not args.force:
        sys.exit(f"[append] {record_id} already in registry. Use --force to override.")

    # Build the record
    record = {
        "id": record_id,
        "label": args.label,
        "timestamp": timestamp,
        "git_sha": git_sha(),
        "config": {
            "parametrization": parametrization,
            "num_iter": int(meta.get("NUM_ITER", 0)) or None,
            "shock_type": args.shock_type,
            "backend": meta.get("BACKEND"),
            "n_threads": int(meta.get("N_THREADS", 1)),
            "n_workers": int(meta.get("N_WORKERS", 1)),
            "n_refsim_parallel": int(meta.get("N_REFSIM_PARALLEL", 1)),
            "use_jax_2b": meta.get("HAFISCAL_USE_JAX_2B") == "1",
            "use_solution_cache": meta.get("HAFISCAL_USE_SOLUTION_CACHE") == "1",
            "host": meta.get("HOST"),
        },
        "timing": {
            "wall_total_s": timing.get("wall_total_s"),
            "wall_jax_total_s": bench.get("wall_jax_total_s"),
            "wall_ref_sim_s": bench.get("wall_ref_sim_s"),
            "wall_iter_s": bench.get("iter_walls_s", []),
            "exit_status": timing.get("exit_status"),
        },
        "correctness": {
            "Cratio_0": bench.get("Cratio_0"),
            "Total_Diff_final": bench.get("Total_Diff_final"),
            "has_error": bench.get("has_error", False),
        },
        "memory": {
            "peak_rss_parent_mb": timing.get("peak_rss_parent_mb"),
            "peak_vram_mb": mem.get("peak_vram_mb"),
            "avg_cpu_pct": timing.get("avg_cpu_pct"),
        },
        "hypothesis": args.hypothesis,
        "outcome": args.outcome,
        "tags": [t for t in args.tags.split(",") if t.strip()],
        "log_paths": [
            str(bench_path.relative_to(REPO_ROOT)) if bench_path.exists() else None,
            str(timing_path.relative_to(REPO_ROOT)) if timing_path.exists() else None,
            str(mem_path.relative_to(REPO_ROOT)) if mem_path.exists() else None,
        ],
        "parent_ids": [s for s in args.parent_ids.split(",") if s.strip()],
    }
    if args.vs_baseline:
        record["vs_baseline"] = {"baseline_id": args.vs_baseline}
        # Deltas vs baseline computed by summarize.py / cross.py on demand
        # (avoids stale percentages when the baseline record changes).
    record["log_paths"] = [p for p in record["log_paths"] if p]

    with REGISTRY.open("a") as f:
        f.write(json.dumps(record) + "\n")
    print(f"[append] wrote {record_id} → {REGISTRY}")


if __name__ == "__main__":
    main()
