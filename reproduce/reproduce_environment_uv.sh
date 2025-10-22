#!/bin/bash
# HAFiscal Environment Setup with UV
# This script sets up the Python environment using UV package manager

set -e

echo "========================================"
echo "HAFiscal Environment Setup (UV)"
echo "========================================"
echo ""

# Check if uv is installed
if ! command -v uv >/dev/null 2>&1; then
    echo "UV is not installed. Installing..."
    echo ""
    
    # Check if running in CI or non-interactive mode
    if [[ -z "${CI:-}" ]] && [[ -t 0 ]]; then
        echo "This will install UV to ~/.cargo/bin/"
        echo -n "Continue? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "Installation cancelled."
            echo ""
            echo "To install UV manually, run:"
            echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
            exit 1
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

# Ensure Python 3.9 is available
echo "Checking Python 3.9 availability..."
if uv python list | grep -q "cpython-3.9"; then
    echo "✅ Python 3.9 is available"
else
    echo "Installing Python 3.9..."
    uv python install 3.9
    echo "✅ Python 3.9 installed"
fi
echo ""

# Install dependencies
echo "Installing dependencies..."
echo "This will:"
echo "  - Create a virtual environment in .venv/"
echo "  - Install all Python packages"
echo "  - Take approximately 5-10 seconds"
echo ""

# Sync all dependency groups
if uv sync --all-groups; then
    echo ""
    echo "✅ Environment setup complete!"
else
    echo ""
    echo "❌ Environment setup failed"
    exit 1
fi

echo ""
echo "========================================"
echo "Setup Summary"
echo "========================================"
echo "Virtual environment: .venv/"
echo "Python version: 3.9"
echo "Packages: All dependency groups installed"
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
            cd "$(dirname "$0")/.."
            exec bash --rcfile <(echo ". ~/.bashrc 2>/dev/null || . ~/.bash_profile 2>/dev/null || true; source .venv/bin/activate; echo '✅ Environment activated'; echo 'Python:' \$(python --version); PS1='(hafiscal) \$ '")
        fi
    fi
    
    echo ""
    echo "To activate manually, run:"
    echo "  source .venv/bin/activate"
    echo ""
else
    # Script is being sourced
    echo "Activating environment in current shell..."
    source "$(dirname "${BASH_SOURCE[0]}")/../.venv/bin/activate"
    echo "✅ Environment activated!"
    echo ""
fi

echo "To verify the installation:"
echo "  python --version"
echo "  python -c 'import HARK; print(f\"✅ HARK {HARK.__version__}\")"
echo ""
echo "To reproduce results:"
echo "  ./reproduce.sh --docs      # Documents only"
echo "  ./reproduce.sh --comp min  # Minimal computational results"
echo "  ./reproduce.sh --all       # Everything (computation + documents)"
echo ""
