#!/usr/bin/env python3
"""
Build the run manifest for a `./reproduce.sh --comp` invocation.

Spec: plans/20260425-1015h_reproduce-self-documenting-runs.md §4 (schema), §6 (provenance markers), §7 (storage layout).

Subcommands:
    init        Create the initial manifest JSON at run start (after pre-flight cleared).
    step        Append a step record (command, timing, exit code).
    record-output  Walk output directories; record sha256 and bytes of every file.
    finalize    Write end timestamp, total wall, exit code; mark manifest complete.

Reads pre-flight state from HAFISCAL_PREFLIGHT_* env vars set by reproduce.sh's
_preflight_for_comp() (see Phase 1).

The recipe / commit-msg / tag-msg generators are in Phase 3 (added as
additional subcommands to this same script).
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1"

REPO_ROOT = Path(__file__).resolve().parent.parent

# Input-data files (per plan §14.2 decision 4: broad boundary).
INPUT_DATA_FILES = [
    "Code/HA-Models/Target_AggMPCX_LiquWealth/LiquWealth_Distribution_a.xlsx",
    "Code/HA-Models/Target_AggMPCX_LiquWealth/LiquWealth_Distribution_b.xlsx",
    "Code/HA-Models/Target_AggMPCX_LiquWealth/Data_AggMPC_LotteryWin.xlsx",
]

# Calibration files (technically Step-2 outputs, but inputs to Step 5).
CALIBRATION_INPUT_FILES = [
    "Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt",
    "Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget_Splurge0.txt",
]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """UTC timestamp in ISO 8601 with seconds granularity."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path, chunk_size: int = 65536) -> str:
    """sha256 of file contents, computed in chunks to bound memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str, cwd: Path | None = None) -> str:
    """Run a git command and return stripped stdout. Returns '' on failure."""
    cwd = cwd or REPO_ROOT
    try:
        out = subprocess.check_output(
            ["git", *args], cwd=cwd, stderr=subprocess.DEVNULL
        )
        return out.decode("utf-8").strip()
    except subprocess.CalledProcessError:
        return ""


def _hark_state() -> dict:
    """Capture HARK version and (if installed from git) source SHA."""
    state = {
        "hark_version": None,
        "hark_install_path": None,
        "hark_git_commit": None,
    }
    try:
        import HARK  # noqa: I201
        state["hark_version"] = getattr(HARK, "__version__", None)
        state["hark_install_path"] = str(Path(HARK.__file__).resolve().parent)
        # If HARK is installed from a git checkout, record its SHA.
        hark_git = _git("rev-parse", "HEAD", cwd=Path(state["hark_install_path"]).parent)
        state["hark_git_commit"] = hark_git or None
    except ImportError:
        pass
    return state


def _hafiscal_env_vars() -> dict:
    """Snapshot every HAFISCAL_* env var (None if unset)."""
    keys = [
        "HAFISCAL_RUN_STEP_1",
        "HAFISCAL_RUN_STEP_2",
        "HAFISCAL_RUN_STEP_3",
        "HAFISCAL_RUN_STEP_4",
        "HAFISCAL_RUN_STEP_5",
        "HAFISCAL_MC_SHUFFLE",
        "HAFISCAL_INCOME_SHUFFLE",
        "HAFISCAL_SPLURGE_OLD",
        "HAFISCAL_SIM_METHOD",
    ]
    return {k: os.environ.get(k) for k in keys}


def _capture_pip_freeze(target_path: Path) -> tuple[str, str]:
    """
    Capture `uv pip freeze` to target_path; return (path, sha256).

    Falls back to plain `pip freeze` if `uv` isn't available.
    """
    cmd_candidates = [["uv", "pip", "freeze"], ["pip", "freeze"]]
    output = None
    used_cmd = None
    for cmd in cmd_candidates:
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
            used_cmd = " ".join(cmd)
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    if output is None:
        output = "# pip freeze unavailable: neither `uv pip freeze` nor `pip freeze` succeeded\n"
        used_cmd = "(none)"

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w") as f:
        f.write(f"# Captured via: {used_cmd}\n# At: {_now_iso()}\n")
        f.write(output)
    # Record path as repo-relative if inside repo, absolute otherwise.
    try:
        rel = str(target_path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        rel = str(target_path.resolve())
    return rel, _sha256_file(target_path)


def _file_hash_block(rel_paths: list[str]) -> dict[str, str | None]:
    """Hash each rel-path; return {rel_path: sha256_or_None_if_missing}."""
    out = {}
    for rel in rel_paths:
        p = REPO_ROOT / rel
        if p.exists() and p.is_file():
            out[rel] = _sha256_file(p)
        else:
            out[rel] = None
    return out


def _git_status_summary() -> str:
    """One-line summary of dirty status (for manifest when --accept-dirty)."""
    porcelain = _git("status", "--porcelain")
    if not porcelain:
        return ""
    lines = porcelain.split("\n")
    return f"{len(lines)} file(s) modified/added/deleted; first 5: " + "; ".join(
        lines[:5]
    )


def _parse_result_alltarget(path: Path) -> dict | None:
    """Parse the existing Result_AllTarget.txt format (Python repr of a dict)."""
    if not path.exists():
        return None
    try:
        contents = path.read_text().strip()
        # The existing format is a Python literal; ast.literal_eval is the safe parse.
        import ast
        return ast.literal_eval(contents)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------

def _load_manifest(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Manifest not found: {path}")
    with open(path) as f:
        return json.load(f)


def _save_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=False)
        f.write("\n")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> int:
    """Create the initial manifest JSON at run start."""
    manifest_path = Path(args.manifest)
    pip_freeze_path = manifest_path.with_name(manifest_path.stem + "_pip_freeze.txt")

    # Split on ';' (the separator used by reproduce.sh's _preflight_for_comp;
    # individual overrides may contain spaces internally, so whitespace-split is wrong).
    overrides_str = os.environ.get("HAFISCAL_PREFLIGHT_OVERRIDES", "")
    overrides = [o.strip() for o in overrides_str.split(";") if o.strip()]

    branch = os.environ.get("HAFISCAL_PREFLIGHT_BRANCH", "") or _git("rev-parse", "--abbrev-ref", "HEAD")
    head_sha = os.environ.get("HAFISCAL_PREFLIGHT_HEAD_SHA", "") or _git("rev-parse", "HEAD")
    is_dirty = os.environ.get("HAFISCAL_PREFLIGHT_DIRTY", "false") == "true"

    # Capture pip freeze.
    pip_rel, pip_sha = _capture_pip_freeze(pip_freeze_path)

    # HARK state.
    hark = _hark_state()

    # Argv: bash script can pass us its argv via --argv (space-separated, single string).
    argv_list = args.argv.split() if args.argv else []

    manifest = {
        "schema_version": SCHEMA_VERSION,

        "invocation": {
            "command_line": " ".join(argv_list) if argv_list else "",
            "argv": argv_list,
            "scope": args.scope,
            "modifiers": args.modifiers.split(",") if args.modifiers else [],
            "started_at_utc": _now_iso(),
            "ended_at_utc": None,
            "wall_clock_seconds": None,
            "exit_code": None,
            "user": getpass.getuser(),
            "hostname": socket.gethostname(),
            "platform": f"{platform.system().lower()}-{platform.machine()}",
            "platform_release": platform.release(),
            "hafiscal_env_vars_at_start": _hafiscal_env_vars(),
        },

        "code_state": {
            "branch": branch,
            "git_commit": head_sha,
            "git_dirty": is_dirty,
            "git_status_summary": _git_status_summary() if is_dirty else "",
            "git_unpushed_commits": [],  # filled if --accept-unpushed; left empty for now
            "preflight_status": "clean" if not overrides else "overridden",
            "overrides_used": overrides,

            "hark_version": hark["hark_version"],
            "hark_install_path": hark["hark_install_path"],
            "hark_git_commit": hark["hark_git_commit"],
            "python_version": platform.python_version(),
        },

        "environment_lock": {
            "pip_freeze_path": pip_rel,
            "pip_freeze_sha256": pip_sha,
            "uv_lockfile_sha256": _file_hash_block(["uv.lock"]).get("uv.lock"),
            "python_version_file": (REPO_ROOT / ".python-version").read_text().strip()
                if (REPO_ROOT / ".python-version").exists() else None,
        },

        "input_data_hashes": _file_hash_block(INPUT_DATA_FILES),

        "calibration_inputs": {
            "Result_AllTarget_path": "Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt",
            "Result_AllTarget_contents_sha256": _file_hash_block(
                ["Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt"]
            ).get("Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt"),
            "Result_AllTarget_parsed": _parse_result_alltarget(
                REPO_ROOT / "Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt"
            ),
            "extra_calibration_files": _file_hash_block(CALIBRATION_INPUT_FILES[1:]),
        },

        "steps_executed": [],

        "outputs": {},

        "log_file": args.log_file or None,
    }

    _save_manifest(manifest_path, manifest)
    print(f"[manifest] init → {manifest_path}")
    return 0


def cmd_step(args: argparse.Namespace) -> int:
    """Append a step record."""
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)

    started = args.started or _now_iso()
    ended = args.ended or _now_iso()
    try:
        wall = (datetime.fromisoformat(ended.replace("Z", "+00:00"))
                - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds()
    except Exception:
        wall = None

    manifest["steps_executed"].append({
        "step": args.name,
        "command": args.command,
        "started_at_utc": started,
        "ended_at_utc": ended,
        "wall_clock_seconds": wall,
        "exit_code": args.exit_code,
    })
    _save_manifest(manifest_path, manifest)
    print(f"[manifest] step '{args.name}' recorded (rc={args.exit_code}, wall={wall}s)")
    return 0


def cmd_record_output(args: argparse.Namespace) -> int:
    """Walk one or more directories, hash every regular file, record in manifest."""
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)
    outputs = manifest.setdefault("outputs", {})

    roots = args.root  # list (nargs='+')
    new_count = 0
    for root_str in roots:
        root = (REPO_ROOT / root_str).resolve()
        if not root.exists():
            print(f"[manifest] output root does not exist (skipping): {root_str}", file=sys.stderr)
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            # Skip dotfiles (e.g., __pycache__ / .DS_Store).
            if any(part.startswith(".") for part in p.relative_to(REPO_ROOT).parts):
                continue
            rel = str(p.relative_to(REPO_ROOT))
            try:
                stat = p.stat()
                outputs[rel] = {
                    "sha256": _sha256_file(p),
                    "bytes": stat.st_size,
                    "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
                new_count += 1
            except OSError as e:
                print(f"[manifest] cannot hash {rel}: {e}", file=sys.stderr)

    _save_manifest(manifest_path, manifest)
    print(f"[manifest] record-output: hashed {new_count} files under {len(roots)} root(s)")
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    """Write end timestamp, total wall, exit code."""
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)

    started = manifest["invocation"].get("started_at_utc")
    ended = _now_iso()
    try:
        wall = (datetime.fromisoformat(ended.replace("Z", "+00:00"))
                - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds()
    except Exception:
        wall = None

    manifest["invocation"]["ended_at_utc"] = ended
    manifest["invocation"]["wall_clock_seconds"] = wall
    manifest["invocation"]["exit_code"] = args.exit_code

    _save_manifest(manifest_path, manifest)
    print(f"[manifest] finalize → {manifest_path} (wall={wall}s, rc={args.exit_code})")
    return 0


# ---------------------------------------------------------------------------
# Phase 3: recipe / commit-msg / tag generators
# ---------------------------------------------------------------------------

def _existing_tag_names() -> set[str]:
    """Set of all tag names known locally + on origin."""
    local = set(_git("tag", "--list").splitlines())
    remote = set()
    out = _git("ls-remote", "--tags", "origin")
    if out:
        for line in out.splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2 and parts[1].startswith("refs/tags/"):
                # Strip 'refs/tags/' and any '^{}' deref suffix.
                name = parts[1][len("refs/tags/"):]
                if name.endswith("^{}"):
                    name = name[:-3]
                remote.add(name)
    return {t for t in (local | remote) if t}


def _generate_tag_name(scope: str, modifiers: list[str], run_date_iso: str) -> str:
    """
    Tag name pattern: reproduce-<YYYYMMDD>-comp-<scope>[-<modifier>][-N]

    Collision-resolution: append -2, -3, ... if the base name is already taken
    locally or on origin.
    """
    # Date in YYYYMMDD from the UTC run-start ISO timestamp.
    date_part = run_date_iso[:10].replace("-", "")
    parts = ["reproduce", date_part, "comp", scope]
    for m in modifiers:
        if m:
            parts.append(m)
    base = "-".join(parts)
    existing = _existing_tag_names()
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def _key_outputs(manifest: dict, max_n: int = 8) -> list[tuple[str, str]]:
    """Pick a few headline output files to mention in the commit msg."""
    outputs = manifest.get("outputs", {})
    # Prefer the canonical paper-table outputs first.
    priority_substrings = [
        "Tables/Baseline/Multiplier.tex",
        "Tables/Baseline/welfare6.tex",
        "Tables/Baseline/welfare6_parallel_summary.json",
    ]
    chosen = []
    seen = set()
    for sub in priority_substrings:
        for path, info in outputs.items():
            if sub in path and path not in seen:
                chosen.append((path, info["sha256"][:12]))
                seen.add(path)
    # Then fill with other Tables/Baseline/*.tex files.
    for path, info in outputs.items():
        if len(chosen) >= max_n:
            break
        if path in seen:
            continue
        if "Tables/Baseline/" in path and path.endswith(".tex"):
            chosen.append((path, info["sha256"][:12]))
            seen.add(path)
    return chosen


def cmd_emit_recipe(args: argparse.Namespace) -> int:
    """Generate the reproduce-recipe.sh script."""
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)
    out_path = manifest_path.with_name(manifest_path.stem + ".reproduce-recipe.sh")

    cs = manifest["code_state"]
    inv = manifest["invocation"]

    # Build the env-var export block for any HAFISCAL_RUN_STEP_* / shuffle vars
    # that were set at the original invocation.
    env_lines = []
    for k, v in (inv.get("hafiscal_env_vars_at_start") or {}).items():
        if v is not None:
            env_lines.append(f'export {k}={v!r}')
    env_block = "\n".join(env_lines) if env_lines else "# (no HAFISCAL_* env vars were set at the original invocation)"

    # Hash-verification block for input data files.
    hash_lines = []
    for path, sha in (manifest.get("input_data_hashes") or {}).items():
        if sha:
            hash_lines.append(f'    "{sha}:{path}"')
    hash_block = " \\\n".join(hash_lines) if hash_lines else "# (no input-data files recorded)"

    cmd_line = inv.get("command_line") or "(unknown)"

    script = f"""#!/usr/bin/env bash
