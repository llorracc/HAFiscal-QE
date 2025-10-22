#!/usr/bin/env python3
"""
HAFiscal Reproduction Script (Python Version)

Cross-platform reproduction script for HAFiscal project.
Mirrors the functionality of reproduce.sh with identical CLI interface.
"""

import argparse
import os
import subprocess
import sys
import shutil
from pathlib import Path
from typing import List, Optional, Tuple


class ReproductionScript:
    """Main reproduction script controller."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.resolve()
        self.reproduce_dir = self.project_root / "reproduce"
        self.dry_run = False
        
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
        print("   - Compiles all .tex files in Subfiles/ directory")
        print("   - Estimated time: A few minutes")
        print()
        print("3) Minimal Computational Results")
        print("   - Reproduces a subset of computational results")
        print("   - Estimated time: ~1 hour")
        print("   - Good for testing and quick verification")
        print()
        print("4) Core Computational Results [NOT YET IMPLEMENTED]")
        print("   - Would reproduce central computational results")
        print("   - Estimated time: ~4-6 hours (when implemented)")
        print("   - Currently defaults to minimal computational results")
        print()
        print("5) All Computational Results")
        print("   - Reproduces all computational results from the paper")
        print("   - ⚠️  WARNING: This may take 1-2 DAYS to complete")
        print("   - Requires significant computational resources")
        print()
        print("6) Everything")
        print("   - All LaTeX documents + All computational results")
        print("   - Estimated time: 1-2 days")
        print()
        print("0) Exit")
        print()
        
        try:
            choice = input("Enter your choice (0-6): ").strip()
            return choice
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            return None
    
    def run_interactive_menu(self) -> int:
        """Execute interactive menu mode."""
        while True:
            choice = self.show_interactive_menu()
            
            if choice is None or choice == "0":
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
                    print("⚠️  Core computational results not yet implemented.")
                    print("   Defaulting to minimal computational results...")
                    print()
                    return self.reproduce_minimal_results()
                elif choice == "5":
                    return self.reproduce_all_computational_results()
                elif choice == "6":
                    return self.reproduce_all_results()
                else:
                    print(f"Invalid choice: {choice}")
                    print("Please enter a number between 0 and 6.")
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
    
    def reproduce_minimal_results(self) -> int:
        """Reproduce minimal computational results."""
        print("=" * 40)
        print("Reproducing Minimal Computational Results...")
        print("=" * 40)
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
    
    def reproduce_core_results(self) -> int:
        """Reproduce core computational results (not yet implemented)."""
        print("⚠️  Core computational results not yet implemented.")
        print("   Defaulting to minimal computational results...")
        print()
        return self.reproduce_minimal_results()
    
    def reproduce_all_computational_results(self) -> int:
        """Reproduce all computational results."""
        print("=" * 40)
        print("Reproducing ALL Computational Results...")
        print("=" * 40)
        print()
        print("⚠️  WARNING: This may take 1-2 DAYS to complete!")
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
        print("⚠️  Estimated time: 1-2 DAYS")
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
    
    def run(self, args: argparse.Namespace) -> int:
        """Main execution logic."""
        # Handle help
        if args.help:
            self.print_help()
            return 0
        
        # Set dry-run mode
        if args.dry_run:
            self.dry_run = True
            if args.action not in ['docs', None]:
                print("⚠️  Dry-run mode is only supported for --docs")
                print("   Other actions will execute normally.")
                print()
        
        # Handle explicit actions
        if args.action == 'docs':
            if self.dry_run:
                print("=" * 40)
                print("🔍 DRY RUN MODE: Documents")
                print("=" * 40)
                print("The following commands would be executed:")
                print()
            return self.reproduce_documents(scope=args.docs_scope)
        
        elif args.action == 'comp':
            scope = args.comp_scope
            if scope == 'min':
                return self.reproduce_minimal_results()
            elif scope == 'core':
                return self.reproduce_core_results()
            elif scope == 'all':
                return self.reproduce_all_computational_results()
            else:
                print(f"Unknown computational scope: {scope}")
                return 1
        
        elif args.action == 'all':
            return self.reproduce_all_results()
        
        elif args.action == 'interactive':
            return self.run_interactive_menu()
        
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
                ret = self.reproduce_core_results()
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
    --docs, -d [SCOPE]  Reproduce LaTeX documents (SCOPE: main|all|figures|tables|subfiles, default: main)
                         main: only repo root files (HAFiscal-QE.tex, HAFiscal-Slides.tex)
                         all: root files + Figures/ + Tables/ + Subfiles/
                         figures: root files + Figures/
                         tables: root files + Tables/
                         subfiles: root files + Subfiles/
    --comp, -c [SCOPE]  Reproduce computational results (SCOPE: min|core|all, default: core)
                         min: minimal computational results (~1 hour)
                         core: core computational results (~4-6 hours) [NOT YET IMPLEMENTED - defaults to min]
                         all: all computational results (may take 1-2 days)
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

EXAMPLES:
    python3 reproduce.py                      # Test environment, then run (interactive/auto)
    python3 reproduce.py --docs               # Compile repo root documents (default: main scope)
    python3 reproduce.py --docs main          # Compile only repo root documents
    python3 reproduce.py --docs all           # Compile root + Figures/ + Tables/ + Subfiles/
    python3 reproduce.py --docs figures       # Compile repo root + Figures/
    python3 reproduce.py --docs tables        # Compile repo root + Tables/
    python3 reproduce.py --docs subfiles      # Compile repo root + Subfiles/
    python3 reproduce.py --docs --dry-run     # Show document compilation commands
    python3 reproduce.py --docs main --dry-run # Show commands for root documents only
    python3 reproduce.py --comp min           # Minimal computational results (~1 hour)
    python3 reproduce.py --comp core          # Core computational results (~4-6 hours) [defaults to min]
    python3 reproduce.py --comp all           # All computational results (1-2 days)
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
    parser = argparse.ArgumentParser(
        description="HAFiscal Reproduction Script (Python Version)",
        add_help=False,  # We'll handle help ourselves
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--help', '-h', action='store_true',
                       help='Show help message')
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
    args.comp_scope = 'core'
    
    if args.action == 'docs' and remaining:
        if remaining[0] in ['main', 'all', 'figures', 'tables', 'subfiles']:
            args.docs_scope = remaining[0]
            remaining = remaining[1:]
    
    if args.action == 'comp' and remaining:
        if remaining[0] in ['min', 'core', 'all']:
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
