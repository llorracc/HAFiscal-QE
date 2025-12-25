# HAFiscal Installation Guide

**Version**: 2.0  
**Last Updated**: 2025-11-16  
**For**: {{REPO_NAME}} and econ-ark/HAFiscal

> **Note**: This guide applies to both the source repository ({{REPO_NAME}}) and the public repository (econ-ark/HAFiscal). For contributors editing the source, see [CONTRIBUTING.md](../CONTRIBUTING.md).

---

This guide provides detailed, platform-specific instructions for setting up HAFiscal on your system.

## Platform Support

HAFiscal is tested and supported on:

- **macOS** (Intel & Apple Silicon) ✅
- **Linux** (Ubuntu 22.04 LTS recommended) ✅
- **Windows** (via WSL2 with Ubuntu 22.04) ✅

## Prerequisites

### All Platforms

1. **LaTeX Distribution** - Required for document generation
2. **Python 3.9 (exactly)** - Required for computational reproduction
3. **Git** - For cloning the repository

### Storage Requirements

- **Minimum**: 2 GB (LaTeX + Python environment + code)
- **Recommended**: 5 GB (includes space for computational results)

### Time Requirements

- **Installation**: 10-30 minutes (depending on internet speed)
- **Document reproduction**: 5-10 minutes
- **Minimal computation**: ~1 hour
- **Full computation**: 4-5 days on high-end hardware

---

## macOS Installation

### Step 1: Install Homebrew (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Step 2: Install LaTeX

**Option A: Full MacTeX** (Recommended - 4.5 GB)

```bash
brew install --cask mactex
```

**Option B: BasicTeX** (Minimal - 100 MB, may need additional packages)

```bash
brew install --cask basictex
brew install latexmk
```

### Step 3: Install UV Package Manager (Recommended)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Add to your shell profile (UV installer will guide you):

```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

Then restart your terminal or run:

```bash
source ~/.zshrc  # or ~/.bash_profile for bash
```

### Step 4: Clone Repository

```bash
git clone {{REPO_URL}}.git
cd {{REPO_NAME}}
```

### Step 5: Setup Python Environment

**With UV** (Recommended - ~5 seconds):

```bash
./reproduce/reproduce_environment_comp_uv.sh
# This creates an architecture-specific venv (e.g., .venv-linux-x86_64/)
# New shells will auto-activate - no manual activation needed!

# Or manually:
uv sync
# Activate architecture-specific venv:
# source .venv-linux-x86_64/bin/activate  (Intel/AMD Linux)
# source .venv-darwin-arm64/bin/activate  (Apple Silicon)
```

**With Conda** (Alternative - ~2-3 minutes):

```bash
conda env create -f environment.yml
conda activate HAFiscal
```

### Step 6: Test Installation

```bash
# Test document generation
./reproduce.sh --docs main
```

**Success!** You should now have `HAFiscal.pdf` and `HAFiscal-Slides.pdf`.

### macOS Troubleshooting

**LaTeX not found:**

```bash
# Add MacTeX to PATH
export PATH="/Library/TeX/texbin:$PATH"
```

**UV command not found:**

```bash
# Check UV installation
ls -la ~/.cargo/bin/uv

# If missing, reinstall
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Python environment activation fails:**

```bash
# Make sure you're using the architecture-specific venv
# Examples:
source .venv-linux-x86_64/bin/activate  # Intel/AMD Linux
source .venv-darwin-arm64/bin/activate  # Apple Silicon

# Or use UV's run command
uv run python script.py
```

---

## Linux Installation (Ubuntu/Debian)

### Step 1: Update Package Manager

```bash
sudo apt-get update
```

### Step 2: Install LaTeX

**Option A: Full TeX Live** (Recommended - complete distribution)

```bash
sudo apt-get install texlive-full
```

**Option B: Medium TeX Live** (Faster install, most packages)

```bash
sudo apt-get install texlive texlive-latex-extra texlive-fonts-recommended
sudo apt-get install latexmk
```

### Step 3: Install Build Tools

```bash
sudo apt-get install build-essential curl git
```

### Step 4: Install UV Package Manager (Recommended)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Add to your shell profile:

```bash
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Step 5: Clone Repository

```bash
git clone {{REPO_URL}}.git
cd {{REPO_NAME}}
```

### Step 6: Setup Python Environment

**With UV** (Recommended - ~5 seconds):

```bash
./reproduce/reproduce_environment_comp_uv.sh
# This creates an architecture-specific venv (e.g., .venv-linux-x86_64/)
# New shells will auto-activate - no manual activation needed!

