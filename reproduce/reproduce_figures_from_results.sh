#!/bin/bash
# Reproduce figures from pre-computed results
#
# This script generates figure files (PDF, PNG, JPG, SVG) from computational
# results that have already been computed and saved in Code/HA-Models/Results/
#
# If result files are missing, automatically fetches them from the
# 'with-precomputed-artifacts' branch (if it exists), generates figures,
# then cleans up the fetched files.
#
# Options:
#   IMPC    Generate IMPC (Intertemporal MPC) figures
#   LP      Generate Lorenz Points figures  
#   all     Generate all figures from results

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PANDEMIC_CODE_DIR="$PROJECT_ROOT/Code/HA-Models/FromPandemicCode"
RESULTS_DIR="$PROJECT_ROOT/Code/HA-Models/Results"

# Parse figure type argument
FIGURE_TYPE="${1:-all}"

# Track if we fetched files (for cleanup later)
FETCHED_PRECOMPUTED=false
FETCHED_FILES=()

echo "========================================"
echo "Reproducing Figures from Results"
echo "========================================"
echo ""

# Define required result files based on figure type
declare -a REQUIRED_RESULT_FILES
case "$FIGURE_TYPE" in
    IMPC)
        REQUIRED_RESULT_FILES=(
            "Code/HA-Models/Results/AllResults_CRRA_2.0_R_1.01.txt"
            "Code/HA-Models/Results/AllResults_CRRA_2.0_R_1.01_Splurge0.txt"
        )
        ;;
    LP)
        REQUIRED_RESULT_FILES=(
            "Code/HA-Models/Results/AllResults_CRRA_2.0_R_1.01.txt"
        )
        ;;
    all)
        REQUIRED_RESULT_FILES=(
            "Code/HA-Models/Results/AllResults_CRRA_2.0_R_1.01.txt"
            "Code/HA-Models/Results/AllResults_CRRA_2.0_R_1.01_Splurge0.txt"
        )
        ;;
    *)
        echo "❌ Error: Unknown figure type: $FIGURE_TYPE"
        echo "   Valid types: IMPC, LP, all"
        exit 1
        ;;
esac

# Check which result files are missing
MISSING_FILES=()
for file in "${REQUIRED_RESULT_FILES[@]}"; do
    if [[ ! -f "$PROJECT_ROOT/$file" ]]; then
        MISSING_FILES+=("$file")
    fi
done

