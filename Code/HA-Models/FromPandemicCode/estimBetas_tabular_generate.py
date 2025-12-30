#!/usr/bin/env python3
"""
Generate estimBetas.ltx table from AllResults file

This script parses AllResults_CRRA_2.0_R_1.01.txt and generates a LaTeX
tabular environment containing the estimated discount factor distributions
and estimation targets for each education group.

Output: Tables/CRRA2/estimBetas.ltx
"""

import re
import os
import sys

def parse_allresults(filepath):
    """
    Parse AllResults_CRRA_2.0_R_1.01.txt and extract relevant values.
    
    Returns dict with structure:
    {
        'dropout': {'beta': float, 'nabla': float, 'median_lw_pi': float, 'disc_fac_range': [float, float]},
        'highschool': {...},
        'college': {...}
    }
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Results file not found: {filepath}")
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    results = {}
    education_names = ['dropout', 'highschool', 'college']
    education_indices = [0, 1, 2]
    
    for i, name in zip(education_indices, education_names):
        # Find the line starting with "Education group = {i}.00:"
        pattern = f"Education group = {i}.00:"
        beta_nabla_line = None
        median_line = None
        approx_line = None
        
        for j, line in enumerate(lines):
            if pattern in line:
                beta_nabla_line = line
                # Median is next line
                if j + 1 < len(lines):
                    median_line = lines[j + 1]
                # Approximation is ~6 lines later
                for k in range(j + 1, min(j + 10, len(lines))):
                    if 'Actual approximation to beta distribution:' in lines[k]:
                        if k + 1 < len(lines):
                            approx_line = lines[k + 1]
                        break
                break
        
        if not all([beta_nabla_line, median_line, approx_line]):
            raise ValueError(f"Could not find all required data for {name}")
        
        # Parse beta and nabla
        beta_match = re.search(r'beta = ([\d.]+)', beta_nabla_line)
        nabla_match = re.search(r'nabla = ([\d.]+)', beta_nabla_line)
        
        # Parse median LW/PI
        median_match = re.search(r'Median LW/PI-ratio = ([\d.]+)', median_line)
        
        # Parse discount factor range [min ... max]
        # Line looks like: "\t[0.4468 0.5375 0.6282 0.719  0.8097 0.9004 0.9911]"
        approx_cleaned = approx_line.strip().replace('[', '').replace(']', '')
        disc_facs = [float(x) for x in approx_cleaned.split()]
        disc_fac_min = disc_facs[0]
        disc_fac_max = disc_facs[-1]
        
        results[name] = {
            'beta': float(beta_match.group(1)),
            'nabla': float(nabla_match.group(1)),
            'median_lw_pi': float(median_match.group(1)),
            'disc_fac_range': [disc_fac_min, disc_fac_max]
        }
    
    return results


def generate_estimBetas_ltx(results, output_path):
    """
    Generate estimBetas.ltx containing the tabular environment.
    
    The output is designed to be included via \includetabular in Tables/estimBetas.tex
    """
    
    # Data values from SCF 2004 (hardcoded empirical targets)
    data_median = {
        'dropout': 4.64,
        'highschool': 30.2,
        'college': 112.8
    }
    
    # Build the LaTeX tabular
    output = ""
    
    # Panel A: Estimated discount factor distributions
    output += "\\begin{tabular*}\n"
    output += "  {\\textwidth}{@{\\extracolsep{\\fill}}lccc@{}}\n"
    output += "  % Panel A header as part of table structure\n"
    output += "  \\multicolumn{4}{c}{\\small Panel A: Estimated discount factor distributions} \\\\\n"
    output += "  \\addlinespace\n"
    output += "  \\hline\n"
    output += "  & Dropout & Highschool & College \\\\ \\hline\n"
    
    # Row 1: (beta, nabla)
    output += "  $(\\beta_e, \\nabla_e)$ & "
    output += f"({results['dropout']['beta']:.3f}, {results['dropout']['nabla']:.3f}) & "
    output += f"({results['highschool']['beta']:.3f}, {results['highschool']['nabla']:.3f}) & "
    output += f"({results['college']['beta']:.3f}, {results['college']['nabla']:.3f}) \\\\\n"
    
    # Row 2: (Min, max) in approximation
    output += "  (Min, max) in approximation & "
    d_min, d_max = results['dropout']['disc_fac_range']
    h_min, h_max = results['highschool']['disc_fac_range']
    c_min, c_max = results['college']['disc_fac_range']
    output += f"({d_min:.3f}, {d_max:.3f}) & "
    output += f"({h_min:.3f}, {h_max:.3f}) & "
    output += f"({c_min:.3f}, {c_max:.3f}) \\\\\n"
    
    output += "  \\hline\n"
    output += "\\end{tabular*}\n"
    output += "\n"
    output += "\\vspace{0.5em}\n"
    output += "\n"
    
    # Panel B: Estimation targets
    output += "\\begin{tabular*}\n"
    output += "  {\\textwidth}{@{\\extracolsep{\\fill}}lccc@{}}\n"
    output += "  % Panel B header as part of table structure\n"
    output += "  \\multicolumn{4}{c}{\\small Panel B: Estimation targets} \\\\\n"
    output += "  \\addlinespace\n"
    output += "  \\hline\n"
    output += "  & Dropout & Highschool & College \\\\ \\hline\n"
    
    # Row 1: Median LW/PI (data)
    output += "  Median LW/ quarterly PI (data, percent) & "
    output += f"{data_median['dropout']:.2f} & "
    output += f"{data_median['highschool']:.1f} & "
    output += f"{data_median['college']:.1f} \\\\\n"
    
    # Row 2: Median LW/PI (model)
    output += "  Median LW/ quarterly PI (model, percent) & "
    output += f"{results['dropout']['median_lw_pi']:.2f} & "
    output += f"{results['highschool']['median_lw_pi']:.2f} & "
    output += f"{results['college']['median_lw_pi']:.2f} \\\\\n"
    
    output += "  \\hline\n"
    output += "\\end{tabular*}\n"
    
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
    output_file = os.path.join(script_dir, 'Tables', 'CRRA2', 'estimBetas.ltx')
    
    print(f"Reading results from: {results_file}")
    print(f"Generating table at: {output_file}")
    
    try:
        # Parse results
        results = parse_allresults(results_file)
        
        # Generate LaTeX table
        generate_estimBetas_ltx(results, output_file)
        
        print("\n✅ Success! Table generated successfully.")
        print(f"\nTo use in LaTeX, add to Tables/estimBetas.tex:")
        print(f"  \\includetabular{{\\latexroot/Code/HA-Models/FromPandemicCode/Tables/CRRA2/estimBetas.ltx}}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

