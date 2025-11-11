#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adjust SCF 2004 data from 2022 dollars to 2013 dollars

This script converts dollar-denominated variables in the SCF 2004 summary extract
from 2022 dollars (current Fed download) to 2013 dollars (paper vintage) by
dividing by the empirically-determined inflation factor of 1.1587.

Usage:
    python adjust_scf_inflation.py rscfp2004.dta rscfp2004_adjusted.dta

The inflation factor 1.1587 was determined by comparing the git-versioned
(2013$) and current (2022$) versions of the data. This factor is perfectly
consistent across all dollar-denominated variables.

See docs/SCF_DATA_VINTAGE.md for detailed explanation.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Empirically-determined inflation factor (2013$ → 2022$)
INFLATION_FACTOR = 1.1587

# Dollar-denominated variables in rscfp2004.dta
# These are the variables that need to be adjusted
DOLLAR_VARIABLES = [
    'income',      # Total household income
    'wageinc',     # Wage income
    'bussefarminc', # Business/farm/self-employment income
    'intdivinc',   # Interest/dividend income
    'kginc',       # Capital gains income
    'ssretinc',    # Social Security/retirement income
    'transfothinc', # Transfer/other income
    'norminc',     # Normal income (permanent income measure)
    'networth',    # Net worth
    'asset',       # Total assets
    'fin',         # Financial assets
    'nfin',        # Non-financial assets
    'debt',        # Total debt
    'mrthel',      # Mortgage/home equity loan debt
    'resdbt',      # Other residential debt
    'othloc',      # Other lines of credit
    'ccbal',       # Credit card balance
    'install',     # Installment loans
    'odebt',       # Other debt
    'liq',         # Liquid assets
    'cds',         # CDs
    'nmmf',        # Money market funds
    'stocks',      # Stocks
    'bond',        # Bonds
    'savbnd',      # Savings bonds
    'cashli',      # Cash value of life insurance
    'othma',       # Other managed assets
    'othfin',      # Other financial assets
    'vehic',       # Vehicles
    'houses',      # Primary residence value
    'oresre',      # Other residential real estate
    'nnresre',     # Non-residential real estate
    'bus',         # Business equity
    'othnfin',     # Other non-financial assets
    'veh_inst',    # Vehicle installment debt
]

def adjust_inflation(input_file, output_file):
    """
    Adjust dollar variables from 2022$ to 2013$ by dividing by inflation factor.
    
    Parameters
    ----------
    input_file : str or Path
        Path to input .dta file (2022 dollars)
    output_file : str or Path
        Path to output .dta file (2013 dollars)
    """
    print(f"Loading data from: {input_file}")
    df = pd.read_stata(input_file)
    
    print(f"Data shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
    print()
    
    # Identify which dollar variables are present in the data
    present_vars = [var for var in DOLLAR_VARIABLES if var in df.columns]
    missing_vars = [var for var in DOLLAR_VARIABLES if var not in df.columns]
    
    print(f"Adjusting {len(present_vars)} dollar-denominated variables:")
    print(f"  Inflation factor: {INFLATION_FACTOR}")
    print(f"  Conversion: 2022$ / {INFLATION_FACTOR} = 2013$")
    print()
    
    # Adjust each dollar variable
    adjusted_count = 0
    for var in present_vars:
        # Check if variable has any non-zero values
        if df[var].abs().max() > 0:
            df[var] = df[var] / INFLATION_FACTOR
            adjusted_count += 1
    
    print(f"✓ Adjusted {adjusted_count} variables")
    
    if missing_vars:
        print(f"\nNote: {len(missing_vars)} expected variables not found in data:")
        for var in missing_vars[:5]:  # Show first 5
            print(f"  - {var}")
        if len(missing_vars) > 5:
            print(f"  ... and {len(missing_vars) - 5} more")
    
    print()
    print(f"Saving adjusted data to: {output_file}")
    df.to_stata(output_file, write_index=False)
    
    print()
    print("✓ Inflation adjustment complete!")
    print()
    print("The adjusted file now uses 2013 dollars and should match")
    print("the git-versioned data and paper results.")

def verify_adjustment(original_2013_file, adjusted_file):
    """
    Verify that the adjustment worked by comparing to the original 2013$ file.
    
    Parameters
    ----------
    original_2013_file : str or Path
        Path to original git-versioned file (2013 dollars)
    adjusted_file : str or Path
        Path to adjusted file (should now be 2013 dollars)
    """
    print("="*70)
    print("VERIFICATION: Comparing adjusted file to git-versioned file")
    print("="*70)
    print()
    
    df_orig = pd.read_stata(original_2013_file)
    df_adj = pd.read_stata(adjusted_file)
    
    # Check a few key variables
    test_vars = ['income', 'networth', 'norminc']
    
    print("Comparing medians (first implicate):")
    for var in test_vars:
        if var in df_orig.columns and var in df_adj.columns:
            # Use first implicate
            orig_imp1 = df_orig[df_orig['y1'] % 10 == 1]
            adj_imp1 = df_adj[df_adj['y1'] % 10 == 1]
            
            orig_med = orig_imp1[var].median()
            adj_med = adj_imp1[var].median()
            diff = abs(orig_med - adj_med)
            pct_diff = (diff / orig_med * 100) if orig_med != 0 else 0
            
            print(f"  {var:12} Original: ${orig_med:>10,.0f}  Adjusted: ${adj_med:>10,.0f}  Diff: {pct_diff:.3f}%")
    
    print()
    print("If differences are < 0.01%, the adjustment is working correctly.")
    print("="*70)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python adjust_scf_inflation.py INPUT.dta OUTPUT.dta")
        print()
        print("Converts SCF 2004 data from 2022 dollars to 2013 dollars")
        print("by dividing dollar variables by 1.1587")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    adjust_inflation(input_file, output_file)
    
    # If original 2013$ file exists, verify the adjustment
    original_2013 = input_file.parent / "rscfp2004_2013USD.dta"
    if original_2013.exists():
        print()
        verify_adjustment(original_2013, output_file)

