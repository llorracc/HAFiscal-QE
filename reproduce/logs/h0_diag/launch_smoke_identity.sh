#!/bin/bash
# launch_smoke_identity.sh AGG_MODE
#   AGG_MODE = on | off
#
# Smoke test: under standard config (no AgentCount override), the new
# HAFISCAL_AGGREGATE_BY_EDU_SHARE switch should produce identical results
# whether on or off. Verifies pop_rescale_factor = 1 in standard config.
set -euo pipefail
MODE="${1:?missing AGG_MODE (on|off)}"
HERE=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
LOGDIR=/home/shared/github/llorracc/HAFiscal-Latest/reproduce/logs/h0_diag
TS=$(date +%Y%m%d-%H%M%S)
LOG="$LOGDIR/smoke_identity_${MODE}_${TS}.log"

cd "$HERE"
nohup env \
  HAFISCAL_INTERPRETATION=ESC HAFISCAL_PERM_DURING_UNEMP=off \
  HAFISCAL_TM_A_INDEXED=1 HAFISCAL_TM_A_CACHE=1 \
  HAFISCAL_DRIFT_HARD_FAIL=0 HAFISCAL_DRIFT_THRESHOLD=0.03 \
  HAFISCAL_SIM_METHOD=both \
  HAFISCAL_AGGREGATE_BY_EDU_SHARE="$MODE" \
  HAFISCAL_FIGS_SUFFIX="_smoke_identity_${MODE}" \
  PYTHONUNBUFFERED=1 \
  python -u AggFiscalMAIN_reduced.py > "$LOG" 2>&1 &
PYPID=$!
disown
echo "MODE=$MODE PID=$PYPID LOG=$LOG"
