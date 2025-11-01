#!/bin/bash

# HAFiscal Reproduction Script
# This script provides options for reproducing different aspects of the HAFiscal project

set -eo pipefail

# ============================================================================
# CHECK FOR WINDOWS (NON-WSL) ENVIRONMENT
# ============================================================================
case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*)
        echo "================================================================"
        echo "❌ ERROR: Windows Native Environment Detected"
        echo "================================================================"
        echo ""
        echo "This script requires a Unix-like environment and cannot run"
        echo "directly on Windows."
        echo ""
        echo "Please use Windows Subsystem for Linux 2 (WSL2) instead:"
        echo ""
        echo "1. Install WSL2 (if not already installed):"
        echo "   https://docs.microsoft.com/en-us/windows/wsl/install"
        echo ""
        echo "2. Open a WSL2 terminal (Ubuntu recommended)"
        echo ""
        echo "3. Navigate to this project directory in WSL2"
        echo ""
        echo "4. Run this script again from within WSL2"
        echo ""
        echo "Note: WSL1 is not supported. You must use WSL2."
        echo ""
        exit 1
        ;;
esac

# ============================================================================
# CHECK FOR BROKEN SYMLINKS (Git clone from Windows)
# ============================================================================
# If the repository was cloned in Windows and then accessed from WSL2,
# symlinks will be broken (converted to text files). Check for this.
check_symlinks() {
    # Symlink check disabled for QE distribution
    # This repository intentionally has dereferenced symlinks (real files)
    # created by rsync -L during QE package preparation
    :
}
# Run the symlink check
check_symlinks

# ============================================================================
# CHECK FOR LIMITED TERMINAL CAPABILITIES (e.g., Emacs Shell)
# ============================================================================
# Emacs shell (M-x shell) and other limited terminals don't properly handle
# subprocess output. Detect and warn the user to use a proper terminal.

if [[ "${TERM:-}" == "dumb" ]] || [[ -n "${EMACS:-}" ]] || [[ -n "${INSIDE_EMACS:-}" ]]; then
    echo "================================================================"
    echo "❌ ERROR: Limited Terminal Environment Detected"
    echo "================================================================"
    echo ""
    echo "This script requires a full terminal emulator to run properly."
    echo ""
    echo "Detected environment:"
    if [[ "${TERM:-}" == "dumb" ]]; then
        echo "  • TERM=dumb (typically Emacs shell mode)"
    fi
    if [[ -n "${EMACS:-}" ]]; then
        echo "  • EMACS variable set"
    fi
    if [[ -n "${INSIDE_EMACS:-}" ]]; then
        echo "  • INSIDE_EMACS variable set"
    fi
    echo ""
    echo "SOLUTION:"
    echo ""
    echo "Option 1: Use a regular terminal (Recommended)"
    echo "  • macOS: Terminal.app or iTerm2"
    echo "  • Linux: gnome-terminal, xterm, or your system's default terminal"
    echo "  • Windows: WSL2 terminal"
    echo ""
    echo "Option 2: Use Emacs term mode (full terminal emulator)"
    echo "  • In Emacs: M-x ansi-term RET /bin/bash RET"
    echo "  • Then run this script in that terminal"
    echo ""
    echo "Why: Emacs shell mode (M-x shell) is a 'dumb' terminal that doesn't"
    echo "     properly handle subprocess output from scripts like this."
    echo ""
    exit 1
fi


# ============================================================================
# BENCHMARKING CONFIGURATION
# Benchmarking is ON by default. Set BENCHMARK=false to disable.
# ============================================================================
BENCHMARK_ENABLED="${BENCHMARK:-true}"
BENCHMARK_START_TIME=""
BENCHMARK_START_ISO=""

benchmark_start() {
    if [[ "$BENCHMARK_ENABLED" == "true" ]]; then
        BENCHMARK_START_TIME=$(date +%s)
        BENCHMARK_START_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    fi
}

