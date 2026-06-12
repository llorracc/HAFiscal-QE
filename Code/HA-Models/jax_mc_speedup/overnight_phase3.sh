#!/bin/bash
# Phase 3: validate JAX-AD cache MISS+HIT at Baseline scale with the new
# SHA-fix code path. Phase 1 + phase 2 used HS_Only + Reduced_Run; phase 3
# fills in the Baseline numbers.
#
# Runs AFTER phase 2 completes (watches phase2 master.log for DONE line).
set -uo pipefail
cd /home/shared/github/llorracc/HAFiscal-Latest || exit 1
unset VIRTUAL_ENV

PY=.venv-linux-x86_64/bin/python
LOG_DIR=Code/HA-Models/jax_mc_speedup/overnight_phase3_logs
mkdir -p "$LOG_DIR"

echo "[$(date '+%F %T')] phase 3 START" | tee -a "$LOG_DIR/master.log"

PHASE2_LOG="Code/HA-Models/jax_mc_speedup/overnight_phase2_logs/master.log"
WAITED=0
echo "[$(date '+%F %T')] waiting for phase 2 DONE line in $PHASE2_LOG..." \
    | tee -a "$LOG_DIR/master.log"
while [ "$WAITED" -lt 5400 ]; do
    if grep -q "phase 2 DONE" "$PHASE2_LOG" 2>/dev/null; then
        echo "[$(date '+%F %T')] phase 2 done; proceeding" \
            | tee -a "$LOG_DIR/master.log"
        break
    fi
    sleep 30
    WAITED=$((WAITED + 30))
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
        echo "[FAIL rc=$rc t=${elapsed}s] $label (see $LOG_DIR/${label}.log)" \
            | tee -a "$LOG_DIR/master.log"
    else
        echo "[OK t=${elapsed}s] $label" \
            | tee -a "$LOG_DIR/master.log"
    fi
}

# Wipe any Baseline cache so step 1 is a true MISS. (Old pre-SHA-fix entries
# are already unreachable but still on disk; removing the dir cleans them up.)
rm -rf Code/HA-Models/solution_cache/Baseline/recession 2>/dev/null

BENCH="Code/HA-Models/jax_mc_speedup/jax_mc_speedup_bench.py"

# Step 1: Baseline cache MISS (writes fresh entry with new SHA-fix keying)
run_step "Baseline_cache_miss_v0" \
    env PYTHONUNBUFFERED=1 HAFISCAL_USE_SOLUTION_CACHE=1 \
    "$PY" "$BENCH" --label Baseline_cache_miss_v0 --parametrization Baseline --num-iter 4

# Step 2: Baseline cache HIT — measures the JAX-AD load wall at Baseline
run_step "Baseline_cache_hit_v0" \
    env PYTHONUNBUFFERED=1 HAFISCAL_USE_SOLUTION_CACHE=1 \
    "$PY" "$BENCH" --label Baseline_cache_hit_v0 --parametrization Baseline --num-iter 4

# Step 3-5: 2B at Baseline, more cohorts for a fuller speedup curve
run_step "2B_Baseline_cohort5" \
    env PYTHONUNBUFFERED=1 "$PY" Code/HA-Models/jax_mc_speedup/test_2B_scaled.py \
    --parametrization Baseline --cohort 5

run_step "2B_Baseline_cohort15" \
    env PYTHONUNBUFFERED=1 "$PY" Code/HA-Models/jax_mc_speedup/test_2B_scaled.py \
    --parametrization Baseline --cohort 15

echo "[$(date '+%F %T')] phase 3 DONE" | tee -a "$LOG_DIR/master.log"
