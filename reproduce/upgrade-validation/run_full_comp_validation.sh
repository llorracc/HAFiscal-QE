#!/bin/bash
# =============================================================================
# HAFiscal Full Computation Validation Script (--comp full)
# 
# This script validates the HARK 0.17.0 migration by running the complete
# computational pipeline and comparing numerical outputs.
#
# IMPORTANT:
# - This takes 4-5 DAYS to complete (migration-era figure, 2026-01 full-MC
#   validation runs; Step-5a measured 9.45h forked-AD at Baseline, 2026-06-11
#   — see Code/HA-Models/README.md)
# - Run in an external terminal (not Cursor) for reliability
# - Results from --comp min validation are preserved separately
#
# Usage (in external terminal):
#   cd /home/econ-ark/GitHub/llorracc/HAFiscal-Latest/reproduce/upgrade-validation
#   nohup ./run_full_comp_validation.sh > /tmp/hafiscal_full_validation.log 2>&1 &
#   disown
#
# Or with tmux:
#   tmux new -s hafiscal-full
#   ./run_full_comp_validation.sh
#   # Ctrl+B, D to detach
#
# Monitor progress:
#   tail -f /tmp/hafiscal_full_validation.log
#   cat /tmp/hafiscal_full_validation_status.txt
#
# NOTE: Progress-reporting additions (profiler logs, heartbeat files, etc.) 
# are INFORMATIONAL ONLY and do not affect numerical validation.
# =============================================================================

set -e  # Exit on error (but we'll trap errors)

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="/tmp/hafiscal_full_validation.log"
STATUS_FILE="/tmp/hafiscal_full_validation_status.txt"
RESULTS_DIR="$SCRIPT_DIR/results_full_$TIMESTAMP"

# Meaningful difference threshold (0.02 log points = ~2%)
THRESHOLD=0.02

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
    log "============================================================"
    log "ERROR on line $line_no (exit code: $error_code)"
    log "============================================================"
    status "FAILED at line $line_no with error $error_code - check log for details"
    
    # Try to capture partial results
    if [ -d "$RESULTS_DIR" ]; then
        log "Attempting to capture partial snapshot..."
        cd "$SCRIPT_DIR"
        python3 capture_snapshot.py \
            --output "$RESULTS_DIR/snapshot_partial_error" \
            --notes "Partial snapshot after error at line $line_no" 2>/dev/null || true
    fi
    
    exit $error_code
}

trap 'error_handler ${LINENO} $?' ERR

# Progress reporting function
report_progress() {
    local phase=$1
    local detail=$2
    local elapsed_hours=$(( ($(date +%s) - START_TIME) / 3600 ))
    local elapsed_mins=$(( (($(date +%s) - START_TIME) % 3600) / 60 ))
    
    status "Phase $phase: $detail (elapsed: ${elapsed_hours}h ${elapsed_mins}m)"
}

# =============================================================================
# Initialize
# =============================================================================
mkdir -p "$RESULTS_DIR"
echo "" > "$LOG_FILE"
START_TIME=$(date +%s)

log "============================================================"
log "HAFiscal FULL Computation Validation"
log "============================================================"
log ""
log "Timestamp: $TIMESTAMP"
log "Project root: $PROJECT_ROOT"
log "Results directory: $RESULTS_DIR"
log "Threshold: $THRESHOLD log points (~$(echo "$THRESHOLD * 100" | bc)%)"
log ""
log "IMPORTANT: This takes 4-5 DAYS to complete (migration-era figure; see Code/HA-Models/README.md)."
log "Monitor with: tail -f $LOG_FILE"
log "Quick status: cat $STATUS_FILE"
log ""
log "Note: Progress/profiler output is informational only,"
log "      not used for numerical validation."
log ""

# =============================================================================
# Phase 1: Verify --comp min results exist (for reference)
# =============================================================================
status "Phase 1/5: Verifying --comp min results exist..."

COMP_MIN_RESULTS=$(ls -td "$SCRIPT_DIR"/results_202* 2>/dev/null | head -1)
if [ -n "$COMP_MIN_RESULTS" ] && [ -d "$COMP_MIN_RESULTS" ]; then
    log "Found --comp min results at: $COMP_MIN_RESULTS"
    log "These will be preserved (not overwritten)."
    
    # Copy reference to new results dir
    echo "$COMP_MIN_RESULTS" > "$RESULTS_DIR/comp_min_reference.txt"
else
    log "WARNING: No --comp min results found. Proceeding anyway."
fi

# =============================================================================
# Phase 2: Capture CURRENT state snapshot (before full run)
# =============================================================================
report_progress "2/5" "Capturing pre-run snapshot..."

log ""
log "Capturing current results snapshot (before --comp full)..."
cd "$SCRIPT_DIR"

# Check if we have existing results to snapshot
RESULT_FILE="$PROJECT_ROOT/Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt"
if [ -f "$RESULT_FILE" ]; then
    python3 capture_snapshot.py \
        --output "$RESULTS_DIR/snapshot_before" \
        --notes "Pre-full-run snapshot at $TIMESTAMP"
    log "Pre-run snapshot saved to: $RESULTS_DIR/snapshot_before"
    
    # Show what was captured
    log "Captured estimation results:"
    cat "$RESULTS_DIR/snapshot_before/estimation_results.json" | head -20
