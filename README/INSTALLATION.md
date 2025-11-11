# HAFiscal Installation Guide

This guide provides detailed, platform-specific instructions for setting up HAFiscal on your system.

## Platform Support

HAFiscal is tested and supported on:
- **macOS** (Intel & Apple Silicon) ✅
- **Linux** (Ubuntu 22.04 LTS recommended) ✅  
- **Windows** (via WSL2 with Ubuntu 22.04) ✅

## Prerequisites

### All Platforms

1. **LaTeX Distribution** - Required for document generation
2. **Python 3.9** - Required for computational reproduction
3. **Git** - For cloning the repository

### Storage Requirements

- **Minimum**: 2 GB (LaTeX + Python environment + code)
- **Recommended**: 5 GB (includes space for computational results)

### Time Requirements

- **Installation**: 10-30 minutes (depending on internet speed)
- **Document reproduction**: 5-10 minutes
- **Minimal computation**: ~1 hour
- **Full computation**: 3-4 days on a high-end 2025 laptop

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

### Step 3: Install UV Package Manager

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
git clone https://github.com/econ-ark/HAFiscal.git
cd HAFiscal
```

### Step 5: Setup Python Environment

```bash
# Setup environment (~5 seconds with UV)
./reproduce/reproduce_environment_comp_uv.sh
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

