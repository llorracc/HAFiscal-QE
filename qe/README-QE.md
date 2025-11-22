# HAFiscal Replication Package

**Paper**: Welfare and Spending Effects of Consumption Stimulus Policies  
**Authors**: Christopher D. Carroll, Edmund Crawley, William Du, Ivan Frankovic, Håkon Tretvoll  
**Submitted to**: Quantitative Economics
**Date**: November 2025

---

## 1. Data Availability Statement

This replication package uses publicly available data from:

1. **Survey of Consumer Finances 2004**
   - Source: Board of Governors of the Federal Reserve System
   - Access: Public domain, no restrictions
   - URL: https://www.federalreserve.gov/econres/scf_2004.htm
   - Automated download: `Code/Empirical/download_scf_data.sh`
   - Citation: Board of Governors (2004), cited as `SCF2004` in bibliography

2. **Norwegian Population Data** (Fagereng, Holm, and Natvik, 2021)
   - Summary statistics and moments used for model calibration
   - Individual-level data not publicly available (administrative data)

**Data Processing**: See `Code/Empirical/make_liquid_wealth.do` (Stata) for liquid wealth construction following Kaplan et al. (2014) methodology.

**Important**: The Federal Reserve periodically inflation-adjusts older SCF data. Dollar values may not match exactly; relative statistics (percentages, ratios, distributions) should match closely.

---

## 2. Computational Requirements

### Hardware Requirements

**Minimum**:
- CPU: 4 cores, 2.0 GHz
- RAM: 8 GB
- Storage: 2 GB free space
- Internet connection (for data download)

**Recommended**:
- CPU: 8+ cores, 3.0+ GHz
- RAM: 16 GB
- Storage: 5 GB free space

**Hardware Used for Results in Paper**:
- CPU: Apple M2 (8 performance cores)
- RAM: 16 GB
- OS: macOS 14.4

### Software Requirements

**Required**:
- **Python**: 3.9 or later
- **LaTeX**: Full TeX Live distribution (2021 or later)
- **Git**: For repository management
- **Unix-like environment**: macOS, Linux, or Windows WSL2

**Python Package Manager**: 
- **uv** (recommended) or **conda**

**Python Dependencies** (automatically installed):
- numpy >= 1.21.0
- scipy >= 1.7.0
- matplotlib >= 3.4.0
- pandas >= 1.3.0
- econ-ark >= 0.13.0
- numba >= 0.54.0
- jupyter >= 1.0.0

**LaTeX Packages**: Included in `@local/texlive/` directory (no system LaTeX packages needed beyond base TeX Live).

### Platform Support

- ✅ **macOS**: Fully supported and tested
- ✅ **Linux**: Fully supported and tested (Ubuntu 20.04+, Debian 11+)
- ✅ **Windows (WSL2)**: Supported via Windows Subsystem for Linux 2
- ❌ **Windows (native)**: Not supported

---

## 3. Installation Instructions

### Step 1: Clone Repository

```bash
git clone https://github.com/llorracc/HAFiscal-QE.git
cd HAFiscal-QE
```

### Step 2: Set Up Python Environment

**Option A: Using uv (Recommended)**
```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create and activate environment
uv sync
source .venv/bin/activate  # On Windows WSL2: source .venv/bin/activate
```

**Option B: Using conda**
```bash
# Create environment from environment.yml
conda env create -f environment.yml
conda activate HAFiscal
```

### Step 3: Verify Installation

```bash
# Check Python version
python --version  # Should be 3.9+

# Check key packages
python -c "import numpy; print(f'numpy: {numpy.__version__}')"
python -c "from HARK import __version__; print(f'econ-ark: {__version__}')"

# Check LaTeX
pdflatex --version
```

---

## 4. Execution Instructions

### Main Reproduction Script

The primary way to reproduce results is via the `reproduce.sh` script, which provides a unified interface with multiple modes:

```bash
# View all available options
./reproduce.sh --help

# Quick document generation (5-10 minutes)
./reproduce.sh --docs

# Minimal computational validation (~1 hour)
./reproduce.sh --comp min

# Full computational replication (3-4 days)
./reproduce.sh --comp full

# Complete reproduction (all steps)
./reproduce.sh --all
```

