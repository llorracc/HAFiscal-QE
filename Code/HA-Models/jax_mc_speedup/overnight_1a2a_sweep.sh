#!/bin/bash
# Overnight 1A-2A characterization sweep: HS_Only + Reduced_Run.
#
# Per-flag: each 1A/1B/1C/1D/2A individually, plus v0 (none) and ALL-on.
# Plus cache-miss + cache-hit measurements per scale.
#
# Run as:
#   nohup bash Code/HA-Models/jax_mc_speedup/overnight_1a2a_sweep.sh \
#     > Code/HA-Models/jax_mc_speedup/overnight_1a2a_sweep.log 2>&1 &
set -uo pipefail

cd /home/shared/github/llorracc/HAFiscal-Latest || exit 1
unset VIRTUAL_ENV

PY=.venv-linux-x86_64/bin/python
BENCH=Code/HA-Models/jax_mc_speedup/jax_mc_speedup_bench.py
LOG_DIR=Code/HA-Models/jax_mc_speedup/overnight_1a2a_logs
mkdir -p "$LOG_DIR"

FLAG_2D="HAFISCAL_JAX_MC_USE_2D_LIFT=1"
FLAG_VS="HAFISCAL_JAX_MC_VMAP_SEEDS=1"
FLAG_BT="HAFISCAL_JAX_MC_BATCH_TABLES=1"
FLAG_LP="HAFISCAL_JAX_MC_LAZY_PANEL=1"
FLAG_VC="HAFISCAL_JAX_MC_VMAP_COHORTS=1"

run_one() {
    local label="$1"; shift
    local scale="$1"; shift
    local log="$LOG_DIR/${label}.log"
    echo "==========================================================" | tee -a "$LOG_DIR/master.log"
    echo "[$(date '+%F %T')] LABEL=$label SCALE=$scale ENV=[$*]" | tee -a "$LOG_DIR/master.log"
    echo "==========================================================" | tee -a "$LOG_DIR/master.log"
    local start_ts=$(date +%s)
    env "$@" PYTHONUNBUFFERED=1 \
        "$PY" "$BENCH" --label "$label" --parametrization "$scale" --num-iter 4 \
        > "$log" 2>&1
    local rc=$?
    local elapsed=$(($(date +%s) - start_ts))
    if [ $rc -ne 0 ]; then
        echo "[FAIL rc=$rc t=${elapsed}s] $label  (see $log)" | tee -a "$LOG_DIR/master.log"
    else
        echo "[OK t=${elapsed}s] $label" | tee -a "$LOG_DIR/master.log"
    fi
}

echo "[$(date '+%F %T')] START overnight 1A-2A sweep" | tee -a "$LOG_DIR/master.log"

# ---- HS_Only sweep (cache off) ----
run_one "v0__HS_Only"        HS_Only
run_one "1A_2D__HS_Only"     HS_Only $FLAG_2D
run_one "1B_VS__HS_Only"     HS_Only $FLAG_VS
run_one "1C_BT__HS_Only"     HS_Only $FLAG_BT
run_one "1D_LP__HS_Only"     HS_Only $FLAG_LP
run_one "2A_VC__HS_Only"     HS_Only $FLAG_VC
run_one "ALL__HS_Only"       HS_Only $FLAG_2D $FLAG_VS $FLAG_BT $FLAG_LP $FLAG_VC

# Cache populate + hit at HS_Only (wipe first so MISS is a true miss)
rm -rf Code/HA-Models/solution_cache/HS_Only 2>/dev/null
run_one "ALL__HS_Only__cache_miss" HS_Only $FLAG_2D $FLAG_VS $FLAG_BT $FLAG_LP $FLAG_VC HAFISCAL_USE_SOLUTION_CACHE=1
run_one "ALL__HS_Only__cache_hit"  HS_Only $FLAG_2D $FLAG_VS $FLAG_BT $FLAG_LP $FLAG_VC HAFISCAL_USE_SOLUTION_CACHE=1

# ---- Reduced_Run sweep (cache off) ----
run_one "v0__Reduced_Run"        Reduced_Run
run_one "1A_2D__Reduced_Run"     Reduced_Run $FLAG_2D
run_one "1B_VS__Reduced_Run"     Reduced_Run $FLAG_VS
run_one "1C_BT__Reduced_Run"     Reduced_Run $FLAG_BT
run_one "1D_LP__Reduced_Run"     Reduced_Run $FLAG_LP
run_one "2A_VC__Reduced_Run"     Reduced_Run $FLAG_VC
run_one "ALL__Reduced_Run"       Reduced_Run $FLAG_2D $FLAG_VS $FLAG_BT $FLAG_LP $FLAG_VC

# Cache populate + hit at Reduced_Run
rm -rf Code/HA-Models/solution_cache/Reduced_Run 2>/dev/null
run_one "ALL__Reduced_Run__cache_miss" Reduced_Run $FLAG_2D $FLAG_VS $FLAG_BT $FLAG_LP $FLAG_VC HAFISCAL_USE_SOLUTION_CACHE=1
run_one "ALL__Reduced_Run__cache_hit"  Reduced_Run $FLAG_2D $FLAG_VS $FLAG_BT $FLAG_LP $FLAG_VC HAFISCAL_USE_SOLUTION_CACHE=1

echo "[$(date '+%F %T')] DONE overnight 1A-2A sweep" | tee -a "$LOG_DIR/master.log"
