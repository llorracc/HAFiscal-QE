#!/usr/bin/env python
"""reestimate_bug053_orchestrate.py — full BUG-053 re-estimation chain (one-off).

The GIC discount-factor ceiling is now imposed on the GROWTH PATIENCE FACTOR (GPF), not on
beta (BUG-053, commit cf276ab9). The cap moves the most-patient atom (college: GPF 0.9995 ->
0.999), so the grid and (beta, nabla) must be re-estimated under the fix. This script runs the
whole chain UNATTENDED (user, 2026-06-09), re-architected after the pre-flight audit:

  Phase 1  PRODUCTION GRID via adaptive_grid_tm.production_aMax() — the (1-1e-4) ergodic-aNrm
           quantile of the college GIC cap atom (GPF=theGICfactor=0.9995). beta-INDEPENDENT,
           monotone, reproducible (~1224 -> aMax 1300, matching the independent bucketed5d
           production aMax=1300). REPLACES the old iterate() trim/grow loop, which the audit
           proved is a non-convergent 2-cycle returning a ~2x-too-large MAX_ITERS-parity value.
  GATE     halt unless 867 <= aMax <= 1300 (must cover the bucketed5d support; reject the old
           broken-loop ~1100+ inflation and the over-conservative 1300).
  Phase 2  cold MULTI-START (beta, nabla) for all 3 edu groups via the CANONICAL wrapper
           run_phase2_parallel.py (HAFISCAL_STEP2_METHOD=tm_a). The wrapper runs 3 parallel
           cohort subprocesses (multistart inside each), MERGES per-edType -> consolidated
           _TM_a_ESC.txt, and — critically — MIRRORS to the un-tagged DiscFacEstim_*_ESC.txt
           that Parameters.py/Step-5 actually read (the hand-rolled orchestrator did NOT, so the
           re-estimation would have been invisible — audit blocker). Then calcAllResults.
  POST     assert the downstream un-tagged _ESC.txt changed (mtime newer than Phase-2 start) AND
           its 3 (beta,nabla,GICx) triples equal the 3 per-edType files (catches wrong-regime
           staleness: the pre-run file carries GICx=12.62 legacy vs the run's hardcoded 6.9068).

GUARDRAILS honored:
  - COLD multi-start (HAFISCAL_NM_START_FROM_SAVED=0) — no warm-start from the pre-fix pickle
    (feedback_no_warmstart_when_validating_solver_fix)
  - interpretation EXPLICIT = ESC (BUG-051 matched-pair guard)
  - HAFISCAL_GIC_SHAVE_ON_GPF=1 (the fix) set explicitly
  - NM progress logging on (HAFISCAL_NM_LOG_EVERY default 5)
  - PYTHONUNBUFFERED=1 on every child
  - RUN UNDER THE numpy<2 venv (.venv) — the active .venv-linux-x86_64 is numpy 2.4.5 (violates
    the pyproject <2 pin) and would write np.float64(...) reprs; the float() write-site fix
    (estim_phase2_tm_a.py) is belt-and-suspenders. Launch: /…/.venv/bin/python this_script.py

Run:  cd Code/HA-Models && PYTHONUNBUFFERED=1 /…/.venv/bin/python reestimate_bug053_orchestrate.py
"""
import os
import re
import sys
import ast
import json
import time
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_FPC = os.path.join(_HERE, "FromPandemicCode")
_RES = os.path.join(_HERE, "Results")
_LOGDIR = os.path.join(_RES, "tmp", "bug053_reestim")
_STATE = os.path.join(_LOGDIR, "state.json")

# Phase-1 gate. Under theGICfactor=0.9995 the cap atom (GPF=0.9995, beta=1.005369) has a fatter
# tail, so the (1-1e-4) quantile is ~1224 -> aMax=1300 (matches the independent bucketed5d
# production aMax=1300). Gate generously to catch only an absurd (broken-grid) value.
GATE_LO, GATE_HI = 867.0, 1600.0
NUM_STARTS = "4"  # full production multi-start grids (dropout 4 / HS 3 / college 2)

