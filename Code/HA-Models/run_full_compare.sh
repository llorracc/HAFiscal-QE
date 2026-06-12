#!/bin/bash
# Full comparison script for HAFiscal 0.14.1-bugfixed vs 0.17.0-native-adjusted
#
# Usage:
#   ./run_full_compare.sh              # Run all steps (4-5 days)
#   ./run_full_compare.sh --step 1     # Run only step 1 (~1 hour)
#   ./run_full_compare.sh --quick      # Quick mode (~1 hour total)
#
# Steps:
#   1: Splurge estimation (~30 min each)
#   2: Discount factor estimation (~48 hours each)
#   3: Robustness Splurge=0 (optional)
#   4: HANK/SAM Jacobians (~12 hours each)
#   5: Policy comparisons (~12 hours each)
#
# Output: /tmp/hafiscal_full_compare/

cd /home/econ-ark/GitHub/llorracc/HAFiscal-Latest/Code/HA-Models

echo "========================================"
echo "HAFiscal Full Reproduction Comparison"
echo "========================================"
echo ""
echo "This compares:"
echo "  - 0.14.1-bugfixed (with KinkedR fix)"
echo "  - 0.17.0-native-adjusted (with sequential execution)"
echo ""

# Run the comparison
python full_compare.py "$@"

exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo "✅ Full comparison PASSED - outputs match"
else
    echo "⚠️ Full comparison found DIFFERENCES"
    echo "Check /tmp/hafiscal_full_compare/ for details"
fi

exit $exit_code
