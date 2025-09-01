#!/usr/bin/env python3
"""
consolidate-subfiles.py

Consolidates HAFiscal subfiles into a single LaTeX document for QE submission.
Reads from HAFiscal-Latest and outputs consolidated content.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional

def extract_subfile_content(filepath: Path) -> str:
    """
    Extract the main content from a subfile, removing the subfile boilerplate.
    
    Args:
        filepath: Path to the subfile
        
    Returns:
        The extracted content as a string
    """
    if not filepath.exists():
        print(f"Warning: Subfile {filepath} not found")
        return f"% Content from {filepath.name} not found\n"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove subfile document structure
    # Pattern to match \documentclass through \begin{document}
    begin_pattern = r'\\documentclass.*?\\begin\{document\}'
    content = re.sub(begin_pattern, '', content, flags=re.DOTALL)
    
    # Remove \end{document}
    content = re.sub(r'\\end\{document\}', '', content)
    
    # Remove \onlyinsubfile commands and their content
    content = re.sub(r'\\onlyinsubfile\{[^}]*\}', '', content)
    
    # Process \notinsubfile commands - keep their content
    content = re.sub(r'\\notinsubfile\{([^}]*)\}', r'\1', content)
    
    # Remove \input{./.econtexRoot} commands (from subfile boilerplate)
    content = re.sub(r'\\input\{\.?/?\.econtexRoot\}', '', content)
    
    # Remove duplicate section headers if they exist
    # Look for patterns like \section{...} that appear at the beginning
    content = re.sub(r'^.*?\\hypertarget\{[^}]*\}\{\}\\par\\section\{[^}]*\}\\label\{[^}]*\}', '', content, count=1, flags=re.MULTILINE | re.DOTALL)
    
    # Remove standalone section commands at the beginning
    content = re.sub(r'^\\section\{[^}]*\}\s*', '', content, count=1, flags=re.MULTILINE)
    
    # Remove \setcounter{page} commands (from subfiles)
    content = re.sub(r'\\setcounter\{page\}\{[^}]*\}\\pagenumbering\{[^}]*\}', '', content)
    
    # Clean up extra whitespace
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    
    return content.strip()

def process_subfile_commands(content: str, base_path: Path) -> str:
    r"""
    Process \subfile{} commands in the content, replacing them with actual content.
    
    Args:
        content: LaTeX content containing \subfile commands
        base_path: Base path for resolving subfile paths
        
    Returns:
        Content with subfiles replaced by their actual content
    """
    def replace_subfile(match):
        subfile_path = match.group(1)
        full_path = base_path / f"{subfile_path}.tex"
        
        print(f"Processing subfile: {subfile_path}")
        
        # Extract content from subfile
        subfile_content = extract_subfile_content(full_path)
        
        # Add comment markers for clarity
        return f"\n% BEGIN: Content from {subfile_path}\n{subfile_content}\n% END: Content from {subfile_path}\n"
    
    # Pattern to match \subfile{...} commands
    pattern = r'\\subfile\{([^}]+)\}'
    return re.sub(pattern, replace_subfile, content)

def consolidate_hafiscal(hafiscal_latest_path: Path, output_path: Path) -> None:
    """
    Main function to consolidate HAFiscal document.
    
    Args:
        hafiscal_latest_path: Path to HAFiscal-Latest directory
        output_path: Path for output consolidated file
    """
    # Read the existing HAFiscal-QE.tex as base
    qe_template_path = hafiscal_latest_path / "HAFiscal-QE.tex"
    
    if not qe_template_path.exists():
        print(f"Error: {qe_template_path} not found")
        sys.exit(1)
    
    with open(qe_template_path, 'r', encoding='utf-8') as f:
        qe_content = f.read()
    
    # Read Subfiles.texinput to get the list of sections
    subfiles_input_path = hafiscal_latest_path / "Subfiles.texinput"
    
    if not subfiles_input_path.exists():
        print(f"Error: {subfiles_input_path} not found")
        sys.exit(1)
    
    with open(subfiles_input_path, 'r', encoding='utf-8') as f:
        subfiles_content = f.read()
    
    # Extract subfile paths
    subfile_pattern = r'\\subfile\{([^}]+)\}'
    subfiles = re.findall(subfile_pattern, subfiles_content)
    
    # Process each section placeholder in HAFiscal-QE.tex
    consolidated_content = qe_content
    
    # Define section mappings
    section_mappings = [
        ("\\section{Introduction}", "Subfiles/Intro"),
        ("\\section{Literature Review}", "Subfiles/literature"),
        ("\\section{Model}", "Subfiles/Model"),
        ("\\section{Parameterization}", "Subfiles/Parameterization"),
        ("\\section{Comparing Policies}", "Subfiles/Comparing-policies"),
        ("\\section{HANK Model Results}", "Subfiles/HANK"),
        ("\\section{Conclusion}", "Subfiles/Conclusion"),
        ("\\section{No Splurge Appendix}", "Subfiles/Appendix-NoSplurge"),
    ]
    
    # Replace section placeholders with actual content
    for section_marker, subfile_path in section_mappings:
        print(f"\nProcessing section: {section_marker}")
        
        # Find the section and its placeholder comment
        pattern = rf'({re.escape(section_marker)})\n% Content from .* would be inserted here'
        
        if re.search(pattern, consolidated_content):
            # Extract content from subfile
            full_path = hafiscal_latest_path / f"{subfile_path}.tex"
            content = extract_subfile_content(full_path)
            
            # Replace the section and placeholder with section and content
            # Use a lambda to avoid escape sequence issues
            replacement = lambda m: f"{section_marker}\n{content}"
            consolidated_content = re.sub(pattern, replacement, consolidated_content)
        else:
            print(f"  Warning: Section marker '{section_marker}' not found in template")
    
    # Handle bibliography file
    # Copy HAFiscal.bib to working directory (will be done by main script)
    
    # Write consolidated content
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(consolidated_content)
    
    print(f"\nConsolidation complete. Output written to: {output_path}")
    
    # Report statistics
    original_lines = len(qe_content.splitlines())
    consolidated_lines = len(consolidated_content.splitlines())
    print(f"\nStatistics:")
    print(f"  Original template: {original_lines} lines")
    print(f"  Consolidated document: {consolidated_lines} lines")
    print(f"  Lines added: {consolidated_lines - original_lines}")

def main():
    """Main entry point."""
    # Default paths
    script_dir = Path(__file__).parent
    qe_root = script_dir.parent.parent
    hafiscal_latest = qe_root.parent / "HAFiscal-Latest"
    output_file = qe_root / "working" / "HAFiscal-QE-consolidated.tex"
    
    # Allow command line override
    if len(sys.argv) > 1:
        hafiscal_latest = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_file = Path(sys.argv[2])
    
    print(f"HAFiscal-Latest path: {hafiscal_latest}")
    print(f"Output path: {output_file}")
    
    if not hafiscal_latest.exists():
        print(f"Error: HAFiscal-Latest directory not found at {hafiscal_latest}")
        sys.exit(1)
    
    consolidate_hafiscal(hafiscal_latest, output_file)

if __name__ == "__main__":
    main() 