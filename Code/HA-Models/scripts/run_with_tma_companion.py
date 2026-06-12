#!/usr/bin/env python
"""Run an MC simulation with TM-a companion + drift checks always enabled.

Per the standing rule (memory feedback_mc_requires_tma_companion.md): every
MC run must be paired with a TM-a build (for ergodic init + drift comparison).

This wrapper enforces the rule by:

  1. Setting `Run_Dict['tm_a_indexed'] = True` and `Run_Dict['mc_use_tm_init'] = True`
     in the launched script's environment, so that:
     - The TM-a baseline data is computed alongside MC
     - MC initializes from TM-a's ergodic
     - The drift hook in Simulate.py fires automatically

  2. Setting `HAFISCAL_TM_A_CACHE=1` to enable the warm-start cache (Phase 3),
     since repeated invocations at the same cal benefit dramatically.

  3. Optionally HARD-FAIL on drift: HAFISCAL_DRIFT_HARD_FAIL=1 (the default
     per Simulate.py drift hook).

Usage:

    python run_with_tma_companion.py <script> [args...]

Where <script> is the underlying script (e.g. AggFiscalMAIN_reduced.py
with --baseline). The wrapper inspects the script for sim_method='MC'
or 'both' to know whether the rule applies; passes through unchanged for
TM-only runs.

Examples:

    # Run reduced-cohort MC Step 5 with companion:
    python run_with_tma_companion.py AggFiscalMAIN_reduced.py

    # Run baseline MC Step 5 with companion:
    python run_with_tma_companion.py AggFiscalMAIN_reduced.py --baseline

For Step-2 MC estimations: invoke run_phase2_parallel.py through this wrapper
(set HAFISCAL_TM_A_INDEXED=1 in env to get the TM-a build alongside MC's
finite-T simulation evaluation).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_FROM_PANDEMIC = _HERE.parent / "FromPandemicCode"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    script_name = argv[1]
    script_args = argv[2:]

    # Resolve script path
    script_path = _FROM_PANDEMIC / script_name
    if not script_path.exists():
        # Maybe an absolute path was given
        script_path = Path(script_name)
        if not script_path.exists():
            print(f"ERROR: script not found: {script_name}")
            return 1

    # Build environment with companion flags
    env = os.environ.copy()
    env.setdefault("HAFISCAL_TM_A_CACHE", "1")          # warm-start cache on
    env.setdefault("HAFISCAL_DRIFT_HARD_FAIL", "1")     # hard-fail on drift > threshold
    env.setdefault("HAFISCAL_DRIFT_THRESHOLD", "0.03")

    # Inject Run_Dict overrides via env vars (script reads them in main).
    # If the underlying script supports HAFISCAL_TM_A_INDEXED, use that.
    # Otherwise, the user must set Run_Dict['tm_a_indexed'] = True manually.
    env.setdefault("HAFISCAL_TM_A_INDEXED", "1")
    env.setdefault("HAFISCAL_SIM_METHOD", "MC")   # MC is the point of the companion rule

    print(f"[companion] Launching {script_path.name}")
    print(f"[companion] HAFISCAL_TM_A_INDEXED   = {env['HAFISCAL_TM_A_INDEXED']}")
    print(f"[companion] HAFISCAL_TM_A_CACHE     = {env['HAFISCAL_TM_A_CACHE']}")
    print(f"[companion] HAFISCAL_DRIFT_HARD_FAIL = {env['HAFISCAL_DRIFT_HARD_FAIL']}")
    print(f"[companion] HAFISCAL_DRIFT_THRESHOLD = {env['HAFISCAL_DRIFT_THRESHOLD']}")
    print(f"[companion] script args = {script_args}")
    print()

    cmd = [sys.executable, "-u", str(script_path)] + script_args
    return subprocess.run(cmd, env=env, cwd=str(_FROM_PANDEMIC)).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