# Auto-generated by reproduce/build_manifest.py emit-recipe.
# Reproduces the run captured in:
#   {manifest_path.name}
# Originally invoked as:
#   {cmd_line}
# At: {inv.get('started_at_utc')}
# By: {inv.get('user')}@{inv.get('hostname')} on {inv.get('platform')}
# Wall clock: {inv.get('wall_clock_seconds')} seconds.

set -euo pipefail

ANCHOR_COMMIT="{cs.get('git_commit', '')}"
ANCHOR_BRANCH="{cs.get('branch', '')}"
ANCHOR_HARK_VERSION="{cs.get('hark_version', '')}"

# 1. Verify worktree clean (refuse to replay onto a dirty tree).
if [[ -n "$(git status --porcelain)" ]]; then
    echo "Worktree dirty; refuse to replay (commit/stash first)." >&2
    exit 1
fi

# 2. Check out the recorded commit.
git fetch origin || true
git checkout "$ANCHOR_COMMIT"

# 3. Verify HARK version matches.
got_hark="$(python -c 'import HARK; print(HARK.__version__)' 2>/dev/null || true)"
if [[ "$got_hark" != "$ANCHOR_HARK_VERSION" ]]; then
    echo "HARK version mismatch: expected $ANCHOR_HARK_VERSION, got '$got_hark'" >&2
    echo "Re-sync env: bash reproduce/uv_sync_repair.sh" >&2
    exit 1