else
    log "No existing results found - this appears to be a fresh run"
    mkdir -p "$RESULTS_DIR/snapshot_before"
    echo '{"note": "No pre-existing results"}' > "$RESULTS_DIR/snapshot_before/metadata.json"
fi

# =============================================================================
# Phase 3: Run ./reproduce.sh --comp full
# =============================================================================
report_progress "3/5" "Running ./reproduce.sh --comp full (4-5 days; migration-era figure)..."

log ""
log "============================================================"
log "STARTING: ./reproduce.sh --comp full"
log "============================================================"
log ""
log "Expected duration: 4-5 days (as of the 2026-01 migration-validation MC runs)"
log "  - Step 1 (splurge estimation): ~20 minutes"
log "  - Step 2 (discount factors): ~21 hours (2026-01 migration-era MC figure)"
log "  - Step 3 (Splurge=0 robustness): ~21 hours (2026-01 migration-era MC figure)"
log "  - Step 4 (HANK-SAM): ~1 hour"
log "  - Step 5 (policy analysis): ~65 hours (migration-era MC figure; Step-5a measured 9.45h forked-AD at Baseline, 2026-06-11 — see Code/HA-Models/README.md)"
log ""
log "Progress will be logged here. You can also monitor:"
log "  - Profiler status: cat /tmp/hafiscal_status.json"
log "  - Heartbeat: cat /tmp/hafiscal_heartbeat"
log "  - Detailed timing: cat /tmp/hafiscal_timing.json"
log ""

cd "$PROJECT_ROOT"

# Deactivate any conda environment
if [ -n "$CONDA_DEFAULT_ENV" ]; then
    log "Deactivating conda environment: $CONDA_DEFAULT_ENV"
    conda deactivate 2>/dev/null || true
fi

# Run the full computation with output to both log and results
COMP_START=$(date +%s)
./reproduce.sh --comp full 2>&1 | tee "$RESULTS_DIR/comp_full_output.log"
COMP_END=$(date +%s)
COMP_DURATION=$(( (COMP_END - COMP_START) / 3600 ))

log ""
log "============================================================"
log "COMPLETED: ./reproduce.sh --comp full"
log "Duration: approximately $COMP_DURATION hours"
log "============================================================"
log ""

# =============================================================================
# Phase 4: Capture post-run snapshot
# =============================================================================
report_progress "4/5" "Capturing post-run snapshot..."

cd "$SCRIPT_DIR"
python3 capture_snapshot.py \
    --output "$RESULTS_DIR/snapshot_after" \
    --notes "Post-full-run snapshot at $(date +%Y%m%d-%H%M%S), duration: ${COMP_DURATION}h"
log "Post-run snapshot saved to: $RESULTS_DIR/snapshot_after"

# =============================================================================
# Phase 5: Compare snapshots
# =============================================================================
report_progress "5/5" "Comparing numerical results..."

log ""
log "============================================================"
log "Comparing before vs after snapshots"
log "Threshold: $THRESHOLD log points"
log "============================================================"
log ""

# Run comparison
COMPARE_OUTPUT="$RESULTS_DIR/comparison_output.txt"
COMPARE_REPORT="$RESULTS_DIR/comparison_report.md"

python3 compare_results.py \
    --baseline "$RESULTS_DIR/snapshot_before" \
    --attempt "$RESULTS_DIR/snapshot_after" \
    --output "$COMPARE_REPORT" \
    --threshold "$THRESHOLD" \
    2>&1 | tee "$COMPARE_OUTPUT"

COMPARE_EXIT=$?

# =============================================================================
# Final Summary
# =============================================================================
log ""
log "============================================================"
log "VALIDATION COMPLETE"
log "============================================================"
log ""

TOTAL_HOURS=$(( ($(date +%s) - START_TIME) / 3600 ))
TOTAL_MINS=$(( (($(date +%s) - START_TIME) % 3600) / 60 ))

if [ $COMPARE_EXIT -eq 0 ]; then
    log "RESULT: ✅ VALIDATION PASSED"
    log ""
    log "All numerical outputs are within the $THRESHOLD log-point tolerance."
    log "The HARK 0.17.0 migration is fully validated for --comp full."
    status "COMPLETED: VALIDATION PASSED (${TOTAL_HOURS}h ${TOTAL_MINS}m)"
else
    log "RESULT: 🛑 MEANINGFUL DIFFERENCES DETECTED"
    log ""
    log "Some numerical outputs exceed the $THRESHOLD log-point threshold."
    log "Review the comparison report for details:"
    log "  $COMPARE_REPORT"
    log ""
    log "ACTION REQUIRED: Analyze differences before proceeding."
    status "PAUSED: Meaningful differences found - review $COMPARE_REPORT"
fi

log ""
log "Results saved to: $RESULTS_DIR"
log ""
log "Files created:"
ls -la "$RESULTS_DIR" | tee -a "$LOG_FILE"
log ""
log "Total duration: ${TOTAL_HOURS} hours ${TOTAL_MINS} minutes"
log "Finished at: $(date)"
log ""
log "To review comparison:"
log "  cat $COMPARE_REPORT"
log ""
log "To compare with --comp min results:"
if [ -n "$COMP_MIN_RESULTS" ]; then
    log "  diff $COMP_MIN_RESULTS/snapshot_after/estimation_results.json $RESULTS_DIR/snapshot_after/estimation_results.json"
fi
