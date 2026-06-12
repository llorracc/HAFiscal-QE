"""HAFiscal results registry — atomic per-output storage with SQLite index.

Per the design in `plans/20260503-1030h_results-registry-and-impc-gof.md`.

Key design points:
- SQLite (`Results/registry/registry.db`) holds runs, outputs, metrics, bug fixes.
- Each output is an independently versioned file under `Results/registry/outputs/<type>/`,
  named `<commit>_<confighash>_<date>.<ext>`. Date LAST per user direction.
- Per-output atomicity: write to `<path>.tmp`, then `os.rename()` (POSIX atomic).
  SQLite `INSERT OR REPLACE` for the matching row is also atomic.
- Symlink "views" under `Results/registry/views/latest_by_config/<bucket>/<output_type>`
  give human-browsable shortcuts to the most-recent file for each (config, type) tuple.

Public API:
- get_current_config()              -> dict
- config_hash(config_dict)          -> 6-char str
- make_run_id(config_hash)          -> "<commit>_<confighash>_<date>"
- ensure_db()                       -> initializes schema if needed
- register_run(config, ...)         -> creates the run row, returns run_id
- register_output(run_id, output_type, source_path, ...)  -> atomic copy + INSERT
- record_metric(run_id, name, value=None, json_value=None)
- record_bug_fix(run_id, bug_id)
- mark_run_status(run_id, status)
- find_latest_run(config_hash)      -> run_id or None
- find_output_path(run_id, output_type, cohort=None, start_idx=None) -> path or None
- find_warm_start_cal(target_config) -> path to step2_cal or None

Importable from any HAFiscal Python script. Falls back to a no-op stub if
sqlite3 is unavailable (it ships with stdlib so this should never fire).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HA_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _HA_ROOT.parent.parent
_REGISTRY_ROOT = _HA_ROOT / "Results" / "registry"
_DB_PATH = _REGISTRY_ROOT / "registry.db"
_OUTPUTS_ROOT = _REGISTRY_ROOT / "outputs"
_VIEWS_ROOT = _REGISTRY_ROOT / "views"

SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);

CREATE TABLE IF NOT EXISTS runs (
  run_id          TEXT PRIMARY KEY,
  config_hash     TEXT NOT NULL,
  config_json     TEXT NOT NULL,
  commit_sha      TEXT NOT NULL,
  branch          TEXT,
  date_iso        TEXT NOT NULL,
  date_local      TEXT NOT NULL,
  hark_version    TEXT,
  python_version  TEXT,
  wall_total_sec  REAL,
  status          TEXT NOT NULL,
  warm_start_run_id TEXT,
  notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_config_hash ON runs(config_hash);
CREATE INDEX IF NOT EXISTS idx_runs_date ON runs(date_iso DESC);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);

CREATE TABLE IF NOT EXISTS outputs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id          TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  output_type     TEXT NOT NULL,
  cohort          INTEGER,
  start_idx       INTEGER,
  path            TEXT NOT NULL,
  content_hash    TEXT NOT NULL,
  size_bytes      INTEGER,
  created_iso     TEXT NOT NULL,
  UNIQUE(run_id, output_type, cohort, start_idx)
);
CREATE INDEX IF NOT EXISTS idx_outputs_type_run ON outputs(output_type, run_id);
CREATE INDEX IF NOT EXISTS idx_outputs_run ON outputs(run_id);
CREATE INDEX IF NOT EXISTS idx_outputs_hash ON outputs(content_hash);

CREATE TABLE IF NOT EXISTS metrics (
  run_id          TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  metric_name     TEXT NOT NULL,
  metric_value    REAL,
  metric_json     TEXT,
  PRIMARY KEY (run_id, metric_name)
);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_metrics_run ON metrics(run_id);

CREATE TABLE IF NOT EXISTS run_bug_fixes (
  run_id   TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  bug_id   TEXT NOT NULL,
  PRIMARY KEY (run_id, bug_id)
);
"""


