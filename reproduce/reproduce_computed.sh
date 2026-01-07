#!/bin/bash

set -euo pipefail

# Resolve paths robustly (works even if invoked from outside repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Make sure the necessary requirements are available
source "$SCRIPT_DIR/reproduce_environment.sh"

# Change directory to the location of the Python script
cd "$PROJECT_ROOT/Code/HA-Models"

# Create empty version file for full reproduction
rm -f version
touch version

# Pass HAFISCAL_RUN_STEP_3 environment variable if set
# (defaults to false in do_all.py if not set)
export HAFISCAL_RUN_STEP_3="${HAFISCAL_RUN_STEP_3:-false}"

# Run the Python script
# NOTE: With 'set -e', any failure here aborts the script, preventing
# the PREGENERATED flag from being removed on a failed computation.
python do_all.py

# =============================================================================
# REMOVE PREGENERATED FLAG AFTER SUCCESSFUL COMPUTATION
# =============================================================================
# After computational results are regenerated, remove the flag file that
# triggers PREGENERATED markers in table/figure captions.

FLAG_FILE="$PROJECT_ROOT/reproduce/.results_pregenerated"

if [[ -f "$FLAG_FILE" ]]; then
    echo ""
    echo "========================================"
    echo "✅ Computation Complete"
    echo "========================================"
    echo ""
    echo "Removing PREGENERATED flag file..."
    rm -f "$FLAG_FILE"
    echo "✓ Flag removed - table/figure captions will no longer show PREGENERATED markers"
    echo "  (Recompile HAFiscal.tex to see updated captions)"
    echo ""
else
    echo ""
    echo "ℹ️  No PREGENERATED flag file found (already removed or never created)"
    echo ""
fi
