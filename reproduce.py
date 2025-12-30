#!/usr/bin/env python3
"""
HAFiscal Reproduction Script (Python Version)

Cross-platform reproduction script for HAFiscal project.
Mirrors the functionality of reproduce.sh with identical CLI interface.
"""

import argparse
import atexit
import json
import os
import platform
import subprocess
import sys
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# ============================================================================
# CHECK FOR WINDOWS (NON-WSL) ENVIRONMENT
# ============================================================================
def check_windows_environment():
    """Check if running on Windows (non-WSL) and exit with error message."""
    system = platform.system()
    
    # Check if we're on Windows but NOT in WSL
    if system == "Windows":
        # Check if we're in WSL by looking for WSL-specific indicators
        is_wsl = False
        try:
            with open("/proc/version", "r") as f:
                version_info = f.read().lower()
                is_wsl = "microsoft" in version_info or "wsl" in version_info
        except FileNotFoundError:
            is_wsl = False
        
        if not is_wsl:
            print("=" * 64)
            print("❌ ERROR: Windows Native Environment Detected")
            print("=" * 64)
            print()
            print("This script requires a Unix-like environment and cannot run")
            print("directly on Windows.")
            print()
            print("Please use Windows Subsystem for Linux 2 (WSL2) instead:")
            print()
            print("1. Install WSL2 (if not already installed):")
            print("   https://docs.microsoft.com/en-us/windows/wsl/install")
            print()
            print("2. Open a WSL2 terminal (Ubuntu recommended)")
            print()
            print("3. Navigate to this project directory in WSL2")
            print()
            print("4. Run this script again from within WSL2:")
            print("   python3 reproduce.py [options]")
            print()
            print("Note: WSL1 is not supported. You must use WSL2.")
            print()
            sys.exit(1)

# Run the check immediately
check_windows_environment()


# ============================================================================
# CHECK FOR BROKEN SYMLINKS (Git clone from Windows)
# ============================================================================
def check_symlinks():
    """Check if symlinks are broken (cloned from Windows then accessed from WSL2)."""
    # Check a known symlink that should exist in the repository
    test_symlink = Path("Tables/.latexmkrc")
    
    if test_symlink.exists():
        # File exists - check if it's actually a symlink
        if not test_symlink.is_symlink():
            # It's a regular file, not a symlink - likely cloned from Windows
            print("=" * 64)
            print("❌ ERROR: Broken Symlinks Detected")
            print("=" * 64)
            print()
            print("This repository contains symlinks that have been corrupted.")
            print("This typically happens when the repository was cloned using")
            print("Git for Windows and then accessed from WSL2.")
            print()
            print("SOLUTION:")
            print()
            print("1. DELETE the current repository clone")
            print()
            print("2. Open a WSL2 terminal (Ubuntu recommended)")
            print()
            print("3. Clone the repository FROM WITHIN WSL2:")
            print("   cd ~")
            print("   git clone https://github.com/econ-ark/HAFiscal.git")
            print("   cd HAFiscal")
            print()
            print("4. Run this script again:")
            print("   python3 reproduce.py")
            print()
            print("IMPORTANT: Always clone Git repositories with symlinks from")
            print("within WSL2, not from Windows. Git for Windows does not handle")
            print("symlinks properly for cross-platform use.")
            print()
            print("See README.md for more information on Windows setup.")
            print()
            sys.exit(1)

# Run the symlink check
check_symlinks()


def ensure_uv_environment():
    """
    Ensure we're running in the uv .venv environment.
    If not, re-execute this script with the environment activated.
    """
    # Get the expected venv path
    script_dir = Path(__file__).parent.resolve()
    expected_venv = script_dir / ".venv"
    
    # Check if we're already in the correct uv .venv environment
    current_venv = os.environ.get('VIRTUAL_ENV', '')
    if current_venv:
        # Normalize paths to handle symlinks
        try:
            normalized_current = Path(current_venv).resolve()
            if normalized_current == expected_venv:
                # Already in correct environment
                return
        except (OSError, RuntimeError):
            pass
    
    # Check if .venv exists
    if not expected_venv.exists():
        print("=" * 40)
        print("❌ UV Virtual Environment Not Found")
        print("=" * 40)
        print()
        print("The uv virtual environment (.venv) does not exist.")
        print()
        print("Please set up the environment first:")
        print("  ./reproduce/reproduce_environment_comp_uv.sh")
        print()
        print("Or manually:")
        print("  uv sync --all-groups")
        print()
        sys.exit(1)
    
    venv_python = expected_venv / "bin" / "python"
    if sys.platform == "win32":
        venv_python = expected_venv / "Scripts" / "python.exe"
    
    if not venv_python.exists():
        print("=" * 40)
        print("❌ UV Virtual Environment Incomplete")
        print("=" * 40)
        print()
        print("The .venv directory exists but appears incomplete.")
        print()
        print("Please re-run the setup:")
        print("  ./reproduce/reproduce_environment_comp_uv.sh")
        print()
        print("Or manually:")
        print("  uv sync --all-groups")
        print()
        sys.exit(1)
    
    # We need to activate the environment
    print("=" * 40)
    print("🔄 Activating UV Environment")
    print("=" * 40)
    print()
    
    # Check if conda is active and warn user
    conda_env = os.environ.get('CONDA_DEFAULT_ENV', '')
    if conda_env:
        print(f"ℹ️  Detected active conda environment: {conda_env}")
        print("   Switching to uv .venv environment...")
        print()
    
    print("✅ Activating .venv and re-running reproduce.py...")
    print()
    
    # Re-execute this script with the venv Python
    args = [str(venv_python)] + sys.argv
    os.execv(str(venv_python), args)