benchmark_end() {
    if [[ "$BENCHMARK_ENABLED" != "true" ]]; then
        return 0
    fi
    
    # Skip if benchmarking was never started (no action specified)
    if [[ -z "$BENCHMARK_START_TIME" ]]; then
        return 0
    fi
    
    local exit_status=$1
    
    # Only save benchmarks for successful runs (exit status 0)
    if [[ "$exit_status" -ne 0 ]]; then
        return 0
    fi
    
    local end_time=$(date +%s)
    local end_iso=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local duration=$((end_time - BENCHMARK_START_TIME))
    
    # Build filename: [kind]_[vers]_[opts]_YYYYMMDD-HHMM_[duration]s.json
    local kind="unknown"
    local vers=""
    local opts=""
    
    # Determine kind and version
    if [[ -n "${ACTION}" ]]; then
        case "$ACTION" in
            docs)
                kind="docs"
                vers="${DOCS_SCOPE:-main}"
                ;;
            comp)
                kind="comp"
                vers="${COMP_SCOPE:-min}"
                ;;
            envt)
                kind="envt"
                vers="${ENVT_SCOPE:-both}"
                # If testing comp environment and UV is detected, use comp_uv
                if [[ "$vers" == "comp" && "${ENVT_USING_UV:-false}" == "true" ]]; then
                    vers="comp_uv"
                fi
                ;;
            all)
                kind="all"
                vers="full"
                ;;
            *)
                kind="${ACTION}"
                ;;
        esac
    fi
    
    # Add options
    if [[ "$DRY_RUN" == "true" ]]; then
        opts="dry-run"
    fi
    
    # Build filename with underscores, timestamp, and 5-digit zero-padded duration
    local filename="${kind}"
    [[ -n "$vers" ]] && filename="${filename}_${vers}"
    [[ -n "$opts" ]] && filename="${filename}_${opts}"
    
    # Add timestamp (YYYYMMDD-HHMM format)
    local timestamp=$(date -d "@$BENCHMARK_START_TIME" '+%Y%m%d-%H%M' 2>/dev/null || date -r "$BENCHMARK_START_TIME" '+%Y%m%d-%H%M')
    filename="${filename}_${timestamp}"
    
    # Format duration as 5-digit zero-padded with 's' suffix
    local duration_str=$(printf "%05d" "$duration")
    filename="${filename}_${duration_str}s.json"
    
    # Ensure benchmarks directory exists
    local benchmark_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/reproduce/benchmarks/results"
    mkdir -p "$benchmark_dir"
    
    # Capture system info and create benchmark
    local capture_script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/reproduce/benchmarks/capture_system_info.py"
    if [[ -f "$capture_script" ]]; then
        local temp_sysinfo="/tmp/hafiscal_bench_$$_sysinfo.json"
        python3 "$capture_script" --pretty --output "$temp_sysinfo" 2>/dev/null || true
        
        local output_file="$benchmark_dir/$filename"
        local sysinfo=""
        
        # Try to read system info if file exists and is valid
        if [[ -f "$temp_sysinfo" && -s "$temp_sysinfo" ]]; then
            # Validate it's actual JSON by checking for opening brace
            if grep -q "^{" "$temp_sysinfo" 2>/dev/null; then
                sysinfo=$(sed 's/^/  /' "$temp_sysinfo" | sed '1d; $d')
            fi
        fi
        
        # Create benchmark JSON
        if [[ -n "$sysinfo" ]]; then
            # Include system info
            cat > "$output_file" << EOF
{
  "benchmark_version": "1.0.0",
  "benchmark_id": "${kind}-${vers:-unknown}_${timestamp}",
  "timestamp": "$BENCHMARK_START_ISO",
  "timestamp_end": "$end_iso",
  "reproduction_mode": "${kind}",
  "reproduction_scope": "${vers:-unknown}",
  "reproduction_args": [$(printf '"%s"' "${@}" | sed 's/" "/", "/g')],
  "exit_status": $exit_status,
  "duration_seconds": $duration,
${sysinfo},
  "metadata": {
    "user": "${USER:-unknown}",
    "session_id": "$$",
    "ci": ${CI:-false},
    "dry_run": ${DRY_RUN:-false},
    "notes": ""
  }
}
EOF
        else
            # System info unavailable - create minimal benchmark
            cat > "$output_file" << EOF
{
  "benchmark_version": "1.0.0",
  "benchmark_id": "${kind}-${vers:-unknown}_${timestamp}",
  "timestamp": "$BENCHMARK_START_ISO",
  "timestamp_end": "$end_iso",
  "reproduction_mode": "${kind}",
  "reproduction_scope": "${vers:-unknown}",
  "reproduction_args": [$(printf '"%s"' "${@}" | sed 's/" "/", "/g')],
  "exit_status": $exit_status,
  "duration_seconds": $duration,
  "metadata": {
    "user": "${USER:-unknown}",
    "session_id": "$$",
    "ci": ${CI:-false},
    "dry_run": ${DRY_RUN:-false},
    "notes": "System info unavailable"
  }
}
EOF
        fi
        
        # Create/update latest symlink
        ln -sf "$filename" "$benchmark_dir/latest.json"
        
        echo ""
        echo "📊 Benchmark saved: reproduce/benchmarks/results/$filename"
        echo "   Duration: $(printf '%d:%02d:%02d' $((duration/3600)) $((duration%3600/60)) $((duration%60))) ($duration seconds)"
        
        # Cleanup
        rm -f "$temp_sysinfo"
    fi
}

# Trap to ensure benchmark is saved even on error
trap 'benchmark_end $?' EXIT

show_help() {
    cat << EOF
HAFiscal Reproduction Script

This script provides multiple reproduction options and includes environment testing.

USAGE:
    ./reproduce.sh [OPTION]

OPTIONS:
    --help, -h          Show this help message
    --envt, -e          Test environment setup (TeX Live + Python/computational)
    --docs, -d [SCOPE]  Reproduce LaTeX documents (SCOPE: main|all|figures|tables|subfiles, default: main)
                         main: only repo root files (HAFiscal-QE.tex, HAFiscal-Slides.tex)
                         all: root files + Figures/ + Tables/ + Subfiles/
                         figures: root files + Figures/
                         tables: root files + Tables/
                         subfiles: root files + Subfiles/
    --comp, -c [SCOPE]  Reproduce computational results (SCOPE: min|full|max, default: min)
                         min: minimal computational results (~1 hour)
                         full: all computational results needed for the printed document (3-4 days on a high-end 2025 laptop)
                         max: full results + robustness (Step 3: Splurge=0 for Online Appendix) (~5 days on a high-end 2025 laptop)
    --data              Reproduce empirical data moments from SCF 2004 (~1 minute + download time)
                         Downloads SCF data if needed, calculates moments used in paper
    --all, -a           Reproduce everything: all documents + all computational results
    --interactive, -i   Show interactive menu (delegates to reproduce.py)
    --dry-run           Show commands that would be executed (only with --docs)
    --stop-on-error     Stop compilation on first error (useful for debugging, only with --docs)

ENVIRONMENT TESTING:
    Use --envt to test your environment setup (TeX Live and/or Python).
    For environment issues, see README.md for setup instructions.

ENVIRONMENT VARIABLES:
    REPRODUCE_TARGETS   Comma-separated list of targets to reproduce (non-interactive mode)
                       Valid values: docs, comp, all
                       Examples:
                         REPRODUCE_TARGETS=docs
                         REPRODUCE_TARGETS=comp,docs  
                         REPRODUCE_TARGETS=all
    
    BENCHMARK          Enable/disable automatic benchmarking (default: true)
                       Examples:
                         BENCHMARK=false ./reproduce.sh --docs    # Disable benchmarking
                         BENCHMARK=true ./reproduce.sh --comp min # Enable (default)

EXAMPLES:
    ./reproduce.sh                           # Show quick examples (this help)
    ./reproduce.sh --interactive             # Show interactive menu
    ./reproduce.sh --envt                    # Test both TeX Live and computational environments
    ./reproduce.sh --envt texlive            # Test TeX Live environment only
    ./reproduce.sh --envt comp_uv            # Test computational (UV) environment only
    ./reproduce.sh --docs                    # Compile repo root documents (default: main scope)
    ./reproduce.sh --docs main               # Compile only repo root documents  
    ./reproduce.sh --docs all                # Compile root + Figures/ + Tables/ + Subfiles/
    ./reproduce.sh --docs figures            # Compile repo root + Figures/
    ./reproduce.sh --docs tables             # Compile repo root + Tables/
    ./reproduce.sh --docs subfiles           # Compile repo root + Subfiles/
    ./reproduce.sh --docs --dry-run          # Show document compilation commands
    ./reproduce.sh --docs main --dry-run     # Show commands for root documents only
    ./reproduce.sh --docs figures --dry-run  # Show commands for root + figures
    ./reproduce.sh --docs tables --dry-run   # Show commands for root + tables
    ./reproduce.sh --docs all --stop-on-error # Stop on first compilation error
    ./reproduce.sh --comp min                # Minimal computational results (~1 hour)
    ./reproduce.sh --comp full               # All computational results for printed document (3-4 days on a high-end 2025 laptop)
    ./reproduce.sh --comp max                # Maximum computational results including robustness (~5 days on a high-end 2025 laptop)
    ./reproduce.sh --data                    # Empirical data moments from SCF 2004 (~1 minute + download)
    ./reproduce.sh --all                     # Everything: all documents + all computational results
    
    # Advanced examples:
    BENCHMARK=false ./reproduce.sh --docs main   # Disable benchmarking
    ./reproduce.sh --docs main --dry-run         # Preview commands without executing

EOF
}

