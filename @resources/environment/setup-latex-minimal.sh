#!/bin/bash
# =============================================================================
# HAFiscal Minimal LaTeX Setup - SINGLE SOURCE OF TRUTH
# =============================================================================
# This script installs and configures a minimal LaTeX environment for HAFiscal.
# It is called by:
#   - .devcontainer/setup.sh (Docker/DevContainer)
#   - .github/workflows/push-build-docs.yml (GitHub Actions)
#
# Strategy:
#   1. Verifies required LaTeX packages (catchfile, beamer) are installed
#   2. Assumes packages were installed via reproduce/docker/setup.sh (SST)
#   3. Configures TEXMFHOME and TEXINPUTS for local packages
#
# IMPORTANT: This script does NOT install packages - it only verifies they exist.
# Package installation is handled by reproduce/docker/setup.sh (Single Source of Truth).
# This script maintains the SST principle by not duplicating installation logic.
# =============================================================================

set -e

echo "📄 Verifying MINIMAL LaTeX Environment (HAFiscal)..."
echo "   - Verifying: catchfile, beamer (should be installed via reproduce/docker/setup.sh)"
echo "   - Configuring: TEXMFHOME and TEXINPUTS for local packages"
echo "   - Local packages: 45 packages from @local/texlive/texmf-local/ (in repo)"

# Determine the repository root
if [ -n "$GITHUB_WORKSPACE" ]; then
    # Running in GitHub Actions
    REPO_ROOT="$GITHUB_WORKSPACE"
elif [ -n "${REPO_NAME}" ] && [ -d "/workspaces/${REPO_NAME}" ]; then
    # Running in DevContainer (with REPO_NAME set)
    REPO_ROOT="/workspaces/${REPO_NAME}"
elif [ -d "/workspaces/HAFiscal-Latest" ] || [ -d "/workspaces/HAFiscal-Public" ] || [ -d "/workspaces/HAFiscal-QE" ]; then
    # Fallback: try common repo names
    for repo in HAFiscal-Latest HAFiscal-Public HAFiscal-QE; do
        if [ -d "/workspaces/${repo}" ]; then
            REPO_ROOT="/workspaces/${repo}"
            break
        fi
    done
else
    # Fallback: try to find repo root from script location
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

echo "   - Repository root: $REPO_ROOT"

# =============================================================================
# Step 1: Verify required LaTeX packages are installed
# =============================================================================
# NOTE: This script assumes packages were installed via reproduce/docker/setup.sh (SST)
# which includes catchfile and beamer in its package list. This script only verifies
# they exist - it does NOT install them (to maintain SST principle).
echo ""
echo "1️⃣  Verifying required LaTeX packages..."

# Check if packages are available
CATCHFILE_FOUND=$(kpsewhich catchfile.sty 2>/dev/null || echo "")
BEAMER_FOUND=$(kpsewhich beamer.cls 2>/dev/null || echo "")

if [ -n "$CATCHFILE_FOUND" ] && [ -n "$BEAMER_FOUND" ]; then
    echo "   ✅ catchfile and beamer available"
    echo "      catchfile: $CATCHFILE_FOUND"
    echo "      beamer: $BEAMER_FOUND"
else
    echo "   ❌ ERROR: Required LaTeX packages not found!"
    echo "      catchfile: ${CATCHFILE_FOUND:-NOT FOUND}"
    echo "      beamer: ${BEAMER_FOUND:-NOT FOUND}"
    echo ""
    echo "   These packages should be installed by reproduce/docker/setup.sh (SST)"
    echo "   Please run the SST setup script first:"
    echo "      bash reproduce/docker/setup.sh"
    echo ""
    echo "   Or if using Docker/DevContainer, ensure setup.sh ran during container build"
    exit 1
fi

# =============================================================================
# Step 2: Verify LaTeX installation
# =============================================================================
echo ""
echo "2️⃣  Verifying LaTeX installation..."

if command -v pdflatex >/dev/null 2>&1; then
    LATEX_VERSION=$(pdflatex --version | head -1)
    echo "   ✅ $LATEX_VERSION"
else
    echo "   ❌ pdflatex not found"
    exit 1
fi

if command -v latexmk >/dev/null 2>&1; then
    LATEXMK_VERSION=$(latexmk --version | head -1)
    echo "   ✅ $LATEXMK_VERSION"
else
    echo "   ❌ latexmk not found"
    exit 1
fi

# =============================================================================
# Step 3: Configure TEXMFHOME to use local packages
# =============================================================================
echo ""
echo "3️⃣  Configuring TEXMFHOME for local LaTeX packages..."

export TEXMFHOME="${REPO_ROOT}/@local/texlive/texmf-local"

# Verify local packages directory exists
if [ -d "$TEXMFHOME/tex/latex" ]; then
    PACKAGE_COUNT=$(find "$TEXMFHOME/tex/latex" -name "*.sty" | wc -l)
    echo "   ✅ TEXMFHOME=$TEXMFHOME"
    echo "   ✅ Found $PACKAGE_COUNT local .sty files"
else
    echo "   ⚠️  Warning: $TEXMFHOME/tex/latex not found"
    echo "   ⚠️  LaTeX compilation may fail if additional packages are needed"
fi

# Export for current shell (caller must persist if needed)
echo "TEXMFHOME=$TEXMFHOME" >> ${GITHUB_ENV:-/dev/null} 2>/dev/null || true

# =============================================================================
# Step 4: Configure TEXINPUTS for @resources and @local packages
# =============================================================================
echo ""
echo "4️⃣  Configuring TEXINPUTS for @resources and @local packages..."

# Add @resources packages directory
export TEXINPUTS="${REPO_ROOT}/@resources/texlive/texmf-local/tex/latex//:${TEXINPUTS:-}"

# Add @local directory (needed for owner.tex, config.ltx, etc.)
# The double slash (//) allows LaTeX to search subdirectories recursively
export TEXINPUTS="${REPO_ROOT}/@local//:${TEXINPUTS}"

echo "   ✅ TEXINPUTS configured"
echo "   ✅ Includes: @resources/texlive/texmf-local/tex/latex/"
echo "   ✅ Includes: @local/"

# Export for GitHub Actions
echo "TEXINPUTS=$TEXINPUTS" >> ${GITHUB_ENV:-/dev/null} 2>/dev/null || true

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ HAFiscal Minimal LaTeX Environment Ready"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📦 Verified packages:"
echo "   - catchfile"
echo "   - beamer"
echo ""
echo "📄 Local packages (45 total, includes pdfsuppressruntime + pgf for beamer):"
echo "   - Location: @local/texlive/texmf-local/tex/latex/"
echo "   - TEXMFHOME: $TEXMFHOME"
echo ""
echo "✅ LaTeX environment verified and configured"
echo ""
