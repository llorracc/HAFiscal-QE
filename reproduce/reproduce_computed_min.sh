#!/bin/bash

# Get the absolute path of the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Make sure the necessary requirements are available
source "$SCRIPT_DIR/reproduce_environment.sh"

# Change directory to the location of the Python script
cd "$PROJECT_ROOT/Code/HA-Models" || exit

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
python3 "$SCRIPT_DIR/table_renamer.py" "$PROJECT_ROOT" backup "${TABLES[@]}"

# Run the minimal reproduction script
python reproduce_min.py

# Rename newly created tables to have _min suffix
python3 "$SCRIPT_DIR/table_renamer.py" "$PROJECT_ROOT" rename_min "${TABLES[@]}"

# Restore original tables
python3 "$SCRIPT_DIR/table_renamer.py" "$PROJECT_ROOT" restore "${TABLES[@]}"
