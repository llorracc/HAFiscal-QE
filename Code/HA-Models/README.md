# Heterogeneous Agent Models for HAFiscal

This directory contains the core computational code for the heterogeneous agent models used in "Welfare and Spending Effects of Consumption Stimulus Policies" by Carroll, Crawley, Du, Frankovic, and Tretvoll (2025).

## Quick Start

### Running the Complete Pipeline

```bash
# Run all computational steps (4-5 days)
python do_all.py

# Or run minimal validation (~1 hour)
python reproduce_min.py
```

### Running Individual Steps

```bash
# Step 1: Estimate splurge factor (~20 minutes)
cd Target_AggMPCX_LiquWealth
python Estimation_BetaNablaSplurge.py

# Step 2: Estimate discount factor distributions (~21 hours)
cd FromPandemicCode
python EstimAggFiscalMAIN.py

# Step 5: Compare fiscal stimulus policies (~65 hours)
cd FromPandemicCode
python AggFiscalMAIN.py
```

## Computational Pipeline

The model estimation and policy analysis follows a 5-step pipeline controlled by `do_all.py`:

### Step 1: Estimate Splurge Factor

- **Script**: `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py`
- **Purpose**: Jointly estimate discount factor distribution (Beta, Nabla) and splurge factor
- **Targets**: Aggregate MPC and liquid wealth distribution from SCF 2004
- **Output**:
  - Figure 1 (liquid wealth distribution fit)
  - Estimated parameters saved for later steps
  - Table 1 (calibration results)
- **Runtime**: ~20 minutes

### Step 2: Estimate Discount Factor Distributions  

- **Script**: `FromPandemicCode/EstimAggFiscalMAIN.py`
- **Purpose**: Estimate separate discount factor distributions for three education groups
- **Method**: Simulated Method of Moments matching consumption drop upon UI exit
- **Output**:
  - Figure 2 (lifecycle profiles) via `CreateLPfig.py`
  - Figure 3 (impulse response functions) via `CreateIMPCfig.py`
  - Estimated parameters for each education group
  - Results written to `Results/AllResults_CRRA_2.0_R_1.01.txt`
- **Runtime**: ~21 hours (7 hours per education group)

### Step 3: Robustness with Splurge=0 (Optional)

- **Script**: `FromPandemicCode/EstimAggFiscalMAIN.py` with Splurge=0
- **Purpose**: Online appendix robustness check with zero splurge
- **Output**: Alternative parametrization results
- **Runtime**: Similar to Step 2 (~21 hours)

### Step 4: HANK-SAM Model Robustness

- **Scripts**:
  - `HA-Fiscal-HANK-SAM.py` - Compute Jacobian matrices
  - `HA-Fiscal-HANK-SAM-to-python.py` - Run experiments
- **Purpose**: Robustness check using Sequence Space Jacobian methods
- **Output**:
  - Figure 5 (HANK-SAM policy comparisons)
  - Jacobian matrices for dashboard: `HA_Fiscal_Jacs.obj`, `HA_Fiscal_Jacs_UI_extend_real.obj`
- **Runtime**: ~1 hour

### Step 5: Compare Fiscal Stimulus Policies

- **Script**: `FromPandemicCode/AggFiscalMAIN.py`
- **Purpose**: Welfare and spending analysis of three policies:
  - UI benefit extension
  - Stimulus checks (lump-sum transfers)
  - Payroll tax cuts
- **Output**:
  - Figure 4 (six subfigures showing policy effects)
  - Figure 6 (welfare comparisons)
  - Tables 6-8 (fiscal multipliers, welfare, and decompositions)
  - Generated in `FromPandemicCode/Tables/CRRA2/` subdirectory
- **Runtime**: ~65 hours

## Directory Structure

```
Code/HA-Models/
├── do_all.py                          # Main pipeline script
├── reproduce_min.py                   # Quick validation script
├── parameters.py                      # Shared parameter definitions
├── Results/                           # Text files with numerical results
│   └── AllResults_CRRA_2.0_R_1.01.txt
├── Target_AggMPCX_LiquWealth/        # Step 1: Estimate splurge
│   ├── Estimation_BetaNablaSplurge.py
│   └── ...
└── FromPandemicCode/                  # Steps 2-5: Main analysis
    ├── EstimAggFiscalMAIN.py         # Step 2: Estimation
    ├── AggFiscalMAIN.py              # Step 5: Policy comparison
    ├── AggFiscalModel.py             # Model class definitions
    ├── EstimParameters.py            # Calibrated parameters
    ├── CreateLPfig.py                # Generate Figure 2
    ├── CreateIMPCfig.py              # Generate Figure 3
    ├── Output_Results.py             # Generate Figure 4, Table 6
    ├── Welfare.py                    # Generate Figure 6, Table 7
    ├── FiscalTools.py                # Utility functions
    ├── Figures/                      # Generated figure files
    │   ├── CRRA2/                    # Baseline parametrization
    │   ├── CRRA2_PVSame/             # Equal present value
    │   └── ...                       # Other parametrizations
    └── Tables/                       # Generated table files
        ├── CRRA2/                    # Baseline parametrization
        └── ...                       # Other parametrizations
```

