#!/bin/bash
#
# Watch for alerts during full reproduction comparison
#
# This script monitors the alert directory and prints new alerts as they appear.
# Useful for AI agents or users who want to be notified of discrepancies.
#
# Usage:
#   ./watch_reproduction.sh           # Watch for alerts
#   ./watch_reproduction.sh --check   # Check current status and exit
#

set -e

ALERT_DIR="/tmp/hafiscal_full_repro/alerts"
LOG_DIR="/tmp/hafiscal_full_repro/logs"
CHECKPOINT_DIR="/tmp/hafiscal_full_repro/checkpoints"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_status() {
    echo "============================================================"
    echo "HAFiscal Full Reproduction - Status Check"
    echo "============================================================"
    echo ""
    
    # Check if orchestrator is running
    PID_FILE="$LOG_DIR/orchestrator.pid"
    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "${GREEN}✅ Orchestrator is running (PID: $PID)${NC}"
        else
            echo -e "${YELLOW}⚠️  Orchestrator is NOT running (stale PID file)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Orchestrator is NOT running (no PID file)${NC}"
    fi
    echo ""
    
    # Check step completion
    echo "Step Status:"
    for i in 1 2 3 4 5; do
        CHECKPOINT="$CHECKPOINT_DIR/step${i}_checkpoint.json"
        if [[ -f "$CHECKPOINT" ]]; then
            COMPLETED=$(jq -r '.completed_at // "unknown"' "$CHECKPOINT" 2>/dev/null || echo "unknown")
            echo -e "  Step $i: ${GREEN}✅ Completed${NC} at $COMPLETED"
        else
            echo -e "  Step $i: ⏳ Not completed"
        fi
    done
    echo ""
    
    # Check paused state
    PAUSED_FILE="$CHECKPOINT_DIR/paused_state.json"
    if [[ -f "$PAUSED_FILE" ]]; then
        PAUSED_STEP=$(jq -r '.paused_at_step // "unknown"' "$PAUSED_FILE" 2>/dev/null || echo "unknown")
        PAUSED_REASON=$(jq -r '.reason // "unknown"' "$PAUSED_FILE" 2>/dev/null || echo "unknown")
        echo -e "${RED}🛑 PAUSED at step $PAUSED_STEP${NC}"
        echo "   Reason: $PAUSED_REASON"
        echo ""
    fi
    
    # Check alerts
    if [[ -d "$ALERT_DIR" ]]; then
        ALERT_COUNT=$(ls -1 "$ALERT_DIR"/*.txt 2>/dev/null | wc -l)
        if [[ $ALERT_COUNT -gt 0 ]]; then
            echo -e "${RED}🚨 $ALERT_COUNT ALERT(S) FOUND:${NC}"
            for alert in "$ALERT_DIR"/*.txt; do
                if [[ -f "$alert" ]]; then
                    echo "   - $(basename "$alert")"
                fi
            done
            echo ""
            echo "To view latest alert:"
            echo "   cat $(ls -t "$ALERT_DIR"/*.txt 2>/dev/null | head -1)"
        else
            echo -e "${GREEN}✅ No alerts${NC}"
        fi
    else
        echo -e "${GREEN}✅ No alerts (directory doesn't exist)${NC}"
    fi
    echo ""
    
    # Show log tail
    if [[ -f "$LOG_DIR/master.log" ]]; then
        echo "Recent log entries:"
        echo "---"
        tail -10 "$LOG_DIR/master.log"
        echo "---"
    fi
}

watch_alerts() {
    echo "============================================================"
    echo "Watching for alerts..."
    echo "Press Ctrl+C to stop"
    echo "============================================================"
    echo ""
    
    mkdir -p "$ALERT_DIR"
    
    # Track which alerts we've seen
    SEEN_ALERTS=""
    
    while true; do
        # Check for new alerts
        if [[ -d "$ALERT_DIR" ]]; then
            for alert in "$ALERT_DIR"/*.txt; do
                if [[ -f "$alert" ]]; then
                    ALERT_NAME=$(basename "$alert")
                    if [[ ! "$SEEN_ALERTS" =~ "$ALERT_NAME" ]]; then
                        echo ""
                        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
                        echo -e "${RED}🚨 NEW ALERT: $ALERT_NAME${NC}"
                        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
                        echo ""
                        cat "$alert"
                        echo ""
                        SEEN_ALERTS="$SEEN_ALERTS $ALERT_NAME"
                    fi
                fi
            done
        fi
        
        # Check paused state
        if [[ -f "$CHECKPOINT_DIR/paused_state.json" ]]; then
            if [[ ! -f "/tmp/.reproduction_paused_notified" ]]; then
                echo ""
                echo -e "${YELLOW}⏸️  REPRODUCTION PAUSED - Check alerts above${NC}"
                touch "/tmp/.reproduction_paused_notified"
            fi
        else
            rm -f "/tmp/.reproduction_paused_notified"
        fi
        
        sleep 5
    done
}

# Parse arguments
case "${1:-}" in
    --check)
        check_status
        ;;
    --watch|"")
        check_status
        echo ""
        watch_alerts
        ;;
    *)
        echo "Usage: $0 [--check|--watch]"
        echo ""
        echo "  --check  Check status and exit"
        echo "  --watch  Watch for alerts continuously (default)"
        ;;
esac
