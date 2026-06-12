#!/bin/bash
# Phase 5 (overnight 2026-05-21): retry the parallel+2B Baseline bench after
# the policies chain finishes, plus head-to-head verify_welfare_replay if
# the bench succeeds.
#
# Waits for the all-policies chain to finish first.
set -uo pipefail

cd /home/shared/github/llorracc/HAFiscal-Latest || exit 1
unset VIRTUAL_ENV

PY=.venv-linux-x86_64/bin/python
LOG_DIR=Code/HA-Models/jax_mc_speedup/overnight_phase5_parallel_logs
mkdir -p "$LOG_DIR"

echo "[$(date '+%F %T')] phase 5 parallel+2B retry START" | tee -a "$LOG_DIR/master.log"

POLICIES_LOG="Code/HA-Models/jax_mc_speedup/overnight_2B_policies_logs/master.log"
WAITED=0
echo "[$(date '+%F %T')] waiting for all-policies chain to finish..." | tee -a "$LOG_DIR/master.log"
while [ "$WAITED" -lt 21600 ]; do  # 6 hours max
    if grep -q "overnight 2B policies DONE" "$POLICIES_LOG" 2>/dev/null; then
        echo "[$(date '+%F %T')] policies chain done; proceeding" | tee -a "$LOG_DIR/master.log"
        break
    fi
    sleep 60
    WAITED=$((WAITED + 60))
done

run_step() {
    local label="$1"; shift
    echo "==========================================================" | tee -a "$LOG_DIR/master.log"
    echo "[$(date '+%F %T')] STEP: $label" | tee -a "$LOG_DIR/master.log"
    echo "==========================================================" | tee -a "$LOG_DIR/master.log"
    local start_ts=$(date +%s)
    "$@" > "$LOG_DIR/${label}.log" 2>&1
    local rc=$?
    local elapsed=$(($(date +%s) - start_ts))
    if [ $rc -ne 0 ]; then
        echo "[FAIL rc=$rc t=${elapsed}s] $label (see $LOG_DIR/${label}.log)" | tee -a "$LOG_DIR/master.log"
    else
        echo "[OK t=${elapsed}s] $label" | tee -a "$LOG_DIR/master.log"
        grep -E "wall_jax_total:|HARK welfare cell:|JAX-replay-v2 welfare cell:|Relative diff:|Total wall:" \
            "$LOG_DIR/${label}.log" 2>/dev/null | tee -a "$LOG_DIR/master.log"
    fi
}

# Step 1: retry parallel+2B bench on CPU
run_step "Baseline_2B_parallel21_cpu_retry" \
    env JAX_PLATFORMS=cpu HAFISCAL_PARALLEL_SOLVE=21 HAFISCAL_USE_JAX_2B=1 \
        HAFISCAL_USE_SOLUTION_CACHE=1 PYTHONUNBUFFERED=1 \
    "$PY" Code/HA-Models/jax_mc_speedup/jax_mc_speedup_bench.py \
    --label Baseline_2B_parallel21_cpu_retry --parametrization Baseline --num-iter 4

# Step 2: head-to-head verify_welfare_replay with parallel+2B
# Only if step 1 produced a wall_jax_total
if grep -q "wall_jax_total: [0-9]" "$LOG_DIR/Baseline_2B_parallel21_cpu_retry.log" 2>/dev/null; then
    # NOTE: cache OFF here on purpose. With cache ON the AD result for
    # this exact param combo would HIT the entry already populated by
    # serial 2B (since HAFISCAL_PARALLEL_SOLVE isn't in the cache key —
    # it doesn't affect numerical output). That HIT would skip the actual
    # parallel+2B compute, making the head-to-head wall meaningless.
    run_step "verify_Baseline_parallel21_2B_recessionCheck" \
        env JAX_PLATFORMS=cpu HAFISCAL_PARALLEL_SOLVE=21 HAFISCAL_USE_JAX_2B=1 \
            HAFISCAL_USE_SOLUTION_CACHE=0 PYTHONUNBUFFERED=1 \
        "$PY" Code/HA-Models/FromPandemicCode/verify_welfare_replay.py \
        --parametrization Baseline --policy recessionCheck
else
    echo "[$(date '+%F %T')] step 1 didn't produce wall_jax_total; skipping verify_replay" | tee -a "$LOG_DIR/master.log"
fi

echo "[$(date '+%F %T')] phase 5 parallel+2B retry DONE" | tee -a "$LOG_DIR/master.log"
