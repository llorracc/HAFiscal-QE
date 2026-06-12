#!/usr/bin/env python3
"""
Parallel Validation Orchestrator for HAFiscal HARK Migration

Runs HARK 0.14.1 and 0.17.0 versions in parallel, comparing results
after each step. Halts and sends email notification on meaningful divergence.

Usage:
    python parallel_validation.py [--start-step N] [--dry-run]
    
Monitoring:
    tail -f /tmp/hafiscal_parallel_validation.log
"""

import os
import sys
import json
import subprocess
import time
import math
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import email notification
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
EMAIL_AVAILABLE = False
try:
    # Check if email_config exists first
    if (SCRIPT_DIR / "email_config.py").exists():
        from send_notification import send_email
        EMAIL_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Email notification not available: {e}")


# Configuration
MEANINGFUL_DIFF_THRESHOLD = 0.02  # 2% in log points

CLONE_0141 = Path("/home/econ-ark/GitHub/llorracc/HAFiscal-validation-0.14.1")
CLONE_0170 = Path("/home/econ-ark/GitHub/llorracc/HAFiscal-validation-0.17.0")

VENV_0141 = CLONE_0141 / ".venv-validation"
VENV_0170 = CLONE_0170 / ".venv-validation"

OUTPUT_BASE = Path("/tmp/hafiscal_parallel_validation")
LOG_FILE = Path("/tmp/hafiscal_parallel_validation.log")
STATUS_FILE = Path("/tmp/hafiscal_parallel_validation_status.json")

STEP_INFO = {
    1: {"name": "Estimation_BetaNablaSplurge", "est_minutes": 5},
    2: {"name": "EstimAggFiscalMAIN", "est_minutes": 180},
    3: {"name": "AggFiscalMAIN", "est_minutes": 10},
    4: {"name": "Simulate", "est_minutes": 60},
    5: {"name": "Output_Results", "est_minutes": 5},
}


