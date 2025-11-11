#!/bin/bash
# =============================================================================
# Install Git Hooks for HAFiscal Development
# =============================================================================
# This script installs recommended git hooks, including SST validation.
#
# Usage:
#   bash @resources/environment/install-hooks.sh
#
# What it does:
#   - Installs pre-commit hook with SST validation
#   - Backs up existing hooks
#   - Makes hooks executable
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🪝 Installing HAFiscal Git Hooks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$REPO_ROOT"

# Ensure hooks directory exists
if [ ! -d .git/hooks ]; then
    echo "Creating .git/hooks directory..."
    mkdir -p .git/hooks
fi

# Install pre-commit hook
HOOK_TEMPLATE="@resources/environment/pre-commit-hook-template"
HOOK_DEST=".git/hooks/pre-commit"

if [ ! -f "$HOOK_TEMPLATE" ]; then
    echo "❌ Error: Hook template not found at $HOOK_TEMPLATE"
    exit 1
fi

# Backup existing hook if present
if [ -f "$HOOK_DEST" ]; then
    BACKUP="$HOOK_DEST.backup.$(date +%Y%m%d_%H%M%S)"
    echo "📦 Backing up existing pre-commit hook to:"
    echo "   $BACKUP"
    cp "$HOOK_DEST" "$BACKUP"
fi

# Install hook
echo "📥 Installing pre-commit hook..."
cp "$HOOK_TEMPLATE" "$HOOK_DEST"
chmod +x "$HOOK_DEST"

echo "✅ Pre-commit hook installed"
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Git Hooks Installation Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Installed hooks:"
echo "  ✅ pre-commit - Safety checks + SST validation"
echo ""
echo "What this does:"
echo "  • Validates Single Source of Truth (SST) pattern"
echo "  • Prevents accidental massive deletions"
echo "  • Warns about risky LaTeX file changes"
echo "  • Requires confirmation for large commits"
echo ""
echo "To bypass a hook (use sparingly):"
echo "  git commit --no-verify"
echo ""
echo "Documentation:"
echo "  @resources/environment/README.md"
echo ""

