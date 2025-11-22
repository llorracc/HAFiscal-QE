#!/bin/bash
# Reproduce Empirical Data Moments from SCF 2004
#
# This script downloads SCF 2004 data (if needed) and runs the empirical
# analysis to calculate the data moments used in the HAFiscal paper.
#
# Options:
#   --use-latest-scf-data    Download and use the latest SCF 2004 data from the Fed
#                            (inflated to current dollars, not 2013 dollars)

set -e

# Parse command line arguments
USE_LATEST_DATA=0
for arg in "$@"; do
    case $arg in
        --use-latest-scf-data)
            USE_LATEST_DATA=1
            shift
            ;;
    esac
done

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EMPIRICAL_DIR="$PROJECT_ROOT/Code/Empirical"

echo "========================================"
echo "Reproducing Empirical Data Moments"
echo "========================================"
echo ""

# Check if we're in the right directory
if [ ! -d "$EMPIRICAL_DIR" ]; then
    echo "❌ Error: Code/Empirical directory not found"
    echo "   Expected: $EMPIRICAL_DIR"
    exit 1
fi

cd "$EMPIRICAL_DIR"

# ============================================================================
# Step 1: Download SCF 2004 data if needed
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Checking SCF 2004 Data Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ $USE_LATEST_DATA -eq 1 ]; then
    echo "ℹ️  Downloading and comparing latest SCF data from Federal Reserve"
    echo ""
    echo "   This will:"
    echo "   1. Download latest data from Fed (2022 dollars)"
    echo "   2. Adjust it to 2013 dollars (divide by 1.1587)"
    echo "   3. Run analysis on BOTH git-versioned and adjusted data"
    echo "   4. Show comparison to verify they match"
    echo ""
    echo "   Inflation factor: 1.1587 (empirically determined)"
    echo "   See docs/SCF_DATA_VINTAGE.md for details."
    echo ""
    read -p "   Continue? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   Cancelled. Use git-versioned data (default) instead."
        exit 0
    fi
    echo ""
    
    # Ensure git-versioned file exists
    if [ ! -f "rscfp2004.dta" ]; then
        echo "❌ Error: Git-versioned rscfp2004.dta not found"
        echo "   Cannot compare without baseline data."
        exit 1
    fi
    
    # Save git-versioned file with explicit name
    echo "📋 Preserving git-versioned data..."
    cp rscfp2004.dta rscfp2004_git_2013USD.dta
    echo "   ✓ Saved as rscfp2004_git_2013USD.dta"
    echo ""
    
    # Download latest data
    echo "📥 Step 1: Downloading latest SCF 2004 data from Federal Reserve..."
    echo ""
    
    if [ ! -x "./download_scf_data.sh" ]; then
        echo "❌ Error: download_scf_data.sh not found or not executable"
        exit 1
    fi
    
    # Temporarily move git-versioned file
    mv rscfp2004.dta rscfp2004_temp_backup.dta
    
    ./download_scf_data.sh
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ Data download failed"
        mv rscfp2004_temp_backup.dta rscfp2004.dta
        exit 1
    fi
    
    # Rename downloaded file
    if [ -f "rscfp2004.dta" ]; then
        mv rscfp2004.dta rscfp2004_latest_2022USD.dta
        echo "   ✓ Downloaded as rscfp2004_latest_2022USD.dta"
    else
        echo "❌ Error: Downloaded file not found"
        mv rscfp2004_temp_backup.dta rscfp2004.dta
        exit 1
    fi
    
    # Restore git-versioned file
    mv rscfp2004_temp_backup.dta rscfp2004.dta
    
    echo ""
    echo "🔧 Step 2: Adjusting inflation (2022$ → 2013$)..."
    echo ""
    
    # Run inflation adjustment script
    if [ ! -f "adjust_scf_inflation.py" ]; then
        echo "❌ Error: adjust_scf_inflation.py not found"
        exit 1
    fi
    
    python adjust_scf_inflation.py rscfp2004_latest_2022USD.dta rscfp2004_latest_adjusted_2013USD.dta
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ Inflation adjustment failed"
        exit 1
    fi
    
    echo ""
    echo "✅ Data preparation complete!"
    echo "   Files created:"
    echo "   • rscfp2004_git_2013USD.dta           - Git-versioned (2013$, baseline)"
    echo "   • rscfp2004_latest_2022USD.dta        - Downloaded (2022$, unadjusted)"
    echo "   • rscfp2004_latest_adjusted_2013USD.dta - Downloaded + adjusted (2013$)"
    echo ""
    
    # Set flag to run comparison analysis
    COMPARE_DATASETS=1
