#!/bin/bash
# Consolidated Standalone Files Compilation Script
# 
# This script compiles .tex files in specific directories (Figures/, Tables/, Subfiles/)
# based on command-line arguments. It combines functionality from both previous scripts.
#
# Usage: ./reproduce-standalone-files.sh [OPTIONS] [TARGETS]
# Options:
#   --figures       Compile all .tex files in Figures/ directory
#   --tables        Compile all .tex files in Tables/ directory  
#   --subfiles      Compile all .tex files in Subfiles/ directory
#   --all           Compile all standalone files (equivalent to --figures --tables --subfiles)
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

# Directory compilation flags
COMPILE_FIGURES=false
COMPILE_TABLES=false
COMPILE_SUBFILES=false

# Colors for output formatting
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color
readonly BOLD='\033[1m'

# Function to show help
show_help() {
    cat << 'HELP'
Usage: ./reproduce-standalone-files.sh [OPTIONS] [TARGETS]

Compile .tex files in specific directories as standalone documents.

TARGETS:
  --figures       Compile all .tex files in Figures/ directory
  --tables        Compile all .tex files in Tables/ directory
  --subfiles      Compile all .tex files in Subfiles/ directory
  --all           Compile all standalone files (equivalent to --figures --tables --subfiles)

OPTIONS:
  --quiet         Suppress routine output, show only errors and summary
  --verbose       Show detailed compilation output
  --continue      Continue compilation even if individual files fail  
  --clean-first   Clean auxiliary files before compilation
  --help, -h      Show this help message

EXAMPLES:
  ./reproduce-standalone-files.sh --figures                    # Compile only figures
  ./reproduce-standalone-files.sh --tables --subfiles         # Compile tables and subfiles
  ./reproduce-standalone-files.sh --all                       # Compile everything
  ./reproduce-standalone-files.sh --all --verbose             # Compile everything with verbose output
  ./reproduce-standalone-files.sh --figures --clean-first     # Clean then compile figures
  ./reproduce-standalone-files.sh --continue --all            # Don't stop on first error

RUN FROM ANYWHERE:
  # From project root directory:
  ./reproduce/reproduce-standalone-files.sh --all
  
  # From reproduce/ directory:
  ./reproduce-standalone-files.sh --all

DIRECTORY STRUCTURE:
  Figures/        Figure files and plots
  Tables/         Table files and data presentations
  Subfiles/       Document sections and appendices

Each file is compiled as a standalone document with full bibliography and cross-references.
HELP
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --figures)
            COMPILE_FIGURES=true
            shift
            ;;
        --tables)
            COMPILE_TABLES=true
            shift
            ;;
        --subfiles)
            COMPILE_SUBFILES=true
            shift
            ;;
        --all)
            COMPILE_FIGURES=true
            COMPILE_TABLES=true
            COMPILE_SUBFILES=true
            shift
            ;;
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
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if any compilation targets were specified
if [[ "$COMPILE_FIGURES" == "false" && "$COMPILE_TABLES" == "false" && "$COMPILE_SUBFILES" == "false" ]]; then
    echo -e "${RED}ERROR: No compilation targets specified${NC}"
    echo ""
    echo "You must specify at least one of: --figures, --tables, --subfiles, or --all"
    echo "Use --help for more information"
    exit 1
fi

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

