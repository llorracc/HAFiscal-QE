#!/bin/bash
# =============================================================================
# Setup Git Hooks for HAFiscal Development
# =============================================================================
# This script configures git to use hooks from .githooks/ directory.
# Hooks are tracked in git, so they're automatically available after clone.
#
# Usage:
#   bash @resources/environment/install-hooks.sh
#
# What it does:
#   - Configures core.hooksPath to use .githooks/ directory
#   - Ensures all hooks in .githooks/ are executable
#   - Verifies hooks are properly set up
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🪝 Setting Up HAFiscal Git Hooks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$REPO_ROOT"

# Check if .githooks directory exists
if [ ! -d .githooks ]; then
    echo "❌ Error: .githooks/ directory not found"
    echo "   Hooks should be tracked in git. If this is a fresh clone,"
    echo "   ensure you've pulled the latest changes."
    exit 1
fi

# Configure git to use .githooks/ directory
CURRENT_HOOKSPATH=$(git config core.hooksPath 2>/dev/null || echo "")
if [ "$CURRENT_HOOKSPATH" != ".githooks" ]; then
    echo "📝 Configuring git to use .githooks/ directory..."
    git config core.hooksPath .githooks
    echo "✅ Set core.hooksPath = .githooks"
else
    echo "✅ core.hooksPath already configured (.githooks)"
fi
echo ""

# Ensure all hooks are executable
echo "🔧 Making hooks executable..."
HOOKS_FOUND=0
for hook in .githooks/*; do
    if [ -f "$hook" ] && [ ! -L "$hook" ]; then
        # Skip backup files
        if [[ "$hook" != *.bak ]] && [[ "$hook" != *.backup* ]]; then
            chmod +x "$hook"
            HOOKS_FOUND=$((HOOKS_FOUND + 1))
        fi
    fi
done

if [ $HOOKS_FOUND -eq 0 ]; then
    echo "⚠️  Warning: No hooks found in .githooks/ directory"
else
    echo "✅ Made $HOOKS_FOUND hook(s) executable"
fi
echo ""

# List available hooks
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Git Hooks Setup Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Available hooks in .githooks/:"
for hook in .githooks/*; do
    if [ -f "$hook" ] && [ ! -L "$hook" ] && [[ "$hook" != *.bak ]] && [[ "$hook" != *.backup* ]]; then
        hook_name=$(basename "$hook")
        echo "  ✅ $hook_name"
    fi
done
echo ""

# Verify key hooks exist
if [ -f .githooks/pre-commit ]; then
    echo "Key hooks:"
    echo "  ✅ pre-commit - Safety checks + SST validation + gh-pages detection"
    if [ -f .githooks/pre-push ]; then
        echo "  ✅ pre-push - Pre-push validation"
    fi
    if [ -f .githooks/post-push ]; then
        echo "  ✅ post-push - GitHub Actions monitoring"
    fi
    if [ -f .githooks/post-checkout ]; then
        echo "  ✅ post-checkout - Environment change detection"
    fi
    echo ""
fi

echo "What hooks do:"
echo "  • pre-commit: Validates SST pattern, prevents massive deletions,"
echo "                warns about risky changes, skips checks on gh-pages"
echo "  • pre-push:   Validates before pushing to remote"
echo "  • post-push:  Monitors GitHub Actions workflows"
echo "  • post-checkout: Warns if environment files changed"
echo ""
echo "To bypass a hook (use sparingly):"
echo "  git commit --no-verify    # Skip pre-commit"
echo "  git push --no-verify      # Skip pre-push"
echo ""
echo "Note: Hooks are tracked in git, so they're automatically"
echo "      available after cloning. This script just ensures"
echo "      core.hooksPath is configured correctly."
echo ""
echo "Documentation:"
echo "  @resources/environment/README.md"
echo ""

