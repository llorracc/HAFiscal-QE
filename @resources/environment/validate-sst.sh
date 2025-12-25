#!/bin/bash
# =============================================================================
# SST Validation Script
# =============================================================================
# Ensures that .devcontainer and GitHub Actions properly use SST scripts
# and don't contain direct LaTeX installation commands.
#
# This prevents accidental SST bypass where someone adds LaTeX setup
# directly to these files instead of modifying the master SST script.
#
# Usage:
#   bash @resources/environment/validate-sst.sh
#
# Exit codes:
#   0 = SST pattern properly maintained
#   1 = SST violation detected
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🔍 Validating Single Source of Truth (SST) pattern..."
echo ""

VIOLATIONS=0

# =============================================================================
# Check 1: Ensure SST scripts are called
# =============================================================================
echo "1️⃣  Checking that SST scripts are properly called..."

if ! grep -q "setup-latex-minimal.sh" "$REPO_ROOT/.devcontainer/setup.sh"; then
    echo "   ❌ VIOLATION: .devcontainer/setup.sh does not call setup-latex-minimal.sh"
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo "   ✅ .devcontainer/setup.sh calls SST script"
fi

if ! grep -q "setup-latex-minimal.sh" "$REPO_ROOT/.github/workflows/push-build-docs.yml"; then
    echo "   ❌ VIOLATION: push-build-docs.yml does not call setup-latex-minimal.sh"
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo "   ✅ GitHub Actions workflow calls SST script"
fi

# =============================================================================
# Check 2: Ensure no direct LaTeX installation commands
# =============================================================================
echo ""
echo "2️⃣  Checking for direct LaTeX installation (SST bypass)..."

# Check .devcontainer/setup.sh
# Exclude the line that calls the SST script itself
DEVCONTAINER_LATEX=$(grep -n "apt-get install.*tex\|tlmgr install" "$REPO_ROOT/.devcontainer/setup.sh" | grep -v "setup-latex-minimal.sh" || true)
if [ -n "$DEVCONTAINER_LATEX" ]; then
    echo "   ❌ VIOLATION: .devcontainer/setup.sh contains direct LaTeX installation:"
    echo "$DEVCONTAINER_LATEX" | sed 's/^/      /'
    echo "   → Should be in @resources/environment/setup-latex-minimal.sh instead"
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo "   ✅ .devcontainer/setup.sh does not bypass SST"
fi

# Check GitHub Actions workflow
WORKFLOW_LATEX=$(grep -n "apt-get install.*tex\|tlmgr install" "$REPO_ROOT/.github/workflows/push-build-docs.yml" | grep -v "setup-latex-minimal.sh" || true)
if [ -n "$WORKFLOW_LATEX" ]; then
    echo "   ❌ VIOLATION: push-build-docs.yml contains direct LaTeX installation:"
    echo "$WORKFLOW_LATEX" | sed 's/^/      /'
    echo "   → Should be in @resources/environment/setup-latex-minimal.sh instead"
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo "   ✅ GitHub Actions workflow does not bypass SST"
fi

# =============================================================================
# Check 3: Verify SST master script exists
# =============================================================================
echo ""
echo "3️⃣  Checking that SST master script exists..."

if [ ! -f "$REPO_ROOT/@resources/environment/setup-latex-minimal.sh" ]; then
    echo "   ❌ VIOLATION: SST master script not found"
    echo "      Expected: @resources/environment/setup-latex-minimal.sh"
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo "   ✅ SST master script exists"
    
    # Check if it's executable
    if [ ! -x "$REPO_ROOT/@resources/environment/setup-latex-minimal.sh" ]; then
        echo "   ⚠️  Warning: SST script is not executable"
        echo "      Run: chmod +x @resources/environment/setup-latex-minimal.sh"
    fi
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $VIOLATIONS -eq 0 ]; then
    echo "✅ SST VALIDATION PASSED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "All environments properly use SST pattern."
    echo "LaTeX setup is centralized in:"
    echo "  → @resources/environment/setup-latex-minimal.sh"
    echo ""
    exit 0
else
    echo "❌ SST VALIDATION FAILED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Found $VIOLATIONS violation(s) of SST pattern."
    echo ""
    echo "To fix:"
    echo "  1. Remove direct LaTeX installation from flagged files"
    echo "  2. Move LaTeX setup logic to @resources/environment/setup-latex-minimal.sh"
    echo "  3. Ensure files call the SST script: bash @resources/environment/setup-latex-minimal.sh"
    echo ""
    echo "Documentation: @resources/environment/README.md"
    echo ""
    exit 1
fi

