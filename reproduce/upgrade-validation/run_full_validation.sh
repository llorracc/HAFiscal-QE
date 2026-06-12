#!/bin/bash
# =============================================================================
# HAFiscal Full Validation Script
# 
# This script runs the complete validation workflow in the background.
# It continues running even if the AI connection drops.
#
# Usage:
#   nohup ./run_full_validation.sh > /tmp/hafiscal_validation.log 2>&1 &
#
# Monitor progress:
#   tail -f /tmp/hafiscal_validation.log
#   tail -f /tmp/hafiscal_validation_status.txt
# =============================================================================

set -e  # Exit on error (but we'll trap errors)

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="/tmp/hafiscal_validation.log"
STATUS_FILE="/tmp/hafiscal_validation_status.txt"
RESULTS_DIR="$SCRIPT_DIR/results_$TIMESTAMP"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

status() {
    echo "$1" > "$STATUS_FILE"
    log "STATUS: $1"
}

error_handler() {
    local line_no=$1
    local error_code=$2
    log "ERROR on line $line_no (exit code: $error_code)"
    status "FAILED at line $line_no with error $error_code"
    exit $error_code
}

trap 'error_handler ${LINENO} $?' ERR

# Initialize
mkdir -p "$RESULTS_DIR"
echo "" > "$LOG_FILE"

log "============================================================"
log "HAFiscal Full Validation - Started"
log "============================================================"
log "Timestamp: $TIMESTAMP"
log "Project root: $PROJECT_ROOT"
log "Results directory: $RESULTS_DIR"
log ""

# =============================================================================
# Phase 1: Capture CURRENT state snapshot (before any new runs)
# =============================================================================
status "Phase 1: Capturing current state snapshot..."

log "Capturing current results snapshot..."
cd "$SCRIPT_DIR"

# Check if we have existing results to snapshot
if [ -f "$PROJECT_ROOT/Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt" ]; then
    python3 capture_snapshot.py \
        --output "$RESULTS_DIR/snapshot_before" \
        --notes "Pre-validation snapshot at $TIMESTAMP"
    log "Snapshot saved to: $RESULTS_DIR/snapshot_before"
else
    log "No existing results found, skipping pre-snapshot"
fi

# =============================================================================
# Phase 2: Run fresh --comp min
# =============================================================================
status "Phase 2: Running ./reproduce.sh --comp min (this takes ~2 hours)..."

log ""
log "============================================================"
log "Running: ./reproduce.sh --comp min"
log "This typically takes 1.5-2 hours..."
log "============================================================"
log ""

cd "$PROJECT_ROOT"

# Deactivate any conda environment
if [ -n "$CONDA_DEFAULT_ENV" ]; then
    log "Deactivating conda environment: $CONDA_DEFAULT_ENV"
    conda deactivate 2>/dev/null || true
fi

# Run the computation
START_TIME=$(date +%s)
./reproduce.sh --comp min 2>&1 | tee "$RESULTS_DIR/comp_min_output.log"
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

log ""
log "Computation completed in $((DURATION / 60)) minutes"
log ""

# =============================================================================
# Phase 3: Capture post-run snapshot
# =============================================================================
status "Phase 3: Capturing post-run snapshot..."

cd "$SCRIPT_DIR"
python3 capture_snapshot.py \
    --output "$RESULTS_DIR/snapshot_after" \
    --notes "Post-validation snapshot at $(date +%Y%m%d-%H%M%S)"
log "Snapshot saved to: $RESULTS_DIR/snapshot_after"

# =============================================================================
# Phase 4: Compare snapshots (if we had a before snapshot)
# =============================================================================
status "Phase 4: Comparing results..."

if [ -d "$RESULTS_DIR/snapshot_before" ]; then
    log ""
    log "============================================================"
    log "Comparing before vs after snapshots"
    log "============================================================"
    log ""
    
    python3 compare_results.py \
        --baseline "$RESULTS_DIR/snapshot_before" \
        --attempt "$RESULTS_DIR/snapshot_after" \
        --output "$RESULTS_DIR/comparison_report.md" \
        --threshold 0.02 \
        2>&1 | tee "$RESULTS_DIR/comparison_output.txt"
    
    COMPARE_EXIT=$?
    
    if [ $COMPARE_EXIT -eq 0 ]; then
        log ""
        log "============================================================"
        log "VALIDATION PASSED - All metrics within tolerance"
        log "============================================================"
        status "COMPLETED: VALIDATION PASSED"
    else
        log ""
        log "============================================================"
        log "VALIDATION PAUSED - Meaningful differences detected"
        log "Review: $RESULTS_DIR/comparison_report.md"
        log "============================================================"
        status "PAUSED: Meaningful differences found - review needed"
    fi
else
    log "No pre-snapshot available, showing current results only"
    
    # Extract key values for summary
    RESULT_FILE="$PROJECT_ROOT/Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt"
    if [ -f "$RESULT_FILE" ]; then
        log ""
        log "============================================================"
        log "Current Results (Result_AllTarget.txt):"
        log "============================================================"
        cat "$RESULT_FILE" | tee "$RESULTS_DIR/final_results.txt"
    fi
    status "COMPLETED: Fresh run finished, results captured"
fi

# =============================================================================
# Summary
# =============================================================================
log ""
log "============================================================"
log "VALIDATION COMPLETE"
log "============================================================"
log ""
log "Results saved to: $RESULTS_DIR"
log ""
log "Files created:"
ls -la "$RESULTS_DIR" | tee -a "$LOG_FILE"
log ""
log "To review:"
log "  - Full log: $LOG_FILE"
log "  - Status: $STATUS_FILE"
log "  - Results: $RESULTS_DIR/"
log ""
log "Finished at: $(date)"
