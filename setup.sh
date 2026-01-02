#!/bin/bash
# HAFiscal Repository Setup Script
#
# This script fixes executable permissions for shell scripts and Python scripts
# that may have been lost during git clone on some systems.
#
# Usage: ./setup.sh
# Or:    bash setup.sh

set -e

echo "Setting executable permissions for shell scripts and Python scripts..."

# Fix permissions for all .sh files
find . -name "*.sh" -type f ! -path "./.git/*" -exec chmod +x {} \;

# Fix permissions for reproduce.py if it exists
if [[ -f "reproduce.py" ]]; then
    chmod +x reproduce.py
fi

echo "✓ Executable permissions set successfully"
echo ""
echo "You can now run scripts directly, for example:"
echo "  ./reproduce.sh --help"