# If files are missing, try to fetch from with-precomputed-artifacts branch
if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
    # Check if with-precomputed-artifacts branch exists
    PRECOMPUTED_BRANCH="with-precomputed-artifacts"
    REMOTE="${REMOTE:-origin}"
    
    # Check if we're in a git repository and if the precomputed branch exists
    if git -C "$PROJECT_ROOT" rev-parse --git-dir > /dev/null 2>&1; then
        # Check for branch existence (try remote first, then local)
        BRANCH_EXISTS=false
        if git -C "$PROJECT_ROOT" ls-remote --heads "$REMOTE" "$PRECOMPUTED_BRANCH" 2>/dev/null | grep -q "$PRECOMPUTED_BRANCH"; then
            BRANCH_EXISTS=true
            BRANCH_LOCATION="$REMOTE/$PRECOMPUTED_BRANCH"
        elif git -C "$PROJECT_ROOT" show-ref --verify --quiet "refs/heads/$PRECOMPUTED_BRANCH"; then
            BRANCH_EXISTS=true
            BRANCH_LOCATION="$PRECOMPUTED_BRANCH"
        fi
        
        if [[ "$BRANCH_EXISTS" == "true" ]]; then
            echo "========================================"
            echo "📦 Fetching Precomputed Result Files"
            echo "========================================"
            echo ""
            echo "The following result files are missing:"
            for file in "${MISSING_FILES[@]}"; do
                echo "  • $file"
            done
            echo ""
            echo "Fetching them from the '$PRECOMPUTED_BRANCH' branch..."
            echo ""
            
            # Fetch the branch if it's remote
            if [[ "$BRANCH_LOCATION" == "$REMOTE/$PRECOMPUTED_BRANCH" ]]; then
                echo "→ Fetching $PRECOMPUTED_BRANCH from $REMOTE..."
                git -C "$PROJECT_ROOT" fetch "$REMOTE" "$PRECOMPUTED_BRANCH" 2>/dev/null || true
            fi
            
            # Extract result files using git archive
            echo "→ Extracting precomputed result files..."
            cd "$PROJECT_ROOT" || exit
            if git archive "$BRANCH_LOCATION" Code/HA-Models/Results 2>/dev/null | tar -x 2>/dev/null; then
                # Verify files were extracted
                ALL_FOUND=true
                for file in "${MISSING_FILES[@]}"; do
                    if [[ -f "$PROJECT_ROOT/$file" ]]; then
                        FILE_SIZE=$(du -h "$PROJECT_ROOT/$file" 2>/dev/null | cut -f1)
                        echo "  ✓ $file ($FILE_SIZE)"
                        FETCHED_FILES+=("$PROJECT_ROOT/$file")
                    else
                        echo "  ✗ $file (MISSING)"
                        ALL_FOUND=false
                    fi
                done
                
                if [[ "$ALL_FOUND" == "true" ]]; then
                    echo ""
                    echo "✅ Successfully fetched precomputed files from branch"
                    echo "   (These will be automatically cleaned up after figure generation)"
                    echo ""
                    FETCHED_PRECOMPUTED=true
                else
                    echo ""
                    echo "❌ ERROR: Some files could not be extracted from branch"
                    echo ""
                    echo "The with-precomputed-artifacts branch exists but doesn't contain all required files."
                    echo "You must run the computational reproduction:"
                    echo "  ./reproduce.sh --comp min   (or --comp full)"
                    echo ""
                    exit 1
                fi
            else
                echo ""
                echo "❌ ERROR: Could not extract files from branch"
                echo ""
                echo "Failed to fetch from '$PRECOMPUTED_BRANCH' branch."
                echo "You must run the computational reproduction:"
                echo "  ./reproduce.sh --comp min   (or --comp full)"
                echo ""
                exit 1
            fi
        else
            echo "========================================"
            echo "❌ Missing Required Result Files"
            echo "========================================"
            echo ""
            echo "The following result files are required but not found:"
            for file in "${MISSING_FILES[@]}"; do
                echo "  • $file"
            done
            echo ""
            echo "The '$PRECOMPUTED_BRANCH' branch does not exist in this repository."
            echo "You must run the computational reproduction:"
            echo "  ./reproduce.sh --comp min   (or --comp full)"
            echo ""
            exit 1
        fi
    else
        echo "❌ ERROR: Not in a git repository"
        echo "   Cannot fetch precomputed files."
        echo ""
        echo "You must run the computational reproduction:"
        echo "  ./reproduce.sh --comp min   (or --comp full)"
        echo ""
        exit 1
    fi
fi

# Check for Python with required packages
check_python() {
    if ! python3 -c "import matplotlib, numpy, pandas" 2>/dev/null; then
        echo "❌ Error: Required Python packages not available"
        echo "   Packages needed: matplotlib, numpy, pandas, HARK"
        echo ""
        echo "   To set up environment:"
        echo "     ./reproduce.sh --envt comp_uv"
        exit 1
    fi
}

echo "Checking Python environment..."
check_python
echo "✅ Python environment OK"
echo ""

echo "✅ All required result files present"
echo ""

# Change to FromPandemicCode directory
cd "$PANDEMIC_CODE_DIR"

