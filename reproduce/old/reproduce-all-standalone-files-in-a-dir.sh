#!/bin/bash

# Enhanced Directory-based LaTeX Compilation Script with Error Detection and Interactive Retry
# Implements comprehensive log file analysis to detect and categorize LaTeX/BibTeX errors
# Usage: ./reproduce-all-standalone-files-in-a-dir.sh <directory>
# where <directory> is relative to the repository root and contains .tex files

set -euo pipefail

# Global arrays to store error and warning information
declare -a errors_found
declare -a error_details
declare -a warnings_found
declare -a warning_details

# Colors for better output formatting
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color
readonly BOLD='\033[1m'

# Function to analyze compilation logs for errors
analyze_compilation_logs() {
    local file="$1"
    local basename="${file%.tex}"
    
    # Clear global arrays
    errors_found=()
    error_details=()
    warnings_found=()
    warning_details=()
    
    echo "🔍 Analyzing log files for $file..."
    
    # Check .log file for LaTeX errors
    if [[ -f "${basename}.log" ]]; then
        # Fatal LaTeX errors
        if grep -q "! LaTeX Error\|! Undefined control sequence\|! Emergency stop\|! Missing" "${basename}.log"; then
            errors_found+=("LATEX_FATAL")
            local fatal_errors=$(grep -A2 "! LaTeX Error\|! Undefined control sequence\|! Emergency stop\|! Missing" "${basename}.log" | head -10)
            error_details+=("$fatal_errors")
        fi
        
        # Multiply defined citations/labels (WARNING, not error)
        if grep -q "multiply defined\|Multiply defined" "${basename}.log"; then
            warnings_found+=("MULTIPLY_DEFINED")
            local multiply_warnings=$(grep "multiply defined\|Multiply defined" "${basename}.log")
            warning_details+=("$multiply_warnings")
        fi
        
        # Citation warnings (undefined references)
        if grep -q "Citation.*undefined\|LaTeX Warning: There were undefined references\|LaTeX Warning: Citation" "${basename}.log"; then
            errors_found+=("UNDEFINED_CITATIONS")
            local citation_errors=$(grep "Citation.*undefined\|LaTeX Warning: Citation" "${basename}.log" | head -5)
            error_details+=("$citation_errors")
        fi
        
        # Missing references
        if grep -q "LaTeX Warning: There were undefined references\|LaTeX Warning: Reference.*undefined" "${basename}.log"; then
            errors_found+=("UNDEFINED_REFERENCES")
            local ref_errors=$(grep "LaTeX Warning: Reference.*undefined" "${basename}.log" | head -3)
            error_details+=("$ref_errors")
        fi
        
        # Package errors (be more specific to avoid false positives)
        if grep -q "! Package.*Error\|Error: Package" "${basename}.log"; then
            errors_found+=("PACKAGE_ERROR")
            local package_errors=$(grep -A2 "! Package.*Error\|Error: Package" "${basename}.log" | head -5)
            error_details+=("$package_errors")
        fi
    fi
    
    # Check .blg file for BibTeX errors
    if [[ -f "${basename}.blg" ]]; then
        if grep -q "error message\|Illegal.*command\|another.*bibdata\|I couldn't open\|I found no" "${basename}.blg"; then
            errors_found+=("BIBTEX_ERROR")
            local bibtex_errors=$(grep -B1 -A2 "error message\|Illegal.*command\|another.*bibdata\|I couldn't open\|I found no" "${basename}.blg")
            error_details+=("$bibtex_errors")
        fi
        
        # Check for warnings that might indicate problems (WARNING, not error)
        if grep -q "Warning--" "${basename}.blg"; then
            local warning_count=$(grep -c "Warning--" "${basename}.blg" 2>/dev/null || echo "0")
            if [[ $warning_count -gt 0 ]]; then
                warnings_found+=("BIBTEX_WARNINGS")
                local bibtex_warnings=$(grep "Warning--" "${basename}.blg" | head -3)
                warning_details+=("Found $warning_count BibTeX warnings:\n$bibtex_warnings")
            fi
        fi
    fi
    
    # Check .aux file for structural issues
    if [[ -f "${basename}.aux" ]]; then
        # Check for duplicate \bibdata commands
        local bibdata_count=$(grep -c "\\\\bibdata" "${basename}.aux" 2>/dev/null || echo "0")
        if [[ $bibdata_count -gt 1 ]]; then
            errors_found+=("DUPLICATE_BIBDATA")
            local bibdata_lines=$(grep -n "\\\\bibdata" "${basename}.aux")
            error_details+=("Found $bibdata_count \\bibdata commands in ${basename}.aux:\n$bibdata_lines")
        fi
        
        # Check for missing \bibdata (if citations exist but no bibliography)
        if [[ $bibdata_count -eq 0 ]] && grep -q "\\\\citation" "${basename}.aux"; then
            errors_found+=("MISSING_BIBDATA")
            error_details+=("Citations found but no \\bibdata command in ${basename}.aux")
        fi
    fi
    
    # Return the number of errors found
    return ${#errors_found[@]}
}

# Function to display warnings (non-blocking)
display_warnings() {
    local file="$1"
    
    if [[ ${#warnings_found[@]} -eq 0 ]]; then
        return 0
    fi
    
    echo -e "\n${YELLOW}${BOLD}⚠️  Compilation warnings found in $file (non-fatal):${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    for i in "${!warnings_found[@]}"; do
        case "${warnings_found[$i]}" in
            "MULTIPLY_DEFINED")
                echo -e "\n${YELLOW}⚠️  Multiply Defined Citations:${NC}"
                echo -e "${BLUE}Same citation appears multiple times. This is usually harmless.${NC}"
                ;;
            "BIBTEX_WARNINGS")
                echo -e "\n${YELLOW}📚 BibTeX Warnings:${NC}"
                echo -e "${BLUE}Non-fatal bibliography warnings. Document will compile correctly.${NC}"
                ;;
        esac
        
        echo -e "\n${BOLD}Details:${NC}"
        echo -e "${warning_details[$i]}"
        echo -e "${BLUE}────────────────────────────────────────────────────────────────────────────${NC}"
    done
}

# Function to display errors with nice formatting and context
display_errors_with_context() {
    local file="$1"
    
    echo -e "\n${RED}${BOLD}❌ Compilation errors found in $file:${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    for i in "${!errors_found[@]}"; do
        case "${errors_found[$i]}" in
            "LATEX_FATAL")
                echo -e "\n${RED}🚨 FATAL LaTeX Error:${NC}"
                echo -e "${YELLOW}This needs immediate attention - compilation cannot proceed.${NC}"
                ;;
            "UNDEFINED_CITATIONS")
                echo -e "\n${YELLOW}📚 Undefined Citations:${NC}"
                echo -e "${YELLOW}Citations not found in bibliography. Check .bib files or citation keys.${NC}"
                ;;
            "UNDEFINED_REFERENCES")
                echo -e "\n${YELLOW}🔗 Undefined References:${NC}"
                echo -e "${YELLOW}\\ref or \\eqref pointing to non-existent labels.${NC}"
                ;;
            "BIBTEX_ERROR")
                echo -e "\n${RED}📖 BibTeX Error:${NC}"
                echo -e "${YELLOW}Problem with bibliography processing. Check .bib file syntax.${NC}"
                ;;
            "DUPLICATE_BIBDATA")
                echo -e "\n${RED}🔄 Duplicate Bibliography Data:${NC}"
                echo -e "${YELLOW}Multiple \\bibdata commands in .aux file. Check for duplicate \\bibliography commands.${NC}"
                ;;
            "MISSING_BIBDATA")
                echo -e "\n${RED}📖 Missing Bibliography Data:${NC}"
                echo -e "${YELLOW}Citations exist but no \\bibliography command found.${NC}"
                ;;
            "PACKAGE_ERROR")
                echo -e "\n${RED}📦 Package Error:${NC}"
                echo -e "${YELLOW}LaTeX package error. Check package installation and usage.${NC}"
                ;;
        esac
        
        echo -e "\n${BOLD}Details:${NC}"
        echo -e "${error_details[$i]}"
        echo -e "${BLUE}────────────────────────────────────────────────────────────────────────────${NC}"
    done
    
    echo -e "\n${BOLD}💡 Suggestions:${NC}"
    echo "• Check the full .log file for more details: less ${file%.tex}.log"
    echo "• For BibTeX issues, check: less ${file%.tex}.blg"
    echo "• For structure issues, examine: less ${file%.tex}.aux"
}

