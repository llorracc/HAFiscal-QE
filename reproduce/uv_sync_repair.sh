#!/usr/bin/env bash
# Repair a broken or inconsistent uv environment (wrong Python, stale numpy, lockfile drift).
# Run from repo root: bash reproduce/uv_sync_repair.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.python-version" ]]; then
  PY="$(tr -d '[:space:]' < "$ROOT/.python-version")"
else
  PY="3.11"
fi

UV_PE="$(bash "$ROOT/reproduce/uv_platform_venv_path.sh")"

echo "==> HAFiscal uv repair (Python ${PY}, env ${UV_PE})"
echo "    Repo: $ROOT"
echo ""

# Active env vars often make uv target the wrong interpreter or wrong venv path.
unset VIRTUAL_ENV
export UV_PROJECT_ENVIRONMENT="$UV_PE"

export UV_LINK_MODE="${UV_LINK_MODE:-copy}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not on PATH. Install: https://docs.astral.sh/uv/"
  exit 1
fi

echo "==> uv python install ${PY}"
uv python install "${PY}"

echo "==> uv lock (refresh lockfile from pyproject.toml)"
uv lock

# Remove a possibly broken or partially deleted venv (macOS sometimes leaves non-empty trees;
# plain rm -rf can fail with "Directory not empty" if files are busy or permissions are odd).
remove_tree() {
  local target="$1"
  [[ -e "$target" ]] || return 0
  echo "==> Removing $target (best-effort; may take a few seconds)..."
  chmod -R u+w "$target" 2>/dev/null || true
  rm -rf "$target" 2>/dev/null || true
  if [[ -e "$target" ]]; then
    find "$target" -depth -delete 2>/dev/null || true
  fi
  if [[ -e "$target" ]]; then
    python3 -c "import shutil, sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" "$target" 2>/dev/null || true
  fi
  if [[ -e "$target" ]]; then
    echo ""
    echo "ERROR: Could not fully remove: $target"
    echo "Close Cursor/VSCode terminals using this venv, deactivate conda, then run manually:"
    echo "  chmod -R u+w '$target' && rm -rf '$target'"
    echo "If it still fails, quit apps locking the path and retry, or reboot and delete again."
    exit 1
  fi
}

# Drop stale .venv symlink or broken flat .venv; rebuild platform venv from scratch
remove_tree "$ROOT/$UV_PE"
if [[ -L "$ROOT/.venv" ]] || [[ -d "$ROOT/.venv" ]]; then
  remove_tree "$ROOT/.venv"
fi

echo "==> uv sync --all-groups --python ${PY}"
uv sync --all-groups --python "${PY}"

(
  cd "$ROOT"
  ln -sfn "$UV_PE" .venv
  echo "==> Linked .venv -> $UV_PE"
)

echo ""
echo "==> Verify"
"$ROOT/$UV_PE/bin/python" -V
"$ROOT/$UV_PE/bin/python" -c "import numpy, numba; print('numpy', numpy.__version__, 'numba', numba.__version__)"
"$ROOT/$UV_PE/bin/python" -m pip --version
echo ""
echo "Done. Default path .venv points at $UV_PE; plain 'uv sync' matches this layout."