case "$FIGURE_TYPE" in
    IMPC)
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Generating IMPC Figures"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Running: NONINTERACTIVE=1 python3 CreateIMPCfig.py"
        echo ""
        
        START_TIME=$(date +%s)
        NONINTERACTIVE=1 python3 CreateIMPCfig.py
        EXIT_CODE=$?
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        
        if [ $EXIT_CODE -eq 0 ]; then
            echo ""
            echo "✅ IMPC figures generated successfully (${DURATION}s)"
            echo ""
            echo "Generated files:"
            echo "  • IMPCs_wSplZero.{pdf,png,jpg,svg}"
            echo "  • IMPCs_wSplEstimated.{pdf,png,jpg,svg}"
            echo "  • IMPCs_both.{pdf,png,jpg,svg}"
        else
            echo ""
            echo "❌ IMPC figure generation failed (exit code: $EXIT_CODE)"
            
            # Clean up fetched files even on failure
            if [[ "$FETCHED_PRECOMPUTED" == "true" && ${#FETCHED_FILES[@]} -gt 0 ]]; then
                echo ""
                echo "→ Cleaning up fetched result files..."
                for file in "${FETCHED_FILES[@]}"; do
                    if [[ -f "$file" ]]; then
                        rm -f "$file"
                        echo "  ✓ Removed $(basename "$file")"
                    fi
                done
                echo "✅ Cleanup complete"
            fi
            
            exit $EXIT_CODE
        fi
        ;;
        
    LP)
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Generating Lorenz Points Figures"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Running: NONINTERACTIVE=1 python3 CreateLPfig.py"
        echo ""
        
        START_TIME=$(date +%s)
        NONINTERACTIVE=1 python3 CreateLPfig.py
        EXIT_CODE=$?
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        
        if [ $EXIT_CODE -eq 0 ]; then
            echo ""
            echo "✅ Lorenz Points figures generated successfully (${DURATION}s)"
            echo ""
            echo "Generated files:"
            echo "  • LorenzPoints_*.{pdf,png,jpg,svg}"
        else
            echo ""
            echo "❌ Lorenz Points figure generation failed (exit code: $EXIT_CODE)"
            
            # Clean up fetched files even on failure
            if [[ "$FETCHED_PRECOMPUTED" == "true" && ${#FETCHED_FILES[@]} -gt 0 ]]; then
                echo ""
                echo "→ Cleaning up fetched result files..."
                for file in "${FETCHED_FILES[@]}"; do
                    if [[ -f "$file" ]]; then
                        rm -f "$file"
                        echo "  ✓ Removed $(basename "$file")"
                    fi
                done
                echo "✅ Cleanup complete"
            fi
            
            exit $EXIT_CODE
        fi
        ;;
        
    all)
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Generating All Figures from Results"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        # Run IMPC
        echo "Step 1/2: IMPC Figures"
        echo "Running: NONINTERACTIVE=1 python3 CreateIMPCfig.py"
        echo ""
        if ! NONINTERACTIVE=1 python3 CreateIMPCfig.py; then
            # Clean up fetched files on failure
            if [[ "$FETCHED_PRECOMPUTED" == "true" && ${#FETCHED_FILES[@]} -gt 0 ]]; then
                echo ""
                echo "→ Cleaning up fetched result files..."
                for file in "${FETCHED_FILES[@]}"; do
                    if [[ -f "$file" ]]; then
                        rm -f "$file"
                        echo "  ✓ Removed $(basename "$file")"
                    fi
                done
                echo "✅ Cleanup complete"
            fi
            exit 1
        fi
        echo "✅ IMPC figures complete"
        echo ""
        
        # Run LP
        echo "Step 2/2: Lorenz Points Figures"
        echo "Running: NONINTERACTIVE=1 python3 CreateLPfig.py"
        echo ""
        if ! NONINTERACTIVE=1 python3 CreateLPfig.py; then
            # Clean up fetched files on failure
            if [[ "$FETCHED_PRECOMPUTED" == "true" && ${#FETCHED_FILES[@]} -gt 0 ]]; then
                echo ""
                echo "→ Cleaning up fetched result files..."
                for file in "${FETCHED_FILES[@]}"; do
                    if [[ -f "$file" ]]; then
                        rm -f "$file"
                        echo "  ✓ Removed $(basename "$file")"
                    fi
                done
                echo "✅ Cleanup complete"
            fi
            exit 1
        fi
        echo "✅ Lorenz Points figures complete"
        echo ""
        
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ All figures generated successfully"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ;;
esac

# Clean up fetched precomputed files if we fetched them
if [[ "$FETCHED_PRECOMPUTED" == "true" && ${#FETCHED_FILES[@]} -gt 0 ]]; then
    echo ""
    echo "→ Cleaning up fetched result files..."
    for file in "${FETCHED_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            rm -f "$file"
            echo "  ✓ Removed $(basename "$file")"
        fi
    done
    echo "✅ Cleanup complete - working tree is clean"
fi


# Display prominent warning if we used precomputed artifacts
if [[ "$FETCHED_PRECOMPUTED" == "true" && ${#FETCHED_FILES[@]} -gt 0 ]]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚠️  WARNING: PRECOMPUTED ARTIFACTS WERE USED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "This figure generation used precomputed result files (.txt files)"
    echo "that were temporarily fetched from the 'with-precomputed-artifacts' branch."
    echo ""
    echo "This means you have NOT run the full computational reproduction."
    echo ""
    echo "To run a complete, from-scratch reproduction:"
    echo "  ./reproduce.sh --comp full"
    echo ""
    echo "The full reproduction takes 4-5 days on a high-end 2025 laptop but provides complete verification"
    echo "of all computational results from which these figures were generated."
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo ""
    echo "✅ Figure generation complete!"
fi
