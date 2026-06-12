#!/bin/bash
# Overnight chain: Baseline welfare verify (Check + TaxCut), load-balance bench.
# Uses Baseline DEFAULT agent count (10k total), NOT 5x — at 5x the run_experiment
# phase takes ~15-20 min sequentially per AD iter × 4-5 iters × 2 scenarios = 2-3 hours
# per verification. Default gives ~10-20 min per verification — actually finishes overnight.
set -e
cd /home/shared/github/llorracc/HAFiscal-Latest
unset VIRTUAL_ENV

LOG_DIR=reproduce/logs/overnight
PY=.venv-linux-x86_64/bin/python

echo "[chain] starting at $(date)" >&2

# Step 1: Baseline welfare verify for recessionCheck (default AgentCountTotal)
echo "[chain] [1/3] Baseline (default) recessionCheck welfare verify ..." >&2
START=$(date +%s)
env PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    timeout 3600 \
    "$PY" Code/HA-Models/FromPandemicCode/verify_welfare_replay.py \
    --parametrization Baseline --policy recessionCheck --solve-workers 21 \
    > "$LOG_DIR/baseline_welfare_check.log" 2>&1 || echo "[chain] [1/3] exited non-zero" >&2
echo "[chain] [1/3] done in $(($(date +%s) - START))s at $(date)" >&2

# Step 2: load-balance speedup measurement (Baseline 5x for full-scale)
echo "[chain] [2/3] load-balance speedup at Baseline 5x ..." >&2
START=$(date +%s)
env PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    HAFISCAL_AGENTCOUNT_D=16000 HAFISCAL_AGENTCOUNT_H=88000 HAFISCAL_AGENTCOUNT_C=56000 \
    TEST_PARAM=Baseline TEST_N_WORKERS=21 \
    timeout 2400 \
    "$PY" Code/HA-Models/FromPandemicCode/load_balance_bench.py \
    > "$LOG_DIR/load_balance_bench.log" 2>&1 || echo "[chain] [2/3] exited non-zero" >&2
echo "[chain] [2/3] done in $(($(date +%s) - START))s at $(date)" >&2

# Step 3: Baseline welfare verify for recessionTaxCut
echo "[chain] [3/3] Baseline (default) recessionTaxCut welfare verify ..." >&2
START=$(date +%s)
env PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    timeout 3600 \
    "$PY" Code/HA-Models/FromPandemicCode/verify_welfare_replay.py \
    --parametrization Baseline --policy recessionTaxCut --solve-workers 21 \
    > "$LOG_DIR/baseline_welfare_taxcut.log" 2>&1 || echo "[chain] [3/3] exited non-zero" >&2
echo "[chain] [3/3] done in $(($(date +%s) - START))s at $(date)" >&2

echo "[chain] overnight chain complete at $(date)" >&2
