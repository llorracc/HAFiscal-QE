#!/bin/bash
# HAFiscal LaTeX Document Reproduction Script
# 
# This script provides comprehensive document compilation following research reproduction best practices.
# Consolidates functionality from multiple reproduction scripts into a single, maintainable solution.

set -eo pipefail

# Configuration with sensible defaults
BUILD_MODE="${BUILD_MODE:-LONG}"
ONLINE_APPENDIX_HANDLING="${ONLINE_APPENDIX_HANDLING:-LINK_ONLY}"
LATEX_OPTS="${LATEX_OPTS:-}"
REPRODUCTION_MODE="${REPRODUCTION_MODE:-full}"
VERBOSE=false
CLEAN_FIRST=false
DRY_RUN=false
STOP_ON_ERROR="${STOP_ON_ERROR:-false}"
SCOPE="main"
DRAFT_MODE_ENABLED="false"
REPO_TYPE="STANDARD"  # Will be set to "QE" if HAFiscal.tex exists

show_help() {
    cat << 'EOF'
HAFiscal LaTeX Document Reproduction Script

USAGE:
    ./reproduce_documents.sh [OPTIONS] [TARGETS...]

OPTIONS:
    --help, -h              Show this help message
    --quick, -q             Quick compilation (single pass)
    --verbose, -v           Verbose output
    --clean, -c             Clean build artifacts before compilation
    --draft                 Compile HAFiscal*.tex in draft mode
                              - Latest/Public: Shows equation/figure/section labels
                              - QE: Shows line numbers (output: HAFiscal-draft.pdf)
                            Only applicable to HAFiscal.tex and HAFiscal.tex
                            Can also be controlled via DRAFT_MODE environment variable
    --single DOCUMENT       Compile only specified document
    --list                  List available documents
    --dry-run               Show commands that would be executed without running them
    --stop-on-error         Stop compilation on first error (useful for debugging)
                            Can also be controlled via STOP_ON_ERROR environment variable
    --scope SCOPE           Compilation scope (main|all|figures|tables|subfiles, default: main)
                            main: only repo root files
                            all: root + Figures/ + Tables/ + Subfiles/
                            figures: root + Figures/
                            tables: root + Tables/
                            subfiles: root + Subfiles/

TARGETS:
    main                    HAFiscal.tex (main paper)
    slides                  HAFiscal-Slides.tex
    appendix-hank          Subfiles/Appendix-HANK.tex
    appendix-nosplurge     Subfiles/Appendix-NoSplurge.tex
    all                    All documents (default)

EXAMPLES:
    ./reproduce_documents.sh                    # Compile all documents
    ./reproduce_documents.sh main slides       # Compile specific documents
    ./reproduce_documents.sh --single HAFiscal.tex
    ./reproduce_documents.sh --quick           # Fast compilation
    ./reproduce_documents.sh --draft           # Compile HAFiscal*.tex in draft mode
    DRAFT_MODE=1 ./reproduce_documents.sh      # Draft mode via environment variable
EOF
}

log_info() { echo "📋 $*"; }
log_success() { echo "✅ $*"; }
log_error() { echo "❌ ERROR: $*" >&2; }
log_warning() { echo "⚠️  WARNING: $*"; }

# Track if we fetched bibliography from with-precomputed-artifacts (for cleanup later)
FETCHED_BIBLIOGRAPHY=false

# Function to clean up auxiliary files after document compilation
cleanup_auxiliary_files() {
    local doc_path="$1"
    local doc_name="$2"
    
    if [[ "$DRY_RUN" == true ]]; then
        return 0
    fi
    
    log_info "Cleaning auxiliary files for $doc_name..."
    
    # Get the directory containing the document
    local doc_dir
    doc_dir=$(dirname "$doc_path")
    local doc_basename
    doc_basename=$(basename "$doc_path" .tex)
    
    # Preserve draft-mode PDFs before cleanup
    local draft_pdf_backup=""
    if [[ "$doc_basename" == "HAFiscal" ]] && [[ -f "HAFiscal-draft.pdf" ]]; then
        draft_pdf_backup="HAFiscal-draft.pdf.PRESERVE"
        mv "HAFiscal-draft.pdf" "$draft_pdf_backup" 2>/dev/null || true
        log_info "Preserving HAFiscal-draft.pdf during cleanup..."
    fi
    
    # Run standard latexmk cleanup
    if [[ -n "$doc_dir" && "$doc_dir" != "." ]]; then
        (cd "$doc_dir" && latexmk -c "$(basename "$doc_path")" >/dev/null 2>&1) || true
        
        # For non-root documents, also remove .txt and .dep files
        (cd "$doc_dir" && rm -f "${doc_basename}.txt" "${doc_basename}.dep" >/dev/null 2>&1) || true
    else
        latexmk -c "$doc_path" >/dev/null 2>&1 || true
    fi
    
    # Restore draft-mode PDF after cleanup
    if [[ -n "$draft_pdf_backup" ]] && [[ -f "$draft_pdf_backup" ]]; then
        mv "$draft_pdf_backup" "HAFiscal-draft.pdf" 2>/dev/null || true
        log_success "Restored HAFiscal-draft.pdf after cleanup"
    fi
    
    return 0
}

