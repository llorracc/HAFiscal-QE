#!/usr/bin/env python3
"""
Python version of make_liquid_wealth.do

This script constructs liquid wealth from the 2004 SCF dataset and produces
empirical results used in the HAFiscal paper.

Original Stata version: make_liquid_wealth.do
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')


def load_data(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load SCF 2004 data files."""
    print("Loading data files...")
    
    # Load main data
    rscfp_file = data_dir / "rscfp2004.dta"
    if not rscfp_file.exists():
        raise FileNotFoundError(
            f"Required file not found: {rscfp_file}\n"
            "Please download from: https://www.federalreserve.gov/econres/scf_2004.htm"
        )
    
    # Load with specific columns
    columns = ['yy1', 'y1', 'wgt', 'age', 'educ', 'edcl', 'norminc', 
               'liq', 'cds', 'nmmf', 'stocks', 'bond', 'ccbal', 
               'install', 'veh_inst']
    df = pd.read_stata(rscfp_file, columns=columns)
    
    # Load or create ccbal_answer
    ccbal_file = data_dir / "ccbal_answer.dta"
    if not ccbal_file.exists():
        print("Creating ccbal_answer.dta from p04i6.dta...")
        p04i6_file = data_dir / "p04i6.dta"
        if not p04i6_file.exists():
            raise FileNotFoundError(
                f"Required file not found: {p04i6_file}\n"
                "Please download from: https://www.federalreserve.gov/econres/scf_2004.htm"
            )
        ccbal_df = pd.read_stata(p04i6_file, columns=['Y1', 'X432'])
        ccbal_df.columns = ['y1', 'x432']
        ccbal_df.to_stata(ccbal_file)
    else:
        ccbal_df = pd.read_stata(ccbal_file)
        
    # Delete p04i6.dta if it exists
    
    return df, ccbal_df


def merge_and_filter(df: pd.DataFrame, ccbal_df: pd.DataFrame) -> pd.DataFrame:
    """Merge data and perform initial filtering."""
    print("Merging and filtering data...")
    
    # Merge with ccbal_answer
    df = df.merge(ccbal_df, on='y1', how='left')
    df.loc[df['x432'] == 1, 'ccbal'] = 0
    df = df.drop(columns=['x432'])
    
    # Calculate mean age by household
    df['age'] = df.groupby('yy1')['age'].transform('mean')
    
    # Sample selection: age 25-62, positive income
    df = df[(df['age'] >= 25) & (df['age'] <= 62)]
    df = df[df['norminc'] >= 0]
    
    return df


def calculate_liquid_wealth(df: pd.DataFrame, include_installment: bool = False) -> pd.DataFrame:
    """Calculate liquid wealth measures."""
    print("Calculating liquid wealth...")
    
    # Generate liquid wealth (two measures)
    df['tempLiqWealthInst'] = (
        df['liq'] * 1.05 + df['cds'] + df['nmmf'] + df['stocks'] + 
        df['bond'] - df['ccbal'] - (df['install'] - df['veh_inst'])
    )
    df['tempLiqWealthKaplan'] = (
        df['liq'] * 1.05 + df['cds'] + df['nmmf'] + df['stocks'] + 
        df['bond'] - df['ccbal']
    )
    
    # Drop intermediate columns
    df = df.drop(columns=['liq', 'cds', 'nmmf', 'stocks', 'bond', 
                          'ccbal', 'install', 'veh_inst'])
    
    # Generate education classifications
    # 1=no high school, 2=high school/some college, 3=college
    df['myEd'] = 1
    df.loc[df['edcl'].isin([2, 3]), 'myEd'] = 2
    df.loc[df['edcl'] == 4, 'myEd'] = 3
    
    df['myEdText'] = df['myEd'].map({
        1: "No high school",
        2: "High school/some college",
        3: "College"
    })
    df = df.drop(columns=['educ', 'edcl'])
    
    # Calculate household-level aggregates
    for col in ['tempLiqWealthInst', 'tempLiqWealthKaplan', 'norminc']:
        new_col = col.replace('temp', '').replace('norminc', 'permInc')
        if 'Wealth' in col:
            new_col = new_col[0].lower() + new_col[1:]  # lowercase first letter
        df[new_col] = df.groupby('yy1')[col].transform('mean')
    
    df['weight'] = df.groupby('yy1')['wgt'].transform('mean') * 5
    df = df.drop(columns=['tempLiqWealthInst', 'tempLiqWealthKaplan', 
                          'norminc', 'wgt'])
    
    # Keep only one observation per household (where y1 mod 5 == 1)
    df = df[df['y1'] % 5 == 1]
    df = df.drop(columns=['y1'])
    
    # Drop lowest 5% of permanent income
    total_weight = df['weight'].sum()
    df['normweight'] = df['weight'] / total_weight
    df = df.sort_values('permInc')
    df['sumW'] = df['normweight'].cumsum()
    df = df[df['sumW'] >= 0.05]
    df = df.drop(columns=['normweight', 'sumW'])
    
    # Choose liquid wealth measure
    if include_installment:
        df['liqWealth'] = df['liqWealthInst']
    else:  # Default measure used in paper
        df['liqWealth'] = df['liqWealthKaplan']
    
    # Drop negative liquid wealth
    df = df[df['liqWealth'] >= 0]
    
    # Recalculate weights after dropping observations
    total_weight = df['weight'].sum()
    df['normweight'] = df['weight'] / total_weight
    
    # Calculate education-specific weights
    df['edfrac'] = df.groupby('myEd')['normweight'].transform('sum')
    df['edWeight'] = df['normweight'] / df['edfrac']
    
    return df


