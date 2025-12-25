#!/bin/bash
# SCRIPT_TYPE: orchestrator
# SCRIPT_PURPOSE: Create HAFiscal-QE repository from HAFiscal-Public for Quantitative Economics submission
# Usage: ./make-repo-Public-to-QE.sh
#
# To push to remote after creation, run:
#   ./post-QE.sh
#
# This script creates a clean QE-optimized repository from HAFiscal-Public by:
# 1. Syncing base content from Public
# 2. Removing development files and infrastructure
# 3. Simplifying for journal submission
# 4. Creating two branches for different use cases
#
# BRANCH STRUCTURE:
#   - main: QE submission version (no generated files, .bib excluded)
#   - with-precomputed-artifacts: includes .bib and data files (DEFAULT)
#
# The 'with-precomputed-artifacts' branch is set as default for:
#   - Direct upload to Overleaf (repository has no symlinks in tracked files)
#   - Default clone experience for reproducibility
#   - Pull request targets
#
# EXCLUSION STRATEGY (SST):
#   - General patterns:      make-repo-Public-to-QE_excludes.txt (--exclude-from)
#   - Project-specific:      Inline --exclude with ${PROJECT_NAME} variable
#   This follows the same pattern as make-repo-Latest-to-Public.sh for consistency
#
# Created: 2025-10-09
# Based on: make-Latest-to-Public.sh structure

set -euo pipefail

# OS detection for sed -i compatibility (macOS vs Linux)
# macOS requires '', Linux doesn't
if [[ "$(uname)" == "Darwin" ]]; then
    SED_INPLACE=(-i '')
else
    SED_INPLACE=(-i)
fi

# Parse command line arguments
for arg in "$@"; do
    case "$arg" in
        --help|-h)
            echo "Usage: make-repo-Public-to-QE.sh"
            echo ""
            echo "Creates HAFiscal-QE repository from HAFiscal-Public."
            echo "Does NOT push to remote (use ./post-QE.sh for that)."
            echo ""
            echo "Environment Variables:"
            echo "  VERBOSITY_LEVEL=normal|verbose  Logging verbosity"
            echo ""
            exit 0
            ;;
    esac
done

# Enhanced error trapping
trap 'echo "❌ ERROR in make-repo-Public-to-QE.sh at line $LINENO: Command failed with exit code $?" >&2' ERR

# Source paths.sh to get standardized path variables
source "$(git rev-parse --show-toplevel 2>/dev/null)/scripts/utils/paths.sh" "QE" "orchestrator"

# Load utility functions
source "$MAKE_ROOT/scripts/utils/project-utils.sh"

# Initialize dual-variable verbosity system
init_verbosity_system
setup_build_environment
setup_logging_environment

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_NAME="${PROJECT_NAME:-HAFiscal}"
ghID="llorracc"

log_major_section "Creating HAFiscal-QE from HAFiscal-Public"
log_info "Source: $PUBLIC_ROOT"
log_info "Target: $QE_ROOT"

# =============================================================================
# STEP 1: PRE-FLIGHT CHECKS
# =============================================================================

check_public_repo_clean() {
    log_major_section "Pre-flight checks"
    
    # Check if Public repository exists
    if [[ ! -d "$PUBLIC_ROOT" ]]; then
        log_error "HAFiscal-Public directory not found at: $PUBLIC_ROOT"
        log_error "To build HAFiscal-Public, run:"
        log_error "  1. ./make-Latest-to-Public.sh       (sync and transform)"
        log_error "  2. ./makePDF-Portable-Public.sh (build PDF)"
        log_error "  3. ./makeWeb-HEAD-Public.sh     (build HTML)"
        log_info "Or use the orchestrator: ./make-Latest-to-Public-to-QE.sh (recommended)"
        exit 1
    fi
    
    # Check if Public has clean git state
    log_info "Checking HAFiscal-Public git state..."
    cd "$PUBLIC_ROOT"
    if [[ -n $(git status --porcelain 2>/dev/null) ]]; then
        log_warning "HAFiscal-Public has uncommitted changes"
        log_info "Continuing anyway - QE will sync current Public state"
    else
        log_success "HAFiscal-Public is clean"
    fi
    
    # Check if essential files exist
    if [[ ! -f "$PUBLIC_ROOT/$PROJECT_NAME.tex" ]]; then
        log_error "$PROJECT_NAME.tex not found in Public repository"
        exit 1
    fi
    
    log_success "✅ Pre-flight checks passed"
    cd "$MAKE_ROOT"
}

# =============================================================================
# STEP 1.5: VERIFY .BIB FILE EXISTS IN PUBLIC
# =============================================================================

verify_bib_exists() {
    log_major_section "Verifying bibliography source file exists"
    
    cd "$PUBLIC_ROOT"
    
    # Check if .bib file exists
    if [[ ! -f "$PROJECT_NAME.bib" ]]; then
        log_error "❌ CRITICAL: $PROJECT_NAME.bib not found in $PUBLIC_ROOT"
        log_error ""
        log_error "The bibliography source file is required to generate .bbl file."
        log_error ""
        log_error "QE journal requires:"
        log_error "  - .bbl file (compiled bibliography) on main branch"
        log_error "  - .bib file (source) on with-precomputed-artifacts branch only"
        log_error ""
        log_error "ACTION REQUIRED:"
        log_error "  The .bib file should NEVER be deleted from HAFiscal-Latest or HAFiscal-Public."
        log_error "  It is only excluded from HAFiscal-QE main branch (kept in with-precomputed-artifacts)."
        log_error ""
        log_error "To fix:"
        log_error "  cd HAFiscal-Latest"
        log_error "  git show 82de134e^:HAFiscal.bib > HAFiscal.bib  # Restore from git history"
        log_error "  # Or copy from HAFiscal-reproduce if available"
        log_error "  git add HAFiscal.bib"
        log_error "  git commit -m 'Restore HAFiscal.bib (required for .bbl generation)'"
        log_error "  git push"
        log_error ""
        log_error "  Then run make-Latest-to-Public.sh to sync to Public"
        log_error ""
        exit 1
    fi
    
    log_success "✓ Found $PROJECT_NAME.bib ($(wc -l < "$PROJECT_NAME.bib" | tr -d ' ') lines)"
    log_info "  Will be synced to QE repo for paper compilation with qe.bst style"
    log_info ""
    
    cd "$MAKE_ROOT"
}

# =============================================================================
# STEP 2: SETUP QE REPOSITORY
# =============================================================================

setup_qe_repo() {
    log_major_section "Setting up HAFiscal-QE repository"
    
    # Check if QE repo already exists locally
    if [[ -d "$QE_ROOT" ]]; then
        log_info "QE repository already exists at: $QE_ROOT"
        
        # Check if it's a git repository
        if [[ -d "$QE_ROOT/.git" ]]; then
            log_success "Using existing git repository"
        else
            log_info "Directory exists but is not a git repository - initializing..."
            cd "$QE_ROOT"
            git init
            git config --local core.autocrlf false
            git config --local core.filemode false
            cd "$MAKE_ROOT"
        fi
    else
        log_info "Creating new HAFiscal-QE directory..."
        mkdir -p "$QE_ROOT"
        
        cd "$QE_ROOT"
        git init
        git config --local core.autocrlf false
        git config --local core.filemode false
        log_success "✅ Git repository initialized"
        cd "$MAKE_ROOT"
    fi
    
    # Check if remote repository exists on GitHub
    log_info "Checking GitHub remote repository status..."
    if gh repo view "$ghID/$PROJECT_NAME-QE" >/dev/null 2>&1; then
        log_success "GitHub repository $ghID/$PROJECT_NAME-QE already exists"
        
        # Verify and correct remote configuration
        cd "$QE_ROOT"
        EXPECTED_REMOTE="https://github.com/$ghID/$PROJECT_NAME-QE.git"
        
        if git remote get-url origin >/dev/null 2>&1; then
            CURRENT_REMOTE=$(git remote get-url origin)
            if [[ "$CURRENT_REMOTE" != "$EXPECTED_REMOTE" ]]; then
                log_warning "Remote URL incorrect: $CURRENT_REMOTE"
                log_info "Correcting remote URL to: $EXPECTED_REMOTE"
                git remote set-url origin "$EXPECTED_REMOTE"
                log_success "✅ Remote URL corrected"
            else
                log_success "Remote URL is correct: $EXPECTED_REMOTE"
            fi
        else
            log_info "Adding remote origin..."
            git remote add origin "$EXPECTED_REMOTE"
            log_success "✅ Remote origin added"
        fi
        cd "$MAKE_ROOT"
    else
        log_info "GitHub repository does not exist - it exists locally only"
        log_info "To create it on GitHub, run: gh repo create $ghID/$PROJECT_NAME-QE --public --source $QE_ROOT --remote origin"
    fi
}

# =============================================================================
# STEP 3: SYNC BASE CONTENT FROM PUBLIC
# =============================================================================
# CREATE PREGENERATED FLAG FILE
# =============================================================================
# Creates flag file that signals table/figure captions should show PREGENERATED marker
# This flag is removed by reproduce_documents.sh after successful computation

create_pregenerated_flag() {
    log_major_section "Creating PREGENERATED flag file"
    
    cd "$QE_ROOT"
    
    # Create tabular directory if it doesn't exist
    mkdir -p reproduce
    
    # Create flag file
    touch reproduce/.results_pregenerated
    
    log_success "✅ Created reproduce/.results_pregenerated flag file"
    log_info "    Table and figure captions will show 'PREGENERATED: ' prefix until computation completes"
    log_info "    Flag will be removed by reproduce_documents.sh after successful --comp all"
    
    cd "$MAKE_ROOT"
}

# =============================================================================

