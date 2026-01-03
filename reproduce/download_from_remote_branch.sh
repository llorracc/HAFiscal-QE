#!/bin/bash
# ============================================================================
# download_from_remote_branch.sh
# ============================================================================
# Shared functions for downloading files from the with-precomputed-artifacts
# branch on GitHub WITHOUT using git operations (avoids bloating .git/objects/).
#
# Usage: source this file, then call download_from_branch()
# ============================================================================

# Configuration
GITHUB_REPO="${GITHUB_REPO:-llorracc/HAFiscal-QE}"
PRECOMPUTED_BRANCH="${PRECOMPUTED_BRANCH:-with-precomputed-artifacts}"
RAW_BASE_URL="https://raw.githubusercontent.com/${GITHUB_REPO}/${PRECOMPUTED_BRANCH}"

# Download a single file from the with-precomputed-artifacts branch
# Arguments:
#   $1 - Remote path (relative to repo root, e.g., "Code/HA-Models/FromPandemicCode/HA_Fiscal_Jacs.obj")
#   $2 - Local destination path (where to save the file)
# Returns: 0 on success, 1 on failure
download_from_branch() {
    local remote_path="$1"
    local local_path="$2"
    local url="${RAW_BASE_URL}/${remote_path}"
    
    # Create destination directory if needed
    local dest_dir=$(dirname "$local_path")
    if [[ ! -d "$dest_dir" ]]; then
        mkdir -p "$dest_dir"
    fi
    
    # Download with progress indicator for large files
    if curl -L --fail --progress-bar -o "$local_path" "$url" 2>&1; then
        if [[ -f "$local_path" && -s "$local_path" ]]; then
            return 0
        else
            rm -f "$local_path" 2>/dev/null
            return 1
        fi
    else
        rm -f "$local_path" 2>/dev/null
        return 1
    fi
}

# Download a single file silently (no progress bar)
download_from_branch_silent() {
    local remote_path="$1"
    local local_path="$2"
    local url="${RAW_BASE_URL}/${remote_path}"
    
    local dest_dir=$(dirname "$local_path")
    if [[ ! -d "$dest_dir" ]]; then
        mkdir -p "$dest_dir"
    fi
    
    if curl -L --fail --silent --show-error -o "$local_path" "$url" 2>&1; then
        if [[ -f "$local_path" && -s "$local_path" ]]; then
            return 0
        fi
    fi
    rm -f "$local_path" 2>/dev/null
    return 1
}

# Check if a file exists on the remote branch (without downloading)
check_remote_file_exists() {
    local remote_path="$1"
    local url="${RAW_BASE_URL}/${remote_path}"
    
    # Use HEAD request to check existence
    local http_code=$(curl -L --silent --head --write-out "%{http_code}" --output /dev/null "$url")
    [[ "$http_code" == "200" ]]
}

# Print error message for download failure
print_download_error() {
    local file="$1"
    echo ""
    echo "❌ ERROR: Could not download ${file}"
    echo ""
    echo "This may indicate:"
    echo "  • Network connectivity issues"
    echo "  • GitHub is temporarily unavailable"
    echo "  • The file doesn't exist on the '${PRECOMPUTED_BRANCH}' branch"
    echo ""
    echo "Attempted URL:"
    echo "  ${RAW_BASE_URL}/${file}"
    echo ""
    echo "Alternative: Run the full computational reproduction:"
    echo "  ./reproduce.sh --comp full"
    echo ""
}

