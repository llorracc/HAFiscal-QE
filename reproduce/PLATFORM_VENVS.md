# Platform-Specific Virtual Environments

## Overview

This project now supports **platform-specific virtual environments** to enable seamless switching between macOS (local development) and Linux (DevContainer) without rebuilding venvs each time.

## How It Works

- **macOS**: Uses `.venv-darwin/` directory
- **Linux**: Uses `.venv-linux/` directory  
- **Legacy support**: Falls back to `.venv/` if platform-specific venv doesn't exist

Each platform maintains its own venv with platform-specific Python binaries and compiled packages, preventing architecture mismatches.

## Quick Start

### First-Time Setup

1. **On macOS**:
   ```bash
   ./reproduce/reproduce_environment_comp_uv.sh
   ```
   This creates `.venv-darwin/` and a symlink `.venv -> .venv-darwin`

2. **In DevContainer (Linux)**:
   ```bash
   ./reproduce/reproduce_environment_comp_uv.sh
   ```
   This creates `.venv-linux/` and updates the symlink `.venv -> .venv-linux`

### Migrating Existing .venv

If you already have a `.venv` directory:

```bash
./reproduce/migrate_to_platform_venvs.sh
```

This will:
- Move your existing `.venv` to `.venv-{platform}` based on your current OS
- Preserve all installed packages
- Set up the symlink structure

### Using the Environments

The `reproduce.sh` script automatically detects and uses the correct platform-specific venv:

```bash
./reproduce.sh --envt        # Test environment (auto-detects platform)
./reproduce.sh --docs        # Compile documents
./reproduce.sh --comp min    # Run computations
```

## Technical Details

### Symlink Strategy

UV expects `.venv/` to exist. To work with platform-specific venvs:

1. A symlink `.venv -> .venv-{platform}` is maintained
2. UV commands work normally through the symlink
3. The symlink is gitignored (via `.venv/` pattern)
4. **Each platform automatically fixes the symlink** when scripts run:
   - Scripts detect if `.venv` symlink points to wrong platform
   - If wrong, they remove and recreate it pointing to current platform's venv
   - This ensures the symlink is always correct for the current platform

### Platform Detection

The scripts detect platform using `uname -s`:
- `Darwin` → `.venv-darwin`
- `Linux` → `.venv-linux`
- Other → `.venv` (fallback)

### Git Ignore

Both platform-specific venvs are gitignored:
- `.venv-darwin/`
- `.venv-linux/`
- `.venv/` (legacy or symlink)

## Benefits

✅ **No rebuilds**: Switch between macOS and DevContainer without recreating venvs  
✅ **Architecture safety**: Each platform has correctly compiled packages  
✅ **Backward compatible**: Legacy `.venv/` still works during migration  
✅ **Automatic detection**: Scripts auto-detect and use the correct venv  

## Troubleshooting

### "Virtual Environment Incomplete" Error

This usually means the venv was synced from another platform. Fix:

```bash
rm -rf .venv-{platform}  # Remove broken venv
./reproduce/reproduce_environment_comp_uv.sh  # Recreate
```

### Symlink Issues

If the `.venv` symlink is broken:

```bash
rm -f .venv
ln -s .venv-{platform} .venv  # Replace {platform} with darwin or linux
```

### Manual Activation

To manually activate a platform-specific venv:

```bash
# macOS
source .venv-darwin/bin/activate

# Linux
source .venv-linux/bin/activate
```

## Files Modified

- `reproduce.sh` - Platform detection and venv path resolution
- `reproduce/reproduce_environment_comp_uv.sh` - Creates platform-specific venvs
- `reproduce/reproduce_data_moments.sh` - Uses platform-specific venvs
- `.gitignore` - Added platform-specific venv patterns
- `reproduce/migrate_to_platform_venvs.sh` - Migration helper script

