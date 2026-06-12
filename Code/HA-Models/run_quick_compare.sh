#!/bin/bash
# Quick comparison script for HAFiscal validation
# Usage: ./run_quick_compare.sh
#
# This runs in ~30 seconds and tests:
# - Solver: consumption function values
# - Simulation: wealth distributions  
# - MPC: marginal propensity to consume calculations
# - Objective: estimation target calculations
#
# Exit code 0 = all match, 1 = differences detected

cd /home/econ-ark/GitHub/llorracc/HAFiscal-Latest/Code/HA-Models

echo "========================================"
echo "HAFiscal Quick Validation"
echo "========================================"
echo ""

python quick_compare.py

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ Quick validation PASSED"
else
    echo ""
    echo "⚠️ Quick validation found DIFFERENCES"
    echo "Check /tmp/hafiscal_quick_compare/ for details"
fi

exit $exit_code
