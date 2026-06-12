#!/usr/bin/env python3
"""
Step Runner for HAFiscal Parallel Validation

Runs individual steps of the HAFiscal computation and captures results.
Designed to be called from the orchestration script for both 0.14.1 and 0.17.0 versions.

Usage:
    python step_runner.py --step N --output-dir /path/to/output --clone-dir /path/to/clone
    
Steps:
    1: Estimation_BetaNablaSplurge (splurge factor estimation)
    2: EstimAggFiscalMAIN (discount factor estimation) 
    3: AggFiscalMAIN (aggregate fiscal policy)
    4: Simulate (HANK-SAM simulation)
    5: Output_Results (generate outputs)
"""

import os
import sys
import json
import argparse
import subprocess
import time
import re
from pathlib import Path
from datetime import datetime


def get_project_root(clone_dir=None):
    """Find the project root (directory containing Code/HA-Models)"""
    if clone_dir:
        return Path(clone_dir)
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "Code" / "HA-Models").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root")


def capture_step_results(step_num, output_dir, clone_dir):
    """Capture numerical results after a step completes"""
    results = {
        "step": step_num,
        "timestamp": datetime.now().isoformat(),
        "values": {}
    }
    
    project_root = get_project_root(clone_dir)
    ha_models = project_root / "Code" / "HA-Models"
    
    # Step-specific result files to capture
    result_locations = {
        1: [  # Estimation_BetaNablaSplurge
            ha_models / "Target_AggMPCX_LiquWealth" / "AllResults.txt",
            ha_models / "Target_AggMPCX_LiquWealth" / "Result_AllTarget.txt",
            ha_models / "Target_AggMPCX_LiquWealth" / "Result_AllTarget_Splurge0.txt",
        ],
        2: [  # EstimAggFiscalMAIN  
            ha_models / "FromPandemicCode" / "Results" / "EstimResults.txt",
        ],
        3: [  # AggFiscalMAIN
            ha_models / "FromPandemicCode" / "Results" / "AggFiscalResults.txt",
        ],
        4: [  # Simulate
            ha_models / "FromPandemicCode" / "Results" / "SimulationResults.txt",
        ],
        5: [  # Output_Results
        ],
    }
    
    # Parse result files
    for result_file in result_locations.get(step_num, []):
        if result_file.exists():
            try:
                content = result_file.read_text()
                # Try to parse as Python dict
                values = eval(content)
                if isinstance(values, dict):
                    for key, val in values.items():
                        if isinstance(val, (int, float)):
                            results["values"][f"{result_file.name}:{key}"] = val
            except:
                pass
    
    # Also capture any .ltx files (contain computed values)
    params_dir = ha_models / "FromPandemicCode" / "Parameters"
    if params_dir.exists():
        for ltx_file in params_dir.glob("*.ltx"):
            try:
                content = ltx_file.read_text()
                # Extract numerical values from LaTeX commands
                matches = re.findall(r'\\newcommand\{\\(\w+)\}\{([0-9.e+-]+)\}', content)
                for name, value in matches:
                    try:
                        results["values"][f"ltx:{name}"] = float(value)
                    except ValueError:
                        pass
            except:
                pass
    
    # Save results
    output_path = Path(output_dir) / f"step_{step_num}_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    return results


