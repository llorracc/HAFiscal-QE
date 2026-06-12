#!/usr/bin/env bash
# Wrapper that sets LD_PRELOAD to the venv-bundled libnvJitLink.so.12,
# then execs its arguments. This works around a JAX-CUDA12 plugin issue
# where cuSPARSE (built against CUDA 12.9 nvJitLink ABI) fails to load
# because the OS loader picks up the older system libnvJitLink (CUDA
# 12.6) first.
#
# Without this wrapper, JAX falls back to CPU silently:
#   RuntimeError: Unable to load cuSPARSE. Is it installed?
#   ... Falling back to cpu.
#
# Usage:
#   bash Code/HA-Models/jax_mc_speedup/run_with_gpu.sh python ...
#
# Or as a substitute for plain python:
#   bash Code/HA-Models/jax_mc_speedup/run_with_gpu.sh \
#       .venv-linux-x86_64/bin/python Code/HA-Models/jax_mc_speedup/jax_mc_speedup_bench.py \
#       --label Baseline_GPU --parametrization Baseline --num-iter 4
#
# Also re-applies the venv JAX plugin patch (see apply_jax_gpu_patch.sh)
# if it's been clobbered by a `uv sync` since last use; this makes
# subsequent `python ...` invocations without the wrapper work too.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv-linux-x86_64"
NVJL_LIB="$VENV_DIR/lib/python3.11/site-packages/nvidia/nvjitlink/lib/libnvJitLink.so.12"

if [ ! -f "$NVJL_LIB" ]; then
    echo "[run_with_gpu] ERROR: $NVJL_LIB not found." >&2
    echo "[run_with_gpu] Is the venv synced? Run: uv sync --all-groups" >&2
    exit 1
fi

# Re-apply the in-venv JAX patch if it's been clobbered by a uv sync
PATCH_SH="$REPO_ROOT/Code/HA-Models/jax_mc_speedup/apply_jax_gpu_patch.sh"
if [ -f "$PATCH_SH" ]; then
    bash "$PATCH_SH" --quiet || true
fi

export LD_PRELOAD="$NVJL_LIB${LD_PRELOAD:+:$LD_PRELOAD}"
exec "$@"
