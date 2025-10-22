#!/bin/bash

# === DEBUG ERROR HANDLING ===
set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Trap function to show which command failed
debug_trap_error() {
    local exit_code=$?
    local line_number=$1
    echo "ERROR: Command failed with exit code $exit_code on line $line_number in $0" >&2
    echo "Failed command was: $(sed -n "${line_number}p" "$0")" >&2
    exit $exit_code
}

# Enable error trapping
trap 'debug_trap_error $LINENO' ERR
# === END DEBUG ERROR HANDLING ===


# latexmk-fallback.sh - Provides latexmk interface using basic pdflatex/bibtex sequence
# 
# This script can be sourced to provide a latexmk function that works even when
# latexmk is not installed. It supports the most common latexmk options used
# in LaTeX build workflows.
#
# Usage:
#   source latexmk-fallback.sh
#   latexmk -pdf document.tex    # Works whether real latexmk exists or not



# Check if real latexmk is available
if command -v latexmk >/dev/null 2>&1; then
    # Real latexmk exists, create a wrapper that preserves all functionality
    latexmk() {
        command latexmk "$@"
    }
else
    # Real latexmk doesn't exist, provide fallback implementation
    latexmk() {
        local pdf_mode=false
        local clean_mode=false
        local quiet_mode=false
        local rc_file=""
        local files=()
        
        # Parse command line arguments
        while [[ $# -gt 0 ]]; do
            case $1 in
                -pdf)
                    pdf_mode=true
                    shift
                    ;;
                -c)
                    clean_mode=true
                    shift
                    ;;
                -quiet)
                    quiet_mode=true
                    shift
                    ;;
                -r)
                    rc_file="$2"
                    shift 2
                    ;;
                -*)
                    # Skip other options we don't handle
                    echo "latexmk-fallback: Ignoring unsupported option: $1" >&2
                    shift
                    ;;
                *)
                    files+=("$1")
                    shift
                    ;;
            esac
        done
        
        # If no files specified, check for default files in latexmkrc
        if [[ ${#files[@]} -eq 0 ]]; then
            files=($(get_default_files))
        fi
        
        if [[ "$clean_mode" == "true" ]]; then
            # Clean mode - remove auxiliary files
            latexmk_clean "${files[@]}"
        else
            # Default to PDF build mode (matches common usage)
            for file in "${files[@]}"; do
                latexmk_build_pdf "$file" "$quiet_mode"
            done
        fi
    }
    
    # Function to extract default files from latexmkrc files
    get_default_files() {
        local default_files=()
        
        # Use .latexmkrc-for-pdf explicitly
        local rc_file=".latexmkrc-for-pdf"
        
        if [[ -f "$rc_file" ]]; then
            # Extract @default_files = (...) using perl-style parsing
            local extracted=$(grep -E '^\s*@default_files\s*=' "$rc_file" | head -1)
            if [[ -n "$extracted" ]]; then
                # Extract content between parentheses
                # Handle both: @default_files = ('file1.tex', 'file2.tex'); 
                #         and: @default_files = ('file1.tex, file2.tex');
                local files_content=$(echo "$extracted" | sed -n "s/.*(\s*\(.*\)\s*).*/\1/p")
                
                # Remove outer quotes and split intelligently
                files_content=$(echo "$files_content" | sed "s/^['\"]//;s/['\"]$//")
                
                # Handle comma-separated files within quotes or separate quoted files
                if [[ "$files_content" == *,* ]]; then
                    # Split by comma and clean up each file
                    while IFS= read -r file; do
                        # Remove quotes and whitespace
                        file=$(echo "$file" | sed "s/['\"]//g" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
                        if [[ -n "$file" && -f "$file" ]]; then
                            default_files+=("$file")
                        fi
                    done <<< "$(echo "$files_content" | tr ',' '\n')"
                else
                    # Single file, just clean it up
                    local file=$(echo "$files_content" | sed "s/['\"]//g" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
                    if [[ -n "$file" && -f "$file" ]]; then
                        default_files+=("$file")
                    fi
                fi
            fi
        else
            echo "Note: .latexmkrc-for-pdf not found, will use all .tex files in current directory" >&2
        fi
        
        # If no default files found, fall back to all .tex files
        if [[ ${#default_files[@]} -eq 0 ]]; then
            default_files=($(find . -maxdepth 1 -name "*.tex" -type f | grep -v '/\.' | sort))
        fi
        
        printf "%s\n" "${default_files[@]}"
    }
    
    # Clean function - removes auxiliary files
    latexmk_clean() {
        local files=("$@")
        
        if [[ ${#files[@]} -eq 0 ]]; then
            # Clean all auxiliary files in current directory
            find . -maxdepth 1 \( \
                -name '*.aux' -o \
                -name '*.log' -o \
                -name '*.out' -o \
                -name '*.toc' -o \
                -name '*.bbl' -o \
                -name '*.blg' -o \
                -name '*.fdb_latexmk' -o \
                -name '*.fls' -o \
                -name '*.nav' -o \
                -name '*.snm' -o \
                -name '*.vrb' \
            \) -delete 2>/dev/null || true
            
            # Remove auto directories
            find . -maxdepth 3 -name 'auto' -type d -exec rm -rf {} \; 2>/dev/null || true
        else
            # Clean specific files
            for file in "${files[@]}"; do
                local base=$(basename "$file" .tex)
                rm -f "$base".{aux,log,out,toc,bbl,blg,fdb_latexmk,fls,nav,snm,vrb} 2>/dev/null || true
            done
        fi
    }
    
    # Build function - implements the pdflatex/bibtex/pdflatex/pdflatex sequence
    latexmk_build_pdf() {
        local file="$1"
        local quiet="$2"
        
        if [[ ! -f "$file" ]]; then
            echo "latexmk-fallback: File not found: $file" >&2
            return 1
        fi
        
        local base=$(basename "$file" .tex)
        # Use LATEX_INTERACTION environment variable if set, otherwise default to nonstopmode
        local interaction_mode="${LATEX_INTERACTION:-nonstopmode}"
        local pdflatex_opts="-interaction=$interaction_mode"
        local output_redirect=""
        
        if [[ "$quiet" == "true" ]]; then
            output_redirect=">/dev/null 2>&1"
        fi
        
        echo "latexmk-fallback: Building $file using pdflatex/bibtex sequence..."
        
        # Pass 1: Generate initial .aux files
        if [[ "$quiet" == "true" ]]; then
            pdflatex "$pdflatex_opts" "$file" >/dev/null 2>&1
        else
            echo "Pass 1: Generating .aux files"
            pdflatex "$pdflatex_opts" "$file"
        fi
        
        if [[ $? -ne 0 ]]; then
            echo "latexmk-fallback: pdflatex pass 1 failed for $file" >&2
            return 1
        fi
        
        # Process bibliography if .aux file exists
        if [[ -f "$base.aux" ]]; then
            if [[ "$quiet" == "true" ]]; then
                bibtex "$base.aux" >/dev/null 2>&1 || true
            else
                echo "Processing bibliography"
                bibtex "$base.aux" 2>/dev/null || true
            fi
        fi
        
        # Process any auxiliary .tex files (like appendices)
        local aux_files=($(find . -maxdepth 1 -name "$base-*.tex" -type f 2>/dev/null))
        if [[ ${#aux_files[@]} -gt 0 ]]; then
            for aux_file in "${aux_files[@]}"; do
                if [[ "$quiet" == "true" ]]; then
                    pdflatex "$pdflatex_opts" "$aux_file" >/dev/null 2>&1 || true
                else
                    echo "Processing auxiliary file: $aux_file"
                    pdflatex "$pdflatex_opts" "$aux_file" >/dev/null 2>&1 || true
                fi
            done
        fi
        
        # Pass 2: Resolve citations
        if [[ "$quiet" == "true" ]]; then
            pdflatex "$pdflatex_opts" "$file" >/dev/null 2>&1
        else
            echo "Pass 2: Resolving citations"
            pdflatex "$pdflatex_opts" "$file"
        fi
        
        if [[ $? -ne 0 ]]; then
            echo "latexmk-fallback: pdflatex pass 2 failed for $file" >&2
            return 1
        fi
        
        # Pass 3: Final cross-reference resolution
        if [[ "$quiet" == "true" ]]; then
            pdflatex "$pdflatex_opts" "$file" >/dev/null 2>&1
        else
            echo "Pass 3: Final resolution"
            pdflatex "$pdflatex_opts" "$file"
        fi
        
        if [[ $? -ne 0 ]]; then
            echo "latexmk-fallback: pdflatex pass 3 failed for $file" >&2
            return 1
        fi
        
        if [[ "$quiet" != "true" ]]; then
            echo "latexmk-fallback: Successfully built $base.pdf"
        fi
        
        return 0
    }
    
    echo "latexmk-fallback: Using fallback implementation (real latexmk not found)" >&2
fi

# Export the function so it's available in the current shell
export -f latexmk 2>/dev/null || true 