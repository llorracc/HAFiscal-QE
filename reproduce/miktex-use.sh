#!/bin/bash
# Source this file to use project-local MiKTeX
# Usage: source reproduce/miktex-use.sh

# Script is in reproduce/, project root is one level up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIKTEX_ROOT="$SCRIPT_DIR/.miktex"

# Set MiKTeX environment variables
export MIKTEX_USERINSTALL=true
export MIKTEX_USERCONFIG="$MIKTEX_ROOT/texmfs/config"
export MIKTEX_USERDATA="$MIKTEX_ROOT/texmfs/data"
export MIKTEX_INSTALL="$MIKTEX_ROOT/texmfs/install"

# Add MiKTeX binaries to PATH
export PATH="/usr/local/bin:$PATH"

echo "✅ Using project-local MiKTeX"
echo "   Data: $MIKTEX_ROOT/"

if command -v miktex-pdflatex >/dev/null 2>&1; then
    miktex-pdflatex --version | head -1
    echo "   pdflatex: $(which miktex-pdflatex)"
else
    echo "⚠️  MiKTeX binaries not found"
    echo "   Make sure MiKTeX is installed system-wide"
fi

echo ""
echo "Switch to TeX Live 2022: source ~/texlive2022.sh"

