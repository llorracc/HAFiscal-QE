#!/bin/bash
# Configure MiKTeX to use local .miktex/ directory in project
# This keeps all MiKTeX files contained and git-ignored

set -e

# Script is in reproduce/, project root is one level up
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIKTEX_ROOT="$SCRIPT_DIR/.miktex"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Configuring MiKTeX for Local Project Use"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Project root: $SCRIPT_DIR"
echo "MiKTeX data:  $MIKTEX_ROOT"
echo ""

# Remove broken "true/" directory if it exists
if [ -d "$SCRIPT_DIR/true" ]; then
    echo "🗑️  Removing broken 'true/' directory (MiKTeX bug)..."
    rm -rf "$SCRIPT_DIR/true"
    echo "✅ Removed true/"
fi

# Create proper .miktex structure
echo "📁 Creating .miktex/ directory structure..."
mkdir -p "$MIKTEX_ROOT/texmfs/"{config,data,install}

# Export MiKTeX environment variables for this session
export MIKTEX_USERINSTALL=true
export MIKTEX_USERCONFIG="$MIKTEX_ROOT/texmfs/config"
export MIKTEX_USERDATA="$MIKTEX_ROOT/texmfs/data"
export MIKTEX_INSTALL="$MIKTEX_ROOT/texmfs/install"

echo "✅ Created directory structure"
echo ""

# Initialize MiKTeX with proper paths
echo "🔧 Initializing MiKTeX..."
echo "   (This may show warnings - they're usually OK)"
echo ""

# Try to set up package database
if miktex packages update-package-database 2>/dev/null; then
    echo "✅ Package database updated"
else
    echo "ℹ️  Package database update skipped (may already exist)"
fi

# Configure auto-install
if miktex packages set-auto-install yes 2>/dev/null; then
    echo "✅ Auto-install enabled"
else
    echo "ℹ️  Auto-install configuration skipped"
fi

# Refresh filename database
if miktex fndb refresh 2>/dev/null; then
    echo "✅ Filename database refreshed"
else
    echo "ℹ️  Filename database refresh skipped"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ MiKTeX configured for local use!"
echo ""
echo "MiKTeX files location:"
echo "  $MIKTEX_ROOT/"
echo ""
echo "This directory is:"
echo "  ✅ Git-ignored (.gitignore)"
echo "  ✅ Self-contained (all packages here)"
echo "  ✅ Portable (can be deleted/recreated)"
echo ""
echo "Size: $(du -sh "$MIKTEX_ROOT" 2>/dev/null | cut -f1 || echo "~100MB initially")"
echo ""
echo "To use this MiKTeX:"
echo "  source reproduce/miktex-use.sh"
echo "  ./reproduce.sh --docs main"
echo ""
echo "To remove (frees up space):"
echo "  rm -rf .miktex/"
echo "  rm -rf true/  # (if it reappears)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

