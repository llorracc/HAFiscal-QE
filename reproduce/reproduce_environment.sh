#!/bin/bash
# HAFiscal Environment Setup Wrapper
# This script delegates to reproduce_environment_comp_uv.sh (SST for UV setup)
# and only falls back to conda if UV setup fails or is unavailable

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PRIORITY 1: Try UV environment setup (Single Source of Truth)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if [[ -f "$SCRIPT_DIR/reproduce_environment_comp_uv.sh" ]]; then
    # Source the UV environment setup script (SST)
    if source "$SCRIPT_DIR/reproduce_environment_comp_uv.sh"; then
        # UV setup succeeded - we're done!
        return 0 2>/dev/null || exit 0
    else
        echo ""
        echo "⚠️  UV environment setup failed or unavailable"
        echo "   Falling back to conda..."
        echo ""
    fi
else
    echo "⚠️  UV setup script not found: $SCRIPT_DIR/reproduce_environment_comp_uv.sh"
    echo "   Falling back to conda..."
    echo ""
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FALLBACK: Use conda if UV is not available
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Conda Fallback Environment Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  NOTE: UV is recommended for better performance"
echo "   To install UV:"
echo "     curl -LsSf https://astral.sh/uv/install.sh | sh"
echo ""

ENV_NAME="HAFiscal"
ENV_FILE="$PROJECT_ROOT/binder/environment.yml"

# Check if conda is available
if ! command -v conda >/dev/null 2>&1; then
    echo "❌ Neither UV nor conda is available"
    echo ""
    echo "Please install one of the following:"
    echo ""
    echo "1. UV (recommended, faster):"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    echo "2. Conda/Miniconda:"
    echo "   https://docs.conda.io/en/latest/miniconda.html"
    echo ""
    return 1 2>/dev/null || exit 1
fi

# Initialize conda for bash
eval "$(conda shell.bash hook)" 2>/dev/null || true

# Check if environment exists
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "✅ Found conda environment: $ENV_NAME"
    echo "   Activating..."
    conda activate "$ENV_NAME"
    
    # Verify it's working
    PYTHON_ARCH=$(python -c "import platform; print(platform.machine())" 2>/dev/null || echo "unknown")
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    echo ""
    echo "Environment details:"
    echo "  Python: $PYTHON_VERSION ($PYTHON_ARCH)"
    echo "  Path: $(which python)"
    echo ""
    echo "✅ Conda environment activated"
    echo ""
    
    return 0 2>/dev/null || exit 0
elif [[ -f "$ENV_FILE" ]]; then
    echo "Creating conda environment from $ENV_FILE..."
    echo ""
    
    # Force arm64 on Apple Silicon Macs
    if [[ "$(uname -m)" == "arm64" ]]; then
        echo "   Detected Apple Silicon - forcing arm64 packages"
        CONDA_SUBDIR=osx-arm64 conda env create -f "$ENV_FILE" -n "$ENV_NAME"
    else
        conda env create -f "$ENV_FILE" -n "$ENV_NAME"
    fi
    
    echo ""
    echo "Activating new conda environment..."
    conda activate "$ENV_NAME"
    
    echo "✅ Conda environment created and activated"
    echo ""
    
    return 0 2>/dev/null || exit 0
else
    echo "❌ Cannot create conda environment: $ENV_FILE not found"
    return 1 2>/dev/null || exit 1
fi