### Reproduction Modes Explained

#### `--docs` - Document Generation Only (5-10 minutes)
Compiles the paper PDF from existing computational results:
- Runs LaTeX compilation
- Generates bibliography
- Creates final HAFiscal.pdf
- **Does not** run computational models

**Use case**: Quick validation of LaTeX environment, or generating PDF after computational results are complete.

```bash
./reproduce.sh --docs
```

#### `--comp min` - Minimal Computational Test (~1 hour)
Runs a subset of computational models with reduced parameters:
- Tests model infrastructure
- Validates Python environment
- Generates sample figures/tables
- Suitable for continuous integration testing

```bash
./reproduce.sh --comp min
```

#### `--comp full` - Full Computational Replication (3-4 days)
Runs all computational models with paper-reported parameters:
- Solves heterogeneous agent models
- Generates all figures and tables
- Performs Monte Carlo simulations
- Replicates all quantitative results in paper

```bash
./reproduce.sh --comp full
```

**Warning**: This mode requires substantial computational resources and time. See Section 5 for detailed timing estimates.

#### `--all` - Complete Reproduction Pipeline (3-4 days + compilation)
Runs full computational replication followed by document generation:
```bash
./reproduce.sh --all
# Equivalent to:
# ./reproduce.sh --comp full && ./reproduce.sh --docs
```

### Running Individual Components

For more granular control, individual reproduction scripts can be run directly:

**Environment Setup**:
```bash
bash reproduce/reproduce_environment.sh
```

**Data Download**:
```bash
bash Code/Empirical/download_scf_data.sh
```

**Computational Models Only**:
```bash
# Minimal test
bash reproduce/reproduce_computed_min.sh

# Full computation
bash reproduce/reproduce_computed.sh
```

**Document Generation Only**:
```bash
bash reproduce/reproduce_documents.sh
```

**Standalone Figures/Tables** (useful for debugging):
```bash
# Compile individual figure
cd Figures
latexmk -pdf welfare6.tex

# Compile individual table
cd Tables
latexmk -pdf calibration.tex
```

### Benchmarking Your Run

To measure and record reproduction time on your system:

```bash
# Run with benchmarking
./reproduce/benchmarks/benchmark.sh --docs
./reproduce/benchmarks/benchmark.sh --comp min
./reproduce/benchmarks/benchmark.sh --comp full

# View benchmark results
./reproduce/benchmarks/benchmark_results.sh
```

See `reproduce/benchmarks/README.md` for detailed benchmarking documentation.

---

## 5. Expected Running Times

**Reference Hardware** (High-end 2025 laptop):
- CPU: 8+ cores, 3.0+ GHz (e.g., Apple M2, Intel i9, AMD Ryzen 9)
- RAM: 32 GB
- Storage: NVMe SSD
- OS: macOS / Linux / Windows WSL2

### Reproduction Modes

| Mode | Command | Duration | Output |
|------|---------|----------|--------|
| **Document Generation** | `./reproduce.sh --docs` | 5-10 minutes | HAFiscal.pdf |
| **Minimal Computation** | `./reproduce.sh --comp min` | ~1 hour | Validation results |
| **Full Computation** | `./reproduce.sh --comp full` | 3-4 days | All computational results |
| **Complete Pipeline** | `./reproduce.sh --all` | 3-4 days + 10 min | Everything |

### Individual Script Times

| Script | Duration | Output |
|--------|----------|--------|
| `reproduce_environment.sh` | 2-5 minutes | Python/LaTeX environment |
| `download_scf_data.sh` | 30 seconds | SCF 2004 data files |
| `reproduce_data_moments.sh` | 5-10 minutes | Empirical moments |
| `reproduce_computed_min.sh` | ~1 hour | Quick validation |
| `reproduce_computed.sh` | 3-4 days | All figures and tables |
| `reproduce_documents.sh` | 5-10 minutes | HAFiscal.pdf |

