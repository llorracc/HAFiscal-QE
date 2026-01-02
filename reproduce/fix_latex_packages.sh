#!/bin/bash
# Fix script for missing LaTeX packages

set -e

echo "========================================"
echo "HAFiscal LaTeX Package Fix"
echo "========================================"
echo ""

# Detect TeX Live installation
if command -v tlmgr >/dev/null 2>&1; then
    TEXLIVE_BIN=$(dirname "$(which tlmgr)")
    echo "✅ Found TeX Live: $TEXLIVE_BIN"
    echo ""
    
    # List of commonly missing packages for HAFiscal
    PACKAGES=(
        "moreverb"      # verbatimwrite environment
        "booktabs"      # Professional tables
        "enumitem"      # Enhanced lists
        "siunitx"       # SI units
        "subfiles"      # Subfile support
        "natbib"        # Bibliography
        "hyperref"      # Hyperlinks
        "geometry"      # Page layout
        "amsmath"       # Math
        "amsfonts"      # Math fonts
    )
    
    echo "Checking for missing packages..."
    MISSING_PACKAGES=()
    
    for pkg in "${PACKAGES[@]}"; do
        if ! kpsewhich "${pkg}.sty" >/dev/null 2>&1; then
            MISSING_PACKAGES+=("$pkg")
            echo "  ❌ Missing: $pkg"
        else
            echo "  ✅ Found: $pkg"
        fi
    done
    
    if [[ ${#MISSING_PACKAGES[@]} -eq 0 ]]; then
        echo ""
        echo "✅ All required packages are installed"
        exit 0
    fi
    
    echo ""
    echo "Installing missing packages..."
    echo ""
    
    for pkg in "${MISSING_PACKAGES[@]}"; do
        echo "→ Installing $pkg..."
        sudo "$TEXLIVE_BIN/tlmgr" install "$pkg" || {
            echo "  ⚠️  Failed to install $pkg (may require sudo or package name differs)"
        }
    done
    
    echo ""
    echo "✅ Package installation complete"
    echo ""
    echo "If packages still fail, try:"
    echo "  sudo $TEXLIVE_BIN/tlmgr update --self"
    echo "  sudo $TEXLIVE_BIN/tlmgr install --reinstall <package-name>"
    
elif command -v pdflatex >/dev/null 2>&1; then
    echo "⚠️  TeX Live found but tlmgr not available"
    echo ""
    echo "Manual fixes:"
    echo "1. Install TeX Live with package manager:"
    echo "   macOS: brew install --cask mactex"
    echo "   Linux: sudo apt-get install texlive-full"
    echo ""
    echo "2. Or install minimal TeX Live and add packages:"
    echo "   Download from: https://www.tug.org/texlive/"
    echo ""
else
    echo "❌ LaTeX not found"
    echo ""
    echo "Installation options:"
    echo "1. macOS: brew install --cask mactex"
    echo "2. Linux: sudo apt-get install texlive-full"
    echo "3. Download from: https://www.tug.org/texlive/"
    exit 1
fi