class ReproductionScript:
    """Main reproduction script controller."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.resolve()
        self.reproduce_dir = self.project_root / "reproduce"
        self.dry_run = False
        self.benchmark_enabled = os.environ.get('BENCHMARK', 'true').lower() == 'true'
        self.benchmark_start_time = None
        self.benchmark_start_iso = None
        self.action = None
        self.action_scope = None
        self.exit_status = 0
        self.envt_using_uv = False
        
        # Register benchmark save on exit
        if self.benchmark_enabled:
            atexit.register(self._save_benchmark)
        
    def show_interactive_menu(self) -> Optional[str]:
        """Show interactive menu and return user's choice."""
        print("=" * 40)
        print("   HAFiscal Reproduction Options")
        print("=" * 40)
        print()
        print("Please select what you would like to reproduce:")
        print()
        print("1) LaTeX Documents")
        print("   - Compiles all PDF documents from LaTeX source")
        print("   - Estimated time: A few minutes")
        print()
        print("2) Subfiles")
        print("   - Compiles all .tex files in Subfiles/, Figures/, and Tables/ directories")
        print("   - Estimated time: A few minutes")
        print()
        print("3) Minimal Computational Results")
        print("   - Reproduces a subset of computational results")
        print("   - ⚠️  PREREQUISITE: Requires full computational results to be run first (option 4)")
        print("   - Estimated time: ~1 hour")
        print("   - Good for testing and quick verification")
        print()
        print("4) All Computational Results")
        print("   - Reproduces all computational results from the paper")
        print("   - ⚠️  WARNING: This may take 4-5 DAYS on a high-end 2025 laptop")
        print("   - Requires significant computational resources")
        print("   - Upon completion, a benchmark log will be generated in reproduce/benchmarks/results/")
        print()
        print("5) Everything")
        print("   - All documents + all computational results")
        print("   - ⚠️  WARNING: This may take 4-5 DAYS on a high-end 2025 laptop")
        print("   - Complete reproduction of the entire project")
        print()
        print("6) Exit")
        print()
        
        try:
            choice = input("Enter your choice (1-6): ").strip()
            return choice
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            return None
    
    def run_interactive_menu(self) -> int:
        """Execute interactive menu mode."""
        while True:
            choice = self.show_interactive_menu()
            
            if choice is None or choice == "6":
                print("Exiting.")
                return 0
            
            print()
            
            try:
                if choice == "1":
                    return self.reproduce_documents()
                elif choice == "2":
                    return self.reproduce_subfiles()
                elif choice == "3":
                    return self.reproduce_minimal_results()
                elif choice == "4":
                    return self.reproduce_all_computational_results()
                elif choice == "5":
                    return self.reproduce_all_results()
                else:
                    print(f"Invalid choice: {choice}")
                    print("Please enter a number between 1 and 6.")
                    print()
                    input("Press Enter to continue...")
                    continue
            except KeyboardInterrupt:
                print("\n\nInterrupted by user.")
                return 130
    
    def test_environment(self) -> bool:
        """Test if required dependencies are available."""
        print("=" * 40)
        print("Environment Testing")
        print("=" * 40)
        print()
        print("🔍 Checking required dependencies...")
        
        env_ok = True
        missing_deps = []
        
        # Test basic commands
        print("• Checking basic tools...")
        required_commands = ["latexmk", "pdflatex", "bibtex", "python3"]
        
        for cmd in required_commands:
            if not shutil.which(cmd):
                missing_deps.append(cmd)
                env_ok = False
        
        # Test LaTeX environment
        print("• Checking LaTeX environment...")
        texlive_script = self.reproduce_dir / "reproduce_environment_texlive.sh"
        if texlive_script.exists():
            try:
                subprocess.run(
                    ["bash", str(texlive_script)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                    timeout=30
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                missing_deps.append("LaTeX packages (see reproduce_environment_texlive.sh)")
                env_ok = False
        else:
            print("  ⚠️  Cannot verify LaTeX packages (reproduce_environment_texlive.sh not found)")
        
        # Test computational environment
        print("• Checking computational environment...")
        env_script = self.reproduce_dir / "reproduce_environment.sh"
        if env_script.exists():
            try:
                subprocess.run(
                    ["bash", str(env_script)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                    timeout=30
                )
                print("  ✅ Python/Conda environment OK")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                print("  ⚠️  Python/Conda environment needs setup (non-critical for document reproduction)")
        
        # Report results
        print()
        if env_ok:
            print("✅ Environment testing passed!")
            print("All essential dependencies are available.")
            print()
            return True
        else:
            print("❌ Environment testing failed!")
            print()
            print("Missing dependencies:")
            for dep in missing_deps:
                print(f"  • {dep}")
            print()
            print("📖 For setup instructions, please see:")
            print("   README.md - General setup guide")
            print("   reproduce/reproduce_environment_texlive.sh - LaTeX setup")
            print("   reproduce/reproduce_environment.sh - Python/Conda setup")
            print()
            print("You can still run specific components if their dependencies are met:")
            print("   ./reproduce.py --docs      # Requires LaTeX tools")
            print("   ./reproduce.py --docs subfiles  # Requires LaTeX tools")
            print("   ./reproduce.py --comp min  # Requires Python environment")
            print("   ./reproduce.py --all       # Requires Python environment")
            print()
            return False
    
    def reproduce_documents(self, scope: str = "main") -> int:
        """Reproduce LaTeX documents."""
        print("=" * 40)
        print("Reproducing LaTeX Documents...")
        print("=" * 40)
        print()
        
        doc_script = self.reproduce_dir / "reproduce_documents.sh"
        if not doc_script.exists():
            print(f"ERROR: {doc_script} not found")
            print("Please run from the project root directory")
            return 1
        
        args = ["bash", str(doc_script), "--quick", "--verbose", "--scope", scope]
        
        if self.dry_run:
            args.append("--dry-run")
        
        try:
            result = subprocess.run(args, cwd=self.project_root)
            return result.returncode
        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
            return 130
    
    def reproduce_subfiles(self) -> int:
        """Compile all subfiles."""
        print("=" * 40)
        print("Compiling All Subfiles...")
        print("=" * 40)
        print()
        
        subfiles_dir = self.project_root / "Subfiles"
        if not subfiles_dir.exists():
            print("ERROR: Subfiles/ directory not found")
            return 1
        
        # Find all .tex files in Subfiles directory
        tex_files = sorted(subfiles_dir.glob("*.tex"))
        tex_files = [f for f in tex_files if not f.name.startswith(".")]
        
        if not tex_files:
            print("No .tex files found in Subfiles/ directory")
            return 0
        
        print(f"Found {len(tex_files)} subfile(s) to compile:")
        for f in tex_files:
            print(f"  • {f.name}")
        print()
        
        failed_files = []
        
        for i, tex_file in enumerate(tex_files, 1):
            print(f"[{i}/{len(tex_files)}] Compiling {tex_file.name}...")
            
            if self.dry_run:
                print(f"  Would run: latexmk -pdf -cd {tex_file}")
                continue
            
            try:
                result = subprocess.run(
                    ["latexmk", "-pdf", "-cd", str(tex_file)],
                    cwd=self.project_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                
                if result.returncode == 0:
                    print(f"  ✅ {tex_file.name} compiled successfully")
                else:
                    print(f"  ❌ {tex_file.name} failed to compile")
                    failed_files.append(tex_file.name)
            except KeyboardInterrupt:
                print("\n\nInterrupted by user.")
                return 130
        
        print()
        if failed_files:
            print(f"❌ {len(failed_files)} file(s) failed to compile:")
            for f in failed_files:
                print(f"  • {f}")
            return 1
        else:
            print(f"✅ All {len(tex_files)} subfile(s) compiled successfully!")
            return 0
    
    def test_environment_comprehensive(self, scope: str = "both") -> int:
        """Test TeX Live and/or computational environments.
        
        Args:
            scope: Which environment(s) to test - 'texlive', 'comp', 'comp_uv', or 'both' (default)
        """
        print("=" * 40)
        print("Testing HAFiscal Environment Setup")
        print("=" * 40)
        print()
        
        if scope == "texlive":
            print("Testing: TeX Live environment only")
        elif scope == "comp":
            print("Testing: Computational environment only")
        else:  # both
            print("Testing: Both TeX Live and computational environments")
        print()
        
        overall_status = 0
        
        # Test TeX Live environment (if requested)
        if scope in ["texlive", "both"]:
            print("━" * 40)
            print("1️⃣  Testing TeX Live Environment")
            print("━" * 40)
            print()
        
        texlive_script = self.reproduce_dir / "reproduce_environment_texlive.sh"
        if texlive_script.exists():
            try:
                result = subprocess.run(
                    ["bash", str(texlive_script)],
                    cwd=self.project_root,
                    timeout=120
                )
                print()
                if result.returncode == 0:
                    print("✅ TeX Live environment: PASSED")
                else:
                    print("❌ TeX Live environment: FAILED")
                    overall_status = 1
            except subprocess.TimeoutExpired:
                print("❌ TeX Live test timed out")
                overall_status = 1
        else:
            print("⚠️  TeX Live test script not found")
            overall_status = 1
            print()
        
        # Test Computational environment (if requested)
        if scope in ["comp", "both"]:
            if scope == "both":
                print("━" * 40)
                print("2️⃣  Testing Computational Environment")
                print("━" * 40)
            else:
                print("━" * 40)
                print("Testing Computational Environment")
                print("━" * 40)
            print()
            
            # Check for UV environment first
            venv_path = self.project_root / ".venv"
            if venv_path.exists() and (self.project_root / "pyproject.toml").exists():
                print("🔍 Checking UV environment (.venv)...")
                # Set flag for benchmark filename generation
                self.envt_using_uv = True
                venv_python = venv_path / "bin" / "python"
                if sys.platform == "win32":
                    venv_python = venv_path / "Scripts" / "python.exe"
                
                if venv_python.exists():
                    print("  ✅ UV environment exists")
                    
                    # Test key packages
                    try:
                        result = subprocess.run(
                            [str(venv_python), "-c",
                             "import numpy, scipy, pandas, matplotlib; print('✅ Key packages available')"],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0:
                            print("  " + result.stdout.strip())
                        else:
                            print("  ⚠️  Some packages may be missing")
                            overall_status = 1
                    except Exception:
                        print("  ⚠️  Error checking packages")
                        overall_status = 1
                    
                    # Check for HARK
                    try:
                        result = subprocess.run(
                            [str(venv_python), "-c",
                             "import HARK; print(f'  ✅ HARK {HARK.__version__} installed')"],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0:
                            print(result.stdout.strip())
                        else:
                            print("  ⚠️  HARK (econ-ark) not installed")
                            print("     Run: uv sync --all-groups")
                            overall_status = 1
                    except Exception:
                        print("  ⚠️  HARK (econ-ark) not installed")
                        overall_status = 1
                else:
                    print("  ❌ UV environment incomplete")
                    print("     Run: uv sync --all-groups")
                    overall_status = 1
            # Check for conda environment
            elif os.environ.get('CONDA_DEFAULT_ENV') or shutil.which('conda'):
                print("🔍 Checking Conda environment...")
                
                env_script = self.reproduce_dir / "reproduce_environment.sh"
                if env_script.exists():
                    try:
                        result = subprocess.run(
                            ["bash", str(env_script)],
                            cwd=self.project_root,
                            timeout=60
                        )
                        if result.returncode == 0:
                            print("  ✅ Conda environment: PASSED")
                        else:
                            print("  ❌ Conda environment: FAILED")
                            overall_status = 1
                    except subprocess.TimeoutExpired:
                        print("  ❌ Conda test timed out")
                        overall_status = 1
                else:
                    print("  ⚠️  Conda test script not found")
                    overall_status = 1
            else:
                print("❌ No Python environment detected")
                print()
                print("Please set up an environment:")
                print("  Option 1 (Recommended): ./reproduce/reproduce_environment_comp_uv.sh")
                print("  Option 2 (Traditional):  conda env create -f environment.yml")
                overall_status = 1
                print()
        
        # Summary
        print("━" * 40)
        print("Environment Test Summary")
        print("━" * 40)
        print()
        
        if overall_status == 0:
            print("✅ All environment tests PASSED")
            print()
            print("Your system is ready to reproduce HAFiscal results!")
            print()
            print("Next steps:")
            print("  python3 reproduce.py --docs      # Compile documents")
            print("  python3 reproduce.py --comp min  # Run minimal computation")
        else:
            print("❌ Some environment tests FAILED")
            print()
            print("Please fix the issues above before proceeding.")
            print()
            print("For help, see:")
            print("  README.md - Setup instructions")
            print("  README/INSTALLATION.md - Platform-specific guides")
            print("  README/TROUBLESHOOTING.md - Common issues")
        print()
        
        return overall_status
    
    def reproduce_minimal_results(self) -> int:
        """Reproduce minimal computational results."""
        print("=" * 40)
        print("Reproducing Minimal Computational Results...")
        print("=" * 40)
        print()
        
        # Check for required .obj files
        ha_models_dir = self.project_root / "Code" / "HA-Models"
        required_files = [
            ha_models_dir / "FromPandemicCode" / "HA_Fiscal_Jacs.obj",
            ha_models_dir / "FromPandemicCode" / "HA_Fiscal_Jacs_UI_extend_real.obj"
        ]
        
        missing_files = [f for f in required_files if not f.exists()]
        
        if missing_files:
            print("❌ ERROR: Required Files Missing")
            print("=" * 40)
            print()
            print("The minimal computational reproduction requires pre-computed object files")
            print("from the full computational reproduction. The following files are missing:")
            print()
            for f in missing_files:
                rel_path = f.relative_to(self.project_root)
                print(f"  • {rel_path}")
            print()
            print("To generate these files, you must first run the full computational reproduction:")
            print()
            print("  ./reproduce.sh --comp full")
            print()
            print("or:")
            print()
            print("  python3 reproduce.py --comp full")
            print()
            print("Note: This will take 4-5 days on a high-end 2025 laptop to complete.")
            print()
            print("The minimal reproduction (--comp min) is designed to quickly verify")
            print("results using pre-computed Jacobians from the full run.")
            print()
            return 1
        
        print("✅ All required .obj files found. Proceeding with minimal reproduction...")
        print()
        
        comp_script = self.reproduce_dir / "reproduce_computed_min.sh"
        if not comp_script.exists():
            print(f"ERROR: {comp_script} not found")
            return 1
        
        print("⚠️  This will take approximately 1 hour.")
        print()
        
        if self.dry_run:
            print(f"Would run: bash {comp_script}")
            return 0
        
        try:
            result = subprocess.run(["bash", str(comp_script)], cwd=self.project_root)
            return result.returncode
        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
            return 130
    
    def reproduce_all_computational_results(self) -> int:
        """Reproduce all computational results."""
        print("=" * 40)
        print("Reproducing ALL Computational Results...")
        print("=" * 40)
        print()
        print("⚠️  WARNING: This may take 4-5 DAYS on a high-end 2025 laptop!")
        print("   This will reproduce ALL computational results from the paper,")
        print("   including robustness checks and alternative specifications.")
        print()
        
        if not self.dry_run:
            confirm = input("Are you sure you want to continue? (yes/no): ").strip().lower()
            if confirm != "yes":
                print("Cancelled.")
                return 0
            print()
        
        comp_script = self.reproduce_dir / "reproduce_computed.sh"
        if not comp_script.exists():
            print(f"ERROR: {comp_script} not found")
            return 1
        
        if self.dry_run:
            print(f"Would run: bash {comp_script}")
            return 0
        
        try:
            result = subprocess.run(["bash", str(comp_script)], cwd=self.project_root)
            return result.returncode
        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
            return 130
    
    def reproduce_all_results(self) -> int:
        """Reproduce everything: all documents + all computational results."""
        print("=" * 40)
        print("Reproducing EVERYTHING...")
        print("=" * 40)
        print()
        print("This will:")
        print("  1. Compile all LaTeX documents")
        print("  2. Reproduce all computational results")
        print()
        print("⚠️  Estimated time: 4-5 DAYS on a high-end 2025 laptop")
        print()
        
        if not self.dry_run:
            confirm = input("Are you sure you want to continue? (yes/no): ").strip().lower()
            if confirm != "yes":
                print("Cancelled.")
                return 0
            print()
        
        # Run computational results first
        print("Step 1/2: Running computational results...")
        print()
        ret = self.reproduce_all_computational_results()
        if ret != 0:
            print()
            print("❌ Computational results failed.")
            return ret
        
        print()
        print("Step 2/2: Compiling documents...")
        print()
        ret = self.reproduce_documents(scope="all")
        if ret != 0:
            print()
            print("❌ Document compilation failed.")
            return ret
        
        print()
        print("=" * 40)
        print("✅ All reproduction steps completed!")
        print("=" * 40)
        return 0
    
    def is_interactive(self) -> bool:
        """Check if running in interactive mode (TTY)."""
        return sys.stdin.isatty() and sys.stdout.isatty()
    
    def _start_benchmark(self, action: str, scope: str = None):
        """Start benchmark timing."""
        if self.benchmark_enabled:
            self.benchmark_start_time = time.time()
            self.benchmark_start_iso = datetime.now(timezone.utc).isoformat()
            self.action = action
            self.action_scope = scope
    
    def _save_benchmark(self):
        """Save benchmark data to JSON file."""
        if not self.benchmark_enabled or self.benchmark_start_time is None:
            return
        
        # Only save benchmarks for successful runs (exit status 0)
        if self.exit_status != 0:
            return
        
        try:
            # Calculate duration
            end_time = time.time()
            end_iso = datetime.now(timezone.utc).isoformat()
            duration = int(end_time - self.benchmark_start_time)
            
            # Build filename: [kind]_[vers]_[opts]_YYYYMMDD-HHMM_[duration]s.json
            kind = self.action or "unknown"
            vers = self.action_scope or "unknown"
            
            # If testing comp environment and UV is detected, use comp_uv
            if kind == "envt" and vers == "comp" and self.envt_using_uv:
                vers = "comp_uv"
            
            opts = []
            
            if self.dry_run:
                opts.append("dry-run")
            
            # Build filename with underscores, timestamp, and 5-digit zero-padded duration
            filename = f"{kind}_{vers}"
            if opts:
                filename += f"_{'_'.join(opts)}"
            
            # Add timestamp (YYYYMMDD-HHMM format)
            timestamp = datetime.datetime.fromisoformat(self.benchmark_start_iso).strftime("%Y%m%d-%H%M")
            filename += f"_{timestamp}"
            
            # Format duration as 5-digit zero-padded with 's' suffix
            duration_str = f"{duration:05d}"
            filename += f"_{duration_str}s.json"
            
            # Ensure benchmarks directory exists
            benchmark_dir = self.project_root / "reproduce" / "benchmarks" / "results"
            benchmark_dir.mkdir(parents=True, exist_ok=True)
            
            # Capture system info
            capture_script = self.project_root / "reproduce" / "benchmarks" / "capture_system_info.py"
            if capture_script.exists():
                result = subprocess.run(
                    [sys.executable, str(capture_script), "--pretty"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    system_info = json.loads(result.stdout)
                    
                    # Build benchmark data
                    benchmark_data = {
                        "benchmark_version": "1.0.0",
                        "benchmark_id": f"{kind}-{vers}_{timestamp}",
                        "timestamp": self.benchmark_start_iso,
                        "timestamp_end": end_iso,
                        "reproduction_mode": kind,
                        "reproduction_scope": vers,
                        "exit_status": self.exit_status,
                        "duration_seconds": duration,
                        **system_info,
                        "metadata": {
                            **system_info.get("metadata", {}),
                            "dry_run": self.dry_run,
                            "ci": os.environ.get('CI', 'false').lower() == 'true'
                        }
                    }
                    
                    # Save to file
                    output_file = benchmark_dir / filename
                    with open(output_file, 'w') as f:
                        json.dump(benchmark_data, f, indent=2)
                    
                    # Create/update latest symlink
                    latest_link = benchmark_dir / "latest.json"
                    if latest_link.exists() or latest_link.is_symlink():
                        latest_link.unlink()
                    latest_link.symlink_to(filename)
                    
                    # Print summary
                    hours = duration // 3600
                    minutes = (duration % 3600) // 60
                    seconds = duration % 60
                    print()
                    print(f"📊 Benchmark saved: reproduce/benchmarks/results/{filename}")
                    print(f"   Duration: {hours:d}:{minutes:02d}:{seconds:02d} ({duration} seconds)")
        except Exception as e:
            # Silently fail - don't interrupt the main workflow
            pass
    
    def run(self, args: argparse.Namespace) -> int:
        """Main execution logic."""
        # Handle help
        if args.help:
            self.print_help()
            return 0
        
        # Set flags from args
        if args.dry_run:
            self.dry_run = True
            if args.action not in ['docs', None]:
                print("⚠️  Dry-run mode is only supported for --docs")
                print("   Other actions will execute normally.")
                print()
        
        # Set UV flag if explicitly requested via comp_uv
        if hasattr(args, 'force_uv') and args.force_uv:
            self.envt_using_uv = True
        
        # Handle explicit actions
        if args.action == 'envt':
            ret = self.test_environment_comprehensive(scope=args.envt_scope)
            self.exit_status = ret
            return ret
        
        elif args.action == 'docs':
            self._start_benchmark('docs', args.docs_scope)
            if self.dry_run:
                print("=" * 40)
                print("🔍 DRY RUN MODE: Documents")
                print("=" * 40)
                print("The following commands would be executed:")
                print()
            ret = self.reproduce_documents(scope=args.docs_scope)
            self.exit_status = ret
            return ret
        
        elif args.action == 'comp':
            scope = args.comp_scope
            self._start_benchmark('comp', scope)
            if scope == 'min':
                ret = self.reproduce_minimal_results()
            elif scope == 'full':
                ret = self.reproduce_all_computational_results()
            else:
                print(f"Unknown computational scope: {scope}")
                ret = 1
            self.exit_status = ret
            return ret
        
        elif args.action == 'all':
            self._start_benchmark('all', 'full')
            ret = self.reproduce_all_results()
            self.exit_status = ret
            return ret
        
        elif args.action == 'interactive':
            ret = self.run_interactive_menu()
            self.exit_status = ret
            return ret
        
        # No explicit action specified
        # Test environment first
        if not self.test_environment():
            # Environment test failed, but continue if user explicitly wants to
            pass
        
        # Check for REPRODUCE_TARGETS environment variable
        targets = os.environ.get('REPRODUCE_TARGETS', '').strip()
        if targets:
            return self.process_reproduce_targets(targets)
        
        # Decide between interactive or automatic mode
        if self.is_interactive():
            return self.run_interactive_menu()
        else:
            print("Running in non-interactive mode.")
            print("Use --help to see available options.")
            return 0
    
    def process_reproduce_targets(self, targets: str) -> int:
        """Process REPRODUCE_TARGETS environment variable."""
        print(f"Processing REPRODUCE_TARGETS: {targets}")
        print()
        
        executed_targets = []
        
        for target in targets.split(','):
            target = target.strip().lower()
            
            if target == 'docs':
                print("Target: docs")
                ret = self.reproduce_documents()
                if ret != 0:
                    return ret
                executed_targets.append(target)
            
            elif target == 'comp':
                print("Target: comp")
                ret = self.reproduce_minimal_results()
                if ret != 0:
                    return ret
                executed_targets.append(target)
            
            elif target == 'all':
                print("Target: all")
                ret = self.reproduce_all_results()
                if ret != 0:
                    return ret
                executed_targets.append(target)
            
            else:
                print(f"⚠️  Unknown target: {target}")
        
        print()
        if executed_targets:
            print(f"Completed targets: {', '.join(executed_targets)}")
        else:
            print("No targets were executed")
        
        return 0
    
    def print_help(self):
        """Print detailed help message."""
        help_text = """
HAFiscal Reproduction Script (Python Version)

This script provides multiple reproduction options and includes environment testing.

USAGE:
    python3 reproduce.py [OPTION]
    ./reproduce.py [OPTION]  (if executable)

OPTIONS:
    --help, -h          Show this help message
    --envt, -e [SCOPE]  Test environment setup (SCOPE: texlive|comp_uv|both, default: both)
                         texlive: Test TeX Live environment only
                         comp_uv: Test computational (UV) environment only
                         both: Test both environments
    --docs, -d [SCOPE]  Reproduce LaTeX documents (SCOPE: main|all|figures|tables|subfiles, default: main)
                         main: only repo root files (HAFiscal.tex, HAFiscal-Slides.tex)
                         all: root files + Figures/ + Tables/ + Subfiles/
                         figures: root files + Figures/
                         tables: root files + Tables/
                         subfiles: root files + Subfiles/
    --comp, -c [SCOPE]  Reproduce computational results (SCOPE: min|full, default: min)
                         min: minimal computational results (~1 hour)
                         full: all computational results needed for the printed document (may take 4-5 days on a high-end 2025 laptop)
    --all, -a           Reproduce everything: all documents + all computational results
    --interactive, -i   Show interactive menu (default when run from terminal)
    --dry-run           Show commands that would be executed (only with --docs)

ENVIRONMENT TESTING:
    When run without arguments, this script first checks your environment setup.
    If environment testing fails, see README.md for setup instructions.

ENVIRONMENT VARIABLES:
    REPRODUCE_TARGETS   Comma-separated list of targets to reproduce (non-interactive mode)
                       Valid values: docs, comp, all
                       Examples:
                         REPRODUCE_TARGETS=docs
                         REPRODUCE_TARGETS=comp,docs
                         REPRODUCE_TARGETS=all
    
    BENCHMARK          Enable/disable automatic benchmarking (default: true)
                       Examples:
                         BENCHMARK=false python3 reproduce.py --docs    # Disable benchmarking
                         BENCHMARK=true python3 reproduce.py --comp min # Enable (default)

EXAMPLES:
    python3 reproduce.py                      # Test environment, then run (interactive/auto)
    python3 reproduce.py --envt               # Test both TeX Live and computational environments
    python3 reproduce.py --envt texlive       # Test TeX Live environment only
    python3 reproduce.py --envt comp_uv       # Test computational (UV) environment only
    python3 reproduce.py --docs               # Compile repo root documents (default: main scope)
    python3 reproduce.py --docs main          # Compile only repo root documents
    python3 reproduce.py --docs all           # Compile root + Figures/ + Tables/ + Subfiles/
    python3 reproduce.py --docs figures       # Compile repo root + Figures/
    python3 reproduce.py --docs tables        # Compile repo root + Tables/
    python3 reproduce.py --docs subfiles      # Compile repo root + Subfiles/
    python3 reproduce.py --docs --dry-run     # Show document compilation commands
    python3 reproduce.py --docs main --dry-run # Show commands for root documents only
    python3 reproduce.py --comp min           # Minimal computational results (~1 hour)
    python3 reproduce.py --comp full          # All computational results for printed document (4-5 days on a high-end 2025 laptop)
    python3 reproduce.py --all                # Everything: all documents + all computational results

    # Non-interactive examples:
    REPRODUCE_TARGETS=docs python3 reproduce.py    # Documents only
    REPRODUCE_TARGETS=comp python3 reproduce.py    # Core computational results
    REPRODUCE_TARGETS=comp,docs python3 reproduce.py # Core computational results + documents
    echo | REPRODUCE_TARGETS=all python3 reproduce.py # Force non-interactive, everything

CROSS-PLATFORM COMPATIBILITY:
    This Python version works on Windows, macOS, and Linux.
    Requires: Python 3.7+, bash (for calling underlying scripts)
    On Windows: Git Bash or WSL recommended for full functionality
"""
        print(help_text)


def main():
    """Main entry point."""
    # Ensure we're running in the UV environment
    ensure_uv_environment()
    
    parser = argparse.ArgumentParser(
        description="HAFiscal Reproduction Script (Python Version)",
        add_help=False,  # We'll handle help ourselves
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--help', '-h', action='store_true',
                       help='Show help message')
    parser.add_argument('--envt', '-e', dest='action', action='store_const', const='envt',
                       help='Test environment setup')
    parser.add_argument('--docs', '-d', dest='action', action='store_const', const='docs',
                       help='Reproduce LaTeX documents')
    parser.add_argument('--comp', '-c', dest='action', action='store_const', const='comp',
                       help='Reproduce computational results')
    parser.add_argument('--all', '-a', dest='action', action='store_const', const='all',
                       help='Reproduce everything')
    parser.add_argument('--interactive', '-i', dest='action', action='store_const', const='interactive',
                       help='Show interactive menu')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show commands that would be executed (docs only)')
    
    # Parse known args to handle scope parameters
    args, remaining = parser.parse_known_args()
    
    # Handle scope parameters
    args.docs_scope = 'main'
    args.comp_scope = 'min'
    args.envt_scope = 'both'
    args.force_uv = False  # Flag to force UV environment in benchmark
    
    if args.action == 'envt' and remaining:
        if remaining[0] in ['texlive', 'comp', 'comp_uv', 'both']:
            args.envt_scope = remaining[0]
            # Map comp_uv to comp for the test, but set UV flag
            if remaining[0] == 'comp_uv':
                args.envt_scope = 'comp'
                args.force_uv = True
            remaining = remaining[1:]
    
    if args.action == 'docs' and remaining:
        if remaining[0] in ['main', 'all', 'figures', 'tables', 'subfiles']:
            args.docs_scope = remaining[0]
            remaining = remaining[1:]
    
    if args.action == 'comp' and remaining:
        if remaining[0] in ['min', 'full']:
            args.comp_scope = remaining[0]
            remaining = remaining[1:]
    
    # Check for unexpected arguments
    if remaining:
        print(f"Unknown arguments: {' '.join(remaining)}")
        print("Run with --help for available options")
        return 1
    
    # Create and run script
    script = ReproductionScript()
    try:
        return script.run(args)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        return 130


if __name__ == '__main__':
    sys.exit(main())
