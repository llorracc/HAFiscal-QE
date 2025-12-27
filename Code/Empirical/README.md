# Empirical Data Processing for HAFiscal

**Last Updated**: 2025-11-16  
**Version**: 2.0

This directory contains scripts for processing Survey of Consumer Finances (SCF) 2004 data to generate empirical moments used in model calibration.

---

## Quick Start

### Download Data

```bash
./download_scf_data.sh
```

### Run Analysis

```bash
# Python version (recommended)
python3 make_liquid_wealth.py
```

---

## Overview

This directory processes SCF 2004 data to construct liquid wealth measures following Kaplan et al. (2014) methodology. The output provides calibration targets for the heterogeneous agent models in `../HA-Models/`.

### Key Outputs

The analysis produces empirical moments used throughout the paper:

- Liquid wealth distribution by education group (Table 2, Panel B; Table 4, Panel B; Table 5)
- Permanent income statistics by education group (Table 2, Panel B)
- Lorenz curve percentiles for wealth inequality (Figure 2)
- Population shares by education group (Table 2, Panel B)

---

## Files in this Directory

### Analysis Scripts

- **`make_liquid_wealth.py`**: **[PRIMARY]** Python script that produces all empirical numbers used in the paper from SCF 2004. Outputs results to console and creates intermediate data files.

- **`compare_scf_datasets.py`**: Utility script to compare different vintages of SCF data and detect inflation adjustments. Used for data quality assurance.

- **`adjust_scf_inflation.py`**: Utility to adjust SCF data for inflation when comparing across vintages or when Federal Reserve updates older data.

### Data Download

- **`download_scf_data.sh`**: Shell script to automatically download the required SCF 2004 data files from the Federal Reserve website. Downloads both summary extract and full public data.

### Data Files

**Note**: These files are included in the repository for convenience but can also be downloaded using `download_scf_data.sh`.

- **`rscfp2004.dta`**: Summary extract data for SCF 2004 in Stata format (original vintage).
- **`rscfp2004_USD2022.dta`**: Summary extract data for SCF 2004 inflation-adjusted to 2022 dollars.
- **`ccbal_answer.dta`**: Small file created from the full public data set (p04i6.dta) containing credit card balance information in Stata format.
- **`rscfp2004_dta.about`**: Metadata file describing the data vintage and source.

**CSV versions** (when available):

- `rscfp2004.csv`: CSV version of summary extract
- `ccbal_answer.csv`: CSV version of credit card balance data

---

## Data Sources

### Federal Reserve Board SCF 2004

