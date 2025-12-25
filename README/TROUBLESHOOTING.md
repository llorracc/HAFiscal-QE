# HAFiscal Troubleshooting Guide

This guide helps resolve common issues when installing or running HAFiscal.

## Quick Diagnostics

Run this to check your environment:

```bash
./reproduce/test-cross-platform.sh
```

This tests:

- Environment setup
- Python path construction  
- LaTeX installation
- Platform compatibility

---

## Installation Issues

### UV Installation Problems

#### `uv: command not found`

**Problem:** UV isn't in your PATH after installation.

**Solution:**

```bash
# Check if UV is installed
ls -la ~/.cargo/bin/uv

# If it exists, add to PATH
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc  # or ~/.zshrc for macOS
source ~/.bashrc  # or source ~/.zshrc
```

#### UV Installation Fails

**Problem:** Installation script fails or hangs.

**Solution:**

```bash
# Try manual installation
curl -LsSf https://astral.sh/uv/install.sh > install-uv.sh
bash install-uv.sh

# If that fails, use Conda instead (see INSTALLATION.md)
```

---

### LaTeX Installation Problems

#### `pdflatex: command not found`

**Problem:** LaTeX is not installed or not in PATH.

**Platform-specific solutions:**

**macOS:**

```bash
# If MacTeX is installed, add to PATH
export PATH="/Library/TeX/texbin:$PATH"
echo 'export PATH="/Library/TeX/texbin:$PATH"' >> ~/.zshrc

# If not installed
brew install --cask mactex
```

**Linux:**

```bash
# Install LaTeX
sudo apt-get install texlive-full

# Or minimal install
sudo apt-get install texlive latexmk
```

**Windows (WSL2):**

```bash
# In WSL2 Ubuntu terminal
sudo apt-get install texlive-full
```

#### LaTeX Package Missing

**Problem:** Error like `! LaTeX Error: File 'subfiles.sty' not found.`

**Solution:**

**macOS:**

```bash
sudo tlmgr install subfiles  # or whatever package is missing
```

**Linux:**

```bash
# Install more packages
sudo apt-get install texlive-latex-extra texlive-fonts-recommended
```

---

### Python Environment Problems

#### Python 3.9 Not Available

**Problem:** UV or Conda can't find Python 3.9.

**Solution with UV:**

```bash
# UV will automatically install Python 3.9
uv python install 3.9
uv sync --all-groups
```

**Solution with Conda:**

```bash
# Specify Python version explicitly
conda env create -f environment.yml
```

#### Module Import Errors

**Problem:** `ModuleNotFoundError: No module named 'HARK'` or similar.

**Solution:**

```bash
# Make sure environment is activated (auto-activates in new shells with UV)
# Manual activation if needed:
# source .venv-linux-x86_64/bin/activate  # UV (Intel/AMD Linux)
# source .venv-darwin-arm64/bin/activate   # UV (Apple Silicon)
# or
conda activate hafiscal  # for Conda

# If still failing, reinstall environment
rm -rf .venv-*  # Remove all architecture-specific venvs
./reproduce/reproduce_environment_comp_uv.sh
```

---

## Runtime Issues

### Document Generation Problems

#### `latexmk` Fails with "Circular Reference"

**Problem:** LaTeX compilation fails with circular reference errors.

**Solution:**
This is usually handled automatically by `.latexmkrc`, but if it persists:

```bash
# Clean auxiliary files and rebuild
./reproduce.sh --docs main --clean
```

#### Bibliography Not Updating

**Problem:** Citation changes don't appear in PDF.

**Solution:**

```bash
# Force full rebuild
cd /path/to/HAFiscal
rm -f *.aux *.bbl *.blg
./reproduce.sh --docs main
```

#### PDF Generation Incomplete

**Problem:** PDF is generated but missing content or has "??" references.

**Solution:**

```bash
# Run full compilation (not --quick)
./reproduce.sh --docs main

# LaTeX needs multiple passes for cross-references
# The script handles this automatically
```

---

### Computational Reproduction Problems

#### Computation Takes Too Long

**Problem:** `./reproduce.sh --comp full` has been running for days.

**Expected behavior:** Full computation takes 4-5 days on a high-end 2025 laptop.

**Solutions:**

1. **Run minimal version first:**

   ```bash
   ./reproduce.sh --comp min  # ~1 hour
   ```

2. **Monitor progress:**

   ```bash
   # Check which Python processes are running
   ps aux | grep python
   
   # Monitor CPU usage
   top  # or htop if installed
   ```

3. **If truly stuck:**

   ```bash
   # Kill and restart
   pkill -f python
   ./reproduce.sh --comp min
   ```

#### Python Script Crashes

**Problem:** Python script exits with error during computation.

**Solution:**

1. **Check error message** - Look for specific module or function that failed

