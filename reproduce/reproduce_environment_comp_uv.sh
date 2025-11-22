#!/bin/bash
# HAFiscal Environment Setup with UV
# This script sets up the Python environment using UV package manager
# This is the SINGLE SOURCE OF TRUTH for UV environment setup

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "========================================"
echo "HAFiscal Environment Setup (UV)"
echo "========================================"
echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1: Check if .venv already exists and is valid
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if [[ -d "$PROJECT_ROOT/.venv" ]] && [[ -f "$PROJECT_ROOT/.venv/bin/python" ]]; then
    echo "✅ Found existing UV environment at .venv/"
    
    # Verify it has HARK installed
    if "$PROJECT_ROOT/.venv/bin/python" -c "import HARK" 2>/dev/null; then
        echo "✅ UV environment has HARK installed"
        
        # Get environment details
        HARK_VERSION=$("$PROJECT_ROOT/.venv/bin/python" -c "import HARK; print(HARK.__version__)" 2>/dev/null || echo "unknown")
        PYTHON_VERSION=$("$PROJECT_ROOT/.venv/bin/python" --version 2>&1 | awk '{print $2}')
        PYTHON_ARCH=$("$PROJECT_ROOT/.venv/bin/python" -c "import platform; print(platform.machine())" 2>/dev/null || echo "unknown")
        
        echo ""
        echo "Environment details:"
        echo "  Python: $PYTHON_VERSION ($PYTHON_ARCH)"
        echo "  HARK: $HARK_VERSION"
        echo "  Path: $PROJECT_ROOT/.venv"
        echo ""
        
        # Activate if being sourced
        if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
            source "$PROJECT_ROOT/.venv/bin/activate"
            echo "✅ UV environment activated"
            
            # Export environment variables for use in subscripts (PLAN A)
            export HAFISCAL_PYTHON="$PROJECT_ROOT/.venv/bin/python"
            export HAFISCAL_PYTHON3="$PROJECT_ROOT/.venv/bin/python3"
        else
            echo "✅ UV environment ready (not activated - script was executed, not sourced)"
            echo "   To activate: source .venv/bin/activate"
        fi
        echo ""
        return 0 2>/dev/null || exit 0
    else
        echo "⚠️  UV environment exists but HARK is not installed"
        echo "   Will attempt to install dependencies..."
        echo ""
    fi
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2: Check if UV is installed
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if ! command -v uv >/dev/null 2>&1; then
    echo "UV is not installed."
    echo ""
    
    # Check if running in CI or non-interactive mode
    if [[ -z "${CI:-}" ]] && [[ -t 0 ]]; then
        echo "This will install UV to ~/.cargo/bin/"
        echo -n "Continue? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo ""
            echo "Installation cancelled."
            echo ""
            echo "To install UV manually, run:"
            echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
            echo ""
            return 1 2>/dev/null || exit 1
        fi
    fi
    
    echo "Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Add to PATH for this session
    export PATH="$HOME/.cargo/bin:$PATH"
    
    echo "✅ UV installed successfully"
    echo ""
else
    echo "✅ UV is already installed"
    UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
    echo "   Version: $UV_VERSION"
    echo ""
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

# Create .venv if it doesn't exist
if [[ ! -d ".venv" ]]; then
    echo "Creating virtual environment..."
    echo ""
    
    # Force arm64 on Apple Silicon
    if [[ "$(uname -m)" == "arm64" ]]; then
        echo "Detected Apple Silicon - creating arm64 environment"
        arch -arm64 uv venv --python 3.9
    else
        uv venv --python 3.9
    fi
    echo ""
fi

# Install/sync dependencies
echo "Installing dependencies..."
echo "This will:"
echo "  - Create/update virtual environment in .venv/"
echo "  - Install all Python packages from pyproject.toml"
echo "  - Take approximately 5-10 seconds"
echo ""

# Force arm64 on Apple Silicon
if [[ "$(uname -m)" == "arm64" ]]; then
    if arch -arm64 uv sync --all-groups; then
        echo ""
        echo "✅ Environment setup complete (arm64)!"
    else
        echo ""
        echo "❌ Environment setup failed"
        return 1 2>/dev/null || exit 1
    fi
else
    if uv sync --all-groups; then
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
echo "Virtual environment: .venv/"
echo "Python version: 3.9"
echo "Packages: All dependency groups installed"

# Verify the environment
if [[ -f "$PROJECT_ROOT/.venv/bin/python" ]]; then
    FINAL_ARCH=$("$PROJECT_ROOT/.venv/bin/python" -c "import platform; print(platform.machine())" 2>/dev/null || echo "unknown")
    FINAL_VERSION=$("$PROJECT_ROOT/.venv/bin/python" --version 2>&1 | awk '{print $2}')
    echo "Architecture: $FINAL_ARCH"
    echo "Python: $FINAL_VERSION"
fi
echo ""

# Check if we're being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being executed (not sourced)
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "ACTIVATION OPTIONS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "The environment is ready but not yet activated."
    echo ""
    echo "Choose one of the following options:"
    echo ""
    echo "1) Activate in your current shell:"
    echo "   source .venv/bin/activate"
    echo ""
    echo "2) Start a new shell with environment activated:"
    echo "   (automatic activation, type 'exit' to return)"
    echo ""
    
    # Check if running interactively
    if [[ -t 0 ]] && [[ -z "${CI:-}" ]]; then
        echo -n "Start new shell with activated environment? (Y/n): "
        read -r response
        if [[ ! "$response" =~ ^[Nn]$ ]]; then
            echo ""
            echo "Starting new shell with environment activated..."
            echo "Type 'exit' to return to your original shell"
            echo ""
            # Start a new shell with the environment activated
            exec bash --rcfile <(echo ". ~/.bashrc 2>/dev/null || . ~/.bash_profile 2>/dev/null || true; source $PROJECT_ROOT/.venv/bin/activate; echo '✅ Environment activated'; echo 'Python:' \$(python --version); PS1='(hafiscal) \$ '")
        fi
    fi
    
    echo ""
    echo "To activate manually, run:"
    echo "  source .venv/bin/activate"
    echo ""
else
    # Script is being sourced - activate immediately
    echo "Activating environment in current shell..."
    source "$PROJECT_ROOT/.venv/bin/activate"
    echo "✅ Environment activated!"
    
    # Export environment variables for use in subscripts (PLAN A)
    export HAFISCAL_PYTHON="$PROJECT_ROOT/.venv/bin/python"
    export HAFISCAL_PYTHON3="$PROJECT_ROOT/.venv/bin/python3"
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
