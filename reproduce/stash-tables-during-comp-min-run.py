#!/usr/bin/env python3
"""
Table File Management for HAFiscal Minimal Reproduction

This script manages table files during minimal computational reproduction.
It backs up original tables, renames newly generated tables with _min suffix,
and restores original tables so the paper continues to use full results.

Usage:
    stash-tables-during-comp-min-run.py PROJECT_ROOT backup TABLE1 [TABLE2 ...]
    stash-tables-during-comp-min-run.py PROJECT_ROOT rename_min TABLE1 [TABLE2 ...]
    stash-tables-during-comp-min-run.py PROJECT_ROOT restore TABLE1 [TABLE2 ...]

Actions:
    backup      - Create .backup copies of existing tables
    rename_min  - Rename tables with _min suffix (e.g., Table.tex -> Table_min.tex)
    restore     - Restore original tables from .backup files and remove backups

Example:
    python3 stash-tables-during-comp-min-run.py /path/to/project backup Tables/MyTable.tex
    python3 stash-tables-during-comp-min-run.py /path/to/project rename_min Tables/MyTable.tex
    python3 stash-tables-during-comp-min-run.py /path/to/project restore Tables/MyTable.tex

This allows minimal reproduction to generate _min versions of tables
while preserving the original full-computation tables for the paper.
"""

import sys
import os
import shutil
from pathlib import Path


def backup_tables(project_root, tables):
    """
    Create backup copies of existing tables.
    
    Args:
        project_root: Path to project root directory
        tables: List of relative paths to table files
    """
    backed_up = 0
    skipped = 0
    
    for table in tables:
        src = Path(project_root) / table
        
        if not src.exists():
            skipped += 1
            continue
            
        dst = Path(str(src) + '.backup')
        
        try:
            shutil.copy2(src, dst)
            print(f"  ✓ Backed up: {table}")
            backed_up += 1
        except Exception as e:
            print(f"  ✗ Error backing up {table}: {e}", file=sys.stderr)
    
    if backed_up > 0:
        print(f"\nBackup summary: {backed_up} files backed up, {skipped} skipped")


def rename_min(project_root, tables):
    """
    Rename tables with _min suffix before extension.
    
    Example: Table.tex -> Table_min.tex
    
    Args:
        project_root: Path to project root directory
        tables: List of relative paths to table files
    """
    renamed = 0
    skipped = 0
    
    for table in tables:
        src = Path(project_root) / table
        
        if not src.exists():
            skipped += 1
            continue
        
        # Split path and filename
        parent = src.parent
        stem = src.stem  # filename without extension
        suffix = src.suffix  # extension with dot
        
        # Create new filename with _min suffix
        dst = parent / f"{stem}_min{suffix}"
        
        try:
            shutil.move(src, dst)
            print(f"  ✓ Renamed: {table} → {dst.name}")
            renamed += 1
        except Exception as e:
            print(f"  ✗ Error renaming {table}: {e}", file=sys.stderr)
    
    if renamed > 0:
        print(f"\nRename summary: {renamed} files renamed, {skipped} skipped")


def restore_tables(project_root, tables):
    """
    Restore original tables from backup files.
    
    Copies .backup files back to original names and removes backups.
    
    Args:
        project_root: Path to project root directory
        tables: List of relative paths to table files
    """
    restored = 0
    skipped = 0
    
    for table in tables:
        src = Path(project_root) / table
        backup = Path(str(src) + '.backup')
        
        if not backup.exists():
            skipped += 1
            continue
        
        try:
            # Restore original file from backup
            shutil.copy2(backup, src)
            # Remove backup file
            backup.unlink()
            print(f"  ✓ Restored: {table}")
            restored += 1
        except Exception as e:
            print(f"  ✗ Error restoring {table}: {e}", file=sys.stderr)
    
    if restored > 0:
        print(f"\nRestore summary: {restored} files restored, {skipped} skipped")


def show_usage():
    """Display usage information."""
    print(__doc__)


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Error: Insufficient arguments\n", file=sys.stderr)
        show_usage()
        sys.exit(1)
    
    project_root = sys.argv[1]
    action = sys.argv[2]
    tables = sys.argv[3:]
    
    if not tables:
        print("Error: No table files specified\n", file=sys.stderr)
        show_usage()
        sys.exit(1)
    
    # Verify project root exists
    if not os.path.isdir(project_root):
        print(f"Error: Project root directory not found: {project_root}", file=sys.stderr)
        sys.exit(1)
    
    # Execute requested action
    if action == 'backup':
        # Only print header if we'll actually process files
        existing_tables = [t for t in tables if (Path(project_root) / t).exists()]
        if existing_tables:
            print(f"Backing up {len(existing_tables)} table(s)...")
        backup_tables(project_root, tables)
        
    elif action == 'rename_min':
        # Only print header if we'll actually process files
        existing_tables = [t for t in tables if (Path(project_root) / t).exists()]
        if existing_tables:
            print(f"Renaming {len(existing_tables)} table(s) with _min suffix...")
        rename_min(project_root, tables)
        
    elif action == 'restore':
        # Only print header if we'll actually process files
        existing_backups = [t for t in tables if (Path(project_root) / f"{t}.backup").exists()]
        if existing_backups:
            print(f"Restoring {len(existing_backups)} table(s) from backup...")
        restore_tables(project_root, tables)
        
    else:
        print(f"Error: Unknown action '{action}'", file=sys.stderr)
        print("\nValid actions: backup, rename_min, restore\n", file=sys.stderr)
        show_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()
