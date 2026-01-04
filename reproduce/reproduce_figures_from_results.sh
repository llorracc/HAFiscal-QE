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

# If files are missing, download them from GitHub via HTTP
if [[ ${#MISSING_FILES[@]} -gt 0 ]]; then
    # Download from GitHub raw URL (avoids git fetch which bloats .git/objects/)
    GITHUB_REPO="${GITHUB_REPO:-llorracc/HAFiscal-QE}"
    PRECOMPUTED_BRANCH="${PRECOMPUTED_BRANCH:-with-precomputed-artifacts}"
    RAW_BASE_URL="https://raw.githubusercontent.com/${GITHUB_REPO}/${PRECOMPUTED_BRANCH}"
    
    echo "========================================"
    echo "📦 Downloading Precomputed Result Files"
    echo "========================================"
    echo ""
    echo "The following result files are missing:"
    for file in "${MISSING_FILES[@]}"; do
        echo "  • $file"
    done
    echo ""
    echo "Downloading from GitHub (${PRECOMPUTED_BRANCH} branch)..."
    echo ""
    
    ALL_DOWNLOADED=true
    for file in "${MISSING_FILES[@]}"; do
        local_path="$PROJECT_ROOT/$file"
        remote_url="${RAW_BASE_URL}/${file}"
        filename=$(basename "$file")
        
        # Create destination directory if needed
        mkdir -p "$(dirname "$local_path")"
        
        echo "→ Downloading ${filename}..."
        if curl -L --fail --progress-bar -o "$local_path" "$remote_url" 2>&1; then
            if [[ -f "$local_path" && -s "$local_path" ]]; then
                FILE_SIZE=$(du -h "$local_path" 2>/dev/null | cut -f1)
                echo "  ✓ $file ($FILE_SIZE)"
                FETCHED_FILES+=("$local_path")
            else
                echo "  ✗ $file (EMPTY OR FAILED)"
                rm -f "$local_path" 2>/dev/null
                ALL_DOWNLOADED=false
            fi
        else
            echo "  ✗ $file (DOWNLOAD FAILED)"
            rm -f "$local_path" 2>/dev/null
            ALL_DOWNLOADED=false
        fi
    done
    
    if [[ "$ALL_DOWNLOADED" == "true" ]]; then
        echo ""
        echo "✅ Successfully downloaded precomputed files"
        echo "   (These will be automatically cleaned up after figure generation)"
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
        echo "Alternative: Run the computational reproduction:"
        echo "  ./reproduce.sh --comp min   (or --comp full)"
        echo ""
        # Clean up any partially downloaded files
        for file in "${FETCHED_FILES[@]}"; do
            rm -f "$file" 2>/dev/null
        done
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
    echo "that were downloaded from GitHub's '${PRECOMPUTED_BRANCH:-with-precomputed-artifacts}' branch."
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
