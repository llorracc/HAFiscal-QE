# HAFiscal Quick Reference

Quick commands and information for working with HAFiscal.

## One-Line Installation

### macOS

```bash
brew install --cask mactex && curl -LsSf https://astral.sh/uv/install.sh | sh && git clone {{REPO_URL}}.git && cd {{REPO_NAME}} && ./reproduce/reproduce_environment_comp_uv.sh
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get install -y texlive-full build-essential curl git && curl -LsSf https://astral.sh/uv/install.sh | sh && git clone {{REPO_URL}}.git && cd {{REPO_NAME}} && ./reproduce/reproduce_environment_comp_uv.sh
```

---

## Interactive Dashboard
**No installation required** — explore results in your browser:
| Task | Command/Link |
|------|--------------|
| Launch in browser | [![Launch](https://img.shields.io/badge/Launch-Dashboard-orange)](https://mybinder.org/v2/gh/llorracc/HAFiscal-Public/HEAD?urlpath=voila%2Frender%2Fdashboard%2Fapp.ipynb) |
| Run locally | `cd dashboard && ./start-dashboard.sh` |
| Run with Voila | `cd dashboard && voila app.ipynb` |
| Documentation | [DASHBOARD.md](DASHBOARD.md) |
| Full docs | [dashboard/DASHBOARD_README.md](../dashboard/DASHBOARD_README.md) |
---
## Common Commands

### Environment Setup

```bash
# Setup environment (first time)
./reproduce/reproduce_environment_comp_uv.sh
# Note: UV automatically activates the environment in new shells - manual activation usually not needed

# Activate environment manually if needed (UV - architecture-specific):
# source .venv-linux-x86_64/bin/activate  (Intel/AMD Linux)
# source .venv-darwin-arm64/bin/activate  (Apple Silicon macOS)
# source .venv-darwin-x86_64/bin/activate (Intel macOS)

# Activate environment (Conda)
conda activate hafiscal
```

### Document Generation

```bash
# Generate main paper and slides (~5-10 min)
./reproduce.sh --docs main

# Generate all documents including subdirectories
./reproduce.sh --docs all

# Quick debug build
BUILD_MODE=SHORT ./reproduce.sh --docs main --quick
```

### Computational Reproduction

```bash
# Minimal computation (~1 hour)
./reproduce.sh --comp min

# Full computation (4-5 days on a high-end 2025 laptop)
./reproduce.sh --comp full

# Maximum computation including robustness (~5 days on a high-end 2025 laptop)
./reproduce.sh --comp max

# Everything (documents + computation)
./reproduce.sh --all
```

### Testing

```bash
# Quick compatibility test (no Docker)
./reproduce/test-cross-platform.sh

# Comprehensive Ubuntu 22.04 test (requires Docker)
./reproduce/test-ubuntu-22.04.sh
```

---

## File Locations

### Main Outputs

- `HAFiscal.pdf` - Main paper
- `HAFiscal-Slides.pdf` - Presentation slides

### Configuration

- `pyproject.toml` - Python dependencies
- `uv.lock` - Locked dependency versions
- `.latexmkrc` - LaTeX compilation config
- `.gitattributes` - Line ending config (ensures cross-platform compatibility)

### Documentation

- `README.md` - Main documentation
- `INSTALLATION.md` - Platform-specific setup
- `TROUBLESHOOTING.md` - Common issues
- `reproduce/README.md` - Reproduction scripts

---

## Directory Structure

```
HAFiscal/
├── Code/                   # Computational code
│   ├── HA-Models/         # Heterogeneous agent models
│   └── Empirical/         # Empirical analysis
├── Figures/               # Figure generation
├── Tables/                # Table generation
├── Subfiles/              # LaTeX subfiles
├── reproduce/             # Reproduction scripts
├── HAFiscal.tex          # Main LaTeX document
├── HAFiscal.pdf          # Generated paper
└── .venv/                # Python environment (UV)
```

---

## Environment Variables

### LaTeX Compilation

```bash
# Build mode
BUILD_MODE=SHORT    # Quick debug build
BUILD_MODE=LONG     # Full build (default)

# Verbosity
VERBOSITY_LEVEL=quiet   # Minimal output
VERBOSITY_LEVEL=normal  # Default
VERBOSITY_LEVEL=verbose # Detailed output
VERBOSITY_LEVEL=debug   # Maximum detail

# Example
BUILD_MODE=SHORT VERBOSITY_LEVEL=verbose ./reproduce.sh --docs main
```

### BibTeX File Paths (Advanced)

**Note**: These are automatically set by `reproduce.sh`. Manual configuration is rarely needed.

```bash
# Bibliography file locations (.bib files)
BIBINPUTS=@resources/texlive/texmf-local/bibtex/bib/:resources-private/references/

# Bibliography style file locations (.bst files)  
BSTINPUTS=qe/:@resources/texlive/texmf-local/bibtex/bst/
```

---

## Troubleshooting Quick Fixes

### LaTeX not found

```bash
# macOS
export PATH="/Library/TeX/texbin:$PATH"

# Check
pdflatex --version
```

### Python environment not working

```bash
# Reinstall
rm -rf .venv-*  # Remove architecture-specific venvs
./reproduce/reproduce_environment_comp_uv.sh
# UV automatically activates the environment - no manual activation needed
# Or manually: source .venv-{platform}-{arch}/bin/activate
```

### Scripts permission denied

```bash
chmod +x reproduce.sh reproduce/*.sh
```

### Compilation errors

```bash
# Clean and rebuild
rm -f *.aux *.bbl *.blg *.log
./reproduce.sh --docs main
```

---

## Platform-Specific Notes

### macOS

- Use `brew` for LaTeX: `brew install --cask mactex`
- Use `zsh` by default (not bash)
- Shell config: `~/.zshrc`

### Linux

- Use `apt-get` for LaTeX: `sudo apt-get install texlive-full`
- Shell config: `~/.bashrc`
- May need: `sudo apt-get install build-essential`

### Windows (WSL2)

- Install WSL2: `wsl --install` (PowerShell as Admin)
- Work in WSL filesystem (`~/HAFiscal`) not Windows (`/mnt/c/...`)
- Shell config: `~/.bashrc` (in Ubuntu)

---

## Time Estimates

| Task | Time |
|------|------|
| Installation | 10-30 min |
| Environment setup (UV) | ~5 sec |
| Environment setup (Conda) | ~3 min |
| Document generation | 5-10 min |
| Minimal computation | ~1 hour |
| Full computation | 4-5 days on a high-end 2025 laptop |
| Cross-platform test | ~1 min |
| Docker Ubuntu test | ~2 min |

---

## Keyboard Shortcuts

### Interactive Menu (`./reproduce.sh`)

- `1` - Documents only
- `2` - Minimal computation
- `3` - Full computation
- `q` - Quit

---

## URLs and Links

- **Main Repository**: {{REPO_URL}}
- **Econ-ARK**: <https://econ-ark.org>
- **UV Package Manager**: <https://astral.sh/uv>
- **MacTeX**: <https://tug.org/mactex/>
- **TeX Live**: <https://tug.org/texlive/>

---

## Getting Help

- Check [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
- See [`INSTALLATION.md`](INSTALLATION.md)
- Search GitHub issues
- Create new issue with details

---

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| macOS (Intel) | ✅ Tested | Fully supported |
| macOS (Apple Silicon) | ✅ Tested | M1/M2/M3 supported |
| Ubuntu 22.04 LTS | ✅ Tested | Recommended Linux distro |
| Other Linux | ✅ Likely works | If dependencies available |
| Windows WSL2 (Ubuntu 22.04) | ✅ Tested | Recommended for Windows |
| Windows (native) | ❌ Not supported | Use WSL2 instead |

---

## Python Packages

Key dependencies (managed by UV or Conda):

- `econ-ark` (HARK) - Heterogeneous agent modeling
- `sequence-jacobian` - Jacobian computation
- `numpy`, `scipy` - Numerical computing
- `matplotlib` - Plotting
- `pandas` - Data manipulation

---

## LaTeX Packages

Key packages required:

- `latexmk` - Automated compilation
- `econark` - Document class (included)
- `subfiles` - Modular documents
- `amsmath` - Mathematics
- `hyperref` - Cross-references
- `natbib` - Bibliography

---

**Last Updated**: 2025-10-22

For comprehensive documentation, see [`README.md`](README.md).
