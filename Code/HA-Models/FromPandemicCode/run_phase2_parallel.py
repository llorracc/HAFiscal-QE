#!/usr/bin/env python
"""Run the Step-2 (β/∇) estimation with selected education types in parallel.

Each education type's Nelder-Mead optimization is independent of the others —
the only coupling between them is that the AggDemandEconomy holds all 21
agents (3 edTypes × 7 DiscFac grid points), but for steady-state (β,∇)
estimation that's just a holder; no cross-edType dynamics.

Approach:
  - Spawn one subprocess per edType in HAFISCAL_WRAPPER_EDTYPES (default "0,1,2"),
    each running EstimAggFiscalMAIN.py with HAFISCAL_EDTYPES={N} so only that
    edType runs Nelder-Mead.
  - Each subprocess gets HAFISCAL_SERIAL=1 in its environment to force the
    sequential `multi_thread_commands_fake` path inside HARK. The parallel
    `multi_thread_commands` path triggers fresh joblib worker spawns each
    Nelder-Mead eval; over hundreds of evals the workers re-import
    EstimAggFiscalMAIN at module level, run its top-level setup, and OOM.
    Subprocess-level parallelism (this wrapper) replaces in-process worker
    parallelism (joblib) so we get speedup without the recursion bug.
  - Each subprocess writes to ../Results/DiscFacEstim_..._edType{N}.txt.
  - When all subprocesses finish, this wrapper merges them into the canonical
    DiscFacEstim_....txt. For edTypes NOT run in this invocation (e.g.
    HAFISCAL_WRAPPER_EDTYPES=1,2 reuses a previously-completed Dropout result),
    the merger reads the existing canonical file's record for that edType.
  - Final calcAllResults pass: re-runs EstimAggFiscalMAIN with
    HAFISCAL_SKIP_ESTIMATION_OPTIMIZE=1 to get full-population statistics
    using the merged β/∇ values.

Usage:
  cd Code/HA-Models/FromPandemicCode
  python run_phase2_parallel.py                              # all 3 edTypes
  HAFISCAL_WRAPPER_EDTYPES=1,2 python run_phase2_parallel.py # HS+College only

Speedup: edTypes run concurrently. Wall clock ≈ longest single edType
(typically Dropout) instead of sum of all three. Roughly 2.5-3× over the
sequential baseline.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES_DIR = (HERE.parent / 'Results').resolve()
LOG_DIR = Path('/tmp')


def _result_filename_base(method: str = "mc") -> str:
    """Reproduce the child estimator's canonical filename exactly.

    Pattern: `DiscFacEstim_CRRA_X_R_Y[_altBenefits|_Splurge0][_TM_a][_ESC].txt`

    Order matters: method (`_TM_a`) BEFORE interpretation (`_ESC`), so the
    wrapper can derive per-cohort paths by inserting `_edType{N}` before
    the method+interpretation suffixes — see `_per_cohort_path()` below.

    Parameters
    ----------
    method : 'mc' or 'tm_a'
        Step-2 estimator. Selects whether `_TM_a` is in the suffix.
    """
    sys.path.insert(0, str(HERE))
    import EstimParameters as ep
    base = f"DiscFacEstim_CRRA_{ep.CRRA}_R_{ep.Rfree_base[0]}"
    if ep.IncUnemp != 0.7 or ep.IncUnempNoBenefits != 0.5:
        base += "_altBenefits"
    if ep.Splurge == 0:
        base += "_Splurge0"
    if method == "tm_a":
        base += "_TM_a"
    # ESC interpretation suffix (always last). CDC stays unsuffixed for
    # backward compat with legacy reads.
    sys.path.insert(0, str(HERE.parent))
    from _interpretation import interp_suffix
    base += interp_suffix()
    return base + ".txt"


def _per_cohort_path(canonical_filename: str, et: int, method: str = "mc") -> str:
    """Path the child estimator writes for a single edType.

    Both estimators use the convention: insert `_edType{N}` BEFORE the
    method+interpretation suffixes.

    - MC + CDC:    `....txt`           → `..._edType{N}.txt`
    - MC + ESC:    `..._ESC.txt`       → `..._edType{N}_ESC.txt`
    - TM-a + CDC:  `..._TM_a.txt`      → `..._edType{N}_TM_a.txt`
    - TM-a + ESC:  `..._TM_a_ESC.txt`  → `..._edType{N}_TM_a_ESC.txt`
    """
    # Strip the trailing method+interp suffix(es), insert _edType, re-append
    sys.path.insert(0, str(HERE.parent))
    from _interpretation import interp_suffix
    method_suffix = "_TM_a" if method == "tm_a" else ""
    interp = interp_suffix()
    trailing = method_suffix + interp + ".txt"
    if not canonical_filename.endswith(trailing):
        raise ValueError(
            f"canonical filename {canonical_filename!r} doesn't end with "
            f"expected trailing {trailing!r} for method={method!r}"
        )
    base = canonical_filename[: -len(trailing)]
    return base + f"_edType{et}" + trailing


def _read_existing_record(canonical_path: Path, edtype: int) -> str | None:
    """Pull the dict-line for `edtype` from an existing canonical file, if any."""
    if not canonical_path.exists():
        return None
    needle = f"'EducationGroup': {edtype}"
    for line in canonical_path.read_text().splitlines():
        if needle in line:
            return line.strip()
    return None


def main() -> int:
    # HAFISCAL_STEP2_METHOD: dispatch to MC (EstimAggFiscalMAIN.py) or TM-a
    # (estim_phase2_tm_a.py) estimator. Both honor HAFISCAL_EDTYPES and write
    # canonical + per-cohort files (with method+interp suffixes); only the
    # script path and canonical filename pattern differ.
    STEP2_METHOD = os.environ.get("HAFISCAL_STEP2_METHOD", "mc").lower()
    if STEP2_METHOD not in ("mc", "tm_a"):
        raise ValueError(f"HAFISCAL_STEP2_METHOD must be 'mc' or 'tm_a'; got {STEP2_METHOD!r}")
    print(f"[wrapper] HAFISCAL_STEP2_METHOD = {STEP2_METHOD}")

    canonical_filename = _result_filename_base(method=STEP2_METHOD)
    canonical_path = RES_DIR / canonical_filename
    print(f"[wrapper] canonical result file: {canonical_path}")

    # Determine which edTypes to launch (default = all three)
    wrapper_env = os.environ.get("HAFISCAL_WRAPPER_EDTYPES", "0,1,2")
    edtypes_to_run = [int(s) for s in wrapper_env.split(",") if s.strip()]
    print(f"[wrapper] launching subprocesses for edTypes={edtypes_to_run}")
    edtypes_skipped = [et for et in (0, 1, 2) if et not in edtypes_to_run]
    if edtypes_skipped:
        print(f"[wrapper] skipping edTypes={edtypes_skipped}; will reuse existing records from {canonical_path}")

    # BUG-039 Phase F: HAFISCAL_PARALLEL_MULTISTART=1 enables per-(cohort, start)
    # subprocess parallelism. When set with HAFISCAL_NUM_STARTS > 1, each cohort's
    # multistart points run as separate concurrent subprocesses (instead of the
    # default "one subprocess per cohort, sequential multistart inside"). For D
    # with 4 starts: ~4× speedup vs sequential multistart inside the subprocess.
    PARALLEL_MULTISTART = os.environ.get("HAFISCAL_PARALLEL_MULTISTART", "0") == "1"
    NUM_STARTS = int(os.environ.get("HAFISCAL_NUM_STARTS", "1"))
    if PARALLEL_MULTISTART and NUM_STARTS > 1:
        # Per-cohort multistart count (must match _multistart_grid in EstimAggFiscalMAIN.py)
        # Capped by HAFISCAL_NUM_STARTS env var.
        _per_cohort_max_starts = {0: 4, 1: 3, 2: 2}
        _starts_per_cohort = {et: min(NUM_STARTS, _per_cohort_max_starts.get(et, 1))
                              for et in edtypes_to_run}
        print(f"[wrapper Phase F] HAFISCAL_PARALLEL_MULTISTART=1, NUM_STARTS={NUM_STARTS}; "
              f"per-cohort start counts: {_starts_per_cohort}")
    else:
        if PARALLEL_MULTISTART:
            print(f"[wrapper] HAFISCAL_PARALLEL_MULTISTART=1 but NUM_STARTS={NUM_STARTS} "
                  f"(needs >1 to take effect); using legacy per-cohort subprocess mode")
        _starts_per_cohort = None

    python = sys.executable
    script = HERE / ("EstimAggFiscalMAIN.py" if STEP2_METHOD == "mc" else "estim_phase2_tm_a.py")
    if STEP2_METHOD == "tm_a" and PARALLEL_MULTISTART:
        # The TM-a estimator doesn't currently honor HAFISCAL_PIN_START_INDEX
        # (Phase F per-(cohort, start) parallelism is MC-only). Fall back to
        # per-cohort multistart-inside-subprocess for TM-a.
        print("[wrapper] HAFISCAL_PARALLEL_MULTISTART=1 not supported for TM-a; "
              "falling back to per-cohort subprocess mode (multistart runs inside)")
        _starts_per_cohort = None

    if _starts_per_cohort is None:
        # Legacy mode: one subprocess per cohort
        procs: dict[int, subprocess.Popen] = {}
        log_paths: dict[int, Path] = {}
        t0 = time.time()
        for et in edtypes_to_run:
            env = os.environ.copy()
            env["HAFISCAL_EDTYPES"] = str(et)
            env["HAFISCAL_SERIAL"] = "1"
            log_path = LOG_DIR / f"phase2_parallel_edType{et}.log"
            log_paths[et] = log_path
            log_fh = open(log_path, "w")
            print(f"[wrapper] launching edType={et} → {log_path}")
            procs[et] = subprocess.Popen(
                [python, "-u", str(script)],
                cwd=str(HERE),
                env=env,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
            )

        # Wait for all subprocesses, reporting per-edType completion
        durations: dict[int, float] = {}
        remaining = set(edtypes_to_run)
        while remaining:
            time.sleep(15)
            for et in list(remaining):
                rc = procs[et].poll()
                if rc is not None:
                    durations[et] = time.time() - t0
                    tag = "OK" if rc == 0 else f"FAIL (rc={rc})"
                    print(f"[wrapper] edType={et} {tag} after {durations[et]/60:.1f} min")
                    remaining.discard(et)

        for et, p in procs.items():
            if p.returncode != 0:
                print(f"[wrapper] FATAL: edType={et} exited rc={p.returncode}; see {log_paths[et]}")
                return 1
    else:
        # BUG-039 Phase F: per-(cohort, start) subprocesses
        procs: dict[tuple, subprocess.Popen] = {}  # keyed by (et, k)
        log_paths: dict[tuple, Path] = {}
        t0 = time.time()
        for et in edtypes_to_run:
            for k in range(_starts_per_cohort[et]):
                env = os.environ.copy()
                env["HAFISCAL_EDTYPES"] = str(et)
                env["HAFISCAL_SERIAL"] = "1"
                env["HAFISCAL_PIN_START_INDEX"] = str(k)
                log_path = LOG_DIR / f"phase2_parallel_edType{et}_start{k}.log"
                log_paths[(et, k)] = log_path
                log_fh = open(log_path, "w")
                print(f"[wrapper] launching edType={et} start={k} → {log_path}")
                procs[(et, k)] = subprocess.Popen(
                    [python, "-u", str(script)],
                    cwd=str(HERE),
                    env=env,
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                )

        # Wait for all (cohort, start) subprocesses
        durations: dict[tuple, float] = {}
        remaining = set(procs.keys())
        while remaining:
            time.sleep(15)
            for key in list(remaining):
                rc = procs[key].poll()
                if rc is not None:
                    durations[key] = time.time() - t0
                    tag = "OK" if rc == 0 else f"FAIL (rc={rc})"
                    print(f"[wrapper] edType={key[0]} start={key[1]} {tag} after {durations[key]/60:.1f} min")
                    remaining.discard(key)

        for key, p in procs.items():
            if p.returncode != 0:
                print(f"[wrapper] FATAL: edType={key[0]} start={key[1]} exited rc={p.returncode}; see {log_paths[key]}")
                return 1

        # For each cohort, pick the best-basin start file and write it to the
        # canonical per-edType file (so the existing merge logic below works).
        # Use _per_cohort_path() so file naming respects method+interp suffix order.
        import ast as _ast
        for et in edtypes_to_run:
            best_dist = float('inf')
            best_line = None
            best_k = None
            for k in range(_starts_per_cohort[et]):
                start_file = RES_DIR / _per_cohort_path(canonical_filename, et, method=STEP2_METHOD).replace(
                    f'_edType{et}', f'_edType{et}_start{k}'
                )
                if not start_file.exists():
                    print(f"[wrapper] FATAL: missing {start_file}")
                    return 1
                line = start_file.read_text().strip()
                rec = _ast.literal_eval(line)
                d = float(rec.get('distance', float('inf')))
                if d < best_dist:
                    best_dist = d
                    best_line = line
                    best_k = k
            print(f"[wrapper] edType={et}: best basin from start={best_k} (distance={best_dist:.4f})")
            # Write the best basin to the canonical per-edType file
            per_path = RES_DIR / _per_cohort_path(canonical_filename, et, method=STEP2_METHOD)
            with open(per_path, 'w') as f:
                f.write(best_line + '\n')

    # Merge: pull from per-edType files for the subprocesses we ran, and from
    # the existing canonical file for any skipped edTypes.
    print(f"[wrapper] merging records into {canonical_path}")
    merged_lines: list[str] = []
    for et in (0, 1, 2):
        if et in edtypes_to_run:
            per_path = RES_DIR / _per_cohort_path(canonical_filename, et, method=STEP2_METHOD)
            if not per_path.exists():
                print(f"[wrapper] FATAL: subprocess for edType={et} produced no {per_path}")
                return 1
            merged_lines.append(per_path.read_text().strip())
        else:
            prior = _read_existing_record(canonical_path, et)
            if prior is None:
                print(f"[wrapper] FATAL: edType={et} skipped but no prior record in {canonical_path}")
                return 1
            print(f"[wrapper] reusing prior edType={et} record from {canonical_path}")
            merged_lines.append(prior)

    # Append the parameter footer (single-edType subprocesses skip it)
    sys.path.insert(0, str(HERE))
    import EstimParameters as ep
    footer = (f"\nParameters: R = {round(ep.Rfree_base[0], 2)}, CRRA = {round(ep.CRRA, 2)}, "
              f"IncUnemp = {round(ep.IncUnemp, 2)}, IncUnempNoBenefits = {round(ep.IncUnempNoBenefits, 2)}, "
              f"Splurge = {ep.Splurge}\n")

    # Candidate-routing (QE-baseline freeze): writes `_candidate` sibling
    # unless HAFISCAL_PROMOTE=1. See generated_output.py.
    from generated_output import open_generated, output_path as _routed
    with open_generated(canonical_path) as f:
        f.write('\n'.join(merged_lines) + '\n' + footer)
    print(f"[wrapper] wrote merged {_routed(canonical_path)}")

    # If we ran TM-a Step-2, also write the merged result to the
    # un-method-tagged canonical file (e.g. `..._ESC.txt`). Downstream
    # consumers (Parameters.py via resolve_path → Step 5, table generators
    # via AllResults) read from the un-tagged canonical file. Without this
    # mirror, TM-a Step 2 outputs would be invisible to Step 5 / tables.
    if STEP2_METHOD == "tm_a":
        downstream_canonical = _result_filename_base(method="mc")
        downstream_path = RES_DIR / downstream_canonical
        with open_generated(downstream_path) as f:
            f.write('\n'.join(merged_lines) + '\n' + footer)
        print(f"[wrapper] mirrored TM-a result to downstream canonical {_routed(downstream_path)}")

    total = (time.time() - t0) / 60
    longest = max(durations.values()) / 60
    print(f"[wrapper] total wall clock: {total:.1f} min  |  longest edType: {longest:.1f} min  |  speedup vs sequential: {sum(durations.values())/(longest*60):.2f}×")

    # Run a final calcAllResults pass (full-population stats with merged params).
    # Always uses EstimAggFiscalMAIN.py (MC-method full-population stats), not the
    # estim_phase2_tm_a.py script — TM-a is an estimator-only path; AllResults
    # computation is MC-format regardless of how the cal was estimated.
    calcAllResults_script = HERE / "EstimAggFiscalMAIN.py"
    print(f"[wrapper] running final calcAllResults pass over merged file via {calcAllResults_script.name}…")
    env = os.environ.copy()
    env.pop("HAFISCAL_EDTYPES", None)  # ensure full-pop mode
    # NOTE: do NOT pop HAFISCAL_STEP2_METHOD — even though calcAllResults
    # uses MC-format helpers, the saved cal it reads was estimated under
    # the configured step2_method. Preserving the env var ensures the
    # registry records the correct step2_method for warm-start lookup.
    env["HAFISCAL_SKIP_ESTIMATION_OPTIMIZE"] = "1"  # gate skips Nelder-Mead but runs calcAllResults
    rc = subprocess.run([python, "-u", str(calcAllResults_script)], cwd=str(HERE), env=env).returncode
    if rc != 0:
        print(f"[wrapper] WARNING: calcAllResults pass exited rc={rc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