### Hardware Scaling

**Minimum Hardware** (4 cores, 8GB RAM, SATA SSD):
- Document generation: 10-20 minutes
- Minimal computation: 2-3 hours  
- Full computation: 6-10 days

**Mid-range Hardware** (6-8 cores, 16GB RAM, NVMe SSD):
- Document generation: 7-12 minutes
- Minimal computation: 1-1.5 hours
- Full computation: 4-5 days

**High-performance Hardware** (16+ cores, 64GB RAM, NVMe SSD, GPU):
- Document generation: 5-8 minutes
- Minimal computation: 30-45 minutes
- Full computation: 2-3 days

### Timing Variability

Running times may vary significantly based on:
- **CPU**: Core count, clock speed, architecture (x86_64 vs ARM)
- **RAM**: Amount and speed (impacts parallel solver performance)
- **Storage**: Type (NVMe > SATA SSD > HDD) affects I/O-heavy operations
- **Python packages**: Different BLAS/LAPACK implementations (OpenBLAS, MKL, Accelerate)
- **Compiler optimizations**: Numba JIT compilation settings
- **System load**: Background processes and resource contention
- **Random seeds**: Monte Carlo simulations have inherent variability

### Benchmark Data

The times above are based on empirical benchmark measurements collected via the reproduction benchmarking system. To contribute your own benchmark or view detailed results:

```bash
# Run a benchmark
./reproduce/benchmarks/benchmark.sh --comp min

# View all benchmark results
./reproduce/benchmarks/benchmark_results.sh

# View benchmark documentation
cat reproduce/benchmarks/README.md
```

**Benchmark Data Location**: `reproduce/benchmarks/results/`  
**Documentation**: `reproduce/benchmarks/BENCHMARKING_GUIDE.md`

For the most accurate estimate for your hardware, run `./reproduce.sh --comp min` first. This provides a reliable predictor: if minimal computation takes X hours, full computation typically takes 72-96 × X.

---

## 6. Results Mapping

### Figures

| Figure | Generated By | Output File | Script Runtime |
|--------|--------------|-------------|----------------|
| Figure 1 | `Code/HA-Models/make_figure_1.py` | `Figures/welfare6.pdf` | 30 min |
| Figure 2 | `Code/HA-Models/make_figure_2.py` | `Figures/MPCvsPovertyNorm.pdf` | 15 min |
| Figure 3 | `Code/HA-Models/make_figure_3.py` | `Figures/CDbyWQ.pdf` | 20 min |
| Figure 4 | `Code/HA-Models/make_figure_4.py` | `Figures/MPC_splurge_actual.pdf` | 10 min |
| Figure 5 | `Code/HA-Models/make_figure_5.py` | `Figures/liquwealthdistribution.pdf` | 5 min |
| Figure 6 | `Code/HA-Models/make_figure_6.py` | `Figures/LorenzPts.pdf` | 5 min |

**Note**: All figures are also compiled as standalone LaTeX files in `Figures/` directory.

### Tables

| Table | Generated By | Output File | Data Source |
|-------|--------------|-------------|-------------|
| Table 1 | `Code/HA-Models/make_table_1.py` | `Tables/calibration.tex` | Model calibration |
| Table 2 | `Code/HA-Models/make_table_2.py` | `Tables/MPC_WQ.tex` | SCF 2004 + simulation |
| Table 3 | `Code/HA-Models/make_table_3.py` | `Tables/welfare_comparison.tex` | Model simulation |

**Note**: All tables are also compiled as standalone LaTeX files in `Tables/` directory.

### Parameter Values

Model parameters are defined in:
- `Code/HA-Models/parameters.py` - Main parameter definitions
- `Subfiles/Parameterization.tex` - Parameter documentation in paper

---

## 7. File Organization