# ---------- DB lifecycle ----------

def _connect() -> sqlite3.Connection:
    _REGISTRY_ROOT.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_db() -> None:
    """Initialize the schema if the DB doesn't exist or is stale."""
    _REGISTRY_ROOT.mkdir(parents=True, exist_ok=True)
    _OUTPUTS_ROOT.mkdir(parents=True, exist_ok=True)
    _VIEWS_ROOT.mkdir(parents=True, exist_ok=True)
    (_VIEWS_ROOT / "latest_by_config").mkdir(parents=True, exist_ok=True)
    (_VIEWS_ROOT / "latest_by_run").mkdir(parents=True, exist_ok=True)
    conn = _connect()
    try:
        conn.executescript(_SCHEMA_SQL)
        cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
        row = cur.fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        elif row[0] != SCHEMA_VERSION:
            raise RuntimeError(
                f"Registry schema version mismatch: file={row[0]}, code={SCHEMA_VERSION}. "
                "Migration required (not implemented yet)."
            )
        conn.commit()
    finally:
        conn.close()


# ---------- Config canonicalization ----------

def _read_env_or(default: Any, *names: str) -> Any:
    for name in names:
        val = os.environ.get(name)
        if val is not None and val != "":
            return val
    return default


def get_current_config() -> dict:
    """Return canonical dict of all registry-relevant configuration dimensions.

    Reads env vars + (where unambiguous) values from EstimParameters /
    Parameters. Best-effort; returns "unknown" for anything not yet wired.
    """
    # Try to import EstimParameters for parametric values; tolerate failure
    # (e.g., during init before the path is set up)
    crra, rfree, splurge, inc_unemp, inc_unemp_no_benefits = [None] * 5
    try:
        sys.path.insert(0, str(_HA_ROOT / "FromPandemicCode"))
        import EstimParameters as _ep  # noqa: F401
        crra = float(_ep.CRRA)
        rfree = float(_ep.Rfree_base[0])
        splurge = float(_ep.Splurge)
        inc_unemp = float(_ep.IncUnemp)
        inc_unemp_no_benefits = float(_ep.IncUnempNoBenefits)
    except Exception:
        pass

    interp = (os.environ.get("HAFISCAL_INTERPRETATION") or "CDC").upper()
    cohort_set_raw = os.environ.get("HAFISCAL_WRAPPER_EDTYPES") or os.environ.get("HAFISCAL_EDTYPES") or "0,1,2"
    cohort_set = sorted(int(s) for s in cohort_set_raw.split(",") if s.strip())

    return {
        "interpretation": interp,
        "step1_method": "MC",  # only one for now
        "step2_method": (os.environ.get("HAFISCAL_STEP2_METHOD") or "mc").lower(),
        "step5_method": "TM",  # default; overridden if AggFiscalMAIN sets sim_method='MC'
        "step5_scope": "unknown",  # set by caller (AggFiscalMAIN_reduced.py knows)
        "gicx_mode": (os.environ.get("HAFISCAL_GICX_MODE") or "hardcoded").lower(),
        "nm_start_from_saved": int(os.environ.get("HAFISCAL_NM_START_FROM_SAVED") or "1"),
        "num_starts": int(os.environ.get("HAFISCAL_NUM_STARTS") or "1"),
        "parallel_multistart": int(os.environ.get("HAFISCAL_PARALLEL_MULTISTART") or "0"),
        "nm_xatol": float(os.environ.get("HAFISCAL_NM_XATOL") or "0.01"),
        "nm_fatol": float(os.environ.get("HAFISCAL_NM_FATOL") or "0.01"),
        "crra": crra,
        "rfree": rfree,
        "inc_unemp": inc_unemp,
        "inc_unemp_no_benefits": inc_unemp_no_benefits,
        "splurge_value": splurge,
        "cohort_set": cohort_set,
    }