sync_from_public() {
    log_major_section "Syncing base content: Public → QE"

    # Make HAFiscal.bib writable before rsync (read-only protection)
    if [[ -f "$QE_ROOT/$PROJECT_NAME.bib" ]]; then
        log_verbose "Making existing $PROJECT_NAME.bib writable for rsync update"
        chmod +w "$QE_ROOT/$PROJECT_NAME.bib" || true
    fi

    # Sync core content from Public to QE
    # Keep essential LaTeX structure but exclude development infrastructure
    log_info "Running rsync from Public to QE..."
    
    # SST: Use external file for general patterns, inline for project-specific
    #
    # NOTE: rsync can legitimately return code 24 ("some files vanished") if files are being
    # written/rotated by other processes while syncing (for example transient results files).
    # In this workflow, a small number of vanished files is not necessarily fatal, so we treat
    # exit code 24 as a warning and continue.
    set +e
    rsync \
      -azh \
      --chmod=a+rw \
      --delete --delete-before \
      --ignore-times --modify-window=0 \
      --exclude-from="$MAKE_ROOT/make-repo-Public-to-QE_excludes.txt" \
      --exclude="${PROJECT_NAME}.tex" \
      --exclude="${PROJECT_NAME}-Slides.pdf" \
      --exclude="${PROJECT_NAME}-Slides.tex" \
      --exclude="${PROJECT_NAME}-dashboard.ipynb" \
      --exclude="${PROJECT_NAME}-jupyterlab.ipynb" \
      "$PUBLIC_ROOT/" "$QE_ROOT/"
    local rsync_exit=$?
    set -e

    if [[ $rsync_exit -ne 0 ]]; then
        if [[ $rsync_exit -eq 24 ]]; then
            log_warning "rsync reported vanished files (exit code 24). Continuing."
        else
            log_error "rsync failed with exit code: $rsync_exit"
            exit "$rsync_exit"
        fi
    fi
    
    log_success "✅ Base content synced from Public to QE"
    
    # Debug: Check if image PDFs were copied
    log_info "DEBUG: Checking if image PDFs were copied..."
    if ls "$QE_ROOT/images/"*.pdf >/dev/null 2>&1; then
        log_success "✓ Image PDFs found in QE: $(ls "$QE_ROOT/images/"*.pdf 2>/dev/null | wc -l | tr -d ' ') files"
    else
        log_warning "⚠ No image PDFs found in QE after rsync"
    fi
    
    log_info "HAFiscal.tex excluded from sync (will be created by build-QE-submission-PDFs.sh)"
    # Verify essential files were synced
    if [[ ! -f "$QE_ROOT/Subfiles.ltx" ]]; then
        log_error "Subfiles.ltx not found after sync: $QE_ROOT/Subfiles.ltx"
        exit 1
    fi
    
    log_success "✅ Essential files verified"
    
    # Ensure compliance directory exists for generated reports
    if [[ ! -d "$QE_ROOT/qe/compliance" ]]; then
        log_info "Creating qe/compliance/ directory for generated reports..."
        mkdir -p "$QE_ROOT/qe/compliance"
        log_success "Created qe/compliance/ directory"
    fi
    
    # Clean up old compliance reports (keep only latest or none)
    # Old reports accumulate from previous syncs because qe/ is excluded from rsync
    log_info "Cleaning up old compliance reports from qe/compliance/..."
    local deleted_reports=0
    if [[ -d "$QE_ROOT/qe/compliance" ]]; then
        # Delete all timestamped compliance reports
        for pattern in "QE-COMPLIANCE-REPORT_*.md" "QE-COMPLIANCE-CHECKLIST_*.md"; do
            while IFS= read -r -d '' report; do
                rm -f "$report"
                ((deleted_reports+=1))
            done < <(find "$QE_ROOT/qe/compliance" -maxdepth 1 -name "$pattern" -print0 2>/dev/null)
        done
        
        # Also remove LATEST symlinks (will be regenerated if needed)
        rm -f "$QE_ROOT/qe/compliance/QE-COMPLIANCE-REPORT-LATEST.md"
        rm -f "$QE_ROOT/qe/compliance/QE-COMPLIANCE-CHECKLIST-LATEST.md"
        
        if [[ $deleted_reports -gt 0 ]]; then
            log_success "✓ Deleted $deleted_reports old compliance report(s)"
        else
            log_info "  No old compliance reports to delete"
        fi
    fi
    
    # NOTE: qe/requirements/ will be copied AFTER orphan branch creation
    # (doing it here would be lost when orphan branch resets working directory)
    
    # =============================================================================
    # TRANSFORM REPOSITORY-SPECIFIC CONTENT
    # =============================================================================
    log_minor_section "Transforming repository-specific content for QE"
    
    # Transform Dockerfile: Update symlink path from HAFiscal-Public to HAFiscal-QE
    if [[ -f "$QE_ROOT/Dockerfile" ]]; then
        log_info "Transforming Dockerfile symlink path..."
        
        # Check if transformation is needed
        if grep -q "HAFiscal-Public" "$QE_ROOT/Dockerfile"; then
            # Create backup (in case of errors)
            cp "$QE_ROOT/Dockerfile" "$QE_ROOT/Dockerfile.backup" 2>/dev/null || true
            
            # Transform HAFiscal-Public to HAFiscal-QE
            if sed "${SED_INPLACE[@]}" 's|/workspaces/HAFiscal-Public|/workspaces/HAFiscal-QE|g' "$QE_ROOT/Dockerfile"; then
                log_success "  ✓ Updated Dockerfile symlink path: HAFiscal-Public → HAFiscal-QE"
                
                # Verify transformation succeeded
                if grep -q "HAFiscal-Public" "$QE_ROOT/Dockerfile"; then
                    log_error "  ❌ Transformation incomplete - HAFiscal-Public still present"
                    exit 1
                fi
                
                # Show the changed line for verification
                CHANGED_LINE=$(grep -n "/workspaces/HAFiscal-QE" "$QE_ROOT/Dockerfile" | head -1)
                log_info "  Changed line: $CHANGED_LINE"
                
                # Remove backup if successful
                rm -f "$QE_ROOT/Dockerfile.backup" 2>/dev/null || true
            else
                log_error "  ❌ Failed to transform Dockerfile"
                # Restore backup if sed failed
                if [[ -f "$QE_ROOT/Dockerfile.backup" ]]; then
                    mv "$QE_ROOT/Dockerfile.backup" "$QE_ROOT/Dockerfile"
                    log_info "  Restored Dockerfile from backup"
                fi
                exit 1
            fi
        else
            log_info "  ✓ Dockerfile already has correct path (HAFiscal-QE)"
        fi
    else
        log_warning "  ⚠️ Dockerfile not found in QE repository"
    fi
    
    # Transform .dockerignore: Update comment from HAFiscal-Public to HAFiscal-QE
    if [[ -f "$QE_ROOT/.dockerignore" ]]; then
        log_info "Transforming .dockerignore comments..."
        
        # Check if transformation is needed
        if grep -q "HAFiscal-Public" "$QE_ROOT/.dockerignore"; then
            # Transform comment
            if sed "${SED_INPLACE[@]}" 's|HAFiscal-Public|HAFiscal-QE|g' "$QE_ROOT/.dockerignore"; then
                log_success "  ✓ Updated .dockerignore comment: HAFiscal-Public → HAFiscal-QE"
            else
                log_warning "  ⚠️ Failed to transform .dockerignore (non-critical)"
            fi
        else
            log_info "  ✓ .dockerignore already has correct reference (HAFiscal-QE)"
        fi
    else
        log_warning "  ⚠️ .dockerignore not found in QE repository"
    fi
    
    log_success "✅ Repository-specific content transformed for QE"
    
    # =============================================================================
    # DELETE QE-INAPPROPRIATE FILES (if they exist)
    # =============================================================================
    log_minor_section "Cleaning up QE-inappropriate files"
    
    # Files that should not exist in QE submission
    local files_to_delete=(
        "econark.bst"                           # Use qe.bst instead
        "REPRODUCE_SH_MODIFICATION_SUMMARY.md"  # Development documentation
        "REMARK.md"                             # REMARK-specific README
        "DO-NOT-EDIT-THIS-REPOSITORY.md"        # Public warning (not needed for QE)
        "._relpath-to-latexroot.ltx"           # Path configuration (not needed in QE)
        ".cursorindexingignore.additions"       # Development config
        ".editorconfig"                         # Development config
        "HAFiscal_paperpile.bib"                # Paperpile metadata
        "README-QE.md"                          # QE-specific README (handled separately)
        "reproduce_min.sh"                      # Minimal reproduction script (not for QE)
        "reproduce/build-provenance.md"         # Build provenance documentation
        "reproduce_html_README.md"              # HTML reproduction README
        "HAFiscal.md"                           # Markdown version (not needed for QE)
        "@resources/texlive/texmf-local/bibtex/bst/econark.bst"  # Use qe.bst instead
    )
    # CHANGED 2025-12-17: NOW KEEPING in QE for modern best practices:
    #   - CITATION.cff: GitHub citation integration (QE recommends)
    #   - codemeta.json: Software metadata standard
    #   - schema.json: Search engine structured data
    #   - .zenodo.json: Rich Zenodo archival metadata
    # Rationale: Improves discoverability, citability, reproducibility with no downside
    
    local files_kept_for_metadata=(
        "CITATION.cff"                          # Kept: GitHub citation, QE recommended
        "codemeta.json"                         # Kept: Software metadata standard
        "schema.json"                           # Kept: Search engine indexing
        # .zenodo.json kept automatically (not in removal list)
    )

    # Delete specific files
    for file in "${files_to_delete[@]}"; do
        if [[ -f "$QE_ROOT/$file" ]]; then
            log_info "Deleting: $file"
            rm -f "$QE_ROOT/$file"
        fi
    done

    # Keep LICENSE file (required by QE compliance checker B.3)
    # QE requires an open license (CC BY, MIT, Apache, etc.)
    if [[ -f "$QE_ROOT/LICENSE" ]]; then
        log_info "Keeping LICENSE file (required for QE compliance)"
    elif [[ -f "$PUBLIC_ROOT/LICENSE" ]]; then
        log_info "Copying LICENSE file from Public (required for QE compliance)"
        cp "$PUBLIC_ROOT/LICENSE" "$QE_ROOT/LICENSE"
        log_success "  ✓ LICENSE file copied"
    else
        log_warning "⚠ LICENSE file not found in Public - QE compliance check B.3 will fail"
        log_warning "  Consider adding a LICENSE file (e.g., Apache 2.0, MIT, CC BY 4.0)"
    fi
    
    # Delete all *_paperpile.bib files (Paperpile metadata)
    local paperpile_count=0
    while IFS= read -r -d '' paperpile_file; do
        log_info "Deleting: $(basename "$paperpile_file")"
        rm -f "$paperpile_file"
        ((paperpile_count++))
    done < <(find "$QE_ROOT" -name '*_paperpile.bib' -print0 2>/dev/null)
    
    if [[ $paperpile_count -gt 0 ]]; then
        log_info "Deleted $paperpile_count paperpile bibliography files"
    fi

    # NOTE: .bib files are NOT deleted here - they will be preserved in
    # with-precomputed-artifacts branch and deleted by purge script later

    # Delete emacs auto-save files (#*#)
    local emacs_count=0
    log_info "Searching for emacs auto-save files (#*#) in $QE_ROOT..."
    while IFS= read -r -d '' emacs_file; do
        log_info "Deleting: $emacs_file"
        rm -f "$emacs_file"
        ((emacs_count++))
    done < <(find "$QE_ROOT" -name '#*#' -print0 2>/dev/null)

    if [[ $emacs_count -gt 0 ]]; then
        log_info "Deleted $emacs_count emacs auto-save files"
    else
        log_info "No emacs auto-save files found to delete"
    fi

    # Delete HAFiscal-draft.* files (draft versions, not needed for QE)
    local draft_count=0
    log_info "Searching for HAFiscal-draft.* files..."
    while IFS= read -r -d '' draft_file; do
        log_info "Deleting: $(basename "$draft_file")"
        rm -f "$draft_file"
        ((draft_count++))
    done < <(find "$QE_ROOT" -maxdepth 1 -name 'HAFiscal-draft.*' -type f -print0 2>/dev/null)
    
    if [[ $draft_count -gt 0 ]]; then
        log_info "Deleted $draft_count HAFiscal-draft.* file(s)"
    else
        log_info "No HAFiscal-draft.* files found to delete"
    fi

    # Delete Stata .do files (QE uses Python-only workflow)
    local do_count=0
    log_info "Searching for Stata .do files..."
    while IFS= read -r -d '' do_file; do
        log_info "Deleting: $do_file"
        rm -f "$do_file"
        ((do_count++))
    done < <(find "$QE_ROOT" -type f -name "*.do" -print0 2>/dev/null)
    
    if [[ $do_count -gt 0 ]]; then
        log_info "Deleted $do_count Stata .do file(s)"
    else
        log_info "No Stata .do files found to delete"
    fi

    # Delete CSV files from Code/Empirical/Data/ directory (generated artifacts)
    if [[ -d "$QE_ROOT/Code/Empirical/Data" ]]; then
        local csv_count=0
        log_info "Searching for CSV files in Code/Empirical/Data/..."
        while IFS= read -r -d '' csv_file; do
            log_info "Deleting: $csv_file"
            rm -f "$csv_file"
            ((csv_count++))
        done < <(find "$QE_ROOT/Code/Empirical/Data" -type f -name "*.csv" -print0 2>/dev/null)
        
        if [[ $csv_count -gt 0 ]]; then
            log_info "Deleted $csv_count CSV file(s) from Code/Empirical/Data/"
        else
            log_info "No CSV files found in Code/Empirical/Data/ to delete"
        fi
    else
        log_info "Code/Empirical/Data/ directory not found - skipping CSV deletion"
    fi

    # Delete QE-inappropriate directories
    local dirs_to_delete=(
        "images"                    # Generated PDFs - not needed for QE source submission
        "pkgs"                      # Package management artifacts
        "true"                      # Unknown/legacy directory
        ".claude"                   # Claude AI assistant directory
        "HAFiscal_variants"         # Variant directories
        ".githooks"                 # Git hooks directory
        "README_IF_YOU_ARE_AN_AI"   # AI assistant documentation
        "Figures/Data"              # Data files in Figures directory
        "history"                   # History documentation directory
    )
    
    for dir in "${dirs_to_delete[@]}"; do
        if [[ -d "$QE_ROOT/$dir" ]]; then
            log_info "Deleting directory: $dir/"
            rm -rf "$QE_ROOT/$dir"
        fi
    done
    
    # =============================================================================
    # DELETE UNNECESSARY @local/ FILES (bisection test identified only 3 are needed)
    # =============================================================================
    log_minor_section "Cleaning up unnecessary @local/ files"
    
    # Only these 2 files are necessary for QE build:
    # - local-qe.sty
    # - local-qe-figs-and-tables.sty
    # Note: hiddenappendix.sty not needed - hiddencontent blocks are removed by transform_for_qe()
    # All other @local/ files should be deleted
    
    if [[ -d "$QE_ROOT/@local" ]]; then
        log_info "Removing unnecessary files from @local/ (keeping only 2 required files)..."
        
        # Keep these files (the 2 necessary ones)
        # Note: hiddenappendix.sty not needed - hiddencontent blocks removed by transform_for_qe()
        local keep_files=(
            "local-qe.sty"
            "local-qe-figs-and-tables.sty"
        )
        
        # Delete all other files in @local/
        local deleted_count=0
        while IFS= read -r -d '' file; do
            local basename_file=$(basename "$file")
            local should_keep=false
            
            # Check if this file should be kept
            for keep_file in "${keep_files[@]}"; do
                if [[ "$basename_file" == "$keep_file" ]]; then
                    should_keep=true
                    break
                fi
            done
            
            # Delete if not in keep list
            if [[ "$should_keep" == "false" ]]; then
                log_info "  Deleting: @local/$basename_file"
                rm -f "$file"
                ((deleted_count+=1))
            fi
        done < <(find "$QE_ROOT/@local" -maxdepth 1 -type f -print0 2>/dev/null)
        
        if [[ $deleted_count -gt 0 ]]; then
            log_success "  ✓ Deleted $deleted_count unnecessary file(s) from @local/"
        else
            log_info "  No unnecessary files found in @local/"
        fi
    fi
    
    log_success "✅ QE-inappropriate files cleaned up"

    # DEBUG: Check if HAFiscal.bib exists after sync
    log_info "DEBUG: Checking for HAFiscal.bib after sync_from_public..."
    if [[ -f "$QE_ROOT/HAFiscal.bib" ]]; then
        log_success "✓ HAFiscal.bib exists ($(ls -lh "$QE_ROOT/HAFiscal.bib" | awk '{print $5}'))"
    else
        log_warning "⚠ HAFiscal.bib NOT FOUND after sync"
    fi

    # NOTE: QE repository KEEPS HAFiscal.tex (it's the main file)
    # build-QE-submission-PDFs.sh creates HAFiscal.tex via consolidation script

    # Generate REPLICATION.md from template if needed (README.md will be generated by QE workflow)
    # This runs AFTER rsync to ensure variables are filled from QE's git metadata
    log_info "Checking README/REPLICATION.md status..."
    DEV_ROOT="$(dirname "$MAKE_ROOT")"
    
    # Check if REPLICATION.md was copied from Public
    if [[ -f "$QE_ROOT/README/REPLICATION.md" ]]; then
        log_info "✓ README/REPLICATION.md copied from Public (preserving it)"
    elif [[ -f "$DEV_ROOT/README/generate-readme.py" ]] && [[ -f "$DEV_ROOT/README/REPLICATION-template.md" ]]; then
        log_info "Generating README/REPLICATION.md from template..."
        python3 "$DEV_ROOT/README/generate-readme.py" "$QE_ROOT" \
            "REPLICATION-template.md" \
            "README/REPLICATION.md" && \
            log_success "✓ Generated README/REPLICATION.md from template"
    else
        log_warning "⚠ REPLICATION.md not found and template system unavailable"
        log_warning "⚠ Note: README.md will be generated by QE-SUBMISSION-PREPARE.md workflow (Step 3)"
    fi

    # Update README/DOCKER.md for QE-specific DockerHub image
    if [[ -f "$QE_ROOT/README/DOCKER.md" ]]; then
        log_info "Updating README/DOCKER.md for QE repository..."
        
        cat > "$QE_ROOT/README/DOCKER.md" <<'EOF_DOCKER'
# Using Docker with HAFiscal-QE

## Quick Start (Pre-built Image - Recommended)

The easiest way to use this repository is with the pre-built Docker image:

```bash
# Pull the image from DockerHub
docker pull llorracc/hafiscal-qe:latest

# Run interactively
docker run -it llorracc/hafiscal-qe:latest

# Inside container
cd /workspace
./reproduce.sh --docs       # Build paper (30 seconds)
./reproduce.sh --comp min   # Quick validation (1 hour)
./reproduce.sh --comp full  # Full replication (4-5 days)
```

**Image Details**:
- **DockerHub**: https://hub.docker.com/r/llorracc/hafiscal-qe
- **Size**: 3.2 GB
- **Includes**: TeX Live 2025, Python 3.11, all dependencies
- **Verified**: QE compliance tested

## Building from Source (Advanced)

If you need to customize the environment:

```bash
git clone https://github.com/llorracc/HAFiscal-QE
cd HAFiscal-QE

docker build -t llorracc/hafiscal-qe:latest .
```

**Build time**: 15-20 minutes (installs TeX Live + Python environment)

## Prerequisites

- **Docker**: Install Docker Desktop or Docker Engine
  - [Docker installation guide](https://docs.docker.com/get-docker/)
- **Git**: For cloning repository

---

**Last Updated**: December 15, 2025
EOF_DOCKER
        
        log_success "✓ Updated README/DOCKER.md for QE repository"
    else
        log_warning "⚠ README/DOCKER.md not found - Docker documentation not updated"
    fi

    # Note: README.pdf marker file will be created by create_qe_readme() after pandoc conversion

}

# =============================================================================
# STEP 4: CONVERT FIGURES AND TABLES TO QE STANDALONE FORMAT
# =============================================================================

convert_figures_tables() {
    log_major_section "Converting Figures/Tables to QE standalone format"

    cd "$QE_ROOT"

    # NOTE: QE class files are copied to root by cleanup_qe_directory() after qe/ is synced
    # This function copies them to Figures/, Tables/, and Subfiles/ for standalone compilation

    # Copy QE class files to Figures/, Tables/, and Subfiles/ for standalone compilation
    log_info "Copying QE class files to Figures/, Tables/, and Subfiles/..."
    
    if [[ -f "qe/tex/econsocart.cls" ]]; then
        cp qe/tex/econsocart.cls Figures/ || true
        cp qe/tex/econsocart.cls Tables/ || true
        cp qe/tex/econsocart.cls Subfiles/ || true
        log_success "  ✓ econsocart.cls copied"
    else
        log_warning "  ⚠ qe/tex/econsocart.cls not found"
    fi
    
    if [[ -f "qe/tex/econsocart.cfg" ]]; then
        cp qe/tex/econsocart.cfg Figures/ || true
        cp qe/tex/econsocart.cfg Tables/ || true
        cp qe/tex/econsocart.cfg Subfiles/ || true
        log_success "  ✓ econsocart.cfg copied"
    else
        log_warning "  ⚠ qe/tex/econsocart.cfg not found"
    fi
    
    if [[ -f "qe/tex/qe.bst" ]]; then
        cp qe/tex/qe.bst Figures/ || true
        cp qe/tex/qe.bst Tables/ || true
        cp qe/tex/qe.bst tabular/ || true
        log_success "  ✓ qe.bst copied"
    else
        log_warning "  ⚠ qe/tex/qe.bst not found"
    fi
    
    cd "$MAKE_ROOT"

    # Call the conversion script
    local convert_script="$MAKE_ROOT/scripts/qe/utils/convert-figures-tables-to-qe-standalone.sh"

    if [[ ! -f "$convert_script" ]]; then
        log_error "Conversion script not found: $convert_script"
        exit 1
    fi
    
    log_info "Running conversion script..."
    if bash "$convert_script" "$QE_ROOT"; then
        log_success "✅ Figures/Tables converted to QE format"
    
    # Debug: Check if image PDFs still exist after conversion
    cd "$QE_ROOT"
    if ls images/*.pdf >/dev/null 2>&1; then
        log_info "DEBUG: After conversion: $(ls images/*.pdf 2>/dev/null | wc -l | tr -d " ") PDF files still in images/"
    else
        log_warning "DEBUG: After conversion: NO PDF files in images/ - they were deleted!"
    fi
    else
        log_error "Conversion script failed"
        exit 1
    fi
}

# =============================================================================
# STEP 4.5: CLEANUP QE DIRECTORY
# =============================================================================

cleanup_qe_directory() {
    log_major_section "Preparing qe/ directory for final submission"

    cd "$MAKE_ROOT"

    # Step 1: Copy qe/ directory from Public's qe branch
    log_info "Step 1: Copying qe/ directory from Public (qe branch)..."

    # Save current branch in Public
    cd "$PUBLIC_ROOT"
    local public_original_branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "main")

    # PHASE 1 FIX: Commit uncommitted changes before checking out qe branch
    # This prevents data loss from stashing (which may not be properly restored)
    local had_changes=false
    if ! git diff-index --quiet HEAD -- 2>/dev/null || ! git diff --cached --quiet HEAD 2>/dev/null; then
        log_info "Committing uncommitted changes in Public before qe branch checkout..."
        git add -A || true
        TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        git commit --no-verify -m "Auto-commit before QE sync $TIMESTAMP

Changes from Latest-to-Public sync committed before checking out
qe branch to prevent data loss. These changes will be squashed into
a single orphan commit when post-Public.sh is run.

See: docs/WORKFLOW-FIX-PLAN-POST-PUBLIC.md" >/dev/null 2>&1 || true
        had_changes=true
        log_success "  ✓ Changes committed in Public"
    fi

    # Checkout qe branch (no stash needed, changes are committed)
    log_verbose "Checking out qe branch in Public..."
    if ! git checkout qe 2>&1; then
        log_error "Failed to checkout qe branch in Public"
        log_error "Please ensure the qe branch exists and there are no conflicts"
        cd "$MAKE_ROOT"
        exit 1
    fi

    # Copy qe/ directory to QE
    if [[ -d "qe" ]]; then
        # Use -L to dereference symlinks (materialize LATEST symlinks)
        # Exclude timestamped files (keep only the materialized LATEST versions)
        rsync -rLptgoD --delete \
            --exclude='*_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9]*' \
            "qe/" "$QE_ROOT/qe/"
        log_success "  ✓ Copied qe/ directory from Public (qe branch)"
        log_info "    Symlinks materialized, timestamped files excluded"

        # Copy QE class files to root directory for main document compilation
        cd "$QE_ROOT"
        log_info "Copying QE class files to repository root..."

        if [[ -f "qe/tex/econsocart.cls" ]]; then
            cp qe/tex/econsocart.cls . || true
            log_success "  ✓ econsocart.cls → root"
        else
            log_warning "  ⚠ qe/tex/econsocart.cls not found (root)"
        fi

        if [[ -f "qe/tex/econsocart.cfg" ]]; then
            cp qe/tex/econsocart.cfg . || true
            log_success "  ✓ econsocart.cfg → root"
        else
            log_warning "  ⚠ qe/tex/econsocart.cfg not found (root)"
        fi

        if [[ -f "qe/tex/qe.bst" ]]; then
            cp qe/tex/qe.bst . || true
            log_success "  ✓ qe.bst → root"
        else
            log_warning "  ⚠ qe/tex/qe.bst not found (root)"
        fi

        cd "$PUBLIC_ROOT"
    else
        log_warning "  ⚠ qe/ directory not found on Public qe branch"
    fi

    # Return Public to original branch
    git checkout "$public_original_branch" >/dev/null 2>&1

    # PHASE 1 FIX: No stash to restore (changes were committed)
    if [[ "$had_changes" == "true" ]]; then
        log_verbose "Changes are safely committed in Public (no stash to restore)"
    fi

    # Step 2: Remove build artifacts that shouldn't be in final submission
    cd "$QE_ROOT"

    if [[ ! -d "qe" ]]; then
        log_warning "qe/ directory not found - skipping cleanup"
        cd "$MAKE_ROOT"
        return 0
    fi

    log_info "Step 2: Removing build artifacts from qe/..."

    # Remove template (used for building, not for editors)
    if [[ -f "qe/HAFiscal-QE-template.tex" ]]; then
        rm "qe/HAFiscal-QE-template.tex"
        log_info "  ✓ Removed HAFiscal-QE-template.tex (build artifact)"
    fi

    # Remove theorem environments file (reference material, not needed)
    if [[ -f "qe/qe-official-theorem-environments.ltx" ]]; then
        rm "qe/qe-official-theorem-environments.ltx"
        log_info "  ✓ Removed qe-official-theorem-environments.ltx (reference material)"
    fi

    # Keep compliance directory (contains QE-COMPLIANCE-SPEC.md for Data Editors
    # and will hold compliance reports generated later)
    if [[ -d "qe/compliance" ]]; then
        log_info "  ✓ Keeping compliance/ directory (QE-COMPLIANCE-SPEC.md + reports)"
    fi

    # Remove tex directory (class files copied to root, source not needed)
    if [[ -d "qe/tex" ]]; then
        rm -rf "qe/tex"
        log_info "  ✓ Removed tex/ directory (class files already in root)"
    fi

    # Remove obsolete README files if they exist
    # NOTE: Keep README-QE.md in qe/ (it's documentation for authors, also copied to root)
    if [[ -f "qe/README_QE_FILES.md" ]]; then
        rm "qe/README_QE_FILES.md"
        log_info "  ✓ Removed README_QE_FILES.md (obsolete)"
    fi

    # Remove obsolete QE-COMPLIANCE.md (replaced by REPORT/CHECKLIST in compliance/)
    if [[ -f "qe/QE-COMPLIANCE.md" ]]; then
        rm "qe/QE-COMPLIANCE.md"
        log_info "  ✓ Removed QE-COMPLIANCE.md (obsolete - replaced by timestamped reports)"
    fi

    # Remove qe/README.md (moved to HAFiscal-dev/docs/project/qe-submission-workflow.md)
    if [[ -f "qe/README.md" ]]; then
        rm "qe/README.md"
        log_info "  ✓ Removed qe/README.md (moved to dev workspace docs)"
    fi

    log_success "✅ qe/ directory prepared for final submission"
    log_info "Remaining in qe/: documentation for authors"

    # Show what remains
    if [[ -d "qe" ]]; then
        log_info "Contents: $(ls qe/ 2>/dev/null | tr '\n' ' ')"
    fi

    cd "$MAKE_ROOT"
}

# =============================================================================
# STEP 5: ADAPT REPRODUCE SCRIPTS FOR QE
# =============================================================================

adapt_reproduce_scripts() {
    log_major_section "Adapting reproduce scripts for QE environment"
    
    cd "$QE_ROOT"
    
    # Check if reproduce scripts exist
    if [[ ! -f "reproduce.sh" ]]; then
        log_warning "reproduce.sh not found - skipping adaptation"
        cd "$MAKE_ROOT"
        return 0
    fi
    
    # NOTE: QE repository now uses HAFiscal.tex (not HAFiscal-QE.tex)
    # The consolidation script creates HAFiscal.tex, so no filename conversion needed
    # reproduce_documents.sh in Latest/Public already updated to use HAFiscal.tex
    log_info "QE repository uses HAFiscal.tex (no filename conversion needed)"
    
    # Disable symlink check in QE repository (symlinks are dereferenced by rsync -L)
    if [[ -f "reproduce.sh" ]]; then
        log_info "Disabling symlink check (QE uses dereferenced symlinks)..."
        # Replace the check_symlinks function with a no-op for QE distribution
        sed -i.bak '/^check_symlinks() {$/,/^}$/c\
check_symlinks() {\
    # Symlink check disabled for QE distribution\
    # This repository intentionally has dereferenced symlinks (real files)\
    # created by rsync -L during QE package preparation\
    :\
}\
' reproduce.sh
        rm -f reproduce.sh.bak
        log_success "  ✓ Disabled symlink check for QE distribution"
    fi
    
    # # Update reproduce/README.md if it exists
    # if [[ -f "reproduce/README.md" ]]; then
    #     sed -i.bak 's/HAFiscal\.tex/HAFiscal-QE.tex/g' reproduce/README.md
    #     sed -i.bak 's/HAFiscal-Latest/HAFiscal-QE/g' reproduce/README.md
    #     rm -f reproduce/README.md.bak
    #     log_success "  ✓ reproduce/README.md adapted"
    # fi
    
    # Set execute permissions on all shell and Python scripts
    log_info "Setting execute permissions on scripts..."
    find . -maxdepth 1 -type f \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} \; 2>/dev/null || true
    if [[ -d "reproduce" ]]; then
        find reproduce -type f \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} \; 2>/dev/null || true
    fi
    log_success "  ✓ Execute permissions set"
    
    log_success "✅ Reproduce scripts adapted for QE environment"
    
    cd "$MAKE_ROOT"
}

# =============================================================================
# STEP 6: QE-SPECIFIC TRANSFORMATIONS
# =============================================================================

transform_for_qe() {
    log_major_section "Applying QE-specific transformations"
    
    cd "$QE_ROOT"
    
    # Remove development configuration files (keep environment files for reproducibility)
    log_info "Removing development configuration files..."
    rm -f .chktexrc .cursorrules .latexindent.yaml .aspell.conf || true
    rm -f .cursorindexingignore .editorconfig || true
    rm -f .gitignore.cleaned .gitignore.cleanup-summary.md .gitignore.reorganized || true
    rm -f pytest.ini poetry.lock uv.lock || true
    # Keep: pyproject.toml, binder/environment.yml for reproducibility
    rm -f *.ipynb || true
    
    # Remove development directories (keep binder/ and reproduce/ for reproducibility)
    log_info "Removing development directories..."
    rm -rf .devcontainer/ .devcontainer_dashboard/ || true
    
    # Remove any remaining .devcontainer* files/directories (catch-all)
    log_info "Removing any remaining .devcontainer* files..."
    find . -maxdepth 1 -name ".devcontainer*" -type f -delete 2>/dev/null || true
    find . -maxdepth 1 -name ".devcontainer*" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Keep specific CI test workflows, remove everything else in .github/
    log_info "Cleaning .github/ directory (keeping test workflows)..."
    if [[ -d .github/workflows ]]; then
        # Remove all workflows except test-uv-setup.yml and test-latex-compilation.yml
        find .github/workflows -type f ! -name 'test-uv-setup.yml' ! -name 'test-latex-compilation.yml' -delete 2>/dev/null || true
    fi
    # Remove all other .github/ subdirectories and files
    find .github -mindepth 1 -maxdepth 1 ! -name 'workflows' -exec rm -rf {} + 2>/dev/null || true
    
    rm -rf .githooks/ .vscode/ .specstory/ || true
    rm -rf README_IF_YOU_ARE_AN_AI/ architecture/ history/ docs/ || true
    rm -rf prompts/ prompts_local/ Tools/ || true
    rm -rf dashboard/ || true
    # Keep: binder/ and reproduce/ for reproducibility
    rm -rf Old/ Private*/ private*/ *private*/ || true
    
    # Remove test files
    log_info "Removing test files..."
    find . -name 'test_*.py' -delete 2>/dev/null || true
    find . -name '*_test.py' -delete 2>/dev/null || true
    find . -name 'test*.tex' -delete 2>/dev/null || true

    # Remove latexindent log files
    log_info "Removing latexindent log files..."
    find . -name 'indent.log' -type f -delete 2>/dev/null || true

    # Remove PDF artifacts (QE wants source only)
    log_info "Removing PDF artifacts..."
    rm -f *.pdf Subfiles/*.pdf *-Slides.pdf 2>/dev/null || true
    
    # Simplify .gitignore for QE submission
    log_info "Creating simplified .gitignore for QE..."
    cat > .gitignore << 'EOF'
# QE Submission Repository - Minimal .gitignore

# LaTeX compilation artifacts
*.aux
*.log
*.out
*.toc
*.fls
*.fdb_latexmk
*.synctex.gz
*.blg
*.xbb
*.dep
indent.log

# Bibliography source files (QE requires .bbl, not .bib source)
# Note: .bbl is TRACKED (required by journal), .bib is ignored
*.bib

# PDF files (not tracked in QE submission)
*.pdf

# System files
.DS_Store
Thumbs.db

# Editor files
*~
*.bak
*.backup
*backup*
*.brf
\#*\#

# AI assistant directories
.claude/
.cursor/
.specstory/
.cursorignore
.cursorindexingignore

# Benchmark runtime results
reproduce/benchmarks/results/auto/
reproduce/benchmarks/results/latest.json

# Environment verification markers (timestamp files)
reproduce/reproduce_environment_*.verified
*.verified

# AUCTeX auto folders
auto/
/auto/

# Virtual environment directories
# Ignore all directories beginning with .venv
.venv*/
EOF
    
    # NOTE: Titlepage transformation not needed for QE
    # The QE build uses HAFiscal-QE-template.tex which has hardcoded authors
    # in native econsocart format. The titlepage subfile is not included in
    # Subfiles.ltx, so it's never used during QE compilation.
    
    # NOTE: hiddencontent blocks are removed in generate_hafiscal_tex() after HAFiscal.tex is created
    
    log_success "✅ QE transformations applied"
    
    cd "$MAKE_ROOT"
}

# =============================================================================
# STEP 7: PURGE, COPY, AND ANNOTATE FILES
# =============================================================================

purge_generated_files() {
    log_major_section "Purging, copying, and annotating files"
    
    cd "$QE_ROOT"
    
    log_info "Processing strategy:"
    log_info "  1. Purge all generated files (clean slate)"
    log_info "  2. Copy ONLY referenced images from Public"
    log_info "  3. Annotate copied images with 'pregenerated' label"
    log_info "  4. Annotate tabular files with 'PREGENERATED' labels"
    log_info ""
    
    # Step 1: Run purge script first to clean everything
    log_info "Step 1: Purging all generated files (including old images)..."
    
    local purge_script="$MAKE_ROOT/scripts/utils/purge-generated-files.sh"
    
    if [[ ! -f "$purge_script" ]]; then
        log_error "Purge script not found: $purge_script"
        exit 1
    fi
    
    # Run purge script in non-interactive mode
    if PURGE_NON_INTERACTIVE=true bash "$purge_script"; then
        log_success "  ✓ Purge complete - all generated files removed"
    else
        log_error "Purge script failed"
        exit 1
    fi
    
    # Step 2: Find all \includegraphics references and copy images
    log_info "Step 2: Finding image references and copying from Public..."
    
    # Check for ImageMagick (needed for Step 3)
    local MAGICK_CMD=""
    if command -v magick >/dev/null 2>&1; then
        MAGICK_CMD="magick"
    elif command -v convert >/dev/null 2>&1; then
        MAGICK_CMD="convert"
    else
        log_error "ImageMagick not found (needed for image annotation)"
        log_error "Install with: brew install imagemagick"
        exit 1
    fi
    
    # Find all .tex files up to depth 3 (exclude Old/ and dot-files)
    local tex_files=$(find . -maxdepth 3 -name "*.tex" \
        -not -path "./Old/*" \
        -not -path "./_*" \
        -not -path "./.*" \
        2>/dev/null)
    
    # Extract image references from \includegraphics commands
    # Handles: \includegraphics{path}, \includegraphics[options]{path}
    local image_refs=$(echo "$tex_files" | xargs grep -h "\\\\includegraphics" 2>/dev/null | \
        sed -E 's/.*\\includegraphics(\[[^]]*\])?\{([^}]+)\}.*/\2/' | \
        sort -u)
    
    local ref_count=$(echo "$image_refs" | grep -c . || echo 0)
    log_info "  Found $ref_count unique image references in .tex files"
    
    # Create images/ directory
    mkdir -p images
    
    local copied_count=0
    local missing_count=0
    local skipped_count=0
    
    # Source directory (HAFiscal-Public/images/)
    local source_images="$PUBLIC_ROOT/images"
    
    while IFS= read -r img_ref; do
        [[ -z "$img_ref" ]] && continue
        
        # Skip if not referencing images/ directory
        if [[ "$img_ref" != *"images/"* ]] && [[ "$img_ref" != "\\latexroot/images/"* ]]; then
            ((skipped_count++))
            continue
        fi
        
        # Extract just the filename from the reference
        # Handle paths like: images/foo.pdf, \latexroot/images/foo, ./images/foo
        local img_basename=$(echo "$img_ref" | sed -E 's|.*/images/||' | sed 's|\\latexroot/||')
        
        # Try to find the source file with various extensions
        local source_file=""
        for ext in "" ".pdf" ".png" ".jpg" ".jpeg" ".svg"; do
            if [[ -f "$source_images/${img_basename}${ext}" ]]; then
                source_file="$source_images/${img_basename}${ext}"
                break
            fi
        done
        
        if [[ -z "$source_file" ]]; then
            log_warning "    Source not found: $img_basename"
            ((missing_count++))
            continue
        fi
        
        # Copy to QE images/ directory
        local dest_file="images/$(basename "$source_file")"
        if cp "$source_file" "$dest_file" 2>/dev/null; then
            ((copied_count++))
            if [[ $((copied_count % 10)) -eq 0 ]]; then
                log_info "    Copied $copied_count images..."
            fi
        else
            log_warning "    Failed to copy: $source_file"
        fi
    done <<< "$image_refs"
    
    log_success "  ✓ Copied $copied_count images to images/ directory"
    [[ $skipped_count -gt 0 ]] && log_info "    (Skipped $skipped_count non-images/ references)"
    [[ $missing_count -gt 0 ]] && log_warning "    (Missing $missing_count source files)"
    
    # Step 3: Annotate ALL images in images/ directory
    log_info "Step 3: Annotating images with 'pregenerated' watermark..."
    
    local annotated_count=0
    local failed_count=0
    
    # Find all image files in images/ directory
    if [[ -d "images" ]]; then
        while IFS= read -r img_file; do
            [[ -z "$img_file" ]] && continue
            
            local temp_file="${img_file}.tmp"
            
            if $MAGICK_CMD "$img_file" \
                -gravity center \
                -pointsize 48 \
                -font Helvetica-Bold \
                -fill "rgba(255,0,0,0.5)" \
                -stroke "rgba(255,255,255,0.7)" \
                -strokewidth 2 \
                -annotate +0+0 "pregenerated" \
                "$temp_file" 2>/dev/null; then
                
                mv "$temp_file" "$img_file"
                ((annotated_count++))
                
                if [[ $((annotated_count % 10)) -eq 0 ]]; then
                    log_info "    Annotated $annotated_count images..."
                fi
            else
                log_warning "    Failed to annotate: $img_file"
                rm -f "$temp_file"
                ((failed_count++))
            fi
        done < <(find images/ -type f \( -name "*.pdf" -o -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" \) 2>/dev/null)
    fi
    
    log_success "  ✓ Annotated $annotated_count images"
    [[ $failed_count -gt 0 ]] && log_warning "    (Failed to annotate $failed_count images)"
    
    # Step 4: Annotate tabular content with PREGENERATED labels
    
    # Summary
    log_success "✅ Processing complete"
    log_info ""
    log_info "Repository state:"
    log_info "  • Generated files: Purged (LaTeX artifacts, old images removed)"
    log_info "  • images/ directory: Contains ONLY referenced images ($copied_count files, all annotated)"
    log_info "  • Other directories: Unchanged (@resources/, @local/, Code/)"
    log_info "  • Original state preserved in 'including-generated-objects' branch"
    
    cd "$MAKE_ROOT"
}

# =============================================================================
# STEP 8.5: COMPILE PAPER IN QE REPO TO GENERATE QE-STYLE .BBL
# =============================================================================

compile_paper_for_qe_bbl() {
    log_major_section "Compiling paper in QE repo to generate QE-style bibliography"
    
    cd "$QE_ROOT"
    
    # Verify .bib was synced
    if [[ ! -f "$PROJECT_NAME.bib" ]]; then
        log_error "❌ $PROJECT_NAME.bib not found in QE repo"
        log_error "   It should have been synced from Public"
        exit 1
    fi
    
    log_info "Running ./reproduce.sh --docs main (compiles with qe.bst style)..."
    log_info ""
    
    # Run reproduce.sh --docs main
    if ./reproduce.sh --docs main >/dev/null 2>&1; then
        log_success "  ✓ Paper compilation completed"
    else
        log_warning "  ⚠ Compilation had warnings (checking .bbl anyway)"
    fi
    
    # Verify .bbl was generated
    if [[ ! -f "$PROJECT_NAME.bbl" ]]; then
        log_error "❌ $PROJECT_NAME.bbl was not created by paper compilation"
        log_error "   Check ./reproduce.sh --docs main output for errors"
        cd "$MAKE_ROOT"
        exit 1
    fi
    
    # Count entries (QE uses \bibitem, not \harvarditem)
    local bbl_entries=$(grep -c "^\\\\bibitem" "$PROJECT_NAME.bbl" 2>/dev/null || echo "0")
    bbl_entries=$(echo "$bbl_entries" | tr -d '\n\r' | head -1)
    
    if [[ $bbl_entries -eq 0 ]]; then
        log_error "❌ $PROJECT_NAME.bbl was created but has ZERO bibliography entries"
        log_error "   This means BibTeX failed during paper compilation"
        if [[ -f "$PROJECT_NAME.blg" ]]; then
            log_error ""
            log_error "BibTeX log:"
            tail -20 "$PROJECT_NAME.blg" | sed 's/^/    /'
        fi
        cd "$MAKE_ROOT"
        exit 1
    fi
    
    log_success ""
    log_success "✅ QE-style bibliography generated successfully"
    log_success "   Generated: $PROJECT_NAME.bbl ($bbl_entries entries, $(wc -l < "$PROJECT_NAME.bbl" | tr -d ' ') lines)"
    log_success "   Style: qe.bst (QE journal bibliography style)"
    log_info ""
    log_info "The .bbl file will be:"
    log_info "  - Kept on BOTH branches (main and with-precomputed-artifacts)"
    log_info "  - Required by QE for paper compilation"
    log_info ""
    log_info "The .bib file will be:"
    log_info "  - Kept on with-precomputed-artifacts branch (for reference)"
    log_info "  - Excluded from main branch (per QE policy)"
    log_info ""
    
    cd "$MAKE_ROOT"
}

# =============================================================================
# STEP 7A: GENERATE HAFiscal.tex FROM TEMPLATE
# =============================================================================

generate_hafiscal_tex() {
    log_major_section "Generating HAFiscal.tex from template for QE submission"
    
    cd "$QE_ROOT"
    
    # HAFiscal.tex must be generated fresh from the template for QE submission
    # This ensures it uses the current, correct template without obsolete lines
    # The generated file is INCLUDED in the distribution so users can compile directly
    
    log_info "Calling build-qe-submission.sh to generate HAFiscal.tex..."
    
    # build-qe-submission.sh expects to be called with PUBLIC_ROOT as SOURCE_DIR
    # It will use the qe branch of Public and the template from Public/qe/HAFiscal-QE-template.tex
    # It runs from MAKE_ROOT context (needs paths.sh infrastructure)
    cd "$MAKE_ROOT"
    
    if [[ ! -f "$MAKE_ROOT/scripts/qe/build-qe-submission.sh" ]]; then
        log_error "build-qe-submission.sh not found in $MAKE_ROOT/scripts/qe/"
        exit 1
    fi
    
    # Call build script with PUBLIC_ROOT as source (will checkout qe branch and use template from there)
    if bash "$MAKE_ROOT/scripts/qe/build-qe-submission.sh" "$PUBLIC_ROOT"; then
        log_success "✅ HAFiscal.tex generated successfully"
    else
        log_error "Failed to generate HAFiscal.tex from template"
        exit 1
    fi
    
    # Verify HAFiscal.tex was created
    if [[ ! -f "$QE_ROOT/HAFiscal.tex" ]]; then
        log_error "HAFiscal.tex was not created by build script"
        exit 1
    fi
    
    # Remove hiddencontent blocks from HAFiscal.tex
    # Since references to hidden appendix content are substituted with plain text,
    # there's no need to include these blocks at all in the QE version
    cd "$QE_ROOT"
    log_info "Removing hiddencontent blocks from HAFiscal.tex..."
    if grep -q "hiddencontent" HAFiscal.tex; then
        sed "${SED_INPLACE[@]}" '/\\begin{hiddencontent}/,/\\end{hiddencontent}/d' HAFiscal.tex
        log_success "  ✓ Removed hiddencontent blocks from HAFiscal.tex"
    else
        log_info "  No hiddencontent blocks found in HAFiscal.tex"
    fi
    cd "$MAKE_ROOT"
    
    log_info "HAFiscal.tex will be included in QE distribution"
    
    cd "$MAKE_ROOT"
}

# =============================================================================
# STEP 8: CREATE QE-SPECIFIC README
# =============================================================================

create_qe_readme() {
    log_major_section "Creating QE-specific README"
    
    # Check if README.md already exists (copied from qe/README-QE.md)
    if [[ -f "$QE_ROOT/README.md" ]]; then
        log_info "README.md already exists (copied from qe/README-QE.md)"
        log_info "Converting README.md to README.pdf..."
        
        cd "$QE_ROOT"
        
        # Check if pandoc is available
        if command -v pandoc >/dev/null 2>&1; then
            # FIX 1: Use xelatex as primary engine (better unicode support than pdflatex)
            # xelatex handles unicode characters like box-drawing (├, ─, └) that pdflatex cannot
            pandoc README.md -o README.pdf \
                --pdf-engine=xelatex \
                --variable=geometry:margin=1in \
                --variable=fontsize:11pt \
                --variable=mainfont="DejaVu Sans" \
                --variable=monofont="DejaVu Sans Mono" \
                --toc \
                --toc-depth=2 \
                2>&1 || {
                    log_warning "⚠ xelatex conversion failed, trying lualatex"
                    # FIX 2: Fallback to lualatex (also has good unicode support)
                    pandoc README.md -o README.pdf \
                        --pdf-engine=lualatex \
                        --variable=geometry:margin=1in \
                        --variable=fontsize:11pt \
                        --variable=mainfont="DejaVu Sans" \
                        --variable=monofont="DejaVu Sans Mono" \
                        --toc \
                        --toc-depth=2 \
                        2>&1 || {
                            log_warning "⚠ lualatex conversion failed, trying pdflatex with unicode sanitization"
                            # FIX 3: Last resort - sanitize unicode and use pdflatex
                            # Replace box-drawing characters with ASCII equivalents
                            sed 's/├/|/g; s/─/-/g; s/└/`/g; s/│/|/g' README.md > README-sanitized.md
                            pandoc README-sanitized.md -o README.pdf \
                                --pdf-engine=pdflatex \
                                --variable=geometry:margin=1in \
                                --variable=fontsize:11pt \
                                --toc \
                                --toc-depth=2 \
                                2>&1 || log_warning "⚠ PDF conversion failed - install pandoc for README.pdf generation"
                            rm -f README-sanitized.md
                        }
                }
            
            if [[ -f "README.pdf" ]]; then
                log_success "✅ README.pdf created successfully"

                # Create marker file
                touch "README-pdf-is-pandoc-compiled-version-of-README.md"
                log_success "✅ Created marker file: README-pdf-is-pandoc-compiled-version-of-README.md"
            else
                log_warning "⚠ README.pdf not created - manual conversion may be needed"
            fi
        else
            log_warning "⚠ pandoc not found - README.pdf not created"
            log_info "   To create README.pdf manually:"
            log_info "   brew install pandoc  # macOS"
            log_info "   sudo apt-get install pandoc texlive-latex-base texlive-latex-recommended  # Linux"
            log_info "   pandoc README.md -o README.pdf --pdf-engine=pdflatex"
        fi
        
        cd "$MAKE_ROOT"
        return 0
    fi
    
    # Fallback: Create generic README if qe/README-QE.md wasn't found
    log_info "Creating fallback README (qe/README-QE.md not found)"
    
    cat > "$QE_ROOT/README.md" << 'EOF'
# Welfare and Spending Effects of Consumption Stimulus Policies

**Quantitative Economics Journal Submission**

This repository contains the submission materials for the paper submitted to *Quantitative Economics*.

## Authors

Christopher D. Carroll (Johns Hopkins University)  
Edmund Crawley (Federal Reserve Board)  
Ivan Frankovic (European Central Bank)

## Repository Contents

This is a clean submission repository containing:
- LaTeX source files (`HAFiscal.tex`, `Subfiles/*.tex`)
- Bibliography (`HAFiscal.bib`)
- Figures and tables (`Figures/`, `Tables/`)
- Essential style files (`@local/`, `@resources/`)
- Graphics and images (`images/`)

## Compilation

To compile the paper:

```bash
pdflatex HAFiscal
bibtex HAFiscal
pdflatex HAFiscal
pdflatex HAFiscal
```

Or use latexmk:

```bash
latexmk -pdf HAFiscal.tex
```

## Reproduction

To reproduce the computational results and figures in this paper:

```bash
./reproduce.sh --comp min    # Minimal computational reproduction
./reproduce.sh --docs main   # Reproduce main document
./reproduce.sh --help        # See all options
```

For detailed reproduction instructions, see [README/REPLICATION.md](README/REPLICATION.md).

See `reproduce/README.md` for additional technical details.

## Requirements

### LaTeX Compilation
- LaTeX distribution (TeX Live 2020 or later recommended)
- BibTeX
- Standard LaTeX packages (econark class and dependencies)

### Computational Reproducibility
- Python 3.11+
- See `pyproject.toml` for Python package dependencies
- See `binder/environment.yml` for conda environment specification
- See `binder/requirements.txt` for pip package list

## Abstract

[Abstract will be extracted from paper]

## Repository Structure

```
HAFiscal-QE/
├── README.md                # This file
├── HAFiscal-QE.tex         # Main paper file (QE submission version)
├── HAFiscal.bib            # Bibliography
├── pyproject.toml          # Python dependencies
├── reproduce.sh            # Main reproduction script
├── reproduce/              # Reproduction infrastructure
│   ├── README.md           # Detailed reproduction instructions
│   └── ...                 # Additional reproduction scripts
├── Subfiles/               # Paper sections
├── Tables/                 # Table files
├── Figures/                # Figure files
├── images/                 # Graphics
├── binder/                 # Environment specifications
│   ├── environment.yml     # Conda environment
│   └── requirements.txt    # Pip requirements
├── @local/                 # Local style files
├── @resources/             # LaTeX resources
└── Code/                   # Replication code
```

## LaTeX Resource Directories

This repository uses a custom search path system to organize LaTeX packages and resources:

### `@resources/` Directory
Contains **shared LaTeX resources** and configurations:
- `tex-add-search-paths.tex` - Configures TeX to search these directories
- `texlive/texmf-local/` - Custom LaTeX packages, classes, and styles
- `econ-ark/` - Mathematical notation system (econark-shortcuts.sty)
- Configuration files for various tools (git, shell, LaTeX)

These are resources that could be shared across multiple projects.

### `@local/` Directory  
Contains **project-specific LaTeX configuration**:
- `local.sty` - Main package loading and custom definitions for this paper
- `local-qe.sty` - QE journal-specific package configuration
- `qe-dir-add-to-search-path.sty` - Adds qe/ directory to search path
- Other `.sty` files with HAFiscal-specific customizations

### How the Search Path System Works

The first line in `HAFiscal-QE.tex` and subfiles is:
```latex
\input{@resources/tex-add-search-paths}
```

This executes the search path configuration, which tells LaTeX to look for files in:
- `@resources/texlive/texmf-local/tex/latex/` (and subdirectories)
- `@local/` 
- Parent directories (`../`, `../../`, etc.) for files in subdirectories

This system enables:
1. **Standalone compilation** - Files in `Tables/` and `Figures/` subdirectories can compile independently
2. **Clean organization** - Separates shared resources from project-specific files
3. **Easy maintenance** - LaTeX packages are centralized and version-controlled
4. **Portability** - All dependencies included in the repository

When you compile from subdirectories (e.g., `Tables/calibration.tex`), the multi-level path configuration ensures LaTeX can still find packages in `@local/` and `@resources/` by searching parent directories.

### Technical Details

The search path system modifies two TeX path variables:
- `\input@path` - For `.sty`, `.cls`, and general input files
- `\bibinput@path` - For bibliography files (`.bst`, `.bib`)

Both are configured to search up to 3 directory levels, allowing subfiles at various depths to find all necessary resources.


## Submission Information

- Journal: Quantitative Economics
- Submission Type: Original Research
- Generated from: HAFiscal-Public repository
- Build Date: [Generated by script]

## Contact

For questions about this submission, please contact:  
Christopher D. Carroll <ccarroll@jhu.edu>

---

*This repository was automatically generated from the HAFiscal-Public repository using the HAFiscal-make build system.*
EOF

    log_success "✅ QE-specific README created"

    # Convert README.md to README.pdf (same as non-fallback path)
    log_info "Converting README.md to README.pdf..."

    cd "$QE_ROOT"

    # Check if pandoc is available
    if command -v pandoc >/dev/null 2>&1; then
        # FIX 1: Use xelatex as primary engine (better unicode support than pdflatex)
        # xelatex handles unicode characters like box-drawing (├, ─, └) that pdflatex cannot
        pandoc README.md -o README.pdf \
            --pdf-engine=xelatex \
            --variable=geometry:margin=1in \
            --variable=fontsize:11pt \
            --variable=mainfont="DejaVu Sans" \
            --variable=monofont="DejaVu Sans Mono" \
            --toc \
            --toc-depth=2 \
            2>&1 || {
                log_warning "⚠ xelatex conversion failed, trying lualatex"
                # FIX 2: Fallback to lualatex (also has good unicode support)
                pandoc README.md -o README.pdf \
                    --pdf-engine=lualatex \
                    --variable=geometry:margin=1in \
                    --variable=fontsize:11pt \
                    --variable=mainfont="DejaVu Sans" \
                    --variable=monofont="DejaVu Sans Mono" \
                    --toc \
                    --toc-depth=2 \
                    2>&1 || {
                        log_warning "⚠ lualatex conversion failed, trying pdflatex with unicode sanitization"
                        # FIX 3: Last resort - sanitize unicode and use pdflatex
                        # Replace box-drawing characters with ASCII equivalents
                        sed 's/├/|/g; s/─/-/g; s/└/`/g; s/│/|/g' README.md > README-sanitized.md
                        pandoc README-sanitized.md -o README.pdf \
                            --pdf-engine=pdflatex \
                            --variable=geometry:margin=1in \
                            --variable=fontsize:11pt \
                            --toc \
                            --toc-depth=2 \
                            2>&1 || log_warning "⚠ PDF conversion failed - install pandoc for README.pdf generation"
                        rm -f README-sanitized.md
                    }
            }

        if [[ -f "README.pdf" ]]; then
            log_success "✅ README.pdf created successfully"

            # Create marker file
            touch "README-pdf-is-pandoc-compiled-version-of-README.md"
            log_success "✅ Created marker file: README-pdf-is-pandoc-compiled-version-of-README.md"
        else
            log_warning "⚠ README.pdf not created - manual conversion may be needed"
        fi
    else
        log_warning "⚠ pandoc not found - README.pdf not created"
        log_info "   To create README.pdf manually:"
        log_info "   brew install pandoc  # macOS"
        log_info "   sudo apt-get install pandoc texlive-latex-base texlive-latex-recommended  # Linux"
        log_info "   pandoc README.md -o README.pdf --pdf-engine=pdflatex"
    fi

    cd "$MAKE_ROOT"
}

# =============================================================================
# STEP 9: FINALIZE AND COMMIT
# =============================================================================

finalize_qe_repo() {
    log_major_section "Step 1: Create main branch with ALL artifacts"
    
    cd "$QE_ROOT"
    
    # Track whether push succeeds (for end-of-script messaging)
    PUSH_SUCCEEDED=false
    
    # Create QE-specific README
    # Skip README generation if requested by workflow (which will create comprehensive version in Step 3)
    if [[ "${SKIP_QE_README_GENERATION:-false}" == "true" ]]; then
        log_info "Skipping README generation (will be handled by workflow Step 3)"
    else
        create_qe_readme
    fi
    
    # BUGFIX: create_qe_readme() changes back to MAKE_ROOT, so we need to cd back to QE_ROOT
    cd "$QE_ROOT"
    
    # =========================================================================
    # NEW SIMPLIFIED WORKFLOW:
    # 0. Clean up existing branches from previous runs (CRITICAL for regeneration)
    # 1. Create orphan main branch FIRST (empty, no commits yet)
    # 2. rsync has already populated working directory (done before this function)
    # 3. Commit everything INCLUDING all precomputed artifacts
    # 4. Push to remote
    # 
    # Later: create_wpa_branch() will create normal branch from main
    # Later: delete_artifacts_from_main() will remove artifacts from main
    # =========================================================================
    
    log_major_section "Cleaning up existing branches (if any)"
    
    # Use "main" as default branch name
    default_branch="main"
    
    # CRITICAL: Delete existing branches from previous runs
    # We need to do this BEFORE creating the new orphan branch
    log_info "Checking for existing branches to delete..."
    
    # Get current branch (so we don't try to delete it while on it)
    current_branch=$(git branch --show-current 2>/dev/null || echo "")
    
    # If we're on main or wpa, switch to a temporary branch first
    if [[ "$current_branch" == "main" ]] || [[ "$current_branch" == "with-precomputed-artifacts" ]]; then
        log_info "Currently on branch: $current_branch"
        log_info "Creating temporary branch for cleanup..."
        git checkout --orphan temp-cleanup-branch >/dev/null 2>&1
        log_success "✓ Switched to temporary cleanup branch"
    fi
    
    # Delete main branch if it exists
    if git rev-parse --verify main >/dev/null 2>&1; then
        log_info "Deleting existing main branch..."
        git branch -D main >/dev/null 2>&1 || true
        log_success "✓ Deleted main"
    fi
    
    # Delete with-precomputed-artifacts branch if it exists
    if git rev-parse --verify with-precomputed-artifacts >/dev/null 2>&1; then
        log_info "Deleting existing with-precomputed-artifacts branch..."
        git branch -D with-precomputed-artifacts >/dev/null 2>&1 || true
        log_success "✓ Deleted with-precomputed-artifacts"
    fi
    
    # Delete any other non-standard branches (except temp-cleanup-branch)
    # Note: Add || true to handle case where grep finds no matches (exit code 1)
    git branch | grep -v "temp-cleanup-branch" | grep -v "^\*" | while read -r branch; do
        branch=$(echo "$branch" | xargs)  # Trim whitespace
        if [[ -n "$branch" ]] && [[ "$branch" != "main" ]] && [[ "$branch" != "with-precomputed-artifacts" ]]; then
            log_info "Deleting branch: $branch"
            git branch -D "$branch" >/dev/null 2>&1 || true
        fi
    done || true  # Don't fail if no branches to delete (grep returns 1)
    
    log_success "✓ Branch cleanup complete"
    
    # Now create the new orphan main branch
    log_major_section "Creating orphan main branch with all artifacts"
    log_info "Using branch name: $default_branch"
    
    # Create orphan branch (fresh start, no history)
    log_info "Creating orphan branch: $default_branch"
    git checkout --orphan "$default_branch" >/dev/null 2>&1
    
    # At this point: working directory is populated by rsync (done earlier)
    # but no commits exist yet on this orphan branch
    
    # Create commit message
    commit_msg="QE Submission from HAFiscal-Public $(date -u +%Y-%m-%dT%H:%M:%SZ)

Synchronized from HAFiscal-Public with QE-specific transformations.

This commit includes ALL content from Public INCLUDING precomputed artifacts:
- LaTeX source files (HAFiscal.tex, Subfiles/)
- Bibliography files (HAFiscal.bib, HAFiscal.bbl)
- Generated data files (Code/Empirical/*.dta)
- Computational results (Code/HA-Models/.../*.csv)
- All figures and tables

Branch structure:
- main: Will have precomputed artifacts removed (next commit)
- with-precomputed-artifacts: Will keep all artifacts (branched from this commit)

Build system: HAFiscal-make
Source commit: $(cd $PUBLIC_ROOT && git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
    
    # Copy qe/requirements/ (excluded by rsync but needed for QE compliance)
    log_info "Copying qe/requirements/ from Public..."
    if [[ -d "$PUBLIC_ROOT/qe/requirements" ]]; then
        mkdir -p "$QE_ROOT/qe/requirements"
        cp -r "$PUBLIC_ROOT/qe/requirements"/* "$QE_ROOT/qe/requirements/" 2>/dev/null || true
        log_success "✓ Copied qe/requirements/ directory"
    else
        log_warning "⚠ $PUBLIC_ROOT/qe/requirements/ not found"
    fi
    
    # Basic cleanup (remove unwanted files, but KEEP all precomputed artifacts)
    log_info "Removing unwanted files..."
    
    # Remove development-only files
    find . -maxdepth 3 -type f -name "*.md" | while read -r file; do
        basename_file=$(basename "$file" .md)
        # Skip README files and qe/ directory files
        if [[ "$basename_file" =~ README ]] || [[ "$file" =~ /README/ ]] || [[ "$file" =~ /qe/ ]]; then
            continue
        fi
        # Remove all-caps markdown files (CHANGELOG, CONTRIBUTING, etc.)
        if [[ "$basename_file" =~ ^[A-Z0-9_-]+$ ]]; then
            rm -f "$file"
        fi
    done
    
    # Remove specific unwanted files
    find . -type f -name "*_paperpile*" -delete 2>/dev/null || true
    find . -type f -name "econark.bst" -delete 2>/dev/null || true
    find . -type f -name "*.DEPRECATED" -delete 2>/dev/null || true
    rm -f ./reproduce_min.sh 2>/dev/null || true
    rm -rf ./scripts 2>/dev/null || true
    rm -f ./HAFiscal.md 2>/dev/null || true
    
    log_success "✓ Cleanup complete"
    
    # Stage ALL files including precomputed artifacts
    log_info "Staging all files (including precomputed artifacts)..."
    git add -A >/dev/null 2>&1
    
    # Force-add files that might be gitignored (we want them in THIS commit)
    log_info "Force-adding gitignored artifacts..."
    [[ -f "HAFiscal.bib" ]] && git add --force HAFiscal.bib 2>/dev/null || true
    [[ -f "HAFiscal.bbl" ]] && git add --force HAFiscal.bbl 2>/dev/null || true
    [[ -f "Code/Empirical/rscfp2004.dta" ]] && git add --force Code/Empirical/rscfp2004.dta 2>/dev/null || true
    [[ -f "Code/Empirical/ccbal_answer.dta" ]] && git add --force Code/Empirical/ccbal_answer.dta 2>/dev/null || true
    
    # Force-add CSV files from Reduced_Run/ if they exist
    if [[ -d "Code/HA-Models/FromPandemicCode/Figures/Reduced_Run" ]]; then
        find "Code/HA-Models/FromPandemicCode/Figures/Reduced_Run" -type f -name "*.csv" -exec git add --force {} \; 2>/dev/null || true
    fi
    
    # CRITICAL: Force-add ALL PDF files (they are gitignored but we want them in wpa branch)
    log_info "Force-adding PDF files..."
    PDF_COUNT=$(find . -name "*.pdf" -type f ! -path "./.git/*" 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$PDF_COUNT" -gt 0 ]]; then
        find . -name "*.pdf" -type f ! -path "./.git/*" -exec git add --force {} \; 2>/dev/null || true
        log_info "  Added $PDF_COUNT PDF files"
    else
        log_warning "  No PDF files found to add"
    fi
    
    log_success "✓ All files staged (including artifacts)"

    # Commit everything (first commit on orphan branch)
    log_info "Creating commit with all artifacts..."
    if git commit --no-verify -m "$commit_msg" >/dev/null 2>&1; then
        COMMIT_HASH=$(git rev-parse --short HEAD)
        log_success "✓ Created orphan commit (${COMMIT_HASH})"
    else
        log_error "❌ ERROR: Failed to create commit"
        exit 1
    fi
    
    # Push to remote (force push replaces any existing history)
    if git remote get-url origin >/dev/null 2>&1; then
        log_info "Force-pushing to origin:${default_branch}..."
        remote_url=$(git remote get-url origin)
        
        if [[ "$remote_url" =~ HAFiscal-QE ]]; then
            if git push --no-verify -f origin "${default_branch}"; then
                PUSH_SUCCEEDED=true
                log_success "✓ Pushed to remote"
                
                # Set upstream tracking
                git branch --set-upstream-to=origin/"${default_branch}" "${default_branch}" 2>/dev/null || true
                
                # Cleanup
                git reflog expire --expire=now --all 2>/dev/null || true
                git gc --prune=now --quiet 2>/dev/null || true
            else
                log_error "❌ Push failed"
                PUSH_SUCCEEDED=false
            fi
        else
            log_warning "⚠ Remote URL doesn't match HAFiscal-QE: $remote_url"
            PUSH_SUCCEEDED=false
        fi
    else
        log_info "No remote configured (local only)"
        PUSH_SUCCEEDED=false
    fi
    
    cd "$MAKE_ROOT"
    
    log_major_success "✅ Step 1 complete: main branch created with all artifacts"
    
    # Export push status for main() function
    export FINALIZE_PUSH_SUCCEEDED="$PUSH_SUCCEEDED"
}

# =============================================================================
# STEP 9: QE COMPLIANCE CHECK - REMOVED
# =============================================================================
# Compliance check moved to Step 5 of QE-SUBMISSION-PREPARE.md workflow
# (after README.md is generated in Step 3)
#
# This ensures compliance check runs with complete repository state including:
# - Generated README.md with QE metadata
# - All documentation files
# - Complete replication package
#
# The comprehensive compliance check in QE-SUBMISSION-PREPARE.md generates:
# - Detailed compliance report with evidence
# - Compliance checklist
# - Timestamped documentation
# =============================================================================

# =============================================================================
# STEP 10: CREATE WITH-PRECOMPUTED-ARTIFACTS BRANCH
# =============================================================================

create_wpa_branch() {
    log_major_section "Step 2: Create with-precomputed-artifacts branch from main"
    
    cd "$QE_ROOT"
    
    # Ensure we're on main branch
    if [[ "$(git branch --show-current)" != "main" ]]; then
        log_info "Switching to main branch..."
        git checkout main
    fi
    
    log_info "Current state: main branch has ALL artifacts from sync"
    
    # Delete old wpa branch if it exists
    if git rev-parse --verify with-precomputed-artifacts >/dev/null 2>&1; then
        log_info "Deleting existing with-precomputed-artifacts branch..."
        git branch -D with-precomputed-artifacts
    fi
    
    # Create NORMAL branch from main (NOT orphan - shares history with main)
    log_info "Creating with-precomputed-artifacts as normal branch from main..."
    git checkout -b with-precomputed-artifacts
    log_success "✓ Created branch (shares commit history with main)"
    
    # Modify .gitignore to allow PDF files on this branch
    log_info "Modifying .gitignore to allow PDF files..."
    if [[ -f ".gitignore" ]]; then
        sed -i.bak '/^# PDF files (not tracked in QE submission)$/d' .gitignore
        sed -i.bak '/^\*\.pdf$/d' .gitignore
        rm -f .gitignore.bak
        git add .gitignore
        log_success "✓ Modified .gitignore"
    fi
    
    # Commit the .gitignore change
    log_info "Committing .gitignore modification..."
    if git commit --no-verify -m "Allow PDF files in with-precomputed-artifacts branch" >/dev/null 2>&1; then
        log_success "✓ Committed .gitignore change"
    else
        log_warning "⚠ No changes to commit (possibly already done)"
    fi
    
    # Push to remote
    if git remote get-url origin >/dev/null 2>&1; then
        log_info "Pushing with-precomputed-artifacts to remote..."
        if git push -f origin with-precomputed-artifacts 2>&1; then
            log_success "✓ Pushed to remote"
            git branch --set-upstream-to=origin/with-precomputed-artifacts with-precomputed-artifacts 2>/dev/null || true
            
            # Set as default branch on GitHub
            log_info "Setting with-precomputed-artifacts as default branch..."
            if command -v gh >/dev/null 2>&1; then
                if gh repo edit ${ghID}/HAFiscal-QE --default-branch with-precomputed-artifacts 2>&1; then
                    log_success "✓ Set as default branch on GitHub"
                    
                    # Update local origin/HEAD to point to new default
                    log_info "Updating local origin/HEAD symref..."
                    git remote set-head origin with-precomputed-artifacts >/dev/null 2>&1
                    log_success "✓ Updated origin/HEAD -> origin/with-precomputed-artifacts"
                else
                    log_warning "⚠ Could not set default branch (run manually if needed)"
                fi
            else
                log_warning "⚠ GitHub CLI not found - cannot set default branch"
            fi
        else
            log_error "❌ Push failed"
            exit 1
        fi
    fi
    
    log_major_success "✅ Step 2 complete: with-precomputed-artifacts branch created and set as default"
}

# =============================================================================
# STEP 3: DELETE PRECOMPUTED ARTIFACTS FROM MAIN BRANCH
# =============================================================================

delete_artifacts_from_main() {
    log_major_section "Step 3: Delete precomputed artifacts from main branch"
    
    cd "$QE_ROOT"
    
    # Switch back to main branch
    log_info "Checking out main branch..."
    git checkout main
    log_success "✓ On main branch"
    
    # Delete precomputed artifacts (these are preserved in wpa branch)
    log_info "Deleting precomputed artifacts..."
    
    # Delete .bib files (except in @resources/@local)
    find . -type f -name "*.bib" ! -path "*/@resources/*" ! -path "*/@local/*" -delete 2>/dev/null || true
    
    # Delete .dta files
    find . -type f -name "*.dta" -delete 2>/dev/null || true
    
    # Delete .csv files (except in @resources/@local)
    find . -type f -name "*.csv" ! -path "*/@resources/*" ! -path "*/@local/*" -delete 2>/dev/null || true
    
    # Delete .obj files
    find . -type f -name "*.obj" -delete 2>/dev/null || true
    
    log_success "✓ Deleted precomputed artifacts from working tree"
    
    # Stage deletions
    log_info "Staging deletions..."
    git add -A
    
    # Commit
    log_info "Committing artifact removal..."
    commit_msg="Remove precomputed artifacts from main branch

These artifacts are preserved in with-precomputed-artifacts branch.
Main branch contains source-only submission per QE requirements.

Deleted:
- Bibliography source files (*.bib)
- Data files (*.dta, *.csv)
- Binary model files (*.obj)

To restore: git checkout with-precomputed-artifacts -- <file>"
    
    if git commit --no-verify -m "$commit_msg" >/dev/null 2>&1; then
        log_success "✓ Committed deletions"
    else
        log_info "No changes to commit (artifacts may already be deleted)"
    fi
    
    # Push to remote
    if git remote get-url origin >/dev/null 2>&1; then
        log_info "Pushing main branch to remote..."
        if git push origin main 2>&1; then
            log_success "✓ Pushed to remote"
        else
            log_error "❌ Push failed"
            exit 1
        fi
    fi
    
    log_major_success "✅ Step 3 complete: main branch cleaned (source-only)"
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    check_public_repo_clean                    # Verify Public repo exists and has essential files
    setup_qe_repo                              # Initialize or reuse QE git repository, check GitHub remote
    sync_from_public                           # Rsync base content from Public to QE, delete inappropriate files
    create_pregenerated_flag                   # Create flag file to mark tables/figures as pregenerated
    convert_figures_tables                     # Convert Figures/Tables to QE standalone format, copy class files
    adapt_reproduce_scripts                    # Disable symlink checks, set execute permissions on scripts
    transform_for_qe                           # Remove dev configs/dirs, simplify .gitignore, remove PDF artifacts
    cleanup_qe_directory                       # Copy qe/ directory from Public, remove build artifacts from qe/
    generate_hafiscal_tex                      # Generate HAFiscal.tex AND HAFiscal.bbl from template using build-qe-submission.sh
    # compile_paper_for_qe_bbl                 # REMOVED: Redundant - .bbl already created by generate_hafiscal_tex()
    # check_qe_compliance                      # REMOVED: Run in Step 5 of QE-SUBMISSION-PREPARE.md (after README.md generated)
    
    # NEW WORKFLOW: Three-step branch creation process
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "THREE-STEP BRANCH WORKFLOW"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    finalize_qe_repo                           # STEP 1: Create orphan main with ALL artifacts
    create_wpa_branch                          # STEP 2: Create normal branch from main, set as default
    delete_artifacts_from_main                 # STEP 3: Delete artifacts from main, commit
    
    # =========================================================================
    # BUILD, TEST, AND PUSH DOCKER IMAGE
    # =========================================================================
    
    if [[ -n "${SKIP_DOCKER:-}" ]]; then
        log_major_section "Skipping Docker Image Build (SKIP_DOCKER set)"
        log_info "To build Docker image later, run:"
        log_info "  cd $QE_ROOT && bash reproduce/build-and-test-docker.sh"
        echo ""
    else
        log_major_section "Building, Testing, and Pushing Docker Image"
        
        DOCKER_BUILD_SCRIPT="$QE_ROOT/reproduce/build-and-test-docker.sh"
        
        if [[ -f "$DOCKER_BUILD_SCRIPT" ]]; then
            log_info "Running Docker build-test-push script..."
            log_info "Script: $DOCKER_BUILD_SCRIPT"
            echo ""
            
            cd "$QE_ROOT"
            if bash "$DOCKER_BUILD_SCRIPT"; then
                log_success "✅ Docker image built, tested, and pushed successfully"
            else
                log_error "❌ Docker build-test-push failed"
                log_error "See error messages above for debugging suggestions"
                exit 1
            fi
            cd "$MAKE_ROOT"
        else
            log_warning "⚠ Docker build script not found: $DOCKER_BUILD_SCRIPT"
            log_warning "Skipping Docker image build"
        fi
    fi
    
    echo ""
    log_success ""
    log_major_success "========================================="
    log_major_success "HAFiscal-QE CREATION COMPLETE"
    log_major_success "========================================="
    log_success ""
    log_success "QE repository location: $QE_ROOT"
    log_success "Ready for Quantitative Economics journal submission"
    log_success ""
    
    # ----------------------------------------------------------------------------
    # Push status and next steps
    # ----------------------------------------------------------------------------
    
    # Check if push succeeded (from finalize_qe_repo)
    if [[ "${FINALIZE_PUSH_SUCCEEDED:-false}" == "true" ]]; then
        log_major_section "Repository Pushed to Remote"
        log_success "✓ HAFiscal-QE has been pushed to GitHub"
        log_success "✓ Remote repository updated with single orphan commit"
        echo ""
        
        log_major_section "Next Step: Generate Compliance Report"
        echo ""
        echo "⚠️  IMPORTANT: Before final submission, generate a compliance report."
        echo ""
        echo "⚠️  WARNING: Compliance report generation can take ~20 minutes."
        echo ""
        echo "To generate the compliance report, run:"
        echo ""
        echo "  cd $(dirname "$MAKE_ROOT")"
        echo "  cat QE-COMPLIANCE-TESTING.md | claude"
        echo ""
        echo "Or use your preferred AI assistant with the prompt:"
        echo "  $(dirname "$MAKE_ROOT")/QE-COMPLIANCE-TESTING.md"
        echo ""
        echo "The compliance report will be generated in:"
        echo "  $QE_ROOT/qe/compliance/YYYYMMDD-HHMMh_QE-COMPLIANCE-REPORT.md"
        echo ""
        echo "After the compliance report is generated and you've verified compliance,"
        echo "push the repository again to include the report:"
        echo ""
        echo "  cd $QE_ROOT"
        echo "  git add qe/compliance/*_QE-COMPLIANCE-REPORT.md qe/compliance/*_QE-COMPLIANCE-CHECKLIST.md"
        echo "  git commit -m \"Add compliance verification report\""
        echo "  git push -f origin main"
        echo ""
        
        # Copy second push command to clipboard (macOS)
        if command -v pbcopy >/dev/null 2>&1; then
            SECOND_PUSH_CMD="cd $QE_ROOT && git add qe/compliance/*_QE-COMPLIANCE-*.md && git commit -m \"Add compliance verification report\" && git push -f origin main"
            echo "$SECOND_PUSH_CMD" | pbcopy
            echo "📋 Second push command copied to clipboard"
        fi
        echo ""
    else
        log_major_section "Next Step: Push to Remote"
        
        # Determine which push command to show
        PUSH_SCRIPT="$MAKE_ROOT/post-QE.sh"
        
        if [[ -x "$PUSH_SCRIPT" ]]; then
            PUSH_COMMAND="cd $MAKE_ROOT && ./post-QE.sh \"$QE_ROOT\""
        else
            PUSH_COMMAND="cd $QE_ROOT && git push -f origin main"
        fi
        
        echo ""
        echo "HAFiscal-QE has been created locally but NOT pushed to remote."
        echo ""
        echo "To push the single-commit version to GitHub, run:"
        echo ""
        echo "  $PUSH_COMMAND"
        echo ""
        
        # Copy command to clipboard (macOS)
        if command -v pbcopy >/dev/null 2>&1; then
            echo "$PUSH_COMMAND" | pbcopy
            echo "📋 Push command copied to clipboard - paste to execute"
        fi
        echo ""
        echo "After pushing, generate a compliance report (takes ~20 minutes):"
        echo "  cd $(dirname "$MAKE_ROOT")"
        echo "  cat QE-COMPLIANCE-TESTING.md | claude"
        echo ""
        echo "Then push again to include the compliance report:"
        echo "  cd $QE_ROOT"
        echo "  git add qe/compliance/*_QE-COMPLIANCE-*.md"
        echo "  git commit -m \"Add compliance verification report\""
        echo "  git push -f origin main"
        echo ""
    fi
}

main "$@"

