# Getting Started with HAFiscal

**Welcome!** This guide will help you get started with the HAFiscal replication package. Follow the steps below based on what you want to accomplish.

---

## Quick Navigation

### I want to...

#### ...just compile the paper PDF (5-10 minutes)
**Read**: [Quick Start section in main README.md](../README.md#quick-start)  
**Run**: `./reproduce.sh --docs`  
**Time**: 5-10 minutes  
**Requirements**: LaTeX installation only

#### ...reproduce all results (4-5 days)
**Read in order**:

1. [INSTALLATION.md](INSTALLATION.md) - Set up your environment
2. [REPLICATION.md](REPLICATION.md) Section 4 - Execution instructions
3. [Code/README.md](../Code/README.md) - Understand the computational workflow

**Run**: `./reproduce.sh --comp full`  
**Time**: 4-5 days on high-end hardware  
**Requirements**: Python environment, LaTeX, computational resources

#### ...test that everything works (~1 hour)
**Read**: [INSTALLATION.md](INSTALLATION.md) - Set up your environment  
**Run**: `./reproduce.sh --comp min`  
**Time**: ~1 hour  
**Requirements**: Python environment, LaTeX

#### ...understand the code structure
**Read**: [Code/README.md](../Code/README.md)  
**Location**: `Code/HA-Models/` directory  
**Key file**: `Code/HA-Models/do_all.py` (main orchestrator)

#### ...troubleshoot an issue
**Read**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)  
**Also check**: [QUICK-REFERENCE.md](QUICK-REFERENCE.md) for common commands

#### ...contribute to the project
**Read**: [CONTRIBUTING.md](CONTRIBUTING.md)  
**Note**: This repository is the Single Source of Truth (SST). External contributions go to HAFiscal-Public.

---

## First-Time User Path

If this is your first time working with HAFiscal, follow this sequence:

### Step 1: Understand What You're Getting

- **Read**: [Main README.md](../README.md) - Overview and quick start
- **Time**: 5 minutes
- **Purpose**: Understand the repository structure and what's included

### Step 2: Set Up Your Environment

- **Read**: [INSTALLATION.md](INSTALLATION.md) - Platform-specific installation
- **Time**: 10-30 minutes (depending on platform)
- **Purpose**: Install required software (Python, LaTeX, dependencies)

### Step 3: Verify Installation

- **Run**: `./reproduce.sh --comp min` - Minimal computational test
- **Time**: ~1 hour
- **Purpose**: Verify that your environment is working correctly

### Step 4: Understand the Workflow

- **Read**: [REPLICATION.md](REPLICATION.md) - Complete replication guide
- **Time**: 15-20 minutes
- **Purpose**: Understand data sources, computational steps, and outputs

### Step 5: Run Full Replication (Optional)

- **Read**: [Code/README.md](../Code/README.md) - Detailed code workflow
- **Run**: `./reproduce.sh --comp full` - Full computational replication
- **Time**: 4-5 days
- **Purpose**: Reproduce all results from the paper

---

## Documentation Map

```
{{REPO_NAME}}/
├── README.md                    # Main entry point (start here)
│
├── README/
│   ├── GETTING-STARTED.md       # This file (navigation guide)
│   ├── INSTALLATION.md          # Environment setup
│   ├── REPLICATION.md           # Complete replication guide
│   ├── QUICK-REFERENCE.md       # Command reference
│   ├── TROUBLESHOOTING.md       # Common issues
│   └── CONTRIBUTING.md          # Contribution guidelines
│
├── Code/
│   └── README.md                # Code workflow documentation
│
└── reproduce/
    └── README.md                # Reproduction script documentation
```

**Reading Order for First-Time Users**:

1. `README.md` (root) - Overview
2. `README/GETTING-STARTED.md` (this file) - Navigation
3. `README/INSTALLATION.md` - Setup
4. `README/REPLICATION.md` - Replication workflow
5. `Code/README.md` - Code details (if needed)

