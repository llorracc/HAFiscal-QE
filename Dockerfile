# HAFiscal Dockerfile
# 
# Single Source of Truth (SST): reproduce/docker/setup.sh
# This Dockerfile uses setup.sh directly to ensure consistency with devcontainer builds.
# All TeX Live and Python environment setup logic is maintained in setup.sh.
#
# Based on .devcontainer/devcontainer.json
# Should produce functionally equivalent containers to the devcontainer build process

FROM mcr.microsoft.com/devcontainers/python:3.11

# Set environment variables (from containerEnv in devcontainer.json)
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# ============================================================================
# Install system dependencies (from onCreateCommand in devcontainer.json)
# ============================================================================
RUN apt-get update && apt-get install -y \
    wget \
    perl \
    build-essential \
    fontconfig \
    curl \
    git \
    zsh \
    && rm -rf /var/lib/apt/lists/*

# Install Oh My Zsh (from onCreateCommand in devcontainer.json)
RUN if [ ! -d /home/vscode/.oh-my-zsh ]; then \
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended || true && \
    chsh -s $(which zsh) vscode || true; \
    fi

# Set working directory
WORKDIR /workspace

# Copy the entire repository (including reproduce/docker for setup scripts)
COPY . /workspace/

# Make Docker setup scripts executable (if they exist)
RUN if [ -f /workspace/reproduce/docker/setup.sh ]; then \
        chmod +x /workspace/reproduce/docker/setup.sh; \
    fi && \
    if [ -f /workspace/reproduce/docker/detect-arch.sh ]; then \
        chmod +x /workspace/reproduce/docker/detect-arch.sh; \
    fi && \
    if [ -f /workspace/reproduce/docker/run-setup.sh ]; then \
        chmod +x /workspace/reproduce/docker/run-setup.sh; \
    fi && \
    if [ -f /workspace/reproduce/reproduce_environment_comp_uv.sh ]; then \
        chmod +x /workspace/reproduce/reproduce_environment_comp_uv.sh; \
    fi

# ============================================================================
# Install TeX Live 2025 and Python environment using setup.sh (SST)
# ============================================================================
# Single Source of Truth: reproduce/docker/setup.sh
# This script handles:
#   - TeX Live 2025 installation (scheme-basic + LaTeX format + individual packages only, no collections)
#   - UV (Python package manager) installation
#   - Python virtual environment setup
#   - PATH and TEXINPUTS configuration
#   - Shell auto-activation setup
#
# Create workspace structure expected by setup.sh
RUN mkdir -p /workspaces && ln -s /workspace /workspaces/HAFiscal-QE && \
    chown -R vscode:vscode /workspace /workspaces

# Ensure vscode user has sudo access (required by setup.sh)
RUN echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/vscode && \
    chmod 0440 /etc/sudoers.d/vscode

# Install TeX Live only (Python venv will be built at container start)
# Single Source of Truth: reproduce/docker/setup.sh
# Set workspaceFolder environment variable to help setup.sh detect workspace
# Skip Python environment setup (SKIP_PYTHON_SETUP=1) - will be built at runtime
RUN su vscode -c "cd /workspace && \
    export workspaceFolder=/workspace && \
    export SKIP_PYTHON_SETUP=1 && \
    bash reproduce/docker/setup.sh"

# Verify TeX Live was installed
# Python venv will be built at container startup (architecture-specific)
RUN TEXLIVE_BIN=$(find /usr/local/texlive/2025/bin -type d -mindepth 1 -maxdepth 1 | head -1) && \
    if [ ! -f "$TEXLIVE_BIN/pdflatex" ]; then \
        echo "❌ pdflatex not found after setup!"; \
        exit 1; \
    fi && \
    # Verify font generation capability (critical for document compilation)
    if ! $TEXLIVE_BIN/mktextfm cmr10 >/dev/null 2>&1; then \
        echo "⚠️  Warning: Font generation test failed (may be OK if fonts are pre-generated)"; \
    else \
        echo "✅ Font generation capability verified"; \
    fi && \
    echo "✅ TeX Live setup verification passed" && \
    echo "ℹ️  Python environment will be built at container startup for your architecture"

# NOTE: Platform and architecture-specific virtual environment auto-activation is configured by setup.sh
# The setup.sh script (called above) adds activation code to shell RC files that:
# - Detects platform (Linux/Darwin) and architecture (x86_64, aarch64, arm64)
# - Selects architecture-specific venv (.venv-linux-x86_64, .venv-darwin-arm64, etc.)
# - No verification needed - architecture is encoded in venv name
# Single Source of Truth: reproduce/docker/setup.sh

# Set PATH environment variable (from containerEnv in devcontainer.json)
# Note: We include TeX Live in ENV PATH for non-interactive shells
# The architecture-specific path is determined at runtime, but we include common locations
# Interactive shells will also source /etc/profile.d/texlive.sh for the correct arch-specific path
ENV PATH="/usr/local/texlive/2025/bin/aarch64-linux:/usr/local/texlive/2025/bin/x86_64-linux:/home/vscode/.local/bin:/home/vscode/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Expose ports for Jupyter Lab and Voila Dashboard (from forwardPorts)
EXPOSE 8888 8866

# Switch to vscode user (matches devcontainer behavior)
# This ensures the venv activation scripts in ~/.bashrc and ~/.zshrc are sourced
USER vscode
WORKDIR /workspace

# Create entrypoint script that builds Python venv at container startup
# This ensures venv is built for the correct platform and architecture
RUN echo '#!/bin/bash' > /home/vscode/entrypoint.sh && \
    echo 'set -e' >> /home/vscode/entrypoint.sh && \
    echo '' >> /home/vscode/entrypoint.sh && \
    echo '# Determine platform and architecture-specific venv path' >> /home/vscode/entrypoint.sh && \
    echo 'PLATFORM=$(uname -s | tr "[:upper:]" "[:lower:]")' >> /home/vscode/entrypoint.sh && \
    echo 'ARCH=$(uname -m)' >> /home/vscode/entrypoint.sh && \
    echo 'if [ "$PLATFORM" = "darwin" ]; then' >> /home/vscode/entrypoint.sh && \
    echo '    VENV_PATH="/workspace/.venv-darwin-$ARCH"' >> /home/vscode/entrypoint.sh && \
    echo 'else' >> /home/vscode/entrypoint.sh && \
    echo '    VENV_PATH="/workspace/.venv-linux-$ARCH"' >> /home/vscode/entrypoint.sh && \
    echo 'fi' >> /home/vscode/entrypoint.sh && \
    echo '' >> /home/vscode/entrypoint.sh && \
    echo '# Build Python environment if it does not exist' >> /home/vscode/entrypoint.sh && \
    echo 'if [ ! -d "$VENV_PATH" ] || [ ! -f "$VENV_PATH/bin/python" ]; then' >> /home/vscode/entrypoint.sh && \
    echo '    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"' >> /home/vscode/entrypoint.sh && \
    echo '    echo "Building Python environment for your architecture..."' >> /home/vscode/entrypoint.sh && \
    echo '    echo "Architecture: $(uname -m)"' >> /home/vscode/entrypoint.sh && \
    echo '    echo "This is a one-time setup (2-3 minutes)"' >> /home/vscode/entrypoint.sh && \
    echo '    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"' >> /home/vscode/entrypoint.sh && \
    echo '    cd /workspace' >> /home/vscode/entrypoint.sh && \
    echo '    if ! bash /workspace/reproduce/reproduce_environment_comp_uv.sh; then' >> /home/vscode/entrypoint.sh && \
    echo '        echo "❌ Failed to build Python environment"' >> /home/vscode/entrypoint.sh && \
    echo '        exit 1' >> /home/vscode/entrypoint.sh && \
    echo '    fi' >> /home/vscode/entrypoint.sh && \
    echo '    echo "✅ Python environment ready"' >> /home/vscode/entrypoint.sh && \
    echo 'else' >> /home/vscode/entrypoint.sh && \
    echo '    echo "ℹ️  Python environment already exists: $VENV_PATH"' >> /home/vscode/entrypoint.sh && \
    echo 'fi' >> /home/vscode/entrypoint.sh && \
    echo '' >> /home/vscode/entrypoint.sh && \
    echo '# Source .bashrc for environment setup' >> /home/vscode/entrypoint.sh && \
    echo 'if [ -f ~/.bashrc ]; then source ~/.bashrc; fi' >> /home/vscode/entrypoint.sh && \
    echo 'cd /workspace' >> /home/vscode/entrypoint.sh && \
    echo 'exec "$@"' >> /home/vscode/entrypoint.sh && \
    chmod +x /home/vscode/entrypoint.sh

# Default command: use interactive bash to ensure .bashrc is sourced
# This ensures the venv is automatically activated
# For interactive sessions: docker run -it hafiscal:latest
ENTRYPOINT ["/home/vscode/entrypoint.sh"]
CMD ["/bin/bash", "-i"]