fi

# 4. Verify input-data hashes match.
for entry in \\
{hash_block}; do
    expected="${{entry%%:*}}"
    path="${{entry#*:}}"
    got="$(shasum -a 256 "$path" | cut -d' ' -f1)"
    if [[ "$expected" != "$got" ]]; then
        echo "Input-data hash mismatch on $path" >&2
        echo "  expected: $expected" >&2
        echo "  got:      $got" >&2
        exit 1
    fi
done

# 5. Re-establish the original invocation's env vars.
{env_block}

# 6. Replay the original command.
exec {cmd_line}
"""
    out_path.write_text(script)
    out_path.chmod(0o755)
    print(f"[manifest] emit-recipe → {out_path}")
    return 0


def cmd_emit_commit_msg(args: argparse.Namespace) -> int:
    """Generate the .commit-msg.txt file (passed to `git commit -F`)."""
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)
    out_path = manifest_path.with_name(manifest_path.stem + ".commit-msg.txt")

    cs = manifest["code_state"]
    inv = manifest["invocation"]
    cal = manifest.get("calibration_inputs", {}) or {}
    cal_parsed = cal.get("Result_AllTarget_parsed") or {}

    wall = inv.get("wall_clock_seconds") or 0
    wall_min = int(wall // 60)
    wall_sec = int(wall % 60)

    # Per-step durations.
    step_lines = []
    for s in manifest.get("steps_executed", []):
        s_wall = s.get("wall_clock_seconds") or 0
        s_wall_min = int(s_wall // 60)
        step_lines.append(
            f"  Step {s.get('step', '?')}: {s_wall_min}min  (rc={s.get('exit_code')})"
            f" — {s.get('command', '')}"
        )
    step_block = "\n".join(step_lines) if step_lines else "  (no steps recorded)"

    # Key output hashes (truncated to 12 hex chars for readability).
    key_outs = _key_outputs(manifest)
    out_lines = [f"  {path}  sha256:{sha}" for path, sha in key_outs]
    out_block = "\n".join(out_lines) if out_lines else "  (no outputs recorded)"

    # Calibration line.
    cal_line = (
        f"Calibration (from {cal.get('Result_AllTarget_path', '?')}, "
        f"sha256 {cal.get('Result_AllTarget_contents_sha256', 'unknown')[:12]}): "
        f"ς={cal_parsed.get('splurge', '?')}, "
        f"β={cal_parsed.get('beta', '?')}, "
        f"∇={cal_parsed.get('nabla', '?')}"
        if cal_parsed else
        "Calibration: (Result_AllTarget.txt not present or unparseable)"
    )

    tag_name = _generate_tag_name(
        scope=inv.get("scope", "unknown"),
        modifiers=inv.get("modifiers", []) or [],
        run_date_iso=inv.get("started_at_utc", _now_iso()),
    )

    body = f"""reproduce: {inv.get('command_line', '?')} — {inv.get('started_at_utc', '?')[:10]} UTC

