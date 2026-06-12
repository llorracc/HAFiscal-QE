#!/bin/bash
# Fix script for missing HAFiscal.bib bibliography file
# Downloads from GitHub raw URL (avoids git fetch which bloats .git/objects/)

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

# Download from GitHub raw URL
GITHUB_REPO="${GITHUB_REPO:-llorracc/HAFiscal-QE}"
PRECOMPUTED_BRANCH="${PRECOMPUTED_BRANCH:-with-precomputed-artifacts}"
RAW_URL="https://raw.githubusercontent.com/${GITHUB_REPO}/${PRECOMPUTED_BRANCH}/HAFiscal.bib"

echo "Attempting to download from GitHub..."
echo "URL: $RAW_URL"
echo ""

if curl -L --fail --progress-bar -o HAFiscal.bib "$RAW_URL" 2>&1; then
    if [[ -f "HAFiscal.bib" && -s "HAFiscal.bib" ]]; then
        FILE_SIZE=$(du -h "HAFiscal.bib" 2>/dev/null | cut -f1)
        echo ""
        echo "✅ Successfully downloaded HAFiscal.bib ($FILE_SIZE)"
        exit 0
    fi
fi

# Download failed
rm -f HAFiscal.bib 2>/dev/null || true

echo ""
echo "⚠️  Could not download HAFiscal.bib from GitHub"
echo ""
echo "This may indicate:"
echo "  • Network connectivity issues"
echo "  • GitHub is temporarily unavailable"
echo "  • The file doesn't exist on the '${PRECOMPUTED_BRANCH}' branch"
echo ""
echo "Manual fixes:"
echo ""
echo "1. Check if it exists in Figures/ directory:"
if [[ -f "Figures/HAFiscal.bib" ]]; then
    echo "   ✅ Found in Figures/ - copying..."
    cp Figures/HAFiscal.bib HAFiscal.bib
    echo "   ✅ Copied to project root"
    exit 0
else
    echo "   ❌ Not found in Figures/"
fi
echo ""
echo "2. Create an empty bibliography file (citations will be missing):"
echo "   touch HAFiscal.bib"
echo ""
exit 1
