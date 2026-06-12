#!/bin/bash
# =============================================================================
# HAFiscal Parallel Validation Launcher
# =============================================================================
# Runs HARK 0.14.1 and 0.17.0 versions in parallel, comparing after each step.
# Sends email notification when divergence is detected.
#
# Usage:
#   ./run_parallel_validation.sh [--start-step N] [--dry-run]
#
# Monitoring:
#   tail -f /tmp/hafiscal_parallel_validation.log
#   cat /tmp/hafiscal_parallel_validation_status.json
#
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Validation directories
CLONE_0141="/home/econ-ark/GitHub/llorracc/HAFiscal-validation-0.14.1"
CLONE_0170="/home/econ-ark/GitHub/llorracc/HAFiscal-validation-0.17.0"

LOG_FILE="/tmp/hafiscal_parallel_validation.log"
STATUS_FILE="/tmp/hafiscal_parallel_validation_status.json"

# Check that clones exist
if [[ ! -d "$CLONE_0141" ]]; then
    echo "ERROR: HARK 0.14.1 validation clone not found at $CLONE_0141"
    echo "Please run the setup first."
    exit 1
fi

if [[ ! -d "$CLONE_0170" ]]; then
    echo "ERROR: HARK 0.17.0 validation clone not found at $CLONE_0170"
    echo "Please run the setup first."
    exit 1
fi

# Copy necessary files to clones
echo "Setting up validation environment..."

# Create directories
mkdir -p "$CLONE_0141/reproduce/upgrade-validation"
mkdir -p "$CLONE_0170/reproduce/upgrade-validation"

# Copy step_runner.py to both clones
cp "$SCRIPT_DIR/step_runner.py" "$CLONE_0141/reproduce/upgrade-validation/"
cp "$SCRIPT_DIR/step_runner.py" "$CLONE_0170/reproduce/upgrade-validation/"

echo ""
echo "=============================================="
echo "HAFiscal Parallel Validation"
echo "=============================================="
echo ""
echo "HARK 0.14.1 clone: $CLONE_0141"
echo "HARK 0.17.0 clone: $CLONE_0170"
echo ""
echo "Monitoring commands:"
echo "  Log:    tail -f $LOG_FILE"
echo "  Status: watch -n5 'cat $STATUS_FILE | python3 -m json.tool 2>/dev/null || cat $STATUS_FILE'"
echo ""
echo "Starting validation..."
echo ""

# Initialize log
echo "============================================" > "$LOG_FILE"
echo "HAFiscal Parallel Validation Started" >> "$LOG_FILE"
echo "Time: $(date -Iseconds)" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

# Run the Python orchestrator
cd "$PROJECT_ROOT"
python3 "$SCRIPT_DIR/parallel_validation.py" "$@" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=$?

echo ""
echo "=============================================="
if [[ $EXIT_CODE -eq 0 ]]; then
    echo "VALIDATION COMPLETE - ALL STEPS PASSED"
else
    echo "VALIDATION STOPPED - Check log for details"
fi
echo "=============================================="
echo ""
echo "Results saved to: /tmp/hafiscal_parallel_validation/"
echo "Log file: $LOG_FILE"

exit $EXIT_CODE
