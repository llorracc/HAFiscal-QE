# Binder Configuration

This directory contains configuration files for [MyBinder.org](https://mybinder.org), which allows users to launch interactive Jupyter notebooks in the cloud.

## Files

- **`environment.yml`** → symlink to `../environment.yml` (Single Source of Truth)
- **`apt.txt`** - System packages to install via apt-get
- **`postBuild`** - Post-installation script
- **`requirements.txt`** - Additional pip requirements

## Single Source of Truth

The `environment.yml` file is a **symlink** to the root-level `environment.yml`. This ensures:

- Only one environment specification to maintain
- Binder environment matches local development environment
- Changes to root `environment.yml` automatically apply to binder

When synced to HAFiscal-Public via `makePublic-master.sh`, the symlink is materialized (converted to a regular file) by rsync's `-L` flag, which is the correct behavior for distribution.

## Testing Binder

To test the binder configuration locally:

```bash
# Activate the environment
conda env create -f ../environment.yml
conda activate hafiscal

# Or with uv
uv sync --group=standalone
```

## Launching on MyBinder

Click the binder badge in the main README to launch the repository on MyBinder.org.
