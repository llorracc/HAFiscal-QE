#!/bin/bash

set -euo pipefail

# MICRO Level Computation - Fast verification (~2 minutes)
# Tests agent creation, solve, and simulation

# Get the absolute path of the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source environment setup
source "$SCRIPT_DIR/reproduce_environment.sh"

# Force non-interactive matplotlib backend
export MATPLOTLIB_BACKEND=Agg
export MPLBACKEND=Agg

echo "========================================"
echo "MICRO Level Computational Verification"
echo "========================================"
echo ""
echo "This is a fast verification level (~2 minutes)"
echo "Testing: Agent creation, solve, and simulation"
echo ""

# Change to code directory
cd "$PROJECT_ROOT/Code/HA-Models/FromPandemicCode"

# Run the micro-level comparison
python "$SCRIPT_DIR/hark_version_comparison.py" --level micro --code-dir "$(pwd)"

echo ""
echo "========================================"
echo "MICRO Level Complete"
echo "========================================"
