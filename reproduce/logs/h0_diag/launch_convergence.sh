#!/bin/bash
# launch_convergence.sh QUOTA SEED [SIM_METHOD] [MCOUNT]
#   QUOTA = 1x | 2x        (cohort N multiplier of friendly-quota)
#   SEED  = 0 | 100 | 200
#   SIM_METHOD = both | MC | TM   (default: both)
#   MCOUNT = override TM grid count (default: 50)
#
# Single-config wrapper for the MC-shuffle vs TM-a convergence study.
# Phase A (MC sensitivity to N): 6 'both' runs across (1x, 2x) × (3 seeds).
# Phase B (TM grid sensitivity): TM-only runs at mCount=50/100/200.
set -euo pipefail
QUOTA="${1:?missing QUOTA (1x|2x)}"
SEED="${2:?missing SEED (0|100|200)}"
SIM_METHOD="${3:-both}"
MCOUNT="${4:-50}"

HERE=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
LOGDIR=/home/shared/github/llorracc/HAFiscal-Latest/reproduce/logs/h0_diag
TS=$(date +%Y%m%d-%H%M%S)
TAG="${QUOTA}_seed${SEED}_${SIM_METHOD}_m${MCOUNT}"
LOG="$LOGDIR/conv_${TAG}_${TS}.log"
PIDFILE="$LOGDIR/conv_${TAG}.pid"

# Cohort-specific N at friendly-urate quota-exact figures
case "$QUOTA" in
    1x)  AC_D=4900;  AC_H=9800;  AC_C=17640 ;;
    2x)  AC_D=9800;  AC_H=19600; AC_C=35280 ;;
    *) echo "ERROR: QUOTA must be 1x or 2x" >&2; exit 2 ;;
esac

cd "$HERE"
nohup env \
  HAFISCAL_URATE_NORMAL_D=0.090 HAFISCAL_URATE_NORMAL_H=0.045 HAFISCAL_URATE_NORMAL_C=0.025 \
  HAFISCAL_AGENTCOUNT_D=$AC_D HAFISCAL_AGENTCOUNT_H=$AC_H HAFISCAL_AGENTCOUNT_C=$AC_C \
  HAFISCAL_MC_SHUFFLE=1 HAFISCAL_INCOME_SHUFFLE=1 HAFISCAL_MARKOV_SHUFFLE=1 \
  HAFISCAL_SEED_OFFSET="$SEED" \
  HAFISCAL_SIM_METHOD="$SIM_METHOD" \
  HAFISCAL_TM_MCOUNT="$MCOUNT" \
  HAFISCAL_INTERPRETATION=ESC HAFISCAL_PERM_DURING_UNEMP=off \
  HAFISCAL_TM_A_INDEXED=1 HAFISCAL_TM_A_CACHE=1 \
  HAFISCAL_DRIFT_HARD_FAIL=0 HAFISCAL_DRIFT_THRESHOLD=0.03 \
  HAFISCAL_FIGS_SUFFIX="_conv_${TAG}" \
  PYTHONUNBUFFERED=1 \
  python -u AggFiscalMAIN_reduced.py >"$LOG" 2>&1 &
PYPID=$!
disown
echo $PYPID > "$PIDFILE"
echo "TAG=$TAG  PID=$PYPID  LOG=$LOG"