show_interactive_menu() {
    echo "========================================"
    echo "   HAFiscal Reproduction Options"
    echo "========================================"
    echo ""
    echo "Please select what you would like to reproduce:"
    echo ""
    echo "1) LaTeX Documents"
    echo "   - Compiles all PDF documents from LaTeX source"
    echo "   - Estimated time: A few minutes"
    echo ""
    echo "2) Subfiles"
    echo "   - Compiles all .tex files in Subfiles/ directory"
    echo "   - Estimated time: A few minutes"
    echo ""
    echo "3) Minimal Computational Results"
    echo "   - Reproduces a subset of computational results"
    echo "   - Estimated time: ~1 hour"
    echo "   - Good for testing and quick verification"
    echo ""
    echo "4) All Computational Results"
    echo "   - Reproduces all computational results from the paper"
    echo "   - ⚠️  WARNING: This may take 3-4 DAYS on a high-end 2025 laptop"
    echo "   - Requires significant computational resources"
    echo ""
    echo "5) Everything"
    echo "   - All documents + all computational results"
    echo "   - ⚠️  WARNING: This may take 3-4 DAYS on a high-end 2025 laptop"
    echo "   - Complete reproduction of the entire project"
    echo ""
    echo "6) Exit"
    echo ""
    echo -n "Enter your choice (1-6): "
}

reproduce_documents() {
    echo "========================================"
    echo "Reproducing LaTeX Documents..."
    echo "========================================"
    echo ""
    
    if [[ -f "./reproduce/reproduce_documents.sh" ]]; then
        local args=("--quick" "--verbose")
        
        # Add scope-specific arguments
        args+=("--scope" "${DOCS_SCOPE:-main}")
        
        if [[ "${DRY_RUN:-false}" == true ]]; then
            args+=("--dry-run")
        fi
        
        if [[ "${STOP_ON_ERROR:-false}" == true ]]; then
            args+=("--stop-on-error")
        fi
        
        ./reproduce/reproduce_documents.sh "${args[@]}"
    else
        echo "ERROR: ./reproduce/reproduce_documents.sh not found"
        echo "Please run from the project root directory"
        return 1
    fi
}

