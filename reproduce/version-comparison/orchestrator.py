#!/usr/bin/env python
"""
Orchestrator for 0.14.1 vs 0.17.0 component-level numerical equivalence tests.

Runs each test step inside two Docker containers (hafiscal-014 and hafiscal-017),
collects JSON output, and compares for bitwise equivalence.

Usage:
    python orchestrator.py [--step N] [--atol 1e-14] [--workspace-014 PATH] [--workspace-017 PATH]
"""

import argparse
import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from compare_utils import compare_json, print_report

DEFAULT_014_WORKSPACE = "/tmp/HAFiscal-014"
DEFAULT_017_WORKSPACE = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

STEPS = {
    1: "test_step1_splurge.py",
    2: "test_step2_discfac.py",
    3: "test_step3_robustness.py",
    4: "test_step4_hank_sam.py",
    5: "test_step5_policy.py",
    6: "test_step2_inputs.py",
}

STEP_NAMES = {
    1: "Step 1: Splurge Estimation",
    2: "Step 2: Discount Factor Estimation",
    3: "Step 3: Robustness (Splurge=0)",
    4: "Step 4: HANK-SAM Jacobians",
    5: "Step 5: Policy Simulations",
    6: "Step 2b: Input Divergence Diagnostic",
}

TIMEOUT_SECONDS = {
    1: 1800,   # 30 min
    2: 7200,   # 2 hours
    3: 7200,   # 2 hours
    4: 3600,   # 1 hour
    5: 3600,   # 1 hour
    6: 7200,   # 2 hours
}


def run_in_docker(image, workspace_path, test_script, timeout):
    """Run a test script inside a Docker container, return parsed JSON or error."""
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{workspace_path}:/workspace",
        "-v", f"{SCRIPT_DIR}:/tests:ro",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "MPLBACKEND=Agg",
        image,
        "python", "-u", f"/tests/{test_script}",
    ]

    print(f"  Running: {image} / {test_script}", file=sys.stderr)
    print(f"  Command: {' '.join(cmd)}", file=sys.stderr)

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, f"TIMEOUT after {timeout}s"

    elapsed = time.time() - t0
    print(f"  Completed in {elapsed:.1f}s (exit code {result.returncode})", file=sys.stderr)

    if result.returncode != 0:
        return None, f"EXIT {result.returncode}\nSTDERR:\n{result.stderr[-2000:]}"

    stdout = result.stdout.strip()
    json_start = stdout.rfind("\n{")
    if json_start >= 0:
        stdout = stdout[json_start + 1:]
    elif not stdout.startswith("{"):
        lines = stdout.split("\n")
        for line in reversed(lines):
            line = line.strip()
            if line.startswith("{"):
                stdout = line
                break

    try:
        return json.loads(stdout), None
    except json.JSONDecodeError as e:
        tail = result.stdout[-500:] if result.stdout else "(empty)"
        return None, f"JSON parse error: {e}\nTail of stdout:\n{tail}"


def run_step(step_num, workspace_014, workspace_017, atol):
    """Run a single test step in both containers and compare."""
    script = STEPS[step_num]
    name = STEP_NAMES[step_num]
    timeout = TIMEOUT_SECONDS[step_num]

    print(f"\n{'#'*80}", file=sys.stderr)
    print(f"  {name}", file=sys.stderr)
    print(f"{'#'*80}", file=sys.stderr)

    image_014 = os.environ.get("HAFISCAL_014_IMAGE", "hafiscal-014-arm")
    result_014, err_014 = run_in_docker(image_014, workspace_014, script, timeout)
    if err_014:
        print(f"  [0.14.1] ERROR: {err_014}", file=sys.stderr)
        return False, [dict(metric="ERROR_014", val_014=err_014, val_017=None,
                            abs_diff=None, rel_diff=None, verdict="ERROR")]

    result_017, err_017 = run_in_docker("hafiscal-017", workspace_017, script, timeout)
    if err_017:
        print(f"  [0.17.0] ERROR: {err_017}", file=sys.stderr)
        return False, [dict(metric="ERROR_017", val_014=None, val_017=err_017,
                            abs_diff=None, rel_diff=None, verdict="ERROR")]

    passed, rows = compare_json(result_014, result_017, atol=atol)
    print_report(name, rows, file=sys.stderr)
    return passed, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=int, default=0,
                        help="Run only this step (1-5). 0 = all.")
    parser.add_argument("--atol", type=float, default=1e-14,
                        help="Absolute tolerance for comparison.")
    parser.add_argument("--workspace-014", default=DEFAULT_014_WORKSPACE)
    parser.add_argument("--workspace-017", default=DEFAULT_017_WORKSPACE)
    args = parser.parse_args()

    steps_to_run = [args.step] if args.step else sorted(STEPS.keys())

    overall = {}
    for s in steps_to_run:
        passed, rows = run_step(s, args.workspace_014, args.workspace_017, args.atol)
        overall[s] = {"name": STEP_NAMES[s], "passed": passed, "rows": rows}

    print("\n" + "=" * 80)
    print("  OVERALL SUMMARY")
    print("=" * 80)
    all_ok = True
    for s in steps_to_run:
        status = "PASS" if overall[s]["passed"] else "FAIL"
        if not overall[s]["passed"]:
            all_ok = False
        print(f"  Step {s}: {overall[s]['name']:50s} [{status}]")

    print()
    if all_ok:
        print("  ALL STEPS PASSED -- 0.14.1 and 0.17.0 produce equivalent results")
    else:
        print("  SOME STEPS FAILED -- see details above")

    full_report = {
        "summary": {s: {"name": STEP_NAMES[s], "passed": overall[s]["passed"]}
                    for s in steps_to_run},
        "all_passed": all_ok,
    }
    print(json.dumps(full_report, indent=2))

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
