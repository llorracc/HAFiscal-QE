#!/bin/bash
# Deploy README-QE.md compliance checklist
#
# This script:
# 1. Archives old README-QE.md if it exists
# 2. Runs the compliance checker on HAFiscal-QE/
# 3. Generates new README-QE.md
# 4. Deploys to both HAFiscal-Latest/ and HAFiscal-QE/
#
# Usage:
#   ./deploy-hafiscal-qe-compliance.sh [path-to-HAFiscal-QE]

set -e  # Exit on error

# Path constants
LATEST_ROOT="/Volumes/Sync/GitHub/llorracc/HAFiscal/HAFiscal-Latest"
PUBLIC_ROOT="/Volumes/Sync/GitHub/llorracc/HAFiscal/HAFiscal-Public"
QE_ROOT="/Volumes/Sync/GitHub/llorracc/HAFiscal/HAFiscal-QE"
MAKE_ROOT="/Volumes/Sync/GitHub/llorracc/HAFiscal/HAFiscal-make"

# Override QE_ROOT if provided as argument
if [[ -n "$1" ]]; then
    QE_ROOT="$1"
fi

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "=========================================="
echo "HAFiscal-QE Compliance Checklist Deploy"
echo "=========================================="
echo ""

# Verify QE_ROOT exists
if [[ ! -d "$QE_ROOT" ]]; then
    echo -e "${RED}✗ ERROR: QE repository not found at: $QE_ROOT${NC}"
    echo ""
    echo "Please ensure HAFiscal-QE/ exists, or provide path as argument:"
    echo "  ./deploy-hafiscal-qe-compliance.sh /path/to/HAFiscal-QE"
    exit 1
fi

echo -e "${BLUE}Target QE Repository:${NC} $QE_ROOT"
echo ""

# Step 1: Archive old README-QE.md if it exists
if [[ -f "$LATEST_ROOT/README-QE.md" ]]; then
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    OLD_DIR="$LATEST_ROOT/old"
    
    mkdir -p "$OLD_DIR"
    mv "$LATEST_ROOT/README-QE.md" "$OLD_DIR/HAFiscal-QE_${TIMESTAMP}.md"
    
    echo -e "${GREEN}✓${NC} Archived old README-QE.md to old/HAFiscal-QE_${TIMESTAMP}.md"
else
    echo -e "${YELLOW}⚠${NC} No existing README-QE.md found (first generation)"
fi
echo ""

# Step 2: Run compliance checker and generate new README-QE.md
echo "Generating compliance checklist..."
echo -e "${BLUE}Running:${NC} python3 $LATEST_ROOT/qe/generate-hafiscal-qe.py $QE_ROOT"
echo ""

cd "$LATEST_ROOT/qe"

if python3 generate-hafiscal-qe.py "$QE_ROOT" > /tmp/hafiscal-qe-generation.log 2>&1; then
    echo -e "${GREEN}✓${NC} Generated README-QE.md"
else
    echo -e "${RED}✗ Generation failed${NC}"
    echo ""
    echo "Error log:"
    cat /tmp/hafiscal-qe-generation.log
    exit 1
fi
echo ""

# Step 3: Verify the generated file exists
if [[ ! -f "$LATEST_ROOT/README-QE.md" ]]; then
    echo -e "${RED}✗ Generated file not found: $LATEST_ROOT/README-QE.md${NC}"
    exit 1
fi

# Get file statistics
FILE_SIZE=$(wc -c < "$LATEST_ROOT/README-QE.md")
LINE_COUNT=$(wc -l < "$LATEST_ROOT/README-QE.md")

echo -e "${GREEN}✓${NC} File created: ${FILE_SIZE} bytes, ${LINE_COUNT} lines"
echo ""

# Step 4: Copy to HAFiscal-QE/
echo "Deploying to HAFiscal-QE/..."

if cp "$LATEST_ROOT/README-QE.md" "$QE_ROOT/README-QE.md"; then
    echo -e "${GREEN}✓${NC} Deployed to HAFiscal-QE/README-QE.md"
else
    echo -e "${RED}✗ Deployment failed${NC}"
    exit 1
fi
echo ""

# Step 5: Summary report
echo "=========================================="
echo -e "${GREEN}✅ Deployment complete${NC}"
echo "=========================================="
echo ""
echo "Generated files:"
echo "  1. $LATEST_ROOT/README-QE.md (master copy)"
echo "  2. $QE_ROOT/README-QE.md (deployed copy)"
echo ""
echo "Review the compliance checklist:"
echo -e "  ${BLUE}cat $QE_ROOT/README-QE.md | less${NC}"
echo ""
echo "Or view in editor:"
echo -e "  ${BLUE}open $QE_ROOT/README-QE.md${NC}"
echo ""

# Step 6: Show quick summary from the generated file
if command -v grep >/dev/null 2>&1; then
    echo "Quick Summary:"
    echo ""
    
    # Extract status counts
    if grep -A 10 "Quick Status Dashboard" "$LATEST_ROOT/README-QE.md" | head -15 > /tmp/hafiscal-qe-summary.txt 2>/dev/null; then
        cat /tmp/hafiscal-qe-summary.txt
        echo ""
    fi
    
    # Extract critical items if any
    if grep -A 5 "Critical Items" "$LATEST_ROOT/README-QE.md" > /tmp/hafiscal-qe-critical.txt 2>/dev/null; then
        echo "----------------------------------------"
        head -10 /tmp/hafiscal-qe-critical.txt
        echo ""
    fi
fi

echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Review the generated checklist"
echo "  2. Address any critical (❌) items"
echo "  3. Commit changes if satisfied:"
echo -e "     ${BLUE}cd $LATEST_ROOT${NC}"
echo -e "     ${BLUE}git add README-QE.md${NC}"
echo -e "     ${BLUE}git commit -m 'Update QE compliance checklist'${NC}"
echo ""

