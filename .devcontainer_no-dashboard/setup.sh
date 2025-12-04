#!/bin/bash
set -e

echo "🚀 Setting up HAFiscal development environment with TeX Live 2025..."
echo "📦 METHOD: TeX Live 2025 (scheme-basic + individual packages)"
echo ""
echo "This matches the standalone Docker image: hafiscal-texlive-2025"
echo ""

START_TEXLIVE=$(date +%s)

# Detect workspace directory from script path (works regardless of $PWD)
SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"

# Try to find workspace directory
# Method 1: If script is in /workspaces/*/.devcontainer/, go up two levels
if [[ "$SCRIPT_DIR" =~ /workspaces/([^/]+)/.devcontainer ]]; then
    WORKSPACE_NAME="${BASH_REMATCH[1]}"
    WORKSPACE_DIR="/workspaces/$WORKSPACE_NAME"
# Method 2: If script path contains workspace name pattern
elif [[ "$SCRIPT_PATH" =~ /workspaces/([^/]+)/ ]]; then
    WORKSPACE_NAME="${BASH_REMATCH[1]}"
    WORKSPACE_DIR="/workspaces/$WORKSPACE_NAME"
# Method 3: Use ${workspaceFolder} if available (from devcontainer)
elif [ -n "${workspaceFolder}" ]; then
    WORKSPACE_DIR="${workspaceFolder}"
# Method 4: Fallback - try to detect from $PWD
else
    WORKSPACE_DIR="/workspaces/$(basename "$PWD" 2>/dev/null || echo "HAFiscal-Latest")"
fi

# Ensure we're in the right directory
if [ -d "$WORKSPACE_DIR" ]; then
    cd "$WORKSPACE_DIR"
else
    echo "❌ Error: Could not find workspace directory: $WORKSPACE_DIR"
    echo "   Script path: $SCRIPT_PATH"
    echo "   PWD: $PWD"
    exit 1
fi

# ============================================================================
# 1. Install TeX Live 2025 from official installer
# ============================================================================
echo "📄 Installing TeX Live 2025 (scheme-basic)..."

# Install prerequisites (should already be done in onCreateCommand, but ensure they're there)
sudo apt-get update
sudo apt-get install -y wget perl build-essential fontconfig curl

# Download and install TeX Live 2025
echo "Downloading TeX Live 2025 installer..."
cd /tmp
wget -q https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz
tar -xzf install-tl-unx.tar.gz
cd "$(find . -maxdepth 1 -name "install-tl-*" -type d | head -1)"

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
sudo ./install-tl --profile=texlive.profile --no-interaction

# Add to PATH
TEXLIVE_BIN=$(find /usr/local/texlive/2025/bin -type d -mindepth 1 -maxdepth 1 | head -1)
export PATH="$TEXLIVE_BIN:$PATH"
echo "export PATH=\"$TEXLIVE_BIN:\$PATH\"" | sudo tee /etc/profile.d/texlive.sh
sudo chmod +x /etc/profile.d/texlive.sh

# Also add to ~/.bashrc and ~/.zshrc for interactive shells
echo "export PATH=\"$TEXLIVE_BIN:\$PATH\"" >> ~/.bashrc
echo "export PATH=\"$TEXLIVE_BIN:\$PATH\"" >> ~/.zshrc 2>/dev/null || true

# Update tlmgr
echo "Updating tlmgr..."
$TEXLIVE_BIN/tlmgr update --self || true

# Install basic collection (includes pdflatex and core tools)
echo "Installing collection-basic (includes pdflatex)..."
$TEXLIVE_BIN/tlmgr install collection-basic || true

# Install individual packages (same as standalone Docker image)
echo "Installing individual LaTeX packages (this may take 10-15 minutes)..."
$TEXLIVE_BIN/tlmgr install \
    accents \
    amsbsy \
    amsfonts \
    amsmath \
    amsopn \
    amssymb \
    amstext \
    amsthm \
    appendix \
    array \
    atbegshi-ltx \
    babel \
    bigintcalc \
    bitset \
    bookmark \
    booktabs \
    cancel \
    caption \
    caption3 \
    changepage \
    currfile \
    dcolumn \
    enumerate \
    enumitem \
    environ \
    epstopdf-base \
    etoolbox \
    eucal \
    expl3 \
    filehook \
    filehook-2020 \
    float \
    fontenc \
    geometry \
    gettitlestring \
    graphics \
    graphicx \
    hhline \
    hycolor \
    hyperref \
    iftex \
    ifthen \
    ifvtex \
    import \
    infwarerr \
    intcalc \
    keyval \
    kvdefinekeys \
    kvoptions \
    kvsetkeys \
    ltxcmds \
    moreverb \
    multirow \
    nameref \
    natbib \
    optional \
    pathtools \
    pdfescape \
    pdftexcmds \
    pgfcore \
    pgfrcs \
    pgfsys \
    placeins \
    refcount \
    rerunfilecheck \
    sansmathaccent \
    koma-script \
    scrbase \
    scrkbase \
    scrlayer \
    scrlayer-scrpage \
    scrlfile \
    scrlfile-hook \
    scrlogo \
    setspace \
    siunitx \
    snapshot \
    stringenc \
    subcaption \
    subfiles \
    tocbasic \
    translations \
    translator \
    trig \
    trimspaces \
    typearea \
    uniquecounter \
    url \
    verbatim \
    webpdf-macros \
    xcolor \
    xparse \
    xpatch \
    xr-hyper \
    xxcolor \
    latexmk \
    || echo "⚠️  Some packages may have failed (check output above)"

# Verify latexmk installation (critical for document compilation)
echo ""
echo "🔍 Verifying latexmk installation..."
if [ -f "$TEXLIVE_BIN/latexmk" ]; then
    echo "✅ latexmk found at: $TEXLIVE_BIN/latexmk"
    $TEXLIVE_BIN/latexmk -v | head -1
else
    echo "⚠️  latexmk not found, attempting to install..."
    sudo $TEXLIVE_BIN/tlmgr install latexmk || {
        echo "❌ Failed to install latexmk - document compilation will fail"
        echo "   You may need to install it manually: sudo $TEXLIVE_BIN/tlmgr install latexmk"
    }
fi

# Update font cache
echo "Updating font cache..."
$TEXLIVE_BIN/mktexlsr || true

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

# Test package availability
echo ""
echo "🔍 Testing package availability..."
for pkg in amsmath hyperref geometry booktabs enumitem natbib siunitx subfiles; do
    if $TEXLIVE_BIN/kpsewhich ${pkg}.sty >/dev/null 2>&1; then
        echo "  ✅ $pkg"
    else
        echo "  ⚠️  $pkg (not found)"
    fi
done

# ============================================================================
# 2. Install UV (Python package manager)
# ============================================================================
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

# Verify .venv was created
if [ ! -d ".venv" ] || [ ! -f ".venv/bin/python" ]; then
    echo "❌ Virtual environment (.venv) was not created successfully"
    echo "   Expected: .venv/bin/python"
    exit 1
fi
echo "✅ Virtual environment created successfully at: $(pwd)/.venv"

# Configure shell to auto-activate .venv on container start
# Use absolute path to .venv for reliability (works regardless of $PWD)
VENV_PATH="$(pwd)/.venv"
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

# Verify virtual environment
if [ -f "$VENV_PATH/bin/python" ]; then
    echo "✅ Virtual environment ready: $VENV_PATH"
    echo "   Python: $($VENV_PATH/bin/python --version 2>&1)"
else
    echo "❌ Virtual environment not found at: $VENV_PATH"
fi

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