2. **Verify environment:**

   ```bash
   # Activate architecture-specific venv:
   # source .venv-linux-x86_64/bin/activate  (Intel/AMD Linux)
   # source .venv-darwin-arm64/bin/activate  (Apple Silicon)
   python --version  # Should show 3.9.x
   python -c "import HARK; print(HARK.__version__)"
   ```

3. **Check memory:**

   ```bash
   # Linux/macOS
   free -h  # Linux
   vm_stat  # macOS
   
   # If low on memory, close other applications
   ```

4. **Re-run specific script:**

   ```bash
   cd Code/HA-Models
   # Activate architecture-specific venv:
   # source .venv-linux-x86_64/bin/activate  # Intel/AMD Linux
   # source .venv-darwin-arm64/bin/activate   # Apple Silicon
   python do_all.py  # or specific script that failed
   ```

---

## Platform-Specific Issues

### macOS Issues

#### Rosetta 2 on Apple Silicon

**Problem:** Some packages need Rosetta 2 on M1/M2/M3 Macs.

**Solution:**

```bash
# Install Rosetta 2 if prompted
softwareupdate --install-rosetta

# UV handles architecture automatically
```

#### XCode Command Line Tools

**Problem:** Compilation errors about missing compilers.

**Solution:**

```bash
xcode-select --install
```

---

### Linux Issues

#### Permission Denied on Scripts

**Problem:** `bash: ./reproduce.sh: Permission denied`

**Solution:**

```bash
chmod +x reproduce.sh
chmod +x reproduce/*.sh
```

#### Missing System Libraries

**Problem:** Python packages fail to install due to missing C libraries.

**Solution:**

```bash
sudo apt-get install build-essential python3-dev
```

---

### Windows (WSL2) Issues

#### Broken Symlinks Error

**Problem:** Script exits with "❌ ERROR: Broken Symlinks Detected"

**Cause:** Repository was cloned using Git for Windows and then accessed from WSL2.

**Why this happens:** Git for Windows converts symlinks to regular text files. When accessed from WSL2, these appear as broken symlinks and the repository won't work.

**Solution:**

1. **Delete** the current repository clone (the one cloned from Windows)
2. Open a WSL2 terminal
3. Clone FROM WITHIN WSL2:

   ```bash
   cd ~
   git clone {{REPO_URL}}.git
   cd {{REPO_NAME}}
   ```

**Prevention:** Always clone this repository from within WSL2, never from Windows.

#### WSL2 Not Installed

**Problem:** `wsl: command not found` in PowerShell.

**Solution:**

1. Make sure you're on Windows 10 version 2004+ or Windows 11
2. Enable "Virtual Machine Platform" in Windows Features
3. Run as Administrator: `wsl --install`
4. Restart computer

#### Slow File Access

**Problem:** Everything is very slow in WSL2.

**Solution:**

```bash
# Work in WSL filesystem (fast)
cd ~/HAFiscal

# NOT in Windows filesystem (slow)
# Avoid: cd /mnt/c/Users/YourName/HAFiscal
```

**Why?** WSL2 accessing Windows filesystem (`/mnt/c/...`) is much slower than accessing its own filesystem (`~/...`).

#### WSL2 Out of Memory

**Problem:** WSL2 runs out of memory during computation.

**Solution:**

Create/edit `.wslconfig` in your Windows user folder (`C:\Users\YourName\.wslconfig`):

```ini
[wsl2]
memory=8GB
processors=4
```

Then restart WSL2:

```powershell
# In PowerShell
wsl --shutdown
```

---

## Path and File Issues

### Paths with Spaces

**Problem:** Scripts fail with paths containing spaces.

**Solution:**
Most scripts handle this correctly, but if you encounter issues:

```bash
# Move to path without spaces
mv "/path/with spaces/HAFiscal" ~/HAFiscal
cd ~/HAFiscal
```

### Windows Backslash Paths

**Problem:** Path errors on Linux/WSL2 after editing on Windows.

**Expected:** All path issues have been fixed (as of 2025-10-22).

**If you still see issues:**

```bash
# Report this as a bug - we thought we fixed all of these!
# Include the error message and file name
```

---

## Testing and Validation Issues

### Cross-Platform Test Failures

**Problem:** `./reproduce/test-cross-platform.sh` shows errors.

**Solutions by test:**

#### Test 1: Environment Setup Fails

```bash
# .venv not found
./reproduce/reproduce_environment_comp_uv.sh
```

#### Test 4: Python Path Construction Fails

```bash
# Usually means Python environment issue
# Activate architecture-specific venv:
   # source .venv-linux-x86_64/bin/activate  (Intel/AMD Linux)
   # source .venv-darwin-arm64/bin/activate  (Apple Silicon)
python --version
```

#### Test 6: LaTeX Not Found