def _canonicalize(config: dict) -> str:
    """Canonical JSON for hashing (sorted keys, no whitespace)."""
    return json.dumps(config, sort_keys=True, separators=(",", ":"))


def config_hash(config: dict) -> str:
    """Stable 6-char short hash (first 6 chars of SHA-256 hex digest)."""
    canon = _canonicalize(config).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()[:6]


def config_summary(config: dict) -> str:
    """Human-readable one-liner of the most-load-bearing dims."""
    nm_start = config.get('nm_start_from_saved')
    if nm_start == "legacy_unknown" or nm_start is None:
        warm_tag = "legacy"
    elif nm_start in (1, "1", True):
        warm_tag = "warm"
    else:
        warm_tag = "cold"
    return (
        f"{config.get('interpretation')}_"
        f"{str(config.get('step2_method')).upper()}_"
        f"{config.get('step5_method')}_"
        f"{config.get('gicx_mode')}_"
        f"{warm_tag}"
    )


# ---------- Run-id ----------

def _git_commit_short() -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(_REPO_ROOT), "rev-parse", "--short=8", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "nogit000"


def _git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(_REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _git_commit_full() -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(_REPO_ROOT), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "0" * 40


def make_run_id(cfg_hash: str | None = None, when: datetime | None = None) -> str:
    """Build a run_id `<commit>_<confighash>_<date>`.

    If cfg_hash is None, computes from current config.
    If when is None, uses current local time.
    """
    if cfg_hash is None:
        cfg_hash = config_hash(get_current_config())
    if when is None:
        when = datetime.now()
    commit_short = _git_commit_short()
    date_local = when.strftime("%Y%m%d-%H%M%S")
    return f"{commit_short}_{cfg_hash}_{date_local}"


# ---------- Run lifecycle ----------

def register_run(
    config: dict | None = None,
    *,
    run_id: str | None = None,
    notes: str | None = None,
    warm_start_run_id: str | None = None,
) -> str:
    """Insert a new row into runs. Returns the run_id.

    Idempotent: if run_id already exists, leaves the existing row alone
    and returns it. (Useful when the same script is re-imported in a
    subprocess that's part of the same logical run.)
    """
    ensure_db()
    if config is None:
        config = get_current_config()
    cfg_hash = config_hash(config)
    if run_id is None:
        run_id = make_run_id(cfg_hash)

    now = datetime.now(timezone.utc)
    row = (
        run_id,
        cfg_hash,
        _canonicalize(config),
        _git_commit_full(),
        _git_branch(),
        now.isoformat(),
        datetime.now().strftime("%Y%m%d-%H%M%S"),
        _hark_version(),
        ".".join(map(str, sys.version_info[:3])),
        None,                # wall_total_sec — set later via mark_run_status
        "in_progress",
        warm_start_run_id,
        notes,
    )

    conn = _connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO runs "
            "(run_id, config_hash, config_json, commit_sha, branch, date_iso, "
            " date_local, hark_version, python_version, wall_total_sec, status, "
            " warm_start_run_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
        conn.commit()
    finally:
        conn.close()
    return run_id


def mark_run_status(run_id: str, status: str, *, wall_total_sec: float | None = None) -> None:
    """Update status (and optionally wall time) for an existing run."""
    ensure_db()
    conn = _connect()
    try:
        if wall_total_sec is None:
            conn.execute(
                "UPDATE runs SET status = ? WHERE run_id = ?",
                (status, run_id),
            )
        else:
            conn.execute(
                "UPDATE runs SET status = ?, wall_total_sec = ? WHERE run_id = ?",
                (status, wall_total_sec, run_id),
            )
        conn.commit()
    finally:
        conn.close()


# ---------- Output registration ----------

def _content_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _output_filename(run_id: str, ext: str) -> str:
    """`<run_id>.<ext>` — runs already encode commit/confighash/date."""
    return f"{run_id}{ext}"


def register_output(
    run_id: str,
    output_type: str,
    source_path: str | Path,
    *,
    cohort: int | None = None,
    start_idx: int | None = None,
    move: bool = False,
) -> Path:
    """Register an output file in the registry.

    Atomically copies (or moves) `source_path` to
    `Results/registry/outputs/<output_type>/<run_id><ext>`, then INSERTS/REPLACES
    a row in `outputs`.

    Returns the destination Path.
    """
    ensure_db()
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"register_output: {src} does not exist")

    ext = src.suffix
    dest_dir = _OUTPUTS_ROOT / output_type
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _output_filename(run_id, ext)
    dest_tmp = dest.with_suffix(dest.suffix + ".tmp")

    # Atomic copy: write to .tmp, then rename
    if move:
        shutil.move(str(src), str(dest_tmp))
    else:
        shutil.copy2(str(src), str(dest_tmp))
    os.replace(str(dest_tmp), str(dest))   # atomic rename

    h = _content_hash(dest)
    size = dest.stat().st_size
    now = datetime.now(timezone.utc).isoformat()
    rel_path = str(dest.relative_to(_REGISTRY_ROOT))

    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO outputs "
            "(run_id, output_type, cohort, start_idx, path, content_hash, size_bytes, created_iso) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, output_type, cohort, start_idx, rel_path, h, size, now),
        )
        conn.commit()
    finally:
        conn.close()

    _refresh_view_symlinks(run_id, output_type, dest, cohort, start_idx)
    return dest