# Function to resolve document target to file path
resolve_document() {
    case "$1" in
        "main") echo "HAFiscal.tex" ;;
        "slides") echo "HAFiscal-Slides.tex" ;;
        "appendix-hank") echo "Subfiles/Appendix-HANK.tex" ;;
        "appendix-nosplurge") echo "Subfiles/Appendix-NoSplurge.tex" ;;
        *) echo "$1" ;;  # Return as-is for direct file paths
    esac
}

list_documents() {
    echo "Available document targets:"
    echo "  main -> HAFiscal.tex"
    echo "  slides -> HAFiscal-Slides.tex"
    echo "  appendix-hank -> Subfiles/Appendix-HANK.tex"
    echo "  appendix-nosplurge -> Subfiles/Appendix-NoSplurge.tex"
}

# Enhanced LaTeX Error Parser
parse_latex_error() {
    local log_file="$1"
    local doc_name="$2"
    
    if [[ ! -f "$log_file" ]]; then
        log_error "$doc_name: Log file not found: $log_file"
        return 1
    fi
    
    printf "\n"
    printf "🔍 LaTeX Error Analysis for %s:\n" "$doc_name"
    printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    local found_errors=false
    local current_file=""
    local line_number=""
    
    # Parse the log file for common error patterns
    while IFS= read -r line; do
        # Track current file being processed
        if [[ "$line" =~ ^\([^\)]+\) ]] || [[ "$line" =~ \([^\)]+\.tex ]]; then
            current_file=$(echo "$line" | grep -o '([^)]*\.tex' | sed 's/^(//' | tail -1)
        fi
        
        # Extract line numbers from error context  
        if [[ "$line" =~ l\.[0-9]+ ]]; then
            line_number=$(echo "$line" | grep -o 'l\.[0-9]\+' | cut -d. -f2)
        fi
        
        # Undefined control sequence
        if [[ "$line" =~ Undefined\ control\ sequence ]]; then
            found_errors=true
            local next_line
            read -r next_line
            local undefined_cmd
            undefined_cmd=$(echo "$next_line" | grep -o '\\[a-zA-Z]*' | head -1)
            echo "❌ Undefined Control Sequence: ${undefined_cmd:-unknown}"
            [[ -n "$current_file" ]] && echo "   📄 File: $current_file"
            [[ -n "$line_number" ]] && echo "   📍 Line: $line_number"
            echo "   💡 Common fixes:"
            case "$undefined_cmd" in
                "\\cite"*|"\\ref"*|"\\label"*)
                    echo "      • Check bibliography (.bib) file exists and is accessible"
                    echo "      • Run bibtex/bibliography compilation step"
                    echo "      • Verify cross-reference labels exist"
                    ;;
                "\\usepackage"*)
                    echo "      • Install missing LaTeX package"
                    echo "      • Check package name spelling"
                    ;;
                "\\begin"*|"\\end"*)
                    echo "      • Check environment name spelling"
                    printf "      • Ensure matching \\\\begin{} and \\\\end{} pairs\n"
                    ;;
                *)
                    echo "      • Check command spelling and syntax"
                    echo "      • Verify required packages are loaded"
                    echo "      • Add missing \\usepackage{} statements"
                    ;;
            esac
            printf "\n"
        fi
        
        # Missing file
        if [[ "$line" =~ File.*not\ found ]] || [[ "$line" =~ I\ couldn\'t\ open\ file\ name ]]; then
            found_errors=true
            local missing_file
            missing_file=$(echo "$line" | grep -o "'[^']*'" | tr -d "'")
            echo "❌ Missing File: ${missing_file:-unknown}"
            [[ -n "$current_file" ]] && echo "   📄 From: $current_file"
            echo "   💡 Common fixes:"
            echo "      • Check file path and spelling"
            echo "      • Ensure file exists in the correct directory"
            echo "      • Verify relative path is correct from document location"
            printf "\n"
        fi
        
        # Missing bibliography
        if [[ "$line" =~ Empty\ bibliography ]] || [[ "$line" =~ I\ couldn\'t\ open\ database\ file ]]; then
            found_errors=true
            echo "❌ Bibliography Issue"
            [[ -n "$current_file" ]] && echo "   📄 File: $current_file"
            echo "   💡 Common fixes:"
            echo "      • Ensure bibliography file (.bib) exists"
            printf "      • Check \\\\bibliography{} command references correct file\n"
            echo "      • Run: bibtex $doc_name"
            printf "\n"
        fi
        
        # Package errors
        if [[ "$line" =~ Package.*Error ]]; then
            found_errors=true
            local package_name
            package_name=$(echo "$line" | grep -o 'Package [^ ]*' | cut -d' ' -f2)
            echo "❌ Package Error: ${package_name:-unknown}"
            [[ -n "$current_file" ]] && echo "   📄 File: $current_file" 
            [[ -n "$line_number" ]] && echo "   📍 Line: $line_number"
            echo "   💡 Common fixes:"
            echo "      • Update LaTeX distribution"
            echo "      • Check package documentation for correct usage"
            echo "      • Verify package compatibility with other loaded packages"
            printf "\n"
        fi
        
        # Compilation stopped
        if [[ "$line" =~ Emergency\ stop ]] || [[ "$line" =~ job\ aborted ]]; then
            found_errors=true
            echo "❌ Compilation Emergency Stop"
            echo "   💡 This usually indicates a serious syntax error above"
            echo "      • Check for unmatched braces { }"
            echo "      • Look for incomplete commands or environments"
            echo "      • Review recent changes to the document"
            printf "\n"
        fi
        
    done < "$log_file"
    
    # Bibliography-specific checks
    if grep -q "Illegal, another.*bibdata command" "$log_file" 2>/dev/null; then
        found_errors=true
        echo "❌ Duplicate Bibliography Command"
        printf "   💡 This indicates multiple \\\\bibliography{} calls\n"
        printf "      • Check for duplicate \\\\smartbib{} usage\n"
        echo "      • Verify subfile bibliography handling"
        echo "      • Try: latexmk -C $doc_name && latexmk $doc_name"
        printf "\n"
    fi
    
    if ! $found_errors; then
        echo "ℹ️  No specific errors detected in log analysis"
        echo "   💡 The issue might be:"
        echo "      • A warning treated as error by latexmk"
        echo "      • Resource constraints (disk space, memory)"
        echo "      • Permission issues with output directory"
        printf "\n"
        echo "🔍 Recent log file excerpts:"
        echo "   Last 10 lines of $log_file:"
        tail -10 "$log_file" | sed 's/^/      /'
    fi
    
    printf "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    printf "📝 Full log available at: %s\n" "$log_file"
    printf "\n"
}

# Function to fetch HAFiscal.bib from with-precomputed-artifacts if needed
fetch_bibliography_if_needed() {
    # Check if HAFiscal.bib already exists - if so, don't fetch or track it
    # This ensures we only clean up files we fetched, not pre-existing ones
    if [[ -f "HAFiscal.bib" ]]; then
        return 0
    fi

    log_info "HAFiscal.bib not found in working directory"

    # Check if with-precomputed-artifacts branch exists
    PRECOMPUTED_BRANCH="with-precomputed-artifacts"
    REMOTE="${REMOTE:-origin}"

    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        log_warning "Not in a git repository - cannot fetch HAFiscal.bib"
        log_warning "Bibliography citations may not work correctly"
        return 0
    fi

    # Check for branch existence (try remote first, then local)
    BRANCH_EXISTS=false
    if git ls-remote --heads "$REMOTE" "$PRECOMPUTED_BRANCH" 2>/dev/null | grep -q "$PRECOMPUTED_BRANCH"; then
        BRANCH_EXISTS=true
        BRANCH_LOCATION="$REMOTE/$PRECOMPUTED_BRANCH"
    elif git show-ref --verify --quiet "refs/heads/$PRECOMPUTED_BRANCH"; then
        BRANCH_EXISTS=true
        BRANCH_LOCATION="$PRECOMPUTED_BRANCH"
    fi

    if [[ "$BRANCH_EXISTS" == "true" ]]; then
        echo ""
        echo "========================================"
        echo "📦 Fetching Bibliography File"
        echo "========================================"
        echo ""
        echo "HAFiscal.bib is required for citations but not present in main branch."
        echo "Fetching it from '$PRECOMPUTED_BRANCH' branch..."
        echo ""

        # Fetch the branch if it's remote
        if [[ "$BRANCH_LOCATION" == "$REMOTE/$PRECOMPUTED_BRANCH" ]]; then
            echo "→ Fetching $PRECOMPUTED_BRANCH from $REMOTE..."
            git fetch "$REMOTE" "$PRECOMPUTED_BRANCH" 2>/dev/null || true
        fi

        # Extract HAFiscal.bib using git show
        echo "→ Extracting HAFiscal.bib..."
        if git show "$BRANCH_LOCATION:HAFiscal.bib" > HAFiscal.bib 2>/dev/null; then
            if [[ -f "HAFiscal.bib" && -s "HAFiscal.bib" ]]; then
                FILE_SIZE=$(du -h "HAFiscal.bib" 2>/dev/null | cut -f1)
                echo "  ✓ HAFiscal.bib ($FILE_SIZE)"
                echo ""
                echo "✅ Successfully fetched bibliography from branch"
                echo "   (This will be automatically cleaned up after document compilation)"
                echo ""
                FETCHED_BIBLIOGRAPHY=true
            else
                log_error "HAFiscal.bib extraction failed or file is empty"
                rm -f HAFiscal.bib 2>/dev/null || true
            fi
        else
            log_warning "Could not extract HAFiscal.bib from '$PRECOMPUTED_BRANCH' branch"
            log_warning "Bibliography citations may not work correctly"
        fi
    else
        log_warning "'$PRECOMPUTED_BRANCH' branch does not exist"
        log_warning "Bibliography citations may not work correctly"
    fi

    return 0
}

validate_environment() {
    log_info "Validating compilation environment..."
    
    # Skip expensive validation in dry-run mode
    if [[ "$DRY_RUN" == true ]]; then
        log_info "Skipping environment validation (dry-run mode)"
        return 0
    fi
    
    
    # Allow skipping TeX Live package checks for speed
    if [[ "${SKIP_TEXLIVE_CHECK:-}" == "true" ]] || [[ "${SKIP_ENV_CHECK:-}" == "true" ]]; then
        log_warning "Skipping TeX Live package checks (SKIP_TEXLIVE_CHECK or SKIP_ENV_CHECK set)"
        # Ensure TeX Live bin is in PATH (for non-interactive shells)
        if [[ -f /etc/profile.d/texlive.sh ]]; then
            source /etc/profile.d/texlive.sh 2>/dev/null || true
        fi
        # Also check common TeX Live locations
        if ! command -v latexmk >/dev/null 2>&1; then
            for texlive_bin in /usr/local/texlive/*/bin/*/latexmk; do
                if [[ -f "$texlive_bin" ]]; then
                    export PATH="$(dirname "$texlive_bin"):$PATH"
                    break
                fi
            done
        fi
        # Still do minimal checks
        if ! command -v latex >/dev/null 2>&1; then
            log_error "latex command not found - please install TeX Live"
            return 1
        fi
        if ! command -v latexmk >/dev/null 2>&1; then
            log_error "latexmk is not installed or not in PATH"
            log_error "Tried PATH: $PATH"
            return 1
        fi
        if [[ ! -f "HAFiscal.tex" ]]; then
            log_error "HAFiscal.tex not found - run from project root directory"
            return 1
        fi
        log_success "Environment validation completed (minimal checks)"
        return 0
    fi
    # Check TeX Live installation first
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$script_dir/reproduce_environment_texlive.sh" ]]; then
        log_info "Checking TeX Live environment..."
        if ! source "$script_dir/reproduce_environment_texlive.sh"; then
            log_error "TeX Live environment check failed"
            log_error "Please install TeX Live and required packages before continuing"
            return 1
        fi
        log_success "TeX Live environment verified"
    else
        log_warning "TeX Live verification script not found - skipping comprehensive checks"
        
        # Minimal TeX Live check as fallback
        if ! command -v latex >/dev/null 2>&1; then
            log_error "latex command not found - please install TeX Live"
            return 1
        fi
    fi
    
    # Ensure TeX Live bin is in PATH (for non-interactive shells)
    # Try to source the TeX Live PATH if available
    if [[ -f /etc/profile.d/texlive.sh ]]; then
        source /etc/profile.d/texlive.sh 2>/dev/null || true
    fi
    # Also check common TeX Live locations
    if ! command -v latexmk >/dev/null 2>&1; then
        # Try to find latexmk in TeX Live directories
        for texlive_bin in /usr/local/texlive/*/bin/*/latexmk; do
            if [[ -f "$texlive_bin" ]]; then
                export PATH="$(dirname "$texlive_bin"):$PATH"
                break
            fi
        done
    fi
    if ! command -v latexmk >/dev/null 2>&1; then
        log_error "latexmk is not installed or not in PATH"
        log_error "Tried PATH: $PATH"
        return 1
    fi
    
    if [[ ! -f "HAFiscal.tex" ]]; then
        log_error "HAFiscal.tex not found - run from project root directory"
        return 1
    fi
    
    log_success "Environment validation completed"
}

setup_build_environment() {
    log_info "Setting up build environment..."
    
    export BUILD_MODE
    export ONLINE_APPENDIX_HANDLING
    
    # Preserve existing TEXINPUTS (from setup-latex-minimal.sh) and prepend qe/ directory
    # Use absolute path for qe/ to ensure it works regardless of working directory
    local qe_path
    if [[ -d "./qe" ]]; then
        qe_path="$(cd ./qe && pwd)"
    else
        qe_path="./qe"
    fi
    export TEXINPUTS="${qe_path}/:${TEXINPUTS:-}"
    
    # Also ensure @local/ is in TEXINPUTS if not already present (for owner.tex, config.ltx, etc.)
    # This handles cases where setup-latex-minimal.sh wasn't run or TEXINPUTS wasn't set
    if [[ -z "${TEXINPUTS:-}" ]] || [[ "$TEXINPUTS" != *"@local"* ]]; then
        local repo_root
        repo_root="$(pwd)"
        if [[ -d "$repo_root/@local" ]]; then
            export TEXINPUTS="${repo_root}/@local//:${TEXINPUTS}"
            log_info "Added @local/ to TEXINPUTS for owner.tex and config.ltx"
        fi
    fi
    
    export BSTINPUTS="./qe/:@resources/texlive/texmf-local/bibtex/bst/:${BSTINPUTS:-}"
    export BIBINPUTS="@resources/texlive/texmf-local/bibtex/bib/:resources-private/references/:${BIBINPUTS:-}"
    
    # Log TEXINPUTS for debugging (especially important in CI environments)
    if [[ "${VERBOSE:-false}" == "true" ]] || [[ -n "${CI:-}" ]]; then
        log_info "TEXINPUTS=${TEXINPUTS:-<not set>}"
    fi
    
    log_info "Build mode: $BUILD_MODE, Appendix handling: $ONLINE_APPENDIX_HANDLING"
}

compile_document() {
    local doc_path="$1"
    local doc_name
    doc_name="$(basename "$doc_path" .tex)"
    
    if [[ ! -f "$doc_path" ]]; then
        log_error "Document not found: $doc_path"
        return 1
    fi
    
    # Determine directory and filename
    local doc_dir
    local doc_file
    doc_dir="$(dirname "$doc_path")"
    doc_file="$(basename "$doc_path")"
    
    # For subdirectory files (Figures/, Tables/, Subfiles/), we need to cd into that directory
    # This ensures relative paths in .latexmkrc work correctly
    local needs_cd=false
    if [[ "$doc_dir" != "." && "$doc_dir" != "" ]]; then
        needs_cd=true
    fi
    
    # Configure latexmk options
    # -f forces latexmk to continue despite warnings (undefined refs are resolved in later passes)
    local latexmk_opts=("-f")
    if [[ -n "$LATEX_OPTS" ]]; then
        read -ra opts <<< "$LATEX_OPTS"
        latexmk_opts+=("${opts[@]}")
    fi
    
    # Handle draft mode
    local current_draft_mode="$DRAFT_MODE_ENABLED"
    
    # Validate: Only HAFiscal*.tex supports draft mode
    if [[ "$current_draft_mode" == "true" ]] && [[ ! "$doc_name" =~ ^HAFiscal ]]; then
        log_info "ℹ️  Draft mode only available for HAFiscal*.tex (not $doc_name), compiling normally"
        current_draft_mode="false"
    fi
    
    # Apply show-labels mode based on repository type, document name, and SHOW_LABELS variable
    if [[ "$REPO_TYPE" == "QE" ]] && [[ "$doc_name" == "HAFiscal" ]]; then
        # QE repository: Draft mode controls line numbers
        if [[ "$current_draft_mode" == "true" ]]; then
            log_info "📝 Compiling in QE draft mode (with line numbers)"
            latexmk_opts+=("-usepretex=\\def\\DraftMode{}\\def\\OnlineAppendixHandling{${ONLINE_APPENDIX_HANDLING}}")
            latexmk_opts+=("-jobname=HAFiscal-draft")
        else
            latexmk_opts+=("-usepretex=\\def\\OnlineAppendixHandling{${ONLINE_APPENDIX_HANDLING}}")
        fi
    elif [[ "$REPO_TYPE" == "STANDARD" ]] && [[ "$doc_name" == "HAFiscal" ]]; then
        # Latest/Public repository: Use show-labels mechanism
        if [[ "${SHOW_LABELS:-}" == "true" ]] || [[ "$current_draft_mode" == "true" ]]; then
            log_info "📝 Compiling with labels visible"
            latexmk_opts+=("-usepretex=\\def\\ShowLabelsOverride{}\\def\\OnlineAppendixHandling{${ONLINE_APPENDIX_HANDLING}}")
        elif [[ "${SHOW_LABELS:-}" == "false" ]]; then
            log_info "📝 Compiling with labels hidden (override)"
            latexmk_opts+=("-usepretex=\\def\\HideLabelsOverride{}\\def\\OnlineAppendixHandling{${ONLINE_APPENDIX_HANDLING}}")
        else
            # No override - use default from .tex file
            latexmk_opts+=("-usepretex=\\def\\OnlineAppendixHandling{${ONLINE_APPENDIX_HANDLING}}")
        fi
    else
        # Draft mode requested but not applicable to this document
        latexmk_opts+=("-usepretex=\\def\\OnlineAppendixHandling{${ONLINE_APPENDIX_HANDLING}}")
    fi
    
    # Handle dry-run mode
    if [[ "$DRY_RUN" == true ]]; then
        # Show the command that would be executed
        echo "# Compiling: $doc_path"
        if [[ "$CLEAN_FIRST" == "true" ]]; then
            echo "latexmk -c \"$doc_path\""
        fi
        
        # Format command with proper shell escaping for copy-paste usage
        local escaped_opts=()
        for opt in "${latexmk_opts[@]}"; do
            # Escape backslashes for shell copy-paste and quote the option if it contains special characters
            if [[ "$opt" == *"\\"* ]] || [[ "$opt" == *"{"* ]] || [[ "$opt" == *"}"* ]]; then
                # Double the backslashes and quote the entire option
                escaped_opt=${opt//\\/\\\\}
                escaped_opts+=("\"$escaped_opt\"")
            else
                escaped_opts+=("$opt")
            fi
        done
        
        echo "latexmk" "${escaped_opts[@]}" "\"$doc_path\""
        echo ""
        return 0
    fi
    
    log_info "Compiling: $doc_path"
    
    if [[ "$CLEAN_FIRST" == "true" ]]; then
        if [[ "$needs_cd" == "true" ]]; then
            (cd "$doc_dir" && latexmk -c "$doc_file") >/dev/null 2>&1 || true
        else
            latexmk -c "$doc_path" >/dev/null 2>&1 || true
        fi
    fi
    
    # PDF viewer management integration
    
    local start_time
    start_time=$(date +%s)
    
    # Ensure TEXINPUTS is exported and available to latexmk/pdflatex
    # This is critical for finding @local/owner.tex and other local files
    export TEXINPUTS
    
    if [[ "$REPRODUCTION_MODE" == "quick" ]]; then
        # Try compilation first
        local compile_result
        if [[ "$needs_cd" == "true" ]]; then
            (cd "$doc_dir" && latexmk "${latexmk_opts[@]}" "$doc_file")
            compile_result=$?
        else
            latexmk "${latexmk_opts[@]}" "$doc_path"
            compile_result=$?
        fi
        
        if [[ $compile_result -eq 0 ]]; then
            local end_time
            end_time=$(date +%s)
            log_success "$doc_name completed in $((end_time - start_time))s (quick mode)"
            # DEFERRED:             cleanup_auxiliary_files "$doc_path" "$doc_name"
        else
            # If latexmk fails, clean and retry once
            log_info "Cleaning and retrying $doc_name..."
            if [[ "$needs_cd" == "true" ]]; then
                (cd "$doc_dir" && latexmk -c "$doc_file") >/dev/null 2>&1 || true
                (cd "$doc_dir" && latexmk "${latexmk_opts[@]}" "$doc_file")
                compile_result=$?
            else
                latexmk -c "$doc_path" >/dev/null 2>&1 || true
                latexmk "${latexmk_opts[@]}" "$doc_path"
                compile_result=$?
            fi
            
            if [[ $compile_result -eq 0 ]]; then
                local end_time
                end_time=$(date +%s)
                log_success "$doc_name completed in $((end_time - start_time))s (quick mode - retry)"
            # DEFERRED:                 cleanup_auxiliary_files "$doc_path" "$doc_name"
            else
                # Check if PDF was generated despite error
                local pdf_output="${doc_path%.tex}.pdf"
                if [[ -f "$pdf_output" ]]; then
                    local end_time
                    end_time=$(date +%s)
                    log_warning "$doc_name: latexmk reported error but PDF was generated"
                    log_success "$doc_name completed in $((end_time - start_time))s (quick mode - with warnings)"
            # DEFERRED:                     cleanup_auxiliary_files "$doc_path" "$doc_name"
                else
                    log_error "$doc_name compilation failed"
                    # Enhanced error analysis
                    local log_file="${doc_path%.tex}.log"
                    if [[ -f "$log_file" ]]; then
                        parse_latex_error "$log_file" "$doc_name"
                    fi
                    return 1
                fi
            fi
        fi
    else
        # Full mode: latexmk handles bibtex and initial pdflatex passes
        local compile_result
        if [[ "$needs_cd" == "true" ]]; then
            (cd "$doc_dir" && latexmk "${latexmk_opts[@]}" "$doc_file")
            compile_result=$?
        else
            latexmk "${latexmk_opts[@]}" "$doc_path"
            compile_result=$?
        fi
        
        # Check if PDF was generated (compile_result may be non-zero for warnings)
        local pdf_check="${doc_path%.tex}.pdf"
        if [[ "$needs_cd" == "true" ]]; then
            pdf_check="$doc_dir/${doc_file%.tex}.pdf"
        fi
        
        if [[ ! -f "$pdf_check" ]]; then
            # No PDF generated - actual failure
            log_error "$doc_name compilation failed"
            local log_file="${doc_path%.tex}.log"
            if [[ -f "$log_file" ]]; then
                parse_latex_error "$log_file" "$doc_name"
            fi
            return 1
        fi
        
        # Run additional pdflatex passes to resolve remaining undefined references
        # (latexmk may stop early when bibtex doesn't produce changes)
        local log_file="${doc_path%.tex}.log"
        if [[ "$needs_cd" == "true" ]]; then
            log_file="$doc_dir/${doc_file%.tex}.log"
        fi
        
        # Check for undefined references and run extra passes if needed
        local max_extra_passes=2
        local pass=0
        while [[ $pass -lt $max_extra_passes ]]; do
            if grep -q "undefined" "$log_file" 2>/dev/null; then
                ((pass++))
                if [[ "$VERBOSE" == "true" ]]; then
                    echo "  Extra pass $pass to resolve remaining references..."
                fi
                if [[ "$needs_cd" == "true" ]]; then
                    (cd "$doc_dir" && pdflatex -interaction=nonstopmode "$doc_file") >/dev/null 2>&1
                else
                    pdflatex -interaction=nonstopmode "$doc_path" >/dev/null 2>&1
                fi
            else
                break
            fi
        done
        
        local end_time
        end_time=$(date +%s)
        log_success "$doc_name completed in $((end_time - start_time))s (full mode)"
    fi
    
    # Clean up auxiliary files after successful compilation
            # DEFERRED:     cleanup_auxiliary_files "$doc_path" "$doc_name"
    
    # Verify output (after cleanup to avoid any interference)
    # Check for draft mode output filename first, then regular filename
    local pdf_output="${doc_path%.tex}.pdf"
    if [[ "$current_draft_mode" == "true" ]] && [[ "$REPO_TYPE" == "QE" ]] && [[ "$doc_name" == "HAFiscal" ]]; then
        pdf_output="HAFiscal-draft.pdf"
    fi
    
    if [[ -f "$pdf_output" ]]; then
        local pdf_size
        pdf_size=$(stat -f%z "$pdf_output" 2>/dev/null || stat -c%s "$pdf_output" 2>/dev/null || echo "unknown")
        log_info "Generated: $pdf_output ($pdf_size bytes)"
    fi
    
    # Final cleanup to ensure any files created during verification are removed
    if [[ "$DRY_RUN" != true ]]; then
        local doc_dir
        doc_dir=$(dirname "$doc_path")
        local doc_basename
        doc_basename=$(basename "$doc_path" .tex)
        
        # For non-root documents, ensure .txt and .dep files are removed
        if [[ -n "$doc_dir" && "$doc_dir" != "." ]]; then
            (cd "$doc_dir" && rm -f "${doc_basename}.txt" "${doc_basename}.dep" >/dev/null 2>&1) || true
        fi
    fi
    
    return 0
}

main() {
    local targets=()
    local single_document=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --quick|-q)
                REPRODUCTION_MODE="quick"
                shift
                ;;
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --clean|-c)
                CLEAN_FIRST=true
                shift
                ;;
            --draft)
                DRAFT_MODE_ENABLED="true"
                shift
                ;;
            --single)
                if [[ -n "${2:-}" ]]; then
                    single_document="$2"
                    shift 2
                else
                    log_error "--single requires a document name"
                    exit 1
                fi
                ;;
            --list)
                list_documents
                exit 0
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --stop-on-error)
                STOP_ON_ERROR=true
                shift
                ;;
            --scope)
                if [[ -n "${2:-}" && "$2" =~ ^(main|all|figures|tables|subfiles)$ ]]; then
                    SCOPE="$2"
                    shift 2
                else
                    log_error "--scope requires one of: main, all, figures, tables, subfiles"
                    exit 1
                fi
                ;;
            -*)
                log_error "Unknown option: $1"
                exit 1
                ;;
            *)
                targets+=("$1")
                shift
                ;;
        esac
    done
    
    # Check SHOW_LABELS environment variable (from parent reproduce.sh)
    if [[ -n "${SHOW_LABELS:-}" ]]; then
        case "$SHOW_LABELS" in
            true)
                DRAFT_MODE_ENABLED="true"
                log_info "Show labels mode enabled via SHOW_LABELS environment variable"
                ;;
            false)
                DRAFT_MODE_ENABLED="false"
                log_info "Show labels mode disabled via SHOW_LABELS environment variable"
                ;;
        esac
    fi
    
    # Check environment variable if command-line flag not set
    if [[ "$DRAFT_MODE_ENABLED" != "true" ]] && [[ -n "${DRAFT_MODE:-}" ]]; then
        case "$DRAFT_MODE" in
            1|true|yes|TRUE|YES)
                DRAFT_MODE_ENABLED="true"
                log_info "Draft mode enabled via DRAFT_MODE environment variable"
                ;;
        esac
    fi
    
    # Change to project root if we're in reproduce/ directory
    if [[ "$(basename "$(pwd)")" == "reproduce" ]]; then
        cd ..
    fi

    # Fetch bibliography from with-precomputed-artifacts if needed
    fetch_bibliography_if_needed

    # Validate and setup
    if ! validate_environment; then
        exit 1
    fi
    
    setup_build_environment
    
    # Detect repository type for draft mode handling
    if [[ -f "HAFiscal.tex" ]]; then
        REPO_TYPE="QE"
        if [[ "$VERBOSE" == "true" ]]; then
            log_info "Repository type: QE"
        fi
    else
        REPO_TYPE="STANDARD"
        if [[ "$VERBOSE" == "true" ]]; then
            log_info "Repository type: Latest/Public"
        fi
    fi
    
    log_info "Starting HAFiscal document reproduction (mode: $REPRODUCTION_MODE)"
    
    # Handle single document compilation
    if [[ -n "$single_document" ]]; then
        compile_document "$single_document"
        exit $?
    fi
    
    # Set default behavior (no specific targets needed as scope handles discovery)
    if [[ ${#targets[@]} -eq 0 ]]; then
        targets=()  # Empty targets is fine, scope-based discovery handles it
    fi
    
    # Resolve targets to document paths based on scope
    local docs_to_compile=()
    
    # Discover available root files (for validation and potential inclusion)
    local root_tex_files=()
    while IFS= read -r -d '' file; do
        root_tex_files+=("$(basename "$file")")
    done < <(find . -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 | sort -z)
    
    if [[ ${#root_tex_files[@]} -eq 0 ]]; then
        log_error "No .tex files found in repo root directory"
        exit 1
    fi
    
    # Add files to compilation list based on scope
    case "$SCOPE" in
        "main")
            log_info "Scope: main - compiling only repo root files"
            log_info "Found ${#root_tex_files[@]} .tex files in repo root:"
            for file in "${root_tex_files[@]}"; do
                log_info "  - $file"
            done
            docs_to_compile+=("${root_tex_files[@]}")
            ;;
        "all")
            log_info "Scope: all - including Figures/, Tables/, and Subfiles/"
            
            # Include root files
            log_info "Found ${#root_tex_files[@]} .tex files in repo root:"
            for file in "${root_tex_files[@]}"; do
                log_info "  - $file"
            done
            docs_to_compile+=("${root_tex_files[@]}")
            
            # Add .tex files from Figures/
            if [[ -d "Figures" ]]; then
                local figures_files=()
                while IFS= read -r -d '' file; do
                    figures_files+=("$file")
                done < <(find Figures -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#figures_files[@]} -gt 0 ]]; then
                    log_info "Found ${#figures_files[@]} .tex files in Figures/:"
                    for file in "${figures_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${figures_files[@]}")
                fi
            fi
            
            # Add .tex files from Tables/
            if [[ -d "Tables" ]]; then
                local tables_files=()
                while IFS= read -r -d '' file; do
                    tables_files+=("$file")
                done < <(find Tables -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#tables_files[@]} -gt 0 ]]; then
                    log_info "Found ${#tables_files[@]} .tex files in Tables/:"
                    for file in "${tables_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${tables_files[@]}")
                fi
            fi
            
            # Add .tex files from Subfiles/
            if [[ -d "Subfiles" ]]; then
                local subfiles_files=()
                while IFS= read -r -d '' file; do
                    subfiles_files+=("$file")
                done < <(find Subfiles -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#subfiles_files[@]} -gt 0 ]]; then
                    log_info "Found ${#subfiles_files[@]} .tex files in Subfiles/:"
                    for file in "${subfiles_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${subfiles_files[@]}")
                fi
            fi
            ;;
        "figures")
            log_info "Scope: figures - including Figures/"
            
            # Add .tex files from Figures/
            if [[ -d "Figures" ]]; then
                local figures_files=()
                while IFS= read -r -d '' file; do
                    figures_files+=("$file")
                done < <(find Figures -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#figures_files[@]} -gt 0 ]]; then
                    log_info "Found ${#figures_files[@]} .tex files in Figures/:"
                    for file in "${figures_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${figures_files[@]}")
                fi
            fi
            ;;
        "tables")
            log_info "Scope: tables - including Tables/"
            
            # Add .tex files from Tables/
            if [[ -d "Tables" ]]; then
                local tables_files=()
                while IFS= read -r -d '' file; do
                    tables_files+=("$file")
                done < <(find Tables -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#tables_files[@]} -gt 0 ]]; then
                    log_info "Found ${#tables_files[@]} .tex files in Tables/:"
                    for file in "${tables_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${tables_files[@]}")
                fi
            fi
            ;;
        "subfiles")
            log_info "Scope: subfiles - including Subfiles/"
            
            # Add .tex files from Subfiles/
            if [[ -d "Subfiles" ]]; then
                local subfiles_files=()
                while IFS= read -r -d '' file; do
                    subfiles_files+=("$file")
                done < <(find Subfiles -maxdepth 1 -name "*.tex" -type f ! -name ".*" -print0 2>/dev/null | sort -z)
                
                if [[ ${#subfiles_files[@]} -gt 0 ]]; then
                    log_info "Found ${#subfiles_files[@]} .tex files in Subfiles/:"
                    for file in "${subfiles_files[@]}"; do
                        log_info "  - $file"
                    done
                    docs_to_compile+=("${subfiles_files[@]}")
                fi
            fi
            ;;
    esac
    
    # Handle specific targets if any were provided (legacy behavior)
    local target
    for target in "${targets[@]}"; do
        if [[ "$target" != "all" ]]; then
            local resolved_doc
            resolved_doc=$(resolve_document "$target")
            docs_to_compile+=("$resolved_doc")
        fi
    done
    
    # Remove duplicates
    local unique_docs=()
    local doc existing found
    for doc in "${docs_to_compile[@]}"; do
        found=false
        for existing in "${unique_docs[@]}"; do
            if [[ "$doc" == "$existing" ]]; then
                found=true
                break
            fi
        done
        if [[ "$found" == "false" ]]; then
            unique_docs+=("$doc")
        fi
    done
    
    # Compile documents
    local success_count=0
    local total_count=${#unique_docs[@]}
    local current=0
    
    log_info "Compiling $total_count document(s)..."
    echo ""
    
    for doc in "${unique_docs[@]}"; do
        ((++current))
        echo "========================================"
        echo "📄 Document $current/$total_count: $(basename "$doc")"
        echo "========================================"
        
        if compile_document "$doc"; then
            ((++success_count))
        else
            # Document failed - check if we should stop
            if [[ "${STOP_ON_ERROR:-false}" == "true" ]]; then
                echo ""
                echo "========================================"
                log_error "Stopping due to compilation failure (STOP_ON_ERROR=true)"
                log_error "Failed on: $doc"
                log_info "Compiled successfully: $success_count/$current documents"
                echo "========================================"
                exit 1
            fi
        fi
        echo ""
    done
    
    
    # ========================================
    # GLOBAL CLEANUP: Clean auxiliary files after all documents compiled
    # ========================================
    echo ""
    echo "========================================"
    log_info "Cleaning auxiliary files for all documents..."
    echo "========================================"
    
    for doc in "${unique_docs[@]}"; do
        doc_name=$(basename "$doc" .tex)
        echo "  🧹 Cleaning: $doc_name"
        cleanup_auxiliary_files "$doc" "$doc_name"
    done
    
    log_success "Cleanup completed for all documents"
    echo ""
    echo "========================================"
    log_info "Reproduction completed: $success_count/$total_count documents successful"
    
    # Check if using precomputed artifacts and warn if so
    PREGENERATED_FLAG="./reproduce/.results_pregenerated"
    if [[ -f "$PREGENERATED_FLAG" ]]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "⚠️  WARNING: DOCUMENTS COMPILED WITH PRECOMPUTED ARTIFACTS"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "The compiled documents include figures and tables generated from"
        echo "precomputed results that were NOT freshly computed in this session."
        echo ""
        echo "This means you have NOT run the full computational reproduction."
        echo ""
        echo "To run a complete, from-scratch reproduction:"
        echo "  ./reproduce.sh --comp full"
        echo ""
        echo "The full reproduction takes 4-5 days on a high-end 2025 laptop but provides complete verification"
        echo "of all computational results shown in the documents."
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    fi

    # Clean up fetched bibliography file - ONLY if we fetched it (didn't exist at start)
    # FETCHED_BIBLIOGRAPHY is only true if the file was absent and we fetched it
    if [[ "$FETCHED_BIBLIOGRAPHY" == "true" ]]; then
        echo ""
        echo "→ Cleaning up fetched HAFiscal.bib..."
        if [[ -f "HAFiscal.bib" ]]; then
            rm -f HAFiscal.bib
            echo "  ✓ Removed HAFiscal.bib"
        fi
        echo "✅ Cleanup complete - working tree is clean"
    fi

    if [[ $success_count -eq $total_count ]]; then
        log_success "All documents compiled successfully!"
        exit 0
    else
        log_error "Some documents failed to compile"
        exit 1
    fi
}

# Run main function with all arguments
main "$@" 
