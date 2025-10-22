#!/bin/bash

# HAFiscal Reproduction Script
# This script provides options for reproducing different aspects of the HAFiscal project

set -eo pipefail

show_help() {
    cat << EOF
HAFiscal Reproduction Script

This script provides multiple reproduction options and includes environment testing.

USAGE:
    ./reproduce.sh [OPTION]

OPTIONS:
    --help, -h          Show this help message
    --docs, -d [SCOPE]  Reproduce LaTeX documents (SCOPE: main|all|figures|tables|subfiles, default: main)
                         main: only repo root files (HAFiscal-QE.tex, HAFiscal-Slides.tex)
                         all: root files + Figures/ + Tables/ + Subfiles/
                         figures: root files + Figures/
                         tables: root files + Tables/
                         subfiles: root files + Subfiles/
    --comp, -c [SCOPE]  Reproduce computational results (SCOPE: min|all, default: min)
                         min: minimal computational results (~1 hour)
                         all: all computational results (may take 1-2 days)
    --all, -a           Reproduce everything: all documents + all computational results
    --interactive, -i   Show interactive menu (default when run from terminal)
    --dry-run           Show commands that would be executed (only with --docs)

ENVIRONMENT TESTING:
    When run without arguments, this script first checks your environment setup.
    If environment testing fails, see README.md for setup instructions.

ENVIRONMENT VARIABLES:
    REPRODUCE_TARGETS   Comma-separated list of targets to reproduce (non-interactive mode)
                       Valid values: docs, comp, all
                       Examples:
                         REPRODUCE_TARGETS=docs
                         REPRODUCE_TARGETS=comp,docs  
                         REPRODUCE_TARGETS=all

EXAMPLES:
    ./reproduce.sh                           # Test environment, then run (interactive/auto)
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
    ./reproduce.sh --comp min                # Minimal computational results (~1 hour)
    ./reproduce.sh --comp all                # All computational results (1-2 days)
    ./reproduce.sh --all                     # Everything: all documents + all computational results
    
    # Non-interactive examples:
    REPRODUCE_TARGETS=docs ./reproduce.sh    # Documents only
    REPRODUCE_TARGETS=comp ./reproduce.sh    # Core computational results
    REPRODUCE_TARGETS=comp,docs ./reproduce.sh # Core computational results + documents
    echo | REPRODUCE_TARGETS=all ./reproduce.sh # Force non-interactive, everything

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
    echo "   - ⚠️  WARNING: This may take 1-2 DAYS to complete"
    echo "   - Requires significant computational resources"
    echo ""
    echo "5) Everything"
    echo "   - All documents + all computational results"
    echo "   - ⚠️  WARNING: This may take 1-2 DAYS to complete"
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
    echo "⚠️  WARNING: This process may take 1-2 DAYS to complete!"
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
    echo "⚠️  WARNING: This process may take 1-2 DAYS to complete!"
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
                break
                ;;
            5)
                reproduce_all_computational_results
                break
                ;;
            6)
                reproduce_all_results
                break
                ;;
            7)
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
        echo "Or run: ./reproduce/reproduce_environment_uv.sh"
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
        echo "     ./reproduce/reproduce_environment_uv.sh  (recommended, fast)"
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
    echo "⚠️  WARNING: This final step may take 1-2 DAYS to complete!"
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

# Parse all arguments first
while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --dry-run)
            DRY_RUN=true
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
            if [[ $# -gt 0 && "$1" =~ ^(min|all)$ ]]; then
                COMP_SCOPE="$1"
                shift
            else
                # Default to min if no scope specified
                COMP_SCOPE="min"
            fi
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
        echo "  ./reproduce/reproduce_environment_uv.sh"
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
        echo "  ./reproduce/reproduce_environment_uv.sh"
        echo ""
        echo "Or manually:"
        echo "  uv sync --all-groups"
        echo ""
        exit 1
    fi
    
    # We need to activate the environment
    echo "========================================"
    echo "🔄 Activating UV Environment"
    echo "========================================"
    echo ""
    
    # Check if conda is active and warn user
    if [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
        echo "ℹ️  Detected active conda environment: $CONDA_DEFAULT_ENV"
        echo "   Switching to uv .venv environment..."
        echo ""
    fi
    
    # Re-execute this script with the environment activated
    # Use exec to replace the current process
    echo "✅ Activating .venv and re-running reproduce.sh..."
    echo ""
    
    # Build the command to re-exec
    local reexec_cmd="source '$venv_path/bin/activate' && "
    
    # Preserve the original command with all arguments
    reexec_cmd+="exec bash '$0'"
    for arg in "$@"; do
        # Properly quote arguments that might contain spaces
        reexec_cmd+=" $(printf '%q' "$arg")"
    done
    
    # Execute in a new bash process
    exec bash -c "$reexec_cmd"
}

    # Save all arguments to pass through
    SCRIPT_ARGS=("$@")
    
    # Restore original arguments since we consumed them in parsing
    # We need to reconstruct them for the re-exec
    ARGS_FOR_REEXEC=()
    [[ "$DRY_RUN" == true ]] && ARGS_FOR_REEXEC+=("--dry-run")
    [[ -n "$ACTION" ]] && {
        case "$ACTION" in
            docs) ARGS_FOR_REEXEC+=("--docs" "$DOCS_SCOPE") ;;
            comp) ARGS_FOR_REEXEC+=("--comp" "$COMP_SCOPE") ;;
            all) ARGS_FOR_REEXEC+=("--all") ;;
            interactive) ARGS_FOR_REEXEC+=("--interactive") ;;
        esac
    }
    
    ensure_uv_environment "${ARGS_FOR_REEXEC[@]}"


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
            all)
                reproduce_all_computational_results
                exit $?
                ;;
            *)
                echo "ERROR: Unknown computational scope: $COMP_SCOPE"
                echo "Valid scopes: min, all"
                exit 1
                ;;
        esac
        ;;
    all)
        reproduce_all_results
        exit $?
        ;;
    interactive)
        run_interactive_menu
        exit $?
        ;;
    "")
        # No arguments provided - run environment testing first
        echo "HAFiscal Reproduction Script"
        echo ""
        
        # Test environment setup first
        if ! test_environment; then
            echo "Environment testing failed. Please set up your environment before proceeding."
            echo "Exiting..."
            exit 1
        fi
        
        if is_interactive; then
            # Running in interactive terminal - show menu
            echo "Environment testing passed. Starting interactive menu..."
            echo ""
            run_interactive_menu
        else
            # Non-interactive mode - check for environment variable override
            if [[ -n "${REPRODUCE_TARGETS:-}" ]]; then
                echo "Environment testing passed. Processing REPRODUCE_TARGETS..."
                echo ""
                process_reproduce_targets
                exit $?
            else
                # No environment variable set, use automatic full reproduction
                echo "Environment testing passed. Starting automatic full reproduction..."
                echo ""
                echo "⚠️  This will run all reproduction steps in sequence:"
                echo "   1. Documents → 2. Subfiles → 3. Minimal results → 4. All results"
                echo "   Final step may take 1-2 DAYS to complete!"
                echo ""
                
                run_automatic_reproduction || exit 1
                exit 0
            fi
        fi
        ;;
    *)
        echo "Unknown action: $ACTION"
        echo "Run with --help for available options"
        exit 1
        ;;
esac
