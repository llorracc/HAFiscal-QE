#!/bin/bash

set -euo pipefail

# NANO Level Computation - Fastest verification (~30 seconds)
# Tests agent creation and solve with minimal configuration

# Get the absolute path of the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source environment setup
source "$SCRIPT_DIR/reproduce_environment.sh"

# Force non-interactive matplotlib backend
export MATPLOTLIB_BACKEND=Agg
export MPLBACKEND=Agg

echo "========================================"
echo "NANO Level Computational Verification"
echo "========================================"
echo ""
echo "This is the fastest verification level (~30 seconds)"
echo "Testing: Agent creation and solve"
echo ""

# Change to code directory
cd "$PROJECT_ROOT/Code/HA-Models/FromPandemicCode"

# Run the nano-level comparison
python "$SCRIPT_DIR/hark_version_comparison.py" --level nano --code-dir "$(pwd)"

echo ""
echo "========================================"
echo "NANO Level Complete"
echo "========================================"