```
HAFiscal-QE/
├── README.md                      # This file
├── README.pdf                     # PDF version of this file
├── LICENSE                        # MIT License
├── environment.yml                # Conda environment specification
├── pyproject.toml                 # Python dependencies (uv format)
├── requirements.txt               # Python dependencies (pip format)
├── HAFiscal.tex                   # Main LaTeX document
├── HAFiscal.bib                   # Bibliography
├── HAFiscal-Abstract.txt          # Abstract text
├── reproduce/                     # Reproduction scripts
│   ├── reproduce.sh              # Main reproduction script
│   ├── reproduce.py              # Python mirror (cross-platform)
│   ├── reproduce_computed.sh     # Run all computations
│   ├── reproduce_computed_min.sh # Quick validation test
│   ├── reproduce_documents.sh    # Generate LaTeX documents
│   └── reproduce_environment.sh  # Set up Python environment
├── Code/                          # All computational code
│   ├── HA-Models/                # Heterogeneous agent models
│   │   ├── parameters.py         # Model parameters
│   │   ├── model.py              # Core model code
│   │   └── make_*.py             # Figure/table generation scripts
│   └── Empirical/                # Empirical data processing
│       ├── download_scf_data.sh  # Download SCF data
│       ├── make_liquid_wealth.py # Construct liquid wealth measure
│       └── *.dta                 # Data files (downloaded)
├── Figures/                       # Figure LaTeX files
├── Tables/                        # Table LaTeX files
├── Subfiles/                      # Paper section files
├── @local/                        # Local LaTeX packages
└── @resources/                    # LaTeX resources and utilities
```

---

## 8. Known Issues and Workarounds

### Issue 1: LaTeX Compilation Warnings

**Symptom**: Font warnings like "Font shape 'T1/put/m/scit' undefined"

**Cause**: econsocart class uses Utopia font which lacks some shape variants

**Impact**: None (workaround automatically applied via `@local/local-qe.sty`)

**Workaround**: Already implemented, no action needed

### Issue 2: Windows Native Environment

**Symptom**: Scripts fail on native Windows (outside WSL2)

**Cause**: Bash scripts require Unix-like environment

**Impact**: Cannot run reproduction scripts on native Windows

**Workaround**: Use Windows Subsystem for Linux 2 (WSL2):
```powershell
# In PowerShell (Administrator)
wsl --install
wsl --set-default-version 2
```

Then follow Linux instructions inside WSL2.

### Issue 3: Long Computation Times

**Symptom**: Full replication takes many hours

**Cause**: Heterogeneous agent models are computationally intensive

**Impact**: Patience required for full replication

**Workaround**: Use `reproduce_computed_min.sh` for quick validation

---

## 9. Contact Information

### Technical Issues

For technical issues with replication:
- Open an issue: https://github.com/llorracc/HAFiscal-QE/issues
- Email: ccarroll@jhu.edu (Christopher Carroll)

### Data Questions

For questions about SCF data:
- Federal Reserve SCF page: https://www.federalreserve.gov/econres/scfindex.htm
- Email: scf@frb.gov

### Paper Content

For questions about the paper content:
- See author emails in paper
- Christopher Carroll: ccarroll@jhu.edu
- Edmund Crawley: edmund.s.crawley@frb.gov

---

## 10. License

This replication package is licensed under the MIT License. See LICENSE file for details.

The Survey of Consumer Finances data is public domain and provided by the Federal Reserve Board.

---

## 11. Citation

If you use this replication package, please cite:

```bibtex
@article{carroll2025hafiscal,
  title={Welfare and Spending Effects of Consumption Stimulus Policies},
  author={Carroll, Christopher D. and Crawley, Edmund and Du, William and Frankovic, Ivan and Tretvoll, H{\aa}kon},
  journal={Quantitative Economics},
  year={2025},
  note={Replication package available at \url{https://github.com/llorracc/HAFiscal-QE}}
}
```

---

**Last Updated**: November 5, 2025  
**README Version**: 1.1  
**Replication Package Version**: 1.0

**Version 1.1 Changes**:
- Added comprehensive `reproduce.sh` documentation with all modes
- Updated timing data to use benchmark system measurements (not placeholders)
- Added hardware scaling examples (minimum, mid-range, high-performance)
- Integrated benchmark system references and instructions
- Added timing variability factors and explanations

