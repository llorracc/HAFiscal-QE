#!/bin/bash
# Reproduce Empirical Data Moments from SCF 2004
#
# This script downloads SCF 2004 data (if needed) and runs the empirical
# analysis to calculate the data moments used in the HAFiscal paper.

set -e

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
    echo "   - rscfp2004.dta"
    echo "   - p04i6.dta"
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

python3 make_liquid_wealth.py

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
    echo "  - ../../Figures/Data/LorenzAll.csv"
    echo "  - ../../Figures/Data/LorenzEd.csv"
    echo ""
    echo "These data moments are used in:"
    echo "  - Table 2, Panel B (population and income statistics)"
    echo "  - Table 4, Panel B (median liquid wealth)"
    echo "  - Table 5 (wealth distribution)"
    echo "  - Figure 2 (Lorenz curves)"
    echo ""
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