---

## Common Workflows

### Workflow 1: Quick Paper Compilation
**Goal**: Generate the paper PDF from existing results

```bash
# 1. Clone repository
git clone {{REPO_URL}}.git
cd {{REPO_NAME}}

# 2. Install LaTeX (if not already installed)
# macOS: brew install --cask mactex
# Linux: sudo apt-get install texlive-full

# 3. Compile paper
./reproduce.sh --docs

# Output: HAFiscal.pdf
```

**Time**: 5-10 minutes  
**Documentation**: [REPLICATION.md](REPLICATION.md) Section 4.1

### Workflow 2: Minimal Verification
**Goal**: Test that the environment works without full computation

```bash
# 1. Follow installation steps (see INSTALLATION.md)
# 2. Set up Python environment
./reproduce/reproduce_environment_comp_uv.sh
source .venv/bin/activate

# 3. Run minimal computation
./reproduce.sh --comp min

# 4. Compile paper
./reproduce.sh --docs
```

**Time**: ~1 hour  
**Documentation**: [INSTALLATION.md](INSTALLATION.md), [REPLICATION.md](REPLICATION.md) Section 4.2

### Workflow 3: Full Replication
**Goal**: Reproduce all computational results from the paper

```bash
# 1. Follow installation steps (see INSTALLATION.md)
# 2. Set up Python environment
./reproduce/reproduce_environment_comp_uv.sh
source .venv/bin/activate

# 3. Download data (if needed)
bash Code/Empirical/download_scf_data.sh

# 4. Run full computation
./reproduce.sh --comp full

# 5. Compile paper
./reproduce.sh --docs
```

**Time**: 4-5 days on high-end hardware  
**Documentation**: [REPLICATION.md](REPLICATION.md) Section 4.3, [Code/README.md](../Code/README.md)

---

## Key Files to Know

| File | Purpose | When to Read |
|------|---------|--------------|
| `README.md` (root) | Main entry point | Always start here |
| `README/GETTING-STARTED.md` | Navigation guide | First-time users |
| `README/INSTALLATION.md` | Environment setup | Before running code |
| `README/REPLICATION.md` | Complete replication guide | Before full replication |
| `README/QUICK-REFERENCE.md` | Command reference | Quick lookups |
| `README/TROUBLESHOOTING.md` | Common issues | When problems occur |
| `Code/README.md` | Code workflow | Understanding computational steps |
| `reproduce.sh` | Main reproduction script | Running reproductions |

---

## Platform-Specific Notes

### macOS

- **Installation**: See [INSTALLATION.md](INSTALLATION.md) Section "macOS Installation"
- **Package Manager**: Homebrew recommended
- **LaTeX**: MacTeX via Homebrew (`brew install --cask mactex`)
- **Python**: Use UV or Conda (see installation guide)

### Linux (Ubuntu/Debian)

- **Installation**: See [INSTALLATION.md](INSTALLATION.md) Section "Linux Installation"
- **Package Manager**: apt-get
- **LaTeX**: `sudo apt-get install texlive-full`
- **Python**: Use UV or Conda (see installation guide)

### Windows

- **Installation**: See [INSTALLATION.md](INSTALLATION.md) Section "Windows Installation"
- **Requirement**: Windows Subsystem for Linux 2 (WSL2)
- **Note**: Native Windows is not supported

---

## Next Steps

1. **Choose your workflow** from the "Common Workflows" section above
2. **Follow the documentation** in the order specified
3. **Run the commands** as documented
4. **Refer to troubleshooting** if you encounter issues

---

## Getting Help

- **Documentation**: Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) first
- **Quick Reference**: See [QUICK-REFERENCE.md](QUICK-REFERENCE.md) for common commands
- **Issues**: Open an issue on the repository (if applicable)
- **Questions**: Contact the authors (see main README.md)

---

**Last Updated**: 2025-11-26  
**Version**: 1.0
