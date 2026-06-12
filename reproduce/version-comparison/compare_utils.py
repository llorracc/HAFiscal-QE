"""Comparison utilities for version equivalence testing."""

import json
import sys
import numpy as np


def json_safe(obj):
    """Convert numpy types to JSON-serializable Python types."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(x) for x in obj]
    return obj


def flatten_metrics(d, prefix=""):
    """Flatten a nested dict into dot-separated keys with scalar/list values."""
    flat = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            flat.update(flatten_metrics(v, key))
        else:
            flat[key] = v
    return flat


def compare_json(result_014, result_017, atol=1e-14):
    """Compare two JSON result dicts, returning a per-metric comparison report.

    Returns (all_pass, report_rows) where each row is a dict with keys:
        metric, val_014, val_017, abs_diff, rel_diff, verdict
    """
    flat_014 = flatten_metrics(result_014)
    flat_017 = flatten_metrics(result_017)

    all_keys = sorted(set(flat_014.keys()) | set(flat_017.keys()))
    rows = []
    all_pass = True

    for key in all_keys:
        v0 = flat_014.get(key)
        v1 = flat_017.get(key)

        if v0 is None or v1 is None:
            rows.append(dict(metric=key, val_014=v0, val_017=v1,
                             abs_diff=None, rel_diff=None, verdict="MISSING"))
            all_pass = False
            continue

        if isinstance(v0, list) and isinstance(v1, list):
            a0, a1 = np.array(v0, dtype=float), np.array(v1, dtype=float)
            if a0.shape != a1.shape:
                rows.append(dict(metric=key, val_014=v0, val_017=v1,
                                 abs_diff=None, rel_diff=None, verdict="SHAPE_MISMATCH"))
                all_pass = False
                continue
            ad = float(np.max(np.abs(a0 - a1)))
            denom = np.maximum(np.abs(a0), np.abs(a1))
            denom[denom == 0] = 1.0
            rd = float(np.max(np.abs(a0 - a1) / denom))
        elif isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
            ad = abs(v0 - v1)
            denom = max(abs(v0), abs(v1), 1e-300)
            rd = ad / denom
        else:
            if v0 == v1:
                rows.append(dict(metric=key, val_014=v0, val_017=v1,
                                 abs_diff=0, rel_diff=0, verdict="PASS"))
            else:
                rows.append(dict(metric=key, val_014=v0, val_017=v1,
                                 abs_diff=None, rel_diff=None, verdict="TYPE_MISMATCH"))
                all_pass = False
            continue

        if ad <= atol:
            verdict = "PASS"
        elif ad <= 1e-10:
            verdict = "WARN"
        else:
            verdict = "FAIL"
            all_pass = False

        rows.append(dict(metric=key, val_014=str(v0)[:40], val_017=str(v1)[:40],
                         abs_diff=ad, rel_diff=rd, verdict=verdict))

    return all_pass, rows


def print_report(step_name, rows, file=sys.stdout):
    """Print a formatted comparison report."""
    print(f"\n{'='*80}", file=file)
    print(f"  {step_name}", file=file)
    print(f"{'='*80}", file=file)
    hdr = f"{'Metric':<45} {'AbsDiff':>12} {'RelDiff':>12} {'Verdict':>8}"
    print(hdr, file=file)
    print("-" * len(hdr), file=file)
    for r in rows:
        ad = f"{r['abs_diff']:.2e}" if r['abs_diff'] is not None else "N/A"
        rd = f"{r['rel_diff']:.2e}" if r['rel_diff'] is not None else "N/A"
        print(f"{r['metric']:<45} {ad:>12} {rd:>12} {r['verdict']:>8}", file=file)
