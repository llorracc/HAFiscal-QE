#!/bin/bash
set -e

echo "🚀 Setting up HAFiscal development environment with TeX Live 2025..."
echo "📦 METHOD: TeX Live 2025 (scheme-basic + individual packages)"
echo ""
echo "This matches the standalone Docker image: hafiscal-texlive-2025"
echo ""

START_TEXLIVE=$(date +%s)

# ============================================================================
# Helper Functions
# ============================================================================

# Check disk space (requires at least MIN_FREE_GB GB free)
check_disk_space() {
    local MIN_FREE_GB=${1:-5}
    
    # Get available disk space in GB (cross-platform)
    # Linux: df -BG, macOS: df -g
    if df -BG / &>/dev/null; then
        # Linux: df -BG shows sizes in GB
        local AVAILABLE_GB=$(df -BG / | awk 'NR==2 {print $4}' | sed 's/G//')
    else
        # macOS: df -g shows sizes in GB (lowercase g)
        local AVAILABLE_GB=$(df -g / | awk 'NR==2 {print $4}')
    fi
    
    echo "📊 Checking disk space..."
    echo "   Available: ${AVAILABLE_GB}GB"
    echo "   Required: ${MIN_FREE_GB}GB"
    
    if [ "$AVAILABLE_GB" -lt "$MIN_FREE_GB" ]; then
        echo "❌ ERROR: Insufficient disk space!"
        echo "   Available: ${AVAILABLE_GB}GB, Required: ${MIN_FREE_GB}GB"
        echo "   Please free up disk space or increase available space."
        df -h /
        exit 1
    fi
    echo "✅ Sufficient disk space available"
}

# Retry a command with exponential backoff
# Usage: retry_command <max_attempts> <command>
retry_command() {
    local MAX_ATTEMPTS=$1
    shift
    local ATTEMPT=1
    local DELAY=5
    
    while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
        echo "   Attempt $ATTEMPT/$MAX_ATTEMPTS..."
        if "$@"; then
            return 0
        fi
        
        if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
            echo "   ⚠️  Command failed, retrying in ${DELAY} seconds..."
            sleep $DELAY
            DELAY=$((DELAY * 2))  # Exponential backoff
        fi
        ATTEMPT=$((ATTEMPT + 1))
    done
    
    echo "❌ Command failed after $MAX_ATTEMPTS attempts"
    return 1
}

# Download with retry
download_with_retry() {
    local URL=$1
    local OUTPUT=$2
    local MAX_ATTEMPTS=${3:-3}
    
    echo "📥 Downloading: $URL"
    # Use --show-progress for better visibility in CI, but allow it to fail gracefully
    retry_command $MAX_ATTEMPTS wget --show-progress --progress=bar:force "$URL" -O "$OUTPUT" || \
    retry_command $MAX_ATTEMPTS wget "$URL" -O "$OUTPUT"  # Fallback to simple wget if progress fails
}

# Detect workspace directory from script path (works regardless of $PWD)
SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"

# Try to find workspace directory
# Method 1: If script is in /workspaces/*/reproduce/docker/, go up two levels
if [[ "$SCRIPT_DIR" =~ /workspaces/([^/]+)/reproduce/docker ]]; then
    WORKSPACE_NAME="${BASH_REMATCH[1]}"
    WORKSPACE_DIR="/workspaces/$WORKSPACE_NAME"
# Method 2: If script is in local reproduce/docker/, go up two levels
elif [[ "$SCRIPT_DIR" =~ /([^/]+)/reproduce/docker ]]; then
    WORKSPACE_NAME="${BASH_REMATCH[1]}"
    # Try to find full path
    if [[ "$SCRIPT_DIR" =~ ^/workspaces/ ]]; then
        WORKSPACE_DIR="/workspaces/$WORKSPACE_NAME"
    else
        WORKSPACE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
    fi
# Method 3: If script path contains workspace name pattern
elif [[ "$SCRIPT_PATH" =~ /workspaces/([^/]+)/ ]]; then
    WORKSPACE_NAME="${BASH_REMATCH[1]}"
    WORKSPACE_DIR="/workspaces/$WORKSPACE_NAME"
# Method 4: Use ${workspaceFolder} if available (from devcontainer)
elif [ -n "${workspaceFolder}" ]; then
    WORKSPACE_DIR="${workspaceFolder}"
# Method 4b: Use GITHUB_WORKSPACE if available (from GitHub Actions)
elif [ -n "${GITHUB_WORKSPACE}" ]; then
    WORKSPACE_DIR="${GITHUB_WORKSPACE}"
