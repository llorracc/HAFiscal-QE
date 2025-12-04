#!/bin/bash
# Fix LaTeX compatibility issues in devcontainer
# Moves packages that are too new for LaTeX 2021 kernel

set -e

# Detect workspace directory dynamically
# Try to get workspace name from current directory or script location
if [ -n "$PWD" ] && [[ "$PWD" == /workspaces/* ]]; then
    REPO_ROOT="$PWD"
elif [ -n "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    if [[ "$WORKSPACE_ROOT" == /workspaces/* ]]; then
        REPO_ROOT="$WORKSPACE_ROOT"
    else
        # Try /workspaces with basename
        WORKSPACE_NAME="$(basename "$WORKSPACE_ROOT")"
        REPO_ROOT="/workspaces/$WORKSPACE_NAME"
    fi
else
    # Fallback
    REPO_ROOT="/workspaces/$(basename "$PWD" 2>/dev/null || echo "HAFiscal-Latest")"
fi

LOCAL_LATEX="$REPO_ROOT/@local/texlive/texmf-local/tex/latex"
BACKUP_DIR="/tmp/latex-incompatible-packages"

echo "🔧 Fixing LaTeX compatibility for devcontainer..."
echo "   LaTeX kernel: $(pdflatex --version | head -1)"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# List of packages incompatible with LaTeX 2021-11-15
INCOMPATIBLE_PACKAGES=(
    "koma-script"  # v3.48 requires LaTeX >= 2022-06-01
    "hyperref"     # 2025 version requires LaTeX >= 2025-11-01
)

MOVED_COUNT=0

for pkg in "${INCOMPATIBLE_PACKAGES[@]}"; do
    PKG_PATH="$LOCAL_LATEX/$pkg"
    if [ -d "$PKG_PATH" ]; then
        echo "   Moving $pkg to $BACKUP_DIR/"
        mv "$PKG_PATH" "$BACKUP_DIR/"
        MOVED_COUNT=$((MOVED_COUNT + 1))
    elif [ -d "$BACKUP_DIR/$pkg" ]; then
        echo "   ✓ $pkg already moved"
    else
        echo "   ℹ $pkg not found (system version will be used)"
    fi
done

echo ""
if [ $MOVED_COUNT -gt 0 ]; then
    echo "✅ Moved $MOVED_COUNT incompatible package(s)"
    echo "   System-provided compatible versions will be used instead"
else
    echo "✅ All incompatible packages already moved"
fi

echo ""
echo "📋 Package versions now in use:"
echo "   - koma-script: system v3.35 (2021/11/13)"
echo "   - hyperref: system 2021 version"
echo ""
echo "🎯 You can now compile directly:"
echo "   pdflatex -interaction=nonstopmode HAFiscal.tex"
echo "   ./reproduce.sh --docs main"

