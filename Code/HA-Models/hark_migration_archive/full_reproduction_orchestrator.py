#!/usr/bin/env python3
"""
Full Reproduction Comparison Orchestrator

Runs the complete HAFiscal paper reproduction (do_all.py steps) in parallel
on both 0.14.1-bugfixed and 0.17.0-native codebases, comparing results after
each step and alerting on discrepancies.

Key Features:
- Incremental execution (step by step)
- Background execution with log files for `tail -f` monitoring
- Real-time comparison after each step
- Automatic pause and diagnosis on discrepancies
- Checkpointing for resume capability

Usage:
    # Run all steps
    python full_reproduction_orchestrator.py --all
    
    # Run specific step
    python full_reproduction_orchestrator.py --step 1
    
    # Resume from last checkpoint
    python full_reproduction_orchestrator.py --resume
    
    # Monitor progress
    tail -f /tmp/hafiscal_full_repro/logs/master.log
"""

import os
import sys
import json
import time
import shutil
import argparse
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import numpy as np

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = Path("/tmp/hafiscal_full_repro")
LOG_DIR = BASE_DIR / "logs"
RESULTS_DIR = BASE_DIR / "results"
CHECKPOINT_DIR = BASE_DIR / "checkpoints"
COMPARISON_DIR = BASE_DIR / "comparisons"
ALERT_DIR = BASE_DIR / "alerts"

# Codebase paths
CODEBASES = {
    "0.14.1-bugfixed": Path("/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed"),
    "0.17.0-native": Path("/home/econ-ark/GitHub/llorracc/HAFiscal-Latest"),
}

# Tolerance for numerical comparisons (log difference)
DEFAULT_TOLERANCE = 0.01  # 1%

# =============================================================================
# REPRODUCTION STEPS
# =============================================================================

@dataclass
class ReproductionStep:
    """Definition of a reproduction step."""
    id: int
    name: str
    description: str
    script: str
    cwd: str  # Relative to codebase
    expected_duration_hours: float
    output_files: List[str]  # Files to compare (relative to cwd)
    comparison_type: str  # "text", "numeric", "figure"
    tolerance: float = DEFAULT_TOLERANCE

REPRODUCTION_STEPS = [
    ReproductionStep(
        id=1,
        name="splurge_estimation",
        description="Estimating the splurge factor (Section 3.1)",
        script="Estimation_BetaNablaSplurge.py",
        cwd="Code/HA-Models/Target_AggMPCX_LiquWealth",
        expected_duration_hours=0.5,
        output_files=[
            "Result_AllTarget.txt",
            "Result_AllTarget_Splurge0.txt",
        ],
        comparison_type="text",
    ),
    ReproductionStep(
        id=2,
        name="discount_factor_estimation",
        description="Estimating discount factor distributions (Section 3.3.3) - MAIN ESTIMATION",
        script="EstimAggFiscalMAIN.py",
        cwd="Code/HA-Models/FromPandemicCode",
        expected_duration_hours=48,
        output_files=[
            "Tables/CRRA2/estimBetas.ltx",
            "Tables/CRRA2/nonTargetedMoments.ltx",
            "../Results/AllResults_CRRA_2.0_R_1.01.txt",
            "../Results/DiscFacEstim_CRRA_2.0_R_1.01.txt",
        ],
        comparison_type="text",
    ),
    ReproductionStep(
        id=3,
        name="robustness_splurge0",
        description="Robustness: Splurge=0 estimation (Online Appendix)",
        script="EstimAggFiscalMAIN.py 1.01 2.0 0.7 0.5 0",
        cwd="Code/HA-Models/FromPandemicCode",
        expected_duration_hours=48,
        output_files=[
            # Robustness results go to different files
        ],
        comparison_type="text",
    ),
    ReproductionStep(
        id=4,
        name="hank_sam_jacobians",
        description="HANK/SAM Model - Computing Jacobians (Section 5)",
        script="HA-Fiscal-HANK-SAM.py",
        cwd="Code/HA-Models/FromPandemicCode",
        expected_duration_hours=12,
        output_files=[
            # Jacobian outputs
        ],
        comparison_type="numeric",
    ),
    ReproductionStep(
        id=5,
        name="policy_comparisons",
        description="Comparing fiscal stimulus policies (Section 4)",
        script="AggFiscalMAIN.py",
        cwd="Code/HA-Models/FromPandemicCode",
        expected_duration_hours=12,
        output_files=[
            "Tables/Reduced_Run/Multiplier.ltx",
            "Tables/Reduced_Run/welfare1.ltx",
            "Tables/Reduced_Run/welfare2.ltx",
        ],
        comparison_type="text",
    ),
]

