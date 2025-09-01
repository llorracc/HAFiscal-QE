#!/bin/bash
# test-qe-compilation.sh
# Test compilation of consolidated HAFiscal document with QE class

set -e

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
QE_ROOT="$(dirname "$SCRIPT_DIR")"
WORKING="${QE_ROOT}/working"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Testing QE Compilation ===${NC}"

# Check if consolidated file exists
if [ ! -f "${WORKING}/HAFiscal-QE-consolidated.tex" ]; then
    echo -e "${RED}Error: Consolidated file not found. Run prepare-qe-submission.sh first.${NC}"
    exit 1
fi

cd "${WORKING}"

# First attempt: compile with pdflatex
echo -e "\n${YELLOW}Attempting compilation with pdflatex...${NC}"
pdflatex -interaction=nonstopmode HAFiscal-QE-consolidated.tex || true

# Run bibtex if aux file was created
if [ -f "HAFiscal-QE-consolidated.aux" ]; then
    echo -e "\n${YELLOW}Running bibtex...${NC}"
    bibtex HAFiscal-QE-consolidated || true
fi

# Second and third passes
echo -e "\n${YELLOW}Second pdflatex pass...${NC}"
pdflatex -interaction=nonstopmode HAFiscal-QE-consolidated.tex || true

echo -e "\n${YELLOW}Third pdflatex pass...${NC}"
pdflatex -interaction=nonstopmode HAFiscal-QE-consolidated.tex || true

# Check for output
if [ -f "HAFiscal-QE-consolidated.pdf" ]; then
    echo -e "\n${GREEN}Success! PDF generated: ${WORKING}/HAFiscal-QE-consolidated.pdf${NC}"
    
    # Check for warnings/errors
    if grep -q "LaTeX Warning" HAFiscal-QE-consolidated.log; then
        echo -e "\n${YELLOW}LaTeX warnings found:${NC}"
        grep "LaTeX Warning" HAFiscal-QE-consolidated.log | head -10
    fi
    
    if grep -q "! " HAFiscal-QE-consolidated.log; then
        echo -e "\n${RED}LaTeX errors found:${NC}"
        grep -A 2 "! " HAFiscal-QE-consolidated.log | head -20
    fi
else
    echo -e "\n${RED}Failed to generate PDF. Check ${WORKING}/HAFiscal-QE-consolidated.log for details.${NC}"
    exit 1
fi 