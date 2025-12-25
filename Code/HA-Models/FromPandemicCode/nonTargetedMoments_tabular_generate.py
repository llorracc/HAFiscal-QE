#!/usr/bin/env python3
"""
Generate nonTargetedMoments.ltx table from AllResults file

This script parses AllResults_CRRA_2.0_R_1.01.txt and generates a LaTeX
tabular environment showing model fit with respect to non-targeted moments
(wealth shares and MPCs by education group and wealth quartile).

Output: Tables/CRRA2/nonTargetedMoments.ltx
"""

import re
import os
import sys

def parse_allresults(filepath):
    """
    Parse AllResults_CRRA_2.0_R_1.01.txt and extract non-targeted moment values.
    
    Returns dict with structure:
    {
        'wealth_shares_by_ed': [dropout, highschool, college],  # percents
        'wealth_shares_by_wq': [wq4, wq3, wq2, wq1],           # percents  
        'mpc_by_ed': [dropout, highschool, college, population],
        'mpc_by_wq': [wq4, wq3, wq2, wq1, population]
    }
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Results file not found: {filepath}")
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    results = {}
    
    # Find the "Population calculations:" section
    for i, line in enumerate(lines):
        if 'Population calculations:' in line:
            # Next few lines contain the data we need
            # Look for specific patterns
            for j in range(i, min(i + 20, len(lines))):
                current_line = lines[j]
                
                # Line 37: Wealth shares by Ed.= [1.207, 16.826, 81.968]
                if 'Wealth shares by Ed.' in current_line:
                    match = re.search(r'\[([\d., ]+)\]', current_line)
                    if match:
                        values = [float(x.strip()) for x in match.group(1).split(',')]
                        results['wealth_shares_by_ed'] = values
                
                # Line 38: Wealth Shares by Wealth Q = [0.12, 0.98, 3.85, 95.06]
                # This is ordered from poorest to richest
                if 'Wealth Shares by Wealth Q' in current_line:
                    match = re.search(r'\[([\d., ]+)\]', current_line)
                    if match:
                        values = [float(x.strip()) for x in match.group(1).split(',')]
                        # Table header is [WQ4, WQ3, WQ2, WQ1] where WQ4=poorest, WQ1=richest
                        # AllResults is already in this order [poorest...richest]
                        results['wealth_shares_by_wq'] = values
                
                # Line 44: Average lottery-win-year MPCs by Wealth (incl. splurge) = [0.74, 0.609, 0.475, 0.324, 0.537]
                # This is ordered from richest to poorest (opposite of wealth shares!)
                if 'Average lottery-win-year MPCs by Wealth (incl. splurge)' in current_line and 'simple' not in current_line:
                    match = re.search(r'\[([\d., ]+)\]', current_line)
                    if match:
                        values = [float(x.strip()) for x in match.group(1).split(',')]
                        # First 4 are MPCs by WQ (from richest to poorest), last is population
                        # Table wants [WQ4, WQ3, WQ2, WQ1] = [poorest to richest]
                        # So reverse the first 4 values
                        results['mpc_by_wq'] = list(reversed(values[:4])) + [values[4]]
                
                # Line 45: Average lottery-win-year MPCs by Education (incl. splurge) = [0.777, 0.606, 0.383, 0.537]
                if 'Average lottery-win-year MPCs by Education (incl. splurge)' in current_line:
                    match = re.search(r'\[([\d., ]+)\]', current_line)
                    if match:
                        values = [float(x.strip()) for x in match.group(1).split(',')]
                        # First 3 are by education, last is population
                        results['mpc_by_ed'] = values
    
    # Validate that we found everything
    required_keys = ['wealth_shares_by_ed', 'wealth_shares_by_wq', 'mpc_by_ed', 'mpc_by_wq']
    for key in required_keys:
        if key not in results:
            raise ValueError(f"Could not find required data: {key}")
    
    return results


def generate_nonTargetedMoments_ltx(results, output_path):
    """
    Generate nonTargetedMoments.ltx containing the tabular environment.
    
    The output is designed to be included via \includetabular in Tables/nonTargetedMoments.tex
    """
    
    # Empirical data values from SCF 2004 (hardcoded)
    # Wealth shares by education group (percent)
    data_wealth_ed = [0.8, 17.9, 81.2]  # [dropout, highschool, college]
    
    # Wealth shares by wealth quartile (percent) - from poorest to richest
    data_wealth_wq = [0.14, 1.60, 8.51, 89.76]  # [WQ4, WQ3, WQ2, WQ1]
    
    # Extract model values
    model_wealth_ed = results['wealth_shares_by_ed']
    model_wealth_wq = results['wealth_shares_by_wq']
    mpc_ed = results['mpc_by_ed']
    mpc_wq = results['mpc_by_wq']
    
    # Build the LaTeX tabular
    output = ""
    
    # Panel A: Non-targeted moments by education group
    output += "%   Panel A header as part of table structure\n"
    output += "\\centering\n"
    output += "\\begin{tabular}{lcccc}\n"
    output += "  \\multicolumn{5}{c}{\\small Panel A: Non-targeted moments by education group}    \\\\\n"
    output += "  \\addlinespace\n"
    output += "  \\hline\n"
    output += "                               & Dropout & Highschool & College & Population \\\\\n"
    output += "  \\hline\n"
    
    # Row 1: Percent of liquid wealth (data)
    output += f"  Percent of liquid wealth (data)  & {data_wealth_ed[0]:.1f}     & {data_wealth_ed[1]:.1f}       & {data_wealth_ed[2]:.1f}    & 100        \\\\\n"
    
    # Row 2: Percent of liquid wealth (model)
    output += f"  Percent of liquid wealth (model) & {model_wealth_ed[0]:.1f}     & {model_wealth_ed[1]:.1f}       & {model_wealth_ed[2]:.1f}    & 100        \\\\\n"
    
    output += "  \\hline\n"
    
    # Row 3: Avg. lottery-win-year MPC
    output += f"  Avg.\\ lottery-win-year MPC       & {mpc_ed[0]:.2f}    & {mpc_ed[1]:.2f}       & {mpc_ed[2]:.2f}    & {mpc_ed[3]:.2f}       \\\\\n"
    
    output += "  \\hline\n"
    output += "\\end{tabular}\n"
    output += "\n"
    output += "\\vspace{0.5em}\n"
    output += "\n"
    
    # Panel B: Non-targeted moments by wealth quartile
    output += "%     Panel B header as part of table structure\n"
    output += "\\centering\n"
    output += "\\begin{tabular}{lcccc}\n"
    output += "  \\multicolumn{5}{c}{\\small Panel B: Non-targeted moments by wealth quartile} \\\\\n"
    output += "  \\addlinespace\n"
    output += "  \\hline\n"
    output += "                               & WQ 4 & WQ 3 & WQ 2 & WQ 1                \\\\\n"
    output += "  \\hline\n"
    
    # Row 1: Percent of liquid wealth (data)
    output += f"  Percent of liquid wealth (data)  & {data_wealth_wq[0]:.2f} & {data_wealth_wq[1]:.2f} & {data_wealth_wq[2]:.2f} & {data_wealth_wq[3]:.2f}               \\\\\n"
    
    # Row 2: Percent of liquid wealth (model)
    output += f"  Percent of liquid wealth (model) & {model_wealth_wq[0]:.2f} & {model_wealth_wq[1]:.2f} & {model_wealth_wq[2]:.2f} & {model_wealth_wq[3]:.2f}               \\\\\n"
    
    output += "  \\hline\n"
    
    # Row 3: Avg. lottery-win-year MPC
    output += f"  Avg.\\ lottery-win-year MPC       & {mpc_wq[0]:.2f} & {mpc_wq[1]:.2f} & {mpc_wq[2]:.2f} & {mpc_wq[3]:.2f}                \\\\\n"
    
    output += "  \\hline\n"
    output += "\\end{tabular}\n"
    
    # Write to file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(output)
    
    print(f"✅ Generated {output_path}")


def main():
    """Main entry point"""
    
    # Determine paths relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Input: AllResults file
    results_file = os.path.join(script_dir, '..', 'Results', 'AllResults_CRRA_2.0_R_1.01.txt')
    
    # Output: LaTeX tabular file
    output_file = os.path.join(script_dir, 'Tables', 'CRRA2', 'nonTargetedMoments.ltx')
    
    print(f"Reading results from: {results_file}")
    print(f"Generating table at: {output_file}")
    
    try:
        # Parse results
        results = parse_allresults(results_file)
        
        # Generate LaTeX table
        generate_nonTargetedMoments_ltx(results, output_file)
        
        print("\n✅ Success! Table generated successfully.")
        print(f"\nTo use in LaTeX, add to Tables/nonTargetedMoments.tex:")
        print(f"  \\includetabular{{\\latexroot/Code/HA-Models/FromPandemicCode/Tables/CRRA2/nonTargetedMoments.ltx}}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

