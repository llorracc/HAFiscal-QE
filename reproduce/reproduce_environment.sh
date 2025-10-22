#!/bin/bash

# Detect whether the script is being sourced
(return 0 2>/dev/null) && SOURCED=1 || SOURCED=0

if [ "$SOURCED" -eq 0 ]; then
    set -e
fi

# ---- Windows Detection ----
detect_windows() {
    # Check if we're running on Windows (various detection methods)
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]] || [[ -n "$WINDIR" ]] || [[ -n "$windir" ]]; then
        return 0  # We are on Windows
    fi
    
    # Additional check for Windows paths in PWD or common Windows environment variables
    if [[ "$PWD" =~ ^/[a-zA-Z]/ ]] && [[ -n "$SYSTEMROOT" ]]; then
        return 0  # Likely Windows with Unix-like shell
    fi
    
    return 1  # Not Windows
}

if detect_windows; then
    echo "🚫 Windows Detected - WSL Required"
    echo "========================================="
    echo ""
    echo "❌ This reproduction system is designed for Unix-like environments."
    echo "   Native Windows is not supported due to:"
    echo "   • Path handling differences"
    echo "   • LaTeX package compatibility issues" 
    echo "   • Shell script dependencies"
    echo ""
    echo "✅ RECOMMENDED SOLUTION: Use Windows Subsystem for Linux (WSL)"
    echo ""
    echo "   1. Install WSL2 from Microsoft Store or:"
    echo "      https://docs.microsoft.com/en-us/windows/wsl/install"
    echo ""
    echo "   2. Install Ubuntu or your preferred Linux distribution"
    echo ""
    echo "   3. Clone this repository inside WSL:"
    echo "      cd ~/  # or your preferred directory"
    echo "      git clone [repository-url]"
    echo ""
    echo "   4. Run the reproduction scripts from within WSL"
    echo ""
    echo "🔍 Alternative: Use Docker (if available)"
    echo "   docker run -it --rm -v \$(pwd):/workspace ubuntu:latest bash"
    echo ""
    error_exit "Please use WSL or a Unix-like environment"
fi

# ---- Dependency Version Checking ----
check_dependency_versions() {
    echo "🔍 Checking dependency versions..."
    
    local warnings=0
    
    # Check LaTeX distribution
    if command -v pdflatex >/dev/null 2>&1; then
        local latex_version
        latex_version=$(pdflatex --version 2>/dev/null | head -1 | grep -o '20[0-9][0-9]' | head -1)
        if [[ -n "$latex_version" && "$latex_version" -lt 2020 ]]; then
            echo "⚠️  WARNING: Old LaTeX distribution detected ($latex_version)"
            echo "   Some packages may not work correctly with pre-2020 LaTeX"
            echo "   Consider updating your LaTeX distribution"
            warnings=$((warnings + 1))
        fi
    fi
    
    # Check latexmk version
    if command -v latexmk >/dev/null 2>&1; then
        local latexmk_version
        latexmk_version=$(latexmk --version 2>/dev/null | head -1 | grep -o '[0-9]\+\.[0-9]\+' | head -1)
        if [[ -n "$latexmk_version" ]]; then
            # Convert version to comparable number (e.g., "4.70" -> "470")
            local version_num
            version_num=$(echo "$latexmk_version" | awk -F. '{printf "%d%02d", $1, $2}')
            if [[ "$version_num" -lt 465 ]]; then
                echo "⚠️  WARNING: Old latexmk version detected ($latexmk_version)"
                echo "   Version 4.65+ recommended for best compatibility"
                echo "   Current version may have issues with bibliography processing"
                warnings=$((warnings + 1))
            fi
        fi
    fi
    
    # Check bibtex availability 
    if ! command -v bibtex >/dev/null 2>&1; then
        echo "⚠️  WARNING: bibtex not found in PATH"
        echo "   This may cause bibliography processing to fail"
        echo "   Ensure your LaTeX distribution includes bibtex"
        warnings=$((warnings + 1))
    fi
    
    # Check for problematic conda/LaTeX combinations
    if command -v conda >/dev/null 2>&1 && command -v pdflatex >/dev/null 2>&1; then
        local conda_latex_path
        conda_latex_path=$(which pdflatex 2>/dev/null || echo "")
        if [[ "$conda_latex_path" == *"conda"* ]] || [[ "$conda_latex_path" == *"miniconda"* ]]; then
            echo "ℹ️  INFO: LaTeX from conda environment detected"
            echo "   If you encounter package issues, consider using system LaTeX instead"
        fi
    fi
    
    if [[ "$warnings" -gt 0 ]]; then
        echo ""
        echo "📝 $warnings version warning(s) detected - builds may still succeed"
        echo "   If you encounter issues, consider updating the flagged tools"
        echo ""
    else
        echo "✅ Dependency versions look good"
    fi
}

