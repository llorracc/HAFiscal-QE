#!/bin/bash

# Get the absolute path of the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Make sure the necessary requirements are available
source "$SCRIPT_DIR/reproduce_environment.sh"

# Change directory to the location of the Python script
cd "$PROJECT_ROOT/Code/HA-Models" || exit

# Check for required .obj files created by full computational reproduction
REQUIRED_FILES=(
    "FromPandemicCode/HA_Fiscal_Jacs.obj"
    "FromPandemicCode/HA_Fiscal_Jacs_UI_extend_real.obj"
)

MISSING_FILES=()
for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        MISSING_FILES+=("$file")
    fi
done

if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
    echo "========================================"
    echo "❌ ERROR: Required Files Missing"
    echo "========================================"
    echo ""
    echo "The minimal computational reproduction requires pre-computed object files"
    echo "from the full computational reproduction. The following files are missing:"
    echo ""
    for file in "${MISSING_FILES[@]}"; do
        echo "  • $file"
    done
    echo ""
    echo "To generate these files, you must first run the full computational reproduction:"
    echo ""
    echo "  ./reproduce.sh --comp full"
    echo ""
    echo "or directly:"
    echo ""
    echo "  ./reproduce/reproduce_computed.sh"
    echo ""
    echo "Note: This will take 3-4 days on a high-end 2025 laptop to complete."
    echo ""
    echo "The minimal reproduction (--comp min) is designed to quickly verify"
    echo "results using pre-computed Jacobians from the full run."
    echo ""
    exit 1
fi

echo "✅ All required .obj files found. Proceeding with minimal reproduction..."
echo ""

# Create version file with '_min' for minimal reproduction
rm -f version
echo "_min" > version

# List of tables to manage
TABLES=(
    "Target_AggMPCX_LiquWealth/Figures/MPC_WealthQuartiles_Table.tex"
    "FromPandemicCode/Tables/CRRA2/Multiplier.tex"
    "FromPandemicCode/Tables/CRRA2/welfare6.tex"
    "FromPandemicCode/Tables/Splurge0/welfare6_SplurgeComp.tex"
    "FromPandemicCode/Tables/Splurge0/Multiplier_SplurgeComp.tex"
)

# Create backups of original tables
python3 "$SCRIPT_DIR/stash-tables-during-comp-min-run.py" "$PROJECT_ROOT" backup "${TABLES[@]}"

# Run the minimal reproduction script
python reproduce_min.py

# Rename newly created tables to have _min suffix
python3 "$SCRIPT_DIR/stash-tables-during-comp-min-run.py" "$PROJECT_ROOT" rename_min "${TABLES[@]}"

# Restore original tables
python3 "$SCRIPT_DIR/stash-tables-during-comp-min-run.py" "$PROJECT_ROOT" restore "${TABLES[@]}"
