"""
Clean_Folders.py - Intelligent cleanup utility for robustness outputs

This script reads the robustness control flags from AggFiscalMAIN.py (SST)
and automatically determines which directories to clean based on which flags
are set to False.

SINGLE SOURCE OF TRUTH:
- AggFiscalMAIN.py defines the robustness control flags
- This script reads those flags and cleans accordingly
- No duplication of directory lists

USAGE:
    python Clean_Folders.py [--dry-run] [--size-threshold MB]

OPTIONS:
    --dry-run          Show what would be deleted without actually deleting
    --size-threshold   Only delete files larger than this (default: 1 MB)

BEHAVIOR:
- Scans AggFiscalMAIN.py to extract robustness flag values
- For each flag set to False, deletes large files (>1MB default) in corresponding directories
- Preserves small files (logs, metadata, config)
- Reports actions taken
"""

import os
import sys
import re
import argparse
from pathlib import Path

# ============================================================================
# Configuration: Map robustness flags to their output directories
# ============================================================================
FLAG_TO_DIRECTORIES = {
    'Run_ADElas_robustness': [
        'Figures/ADElas/',
        'Figures/ADElas_PVSame/'
    ],
    'Run_CRRA1_robustness': [
        'Figures/CRRA1/',
        'Figures/CRRA1_PVSame/'
    ],
    'Run_CRRA3_robustness': [
        'Figures/CRRA3/',
        'Figures/CRRA3_PVSame/'
    ],
    'Run_Rfree_robustness': [
        'Figures/Rfree_1005/',
        'Figures/Rfree_1005_PVSame/',
        'Figures/Rfree_1015/',
        'Figures/Rfree_1015_PVSame/'
    ],
    'Run_Rspell_robustness': [
        'Figures/Rspell_4/',
        'Figures/Rspell_4_PVSame/'
    ],
    'Run_LowerUBnoB': [
        'Figures/LowerUBnoB/',
        'Figures/LowerUBnoB_PVSame/'
    ],
}

# ============================================================================
# Parse AggFiscalMAIN.py to extract flag values (SST)
# ============================================================================
def read_robustness_flags_from_sst(main_script_path='./AggFiscalMAIN.py'):
    """
    Parse AggFiscalMAIN.py to extract robustness flag values.
    
    This function reads the Single Source of Truth (AggFiscalMAIN.py) to
    determine which robustness checks are enabled (True) or disabled (False).
    
    Parameters
    ----------
    main_script_path : str
        Path to AggFiscalMAIN.py
        
    Returns
    -------
    dict
        Mapping of flag names to boolean values
        Example: {'Run_CRRA1_robustness': False, 'Run_Splurge0': True}
    """
    flag_values = {}
    
    if not os.path.exists(main_script_path):
        print(f"ERROR: Cannot find {main_script_path}")
        print("This script must be run from the FromPandemicCode directory")
        sys.exit(1)
    
    with open(main_script_path, 'r') as f:
        content = f.read()
    
    # Pattern to match flag assignments like: Run_CRRA1_robustness = False
    # Matches: flag_name = True/False with optional whitespace and comments
    pattern = r'^(Run_\w+)\s*=\s*(True|False)'
    
    for line in content.split('\n'):
        match = re.match(pattern, line.strip())
        if match:
            flag_name = match.group(1)
            flag_value = match.group(2) == 'True'
            flag_values[flag_name] = flag_value
    
    return flag_values