reproduce_subfiles() {
    echo "========================================"
    echo "Compiling All Subfiles..."
    echo "========================================"
    echo ""
    
    # Check if Subfiles directory exists
    if [[ ! -d "Subfiles" ]]; then
        echo "ERROR: Subfiles/ directory not found"
        return 1
    fi
    
    # Find all .tex files in Subfiles directory (exclude hidden files starting with .)
    local tex_files=()
    while IFS= read -r -d '' file; do
        tex_files+=("$file")
    done < <(find Subfiles -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 | sort -z)
    
    if [[ ${#tex_files[@]} -eq 0 ]]; then
        echo "No .tex files found in Subfiles/ directory"
        return 1
    fi
    
    echo "Found ${#tex_files[@]} .tex files to compile:"
    for file in "${tex_files[@]}"; do
        echo "  - $(basename "$file")"
    done
    echo ""
    
    # Compile each subfile
    local success_count=0
    local total_count=${#tex_files[@]}
    
    for file in "${tex_files[@]}"; do
        local filename
        local basename_no_ext
        filename=$(basename "$file")
        basename_no_ext=$(basename "$file" .tex)
        
        echo "📄 Compiling $filename..."
        
        # Change to Subfiles directory for compilation
        if (cd Subfiles && latexmk -c "$filename" >/dev/null 2>&1 && latexmk "$filename" >/dev/null 2>&1); then
            if [[ -f "Subfiles/${basename_no_ext}.pdf" ]]; then
                echo "✅ Successfully created ${basename_no_ext}.pdf"
                ((success_count++))
            else
                echo "❌ PDF not created for $filename"
            fi
        else
            echo "❌ Error compiling $filename"
        fi
        echo ""
    done
    
    # Summary
    echo "========================================"
    echo "Subfiles Compilation Summary"
    echo "========================================"
    echo "Successfully compiled: $success_count/$total_count files"
    
    if [[ $success_count -eq $total_count ]]; then
        echo "🎉 All subfiles compiled successfully!"
        return 0
    else
        echo "⚠️  Some subfiles failed to compile"
        return 1
    fi
}

reproduce_all_results() {
    echo "========================================"
    echo "Complete Reproduction: All Computational Results + Documents"
    echo "========================================"
    echo ""
    echo "⚠️  WARNING: This process may take 3-4 DAYS on a high-end 2025 laptop!"
    echo "This will reproduce (in order):"
    echo "  1. All computational results"
    echo "  2. All documents (LaTeX compilation)"
    echo ""
    echo "Make sure you have:"
    echo "- Sufficient computational resources"
    echo "- Stable power supply" 
    echo "- No other intensive processes running"
    echo ""
    
    if is_interactive; then
        echo -n "Are you sure you want to continue? (y/N): "
        read -r confirm
        
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            echo ""
            echo "Starting complete reproduction..."
        else
            echo "Cancelled by user."
            return 0
        fi
    else
        echo "Running in non-interactive mode - proceeding with complete reproduction..."
        echo ""
    fi
    
    local step=1
    local total_steps=2
    
    # Step 1: All computational results (DO COMPUTATION FIRST)
    echo ">>> Step $step/$total_steps: Reproducing all computational results..."
    echo "========================================"
    if reproduce_all_computational_results; then
        echo "✅ Step $step/$total_steps completed successfully"
    else
        echo "❌ Step $step/$total_steps failed"
        return 1
    fi
    echo ""
    ((step++))
    
    # Step 2: All documents (DOCUMENTS DEPEND ON COMPUTATION)
    echo ">>> Step $step/$total_steps: Reproducing all documents..."
    echo "========================================"
    # Save current DOCS_SCOPE and set to all temporarily
    local saved_docs_scope="${DOCS_SCOPE:-}"
    DOCS_SCOPE="all"
    if reproduce_documents; then
        echo "✅ Step $step/$total_steps completed successfully"
    else
        echo "❌ Step $step/$total_steps failed"
        DOCS_SCOPE="$saved_docs_scope"  # Restore original scope
        return 1
    fi
    DOCS_SCOPE="$saved_docs_scope"  # Restore original scope
    echo ""
    
    echo "🎉 Complete reproduction finished successfully!"
}

reproduce_minimal_results() {
    echo "========================================"
    echo "Reproducing Minimal Computational Results..."
    echo "========================================"
    echo ""
    echo "This will reproduce a subset of results (~1 hour)"
    echo ""
    
    if [[ -f "./reproduce/reproduce_computed_min.sh" ]]; then
        ./reproduce/reproduce_computed_min.sh
    else
        echo "ERROR: ./reproduce/reproduce_computed_min.sh not found"
        return 1
    fi
}


reproduce_all_computational_results() {
    echo "========================================"
    echo "Reproducing All Computational Results..."
    echo "========================================"
    echo ""
    echo "⚠️  WARNING: This process may take 3-4 DAYS on a high-end 2025 laptop!"
    echo "Make sure you have:"
    echo "- Sufficient computational resources"
    echo "- Stable power supply"
    echo "- No other intensive processes running"
    echo ""
    
    if is_interactive; then
        echo -n "Are you sure you want to continue? (y/N): "
        read -r confirm
        
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            echo ""
            echo "Starting full computational reproduction..."
        else
            echo "Cancelled by user."
            return 0
        fi
    else
        echo "Running in non-interactive mode - proceeding with full reproduction..."
        echo ""
    fi
    
    if [[ -f "./reproduce/reproduce_computed.sh" ]]; then
        ./reproduce/reproduce_computed.sh
    else
        echo "ERROR: ./reproduce/reproduce_computed.sh not found"
        return 1
    fi
}

test_environment_comprehensive() {
    local scope="${1:-both}"
    
    echo "========================================"
    echo "Testing HAFiscal Environment Setup"
    echo "========================================"
    echo ""
    
    case "$scope" in
        texlive)
            echo "Testing: TeX Live environment only"
            ;;
        comp)
            echo "Testing: Computational environment only"
            ;;
        both)
            echo "Testing: Both TeX Live and computational environments"
            ;;
    esac
    echo ""
    
    local overall_status=0
    
    # Test TeX Live environment (if requested)
    if [[ "$scope" == "texlive" || "$scope" == "both" ]]; then
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "1️⃣  Testing TeX Live Environment"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        if [[ -f "./reproduce/reproduce_environment_texlive.sh" ]]; then
            if ./reproduce/reproduce_environment_texlive.sh 2>&1; then
                echo ""
                echo "✅ TeX Live environment: PASSED"
            else
                echo ""
                echo "❌ TeX Live environment: FAILED"
                overall_status=1
            fi
        else
            echo "⚠️  TeX Live test script not found"
            overall_status=1
        fi
        echo ""
    fi
    
    # Test Computational environment (if requested)
    if [[ "$scope" == "comp" || "$scope" == "both" ]]; then
        # Check if environment was already verified (look for any timestamped marker)
        local comp_marker=""
        local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/reproduce"
        
        if [[ "$scope" == "both" ]]; then
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "2️⃣  Testing Computational Environment"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        else
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "Testing Computational Environment"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        fi
        echo ""
    
        # Check for UV environment first
        if [[ -d ".venv" ]] && [[ -f "pyproject.toml" ]]; then
            # Check for existing comp_uv verification marker
            comp_marker=$(find "$script_dir" -name "reproduce_environment_comp_uv_*.verified" -type f 2>/dev/null | head -1)
            if [[ -n "$comp_marker" ]]; then
                echo "✅ Computational (UV) environment already verified (marker file exists)"
                echo "   To force re-verification, remove: $comp_marker"
                echo ""
                # Skip detailed tests since we have a marker
            else
                echo "🔍 Checking UV environment (.venv)..."
                # Set flag for benchmark filename generation
                export ENVT_USING_UV="true"
                if [[ -f ".venv/bin/python" ]]; then
                    echo "  ✅ UV environment exists"
                    
                    # Test key packages
                    if .venv/bin/python -c "import numpy, scipy, pandas, matplotlib; print('✅ Key packages available')" 2>/dev/null; then
                        echo "  ✅ Core scientific packages installed"
                    else
                        echo "  ⚠️  Some packages may be missing"
                        overall_status=1
                    fi
                    
                    # Check for HARK/econ-ark
                    if .venv/bin/python -c "import HARK; print(f'  ✅ HARK {HARK.__version__} installed')" 2>/dev/null; then
                        :
                    else
                        echo "  ⚠️  HARK (econ-ark) not installed"
                        echo "     Run: uv sync --all-groups"
                        overall_status=1
                    fi
                else
                    echo "  ❌ UV environment incomplete"
                    echo "     Run: uv sync --all-groups"
                    overall_status=1
                fi
            fi
        # Check for conda environment
        elif [[ -n "${CONDA_DEFAULT_ENV:-}" ]] || command -v conda >/dev/null 2>&1; then
            echo "🔍 Checking Conda environment..."
            
            if [[ -f "./reproduce/reproduce_environment.sh" ]]; then
                if ./reproduce/reproduce_environment.sh; then
                    echo "  ✅ Conda environment: PASSED"
                else
                    echo "  ❌ Conda environment: FAILED"
                    overall_status=1
                fi
            else
                echo "  ⚠️  Conda test script not found"
                overall_status=1
            fi
        else
            echo "❌ No Python environment detected"
            echo ""
            echo "Please set up an environment:"
            echo "  Option 1 (Recommended): ./reproduce/reproduce_environment_comp_uv.sh"
            echo "  Option 2 (Traditional):  conda env create -f environment.yml"
            overall_status=1
        fi
        echo ""
    fi
    
    # Summary
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Environment Test Summary"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    if [[ $overall_status -eq 0 ]]; then
        echo "✅ ${GREEN}All environment tests PASSED${RESET}"
        echo ""
        
        # Create verification marker file for successful comp_uv tests
        if [[ "$scope" == "comp" && "${ENVT_USING_UV:-false}" == "true" && -z "$comp_marker" ]]; then
            local timestamp=$(date '+%Y%m%d-%H%M')
            local marker_file="$script_dir/reproduce_environment_comp_uv_${timestamp}.verified"
            touch "$marker_file"
            echo "ℹ️  Created verification marker: reproduce_environment_comp_uv_${timestamp}.verified"
            echo "   (Future runs will skip verification unless this file is removed)"
            echo ""
        fi
        
        echo "Your system is ready to reproduce HAFiscal results!"
        echo ""
        echo "Next steps:"
        echo "  ./reproduce.sh --docs      # Compile documents"
        echo "  ./reproduce.sh --comp min  # Run minimal computation"
    else
        echo "❌ ${RED}Some environment tests FAILED${RESET}"
        echo ""
        echo "Please fix the issues above before proceeding."
        echo ""
        echo "For help, see:"
        echo "  README.md - Setup instructions"
        echo "  INSTALLATION.md - Platform-specific guides"
        echo "  TROUBLESHOOTING.md - Common issues"
    fi
    echo ""
    
    return $overall_status
}

run_interactive_menu() {
    while true; do
        show_interactive_menu
        read -r choice
        echo ""
        
        case $choice in
            1)
                reproduce_documents
                break
                ;;
            2)
                DOCS_SCOPE="subfiles"
                reproduce_documents
                break
                ;;
            3)
                reproduce_minimal_results
                break
                ;;
            4)
                reproduce_all_computational_results
                break
                ;;
            5)
                reproduce_all_results
                break
                ;;
            6)
                echo "Exiting..."
                exit 0
                ;;
            *)
                echo "Invalid choice. Please enter 1, 2, 3, 4, 5, or 6."
                echo ""
                ;;
        esac
    done
}

