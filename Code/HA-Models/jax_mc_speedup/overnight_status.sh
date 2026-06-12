#!/bin/bash
# Quick status of all overnight phases. Run in the morning to see what's done
# and what's still going.
#
# Usage:
#   bash Code/HA-Models/jax_mc_speedup/overnight_status.sh
set -uo pipefail
cd /home/shared/github/llorracc/HAFiscal-Latest || exit 1

echo "=== Overnight phase status at $(date) ==="
for p in 1a2a phase2 phase3 phase4 phase5 phase6; do
    log=Code/HA-Models/jax_mc_speedup/overnight_${p}_logs/master.log
    if [ ! -f "$log" ]; then
        printf "  %-8s NOT STARTED\n" "$p"
        continue
    fi
    if grep -qE "^\[.*\] (phase [0-9]+ DONE|DONE overnight)" "$log"; then
        done_line=$(grep -E "^\[.*\] (phase [0-9]+ DONE|DONE overnight)" "$log" | tail -1)
        # Extract just the timestamp
        printf "  %-8s DONE at %s\n" "$p" "$(echo "$done_line" | grep -oE '^\[[^]]+\]')"
    else
        step=$(grep "STEP:" "$log" | tail -1 | sed 's/^.*STEP: //')
        last_ok=$(grep -E "^\[OK|^\[FAIL" "$log" | tail -1)
        if [ -z "$step" ]; then
            printf "  %-8s waiting (queued)\n" "$p"
        else
            printf "  %-8s in step: %s\n" "$p" "$step"
            [ -n "$last_ok" ] && printf "    last completion: %s\n" "$last_ok"
        fi
    fi
done

echo ""
echo "=== Active processes ==="
# shellcheck disable=SC2009  # need full ps fields (elapsed, cmd args) that pgrep can't give
ps aux | grep -E "(jax_mc_speedup_bench|test_2B_scaled|verify_welfare_replay)" \
    | grep -v grep | awk '{printf "  PID=%s elapsed=%s cmd=%s %s %s\n", $2, $10, $11, $12, $13}'

echo ""
echo "=== Cache state ==="
.venv-linux-x86_64/bin/python Code/HA-Models/solution_cache/inspect_cache.py 2>&1 | tail -20

echo ""
echo "=== 2B speedup curves (run after phase 4 / phase 6 done) ==="
echo "  Cold-start: python Code/HA-Models/jax_mc_speedup/analyze_2B_speedup_curve.py"
echo "  Warm-start: python Code/HA-Models/jax_mc_speedup/analyze_2B_speedup_curve.py --warmstart"
