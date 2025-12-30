#!/usr/bin/env python3
"""
Compare empirical results from git-versioned vs. adjusted latest SCF data

This script runs the SCF analysis on both datasets and shows a detailed comparison
to verify that the inflation adjustment is working correctly.

Usage:
    python compare_scf_datasets.py rscfp2004_git_2013USD.dta rscfp2004_latest_adjusted_2013USD.dta
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from make_liquid_wealth import merge_and_filter, calculate_liquid_wealth, calculate_statistics


def load_and_analyze(data_file: Path, ccbal_file: Path, label: str) -> dict:
    """
    Load data and run full analysis pipeline.
    
    Returns dictionary with key statistics.
    """
    print(f"\n{'='*70}")
    print(f"Analyzing: {label}")
    print(f"File: {data_file.name}")
    print(f"{'='*70}\n")
    
    # Load main data
    columns = ['yy1', 'y1', 'wgt', 'age', 'educ', 'edcl', 'norminc', 
               'liq', 'cds', 'nmmf', 'stocks', 'bond', 'ccbal', 
               'install', 'veh_inst']
    df = pd.read_stata(data_file, columns=columns)
    
    # Load ccbal_answer
    ccbal_df = pd.read_stata(ccbal_file)
    
    # Run merge and filter
    df = merge_and_filter(df, ccbal_df)
    
    # Calculate liquid wealth BEFORE filtering to implicate
    # (we need the raw data with all columns)
    df['tempLiqWealthKaplan'] = (
        df['liq'] * 1.05 + df['cds'] + df['nmmf'] + df['stocks'] + 
        df['bond'] - df['ccbal']
    )
    
    # Add education classification
    df['myEd'] = 1
    df.loc[df['edcl'].isin([2, 3]), 'myEd'] = 2
    df.loc[df['edcl'] == 4, 'myEd'] = 3
    
    # Filter to first implicate for statistics
    df_imp1 = df[df['y1'] % 10 == 1].copy()
    
    # Extract key statistics
    results = {}
    
    # Sample size (before implicate filtering)
    results['n_observations'] = len(df)
    results['n_households'] = df['yy1'].nunique()
    
    # Income statistics (using first implicate)
    hh_income = df_imp1.groupby('yy1')['norminc'].first()
    hh_wgt = df_imp1.groupby('yy1')['wgt'].first()
    
    results['median_income'] = np.median(hh_income)
    results['mean_income'] = np.average(hh_income, weights=hh_wgt)
    results['min_income'] = hh_income.min()
    
    # Liquid wealth statistics (using first implicate)
    hh_wealth = df_imp1.groupby('yy1')['tempLiqWealthKaplan'].first()
    
    results['median_liq_wealth'] = np.median(hh_wealth)
    results['mean_liq_wealth'] = np.average(hh_wealth, weights=hh_wgt)
    
    # Wealth-to-income ratio
    wealth_income_ratio = hh_wealth / hh_income
    results['median_wealth_income_ratio'] = np.median(wealth_income_ratio)
    
    # Fraction with negative liquid wealth
    results['frac_negative_wealth'] = np.average(
        (hh_wealth < 0).astype(float),
        weights=hh_wgt
    )
    
    # Age statistics
    hh_age = df_imp1.groupby('yy1')['age'].first()
    results['mean_age'] = np.average(hh_age, weights=hh_wgt)
    
    # Education distribution
    hh_ed = df_imp1.groupby('yy1')['myEd'].first()
    for ed in [1, 2, 3]:
        results[f'frac_ed_{ed}'] = np.average(
            (hh_ed == ed).astype(float),
            weights=hh_wgt
        )
    
    # Percentiles of liquid wealth (unweighted for simplicity)
    for pct in [10, 25, 50, 75, 90]:
        results[f'p{pct}_liq_wealth'] = np.percentile(hh_wealth, pct)
    
    return results


def print_comparison(results_git: dict, results_latest: dict):
    """Print detailed comparison of results."""
    print("\n" + "="*80)
    print("COMPARISON: Git-versioned (2013$) vs. Latest Adjusted (2013$)")
    print("="*80)
    print()
    
    # Sample size
    print("Sample Size:")
    print(f"  {'Metric':<30} {'Git-versioned':>20} {'Latest Adjusted':>20}")
    print("-" * 80)
    print(f"  {'Observations':<30} {results_git['n_observations']:>20,} {results_latest['n_observations']:>20,}")
    print(f"  {'Households':<30} {results_git['n_households']:>20,} {results_latest['n_households']:>20,}")
    print()
    
    # Dollar-denominated statistics
    print("Dollar-Denominated Statistics (should match closely):")
    print(f"  {'Metric':<30} {'Git-versioned':>20} {'Latest Adjusted':>20} {'% Diff':>10}")
    print("-" * 80)
    
    dollar_metrics = [
        ('median_income', 'Median Income'),
        ('mean_income', 'Mean Income'),
        ('min_income', 'Minimum Income'),
        ('median_liq_wealth', 'Median Liquid Wealth'),
        ('mean_liq_wealth', 'Mean Liquid Wealth'),
        ('p10_liq_wealth', 'P10 Liquid Wealth'),
        ('p25_liq_wealth', 'P25 Liquid Wealth'),
        ('p50_liq_wealth', 'P50 Liquid Wealth'),
        ('p75_liq_wealth', 'P75 Liquid Wealth'),
        ('p90_liq_wealth', 'P90 Liquid Wealth'),
    ]
    
    max_dollar_diff = 0
    for key, label in dollar_metrics:
        git_val = results_git[key]
        latest_val = results_latest[key]
        pct_diff = abs(latest_val - git_val) / abs(git_val) * 100 if git_val != 0 else 0
        max_dollar_diff = max(max_dollar_diff, pct_diff)
        print(f"  {label:<30} ${git_val:>19,.0f} ${latest_val:>19,.0f} {pct_diff:>9.3f}%")
    
    print()
    
    # Non-dollar statistics
    print("Non-Dollar Statistics (should match exactly):")
    print(f"  {'Metric':<30} {'Git-versioned':>20} {'Latest Adjusted':>20} {'% Diff':>10}")
    print("-" * 80)
    
    non_dollar_metrics = [
        ('median_wealth_income_ratio', 'Median Wealth/Income'),
        ('frac_negative_wealth', 'Frac. Negative Wealth'),
        ('mean_age', 'Mean Age'),
        ('frac_ed_1', 'Frac. No HS'),
        ('frac_ed_2', 'Frac. HS/Some College'),
        ('frac_ed_3', 'Frac. College'),
    ]
    
    max_nondollar_diff = 0
    for key, label in non_dollar_metrics:
        git_val = results_git[key]
        latest_val = results_latest[key]
        pct_diff = abs(latest_val - git_val) / abs(git_val) * 100 if git_val != 0 else 0
        max_nondollar_diff = max(max_nondollar_diff, pct_diff)
        
        if 'frac' in key or 'ratio' in key:
            print(f"  {label:<30} {git_val:>20.4f} {latest_val:>20.4f} {pct_diff:>9.3f}%")
        else:
            print(f"  {label:<30} {git_val:>20.2f} {latest_val:>20.2f} {pct_diff:>9.3f}%")
    
    print()
    print("="*80)
    print("SUMMARY:")
    print(f"  Maximum difference in dollar values:     {max_dollar_diff:.4f}%")
    print(f"  Maximum difference in non-dollar values: {max_nondollar_diff:.4f}%")
    print()
    
    if max_dollar_diff < 0.05 and max_nondollar_diff < 0.01:
        print("✅ EXCELLENT MATCH!")
        print("   The inflation adjustment is working correctly.")
        print("   Both datasets produce essentially identical results.")
    elif max_dollar_diff < 0.1:
        print("✅ GOOD MATCH!")
        print("   Small differences likely due to rounding in Stata format.")
        print("   Results are consistent within acceptable tolerance.")
    else:
        print("⚠️  SIGNIFICANT DIFFERENCES DETECTED")
        print("   The datasets may not be properly aligned.")
        print("   Review the inflation adjustment procedure.")
    
    print("="*80)


def main():
    """Main comparison routine."""
    if len(sys.argv) != 3:
        print("Usage: python compare_scf_datasets.py GIT_FILE LATEST_FILE")
        print()
        print("Example:")
        print("  python compare_scf_datasets.py \\")
        print("    rscfp2004_git_2013USD.dta \\")
        print("    rscfp2004_latest_adjusted_2013USD.dta")
        return 1
    
    git_file = Path(sys.argv[1])
    latest_file = Path(sys.argv[2])
    
    # Check files exist
    if not git_file.exists():
        print(f"❌ Error: File not found: {git_file}")
        return 1
    if not latest_file.exists():
        print(f"❌ Error: File not found: {latest_file}")
        return 1
    
    # Check for ccbal_answer.dta
    ccbal_file = git_file.parent / "ccbal_answer.dta"
    if not ccbal_file.exists():
        print(f"❌ Error: Required file not found: {ccbal_file}")
        print("   Please run make_liquid_wealth.py first to create this file.")
        return 1
    
    print("="*80)
    print("SCF DATASET COMPARISON")
    print("="*80)
    print()
    print("This script compares empirical results from:")
    print(f"  1. Git-versioned data (2013$):  {git_file.name}")
    print(f"  2. Latest adjusted data (2013$): {latest_file.name}")
    print()
    print("Both datasets should produce nearly identical results if the")
    print("inflation adjustment (2022$ / 1.1587 = 2013$) is working correctly.")
    print()
    
    try:
        # Analyze git-versioned data
        results_git = load_and_analyze(git_file, ccbal_file, "Git-versioned (2013$)")
        
        # Analyze latest adjusted data
        results_latest = load_and_analyze(latest_file, ccbal_file, "Latest Adjusted (2013$)")
        
        # Print comparison
        print_comparison(results_git, results_latest)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