ENV_NAME="HAFiscal"
ENV_FILE="binder/environment.yml"
REQ_FILE="binder/requirements.txt"
VENV_DIR=".venv_${ENV_NAME}"

MINICONDA_URL="https://docs.conda.io/en/latest/miniconda.html"

has_conda() {
    command -v conda >/dev/null 2>&1
}

has_python() {
    command -v python3 >/dev/null 2>&1 && command -v pip3 >/dev/null 2>&1
}

conda_env_path() {
    conda info --base 2>/dev/null | awk '{print $1}' | xargs -I{} echo "{}/envs/$ENV_NAME"
}

error_exit() {
    echo "Error: $1" >&2
    if [ "$SOURCED" -eq 1 ]; then
        return 1
    else
        exit 1
    fi
}

# Run dependency version checking
check_dependency_versions

# ---- TeX Live Environment Verification ----
echo "🔍 Running comprehensive TeX Live verification..."
echo

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEXLIVE_SCRIPT="${SCRIPT_DIR}/reproduce_environment_texlive.sh"

if [[ -f "$TEXLIVE_SCRIPT" ]]; then
    # Source the TeX Live checking script
    # shellcheck source=reproduce_environment_texlive.sh
    if source "$TEXLIVE_SCRIPT"; then
        echo "✅ TeX Live environment verification completed successfully"
    else
        echo "❌ TeX Live environment verification failed"
        echo
        echo "🚨 CRITICAL: TeX Live installation issues detected"
        echo "   LaTeX document compilation will fail without a proper TeX Live setup"
        echo "   Please resolve the TeX Live issues before proceeding"
        echo
        error_exit "TeX Live environment is not ready for HAFiscal compilation"
    fi
else
    echo "⚠️  WARNING: TeX Live verification script not found at: $TEXLIVE_SCRIPT"
    echo "   Performing basic TeX Live checks..."
    
    # Basic fallback check
    if ! command -v latex >/dev/null 2>&1; then
        echo "❌ latex command not found"
        error_exit "Please install TeX Live before continuing"
    fi
    
    if ! command -v pdflatex >/dev/null 2>&1; then
        echo "❌ pdflatex command not found"
        error_exit "Please install TeX Live before continuing"
    fi
    
    echo "✅ Basic TeX Live commands found"
fi

echo

# ---- Conda Path ----

if has_conda; then
    ENV_PATH=$(conda_env_path)

    if [ -d "$ENV_PATH" ]; then
        echo "Activating existing conda environment '$ENV_NAME'..."
        eval "$(conda shell.bash hook)"
        conda activate "$ENV_NAME"
        return 0 2>/dev/null || exit 0
    fi

    if [ -f "$ENV_FILE" ]; then
        echo "Creating conda environment '$ENV_NAME' from $ENV_FILE..."
        conda env create -f "$ENV_FILE" -n "$ENV_NAME" || error_exit "Conda environment creation failed."

        echo "Activating new conda environment '$ENV_NAME'..."
        eval "$(conda shell.bash hook)"
        conda activate "$ENV_NAME"
        return 0 2>/dev/null || exit 0
    fi
else
    echo "Conda is not installed."
    echo
    echo "⚠️  Preferred setup method is via Miniconda or Conda."
    echo "   Please install it from:"
    echo "     $MINICONDA_URL"
    echo
    echo "📦 Falling back to pip + virtualenv..."
fi

# ---- Python venv fallback ----

if [ -d "$VENV_DIR" ]; then
    echo "Activating existing virtualenv at $VENV_DIR..."
    source "$VENV_DIR/bin/activate"
    return 0 2>/dev/null || exit 0
fi

if [ -f "$REQ_FILE" ]; then
    has_python || error_exit "requirements.txt found but Python3 and/or pip3 not available."

    echo "Creating Python virtualenv in $VENV_DIR..."
    python3 -m venv "$VENV_DIR" || error_exit "Failed to create virtualenv."

    echo "Activating new virtualenv at $VENV_DIR..."
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip
    pip install -r "$REQ_FILE" || error_exit "pip install failed."

    return 0 2>/dev/null || exit 0
fi

# ---- Nothing usable found ----

error_exit "No environment found and neither $ENV_FILE nor $REQ_FILE exist."
