# HAFiscal Reproduction Scripts Directory

This directory contains all scripts needed to reproduce the HAFiscal paper's computational results and LaTeX documents. The scripts are organized by function and designed to work together as part of the main `reproduce.sh` workflow.

## 📋 Quick Reference

Most users should use the main reproduction script in the parent directory:

```bash
../reproduce.sh --docs main     # Build main document
../reproduce.sh --comp min      # Run minimal computations
../reproduce.sh --comp full     # Run full computations
../reproduce.sh --comp max      # Run full computations + robustness results
../reproduce.sh --envt texlive  # Test LaTeX environment
../reproduce.sh --envt comp_uv  # Test computational environment
```

The scripts in this directory are typically called by `reproduce.sh` or `reproduce.py`, but can also be used directly for specific tasks.

---

## 🔧 Environment Setup Scripts

### `reproduce_environment.sh`
**Purpose:** Main environment setup wrapper that delegates to UV-based setup  
**When to use:** Called automatically by `reproduce.sh`, but can be sourced directly  
**Details:** Attempts UV environment setup first (via `reproduce_environment_comp_uv.sh`), falls back to conda if UV unavailable

### `reproduce_environment_comp_uv.sh`
**Purpose:** Sets up Python computational environment using UV package manager  
**When to use:** First-time setup, or when recreating Python environment  
**What it does:**

- Installs UV if not present
- Creates `.venv` virtual environment
- Installs Python dependencies from `pyproject.toml`
- Creates verification marker on success

**Usage:**

```bash
./reproduce/reproduce_environment_comp_uv.sh
```

### `reproduce_environment_texlive.sh`
**Purpose:** Verifies TeX Live installation and required LaTeX packages  
**When to use:** To verify LaTeX environment is properly configured  
**What it does:**

- Checks for `pdflatex`, `bibtex`, `latexmk`
- Verifies required LaTeX packages from `required_latex_packages.txt`
- Creates verification marker on success

**Usage:**

```bash
./reproduce/reproduce_environment_texlive.sh
```

---

## 📄 Document Reproduction Scripts

> **Note:** For HTML generation (optional), see [`reproduce_html_README.md`](reproduce_html_README.md)

### `reproduce_documents.sh`
**Purpose:** Main LaTeX document compilation script  
**When to use:** Called by `reproduce.sh --docs [target]`  
**What it does:**

- Sets up proper `BIBINPUTS` and `BSTINPUTS` environment variables
- Compiles specified LaTeX documents using `latexmk`
- Handles both main document and subfiles
- Supports different document variants (main, slides, appendices)

**Arguments:**

- `main` - Compile HAFiscal.tex (main document)
- `slides` - Compile HAFiscal-Slides.tex
- `subfiles` - Compile individual subfiles
- `all` - Compile everything

**Usage:**

```bash
./reproduce/reproduce_documents.sh main
./reproduce/reproduce_documents.sh slides
```

### `reproduce-standalone-files.sh`
**Purpose:** Compile standalone LaTeX files (figures, tables, subfiles)  
**When to use:** To compile individual components without full document build  
**Options:**

- `--figures` - Compile all .tex files in Figures/
- `--tables` - Compile all .tex files in Tables/
- `--subfiles` - Compile all .tex files in Subfiles/
- `--all` - Compile all standalone files
- `--clean-first` - Clean auxiliary files before compilation
- `--continue` - Continue even if some files fail

**Usage:**

```bash
./reproduce/reproduce-standalone-files.sh --figures
./reproduce/reproduce-standalone-files.sh --all --clean-first
```

---

## 📊 Empirical Data Reproduction Scripts

### `reproduce_data_moments.sh`
**Purpose:** Calculate empirical data moments from SCF 2004  
**When to use:** Called by `reproduce.sh --data` or run directly  
**What it does:**

- Downloads SCF 2004 data if needed (via `download_scf_data.sh`)
- Runs Python analysis (`Code/Empirical/make_liquid_wealth.py`)
- Calculates population, income, wealth distribution statistics
- Generates Lorenz curve data used in Figure 2

**Usage:**

```bash
./reproduce/reproduce_data_moments.sh
```

---

## 🧮 Computational Reproduction Scripts

### `reproduce_computed.sh`
**Purpose:** Run full computational pipeline to generate all results  
**When to use:** Called by `reproduce.sh --comp full` or `--comp max`  
**What it does:**

- Activates Python environment
- Runs `Code/HA-Models/do_all.py` to execute computational steps
- Respects `HAFISCAL_RUN_STEP_3` environment variable for robustness results
- Generates figures and tables used in the paper

**Usage:**

```bash
./reproduce/reproduce_computed.sh              # Standard full run
HAFISCAL_RUN_STEP_3=true ./reproduce/reproduce_computed.sh  # Include robustness
```

### `reproduce_computed_min.sh`
**Purpose:** Run minimal computational reproduction using pre-generated results  
**When to use:** Called by `reproduce.sh --comp min` for quick testing  
**What it does:**

