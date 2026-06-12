#!/bin/bash
# Overnight 2B-at-Baseline coverage for the 3 policy scenarios not yet
# validated (recessionCheck was done earlier — -0.120%).
#
# Runs AFTER the currently-running parallel+2B bench finishes (waits for
# /tmp/bench_2B_parallel_cpu.log to show "wall_jax_total:" or fail).
#
# Each step is self-contained — a WSL2 clock-skew interruption doesn't
# cascade. Logs land in overnight_2B_policies_logs/.
set -uo pipefail

cd /home/shared/github/llorracc/HAFiscal-Latest || exit 1
unset VIRTUAL_ENV

PY=.venv-linux-x86_64/bin/python
LOG_DIR=Code/HA-Models/jax_mc_speedup/overnight_2B_policies_logs
mkdir -p "$LOG_DIR"

echo "[$(date '+%F %T')] overnight 2B policies START" | tee -a "$LOG_DIR/master.log"

# Wait for phase 0 (the parallel+2B bench currently running) to complete,
# or timeout after 90 min so we don't block the rest of the chain.
WAITED=0
echo "[$(date '+%F %T')] waiting for phase 0 (parallel+2B bench) to finish..." | tee -a "$LOG_DIR/master.log"
while [ "$WAITED" -lt 5400 ]; do
    if grep -qE "wall_jax_total:|Traceback" /tmp/bench_2B_parallel_cpu.log 2>/dev/null; then
        echo "[$(date '+%F %T')] phase 0 finished" | tee -a "$LOG_DIR/master.log"
        cp /tmp/bench_2B_parallel_cpu.log "$LOG_DIR/phase0_parallel21_2B_bench.log" 2>/dev/null || true
        # Kill any zombie workers
        pkill -9 -f "jax_mc_speedup_bench" 2>/dev/null || true
        pkill -9 -f "_solve_agent_worker" 2>/dev/null || true
        sleep 5
        break
    fi
    sleep 30
    WAITED=$((WAITED + 30))
done
if [ "$WAITED" -ge 5400 ]; then
    echo "[$(date '+%F %T')] WARN: phase 0 not done after 90 min; killing and proceeding" | tee -a "$LOG_DIR/master.log"
    pkill -9 -f "jax_mc_speedup_bench" 2>/dev/null || true
    pkill -9 -f "_solve_agent_worker" 2>/dev/null || true
    sleep 5
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
        echo "[FAIL rc=$rc t=${elapsed}s] $label (see $LOG_DIR/${label}.log)" | tee -a "$LOG_DIR/master.log"
    else
        echo "[OK t=${elapsed}s] $label" | tee -a "$LOG_DIR/master.log"
        # Extract welfare result lines for at-a-glance summary
        grep -E "HARK welfare cell:|JAX-replay-v2 welfare cell:|Relative diff:|Total wall:|paper-grade" \
            "$LOG_DIR/${label}.log" 2>/dev/null | tee -a "$LOG_DIR/master.log"
    fi
}

# Phase 1: recessionUI
run_step "verify_Baseline_2B_recessionUI" \
    env HAFISCAL_USE_JAX_2B=1 HAFISCAL_USE_SOLUTION_CACHE=1 PYTHONUNBUFFERED=1 \
    "$PY" Code/HA-Models/FromPandemicCode/verify_welfare_replay.py \
    --parametrization Baseline --policy recessionUI

# Phase 2: recessionTaxCut
run_step "verify_Baseline_2B_recessionTaxCut" \
    env HAFISCAL_USE_JAX_2B=1 HAFISCAL_USE_SOLUTION_CACHE=1 PYTHONUNBUFFERED=1 \
    "$PY" Code/HA-Models/FromPandemicCode/verify_welfare_replay.py \
    --parametrization Baseline --policy recessionTaxCut

# Phase 3 (conditional): head-to-head — parallel+2B at Baseline for
# recessionCheck. Only runs if phase 0 finished and showed parallel+2B
# wall < serial 2B's 1885s.
if grep -q "wall_jax_total: [0-9]" /tmp/bench_2B_parallel_cpu.log 2>/dev/null; then
    parallel_wall=$(grep "wall_jax_total:" /tmp/bench_2B_parallel_cpu.log | head -1 | awk '{print $2}' | tr -d 's')
    is_faster=$(awk -v w="$parallel_wall" 'BEGIN { print (w + 0 < 1885) ? "1" : "0" }')
    if [ "$is_faster" = "1" ]; then
        echo "[$(date '+%F %T')] phase 0 shows parallel+2B beats serial 2B ($parallel_wall < 1885s); running head-to-head" | tee -a "$LOG_DIR/master.log"
        run_step "verify_Baseline_parallel21_2B_recessionCheck" \
            env JAX_PLATFORMS=cpu HAFISCAL_PARALLEL_SOLVE=21 HAFISCAL_USE_JAX_2B=1 \
                HAFISCAL_USE_SOLUTION_CACHE=1 PYTHONUNBUFFERED=1 \
            "$PY" Code/HA-Models/FromPandemicCode/verify_welfare_replay.py \
            --parametrization Baseline --policy recessionCheck
    else
        echo "[$(date '+%F %T')] phase 0 parallel+2B wall ($parallel_wall) >= serial 2B (1885s); skipping head-to-head" | tee -a "$LOG_DIR/master.log"
    fi
else
    echo "[$(date '+%F %T')] phase 0 didn't produce wall_jax_total; skipping head-to-head" | tee -a "$LOG_DIR/master.log"
fi

echo "[$(date '+%F %T')] overnight 2B policies DONE" | tee -a "$LOG_DIR/master.log"
