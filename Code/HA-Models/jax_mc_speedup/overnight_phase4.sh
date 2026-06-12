#!/bin/bash
# Phase 4: 2B test_2B_scaled at all 21 Baseline cohorts (those not already
# covered by phases 2 and 3). Gives the full per-cohort speedup curve for
# the lax.while_loop variant vs HARK native.
#
# Cohorts already done by other phases: 0, 5, 10, 15, 20.
# Phase 4 covers: 1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17, 18, 19 (16 cohorts).
set -uo pipefail
cd /home/shared/github/llorracc/HAFiscal-Latest || exit 1
unset VIRTUAL_ENV

PY=.venv-linux-x86_64/bin/python
LOG_DIR=Code/HA-Models/jax_mc_speedup/overnight_phase4_logs
mkdir -p "$LOG_DIR"

echo "[$(date '+%F %T')] phase 4 START" | tee -a "$LOG_DIR/master.log"

PHASE3_LOG="Code/HA-Models/jax_mc_speedup/overnight_phase3_logs/master.log"
WAITED=0
echo "[$(date '+%F %T')] waiting for phase 3 DONE line in $PHASE3_LOG..." \
    | tee -a "$LOG_DIR/master.log"
while [ "$WAITED" -lt 7200 ]; do
    if grep -q "phase 3 DONE" "$PHASE3_LOG" 2>/dev/null; then
        echo "[$(date '+%F %T')] phase 3 done; proceeding" \
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

for cohort in 1 2 3 4 6 7 8 9 11 12 13 14 16 17 18 19; do
    run_step "2B_Baseline_cohort${cohort}" \
        env PYTHONUNBUFFERED=1 "$PY" Code/HA-Models/jax_mc_speedup/test_2B_scaled.py \
        --parametrization Baseline --cohort "$cohort"
done

echo "[$(date '+%F %T')] phase 4 DONE" | tee -a "$LOG_DIR/master.log"
