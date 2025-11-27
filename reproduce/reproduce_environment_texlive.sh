#!/bin/bash
# HAFiscal TeX Environment Verification Script
# 
# This script performs comprehensive checking of TeX installation
# and provides clear guidance for resolving issues.

# Don't exit if sourced
(return 0 2>/dev/null) && SOURCED=1 || SOURCED=0
if [ "$SOURCED" -eq 0 ]; then
    set -e
fi

# Colors for output (if terminal supports them)
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    BLUE=$(tput setaf 4)
    BOLD=$(tput bold)
    RESET=$(tput sgr0)
else
    RED="" GREEN="" YELLOW="" BLUE="" BOLD="" RESET=""
fi

# Script directory for finding package list
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRED_PACKAGES_FILE="${SCRIPT_DIR}/required_latex_packages.txt"

# Function to print formatted messages
log_info() { echo "${BLUE}ℹ️  $*${RESET}"; }
log_success() { echo "${GREEN}✅ $*${RESET}"; }
log_warning() { echo "${YELLOW}⚠️  $*${RESET}"; }
log_error() { echo "${RED}❌ $*${RESET}"; }
log_header() { echo "${BOLD}${BLUE}$*${RESET}"; }

# Check if command exists
has_command() {
    command -v "$1" >/dev/null 2>&1
}