Run captured in {manifest_path.name} on commit {cs.get('git_commit', '?')[:12]}
({cs.get('branch', '?')}; HARK {cs.get('hark_version', '?')};
preflight={cs.get('preflight_status', '?')}{', overrides: ' + ', '.join(cs.get('overrides_used', [])) if cs.get('overrides_used') else ''}).

Wall clock: {wall_min}min {wall_sec}s.
{step_block}

{cal_line}

Key outputs (sha256 truncated to 12 hex):
{out_block}
... (full list with hashes in {manifest_path.name})

To replay exactly:
    bash {manifest_path.parent.name}/{manifest_path.stem}.reproduce-recipe.sh

Tagged as: {tag_name}
Full manifest: {manifest_path.relative_to(REPO_ROOT) if str(manifest_path).startswith(str(REPO_ROOT)) else manifest_path}
"""
    out_path.write_text(body)
    print(f"[manifest] emit-commit-msg → {out_path}")
    print(f"[manifest] tag-name to use: {tag_name}")
    return 0


def cmd_emit_tag_msg(args: argparse.Namespace) -> int:
    """Generate the .tag-msg.txt file (passed to `git tag -a -F`)."""
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)
    out_path = manifest_path.with_name(manifest_path.stem + ".tag-msg.txt")

    cs = manifest["code_state"]
    inv = manifest["invocation"]

    body = f"""Reproduction run: {inv.get('command_line', '?')}

