#!/bin/bash
#
# latexmk-clean-preserve-bbl.sh
#
# PURPOSE: Wrapper for 'latexmk -c' that preserves .bbl files
# 
# USAGE: latexmk-clean-preserve-bbl.sh [latexmk-args]
#
# The .bbl (compiled bibliography) file is required for QE submission
# where .bib source may be gitignored. Standard 'latexmk -c' deletes
# .bbl files, which breaks bibliography in subsequent builds.
#
# This wrapper:
#   1. Backs up all .bbl files
#   2. Runs latexmk -c (or -C) with provided arguments
#   3. Restores .bbl files
#

set -e

# Backup all .bbl files in current directory
declare -a BBL_BACKUPS=()
for bbl in *.bbl; do
    if [[ -f "$bbl" ]]; then
        backup="${bbl}.PRESERVE_BBL"
        cp "$bbl" "$backup"
        BBL_BACKUPS+=("$backup:$bbl")
    fi
done

# Run latexmk with all provided arguments
latexmk "$@"
LATEXMK_EXIT=$?

# Restore all .bbl files
for pair in "${BBL_BACKUPS[@]}"; do
    backup="${pair%%:*}"
    original="${pair##*:}"
    if [[ -f "$backup" ]]; then
        mv "$backup" "$original"
    fi
done

exit $LATEXMK_EXIT

