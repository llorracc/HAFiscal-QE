#!/bin/bash
#
# Run Full Reproduction Comparison in Background
#
# Usage:
#   ./run_full_reproduction.sh [--all|--step N|--resume]
#
# Monitor progress:
#   tail -f /tmp/hafiscal_full_repro/logs/master.log
#
# Check for alerts:
#   ls -la /tmp/hafiscal_full_repro/alerts/
#
# View specific step log:
#   tail -f /tmp/hafiscal_full_repro/logs/step1_0.14.1-bugfixed.log
#   tail -f /tmp/hafiscal_full_repro/logs/step1_0.17.0-native.log
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="/tmp/hafiscal_full_repro/logs"
mkdir -p "$LOG_DIR"

echo "============================================================"
echo "HAFiscal Full Reproduction Comparison"
echo "============================================================"
echo ""
echo "Log directory: $LOG_DIR"
echo "Master log: $LOG_DIR/master.log"
echo ""

# Parse arguments
ACTION="${1:---help}"

case "$ACTION" in
    --all)
        echo "Starting FULL reproduction comparison (all steps)..."
        echo "This will take 4-5 DAYS to complete."
        echo ""
        echo "Running in background. Monitor with:"
        echo "  tail -f $LOG_DIR/master.log"
        echo ""
        nohup python full_reproduction_orchestrator.py --all > "$LOG_DIR/orchestrator.log" 2>&1 &
        PID=$!
        echo "Started background process: PID $PID"
        echo "$PID" > "$LOG_DIR/orchestrator.pid"
        echo ""
        echo "To stop: kill $PID"
        ;;
    
    --step)
        STEP_NUM="${2:-1}"
        echo "Running step $STEP_NUM in background..."
        nohup python full_reproduction_orchestrator.py --step "$STEP_NUM" > "$LOG_DIR/orchestrator.log" 2>&1 &
        PID=$!
        echo "Started background process: PID $PID"
        echo "$PID" > "$LOG_DIR/orchestrator.pid"
        ;;
    
    --resume)
        echo "Resuming from last checkpoint..."
        nohup python full_reproduction_orchestrator.py --resume > "$LOG_DIR/orchestrator.log" 2>&1 &
        PID=$!
        echo "Started background process: PID $PID"
        echo "$PID" > "$LOG_DIR/orchestrator.pid"
        ;;
    
    --status)
        python full_reproduction_orchestrator.py --status
        ;;
    
    --list)
        python full_reproduction_orchestrator.py --list
        ;;
    
    --stop)
        PID_FILE="$LOG_DIR/orchestrator.pid"
        if [[ -f "$PID_FILE" ]]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "Stopping process $PID..."
                kill "$PID"
                rm -f "$PID_FILE"
                echo "Stopped."
            else
                echo "Process $PID is not running."
                rm -f "$PID_FILE"
            fi
        else
            echo "No PID file found."
        fi
        ;;
    
    --foreground)
        # Run in foreground (for debugging)
        STEP="${2:-}"
        if [[ -n "$STEP" ]]; then
            python full_reproduction_orchestrator.py --step "$STEP"
        else
            python full_reproduction_orchestrator.py --all
        fi
        ;;
    
    --help|*)
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  --all          Run all steps in background (4-5 days)"
        echo "  --step N       Run specific step N in background"
        echo "  --resume       Resume from last checkpoint"
        echo "  --status       Show current status"
        echo "  --list         List all steps"
        echo "  --stop         Stop background process"
        echo "  --foreground   Run in foreground (for debugging)"
        echo ""
        echo "Monitoring:"
        echo "  tail -f $LOG_DIR/master.log           # Overall progress"
        echo "  tail -f $LOG_DIR/step1_*.log          # Step-specific logs"
        echo "  ls $LOG_DIR/../alerts/                # Check for alerts"
        echo ""
        echo "Alert Handling:"
        echo "  When a discrepancy is detected, the orchestrator pauses"
        echo "  and creates an alert file in /tmp/hafiscal_full_repro/alerts/"
        echo "  Review the alert, investigate, then run --resume to continue."
        ;;
esac