```bash
# See "LaTeX Installation Problems" section above
```

### Docker Test Failures

**Problem:** `./reproduce/test-ubuntu-22.04.sh` fails.

**Solution:**

1. **Check Docker is running:**

   ```bash
   docker ps
   ```

2. **Start Docker Desktop** (macOS/Windows) or Docker daemon (Linux)

3. **Pull Ubuntu image manually:**

   ```bash
   docker pull ubuntu:22.04
   ```

4. **Run test again:**

   ```bash
   ./reproduce/test-ubuntu-22.04.sh
   ```

---

## Performance Issues

### Slow Compilation

**Problem:** Document generation takes a very long time.

**Expected time:** 5-10 minutes for `--docs main`

**If slower:**

1. **Check CPU usage:** Should be near 100% during compilation
2. **Check disk space:** LaTeX needs temporary space
3. **Try minimal build:**

   ```bash
   BUILD_MODE=SHORT ./reproduce.sh --docs main
   ```

### Slow Computation

**Problem:** Python computations are slower than expected.

**Expected time:** ~1 hour for minimal, 4-5 days on a high-end 2025 laptop for full

**Solutions:**

1. **Check CPU:** Should be near 100% during computation
2. **Close other applications:** Free up RAM and CPU
3. **Check swap usage:**

   ```bash
   # If heavily swapping, you need more RAM
   free -h  # Linux
   ```

---

## Environment Conflicts

### Conda vs UV Conflicts

**Problem:** Both Conda and UV are installed, causing confusion.

**Solution:**

**Choose one:**

**Option A: Use UV (recommended, faster)**

```bash
# Deactivate conda
conda deactivate

# Use UV
# Activate architecture-specific venv:
   # source .venv-linux-x86_64/bin/activate  (Intel/AMD Linux)
   # source .venv-darwin-arm64/bin/activate  (Apple Silicon)
```

**Option B: Use Conda**

```bash
# Deactivate UV env
deactivate

# Use Conda
conda activate hafiscal
```

### Multiple Python Versions

**Problem:** Wrong Python version is being used.

**Solution:**

**With UV:**

```bash
# UV manages Python version automatically
uv sync --all-groups
# Activate architecture-specific venv:
   # source .venv-linux-x86_64/bin/activate  (Intel/AMD Linux)
   # source .venv-darwin-arm64/bin/activate  (Apple Silicon)
python --version  # Should show 3.9.x
```

**With Conda:**

```bash
# Conda environment pins Python version
conda activate hafiscal
python --version  # Should show 3.9.x
```

---

## Network Issues

### Download Failures

**Problem:** Package downloads fail or timeout.

**Solution:**

1. **Check internet connection**

2. **Retry with verbose output:**

   ```bash
   uv sync --all-groups --verbose
   ```

3. **Try different network:**
   - Some corporate networks block package repositories
   - Try from home network or mobile hotspot

4. **Use proxy if needed:**

   ```bash
   export HTTP_PROXY=http://proxy.example.com:8080
   export HTTPS_PROXY=http://proxy.example.com:8080
   ```

---

## Getting More Help

### Enable Verbose Output

For better error messages:

```bash
# For UV
uv sync --all-groups --verbose

# For reproduction
./reproduce.sh --docs main --verbose

# For shell scripts
bash -x ./reproduce.sh --docs main
```

### Check Logs

LaTeX logs are usually kept:

```bash
# Check LaTeX log for detailed errors
less HAFiscal.log

# Check for specific errors
grep "Error" HAFiscal.log
grep "Warning" HAFiscal.log
```

### System Information

When reporting issues, include:

```bash
# Platform
uname -a

# Python version
python --version

# UV version
uv --version

# LaTeX version
pdflatex --version

# Environment
echo $PATH
env | grep -i python
```

### Reporting Bugs

If none of these solutions work:

1. **Search existing issues:** {{REPO_URL}}/issues

2. **Create new issue with:**
   - Platform (macOS/Linux/WSL2)
   - Error message (full text)
   - Steps to reproduce
   - System information (see above)
   - What you've already tried

---

## Additional Resources

- **Installation Guide:** [`INSTALLATION.md`](INSTALLATION.md)
- **Main README:** [`README.md`](README.md)
- **Reproduction Guide:** [`reproduce/README.md`](reproduce/README.md)

---

## Still Stuck?

If you've tried everything in this guide and still have issues:

1. Review the [Installation Guide](INSTALLATION.md) - make sure you didn't miss a step
3. Search or create an issue on GitHub
4. Ask for help in the econ-ark community

**Remember:** Most issues are environment-related. The most common fix is to start fresh:

```bash
# Clean slate
rm -rf .venv-*  # Remove all architecture-specific venvs
./reproduce/reproduce_environment_comp_uv.sh
./reproduce.sh --docs main
```

Good luck! 🎯