def run_step(step_num, output_dir, log_file, clone_dir, venv_python):
    """Run a specific step of the HAFiscal computation using subprocess"""
    project_root = get_project_root(clone_dir)
    ha_models = project_root / "Code" / "HA-Models"
    
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Define step scripts and working directories
    step_configs = {
        1: {
            "script": "Estimation_BetaNablaSplurge.py",
            "cwd": ha_models / "Target_AggMPCX_LiquWealth",
        },
        2: {
            "script": "EstimAggFiscalMAIN.py",
            "cwd": ha_models / "FromPandemicCode",
        },
        3: {
            "script": "AggFiscalMAIN.py",
            "cwd": ha_models / "FromPandemicCode",
        },
        4: {
            "script": "Simulate.py",
            "cwd": ha_models / "FromPandemicCode",
        },
        5: {
            "script": "Output_Results.py",
            "cwd": ha_models / "FromPandemicCode",
        },
    }
    
    if step_num not in step_configs:
        with open(log_path, 'a') as log:
            log.write(f"Unknown step: {step_num}\n")
        return False
    
    config = step_configs[step_num]
    script_path = config["cwd"] / config["script"]
    
    start_time = time.time()
    success = False
    error_msg = None
    
    with open(log_path, 'a') as log:
        log.write(f"\n{'='*60}\n")
        log.write(f"Step {step_num} starting at {datetime.now().isoformat()}\n")
        log.write(f"Script: {script_path}\n")
        log.write(f"Working dir: {config['cwd']}\n")
        log.write(f"Python: {venv_python}\n")
        log.write(f"{'='*60}\n")
        log.flush()
    
    # Set up environment
    env = os.environ.copy()
    env["MATPLOTLIB_BACKEND"] = "Agg"
    env["PYTHONPATH"] = f"{ha_models}:{ha_models / 'FromPandemicCode'}:{ha_models / 'Target_AggMPCX_LiquWealth'}"
    
    try:
        # Run the script as a subprocess
        with open(log_path, 'a') as log:
            result = subprocess.run(
                [str(venv_python), str(script_path)],
                cwd=str(config["cwd"]),
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=14400  # 4 hour timeout
            )
            success = result.returncode == 0
            if not success:
                error_msg = f"Script exited with code {result.returncode}"
                
    except subprocess.TimeoutExpired:
        error_msg = "Step timed out after 4 hours"
    except Exception as e:
        error_msg = f"Error running step {step_num}: {e}"
    
    duration = time.time() - start_time
    
    with open(log_path, 'a') as log:
        log.write(f"\n{'='*60}\n")
        log.write(f"Step {step_num} finished at {datetime.now().isoformat()}\n")
        log.write(f"Duration: {duration:.1f}s ({duration/60:.1f} minutes)\n")
        log.write(f"Success: {success}\n")
        if error_msg:
            log.write(f"Error: {error_msg}\n")
        log.write(f"{'='*60}\n")
    
    # Capture results regardless of success (partial results may exist)
    results = capture_step_results(step_num, output_dir, clone_dir)
    results["success"] = success
    results["duration_seconds"] = duration
    results["error"] = error_msg
    
    # Update the results file with final status
    output_path = Path(output_dir) / f"step_{step_num}_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Write completion marker
    marker_path = Path(output_dir) / f"step_{step_num}_complete"
    with open(marker_path, 'w') as f:
        f.write(f"{'SUCCESS' if success else 'FAILED'}\n")
        f.write(f"Duration: {duration:.1f}s\n")
        if error_msg:
            f.write(f"Error: {error_msg}\n")
    
    return success


def main():
    parser = argparse.ArgumentParser(description="Run individual HAFiscal computation steps")
    parser.add_argument("--step", type=int, required=True, help="Step number (1-5)")
    parser.add_argument("--output-dir", required=True, help="Directory for output files")
    parser.add_argument("--log-file", help="Path to log file (default: output-dir/step_N.log)")
    parser.add_argument("--clone-dir", required=True, help="Path to the HAFiscal clone")
    parser.add_argument("--venv-python", required=True, help="Path to the Python executable in the venv")
    
    args = parser.parse_args()
    
    if args.step < 1 or args.step > 5:
        print(f"Error: Step must be 1-5, got {args.step}")
        sys.exit(1)
    
    log_file = args.log_file or os.path.join(args.output_dir, f"step_{args.step}.log")
    
    success = run_step(
        args.step, 
        args.output_dir, 
        log_file, 
        args.clone_dir,
        args.venv_python
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
