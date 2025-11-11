#!/usr/bin/env bash
# sync-from-relpath.sh - Synchronize materialized image files from .relpath symlinks
#
# This script ensures that materialized copies of images in the images/ directory
# are kept up-to-date with their source files, which are referenced by .relpath symlinks.
#
# For each *.relpath symlink:
#   - Follows the symlink to find the source file
#   - Compares source with the materialized copy (if it exists)
#   - Updates the materialized copy if different or missing
#
# Usage: ./sync-from-relpath.sh [--verbose] [--dry-run]

set -euo pipefail

# Get the directory where this script lives (should be images/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES_DIR="$SCRIPT_DIR"

# Options
VERBOSE=false
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --dry-run|-n)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--verbose] [--dry-run]"
            echo ""
            echo "Synchronize materialized image files from .relpath symlinks"
            echo ""
            echo "Options:"
            echo "  --verbose, -v    Show detailed progress"
            echo "  --dry-run, -n    Show what would be done without making changes"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Counters
updated=0
skipped=0
missing=0
created=0
errors=0

echo "=== Syncing images from .relpath symlinks ==="
echo "Images directory: $IMAGES_DIR"
echo ""

# Find all .relpath files
cd "$IMAGES_DIR"
relpath_files=($(find . -maxdepth 1 -name "*.relpath" -type l))

if [[ ${#relpath_files[@]} -eq 0 ]]; then
    echo "No .relpath symlinks found in $IMAGES_DIR"
    exit 0
fi

echo "Found ${#relpath_files[@]} .relpath symlinks"
echo ""

for relpath_link in "${relpath_files[@]}"; do
    # Remove leading ./
    relpath_link="${relpath_link#./}"
    
    # Extract basename by removing .relpath extension
    basename="${relpath_link%.relpath}"
    
    # Check if this is a symlink
    if [[ ! -L "$relpath_link" ]]; then
        echo "⚠️  WARNING: $relpath_link is not a symlink, skipping"
        ((errors++)) || true
        continue
    fi
    
    # Get the target path
    target_path=$(readlink "$relpath_link")
    
    # Resolve to absolute path
    if [[ "$target_path" = /* ]]; then
        # Already absolute
        resolved_target="$target_path"
    else
        # Relative path - resolve from images/ directory
        resolved_target="$IMAGES_DIR/$target_path"
    fi
    
    # Check if target exists
    if [[ ! -f "$resolved_target" ]]; then
        echo "❌ MISSING: $relpath_link → $target_path (target not found)"
        ((missing++)) || true
        continue
    fi
    
    # Check if materialized copy exists
    if [[ ! -f "$basename" ]]; then
        echo "📄 CREATE: $basename (from $target_path)"
        if [[ "$DRY_RUN" == false ]]; then
            cp "$resolved_target" "$basename"
        fi
        ((created++)) || true
    else
        # Compare binary content
        if cmp -s "$resolved_target" "$basename"; then
            if [[ "$VERBOSE" == true ]]; then
                echo "✓ UNCHANGED: $basename (already up-to-date)"
            fi
            ((skipped++)) || true
        else
            echo "🔄 UPDATE: $basename (source changed)"
            if [[ "$DRY_RUN" == false ]]; then
                cp "$resolved_target" "$basename"
            fi
            ((updated++)) || true
        fi
    fi
done

echo ""
echo "=== Sync Summary ==="
echo "  Created:   $created"
echo "  Updated:   $updated"
echo "  Unchanged: $skipped"
echo "  Missing:   $missing"
echo "  Errors:    $errors"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo "(Dry run - no changes made)"
fi

if [[ $missing -gt 0 ]] || [[ $errors -gt 0 ]]; then
    echo "⚠️  Some issues were found. Please review the output above."
    exit 1
fi

echo "✅ Sync complete!"
exit 0
