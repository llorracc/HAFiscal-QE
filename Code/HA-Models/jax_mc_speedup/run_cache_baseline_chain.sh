#!/bin/bash
# Cache validation at Baseline: 2 runs that actually exercise the cache.
#   3'. Cache MISS — fresh, populates cache (~52 min)
#   4'. Cache HIT — replay (~seconds)
# Steps 1-2 from the earlier chain still provide the v0 vs all-on
# comparison (they ran in cache-off mode, so their numbers are valid).
set -e
cd /home/shared/github/llorracc/HAFiscal-Latest
unset VIRTUAL_ENV
LOG_DIR=Code/HA-Models/jax_mc_speedup/baseline_bench_logs
PY=.venv-linux-x86_64/bin/python
BENCH=Code/HA-Models/jax_mc_speedup/jax_mc_speedup_bench.py

echo "[cache_chain] starting at $(date)" >&2

# Run 3': cache MISS (populates cache)
echo "[cache_chain] 1/2: Baseline cache MISS (will populate cache)..." >&2
START=$(date +%s)
env PYTHONUNBUFFERED=1 HAFISCAL_USE_SOLUTION_CACHE=1 \
    "$PY" "$BENCH" --label baseline_cache_miss_v2 --parametrization Baseline --num-iter 4 \
    > "$LOG_DIR/3v2_baseline_cache_miss.log" 2>&1
echo "[cache_chain] 1/2 done in $(($(date +%s) - START))s" >&2

# Run 4': cache HIT (replay)
echo "[cache_chain] 2/2: Baseline cache HIT (replay)..." >&2
START=$(date +%s)
env PYTHONUNBUFFERED=1 HAFISCAL_USE_SOLUTION_CACHE=1 \
    "$PY" "$BENCH" --label baseline_cache_hit_v2 --parametrization Baseline --num-iter 4 \
    > "$LOG_DIR/4v2_baseline_cache_hit.log" 2>&1
echo "[cache_chain] 2/2 done in $(($(date +%s) - START))s" >&2

echo "[cache_chain] all done at $(date)" >&2
echo "[cache_chain] comparison:" >&2
"$PY" "$BENCH" --compare baseline_cache_miss_v2 baseline_cache_hit_v2 >&2
