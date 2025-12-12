#!/bin/bash
# HAFiscal Environment Setup with UV
# This script sets up the Python environment using UV package manager
# This is the SINGLE SOURCE OF TRUTH for UV environment setup

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Platform-specific venv detection
# Returns the appropriate venv directory name based on the current platform
get_platform_venv_path() {
    local platform=""
    
    # Detect platform
    case "$(uname -s)" in
        Darwin)
            platform="darwin"
            ;;
        Linux)
            platform="linux"
            ;;
        *)
            # Fallback to generic .venv for unknown platforms
            platform=""
            ;;
    esac
    
    # Return platform-specific venv path, or fallback to .venv
    if [[ -n "$platform" ]]; then
        echo "$PROJECT_ROOT/.venv-$platform"
    else
        echo "$PROJECT_ROOT/.venv"
    fi
}

# Get the platform-specific venv path
VENV_PATH=$(get_platform_venv_path)
VENV_NAME=$(basename "$VENV_PATH")

echo "========================================"
echo "HAFiscal Environment Setup (UV)"
echo "========================================"
echo ""
echo "Platform: $(uname -s) ($(uname -m))"
echo "Venv location: $VENV_NAME"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1: Check if platform-specific venv already exists and is valid
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Check for platform-specific venv first, then legacy .venv
if [[ -d "$VENV_PATH" ]] && [[ -f "$VENV_PATH/bin/python" ]]; then
    echo "✅ Found existing UV environment at $VENV_NAME/"
    
    # Verify it has HARK installed
    if "$VENV_PATH/bin/python" -c "import HARK" 2>/dev/null; then
        echo "✅ UV environment has HARK installed"
        
        # Get environment details
        HARK_VERSION=$("$VENV_PATH/bin/python" -c "import HARK; print(HARK.__version__)" 2>/dev/null || echo "unknown")
        PYTHON_VERSION=$("$VENV_PATH/bin/python" --version 2>&1 | awk '{print $2}')
        PYTHON_ARCH=$("$VENV_PATH/bin/python" -c "import platform; print(platform.machine())" 2>/dev/null || echo "unknown")
        
        echo ""
        echo "Environment details:"
        echo "  Python: $PYTHON_VERSION ($PYTHON_ARCH)"
        echo "  HARK: $HARK_VERSION"
        echo "  Path: $VENV_PATH"
        echo ""
        
        # Activate if being sourced
        if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
            source "$VENV_PATH/bin/activate"
            echo "✅ UV environment activated"
            
            # Export environment variables for use in subscripts (PLAN A)
            export HAFISCAL_PYTHON="$VENV_PATH/bin/python"
            export HAFISCAL_PYTHON3="$VENV_PATH/bin/python3"
        else
            echo "✅ UV environment ready (not activated - script was executed, not sourced)"
            echo "   To activate: source $VENV_NAME/bin/activate"
        fi
        echo ""
        return 0 2>/dev/null || exit 0
    else
        echo "⚠️  UV environment exists but HARK is not installed"
        echo "   Will attempt to install dependencies..."
        echo ""
    fi
