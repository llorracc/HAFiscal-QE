#!/bin/bash

set -euo pipefail

# Get the absolute path of the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Make sure the necessary requirements are available
source "$SCRIPT_DIR/reproduce_environment.sh"

# Source the download helper functions
source "$SCRIPT_DIR/download_from_remote_branch.sh"

# Change directory to the location of the Python script
cd "$PROJECT_ROOT/Code/HA-Models"

# Force non-interactive matplotlib backend for headless environments
# This prevents TclError when running in terminals without display
export MATPLOTLIB_BACKEND=Agg
export MPLBACKEND=Agg

# Check for required files created by full computational reproduction
# Includes .obj files (Jacobians) and .txt files (estimation results)
REQUIRED_FILES=(
    "FromPandemicCode/HA_Fiscal_Jacs.obj"
    "FromPandemicCode/HA_Fiscal_Jacs_UI_extend_real.obj"
    "Target_AggMPCX_LiquWealth/Result_AllTarget.txt"
    "Target_AggMPCX_LiquWealth/Result_AllTarget_Splurge0.txt"
)

# Remote paths (relative to repo root)
REMOTE_PATHS=(
    "Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj"
    "Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs_UI_extend_real.obj"
    "Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt"
    "Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget_Splurge0.txt"
)

MISSING_FILES=()
MISSING_REMOTE_PATHS=()
for i in "${!REQUIRED_FILES[@]}"; do
    if [[ ! -f "${REQUIRED_FILES[$i]}" ]]; then
        MISSING_FILES+=("${REQUIRED_FILES[$i]}")
        MISSING_REMOTE_PATHS+=("${REMOTE_PATHS[$i]}")
    fi
done

# Track if we fetched files (for cleanup later)
FETCHED_PRECOMPUTED=false
DOWNLOADED_FILES=()

# List of tables to manage
TABLES=(
    "Target_AggMPCX_LiquWealth/Figures/MPC_WealthQuartiles_Table.tex"
    "FromPandemicCode/Tables/CRRA2/Multiplier.tex"
    "FromPandemicCode/Tables/CRRA2/welfare6.tex"
    "FromPandemicCode/Tables/Splurge0/welfare6_SplurgeComp.tex"
    "FromPandemicCode/Tables/Splurge0/Multiplier_SplurgeComp.tex"
)

BACKUP_DONE=false

cleanup() {
    local exit_code=$?

    # Prevent recursive traps
    trap - EXIT

    # Best-effort cleanup; do not mask the original failure
    set +e

    # Always attempt to restore tables if we took backups
    if [[ "$BACKUP_DONE" == "true" ]]; then
        python3 "$SCRIPT_DIR/stash-tables-during-comp-min-run.py" "$PROJECT_ROOT" restore "${TABLES[@]}" >/dev/null 2>&1 || true
    fi

    # Remove only the files we downloaded (do not delete user-provided local artifacts)
    if [[ "$FETCHED_PRECOMPUTED" == "true" && ${#DOWNLOADED_FILES[@]} -gt 0 ]]; then
        echo ""
        echo "→ Cleaning up downloaded precomputed files..."
        for file in "${DOWNLOADED_FILES[@]}"; do
            rm -f "$file" 2>/dev/null || true
            echo "  ✓ Removed $file"
        done
        echo "✅ Cleanup complete"
    fi

    exit "$exit_code"
}

trap cleanup EXIT

# If files are missing, download them from GitHub
if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
    echo "========================================"
    echo "📦 Downloading Precomputed Results"
    echo "========================================"
    echo ""
    echo "The minimal reproduction requires pre-computed .obj files."
    echo "Downloading from GitHub (${PRECOMPUTED_BRANCH} branch)..."
    echo ""

    ALL_DOWNLOADED=true

    for i in "${!MISSING_FILES[@]}"; do
        local_file="${MISSING_FILES[$i]}"
        remote_path="${MISSING_REMOTE_PATHS[$i]}"
        filename="$(basename "$local_file")"

        echo "→ Downloading ${filename}..."
        if download_from_branch "$remote_path" "$local_file"; then
            FILE_SIZE=$(du -h "$local_file" 2>/dev/null | cut -f1)
            echo "  ✓ ${local_file} ($FILE_SIZE)"
            DOWNLOADED_FILES+=("$local_file")
        else
            echo "  ✗ ${local_file} (FAILED)"
            ALL_DOWNLOADED=false
        fi
    done

    if [[ "$ALL_DOWNLOADED" == "true" ]]; then
        echo ""
        echo "✅ Successfully downloaded precomputed files"
        echo "   (These will be automatically cleaned up after reproduction)"
        echo ""
        FETCHED_PRECOMPUTED=true
    else
        echo ""
        echo "❌ ERROR: Some files could not be downloaded"
        echo ""
        echo "This may indicate:"
        echo "  • Network connectivity issues"
        echo "  • GitHub is temporarily unavailable"
        echo "  • The files don't exist on the '${PRECOMPUTED_BRANCH}' branch"
        echo ""
        echo "Alternative: Run the full computational reproduction:"
        echo "  ./reproduce.sh --comp full"
        echo ""
        echo "Note: This will take 4-5 days on a high-end 2025 laptop to complete."
        echo ""
        exit 1
    fi
fi

echo "✅ All required precomputed files found. Proceeding with minimal reproduction..."
echo ""

# Create version file with '_min' for minimal reproduction
rm -f version
echo "_min" > version

# Create backups of original tables
python3 "$SCRIPT_DIR/stash-tables-during-comp-min-run.py" "$PROJECT_ROOT" backup "${TABLES[@]}"
BACKUP_DONE=true

# Run the minimal reproduction script (fail-fast due to set -e)
python reproduce_min.py

# Rename newly created tables to have _min suffix
python3 "$SCRIPT_DIR/stash-tables-during-comp-min-run.py" "$PROJECT_ROOT" rename_min "${TABLES[@]}"

# Restore original tables
python3 "$SCRIPT_DIR/stash-tables-during-comp-min-run.py" "$PROJECT_ROOT" restore "${TABLES[@]}"
BACKUP_DONE=false

# Display prominent warning if we used precomputed artifacts
if [[ "$FETCHED_PRECOMPUTED" == "true" ]]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚠️  WARNING: PRECOMPUTED ARTIFACTS WERE USED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "This reproduction used pre-trained model objects (.obj files)"
    echo "that were downloaded from GitHub's '${PRECOMPUTED_BRANCH}' branch."
    echo ""
    echo "This means you have NOT run the full computational reproduction."
    echo ""
    echo "To run a complete, from-scratch reproduction:"
    echo "  ./reproduce.sh --comp full"
    echo ""
    echo "The full reproduction takes 4-5 days on a high-end 2025 laptop but provides complete verification"
    echo "of all computational results."
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi
