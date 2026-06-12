#!/usr/bin/env python3
"""
Capture a baseline snapshot of HAFiscal quantitative results.

This script collects all quantitative outputs from the HAFiscal codebase
and saves them in a structured format for later comparison.

IMPORTANT: The validation framework focuses on NUMERICAL values, not file hashes.
- Estimation parameters (splurge, beta, nabla) are the primary metrics
- HANK multipliers are secondary metrics
- Figure hashes are captured for reference only (too brittle for validation)

Usage:
    ./capture_snapshot.py --output snapshots/baseline_20260124-1600
    ./capture_snapshot.py --output snapshots/baseline_$(date +%Y%m%d-%H%M) --notes "Pre-upgrade"
"""

import argparse
import json
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
import subprocess
import re

# Project paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CODE_DIR = PROJECT_ROOT / "Code" / "HA-Models"


def get_git_info():
    """Get current git commit and branch."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], 
            cwd=PROJECT_ROOT, 
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL
        ).decode().strip()
        
        dirty = subprocess.call(
            ["git", "diff", "--quiet"], 
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL
        ) != 0
        
        return {"commit": commit, "branch": branch, "dirty": dirty}
    except Exception as e:
        return {"commit": "unknown", "branch": "unknown", "dirty": True, "error": str(e)}


def get_hark_version():
    """Get installed HARK version."""
    try:
        import HARK
        return HARK.__version__
    except Exception as e:
        return f"unknown ({e})"


def parse_result_file(filepath):
    """Parse a Python dict-like result file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read().strip()
        # Safe eval for simple dict literals
        return eval(content)
    except Exception as e:
        return {"error": str(e), "raw": content if 'content' in dir() else "file not found"}


def parse_all_results_file(filepath):
    """Parse the detailed AllResults file."""
    results = {}
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract key metrics using regex
        patterns = {
            "R": r"R = ([\d.]+)",
            "CRRA": r"CRRA = ([\d.]+)",
            "IncUnemp": r"IncUnemp = ([\d.]+)",
            "IncUnempNoBenefits": r"IncUnempNoBenefits = ([\d.]+)",
            "Splurge": r"Splurge = ([\d.]+)",
        }
        
        for name, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                results[name] = float(match.group(1))
        
        # Extract education group results
        ed_pattern = r"Education group = ([\d.]+): beta = ([\d.]+), nabla = ([\d.]+), GICfactor = ([\d.]+)"
        for match in re.finditer(ed_pattern, content):
            ed = int(float(match.group(1)))
            results[f"ed{ed}_beta"] = float(match.group(2))
            results[f"ed{ed}_nabla"] = float(match.group(3))
            results[f"ed{ed}_GICfactor"] = float(match.group(4))
        
        # Extract population metrics
        impc_pattern = r"IMPCs over time = \[([\d., ]+)\]"
        match = re.search(impc_pattern, content)
        if match:
            results["IMPCs"] = [float(x) for x in match.group(1).split(", ")]
        
        return results
    except Exception as e:
        return {"error": str(e)}


def parse_hank_output(log_content):
    """Parse HANK multiplier output from log content."""
    multipliers = {}
    patterns = {
        "UI_active": r"multiplier out of 2Q UI extension \(active taylor rule\) ([\d.-]+)",
        "UI_fixed_nominal": r"multiplier out of 2Q UI extension \(fixed nominal rate\) ([\d.-]+)",
        "UI_fixed_real": r"multiplier out of 2Q UI extension \(fixed real rate\) ([\d.-]+)",
        "transfer_active": r"multiplier out of transfers \(active taylor rule\) ([\d.-]+)",
        "transfer_fixed_nominal": r"multiplier out of transfers \(fixed nominal rate\) ([\d.-]+)",
        "transfer_fixed_real": r"multiplier out of transfers \(fixed real rate\) ([\d.-]+)",
        "taxcut": r"multiplier out of tax cut ([\d.-]+)",
        "taxcut_fixed_real": r"multiplier out of tax cut \(fixed real rate\) ([\d.-]+)",
        "taxcut_fixed_nominal": r"multiplier out of tax cut \(fixed nominal rate\) ([\d.-]+)",
        "phillips_slope": r"slope of phillips curve ([\d.]+)",
    }
    
    for name, pattern in patterns.items():
        match = re.search(pattern, log_content)
        if match:
            multipliers[name] = float(match.group(1))
    
    return multipliers