# =============================================================================
# LOGGING
# =============================================================================

class Logger:
    """Thread-safe logger with file and console output."""
    
    def __init__(self):
        self._ensure_dirs()
        self.master_log = LOG_DIR / "master.log"
        self._lock = threading.Lock()
        
        with open(self.master_log, 'w') as f:
            f.write(f"{'='*70}\n")
            f.write(f"HAFiscal Full Reproduction Comparison\n")
            f.write(f"Started: {datetime.now().isoformat()}\n")
            f.write(f"{'='*70}\n\n")
    
    def _ensure_dirs(self):
        for d in [LOG_DIR, RESULTS_DIR, CHECKPOINT_DIR, COMPARISON_DIR, ALERT_DIR]:
            d.mkdir(parents=True, exist_ok=True)
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {level:8s} | {message}"
        
        with self._lock:
            print(log_line)
            with open(self.master_log, 'a') as f:
                f.write(log_line + "\n")
    
    def alert(self, title: str, details: str):
        """Create an alert file for discrepancy detection."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        alert_file = ALERT_DIR / f"ALERT_{timestamp}.txt"
        
        with open(alert_file, 'w') as f:
            f.write(f"{'!'*70}\n")
            f.write(f"DISCREPANCY ALERT\n")
            f.write(f"{'!'*70}\n\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
            f.write(f"Title: {title}\n\n")
            f.write(f"Details:\n{details}\n")
        
        self.log(f"ALERT created: {alert_file}", "ALERT")
        return alert_file

logger = Logger()

# =============================================================================
# STEP EXECUTION
# =============================================================================

def run_step_for_version(step: ReproductionStep, version: str) -> Dict[str, Any]:
    """Run a single step for a specific version."""
    codebase = CODEBASES[version]
    cwd = codebase / step.cwd
    log_file = LOG_DIR / f"step{step.id}_{version}.log"
    
    # Prepare environment
    env = os.environ.copy()
    env["VERSION_ID"] = version
    
    # CRITICAL: Force non-interactive matplotlib to prevent plt.show() hangs
    env["NONINTERACTIVE"] = "true"
    env["MATPLOTLIB_BACKEND"] = "Agg"
    
    # CRITICAL: Force unbuffered Python output for real-time logging
    env["PYTHONUNBUFFERED"] = "1"
    
    # Add HARK to path
    if version == "0.17.0-native":
        env["PYTHONPATH"] = f"{codebase}/HARK:{codebase}/Code/HA-Models:" + env.get("PYTHONPATH", "")
    
    # Determine Python executable
    venv_python = codebase / ".venv" / "bin" / "python"
    python_cmd = str(venv_python) if venv_python.exists() else "python"
    
    # Build command
    script_parts = step.script.split()
    script_name = script_parts[0]
    script_args = script_parts[1:] if len(script_parts) > 1 else []
    
    cmd = [python_cmd, script_name] + script_args
    
    logger.log(f"[{version}] Starting step {step.id}: {step.name}")
    logger.log(f"[{version}] Command: {' '.join(cmd)}")
    logger.log(f"[{version}] CWD: {cwd}")
    logger.log(f"[{version}] Log: {log_file}")
    
    start_time = time.time()
    
    try:
        with open(log_file, 'w') as f:
            f.write(f"Step {step.id}: {step.name}\n")
            f.write(f"Version: {version}\n")
            f.write(f"Started: {datetime.now().isoformat()}\n")
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write(f"CWD: {cwd}\n")
            f.write(f"{'='*60}\n\n")
        
        process = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        
        # Stream output to log file
        with open(log_file, 'a') as f:
            for line in process.stdout:
                f.write(line)
                f.flush()
        
        process.wait()
        elapsed = time.time() - start_time
        
        result = {
            "version": version,
            "step_id": step.id,
            "step_name": step.name,
            "status": "success" if process.returncode == 0 else "failed",
            "exit_code": process.returncode,
            "elapsed_seconds": elapsed,
            "log_file": str(log_file),
        }
        
        if process.returncode == 0:
            logger.log(f"[{version}] Step {step.id} completed in {elapsed/3600:.2f} hours", "SUCCESS")
        else:
            logger.log(f"[{version}] Step {step.id} FAILED with exit code {process.returncode}", "ERROR")
        
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.log(f"[{version}] Step {step.id} ERROR: {e}", "ERROR")
        return {
            "version": version,
            "step_id": step.id,
            "step_name": step.name,
            "status": "error",
            "error": str(e),
            "elapsed_seconds": elapsed,
            "log_file": str(log_file),
        }

# =============================================================================
# COMPARISON
# =============================================================================

def compare_files(file1: Path, file2: Path, comparison_type: str, tolerance: float) -> Dict[str, Any]:
    """Compare two output files and return comparison results."""
    result = {
        "file1": str(file1),
        "file2": str(file2),
        "comparison_type": comparison_type,
        "identical": False,
        "differences": [],
    }
    
    if not file1.exists():
        result["error"] = f"File 1 not found: {file1}"
        return result
    
    if not file2.exists():
        result["error"] = f"File 2 not found: {file2}"
        return result
    
    try:
        with open(file1, 'r') as f:
            content1 = f.read()
        with open(file2, 'r') as f:
            content2 = f.read()
        
        if comparison_type == "text":
            # Line-by-line comparison
            lines1 = content1.strip().split('\n')
            lines2 = content2.strip().split('\n')
            
            if lines1 == lines2:
                result["identical"] = True
            else:
                # Find differences
                max_lines = max(len(lines1), len(lines2))
                for i in range(max_lines):
                    l1 = lines1[i] if i < len(lines1) else "<missing>"
                    l2 = lines2[i] if i < len(lines2) else "<missing>"
                    if l1 != l2:
                        # Try to extract and compare numbers
                        diff_info = {"line": i + 1, "v1": l1, "v2": l2}
                        try:
                            nums1 = [float(x) for x in l1.split() if x.replace('.', '').replace('-', '').replace('e', '').isdigit()]
                            nums2 = [float(x) for x in l2.split() if x.replace('.', '').replace('-', '').replace('e', '').isdigit()]
                            if nums1 and nums2 and len(nums1) == len(nums2):
                                max_diff = max(abs(n1 - n2) / max(abs(n1), 1e-10) for n1, n2 in zip(nums1, nums2))
                                diff_info["numeric_diff"] = max_diff
                                diff_info["within_tolerance"] = max_diff < tolerance
                        except:
                            pass
                        result["differences"].append(diff_info)
                
                # Check if all numeric differences are within tolerance
                if result["differences"]:
                    all_within = all(
                        d.get("within_tolerance", False) 
                        for d in result["differences"] 
                        if "numeric_diff" in d
                    )
                    result["all_within_tolerance"] = all_within
        
        elif comparison_type == "numeric":
            # Hash comparison for binary/numeric files
            hash1 = hashlib.md5(content1.encode()).hexdigest()
            hash2 = hashlib.md5(content2.encode()).hexdigest()
            result["identical"] = hash1 == hash2
            result["hash1"] = hash1
            result["hash2"] = hash2
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        return result

def compare_step_outputs(step: ReproductionStep, versions: List[str]) -> Dict[str, Any]:
    """Compare outputs from a step across versions."""
    v1, v2 = versions[0], versions[1]
    codebase1 = CODEBASES[v1]
    codebase2 = CODEBASES[v2]
    
    comparison = {
        "step_id": step.id,
        "step_name": step.name,
        "timestamp": datetime.now().isoformat(),
        "versions": versions,
        "files": [],
        "has_discrepancies": False,
    }
    
    for output_file in step.output_files:
        file1 = codebase1 / step.cwd / output_file
        file2 = codebase2 / step.cwd / output_file
        
        file_comparison = compare_files(file1, file2, step.comparison_type, step.tolerance)
        file_comparison["relative_path"] = output_file
        comparison["files"].append(file_comparison)
        
        if not file_comparison.get("identical") and not file_comparison.get("all_within_tolerance"):
            comparison["has_discrepancies"] = True
    
    # Save comparison
    comparison_file = COMPARISON_DIR / f"step{step.id}_comparison.json"
    with open(comparison_file, 'w') as f:
        json.dump(comparison, f, indent=2)
    
    return comparison

# =============================================================================
# ORCHESTRATION
# =============================================================================

def run_step(step: ReproductionStep, versions: List[str] = None) -> Dict[str, Any]:
    """Run a single step on all versions and compare results."""
    if versions is None:
        versions = list(CODEBASES.keys())
    
    logger.log(f"\n{'='*70}")
    logger.log(f"STEP {step.id}: {step.name}")
    logger.log(f"Description: {step.description}")
    logger.log(f"Expected duration: {step.expected_duration_hours} hours")
    logger.log(f"{'='*70}\n")
    
    # Run step on both versions in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(run_step_for_version, step, v): v 
            for v in versions
        }
        
        for future in as_completed(futures):
            version = futures[future]
            results[version] = future.result()
    
    # Check if both succeeded
    all_success = all(r.get("status") == "success" for r in results.values())
    
    if not all_success:
        failed_versions = [v for v, r in results.items() if r.get("status") != "success"]
        logger.log(f"Step {step.id} failed for versions: {failed_versions}", "ERROR")
        
        # Create alert
        alert_details = f"Step {step.id} ({step.name}) failed.\n\n"
        for v, r in results.items():
            alert_details += f"{v}: {r.get('status')} - {r.get('error', r.get('exit_code', 'unknown'))}\n"
        logger.alert(f"Step {step.id} Execution Failure", alert_details)
        
        return {"step_id": step.id, "status": "execution_failed", "results": results}
    
    # Compare outputs
    logger.log(f"Comparing outputs for step {step.id}...")
    comparison = compare_step_outputs(step, versions)
    
    if comparison["has_discrepancies"]:
        logger.log(f"DISCREPANCY DETECTED in step {step.id}!", "ALERT")
        
        # Build detailed discrepancy report
        alert_details = f"Step {step.id} ({step.name}) produced different results.\n\n"
        for fc in comparison["files"]:
            if not fc.get("identical") and not fc.get("all_within_tolerance"):
                alert_details += f"File: {fc['relative_path']}\n"
                if "error" in fc:
                    alert_details += f"  Error: {fc['error']}\n"
                elif fc.get("differences"):
                    alert_details += f"  Differences found: {len(fc['differences'])} lines\n"
                    for diff in fc["differences"][:5]:  # Show first 5
                        alert_details += f"    Line {diff['line']}:\n"
                        alert_details += f"      0.14.1: {diff['v1'][:80]}...\n" if len(diff['v1']) > 80 else f"      0.14.1: {diff['v1']}\n"
                        alert_details += f"      0.17.0: {diff['v2'][:80]}...\n" if len(diff['v2']) > 80 else f"      0.17.0: {diff['v2']}\n"
                        if "numeric_diff" in diff:
                            alert_details += f"      Numeric diff: {diff['numeric_diff']:.4%}\n"
                alert_details += "\n"
        
        alert_file = logger.alert(f"Step {step.id} Numerical Discrepancy", alert_details)
        
        return {
            "step_id": step.id,
            "status": "discrepancy_detected",
            "results": results,
            "comparison": comparison,
            "alert_file": str(alert_file),
        }
    
    logger.log(f"Step {step.id} completed successfully - outputs match!", "SUCCESS")
    
    # Save checkpoint
    checkpoint = {
        "step_id": step.id,
        "step_name": step.name,
        "completed_at": datetime.now().isoformat(),
        "status": "success",
        "results": results,
    }
    checkpoint_file = CHECKPOINT_DIR / f"step{step.id}_checkpoint.json"
    with open(checkpoint_file, 'w') as f:
        json.dump(checkpoint, f, indent=2)
    
    return {"step_id": step.id, "status": "success", "results": results, "comparison": comparison}

def run_all_steps(versions: List[str] = None, start_from: int = 1):
    """Run all steps sequentially."""
    if versions is None:
        versions = list(CODEBASES.keys())
    
    logger.log(f"\n{'#'*70}")
    logger.log(f"STARTING FULL REPRODUCTION COMPARISON")
    logger.log(f"Versions: {versions}")
    logger.log(f"Starting from step: {start_from}")
    logger.log(f"{'#'*70}\n")
    
    all_results = []
    
    for step in REPRODUCTION_STEPS:
        if step.id < start_from:
            logger.log(f"Skipping step {step.id} (starting from {start_from})")
            continue
        
        result = run_step(step, versions)
        all_results.append(result)
        
        # Check if we should pause
        if result["status"] == "discrepancy_detected":
            logger.log(f"\n{'!'*70}")
            logger.log("PAUSING - Discrepancy detected!")
            logger.log(f"Please investigate the alert at: {result.get('alert_file')}")
            logger.log("To continue: python full_reproduction_orchestrator.py --resume")
            logger.log(f"{'!'*70}\n")
            
            # Save state for resume
            state = {
                "paused_at_step": step.id,
                "timestamp": datetime.now().isoformat(),
                "reason": "discrepancy_detected",
                "all_results": all_results,
            }
            with open(CHECKPOINT_DIR / "paused_state.json", 'w') as f:
                json.dump(state, f, indent=2)
            
            return all_results
        
        elif result["status"] == "execution_failed":
            logger.log(f"\n{'!'*70}")
            logger.log("PAUSING - Step execution failed!")
            logger.log("Please check logs and fix the issue.")
            logger.log(f"{'!'*70}\n")
            return all_results
    
    logger.log(f"\n{'='*70}")
    logger.log("ALL STEPS COMPLETED SUCCESSFULLY!")
    logger.log(f"{'='*70}\n")
    
    return all_results

# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Full Reproduction Comparison Orchestrator")
    parser.add_argument("--all", action="store_true", help="Run all steps")
    parser.add_argument("--step", type=int, help="Run specific step (1-5)")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--list", action="store_true", help="List all steps")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--versions", nargs="+", default=list(CODEBASES.keys()),
                       help="Versions to compare (default: all)")
    
    args = parser.parse_args()
    
    if args.list:
        print("\nReproduction Steps:")
        print("-" * 70)
        for step in REPRODUCTION_STEPS:
            print(f"  {step.id}. {step.name}")
            print(f"     {step.description}")
            print(f"     Expected duration: {step.expected_duration_hours} hours")
            print()
        return
    
    if args.status:
        print("\nCurrent Status:")
        print("-" * 70)
        
        # Check checkpoints
        for step in REPRODUCTION_STEPS:
            checkpoint_file = CHECKPOINT_DIR / f"step{step.id}_checkpoint.json"
            if checkpoint_file.exists():
                with open(checkpoint_file) as f:
                    cp = json.load(f)
                print(f"  Step {step.id}: ✅ Completed at {cp['completed_at']}")
            else:
                print(f"  Step {step.id}: ⏳ Not started")
        
        # Check for paused state
        paused_file = CHECKPOINT_DIR / "paused_state.json"
        if paused_file.exists():
            with open(paused_file) as f:
                state = json.load(f)
            print(f"\n⚠️  PAUSED at step {state['paused_at_step']}")
            print(f"   Reason: {state['reason']}")
            print(f"   Time: {state['timestamp']}")
        
        # Check for alerts
        alerts = list(ALERT_DIR.glob("ALERT_*.txt"))
        if alerts:
            print(f"\n🚨 {len(alerts)} alert(s) in {ALERT_DIR}")
        
        return
    
    if args.resume:
        paused_file = CHECKPOINT_DIR / "paused_state.json"
        if paused_file.exists():
            with open(paused_file) as f:
                state = json.load(f)
            start_from = state["paused_at_step"] + 1
            print(f"Resuming from step {start_from}...")
            os.remove(paused_file)
            run_all_steps(args.versions, start_from=start_from)
        else:
            # Find last completed step
            last_completed = 0
            for step in REPRODUCTION_STEPS:
                checkpoint_file = CHECKPOINT_DIR / f"step{step.id}_checkpoint.json"
                if checkpoint_file.exists():
                    last_completed = step.id
            
            if last_completed > 0:
                print(f"Resuming from step {last_completed + 1}...")
                run_all_steps(args.versions, start_from=last_completed + 1)
            else:
                print("No checkpoints found. Starting from step 1...")
                run_all_steps(args.versions)
        return
    
    if args.step:
        step = next((s for s in REPRODUCTION_STEPS if s.id == args.step), None)
        if step is None:
            print(f"Error: Step {args.step} not found")
            return
        run_step(step, args.versions)
        return
    
    if args.all:
        run_all_steps(args.versions)
        return
    
    # Default: show help
    parser.print_help()

if __name__ == "__main__":
    main()
