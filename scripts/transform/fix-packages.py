#!/usr/bin/env python3
"""
fix-packages.py

Automatically fixes missing LaTeX packages and commands in the QE document.
Part of the deterministic transformation pipeline.
"""

import re
import sys
from pathlib import Path

def fix_packages(input_path: Path, output_path: Path) -> None:
    """
    Fix missing packages and commands in the QE document.
    
    Args:
        input_path: Path to input tex file
        output_path: Path to output tex file
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    packages_to_add = []
    
    # Find where to insert additional packages (after existing usepackage commands)
    # Look for the last \usepackage before \endlocaldefs
    package_insert_match = re.search(r'(\\usepackage\{natbib\})', content)
    if package_insert_match:
        insert_pos = package_insert_match.end()
        
        # Packages to add for missing commands
        additional_packages = """
% Additional packages for QE compatibility
\\usepackage{nth}          % For \\nth command (ordinals)
\\usepackage{makecell}     % For \\makecell command in tables
\\usepackage{placeins}     % For \\FloatBarrier command
\\usepackage{afterpage}    % For \\afterpage command
\\usepackage{comment}      % For comment environment
\\usepackage{rotating}     % Already added but ensure it's there
"""
        
        # Insert the packages if they're not already present
        packages_to_check = [
            ('nth', '\\usepackage{nth}'),
            ('makecell', '\\usepackage{makecell}'),
            ('placeins', '\\usepackage{placeins}'),
            ('afterpage', '\\usepackage{afterpage}'),
            ('comment', '\\usepackage{comment}')
        ]
        
        packages_to_add = []
        for pkg_name, pkg_cmd in packages_to_check:
            if f'\\usepackage{{{pkg_name}}}' not in content:
                packages_to_add.append(pkg_cmd)
        
        if packages_to_add:
            additional_packages = '\n% Additional packages for QE compatibility\n' + '\n'.join(packages_to_add) + '\n'
            content = content[:insert_pos] + additional_packages + content[insert_pos:]
    
    # Fix \econtexRoot command error
    # Remove the malformed \renewcommand{\econtexRoot{.}}
    content = re.sub(r'\\renewcommand\{\\econtexRoot\{[^}]*\}\}', '', content)
    
    # Add proper definition if needed
    if '\\newcommand{\\econtexRoot}' not in content and '\\renewcommand{\\econtexRoot}' not in content:
        # Add definition in the preamble
        preamble_insert = re.search(r'(\\newcommand\{\\notinsubfile\}[^}]*\})', content)
        if preamble_insert:
            econtex_def = '\n% Define econtexRoot for compatibility\n\\newcommand{\\econtexRoot}[1]{}\n'
            content = content[:preamble_insert.end()] + econtex_def + content[preamble_insert.end():]
    
    # Fix font shape warnings
    # Add font substitution rules
    font_fix_match = re.search(r'(\\endlocaldefs)', content)
    if font_fix_match:
        font_fixes = """
% Font shape substitutions to avoid warnings
\\substitutefont{T1}{put}{m}{scit}{T1}{put}{m}{sc}
"""
        # Only add if not already present
        if '\\substitutefont' not in content:
            content = content[:font_fix_match.start()] + font_fixes + '\n' + content[font_fix_match.start():]
    
    # Write the fixed content
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Package fixes applied and saved to: {output_path}")
    
    # Report what was fixed
    print("\nFixes applied:")
    if packages_to_add:
        print(f"  - Added {len(packages_to_add)} missing packages")
    print("  - Fixed \\econtexRoot command definition")
    print("  - Added font substitution rules")

def main():
    """Main entry point."""
    # Default paths
    script_dir = Path(__file__).parent
    qe_root = script_dir.parent.parent
    input_file = qe_root / "working" / "HAFiscal-QE-clean.tex"
    output_file = qe_root / "working" / "HAFiscal-QE-fixed.tex"
    
    # Allow command line override
    if len(sys.argv) > 1:
        input_file = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_file = Path(sys.argv[2])
    
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    
    if not input_file.exists():
        print(f"Error: Input file not found at {input_file}")
        sys.exit(1)
    
    fix_packages(input_file, output_file)

if __name__ == "__main__":
    main() 