## Key Python Modules

### Model Definition

- **`AggFiscalModel.py`**: Core model classes
  - `AggFiscalType`: Individual agent type with fiscal parameters
  - `AggregateDemandEconomy`: Market with aggregate demand externality
- **`ConsMarkovModel.py`**: Consumer model with Markov unemployment transitions
- **`EstimAggFiscalModel.py`**: Estimation-specific model variants

### Estimation and Calibration

- **`EstimAggFiscalMAIN.py`**: Main estimation script (Step 2)
- **`EstimParameters.py`**: Calibrated parameter values
- **`EstimSetupEconomy.py`**: Economy setup for estimation

### Policy Analysis

- **`AggFiscalMAIN.py`**: Main policy comparison (Step 5)
  - Also has `AggFiscalMAIN_reduced.py` variant for faster runs
- **`Output_Results.py`**: Generate policy comparison results and figures
- **`Welfare.py`**: Welfare calculations and comparisons

### Utilities

- **`FiscalTools.py`**: Helper functions for fiscal policy analysis
- **`Clean_Folders.py`**: **Intelligent cleanup utility** - reads flags from `AggFiscalMAIN.py` (SST) and cleans accordingly
- **`CreateLPfig.py`**: Generate lifecycle profile figures
- **`CreateIMPCfig.py`**: Generate impulse response figures

### Intelligent Cleanup (SST Pattern)

`Clean_Folders.py` implements **intelligent cleanup** by reading the Single Source of Truth:

- **Single Source of Truth**: `AggFiscalMAIN.py` defines robustness control flags (e.g., `Run_CRRA1_robustness = False`)

- **How it works**: 
  1. `Clean_Folders.py` parses `AggFiscalMAIN.py` to extract flag values
  2. For each flag set to `False`, it deletes large files (>1MB) in corresponding directories
  3. Preserves small files (logs, metadata, config)

- **Why**: This prevents accumulation of orphaned PDFs from development experiments or previously-enabled robustness checks that were later disabled.

- **Usage**:
  ```bash
  cd Code/HA-Models/FromPandemicCode
  python Clean_Folders.py               # Clean with default settings
  python Clean_Folders.py --dry-run     # Preview what would be deleted
  python Clean_Folders.py --size-threshold 5  # Only delete files >5MB
  ```

- **Benefits**: 
  - No duplication of directory lists
  - Always synced with `AggFiscalMAIN.py` flags
  - Can be run manually or integrated into workflow

## Model Features

### Three Education Groups
The model includes separate agent types for:

- **Dropout** (<12 years education)
- **HighSchool** (12 years education)  
- **College** (>12 years education)

Each group has:

- Different income processes
- Different unemployment risks
- Different unemployment benefit replacement rates
- Estimated discount factor distributions

### Key Economic Features

- **Heterogeneous agents**: Idiosyncratic income and unemployment risk
- **Incomplete markets**: Agents cannot fully insure against shocks
- **Liquid wealth**: Excludes "splurge" portion of assets
- **Markov unemployment**: Two states (employed/unemployed) with transitions
- **Aggregate demand**: Output responds to aggregate consumption
- **Fiscal policies**: UI extensions, transfers, tax cuts

### Model Parametrizations

The code supports multiple parametrizations controlled by flags in `AggFiscalMAIN.py`:

| Parametrization | CRRA | Interest Rate | Use Case |
|-----------------|------|---------------|----------|
| **CRRA2** (Baseline) | 2.0 | 1.01 | Main results |
| **CRRA2_PVSame** | 2.0 | 1.01 | Equal present value comparison |
| **Splurge0** | 2.0 | 1.01 | Zero splurge robustness |
| **CRRA1** | 1.0 | 1.01 | Low risk aversion |
| **CRRA3** | 3.0 | 1.01 | High risk aversion |
| **Rfree_1005** | 2.0 | 1.005 | Low interest rate |
| **Rfree_1015** | 2.0 | 1.015 | High interest rate |
| **ADElas** | 2.0 | 1.01 | Alternative AD elasticity |
| **LowerUBnoB** | 2.0 | 1.01 | Lower UB, no benefits cap |

## Dependencies

### Required Python Packages

- **econ-ark** >= 0.16.0 - HARK toolkit for heterogeneous agents
- **numpy** >= 1.21.0 - Numerical computing
- **scipy** >= 1.7.0 - Scientific computing and optimization
- **matplotlib** >= 3.4.0 - Plotting
- **pandas** >= 1.3.0 - Data manipulation
- **numba** >= 0.54.0 - JIT compilation for performance
- **sequence-jacobian** - Sequence space Jacobian methods (Step 4)

