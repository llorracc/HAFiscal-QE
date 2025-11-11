#!/bin/bash

# Make sure the necessary requirements are available
source ./reproduce/reproduce_environment.sh

# Change directory to the location of the Python script
cd Code/HA-Models || exit

# Create empty version file for full reproduction
rm -f version
touch version

# Pass HAFISCAL_RUN_STEP_3 environment variable if set
# (defaults to false in do_all.py if not set)
export HAFISCAL_RUN_STEP_3="${HAFISCAL_RUN_STEP_3:-false}"

# Run the Python script
python do_all.py

# =============================================================================
# REMOVE PREGENERATED FLAG AFTER SUCCESSFUL COMPUTATION
# =============================================================================
# After computational results are regenerated, remove the flag file that
# triggers PREGENERATED markers in table captions.

FLAG_FILE="./.results_pregenerated"

if [[ -f "$FLAG_FILE" ]]; then
    echo ""
    echo "========================================"
    echo "✅ Computation Complete"
    echo "========================================"
    echo ""
    echo "Removing PREGENERATED flag file..."
    rm -f "$FLAG_FILE"
    echo "✓ Flag removed - table captions will no longer show PREGENERATED markers"
    echo "  (Recompile HAFiscal.tex to see updated captions)"
    echo ""
else
    echo ""
    echo "ℹ️  No PREGENERATED flag file found (already removed or never created)"
    echo ""
fi