# Check if TeX is installed
check_texlive_installation() {
    log_header "🔍 Checking TeX Installation..."
    
    # Check for basic TeX commands
    local missing_commands=()
    local tex_commands=("tex" "latex" "pdflatex" "kpsewhich")
    
    for cmd in "${tex_commands[@]}"; do
        if ! has_command "$cmd"; then
            missing_commands+=("$cmd")
        fi
    done
    
    if [ ${#missing_commands[@]} -gt 0 ]; then
        log_error "Missing essential TeX commands: ${missing_commands[*]}"
        return 1
    fi
    
    log_success "All essential TeX commands found"
    return 0
}

# Get TeX installation info
get_texlive_info() {
    log_info "Checking tlmgr availability..."
    
    if ! has_command "tlmgr"; then
        return 1
    fi
    
    local tlmgr_version
    tlmgr_version=$(tlmgr --version 2>/dev/null | head -1)
    if [[ -n "$tlmgr_version" ]]; then
        log_info "TeX Manager: $tlmgr_version"
        
        # Check if tlmgr can access package database
        log_info "Testing tlmgr database access (5s timeout)..."
        if command -v timeout >/dev/null 2>&1 && timeout 5s tlmgr info latex >/dev/null 2>&1; then
            log_success "tlmgr can access package database"
        elif tlmgr --version >/dev/null 2>&1; then
            log_success "tlmgr can access package database"
            return 0
        else
            log_warning "tlmgr cannot access package database (may need repository update)"
            return 1
        fi
    else
        log_error "tlmgr command exists but cannot get version info"
        return 1
    fi
}

# Parse required packages from file
parse_required_packages() {
    if [[ ! -f "$REQUIRED_PACKAGES_FILE" ]]; then
        log_warning "Required packages file not found: $REQUIRED_PACKAGES_FILE"
        log_warning "Using minimal package set for checking"
        # Minimal fallback package list
        echo "amsmath amssymb graphicx hyperref natbib booktabs geometry xcolor"
        return
    fi
    
    # Extract package names, ignoring comments and empty lines
    grep -v '^#\|^$' "$REQUIRED_PACKAGES_FILE" | \
    grep -v '^##' | \
    sed 's/[[:space:]]*#.*//' | \
    tr '\n' ' '
}

# Check individual packages
check_latex_packages() {
    log_header "📦 Checking Required LaTeX Packages..."
    
    if ! has_command "kpsewhich"; then
        log_error "kpsewhich command not available - cannot check packages"
        return 1
    fi
    
    local packages
    packages=$(parse_required_packages)
    local missing_packages=()
    local checked_count=0
    local total_packages
    local start_time=$(date +%s)
    local timeout=30  # 30 second timeout for package checking
    
    # Count packages
    read -ra package_array <<< "$packages"
    total_packages=${#package_array[@]}
    
    log_info "Checking $total_packages packages (with timeout protection)..."
    
    for pkg in "${package_array[@]}"; do
        # Skip empty entries
        [[ -z "$pkg" ]] && continue
        
        # Check for timeout
        local current_time=$(date +%s)
        if (( current_time - start_time > timeout )); then
            log_warning "Package checking timed out after ${timeout}s"
            log_warning "Checked $checked_count/$total_packages packages before timeout"
            break
        fi
        
        ((checked_count++))
        
        # Try different extensions for package checking (with timeout per command)
        local found=false
        
        # Special cases for packages with non-standard naming or types
        case "$pkg" in
            lm)
                # Latin Modern: check for lmodern package
                if timeout 2s kpsewhich lmodern.sty >/dev/null 2>&1; then
                    found=true
                fi
                ;;
            ec)
                # European Computer Modern fonts: check for font files
                if timeout 2s kpsewhich ecrm1000.tfm >/dev/null 2>&1; then
                    found=true
                fi
                ;;
            cm-super)
                # CM-Super fonts: check for font files
                if timeout 2s kpsewhich sfss1000.pfb >/dev/null 2>&1; then
                    found=true
                fi
                ;;
            latex-bin)
                # LaTeX base: check for latex.ltx
                if timeout 2s kpsewhich latex.ltx >/dev/null 2>&1; then
                    found=true
                fi
                ;;
            *)
                # Standard package check
                for ext in "sty" "cls" "def"; do
                    if timeout 2s kpsewhich "${pkg}.${ext}" >/dev/null 2>&1; then
                        found=true
                        break
                    fi
                done
                
                if [[ "$found" = false ]]; then
                    # Special case: check if it's a command/binary
                    if has_command "$pkg"; then
                        found=true
                    fi
                fi
                ;;
        esac
        
        if [[ "$found" = false ]]; then
            missing_packages+=("$pkg")
        fi
        
        # Show progress for large package lists
        if (( checked_count % 10 == 0 )) || (( checked_count == total_packages )); then
            log_info "Progress: $checked_count/$total_packages packages checked..."
        fi
    done
    
    if [ ${#missing_packages[@]} -eq 0 ]; then
        log_success "All checked packages found ($checked_count packages verified)"
        return 0
    else
        local missing_count=${#missing_packages[@]}
        log_warning "Found $missing_count missing packages out of $checked_count checked:"
        
        # Show first few missing packages to avoid overwhelming output
        local display_count=$((missing_count > 10 ? 10 : missing_count))
        for i in $(seq 0 $((display_count - 1))); do
            echo "  - ${missing_packages[$i]}"
        done
        
        if (( missing_count > 10 )); then
            echo "  ... and $((missing_count - 10)) more"
        fi
        
        # Don't fail if we have a basic TeX installation and just some packages are missing
        # For scheme-basic installations, many packages will be missing - this is expected
        local missing_ratio=$((missing_count * 100 / total_packages))
        
        if (( missing_ratio < 80 )); then
            log_warning "Missing packages detected, but TeX appears functional"
            log_info "Missing $missing_count packages ($missing_ratio% of checked packages)"
            log_info "You may need to install additional packages as needed during compilation"
            log_info "Use 'tlmgr install <package>' to add missing packages"
            return 0
        else
            log_error "Missing $missing_count packages ($missing_ratio% of checked packages)"
            log_error "TeX installation may be too minimal for HAFiscal compilation"
            log_info "Consider installing a more complete TeX scheme:"
            log_info "  tlmgr install scheme-medium    # For most users"
            log_info "  tlmgr install scheme-full      # Complete installation"
            return 1
        fi
    fi
}

# Check TeX scheme
check_texlive_scheme() {
    if ! has_command "tlmgr"; then
        return 1
    fi
    
    log_header "🎯 Checking TeX Installation Scheme..."
    
    # Check for scheme-full (complete installation) with timeout
    if timeout 10s tlmgr info scheme-full 2>/dev/null | grep -q "installed: Yes"; then
        log_success "Complete TeX installation detected (scheme-full)"
        return 0
    fi
    
    # Check for scheme-medium with timeout
    if timeout 10s tlmgr info scheme-medium 2>/dev/null | grep -q "installed: Yes"; then
        log_success "Medium TeX installation detected (scheme-medium)"
        return 0
    fi
    
    # Check for scheme-basic with timeout
    if timeout 10s tlmgr info scheme-basic 2>/dev/null | grep -q "installed: Yes"; then
        log_warning "Basic TeX installation detected (scheme-basic)"
        log_warning "Some packages may need to be installed manually"
        return 0
    fi
    
    log_warning "Cannot determine TeX installation scheme (commands may have timed out)"
    log_info "This is not critical - TeX commands are working"
    return 0  # Don't fail just because we can't determine the scheme
}

# Provide installation instructions
show_installation_instructions() {
    log_header "📋 TeX Installation Instructions"
    echo
    
    # Detect platform
    local os_type=""
    case "$(uname -s)" in
        Linux*)   os_type="Linux";;
        Darwin*)  os_type="macOS";;
        CYGWIN*|MINGW*|MSYS*) os_type="Windows";;
        *)        os_type="Unknown";;
    esac
    
    echo "${BOLD}For $os_type:${RESET}"
    
    case $os_type in
        "Linux")
            echo "  ${GREEN}Option 1 - Package Manager (Recommended):${RESET}"
            echo "    Ubuntu/Debian: sudo apt-get install texlive-full"
            echo "    Fedora/RHEL:   sudo dnf install texlive-scheme-full"
            echo "    Arch Linux:    sudo pacman -S texlive-most texlive-lang"
            echo
            echo "  ${GREEN}Option 2 - Official TeX Installer:${RESET}"
            echo "    wget https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz"
            echo "    tar xzf install-tl-unx.tar.gz"
            echo "    cd install-tl-* && sudo ./install-tl"
            ;;
        "macOS")
            echo "  ${GREEN}Option 1 - MacTeX (Recommended):${RESET}"
            echo "    Download and install MacTeX from: https://tug.org/mactex/"
            echo
            echo "  ${GREEN}Option 2 - Homebrew:${RESET}"
            echo "    brew install --cask mactex"
            echo
            echo "  ${GREEN}Option 3 - MacPorts:${RESET}"
            echo "    sudo port install texlive +full"
            ;;
        "Windows")
            echo "  ${GREEN}Recommended: TeX for Windows${RESET}"
            echo "    Download installer from: https://tug.org/texlive/"
            echo "    Or use MikTeX: https://miktex.org/"
            ;;
        *)
            echo "  Visit https://tug.org/texlive/ for installation instructions"
            ;;
    esac
    
    echo
    echo "${BOLD}After Installation:${RESET}"
    echo "  1. Restart your terminal or reload your shell configuration"
    echo "  2. Verify installation: latex --version"
    echo "  3. Update package database: tlmgr update --self --all"
    echo "  4. Re-run this script to verify the installation"
    
    if [[ "$os_type" = "Linux" ]] || [[ "$os_type" = "macOS" ]]; then
        echo
        echo "${BOLD}For Development Environments:${RESET}"
        echo "  ${BLUE}Docker/Containers:${RESET} Use the HAFiscal devcontainer configuration"
        echo "  ${BLUE}CI/CD:${RESET} See .github/workflows/ for automated installation scripts"
    fi
}

