#!/usr/bin/env bash
# Launch one bench (CPU or GPU) with memory tracking.
#
# Args (positional):
#   LABEL          e.g. "2threads_cpu"
#   N_THREADS      HAFISCAL_USE_JAX_2B_THREADS (e.g. 2)
#   BACKEND        "cpu" | "gpu"
#   PARAM          parametrization (default: Baseline)
#   NUM_ITER       --num-iter (default: 4)
#   N_WORKERS      HAFISCAL_PARALLEL_SOLVE (default 1 = no multiprocess solve)
#   N_REFSIM_PARALLEL  HAFISCAL_REFSIM_PARALLEL (default 1 = no parallel ref-sim solve)
#
# Outputs (in this dir):
#   <LABEL>.bench.log     bench stdout+stderr
#   <LABEL>.timing.log    /usr/bin/time -v summary
#   <LABEL>.mem.csv       memory time series (10s interval)
#   <LABEL>.launch.meta   launch metadata
set -euo pipefail

LABEL="$1"
N_THREADS="${2:-2}"
BACKEND="${3:-cpu}"
PARAM="${4:-Baseline}"
NUM_ITER="${5:-4}"
N_WORKERS="${6:-1}"
N_REFSIM_PARALLEL="${7:-1}"

HERE="$(cd "$(dirname "$0")" && pwd)"
# HERE = .../HAFiscal-Latest/Code/HA-Models/jax_mc_speedup/threads_bench_logs
# Need 4 ups to reach HAFiscal-Latest
REPO_ROOT="$(cd "$HERE/../../../.." && pwd)"
VENV_PY="$REPO_ROOT/.venv-linux-x86_64/bin/python"
BENCH_PY="$REPO_ROOT/Code/HA-Models/jax_mc_speedup/jax_mc_speedup_bench.py"

BENCH_LOG="$HERE/${LABEL}.bench.log"
TIMING_LOG="$HERE/${LABEL}.timing.log"
MEM_CSV="$HERE/${LABEL}.mem.csv"
META="$HERE/${LABEL}.launch.meta"

cat > "$META" <<EOF
LABEL=$LABEL
N_THREADS=$N_THREADS
N_WORKERS=$N_WORKERS
BACKEND=$BACKEND
PARAM=$PARAM
NUM_ITER=$NUM_ITER
LAUNCH_TIME=$(date -Is)
HOST=$(hostname)
HAFISCAL_USE_JAX_2B=1
HAFISCAL_USE_JAX_2B_THREADS=$N_THREADS
HAFISCAL_PARALLEL_SOLVE=$N_WORKERS
HAFISCAL_REFSIM_PARALLEL=$N_REFSIM_PARALLEL
HAFISCAL_USE_SOLUTION_CACHE=0
EOF

if [ "$BACKEND" = "gpu" ]; then
    # Apply venv patch (idempotent) so plain python works on GPU
    bash "$REPO_ROOT/Code/HA-Models/jax_mc_speedup/apply_jax_gpu_patch.sh" --quiet
    NVJL="$REPO_ROOT/.venv-linux-x86_64/lib/python3.11/site-packages/nvidia/nvjitlink/lib/libnvJitLink.so.12"
    export LD_PRELOAD="${NVJL}${LD_PRELOAD:+:$LD_PRELOAD}"
    export JAX_PLATFORMS=cuda
    # Disable JAX's 75%-preallocation so nvidia-smi reflects REAL usage
    export XLA_PYTHON_CLIENT_PREALLOCATE=false
    export XLA_PYTHON_CLIENT_ALLOCATOR=platform
    GPU_FLAG=1
    {
        echo "JAX_PLATFORMS=cuda (via wrapper)"
        echo "LD_PRELOAD=$LD_PRELOAD"
        echo "XLA_PYTHON_CLIENT_PREALLOCATE=false"
        echo "XLA_PYTHON_CLIENT_ALLOCATOR=platform"
    } >> "$META"
else
    export JAX_PLATFORMS=cpu
    GPU_FLAG=0
    echo "JAX_PLATFORMS=cpu" >> "$META"
fi

export PYTHONUNBUFFERED=1
export HAFISCAL_USE_JAX_2B=1
export HAFISCAL_USE_JAX_2B_THREADS="$N_THREADS"
export HAFISCAL_PARALLEL_SOLVE="$N_WORKERS"
export HAFISCAL_REFSIM_PARALLEL="$N_REFSIM_PARALLEL"
export HAFISCAL_USE_SOLUTION_CACHE=0

# Launch bench wrapped in /usr/bin/time -v
/usr/bin/time -v -o "$TIMING_LOG" \
    "$VENV_PY" "$BENCH_PY" \
        --label "$LABEL" --parametrization "$PARAM" --num-iter "$NUM_ITER" \
    > "$BENCH_LOG" 2>&1 &
BENCH_TIME_PID=$!
echo "TIME_PID=$BENCH_TIME_PID" >> "$META"

# Wait for python child to appear
sleep 3
PY_PID=$(pgrep -P "$BENCH_TIME_PID" || true)
if [ -z "$PY_PID" ]; then
    # /usr/bin/time may have exec'd instead of fork-exec; the PID IS python
    PY_PID="$BENCH_TIME_PID"
fi
echo "PY_PID=$PY_PID" >> "$META"

# Launch poller against the python PID, in background
nohup bash "$HERE/mem_poller.sh" "$PY_PID" "$MEM_CSV" 10 "$GPU_FLAG" \
    > "$HERE/${LABEL}.poller.log" 2>&1 &
POLLER_PID=$!
echo "POLLER_PID=$POLLER_PID" >> "$META"

echo "[launch_bench] Launched $LABEL"
echo "  TIME_PID=$BENCH_TIME_PID"
echo "  PY_PID=$PY_PID"
echo "  POLLER_PID=$POLLER_PID"
echo "  Logs in: $HERE"
echo
echo "  When this bench completes, append to the registry with:"
echo "    $REPO_ROOT/.venv-linux-x86_64/bin/python \\"
echo "      $REPO_ROOT/Code/HA-Models/experiments/append.py \\"
echo "      --label $LABEL \\"
echo "      --hypothesis '<what you expected>' \\"
echo "      --outcome '<what happened, lesson>' \\"
echo "      --tags <comma-separated-tags> \\"
echo "      --parent-ids <comma-separated-parent-ids> \\"
echo "      --vs-baseline <baseline-id-or-empty>"
