#!/bin/bash
# HAFiscal Quicktest Runner
#
# Runs lightweight validation tests comparing 0.14.1 and 0.17.0 codebases.
#
# Usage:
#   ./run_quicktest.sh [--all|--step N|--list|--status]
#
# Monitor progress:
#   tail -f /tmp/hafiscal_quicktest/logs/quicktest_master.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUICKTEST_DIR="/tmp/hafiscal_quicktest"
LOG_DIR="${QUICKTEST_DIR}/logs"

# Ensure directories exist
mkdir -p "${LOG_DIR}"

# Export quicktest mode
export QUICKTEST=1
export MATPLOTLIB_BACKEND=Agg

echo "=========================================="
echo "  HAFiscal Quicktest Validation"
echo "=========================================="
echo ""
echo "Tolerance: 1% (0.01 log points)"
echo "Monitor: tail -f ${LOG_DIR}/quicktest_master.log"
echo ""

# Check for help
if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --all       Run all quicktest steps"
    echo "  --step N    Run specific step N"
    echo "  --list      List available steps"
    echo "  --status    Show status of completed steps"
    echo ""
    exit 0
fi

# Find Python with quicktest modules
if [[ -f "${SCRIPT_DIR}/.venv/bin/python" ]]; then
    PYTHON="${SCRIPT_DIR}/.venv/bin/python"
elif [[ -f "${SCRIPT_DIR}/venv/bin/python" ]]; then
    PYTHON="${SCRIPT_DIR}/venv/bin/python"
else
    PYTHON="python3"
fi

echo "Using Python: ${PYTHON}"
echo ""

# Run orchestrator
cd "${SCRIPT_DIR}"
exec ${PYTHON} quicktest_orchestrator.py "$@"