Run captured at: {inv.get('started_at_utc', '?')}
On commit: {cs.get('git_commit', '?')}
Branch: {cs.get('branch', '?')}
HARK: {cs.get('hark_version', '?')}
Wall clock: {inv.get('wall_clock_seconds')} seconds.
Preflight: {cs.get('preflight_status', '?')}{' (overrides: ' + ', '.join(cs.get('overrides_used', [])) + ')' if cs.get('overrides_used') else ''}

Manifest: {manifest_path.name}
Recipe:   {manifest_path.stem}.reproduce-recipe.sh

To replay: bash {manifest_path.parent.name}/{manifest_path.stem}.reproduce-recipe.sh
"""
    out_path.write_text(body)
    print(f"[manifest] emit-tag-msg → {out_path}")
    return 0


def cmd_tag_name(args: argparse.Namespace) -> int:
    """Print the tag name that emit-commit-msg / emit-tag-msg would use."""
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)
    inv = manifest["invocation"]
    name = _generate_tag_name(
        scope=inv.get("scope", "unknown"),
        modifiers=inv.get("modifiers", []) or [],
        run_date_iso=inv.get("started_at_utc", _now_iso()),
    )
    print(name)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_manifest", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize manifest at run start.")
    p_init.add_argument("--manifest", required=True, help="Path to manifest JSON to create.")
    p_init.add_argument("--scope", required=True, help="--comp scope (nano/micro/mini/min/full/max).")
    p_init.add_argument("--modifiers", default="", help="Comma-separated modifiers (mc-only,tm-only,auto-commit,...).")
    p_init.add_argument("--log-file", default=None, help="Path to the run's reproduce.sh log file.")
    p_init.add_argument("--argv", default="", help="Space-separated argv of the original ./reproduce.sh invocation.")
    p_init.set_defaults(func=cmd_init)

    p_step = sub.add_parser("step", help="Record a step's execution.")
    p_step.add_argument("--manifest", required=True)
    p_step.add_argument("--name", required=True, help="Short step identifier (e.g., '5a', '5b').")
    p_step.add_argument("--command", required=True, help="The command string that was run.")
    p_step.add_argument("--started", default=None, help="ISO 8601 UTC start time (default: now).")
    p_step.add_argument("--ended", default=None, help="ISO 8601 UTC end time (default: now).")
    p_step.add_argument("--exit-code", type=int, required=True)
    p_step.set_defaults(func=cmd_step)

    p_rec = sub.add_parser("record-output", help="Walk dirs and hash all output files.")
    p_rec.add_argument("--manifest", required=True)
    p_rec.add_argument("--root", required=True, nargs="+",
                       help="One or more output root directories (relative to repo root).")
    p_rec.set_defaults(func=cmd_record_output)

    p_fin = sub.add_parser("finalize", help="Write end timestamp + wall + exit code.")
    p_fin.add_argument("--manifest", required=True)
    p_fin.add_argument("--exit-code", type=int, required=True)
    p_fin.set_defaults(func=cmd_finalize)

    # Phase 3: recipe / commit-msg / tag generators.
    p_rec = sub.add_parser("emit-recipe", help="Generate the .reproduce-recipe.sh script.")
    p_rec.add_argument("--manifest", required=True)
    p_rec.set_defaults(func=cmd_emit_recipe)

    p_cm = sub.add_parser("emit-commit-msg", help="Generate the .commit-msg.txt scratch file.")
    p_cm.add_argument("--manifest", required=True)
    p_cm.set_defaults(func=cmd_emit_commit_msg)

    p_tm = sub.add_parser("emit-tag-msg", help="Generate the .tag-msg.txt scratch file.")
    p_tm.add_argument("--manifest", required=True)
    p_tm.set_defaults(func=cmd_emit_tag_msg)

    p_tn = sub.add_parser("tag-name", help="Print the tag name that would be used (for bash to capture).")
    p_tn.add_argument("--manifest", required=True)
    p_tn.set_defaults(func=cmd_tag_name)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
