#!/bin/bash
# bug034_heartbeat.sh — heartbeat for Phase F's long-running ESC anchor production.
#
# Phase F runs `./reproduce.sh --comp full --mc-only --interpretation esc --auto-commit`
# in the background (~6-12 hours). This script periodically writes [ALIVE] lines to
# reproduce/logs/bug034-fix.log so the user can `tail -f` and see progress
# without checking process status.
#
# Spec: see plans/20260425-2137h_cdc-esc-configurable-refactor.md §1.6
#
# Usage (run in background after starting the anchor production):
#   reproduce/bug034_heartbeat.sh <BG_PID> [INTERVAL_SECONDS]
#     BG_PID            — PID of the backgrounded reproduce.sh process
#     INTERVAL_SECONDS  — seconds between heartbeats (default 600 = 10 min)
#
# Stops automatically when BG_PID exits.

set -euo pipefail

BG_PID="${1:?usage: $0 BG_PID [INTERVAL_SECONDS]}"
INTERVAL="${2:-600}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_HELPER="$SCRIPT_DIR/bug034_log.sh"
SCENARIO_LOG_DIR="$REPO_ROOT/Code/HA-Models/FromPandemicCode/welfare6_parallel_logs/Baseline_esc"

# Initial heartbeat (acknowledge start).
START_TS="$(date -u +%s)"

while kill -0 "$BG_PID" 2>/dev/null; do
    NOW_TS="$(date -u +%s)"
    ELAPSED_S=$((NOW_TS - START_TS))
    ELAPSED_H=$((ELAPSED_S / 3600))
    ELAPSED_M=$(( (ELAPSED_S % 3600) / 60 ))

    # Count completed scenarios (those whose log shows "saved:").
    COMPLETED=0
    LATEST_SCENARIO=""
    LATEST_PCT=""
    if [[ -d "$SCENARIO_LOG_DIR" ]]; then
        COMPLETED="$(grep -l 'saved:' "$SCENARIO_LOG_DIR"/*.log 2>/dev/null | wc -l)"
        # Find most recently modified log file (the in-progress scenario).
        # shellcheck disable=SC2012  # log filenames are alphanumeric; ls -t is the simple mtime sort
        LATEST_LOG="$(ls -t "$SCENARIO_LOG_DIR"/*.log 2>/dev/null | head -1)"
        if [[ -n "$LATEST_LOG" ]]; then
            LATEST_SCENARIO="$(basename "$LATEST_LOG" .log)"
            # Scenario logs typically print progress like "(72s wall)" — best-effort parse.
            LATEST_PCT="$(tail -3 "$LATEST_LOG" | grep -oE '[0-9]+%' | tail -1 || echo '?')"
        fi
    fi

    MSG="ESC anchor alive; elapsed ${ELAPSED_H}h ${ELAPSED_M}m; ${COMPLETED}/12 scenarios complete"
    if [[ -n "$LATEST_SCENARIO" ]] && [[ "$COMPLETED" -lt 12 ]]; then
        MSG="${MSG}; latest: ${LATEST_SCENARIO}${LATEST_PCT:+ ($LATEST_PCT)}"
    fi

    "$LOG_HELPER" ALIVE F 4 T4.1 "$MSG"

    sleep "$INTERVAL"
done

# BG process exited — log the transition.
NOW_TS="$(date -u +%s)"
ELAPSED_S=$((NOW_TS - START_TS))
ELAPSED_H=$((ELAPSED_S / 3600))
ELAPSED_M=$(( (ELAPSED_S % 3600) / 60 ))
"$LOG_HELPER" INFO F 4 T4.1 "background process $BG_PID exited; total elapsed ${ELAPSED_H}h ${ELAPSED_M}m; heartbeat stopping"