# ============================================================================
# Cleanup function
# ============================================================================
def cleanup_directories(flag_values, flag_to_dirs, size_threshold_mb=1, dry_run=False):
    """
    Clean up directories for robustness checks that are disabled (False).
    
    Parameters
    ----------
    flag_values : dict
        Flag name to boolean value mapping from AggFiscalMAIN.py
    flag_to_dirs : dict
        Flag name to list of directories mapping
    size_threshold_mb : float
        Only delete files larger than this many MB
    dry_run : bool
        If True, show what would be deleted without actually deleting
        
    Returns
    -------
    tuple
        (total_files_deleted, total_size_mb_freed)
    """
    size_threshold_bytes = size_threshold_mb * 1_000_000
    total_deleted = 0
    total_size_mb = 0
    
    print('\n' + '='*70)
    if dry_run:
        print('DRY RUN: Showing what would be deleted (no files will be removed)')
    else:
        print('Cleanup: Removing outputs for disabled robustness checks')
    print('='*70)
    print(f'Size threshold: Files larger than {size_threshold_mb} MB')
    print('='*70 + '\n')
    
    # Process each flag
    for flag_name, directories in flag_to_dirs.items():
        flag_value = flag_values.get(flag_name)
        
        if flag_value is None:
            print(f'⚠️  Warning: Flag {flag_name} not found in AggFiscalMAIN.py')
            continue
        
        if flag_value:
            # Flag is True - skip cleanup (outputs should exist)
            print(f'✓ {flag_name} = True  → Keeping outputs')
            continue
        
        # Flag is False - cleanup these directories
        print(f'✗ {flag_name} = False → Cleaning outputs...')
        
        for rel_dir in directories:
            dir_path = './' + rel_dir
            
            if not os.path.exists(dir_path):
                print(f'    (Directory does not exist: {rel_dir})')
                continue
            
            try:
                files = os.listdir(dir_path)
                deleted_in_dir = 0
                size_in_dir = 0
                
                for item in files:
                    item_path = os.path.join(dir_path, item)
                    
                    if not os.path.isfile(item_path):
                        continue
                    
                    size = os.path.getsize(item_path)
                    
                    if size > size_threshold_bytes:
                        size_mb = size / (1024**2)
                        
                        if dry_run:
                            print(f'    [DRY RUN] Would delete: {item} ({size_mb:.1f} MB)')
                        else:
                            os.remove(item_path)
                            print(f'    Deleted: {item} ({size_mb:.1f} MB)')
                        
                        deleted_in_dir += 1
                        size_in_dir += size
                
                if deleted_in_dir > 0:
                    total_deleted += deleted_in_dir
                    total_size_mb += size_in_dir / (1024**2)
                    action = 'would delete' if dry_run else 'deleted'
                    print(f'    → {action.capitalize()} {deleted_in_dir} file(s) from {rel_dir} ({size_in_dir/(1024**2):.1f} MB)')
                else:
                    print(f'    (No large files found in {rel_dir})')
                    
            except Exception as e:
                print(f'    ✗ Error accessing {rel_dir}: {e}')
    
    return total_deleted, total_size_mb

# ============================================================================
# Main execution
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description='Clean up robustness outputs based on flags in AggFiscalMAIN.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Clean_Folders.py                    # Clean with default settings
  python Clean_Folders.py --dry-run          # Preview what would be deleted
  python Clean_Folders.py --size-threshold 5 # Only delete files >5MB
        """
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--size-threshold',
        type=float,
        default=1.0,
        metavar='MB',
        help='Only delete files larger than this many MB (default: 1.0)'
    )
    
    args = parser.parse_args()
    
    # Ensure we're in the right directory
    if not os.path.exists('./AggFiscalMAIN.py'):
        print('ERROR: AggFiscalMAIN.py not found in current directory')
        print('Please run this script from the FromPandemicCode directory')
        sys.exit(1)
    
    # Read flag values from SST
    print('Reading robustness flags from AggFiscalMAIN.py (SST)...')
    flag_values = read_robustness_flags_from_sst()
    
    if not flag_values:
        print('ERROR: No robustness flags found in AggFiscalMAIN.py')
        sys.exit(1)
    
    print(f'Found {len(flag_values)} flags in AggFiscalMAIN.py')
    
    # Perform cleanup
    total_deleted, total_size_mb = cleanup_directories(
        flag_values,
        FLAG_TO_DIRECTORIES,
        size_threshold_mb=args.size_threshold,
        dry_run=args.dry_run
    )
    
    # Summary
    print('\n' + '='*70)
    if args.dry_run:
        print('DRY RUN SUMMARY')
        print('='*70)
        if total_deleted > 0:
            print(f'Would delete {total_deleted} file(s), would free {total_size_mb:.1f} MB')
            print('\nTo actually perform cleanup, run without --dry-run:')
            print('  python Clean_Folders.py')
        else:
            print('No files would be deleted - all directories are clean.')
    else:
        print('CLEANUP SUMMARY')
        print('='*70)
        if total_deleted > 0:
            print(f'✓ Deleted {total_deleted} file(s), freed {total_size_mb:.1f} MB')
        else:
            print('✓ No orphaned outputs found - all directories are clean.')
    print('='*70 + '\n')

if __name__ == '__main__':
    main()