# Function to compile a file with comprehensive error checking
compile_file_with_comprehensive_checking() {
    local file="$1"
    local basename="${file%.tex}"
    
    echo -e "\n${BLUE}${BOLD}🔄 Compiling $file...${NC}"
    
    # Clean auxiliary files first
    echo "🧹 Cleaning auxiliary files..."
    latexmk -c "$file" >/dev/null 2>&1 || true
    
    # Compile with latexmk and capture output
    echo "📝 Running LaTeX compilation..."
    
    # Show the exact command being executed
    local env_vars=""
    # Check for common LaTeX environment variables
    [[ -n "${BUILD_MODE:-}" ]] && env_vars+="BUILD_MODE=$BUILD_MODE "
    [[ -n "${ONLINE_APPENDIX_HANDLING:-}" ]] && env_vars+="ONLINE_APPENDIX_HANDLING=$ONLINE_APPENDIX_HANDLING "
    [[ -n "${TEXINPUTS:-}" ]] && env_vars+="TEXINPUTS=$TEXINPUTS "
    
    if [[ -n "$env_vars" ]]; then
        echo -e "${BLUE}🌍 Environment: ${BOLD}$env_vars${NC}"
    fi
    echo ""
    echo -e "${BLUE}${BOLD}cd $(pwd)/${NC}"
    echo -e "${BLUE}${BOLD}latexmk \"$file\"${NC}"
    echo ""
    
    local compile_output
    local exit_code
    
    # Capture both stdout and stderr, but still show progress
    if compile_output=$(latexmk "$file" 2>&1); then
        exit_code=0
    else
        exit_code=$?
    fi
    
    # Show a summary of what latexmk did
    local run_count=$(echo "$compile_output" | grep -c "Run number" || echo "0")
    echo "📊 LaTeX made $run_count compilation passes"
    
    # Analyze logs regardless of exit code (sometimes warnings don't cause failure)
    analyze_compilation_logs "$file"
    local error_count=$?
    
    # Check for warnings and errors separately
    local warning_count=${#warnings_found[@]}
    
    # Determine success/failure (errors cause failure, warnings do not)
    if [[ $exit_code -eq 0 && $error_count -eq 0 ]]; then
        echo -e "${GREEN}✅ $file compiled successfully${NC}"
        
        # Show warnings if any (but don't fail)
        if [[ $warning_count -gt 0 ]]; then
            display_warnings "$file"
        fi
        
        # Show brief compilation stats
        if [[ -f "${basename}.pdf" ]]; then
            local pdf_size=$(du -h "${basename}.pdf" 2>/dev/null | cut -f1 || echo "unknown")
            echo -e "${GREEN}📄 Generated ${basename}.pdf (${pdf_size})${NC}"
        fi
        
        return 0
    else
        # Show compilation output if there were serious errors
        if [[ $exit_code -ne 0 ]]; then
            echo -e "\n${RED}${BOLD}Compilation failed with exit code: $exit_code${NC}"
        fi
        
        # Show warnings first if any
        if [[ $warning_count -gt 0 ]]; then
            display_warnings "$file"
        fi
        
        # Show errors (these require user intervention)
        if [[ $error_count -gt 0 ]]; then
            display_errors_with_context "$file"
        fi
        
        return 1
    fi
}

# Function to handle interactive retry loop
retry_until_success() {
    local file="$1"
    local attempt=1
    
    while true; do
        if [[ $attempt -gt 1 ]]; then
            echo -e "\n${BLUE}${BOLD}🔄 Attempt #$attempt for $file${NC}"
        fi
        
        if compile_file_with_comprehensive_checking "$file"; then
            echo -e "${GREEN}${BOLD}🎉 Successfully compiled $file!${NC}"
            break
        else
            echo -e "\n${YELLOW}${BOLD}🛠️  Please fix the errors in $file${NC}"
            echo -e "${BOLD}Options:${NC}"
            echo "  • Press ${BOLD}Enter${NC} to retry compilation after making changes"
            echo "  • Press ${BOLD}Ctrl+C${NC} to abort the entire process"
            echo "  • Type ${BOLD}'skip'${NC} to skip this file and continue with others"
            echo -n "Your choice: "
            
            read -r user_input
            
            if [[ "$user_input" == "skip" ]]; then
                echo -e "${YELLOW}⏭️  Skipping $file as requested${NC}"
                break
            fi
            
            echo -e "${BLUE}🔄 Retrying compilation of $file...${NC}"
            ((attempt++))
        fi
    done
}

# Function to show usage information
show_usage() {
    cat << EOF
Enhanced Directory-based LaTeX Compilation Script

USAGE:
    ./reproduce-all-standalone-files-in-a-dir.sh <directory>

ARGUMENTS:
    directory    Directory relative to repository root that contains .tex files to compile
                Examples: Subfiles, Private/Submissions/QE, Tables

DESCRIPTION:
    This script compiles all .tex files in the specified directory with comprehensive
    error detection, interactive retry for failures, and detailed diagnostic output.
    
    The script must be run from the repository root or any subdirectory within the git repo.

EXAMPLES:
    ./reproduce/reproduce-all-standalone-files-in-a-dir.sh Subfiles
    ./reproduce/reproduce-all-standalone-files-in-a-dir.sh Private/Submissions/QE
    ./reproduce/reproduce-all-standalone-files-in-a-dir.sh Tables

EOF
}

# Function to validate directory argument
validate_target_directory() {
    local target_dir="$1"
    local repo_root
    
    # Find repository root
    if ! repo_root=$(git rev-parse --show-toplevel 2>/dev/null); then
        echo -e "${RED}❌ Error: Not in a git repository${NC}"
        echo -e "${YELLOW}This script must be run from within a git repository.${NC}"
        exit 1
    fi
    
    local full_target_path="$repo_root/$target_dir"
    
    # Check if directory exists
    if [[ ! -d "$full_target_path" ]]; then
        echo -e "${RED}❌ Error: Directory '$target_dir' does not exist${NC}"
        echo -e "${YELLOW}Looking for: $full_target_path${NC}"
        echo -e "${BOLD}Available directories in repository root:${NC}"
        find "$repo_root" -maxdepth 2 -type d -name "*" | grep -E "\.(tex|sty)$|[Ss]ubfiles|[Tt]ables|[Pp]rivate" | sort || true
        exit 1
    fi
    
    # Check if directory contains .tex files
    local tex_count
    tex_count=$(find "$full_target_path" -maxdepth 1 -name "*.tex" | wc -l)
    
    if [[ $tex_count -eq 0 ]]; then
        echo -e "${RED}❌ Error: Directory '$target_dir' contains no .tex files${NC}"
        echo -e "${YELLOW}Looking in: $full_target_path${NC}"
        echo -e "${BOLD}Files found in directory:${NC}"
        find "$full_target_path" -maxdepth 1 -type f -exec ls -ld {} \; 2>/dev/null | head -10
        exit 1
    fi
    
    echo -e "${GREEN}✅ Found $tex_count .tex files in $target_dir${NC}" >&2
    echo "$full_target_path"
}

# Main execution function
main() {
    # Parse command line arguments
    if [[ $# -ne 1 ]]; then
        echo -e "${RED}❌ Error: Missing directory argument${NC}"
        echo ""
        show_usage
        exit 1
    fi
    
    local target_dir="$1"
    
    # Handle help requests
    case "$target_dir" in
        -h|--help|help)
            show_usage
            exit 0
            ;;
    esac
    
    echo -e "${BOLD}${BLUE}"
    echo "════════════════════════════════════════════════════════════"
    echo "    Enhanced Directory-based LaTeX Compilation Script"
    echo "    Comprehensive Error Detection & Interactive Retry"
    echo "════════════════════════════════════════════════════════════"
    echo -e "${NC}"
    
    # Validate and get full path to target directory
    local full_target_path
    full_target_path=$(validate_target_directory "$target_dir")
    
    # Change to target directory
    cd "$full_target_path"
    echo -e "${BLUE}📁 Changed to directory: ${BOLD}$full_target_path${NC}"
    
    # Find all .tex files
    local tex_files=(*.tex)
    
    if [[ ${#tex_files[@]} -eq 0 || "${tex_files[0]}" == "*.tex" ]]; then
        echo -e "${RED}❌ No .tex files found in directory${NC}"
        exit 1
    fi
    
    echo -e "${BOLD}Found ${#tex_files[@]} .tex files in '$target_dir' to compile:${NC}"
    for file in "${tex_files[@]}"; do
        echo "  • $file"
    done
    
    echo -e "\n${BOLD}Starting compilation process in $target_dir...${NC}"
    
    local success_count=0
    local skip_count=0
    
    # Process each file
    for file in "${tex_files[@]}"; do
        echo -e "\n${BLUE}${BOLD}════════════════════════════════════════${NC}"
        echo -e "${BOLD}Processing: $file${NC}"
        echo -e "${BLUE}${BOLD}════════════════════════════════════════${NC}"
        
        # Skip non-existent files (shouldn't happen, but safety first)
        if [[ ! -f "$file" ]]; then
            echo -e "${YELLOW}⚠️  Skipping $file (file not found)${NC}"
            continue
        fi
        
        retry_until_success "$file"
        
        # Count results
        if [[ -f "${file%.tex}.pdf" ]]; then
            ((success_count++))
        else
            ((skip_count++))
        fi
    done
    
    # Final summary
    echo -e "\n${BLUE}${BOLD}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}Compilation Summary for '$target_dir':${NC}"
    echo -e "${GREEN}✅ Successfully compiled: $success_count files${NC}"
    if [[ $skip_count -gt 0 ]]; then
        echo -e "${YELLOW}⏭️  Skipped: $skip_count files${NC}"
    fi
    echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════════${NC}"
    
    echo -e "\n${GREEN}${BOLD}🎉 All done! Check the generated PDF files in $target_dir.${NC}"
}

# Run main function only if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

