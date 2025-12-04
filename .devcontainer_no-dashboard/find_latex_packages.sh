#!/bin/bash
# Script to find all LaTeX packages used in HAFiscal project
# This will help determine minimal TeX Live apt packages needed

set -e

echo "🔍 Finding LaTeX packages used in HAFiscal project..."
echo ""

# Get the project root (parent of .devcontainer)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📂 Project root: $PROJECT_ROOT"
echo ""

# Find all .tex files
echo "📄 Finding .tex files..."
TEX_FILES=$(find . -name "*.tex" \
  -not -path "./.venv/*" \
  -not -path "./reproduce/*" \
  -not -path "./.git/*" \
  -not -path "./node_modules/*" \
  | sort)

echo "Found $(echo "$TEX_FILES" | wc -l) .tex files:"
echo "$TEX_FILES" | head -20
echo ""

# Extract all \usepackage and \RequirePackage commands
echo "📦 Extracting package names from .tex files..."
PACKAGES=$(echo "$TEX_FILES" | xargs grep -h -E '\\(usepackage|RequirePackage)' 2>/dev/null \
  | sed -E 's/.*\\(usepackage|RequirePackage)(\[.*\])?\{([^}]+)\}.*/\3/' \
  | tr ',' '\n' \
  | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' \
  | sort -u)

echo "Found $(echo "$PACKAGES" | wc -l) unique LaTeX packages:"
echo "$PACKAGES"
echo ""

# Create a temporary mapping file for package -> apt package
cat > /tmp/latex_pkg_mapping.txt << 'MAPPING'
# Format: latex_package -> apt_package
# Common packages in texlive-latex-recommended
changepage -> texlive-latex-recommended
caption -> texlive-latex-recommended
enumitem -> texlive-latex-recommended
footmisc -> texlive-latex-recommended
geometry -> texlive-latex-recommended
hyperref -> texlive-latex-recommended
natbib -> texlive-latex-recommended
xcolor -> texlive-latex-recommended

# Common packages in texlive-latex-extra
appendix -> texlive-latex-extra
cancel -> texlive-latex-extra
currfile -> texlive-latex-extra
dsfont -> texlive-fonts-extra
etoolbox -> texlive-latex-extra
moreverb -> texlive-latex-extra
multicol -> texlive-latex-extra
placeins -> texlive-latex-extra
setspace -> texlive-latex-extra
subfiles -> texlive-latex-extra
titling -> texlive-latex-extra
verbatim -> texlive-latex-extra
xspace -> texlive-latex-extra

# Fonts
amsfonts -> texlive-fonts-recommended
amssymb -> texlive-fonts-recommended
bbm -> texlive-fonts-extra
pxfonts -> texlive-fonts-extra

# Math/Science
amsmath -> texlive-latex-base
mathtools -> texlive-latex-extra
siunitx -> texlive-science

# Bibliography
bibentry -> texlive-latex-extra
harvard -> texlive-bibtex-extra
natbib -> texlive-latex-recommended

# Graphics
graphicx -> texlive-latex-base
tikz -> texlive-pictures
pgfplots -> texlive-pictures

# Tables
booktabs -> texlive-latex-extra
longtable -> texlive-latex-recommended
tabularx -> texlive-latex-extra

# Other
soul -> texlive-latex-extra
ulem -> texlive-latex-extra
MAPPING

echo "📊 Analyzing package requirements..."
echo ""

# Initialize counters for apt packages
declare -A apt_packages

# For each LaTeX package, try to find which apt package provides it
while IFS= read -r pkg; do
  # Skip empty lines
  [[ -z "$pkg" ]] && continue
  
  # Look up in our mapping
  apt_pkg=$(grep "^$pkg ->" /tmp/latex_pkg_mapping.txt 2>/dev/null | cut -d'>' -f2 | xargs)
  
  if [[ -n "$apt_pkg" ]]; then
    apt_packages["$apt_pkg"]=1
  else
    # Unknown package
    apt_packages["unknown"]=1
    echo "⚠️  Unknown mapping for: $pkg"
  fi
done <<< "$PACKAGES"

echo ""
echo "=========================================="
echo "📦 Required APT Packages Summary"
echo "=========================================="
echo ""

# Sort and display unique apt packages
for apt_pkg in "${!apt_packages[@]}"; do
  if [[ "$apt_pkg" != "unknown" ]]; then
    echo "  ✓ $apt_pkg"
  fi
done | sort

echo ""
echo "=========================================="
echo "🎯 Recommended minimal package list:"
echo "=========================================="
echo ""
echo "sudo apt-get install -y \\"
echo "  latexmk \\"

# Always include base and recommended
echo "  texlive-latex-base \\"
echo "  texlive-latex-recommended \\"

# Add other packages if found
for apt_pkg in texlive-latex-extra texlive-fonts-recommended texlive-fonts-extra texlive-science texlive-bibtex-extra texlive-pictures biber ghostscript; do
  if [[ -n "${apt_packages[$apt_pkg]}" ]]; then
    echo "  $apt_pkg \\"
  fi
done | sed '$ s/ \\$//'  # Remove trailing backslash from last line

echo ""
echo "=========================================="
echo "✅ Analysis complete!"
echo "=========================================="

# Cleanup
rm -f /tmp/latex_pkg_mapping.txt

