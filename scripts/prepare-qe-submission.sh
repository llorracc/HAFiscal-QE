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

# Consolidate subfiles
echo "Consolidating subfiles into single document..."
python3 "${SCRIPT_DIR}/transform/consolidate-subfiles.py" "${HAFISCAL_LATEST}" "${WORKING}/HAFiscal-QE-consolidated.tex"

# Copy bibliography files
echo "Copying bibliography files..."
cp "${HAFISCAL_LATEST}/HAFiscal.bib" "${WORKING}/"
cp "${HAFISCAL_LATEST}/HAFiscal-Add-Refs.bib" "${WORKING}/" 2>/dev/null || true

# Copy figure and table directories
echo "Copying figures and tables..."
cp -r "${HAFISCAL_LATEST}/Figures" "${WORKING}/" 2>/dev/null || true
cp -r "${HAFISCAL_LATEST}/Tables" "${WORKING}/" 2>/dev/null || true
cp -r "${HAFISCAL_LATEST}/Code" "${WORKING}/" 2>/dev/null || true  # For generated figures/tables

# Step 5: Clean QE document
echo -e "\n${YELLOW}Step 5: Cleaning QE document${NC}"
python3 "${SCRIPT_DIR}/transform/clean-qe-document.py" "${WORKING}/HAFiscal-QE-consolidated.tex" "${WORKING}/HAFiscal-QE-clean.tex"

# Step 6: Fix packages and commands
echo -e "\n${YELLOW}Step 6: Fixing missing packages and commands${NC}"
python3 "${SCRIPT_DIR}/transform/fix-packages.py" "${WORKING}/HAFiscal-QE-clean.tex" "${WORKING}/HAFiscal-QE-fixed.tex"

# Step 7: Fix duplicate labels
echo -e "\n${YELLOW}Step 7: Fixing duplicate labels${NC}"
python3 "${SCRIPT_DIR}/transform/fix-duplicate-labels.py" "${WORKING}/HAFiscal-QE-fixed.tex" "${WORKING}/HAFiscal-QE-final.tex"

# Step 8: Compile final document
echo -e "\n${YELLOW}Step 8: Compiling final QE document${NC}"
cd "${WORKING}"

# First pass
echo "Running first pdflatex pass..."
pdflatex -interaction=batchmode HAFiscal-QE-final.tex > compilation.log 2>&1

# Run bibtex
echo "Running bibtex..."
bibtex HAFiscal-QE-final >> compilation.log 2>&1 || true

# Second and third passes
echo "Running second pdflatex pass..."
pdflatex -interaction=batchmode HAFiscal-QE-final.tex >> compilation.log 2>&1

echo "Running third pdflatex pass..."
pdflatex -interaction=batchmode HAFiscal-QE-final.tex >> compilation.log 2>&1

# Check if PDF was generated
if [ -f "HAFiscal-QE-final.pdf" ]; then
    echo -e "${GREEN}Success! PDF generated: ${WORKING}/HAFiscal-QE-final.pdf${NC}"
    
    # Step 9: Prepare submission directory
    echo -e "\n${YELLOW}Step 9: Preparing submission directory${NC}"
    rm -rf "${SUBMISSION}"
    mkdir -p "${SUBMISSION}/manuscript"
    mkdir -p "${SUBMISSION}/supplementary"
    mkdir -p "${SUBMISSION}/metadata"
    
    # Copy final files
    cp HAFiscal-QE-final.pdf "${SUBMISSION}/manuscript/HAFiscal-QE.pdf"
    cp HAFiscal-QE-final.tex "${SUBMISSION}/manuscript/HAFiscal-QE.tex"
    cp HAFiscal.bib "${SUBMISSION}/manuscript/"
    cp -r Figures "${SUBMISSION}/manuscript/" 2>/dev/null || true
    cp -r Tables "${SUBMISSION}/manuscript/" 2>/dev/null || true
    cp -r Code "${SUBMISSION}/manuscript/" 2>/dev/null || true
    
    # Copy QE class files
    cp econsocart.cls "${SUBMISSION}/manuscript/"
    cp econsocart.cfg "${SUBMISSION}/manuscript/"
    cp qe.bst "${SUBMISSION}/manuscript/"
    
    echo -e "\n${GREEN}=== QE Submission Preparation Complete ===${NC}"
    echo "Final PDF: ${SUBMISSION}/manuscript/HAFiscal-QE.pdf"
    echo "Build log: ${BUILD_LOG}"
else
    echo -e "${RED}Error: PDF generation failed. Check ${WORKING}/compilation.log for details.${NC}"
    tail -50 "${WORKING}/compilation.log"
    exit 1
fi 