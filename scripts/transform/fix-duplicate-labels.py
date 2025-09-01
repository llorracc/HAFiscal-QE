#!/usr/bin/env python3
"""
fix-duplicate-labels.py

Automatically detects and fixes duplicate LaTeX labels in the document.
Part of the deterministic transformation pipeline.
"""

import re
import sys
from pathlib import Path
from collections import defaultdict

def find_all_labels(content: str) -> dict:
    """
    Find all label definitions in the content.
    
    Returns:
        Dictionary mapping label names to list of (start_pos, end_pos, full_match)
    """
    labels = defaultdict(list)
    
    # Pattern to match \label{...} commands
    pattern = r'\\label\{([^}]+)\}'
    
    for match in re.finditer(pattern, content):
        label_name = match.group(1)
        labels[label_name].append((match.start(), match.end(), match.group(0)))
    
    return labels

def fix_duplicate_labels(input_path: Path, output_path: Path) -> None:
    """
    Fix duplicate labels in the document.
    
    Args:
        input_path: Path to input tex file
        output_path: Path to output tex file
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all labels
    labels = find_all_labels(content)
    
    # Identify duplicates
    duplicates = {name: occurrences for name, occurrences in labels.items() if len(occurrences) > 1}
    
    if not duplicates:
        print("No duplicate labels found.")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return
    
    print(f"Found {len(duplicates)} duplicate labels:")
    for label_name in duplicates:
        print(f"  - {label_name}: {len(duplicates[label_name])} occurrences")
    
    # Fix duplicates by renaming subsequent occurrences
    # Sort all replacements by position (reverse order to avoid position shifts)
    replacements = []
    
    for label_name, occurrences in duplicates.items():
        # Keep the first occurrence, rename the rest
        for idx, (start_pos, end_pos, full_match) in enumerate(occurrences[1:], 1):
            new_label_name = f"{label_name}:{idx}"
            new_label = f"\\label{{{new_label_name}}}"
            replacements.append((start_pos, end_pos, new_label, label_name, new_label_name))
    
    # Sort replacements by position (reverse order)
    replacements.sort(key=lambda x: x[0], reverse=True)
    
    # Apply replacements
    modified_content = content
    label_mapping = {}
    
    for start_pos, end_pos, new_label, old_name, new_name in replacements:
        modified_content = modified_content[:start_pos] + new_label + modified_content[end_pos:]
        label_mapping[old_name] = new_name
        print(f"  Renamed: {old_name} -> {new_name}")
    
    # Now we need to update references to the renamed labels
    # This is tricky because we need to determine which occurrence each reference refers to
    # For now, we'll add a warning comment near duplicate references
    
    # Find all references
    ref_pattern = r'\\ref\{([^}]+)\}'
    ref_replacements = []
    
    for match in re.finditer(ref_pattern, modified_content):
        ref_name = match.group(1)
        if ref_name in duplicates:
            # Add a warning comment
            warning = f"% WARNING: Reference to duplicate label '{ref_name}' - may need manual review\n"
            ref_replacements.append((match.start(), match.start(), warning))
    
    # Apply reference warnings (in reverse order)
    ref_replacements.sort(key=lambda x: x[0], reverse=True)
    for start_pos, _, warning in ref_replacements:
        # Find the beginning of the line
        line_start = modified_content.rfind('\n', 0, start_pos) + 1
        modified_content = modified_content[:line_start] + warning + modified_content[line_start:]
    
    # Write the fixed content
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    print(f"\nDuplicate labels fixed and saved to: {output_path}")
    
    if ref_replacements:
        print(f"\nWARNING: Found {len(ref_replacements)} references to duplicate labels.")
        print("These have been marked with warning comments for manual review.")

def main():
    """Main entry point."""
    # Default paths
    script_dir = Path(__file__).parent
    qe_root = script_dir.parent.parent
    input_file = qe_root / "working" / "HAFiscal-QE-fixed.tex"
    output_file = qe_root / "working" / "HAFiscal-QE-labels-fixed.tex"
    
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
    
    fix_duplicate_labels(input_file, output_file)

if __name__ == "__main__":
    main() 