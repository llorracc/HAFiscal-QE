#!/bin/bash
# launch_bug041_seeds.sh SEED
#   SEED = 100 | 200 (seed=0 was already run as bug041_fix)
# Launch a single bug041_fix diagnostic with given SEED_OFFSET.
# Output goes to Reduced_Run_diag_bug041_seed<SEED>/
set -euo pipefail
SEED="${1:?missing SEED (100|200)}"
HERE=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
LOGDIR=/home/shared/github/llorracc/HAFiscal-Latest/reproduce/logs/h0_diag
TS=$(date +%Y%m%d-%H%M%S)
LOG="$LOGDIR/diag_bug041_seed${SEED}_${TS}.log"
PIDFILE="$LOGDIR/diag_bug041_seed${SEED}.pid"

cd "$HERE"
ENV_ARGS=(
  HAFISCAL_URATE_NORMAL_D=0.090 HAFISCAL_URATE_NORMAL_H=0.045 HAFISCAL_URATE_NORMAL_C=0.025
  HAFISCAL_AGENTCOUNT_D=4900 HAFISCAL_AGENTCOUNT_H=9800 HAFISCAL_AGENTCOUNT_C=17640
  HAFISCAL_MC_SHUFFLE=1 HAFISCAL_INCOME_SHUFFLE=1 HAFISCAL_MARKOV_SHUFFLE=1
  HAFISCAL_SEED_OFFSET="$SEED"
  HAFISCAL_SIM_METHOD=both
  HAFISCAL_INTERPRETATION=ESC HAFISCAL_PERM_DURING_UNEMP=off
  HAFISCAL_TM_A_INDEXED=1 HAFISCAL_TM_A_CACHE=1
  HAFISCAL_DRIFT_HARD_FAIL=0 HAFISCAL_DRIFT_THRESHOLD=0.03
  HAFISCAL_FIGS_SUFFIX="_diag_bug041_seed${SEED}"
  PYTHONUNBUFFERED=1
)

nohup env "${ENV_ARGS[@]}" python -u AggFiscalMAIN_reduced.py >"$LOG" 2>&1 &
PYPID=$!
disown
echo $PYPID > "$PIDFILE"
echo "SEED=$SEED PID=$PYPID LOG=$LOG"
