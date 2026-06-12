"""Shared parsing/hashing for LOCKED_TABLES.manifest (QE-baseline freeze).

Used by Code/HA-Models/test_locked_tables.py and reproduce/promote_candidates.py.
Manifest format: tab-separated rows `path sha256 lock-date qe-source-rev reason`;
lines starting with `#` (and blank lines) are comments.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "LOCKED_TABLES.manifest"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_manifest(manifest_path=MANIFEST_PATH):
    """Return a list of row dicts: path, sha256, lock_date, qe_source_rev, reason."""
    rows = []
    if not Path(manifest_path).exists():
        return rows
    for lineno, line in enumerate(
            Path(manifest_path).read_text().splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 5:
            raise ValueError(
                f"{manifest_path}:{lineno}: expected 5 tab-separated fields, "
                f"got {len(fields)}: {line!r}")
        rows.append({
            "path": fields[0].strip(),
            "sha256": fields[1].strip(),
            "lock_date": fields[2].strip(),
            "qe_source_rev": fields[3].strip(),
            "reason": fields[4].strip(),
        })
    return rows


def format_row(path, sha256, lock_date, qe_source_rev, reason):
    return "\t".join([path, sha256, lock_date, qe_source_rev, reason])