def calculate_statistics(df: pd.DataFrame, output_dir: Path) -> dict:
    """Calculate all empirical statistics."""
    print("\nCalculating statistics...\n")
    results = {}
    
    # Sort by liquid wealth
    df = df.sort_values(['liqWealth', 'yy1'])
    
    # Cumulative wealth distribution
    df['sumNormW'] = df['normweight'].cumsum() * 100
    total_liq_wealth = (df['normweight'] * df['liqWealth']).sum()
    
    # Education-specific totals
    df['totLiqWealth_ed'] = df.groupby('myEd').apply(
        lambda x: (x['normweight'] * x['liqWealth']).sum()
    ).loc[df['myEd']].values
    df['fracLiqWealth_ed'] = (df['totLiqWealth_ed'] / total_liq_wealth * 100).round(1)
    
    # ========================================================================
    # Display percent of population and wealth share by education
    # ========================================================================
    print("=" * 60)
    print("POPULATION AND WEALTH DISTRIBUTION BY EDUCATION")
    print("=" * 60)
    ed_summary = df.groupby('myEdText').agg({
        'edfrac': 'first',
        'fracLiqWealth_ed': 'first'
    })
    ed_summary['edfrac'] = (ed_summary['edfrac'] * 100).round(1)
    print("\nPercent of population: (see Table 2, Panel B)")
    print(ed_summary['edfrac'])
    print("\nPercent of liquid wealth: (see Table 5, Panel A)")
    print(ed_summary['fracLiqWealth_ed'])
    
    results['education_population_pct'] = ed_summary['edfrac'].to_dict()
    results['education_wealth_pct'] = ed_summary['fracLiqWealth_ed'].to_dict()
    
    # ========================================================================
    # Mean and std dev of initial income at age 25
    # ========================================================================
    print("\n" + "=" * 60)
    print("INITIAL INCOME STATISTICS (AGE 25)")
    print("(see Table 2, Panel B)")
    print("=" * 60)
    df['permIncQ'] = df['permInc'] / 4
    df['logPermIncQ'] = np.log(df['permIncQ'])
    
    for ed in [1, 2, 3]:
        subset = df[(df['myEd'] == ed) & (df['age'] == 25)]
        if len(subset) > 0:
            weights = subset['edWeight']
            log_income = subset['logPermIncQ']
            
            # Weighted statistics
            mean_log = np.average(log_income, weights=weights)
            var_log = np.average((log_income - mean_log)**2, weights=weights)
            std_log = np.sqrt(var_log)
            
            mean_income = np.exp(mean_log)
            df.loc[(df['myEd'] == ed), 'mean_initial_income'] = mean_income
            df.loc[(df['myEd'] == ed), 'sdev_initial_logIncome'] = std_log
    
    initial_income = df.groupby('myEdText').agg({
        'mean_initial_income': 'first',
        'sdev_initial_logIncome': 'first'
    })
    initial_income['mean_initial_income_display'] = (
        initial_income['mean_initial_income'] / 1000
    ).round(1)
    initial_income['sdev_initial_logIncome_display'] = (
        initial_income['sdev_initial_logIncome'].round(2)
    )
    
    print("\nMean initial quarterly income ($1000s):")
    print(initial_income['mean_initial_income_display'])
    print("\nStd dev of log initial quarterly income:")
    print(initial_income['sdev_initial_logIncome_display'])
    
    results['mean_initial_income_1000'] = initial_income['mean_initial_income_display'].to_dict()
    results['sdev_log_income'] = initial_income['sdev_initial_logIncome_display'].to_dict()
    
    # ========================================================================
    # Median liquid wealth / PI by education
    # ========================================================================
    print("\n" + "=" * 60)
    print("MEDIAN LIQUID WEALTH / PERMANENT INCOME")
    print("=" * 60)
    df['indLWoPI'] = df['liqWealth'] / df['permInc']
    
    for ed in [1, 2, 3]:
        subset = df[df['myEd'] == ed].copy()
        subset = subset.sort_values('indLWoPI')
        weights = subset['edWeight'].values
        values = subset['indLWoPI'].values
        
        # Weighted median
        cumsum = np.cumsum(weights)
        median_idx = np.searchsorted(cumsum, cumsum[-1] / 2)
        median = values[median_idx] if median_idx < len(values) else values[-1]
        df.loc[df['myEd'] == ed, 'wtMedLWoPI'] = median
    
    median_lw = df.groupby('myEdText')['wtMedLWoPI'].first()
    median_lw_display = (median_lw * 100).round(2)
    median_lw_quarterly = median_lw_display * 4
    
    print("\nMedian LW/PI (annual, %):")
    print(median_lw_display)
    print("\nMedian LW/PI (quarterly, %), (see Table 4, Panel B):")
    print(median_lw_quarterly)
    
    results['median_lw_pi_annual_pct'] = median_lw_display.to_dict()
    results['median_lw_pi_quarterly_pct'] = median_lw_quarterly.to_dict()
    
    # ========================================================================
    # Lorenz curve for all households
    # ========================================================================
    print("\n" + "=" * 60)
    print("LORENZ CURVE - ALL HOUSEHOLDS")
    print("(see Figure 2, bottom right panel)")
    print("=" * 60)
    df = df.sort_values(['liqWealth', 'yy1'])
    df['weightedLW_all'] = df['normweight'] * df['liqWealth']
    tot_weighted_lw = df['weightedLW_all'].sum()
    df['sumLWall'] = (df['weightedLW_all'] / tot_weighted_lw).cumsum() * 100
    
    # Calculate Lorenz points
    lorenz_points = {}
    for pct in [20, 40, 60, 80]:
        wealth_share = df[df['sumNormW'] < pct]['sumLWall'].max()
        lorenz_points[f'LC_all_{pct}'] = round(wealth_share, 2)
        print(f"Bottom {pct}% holds {wealth_share:.2f}% of wealth")
    
    results['lorenz_all'] = lorenz_points
    
    # Save Lorenz data for plotting
    lorenz_all = df[['yy1', 'myEd', 'sumNormW', 'sumLWall']].copy()
    data_dir = output_dir / 'Data'
    data_dir.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
    lorenz_all.to_csv(data_dir / 'LorenzAll.csv', index=False)
    print(f"\nSaved: {data_dir / 'LorenzAll.csv'}")
    
    # ========================================================================
    # Lorenz curves by education
    # ========================================================================
    print("\n" + "=" * 60)
    print("LORENZ CURVES BY EDUCATION")
    print("(see Figure 2, first three panels)")
    print("=" * 60)
    df['weightedLW'] = df['edWeight'] * df['liqWealth']
    df['totWeightedLW'] = df.groupby('myEd')['weightedLW'].transform('sum')
    df = df.sort_values(['myEd', 'liqWealth', 'yy1'])
    df['sumLW'] = df.groupby('myEd')['weightedLW'].transform(
        lambda x: (x / x.sum()).cumsum() * 100
    )
    df['sumEdW'] = df.groupby('myEd')['edWeight'].transform(
        lambda x: x.cumsum() * 100
    )
    
    for ed in [1, 2, 3]:
        ed_text = df[df['myEd'] == ed]['myEdText'].iloc[0]
        print(f"\n{ed_text}:")
        subset = df[df['myEd'] == ed]
        for pct in [20, 40, 60, 80]:
            wealth_share = subset[subset['sumEdW'] < pct]['sumLW'].max()
            print(f"  Bottom {pct}% holds {wealth_share:.2f}% of wealth")
    
    # Save Lorenz data by education
    lorenz_ed = df[['yy1', 'myEd', 'sumEdW', 'sumLW']].copy()
    data_dir = output_dir / 'Data'
    data_dir.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
    lorenz_ed.to_csv(data_dir / 'LorenzEd.csv', index=False)
    print(f"\nSaved: {data_dir / 'LorenzEd.csv'}")
    
    # ========================================================================
    # Wealth by wealth quartile
    # ========================================================================
    print("\n" + "=" * 60)
    print("WEALTH DISTRIBUTION BY WEALTH QUARTILE")
    print("(see Table 5, Panel B)")
    print("=" * 60)
    df['quartileW'] = pd.qcut(df['weightedLW_all'], q=4, labels=[1, 2, 3, 4])
    wealth_by_quartile = df.groupby('quartileW')['weightedLW_all'].sum()
    pct_by_quartile = (wealth_by_quartile / tot_weighted_lw * 100).round(2)
    
    print("\nPercent of total wealth by quartile:")
    for q, pct in pct_by_quartile.items():
        print(f"  Quartile {q}: {pct:.2f}%")
    
    results['wealth_by_quartile_pct'] = pct_by_quartile.to_dict()
    
    return results


def main():
    """Main execution function."""
    # Get script directory
    script_dir = Path(__file__).parent.absolute()
    
    print("=" * 60)
    print("HAFiscal Empirical Analysis - SCF 2004")
    print("Python version of make_liquid_wealth.do")
    print("=" * 60)
    print()
    
    try:
        # Load data
        df, ccbal_df = load_data(script_dir)
        
        # Merge and filter
        df = merge_and_filter(df, ccbal_df)
        
        # Calculate liquid wealth (False = Kaplan measure, used in paper)
        df = calculate_liquid_wealth(df, include_installment=False)
        
        # Calculate and display all statistics
        results = calculate_statistics(df, script_dir)
        
        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)
        print("\nAll results have been calculated and saved.")
        print("Output files:")
        print("  - Code/Empirical/Data/LorenzAll.csv")
        print("  - Code/Empirical/Data/LorenzEd.csv")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