# Method 5: Fallback - try to detect from $PWD
else
    # Try to detect repo name from git remote or directory name
    if [ -d .git ]; then
        REPO_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || basename "$PWD")
    else
        REPO_NAME=$(basename "$PWD" 2>/dev/null || echo "${REPO_NAME:-HAFiscal}")
    fi
    WORKSPACE_DIR="/workspaces/${REPO_NAME}"
fi

# Ensure we're in the right directory
if [ -d "$WORKSPACE_DIR" ]; then
    cd "$WORKSPACE_DIR"
    echo "✅ Working directory: $WORKSPACE_DIR"
else
    echo "❌ ERROR: Could not find workspace directory: $WORKSPACE_DIR"
    echo "   Script path: $SCRIPT_PATH"
    echo "   Script dir: $SCRIPT_DIR"
    echo "   PWD: $PWD"
    echo "   GITHUB_WORKSPACE: ${GITHUB_WORKSPACE:-<not set>}"
    echo "   workspaceFolder: ${workspaceFolder:-<not set>}"
    echo ""
    echo "   Available directories in parent:"
    ls -la "$(dirname "$SCRIPT_DIR")" 2>/dev/null || echo "   Cannot list parent directory"
    exit 1
fi

# ============================================================================
# 1. Install TeX Live 2025 from official installer
# ============================================================================
echo "📄 Installing TeX Live 2025 (scheme-basic)..."

# Check disk space before starting (TeX Live needs ~2GB for scheme-basic + packages)
check_disk_space 3

# Install prerequisites (should already be done in onCreateCommand, but ensure they're there)
# Skip on macOS if SKIP_APT_GET is set (prerequisites installed via Homebrew)
if [ "${SKIP_APT_GET:-}" != "1" ]; then
    echo "Installing prerequisites via apt-get..."
    if ! sudo apt-get update; then
        echo "❌ ERROR: Failed to update package lists"
        exit 1
    fi

    if ! sudo apt-get install -y wget perl build-essential fontconfig curl; then
        echo "❌ ERROR: Failed to install prerequisites"
        exit 1
    fi
else
    echo "⏭️  Skipping apt-get (SKIP_APT_GET=1, prerequisites installed externally)"
fi

# Download and install TeX Live 2025
echo "Downloading TeX Live 2025 installer..."
cd /tmp

# Clean up any previous installation attempts
rm -rf install-tl-unx.tar.gz install-tl-*

# Download with retry logic
INSTALLER_URL="https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz"
if ! download_with_retry "$INSTALLER_URL" "install-tl-unx.tar.gz" 3; then
    echo "❌ ERROR: Failed to download TeX Live installer after retries"
    echo "   URL: $INSTALLER_URL"
    exit 1
fi

# Extract installer
echo "Extracting installer..."
if ! tar -xzf install-tl-unx.tar.gz; then
    echo "❌ ERROR: Failed to extract TeX Live installer"
    exit 1
fi

