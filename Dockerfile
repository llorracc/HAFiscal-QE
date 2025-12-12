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
RUN mkdir -p /workspaces && ln -s /workspace /workspaces/HAFiscal-Public && \
    chown -R vscode:vscode /workspace /workspaces

# Ensure vscode user has sudo access (required by setup.sh)
RUN echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/vscode && \
    chmod 0440 /etc/sudoers.d/vscode

# Run setup.sh as vscode user (matches devcontainer behavior)
# Single Source of Truth: reproduce/docker/setup.sh
# Set workspaceFolder environment variable to help setup.sh detect workspace
RUN su vscode -c "cd /workspace && \
    export workspaceFolder=/workspace && \
    bash reproduce/docker/setup.sh"

# Verify critical components were installed
# Check for platform-specific venv (.venv-linux in Docker) or fallback to .venv
RUN PLATFORM_VENV=".venv-linux" && \
    if [ -d "/workspace/$PLATFORM_VENV" ] && [ -f "/workspace/$PLATFORM_VENV/bin/python" ]; then \
        echo "✅ Found platform-specific venv: $PLATFORM_VENV"; \
        # Ensure .venv symlink exists for compatibility
        if [ ! -e "/workspace/.venv" ]; then \
            ln -s "$PLATFORM_VENV" /workspace/.venv && \
            echo "✅ Created symlink: .venv -> $PLATFORM_VENV"; \
        fi; \
    elif [ -d "/workspace/.venv" ] && [ -f "/workspace/.venv/bin/python" ]; then \
        echo "✅ Found virtual environment: .venv"; \
    else \
        echo "❌ Virtual environment was not created successfully"; \
        echo "   Checked: $PLATFORM_VENV and .venv"; \
        echo "   Expected: $PLATFORM_VENV/bin/python or .venv/bin/python"; \
        exit 1; \
    fi && \
    TEXLIVE_BIN=$(find /usr/local/texlive/2025/bin -type d -mindepth 1 -maxdepth 1 | head -1) && \
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
    echo "✅ Setup verification passed"

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

# Create a wrapper script that sources .bashrc to ensure venv activation
# Note: .bashrc only runs in interactive shells, so we use bash -i
RUN echo '#!/bin/bash' > /home/vscode/entrypoint.sh && \
    echo 'set -e' >> /home/vscode/entrypoint.sh && \
    echo 'if [ -f ~/.bashrc ]; then source ~/.bashrc; fi' >> /home/vscode/entrypoint.sh && \
    echo 'cd /workspace' >> /home/vscode/entrypoint.sh && \
    echo 'exec "$@"' >> /home/vscode/entrypoint.sh && \
    chmod +x /home/vscode/entrypoint.sh

# Default command: use interactive bash to ensure .bashrc is sourced
# This ensures the venv is automatically activated
# For interactive sessions: docker run -it hafiscal:latest
ENTRYPOINT ["/home/vscode/entrypoint.sh"]
CMD ["/bin/bash", "-i"]