**Official Source**: [Federal Reserve Board - 2004 Survey of Consumer Finances](https://www.federalreserve.gov/econres/scf_2004.htm)

**Required Files**:

- **Main survey data**: Stata version - **scf2004s.zip** → **p04i6.dta**
- **Summary Extract Data**: Stata format - **scfp2004s.zip** → **rscfp2004.dta**

Place these `.dta` files in this directory before running analysis scripts.

### Data Vintage Warning

⚠️ **Important**: When releasing new waves of the SCF, the Federal Reserve Board inflation-adjusts older versions.

- **Original data** (used in paper): Dollar variables in 2004 nominal dollars
- **Current download** (as of 2025): Dollar variables inflation-adjusted to 2022 dollars

With an inflation-adjusted version of `rscfp2004.dta`, numbers marked **USD** below will not exactly replicate the values used in the paper. However, **relative statistics** (percentages, ratios, distributions) should match closely.

**Solution**: Use the `rscfp2004.dta` file included in this repository, or use `adjust_scf_inflation.py` to convert between vintages.

---

## Empirical Results

The analysis script (`make_liquid_wealth.py`) produces the following empirical moments:

### Population Distribution

- **Percent of population in each education group**
  - Used in: Table 2, Panel B
  - Groups: Dropout (<12 yrs), HighSchool (12 yrs), College (>12 yrs)

### Income Statistics

- **Average quarterly permanent income (PI) of "newborn" agents** ⚠️ **USD**
  - Used in: Table 2, Panel B
  - Calculated as normal annual income / 4
  - Subject to inflation adjustment in newer data vintages

- **Standard deviation of log(quarterly PI) of "newborn" agents**
  - Used in: Table 2, Panel B
  - Measures income heterogeneity within education groups

### Wealth Distribution

- **Median liquid wealth / quarterly PI in each education group**
  - Used in: Table 4, Panel B
  - Ratio of liquid wealth to permanent income

- **Percent of liquid wealth held by each education group**
  - Used in: Table 5, Panel A
  - Shows wealth concentration across education

- **Percent of liquid wealth held by four wealth quartiles**
  - Used in: Table 5, Panel B
  - Shows wealth concentration within population

- **Lorenz curve percentiles (20th, 40th, 60th, 80th)**
  - Used in: Figure 2 (lifecycle profiles and wealth distribution)
  - Calculated for entire population and each education group separately
  - **Note**: Individual percentile values not reported in tables, but visible in figures

---

## Liquid Wealth Definition

Following **Kaplan, Violante, and Weidner (2014)**, liquid wealth includes:

### Included Assets

- Cash and cash equivalents
- Checking accounts
- Savings accounts  
- Money market accounts
- Call accounts
- Stocks (directly held)
- Bonds (directly held)
- Mutual funds
- Other liquid financial assets

### Excluded Assets

- Housing equity (illiquid)
- Business equity (illiquid)
- Retirement accounts (illiquid, tax-penalized)
- Vehicles (illiquid)
- Other durables

### Liquid Debt

- Credit card debt (subtracted from liquid wealth)
- Other consumer debt (subtracted if liquid/revolving)

### In SCF Variables
The construction uses multiple SCF variables:

- `LIQ` - Liquid assets (checking, savings, money market)
- `CDS` - Certificates of deposit
- `STOCKS` - Directly held stocks
- `BONDS` - Directly held bonds
- `NMMF` - Non-money market mutual funds
- `CCBAL` - Credit card balance (debt)
- Income variables for constructing permanent income

See `make_liquid_wealth.py` for exact variable definitions and transformations.

---

## Running the Analysis

### Python Version

**Requirements**:

- Python 3.9+
- pandas >= 1.3.0
- numpy >= 1.21.0
- scipy >= 1.7.0 (for statistical functions)

**Run**:

```bash
cd Code/Empirical
python3 make_liquid_wealth.py
```

**Output**: Results printed to console with labeled statistics matching paper tables.

---

## Data Comparison Tools

### Compare SCF Vintages

```bash
python3 compare_scf_datasets.py
```

This script:

- Loads multiple vintages of `rscfp2004.dta`
- Compares key variables across vintages
- Detects inflation adjustments
- Reports differences in summary statistics

Useful when Federal Reserve releases updated data vintages.

### Adjust for Inflation

```bash
python3 adjust_scf_inflation.py --from-year 2004 --to-year 2022
```

Adjusts dollar variables in SCF data from one year's dollars to another, using CPI.

---

## Integration with Computational Models

The empirical moments generated here are used in `../HA-Models/` as calibration targets:

1. **Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py**:
   - Uses liquid wealth distribution to estimate splurge factor
   - Matches aggregate MPC and wealth percentiles

2. **FromPandemicCode/EstimParameters.py**:
   - Hard-codes many empirical moments from this analysis
   - Population shares by education
   - Income statistics
   - Wealth distribution targets

3. **FromPandemicCode/EstimAggFiscalMAIN.py**:
   - Uses education-specific moments for estimation
   - Consumption drop upon UI exit (from Krueger & Mueller)
   - Income and wealth statistics from SCF

To update calibration after reprocessing SCF data:

1. Run `make_liquid_wealth.py`
2. Update hard-coded values in `EstimParameters.py`
3. Re-run estimation in `HA-Models/`

---

## Troubleshooting

### Data File Not Found

```bash
# Download the required data
./download_scf_data.sh

# Or manually download from:
# https://www.federalreserve.gov/econres/scf_2004.htm
```

### Python Module Import Errors

```bash
# Make sure you're in the project environment
cd ../..
uv sync  # or: conda activate HAFiscal
cd Code/Empirical
python3 make_liquid_wealth.py
```

### Numbers Don't Match Paper

- **Check data vintage**: Newer downloads are inflation-adjusted
- **Use included `rscfp2004.dta`**: Original vintage matching paper
- **Relative statistics should still match**: Percentages, ratios, distributions

---

## References

### Data Source
Board of Governors of the Federal Reserve System (2004). Survey of Consumer Finances, 2004. Available at <https://www.federalreserve.gov/econres/scfindex.htm>

### Liquid Wealth Definition
Kaplan, G., Violante, G. L., & Weidner, J. (2014). The wealthy hand-to-mouth. *Brookings Papers on Economic Activity*, 2014(1), 77-138.

### Related Documentation

- **`../../README.md`**: Main replication documentation with data availability statement
- **`../../docs/SCF_DATA_VINTAGE.md`**: Detailed SCF vintage documentation
- **`../../docs/SCF_COMPARISON_WORKFLOW.md`**: Workflow for comparing SCF versions
- **`../HA-Models/README.md`**: Documentation of computational models using this data

---

**Last Updated**: 2025-11-16  
**Version**: 2.0  
**Contact**: See paper for author contact information
