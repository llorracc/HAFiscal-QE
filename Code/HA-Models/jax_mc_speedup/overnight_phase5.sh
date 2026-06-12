#!/bin/bash
# Phase 5: verify_welfare_replay at Reduced_Run + HARK-AD cache validation at
# Baseline (~30 min HARK AD MISS + ~1 min HIT). Validates the HARK-AD cache
# wrapper at production scale (HS_Only smoke was 20s — Baseline is the real
# stress test).
#
# Runs after phase 4 finishes.
set -uo pipefail
cd /home/shared/github/llorracc/HAFiscal-Latest || exit 1
unset VIRTUAL_ENV

PY=.venv-linux-x86_64/bin/python
LOG_DIR=Code/HA-Models/jax_mc_speedup/overnight_phase5_logs
mkdir -p "$LOG_DIR"

echo "[$(date '+%F %T')] phase 5 START" | tee -a "$LOG_DIR/master.log"

PHASE4_LOG="Code/HA-Models/jax_mc_speedup/overnight_phase4_logs/master.log"
WAITED=0
echo "[$(date '+%F %T')] waiting for phase 4 DONE line in $PHASE4_LOG..." \
    | tee -a "$LOG_DIR/master.log"
while [ "$WAITED" -lt 7200 ]; do
    if grep -q "phase 4 DONE" "$PHASE4_LOG" 2>/dev/null; then
        echo "[$(date '+%F %T')] phase 4 done; proceeding" \
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

# Step 1: verify_welfare_replay at Reduced_Run — validates paper-grade welfare
# at larger scale than HS_Only.
run_step "verify_replay_Reduced_Run" \
    env PYTHONUNBUFFERED=1 HAFISCAL_USE_SOLUTION_CACHE=1 \
    "$PY" Code/HA-Models/FromPandemicCode/verify_welfare_replay.py \
    --parametrization Reduced_Run --policy recessionCheck

# Step 2: Baseline HARK-AD smoke (MISS first since no prior HARK-AD entry exists)
# Reuses our smoke_test_hark_ad.py but at Baseline scale.
# Note: smoke_test runs at HS_Only by default; we'll write a Baseline variant
# inline here via a quick Python one-liner.
run_step "HARK_AD_cache_Baseline_smoke" \
    env HAFISCAL_USE_SOLUTION_CACHE=1 PYTHONUNBUFFERED=1 \
    "$PY" -c "
import os, sys, time
sys.path.insert(0, 'Code/HA-Models/solution_cache')
sys.path.insert(0, 'Code/HA-Models/FromPandemicCode')
sys.argv = [sys.argv[0]]
os.environ['HAFISCAL_USE_SOLUTION_CACHE'] = '1'

from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base
from ad_cache import cached_solve_ad_recession_hark

# Wipe any prior HARK-AD entry at Baseline so step 1 is a true MISS
import glob
for f in glob.glob('Code/HA-Models/solution_cache/Baseline/recession/ad_hark_*.pkl'):
    os.remove(f)
for f in glob.glob('Code/HA-Models/solution_cache/Baseline/recession/ad_hark_*.meta.json'):
    os.remove(f)
print('[smoke] === RUN 1: should MISS (Baseline HARK-AD) ===', flush=True)
t0 = time.time()
ctx1 = build_and_solve('Baseline')
run_base(ctx1)
eco1 = deepcopy(ctx1['AggEco'])
eco1.switch_shock_type('recession')
print(f'  build+base+switch in {time.time()-t0:.1f}s', flush=True)
t_ad1 = time.time()
cached_solve_ad_recession_hark(
    {'AggEco': eco1},
    num_max_iterations=ctx1['num_max_iterations_solvingAD'],
    convergence_cutoff=ctx1['convergence_tol_solvingAD'],
    shock_type='recession', name='recession',
    verbose=True,
)
wall_miss = time.time() - t_ad1
print(f'[smoke] MISS wall: {wall_miss:.1f}s', flush=True)
print('[smoke] === RUN 2: should HIT ===', flush=True)
ctx2 = build_and_solve('Baseline')
run_base(ctx2)
eco2 = deepcopy(ctx2['AggEco'])
eco2.switch_shock_type('recession')
t_ad2 = time.time()
cached_solve_ad_recession_hark(
    {'AggEco': eco2},
    num_max_iterations=ctx2['num_max_iterations_solvingAD'],
    convergence_cutoff=ctx2['convergence_tol_solvingAD'],
    shock_type='recession', name='recession',
    verbose=True,
)
wall_hit = time.time() - t_ad2
print(f'[smoke] HIT wall: {wall_hit:.1f}s ({wall_miss/max(wall_hit,1e-3):.0f}x speedup)', flush=True)
print('[smoke] PASS' if wall_hit < wall_miss * 0.1 else '[smoke] WARN: hit not much faster than miss', flush=True)
"

echo "[$(date '+%F %T')] phase 5 DONE" | tee -a "$LOG_DIR/master.log"
