#!/bin/bash
# Extract packages that must be installed individually from required-latex-packages.txt
# This script filters out packages that are in scheme-basic (which are already installed)
# and returns all other packages that must be installed individually via tlmgr
# This includes both standalone packages AND packages that would be in collection-latex
# (since we're not installing collection-latex as a collection, we install them individually)

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_FILE="${SCRIPT_DIR}/required-latex-packages.txt"

if [ ! -f "$PACKAGE_FILE" ]; then
    echo "Error: Package file not found: $PACKAGE_FILE" >&2
    exit 1
fi

# Extract packages marked as "standalone" OR "collection-latex" (exclude only scheme-basic)
# Format: package-name # standalone or package-name # collection-latex
grep -E '^[^#]*#.*(standalone|collection-latex)' "$PACKAGE_FILE" | \
    sed 's/#.*$//' | \
    sed 's/^[[:space:]]*//' | \
    sed 's/[[:space:]]*$//' | \
    grep -v '^$' | \
    grep -v '^#'