# Check for legacy .venv and suggest migration
elif [[ -d "$PROJECT_ROOT/.venv" ]] && [[ -f "$PROJECT_ROOT/.venv/bin/python" ]]; then
    echo "⚠️  Found legacy .venv directory"
    echo ""
    echo "For cross-platform development, consider migrating to platform-specific venvs:"
    echo "  mv .venv $VENV_NAME"
    echo "  # Then create venv for other platform: switch platforms and run this script again"
    echo ""
    echo "Continuing with legacy .venv for now..."
    VENV_PATH="$PROJECT_ROOT/.venv"
    VENV_NAME=".venv"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2: Check if UV is installed, offer alternatives if not
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if ! command -v uv >/dev/null 2>&1; then
    echo "⚠️  UV is not installed."
    echo ""
    
    # Check if running in CI or non-interactive mode
    if [[ -n "${CI:-}" ]] || [[ ! -t 0 ]]; then
        # Non-interactive: try to install UV automatically
        echo "Installing UV automatically (non-interactive mode)..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.cargo/bin:$PATH"
        
        if command -v uv >/dev/null 2>&1; then
            echo "✅ UV installed successfully"
            echo ""
        else
            echo "❌ UV installation failed in non-interactive mode"
            echo "   Falling back to standard Python venv + pip..."
            USE_PIP_FALLBACK=true
        fi
    else
        # Interactive: offer options
        echo "UV provides the fastest environment setup (~5 seconds)."
        echo ""
        echo "Installation options:"
        echo ""
        
        # Check if Homebrew is available
        if command -v brew >/dev/null 2>&1; then
            echo "  1) Install UV via Homebrew: brew install uv  (recommended if you use Homebrew)"
            echo "  2) Install UV directly: curl install script  (no Homebrew needed)"
            echo "  3) Use standard Python pip + venv            (slower, ~2-3 min, no external tools)"
            echo ""
            echo -n "Choose [1-3] or N to cancel: "
        else
            echo "  1) Install UV directly: curl install script  (no Homebrew needed)"
            echo "  2) Use standard Python pip + venv            (slower, ~2-3 min, no external tools)"
            echo ""
            echo "  (Note: Homebrew not detected. If you install Homebrew first, you can use: brew install uv)"
            echo ""
            echo -n "Choose [1-2] or N to cancel: "
        fi
        
        read -r response
        
        case "$response" in
            1)
                if command -v brew >/dev/null 2>&1; then
                    echo ""
                    echo "Installing UV via Homebrew..."
                    brew install uv
                else
                    echo ""
                    echo "Installing UV via curl..."
                    curl -LsSf https://astral.sh/uv/install.sh | sh
                    export PATH="$HOME/.cargo/bin:$PATH"
                fi
                
                if command -v uv >/dev/null 2>&1; then
                    echo "✅ UV installed successfully"
                    echo ""
                else
                    echo "❌ UV installation failed"
                    echo "   Falling back to standard Python venv + pip..."
                    USE_PIP_FALLBACK=true
                fi
                ;;
            2)
                if command -v brew >/dev/null 2>&1; then
                    # Homebrew exists, so option 2 is curl install
                    echo ""
                    echo "Installing UV via curl..."
                    curl -LsSf https://astral.sh/uv/install.sh | sh
                    export PATH="$HOME/.cargo/bin:$PATH"
                    
                    if command -v uv >/dev/null 2>&1; then
                        echo "✅ UV installed successfully"
                        echo ""
                    else
                        echo "❌ UV installation failed"
                        echo "   Falling back to standard Python venv + pip..."
                        USE_PIP_FALLBACK=true
                    fi
                else
                    # No Homebrew, so option 2 is pip+venv
                    echo ""
                    echo "Using standard Python venv + pip..."
                    USE_PIP_FALLBACK=true
                fi
                ;;
            3)
                if command -v brew >/dev/null 2>&1; then
                    # Homebrew exists, so option 3 is pip+venv
                    echo ""
                    echo "Using standard Python venv + pip..."
                    USE_PIP_FALLBACK=true
                else
                    # Invalid option
                    echo ""
                    echo "❌ Invalid choice"
                    return 1 2>/dev/null || exit 1
                fi
                ;;
            [Nn]*)
                echo ""
                echo "Installation cancelled."
                echo ""
                echo "To install UV later:"
                echo "  Without Homebrew: curl -LsSf https://astral.sh/uv/install.sh | sh"
                echo "  With Homebrew:    brew install uv"
                echo ""
                return 1 2>/dev/null || exit 1
                ;;
            *)
                echo ""
                echo "❌ Invalid choice"
                return 1 2>/dev/null || exit 1
                ;;
        esac
    fi
