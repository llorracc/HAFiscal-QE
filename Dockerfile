# HAFiscal-Public Dockerfile
# Based on .devcontainer/devcontainer.json configuration
# This Dockerfile replicates the devcontainer setup for use with Docker Desktop

FROM mcr.microsoft.com/devcontainers/python:3.11

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (from onCreateCommand in devcontainer.json)
RUN apt-get update && apt-get install -y \
    wget \
    perl \
    build-essential \
    fontconfig \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Copy the entire repository (including .devcontainer for setup script)
COPY . /workspace/

# Make setup scripts executable
RUN chmod +x /workspace/.devcontainer/setup.sh && \
    chmod +x /workspace/.devcontainer/detect-arch.sh

# ============================================================================
# Install TeX Live 2025
# ============================================================================
RUN echo "Installing TeX Live 2025..." && \
    cd /tmp && \
    wget -q https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz && \
    tar -xzf install-tl-unx.tar.gz && \
    cd $(find . -maxdepth 1 -name "install-tl-*" -type d | head -1) && \
    echo "selected_scheme scheme-basic" > texlive.profile && \
    echo "TEXDIR /usr/local/texlive/2025" >> texlive.profile && \
    echo "TEXMFLOCAL /usr/local/texlive/texmf-local" >> texlive.profile && \
    echo "TEXMFHOME ~/texmf" >> texlive.profile && \
    echo "TEXMFVAR ~/.texlive2025/texmf-var" >> texlive.profile && \
    echo "TEXMFCONFIG ~/.texlive2025/texmf-config" >> texlive.profile && \
    echo "instopt_adjustpath 1" >> texlive.profile && \
    echo "instopt_adjustrepo 1" >> texlive.profile && \
    echo "tlpdbopt_autobackup 0" >> texlive.profile && \
    echo "tlpdbopt_desktop_integration 0" >> texlive.profile && \
    echo "tlpdbopt_file_assocs 0" >> texlive.profile && \
    echo "tlpdbopt_post_code 1" >> texlive.profile && \
    ./install-tl --profile=texlive.profile --no-interaction && \
    rm -rf /tmp/install-tl-* /tmp/install-tl-unx.tar.gz

# Find TeX Live binary directory and update tlmgr
RUN TEXLIVE_BIN=$(find /usr/local/texlive/2025/bin -type d -mindepth 1 -maxdepth 1 | head -1) && \
    $TEXLIVE_BIN/tlmgr update --self || true && \
    $TEXLIVE_BIN/tlmgr install collection-basic || true

# Install required LaTeX packages
RUN TEXLIVE_BIN=$(find /usr/local/texlive/2025/bin -type d -mindepth 1 -maxdepth 1 | head -1) && \
    $TEXLIVE_BIN/tlmgr install \
    accents amsbsy amsfonts amsmath amsopn amssymb amstext amsthm \
    appendix array atbegshi-ltx babel bigintcalc bitset bookmark \
    booktabs cancel caption caption3 changepage currfile dcolumn \
    enumerate enumitem environ epstopdf-base etoolbox eucal expl3 \
    filehook filehook-2020 float fontenc geometry gettitlestring \
    graphics graphicx hhline hycolor hyperref iftex ifthen ifvtex \
    import infwarerr intcalc keyval kvdefinekeys kvoptions kvsetkeys \
    ltxcmds moreverb multirow nameref natbib optional pathtools \
    pdfescape pdftexcmds pgfcore pgfrcs pgfsys placeins refcount \
    rerunfilecheck sansmathaccent koma-script scrbase scrkbase \
    scrlayer scrlayer-scrpage scrlfile scrlfile-hook scrlogo \
    setspace siunitx snapshot stringenc subcaption subfiles \
    tocbasic translations translator trig trimspaces typearea \
    uniquecounter url verbatim webpdf-macros xcolor xparse xpatch \
    xr-hyper xxcolor latexmk || echo "Some packages may have failed"

# Update font cache
RUN TEXLIVE_BIN=$(find /usr/local/texlive/2025/bin -type d -mindepth 1 -maxdepth 1 | head -1) && \
    $TEXLIVE_BIN/mktexlsr || true

# Create expected workspace structure for UV setup script
# The script expects /workspaces/HAFiscal-Public, so we'll create a symlink
RUN mkdir -p /workspaces && ln -s /workspace /workspaces/HAFiscal-Public

# ============================================================================
# Install UV (Python package manager) and set up Python environment
# ============================================================================
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH" && \
    echo "export PATH=\"\$HOME/.local/bin:\$HOME/.cargo/bin:\$PATH\"" >> /etc/profile.d/uv.sh && \
    chmod +x /etc/profile.d/uv.sh

# Set up Python environment with UV
RUN export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH" && \
    cd /workspace && \
    uv sync --all-groups || echo "uv sync completed with warnings"

# Add TeX Live to PATH permanently
RUN TEXLIVE_BIN=$(find /usr/local/texlive/2025/bin -type d -mindepth 1 -maxdepth 1 | head -1) && \
    echo "export PATH=\"$TEXLIVE_BIN:\$PATH\"" >> /etc/profile.d/texlive.sh && \
    chmod +x /etc/profile.d/texlive.sh

# Set PATH environment variable (from containerEnv in devcontainer.json)
# Note: We'll set this dynamically since TEXLIVE_BIN varies by architecture
ENV PATH="/usr/local/texlive/2025/bin/x86_64-linux:/home/vscode/.local/bin:/home/vscode/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Expose ports for Jupyter Lab and Voila Dashboard (from forwardPorts)
EXPOSE 8888 8866

# Default command
CMD ["/bin/bash"]

