# Empirical Data Processing for HAFiscal - QE Submission Workflow

**Last Updated**: 2025-12-05  
**Version**: 1.0  
**For**: Quantitative Economics Submission Repository

---

## Overview

This document explains how the empirical data processing workflow works in the QE submission repository (`HAFiscal-QE`). The QE repository uses a Python-only workflow and stores data files in a separate branch to ensure reproducibility.

---

## QE Repository Workflow

### Running Data Analysis

In the QE repository, run:

```bash
./reproduce.sh --data
```

This command will:

1. **Automatically checkout data files** from the `with-precomputed-artifacts` branch if they're not present in the worktree
2. **Run the Python analysis** (`make_liquid_wealth.py`)
3. **Generate CSV output files** (`Data/LorenzAll.csv`, `Data/LorenzEd.csv`)
4. **Automatically clean up** data files from the main branch worktree after analysis

### Why Data Files Are Stored in a Separate Branch

The QE submission repository stores `rscfp2004.dta` and `ccbal_answer.dta` in the `with-precomputed-artifacts` branch rather than in the main branch for the following reasons:

1. **QE Requirements**: The main branch should not contain large data files
2. **Reproducibility**: The Federal Reserve periodically updates older SCF data files to adjust for inflation
3. **Stability**: By archiving our own copy (in 2013 dollars), we guarantee that computations will continue to produce the same results even when the Fed updates their inflation adjustments

### The Inflation Adjustment Problem

**The Issue**: When the Federal Reserve releases new waves of the SCF, they inflation-adjust older versions. This means:

- **Original data** (used in paper): Dollar variables in 2004 nominal dollars or 2013 dollars
- **Current download** (as of 2025): Dollar variables inflation-adjusted to 2022 dollars
- **Future downloads**: Will likely be adjusted to newer base years (2023, 2024, etc.)

**Why This Matters**: If you download `rscfp2004.dta` directly from the Fed today, it will be in 2022 dollars. Without proper inflation adjustment, dollar figures will be inflated by approximately 15.87% compared to the paper's results.

**Our Solution**: We archive a version of `rscfp2004.dta` in 2013 dollars on the `with-precomputed-artifacts` branch. This ensures that:

- Results match the paper exactly
- Future Fed updates won't affect reproducibility
- The analysis always uses the correct dollar base year

---

## Using Latest Fed Data (Advanced)

If you want to use the latest data from the Federal Reserve (for comparison or verification), you can use:

```bash
./reproduce.sh --data --use-latest-scf-data
```

**⚠️ Important Warning**: This option assumes that:

1. The downloaded SCF data is currently in **2022 dollars**
2. The inflation adjustment factor is **1.1587** (2022$ → 2013$)

**When the Fed updates their inflation adjustments** (e.g., to 2023 dollars or 2024 dollars), you will need to:

1. Update the inflation factor in `adjust_scf_inflation.py`
2. Verify the factor by comparing to the archived version
3. Update this documentation

The script will automatically:

- Download the latest data from the Fed
- Adjust it to 2013 dollars using the current inflation factor
- Run analysis on both the archived and adjusted versions
- Compare results to verify the adjustment worked correctly

---

## File Locations

### Main Branch (QE Submission)

- **Python scripts**: `Code/Empirical/make_liquid_wealth.py`, `adjust_scf_inflation.py`, etc.
- **Download script**: `Code/Empirical/download_scf_data.sh`
- **Output CSV files**: `Code/Empirical/Data/LorenzAll.csv`, `Code/Empirical/Data/LorenzEd.csv`
- **Documentation**: `Code/Empirical/README.md`, `Code/Empirical/README-QE.md`

### with-precomputed-artifacts Branch

- **`Code/Empirical/rscfp2004.dta`**: Archived SCF 2004 data in 2013 dollars
- **`Code/Empirical/ccbal_answer.dta`**: Credit card balance data (derived from p04i6.dta)
- **Other generated files**: `.bib`, `.csv`, `.obj`, `.txt` result files

---

## Workflow Details

### Automatic File Management

When you run `./reproduce.sh --data`:

1. **Check for files**: Script checks if `rscfp2004.dta` and `ccbal_answer.dta` exist in `Code/Empirical/`
2. **Checkout if missing**: If files are missing, automatically checks them out from `with-precomputed-artifacts` branch
3. **Run analysis**: Executes `make_liquid_wealth.py` to generate CSV files
4. **Cleanup**: Removes data files from main branch worktree (they remain in the branch)

### Manual File Management

If you need to manually checkout files:

```bash
cd Code/Empirical
git checkout with-precomputed-artifacts -- rscfp2004.dta ccbal_answer.dta
```

To remove files after analysis:

```bash
cd Code/Empirical
rm -f rscfp2004.dta ccbal_answer.dta p04i6.dta
```

---

## Troubleshooting

### "with-precomputed-artifacts branch not found"

**Cause**: The branch hasn't been created or pushed to remote yet.

**Solution**: Run the QE submission preparation workflow (`QE-SUBMISSION-PREPARE.md`) which creates this branch automatically.

### "Failed to checkout file from branch"

**Cause**: File doesn't exist in the branch or branch doesn't exist.

**Solution**:

1. Verify branch exists: `git branch -a | grep with-precomputed-artifacts`
2. If missing, run the QE preparation workflow
3. If branch exists but file is missing, you may need to download from Fed (see below)

### "Data download failed"

**Cause**: Network issue or Fed website unavailable.

**Solution**:

1. Check internet connection
2. Verify Fed website is accessible: <https://www.federalreserve.gov/econres/scf_2004.htm>
3. Try manual download and place files in `Code/Empirical/`

### Files downloaded but results don't match paper

**Cause**: Downloaded files are in 2022 dollars (or newer), not 2013 dollars.

**Solution**: Use the archived version from `with-precomputed-artifacts` branch, or use `--use-latest-scf-data` flag which automatically adjusts inflation.

---

## Related Documentation

- **Main README**: `Code/Empirical/README.md` - General documentation (Python-only workflow)
- **QE Submission Workflow**: `QE-SUBMISSION-PREPARE.md` - Complete QE preparation process
- **Data Vintage Details**: `docs/SCF_DATA_VINTAGE.md` - Detailed explanation of SCF data vintages

---

**Last Updated**: 2025-12-05  
**Version**: 1.0  
**Contact**: See paper for author contact information

