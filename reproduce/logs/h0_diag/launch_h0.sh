#!/bin/bash
# launch_h0.sh ARM SEED
#   ARM = treat | control
#   SEED = 0 | 100 | 200
# Launches a single H-0 diagnostic run in the background; writes PID to
# h0_diag/<arm>_seed<seed>.pid and log to h0_diag/<arm>_seed<seed>_<TS>.log.
set -euo pipefail
ARM="${1:?missing ARM (treat|control)}"
SEED="${2:?missing SEED (0|100|200)}"
HERE=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
LOGDIR=/home/shared/github/llorracc/HAFiscal-Latest/reproduce/logs/h0_diag
TS=$(date +%Y%m%d-%H%M%S)
LOG="$LOGDIR/${ARM}_seed${SEED}_${TS}.log"
PIDFILE="$LOGDIR/${ARM}_seed${SEED}.pid"

if [[ "$ARM" == "treat" ]]; then
    AC_D=4900; AC_H=9800; AC_C=17640
elif [[ "$ARM" == "control" ]]; then
    AC_D=10000; AC_H=10000; AC_C=10000
else
    echo "ERROR: ARM must be treat or control, got $ARM" >&2; exit 2
fi

cd "$HERE"
nohup env \
  HAFISCAL_URATE_NORMAL_D=0.090 HAFISCAL_URATE_NORMAL_H=0.045 HAFISCAL_URATE_NORMAL_C=0.025 \
  HAFISCAL_AGENTCOUNT_D=$AC_D HAFISCAL_AGENTCOUNT_H=$AC_H HAFISCAL_AGENTCOUNT_C=$AC_C \
  HAFISCAL_MC_SHUFFLE=1 HAFISCAL_INCOME_SHUFFLE=1 HAFISCAL_MARKOV_SHUFFLE=1 \
  HAFISCAL_SEED_OFFSET="$SEED" \
  HAFISCAL_SIM_METHOD=both \
  HAFISCAL_INTERPRETATION=ESC HAFISCAL_PERM_DURING_UNEMP=off \
  HAFISCAL_TM_A_INDEXED=1 HAFISCAL_TM_A_CACHE=1 \
  HAFISCAL_DRIFT_HARD_FAIL=0 HAFISCAL_DRIFT_THRESHOLD=0.03 \
  HAFISCAL_FIGS_SUFFIX="_h0_${ARM}_seed${SEED}" \
  PYTHONUNBUFFERED=1 \
  python -u AggFiscalMAIN_reduced.py >"$LOG" 2>&1 &
PYPID=$!
disown
# capture the actual python pid (not the shell wrapper)
echo $PYPID > "$PIDFILE"
echo "$ARM seed=$SEED PID=$PYPID LOG=$LOG"