### Step 4: Install UV Package Manager

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
git clone https://github.com/econ-ark/HAFiscal.git
cd HAFiscal
```

### Step 6: Setup Python Environment

```bash
# Setup environment
./reproduce/reproduce_environment_comp_uv.sh
```

### Step 7: Test Installation

```bash
# Test document generation
./reproduce.sh --docs main
```

### Linux Troubleshooting

**Permission denied on scripts:**
```bash
chmod +x reproduce/*.sh
chmod +x reproduce.sh
```

**LaTeX packages missing:**
```bash
# Install specific missing packages
sudo apt-get install texlive-latex-extra
```

---

## Windows (WSL2) Installation

### Why WSL2?

HAFiscal uses bash scripts and Unix tools that work best on Unix-like systems. WSL2 provides a full Linux environment on Windows.

### Step 1: Install WSL2

Open PowerShell as Administrator and run:

```powershell
wsl --install
```

This installs Ubuntu 22.04 by default (recommended).

**Restart your computer** when prompted.

### Step 2: Launch Ubuntu

1. Search for "Ubuntu" in Start menu
2. First launch will take a few minutes to set up
3. Create a username and password when prompted

### Step 3: Update Ubuntu

```bash
sudo apt-get update
sudo apt-get upgrade
```

### Step 4: Install LaTeX

```bash
sudo apt-get install texlive-full
```

**Note:** This is a large download (~4 GB). Be patient.

### Step 5: Install Build Tools

```bash
sudo apt-get install build-essential curl git
```

### Step 6: Install UV Package Manager

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Add to shell profile:
```bash
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Step 7: Clone Repository

**⚠️ CRITICAL: You MUST clone from within WSL2!**

This repository contains symlinks. If you clone using Git for Windows and then access from WSL2, the symlinks will be broken and nothing will work. Always clone FROM WITHIN the WSL2 terminal:

```bash
# Navigate to home directory
cd ~

# Clone repository (FROM WSL2, not Windows!)
git clone https://github.com/econ-ark/HAFiscal.git
cd HAFiscal
```

**Tips:**
- Work within WSL filesystem (`~/HAFiscal`) for best performance
- To access Windows files from WSL2, they're mounted at `/mnt/c/...`
- If you've already cloned in Windows, delete that clone and re-clone from WSL2

### Step 8: Setup Python Environment

```bash
./reproduce/reproduce_environment_comp_uv.sh
```

### Step 9: Test Installation

```bash
./reproduce.sh --docs main
```

### WSL2 Troubleshooting

**WSL not installed:**
- Make sure Windows 10 version 2004+ or Windows 11
- Enable "Virtual Machine Platform" in Windows Features

**Slow file access:**
- Work within WSL filesystem (`~/HAFiscal`) not Windows filesystem (`/mnt/c/...`)
- WSL2 is much faster on its own filesystem

**Out of memory:**
- Create `.wslconfig` in Windows user directory:
```
[wsl2]
memory=8GB
```

---

## Alternative: Using Conda (All Platforms)

If you prefer Conda over UV:

### Install Conda

**macOS/Linux:**
```bash
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

**Windows (WSL2):**
Same as Linux instructions above.

### Setup Environment

```bash
cd HAFiscal
conda env create -f environment.yml
conda activate hafiscal
```

**Note:** Conda setup takes ~2-3 minutes vs ~5 seconds for UV.

---

## Verifying Your Installation

### Quick Verification

```bash
# Test cross-platform compatibility
./reproduce/test-cross-platform.sh
```

This should show all green checkmarks ✅.

### Document Generation Test

```bash
# Generate documents (~5-10 minutes)
./reproduce.sh --docs main
```

Verify output:
- `HAFiscal.pdf` - Main paper
- `HAFiscal-Slides.pdf` - Presentation slides

### Minimal Computation Test

```bash
# Run minimal computation (~1 hour)
./reproduce.sh --comp min
```

This generates a subset of computational results to verify your Python environment.

---

## Next Steps

### For Paper Readers

- Read `HAFiscal.pdf` - The main paper
- Read `HAFiscal-Slides.pdf` - Presentation slides

### For Reproducers

- Review `README.md` - Project overview
- Run `./reproduce.sh` - Interactive reproduction menu
- See `reproduce/README.md` - Reproduction scripts documentation

### For Developers

- Review `README_IF_YOU_ARE_AN_AI/` - Development documentation
- See `reproduce/TESTING-CROSS-PLATFORM.md` - Testing guide
- Read `TROUBLESHOOTING.md` - Common issues and solutions

---

## Getting Help

### Common Issues

See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) for solutions to common problems.

### Documentation

- **Main README**: [`README.md`](README.md)
- **Cross-Platform Testing**: [`reproduce/TESTING-CROSS-PLATFORM.md`](reproduce/TESTING-CROSS-PLATFORM.md)
- **Reproduction Guide**: [`reproduce/README.md`](reproduce/README.md)

### Reporting Issues

If you encounter problems not covered in the documentation:

1. Check existing issues on GitHub
2. Create a new issue with:
   - Your platform (macOS/Linux/WSL2)
   - Error messages
   - Steps to reproduce

---

## Summary of Installation Commands

### macOS Quick Install
```bash
# Install prerequisites
brew install --cask mactex
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup HAFiscal
git clone https://github.com/econ-ark/HAFiscal.git
cd HAFiscal
./reproduce/reproduce_environment_comp_uv.sh
./reproduce.sh --docs main
```

### Linux Quick Install
```bash
# Install prerequisites
sudo apt-get update
sudo apt-get install texlive-full build-essential curl git
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup HAFiscal
git clone https://github.com/econ-ark/HAFiscal.git
cd HAFiscal
./reproduce/reproduce_environment_comp_uv.sh
./reproduce.sh --docs main
```

### Windows (WSL2) Quick Install
```powershell
# In PowerShell as Administrator
wsl --install
# Restart computer, then in Ubuntu:
```

```bash
sudo apt-get update && sudo apt-get install texlive-full build-essential curl git
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/econ-ark/HAFiscal.git
cd HAFiscal
./reproduce/reproduce_environment_comp_uv.sh
./reproduce.sh --docs main
```

---

**Estimated total installation time:**
- macOS: 15-25 minutes
- Linux: 20-30 minutes  
- Windows (WSL2): 30-45 minutes (includes WSL2 setup)

**Success!** You're now ready to reproduce HAFiscal results. 🎉

