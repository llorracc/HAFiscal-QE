# Code Directory

This directory contains all computational code for reproducing the results in "Welfare and Spending Effects of Consumption Stimulus Policies."

## ⚠️ Computational Time Warning

**Full replication takes 4-5 DAYS on a high-end 2025 laptop**. For quick validation (~1 hour), use the minimal reproduction: `../reproduce.sh --comp min`

## Directory Structure

### `HA-Models/` - Heterogeneous Agent Models
**Primary Entry Point**: `do_all.py`

This is the main computational workflow controller. It orchestrates 5 sequential steps:

#### Step 1: Splurge Factor Estimation (~20 minutes)

- **File**: `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py`
- **Purpose**: Estimates the "splurge" factor (κ) using Norwegian lottery data
- **Paper Section**: 3.1
- **Outputs**:
  - Figure 1 → `Target_AggMPCX_LiquWealth/Figures/MPC_WealthQuartiles_Figure.pdf`
  - Table 1 → `Target_AggMPCX_LiquWealth/images/MPC_WealthQuartiles_Table.tex`
  - Estimation results → `Target_AggMPCX_LiquWealth/*.txt`

#### Step 2: Discount Factor Distribution Estimation (~21 hours) ⚠️

- **Files**:
  - `FromPandemicCode/EstimAggFiscalMAIN.py` (main estimation)
  - `FromPandemicCode/CreateLPfig.py` (creates Figure 2)
  - `FromPandemicCode/CreateIMPCfig.py` (creates Figure 3a)
- **Purpose**: Estimates distribution of discount factors (β) for three education groups
- **Paper Section**: 3.3.3
- **Outputs**:
  - Figure 2 → `FromPandemicCode/Figures/`
  - Model parameters → `FromPandemicCode/Results/`
- **Note**: This is the most time-intensive step (~7 hours per education group × 3 groups)

#### Step 3: Robustness Check (~21 hours, OPTIONAL)

- **File**: `FromPandemicCode/EstimAggFiscalMAIN.py` (with Splurge=0 parameter)
- **Purpose**: Robustness analysis with no splurge factor
- **Paper Section**: Online Appendix
- **Parameters**: R=1.01, CRRA=2.0, ReplRate_w=0.7, ReplRate_wo=0.5, Splurge=0
- **Default**: **DISABLED** in `do_all.py` to save time
- **Outputs**: Table 8 → `FromPandemicCode/Tables/Splurge0/welfare6_SplurgeComp.tex`

#### Step 4: HANK Model (~1 hour)

- **Files**:
  - `FromPandemicCode/HA-Fiscal-HANK-SAM.py` (computes household Jacobians)
  - `FromPandemicCode/HA-Fiscal-HANK-SAM-to-python.py` (runs HANK experiments)
- **Purpose**: Robustness check with general equilibrium effects
- **Paper Section**: 5
- **Outputs**:
  - Figure 5 → `FromPandemicCode/Figures/`
  - HANK results → `FromPandemicCode/Results/`

#### Step 5: Policy Comparison (~65 hours) ⚠️

- **File**: `FromPandemicCode/AggFiscalMAIN.py`
- **Purpose**: Compares three fiscal policies (UI, checks, tax cuts)
- **Paper Section**: 4
- **Outputs**:
  - Figure 4 → `FromPandemicCode/Figures/`
  - Figure 6 → `FromPandemicCode/Figures/` (uses Step 4 results)
  - Table 6 (Multipliers) → `FromPandemicCode/Tables/CRRA2/Multiplier.tex`
  - Table 7 (Welfare) → `FromPandemicCode/Tables/CRRA2/welfare6.tex`
- **Note**: This is the longest-running step

### `Empirical/` - Empirical Data Analysis
Contains Stata scripts for processing Survey of Consumer Finances (SCF) 2004 data.

**Key File**: `make_liquid_wealth.do`

- Processes SCF 2004 data
- Calculates liquid wealth statistics by wealth quartile
- Generates empirical moments used in model calibration
- **Requires**: Stata (tested with version MP/18.0)
- **Outputs**: Statistics used in Table 2 (Panel B, lines 1-3), Table 4 (Panel B, line 1), Table 5 (Panels A & B, line 1)

**Data Files**:

- `rscfp2004.dta` - SCF 2004 summary extract (Stata format)
- `rscfp2004.csv` - SCF 2004 summary extract (CSV format)
- `ccbal_answer.dta` - Processed credit card balance data (Stata format)
- `ccbal_answer.csv` - Processed credit card balance data (CSV format)

