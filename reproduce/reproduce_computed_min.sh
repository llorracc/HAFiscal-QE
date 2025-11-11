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

# Track if we fetched files (for cleanup later)
FETCHED_PRECOMPUTED=false

# If files are missing, try to fetch from precomputed-results branch
if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
    # Check if precomputed-results branch exists (only in HAFiscal-QE repo)
    PRECOMPUTED_BRANCH="precomputed-results"
    REMOTE="${REMOTE:-origin}"
    
    # Check if we're in a git repository and if the precomputed branch exists
    if git rev-parse --git-dir > /dev/null 2>&1; then
        # Check for branch existence (try remote first, then local)
        BRANCH_EXISTS=false
        if git ls-remote --heads "$REMOTE" "$PRECOMPUTED_BRANCH" 2>/dev/null | grep -q "$PRECOMPUTED_BRANCH"; then
            BRANCH_EXISTS=true
            BRANCH_LOCATION="$REMOTE/$PRECOMPUTED_BRANCH"
        elif git show-ref --verify --quiet "refs/heads/$PRECOMPUTED_BRANCH"; then
            BRANCH_EXISTS=true
            BRANCH_LOCATION="$PRECOMPUTED_BRANCH"
        fi
        
        if [[ "$BRANCH_EXISTS" == "true" ]]; then
            echo "========================================"
            echo "📦 Fetching Precomputed Results"
            echo "========================================"
            echo ""
            echo "The minimal reproduction requires pre-computed .obj files."
            echo "Fetching them from the '$PRECOMPUTED_BRANCH' branch..."
            echo ""
            
            # Fetch the branch if it's remote
            if [[ "$BRANCH_LOCATION" == "$REMOTE/$PRECOMPUTED_BRANCH" ]]; then
                echo "→ Fetching $PRECOMPUTED_BRANCH from $REMOTE..."
                git fetch "$REMOTE" "$PRECOMPUTED_BRANCH" 2>/dev/null || true
            fi
            
            # Extract .obj files using git archive
            echo "→ Extracting precomputed .obj files..."
            cd "$PROJECT_ROOT" || exit
            if git archive "$BRANCH_LOCATION" Code/HA-Models 2>/dev/null | tar -x 2>/dev/null; then
                # Verify files were extracted
                cd "$PROJECT_ROOT/Code/HA-Models" || exit
                ALL_FOUND=true
                for file in "${REQUIRED_FILES[@]}"; do
                    if [[ -f "$file" ]]; then
                        FILE_SIZE=$(du -h "$file" 2>/dev/null | cut -f1)
                        echo "  ✓ $file ($FILE_SIZE)"
                    else
                        echo "  ✗ $file (MISSING)"
                        ALL_FOUND=false
                    fi
                done
                
                if [[ "$ALL_FOUND" == "true" ]]; then
                    echo ""
                    echo "✅ Successfully fetched precomputed files from branch"
                    echo "   (These will be automatically cleaned up after reproduction)"
                    echo ""
                    FETCHED_PRECOMPUTED=true
                else
                    echo ""
                    echo "❌ ERROR: Some files could not be extracted from branch"
                    echo ""
                    echo "The precomputed-results branch exists but doesn't contain all required files."
                    echo "You must run the full computational reproduction:"
                    echo "  ./reproduce.sh --comp full"
                    echo ""
                    exit 1
                fi
            else
                echo ""
                echo "❌ ERROR: Could not extract files from branch"
                echo ""
                echo "You must run the full computational reproduction:"
                echo "  ./reproduce.sh --comp full"
                echo ""
                exit 1
            fi
        else
            # No precomputed branch - show original error message
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
    else
        echo "========================================"
        echo "❌ ERROR: Not a git repository"
        echo "========================================"
        echo ""
        echo "This script requires a git repository to function properly."
        echo ""
        exit 1
    fi
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

# Clean up fetched precomputed files if we fetched them
if [[ "$FETCHED_PRECOMPUTED" == "true" ]]; then
    echo ""
    echo "→ Cleaning up fetched .obj files..."
    for file in "${REQUIRED_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            rm -f "$file"
            echo "  ✓ Removed $file"
        fi
    done
    echo "✅ Cleanup complete - working tree is clean"
fi

