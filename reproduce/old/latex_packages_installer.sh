#!/bin/bash
# LaTeX Package Installer for HAFiscal Project
# Generated: 2025-10-06 10:17:33
#
# This script verifies all TeXLive LaTeX packages identified as used in the HAFiscal project.
# Excludes local packages from @resources/ and @local/ directories.
# Excludes packages that start with backslash (macros pointing to local packages).
#
# The script will:
# 1. Check for the existence of each package
# 2. Accumulate a list of missing packages
# 3. Report all missing packages and exit with error code 1 if any are missing

set -e  # Exit on error

# Colors for output
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    BLUE=$(tput setaf 4)
    RESET=$(tput sgr0)
else
    RED="" GREEN="" YELLOW="" BLUE="" RESET=""
fi

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
else
    echo "${RED}Unsupported OS: $OSTYPE${RESET}"
    exit 1
fi

echo "${BLUE}Detected OS: $OS${RESET}"
echo "${BLUE}Checking LaTeX packages...${RESET}"
echo ""

# List of TeXLive packages to check
PACKAGES=(
    "algorithmic"
    "amsfonts"
    "amsmath"
    "amssymb"
    "amsthm"
    "appendix"
    "array"
    "bbm"
    "booktabs"
    "caption"
    "color"
    "dcolumn"
    "dsfont"
    "enumerate"
    "enumitem"
    "epstopdf"
    "eurosym"
    "float"
    "floatrow"
    "fontenc"
    "geometry"
    "graphicx"
    "harvard"
    "hyperref"
    "inputenc"
    "mathtools"
    "multirow"
    "natbib"
    "nth"
    "pifont"
    "placeins"
    "pxfonts"
    "ragged2e"
    "rotating"
    "scrlayer-scrpage"
    "sectsty"
    "setspace"
    "siunitx"
    "soul"
    "subcaption"
    "subfig"
    "subfigure"
    "svg"
    "tabulary"
    "threeparttable"
    "ulem"
    "verbatim"
    "xcolor"
)

# Check if kpsewhich is available
if ! command -v kpsewhich >/dev/null 2>&1; then
    echo "${RED}Error: kpsewhich command not found${RESET}"
    echo "Please install TeX Live first"
    exit 1
fi

# Array to accumulate missing packages
MISSING_PACKAGES=()
FOUND_COUNT=0
TOTAL_COUNT=${#PACKAGES[@]}

echo "Checking $TOTAL_COUNT packages..."
echo ""

# Check each package
for pkg in "${PACKAGES[@]}"; do
    # Try to find the package with kpsewhich
    if kpsewhich "${pkg}.sty" >/dev/null 2>&1 || \
       kpsewhich "${pkg}.cls" >/dev/null 2>&1; then
        echo "${GREEN}✓${RESET} $pkg"
        ((FOUND_COUNT++))
    else
        echo "${RED}✗${RESET} $pkg ${YELLOW}(missing)${RESET}"
        MISSING_PACKAGES+=("$pkg")
    fi
done

echo ""
echo "----------------------------------------"
echo "Checked: $TOTAL_COUNT packages"
echo "Found: $FOUND_COUNT packages"
echo "Missing: ${#MISSING_PACKAGES[@]} packages"
echo "----------------------------------------"

# Report results
if [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
    echo ""
    echo "${GREEN}✅ SUCCESS: All required LaTeX packages are installed!${RESET}"
    exit 0
else
    echo ""
    echo "${RED}❌ ERROR: The following packages are missing:${RESET}"
    echo ""
    for pkg in "${MISSING_PACKAGES[@]}"; do
        echo "  - $pkg"
    done
    echo ""
    echo "${YELLOW}To install missing packages:${RESET}"
    echo ""
    if [[ "$OS" == "macos" ]]; then
        echo "  Using tlmgr (TeX Live Manager):"
        echo "  ${BLUE}tlmgr install ${MISSING_PACKAGES[*]}${RESET}"
    else
        echo "  Using apt-get (Debian/Ubuntu):"
        echo "  ${BLUE}sudo apt-get install texlive-latex-extra texlive-fonts-extra${RESET}"
        echo ""
        echo "  Or using tlmgr (if available):"
        echo "  ${BLUE}tlmgr install ${MISSING_PACKAGES[*]}${RESET}"
    fi
    echo ""
    exit 1
fi