else
    # Standard path: use git-versioned data
    COMPARE_DATASETS=0
    NEED_DOWNLOAD=0

    if [ ! -f "rscfp2004.dta" ]; then
        echo "⚠️  Missing: rscfp2004.dta (Summary Extract Data)"
        NEED_DOWNLOAD=1
    fi

    if [ ! -f "p04i6.dta" ]; then
        echo "⚠️  Missing: p04i6.dta (Main Survey Data)"
        NEED_DOWNLOAD=1
    fi

    if [ $NEED_DOWNLOAD -eq 1 ]; then
        echo ""
        echo "📥 Downloading required SCF 2004 data files..."
        echo ""
        
        if [ ! -x "./download_scf_data.sh" ]; then
            echo "❌ Error: download_scf_data.sh not found or not executable"
            exit 1
        fi
        
        ./download_scf_data.sh
        
        if [ $? -ne 0 ]; then
            echo ""
            echo "❌ Data download failed"
            exit 1
        fi
    else
        echo "✅ All required data files present:"
        echo "   - rscfp2004.dta (2013 dollars, matches paper)"
        echo "   - p04i6.dta"
        echo ""
        echo "   To use latest Fed data (2022 dollars), run with:"
        echo "   ./reproduce.sh --data --use-latest-scf-data"
    fi
fi

echo ""

# ============================================================================
# Step 2: Run Python analysis
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Running Empirical Analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ ! -f "make_liquid_wealth.py" ]; then
    echo "❌ Error: make_liquid_wealth.py not found"
    exit 1
fi

# Check for Python with pandas
if ! python3 -c "import pandas" 2>/dev/null; then
    echo "⚠️  Warning: pandas not available in current Python environment"
    echo ""
    
    # Try to activate UV environment if it exists
    if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        echo "Attempting to activate UV environment..."
        source "$PROJECT_ROOT/.venv/bin/activate"
        
        if python3 -c "import pandas" 2>/dev/null; then
            echo "✅ UV environment activated successfully"
        else
            echo "❌ Error: pandas not available even in UV environment"
            echo "   Please install pandas: pip install pandas"
            exit 1
        fi
    else
        echo "❌ Error: pandas not available"
        echo "   Please install: pip install pandas"
        echo "   Or set up the UV environment: ./reproduce/reproduce_environment_comp_uv.sh"
        exit 1
    fi
fi

echo "Running: python3 make_liquid_wealth.py"
echo ""

START_TIME=$(date +%s)

NONINTERACTIVE=1 python3 make_liquid_wealth.py

EXIT_CODE=$?
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ Empirical Analysis Complete"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Duration: ${DURATION} seconds"
    echo ""
    echo "Output files created:"
    echo "  - Figures/Data/LorenzAll.csv"
    echo "  - Figures/Data/LorenzEd.csv"
    echo ""
    echo "These data moments are used in:"
    echo "  - Table 2, Panel B (population and income statistics)"
    echo "  - Table 4, Panel B (median liquid wealth)"
    echo "  - Table 5 (wealth distribution)"
    echo "  - Figure 2 (Lorenz curves)"
    echo ""
    
    # If comparison mode, run comparison analysis
    if [ $COMPARE_DATASETS -eq 1 ]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Step 3: Comparing Git-versioned vs Latest Data"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        if [ ! -f "compare_scf_datasets.py" ]; then
            echo "❌ Error: compare_scf_datasets.py not found"
            exit 1
        fi
        
        echo "Running comparison analysis..."
        echo ""
        
        python3 compare_scf_datasets.py \
            rscfp2004_git_2013USD.dta \
            rscfp2004_latest_adjusted_2013USD.dta
        
        COMPARE_EXIT=$?
        
        if [ $COMPARE_EXIT -eq 0 ]; then
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "✅ Comparison Complete"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "Files retained for reference:"
            echo "  • rscfp2004.dta                       - Git-versioned (used by default)"
            echo "  • rscfp2004_git_2013USD.dta           - Copy of git-versioned"
            echo "  • rscfp2004_latest_2022USD.dta        - Downloaded (2022$, unadjusted)"
            echo "  • rscfp2004_latest_adjusted_2013USD.dta - Downloaded + adjusted (2013$)"
            echo ""
            echo "The comparison shows that both datasets produce equivalent results,"
            echo "confirming the inflation adjustment is working correctly."
            echo ""
        else
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "⚠️  Comparison Failed"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "Exit code: $COMPARE_EXIT"
            echo ""
            echo "The analysis completed but comparison failed."
            echo "Review the error messages above."
            echo ""
        fi
    fi
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "❌ Empirical Analysis Failed"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Exit code: $EXIT_CODE"
    echo "Duration: ${DURATION} seconds"
    echo ""
    exit $EXIT_CODE
fi