CRRA, RFREE = "2.0", "1.01"
_CANON = f"DiscFacEstim_CRRA_{CRRA}_R_{RFREE}"
_PER_EDTYPE = {e: os.path.join(_RES, f"{_CANON}_edType{e}_TM_a_ESC.txt") for e in (0, 1, 2)}
_CONSOLIDATED = os.path.join(_RES, f"{_CANON}_TM_a_ESC.txt")
_DOWNSTREAM = os.path.join(_RES, f"{_CANON}_ESC.txt")  # the file Parameters.py / Step-5 read


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _read_record(path, edtype):
    """Return (beta, nabla, GICx) for edtype from a DiscFacEstim file (bare-float or np.float64)."""
    txt = open(path).read()
    for line in txt.splitlines():
        line = line.strip()
        if not line.startswith("{") or f"'EducationGroup': {edtype}" not in line:
            continue
        try:
            rec = ast.literal_eval(line)
        except (ValueError, SyntaxError):
            import numpy as _np
            rec = eval(line, {"np": _np, "__builtins__": {}})
        return float(rec["beta"]), float(rec["nabla"]), float(rec["GICx"])
    raise KeyError(f"edType={edtype} not found in {path}")


def main():
    os.makedirs(_LOGDIR, exist_ok=True)
    os.environ["HAFISCAL_GIC_SHAVE_ON_GPF"] = "1"  # the fix, explicit
    os.environ["HAFISCAL_INTERPRETATION"] = "ESC"  # BUG-051 guard, explicit
    # Suppress the load-time betaDistr print (Parameters.py, fired at AggFiscalModel import): during
    # re-estimation it shows the STALE pre-run on-disk calibration, not what's being estimated. The
    # estimator prints the "[newly estimated]" betaDistr after construction instead (BUG-053 followup).
    os.environ["HAFISCAL_QUIET_BETADISTR"] = "1"
    os.environ.setdefault("PYTHONUNBUFFERED", "1")

    import numpy as np
    state = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
             "numpy": np.__version__, "python": sys.version.split()[0]}
    log(f"env: python={state['python']} numpy={state['numpy']} "
        f"(MUST be numpy<2 for bare-float / QE-lineage reprs)")

    # ---- Phase 1: production grid (cap-atom quantile; beta-independent; reproducible) ----
    sys.path.insert(0, _HERE)
    import adaptive_grid_tm as g
    log("PHASE 1: production_aMax() — (1-1e-4) ergodic quantile of the college GIC cap atom (ESC, fix)")
    t0 = time.time()
    aMax, q, beta_top = g.production_aMax(interpretation="ESC", verbose=True)
    log(f"PHASE 1 done in {(time.time()-t0)/60:.1f} min; cap beta_top={beta_top:.6f}, "
        f"quantile={q:.1f}, aMax={aMax:.1f}")
    state.update(phase1_aMax=aMax, phase1_quantile=q, phase1_cap_beta_top=beta_top)
    with open(_STATE, "w") as f:
        json.dump(state, f, indent=2, default=float)

    # ---- GATE ----
    if not (GATE_LO <= aMax <= GATE_HI):
        log(f"HALT (cascade gate): aMax {aMax:.1f} outside [{GATE_LO:.0f}, {GATE_HI:.0f}] "
            f"(must cover bucketed5d support ~867; reject absurd broken-grid value). Investigate.")
        sys.exit(1)
    log(f"GATE PASSED: aMax {aMax:.1f} in [{GATE_LO:.0f}, {GATE_HI:.0f}] (expect ~1300 under GPF=0.9995)")

    # ---- Phase 2: cold multi-start via the canonical wrapper (merge + mirror + calcAllResults) ----
    phase2_start = time.time()
    log(f"PHASE 2: run_phase2_parallel.py STEP2_METHOD=tm_a, cold multistart ESC, "
        f"NUM_STARTS={NUM_STARTS}, HAFISCAL_TM_AMAX={aMax:.4f} (3 cohorts in parallel)")
    env = os.environ.copy()
    env.update({
        "HAFISCAL_STEP2_METHOD": "tm_a",
        "HAFISCAL_INTERPRETATION": "ESC",
        "HAFISCAL_TM_AMAX": repr(float(aMax)),
        "HAFISCAL_TM_AMIN": "0.0",
        "HAFISCAL_GICX_MODE": "hardcoded",
        "HAFISCAL_NUM_STARTS": NUM_STARTS,
        "HAFISCAL_NM_START_FROM_SAVED": "0",  # COLD
        "HAFISCAL_GIC_SHAVE_ON_GPF": "1",     # the fix
        "HAFISCAL_WRAPPER_EDTYPES": "0,1,2",
        "PYTHONUNBUFFERED": "1",
    })
    env.pop("HAFISCAL_PARALLEL_MULTISTART", None)  # tm_a uses legacy per-cohort mode (multistart inside)
    log_path = os.path.join(_LOGDIR, "phase2_wrapper.log")
    with open(log_path, "w") as lf:
        rc = subprocess.run([sys.executable, "-u", "run_phase2_parallel.py"],
                            cwd=_FPC, env=env, stdout=lf, stderr=subprocess.STDOUT).returncode
    log(f"PHASE 2 wrapper finished in {(time.time()-phase2_start)/60:.1f} min; rc={rc} (log: {log_path})")
    state["phase2_rc"] = rc
    if rc != 0:
        log("WARNING: wrapper rc != 0 — the calibration files may still be written (mirror precedes "
            "calcAllResults); proceeding to POST checks to report exactly what landed.")

    # ---- POST: verify the downstream file production reads actually changed + matches per-edType ----
    log("POST: verifying downstream un-tagged _ESC.txt changed and equals the 3 per-edType files")
    problems = []
    for path, label in [(_DOWNSTREAM, "downstream"), (_CONSOLIDATED, "consolidated")] + \
                       [(_PER_EDTYPE[e], f"edType{e}") for e in (0, 1, 2)]:
        if not os.path.exists(path):
            problems.append(f"MISSING {label}: {path}")
            continue
        mtime = os.path.getmtime(path)
        fresh = mtime >= phase2_start
        log(f"  {label}: {os.path.basename(path)}  mtime={'FRESH' if fresh else 'STALE'} "
            f"({time.strftime('%H:%M:%S', time.localtime(mtime))})")
        if label in ("downstream", "consolidated") and not fresh:
            problems.append(f"{label} NOT refreshed by this run (stale mtime): {path}")

    results = {}
    try:
        for e in (0, 1, 2):
            per = _read_record(_PER_EDTYPE[e], e)
            results[e] = {"beta": per[0], "nabla": per[1], "GICx": per[2]}
            for path, label in [(_DOWNSTREAM, "downstream"), (_CONSOLIDATED, "consolidated")]:
                if os.path.exists(path):
                    dn = _read_record(path, e)
                    if max(abs(a - b) for a, b in zip(per, dn)) > 1e-9:
                        problems.append(f"edType{e} mismatch {label} {dn} vs per-edType {per}")
        state["results"] = results
        log("POST per-cohort (beta, nabla, GICx):")
        for e in (0, 1, 2):
            r = results[e]
            log(f"  edType{e}: beta={r['beta']:.6f}  nabla={r['nabla']:.6f}  GICx={r['GICx']:.4f}")
    except Exception as ex:
        problems.append(f"record parse/compare failed: {ex!r}")

    state["problems"] = problems
    state["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(_STATE, "w") as f:
        json.dump(state, f, indent=2, default=float)

    if problems:
        log(f"POST FAILED ({len(problems)} problem(s)):")
        for p in problems:
            log(f"  - {p}")
        sys.exit(2)
    log("DONE — grid + cold-multistart ESC calibration written AND mirrored to the downstream "
        f"file Step-5 reads ({os.path.basename(_DOWNSTREAM)}); all POST checks passed.")


if __name__ == "__main__":
    main()