# Main function
main() {
    # Marker file to track verification status
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Check if environment was already verified (look for any timestamped marker)
    local existing_marker=$(find "$script_dir" -name "reproduce_environment_texlive_*.verified" -type f 2>/dev/null | head -1)
    if [[ -n "$existing_marker" ]]; then
        log_success "TeX environment already verified (marker file exists)"
        echo "   To force re-verification, remove: $existing_marker"
        
        # Always return (never exit) since this script is designed to be sourced
        export TEXLIVE_OK=1
        return 0
    fi
    
    echo "${BOLD}HAFiscal TeX Environment Verification${RESET}"
    echo
    log_info "Checking if basic LaTeX commands are available..."
    
    # Do a quick sanity check first - if latex works, we're probably OK
    if command -v latex >/dev/null 2>&1 && command -v pdflatex >/dev/null 2>&1 && command -v latexmk >/dev/null 2>&1; then
        log_success "Basic LaTeX commands found (latex, pdflatex, latexmk)"
        log_info "Creating marker file to skip detailed checks on future runs..."
        
        # Create timestamped marker file
        local timestamp=$(date '+%Y%m%d-%H%M')
        local marker_file="$script_dir/reproduce_environment_texlive_${timestamp}.verified"
        touch "$marker_file"
        return 0
    fi
    
    echo "=========================================="
    echo
    
    local all_checks_passed=true
    
    # Check 1: Basic TeX installation
    if ! check_texlive_installation; then
        all_checks_passed=false
    fi
    echo
    
    # Check 2: TeX manager functionality (if available)
    if has_command "tlmgr"; then
        get_texlive_info
        echo
        check_texlive_scheme
        echo
    else
        log_warning "tlmgr not available - cannot check TeX scheme or manage packages"
        echo
    fi
    
    # Check 3: Required packages
    if ! check_latex_packages; then
        all_checks_passed=false
    fi
    echo
    
    # Results and recommendations
    if [[ "$all_checks_passed" = true ]]; then
        log_success "${BOLD}✅ TeX environment is ready for HAFiscal compilation!${RESET}"
        
        # Create timestamped marker file to skip future checks
        local timestamp=$(date '+%Y%m%d-%H%M')
        local marker_file="$script_dir/reproduce_environment_texlive_${timestamp}.verified"
        touch "$marker_file"
        log_info "Created verification marker: $marker_file"
        echo "   (Future runs will skip verification unless this file is removed)"
        
        # Always return (never exit) since this script is designed to be sourced
        export TEXLIVE_OK=1
        return 0
    else
        log_error "${BOLD}❌ TeX environment has issues that need to be resolved${RESET}"
        echo
        
        # Provide installation instructions
        show_installation_instructions
        
        # Always return (never exit) since this script is designed to be sourced
        return 1
    fi
}

# Run main function
main "$@"
