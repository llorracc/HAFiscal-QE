#!/usr/bin/env python3
"""
Interactive Validation System for HAFiscal 0.14.1 vs 0.17.0

This script runs validation steps one at a time, allowing the AI to:
1. Run a single step for both versions
2. Compare results immediately
3. Pause and diagnose if discrepancies are found
4. Continue to the next step if results match

Usage:
    python interactive_validation.py setup      # Set up both validation environments
    python interactive_validation.py step N     # Run step N for both versions and compare
    python interactive_validation.py status     # Show current validation status
    python interactive_validation.py diagnose N # Show detailed comparison for step N
"""

import os
import sys
import subprocess
import json
import numpy as np
from datetime import datetime
from pathlib import Path

# Configuration
BASE_DIR = Path("/home/econ-ark/GitHub/llorracc")
VALIDATION_DIR = BASE_DIR / "HAFiscal-Latest" / "reproduce" / "upgrade-validation"
CLONE_014 = BASE_DIR / "HAFiscal-validation-0.14.1"
CLONE_017 = BASE_DIR / "HAFiscal-validation-0.17.0"
RESULTS_DIR = VALIDATION_DIR / "interactive_results"
MEANINGFUL_DIFF_THRESHOLD = 0.02  # 2% = 0.02 log points

# Define the validation steps (same as before)
VALIDATION_STEPS = [
    {
        "id": 1,
        "name": "Estimation_BetaNablaSplurge",
        "description": "Estimate splurge factor and discount factor distribution",
        "script": "Estimation_BetaNablaSplurge.py",
        "cwd": "Code/HA-Models/Target_AggMPCX_LiquWealth",
        "output_files": ["Result_AllTarget.txt", "Result_AllTarget_Splurge0.txt"],
        "key_values": ["splurge", "beta", "nabla"]
    },
    {
        "id": 2,
        "name": "EstimAggFiscalMAIN", 
        "description": "Main estimation of aggregate fiscal model",
        "script": "EstimAggFiscalMAIN.py",
        "cwd": "Code/HA-Models/FromPandemicCode",
        "output_files": ["Results/DiscFacEstim_CRRA_2.0_R_1.01.txt"],
        "key_values": ["beta_dropout", "beta_highschool", "beta_college"]
    },
    {
        "id": 3,
        "name": "Simulate_Base",
        "description": "Run baseline simulation",
        "script": "Simulate.py",
        "cwd": "Code/HA-Models/FromPandemicCode", 
        "output_files": ["Figures/Reduced_Run/base_results.csv"],
        "key_values": ["AggCons", "AggIncome"]
    },
]


def get_venv_path(clone_dir: Path, version: str) -> Path:
    """Get the virtual environment path for a clone."""
    # Try different possible venv locations
    possible_venvs = [
        clone_dir / ".venv",  # Default uv location
        clone_dir / f".venv-{version.replace('.', '')}",  # Versioned
        clone_dir / "venv",  # Standard name
    ]
    
    for venv in possible_venvs:
        if (venv / "bin" / "python").exists():
            return venv
    
    # Return default location for creation
    return clone_dir / ".venv"


def setup_environments():
    """Ensure both validation clones exist and are properly configured."""
    print("=" * 60)
    print("Setting up validation environments")
    print("=" * 60)
    
    results = {"0.14.1": False, "0.17.0": False}
    
    # Define HARK versions and Python requirements for each clone
    # HARK 0.14.1 requires Python < 3.12
    # HARK 0.17.0 requires Python >= 3.10
    env_configs = {
        "0.14.1": {
            "hark": "econ-ark==0.14.1",
            "python": "3.9"  # Use Python 3.9 for 0.14.1 (< 3.12)
        },
        "0.17.0": {
            "hark": "econ-ark==0.17.0",
            "python": "3.10"  # Use Python 3.10 for 0.17.0 (>= 3.10)
        }
    }
    
    for version, clone_dir in [("0.14.1", CLONE_014), ("0.17.0", CLONE_017)]:
        print(f"\n--- Setting up {version} environment at {clone_dir} ---")
        
        if not clone_dir.exists():
            print(f"  ERROR: Clone directory does not exist: {clone_dir}")
            continue
        
        config = env_configs[version]
        venv_dir = get_venv_path(clone_dir, version)
        print(f"  Virtual env: {venv_dir}")
        
        python_path = venv_dir / "bin" / "python"
        
        # Check if venv exists and has correct Python version
        needs_recreate = False
        if python_path.exists():
            result = subprocess.run(
                [str(python_path), "--version"],
                capture_output=True, text=True
            )
            current_version = result.stdout.strip() if result.returncode == 0 else ""
            if config["python"] not in current_version:
                print(f"  Venv has wrong Python version: {current_version}")
                print(f"  Recreating with Python {config['python']}...")
                needs_recreate = True
                # Remove old venv
                import shutil
                shutil.rmtree(venv_dir, ignore_errors=True)
        
        if not python_path.exists() or needs_recreate:
            print(f"  Creating virtual environment with Python {config['python']}...")
            # Use uv to create venv with specific Python version
            result = subprocess.run(
                ["uv", "venv", str(venv_dir), "--python", config["python"]],
                cwd=clone_dir,
                capture_output=True, text=True
            )
            if result.returncode != 0:
                print(f"  Warning: Could not create venv with Python {config['python']}")
                print(f"  Trying with default Python...")
                subprocess.run(["uv", "venv", str(venv_dir)], cwd=clone_dir, check=True)
            
        # Check if HARK is installed
        result = subprocess.run(
            [str(python_path), "-c", "import HARK; print(HARK.__version__)"],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print(f"  Installing HARK {version} and dependencies...")
            # Install dependencies
            deps = [
                config["hark"],
                "numpy<2.0",  # Ensure numpy 1.x for compatibility
                "scipy", 
                "pandas",
                "matplotlib",
                "sequence-jacobian==1.0.0"
            ]
            
            install_result = subprocess.run(
                ["uv", "pip", "install", "--python", str(python_path)] + deps,
                cwd=clone_dir,
                capture_output=True,
                text=True
            )
            
            if install_result.returncode != 0:
                print(f"  Installation output: {install_result.stderr[:500]}...")
            
            # Re-check HARK installation
            result = subprocess.run(
                [str(python_path), "-c", "import HARK; print(HARK.__version__)"],
                capture_output=True, text=True
            )
        
        if result.returncode == 0:
            print(f"  ✅ HARK version: {result.stdout.strip()}")
            results[version] = True
        else:
            print(f"  ❌ HARK installation failed")
            print(f"     Error: {result.stderr[:300]}...")
    
    # Create results directory
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 60)
    if all(results.values()):
        print("✅ All environments ready!")
    else:
        print("⚠️  Some environments not ready")
    print("=" * 60)
    
    return all(results.values())


def run_step(step_id: int):
    """
    Run a single validation step for both versions and compare results.
    
    Returns:
        0 - Step completed, results match
        1 - Step completed, results DIVERGE (requires diagnosis)
        2 - Step failed to run
    """
    # Find the step
    step = None
    for s in VALIDATION_STEPS:
        if s["id"] == step_id:
            step = s
            break
    
    if step is None:
        print(f"ERROR: Unknown step {step_id}")
        print(f"Available steps: {[s['id'] for s in VALIDATION_STEPS]}")
        return 2
    
    print("=" * 60)
    print(f"STEP {step_id}: {step['name']}")
    print(f"Description: {step['description']}")
    print("=" * 60)
    
    results = {}
    
    for version, clone_dir in [("0.14.1", CLONE_014), ("0.17.0", CLONE_017)]:
        print(f"\n--- Running {version} ---")
        
        venv_dir = get_venv_path(clone_dir, version)
        python_path = venv_dir / "bin" / "python"
        script_path = clone_dir / step["cwd"] / step["script"]
        work_dir = clone_dir / step["cwd"]
        
        if not script_path.exists():
            print(f"  ERROR: Script not found: {script_path}")
            return 2
        
        # Set environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(clone_dir / "Code" / "HA-Models")
        env["MATPLOTLIB_BACKEND"] = "Agg"
        
        print(f"  Running: {step['script']}")
        start_time = datetime.now()
        
        result = subprocess.run(
            [str(python_path), str(script_path)],
            cwd=str(work_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout per step
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"  Completed in {elapsed:.1f}s (exit code: {result.returncode})")
        
        if result.returncode != 0:
            print(f"  STDERR: {result.stderr[:500]}...")
            # Save error for diagnosis
            error_file = RESULTS_DIR / f"step{step_id}_{version}_error.txt"
            with open(error_file, "w") as f:
                f.write(f"Exit code: {result.returncode}\n")
                f.write(f"STDOUT:\n{result.stdout}\n")
                f.write(f"STDERR:\n{result.stderr}\n")
            print(f"  Error details saved to: {error_file}")
            return 2
        
        # Extract results
        results[version] = extract_step_results(clone_dir, step)
        
        # Save raw output
        output_file = RESULTS_DIR / f"step{step_id}_{version}_output.txt"
        with open(output_file, "w") as f:
            f.write(result.stdout)
    
    # Compare results
    print("\n--- Comparing Results ---")
    comparison = compare_results(results["0.14.1"], results["0.17.0"], step)
    
    # Save comparison
    comparison_file = RESULTS_DIR / f"step{step_id}_comparison.json"
    with open(comparison_file, "w") as f:
        json.dump(comparison, f, indent=2, default=str)
    
    if comparison["has_meaningful_difference"]:
        print("\n" + "!" * 60)
        print("!!! MEANINGFUL DIFFERENCE DETECTED !!!")
        print("!" * 60)
        print_comparison_details(comparison)
        
        # Send email notification
        try:
            send_divergence_notification(step_id, step, comparison)
        except Exception as e:
            print(f"Warning: Could not send email: {e}")
        
        return 1  # Divergence detected
    else:
        print("\n✅ Results match within tolerance")
        return 0  # Success


def extract_step_results(clone_dir: Path, step: dict) -> dict:
    """Extract numerical results from a completed step."""
    results = {}
    
    for output_file in step.get("output_files", []):
        file_path = clone_dir / step["cwd"] / output_file
        if file_path.exists():
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                results[output_file] = parse_output_file(content, step)
            except Exception as e:
                results[output_file] = {"error": str(e)}
    
    return results


def parse_output_file(content: str, step: dict) -> dict:
    """Parse numerical values from output file content."""
    values = {}
    
    # Try to extract key-value pairs
    for line in content.split("\n"):
        line = line.strip()
        if ":" in line or "=" in line:
            parts = line.replace("=", ":").split(":")
            if len(parts) >= 2:
                key = parts[0].strip()
                try:
                    value = float(parts[1].strip().split()[0])
                    values[key] = value
                except (ValueError, IndexError):
                    pass
    
    # Look for specific patterns
    for key in step.get("key_values", []):
        if key not in values:
            # Search for the key in content
            import re
            pattern = rf"{key}\s*[=:]\s*([-+]?\d*\.?\d+)"
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                values[key] = float(match.group(1))
    
    return values


def compare_results(results_014: dict, results_017: dict, step: dict) -> dict:
    """Compare results between two versions."""
    comparison = {
        "step_id": step["id"],
        "step_name": step["name"],
        "timestamp": datetime.now().isoformat(),
        "differences": [],
        "has_meaningful_difference": False,
        "max_log_diff": 0.0
    }
    
    # Get all keys from both results
    all_keys = set()
    for file_results in results_014.values():
        if isinstance(file_results, dict):
            all_keys.update(file_results.keys())
    for file_results in results_017.values():
        if isinstance(file_results, dict):
            all_keys.update(file_results.keys())
    
    # Compare each key
    for key in all_keys:
        val_014 = None
        val_017 = None
        
        # Find values in results
        for file_results in results_014.values():
            if isinstance(file_results, dict) and key in file_results:
                val_014 = file_results[key]
                break
        for file_results in results_017.values():
            if isinstance(file_results, dict) and key in file_results:
                val_017 = file_results[key]
                break
        
        if val_014 is not None and val_017 is not None:
            # Calculate log difference
            if val_014 != 0 and val_017 != 0:
                log_diff = abs(np.log(abs(val_017)) - np.log(abs(val_014)))
            elif val_014 == val_017:
                log_diff = 0.0
            else:
                log_diff = float('inf')
            
            diff_entry = {
                "key": key,
                "value_0.14.1": val_014,
                "value_0.17.0": val_017,
                "log_diff": log_diff,
                "pct_diff": 100 * (val_017 - val_014) / val_014 if val_014 != 0 else float('inf'),
                "is_meaningful": log_diff > MEANINGFUL_DIFF_THRESHOLD
            }
            comparison["differences"].append(diff_entry)
            
            if log_diff > comparison["max_log_diff"]:
                comparison["max_log_diff"] = log_diff
            
            if diff_entry["is_meaningful"]:
                comparison["has_meaningful_difference"] = True
    
    return comparison


def print_comparison_details(comparison: dict):
    """Print detailed comparison results."""
    print(f"\nStep: {comparison['step_name']}")
    print(f"Threshold: {MEANINGFUL_DIFF_THRESHOLD} log points ({MEANINGFUL_DIFF_THRESHOLD*100}%)")
    print(f"Max difference: {comparison['max_log_diff']:.4f} log points")
    print("\nDifferences:")
    print("-" * 80)
    print(f"{'Key':<30} {'0.14.1':>15} {'0.17.0':>15} {'Log Diff':>12} {'Status':>10}")
    print("-" * 80)
    
    for diff in sorted(comparison["differences"], key=lambda x: -x["log_diff"]):
        status = "⚠️ DIFF" if diff["is_meaningful"] else "✓ OK"
        print(f"{diff['key']:<30} {diff['value_0.14.1']:>15.6f} {diff['value_0.17.0']:>15.6f} {diff['log_diff']:>12.4f} {status:>10}")


def send_divergence_notification(step_id: int, step: dict, comparison: dict):
    """Send email notification about divergence."""
    try:
        # Import email config
        sys.path.insert(0, str(VALIDATION_DIR))
        from email_config import EMAIL_CONFIG
        from send_notification import send_email
        
        subject = f"HAFiscal Validation: Divergence in Step {step_id} ({step['name']})"
        
        body = f"""
HAFiscal Validation Alert: Meaningful Difference Detected

Step {step_id}: {step['name']}
Description: {step['description']}
Timestamp: {comparison['timestamp']}

Maximum log-point difference: {comparison['max_log_diff']:.4f}
Threshold: {MEANINGFUL_DIFF_THRESHOLD}

Key Differences:
"""
        for diff in comparison["differences"]:
            if diff["is_meaningful"]:
                body += f"\n  {diff['key']}:"
                body += f"\n    0.14.1: {diff['value_0.14.1']}"
                body += f"\n    0.17.0: {diff['value_0.17.0']}"
                body += f"\n    Log diff: {diff['log_diff']:.4f}"
        
        body += """

The validation has PAUSED. Please investigate the cause of this divergence.

To diagnose:
  python interactive_validation.py diagnose {step_id}

To continue after fixing:
  python interactive_validation.py step {next_step}
"""
        
        send_email(subject, body)
        print("📧 Email notification sent")
    except Exception as e:
        print(f"Could not send email: {e}")


def show_status():
    """Show current validation status."""
    print("=" * 60)
    print("Validation Status")
    print("=" * 60)
    
    for step in VALIDATION_STEPS:
        comparison_file = RESULTS_DIR / f"step{step['id']}_comparison.json"
        if comparison_file.exists():
            with open(comparison_file) as f:
                comparison = json.load(f)
            
            if comparison["has_meaningful_difference"]:
                status = "⚠️ DIVERGED"
            else:
                status = "✅ PASSED"
            print(f"Step {step['id']}: {step['name']:<30} {status}")
        else:
            print(f"Step {step['id']}: {step['name']:<30} ⏳ Not run")


def diagnose_step(step_id: int):
    """Show detailed diagnosis for a step."""
    comparison_file = RESULTS_DIR / f"step{step_id}_comparison.json"
    
    if not comparison_file.exists():
        print(f"No results found for step {step_id}")
        print("Run the step first: python interactive_validation.py step {step_id}")
        return
    
    with open(comparison_file) as f:
        comparison = json.load(f)
    
    print("=" * 60)
    print(f"Diagnosis for Step {step_id}: {comparison['step_name']}")
    print("=" * 60)
    
    print_comparison_details(comparison)
    
    # Show relevant files
    print("\n" + "=" * 60)
    print("Relevant Files for Investigation:")
    print("=" * 60)
    
    for version in ["0.14.1", "0.17.0"]:
        output_file = RESULTS_DIR / f"step{step_id}_{version}_output.txt"
        error_file = RESULTS_DIR / f"step{step_id}_{version}_error.txt"
        
        if output_file.exists():
            print(f"  {version} output: {output_file}")
        if error_file.exists():
            print(f"  {version} error: {error_file}")
    
    # Show step configuration
    step = next((s for s in VALIDATION_STEPS if s["id"] == step_id), None)
    if step:
        print(f"\nStep Script: {step['script']}")
        print(f"Working Dir: {step['cwd']}")
        print(f"Output Files: {step['output_files']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    
    command = sys.argv[1].lower()
    
    if command == "setup":
        success = setup_environments()
        return 0 if success else 1
    
    elif command == "step":
        if len(sys.argv) < 3:
            print("Usage: python interactive_validation.py step N")
            return 1
        step_id = int(sys.argv[2])
        return run_step(step_id)
    
    elif command == "status":
        show_status()
        return 0
    
    elif command == "diagnose":
        if len(sys.argv) < 3:
            print("Usage: python interactive_validation.py diagnose N")
            return 1
        step_id = int(sys.argv[2])
        diagnose_step(step_id)
        return 0
    
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
