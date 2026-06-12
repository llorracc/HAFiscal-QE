#!/usr/bin/env python
"""run_step5a_only.py — Run Step-5a multipliers only, using existing DiscFacEstim.

Wrapper for the systematic speedup test plan
(plans/20260504-1300h_qe_fidelity_speedup_systematic_test.md).

Skips Step-1 + Step-2; reads existing qe_fidelity_full estimates from
Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt.
Skips Step-5b welfare-6 (welfare out of scope per user direction).

Sets the qe_fidelity-equivalent env vars and invokes AggFiscalMAIN_reduced.py.

Usage:
    python run_step5a_only.py                # Reduced_Run scope (default)
    python run_step5a_only.py --smoke-test   # Smoke_Test scope (N=100)
    python run_step5a_only.py --baseline     # Baseline scope (full N=10k, 21 types)

Speedup-test env vars are inherited from the calling environment (pass-through),
so test scripts can set HAFISCAL_MC_SHUFFLE=1 etc. before invoking this wrapper.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

# --- qe_fidelity-equivalent env vars (set if not already in environment) ---
QE_FIDELITY_DEFAULTS = {
    "HAFISCAL_INTERPRETATION": "ESC",
    "HAFISCAL_PERM_DURING_UNEMP": "off",
    "HAFISCAL_SIM_METHOD": "MC",
    "HAFISCAL_TM_A_INDEXED": "1",
    "HAFISCAL_TM_A_CACHE": "1",
    "HAFISCAL_DRIFT_HARD_FAIL": "0",
    "HAFISCAL_DRIFT_THRESHOLD": "0.03",
    "PYTHONUNBUFFERED": "1",
}

env = os.environ.copy()
for k, v in QE_FIDELITY_DEFAULTS.items():
    env.setdefault(k, v)

# --- Forward CLI args (e.g., --smoke-test, --baseline) to the inner script ---
inner_args = [a for a in sys.argv[1:] if a not in ("--no-welfare",)]

# --- Print effective configuration for logging ---
print("=" * 60)
print("[run_step5a_only] starting Step-5a only (no Step-1/2, no welfare-6)")
print("=" * 60)
print(f"  cwd:                 {HERE}")
print(f"  inner args:          {inner_args}")
print(f"  HAFISCAL_INTERPRETATION:    {env['HAFISCAL_INTERPRETATION']}")
print(f"  HAFISCAL_PERM_DURING_UNEMP: {env['HAFISCAL_PERM_DURING_UNEMP']}")
print(f"  HAFISCAL_SIM_METHOD:        {env['HAFISCAL_SIM_METHOD']}")
print(f"  HAFISCAL_TM_A_INDEXED:      {env['HAFISCAL_TM_A_INDEXED']}")
print(f"  HAFISCAL_TM_A_CACHE:        {env['HAFISCAL_TM_A_CACHE']}")
# Speedup test knobs (only print if set, to flag what the test enabled)
for k in (
    "HAFISCAL_MC_SHUFFLE",
    "HAFISCAL_INCOME_SHUFFLE",
    "HAFISCAL_NORMALIZE_PLVL",
    "HAFISCAL_FAST_GRIDS",
    "HAFISCAL_NO_FORK",
    "HAFISCAL_DUR_WORKERS",
    "HAFISCAL_NO_SOLVE_CACHE",
    "HAFISCAL_SERIAL",
    "HAFISCAL_RUN_ONLY_SHOCK",
):
    if env.get(k):
        print(f"  {k:30s} {env[k]}")
print("=" * 60)

# --- Verify the DiscFacEstim file exists and has the expected estimates ---
disc_path = HERE.parent / "Results" / "DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt"
if not disc_path.exists():
    print(f"ERROR: DiscFacEstim file not found: {disc_path}")
    sys.exit(2)
print(f"[run_step5a_only] using DiscFacEstim: {disc_path}")
print(f"[run_step5a_only] file mtime: {time.ctime(disc_path.stat().st_mtime)}")

# --- Invoke AggFiscalMAIN_reduced.py ---
cmd = [sys.executable, "-u", str(HERE / "AggFiscalMAIN_reduced.py")] + inner_args
print(f"[run_step5a_only] running: {' '.join(cmd)}")
print("=" * 60)
sys.stdout.flush()

t0 = time.time()
rc = subprocess.call(cmd, cwd=str(HERE), env=env)
wall = time.time() - t0

print("=" * 60)
print(f"[run_step5a_only] completed: rc={rc}, wall={wall/60:.2f} min")
print("=" * 60)
sys.exit(rc)