# Function to test environment setup
test_environment() {
    echo "========================================"
    echo "Environment Testing"
    echo "========================================"
    echo ""
    
    # Check if UV is available and recommend it
    if command -v uv >/dev/null 2>&1; then
        echo "✅ UV detected (recommended environment manager)"
        echo ""
        echo "Quick setup with UV:"
        echo "  uv sync --all-groups"
        echo "  source .venv/bin/activate"
        echo ""
        echo "Or run: ./reproduce/reproduce_environment_comp_uv.sh"
        echo ""
    else
        echo "ℹ️  UV not detected. Using conda environment."
        echo ""
        echo "For faster setup, consider installing UV:"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        echo ""
    fi
    
    echo "🔍 Checking required dependencies..."
    
    local env_ok=true
    local missing_deps=()
    
    # Test basic commands
    echo "• Checking basic tools..."
    if ! command -v latexmk >/dev/null 2>&1; then
        missing_deps+=("latexmk")
        env_ok=false
    fi
    
    if ! command -v pdflatex >/dev/null 2>&1; then
        missing_deps+=("pdflatex") 
        env_ok=false
    fi
    
    if ! command -v bibtex >/dev/null 2>&1; then
        missing_deps+=("bibtex")
        env_ok=false
    fi
    
    if ! command -v python3 >/dev/null 2>&1; then
        missing_deps+=("python3")
        env_ok=false
    fi
    
    # Test LaTeX environment using existing script
    echo "• Checking LaTeX environment..."
    if [[ -f "./reproduce/reproduce_environment_texlive.sh" ]]; then
        if ! ./reproduce/reproduce_environment_texlive.sh >/dev/null 2>&1; then
            missing_deps+=("LaTeX packages (see reproduce_environment_texlive.sh)")
            env_ok=false
        fi
    else
        echo "  ⚠️  Cannot verify LaTeX packages (reproduce_environment_texlive.sh not found)"
    fi
    
    # Test computational environment if available
    echo "• Checking computational environment..."
    
    # Check for UV environment first
    if [[ -d ".venv" ]] && [[ -f "pyproject.toml" ]]; then
        if [[ -f ".venv/bin/python" ]]; then
            echo "  ✅ UV environment detected and appears valid"
        else
            echo "  ⚠️  UV environment incomplete. Run: uv sync --all-groups"
        fi
    # Fall back to conda check
    elif [[ -f "./reproduce/reproduce_environment.sh" ]]; then
        if ./reproduce/reproduce_environment.sh >/dev/null 2>&1; then
            echo "  ✅ Python/Conda environment OK"
        else
            echo "  ⚠️  Python/Conda environment needs setup (non-critical for document reproduction)"
        fi
    else
        echo "  ⚠️  No environment detected. Run one of:"
        echo "     ./reproduce/reproduce_environment_comp_uv.sh  (recommended, fast)"
        echo "     conda env create -f environment.yml      (traditional)"
    fi
    
    # Report results
    echo ""
    if [[ "$env_ok" == "true" ]]; then
        echo "✅ Environment testing passed!"
        echo "All essential dependencies are available."
        echo ""
        return 0
    else
        echo "❌ Environment testing failed!"
        echo ""
        echo "Missing dependencies:"
        for dep in "${missing_deps[@]}"; do
            echo "  • $dep"
        done
        echo ""
        echo "📖 For setup instructions, please see:"
        echo "   README.md - General setup guide"
        echo "   reproduce/reproduce_environment_texlive.sh - LaTeX setup"
        echo "   reproduce/reproduce_environment.sh - Python/Conda setup"
        echo ""
        echo "You can still run specific components if their dependencies are met:"
        echo "   ./reproduce.sh --docs      # Requires LaTeX tools"
        echo "   ./reproduce.sh --docs subfiles  # Requires LaTeX tools" 
        echo "   ./reproduce.sh --comp min  # Requires Python environment"
        echo "   ./reproduce.sh --all       # Requires Python environment"
        echo ""
        return 1
    fi
}