**Data Source**: Federal Reserve Board - [2004 Survey of Consumer Finances](https://www.federalreserve.gov/econres/scf_2004.htm)

See main `../README.md` section "Data Availability and Provenance Statements" for detailed data documentation.

## Reproduction Workflows

### Quick Test (~1 hour)
Test that environment is working without full computation:

**Option 1: Minimal reproduction script**

```bash
# From project root
./reproduce.sh --comp min
```

**Option 2: Enable only fast steps**

```bash
cd Code/HA-Models
# Edit do_all.py: set run_step_1=True, run_step_4=True, others=False
python do_all.py
```

### Full Reproduction (4-5 days on a high-end 2025 laptop) ⚠️
**Complete replication of all paper results**:

```bash
# From project root - recommended
./reproduce.sh --comp full
```

**Or directly**:

```bash
cd Code/HA-Models
# Edit do_all.py: ensure desired steps are enabled
python do_all.py
```

**Recommended configuration for full replication**:

```python
# In do_all.py
run_step_1 = True   # Required - provides splurge estimate
run_step_2 = True   # Required - baseline model
run_step_3 = False  # Optional - robustness (adds 21 hours)
run_step_4 = True   # Required - HANK model
run_step_5 = True   # Required - policy comparison
```

### Step-by-Step Execution
**For development, debugging, or selective replication**:

1. Navigate to computational directory:

   ```bash
   cd Code/HA-Models
   ```

2. Edit `do_all.py` to enable/disable steps:

   ```python
   run_step_1 = True   # Modify these flags
   run_step_2 = False  # to control execution
   # ... etc
   ```

3. Run the configured workflow:

   ```bash
   python do_all.py
   ```

4. Check outputs in respective directories (see Output Locations below)

**Example: Reproduce only Figure 1**:

```bash
cd Code/HA-Models
# Edit do_all.py: run_step_1=True, all others=False
python do_all.py
```

**Example: Reproduce policy comparison (requires steps 1-2 first)**:

```bash
cd Code/HA-Models  
# Edit do_all.py: run_step_1=True, run_step_2=True, run_step_5=True
python do_all.py
```

## Output Locations

All outputs are generated in subdirectories of `Code/HA-Models/`:

### Figures

- **Figure 1**: `Target_AggMPCX_LiquWealth/Figures/MPC_WealthQuartiles_Figure.pdf`
- **Figure 2**: `FromPandemicCode/Figures/LorenzPtsAll.pdf`
- **Figure 3**:
  - Panel (a): `FromPandemicCode/Figures/iMPC_CRRA2.pdf`
  - Panel (b): `FromPandemicCode/Figures/UIexitcon.pdf`
- **Figure 4**: `FromPandemicCode/Figures/` (6 panels)
  - `MPCall.pdf`, `CAll.pdf`, `YAll.pdf` (with matching `_WGGE` versions)
- **Figure 5**: `FromPandemicCode/Figures/` (6 panels)
  - HANK-SAM comparison figures
- **Figure 6**: `FromPandemicCode/Figures/MPCall_Combined.pdf`

### Tables

- **Table 1**: `Target_AggMPCX_LiquWealth/images/MPC_WealthQuartiles_Table.tex`
- **Table 2-3**: Not generated by code (parameter summaries)
- **Table 4-5**: Partial generation, see `FromPandemicCode/Results/AllResults_CRRA_2.0_R_1.01.txt`
- **Table 6**: `FromPandemicCode/Tables/CRRA2/Multiplier.tex`
- **Table 7**: `FromPandemicCode/Tables/CRRA2/welfare6.tex`
- **Table 8**: `FromPandemicCode/Tables/Splurge0/welfare6_SplurgeComp.tex`

### Results Files

- **All numerical results**: `FromPandemicCode/Results/AllResults_CRRA_2.0_R_1.01.txt`
  - Contains values used in Tables 4-5
  - Written by `EstimAggFiscalMAIN.py` (lines 1105, 1111)
- **Estimation results**: `Target_AggMPCX_LiquWealth/*.txt`

## Integration with Paper

The LaTeX compilation system automatically integrates outputs from this code directory:

### Figures

- Python scripts generate PDFs in `Code/HA-Models/FromPandemicCode/Figures/`
- These are **symlinked** to `../Figures/` directory
- LaTeX document references them via `\FigsDir` macro
- **No manual copying needed**

### Tables

- Python scripts generate `.tex` files with table content
- LaTeX document includes them directly via `\input{}`
- Tables are automatically updated when code runs
- **No manual copying needed**

### Build Integration

```bash
# This workflow keeps everything synchronized:
./reproduce.sh --comp full   # Generate computational results
./reproduce.sh --docs       # Compile paper (uses generated results)
```

The build system ensures figures and tables are always up-to-date.

## Computational Requirements

### Hardware

- **RAM**: 8GB minimum, **32GB recommended**
- **CPU**: Multi-core processor beneficial (estimation can parallelize)
- **Storage**: ~5GB for all intermediate results and outputs
- **Time**: 4-5 days on a high-end 2025 laptop for complete replication

### Benchmarking Reference
On Windows 11 laptop with 32GB RAM and AMD Ryzen 9 5900HS (3.30 GHz):

- Step 1: **20 minutes**
- Step 2: **21 hours** (~7 hours × 3 education groups)
- Step 3: **~21 hours** (similar to Step 2, optional)
- Step 4: **1 hour**
- Step 5: **65 hours**
- **Total**: ~107 hours (4.5 days) with Step 3, ~86 hours (3.6 days) without

Your timing may vary based on hardware.

### Software Dependencies

- **Python**: 3.11.7 (other versions may work)
- **Core packages**:
  - econ-ark==0.14.1 (from conda-forge)
  - numpy==1.26.4
  - matplotlib==3.8.0
  - scipy==1.11.4
  - pandas==2.1.4
  - numba==0.59.0
  - sequence-jacobian (from pip)
- **Optional**: Stata (for empirical analysis only)

**Complete dependency list**: See `../binder/environment.yml`

### Environment Setup

```bash
# Option 1: Using conda (recommended)
uv sync --all-groups  # or: conda env create -f ../environment.yml
conda activate hafiscal

# Option 2: Using pip
pip install econ-ark==0.14.1 numpy pandas matplotlib scipy numba
pip install sequence-jacobian
```

## Troubleshooting

### Installation Issues

**Error: `No module named 'HARK'`**

```bash
# Solution: Install econ-ark package
pip install econ-ark==0.14.1
# or
conda install -c conda-forge econ-ark=0.14.1
```

**Error: `No module named 'sequence_jacobian'`**

```bash
# Solution: Install via pip (not available on conda)
pip install sequence-jacobian
```

**Error: `ModuleNotFoundError: No module named 'numba'`**

```bash
# Solution:
pip install numba==0.59.0
# or
conda install -c conda-forge numba=0.59.0
```

### Execution Issues

**Computation taking too long / want to test first**

```bash
# Solution 1: Use minimal reproduction
./reproduce.sh --comp min  # From project root

# Solution 2: Enable only fast steps
cd Code/HA-Models
# Edit do_all.py: run_step_1=True, run_step_4=True, others=False
python do_all.py
```

**Results differ slightly from paper**

- **Expected**: Small numerical differences possible
- **Cause**: Environment variations (OS, package versions, CPU)
- **Note**: Optimization routines should be deterministic but may vary slightly
- **Acceptable**: Differences in 3rd-4th decimal places
- **Investigate**: Large differences (>1% in key results)

**Script fails partway through**

```bash
# Solution: Steps are mostly independent after Step 1-2
# You can restart from a later step by editing do_all.py

# Example: Step 2 completed, want to skip to Step 5
# In do_all.py:
run_step_1 = False  # Already done
run_step_2 = False  # Already done
run_step_3 = False  # Skip optional
run_step_4 = False  # Skip if not needed
run_step_5 = True   # Run this
```

**Permission errors writing files**

```bash
# Check write permissions in output directories
ls -ld FromPandemicCode/Figures/
ls -ld FromPandemicCode/Tables/
# Should show write permissions (drwxr-xr-x or similar)
```

### Output Issues

**Figures not appearing in paper**

```bash
# Check if figures were generated:
ls -lh FromPandemicCode/Figures/*.pdf
ls -lh Target_AggMPCX_LiquWealth/Figures/*.pdf

# Check if symlinks exist:
ls -lh ../Figures/*.pdf

# Regenerate paper:
cd ..
./reproduce.sh --docs
```

**Tables not updating in paper**

```bash
# Tables are .tex files directly included
# Check if generated:
ls -lh FromPandemicCode/Tables/CRRA2/*.tex

# Regenerate paper:
cd ..
./reproduce.sh --docs
```

## Development Notes

### Modifying the Code

**Adding a new step**:

1. Create new Python script in appropriate subdirectory
2. Add step in `do_all.py`:

   ```python
   run_step_6 = True
   if run_step_6:
       print('Step 6: Your new analysis\n')
       os.chdir('YourSubdir')
       os.system("python " + "your_script.py")
       os.chdir('../')
       print('Concluded Step 6.\n\n')
   ```

3. Update this README with step description
4. Update paper if adding new results

**Modifying parameters**:

- Main parameters in `FromPandemicCode/EstimParameters.py`
- Model parameters in `FromPandemicCode/Parameters.py`
- Splurge factor (κ) in `FromPandemicCode/Parameters.py` (ADelasticity)

### Testing Changes

```bash
# Quick test with Step 1 only
cd Code/HA-Models
# Edit do_all.py: run_step_1=True, others=False
python do_all.py

# Verify outputs
ls -lh Target_AggMPCX_LiquWealth/Figures/
ls -lh Target_AggMPCX_LiquWealth/*.txt
```

### Code Organization

**Key files**:

- `do_all.py` - Main orchestrator
- `reproduce_min.py` - Minimal reproduction script
- `EstimParameters.py` - Estimated parameters
- `Parameters.py` - Model parameters
- `Output_Results.py` - Results formatting and table generation
- `Welfare.py` - Welfare calculations

**Directory structure**:

```
HA-Models/
├── do_all.py                      # Main entry point
├── reproduce_min.py               # Minimal reproduction
├── Target_AggMPCX_LiquWealth/    # Step 1: Splurge estimation
│   ├── Estimation_BetaNablaSplurge.py
│   ├── Figures/                  # Figure 1 output
│   └── images/                   # Table 1 output
└── FromPandemicCode/             # Steps 2-5: Main analysis
    ├── EstimAggFiscalMAIN.py     # Step 2: Estimation
    ├── CreateLPfig.py            # Figure 2
    ├── CreateIMPCfig.py          # Figure 3a
    ├── EvalConsDropUponUILeave.py # Figure 3b
    ├── AggFiscalMAIN.py          # Step 5: Policy comparison
    ├── HA-Fiscal-HANK-SAM.py     # Step 4: HANK household
    ├── HA-Fiscal-HANK-SAM-to-python.py  # Step 4: HANK experiments
    ├── Figures/                  # Figures 2-6 output
    ├── Tables/                   # Tables 6-8 output
    └── Results/                  # Numerical results
```

## Additional Resources

- **Main README**: `../README.md` - Setup and overview
- **AI Documentation**: `../README_IF_YOU_ARE_AN_AI/` - AI-optimized guides
  - Especially: `030_COMPUTATIONAL_WORKFLOWS.md` - Detailed workflow guide
- **Reproduction Scripts**: `../reproduce/` - Script documentation
- **Paper**: `../HAFiscal.pdf` - Complete paper with results
- **Slides**: `../HAFiscal-Slides.pdf` - Presentation version

## Citation

If you use this code, please cite:

Carroll, Christopher D., Edmund Crawley, Weifeng Dai, Ivan Frankovic, and Hakon Tretvoll (2025). "Welfare and Spending Effects of Consumption Stimulus Policies."

## Support

For issues or questions:

1. Check troubleshooting sections above
2. Review main README troubleshooting: `../README.md`
3. Check AI troubleshooting guide: `../README_IF_YOU_ARE_AN_AI/080_TROUBLESHOOTING_FOR_AI_SYSTEMS.md`
4. Verify environment: `../reproduce/reproduce_environment_comp_uv.sh` (or activate: `source ../.venv/bin/activate`)
5. Open an issue on the project repository (if applicable)

---

**Quick Reference Command Summary**:

```bash
# From project root:
./reproduce.sh --comp min       # Test (~1 hour)
./reproduce.sh --comp full      # Full replication (4-5 days on a high-end 2025 laptop)
./reproduce.sh --comp max       # Maximum replication with robustness (~5 days on a high-end 2025 laptop)
./reproduce.sh --docs           # Compile paper

# From Code/HA-Models/:
python do_all.py               # Run configured steps
python reproduce_min.py        # Minimal test
```