# Or manually:
uv sync
# Activate architecture-specific venv:
# source .venv-linux-x86_64/bin/activate  (Intel/AMD Linux)
# source .venv-darwin-arm64/bin/activate  (Apple Silicon)
```

**With Conda** (Alternative - ~2-3 minutes):

```bash
# Install Miniconda first if not present
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# Then create environment
conda env create -f environment.yml
conda activate HAFiscal
```

### Step 7: Test Installation

```bash
./reproduce.sh --docs main
```

### Linux Troubleshooting

**LaTeX packages missing:**

```bash
# Install additional packages as needed
sudo apt-get install texlive-science texlive-bibtex-extra
```

**Permission denied on scripts:**

```bash
chmod +x reproduce.sh
chmod +x reproduce/reproduce_environment_comp_uv.sh
```

---

## Windows Installation (WSL2)

**Important**: HAFiscal is not supported on native Windows. You must use Windows Subsystem for Linux 2 (WSL2).

### Step 1: Install WSL2

Open PowerShell as Administrator and run:

```powershell
wsl --install
wsl --set-default-version 2
```

Restart your computer.

### Step 2: Install Ubuntu 22.04

```powershell
wsl --install -d Ubuntu-22.04
```

Launch Ubuntu from Start menu and complete initial setup (create username/password).

### Step 3: Follow Linux Instructions

Once inside WSL2 Ubuntu terminal, follow the [Linux Installation](#linux-installation-ubuntudebian) steps above.

### Critical: Clone Location

⚠️ **MUST clone inside WSL filesystem**, not in `/mnt/c/`

```bash
# CORRECT - clone in WSL home directory
cd ~
git clone {{REPO_URL}}.git

# WRONG - do not clone in Windows filesystem
# cd /mnt/c/Users/YourName/  # DON'T DO THIS
```

**Why**: The repository uses symlinks which don't work properly in `/mnt/c/`. You'll get git errors and missing figures.

### Step 4: Test Installation

```bash
cd ~/HAFiscal
./reproduce.sh --docs main
```

### Windows/WSL2 Troubleshooting

**"Operation not supported" on git clone:**

- You cloned in `/mnt/c/` instead of WSL filesystem
- Solution: Clone in `~` or `/home/yourusername/`

**Git shows changes to images/ files:**

- Symlinks converted to regular files
- Solution:

```bash
git config core.symlinks true
git checkout HEAD -- images/
```

**LaTeX not found:**

```bash
# Make sure you're in WSL2, not Windows Command Prompt
wsl --list --verbose  # Should show Ubuntu running version 2
```

---

## Alternative: Using Conda (All Platforms)

If you prefer Conda over UV:

### Install Conda

**macOS/Linux**:

```bash
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-$(uname)-x86_64.sh
bash Miniconda3-latest-$(uname)-x86_64.sh
```

**Windows WSL2**:

```bash
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

### Create Environment

```bash
cd HAFiscal
conda env create -f environment.yml
conda activate HAFiscal
```

**Note**: Conda setup takes ~2-3 minutes vs ~5 seconds for UV. UV is recommended for faster workflows.

---

## Verification Steps

After installation, verify everything works:

### 1. Check Python Environment

```bash
# Activate environment (UV automatically activates in new shells)
# Manual activation if needed:
# source .venv-linux-x86_64/bin/activate  # UV (Intel/AMD Linux)
# source .venv-darwin-arm64/bin/activate   # UV (Apple Silicon)
# or: conda activate HAFiscal  # Conda

# Check Python version
python --version  # Should be 3.9+

# Check key packages
python -c "import numpy; print(f'numpy: {numpy.__version__}')"
python -c "from HARK import __version__; print(f'econ-ark: {__version__}')"
```

### 2. Check LaTeX

```bash
# Check pdflatex
pdflatex --version

# Check bibtex
bibtex --version

# Check latexmk
latexmk --version
```

### 3. Run Quick Test

```bash
# Document generation (~5-10 minutes)
./reproduce.sh --docs main

# Verify PDFs created
ls -lh HAFiscal.pdf HAFiscal-Slides.pdf
```

### 4. Run Computational Test (Optional)

```bash
# Minimal computation (~1 hour)
./reproduce.sh --comp min

# This validates the computational environment
```

---

## Environment Comparison: UV vs Conda

| Feature | UV | Conda |
|---------|-----|-------|
| **Install time** | ~5 seconds | ~2-3 minutes |
| **Disk space** | ~200 MB | ~500 MB |
| **Lockfile** | `uv.lock` (fast, deterministic) | `environment.yml` |
| **Python version control** | ✅ Automatic | ⚠️ Manual (via yml) |
| **Cross-platform** | ✅ Yes | ✅ Yes |
| **Recommendation** | ✅ Primary choice | ✅ Fallback option |

**When to use Conda**:

- Already have Conda installed
- Familiar with Conda workflows
- Need conda-specific packages

**When to use UV**:

- New installation (faster)
- Want deterministic builds
- Prefer modern Python tooling

---

## Updating Your Installation

### Update Python Environment

**UV**:

```bash
git pull
uv sync
```

**Conda**:

```bash
git pull
conda env update -f environment.yml
```

### Update LaTeX Packages

**macOS**:

```bash
sudo tlmgr update --self
sudo tlmgr update --all
```

**Linux**:

```bash
sudo apt-get update
sudo apt-get upgrade texlive-full
```

---

## Next Steps

After successful installation:

1. **Generate Documents**: `./reproduce.sh --docs main`
2. **Run Minimal Computation**: `./reproduce.sh --comp min` (~1 hour)
3. **Explore Dashboard**: `cd dashboard && voila app.ipynb`
4. **Read Documentation**: See [README.md](../README.md) for detailed usage

---

## Getting Help

### Documentation

- **Main README**: [README.md](../README.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Quick Reference**: [QUICK-REFERENCE.md](QUICK-REFERENCE.md)

### Support

- **GitHub Issues**: {{REPO_URL}}/issues
- **Email**: <ccarroll@jhu.edu> (Christopher Carroll)

---

**Last Updated**: 2025-11-16  
**Version**: 2.0
