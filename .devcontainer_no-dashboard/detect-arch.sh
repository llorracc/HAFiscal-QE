#!/bin/bash
# Architecture detection script for TeX Live 2025
# Detects the correct TeX Live binary directory for the current architecture

set -e

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)
        TEXLIVE_ARCH="x86_64-linux"
        ;;
    aarch64|arm64)
        TEXLIVE_ARCH="aarch64-linux"
        ;;
    *)
        echo "Warning: Unknown architecture $ARCH, attempting auto-detection..." >&2
        TEXLIVE_ARCH=""
        ;;
esac

# Find the TeX Live binary directory
if [ -d "/usr/local/texlive/2025/bin" ]; then
    if [ -n "$TEXLIVE_ARCH" ] && [ -d "/usr/local/texlive/2025/bin/$TEXLIVE_ARCH" ]; then
        # Use the detected architecture
        TEXLIVE_BIN="/usr/local/texlive/2025/bin/$TEXLIVE_ARCH"
    else
        # Fallback: find the first available directory
        TEXLIVE_BIN=$(find /usr/local/texlive/2025/bin -type d -mindepth 1 -maxdepth 1 | head -1)
    fi
    
    if [ -n "$TEXLIVE_BIN" ] && [ -d "$TEXLIVE_BIN" ]; then
        echo "$TEXLIVE_BIN"
        exit 0
    fi
fi

# If we get here, TeX Live is not installed
echo "Error: TeX Live 2025 binary directory not found" >&2
exit 1

