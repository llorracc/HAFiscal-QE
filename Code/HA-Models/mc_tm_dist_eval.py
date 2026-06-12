#!/usr/bin/env python
"""Evaluate the MC or TM estimation objective at a given (beta, spread, GICx)
for ONE education cohort, printing the model's ergodic median(LW/PI) + Lorenz
curve of liquid wealth.

Purpose: the estimation-phase MC-vs-TM cross-check (user request 2026-06-05).
Lets us compare the MC-simulated ergodic liquid-wealth distribution against the
TM analytical ergodic at *matched* betas:
  - same-beta:   MC@b vs TM@b  (isolates the simulation method)
  - calibrated:  MC@b_MC vs TM@b_TM  (each at its own estimate)

Reuses the *validated* objective functions (betas_obj_func_educ for MC,
betas_obj_func_educ_tm_a for TM) in EVALUATE-only mode — it does NOT estimate
and does NOT write any calibration file. New driver lives in Code/HA-Models/
(not FromPandemicCode/), per repo convention.

Usage:
  python mc_tm_dist_eval.py --method TM --educ 1 --beta 0.9034 --spread 0.1196 --gicx 5.2003
"""
import os
import sys
import argparse

ap = argparse.ArgumentParser()
ap.add_argument('--method', required=True, choices=['MC', 'TM'])
ap.add_argument('--educ', type=int, required=True, choices=[0, 1, 2])
ap.add_argument('--beta', type=float, required=True)
ap.add_argument('--spread', type=float, required=True)
ap.add_argument('--gicx', type=float, required=True)
args = ap.parse_args()

# The estimators read sys.argv POSITIONALLY (EstimParameters.py:84-86: argv[5]
# = Splurge override when len(argv)>=6). Strip our argparse args so len<6 and
# they fall back to the canonical defaults (CRRA 2.0, R 1.01, Splurge from the
# estimated splurge file = the ESC calibration).
sys.argv = [sys.argv[0]]

# BUG-051 matched-pair guard: this is a guarded entry point, so the
# interpretation MUST be set explicitly (refuse to silently assume one). Check
# BEFORE the setdefault below — otherwise the setdefault would mask an unset
# env. _interpretation.py lives in this (HA-Models) dir, which is on sys.path
# as the script dir.
from _interpretation import get_interpretation
get_interpretation(require=True)

# Matched-pair regime + interpretation — MUST be set before importing the
# estimators (they read these at import time).
os.environ.setdefault('HAFISCAL_PERMGROFAC_FIX', '1')      # fixed solver
os.environ.setdefault('HAFISCAL_INTERPRETATION', 'ESC')
os.environ.setdefault('HAFISCAL_UI_STATE_ENCODING', 'bug_fix')

HERE = os.path.dirname(os.path.abspath(__file__))
FPC = os.path.join(HERE, 'FromPandemicCode')
sys.path.insert(0, FPC)
os.chdir(FPC)  # estimators expect FromPandemicCode as cwd

print(f"DISTEVAL_HEADER method={args.method} educ={args.educ} "
      f"beta={args.beta} spread={args.spread} gicx={args.gicx}", flush=True)

import io
import re
from contextlib import redirect_stdout

_buf = io.StringIO()
with redirect_stdout(_buf):
    if args.method == 'MC':
        os.environ['HAFISCAL_SKIP_ESTIMATION'] = '1'   # import setup, do not estimate
        import EstimAggFiscalMAIN as M
        M.betas_obj_func_educ(args.beta, args.spread, args.gicx,
                              educ_type=args.educ, print_mode=True)
    else:
        os.environ['HAFISCAL_EDTYPES'] = ''            # empty -> TM loop is a no-op
        import estim_phase2_tm_a as T
        T.betas_obj_func_educ_tm_a(args.beta, args.spread, args.gicx,
                                   educ_type=args.educ, print_mode=True)
_out = _buf.getvalue()

# Parse median(LW/PI) + Lorenz curve from the objective's print_mode output.
median = None
lorenz = None
if args.method == 'MC':
    m = re.search(r"Median LW/PI-ratio for group e = [\d.]+ is:\s*([\d.]+)", _out)
    if m:
        median = float(m.group(1))
    m = re.search(r"Lorenz shares -[^\n]*\n\s*\[([^\]]+)\]", _out)
    if m:
        lorenz = [float(x) for x in m.group(1).split()]
else:
    m = re.search(r"medianLWPI:\s*model=([\d.]+)", _out)
    if m:
        median = float(m.group(1))
    m = re.search(r"Lorenz:\s*model=\[([^\]]+)\]", _out)
    if m:
        lorenz = [float(x) for x in m.group(1).split(',')]

lor_str = ','.join(f'{x:.4f}' for x in lorenz) if lorenz else 'NA'
print(f"DISTEVAL_RESULT method={args.method} educ={args.educ} "
      f"beta={args.beta} spread={args.spread} median={median} lorenz={lor_str}", flush=True)
print("DISTEVAL_DONE", flush=True)