def _refresh_view_symlinks(
    run_id: str, output_type: str, dest: Path,
    cohort: int | None, start_idx: int | None,
) -> None:
    """Update views/latest_by_config/<bucket>/<output_type> and views/latest_by_run/<run_id>/<output_type>."""
    # Look up config for this run to build the bucket name
    conn = _connect()
    try:
        cur = conn.execute("SELECT config_json FROM runs WHERE run_id = ?", (run_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return
    config = json.loads(row[0])
    bucket = config_summary(config)

    # views/latest_by_config/<bucket>/
    cfg_dir = _VIEWS_ROOT / "latest_by_config" / bucket
    cfg_dir.mkdir(parents=True, exist_ok=True)
    link_name = output_type
    if cohort is not None:
        link_name += f"_edType{cohort}"
    if start_idx is not None:
        link_name += f"_start{start_idx}"
    link_name += dest.suffix
    cfg_link = cfg_dir / link_name
    if cfg_link.is_symlink() or cfg_link.exists():
        cfg_link.unlink()
    cfg_link.symlink_to(os.path.relpath(dest, cfg_dir))

    # views/latest_by_run/<run_id>/
    run_dir = _VIEWS_ROOT / "latest_by_run" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    run_link = run_dir / link_name
    if run_link.is_symlink() or run_link.exists():
        run_link.unlink()
    run_link.symlink_to(os.path.relpath(dest, run_dir))


# ---------- Metrics ----------

def record_metric(
    run_id: str,
    metric_name: str,
    *,
    value: float | None = None,
    json_value: Any = None,
) -> None:
    """UPSERT a metric row. Either value (scalar) or json_value (complex), not both."""
    ensure_db()
    if value is None and json_value is None:
        raise ValueError("record_metric: must provide either value or json_value")
    js = json.dumps(json_value, sort_keys=True) if json_value is not None else None
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO metrics (run_id, metric_name, metric_value, metric_json) "
            "VALUES (?, ?, ?, ?)",
            (run_id, metric_name, value, js),
        )
        conn.commit()
    finally:
        conn.close()


def record_metrics(run_id: str, metrics: dict[str, Any]) -> None:
    """Bulk-record metrics. Scalars (int/float) → metric_value; everything else → metric_json."""
    ensure_db()
    rows = []
    for name, val in metrics.items():
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            rows.append((run_id, name, float(val), None))
        else:
            rows.append((run_id, name, None, json.dumps(val, sort_keys=True)))
    conn = _connect()
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO metrics (run_id, metric_name, metric_value, metric_json) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def record_bug_fix(run_id: str, bug_id: str) -> None:
    ensure_db()
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO run_bug_fixes (run_id, bug_id) VALUES (?, ?)",
            (run_id, bug_id),
        )
        conn.commit()
    finally:
        conn.close()


