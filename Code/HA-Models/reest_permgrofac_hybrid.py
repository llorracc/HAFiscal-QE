#!/usr/bin/env python
"""Hybrid paper-grade re-estimation for BUG-047 (PermGroFac marginal-value fix).

One-off driver to re-estimate the production (β, ∇, GICx) discount-factor
calibration under the FIXED solver (HAFISCAL_PERMGROFAC_FIX=1), so the
canonical Results/DiscFacEstim_*_ESC.txt files are internally consistent with
the now-default-on fix.

Config (decided with the user 2026-06-04):
  - COLD start (HAFISCAL_NM_START_FROM_SAVED=0) — never warm-start off the
    buggy-solver pickle when validating a solver fix.
  - 3-D fitted GICx (HAFISCAL_GICX_MODE=legacy), matching the published
    methodology (per-group GICx, not the pinned logit(0.999)).
  - N=50000 (EstimParameters default), bug_fix encoding, ESC interpretation.
  - HYBRID multistart: Dropout 4 cold starts (BUG-036 multimodality), HS &
    College 1 cold start each (narrow ∇, well-behaved).
  - HAFISCAL_SERIAL=1 per child (the run_phase2_parallel.py approach): avoids
    the joblib worker-respawn OOM over hundreds of evals. Serial per-eval
    ~74 s at N=50000; 6 single-threaded children on 6 of 32 cores run with
    zero contention, so wall ≈ slowest single child (~1.5-1.7 hr).

Launches all 6 (edType, start) children concurrently, waits, picks Dropout's
best basin (min distance), validates every record, backs up the canonical
file, then merges the 3 per-edType records into the canonical + per-edType
files. Reuses run_phase2_parallel.py's helpers for filename conventions.

NOT wired into do_all.py — this is an explicit, user-authorized one-off.
Run:  python reest_permgrofac_hybrid.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

# The child estimator writes records with numpy scalars in the repr
# (e.g. `np.float64(0.75)` under numpy 2.x), so a pure-literal parser
# (ast.literal_eval) rejects them. The codebase reads these files with bare
# `eval()` (EstimAggFiscalMAIN.py:1688/1767); mirror that, but with a
# restricted namespace (np available, no builtins) since these are our own
# trusted output files.
_REC_NS = {"np": np, "__builtins__": {}}


def _load_record(text: str) -> dict:
    return eval(text.strip(), dict(_REC_NS))

HA_MODELS = Path(__file__).resolve().parent
FPC = HA_MODELS / "FromPandemicCode"
RES_DIR = (HA_MODELS / "Results").resolve()
LOG_DIR = Path("/tmp/reest_permgrofac_hybrid")
LOG_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(FPC))
import run_phase2_parallel as wrap  # __main__-guarded: import is side-effect-free

# Hybrid multistart counts per education group.
STARTS = {0: 4, 1: 1, 2: 1}
EDU_NAMES = {0: "Dropout", 1: "Highschool", 2: "College"}

# Interpretation to re-estimate (ESC default; HAFISCAL_REEST_INTERP=CDC for the CDC calibration).
# CDC writes the un-suffixed DiscFacEstim_*.txt; ESC writes _ESC files. The wrap.* filename
# helpers resolve the suffix from HAFISCAL_INTERPRETATION, set below in main().
_REEST_INTERP = os.environ.get("HAFISCAL_REEST_INTERP", "ESC").upper()

# Sanity bounds for the estimated records (abort the canonical write if violated).
BOUNDS = dict(beta=(0.40, 1.00), nabla=(0.0, 0.60))


def _child_env(et: int, k: int | None) -> dict:
    env = dict(os.environ)
    env.update(
        HAFISCAL_SERIAL="1",
        HAFISCAL_INTERPRETATION=_REEST_INTERP,
        HAFISCAL_UI_STATE_ENCODING="bug_fix",
        HAFISCAL_PERMGROFAC_FIX="1",          # the fix (now default; explicit for the record)
        HAFISCAL_GICX_MODE="legacy",          # 3-D fitted GICx
        HAFISCAL_NM_START_FROM_SAVED="0",     # COLD — no warm-start off the buggy pickle
        HAFISCAL_NUM_STARTS=str(STARTS[et]),  # 4 for Dropout (grid), 1 otherwise
        HAFISCAL_EDTYPES=str(et),
        PYTHONUNBUFFERED="1",
    )
    if k is not None:
        env["HAFISCAL_PIN_START_INDEX"] = str(k)  # Dropout: pin one grid start per child
    return env


def main() -> int:
    # ensure the orchestrator's own filename-helper calls resolve to the right interpretation
    os.environ["HAFISCAL_INTERPRETATION"] = _REEST_INTERP
    print(f"[reest] interpretation = {_REEST_INTERP}")
    canonical_filename = wrap._result_filename_base(method="mc")
    canonical_path = RES_DIR / canonical_filename
    python = sys.executable
    script = FPC / "EstimAggFiscalMAIN.py"

    print(f"[reest] canonical target: {canonical_path}")
    print(f"[reest] hybrid starts: {STARTS}  (cold, 3-D fitted GICx, SERIAL=1, N=50000, bug_fix, ESC, fix ON)")

    # --- launch all children concurrently ---------------------------------
    procs: dict[tuple, subprocess.Popen] = {}
    logs: dict[tuple, Path] = {}
    t0 = time.time()
    for et, n in STARTS.items():
        for k in range(n):
            key = (et, k)
            pin = k if n > 1 else None
            log = LOG_DIR / f"ed{et}_start{k}.log"
            logs[key] = log
            fh = open(log, "w")
            print(f"[reest] launch {EDU_NAMES[et]} (edType={et}) start={k} -> {log}")
            procs[key] = subprocess.Popen(
                [python, "-u", str(script)],
                cwd=str(FPC), env=_child_env(et, pin),
                stdout=fh, stderr=subprocess.STDOUT,
            )

    # --- wait, reporting per-child completion ------------------------------
    remaining = set(procs)
    durations: dict[tuple, float] = {}
    while remaining:
        time.sleep(15)
        for key in list(remaining):
            rc = procs[key].poll()
            if rc is not None:
                durations[key] = time.time() - t0
                tag = "OK" if rc == 0 else f"FAIL rc={rc}"
                print(f"[reest] {EDU_NAMES[key[0]]} start={key[1]} {tag} "
                      f"@ {durations[key]/60:.1f} min")
                remaining.discard(key)

    failed = [k for k, p in procs.items() if p.returncode != 0]
    if failed:
        for key in failed:
            print(f"[reest] FATAL: {EDU_NAMES[key[0]]} start={key[1]} failed; see {logs[key]}")
        return 1

    # --- collect per-edType records ---------------------------------------
    # Dropout: pick the best basin (min distance) across its 4 start files.
    # HS/College: single-edtype child already wrote the canonical per-edType file.
    records: dict[int, dict] = {}
    for et, n in STARTS.items():
        per_path = RES_DIR / wrap._per_cohort_path(canonical_filename, et, method="mc")
        if n > 1:
            best_d, best_rec, best_k = float("inf"), None, None
            for k in range(n):
                sf = RES_DIR / wrap._per_cohort_path(canonical_filename, et, method="mc").replace(
                    f"_edType{et}", f"_edType{et}_start{k}")
                if not sf.exists():
                    print(f"[reest] FATAL: missing {sf}")
                    return 1
                rec = _load_record(sf.read_text().strip())
                d = float(rec.get("distance", float("inf")))
                print(f"[reest]   {EDU_NAMES[et]} start={k}: beta={rec['beta']:.5f} "
                      f"nabla={rec['nabla']:.5f} GICx={rec['GICx']:.4f} distance={d:.5f}")
                if d < best_d:
                    best_d, best_rec, best_k = d, rec, k
            print(f"[reest] {EDU_NAMES[et]} best basin = start {best_k} (distance={best_d:.5f})")
            records[et] = best_rec
            # write the chosen basin to the canonical per-edType file (normalized)
            per_path.write_text(repr(_normalize(best_rec, et)) + "\n")
        else:
            if not per_path.exists():
                print(f"[reest] FATAL: missing {per_path}")
                return 1
            records[et] = _load_record(per_path.read_text().strip())

    # --- validate -----------------------------------------------------------
    for et, rec in records.items():
        b, nab, g = float(rec["beta"]), float(rec["nabla"]), float(rec["GICx"])
        lo, hi = BOUNDS["beta"]
        nlo, nhi = BOUNDS["nabla"]
        ok = (lo < b < hi) and (nlo <= nab < nhi) and (g == g) and abs(g) < 1e3
        print(f"[reest] {EDU_NAMES[et]}: beta={b:.5f} nabla={nab:.5f} GICx={g:.4f}  "
              f"{'OK' if ok else 'OUT OF BOUNDS'}")
        if not ok:
            print(f"[reest] FATAL: {EDU_NAMES[et]} record out of sanity bounds; "
                  f"NOT writing canonical. Inspect {logs}.")
            return 1

    # --- back up canonical, then merge -------------------------------------
    if canonical_path.exists():
        bak = canonical_path.with_suffix(f".prebug047.{int(t0)}.txt")
        bak.write_text(canonical_path.read_text())
        print(f"[reest] backed up prior canonical -> {bak.name}")

    sys.path.insert(0, str(FPC))
    import EstimParameters as ep
    footer = (f"\nParameters: R = {round(ep.Rfree_base[0], 2)}, CRRA = {round(ep.CRRA, 2)}, "
              f"IncUnemp = {round(ep.IncUnemp, 2)}, IncUnempNoBenefits = {round(ep.IncUnempNoBenefits, 2)}, "
              f"Splurge = {ep.Splurge}\n")
    merged = [repr(_normalize(records[et], et)) for et in (0, 1, 2)]
    canonical_path.write_text("\n".join(merged) + "\n" + footer)
    print(f"[reest] wrote merged canonical -> {canonical_path}")

    longest = max(durations.values()) / 60
    print(f"[reest] DONE. wall = {(time.time()-t0)/60:.1f} min  |  slowest child = {longest:.1f} min")
    print("[reest] NOTE: AllResults_*.txt (full-pop diagnostic stats) NOT regenerated; "
          "calibration files are the deliverable. Regenerate with the wrapper's "
          "calcAllResults pass if needed.")
    return 0


def _normalize(rec: dict, et: int) -> dict:
    """Emit a clean 4-key record (drop 'distance' so all edTypes match)."""
    return {"EducationGroup": et, "beta": float(rec["beta"]),
            "nabla": float(rec["nabla"]), "GICx": float(rec["GICx"])}


if __name__ == "__main__":
    sys.exit(main())