INSTALL_DIR=$(find . -maxdepth 1 -name "install-tl-*" -type d | head -1)
if [ -z "$INSTALL_DIR" ] || [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ ERROR: Could not find installer directory after extraction"
    exit 1
fi

cd "$INSTALL_DIR"

# Create installation profile (scheme-basic, same as standalone Docker image)
cat > texlive.profile << 'PROFILE'
selected_scheme scheme-basic
TEXDIR /usr/local/texlive/2025
TEXMFLOCAL /usr/local/texlive/texmf-local
TEXMFHOME ~/texmf
TEXMFVAR ~/.texlive2025/texmf-var
TEXMFCONFIG ~/.texlive2025/texmf-config
instopt_adjustpath 1
instopt_adjustrepo 1
tlpdbopt_autobackup 0
tlpdbopt_desktop_integration 0
tlpdbopt_file_assocs 0
tlpdbopt_post_code 1
PROFILE

# Install TeX Live
echo "Installing TeX Live 2025 scheme-basic (this may take 10-15 minutes)..."
echo "   This is a large installation - please be patient..."
if ! sudo ./install-tl --profile=texlive.profile --no-interaction; then
    echo "❌ ERROR: TeX Live installation failed"
    echo "   Check disk space and network connectivity"
    df -h /
    exit 1
fi

# Verify installation succeeded
if [ ! -d "/usr/local/texlive/2025" ]; then
    echo "❌ ERROR: TeX Live installation directory not found"
    echo "   Expected: /usr/local/texlive/2025"
    exit 1
fi

# Add to PATH
TEXLIVE_BIN=$(find /usr/local/texlive/2025/bin -type d -mindepth 1 -maxdepth 1 | head -1)
if [ -z "$TEXLIVE_BIN" ] || [ ! -d "$TEXLIVE_BIN" ]; then
    echo "❌ ERROR: Could not find TeX Live bin directory"
    echo "   Searched in: /usr/local/texlive/2025/bin"
    ls -la /usr/local/texlive/2025/bin/ 2>/dev/null || echo "   Directory does not exist"
    exit 1
fi

export PATH="$TEXLIVE_BIN:$PATH"

# Add to system-wide profile if possible (skip if directory doesn't exist or no permission)
if [ -d "/etc/profile.d" ] && [ -w "/etc/profile.d" ]; then
    echo "export PATH=\"$TEXLIVE_BIN:\$PATH\"" | sudo tee /etc/profile.d/texlive.sh > /dev/null
    sudo chmod +x /etc/profile.d/texlive.sh
elif sudo mkdir -p /etc/profile.d 2>/dev/null; then
    echo "export PATH=\"$TEXLIVE_BIN:\$PATH\"" | sudo tee /etc/profile.d/texlive.sh > /dev/null
    sudo chmod +x /etc/profile.d/texlive.sh
else
    echo "⏭️  Skipping /etc/profile.d/texlive.sh (no permission or directory unavailable)"
fi

# Also add to ~/.bashrc and ~/.zshrc for interactive shells
echo "export PATH=\"$TEXLIVE_BIN:\$PATH\"" >> ~/.bashrc
echo "export PATH=\"$TEXLIVE_BIN:\$PATH\"" >> ~/.zshrc 2>/dev/null || true

# Update tlmgr with retry
echo "Updating tlmgr..."
if ! retry_command 3 sudo $TEXLIVE_BIN/tlmgr update --self; then
    echo "⚠️  Warning: tlmgr self-update failed after retries (may be OK if already up-to-date)"
    echo "   Continuing with installation..."
fi

# Install basic collection (includes pdflatex and core tools) with retry
echo "Installing collection-basic (includes pdflatex)..."
echo "   This may take several minutes..."
if ! retry_command 3 sudo $TEXLIVE_BIN/tlmgr install collection-basic; then
    echo "❌ ERROR: Failed to install collection-basic after retries - this is critical!"
    echo "   pdflatex and other core tools will not be available."
    echo "   Check network connectivity and disk space:"
    df -h /
    exit 1
fi

# Verify collection-basic was installed
if ! command -v pdflatex >/dev/null 2>&1; then
    echo "❌ ERROR: pdflatex not found after installing collection-basic"
    echo "   PATH: $PATH"
    echo "   Expected location: $TEXLIVE_BIN/pdflatex"
    ls -la "$TEXLIVE_BIN/pdflatex" 2>/dev/null || echo "   pdflatex not found in bin directory"
    exit 1
fi
echo "✅ pdflatex verified: $(which pdflatex)"

# ============================================================================
# Parse LaTeX packages from required_latex_packages.txt (Single Source of Truth)
# ============================================================================
parse_latex_packages() {
    local PACKAGES_FILE="${WORKSPACE_DIR}/reproduce/required_latex_packages.txt"
    
    if [ ! -f "$PACKAGES_FILE" ]; then
        echo "❌ ERROR: Required packages file not found: $PACKAGES_FILE" >&2
        echo "   Cannot determine which LaTeX packages to install" >&2
        exit 1
    fi
    
    echo "📄 Reading LaTeX packages from: $PACKAGES_FILE" >&2
    
    # Extract package names from file:
    # - Skip lines starting with # (comments)
    # - Skip empty lines
    # - Remove inline comments (anything after #)
    # - Trim whitespace
    # - Output as space-separated list on single line
    local PACKAGES=$(grep -v '^#\|^$\|^##' "$PACKAGES_FILE" | \
                     sed 's/[[:space:]]*#.*//' | \
                     tr '\n' ' ' | \
                     sed 's/[[:space:]]\+/ /g')
    
    # Add critical packages that may not be in the file yet
    PACKAGES="$PACKAGES latexmk"
    
    # Count packages (for user feedback)
    local PKG_COUNT=$(echo "$PACKAGES" | wc -w | tr -d ' ')
    echo "   Found $PKG_COUNT packages to install" >&2
    
    echo "$PACKAGES"
}

# Install individual packages from required_latex_packages.txt (Single Source of Truth)
# Note: Some packages may already be installed via collection-basic or may not exist as standalone packages
# We install what we can and verify critical packages afterward
echo "Installing individual LaTeX packages (this may take 10-15 minutes)..."
echo "   Checking disk space before package installation..."
check_disk_space 2  # Need at least 2GB for packages

# Many packages are already included in collection-basic or are part of other packages
# We continue even if some packages are "not present" - we'll verify critical ones afterward

# Get package list from SST file
LATEX_PACKAGES=$(parse_latex_packages)

# Install packages with retry logic (wrapped in a function to handle pipe correctly)
install_packages_with_retry() {
    # Use word splitting intentionally to pass each package as separate argument
    # shellcheck disable=SC2086
    sudo $TEXLIVE_BIN/tlmgr install $LATEX_PACKAGES 2>&1 | tee /tmp/tlmgr-install.log
    return ${PIPESTATUS[0]}
}

# Try installing packages with retry
if ! retry_command 2 install_packages_with_retry; then
    TLMGR_EXIT_CODE=1
    echo "⚠️  Package installation failed after retries"
    
    # Check if error is just about packages not present (which is OK if they're in collections)
    if [ -f /tmp/tlmgr-install.log ] && grep -q "package.*not present in repository" /tmp/tlmgr-install.log; then
        echo "⚠️  Some packages not found as standalone (may be part of collections - will verify critical packages)"
    else
        echo "⚠️  tlmgr install had errors - will verify critical packages"
        echo "   Log saved to: /tmp/tlmgr-install.log"
        if [ -f /tmp/tlmgr-install.log ]; then
            echo "   Last 20 lines of log:"
            tail -20 /tmp/tlmgr-install.log
        fi
    fi
else
    TLMGR_EXIT_CODE=0
    echo "✅ Package installation completed successfully"
fi

# Verify latexmk installation (critical for document compilation)
echo ""
echo "🔍 Verifying latexmk installation..."
if [ -f "$TEXLIVE_BIN/latexmk" ]; then
    echo "✅ latexmk found at: $TEXLIVE_BIN/latexmk"
    $TEXLIVE_BIN/latexmk -v | head -1
else
    echo "⚠️  latexmk not found, attempting to install with retry..."
    if ! retry_command 2 sudo $TEXLIVE_BIN/tlmgr install latexmk; then
        echo "❌ ERROR: Failed to install latexmk after retries - document compilation will fail"
        echo "   You may need to install it manually: sudo $TEXLIVE_BIN/tlmgr install latexmk"
        exit 1
    fi
fi

# Update font cache using TeX Live tools
echo "Updating font cache..."
$TEXLIVE_BIN/mktexlsr || true

# Configure TeX Live font generation system
# Ensure font generation directories are writable (uses TeX Live's TEXMFVAR path)
echo "Configuring TeX Live font generation directories..."
mkdir -p ~/.texlive2025/texmf-var/fonts/tfm ~/.texlive2025/texmf-var/fonts/pk
chmod -R u+w ~/.texlive2025/texmf-var 2>/dev/null || true

# Pre-generate commonly used fonts using TeX Live's mktextfm tool
# This prevents "mktextfm failed" errors during document compilation
# Using ONLY TeX Live tools (cross-platform compatible)
echo "Pre-generating commonly used fonts (TeX Live mktextfm)..."
TEXLIVE_BIN_PATH="$TEXLIVE_BIN"
export PATH="$TEXLIVE_BIN_PATH:$PATH"
# Generate base Computer Modern fonts that are commonly needed
for font in cmr10 cmr12 cmbx10 cmbx12 cmti10 cmtt10; do
    echo "  Generating $font..."
    $TEXLIVE_BIN_PATH/mktextfm $font >/dev/null 2>&1 || true
done
# Generate T1-encoded fonts (putr8t, putb8t, etc.) that are commonly used
for font in putr8t putb8t putri8t putrc8t pcrr8t; do
    echo "  Generating $font..."
    $TEXLIVE_BIN_PATH/mktextfm $font >/dev/null 2>&1 || true
done
echo "✅ Font pre-generation completed (TeX Live tools only)"

END_TEXLIVE=$(date +%s)
TEXLIVE_DURATION=$((END_TEXLIVE - START_TEXLIVE))
echo "✅ TeX Live 2025 installation completed in ${TEXLIVE_DURATION}s"
echo "${TEXLIVE_DURATION}" > /tmp/texlive-install-time.txt

# Verify LaTeX installation
echo ""
echo "🔍 Verifying LaTeX installation..."
if command -v pdflatex >/dev/null 2>&1; then
    echo "✅ pdflatex found: $(which pdflatex)"
    pdflatex --version | head -3
else
    echo "⚠️  pdflatex not in PATH, checking /usr/local/texlive/2025..."
    if [ -f "$TEXLIVE_BIN/pdflatex" ]; then
        echo "✅ pdflatex found at: $TEXLIVE_BIN/pdflatex"
        $TEXLIVE_BIN/pdflatex --version | head -3
    else
        echo "❌ pdflatex not found!"
        exit 1
    fi
fi

# Test package availability (including critical packages)
echo ""
echo "🔍 Testing package availability..."
# Check for actual files, not package names (some packages are collections)
# koma-script is a collection - check for scrartcl.cls which is the main class it provides
CRITICAL_CHECKS=("amsmath.sty:amsmath" "hyperref.sty:hyperref" "geometry.sty:geometry" "natbib.sty:natbib" "snapshot.sty:snapshot" "scrartcl.cls:koma-script" "subfiles.sty:subfiles")
WARNING_PACKAGES=("booktabs" "enumitem" "siunitx")
MISSING_CRITICAL=0

for check in "${CRITICAL_CHECKS[@]}"; do
    FILE="${check%%:*}"
    PKG_NAME="${check##*:}"
    if $TEXLIVE_BIN/kpsewhich "$FILE" >/dev/null 2>&1; then
        echo "  ✅ $PKG_NAME"
    else
        echo "  ❌ $PKG_NAME (CRITICAL - $FILE not found)"
        MISSING_CRITICAL=1
    fi
done

for pkg in "${WARNING_PACKAGES[@]}"; do
    if $TEXLIVE_BIN/kpsewhich ${pkg}.sty >/dev/null 2>&1; then
        echo "  ✅ $pkg"
    else
        echo "  ⚠️  $pkg (not found - may cause issues)"
    fi
done

if [ $MISSING_CRITICAL -eq 1 ]; then
    echo ""
    echo "❌ ERROR: Critical LaTeX packages are missing!"
    echo "   Document compilation will fail without these packages."
    echo "   Please check the installation output above for errors."
    exit 1
fi

# ============================================================================
# 2. Install UV (Python package manager)
# ============================================================================

# Skip Python environment setup if requested (for Docker builds)
# Python environment will be built at container startup for correct architecture
if [ "${SKIP_PYTHON_SETUP:-}" = "1" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "ℹ️  Skipping Python environment setup (SKIP_PYTHON_SETUP=1)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Python environment will be built at container startup"
    echo "This ensures packages are built for the correct architecture"
    echo ""
    
    # Still show summary but skip UV/Python setup
    TEXLIVE_DURATION=$(($(date +%s) - START_TEXLIVE))
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ TeX Live 2025 setup complete!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📊 Installation Summary:"
    echo "  - TeX Live Version: 2025 (latest)"
    echo "  - Scheme: basic + 96 individual packages"
    echo "  - TeX Live installation time: ${TEXLIVE_DURATION}s"
    echo "  - Python environment: Will be built at startup"
    echo "  - Matches standalone Docker image: hafiscal-texlive-2025"
    echo ""
    exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Installing UV (Python package manager)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

START_UV=$(date +%s)

# Install UV via official installer
echo "Installing UV..."
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add UV to PATH (UV installer may install to ~/.local/bin or ~/.cargo/bin)
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
echo "export PATH=\"\$HOME/.local/bin:\$HOME/.cargo/bin:\$PATH\"" >> ~/.bashrc

# Also add to .zshrc if zsh is available
if command -v zsh >/dev/null 2>&1; then
    [ -f ~/.zshrc ] || touch ~/.zshrc
    if ! grep -q "\.local/bin.*\.cargo/bin" ~/.zshrc 2>/dev/null; then
        echo "export PATH=\"\$HOME/.local/bin:\$HOME/.cargo/bin:\$PATH\"" >> ~/.zshrc
    fi
fi

# Verify UV installation (check both common locations)
if command -v uv >/dev/null 2>&1; then
    echo "✅ UV installed: $(which uv)"
    uv --version
else
    echo "⚠️  UV not in PATH, checking common locations..."
    if [ -f "$HOME/.local/bin/uv" ]; then
        echo "✅ UV found at: $HOME/.local/bin/uv"
        $HOME/.local/bin/uv --version
        export PATH="$HOME/.local/bin:$PATH"
    elif [ -f "$HOME/.cargo/bin/uv" ]; then
        echo "✅ UV found at: $HOME/.cargo/bin/uv"
        $HOME/.cargo/bin/uv --version
        export PATH="$HOME/.cargo/bin:$PATH"
    else
        echo "❌ UV installation failed! Checked ~/.local/bin and ~/.cargo/bin"
        exit 1
    fi
fi

END_UV=$(date +%s)
UV_DURATION=$((END_UV - START_UV))
echo "✅ UV installation completed in ${UV_DURATION}s"

# ============================================================================
# 3. Set up Python environment with UV
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐍 Setting up Python environment with UV"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Ensure we're in the workspace directory (reuse detection from above)
if [ -d "$WORKSPACE_DIR" ]; then
    cd "$WORKSPACE_DIR"
else
    echo "❌ Error: Could not find workspace directory: $WORKSPACE_DIR"
    exit 1
fi

# Create/update Python environment with UV
echo "Creating Python virtual environment with UV..."

# Ensure UV is in PATH before proceeding
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# Verify UV is available before creating venv
if ! command -v uv >/dev/null 2>&1; then
    echo "❌ Error: UV is not available in PATH"
    echo "   Checked: $HOME/.local/bin and $HOME/.cargo/bin"
    echo "   Current PATH: $PATH"
    exit 1
fi

echo "✅ UV verified: $(which uv)"
uv --version

# Use the proper environment setup script if available (has better error handling)
if [ -f "./reproduce/reproduce_environment_comp_uv.sh" ]; then
    echo "Using reproduce_environment_comp_uv.sh for environment setup..."
    bash ./reproduce/reproduce_environment_comp_uv.sh
else
    # Fallback: direct uv sync (less robust but works if script not available)
    echo "Using direct uv sync (reproduce_environment_comp_uv.sh not found)..."
    if ! uv sync --all-groups; then
        echo "❌ uv sync failed - virtual environment may not be complete"
        exit 1
    fi
fi

# Detect platform-specific venv path with architecture (reproduce_environment_comp_uv.sh creates arch-specific venvs)
# Format: .venv-{platform}-{arch} (hyphen separator for consistency)
# Examples: .venv-linux-x86_64, .venv-darwin-arm64
PLATFORM_VENV=""
PLATFORM=""
ARCH=""

# Detect platform
case "$(uname -s)" in
    Darwin)
        PLATFORM="darwin"
        ;;
    Linux)
        PLATFORM="linux"
        ;;
