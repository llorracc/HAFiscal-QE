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
#   1. Install base LaTeX: texlive-latex-base + texlive-latex-recommended (~122 MB)
#   2. Install texlive-pictures for PGF/TikZ (Beamer slides support) (~50 MB)
#   3. Use 45 additional packages from @local/texlive/texmf-local/ (in repo)
#      (includes pdfsuppressruntime + pgf for HAFiscal-Slides.tex)
#   4. Set TEXMFHOME to point to local packages
#
# Total LaTeX size: ~250 MB vs ~4 GB for full TeXLive installation
# =============================================================================

set -e

echo "📄 Installing MINIMAL LaTeX (HAFiscal SST)..."
echo "   - Base: texlive-latex-base + texlive-latex-recommended"
echo "   - Pictures: texlive-pictures (PGF/TikZ for Beamer slides)"
echo "   - Additional: 45 packages from @local/texlive/texmf-local/ (in repo)"
echo "     (includes pdfsuppressruntime + pgf for HAFiscal-Slides.tex)"

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
# Step 1: Install base LaTeX packages via apt
# =============================================================================
echo ""
echo "1️⃣  Installing base LaTeX packages..."

if command -v apt-get >/dev/null 2>&1; then
    # Ubuntu/Debian (DevContainer, GitHub Actions)
    if [ "$EUID" -eq 0 ] || [ "$USER" = "root" ]; then
        # Running as root
        apt-get update -qq
        apt-get install -y --no-install-recommends \
            latexmk \
            texlive-latex-base \
            texlive-latex-recommended \
            texlive-pictures
        apt-get clean
        rm -rf /var/lib/apt/lists/*
    else
        # Running as non-root (need sudo)
        sudo apt-get update -qq
        sudo apt-get install -y --no-install-recommends \
            latexmk \
            texlive-latex-base \
            texlive-latex-recommended \
            texlive-pictures
        sudo apt-get clean
        sudo rm -rf /var/lib/apt/lists/*
    fi
    echo "   ✅ Installed via apt-get"
else
    echo "   ⚠️  apt-get not available - assuming LaTeX already installed"
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
echo "📦 Installed packages:"
echo "   - latexmk"
echo "   - texlive-latex-base"
echo "   - texlive-latex-recommended"
echo ""
echo "📄 Local packages (45 total, includes pdfsuppressruntime + pgf for beamer):"
echo "   - Location: @local/texlive/texmf-local/tex/latex/"
echo "   - TEXMFHOME: $TEXMFHOME"
echo ""
echo "🎯 Total LaTeX size: ~200 MB (vs ~4 GB for full TeXLive)"
echo ""