# Function to run full automatic reproduction (non-interactive mode)
run_automatic_reproduction() {
    echo "========================================"
    echo "Automatic Full Reproduction"
    echo "========================================"
    echo ""
    echo "Running complete reproduction sequence:"
    echo "  1. Documents (LaTeX compilation)"
    echo "  2. Subfiles (standalone LaTeX files)"
    echo "  3. Minimal computational results"
    echo "  4. All computational results"
    echo ""
    
    local step=1
    local total_steps=4
    
    # Step 1: Documents
    echo ">>> Step $step/$total_steps: Reproducing LaTeX documents..."
    echo "========================================"
    if reproduce_documents; then
        echo "✅ Step $step/$total_steps completed successfully"
    else
        echo "❌ Step $step/$total_steps failed"
        return 1
    fi
    echo ""
    ((step++))
    
    # Step 2: Subfiles  
    echo ">>> Step $step/$total_steps: Compiling subfiles..."
    echo "========================================"
    # Save current DOCS_SCOPE and set to subfiles temporarily
    local saved_docs_scope="${DOCS_SCOPE:-}"
    DOCS_SCOPE="subfiles"
    if reproduce_documents; then
        echo "✅ Step $step/$total_steps completed successfully"
    else
        echo "❌ Step $step/$total_steps failed"
        DOCS_SCOPE="$saved_docs_scope"  # Restore original scope
        return 1
    fi
    DOCS_SCOPE="$saved_docs_scope"  # Restore original scope
    echo ""
    ((step++))
    
    # Step 3: Minimal computational results
    echo ">>> Step $step/$total_steps: Reproducing minimal computational results..."
    echo "========================================"
    if reproduce_minimal_results; then
        echo "✅ Step $step/$total_steps completed successfully"
    else
        echo "❌ Step $step/$total_steps failed"
        return 1
    fi
    echo ""
    ((step++))
    
    # Step 4: All computational results  
    echo ">>> Step $step/$total_steps: Reproducing all computational results..."
    echo "========================================"
    echo "⚠️  WARNING: This final step may take 3-4 DAYS on a high-end 2025 laptop!"
    if reproduce_all_results; then
        echo "✅ Step $step/$total_steps completed successfully"
    else
        echo "❌ Step $step/$total_steps failed"
        return 1
    fi
    echo ""
    
    echo "========================================"
    echo "🎉 Automatic Full Reproduction Complete!"
    echo "========================================"
    echo ""
    echo "All steps completed successfully:"
    echo "  ✅ Documents compiled"
    echo "  ✅ Subfiles compiled"  
    echo "  ✅ Minimal computational results generated"
    echo "  ✅ All computational results generated"
    echo ""
}

is_interactive() {
    # Check if both stdin and stdout are terminals
    [[ -t 0 && -t 1 ]]
}

