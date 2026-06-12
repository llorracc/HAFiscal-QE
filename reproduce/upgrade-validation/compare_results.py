#!/usr/bin/env python3
"""
Compare HAFiscal results between two snapshots or a snapshot and current results.

IMPORTANT: This tool focuses on NUMERICAL values, not file hashes.
File hashes are too brittle (change with timestamps, metadata, etc.)

Meaningful difference threshold: 0.02 log points (~2%)
- If ANY metric exceeds this, the tool will PAUSE and report for user review.

Usage:
    ./compare_results.py --baseline snapshots/baseline_20260124 --current
    ./compare_results.py --baseline snapshots/baseline_20260124 --attempt snapshots/attempt_20260124
    ./compare_results.py --baseline snapshots/baseline_20260124 --current --output comparisons/compare.md
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

# Project paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# Meaningful difference threshold in log points
# 0.02 log points ≈ 2% relative difference
MEANINGFUL_DIFF_THRESHOLD = 0.02


def load_snapshot(snapshot_dir):
    """Load all components of a snapshot."""
    path = Path(snapshot_dir)
    snapshot = {}
    
    # Primary files for numerical comparison
    files = [
        "metadata.json",
        "estimation_results.json", 
        "detailed_results.json",
        "multipliers.json",
        "table_values.json",  # Numerical values from .tex tables
    ]
    
    # Legacy/reference files (not used for validation)
    legacy_files = [
        "figures_hashes.json",  # Deprecated: hashes too brittle for validation
        "figures_metadata.json",  # Metadata only, not for numerical comparison
    ]
    
    for filename in files + legacy_files:
        filepath = path / filename
        if filepath.exists():
            with open(filepath, 'r') as f:
                snapshot[filename.replace('.json', '')] = json.load(f)
    
    return snapshot


def capture_current():
    """Capture current results without saving to disk."""
    from capture_snapshot import (
        get_git_info, get_hark_version, parse_result_file,
        parse_all_results_file, parse_hank_output, find_figures
    )
    
    CODE_DIR = PROJECT_ROOT / "Code" / "HA-Models"
    
    snapshot = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "hark_version": get_hark_version(),
            "git": get_git_info(),
            "notes": "Current state (not saved)",
        },
        "estimation_results": {},
        "detailed_results": {},
        "multipliers": {},
        "figures_hashes": {}
    }
    
    # Estimation results
    result_files = [
        ("Result_AllTarget", CODE_DIR / "Target_AggMPCX_LiquWealth" / "Result_AllTarget.txt"),
        ("Result_AllTarget_Splurge0", CODE_DIR / "Target_AggMPCX_LiquWealth" / "Result_AllTarget_Splurge0.txt"),
    ]
    for name, path in result_files:
        if path.exists():
            snapshot["estimation_results"][name] = parse_result_file(path)
    
    return snapshot


def compare_dicts(baseline, current, path=""):
    """Recursively compare two dictionaries and return differences."""
    diffs = []
    
    all_keys = set(baseline.keys()) | set(current.keys())
    
    for key in all_keys:
        key_path = f"{path}.{key}" if path else key
        
        if key not in baseline:
            diffs.append({
                "path": key_path,
                "type": "added",
                "current": current[key]
            })
        elif key not in current:
            diffs.append({
                "path": key_path,
                "type": "removed",
                "baseline": baseline[key]
            })
        elif isinstance(baseline[key], dict) and isinstance(current[key], dict):
            diffs.extend(compare_dicts(baseline[key], current[key], key_path))
        elif isinstance(baseline[key], (int, float)) and isinstance(current[key], (int, float)):
            if baseline[key] != current[key]:
                abs_diff = current[key] - baseline[key]
                rel_diff = abs_diff / baseline[key] * 100 if baseline[key] != 0 else float('inf')
                diffs.append({
                    "path": key_path,
                    "type": "changed",
                    "baseline": baseline[key],
                    "current": current[key],
                    "abs_diff": abs_diff,
                    "rel_diff": rel_diff
                })
        elif baseline[key] != current[key]:
            diffs.append({
                "path": key_path,
                "type": "changed",
                "baseline": baseline[key],
                "current": current[key]
            })
    
    return diffs


def log_point_diff(baseline_val, current_val, threshold=None):
    """
    Calculate the difference in log points between two values.
    log_point_diff = ln(current) - ln(baseline) ≈ (current - baseline) / baseline for small diffs
    
    Returns (log_diff, is_meaningful) tuple.
    """
    if threshold is None:
        threshold = MEANINGFUL_DIFF_THRESHOLD
        
    if baseline_val == 0 or current_val == 0:
        return (float('inf'), True) if baseline_val != current_val else (0.0, False)
    
    # Use absolute values for negative numbers (like tax cut multipliers)
    b = abs(baseline_val)
    c = abs(current_val)
    
    # Check if signs differ (definitely meaningful)
    if (baseline_val > 0) != (current_val > 0):
        return (float('inf'), True)
    
    log_diff = abs(math.log(c) - math.log(b))
    is_meaningful = log_diff > threshold
    
    return (log_diff, is_meaningful)


def generate_report(baseline, current, output_path=None, threshold=None):
    """
    Generate a comparison report focusing on NUMERICAL differences.
    
    IMPORTANT: If any metric exceeds the threshold (default 0.02 log points ~2%), 
    this function will flag it as a MEANINGFUL DIFFERENCE requiring user review.
    """
    if threshold is None:
        threshold = MEANINGFUL_DIFF_THRESHOLD
    
    meaningful_diffs = []  # Track metrics that exceed threshold
    
    lines = [
        "# HAFiscal Results Comparison Report",
        "",
        f"Generated: {datetime.now().isoformat()}",
        "",
        f"**Meaningful Difference Threshold:** {threshold:.3f} log points (~{threshold*100:.1f}%)",
        "",
        "## Metadata",
        "",
        "| Property | Baseline | Current |",
        "|----------|----------|---------|",
    ]
    
    # Metadata comparison
    b_meta = baseline.get("metadata", {})
    c_meta = current.get("metadata", {})
    
    lines.append(f"| HARK Version | {b_meta.get('hark_version', 'N/A')} | {c_meta.get('hark_version', 'N/A')} |")
    lines.append(f"| Git Commit | {b_meta.get('git', {}).get('commit', 'N/A')[:8]}... | {c_meta.get('git', {}).get('commit', 'N/A')[:8]}... |")
    lines.append(f"| Timestamp | {b_meta.get('timestamp', 'N/A')[:19]} | {c_meta.get('timestamp', 'N/A')[:19]} |")
    
    # Estimation results comparison
    lines.extend([
        "",
        "## Estimation Results",
        "",
    ])
    
    b_est = baseline.get("estimation_results", {}).get("Result_AllTarget", {})
    c_est = current.get("estimation_results", {}).get("Result_AllTarget", {})
    
    if b_est and c_est:
        lines.extend([
            "### Primary Parameters (Result_AllTarget.txt)",
            "",
            "| Parameter | Baseline | Current | Log-Point Diff | Status |",
            "|-----------|----------|---------|----------------|--------|",
        ])
        
        for param in ['splurge', 'beta', 'nabla']:
            b_val = b_est.get(param, 'N/A')
            c_val = c_est.get(param, 'N/A')
            
            if isinstance(b_val, (int, float)) and isinstance(c_val, (int, float)):
                log_diff, is_meaningful = log_point_diff(b_val, c_val, threshold)
                
                if is_meaningful:
                    status = "🛑 **MEANINGFUL**"
                    meaningful_diffs.append({
                        'metric': f"estimation.{param}",
                        'baseline': b_val,
                        'current': c_val,
                        'log_diff': log_diff
                    })
                elif log_diff > 0.005:  # > 0.5%
                    status = "⚠️ Minor"
                else:
                    status = "✅ Match"
                
                lines.append(f"| {param} | {b_val:.10f} | {c_val:.10f} | {log_diff:.6f} | {status} |")
            else:
                lines.append(f"| {param} | {b_val} | {c_val} | N/A | ⚠️ |")
    
    # Multipliers comparison
    b_mult = baseline.get("multipliers", {})
    c_mult = current.get("multipliers", {})
    
    if b_mult or c_mult:
        lines.extend([
            "",
            "## HANK Multipliers",
            "",
            "| Multiplier | Baseline | Current | Log-Point Diff | Status |",
            "|------------|----------|---------|----------------|--------|",
        ])
        
        mult_keys = ['UI_active', 'UI_fixed_nominal', 'transfer_active', 'taxcut', 'phillips_slope']
        for key in mult_keys:
            b_val = b_mult.get(key, 'N/A')
            c_val = c_mult.get(key, 'N/A')
            
            if isinstance(b_val, (int, float)) and isinstance(c_val, (int, float)):
                log_diff, is_meaningful = log_point_diff(b_val, c_val, threshold)
                
                if is_meaningful:
                    status = "🛑 **MEANINGFUL**"
                    meaningful_diffs.append({
                        'metric': f"multipliers.{key}",
                        'baseline': b_val,
                        'current': c_val,
                        'log_diff': log_diff
                    })
                elif log_diff > 0.005:
                    status = "⚠️ Minor"
                else:
                    status = "✅ Match"
                
                lines.append(f"| {key} | {b_val:.6f} | {c_val:.6f} | {log_diff:.6f} | {status} |")
            else:
                lines.append(f"| {key} | {b_val} | {c_val} | N/A | ⚠️ |")
    
    # Summary
    lines.extend([
        "",
        "---",
        "",
        "## Summary",
        "",
    ])
    
    if not meaningful_diffs:
        lines.extend([
            "**✅ VALIDATED** - All metrics within acceptable tolerance (< 0.02 log points).",
            "",
            "No meaningful differences detected. Results are numerically equivalent.",
        ])
    else:
        lines.extend([
            "# 🛑 MEANINGFUL DIFFERENCES DETECTED",
            "",
            f"**{len(meaningful_diffs)} metric(s) exceed the 0.02 log-point threshold.**",
            "",
            "## ⚠️ ACTION REQUIRED",
            "",
            "The following metrics show meaningful differences that require analysis:",
            "",
            "| Metric | Baseline | Current | Log-Point Diff |",
            "|--------|----------|---------|----------------|",
        ])
        
        for diff in meaningful_diffs:
            lines.append(f"| {diff['metric']} | {diff['baseline']:.6f} | {diff['current']:.6f} | {diff['log_diff']:.6f} |")
        
        lines.extend([
            "",
            "## Next Steps",
            "",
            "1. **PAUSE** - Do not proceed with merge",
            "2. **ANALYZE** - Investigate the cause of each difference",
            "3. **DOCUMENT** - Record findings and potential explanations",
            "4. **AWAIT USER INPUT** - Wait for decision on how to proceed",
            "",
            "### Potential Causes to Investigate",
            "",
            "- HARK API changes affecting numerical algorithms",
            "- Bug fixes in HARK that changed behavior",
            "- Changes in default solver parameters",
            "- Floating point precision differences",
            "- Random number generator state differences",
        ])
    
    report = '\n'.join(lines)
    
    # Output
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"Report saved to: {output_path}")
    
    print(report)
    
    # Return meaningful_diffs for programmatic use
    return {
        'report': report,
        'meaningful_diffs': meaningful_diffs,
        'validated': len(meaningful_diffs) == 0
    }


def main():
    parser = argparse.ArgumentParser(
        description="Compare HAFiscal results (focuses on NUMERICAL values, not file hashes)"
    )
    parser.add_argument("--baseline", "-b", required=True, help="Baseline snapshot directory")
    parser.add_argument("--attempt", "-a", help="Attempt snapshot directory (alternative to --current)")
    parser.add_argument("--current", "-c", action="store_true", help="Compare with current results")
    parser.add_argument("--output", "-o", help="Output file for report")
    parser.add_argument("--threshold", "-t", type=float, default=MEANINGFUL_DIFF_THRESHOLD,
                        help=f"Log-point threshold for meaningful diff (default: {MEANINGFUL_DIFF_THRESHOLD})")
    
    args = parser.parse_args()
    
    if not args.current and not args.attempt:
        parser.error("Either --current or --attempt must be specified")
    
    # Allow threshold override (use module-level variable)
    threshold = args.threshold
    
    baseline = load_snapshot(args.baseline)
    
    if args.current:
        current = capture_current()
    else:
        current = load_snapshot(args.attempt)
    
    result = generate_report(baseline, current, args.output, threshold)
    
    # Exit with appropriate code
    if result['validated']:
        print("\n✅ Validation PASSED - All metrics within tolerance")
        sys.exit(0)
    else:
        print(f"\n🛑 Validation PAUSED - {len(result['meaningful_diffs'])} meaningful difference(s) found")
        print("   Review the report above and decide how to proceed.")
        sys.exit(1)  # Non-zero exit to signal that review is needed


if __name__ == "__main__":
    main()
