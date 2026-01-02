#!/bin/bash
# Fix script for missing HAFiscal.bib bibliography file

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "HAFiscal Bibliography Fix"
echo "========================================"
echo ""

# Check if HAFiscal.bib exists
if [[ -f "HAFiscal.bib" ]]; then
    echo "✅ HAFiscal.bib already exists"
    exit 0
fi

echo "❌ HAFiscal.bib not found"
echo ""

# Try to fetch from with-precomputed-artifacts branch
PRECOMPUTED_BRANCH="with-precomputed-artifacts"
REMOTE="${REMOTE:-origin}"

if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Attempting to fetch from '$PRECOMPUTED_BRANCH' branch..."
    
    # Check for branch existence
    BRANCH_EXISTS=false
    if git ls-remote --heads "$REMOTE" "$PRECOMPUTED_BRANCH" 2>/dev/null | grep -q "$PRECOMPUTED_BRANCH"; then
        BRANCH_EXISTS=true
        BRANCH_LOCATION="$REMOTE/$PRECOMPUTED_BRANCH"
        git fetch "$REMOTE" "$PRECOMPUTED_BRANCH" 2>/dev/null || true
    elif git show-ref --verify --quiet "refs/heads/$PRECOMPUTED_BRANCH"; then
        BRANCH_EXISTS=true
        BRANCH_LOCATION="$PRECOMPUTED_BRANCH"
    fi
    
    if [[ "$BRANCH_EXISTS" == "true" ]]; then
        if git show "$BRANCH_LOCATION:HAFiscal.bib" > HAFiscal.bib 2>/dev/null; then
            if [[ -f "HAFiscal.bib" && -s "HAFiscal.bib" ]]; then
                echo "✅ Successfully fetched HAFiscal.bib"
                exit 0
            fi
        fi
    fi
fi

echo "⚠️  Could not automatically fetch HAFiscal.bib"
echo ""
echo "Manual fixes:"
echo "1. Check if HAFiscal.bib exists in another branch:"
echo "   git show with-precomputed-artifacts:HAFiscal.bib > HAFiscal.bib"
echo ""
echo "2. Check if it exists in Figures/ directory:"
if [[ -f "Figures/HAFiscal.bib" ]]; then
    echo "   ✅ Found in Figures/ - copying..."
    cp Figures/HAFiscal.bib HAFiscal.bib
    echo "   ✅ Copied to project root"
else
    echo "   ❌ Not found in Figures/"
fi
echo ""
echo "3. Create an empty bibliography file (citations will be missing):"
echo "   touch HAFiscal.bib"
echo ""
exit 1

