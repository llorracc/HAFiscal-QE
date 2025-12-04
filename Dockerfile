# HAFiscal Dockerfile
# Based on .devcontainer/devcontainer.json and reproduce/docker/setup.sh
# This Dockerfile replicates the devcontainer setup for use with Docker Desktop
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
# Install TeX Live 2025 (matches setup.sh exactly)
# ============================================================================
RUN echo "📄 Installing TeX Live 2025 (scheme-basic)..." && \
    cd /tmp && \
    wget -q https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz && \
    tar -xzf install-tl-unx.tar.gz && \
    cd $(find . -maxdepth 1 -name "install-tl-*" -type d | head -1) && \
    printf '%s\n' \
        "selected_scheme scheme-basic" \
        "TEXDIR /usr/local/texlive/2025" \
        "TEXMFLOCAL /usr/local/texlive/texmf-local" \
        "TEXMFHOME ~/texmf" \
        "TEXMFVAR ~/.texlive2025/texmf-var" \
        "TEXMFCONFIG ~/.texlive2025/texmf-config" \
        "instopt_adjustpath 1" \
        "instopt_adjustrepo 1" \
        "tlpdbopt_autobackup 0" \
        "tlpdbopt_desktop_integration 0" \
        "tlpdbopt_file_assocs 0" \
        "tlpdbopt_post_code 1" > texlive.profile && \
    ./install-tl --profile=texlive.profile --no-interaction && \
    rm -rf /tmp/install-tl-* /tmp/install-tl-unx.tar.gz

# Find TeX Live binary directory using architecture detection (like detect-arch.sh)
RUN ARCH=$(uname -m) && \
    case "$ARCH" in \
        x86_64) TEXLIVE_ARCH="x86_64-linux" ;; \
        aarch64|arm64) TEXLIVE_ARCH="aarch64-linux" ;; \
        *) TEXLIVE_ARCH="" ;; \
    esac && \
    if [ -n "$TEXLIVE_ARCH" ] && [ -d "/usr/local/texlive/2025/bin/$TEXLIVE_ARCH" ]; then \
        TEXLIVE_BIN="/usr/local/texlive/2025/bin/$TEXLIVE_ARCH"; \
    else \
        TEXLIVE_BIN=$(find /usr/local/texlive/2025/bin -type d -mindepth 1 -maxdepth 1 | head -1); \
    fi && \
    echo "$TEXLIVE_BIN" > /tmp/texlive-bin-path.txt && \
    $TEXLIVE_BIN/tlmgr update --self || true && \
    $TEXLIVE_BIN/tlmgr install collection-basic || true

# Install individual LaTeX packages (matches setup.sh package list exactly)
RUN TEXLIVE_BIN=$(cat /tmp/texlive-bin-path.txt) && \
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
RUN TEXLIVE_BIN=$(cat /tmp/texlive-bin-path.txt) && \
    if [ -f "$TEXLIVE_BIN/latexmk" ]; then \
        echo "✅ latexmk found at: $TEXLIVE_BIN/latexmk"; \
        $TEXLIVE_BIN/latexmk -v | head -1 || true; \
    else \
        echo "⚠️  latexmk not found, attempting to install..."; \
        $TEXLIVE_BIN/tlmgr install latexmk || echo "❌ Failed to install latexmk"; \
    fi

# Update font cache
RUN TEXLIVE_BIN=$(cat /tmp/texlive-bin-path.txt) && \
    $TEXLIVE_BIN/mktexlsr || true

# Verify LaTeX installation (matches setup.sh)
RUN TEXLIVE_BIN=$(cat /tmp/texlive-bin-path.txt) && \
    export PATH="$TEXLIVE_BIN:$PATH" && \
    if command -v pdflatex >/dev/null 2>&1; then \
        echo "✅ pdflatex found: $(which pdflatex)"; \
        pdflatex --version | head -3 || true; \
    else \
        if [ -f "$TEXLIVE_BIN/pdflatex" ]; then \
            echo "✅ pdflatex found at: $TEXLIVE_BIN/pdflatex"; \
            $TEXLIVE_BIN/pdflatex --version | head -3 || true; \
        else \
            echo "❌ pdflatex not found!"; \
            exit 1; \
        fi; \
    fi

# Test package availability (matches setup.sh)
RUN TEXLIVE_BIN=$(cat /tmp/texlive-bin-path.txt) && \
    echo "🔍 Testing package availability..." && \
    for pkg in amsmath hyperref geometry booktabs enumitem natbib siunitx subfiles; do \
        if $TEXLIVE_BIN/kpsewhich ${pkg}.sty >/dev/null 2>&1; then \
            echo "  ✅ $pkg"; \
        else \
            echo "  ⚠️  $pkg (not found)"; \
        fi; \
    done

# Add TeX Live to PATH permanently (system-wide and user shells)
RUN TEXLIVE_BIN=$(cat /tmp/texlive-bin-path.txt) && \
    echo "export PATH=\"$TEXLIVE_BIN:\$PATH\"" >> /etc/profile.d/texlive.sh && \
    chmod +x /etc/profile.d/texlive.sh && \
    echo "export PATH=\"$TEXLIVE_BIN:\$PATH\"" >> /home/vscode/.bashrc && \
    echo "export PATH=\"$TEXLIVE_BIN:\$PATH\"" >> /home/vscode/.zshrc 2>/dev/null || true