### Installation

```bash
# Using UV (recommended)
cd ../..  # Return to repository root
uv sync

# Or using conda
conda env create -f environment.yml
conda activate HAFiscal
```

## Output Files

### Figures
Generated figures are saved in `FromPandemicCode/Figures/` organized by parametrization:

- **Figure 1**: `../../Figures/liquwealthdistribution.pdf`
- **Figure 2**: `Figures/CRRA2/LPbyType.pdf` (lifecycle profiles)
- **Figure 3**: `Figures/CRRA2/IMPC_*.pdf` (impulse responses)
- **Figure 4**: Six subfigures from `Output_Results.py`
- **Figure 5**: HANK-SAM comparisons
- **Figure 6**: `Figures/CRRA2/welfare6.pdf`

### Tables
Generated LaTeX tables are saved in `FromPandemicCode/Tables/` organized by parametrization:

- **Table 1**: Created by `Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py:680`
- **Table 6**: `Tables/CRRA2/Multiplier.tex` (fiscal multipliers)
- **Table 7**: `Tables/CRRA2/welfare6.tex` (welfare comparisons)
- **Table 8**: `Tables/CRRA2/decomposition.tex` (spending decomposition)

### Results Files
Numerical results are written to text files in `Results/`:

- **AllResults_CRRA_2.0_R_1.01.txt**: Main estimation results (created by `EstimAggFiscalMAIN.py:1105,1111`)
- Values from these files are manually transcribed into paper tables

## Running Time Estimates

Based on reference hardware (8-core CPU, 16GB RAM, NVMe SSD):

| Task | Script | Runtime |
|------|--------|---------|
| **Complete Pipeline** | `do_all.py` | 4-5 days |
| **Minimal Validation** | `reproduce_min.py` | ~1 hour |
| Step 1 | `Estimation_BetaNablaSplurge.py` | ~20 min |
| Step 2 | `EstimAggFiscalMAIN.py` | ~21 hours |
| Step 3 | `EstimAggFiscalMAIN.py` (Splurge=0) | ~21 hours |
| Step 4 | `HA-Fiscal-HANK-SAM*.py` | ~1 hour |
| Step 5 | `AggFiscalMAIN.py` | ~65 hours |

Actual runtimes vary significantly based on hardware. See `../../reproduce/benchmarks/` for detailed timing information.

## Implementation Details

### Liquid Wealth Calculation
Liquid wealth excludes the "splurge" portion of assets:

```python
liquid_wealth = (1 - ThisType.Splurge) * ThisType.state_now["aLvl"]
```

### Agent Type Organization
Agent types are organized in arrays:

```python
# For each education group, multiple discount factors
num_agents = num_education_types * DiscFacCount
# Example: 3 education types × 7 discount factors = 21 agent types
```

### Path Handling
Scripts detect their execution context and adjust paths:

```python
if os.path.basename(os.getcwd()) == "FromPandemicCode":
    # Running from within FromPandemicCode/
    results_dir = "../Results/"
else:
    # Running from repository root or HA-Models/
    results_dir = "Code/HA-Models/Results/"
```

### Deterministic Results
Optimization routines use fixed random seeds for reproducibility, but small environmental differences (BLAS library, compiler optimizations) may cause minor numerical variations.

## Troubleshooting

### Import Errors

```bash
# Make sure econ-ark is installed
pip install econ-ark --upgrade

# Or reinstall environment
cd ../..
uv sync
```

### Memory Issues

```bash
# Reduce number of simulated agents in EstimParameters.py
AgentCount = 5000  # Default: 10000

# Or increase system swap space
```

### Long Run Times

```bash
# Use reduced version for faster testing
python AggFiscalMAIN_reduced.py

# Or run minimal validation
python reproduce_min.py
```

### Missing Output Files

```bash
# Make sure you've run prior steps
python do_all.py  # Runs all steps in order

# Or run steps individually
cd Target_AggMPCX_LiquWealth
python Estimation_BetaNablaSplurge.py
cd ../FromPandemicCode
python EstimAggFiscalMAIN.py
python AggFiscalMAIN.py
```

## Additional Documentation

- **`do_all-README.md`**: Detailed provenance of all tables and figures
- **`../../README.md`**: Main replication documentation
- **`../../docs/`**: Technical documentation
- **`../../reproduce/README.md`**: Reproduction scripts documentation

## References

- **Paper**: Carroll, Crawley, Du, Frankovic, Tretvoll (2025). "Welfare and Spending Effects of Consumption Stimulus Policies"
- **HARK Documentation**: <https://hark.readthedocs.io/>
- **Econ-ARK**: <https://econ-ark.org/>

---

**Last Updated**: 2025-11-16  
**Version**: 2.0  
**Contact**: See paper for author contact information