# Function to detect and navigate to the correct working directory
setup_working_directory() {
    local current_dir
    current_dir=$(basename "$(pwd)")
    
    # If we're in the reproduce/ directory, change to parent
    if [[ "$current_dir" == "reproduce" ]]; then
        log_info "Script run from reproduce/ directory, changing to project root..."
        cd ..
        if [[ ! -d "Figures" && ! -d "Tables" && ! -d "Subfiles" ]]; then
            log_error "Cannot find target directories (Figures/, Tables/, Subfiles/) from $(pwd)"
            echo ""
            echo "This script should be run from either:"
            echo "  • Project root directory (where Figures/, Tables/, Subfiles/ are located)"
            echo "  • reproduce/ subdirectory"
            echo ""
            echo "Current directory structure:"
            find . -maxdepth 1 -type f -exec ls -la {} \; | head -10
            exit 1
        fi
        log_info "Successfully changed to project root: $(pwd)"
    # If we're already in project root, verify target directories exist
    elif [[ -d "Figures" || -d "Tables" || -d "Subfiles" ]]; then
        log_info "Script run from project root directory: $(pwd)"
    else
        # Try to detect if we're in some other subdirectory of the project
        if [[ -d "../Figures" || -d "../Tables" || -d "../Subfiles" ]]; then
            log_info "Target directories found one level up, changing to parent directory..."
            cd ..
            log_info "Changed to project root: $(pwd)"
        else
            log_error "Cannot locate target directories (Figures/, Tables/, Subfiles/)"
            echo ""
            echo "This script should be run from either:"
            echo "  • Project root directory (where Figures/, Tables/, Subfiles/ are located)"  
            echo "  • reproduce/ subdirectory"
            echo ""
            echo "Current directory: $(pwd)"
            echo "Directory contents:"
            find . -maxdepth 1 -type f -exec ls -la {} \; | head -10
            exit 1
        fi
    fi
    
    # Final verification - check that at least one target directory exists
    local found_dirs=0
    [[ -d "Figures" ]] && ((found_dirs++)) && log_info "Found Figures/ directory"
    [[ -d "Tables" ]] && ((found_dirs++)) && log_info "Found Tables/ directory"  
    [[ -d "Subfiles" ]] && ((found_dirs++)) && log_info "Found Subfiles/ directory"
    
    if [[ $found_dirs -eq 0 ]]; then
        log_error "No target directories (Figures/, Tables/, Subfiles/) found in $(pwd)"
        exit 1
    fi
    
    echo ""
}

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
        log_info "Cleaned auxiliary files for $base_name.tex"
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
        
        # Show PDF info if available and not in quiet mode
        if [[ "$QUIET" != "true" && -f "$base_name.pdf" ]]; then
            local pdf_size
            pdf_size=$(du -h "$base_name.pdf" 2>/dev/null | cut -f1 || echo "unknown")
            log_info "Generated $base_name.pdf ($pdf_size)"
        fi
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
    
    # Find .tex files in the directory
    local tex_files_array=()
    while IFS= read -r -d '' file; do
        tex_files_array+=("$file")
    done < <(find "$dir" -maxdepth 1 -name "*.tex" -not -name ".*" -type f -print0 2>/dev/null | sort -z)
    
    if [[ ${#tex_files_array[@]} -eq 0 ]]; then
        log_warning "No .tex files found in $dir/"
        return 0
    fi
    
    log_info "Found ${#tex_files_array[@]} .tex files in $dir/ (excluding dotfiles)"
    
    for tex_file in "${tex_files_array[@]}"; do
        compile_standalone_file "$tex_file"
    done
}

# Setup working directory - ensure we're in the correct location
setup_working_directory

# Main execution
echo -e "${BLUE}${BOLD}=== Consolidated Standalone Files Compilation ===${NC}"

# Show what will be compiled
compilation_targets=()
[[ "$COMPILE_FIGURES" == "true" ]] && compilation_targets+=("Figures")
[[ "$COMPILE_TABLES" == "true" ]] && compilation_targets+=("Tables") 
[[ "$COMPILE_SUBFILES" == "true" ]] && compilation_targets+=("Subfiles")

echo -e "${BLUE}Compiling .tex files in: ${BOLD}${compilation_targets[*]}${NC}"
echo ""

# Record start time
START_TIME=$(date +%s)

# Compile files in requested directories
if [[ "$COMPILE_FIGURES" == "true" ]]; then
    compile_directory "Figures" "figure files"
fi

if [[ "$COMPILE_TABLES" == "true" ]]; then
    compile_directory "Tables" "table files"
fi

if [[ "$COMPILE_SUBFILES" == "true" ]]; then
    compile_directory "Subfiles" "document sections"
fi

# Calculate elapsed time
END_TIME=$(date +%s)
ELAPSED_TIME=$((END_TIME - START_TIME))

# Show summary
echo ""
echo -e "${BLUE}${BOLD}=== Compilation Summary ===${NC}"
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
    echo -e "${GREEN}${BOLD}All targeted standalone files compiled successfully!${NC}"
    exit 0
fi 