# ============================================================================
# Install UV (Python package manager) and set up Python environment
# ============================================================================
# Install UV as vscode user (matches devcontainer setup)
RUN su vscode -c "curl -LsSf https://astral.sh/uv/install.sh | sh" && \
    echo "export PATH=\"\$HOME/.local/bin:\$HOME/.cargo/bin:\$PATH\"" >> /etc/profile.d/uv.sh && \
    chmod +x /etc/profile.d/uv.sh && \
    echo "export PATH=\"\$HOME/.local/bin:\$HOME/.cargo/bin:\$PATH\"" >> /home/vscode/.bashrc && \
    (touch /home/vscode/.zshrc 2>/dev/null || true) && \
    if ! grep -q "\.local/bin.*\.cargo/bin" /home/vscode/.zshrc 2>/dev/null; then \
        echo "export PATH=\"\$HOME/.local/bin:\$HOME/.cargo/bin:\$PATH\"" >> /home/vscode/.zshrc; \
    fi

# Create expected workspace structure for UV setup script
# The script expects /workspaces/HAFiscal-Public, so we'll create a symlink
RUN mkdir -p /workspaces && ln -s /workspace /workspaces/HAFiscal-Public

# Fix permissions so vscode user can create virtual environment
RUN chown -R vscode:vscode /workspace /workspaces

# Set up Python environment with UV (using reproduce_environment_comp_uv.sh like setup.sh)
# Run as vscode user to match devcontainer behavior
RUN su vscode -c "export PATH=\"/home/vscode/.local/bin:/home/vscode/.cargo/bin:\$PATH\" && \
    cd /workspace && \
    if [ -f \"./reproduce/reproduce_environment_comp_uv.sh\" ]; then \
        echo \"Using reproduce_environment_comp_uv.sh for environment setup...\"; \
        bash ./reproduce/reproduce_environment_comp_uv.sh; \
    else \
        echo \"Using direct uv sync (reproduce_environment_comp_uv.sh not found)...\"; \
        uv sync --all-groups || exit 1; \
    fi"

# Verify .venv was created
RUN if [ ! -d "/workspace/.venv" ] || [ ! -f "/workspace/.venv/bin/python" ]; then \
        echo "❌ Virtual environment (.venv) was not created successfully"; \
        exit 1; \
    else \
        echo "✅ Virtual environment created successfully at: /workspace/.venv"; \
    fi

# Final verification (matches setup.sh)
RUN echo "🔍 Final Verification" && \
    export PATH="/home/vscode/.local/bin:/home/vscode/.cargo/bin:$PATH" && \
    if command -v uv >/dev/null 2>&1; then \
        echo "✅ UV is in PATH: $(which uv)"; \
        uv --version | head -1 || true; \
    else \
        echo "⚠️  UV not found in PATH (may need shell restart)"; \
    fi && \
    VENV_PATH="/workspace/.venv" && \
    if [ -f "$VENV_PATH/bin/python" ]; then \
        echo "✅ Virtual environment ready: $VENV_PATH"; \
        echo "   Python: $($VENV_PATH/bin/python --version 2>&1)"; \
    else \
        echo "❌ Virtual environment not found at: $VENV_PATH"; \
    fi

# Configure shell auto-activation for .venv (matches setup.sh)
# Check if already present to avoid duplicates
RUN VENV_PATH="/workspace/.venv" && \
    if ! grep -q "Auto-activate HAFiscal virtual environment" /home/vscode/.bashrc 2>/dev/null; then \
        echo "" >> /home/vscode/.bashrc && \
        echo "# Auto-activate HAFiscal virtual environment" >> /home/vscode/.bashrc && \
        echo "if [ -f \"$VENV_PATH/bin/activate\" ]; then" >> /home/vscode/.bashrc && \
        echo "    source \"$VENV_PATH/bin/activate\"" >> /home/vscode/.bashrc && \
        echo "fi" >> /home/vscode/.bashrc; \
    fi && \
    (touch /home/vscode/.zshrc 2>/dev/null || true) && \
    if ! grep -q "Auto-activate HAFiscal virtual environment" /home/vscode/.zshrc 2>/dev/null; then \
        echo "" >> /home/vscode/.zshrc && \
        echo "# Auto-activate HAFiscal virtual environment" >> /home/vscode/.zshrc && \
        echo "if [ -f \"$VENV_PATH/bin/activate\" ]; then" >> /home/vscode/.zshrc && \
        echo "    source \"$VENV_PATH/bin/activate\"" >> /home/vscode/.zshrc && \
        echo "fi" >> /home/vscode/.zshrc; \
    fi && \
    # Ensure .bash_profile sources .bashrc for login shells \
    if [ ! -f /home/vscode/.bash_profile ] || ! grep -q "source.*bashrc" /home/vscode/.bash_profile 2>/dev/null; then \
        echo "if [ -f ~/.bashrc ]; then source ~/.bashrc; fi" >> /home/vscode/.bash_profile; \
    fi

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
