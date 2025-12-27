# HAFiscal Environment Setup Scripts

## Single Source of Truth (SST)

This directory contains **shared environment setup scripts** that are used across multiple environments to ensure consistency.

## Why SST?

Previously, the HAFiscal project had **duplicate LaTeX installation logic** in two places:

- `.devcontainer/setup.sh` (for Docker/DevContainer)
- `.github/workflows/push-build-docs.yml` (for GitHub Actions)

This led to:

- ❌ **Drift**: Changes to one might not be applied to the other
- ❌ **Errors**: Copy-paste mistakes (we had a syntax error in one but not the other!)
- ❌ **Maintenance burden**: Every change requires updating multiple files

With SST, we now have:

- ✅ **Single script**: `setup-latex-minimal.sh` contains all LaTeX setup logic
- ✅ **Consistency**: All environments call the same script
- ✅ **Easy maintenance**: Changes in one place automatically apply everywhere

## Directory Structure

```
@resources/environment/
├── README.md                        ← This file
├── setup-latex-minimal.sh           ← LaTeX setup (SST)
├── validate-sst.sh                  ← SST pattern validator
├── install-hooks.sh                 ← Git hooks installer
└── pre-commit-hook-template         ← Pre-commit hook with SST validation
```

## Scripts

### `setup-latex-minimal.sh`

**Purpose**: Install and configure minimal LaTeX environment for HAFiscal compilation.

**What it does**:

1. Installs base LaTeX packages (`texlive-latex-base` + `texlive-latex-recommended`)
2. Verifies LaTeX installation (`pdflatex`, `latexmk`)
3. Configures `TEXMFHOME` to point to `@local/texlive/texmf-local/`
4. Configures `TEXINPUTS` to include `@resources/texlive/texmf-local/`

**Used by**:

- `.devcontainer/setup.sh` (DevContainer initialization)
- `.github/workflows/push-build-docs.yml` (GitHub Actions Ubuntu)

**Strategy**:

- Base installation: ~122 MB (`texlive-latex-base` + `texlive-latex-recommended`)
- Additional packages: 43 `.sty` files from `@local/texlive/texmf-local/` (in repo)
- **Total LaTeX size: ~200 MB** (vs ~4 GB for full TeXLive installation)

**Environment detection**:
The script automatically detects whether it's running in:

- GitHub Actions (`$GITHUB_WORKSPACE`)
- DevContainer (`/workspaces/{{REPO_NAME}}`)
- Other environments (finds repo root from script location)

## How to Use

### For DevContainers

```bash
# Called automatically during devcontainer creation
bash @resources/environment/setup-latex-minimal.sh
```

### For GitHub Actions

```yaml
- name: Install and configure minimal LaTeX (Ubuntu) - SST
  if: runner.os == 'Linux'
  run: |
    bash @resources/environment/setup-latex-minimal.sh
```

### For Local Development (optional)

```bash
# If you want to install minimal LaTeX on your local machine
cd /path/to/{{REPO_NAME}}
bash @resources/environment/setup-latex-minimal.sh
```

## SST Protection: Pre-Commit Hook

To **prevent accidental SST violations**, install the pre-commit hook:

```bash
# Install git hooks (includes SST validation)
bash @resources/environment/install-hooks.sh
```

### What the Pre-Commit Hook Does

When you commit changes to SST-related files, the hook automatically:

1. **Detects SST files**: Checks if commit modifies:
   - `.devcontainer/setup.sh`
   - `.github/workflows/push-build-docs.yml`
   - `@resources/environment/setup-latex-minimal.sh`

2. **Runs validation**: Executes `validate-sst.sh` to check:
   - ✅ SST scripts are properly called
   - ✅ No direct LaTeX installation bypassing SST
   - ✅ Master SST script exists

3. **Blocks commit** if SST pattern is violated

4. **Allows commit** if SST pattern is maintained

### Example Output

```bash
$ git commit -m "Update LaTeX setup"

🔍 HAFiscal Pre-Commit Safety Check...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 Validating Single Source of Truth (SST) pattern...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   📝 SST-related files detected in commit

🔍 Validating Single Source of Truth (SST) pattern...
   ✅ .devcontainer/setup.sh calls SST script
   ✅ GitHub Actions workflow calls SST script
   ✅ .devcontainer/setup.sh does not bypass SST
   ✅ GitHub Actions workflow does not bypass SST
   ✅ SST master script exists
   ✅ SST validation passed

✅ Pre-commit safety check passed!
```

### Bypassing the Hook (Emergency Only)

If you need to bypass the hook (not recommended):

```bash
git commit --no-verify -m "Emergency commit"
```

**Use sparingly!** The hook exists to protect SST integrity.

## Modifying LaTeX Setup

### ✅ Correct Way (SST)

1. Edit **only** `@resources/environment/setup-latex-minimal.sh`
2. Changes automatically apply to:
   - DevContainer (next rebuild)
   - GitHub Actions (next push)
   - Any other environment that calls the script

### ❌ Wrong Way (breaks SST)

Don't directly modify:

- `.devcontainer/setup.sh` LaTeX section ← should only call SST script
- `.github/workflows/push-build-docs.yml` Ubuntu LaTeX steps ← should only call SST script

## Package Management

### Base Packages (installed via apt)

- `latexmk`
- `texlive-latex-base`
- `texlive-latex-recommended`

### Additional Packages (from repo)
45 packages stored in `@local/texlive/texmf-local/tex/latex/`:

- See `reproduce/required_latex_packages.txt` for full list
- See `@local/texlive/README.md` for package details
- Includes `pdfsuppressruntime` and `pgf` (PGF/TikZ) for HAFiscal-Slides.tex

### Adding New LaTeX Packages

If HAFiscal requires a new LaTeX package:

1. **Check if it's in base+recommended**: Try compiling first
2. **If missing**: Download `.sty` file from CTAN
3. **Add to repo**: Place in `@local/texlive/texmf-local/tex/latex/`
4. **Document**: Update `reproduce/required_latex_packages.txt`
5. **No changes needed** to SST script - `TEXMFHOME` auto-discovers new files

## Testing SST Changes

### Test in DevContainer

```bash
# Rebuild devcontainer
# Cmd+Shift+P → "Dev Containers: Rebuild Container"
```

### Test in GitHub Actions

```bash
git add @resources/environment/setup-latex-minimal.sh
git commit -m "Update LaTeX SST script"
git push
# Check: {{REPO_URL}}/actions
```

## History

| Date | Event |
|------|-------|
| 2025-10-23 | Initial minimal LaTeX setup in `.devcontainer/setup.sh` |
| 2025-10-31 | Discovered syntax error in GitHub Actions (missing `fi`) |
| 2025-10-31 | **Created SST**: Extracted common logic to `setup-latex-minimal.sh` |

## Benefits of SST Approach

✅ **Consistency**: All environments use identical LaTeX configuration  
✅ **Maintainability**: Update once, apply everywhere  
✅ **Reliability**: No more copy-paste errors  
✅ **Testability**: Single script easier to test and debug  
✅ **Documentation**: Clear single point of reference

## Related Files

- `@local/texlive/README.md` - Documentation for local LaTeX packages
- `reproduce/required_latex_packages.txt` - List of required LaTeX packages
- `.devcontainer/setup.sh` - DevContainer initialization script
- `.github/workflows/push-build-docs.yml` - GitHub Actions workflow