def log(msg, also_print=True):
    """Write to log file and optionally print"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    
    with open(LOG_FILE, 'a') as f:
        f.write(log_msg + "\n")
    
    if also_print:
        print(log_msg)


def update_status(status_dict):
    """Update status file for monitoring"""
    status_dict["last_update"] = datetime.now().isoformat()
    with open(STATUS_FILE, 'w') as f:
        json.dump(status_dict, f, indent=2)


def log_point_diff(baseline_val, current_val):
    """Calculate absolute log-point difference"""
    if baseline_val == 0 and current_val == 0:
        return 0.0
    if baseline_val == 0 or current_val == 0:
        return float('inf')
    try:
        return abs(math.log(abs(current_val)) - math.log(abs(baseline_val)))
    except (ValueError, ZeroDivisionError):
        return float('inf')


def run_step_in_clone(clone_path, venv_path, step_num, output_dir):
    """Run a step in a specific clone with its virtual environment"""
    venv_python = venv_path / "bin" / "python"
    
    # Always use the step_runner from main repo (it's version-agnostic)
    step_runner = Path("/home/econ-ark/GitHub/llorracc/HAFiscal-Latest/reproduce/upgrade-validation/step_runner.py")
    
    log_file = output_dir / f"step_{step_num}.log"
    
    cmd = [
        sys.executable,  # Use current Python to run step_runner
        str(step_runner),
        "--step", str(step_num),
        "--output-dir", str(output_dir),
        "--log-file", str(log_file),
        "--clone-dir", str(clone_path),
        "--venv-python", str(venv_python)
    ]
    
    env = os.environ.copy()
    env["MATPLOTLIB_BACKEND"] = "Agg"
    
    result = subprocess.run(
        cmd,
        cwd=str(clone_path),
        env=env,
        capture_output=True,
        text=True
    )
    
    # Log any stderr from the step runner itself
    if result.stderr:
        with open(log_file, 'a') as f:
            f.write(f"\n[step_runner stderr]\n{result.stderr}\n")
    
    return result.returncode == 0


def compare_step_results(step_num, output_0141, output_0170):
    """
    Compare results from both versions after a step.
    Returns (is_ok, divergence_details)
    """
    result_file_0141 = output_0141 / f"step_{step_num}_results.json"
    result_file_0170 = output_0170 / f"step_{step_num}_results.json"
    
    if not result_file_0141.exists():
        return False, {"error": f"Missing results from 0.14.1: {result_file_0141}"}
    if not result_file_0170.exists():
        return False, {"error": f"Missing results from 0.17.0: {result_file_0170}"}
    
    with open(result_file_0141) as f:
        results_0141 = json.load(f)
    with open(result_file_0170) as f:
        results_0170 = json.load(f)
    
    # Check for execution errors
    if not results_0141.get("success", False):
        return False, {"error": f"0.14.1 step {step_num} failed: {results_0141.get('error', 'unknown')}"}
    if not results_0170.get("success", False):
        return False, {"error": f"0.17.0 step {step_num} failed: {results_0170.get('error', 'unknown')}"}
    
    # Compare numerical values
    values_0141 = results_0141.get("values", {})
    values_0170 = results_0170.get("values", {})
    
    divergences = []
    
    all_keys = set(values_0141.keys()) | set(values_0170.keys())
    for key in sorted(all_keys):
        val_0141 = values_0141.get(key)
        val_0170 = values_0170.get(key)
        
        if val_0141 is None:
            divergences.append({
                "key": key,
                "issue": "Missing in 0.14.1",
                "val_0170": val_0170
            })
        elif val_0170 is None:
            divergences.append({
                "key": key,
                "issue": "Missing in 0.17.0",
                "val_0141": val_0141
            })
        elif isinstance(val_0141, (int, float)) and isinstance(val_0170, (int, float)):
            diff = log_point_diff(val_0141, val_0170)
            if diff > MEANINGFUL_DIFF_THRESHOLD:
                divergences.append({
                    "key": key,
                    "val_0141": val_0141,
                    "val_0170": val_0170,
                    "log_diff": diff,
                    "percent_diff": 100 * (val_0170 - val_0141) / val_0141 if val_0141 != 0 else float('inf')
                })
    
    meaningful_divergences = [d for d in divergences if d.get("log_diff", float('inf')) > MEANINGFUL_DIFF_THRESHOLD]
    
    if meaningful_divergences:
        return False, {
            "meaningful_divergences": meaningful_divergences,
            "total_comparisons": len(all_keys),
            "all_divergences": divergences
        }
    
    return True, {
        "total_comparisons": len(all_keys),
        "all_values_within_threshold": True
    }


def analyze_divergence(step_num, divergence_details):
    """Analyze the cause of divergence and suggest fixes"""
    analysis = {
        "step": step_num,
        "step_name": STEP_INFO[step_num]["name"],
        "divergence_summary": "",
        "likely_causes": [],
        "proposed_fixes": []
    }
    
    meaningful_divs = divergence_details.get("meaningful_divergences", [])
    
    if meaningful_divs:
        analysis["divergence_summary"] = f"Found {len(meaningful_divs)} meaningful divergence(s) in step {step_num}"
        
        # Categorize divergences
        large_divs = [d for d in meaningful_divs if d.get("log_diff", 0) > 0.1]  # >10%
        
        if large_divs:
            analysis["likely_causes"].append(
                "Large numerical divergence suggests fundamental algorithmic changes in HARK 0.17.0"
            )
        else:
            analysis["likely_causes"].append(
                "Small divergence may be due to floating-point precision differences or minor algorithm changes"
            )
        
        # Analyze by key patterns
        keys = [d["key"] for d in meaningful_divs]
        if any("beta" in k.lower() for k in keys):
            analysis["likely_causes"].append(
                "Divergence in discount factor (beta) parameters - may affect all downstream calculations"
            )
        if any("splurge" in k.lower() for k in keys):
            analysis["likely_causes"].append(
                "Divergence in splurge factor - affects consumption behavior modeling"
            )
        if any("mpc" in k.lower() for k in keys):
            analysis["likely_causes"].append(
                "Divergence in MPC (Marginal Propensity to Consume) - may be downstream from beta/splurge"
            )
        
        # Proposed fixes
        analysis["proposed_fixes"].append({
            "fix_id": 1,
            "description": "Pin random seeds for all stochastic operations",
            "rationale": "Ensures reproducibility by eliminating randomness differences between versions",
            "implementation": "Add np.random.seed(12345) at the start of each simulation"
        })
        
        analysis["proposed_fixes"].append({
            "fix_id": 2,
            "description": "Check HARK changelog for algorithm changes between 0.14.1 and 0.17.0",
            "rationale": "Identify specific changes that might cause divergence",
            "implementation": "Review HARK release notes and update code to match new expectations"
        })
        
        if step_num <= 2:  # Early steps
            analysis["proposed_fixes"].append({
                "fix_id": 3,
                "description": "Isolate the specific HARK component causing divergence",
                "rationale": "Solver, simulator, or optimizer changes may require different handling",
                "implementation": "Create minimal test cases for each HARK component"
            })
    
    return analysis


def send_divergence_notification(step_num, divergence_details, analysis):
    """Send email notification about divergence"""
    if not EMAIL_AVAILABLE:
        log("Email not available - cannot send notification")
        return False
    
    subject = f"HAFiscal Validation: Divergence Detected in Step {step_num}"
    
    body = f"""
