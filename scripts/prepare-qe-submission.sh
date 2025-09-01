#!/bin/bash
# prepare-qe-submission.sh
# Prepares Quantitative Economics submission from HAFiscal sources
# This script is downstream-only and does not modify source repositories

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
QE_ROOT="$(dirname "$SCRIPT_DIR")"
HAFISCAL_MAKE="${QE_ROOT}/../HAFiscal-make"
HAFISCAL_LATEST="${QE_ROOT}/../HAFiscal-Latest"
HAFISCAL_PUBLIC="${QE_ROOT}/../HAFiscal-Public"

# Output directories
BUILD_INFO="${QE_ROOT}/build-info"
WORKING="${QE_ROOT}/working"
SUBMISSION="${QE_ROOT}/submission"

echo -e "${GREEN}=== Quantitative Economics Submission Preparation ===${NC}"
echo "QE Root: ${QE_ROOT}"
echo "HAFiscal-make: ${HAFISCAL_MAKE}"
echo "HAFiscal-Latest: ${HAFISCAL_LATEST}"

# Step 1: Record source repository states
echo -e "\n${YELLOW}Step 1: Recording source repository states${NC}"
mkdir -p "${BUILD_INFO}"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BUILD_LOG="${BUILD_INFO}/build-${TIMESTAMP}.log"

{
    echo "Build timestamp: ${TIMESTAMP}"
    echo "Source repository commits:"
    echo ""
    
    echo "HAFiscal-make:"
    cd "${HAFISCAL_MAKE}"
    git log -1 --format="  Commit: %H%n  Date: %ai%n  Message: %s"
    echo ""
    
    echo "HAFiscal-Latest:"
    cd "${HAFISCAL_LATEST}"
    git log -1 --format="  Commit: %H%n  Date: %ai%n  Message: %s"
    echo ""
    
    if [ -d "${HAFISCAL_PUBLIC}" ]; then
        echo "HAFiscal-Public:"
        cd "${HAFISCAL_PUBLIC}"
        git log -1 --format="  Commit: %H%n  Date: %ai%n  Message: %s"
    fi
} > "${BUILD_LOG}"

echo "Build info saved to: ${BUILD_LOG}"

# Step 2: Build HAFiscal PDF using existing infrastructure
echo -e "\n${YELLOW}Step 2: Building HAFiscal PDF from source${NC}"
cd "${HAFISCAL_MAKE}"
if [ -f "makePDF-Portable-Latest.sh" ]; then
    echo "Running makePDF-Portable-Latest.sh..."
    ./makePDF-Portable-Latest.sh
else
    echo -e "${RED}Error: makePDF-Portable-Latest.sh not found${NC}"
    exit 1
fi

# Step 3: Prepare working directory
echo -e "\n${YELLOW}Step 3: Preparing working directory${NC}"
rm -rf "${WORKING}"
mkdir -p "${WORKING}"

# Copy essential files from HAFiscal-Latest
echo "Copying source files..."
cp -r "${HAFISCAL_LATEST}"/*.tex "${WORKING}/" 2>/dev/null || true
cp -r "${HAFISCAL_LATEST}"/Subfiles "${WORKING}/" 2>/dev/null || true
cp -r "${HAFISCAL_LATEST}"/bibliography "${WORKING}/" 2>/dev/null || true
cp -r "${HAFISCAL_LATEST}"/Figures "${WORKING}/" 2>/dev/null || true
cp -r "${HAFISCAL_LATEST}"/Tables "${WORKING}/" 2>/dev/null || true

# Copy QE class files
echo "Installing QE class files..."
cp "${QE_ROOT}"/resources/qe-templates/econsocart.cls "${WORKING}/"
cp "${QE_ROOT}"/resources/qe-templates/econsocart.cfg "${WORKING}/"
cp "${QE_ROOT}"/resources/qe-templates/qe.bst "${WORKING}/"

# Step 4: Transform to QE format
echo -e "\n${YELLOW}Step 4: Transforming to QE format${NC}"
echo "This step requires the transformation script (to be implemented)..."
# TODO: Call Python/shell script to:
# - Convert document class
# - Restructure author information
# - Consolidate subfiles
# - Adjust bibliography
# - Separate supplementary materials

# Step 5: Prepare submission directory
echo -e "\n${YELLOW}Step 5: Preparing submission directory${NC}"
rm -rf "${SUBMISSION}"
mkdir -p "${SUBMISSION}/manuscript"
mkdir -p "${SUBMISSION}/supplementary"
mkdir -p "${SUBMISSION}/metadata"

# Copy transformed files (placeholder for now)
echo "Submission structure created in: ${SUBMISSION}"

echo -e "\n${GREEN}=== Preparation Complete ===${NC}"
echo "Next steps:"
echo "1. Implement transformation scripts in scripts/transform/"
echo "2. Review and adjust QE formatting"
echo "3. Generate final PDFs"
echo "4. Complete metadata for submission" 