else
    echo "✅ UV is already installed"
    UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
    echo "   Version: $UV_VERSION"
    echo ""
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FALLBACK: Use standard Python venv + pip if UV not available
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if [[ "${USE_PIP_FALLBACK:-false}" == "true" ]]; then
    echo "========================================"
    echo "Using Standard Python Installation"
    echo "========================================"
    echo ""
    
    cd "$PROJECT_ROOT"
    
    # Check Python version
    if ! command -v python3 >/dev/null 2>&1; then
        echo "❌ Python 3 not found"
        echo "   Install from: https://www.python.org/downloads/"
        return 1 2>/dev/null || exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version)
    echo "Using: $PYTHON_VERSION"
    echo ""
    
    # Create venv if it doesn't exist
    if [[ ! -d "$VENV_PATH" ]]; then
        echo "Creating virtual environment at $VENV_NAME..."
        python3 -m venv "$VENV_PATH"
        
        # Create symlink
        if [[ "$VENV_PATH" != "$PROJECT_ROOT/.venv" ]]; then
            ln -sf "$VENV_NAME" .venv
        fi
        
        echo "✅ Virtual environment created"
        echo ""
    fi
    
    # Activate
    source "$VENV_PATH/bin/activate"
    
    # Upgrade pip
    echo "Upgrading pip..."
    python -m pip install --upgrade pip --quiet
    
    # Install dependencies
    echo "Installing dependencies (this may take 2-3 minutes)..."
    if [[ -f "pyproject.toml" ]]; then
        pip install -e . --quiet
    elif [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt --quiet
    else
        echo "❌ No requirements file found"
        return 1 2>/dev/null || exit 1
    fi
    
    echo "✅ Dependencies installed"
    echo ""
    echo "========================================"
    echo "Setup Summary"
    echo "========================================"
    echo "Virtual environment: $VENV_NAME/"
    echo "Python: $(python --version)"
    echo "Method: pip + venv"
    echo ""
    echo "Environment activated!"
    echo ""
    
    # Export environment variables
    export HAFISCAL_PYTHON="$VENV_PATH/bin/python"
    export HAFISCAL_PYTHON3="$VENV_PATH/bin/python3"
    
    echo "To verify the installation:"
    echo "  python --version"
    echo "  python -c 'import HARK; print(f\"✅ HARK {HARK.__version__}\")'"
    echo ""
    echo "To reproduce results:"
    echo "  ./reproduce.sh --docs      # Documents only"
    echo "  ./reproduce.sh --comp min  # Minimal computational results"
    echo "  ./reproduce.sh --all       # Everything (computation + documents)"
    echo ""
    
    # Skip the rest of the UV-specific steps
    return 0 2>/dev/null || exit 0
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3: Ensure Python 3.9 is available
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "Checking Python 3.9 availability..."
if uv python list 2>/dev/null | grep -q "cpython-3.9"; then
    echo "✅ Python 3.9 is available"
else
    echo "Installing Python 3.9..."
    uv python install 3.9
    echo "✅ Python 3.9 installed"
fi
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 4: Create/update .venv and install dependencies
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cd "$PROJECT_ROOT"

# Handle legacy .venv migration
if [[ -e ".venv" ]] && [[ ! -L ".venv" ]] && [[ -d ".venv" ]]; then
    # Legacy .venv directory exists - migrate it
    if [[ ! -d "$VENV_PATH" ]]; then
        echo "Migrating legacy .venv to platform-specific location..."
        mv .venv "$VENV_PATH"
        echo "✅ Moved .venv to $VENV_NAME"
    else
        echo "⚠️  Both legacy .venv and $VENV_NAME exist"
        echo "   Removing legacy .venv (keeping platform-specific venv)..."
        rm -rf .venv
    fi
    echo ""
fi

# Remove any existing symlink before creating venv (UV can't create venv through symlink)
if [[ -L ".venv" ]]; then
    CURRENT_LINK=$(readlink .venv)
    if [[ "$CURRENT_LINK" != "$VENV_NAME" ]]; then
        echo "⚠️  Removing symlink pointing to wrong platform ($CURRENT_LINK)..."
    else
        echo "ℹ️  Removing existing symlink (will recreate after venv creation)..."
    fi
    rm -f .venv
fi

# Clean up any existing .venv symlink/directory before creating venv
# This prevents issues where UV detects a symlink before the venv is ready
# (e.g., in Docker builds where previous layers may have left artifacts)
if [[ -e ".venv" ]] || [[ -L ".venv" ]]; then
    echo "Removing existing .venv (symlink or directory) for clean venv creation..."
    rm -rf .venv
fi

# Also check if platform-specific venv exists but is invalid (missing Python executable)
# This can happen in Docker builds where a previous layer created an incomplete venv
if [[ -d "$VENV_PATH" ]] && [[ ! -f "$VENV_PATH/bin/python" ]]; then
    echo "Removing invalid platform-specific venv (missing Python executable)..."
    rm -rf "$VENV_PATH"
fi

# Create platform-specific venv if it doesn't exist
if [[ ! -d "$VENV_PATH" ]]; then
    echo "Creating virtual environment at $VENV_NAME..."
    echo ""
    
    # UV creates .venv by default, but we want platform-specific location
    # So we'll create it directly at the platform-specific path
    # Force arm64 on Apple Silicon
    if [[ "$(uname -m)" == "arm64" ]]; then
        echo "Detected Apple Silicon - creating arm64 environment"
        arch -arm64 uv venv --python 3.9 "$VENV_PATH"
    else
        uv venv --python 3.9 "$VENV_PATH"
    fi
    
    # Verify the venv was created
    if [[ ! -d "$VENV_PATH" ]]; then
        echo "❌ Error: Venv was not created at expected location"
        echo "   Expected: $VENV_PATH"
        return 1 2>/dev/null || exit 1
    fi
    echo "✅ Created venv at $VENV_NAME"
    echo ""
fi

# Now create symlink so UV can find the venv (UV expects .venv)
# This symlink will be automatically fixed when switching platforms
# Note: We already removed any existing .venv above, so this should always create a fresh symlink
if [[ "$VENV_PATH" != "$PROJECT_ROOT/.venv" ]]; then
    if [[ ! -e ".venv" ]]; then
        ln -s "$VENV_NAME" .venv
        echo "✅ Created symlink: .venv -> $VENV_NAME"
    elif [[ -L ".venv" ]]; then
        CURRENT_LINK=$(readlink .venv)
        if [[ "$CURRENT_LINK" != "$VENV_NAME" ]]; then
            echo "⚠️  Fixing symlink: .venv -> $VENV_NAME (was pointing to $CURRENT_LINK)"
            rm -f .venv
            ln -s "$VENV_NAME" .venv
        fi
    fi
fi

# Install/sync dependencies
echo "Installing dependencies..."
echo "This will:"
echo "  - Create/update virtual environment in $VENV_NAME/"
echo "  - Install all Python packages from pyproject.toml"
echo "  - Take approximately 5-10 seconds"
echo ""

# Force arm64 on Apple Silicon
if [[ "$(uname -m)" == "arm64" ]]; then
    if arch -arm64 uv sync --all-groups --python 3.9; then
        echo ""
        echo "✅ Environment setup complete (arm64)!"
    else
        echo ""
        echo "❌ Environment setup failed"
        return 1 2>/dev/null || exit 1
    fi
else
    if uv sync --all-groups --python 3.9; then
        echo ""
        echo "✅ Environment setup complete!"
    else
        echo ""
        echo "❌ Environment setup failed"
        return 1 2>/dev/null || exit 1
    fi
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 5: Display summary and activate if being sourced
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo ""
echo "========================================"
echo "Setup Summary"
echo "========================================"
echo "Virtual environment: $VENV_NAME/"
echo "Python version: 3.9"
echo "Packages: All dependency groups installed"

# Verify the environment
if [[ -f "$VENV_PATH/bin/python" ]]; then
    FINAL_ARCH=$("$VENV_PATH/bin/python" -c "import platform; print(platform.machine())" 2>/dev/null || echo "unknown")
    FINAL_VERSION=$("$VENV_PATH/bin/python" --version 2>&1 | awk '{print $2}')
    echo "Architecture: $FINAL_ARCH"
    echo "Python: $FINAL_VERSION"
fi
echo ""

# Check if we're being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being executed (not sourced)
    # Check if we're in a non-interactive context (called from reproduce.sh or CI)
    if [[ -n "${REPRODUCE_SCRIPT_CONTEXT:-}" ]] || [[ -n "${CI:-}" ]] || [[ ! -t 0 ]]; then
        # Non-interactive: activate automatically
        echo "Activating environment automatically (non-interactive context)..."
        source "$VENV_PATH/bin/activate"
        echo "✅ Environment activated!"
        
        # Export environment variables for use in subscripts
        export HAFISCAL_PYTHON="$VENV_PATH/bin/python"
        export HAFISCAL_PYTHON3="$VENV_PATH/bin/python3"
        echo ""
    else
        # Interactive: show activation options
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "ACTIVATION OPTIONS"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "The environment is ready but not yet activated."
        echo ""
        echo "Choose one of the following options:"
        echo ""
        echo "1) Activate in your current shell:"
        echo "   source $VENV_NAME/bin/activate"
        echo ""
        echo "2) Start a new shell with environment activated:"
        echo "   (automatic activation, type 'exit' to return)"
        echo ""
        
        echo -n "Start new shell with activated environment? (Y/n): "
        read -r response
        if [[ ! "$response" =~ ^[Nn]$ ]]; then
            echo ""
            echo "Starting new shell with environment activated..."
            echo "Type 'exit' to return to your original shell"
            echo ""
            # Start a new shell with the environment activated
            exec bash --rcfile <(echo ". ~/.bashrc 2>/dev/null || . ~/.bash_profile 2>/dev/null || true; source $VENV_PATH/bin/activate; echo '✅ Environment activated'; echo 'Python:' \$(python --version); PS1='(hafiscal) \$ '")
        else
            echo ""
            echo "To activate manually, run:"
            echo "  source $VENV_NAME/bin/activate"
            echo ""
        fi
    fi
else
    # Script is being sourced - activate immediately
    echo "Activating environment in current shell..."
    source "$VENV_PATH/bin/activate"
    echo "✅ Environment activated!"
    
    # Export environment variables for use in subscripts (PLAN A)
    export HAFISCAL_PYTHON="$VENV_PATH/bin/python"
    export HAFISCAL_PYTHON3="$VENV_PATH/bin/python3"
    echo ""
fi

echo "To verify the installation:"
echo "  python --version"
echo "  python -c 'import HARK; print(f\"✅ HARK {HARK.__version__}\")'"
echo ""
echo "To reproduce results:"
echo "  ./reproduce.sh --docs      # Documents only"
echo "  ./reproduce.sh --comp min  # Minimal computational results"
echo "  ./reproduce.sh --all       # Everything (computation + documents)"
echo ""
