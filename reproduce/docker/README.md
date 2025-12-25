# Docker/Container Setup Scripts

This directory contains scripts for setting up Docker containers and devcontainers.

## Scripts

- **`setup.sh`** - Main setup script that installs:
  - TeX Live 2025 (scheme-basic + individual packages)
  - UV (Python package manager)
  - Python virtual environment (.venv)
  - Shell auto-activation configuration

- **`run-setup.sh`** - Helper script to find and execute setup.sh
  - Used by devcontainer.json postCreateCommand
  - Searches /workspaces for reproduce/docker/setup.sh

- **`detect-arch.sh`** - Architecture detection for TeX Live
  - Detects x86_64-linux or aarch64-linux
  - Returns correct TeX Live binary directory path

- **`activate-venv.sh`** - Virtual environment activation helper
  - Can be sourced manually: `source reproduce/docker/activate-venv.sh`

- **Other utility scripts** - Benchmarking, testing, and maintenance tools

## Usage

### From devcontainer.json
The devcontainer.json automatically calls `run-setup.sh` during container creation.

### From Dockerfile
The Dockerfile makes these scripts executable and can reference them if needed.

### Manual execution

```bash
# From repository root
bash reproduce/docker/setup.sh
```

## Location Rationale

These scripts are in `reproduce/docker/` rather than `.devcontainer/` because:

- They're part of the reproduction infrastructure (not just devcontainer config)
- They're needed by QE repository (which doesn't have `.devcontainer/`)
- They're accessible to both devcontainer.json and Dockerfile builds
- They are shared across repository variants via make-repo scripts

## See Also

- `.devcontainer/devcontainer.json` - Devcontainer configuration
- `Dockerfile` - Standalone Docker image build
- `.devcontainer/README.md` - Devcontainer usage guide