def record_bug_fixes(run_id: str, bug_ids: list[str]) -> None:
    for bid in bug_ids:
        record_bug_fix(run_id, bid)


# ---------- Lookup ----------

def find_latest_run(target_config_hash: str) -> str | None:
    """Return the run_id of the most recent COMPLETE run with this config_hash."""
    ensure_db()
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT run_id FROM runs WHERE config_hash = ? AND status = 'complete' "
            "ORDER BY date_iso DESC LIMIT 1",
            (target_config_hash,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def find_output_path(
    run_id: str, output_type: str,
    *, cohort: int | None = None, start_idx: int | None = None,
) -> Path | None:
    """Return absolute path to an output, or None if not registered."""
    ensure_db()
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT path FROM outputs WHERE run_id = ? AND output_type = ? "
            "AND (cohort IS ?) AND (start_idx IS ?)",
            (run_id, output_type, cohort, start_idx),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return _REGISTRY_ROOT / row[0]


def find_warm_start_cal(target_config: dict | None = None) -> Path | None:
    """Lookup the latest step2_cal output matching a target configuration.

    Used by the warm-start logic in both estimators.
    """
    if target_config is None:
        target_config = get_current_config()
    cfg_hash = config_hash(target_config)
    run_id = find_latest_run(cfg_hash)
    if run_id is None:
        return None
    return find_output_path(run_id, "step2_cal")


# ---------- Internal helpers ----------

def _hark_version() -> str:
    try:
        import HARK
        return getattr(HARK, "__version__", "unknown")
    except Exception:
        return "unknown"


# ---------- CLI for ad-hoc inspection ----------

def _cli_main(argv: list[str]) -> int:
    """Quick CLI: `python _registry.py [list|show <run_id>|metrics <name>]`."""
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    ensure_db()
    conn = _connect()
    try:
        if cmd == "list":
            cur = conn.execute(
                "SELECT run_id, config_hash, status, date_local, wall_total_sec FROM runs ORDER BY date_iso DESC LIMIT 20"
            )
            for run_id, ch, status, date_local, wall in cur:
                wall_str = f"{wall/60:.1f}min" if wall else "—"
                print(f"{date_local}  {ch}  {status:12}  {wall_str:>8}  {run_id}")
        elif cmd == "show" and len(argv) >= 3:
            run_id = argv[2]
            cur = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cur.fetchone()
            if row is None:
                print(f"No run {run_id}")
                return 1
            cols = [d[0] for d in cur.description]
            for col, val in zip(cols, row):
                print(f"  {col}: {val}")
            print("\nMetrics:")
            cur = conn.execute("SELECT metric_name, metric_value, metric_json FROM metrics WHERE run_id = ?", (run_id,))
            for name, value, js in cur:
                disp = value if value is not None else (js[:80] + "..." if js and len(js) > 80 else js)
                print(f"  {name}: {disp}")
        elif cmd == "metrics" and len(argv) >= 3:
            name = argv[2]
            cur = conn.execute(
                "SELECT runs.run_id, runs.date_local, metrics.metric_value FROM metrics "
                "JOIN runs USING (run_id) WHERE metric_name = ? ORDER BY runs.date_iso DESC LIMIT 20",
                (name,),
            )
            for run_id, date_local, value in cur:
                print(f"  {date_local}  {value}  {run_id}")
        else:
            print(f"Unknown command: {cmd}")
            return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main(sys.argv))
