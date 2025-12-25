#!/bin/bash
# Download SCF 2004 Data Files
#
# This script downloads the required data files from the Federal Reserve Board
# website for the HAFiscal empirical analysis.
#
# Data source: https://www.federalreserve.gov/econres/scf_2004.htm

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "SCF 2004 Data Download Script"
echo "========================================"
echo ""
echo "This script will download SCF 2004 data files from:"
echo "  https://www.federalreserve.gov/econres/scf_2004.htm"
echo ""

# Check for required tools
if ! command -v curl &> /dev/null; then
    echo "❌ Error: curl not found. Please install curl."
    exit 1
fi

if ! command -v unzip &> /dev/null; then
    echo "❌ Error: unzip not found. Please install unzip."
    exit 1
fi

# Base URL for SCF 2004 data
BASE_URL="https://www.federalreserve.gov/econres/files"

# ============================================================================
# Download Summary Extract Data (rscfp2004.dta)
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1) Downloading Summary Extract Data"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "rscfp2004.dta" ]; then
    echo "✅ rscfp2004.dta already exists. Skipping download."
else
    echo "Downloading scfp2004s.zip..."
    curl -L -o scfp2004s.zip "${BASE_URL}/scfp2004s.zip"
    
    echo "Extracting rscfp2004.dta..."
    unzip -o scfp2004s.zip rscfp2004.dta
    
    echo "Cleaning up..."
    rm scfp2004s.zip
    
    echo "✅ rscfp2004.dta downloaded successfully"
fi

echo ""

# ============================================================================
# Download Main Survey Data (p04i6.dta)
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2) Downloading Main Survey Data"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "p04i6.dta" ]; then
    echo "✅ p04i6.dta already exists. Skipping download."
else
    echo "Downloading scf2004s.zip..."
    curl -L -o scf2004s.zip "${BASE_URL}/scf2004s.zip"
    
    echo "Extracting p04i6.dta..."
    unzip -o scf2004s.zip p04i6.dta
    
    echo "Cleaning up..."
    rm scf2004s.zip
    
    echo "✅ p04i6.dta downloaded successfully"
fi

echo ""

# ============================================================================
# Verify downloads
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3) Verifying Downloads"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

MISSING_FILES=0

if [ -f "rscfp2004.dta" ]; then
    SIZE=$(stat -f%z "rscfp2004.dta" 2>/dev/null || stat -c%s "rscfp2004.dta" 2>/dev/null)
    echo "✅ rscfp2004.dta ($(numfmt --to=iec-i --suffix=B "$SIZE" 2>/dev/null || echo "$SIZE bytes"))"
else
    echo "❌ rscfp2004.dta missing"
    MISSING_FILES=$((MISSING_FILES + 1))
fi

if [ -f "p04i6.dta" ]; then
    SIZE=$(stat -f%z "p04i6.dta" 2>/dev/null || stat -c%s "p04i6.dta" 2>/dev/null)
    echo "✅ p04i6.dta ($(numfmt --to=iec-i --suffix=B "$SIZE" 2>/dev/null || echo "$SIZE bytes"))"
else
    echo "❌ p04i6.dta missing"
    MISSING_FILES=$((MISSING_FILES + 1))
fi

if [ -f "ccbal_answer.dta" ]; then
    echo "✅ ccbal_answer.dta (pre-existing)"
else
    echo "ℹ️  ccbal_answer.dta will be created when running analysis scripts"
fi

echo ""

# ============================================================================
# Summary
# ============================================================================
if [ $MISSING_FILES -eq 0 ]; then
    echo "========================================"
    echo "✅ Download Complete!"
    echo "========================================"
    echo ""
    echo "All required SCF 2004 data files are present."
    echo ""
    echo "Next steps:"
    echo "  1. Run Python analysis:"
    echo "     python3 make_liquid_wealth.py"
    echo ""
    echo "⚠️  IMPORTANT NOTE:"
    echo "The Federal Reserve periodically updates older SCF data"
    echo "to adjust for inflation. If dollar values don't match the"
    echo "paper exactly, this is likely due to inflation adjustment."
    echo "The relative statistics (percentages, ratios) should still"
    echo "match closely."
    echo ""
else
    echo "========================================"
    echo "❌ Download Incomplete"
    echo "========================================"
    echo ""
    echo "$MISSING_FILES file(s) failed to download."
    echo "Please check your internet connection and try again."
    echo ""
    exit 1
fi