esac

# Detect architecture - use hardware detection on macOS, uname on Linux
if [ "$PLATFORM" = "darwin" ]; then
    # macOS: Check actual hardware, not Rosetta-reported arch
    if sysctl -n hw.optional.arm64 2>/dev/null | grep -q 1; then
        ARCH="arm64"  # Apple Silicon
    else
        ARCH="x86_64"  # Intel Mac
    fi
else
    # Linux/other: use uname
    ARCH="$(uname -m)"
fi

# Normalize architecture names
case "$ARCH" in
    arm64) NORMALIZED_ARCH="arm64" ;;
    aarch64) NORMALIZED_ARCH="aarch64" ;;
    x86_64) NORMALIZED_ARCH="x86_64" ;;
    *) NORMALIZED_ARCH="$ARCH" ;;
esac

# Set platform-specific venv path with architecture (using hyphen separator)
if [ -n "$PLATFORM" ]; then
    PLATFORM_VENV=".venv-${PLATFORM}-${NORMALIZED_ARCH}"
else
    PLATFORM_VENV=".venv"
fi

# Check for platform-specific venv first (created by reproduce_environment_comp_uv.sh)
# Then check for .venv symlink or directory (fallback)
if [ -d "$PLATFORM_VENV" ] && [ -f "$PLATFORM_VENV/bin/python" ]; then
    VENV_PATH="$(pwd)/$PLATFORM_VENV"
    echo "✅ Found architecture-specific virtual environment: $PLATFORM_VENV"
    # Ensure symlink exists (reproduce_environment_comp_uv.sh should create it, but verify)
    if [ ! -e ".venv" ]; then
        ln -s "$PLATFORM_VENV" .venv
        echo "✅ Created symlink: .venv -> $PLATFORM_VENV"
    fi
