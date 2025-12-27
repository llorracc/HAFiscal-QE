# Local LaTeX Packages for HAFiscal

## Overview

This directory contains **minimal LaTeX packages** required to compile HAFiscal.tex with only `texlive-latex-base` and `texlive-latex-recommended` installed.

By using this approach, we avoid installing the massive `texlive-latex-extra` package (~4GB) and instead include only the specific packages needed (~40 packages, <100MB total).

## LaTeX Installation Strategy

### Base System (via apt/system package manager)

- `latexmk` - Build automation tool
- `texlive-latex-base` - Core LaTeX system (~40MB)
- `texlive-latex-recommended` - Common packages (~80MB)
- **Total:** ~122MB

### Additional Packages (in this directory)
Packages stored in `@local/texlive/texmf-local/tex/latex/` are automatically discovered via:

1. Environment variable: `TEXMFHOME=/path/to/@local/texlive/texmf-local`
2. LaTeX search path: Configured in `@resources/tex-paths.ltx` (superseded `tex-add-search-paths.tex` in Oct 2025)

## Packages Included

### Actually Required for HAFiscal
These packages are used by HAFiscal.tex and its subfiles:

1. **subfiles** - Multi-file document structure (used extensively)
2. **import** - File inclusion with path management
3. **cancel** - Math strikethrough notation
4. **moreverb** - Enhanced verbatim (for `\begin{verbatimwrite}`)
5. **environ** - Environment definition utilities
6. **trimspaces** - String trimming utilities
7. **nth** - Ordinal number formatting (\nth{20}, etc.)
8. **changepage** - Page layout adjustments
9. **currfile** - Current file name tracking
10. **ncctools** - Various utilities (from ncclatex bundle)
11. And ~30 more supporting packages from `reproduce/required_latex_packages.txt`

### Eliminated (Previously Required but Not Actually Used)

The following packages were removed from HAFiscal's dependency chain by modifying `.sty`/`.cls` files:

1. **datetime2** + **tracklang** - Removed from `econark.cls` (HAFiscal only uses `\today`)
2. **perpage** - Removed from `econark.cls` (titlepage footnotes not used)
3. **manyfoot** - Removed from `econark.cls` (titlepage footnotes not used)
4. **footmisc** - Removed from `econark.cls` (titlepage footnotes not used)
5. **soul** - Removed from `@local/local.sty` (highlighting not used in main document)
6. **lmodern** - Removed from `@local/local.sty` (cosmetic font, using Computer Modern)
7. **wasysym** - Removed from `econark-ark-required.sty` (symbols not used)

## Size Comparison

| Approach | Size | Pros | Cons |
|----------|------|------|------|
| **Full TeXLive** | ~4GB | Everything included | Slow installation, large containers |
| **texlive-latex-extra** | ~2GB | Most packages | Still very large |
| **Base + Recommended + This Directory** | ~200MB | Fast installation, git-tracked | Requires initial discovery |

## How This Was Created

The packages in this directory were discovered through **iterative compilation**:

1. Start with base + recommended only
2. Attempt to compile HAFiscal.tex
3. Identify missing package from error
4. Check if package is actually used:
   - **If used:** Download `.sty` file from CTAN and add to this directory
   - **If not used:** Remove requirement from `.cls`/`.sty` file
5. Repeat until successful compilation

## Maintenance

**When to update this directory:**

- New LaTeX package dependencies are added to HAFiscal
- Package files are updated on CTAN (rare for stable packages)
- Switching to a newer LaTeX base system

**How to update:**

```bash
# Download individual package from CTAN
cd @local/texlive/texmf-local/tex/latex/
mkdir -p PACKAGENAME
cd PACKAGENAME
wget https://www.ctan.org/tex-archive/macros/latex/contrib/PACKAGENAME/PACKAGENAME.sty
```

## Usage

### In DevContainer (`.devcontainer/setup.sh`)

```bash
# Set TEXMFHOME to point to local packages
# Detect repo root dynamically
REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
export TEXMFHOME="${REPO_ROOT}/@local/texlive/texmf-local"
echo "export TEXMFHOME=${TEXMFHOME}" >> ~/.bashrc
```

### On Host Machine

The `@resources/tex-paths.ltx` file (loaded by `._relpath-to-latexroot.ltx`) automatically configures LaTeX to search this directory.

## See Also

- `reproduce/required_latex_packages.txt` - **Updated list of required packages** (includes packages discovered through iteration)
- `reproduce/reproduce_environment_texlive.sh` - TeXLive verification script (reads from required_latex_packages.txt)
- `binder/apt.txt` - System packages for MyBinder.org environment (now minimal: base + recommended only)
- `docs/LATEX_MINIMAL_SETUP.md` - Complete setup guide and rationale
