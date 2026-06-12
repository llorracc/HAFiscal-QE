#!/usr/bin/env bash
# Patches the venv-installed `jax_plugins/xla_cuda12/__init__.py` to
# preload nvjitlink BEFORE cusparse, fixing the
#
#   RuntimeError: Unable to load cuSPARSE. Is it installed?
#
# error caused by JAX-bundled cuSPARSE (CUDA 12.9 nvJitLink ABI) failing
# to resolve symbol __nvJitLinkGetErrorLogSize_12_9 against the older
# system libnvJitLink (CUDA 12.6).
#
# Idempotent: detects whether the patch is already in place. uv sync will
# clobber it; re-run this script. The run_with_gpu.sh wrapper auto-runs
# it before exec.
#
# Usage:
#   bash Code/HA-Models/jax_mc_speedup/apply_jax_gpu_patch.sh           # verbose
#   bash Code/HA-Models/jax_mc_speedup/apply_jax_gpu_patch.sh --quiet
set -euo pipefail

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1
log() { [ "$QUIET" = "1" ] || echo "$@"; }

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv-linux-x86_64"
PLUGIN_INIT="$VENV_DIR/lib/python3.11/site-packages/jax_plugins/xla_cuda12/__init__.py"

if [ ! -f "$PLUGIN_INIT" ]; then
    log "[jax-gpu-patch] $PLUGIN_INIT not found; nothing to patch (no JAX-CUDA in venv)"
    exit 0
fi

# Marker we add as a comment so we can detect the patch is already applied
MARKER='# HAFISCAL_PATCH: preload nvjitlink before cusparse (see apply_jax_gpu_patch.sh)'

if grep -q "HAFISCAL_PATCH: preload nvjitlink" "$PLUGIN_INIT"; then
    log "[jax-gpu-patch] already applied to $PLUGIN_INIT"
    exit 0
fi

# Insert `_load("nvjitlink", ["libnvJitLink.so.12"])` right before the
# existing `_load("cusparse", ["libcusparse.so.12"])` line. We also pin
# the line we're matching so a future JAX upgrade that changes context
# fails loudly instead of silently mis-patching.
PYTHON="$VENV_DIR/bin/python"
[ -x "$PYTHON" ] || PYTHON=python3

"$PYTHON" - "$PLUGIN_INIT" "$MARKER" <<'PYEOF'
import sys
path, marker = sys.argv[1], sys.argv[2]
with open(path) as f:
    src = f.read()
needle = '  _load("cusparse", ["libcusparse.so.12"])'
if needle not in src:
    raise SystemExit(
        f"[jax-gpu-patch] FATAL: needle not found in {path!r}. "
        "JAX layout may have changed; this patch needs revisiting.\n"
        "Searched for:\n  " + needle)
patch_block = (
    "  " + marker + "\n"
    + '  _load("nvjitlink", ["libnvJitLink.so.12"])\n'
)
new_src = src.replace(needle, patch_block + needle)
with open(path, "w") as f:
    f.write(new_src)
print(f"[jax-gpu-patch] applied to {path}")
PYEOF

log "[jax-gpu-patch] patched $PLUGIN_INIT"