elif [ -d ".venv" ] && [ -f ".venv/bin/python" ]; then
    VENV_PATH="$(pwd)/.venv"
    echo "✅ Found virtual environment: .venv"
else
    echo "❌ Virtual environment was not created successfully"
    echo "   Checked: $PLATFORM_VENV and .venv"
    echo "   Expected: $PLATFORM_VENV/bin/python or .venv/bin/python"
    exit 1
fi

echo "✅ Virtual environment verified at: $VENV_PATH"

# Configure shell to auto-activate venv on container start
# Use absolute path for reliability (works regardless of $PWD)
echo "Configuring shell auto-activation for: $VENV_PATH"

# Create activation snippet that will be sourced by shells
ACTIVATE_SNIPPET="# Auto-activate HAFiscal virtual environment
if [ -f \"$VENV_PATH/bin/activate\" ]; then
    source \"$VENV_PATH/bin/activate\"
fi"

# Add to .bashrc if not already present
if ! grep -q "Auto-activate HAFiscal virtual environment" ~/.bashrc 2>/dev/null; then
    echo "" >> ~/.bashrc
    echo "$ACTIVATE_SNIPPET" >> ~/.bashrc
    echo "✅ Added .venv auto-activation to ~/.bashrc"
fi

# Add to .zshrc if zsh is available
if command -v zsh >/dev/null 2>&1; then
    # Create .zshrc if it doesn't exist
    [ -f ~/.zshrc ] || touch ~/.zshrc
    if ! grep -q "Auto-activate HAFiscal virtual environment" ~/.zshrc 2>/dev/null; then
        echo "" >> ~/.zshrc
        echo "$ACTIVATE_SNIPPET" >> ~/.zshrc
        echo "✅ Added .venv auto-activation to ~/.zshrc"
    fi
fi

# Final verification
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Final Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Verify UV is in PATH
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
    echo "✅ UV is in PATH: $(which uv)"
    uv --version | head -1
else
    echo "⚠️  UV not found in PATH (may need shell restart)"
fi

# Verify virtual environment (should already be verified above, but double-check)
if [ -f "$VENV_PATH/bin/python" ]; then
    echo "✅ Virtual environment ready: $VENV_PATH"
    echo "   Python: $($VENV_PATH/bin/python --version 2>&1)"
else
    echo "❌ Virtual environment not found at: $VENV_PATH"
    echo "   This should not happen - earlier verification should have caught this"
    exit 1
fi

# ============================================================================
# Configure platform-agnostic virtual environment auto-activation
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Configuring shell auto-activation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Adding platform-agnostic venv activation to shell RC files..."

# Create activation code that will be appended to RC files
# This code detects platform and architecture, then activates the correct venv
ACTIVATION_CODE='
# Auto-activate HAFiscal virtual environment (platform and architecture-specific)
# Detects and activates the appropriate venv for the current platform and architecture
if [ -z "${VIRTUAL_ENV:-}" ]; then
    # Determine workspace directory
    HAFISCAL_WORKSPACE="/workspace"
    if [ ! -d "$HAFISCAL_WORKSPACE" ]; then
        # Fallback: try to find workspace from common locations
        if [ -d "/workspace" ]; then
            HAFISCAL_WORKSPACE="/workspace"
        elif [ -d "$HOME/workspace" ]; then
            HAFISCAL_WORKSPACE="$HOME/workspace"
        elif [ -d "$HOME/HAFiscal-Public" ]; then
            HAFISCAL_WORKSPACE="$HOME/HAFiscal-Public"
        fi
    fi

    # Detect platform and architecture
    HAFISCAL_VENV=""
    HAFISCAL_ARCH=$(uname -m)
    case "$(uname -s)" in
        Darwin)
            # macOS: look for .venv-darwin-{arch}
            if [ -f "$HAFISCAL_WORKSPACE/.venv-darwin-$HAFISCAL_ARCH/bin/activate" ]; then
                HAFISCAL_VENV="$HAFISCAL_WORKSPACE/.venv-darwin-$HAFISCAL_ARCH"
            fi
            ;;
        Linux)
            # Linux: look for .venv-linux-{arch}
            if [ -f "$HAFISCAL_WORKSPACE/.venv-linux-$HAFISCAL_ARCH/bin/activate" ]; then
                HAFISCAL_VENV="$HAFISCAL_WORKSPACE/.venv-linux-$HAFISCAL_ARCH"
            fi
            ;;
    esac

    # Activate if found (architecture is encoded in name, so no verification needed)
    if [ -n "$HAFISCAL_VENV" ] && [ -f "$HAFISCAL_VENV/bin/activate" ]; then
        source "$HAFISCAL_VENV/bin/activate"
    fi
