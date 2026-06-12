#!/bin/bash
# Sequential Baseline-scale benchmarks:
#   1. v0 baseline (no flags, cache OFF)
#   2. all-on (1A-2A flags, cache OFF)
#   3. cache MISS (cache ON, fresh)
#   4. cache HIT (cache ON, replay)
#
# Uses Baseline DEFAULT (10k agents) for tractable run time (~10 min each
# vs ~30 min at Baseline 5x). Validates the 1A-2A speedup projection and
# the cache-hit speedup claim.

set -e
cd /home/shared/github/llorracc/HAFiscal-Latest
unset VIRTUAL_ENV
LOG_DIR=Code/HA-Models/jax_mc_speedup/baseline_bench_logs
mkdir -p "$LOG_DIR"
PY=.venv-linux-x86_64/bin/python
BENCH=Code/HA-Models/jax_mc_speedup/jax_mc_speedup_bench.py

echo "[chain] starting at $(date)" >&2

# Wipe any pre-existing Baseline cache so run #3 is a true MISS
rm -rf Code/HA-Models/solution_cache/Baseline 2>/dev/null

# Run 1: baseline (no flags, cache off)
echo "[chain] 1/4: Baseline v0 (cache OFF)..." >&2
START=$(date +%s)
env PYTHONUNBUFFERED=1 \
    "$PY" "$BENCH" --label baseline_v0 --parametrization Baseline --num-iter 4 \
    > "$LOG_DIR/1_baseline_v0.log" 2>&1
echo "[chain] 1/4 done in $(($(date +%s) - START))s" >&2

# Run 2: all flags on (cache off)
echo "[chain] 2/4: Baseline all-on (cache OFF)..." >&2
START=$(date +%s)
env PYTHONUNBUFFERED=1 \
    HAFISCAL_JAX_MC_USE_2D_LIFT=1 \
    HAFISCAL_JAX_MC_VMAP_SEEDS=1 \
    HAFISCAL_JAX_MC_BATCH_TABLES=1 \
    HAFISCAL_JAX_MC_LAZY_PANEL=1 \
    HAFISCAL_JAX_MC_VMAP_COHORTS=1 \
    "$PY" "$BENCH" --label baseline_all_on --parametrization Baseline --num-iter 4 \
    > "$LOG_DIR/2_baseline_all_on.log" 2>&1
echo "[chain] 2/4 done in $(($(date +%s) - START))s" >&2

# Run 3: cache MISS (cache on, fresh)
echo "[chain] 3/4: Baseline cache MISS (cache ON, no prior entry)..." >&2
START=$(date +%s)
env PYTHONUNBUFFERED=1 HAFISCAL_USE_SOLUTION_CACHE=1 \
    "$PY" "$BENCH" --label baseline_cache_miss --parametrization Baseline --num-iter 4 \
    > "$LOG_DIR/3_baseline_cache_miss.log" 2>&1
echo "[chain] 3/4 done in $(($(date +%s) - START))s" >&2

# Run 4: cache HIT (cache on, prior entry exists)
echo "[chain] 4/4: Baseline cache HIT (cache ON, replay)..." >&2
START=$(date +%s)
env PYTHONUNBUFFERED=1 HAFISCAL_USE_SOLUTION_CACHE=1 \
    "$PY" "$BENCH" --label baseline_cache_hit --parametrization Baseline --num-iter 4 \
    > "$LOG_DIR/4_baseline_cache_hit.log" 2>&1
echo "[chain] 4/4 done in $(($(date +%s) - START))s" >&2

echo "[chain] all done at $(date)" >&2
echo "[chain] comparison:" >&2
"$PY" "$BENCH" --compare baseline_v0 baseline_all_on >&2
"$PY" "$BENCH" --compare baseline_cache_miss baseline_cache_hit >&2
