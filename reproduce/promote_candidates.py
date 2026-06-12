#!/usr/bin/env python3
"""Promote `_candidate` result files to frozen canonical status (QE-baseline freeze).

This is the ONE deliberate path by which the paper's result numbers change.
For each file listed in LOCKED_TABLES.manifest (or given on the command line)
that has a `_candidate` sibling:

  1. show the value diff (numbers extracted from frozen vs candidate),
  2. require explicit confirmation (unless --yes),
  3. copy candidate -> frozen,
  4. recompute and update the manifest row (new lock-date / provenance),
  5. flag every wrapper NOTE and prose line quoting a changed number, so the
     prose is re-coordinated in the same reviewed commit.

Then commit with: HAFISCAL_UNLOCK=1 git commit ...  (the pre-commit hook
verifies staged frozen files against the staged manifest).

Usage:
    python reproduce/promote_candidates.py             # all manifest rows
    python reproduce/promote_candidates.py PATH...     # specific frozen files
    python reproduce/promote_candidates.py --dry-run   # report only
    python reproduce/promote_candidates.py --yes       # no interactive prompt

Plan: plans/20260611_qe-baseline-freeze-and-candidate-lock_plan.md §3e
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from locked_manifest import (  # noqa: E402
    MANIFEST_PATH, REPO_ROOT, format_row, parse_manifest, sha256_file)

CANDIDATE_SUFFIX = "_candidate"

# Directories whose .tex files may quote result numbers in prose/NOTEs.
PROSE_SEARCH_DIRS = ["Subfiles", "Tables", "Figures"]

NUMBER_RE = re.compile(r"\d+\.\d+")  # decimals only: integers are too noisy


def candidate_path(canonical: Path) -> Path:
    return canonical.with_name(
        canonical.stem + CANDIDATE_SUFFIX + canonical.suffix)


def extract_numbers(path: Path):
    try:
        return NUMBER_RE.findall(path.read_text(errors="replace"))
    except OSError:
        return []


def value_diff(frozen: Path, cand: Path):
    """Pairwise positional diff of decimal numbers; returns (changed, gone, new)."""
    f_nums, c_nums = extract_numbers(frozen), extract_numbers(cand)
    changed = [(i, a, b) for i, (a, b) in enumerate(zip(f_nums, c_nums)) if a != b]
    return changed, f_nums[len(c_nums):], c_nums[len(f_nums):]


def flag_prose(changed_values, frozen_rel):
    """Grep prose/NOTE files for each pre-promotion value that changed."""
    hits = []
    for _, old, _new in changed_values:
        for d in PROSE_SEARCH_DIRS:
            ddir = REPO_ROOT / d
            if not ddir.is_dir():
                continue
            try:
                out = subprocess.run(
                    ["grep", "-rn", "--include=*.tex", "-F", old, str(ddir)],
                    capture_output=True, text=True, check=False).stdout
            except OSError:
                continue
            for line in out.splitlines():
                hits.append((old, line.replace(str(REPO_ROOT) + os.sep, "")))
    return hits


def update_manifest_row(rows, rel_path, new_sha, provenance):
    today = date.today().isoformat()
    for row in rows:
        if row["path"] == rel_path:
            row["sha256"] = new_sha
            row["lock_date"] = today
            row["qe_source_rev"] = provenance
            row["reason"] = "promoted candidate"
            return
    rows.append({"path": rel_path, "sha256": new_sha, "lock_date": today,
                 "qe_source_rev": provenance, "reason": "promoted candidate"})


def write_manifest(rows):
    text = MANIFEST_PATH.read_text()
    header = [ln for ln in text.splitlines() if ln.startswith("#") or not ln.strip()]
    body = [format_row(r["path"], r["sha256"], r["lock_date"],
                       r["qe_source_rev"], r["reason"]) for r in rows]
    MANIFEST_PATH.write_text("\n".join(header + body) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*",
                    help="frozen files to promote (default: all manifest rows)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show diffs only; change nothing")
    ap.add_argument("--yes", action="store_true",
                    help="promote without interactive confirmation")
    ap.add_argument("--provenance", default="",
                    help="provenance string for the manifest row (e.g. repo rev)")
    args = ap.parse_args()

    rows = parse_manifest()
    if args.paths:
        targets = [Path(p).resolve().relative_to(REPO_ROOT).as_posix()
                   if Path(p).is_absolute() else p for p in args.paths]
    else:
        targets = [r["path"] for r in rows]

    if not targets:
        print("Nothing to promote: manifest has no rows and no paths given.")
        return 0

    provenance = args.provenance or subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=False).stdout.strip() or "unknown"

    promoted = 0
    for rel in targets:
        frozen = REPO_ROOT / rel
        cand = candidate_path(frozen)
        if not cand.exists():
            continue
        print(f"\n=== {rel}")
        print(f"    candidate: {cand.relative_to(REPO_ROOT)}")
        if not frozen.exists():
            print("    (frozen file does not exist yet — candidate is new)")
            changed, gone, new = [], [], extract_numbers(cand)
        else:
            changed, gone, new = value_diff(frozen, cand)
        if not changed and not gone and not new:
            print("    values identical (formatting-only or no change)")
        for i, old, newv in changed:
            print(f"    value[{i}]: {old} -> {newv}")
        if gone:
            print(f"    values removed: {gone}")
        if new:
            print(f"    values added: {new}")

        prose_hits = flag_prose(changed, rel)
        if prose_hits:
            print("    ⚠ prose/NOTE lines quoting a changed value — "
                  "re-coordinate in the SAME commit:")
            for old, line in prose_hits:
                print(f"      [{old}] {line}")

        if args.dry_run:
            continue
        if not args.yes:
            resp = input(f"    Promote {rel}? [y/N] ").strip().lower()
            if resp not in ("y", "yes"):
                print("    skipped")
                continue
        shutil.copy2(cand, frozen)
        update_manifest_row(rows, rel, sha256_file(frozen), provenance)
        promoted += 1
        print(f"    ✅ promoted (manifest row updated)")

    if promoted and not args.dry_run:
        write_manifest(rows)
        print(f"\n{promoted} file(s) promoted. Manifest updated.")
        print("Review the flagged prose lines, then commit with:")
        print("  HAFISCAL_UNLOCK=1 git commit ...")
    elif not args.dry_run:
        print("\nNo candidates found to promote.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