HAFiscal Parallel Validation - Divergence Report
{'='*50}

DIVERGENCE DETECTED at Step {step_num}: {STEP_INFO[step_num]['name']}

Time: {datetime.now().isoformat()}

Summary
-------
{analysis.get('divergence_summary', 'No summary available')}

Likely Causes
-------------
"""
    for i, cause in enumerate(analysis.get('likely_causes', []), 1):
        body += f"{i}. {cause}\n"
    
    body += """
Divergent Values
----------------
"""
    for div in divergence_details.get('meaningful_divergences', [])[:10]:  # Limit to 10
        body += f"- {div['key']}:\n"
        body += f"    HARK 0.14.1: {div.get('val_0141', 'N/A')}\n"
        body += f"    HARK 0.17.0: {div.get('val_0170', 'N/A')}\n"
        log_diff = div.get('log_diff')
        if log_diff is not None and isinstance(log_diff, (int, float)):
            body += f"    Log-point diff: {log_diff:.4f}\n"
        else:
            body += f"    Issue: {div.get('issue', 'Unknown')}\n"
    
    body += """
Proposed Fixes
--------------
"""
    for fix in analysis.get('proposed_fixes', []):
        body += f"\nFix #{fix['fix_id']}: {fix['description']}\n"
        body += f"Rationale: {fix['rationale']}\n"
        body += f"Implementation: {fix['implementation']}\n"
    
    body += """
Next Steps
----------
1. Review the divergent values above
2. Choose a fix approach or investigate further
3. Reply to this email or resume the validation process

Validation is PAUSED until divergence is resolved.