- Checks for required `.obj` files from previous full run
- Temporarily renames existing table files
- Runs minimal computations (figures from existing .obj files)
- Restores original table files
- Much faster than full computation (~5 min vs ~2-3 hours)

**Prerequisites:** Must have run `--comp full` at least once to generate `.obj` files

**Usage:**

```bash
./reproduce/reproduce_computed_min.sh
```

---

## 🛠️ Utility Scripts

### `stash-tables-during-comp-min-run.py`
**Purpose:** Manage table files during minimal computational runs  
**When to use:** Called automatically by `reproduce_computed_min.sh`  
**What it does:**

- Temporarily renames `.tex` files in `Tables/` directory
- Prevents overwriting of full computation results
- Restores files after minimal run completes

**Usage:**

```bash
python stash-tables-during-comp-min-run.py stash    # Rename files
python stash-tables-during-comp-min-run.py restore  # Restore original names
```

---

## 📊 Benchmarking System

The `benchmarks/` subdirectory contains scripts for performance measurement and system information capture.

### `benchmarks/benchmark.sh`
**Purpose:** Wrapper script that times reproduction runs and captures system info  
**Usage:**

```bash
./reproduce/benchmarks/benchmark.sh ../reproduce.sh --docs main
```

### `benchmarks/capture_system_info.py`
**Purpose:** Capture detailed system information for benchmark reports  
**Output:** JSON files in `benchmarks/results/`

See [`benchmarks/README.md`](benchmarks/README.md) for detailed benchmarking documentation.

---

## 📁 Support Files

### `required_latex_packages.txt`
**Purpose:** List of required LaTeX packages for environment verification  
**Format:** One package name per line  
**Used by:** `reproduce_environment_texlive.sh`

---

## 🔍 Verification Markers

Successful environment verifications create marker files:

- `reproduce_environment_texlive_YYYYMMDD-HHMM.verified` - LaTeX environment verified
- `reproduce_environment_comp_uv_YYYYMMDD-HHMM.verified` - Python environment verified

These markers indicate when the environment was last successfully verified and are automatically ignored by git.

---

## 🏛️ Old Scripts

The `old/` subdirectory contains deprecated scripts kept for reference:

- Legacy testing scripts
- Private environment setup scripts
- Old cross-platform test implementations

These are not used in current workflows.

---

## 🚀 Typical Workflows

### First-Time Setup

```bash
# 1. Set up computational environment
./reproduce/reproduce_environment_comp_uv.sh

# 2. Verify environments
../reproduce.sh --envt texlive
../reproduce.sh --envt comp_uv

# 3. Run full reproduction
../reproduce.sh --comp full
../reproduce.sh --docs main
```

### Quick Document Build

```bash
# Just rebuild the LaTeX document (no computations)
../reproduce.sh --docs main
```

### Empirical Data Moments

```bash
# Calculate SCF 2004 data moments (~1 minute + download time)
../reproduce.sh --data
```

### Testing After Code Changes

```bash
# Quick computational test with existing .obj files
../reproduce.sh --comp min
../reproduce.sh --docs main
```

### Full Reproduction for Publication

```bash
# Complete reproduction from scratch
../reproduce.sh --data         # Empirical moments (~1 min)
../reproduce.sh --comp full    # ~2-3 hours
../reproduce.sh --comp max     # +robustness results (~4-6 hours)
../reproduce.sh --docs main
```

---

## 🔗 Related Documentation

- **Main README:** [`../README.md`](../README.md) - Project overview and quick start
- **QE Replication:** [`../README-QE.md`](../README-QE.md) - Instructions for replicators
- **Troubleshooting:** [`../README/TROUBLESHOOTING.md`](../README/TROUBLESHOOTING.md) - Common issues
- **Quick Reference:** [`../README/QUICK-REFERENCE.md`](../README/QUICK-REFERENCE.md) - Command reference
- **Installation:** [`../README/INSTALLATION.md`](../README/INSTALLATION.md) - Platform-specific setup
- **Contributing:** [`../README/CONTRIBUTING.md`](../README/CONTRIBUTING.md) - Contribution guidelines
- **Benchmarking:** [`benchmarks/README.md`](benchmarks/README.md) - Performance testing
- **Container Architecture:** [`../README_IF_YOU_ARE_AN_AI/CONTAINER_ARCHITECTURE.md`](../README_IF_YOU_ARE_AN_AI/CONTAINER_ARCHITECTURE.md) - System design

---

## 💡 Tips

1. **Always use `reproduce.sh`** in the parent directory rather than calling these scripts directly, unless you know what you're doing
2. **Check verification markers** - If environment setup scripts have already created recent `.verified` files, you may not need to run them again
3. **Use `--comp min` for testing** - Much faster than full computation when you only need to verify the build process
4. **Check benchmarks/** for performance data from previous runs
5. **Read script headers** - Each script has detailed comments explaining its purpose and usage

---

**Last Updated:** 2025-10-30  
**Maintainer:** See main repository README
