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

# Check if clean file exists
if [ ! -f "${WORKING}/HAFiscal-QE-clean.tex" ]; then
    echo -e "${RED}Error: Clean file not found. Run clean-qe-document.py first.${NC}"
    exit 1
fi

cd "${WORKING}"

# First attempt: compile with pdflatex
echo -e "\n${YELLOW}Attempting compilation with pdflatex...${NC}"
pdflatex -interaction=nonstopmode HAFiscal-QE-clean.tex || true

# Run bibtex if aux file was created
if [ -f "HAFiscal-QE-clean.aux" ]; then
    echo -e "\n${YELLOW}Running bibtex...${NC}"
    bibtex HAFiscal-QE-clean || true
fi

# Second and third passes
echo -e "\n${YELLOW}Second pdflatex pass...${NC}"
pdflatex -interaction=nonstopmode HAFiscal-QE-clean.tex || true

echo -e "\n${YELLOW}Third pdflatex pass...${NC}"
pdflatex -interaction=nonstopmode HAFiscal-QE-clean.tex || true

# Check for output
if [ -f "HAFiscal-QE-clean.pdf" ]; then
    echo -e "\n${GREEN}Success! PDF generated: ${WORKING}/HAFiscal-QE-clean.pdf${NC}"
    
    # Check for warnings/errors
    if grep -q "LaTeX Warning" HAFiscal-QE-clean.log; then
        echo -e "\n${YELLOW}LaTeX warnings found:${NC}"
        grep "LaTeX Warning" HAFiscal-QE-clean.log | head -10
    fi
    
    if grep -q "! " HAFiscal-QE-clean.log; then
        echo -e "\n${RED}LaTeX errors found:${NC}"
        grep -A 2 "! " HAFiscal-QE-clean.log | head -20
    fi
else
    echo -e "\n${RED}Failed to generate PDF. Check ${WORKING}/HAFiscal-QE-clean.log for details.${NC}"
    exit 1
fi 