Log file: /tmp/hafiscal_parallel_validation.log
Status file: /tmp/hafiscal_parallel_validation_status.json
"""
    
    try:
        send_email(subject, body)
        log("Divergence notification email sent successfully")
        return True
    except Exception as e:
        log(f"Failed to send email notification: {e}")
        return False


def run_parallel_validation(start_step=1, dry_run=False):
    """Main orchestration function"""
    
    # Setup
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    output_0141 = OUTPUT_BASE / "hark_0.14.1"
    output_0170 = OUTPUT_BASE / "hark_0.17.0"
    output_0141.mkdir(parents=True, exist_ok=True)
    output_0170.mkdir(parents=True, exist_ok=True)
    
    log("=" * 60)
    log("HAFiscal Parallel Validation Starting")
    log("=" * 60)
    log(f"HARK 0.14.1 clone: {CLONE_0141}")
    log(f"HARK 0.17.0 clone: {CLONE_0170}")
    log(f"Output directory: {OUTPUT_BASE}")
    log(f"Starting from step: {start_step}")
    log(f"Dry run: {dry_run}")
    log("")
    
    update_status({
        "status": "starting",
        "start_step": start_step,
        "current_step": None
    })
    
    # Copy step_runner.py to both clones if needed
    step_runner_src = Path(__file__).parent / "step_runner.py"
    for clone in [CLONE_0141, CLONE_0170]:
        dest = clone / "reproduce" / "upgrade-validation" / "step_runner.py"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if step_runner_src.exists():
            import shutil
            shutil.copy2(step_runner_src, dest)
    
    validation_results = {}
    
    for step_num in range(start_step, 6):
        step_info = STEP_INFO[step_num]
        log("")
        log(f"{'='*60}")
        log(f"Step {step_num}: {step_info['name']}")
        log(f"Estimated duration: {step_info['est_minutes']} minutes")
        log(f"{'='*60}")
        
        update_status({
            "status": "running",
            "current_step": step_num,
            "step_name": step_info["name"],
            "step_start_time": datetime.now().isoformat(),
            "estimated_duration_minutes": step_info["est_minutes"]
        })
        
        if dry_run:
            log(f"[DRY RUN] Would run step {step_num} on both versions")
            continue
        
        # Run step on both versions in parallel
        log(f"Running step {step_num} on both HARK versions in parallel...")
        step_start = time.time()
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_0141 = executor.submit(
                run_step_in_clone, CLONE_0141, VENV_0141, step_num, output_0141
            )
            future_0170 = executor.submit(
                run_step_in_clone, CLONE_0170, VENV_0170, step_num, output_0170
            )
            
            # Wait for both to complete
            success_0141 = future_0141.result()
            success_0170 = future_0170.result()
        
        step_duration = time.time() - step_start
        log(f"Step {step_num} completed in {step_duration/60:.1f} minutes")
        log(f"  HARK 0.14.1: {'SUCCESS' if success_0141 else 'FAILED'}")
        log(f"  HARK 0.17.0: {'SUCCESS' if success_0170 else 'FAILED'}")
        
        if not success_0141 or not success_0170:
            log(f"ERROR: Step {step_num} failed on one or both versions")
            update_status({
                "status": "failed",
                "current_step": step_num,
                "error": f"Step execution failed: 0.14.1={'OK' if success_0141 else 'FAIL'}, 0.17.0={'OK' if success_0170 else 'FAIL'}"
            })
            
            if EMAIL_AVAILABLE:
                send_email(
                    f"HAFiscal Validation: Step {step_num} FAILED",
                    f"Step {step_num} ({step_info['name']}) failed during execution.\n\n"
                    f"HARK 0.14.1: {'SUCCESS' if success_0141 else 'FAILED'}\n"
                    f"HARK 0.17.0: {'SUCCESS' if success_0170 else 'FAILED'}\n\n"
                    f"Check logs at:\n"
                    f"  {output_0141}/step_{step_num}.log\n"
                    f"  {output_0170}/step_{step_num}.log"
                )
            return False
        
        # Compare results
        log(f"Comparing results for step {step_num}...")
        is_ok, divergence_details = compare_step_results(step_num, output_0141, output_0170)
        
        validation_results[step_num] = {
            "success": is_ok,
            "duration_seconds": step_duration,
            "details": divergence_details
        }
        
        if not is_ok:
            log(f"DIVERGENCE DETECTED in step {step_num}!")
            log(f"Details: {json.dumps(divergence_details, indent=2)}")
            
            # Analyze and notify
            analysis = analyze_divergence(step_num, divergence_details)
            log(f"Analysis: {json.dumps(analysis, indent=2)}")
            
            # Save analysis
            analysis_file = OUTPUT_BASE / f"divergence_analysis_step_{step_num}.json"
            with open(analysis_file, 'w') as f:
                json.dump({"divergence": divergence_details, "analysis": analysis}, f, indent=2)
            
            update_status({
                "status": "paused_divergence",
                "current_step": step_num,
                "divergence": divergence_details,
                "analysis": analysis
            })
            
            # Send email notification
            send_divergence_notification(step_num, divergence_details, analysis)
            
            log("")
            log("=" * 60)
            log("VALIDATION PAUSED - DIVERGENCE DETECTED")
            log(f"Step {step_num}: {step_info['name']}")
            log("Review divergence and choose a fix before continuing.")
            log("=" * 60)
            
            return False
        
        log(f"Step {step_num} VALIDATED - results match within threshold")
        update_status({
            "status": "step_complete",
            "current_step": step_num,
            "result": "MATCH"
        })
    
    # All steps completed successfully
    log("")
    log("=" * 60)
    log("ALL STEPS VALIDATED SUCCESSFULLY!")
    log("HARK 0.14.1 to 0.17.0 migration is validated.")
    log("=" * 60)
    
    update_status({
        "status": "complete",
        "all_steps_validated": True,
        "results": validation_results
    })
    
    if EMAIL_AVAILABLE:
        send_email(
            "HAFiscal Validation: ALL STEPS PASSED",
            "Congratulations!\n\n"
            "The parallel validation of HAFiscal between HARK 0.14.1 and 0.17.0 "
            "has completed successfully. All numerical outputs match within the "
            f"acceptable threshold ({MEANINGFUL_DIFF_THRESHOLD * 100}% log-point difference).\n\n"
            "The HARK migration can be considered validated."
        )
    
    return True


def main():
    parser = argparse.ArgumentParser(description="HAFiscal Parallel Validation")
    parser.add_argument("--start-step", type=int, default=1, help="Step to start from (1-5)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without running")
    
    args = parser.parse_args()
    
    success = run_parallel_validation(
        start_step=args.start_step,
        dry_run=args.dry_run
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