def hash_file(filepath):
    """Calculate SHA256 hash of a file (for reference, not validation)."""
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        return f"error: {e}"


def extract_tex_table_values(tex_file):
    """
    Extract numerical values from a .tex table file.
    
    This parses the actual numbers from LaTeX tables, which is more
    meaningful than comparing file hashes.
    """
    values = {}
    try:
        with open(tex_file, 'r') as f:
            content = f.read()
        
        # Extract numbers from the table (numbers with optional sign, decimal)
        # This captures most common numerical formats in LaTeX tables
        number_pattern = r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?'
        all_numbers = re.findall(number_pattern, content)
        
        # Filter out likely non-data numbers (like column specs, years, etc.)
        # Keep only numbers that look like results (have decimals or are reasonable values)
        data_numbers = []
        for num_str in all_numbers:
            try:
                num = float(num_str)
                # Include if it has a decimal or is in typical result range
                if '.' in num_str or abs(num) < 100:
                    data_numbers.append(num)
            except:
                pass
        
        values['numbers'] = data_numbers
        values['count'] = len(data_numbers)
        
        # Also try to extract labeled values (like "MPC = 0.25")
        labeled_pattern = r'(\w+)\s*[=:]\s*([-+]?\d*\.?\d+)'
        for match in re.finditer(labeled_pattern, content):
            values[match.group(1)] = float(match.group(2))
        
    except Exception as e:
        values['error'] = str(e)
    
    return values


def collect_tex_tables(base_dir):
    """Collect numerical values from all .tex table files."""
    tables = {}
    
    for tex_path in base_dir.rglob("*.tex"):
        # Skip main document files, focus on generated tables
        rel_path = str(tex_path.relative_to(base_dir))
        if 'Table' in rel_path or 'table' in rel_path:
            tables[rel_path] = extract_tex_table_values(tex_path)
    
    return tables


def find_figures(base_dir):
    """
    Find all generated figure files and record metadata.
    
    NOTE: File hashes are captured for informational purposes only.
    They should NOT be used for numerical validation because:
    - Hash changes with any metadata (timestamps, library versions, fonts)
    - Two numerically identical figures can have different hashes
    
    For validation, use numerical outputs from result files instead.
    """
    figures = {}
    extensions = ['.png', '.pdf', '.svg', '.jpg']
    
    for ext in extensions:
        for fig_path in base_dir.rglob(f"*{ext}"):
            rel_path = str(fig_path.relative_to(base_dir))
            figures[rel_path] = {
                "hash": hash_file(fig_path),  # For reference only, not for validation
                "size": fig_path.stat().st_size,
                "mtime": datetime.fromtimestamp(fig_path.stat().st_mtime).isoformat()
            }
    
    return figures


