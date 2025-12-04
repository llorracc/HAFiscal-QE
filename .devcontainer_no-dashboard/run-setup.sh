#!/bin/bash
# Helper script to find and run setup.sh during container build
# This is called by postCreateCommand in devcontainer.json

set -e

echo "🔍 Searching for setup.sh..."
echo "Current directory: $(pwd)"
echo "Contents of /workspaces:"
ls -la /workspaces/ 2>/dev/null || echo "  /workspaces does not exist yet"

# Try to find workspace directories
WORKSPACE_DIRS=$(find /workspaces -maxdepth 1 -type d 2>/dev/null | grep -v '^/workspaces$' || echo '')

if [ -n "$WORKSPACE_DIRS" ]; then
    echo "Found workspace directories:"
    echo "$WORKSPACE_DIRS"
    for DIR in $WORKSPACE_DIRS; do
        if [ -f "$DIR/.devcontainer/setup.sh" ]; then
            echo "✅ Found setup.sh at: $DIR/.devcontainer/setup.sh"
            cd "$DIR"
            echo "Changed to directory: $(pwd)"
            bash .devcontainer/setup.sh
            exit 0
        fi
    done
fi

# Fallback: try hardcoded path
SCRIPT_PATH="/workspaces/HAFiscal-Latest/.devcontainer/setup.sh"
if [ -f "$SCRIPT_PATH" ]; then
    echo "✅ Using hardcoded path: $SCRIPT_PATH"
    cd /workspaces/HAFiscal-Latest
    bash .devcontainer/setup.sh
    exit 0
fi

# If we get here, setup.sh was not found
echo "❌ setup.sh not found. Tried:"
echo "  - Searched /workspaces for .devcontainer/setup.sh"
echo "  - Hardcoded path: $SCRIPT_PATH"
find /workspaces -name setup.sh 2>/dev/null || echo "    (no results)"
exit 1