process_reproduce_targets() {
    local targets="${REPRODUCE_TARGETS:-}"
    
    if [[ -z "$targets" ]]; then
        echo "ERROR: REPRODUCE_TARGETS environment variable not set"
        echo "Valid values: docs, comp, all (comma-separated)"
        echo "Example: REPRODUCE_TARGETS=docs,comp"
        return 1
    fi
    
    # Replace commas with spaces for simple iteration
    local targets_spaced
    targets_spaced=$(echo "$targets" | tr ',' ' ')
    
    local has_error=false
    local executed_targets=""
    
    # Validate all targets first
    for target in $targets_spaced; do
        # Trim whitespace
        target=$(echo "$target" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        case "$target" in
            docs|comp|all)
                # Valid target
                ;;
            *)
                echo "ERROR: Invalid target '$target'"
                echo "Valid targets: docs, comp, all"
                has_error=true
                ;;
        esac
    done
    
    if [[ "$has_error" == true ]]; then
        return 1
    fi
    
    # Execute targets in a logical order: docs, comp, all
    for ordered_target in docs comp all; do
        for target in $targets_spaced; do
            target=$(echo "$target" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            if [[ "$target" == "$ordered_target" ]]; then
                # Check if we've already executed this target
                if [[ "$executed_targets" != *"$target"* ]]; then
                    echo "Executing target: $target"
                    case "$target" in
                        docs)
                            reproduce_documents || return 1
                            ;;
                        comp)
                            # Default to min scope for comp
                            ;;
                        all)
                            reproduce_all_results || return 1
                            ;;
                    esac
                    if [[ -z "$executed_targets" ]]; then
                        executed_targets="$target"
                    else
                        executed_targets="$executed_targets $target"
                    fi
                fi
            fi
        done
    done
    
    echo ""
    if [[ -n "$executed_targets" ]]; then
        echo "Completed targets: $executed_targets"
    else
        echo "No targets were executed"
    fi
}

# Parse command line arguments
DRY_RUN=false
ACTION=""
DOCS_SCOPE="main"  # default scope for --docs
COMP_SCOPE="min"   # default scope for --comp
ENVT_SCOPE="both"  # default scope for --envt

# Parse all arguments first
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --envt|-e)
            ACTION="envt"
            shift
            # Check if next argument is a scope specifier
            if [[ $# -gt 0 && "$1" =~ ^(texlive|comp|comp_uv|both)$ ]]; then
                ENVT_SCOPE="$1"
                # Map comp_uv to comp for the test, but set UV flag
                if [[ "$1" == "comp_uv" ]]; then
                    ENVT_SCOPE="comp"
                    export ENVT_USING_UV="true"
                fi
                shift
            else
                # Default to both if no scope specified
                ENVT_SCOPE="both"
            fi
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --stop-on-error)
            STOP_ON_ERROR=true
            shift
            ;;
        --docs|-d)
            ACTION="docs"
            shift
            # Check if next argument is a scope specifier
            if [[ $# -gt 0 && "$1" =~ ^(main|all|figures|tables|subfiles)$ ]]; then
                DOCS_SCOPE="$1"
                shift
            fi
            ;;
        --comp|-c)
            ACTION="comp"
            shift
            # Check if next argument is a scope specifier
            if [[ $# -gt 0 && "$1" =~ ^(min|full|max)$ ]]; then
                COMP_SCOPE="$1"
                shift
            else
                # Default to min if no scope specified
                COMP_SCOPE="min"
            fi
            ;;
        --data)
            ACTION="data"
            shift
            ;;
        --all|-a)
            ACTION="all"
            shift
            ;;
        --min|-m)
            # Legacy option - provide deprecation warning but still work
            echo "⚠️  WARNING: --min is deprecated. Use '--comp min' instead."
            echo "   This will be removed in a future version."
            ACTION="comp"
            COMP_SCOPE="min"
            shift
            ;;
        --interactive|-i)
            ACTION="interactive"
            shift
            ;;
        *)
            if [[ -z "$ACTION" && -z "$1" ]]; then
                # Empty argument, treat as no arguments
                break
            else
                echo "Unknown option: $1"
                echo "Run with --help for available options"
                exit 1
            fi
            ;;
    esac
done

# ============================================================================
# ENVIRONMENT ACTIVATION CHECK
# Ensure we're running in the uv .venv environment
# ============================================================================

ensure_uv_environment() {
    # Get the expected venv path
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
    local expected_venv="$script_dir/.venv"
    
    # Check if we're already in the correct uv .venv environment
    # Normalize both paths to handle symlinks
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        local normalized_venv="$(cd "$VIRTUAL_ENV" 2>/dev/null && pwd -P || echo "$VIRTUAL_ENV")"
        if [[ "$normalized_venv" == "$expected_venv" ]]; then
            # Already in correct environment - do nothing
            return 0
        fi
    fi
    
    # Check if .venv exists
    local venv_path="$expected_venv"
    
    if [[ ! -d "$venv_path" ]]; then
        echo "========================================"
        echo "❌ UV Virtual Environment Not Found"
        echo "========================================"
        echo ""
        echo "The uv virtual environment (.venv) does not exist."
        echo ""
        echo "Please set up the environment first:"
        echo "  ./reproduce/reproduce_environment_comp_uv.sh"
        echo ""
        echo "Or manually:"
        echo "  uv sync --all-groups"
        echo ""
        exit 1
    fi
    
    if [[ ! -f "$venv_path/bin/python" ]]; then
        echo "========================================"
        echo "❌ UV Virtual Environment Incomplete"
        echo "========================================"
        echo ""
        echo "The .venv directory exists but appears incomplete."
        echo ""
        echo "Please re-run the setup:"
        echo "  ./reproduce/reproduce_environment_comp_uv.sh"
        echo ""
        echo "Or manually:"
        echo "  uv sync --all-groups"
        echo ""
        exit 1
    fi
    
    # Not in correct environment - provide clear instructions
    echo "========================================"
    echo "⚠️  Wrong Python Environment"
    echo "========================================"
    echo ""
    echo "This script requires the UV virtual environment (.venv) to be active."
    echo ""
    if [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
        echo "Currently active: conda environment '$CONDA_DEFAULT_ENV'"
        echo ""
        echo "To fix this, deactivate conda and activate the UV environment:"
        echo "  conda deactivate"
        echo "  source .venv/bin/activate"
        echo "  $0 $@"
    elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
        echo "Currently active: $VIRTUAL_ENV"
        echo ""
        echo "To fix this, deactivate the current environment and activate the correct one:"
        echo "  deactivate"
        echo "  source .venv/bin/activate"
        echo "  $0 $@"
    else
        echo "No Python environment is currently active."
        echo ""
        echo "To fix this, activate the UV environment:"
        echo "  source .venv/bin/activate"
        echo "  $0 $@"
    fi
    echo ""
    echo "Or, if you're in emacs shell, run this command in a regular terminal."
    echo ""
    exit 1

}

    # Save all arguments to pass through
    SCRIPT_ARGS=("$@")
    
    # Restore original arguments since we consumed them in parsing
    # We need to reconstruct them for the re-exec
    ARGS_FOR_REEXEC=()
    [[ "$DRY_RUN" == true ]] && ARGS_FOR_REEXEC+=("--dry-run")
    [[ -n "$ACTION" ]] && {
        case "$ACTION" in
            envt) ARGS_FOR_REEXEC+=("--envt" "$ENVT_SCOPE") ;;
            docs) ARGS_FOR_REEXEC+=("--docs" "$DOCS_SCOPE") ;;
            comp) ARGS_FOR_REEXEC+=("--comp" "$COMP_SCOPE") ;;
            all) ARGS_FOR_REEXEC+=("--all") ;;
            interactive) ARGS_FOR_REEXEC+=("--interactive") ;;
        esac
    }
    
    ensure_uv_environment "${ARGS_FOR_REEXEC[@]}"

