#!/bin/bash
#
# ==================================================================
# TOOL MIGRATION PROVENANCE HEADER  
# ==================================================================
# 
# 📍 ORIGINAL SOURCE: 
#    File: svg-clean.sh
#    Source Commit: 09c4224
#    Migration Date: 2025-08-24
#
# 🔄 UPDATE INSTRUCTIONS: See scripts/tools/svg-clean.md
#
# 🎯 MIGRATION NOTES:
#    - Internal Tools/ references updated to scripts/tools/ 
#    - Part of project independence initiative
#
# ==================================================================

if [[ "${DEBUG:-}" == "1" || "${DEBUG:-}" == "true" ]]; then
    echo "=== DEBUG MODE ENABLED in scripts/tools/svg-clean.sh ==="
    set -x
    set -v
fi

#===============================================================================
# svg-clean.sh - SVG Cleanup Utility for HAFiscal
#===============================================================================
# 
# PURPOSE:
#   Removes junk text that gets added to SVG files due to bugs in dvisvgm 
#   and/or ghostscript during LaTeX to HTML conversion process.
#
# USAGE:
#   svg-clean.sh <directory>
#   svg-clean.sh /path/to/svg/files
#   svg-clean.sh .                    # Clean current directory
#   svg-clean.sh --help              # Show help
#   svg-clean.sh --rollback <backup_dir>  # Restore from backup
#
# WHAT IT CLEANS:
#   - Removes lines containing 'PDF interpreter' 
#   - Removes lines containing 'dNEWDPF'
#   - These are artifacts from ghostscript/dvisvgm conversion bugs
#
# SAFETY FEATURES:
#   - Creates timestamped backups before modification
#   - Validates all input files exist and are readable
#   - Comprehensive error handling and logging
#   - Rollback capability to restore original files
#
# DEPENDENCIES:
#   - sed (standard on macOS/Linux)
#   - Standard POSIX shell utilities
#
# AUTHOR:
#   HAFiscal build system
#   Enhanced: 2025-06-09
#
#===============================================================================

# Strict error handling
set -e  # Exit on any error
set -u  # Exit on undefined variables

# Global configuration
readonly SCRIPT_NAME="${0##*/}"
readonly TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
readonly BACKUP_BASE_DIR="/tmp/svg-clean-backups"
readonly BACKUP_DIR="${BACKUP_BASE_DIR}/${TIMESTAMP}"

# Logging configuration
readonly LOG_PREFIX="[$(date '+%H:%M:%S')]"
PROCESSED_COUNT=0
CLEANED_COUNT=0

#===============================================================================
# Utility Functions
#===============================================================================

log_info() {
    echo "${LOG_PREFIX} ℹ️  $*"
}

log_success() {
    echo "${LOG_PREFIX} ✅ $*"
}

log_warning() {
    echo "${LOG_PREFIX} ⚠️  $*" >&2
}

log_error() {
    echo "${LOG_PREFIX} ❌ $*" >&2
}

show_help() {
    cat << 'EOF'
SVG Cleanup Utility for HAFiscal

USAGE:
    svg-clean.sh <directory>                 Clean SVG files in directory
    svg-clean.sh --help                      Show this help
    svg-clean.sh --rollback <backup_dir>     Restore from backup

EXAMPLES:
    svg-clean.sh .                           Clean current directory
    svg-clean.sh /path/to/svg/files          Clean specific directory
    svg-clean.sh --rollback /tmp/svg-clean-backups/20250609_143022

DESCRIPTION:
    Removes artifact lines from SVG files that are created due to bugs in
    dvisvgm and/or ghostscript during LaTeX to HTML conversion:
    
    - Lines containing 'PDF interpreter'
    - Lines containing 'dNEWDPF'

SAFETY:
    - Creates timestamped backups in /tmp/svg-clean-backups/
    - Validates all files before processing
    - Provides rollback capability
    - Comprehensive error handling

EXIT CODES:
    0  Success
    1  Invalid arguments or general error
    2  Directory not found or not accessible
    3  No SVG files found
    4  Backup operation failed
EOF
}

create_backup() {
    local source_dir="$1"
    local file="$2"
    
    # Create backup directory structure
    local backup_file_dir="${BACKUP_DIR}${source_dir}"
    if [ ! -d "$backup_file_dir" ]; then
        if ! mkdir -p "$backup_file_dir"; then
            log_error "Failed to create backup directory: $backup_file_dir"
            return 1
fi
    fi
    
    # Copy file to backup
    local backup_file="${backup_file_dir}/${file}"
    if ! cp "${source_dir}/${file}" "$backup_file"; then
        log_error "Failed to backup file: $file"
        return 1
    fi
    
    return 0
}

