#!/usr/bin/env bash
# Memory poller for a target PID. Logs (elapsed_s, vmrss_mb, vmsize_mb,
# nproc_threads) and on GPU runs also logs (gpu_used_mb, gpu_util) once
# per interval. Exits cleanly when the target PID is gone.
#
# Usage:
#   bash mem_poller.sh PID OUTPUT_CSV [INTERVAL_SECS] [GPU=0|1]
set -euo pipefail
PID="$1"
OUT="$2"
INT="${3:-10}"
GPU="${4:-0}"

START=$(date +%s)
if [ "$GPU" = "1" ]; then
    echo "elapsed_s,vmrss_mb,vmsize_mb,nthreads,gpu_used_mb,gpu_util_pct" > "$OUT"
else
    echo "elapsed_s,vmrss_mb,vmsize_mb,nthreads" > "$OUT"
fi

while kill -0 "$PID" 2>/dev/null; do
    NOW=$(date +%s)
    ELAPSED=$((NOW - START))
    # /proc/<pid>/status: VmRSS, VmSize, Threads
    if [ -r "/proc/$PID/status" ]; then
        VMRSS_KB=$(awk '/^VmRSS:/{print $2}' "/proc/$PID/status" 2>/dev/null || echo 0)
        VMSIZE_KB=$(awk '/^VmSize:/{print $2}' "/proc/$PID/status" 2>/dev/null || echo 0)
        NTHR=$(awk '/^Threads:/{print $2}' "/proc/$PID/status" 2>/dev/null || echo 0)
        VMRSS_MB=$((VMRSS_KB / 1024))
        VMSIZE_MB=$((VMSIZE_KB / 1024))
        if [ "$GPU" = "1" ]; then
            GPU_INFO=$(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
            GPU_USED=${GPU_INFO%,*}
            GPU_UTIL=${GPU_INFO##*,}
            echo "$ELAPSED,$VMRSS_MB,$VMSIZE_MB,$NTHR,$GPU_USED,$GPU_UTIL" >> "$OUT"
        else
            echo "$ELAPSED,$VMRSS_MB,$VMSIZE_MB,$NTHR" >> "$OUT"
        fi
    fi
    sleep "$INT"
done

echo "[mem_poller] target PID $PID exited at elapsed_s=$(($(date +%s) - START))" >> "$OUT"