# Start benchmarking (only if an action is specified)
if [[ -n "$ACTION" ]]; then
    benchmark_start
fi

# Handle dry-run mode
if [[ "$DRY_RUN" == true ]]; then
    if [[ "$ACTION" == "docs" ]]; then
        # Dry-run is supported for docs - pass the flag
        echo "========================================"
        echo "🔍 DRY RUN MODE: Documents"
        echo "========================================"
        echo "The following commands would be executed:"
        echo ""
        DRY_RUN=true reproduce_documents
        exit $?
    elif [[ -n "$ACTION" ]]; then
        # Dry-run requested for other actions - show polite message
        echo "========================================"
        echo "ℹ️  Dry-run mode information"
        echo "========================================"
        echo ""
        echo "The --dry-run flag is currently only supported with the --docs flag."
        echo ""
        echo "To see what documents would be compiled, use:"
        echo "  ./reproduce.sh --docs --dry-run"
        echo ""
        echo "For other operations (--comp, --all), the reproduction"
        echo "scripts execute complex computational workflows that are not easily"
        echo "represented as simple commands that can be copy-pasted."
        echo ""
        exit 0
    else
        echo "ERROR: --dry-run requires one of: --docs, --comp, --all"
        echo "Currently, dry-run mode is only supported with --docs"
        exit 1
    fi
fi

# Execute the requested action
case "$ACTION" in
    envt)
        test_environment_comprehensive "$ENVT_SCOPE"
        exit $?
        ;;
    docs)
        reproduce_documents
        exit $?
        ;;
    comp)
        case "$COMP_SCOPE" in
            min)
                reproduce_minimal_results
                exit $?
                ;;
            full)
                reproduce_all_computational_results
                exit $?
                ;;
            max)
                # Set environment variable to enable Step 3 (robustness with Splurge=0)
                export HAFISCAL_RUN_STEP_3="true"
                reproduce_all_computational_results
                exit $?
                ;;
            *)
                echo "ERROR: Unknown computational scope: $COMP_SCOPE"
                echo "Valid scopes: min, full, max"
                exit 1
                ;;
        esac
        ;;
    data)
        echo "========================================"
        echo "Reproducing Empirical Data Moments..."
        echo "========================================"
        echo ""
        ./reproduce/reproduce_data_moments.sh
        exit $?
        ;;
    all)
        reproduce_all_results
        exit $?
        ;;
    interactive)
        # Use Python script for interactive menu (SST)
        if [[ -f "./reproduce.py" ]]; then
            python3 ./reproduce.py
            exit $?
        else
            echo "❌ Error: reproduce.py not found"
            echo "   The interactive menu requires reproduce.py"
            exit 1
        fi
        ;;
    "")
        # No arguments provided - show helpful examples
        echo "========================================"
        echo "HAFiscal Reproduction Script"
        echo "========================================"
        echo ""
        echo "Run with arguments to reproduce different parts of the project."
        echo ""
        echo "📖 QUICK EXAMPLES:"
        echo ""
        echo "  # LaTeX documents:"
        echo "  ./reproduce.sh --docs main          # Main paper & slides"
        echo "  ./reproduce.sh --docs all           # Include figures, tables, subfiles"
        echo ""
        echo "  # Computational results:"
        echo "  ./reproduce.sh --comp min           # Quick test (~1 hour)"
        echo "  ./reproduce.sh --comp full          # Full results (3-4 days)"
        echo ""
        echo "  # Empirical data:"
        echo "  ./reproduce.sh --data               # SCF 2004 moments (~1 min)"
        echo ""
        echo "  # Environment testing:"
        echo "  ./reproduce.sh --envt               # Test both environments"
        echo "  ./reproduce.sh --envt texlive       # Test LaTeX only"
        echo "  ./reproduce.sh --envt comp_uv       # Test Python/UV only"
        echo ""
        echo "  # Interactive mode:"
        echo "  ./reproduce.sh --interactive        # Show menu (uses reproduce.py)"
        echo "  ./reproduce.py                      # Python interactive menu (SST)"
        echo ""
        echo "  # Help:"
        echo "  ./reproduce.sh --help               # Full documentation"
        echo ""
        echo "========================================"
        echo ""
        echo "💡 TIP: Start with './reproduce.sh --docs main' to test your LaTeX setup"
        echo "        or './reproduce.sh --help' for complete documentation."
        echo ""
        exit 0
        ;;
    *)
        echo "Unknown action: $ACTION"
        echo "Run with --help for available options"
        exit 1
        ;;
esac