def capture_snapshot(output_dir, notes=""):
    """Capture comprehensive snapshot of current results."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().isoformat()
    
    # Metadata
    metadata = {
        "timestamp": timestamp,
        "hark_version": get_hark_version(),
        "git": get_git_info(),
        "notes": notes,
        "python_version": sys.version,
    }
    
    # Estimation results
    estimation = {}
    result_files = [
        ("Result_AllTarget", CODE_DIR / "Target_AggMPCX_LiquWealth" / "Result_AllTarget.txt"),
        ("Result_AllTarget_Splurge0", CODE_DIR / "Target_AggMPCX_LiquWealth" / "Result_AllTarget_Splurge0.txt"),
    ]
    for name, path in result_files:
        if path.exists():
            estimation[name] = parse_result_file(path)
    
    # Detailed results (expanded for --comp full)
    detailed = {}
    detailed_files = [
        # Main results
        ("AllResults_CRRA_2.0_R_1.01", CODE_DIR / "Results" / "AllResults_CRRA_2.0_R_1.01.txt"),
        ("AllResults_CRRA_2.0_R_1.01_Splurge0", CODE_DIR / "Results" / "AllResults_CRRA_2.0_R_1.01_Splurge0.txt"),
        # Discount factor estimation results
        ("DiscFacEstim_CRRA_2.0_R_1.01", CODE_DIR / "Results" / "DiscFacEstim_CRRA_2.0_R_1.01.txt"),
        ("DiscFacEstim_CRRA_2.0_R_1.01_Splurge0", CODE_DIR / "Results" / "DiscFacEstim_CRRA_2.0_R_1.01_Splurge0.txt"),
    ]
    for name, path in detailed_files:
        if path.exists():
            detailed[name] = parse_all_results_file(path)
    
    # Also capture any .txt result files in Results directory
    results_dir = CODE_DIR / "Results"
    if results_dir.exists():
        for txt_file in results_dir.glob("*.txt"):
            name = txt_file.stem
            if name not in detailed:
                detailed[name] = parse_all_results_file(txt_file)
    
    # HANK multipliers from latest log
    multipliers = {}
    log_dir = PROJECT_ROOT / "reproduce" / "logs"
    if log_dir.exists():
        logs = sorted(log_dir.glob("comp_min_*.log"), reverse=True)
        if logs:
            with open(logs[0], 'r') as f:
                multipliers = parse_hank_output(f.read())
            multipliers["_source_log"] = str(logs[0].name)
    
    # Figure metadata (hashes are for reference only, NOT for validation)
    figures = {}
    figure_dirs = [
        CODE_DIR / "Target_AggMPCX_LiquWealth" / "Figures",
        CODE_DIR / "FromPandemicCode" / "Figures",
    ]
    for fig_dir in figure_dirs:
        if fig_dir.exists():
            figures.update(find_figures(fig_dir))
    
    # LaTeX table values (actual numbers, useful for validation)
    table_values = {}
    table_dirs = [
        CODE_DIR / "Target_AggMPCX_LiquWealth" / "Tables",
        CODE_DIR / "Target_AggMPCX_LiquWealth" / "images",  # Some tables here too
        CODE_DIR / "FromPandemicCode" / "Tables",
        CODE_DIR / "FromPandemicCode" / "Tables" / "CRRA2",  # Step 5 output
        CODE_DIR / "FromPandemicCode" / "Tables" / "CRRA2" / "Splurge",
        CODE_DIR / "FromPandemicCode" / "Tables" / "CRRA2" / "NoSplurge",
        PROJECT_ROOT / "Tables",
    ]
    for table_dir in table_dirs:
        if table_dir.exists():
            table_values.update(collect_tex_tables(table_dir))
    
    # Save all components
    with open(output_path / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    with open(output_path / "estimation_results.json", 'w') as f:
        json.dump(estimation, f, indent=2)
    
    with open(output_path / "detailed_results.json", 'w') as f:
        json.dump(detailed, f, indent=2)
    
    with open(output_path / "multipliers.json", 'w') as f:
        json.dump(multipliers, f, indent=2)
    
    with open(output_path / "figures_metadata.json", 'w') as f:
        json.dump(figures, f, indent=2)
    
    with open(output_path / "table_values.json", 'w') as f:
        json.dump(table_values, f, indent=2)
    
    print(f"✅ Snapshot captured to: {output_path}")
    print(f"   HARK version: {metadata['hark_version']}")
    print(f"   Git commit: {metadata['git']['commit'][:8]}...")
    print(f"   Estimation results: {len(estimation)} files")
    print(f"   Multipliers: {len(multipliers)} values")
    print(f"   Table values: {len(table_values)} tables")
    print(f"   Figures: {len(figures)} files (metadata only, hashes not used for validation)")
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Capture HAFiscal results snapshot")
    parser.add_argument("--output", "-o", required=True, help="Output directory for snapshot")
    parser.add_argument("--notes", "-n", default="", help="Notes about this snapshot")
    
    args = parser.parse_args()
    capture_snapshot(args.output, args.notes)


if __name__ == "__main__":
    main()