clean_svg_file() {
    local file="$1"
    local source_dir="$2"
    local full_path="${source_dir}/${file}"
    local cleaned=0
    
    # Validate file
    if [ ! -f "$full_path" ]; then
        log_warning "File not found: $full_path"
        return 1
    fi
    
    if [ ! -r "$full_path" ]; then
        log_warning "File not readable: $full_path"
        return 1
    fi
    
    if [ ! -w "$full_path" ]; then
        log_warning "File not writable: $full_path"
        return 1
    fi
    
    # Create backup
    if ! create_backup "$source_dir" "$file"; then
        log_error "Backup failed for: $file"
        return 1
    fi
    
    # Check if file contains patterns to clean
    if grep -q 'PDF interpreter\|dNEWDPF' "$full_path"; then
        log_info "Cleaning: $file"
        
        # Clean the file (using portable sed syntax)
        if sed -i.tmp '/PDF interpreter/d' "$full_path" && \
           sed -i.tmp '/dNEWDPF/d' "$full_path"; then
            # Remove temporary files created by sed
            rm -f "${full_path}.tmp"
            cleaned=1
            CLEANED_COUNT=$((CLEANED_COUNT + 1))
            log_success "Cleaned: $file"
        else
            log_error "Failed to clean: $file"
            return 1
fi
    else
        log_info "No cleaning needed: $file"
    fi
    
    PROCESSED_COUNT=$((PROCESSED_COUNT + 1))
    return 0
}

rollback_from_backup() {
    local backup_dir="$1"
    
    if [ ! -d "$backup_dir" ]; then
        log_error "Backup directory not found: $backup_dir"
        return 1
    fi
    
    log_info "Rolling back from backup: $backup_dir"
    
    # Find all files in backup and restore them
    local restored_count=0
    while IFS= read -r backup_file; do
        if [ -f "$backup_file" ]; then
            # Calculate original path
            local relative_path="${backup_file#$backup_dir}"
            local original_file="${relative_path#/}"
            
            if [ -f "$original_file" ]; then
                if cp "$backup_file" "$original_file"; then
                    log_success "Restored: $original_file"
                    restored_count=$((restored_count + 1))
                else
                    log_error "Failed to restore: $original_file"
                fi
            else
                log_warning "Original file not found: $original_file"
            fi
        fi
    done < <(find "$backup_dir" -type f -name "*.svg")
    
    log_success "Rollback completed: $restored_count files restored"
    return 0
}

#===============================================================================
# Main Processing Function
#===============================================================================

process_directory() {
    local target_dir="$1"
    
    # Resolve to absolute path and validate
    if [ ! -d "$target_dir" ]; then
        log_error "Directory does not exist: $target_dir"
        exit 2
    fi
    
    if [ ! -r "$target_dir" ]; then
        log_error "Directory not readable: $target_dir"
        exit 2
    fi
    
    # Convert to absolute path for consistent backup handling
    local abs_dir
    abs_dir=$(cd "$target_dir" && pwd)
    
    log_info "Cleaning SVG files in: $abs_dir"
    log_info "Backup directory: $BACKUP_DIR"
    
    # Change to target directory
    cd "$abs_dir"
    
    # Find SVG files (bash 3.2 compatible)
    local svg_count=0
    local has_svg_files=0
    
    # Check if any SVG files exist
    for file in *.svg; do
        if [ -f "$file" ]; then
            has_svg_files=1
            svg_count=$((svg_count + 1))
        fi
    done
    
    if [ $has_svg_files -eq 0 ]; then
        log_warning "No SVG files found in: $abs_dir"
        exit 3
    fi
    
    log_info "Found $svg_count SVG files to process"
    
    # Process each SVG file (bash 3.2 compatible)
    local failed_count=0
    for file in *.svg; do
        if [ -f "$file" ]; then
            if ! clean_svg_file "$file" "$abs_dir"; then
                failed_count=$((failed_count + 1))
            fi
        fi
    done
    
    # Summary
    echo
    log_success "Processing completed:"
    log_success "  Files processed: $PROCESSED_COUNT"
    log_success "  Files cleaned: $CLEANED_COUNT"
    log_success "  Files skipped: $((PROCESSED_COUNT - CLEANED_COUNT))"
    if [ $failed_count -gt 0 ]; then
        log_warning "  Files failed: $failed_count"
    fi
    log_success "  Backup location: $BACKUP_DIR"
    echo
    
    return 0
}

#===============================================================================
# Main Script Logic
#===============================================================================

main() {
    # Parse command line arguments
    case ${1:-} in
        --help|-h)
            show_help
            exit 0
            ;;
        --rollback)
            if [ $# -ne 2 ]; then
                log_error "Usage: $SCRIPT_NAME --rollback <backup_directory>"
                exit 1
            fi
            rollback_from_backup "$2"
            exit $?
            ;;
        "")
            log_error "Usage: $SCRIPT_NAME <directory>"
            log_error "       $SCRIPT_NAME --help"
            exit 1
            ;;
        -*)
            log_error "Unknown option: $1"
            log_error "Use --help for usage information"
            exit 1
            ;;
        *)
            if [ $# -ne 1 ]; then
                log_error "Usage: $SCRIPT_NAME <directory>"
                exit 1
            fi
            process_directory "$1"
            ;;
    esac
}

# Execute main function with all arguments
main "$@"