fi'

# Add activation code to .bashrc if not already present
if [ -f "$HOME/.bashrc" ]; then
    if ! grep -q "Auto-activate HAFiscal virtual environment" "$HOME/.bashrc" 2>/dev/null; then
        echo "$ACTIVATION_CODE" >> "$HOME/.bashrc"
        echo "✅ Added activation code to ~/.bashrc"
    else
        echo "✅ Activation code already in ~/.bashrc"
    fi
else
    echo "⚠️  ~/.bashrc not found, skipping"
fi

# Add activation code to .zshrc if it exists
if [ -f "$HOME/.zshrc" ]; then
    if ! grep -q "Auto-activate HAFiscal virtual environment" "$HOME/.zshrc" 2>/dev/null; then
        echo "$ACTIVATION_CODE" >> "$HOME/.zshrc"
        echo "✅ Added activation code to ~/.zshrc"
    else
        echo "✅ Activation code already in ~/.zshrc"
    fi
else
    echo "ℹ️  ~/.zshrc not found, skipping"
fi

# Add activation code to .profile for login shells
# .profile needs different logic - check PATH instead of VIRTUAL_ENV
# to avoid skipping when VIRTUAL_ENV is already set but PATH isn't updated
ACTIVATION_CODE_PROFILE='
# Auto-activate HAFiscal virtual environment (platform and architecture-specific)
if [ -z "${VIRTUAL_ENV:-}" ]; then
    # Determine workspace directory
    HAFISCAL_WORKSPACE="/workspace"
    if [ ! -d "$HAFISCAL_WORKSPACE" ]; then
        # Fallback: try to find workspace from common locations
        if [ -d "/workspace" ]; then
            HAFISCAL_WORKSPACE="/workspace"
        elif [ -d "$HOME/workspace" ]; then
            HAFISCAL_WORKSPACE="$HOME/workspace"
        elif [ -d "$HOME/HAFiscal-Public" ]; then
            HAFISCAL_WORKSPACE="$HOME/HAFiscal-Public"
        fi
    fi

    # Detect platform and architecture
    HAFISCAL_VENV=""
    HAFISCAL_ARCH=$(uname -m)
    case "$(uname -s)" in
        Darwin)
            if [ -f "$HAFISCAL_WORKSPACE/.venv-darwin-$HAFISCAL_ARCH/bin/activate" ]; then
                HAFISCAL_VENV="$HAFISCAL_WORKSPACE/.venv-darwin-$HAFISCAL_ARCH"
            fi
            ;;
        Linux)
            if [ -f "$HAFISCAL_WORKSPACE/.venv-linux-$HAFISCAL_ARCH/bin/activate" ]; then
                HAFISCAL_VENV="$HAFISCAL_WORKSPACE/.venv-linux-$HAFISCAL_ARCH"
            fi
            ;;
    esac

    # Activate if found
    if [ -n "$HAFISCAL_VENV" ] && [ -f "$HAFISCAL_VENV/bin/activate" ]; then
        # Check if already activated correctly (PATH contains venv bin)
        case ":$PATH:" in
            *":$HAFISCAL_VENV/bin:"*)
                # Already activated correctly, no action needed
                ;;
            *)
                # Activate the venv
                source "$HAFISCAL_VENV/bin/activate"
                ;;
        esac
    fi
fi'

if [ -f "$HOME/.profile" ]; then
    if ! grep -q "Auto-activate HAFiscal virtual environment" "$HOME/.profile" 2>/dev/null; then
        echo "$ACTIVATION_CODE_PROFILE" >> "$HOME/.profile"
        echo "✅ Added activation code to ~/.profile"
    else
        echo "✅ Activation code already in ~/.profile"
    fi
else
    echo "ℹ️  ~/.profile not found, skipping"
fi

echo ""
echo "✅ Shell auto-activation configured"
echo "   Virtual environments will automatically activate when opening new shells"
echo ""

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ TeX Live 2025 + UV setup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Installation Summary:"
echo "  - TeX Live Version: 2025 (latest)"
echo "  - Scheme: basic + 96 individual packages"
echo "  - TeX Live installation time: ${TEXLIVE_DURATION}s"
echo "  - UV installation time: ${UV_DURATION}s"
echo "  - Virtual environment: $VENV_PATH"
echo "  - Matches standalone Docker image: hafiscal-texlive-2025"
echo ""
echo "💡 Note: Custom packages (econark, hiddenappendix, etc.) must be"
echo "   provided separately in the project repository."


