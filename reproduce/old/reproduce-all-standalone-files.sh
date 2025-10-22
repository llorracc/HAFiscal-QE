#!/bin/bash
# Comprehensive Standalone Files Compilation Script
# 
# This script compiles all .tex files in Figures/, Tables/, and Subfiles/ directories
# as standalone documents. Each file is compiled independently with proper error handling.
#
# Usage: ./reproduce-all-standalone-files.sh [options]
# Options:
#   --quiet         Suppress routine output, show only errors and summary
#   --verbose       Show detailed compilation output  
#   --continue      Continue compilation even if individual files fail
#   --clean-first   Clean auxiliary files before compilation
#   --help, -h      Show this help message

set -e  # Exit on error (can be overridden with --continue)

# Default settings
VERBOSE=false
QUIET=false  
CONTINUE_ON_ERROR=false
CLEAN_FIRST=false
SUCCESSFUL_COMPILATIONS=0
FAILED_COMPILATIONS=0
FAILED_FILES=()

# Colors for output formatting
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Function to show help
show_help() {
    cat << HELP
Usage: $0 [options]

Compile all .tex files in Figures/, Tables/, and Subfiles/ directories as standalone documents.

Options:
  --quiet         Suppress routine output, show only errors and summary
  --verbose       Show detailed compilation output
  --continue      Continue compilation even if individual files fail  
  --clean-first   Clean auxiliary files before compilation
  --help, -h      Show this help message

Examples:
  $0                    # Standard compilation with normal output
  $0 --quiet            # Quiet mode - minimal output
  $0 --verbose          # Verbose mode - show all latexmk output
  $0 --continue         # Don't stop on first error
  $0 --clean-first      # Clean auxiliary files first

The script will compile files in this order:
  1. Figures/*.tex     (figures and plots)
  2. Tables/*.tex      (tables and data)  
  3. Subfiles/*.tex    (document sections)

Each file is compiled as a standalone document with full bibliography and cross-references.
HELP
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose)
            VERBOSE=true
            shift
            ;;
        --quiet)
            QUIET=true
            shift
            ;;
        --continue)
            CONTINUE_ON_ERROR=true
            set +e  # Disable exit on error
            shift
            ;;
        --clean-first)
            CLEAN_FIRST=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if latexmk is available
if ! command -v latexmk >/dev/null 2>&1; then
    echo -e "${RED}ERROR: latexmk is not installed or not in PATH${NC}"
    echo ""
    echo "latexmk is required for this script to work. Please install it:"
    echo "  - On macOS: brew install latexmk"
    echo "  - On Ubuntu/Debian: apt-get install latexmk"  
    echo "  - On other systems: install via your package manager or from CTAN"
    exit 1
fi

# Function to log messages based on verbosity settings
log_info() {
    if [[ "$QUIET" != "true" ]]; then
        echo -e "${BLUE}INFO:${NC} $*"
    fi
}

log_success() {
    if [[ "$QUIET" != "true" ]]; then
        echo -e "${GREEN}SUCCESS:${NC} $*"
    fi
}

log_error() {
    echo -e "${RED}ERROR:${NC} $*" >&2
}

log_warning() {
    if [[ "$QUIET" != "true" ]]; then
        echo -e "${YELLOW}WARNING:${NC} $*"
    fi
}

# Function to compile a single .tex file
compile_standalone_file() {
    local tex_file="$1"
    local base_name
    local dir_name
    base_name=$(basename "$tex_file" .tex)
    dir_name=$(dirname "$tex_file")
    
    log_info "Compiling $tex_file as standalone document..."
    
    # Change to the directory containing the .tex file
    pushd "$dir_name" >/dev/null
    
    local compile_success=true
    local latexmk_opts=""
    
    # Set latexmk options based on verbosity
    if [[ "$VERBOSE" == "true" ]]; then
        latexmk_opts="-interaction=nonstopmode"
    else
        latexmk_opts="-interaction=batchmode -quiet"
    fi
    
    # Clean first if requested
    if [[ "$CLEAN_FIRST" == "true" ]]; then
        latexmk -c "$base_name.tex" >/dev/null 2>&1 || true
    fi
    
    # Compile the file with timeout to prevent hanging
    local timeout_duration=120  # 2 minutes timeout per file
    if [[ "$VERBOSE" == "true" ]]; then
        timeout $timeout_duration latexmk "$latexmk_opts" "$base_name.tex" || compile_success=false
    else
        timeout $timeout_duration latexmk "$latexmk_opts" "$base_name.tex" >/dev/null 2>&1 || compile_success=false
    fi
    
    # Check if compilation timed out
    local exit_code=$?
    if [[ $exit_code -eq 124 ]]; then
        log_error "Compilation of $tex_file timed out after $timeout_duration seconds (likely BibTeX hanging)"
        compile_success=false
    fi
    
    if [[ "$compile_success" == "true" ]]; then
        log_success "Compiled $tex_file successfully"
        ((SUCCESSFUL_COMPILATIONS++))
    else
        log_error "Failed to compile $tex_file"
        FAILED_FILES+=("$tex_file")
        ((FAILED_COMPILATIONS++))
        
        # Show error details if not in quiet mode
        if [[ "$QUIET" != "true" ]] && [[ -f "$base_name.log" ]]; then
            echo -e "${YELLOW}Last few lines of $base_name.log:${NC}"
            tail -10 "$base_name.log" | grep -E "(Error|Warning|!)" || tail -5 "$base_name.log"
        fi
        
        # Clean up any hanging processes
        latexmk -c "$base_name.tex" >/dev/null 2>&1 || true
        
        if [[ "$CONTINUE_ON_ERROR" != "true" ]]; then
            popd >/dev/null
            exit 1
        fi
    fi
    
    popd >/dev/null
}

# Function to find and compile all .tex files in a directory
compile_directory() {
    local dir="$1"
    local description="$2"
    
    if [[ ! -d "$dir" ]]; then
        log_warning "Directory $dir does not exist, skipping..."
        return 0
    fi
    
    log_info "Processing $description in $dir/..."
    
    # Bash 3.2 compatible array population using command substitution
    # Note: This approach works for filenames without spaces. For space-safe approach, 
    # would need bash 4+ features like mapfile, which aren't available in macOS default bash 3.2
    local tex_files_string
    tex_files_string=$(find "$dir" -maxdepth 1 -name "*.tex" -not -name ".*" -type f 2>/dev/null | sort)
    # shellcheck disable=SC2206 # Intentional word splitting for bash 3.2 compatibility
    local tex_files=($tex_files_string)
    
    if [[ ${#tex_files[@]} -eq 0 ]]; then
        log_warning "No .tex files found in $dir/"
        return 0
    fi
    
    log_info "Found ${#tex_files[@]} .tex files in $dir/ (excluding dotfiles)"
    
    for tex_file in "${tex_files[@]}"; do
        compile_standalone_file "$tex_file"
    done
}

# Main execution
echo -e "${BLUE}=== Comprehensive Standalone Files Compilation ===${NC}"
echo -e "${BLUE}Compiling all .tex files in Figures/, Tables/, and Subfiles/ directories${NC}"
echo ""

# Record start time
START_TIME=$(date +%s)

# Compile files in each directory
compile_directory "Figures" "figure files"
compile_directory "Tables" "table files"  
compile_directory "Subfiles" "document sections"

# Calculate elapsed time
END_TIME=$(date +%s)
ELAPSED_TIME=$((END_TIME - START_TIME))

# Show summary
echo ""
echo -e "${BLUE}=== Compilation Summary ===${NC}"
echo -e "${GREEN}Successful compilations: $SUCCESSFUL_COMPILATIONS${NC}"
if [[ $FAILED_COMPILATIONS -gt 0 ]]; then
    echo -e "${RED}Failed compilations: $FAILED_COMPILATIONS${NC}"
    echo -e "${RED}Failed files:${NC}"
    for failed_file in "${FAILED_FILES[@]}"; do
        echo -e "  ${RED}- $failed_file${NC}"
    done
fi
echo "Total time: ${ELAPSED_TIME} seconds"

# Exit with appropriate code
if [[ $FAILED_COMPILATIONS -gt 0 ]]; then
    echo -e "${YELLOW}Some compilations failed. Check the output above for details.${NC}"
    exit 1
else
    echo -e "${GREEN}All standalone files compiled successfully!${NC}"
    exit 0
fi
