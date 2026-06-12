#!/bin/bash
# launch_diag.sh VARIANT
#   VARIANT = full_tm | bigN | nosplurge
# Launches a single MC-vs-TM-a bias-mechanism diagnostic run.
set -euo pipefail
VARIANT="${1:?missing VARIANT (full_tm|bigN|nosplurge)}"
HERE=/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode
LOGDIR=/home/shared/github/llorracc/HAFiscal-Latest/reproduce/logs/h0_diag
TS=$(date +%Y%m%d-%H%M%S)
LOG="$LOGDIR/diag_${VARIANT}_${TS}.log"
PIDFILE="$LOGDIR/diag_${VARIANT}.pid"

# Defaults: same as H-0 treatment (friendly urates, treatment N, all shuffles)
AC_D=4900; AC_H=9800; AC_C=17640
TM_A_INDEXED=1
SPLURGE_OVERRIDE=""

AXTRA_COUNT=""
TM_MCOUNT=""
case "$VARIANT" in
  full_tm)
    TM_A_INDEXED=0  # use full TM instead of TM-a indexed approximation
    ;;
  bigN)
    AC_D=9800; AC_H=19600; AC_C=35280  # 2x quota-exact treatment
    ;;
  nosplurge)
    SPLURGE_OVERRIDE=0
    ;;
  finergrid)
    # D-6 (FIRST attempt, WRONG): bumped solver grid not aggregation grid
    AXTRA_COUNT=192
    SPLURGE_OVERRIDE=0
    ;;
  finer_tm_grid)
    # D-6 (SECOND attempt): bump TM aggregation grid (mCount) 4x with Splurge=0
    # Tests lottery-aggregation-across-kink hypothesis properly this time
    TM_MCOUNT=200
    SPLURGE_OVERRIDE=0
    ;;
  unemp_degenerate)
    # D-8 (2026-05-05): cohort method's unemp_shocks='degenerate' to match
    # qe_fidelity's ψ_unemp=1 behavior. Same config as treat_seed100 baseline
    # (no Splurge override, no other changes). Predicted: residual closes if
    # the (mrkv, pLvl) conditional bias was the dominant remaining mechanism.
    : # all other env vars at default; the fix is the new code default
    ;;
  bug040_off)
    # D-10 (2026-05-05): BUG-040 fix verification, default 'off' mode.
    # Both MC and TM-a use frozen-pLvl-during-unemp (QE-published convention).
    # Predicted: residual closes from 13% to ~0%.
    : # default config — relies on EstimParameters HAFISCAL_PLVL_GROWS_DURING_UNEMP=off default
    ;;
  bug040_on)
    # D-11: BUG-040 fix verification, 'on' mode (Harmenberg convention).
    # Both MC and TM-a apply G uniformly during unemployment.
    # Predicted: residual closes (different absolute multipliers from 'off' but agreement).
    EXTRA_ENV=("HAFISCAL_PLVL_GROWS_DURING_UNEMP=on")
    ;;
  bug041_fix)
    # D-13 (2026-05-05): BUG-041 fix verification — TM-a now uses MC's
    # CFunc-cell-offset convention by default (HAFISCAL_TM_CFUNC_OFFSET=mc).
    # Same config as D-10 (treat_seed100 baseline + BUG-040 fix off mode).
    # Predicted: 13% residual closes to ~0%.
    : # Default config — relies on HAFISCAL_TM_CFUNC_OFFSET=mc default
    ;;
  bug041_legacy)
    # D-13 control: BUG-041 LEGACY mode (HAFISCAL_TM_CFUNC_OFFSET=tm).
    # Reproduces the pre-fix TM-a behavior. Should match D-10 multipliers.
    EXTRA_ENV=("HAFISCAL_TM_CFUNC_OFFSET=tm")
    ;;
  *)
    echo "ERROR: unknown VARIANT $VARIANT" >&2; exit 2;;
esac
EXTRA_ENV=("${EXTRA_ENV[@]:-}")

cd "$HERE"
ENV_ARGS=(
  HAFISCAL_URATE_NORMAL_D=0.090 HAFISCAL_URATE_NORMAL_H=0.045 HAFISCAL_URATE_NORMAL_C=0.025
  HAFISCAL_AGENTCOUNT_D="$AC_D" HAFISCAL_AGENTCOUNT_H="$AC_H" HAFISCAL_AGENTCOUNT_C="$AC_C"
  HAFISCAL_MC_SHUFFLE=1 HAFISCAL_INCOME_SHUFFLE=1 HAFISCAL_MARKOV_SHUFFLE=1
  HAFISCAL_SEED_OFFSET=0
  HAFISCAL_SIM_METHOD=both
  HAFISCAL_INTERPRETATION=ESC HAFISCAL_PERM_DURING_UNEMP=off
  HAFISCAL_TM_A_INDEXED="$TM_A_INDEXED" HAFISCAL_TM_A_CACHE=1
  HAFISCAL_DRIFT_HARD_FAIL=0 HAFISCAL_DRIFT_THRESHOLD=0.03
  HAFISCAL_FIGS_SUFFIX="_diag_${VARIANT}"
  PYTHONUNBUFFERED=1
)
if [[ -n "$SPLURGE_OVERRIDE" ]]; then
  ENV_ARGS+=(HAFISCAL_SPLURGE_OVERRIDE="$SPLURGE_OVERRIDE")
fi
if [[ -n "$AXTRA_COUNT" ]]; then
  ENV_ARGS+=(HAFISCAL_AXTRA_COUNT="$AXTRA_COUNT")
fi
if [[ -n "$TM_MCOUNT" ]]; then
  ENV_ARGS+=(HAFISCAL_TM_MCOUNT="$TM_MCOUNT")
fi
for _x in "${EXTRA_ENV[@]}"; do
  if [[ -n "$_x" ]]; then ENV_ARGS+=("$_x"); fi
done

nohup env "${ENV_ARGS[@]}" python -u AggFiscalMAIN_reduced.py >"$LOG" 2>&1 &
PYPID=$!
disown
echo $PYPID > "$PIDFILE"
echo "VARIANT=$VARIANT PID=$PYPID LOG=$LOG"
