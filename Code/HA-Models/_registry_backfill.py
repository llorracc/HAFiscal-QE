"""One-shot backfill of pre-existing suffix-named cal files into the registry.

Per Phase 5 of `plans/20260503-1030h_results-registry-and-impc-gof.md`.

Best-effort: filename suffixes encode interpretation (`_ESC`), method
(`_TM_a`), splurge=0 (`_Splurge0`), altBenefits, per-cohort (`_edType{N}`),
per-multistart-point (`_start{K}`). Other config dimensions (gicx_mode,
nm_start_from_saved, num_starts, parallel_multistart, NM tolerances) are
NOT recoverable from filenames — those slots use sentinel value "legacy_unknown"
so the resulting config_hash is distinct from any current-defaults hash.

Run:
    python Code/HA-Models/_registry_backfill.py [--dry-run]
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import _registry  # noqa: E402

_RESULTS_DIR = _HERE / "Results"
_TARGET_DIR = _HERE / "Target_AggMPCX_LiquWealth"


# Map filename suffix patterns to inferred dimensions.
# Order matters in the regex (longer patterns first).
_FILENAME_PATTERN = re.compile(
    r"^(?P<base>(?:DiscFacEstim|AllResults))_CRRA_(?P<crra>[\d.]+)_R_(?P<rfree>[\d.]+)"
    r"(?P<altbenefits>_altBenefits)?"
    r"(?P<splurge0>_Splurge0)?"
    r"(?P<edtype>_edType[0-9]+)?"
    r"(?P<start>_start[0-9]+)?"
    r"(?P<tma>_TM_a)?"
    r"(?P<tm>_TM)?"
    r"(?P<esc>_ESC)?"
    r"(?P<bug036>_BUG036_bad_basin)?"
    r"(?P<warmstart_tag>_TM_from_MC_warmstart)?"
    r"\.txt$"
)


def _file_mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat()


def _git_last_touched_commit(path: Path) -> str:
    """Find the commit SHA that last touched this file (best-effort)."""
    try:
        out = subprocess.check_output(
            ["git", "log", "-n", "1", "--format=%H", "--", str(path)],
            cwd=str(path.parent), stderr=subprocess.DEVNULL,
        )
        sha = out.decode().strip()
        return sha if sha else "unknown"
    except Exception:
        return "unknown"


def _infer_config(filename: str) -> dict | None:
    """Infer (best-effort) configuration from filename. Returns None if unparseable."""
    m = _FILENAME_PATTERN.match(filename)
    if m is None:
        return None
    g = m.groupdict()

    # Determine method/interpretation from filename suffixes
    if g["tma"]:
        step2_method = "tm_a"
    elif g["tm"]:
        step2_method = "tm_legacy"  # the older _TM.txt format
    else:
        step2_method = "mc"

    interp = "ESC" if g["esc"] else "CDC"

    return {
        "interpretation": interp,
        "step1_method": "MC",
        "step2_method": step2_method,
        "step5_method": "legacy_unknown",
        "step5_scope": "legacy_unknown",
        "gicx_mode": "legacy_unknown",
        "nm_start_from_saved": "legacy_unknown",
        "num_starts": "legacy_unknown",
        "parallel_multistart": "legacy_unknown",
        "nm_xatol": "legacy_unknown",
        "nm_fatol": "legacy_unknown",
        "crra": float(g["crra"]),
        "rfree": float(g["rfree"]),
        "inc_unemp": "legacy_altBenefits" if g["altbenefits"] else 0.7,
        "inc_unemp_no_benefits": "legacy_altBenefits" if g["altbenefits"] else 0.5,
        "splurge_value": 0.0 if g["splurge0"] else "legacy_unknown",
        "cohort_set": [int(g["edtype"][len("_edType"):])] if g["edtype"] else [0, 1, 2],
        "_legacy_filename": filename,
        "_legacy_tags": {k: v for k, v in g.items() if v and not k.startswith("base")},
    }


def _output_type_from_filename(g: dict) -> tuple[str, dict]:
    """Map regex groupdict → (output_type, extras) for register_output()."""
    if g.get("base") == "DiscFacEstim":
        if g.get("start"):
            return ("step2_per_start", {
                "cohort": int(g["edtype"][len("_edType"):]) if g["edtype"] else None,
                "start_idx": int(g["start"][len("_start"):]),
            })
        if g.get("edtype"):
            return ("step2_per_cohort", {
                "cohort": int(g["edtype"][len("_edType"):]),
            })
        return ("step2_cal", {})
    elif g.get("base") == "AllResults":
        return ("step5_allresults", {})
    return ("unknown", {})


def backfill(dry_run: bool = False) -> dict:
    """Walk Results/*.txt and Target_AggMPCX_LiquWealth/Result_AllTarget*.txt; register each."""
    files_seen = []
    files_skipped = []
    runs_created = set()
    outputs_registered = 0

    if not dry_run:
        _registry.ensure_db()

    candidates = list(_RESULTS_DIR.glob("DiscFacEstim_*.txt")) + \
                 list(_RESULTS_DIR.glob("AllResults_*.txt")) + \
                 list(_TARGET_DIR.glob("Result_AllTarget*.txt"))

    for path in sorted(candidates):
        # Special-case Result_AllTarget files (Step 1) — separate inference
        if path.name.startswith("Result_AllTarget"):
            interp = "ESC" if "_ESC" in path.name else ("CDC" if "_CDC" in path.name else "CDC")
            splurge0 = "_Splurge0" in path.name
            config = {
                "interpretation": interp,
                "step1_method": "MC",
                "step2_method": "legacy_unknown",
                "step5_method": "legacy_unknown",
                "step5_scope": "legacy_unknown",
                "gicx_mode": "legacy_unknown",
                "nm_start_from_saved": "legacy_unknown",
                "num_starts": "legacy_unknown",
                "parallel_multistart": "legacy_unknown",
                "nm_xatol": "legacy_unknown",
                "nm_fatol": "legacy_unknown",
                "crra": 2.0,
                "rfree": 1.01,
                "inc_unemp": 0.7,
                "inc_unemp_no_benefits": 0.5,
                "splurge_value": 0.0 if splurge0 else "legacy_unknown",
                "cohort_set": [0, 1, 2],
                "_legacy_filename": path.name,
                "_legacy_tags": {"splurge0": splurge0, "interp": interp},
            }
            output_type = "splurge"
            extras = {}
            mtime_iso = _file_mtime_iso(path)
            commit_sha = _git_last_touched_commit(path)
            files_seen.append((path.name, config, output_type, extras, mtime_iso, commit_sha))
            continue

        config = _infer_config(path.name)
        if config is None:
            files_skipped.append((path.name, "unparseable filename"))
            continue
        m = _FILENAME_PATTERN.match(path.name)
        output_type, extras = _output_type_from_filename(m.groupdict())
        if output_type == "unknown":
            files_skipped.append((path.name, "unknown output_type"))
            continue
        mtime_iso = _file_mtime_iso(path)
        commit_sha = _git_last_touched_commit(path)
        files_seen.append((path.name, config, output_type, extras, mtime_iso, commit_sha))

    # Print summary
    print(f"Found {len(files_seen)} files to backfill, {len(files_skipped)} skipped.")
    if dry_run:
        print("\nDRY RUN — no DB writes. Files that would be registered:")
        for fname, cfg, otype, extras, mtime, sha in files_seen:
            print(f"  {fname}")
            print(f"    type={otype} extras={extras}")
            print(f"    interp={cfg['interpretation']} step2_method={cfg['step2_method']} "
                  f"splurge={cfg['splurge_value']} cohort_set={cfg['cohort_set']}")
            print(f"    mtime={mtime}  last_commit={sha[:8] if sha != 'unknown' else 'unknown'}")
        if files_skipped:
            print("\nSkipped:")
            for fname, why in files_skipped:
                print(f"  {fname}: {why}")
        return {
            "n_files_seen": len(files_seen),
            "n_files_skipped": len(files_skipped),
        }

    # Real backfill
    for path_name, config, output_type, extras, mtime_iso, commit_sha in files_seen:
        path = _RESULTS_DIR / path_name if (_RESULTS_DIR / path_name).exists() else _TARGET_DIR / path_name
        # Build a synthetic run_id from the file's last-commit + file mtime
        cfg_hash = _registry.config_hash(config)
        commit_short = commit_sha[:8] if commit_sha != "unknown" else "legacy00"
        # parse mtime back to datetime for the date-local string
        date_local = datetime.fromisoformat(mtime_iso).strftime("%Y%m%d-%H%M%S")
        run_id = f"{commit_short}_{cfg_hash}_{date_local}"

        if run_id not in runs_created:
            _registry.register_run(
                config=config, run_id=run_id,
                notes=f"BACKFILL from legacy file {path_name}",
            )
            # Mark as "complete" but with a flag in notes
            _registry.mark_run_status(run_id, "complete-backfilled")
            runs_created.add(run_id)

        _registry.register_output(run_id, output_type, str(path), **extras)
        outputs_registered += 1

    print(f"\nBackfill complete: {len(runs_created)} unique runs created, "
          f"{outputs_registered} outputs registered.")
    print(f"Run `python Code/HA-Models/_registry.py list` to inspect.")
    return {
        "n_runs_created": len(runs_created),
        "n_outputs_registered": outputs_registered,
        "n_files_skipped": len(files_skipped),
    }


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    backfill(dry_run=dry_run)
