#!/bin/bash

set -euo pipefail

# MINI Level Computation - Intermediate verification (~5-10 minutes)
# Tests full setup, solve, simulation, and baseline experiment

# Get the absolute path of the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source environment setup
source "$SCRIPT_DIR/reproduce_environment.sh"

# Force non-interactive matplotlib backend
export MATPLOTLIB_BACKEND=Agg
export MPLBACKEND=Agg

echo "========================================"
echo "MINI Level Computational Verification"
echo "========================================"
echo ""
echo "This is an intermediate verification level (~5-10 minutes)"
echo "Testing: Full setup, solve, simulation, and baseline experiment"
echo ""

# Change to code directory
cd "$PROJECT_ROOT/Code/HA-Models/FromPandemicCode"

# Run the mini-level comparison
python "$SCRIPT_DIR/hark_version_comparison.py" --level mini --code-dir "$(pwd)"

echo ""
echo "========================================"
echo "MINI Level Complete"
echo "========================================"
