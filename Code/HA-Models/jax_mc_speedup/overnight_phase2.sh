#!/bin/bash
# Phase 2 overnight runs (kicks off after phase 1 — overnight_1a2a_sweep.sh — completes):
#   - 2B parity + timing at Reduced_Run + Baseline
#   - verify_welfare_replay at HS_Only with cache (validates HARK-AD cache delivers paper-grade)
#
# Designed to be launched as a chained background task while the user is asleep.
set -uo pipefail

cd /home/shared/github/llorracc/HAFiscal-Latest || exit 1
unset VIRTUAL_ENV

PY=.venv-linux-x86_64/bin/python
LOG_DIR=Code/HA-Models/jax_mc_speedup/overnight_phase2_logs
mkdir -p "$LOG_DIR"

echo "[$(date '+%F %T')] phase 2 START" | tee -a "$LOG_DIR/master.log"

# Wait until the phase 1 sweep finishes. We watch for the "DONE" line in its
# master.log, polling every 30s, capped at 90 min in case of stall.
PHASE1_LOG="Code/HA-Models/jax_mc_speedup/overnight_1a2a_logs/master.log"
echo "[$(date '+%F %T')] waiting for phase 1 to write DONE line in $PHASE1_LOG..." \
    | tee -a "$LOG_DIR/master.log"
WAITED=0
while [ "$WAITED" -lt 5400 ]; do
    if grep -q "DONE overnight 1A-2A sweep" "$PHASE1_LOG" 2>/dev/null; then
        echo "[$(date '+%F %T')] phase 1 done; proceeding" \
            | tee -a "$LOG_DIR/master.log"
        break
    fi
    sleep 30
    WAITED=$((WAITED + 30))
done
if [ "$WAITED" -ge 5400 ]; then
    echo "[$(date '+%F %T')] WARN: waited 90min, phase 1 not done. Proceeding anyway." \
        | tee -a "$LOG_DIR/master.log"
fi

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

# 2B parity at Reduced_Run, cohort 0
run_step "2B_Reduced_Run_cohort0" \
    env PYTHONUNBUFFERED=1 "$PY" Code/HA-Models/jax_mc_speedup/test_2B_scaled.py \
    --parametrization Reduced_Run --cohort 0

# 2B parity at Reduced_Run, cohort 1 (different beta — different convergence iter count)
run_step "2B_Reduced_Run_cohort1" \
    env PYTHONUNBUFFERED=1 "$PY" Code/HA-Models/jax_mc_speedup/test_2B_scaled.py \
    --parametrization Reduced_Run --cohort 1

# 2B parity at Baseline, cohort 0 (representative of small-beta cohort)
run_step "2B_Baseline_cohort0" \
    env PYTHONUNBUFFERED=1 "$PY" Code/HA-Models/jax_mc_speedup/test_2B_scaled.py \
    --parametrization Baseline --cohort 0

# 2B parity at Baseline, cohort 10 (mid-range)
run_step "2B_Baseline_cohort10" \
    env PYTHONUNBUFFERED=1 "$PY" Code/HA-Models/jax_mc_speedup/test_2B_scaled.py \
    --parametrization Baseline --cohort 10

# 2B parity at Baseline, cohort 20 (highest beta — most iters)
run_step "2B_Baseline_cohort20" \
    env PYTHONUNBUFFERED=1 "$PY" Code/HA-Models/jax_mc_speedup/test_2B_scaled.py \
    --parametrization Baseline --cohort 20

# verify_welfare_replay at HS_Only WITH cache on — validates that the
# HARK-AD cache wrapper delivers welfare matching the no-cache path.
run_step "verify_welfare_replay_HS_Only_cached" \
    env HAFISCAL_USE_SOLUTION_CACHE=1 PYTHONUNBUFFERED=1 \
    "$PY" Code/HA-Models/FromPandemicCode/verify_welfare_replay.py \
    --parametrization HS_Only --policy recessionCheck

echo "[$(date '+%F %T')] phase 2 DONE" | tee -a "$LOG_DIR/master.log"
