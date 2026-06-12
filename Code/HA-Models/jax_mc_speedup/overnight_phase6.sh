#!/bin/bash
# Phase 6: 2B with --warm-start (HARK-converged as initial belief instead of
# solution_terminal). Mirrors the real AD-outer-loop inner-solve regime where
# the previous outer iter's converged cFunc is the next outer iter's starting
# belief. Should converge in 1-2 iters at any cohort, including the
# previously-failing cohort 20.
set -uo pipefail
cd /home/shared/github/llorracc/HAFiscal-Latest || exit 1
unset VIRTUAL_ENV

PY=.venv-linux-x86_64/bin/python
LOG_DIR=Code/HA-Models/jax_mc_speedup/overnight_phase6_logs
mkdir -p "$LOG_DIR"

echo "[$(date '+%F %T')] phase 6 START" | tee -a "$LOG_DIR/master.log"

PHASE5_LOG="Code/HA-Models/jax_mc_speedup/overnight_phase5_logs/master.log"
WAITED=0
echo "[$(date '+%F %T')] waiting for phase 5 DONE line in $PHASE5_LOG..." \
    | tee -a "$LOG_DIR/master.log"
while [ "$WAITED" -lt 9000 ]; do
    if grep -q "phase 5 DONE" "$PHASE5_LOG" 2>/dev/null; then
        echo "[$(date '+%F %T')] phase 5 done; proceeding" \
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

# 2B with warm-start at cohorts spanning the beta range
for cohort in 0 5 10 15 20; do
    run_step "2B_Baseline_warmstart_cohort${cohort}" \
        env PYTHONUNBUFFERED=1 "$PY" Code/HA-Models/jax_mc_speedup/test_2B_scaled.py \
        --parametrization Baseline --cohort "$cohort" --warm-start
done

echo "[$(date '+%F %T')] phase 6 DONE" | tee -a "$LOG_DIR/master.log"
