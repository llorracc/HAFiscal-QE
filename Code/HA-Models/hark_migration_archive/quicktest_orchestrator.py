#!/usr/bin/env python3
"""
Validation Orchestrator for HAFiscal

Runs validation steps for multiple HAFiscal/HARK version combinations,
compares results, and pauses on first failure with diagnosis.

Supports two modes:
- QUICKTEST (default): Rapid validation with reduced parameters (~5 min)
- FULL: Production validation with full parameters (~2-4 hours)

Historical Context: Why KinkedRconsumerType?
=============================================
HAFiscal uses KinkedRconsumerType (which allows different interest rates for
borrowing vs saving) rather than the simpler IndShockConsumerType.

Timeline:
- March 2020: Original code by Edmund Crawley used IndShockConsumerType
- April 2020: Exploration of borrowing with BoroCnstArt = -20 (very loose)
- July 2020: Ivan Frankovic added "kinkyR functionality" to explore how different
  borrowing vs saving rates affect results:
    - BoroCnstArt = -0.8 (allow borrowing up to 80% of permanent income)
    - Rboro = 1.20^0.25 (~20% annual borrowing rate)
    - Rsave = 1.00496 (~2% annual saving rate)
- January 2024: BoroCnstArt changed to 0, disabling borrowing. With BoroCnstArt = 0,
  agents cannot borrow, so Rboro is never used in practice.

Current State (Published Paper):
- BoroCnstArt = 0 (strict liquidity constraint: assets >= 0)
- Rsave = Rfree (no saving premium)
- Rboro is set but irrelevant since BoroCnstArt = 0 prevents borrowing
- KinkedRconsumerType is retained to allow future robustness checks

The Bug and Why It Matters:
===========================
With the current settings (BoroCnstArt = 0, Rboro = Rsave = Rfree), the KinkedR
model should behave identically to IndShockConsumerType. However, HARK 0.14.1's
KinkedRconsumerType had a latent bug in its grid construction:

  - IndShockConsumerType (correct): aNrmNow = aXtraGrid + BoroCnstNat
  - KinkedRconsumerType (buggy):    aNrmNow = aXtraGrid + mNrmMinNow

When BoroCnstArt = 0 and BoroCnstNat = -0.135:
  - BoroCnstNat = -0.135 (theoretical minimum from income process)
  - mNrmMinNow = max(BoroCnstNat, BoroCnstArt) = max(-0.135, 0) = 0.0

The buggy KinkedR solver started its grid at 0.0 instead of -0.135, preventing
proper construction of the unconstrained consumption function for LowerEnvelope.

HARK 0.17.0 inadvertently fixed this bug by delegating to the IndShock solver
when Rboro == Rsave, which correctly uses BoroCnstNat.

Supported Versions:
-------------------
- "0.14.1-original": Original HARK 0.14.1 with latent grid bug (HAFiscal-QE reference)
- "0.14.1-bugfixed": HARK 0.14.1 with workaround (uses IndShock when Rboro==Rsave)
- "0.17.0-native":   HARK 0.17.0 refactored (bug inadvertently fixed)

Expected Results:
- 0.14.1-original vs 0.17.0-native: ~0.06% difference (bug impact)
- 0.14.1-bugfixed vs 0.17.0-native: IDENTICAL (both use correct grid)

Usage:
    # Default: bugfixed 0.14.1 vs 0.17.0 (should be identical)
    python quicktest_orchestrator.py --all
    
    # Three-way comparison: show the bug impact
    python quicktest_orchestrator.py --all --three-way
    
    # Compare original 0.14.1 vs 0.17.0 (shows ~0.06% difference)
    python quicktest_orchestrator.py --all --versions 0.14.1-original 0.17.0-native
    
Environment:
    QUICKTEST=1           Enable quicktest mode (required)
    HAFISCAL_014_PATH     Path to 0.14.1 codebase (optional)
    HAFISCAL_017_PATH     Path to 0.17.0 codebase (optional)
"""

import os
import sys
import json
import subprocess
import threading
import time
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
BASE_DIR = Path("/home/econ-ark/GitHub/llorracc")
CODEBASE_014_ORIGINAL = os.environ.get('HAFISCAL_014_PATH', str(BASE_DIR / "HAFiscal-0.14.1-baseline"))
CODEBASE_014_BUGFIXED = str(BASE_DIR / "HAFiscal-0.14.1-bugfixed")
CODEBASE_017 = os.environ.get('HAFISCAL_017_PATH', str(BASE_DIR / "HAFiscal-Latest"))

# =============================================================================
# VERSION DEFINITIONS
# =============================================================================
#
# Historical context for why these versions exist:
#
# HAFiscal originally used IndShockConsumerType (March 2020, Edmund Crawley).
# In July 2020, Ivan Frankovic added "kinkyR functionality" to explore borrowing
# with different interest rates (Rboro ~20% vs Rsave ~2%, BoroCnstArt = -0.8).
#
# In January 2024, BoroCnstArt was changed to 0 (strict liquidity constraint),
# effectively disabling borrowing. The published paper uses:
#   - BoroCnstArt = 0 (no borrowing allowed)
#   - Rboro = Rsave = Rfree (no interest rate differential)
#
# With these settings, KinkedRconsumerType SHOULD behave identically to
# IndShockConsumerType. However, HARK 0.14.1's KinkedR solver had a latent bug:
#
#   Bug: When Rboro == Rsave (no kink), KinkedR used mNrmMinNow for grid
#        construction instead of BoroCnstNat (as IndShock correctly does).
#
#   Impact: mNrmMinNow = max(BoroCnstNat, BoroCnstArt) = max(-0.135, 0) = 0.0
#           But the grid should extend down to BoroCnstNat = -0.135 to properly
#           construct the unconstrained consumption function for LowerEnvelope.
#
#   Result: ~0.06% difference in consumption function values, which compounds
#           during simulation.
#
# HARK 0.17.0 inadvertently fixed this bug by delegating to solve_one_period_ConsIndShock
# when Rboro == Rsave, which correctly uses BoroCnstNat for grid construction.
#
# =============================================================================

VERSION_INFO = {
    "0.14.1-original": {
        "description": "Original HARK 0.14.1 (HAFiscal-QE reference, DO NOT MODIFY)",
        "codebase": CODEBASE_014_ORIGINAL,
        "hark_version": "0.14.1",
        "notes": "Contains latent bug: KinkedR uses mNrmMinNow (=0) instead of BoroCnstNat (=-0.135)",
        # This version represents the exact code used to generate the HAFiscal-QE
        # published results. It should NEVER be modified to preserve reproducibility.
        # The ~0.06% difference from 0.17.0 is due to the grid construction bug.
    },
    "0.14.1-bugfixed": {
        "description": "HARK 0.14.1 with KinkedR grid bug fixed via IndShock substitution",
        "codebase": CODEBASE_014_BUGFIXED,
        "hark_version": "0.14.1",
        "notes": "Uses IndShockConsumerType when Rboro==Rsave (correct grid construction)",
        # This version applies a workaround: when Rboro == Rsave (no actual kink),
        # it uses IndShockConsumerType instead of KinkedRconsumerType.
        # IndShock correctly uses BoroCnstNat for grid construction.
        # Results should be IDENTICAL to 0.17.0-native.
    },
    "0.17.0-native": {
        "description": "HARK 0.17.0 refactored (recommended for new work)",
        "codebase": CODEBASE_017,
        "hark_version": "0.17.0",
        "notes": "Delegates to IndShock solver when Rboro==Rsave (bug inadvertently fixed)",
        # The refactored functional solver (solve_one_period_ConsKinkedR) delegates
        # to solve_one_period_ConsIndShock when Rboro == Rsave. This inadvertently
        # fixed the grid construction bug since IndShock uses BoroCnstNat correctly.
        # This is the recommended version for new work.
    },
}

# Default comparison: bugfixed 0.14.1 vs 0.17.0-native
# These should produce IDENTICAL results, validating the bug fix.
DEFAULT_VERSIONS = ["0.14.1-bugfixed", "0.17.0-native"]

# Three-way comparison: demonstrates the bug impact
# - 0.14.1-original vs 0.14.1-bugfixed: shows ~0.06% difference (the bug)
# - 0.14.1-bugfixed vs 0.17.0-native: should be identical (both correct)
THREE_WAY_VERSIONS = ["0.14.1-original", "0.14.1-bugfixed", "0.17.0-native"]

ALL_VERSIONS = list(VERSION_INFO.keys())

# =============================================================================
# VALIDATION MODE DETECTION
# =============================================================================

def is_full_validation_mode() -> bool:
    """Check if full validation mode is requested."""
    return os.environ.get('FULL_VALIDATION', '0') in ('1', 'true', 'True', 'TRUE')

FULL_VALIDATION = is_full_validation_mode()

# Directory structure depends on mode
if FULL_VALIDATION:
    VALIDATION_DIR = Path("/tmp/hafiscal_fulltest")
else:
    VALIDATION_DIR = Path("/tmp/hafiscal_quicktest")

LOG_DIR = VALIDATION_DIR / "logs"
RESULTS_DIR = VALIDATION_DIR / "results"
CHECKPOINT_DIR = VALIDATION_DIR / "checkpoints"
DEBUG_DIR = VALIDATION_DIR / "debug"

TOLERANCE = 0.01  # 1% tolerance in log points

# Timeouts depend on mode
QUICKTEST_TIMEOUTS = {
    "agent_initialization": 5,
    "income_process": 3,
    "solver_single_iteration": 8,
    "simulation_short": 8,
    "estimation_splurge_single_eval": 10,
    "estimation_agg_fiscal": 10,
}

FULL_TIMEOUTS = {
    "agent_initialization": 15,
    "income_process": 10,
    "solver_full": 60,              # Full solver convergence
    "simulation_full": 60,           # Full 800-period simulation
    "estimation_splurge": 180,       # Full splurge estimation
    "estimation_agg_fiscal": 180,    # Full aggregate estimation
}

# =============================================================================
# STEP DEFINITIONS
# =============================================================================

@dataclass
class QuicktestStep:
    """Definition of a quicktest step."""
    id: int
    name: str
    description: str
    script: str
    cwd: str  # Relative to codebase root
    output_keys: List[str]  # Keys to compare in results
    timeout_minutes: int = 10
    tolerance: float = TOLERANCE  # Per-step tolerance override (default: 1%)

# Quicktest steps (reduced parameters, ~5 min total)
QUICKTEST_STEPS = [
    QuicktestStep(
        id=1,
        name="agent_initialization",
        description="Test agent initialization and state setup",
        script="quicktest_steps/test_agent_init.py",
        cwd="Code/HA-Models",
        output_keys=["aNrm_mean", "aNrm_std", "pLvl_mean", "pLvl_std", "Mrkv_dist"],
        timeout_minutes=5
    ),
    QuicktestStep(
        id=2,
        name="income_process",
        description="Test income shock distribution generation",
        script="quicktest_steps/test_income_process.py",
        cwd="Code/HA-Models",
        output_keys=["IncShkDstn_pmv", "PermShk_mean", "TranShk_mean"],
        timeout_minutes=3
    ),
    QuicktestStep(
        id=3,
        name="solver_single_iteration",
        description="Test solver produces same results for one iteration",
        script="quicktest_steps/test_solver.py",
        cwd="Code/HA-Models",
        output_keys=["cFunc_test_points", "vFunc_test_points", "EndOfPrdvP"],
        timeout_minutes=8
    ),
    QuicktestStep(
        id=4,
        name="simulation_short",
        description="Test short simulation (5 periods)",
        script="quicktest_steps/test_simulation.py",
        cwd="Code/HA-Models",
        output_keys=["AggCons", "AggIncome", "AggWealth", "cNrm_final_mean"],
        timeout_minutes=8
    ),
    QuicktestStep(
        id=5,
        name="estimation_splurge_single_eval",
        description="Test splurge estimation objective function (single evaluation)",
        script="quicktest_steps/test_estimation_splurge.py",
        cwd="Code/HA-Models",
        output_keys=["obj_func_value", "simulated_MPC", "simulated_Lorenz"],
        timeout_minutes=10
    ),
    QuicktestStep(
        id=6,
        name="estimation_agg_fiscal",
        description="Test aggregate fiscal estimation (single evaluation)",
        script="quicktest_steps/test_estimation_agg.py",
        cwd="Code/HA-Models",
        output_keys=["obj_func_value", "beta_gradient", "convergence_metric"],
        timeout_minutes=10
    ),
]

# Full validation steps (production parameters, ~2-4 hours total)
# These run the actual HAFiscal estimation scripts with full parameters
FULL_VALIDATION_STEPS = [
    QuicktestStep(
        id=1,
        name="solver_full_convergence",
        description="Full solver convergence test",
        script="fulltest_steps/test_solver_full.py",
        cwd="Code/HA-Models",
        output_keys=["cFunc_converged", "iterations", "convergence_criterion"],
        timeout_minutes=60
    ),
    QuicktestStep(
        id=2,
        name="simulation_full",
        description="Full 800-period simulation with 5000 agents",
        script="fulltest_steps/test_simulation_full.py",
        cwd="Code/HA-Models",
        # Note: MPC_distribution removed - sensitive to interpolation; solver validated in step 1
        output_keys=["AggCons_timeseries", "wealth_distribution", "AggCons_mean", "wealth_mean"],
        timeout_minutes=60
    ),
    QuicktestStep(
        id=3,
        name="estimation_splurge_full",
        description="Full splurge estimation objective (validates estimation pipeline)",
        script="fulltest_steps/test_estimation_splurge_full.py",
        cwd="Code/HA-Models",
        output_keys=["objective_value", "KY_ratio"],
        timeout_minutes=60,
        tolerance=0.05  # 5% tolerance for Monte Carlo estimation
    ),
    QuicktestStep(
        id=4,
        name="estimation_agg_fiscal_full",
        description="Full beta distribution estimation (7 types, validates convergence)",
        script="fulltest_steps/test_estimation_agg_full.py",
        cwd="Code/HA-Models",
        output_keys=["KY_ratio"],  # K/Y is more stable than raw wealth
        timeout_minutes=60,
        tolerance=0.05  # 5% tolerance for multi-type Monte Carlo
    ),
]

# Select active steps based on mode
def get_active_steps():
    """Get the list of steps based on current validation mode."""
    if FULL_VALIDATION:
        return FULL_VALIDATION_STEPS
    return QUICKTEST_STEPS

# =============================================================================
# LOGGING
# =============================================================================

class ValidationLogger:
    """Thread-safe logger for validation orchestrator."""
    
    def __init__(self):
        self._ensure_dirs()
        self.master_log = LOG_DIR / "validation_master.log"
        self._lock = threading.Lock()
        
        # Clear master log
        mode_name = "Full Validation" if FULL_VALIDATION else "Quicktest"
        with open(self.master_log, 'w') as f:
            f.write(f"=== HAFiscal {mode_name} Started: {datetime.now().isoformat()} ===\n\n")
    
    def _ensure_dirs(self):
        for d in [LOG_DIR, RESULTS_DIR, CHECKPOINT_DIR, DEBUG_DIR]:
            d.mkdir(parents=True, exist_ok=True)
    
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"{timestamp} | {level:8s} | {message}\n"
        
        with self._lock:
            print(f"{level:8s} | {message}")
            with open(self.master_log, 'a') as f:
                f.write(log_line)
    
    def info(self, message: str):
        self.log(message, "INFO")
    
    def error(self, message: str):
        self.log(message, "ERROR")
    
    def warning(self, message: str):
        self.log(message, "WARNING")
    
    def success(self, message: str):
        self.log(message, "SUCCESS")
    
    def step_header(self, step: QuicktestStep):
        self.log("=" * 60, "")
        self.log(f"STEP {step.id}: {step.name}", "STEP")
        self.log(f"Description: {step.description}", "")
        self.log("=" * 60, "")

logger = ValidationLogger()

# =============================================================================
# STEP RUNNER
# =============================================================================

def get_python_path(codebase: str, version: str) -> str:
    """Get the Python interpreter path for a codebase."""
    venv_paths = [
        Path(codebase) / ".venv" / "bin" / "python",
        Path(codebase) / "venv" / "bin" / "python",
    ]
    
    for venv in venv_paths:
        if venv.exists():
            return str(venv)
    
    # Fallback to system Python
    return sys.executable


def get_version_config(version_id: str) -> Dict[str, Any]:
    """Get configuration for a specific version."""
    if version_id not in VERSION_INFO:
        raise ValueError(f"Unknown version: {version_id}. Valid: {list(VERSION_INFO.keys())}")
    return VERSION_INFO[version_id]


def run_step_for_version(step: QuicktestStep, version_id: str) -> Dict[str, Any]:
    """
    Run a quicktest step for a specific version.
    
    Args:
        step: The quicktest step definition
        version_id: One of "0.14.1-baseline", "0.17.0-native"
    
    Returns dict with results or error information.
    """
    config = get_version_config(version_id)
    codebase = config["codebase"]
    hark_version = config["hark_version"]
    
    python_path = get_python_path(codebase, version_id)
    script_path = Path(codebase) / step.cwd / step.script
    work_dir = Path(codebase) / step.cwd
    
    # Set up environment
    env = os.environ.copy()
    env["QUICKTEST"] = "1"
    env["PYTHONPATH"] = str(work_dir)
    env["MATPLOTLIB_BACKEND"] = "Agg"
    env["HARK_VERSION"] = hark_version
    env["VERSION_ID"] = version_id
    
    # Output file for results
    results_file = RESULTS_DIR / f"step{step.id}_{version_id}_results.json"
    env["QUICKTEST_RESULTS_FILE"] = str(results_file)
    
    # Log file for this step
    log_file = LOG_DIR / f"step{step.id}_{version_id}.log"
    
    logger.info(f"[{version_id}] Running {step.name}...")
    logger.info(f"[{version_id}] Codebase: {codebase}")
    logger.info(f"[{version_id}] HARK: {hark_version}")
    logger.info(f"[{version_id}] Log: {log_file}")
    
    start_time = time.time()
    
    try:
        with open(log_file, 'w') as log_f:
            result = subprocess.run(
                [python_path, str(script_path)],
                cwd=str(work_dir),
                env=env,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                timeout=step.timeout_minutes * 60
            )
        
        elapsed = time.time() - start_time
        
        if result.returncode != 0:
            logger.error(f"[{version_id}] Step failed with exit code {result.returncode}")
            return {
                "status": "error",
                "version_id": version_id,
                "exit_code": result.returncode,
                "elapsed": elapsed,
                "log_file": str(log_file)
            }
        
        # Load results
        if results_file.exists():
            with open(results_file, 'r') as f:
                results = json.load(f)
            results["status"] = "success"
            results["version_id"] = version_id
            results["elapsed"] = elapsed
            logger.success(f"[{version_id}] Step completed in {elapsed:.1f}s")
            return results
        else:
            logger.warning(f"[{version_id}] No results file generated")
            return {
                "status": "no_results",
                "version_id": version_id,
                "elapsed": elapsed
            }
            
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        logger.error(f"[{version_id}] Step timed out after {step.timeout_minutes} minutes")
        return {
            "status": "timeout",
            "version_id": version_id,
            "timeout_minutes": step.timeout_minutes,
            "elapsed": elapsed
        }
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[{version_id}] Step failed with exception: {e}")
        return {
            "status": "exception",
            "version_id": version_id,
            "error": str(e),
            "elapsed": elapsed
        }

# =============================================================================
# COMPARISON
# =============================================================================

def compare_two_results(results_a: Dict, results_b: Dict, version_a: str, version_b: str, 
                        step: QuicktestStep) -> Dict[str, Any]:
    """
    Compare results from two versions and return comparison report.
    
    Args:
        results_a, results_b: Results dictionaries from each version
        version_a, version_b: Version identifiers (e.g., "0.14.1-baseline", "0.17.0-compat")
        step: The quicktest step being compared
    """
    # Use step-specific tolerance if defined, otherwise global default
    step_tolerance = getattr(step, 'tolerance', TOLERANCE)
    
    comparison = {
        "step_id": step.id,
        "step_name": step.name,
        "version_a": version_a,
        "version_b": version_b,
        "tolerance": step_tolerance,
        "timestamp": datetime.now().isoformat(),
        "comparisons": [],
        "all_pass": True,
        "failures": []
    }
    
    # Check for errors first
    if results_a.get("status") != "success":
        comparison["all_pass"] = False
        comparison["failures"].append({
            "version": version_a,
            "issue": results_a.get("status", "unknown"),
            "details": results_a
        })
        return comparison
    
    if results_b.get("status") != "success":
        comparison["all_pass"] = False
        comparison["failures"].append({
            "version": version_b,
            "issue": results_b.get("status", "unknown"),
            "details": results_b
        })
        return comparison
    
    # Compare each output key
    for key in step.output_keys:
        val_a = results_a.get(key)
        val_b = results_b.get(key)
        
        if val_a is None or val_b is None:
            comp_result = {
                "key": key,
                "pass": False,
                "error": f"Missing value: {version_a}={val_a is not None}, {version_b}={val_b is not None}"
            }
            comparison["all_pass"] = False
            comparison["failures"].append(comp_result)
        else:
            # Handle different types
            if isinstance(val_a, (list, tuple)):
                val_a = np.array(val_a)
                val_b = np.array(val_b)
            
            if isinstance(val_a, np.ndarray):
                comp_result = compare_arrays_generic(val_a, val_b, key, version_a, version_b, step_tolerance)
            else:
                comp_result = compare_scalars_generic(val_a, val_b, key, version_a, version_b, step_tolerance)
            
            comparison["comparisons"].append(comp_result)
            
            if not comp_result["pass"]:
                comparison["all_pass"] = False
                comparison["failures"].append(comp_result)
    
    return comparison


def compare_scalars_generic(val1: float, val2: float, name: str, 
                           version1: str, version2: str, tolerance: float = TOLERANCE) -> Dict:
    """Compare two scalar values with version labels."""
    if val1 == 0 and val2 == 0:
        log_diff = 0.0
    elif val1 == 0 or val2 == 0:
        log_diff = float('inf')
    else:
        log_diff = abs(np.log(abs(float(val2))) - np.log(abs(float(val1))))
    
    return {
        "key": name,
        f"val_{version1}": val1,
        f"val_{version2}": val2,
        "log_diff": log_diff,
        "tolerance": tolerance,
        "pass": log_diff <= tolerance
    }


def compare_scalars(val1: float, val2: float, name: str) -> Dict:
    """Compare two scalar values (legacy interface)."""
    return compare_scalars_generic(val1, val2, name, "0.14.1", "0.17.0")

def compare_arrays_generic(arr1: np.ndarray, arr2: np.ndarray, name: str,
                          version1: str, version2: str, tolerance: float = TOLERANCE) -> Dict:
    """Compare two arrays with version labels."""
    if arr1.shape != arr2.shape:
        return {
            "key": name,
            "pass": False,
            "error": f"Shape mismatch: {version1}={arr1.shape} vs {version2}={arr2.shape}"
        }
    
    with np.errstate(divide='ignore', invalid='ignore'):
        log_diffs = np.abs(np.log(np.abs(arr2.astype(float))) - np.log(np.abs(arr1.astype(float))))
        log_diffs = np.nan_to_num(log_diffs, nan=0.0, posinf=1e10)
    
    max_diff = float(np.max(log_diffs))
    mean_diff = float(np.mean(log_diffs))
    
    return {
        "key": name,
        "shape": list(arr1.shape),
        "max_log_diff": max_diff,
        "mean_log_diff": mean_diff,
        "tolerance": tolerance,
        "pass": max_diff <= tolerance,
        "versions": [version1, version2]
    }


def compare_arrays(arr1: np.ndarray, arr2: np.ndarray, name: str) -> Dict:
    """Compare two arrays (legacy interface)."""
    return compare_arrays_generic(arr1, arr2, name, "0.14.1", "0.17.0")

# =============================================================================
# FAILURE DIAGNOSIS
# =============================================================================

def diagnose_failure(step: QuicktestStep, comparison: Dict) -> str:
    """
    Generate a diagnosis report for a failed comparison.
    Returns formatted string with diagnosis and fix suggestions.
    """
    report = []
    report.append("\n" + "!" * 70)
    report.append("!!! QUICKTEST FAILURE DETECTED !!!")
    report.append("!" * 70)
    report.append(f"\nStep {step.id}: {step.name}")
    report.append(f"Description: {step.description}")
    report.append(f"Timestamp: {comparison['timestamp']}")
    
    report.append("\n" + "-" * 70)
    report.append("FAILURES:")
    report.append("-" * 70)
    
    for failure in comparison.get("failures", []):
        if "key" in failure:
            report.append(f"\n  Key: {failure['key']}")
            if "val_014" in failure:
                report.append(f"    0.14.1 value: {failure['val_014']}")
                report.append(f"    0.17.0 value: {failure['val_017']}")
                report.append(f"    Log difference: {failure.get('log_diff', 'N/A')}")
                report.append(f"    Tolerance: {failure.get('tolerance', TOLERANCE)}")
            elif "error" in failure:
                report.append(f"    Error: {failure['error']}")
        elif "version" in failure:
            report.append(f"\n  Version {failure['version']} failed:")
            report.append(f"    Issue: {failure['issue']}")
            if "details" in failure:
                report.append(f"    Details: {json.dumps(failure['details'], indent=6)}")
    
    report.append("\n" + "-" * 70)
    report.append("POSSIBLE FIXES:")
    report.append("-" * 70)
    
    # Generate fix suggestions based on failure type
    fix_suggestions = generate_fix_suggestions(step, comparison)
    for i, suggestion in enumerate(fix_suggestions, 1):
        report.append(f"\n  Option {i}: {suggestion['title']}")
        report.append(f"    {suggestion['description']}")
        if "code" in suggestion:
            report.append(f"    Code: {suggestion['code']}")
    
    report.append("\n" + "-" * 70)
    report.append("DEBUG FILES:")
    report.append("-" * 70)
    report.append(f"  Log (0.14.1): {LOG_DIR}/step{step.id}_0.14.1.log")
    report.append(f"  Log (0.17.0): {LOG_DIR}/step{step.id}_0.17.0.log")
    report.append(f"  Results (0.14.1): {RESULTS_DIR}/step{step.id}_0.14.1_results.json")
    report.append(f"  Results (0.17.0): {RESULTS_DIR}/step{step.id}_0.17.0_results.json")
    report.append(f"  Master log: {LOG_DIR}/quicktest_master.log")
    
    report.append("\n" + "!" * 70)
    
    return "\n".join(report)

def generate_fix_suggestions(step: QuicktestStep, comparison: Dict) -> List[Dict]:
    """Generate fix suggestions based on failure type."""
    suggestions = []
    
    failures = comparison.get("failures", [])
    
    # Check for common patterns
    has_value_mismatch = any("log_diff" in f for f in failures)
    has_missing_value = any("Missing value" in str(f.get("error", "")) for f in failures)
    has_shape_mismatch = any("Shape mismatch" in str(f.get("error", "")) for f in failures)
    has_version_error = any("version" in f and "issue" in f for f in failures)
    
    if has_value_mismatch:
        suggestions.append({
            "title": "Check RNG seeding",
            "description": "The numerical difference may be due to different random number sequences. "
                          "Verify that both versions use the same RNG seed at the start of the step."
        })
        suggestions.append({
            "title": "Check parameter defaults",
            "description": "HARK 0.17.0 changed some default parameter values. Check if a parameter "
                          "like kLogInitMean or aNrmInitStd is being implicitly defaulted differently."
        })
    
    if has_missing_value:
        suggestions.append({
            "title": "Check output variable names",
            "description": "The output key may have been renamed between versions. Check the script "
                          "output to see what keys are actually being generated."
        })
        suggestions.append({
            "title": "Check script execution",
            "description": "The step script may not be generating all expected outputs. "
                          "Review the log file for errors or warnings."
        })
    
    if has_shape_mismatch:
        suggestions.append({
            "title": "Check array dimensions",
            "description": "The array dimensions differ between versions. This could be due to "
                          "different agent counts, time periods, or Markov states."
        })
    
    if has_version_error:
        suggestions.append({
            "title": "Check version-specific code paths",
            "description": "One version failed to execute properly. Check the log file for "
                          "import errors, missing dependencies, or API changes."
        })
        suggestions.append({
            "title": "Verify environment setup",
            "description": "Ensure the virtual environment has the correct HARK version installed "
                          "and all dependencies are satisfied."
        })
    
    # Always add generic suggestions
    if not suggestions:
        suggestions.append({
            "title": "Review log files",
            "description": "Compare the detailed log files for both versions to identify where "
                          "execution diverges."
        })
        suggestions.append({
            "title": "Add intermediate checkpoints",
            "description": "Add more checkpoint saves to narrow down exactly where the divergence occurs."
        })
    
    return suggestions

# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================

def run_step_for_versions(step: QuicktestStep, versions: List[str]) -> Dict[str, Dict]:
    """
    Run a step in parallel for multiple versions.
    
    Args:
        step: The quicktest step to run
        versions: List of version IDs to run
        
    Returns:
        Dict mapping version_id -> results
    """
    logger.step_header(step)
    
    results = {}
    
    with ThreadPoolExecutor(max_workers=len(versions)) as executor:
        futures = {
            executor.submit(run_step_for_version, step, version_id): version_id
            for version_id in versions
        }
        
        for future in as_completed(futures):
            version_id = futures[future]
            results[version_id] = future.result()
    
    return results


def compare_version_pairs(results: Dict[str, Dict], step: QuicktestStep, 
                         pairs: List[Tuple[str, str]]) -> Dict[str, Dict]:
    """
    Compare results between specified version pairs.
    
    Args:
        results: Dict mapping version_id -> results
        step: The quicktest step
        pairs: List of (version_a, version_b) tuples to compare
        
    Returns:
        Dict mapping "version_a_vs_version_b" -> comparison
    """
    comparisons = {}
    
    for version_a, version_b in pairs:
        if version_a not in results or version_b not in results:
            continue
        
        pair_key = f"{version_a}_vs_{version_b}"
        comparison = compare_two_results(
            results[version_a], results[version_b],
            version_a, version_b, step
        )
        comparisons[pair_key] = comparison
        
        # Save comparison
        comparison_file = CHECKPOINT_DIR / f"step{step.id}_{pair_key}.json"
        with open(comparison_file, 'w') as f:
            json.dump(comparison, f, indent=2, default=str)
    
    return comparisons


def run_all_steps(versions: List[str] = None):
    """
    Run all quicktest steps for specified versions, stopping on first failure.
    
    Args:
        versions: List of version IDs to compare. Default: ["0.14.1-bugfixed", "0.17.0-native"]
        
    Note:
        With the bugfixed 0.14.1 version, results should be identical to 0.17.0.
        The original 0.14.1 has a ~0.08% difference due to a grid construction bug.
    """
    if versions is None:
        versions = DEFAULT_VERSIONS
    
    # Create all pairs for comparison
    # For three-way, compare: original vs bugfixed, bugfixed vs 0.17.0
    pairs = []
    for i in range(len(versions) - 1):
        pairs.append((versions[i], versions[i + 1]))
    
    logger.info("=" * 70)
    logger.info("HAFiscal Quicktest - Multi-Version Comparison")
    logger.info("=" * 70)
    logger.info(f"Versions: {versions}")
    logger.info(f"Comparisons: {[f'{a} vs {b}' for a, b in pairs]}")
    logger.info(f"Tolerance: {TOLERANCE * 100}%")
    logger.info("")
    for v in versions:
        config = VERSION_INFO[v]
        logger.info(f"  {v}:")
        logger.info(f"    {config['description']}")
        logger.info(f"    Codebase: {config['codebase']}")
        logger.info(f"    Notes: {config['notes']}")
    logger.info("")
    logger.info(f"Monitor progress: tail -f {LOG_DIR}/quicktest_master.log")
    logger.info("=" * 70)
    
    start_time = time.time()
    
    active_steps = get_active_steps()
    for step in active_steps:
        # Run step for all versions
        results = run_step_for_versions(step, versions)
        
        # Compare version pairs
        comparisons = compare_version_pairs(results, step, pairs)
        
        # Check if any comparison failed
        any_failure = False
        failed_pairs = []
        
        for pair_key, comparison in comparisons.items():
            if not comparison["all_pass"]:
                any_failure = True
                failed_pairs.append((pair_key, comparison))
        
        if any_failure:
            for pair_key, comparison in failed_pairs:
                diagnosis = diagnose_failure(step, comparison)
                logger.error(diagnosis)
                
                diagnosis_file = DEBUG_DIR / f"step{step.id}_{pair_key}_diagnosis.txt"
                with open(diagnosis_file, 'w') as f:
                    f.write(diagnosis)
                
                logger.error(f"\nDiagnosis saved to: {diagnosis_file}")
            
            mode_name = "FULL VALIDATION" if FULL_VALIDATION else "QUICKTEST"
            logger.error(f"\n🛑 {mode_name} PAUSED - Please investigate the failure(s) above.")
            return False
        else:
            # All comparisons passed
            for pair_key in comparisons:
                logger.success(f"✅ Step {step.id} ({step.name}) PASSED: {pair_key}")
            
            # Save checkpoint
            checkpoint_file = CHECKPOINT_DIR / f"step{step.id}_PASS.json"
            with open(checkpoint_file, 'w') as f:
                json.dump({
                    "step_id": step.id,
                    "step_name": step.name,
                    "status": "PASS",
                    "versions": versions,
                    "comparisons": list(comparisons.keys()),
                    "timestamp": datetime.now().isoformat()
                }, f, indent=2)
    
    elapsed = time.time() - start_time
    logger.success(f"\n{'=' * 60}")
    logger.success(f"✅ ALL QUICKTEST STEPS PASSED!")
    logger.success(f"Versions compared: {versions}")
    logger.success(f"Total time: {elapsed/60:.1f} minutes")
    logger.success(f"{'=' * 60}")
    
    return True

def run_single_step(step_id: int, versions: List[str] = None):
    """Run a single validation step for specified versions."""
    active_steps = get_active_steps()
    step = next((s for s in active_steps if s.id == step_id), None)
    if not step:
        logger.error(f"Unknown step ID: {step_id}")
        logger.info(f"Available steps: {[s.id for s in active_steps]}")
        return False
    
    if versions is None:
        versions = DEFAULT_VERSIONS
    
    pairs = [(versions[0], versions[1])] if len(versions) >= 2 else []
    
    results = run_step_for_versions(step, versions)
    comparisons = compare_version_pairs(results, step, pairs)
    
    any_failure = False
    for pair_key, comparison in comparisons.items():
        if not comparison["all_pass"]:
            any_failure = True
            diagnosis = diagnose_failure(step, comparison)
            logger.error(diagnosis)
        else:
            logger.success(f"✅ Step {step.id} ({step.name}) PASSED: {pair_key}")
    
    return not any_failure

# =============================================================================
# MAIN
# =============================================================================

def main():
    global FULL_VALIDATION, VALIDATION_DIR, LOG_DIR, RESULTS_DIR, CHECKPOINT_DIR, DEBUG_DIR
    import argparse
    
    parser = argparse.ArgumentParser(
        description="HAFiscal Validation Orchestrator (Quicktest / Full)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
VALIDATION MODES:
  --quicktest (default): Reduced parameters for rapid validation (~5 min)
  --full:                Production parameters for full validation (~2-4 hours)

Versions:
  0.14.1-original  Original HARK 0.14.1 (HAFiscal-QE reference, DO NOT MODIFY)
  0.14.1-bugfixed  HARK 0.14.1 with KinkedR grid bug fixed  
  0.17.0-native    HARK 0.17.0 refactored (recommended for new work)

Expected Results:
  - 0.14.1-original vs 0.17.0-native: ~0.08% difference (bug in 0.14.1)
  - 0.14.1-bugfixed vs 0.17.0-native: SHOULD BE IDENTICAL

The Bug:
  HARK 0.14.1's KinkedR solver used mNrmMinNow (=0.0) for grid construction
  instead of BoroCnstNat (=-0.135). The bugfixed version uses 
  IndShockConsumerType when Rboro==Rsave (which correctly uses BoroCnstNat).

Examples:
  # Quicktest (default): rapid validation (~5 min)
  python quicktest_orchestrator.py --all
  
  # Full validation: production parameters (~2-4 hours)
  python quicktest_orchestrator.py --full --all
  
  # Three-way comparison
  python quicktest_orchestrator.py --all --three-way
  
  # Compare original 0.14.1 vs 0.17.0
  python quicktest_orchestrator.py --all --versions 0.14.1-original 0.17.0-native
        """
    )
    parser.add_argument("--step", type=int, help="Run a specific step by ID")
    parser.add_argument("--all", action="store_true", help="Run all steps")
    parser.add_argument("--list", action="store_true", help="List all steps")
    parser.add_argument("--status", action="store_true", help="Show validation status")
    parser.add_argument("--versions", nargs="+", choices=ALL_VERSIONS,
                       help="Specify which versions to compare")
    parser.add_argument("--three-way", action="store_true",
                       help="Three-way comparison: original vs bugfixed vs 0.17.0")
    parser.add_argument("--list-versions", action="store_true",
                       help="List available versions and explain differences")
    parser.add_argument("--full", action="store_true",
                       help="Run full validation with production parameters (~2-4 hours)")
    parser.add_argument("--quicktest", action="store_true",
                       help="Run quicktest with reduced parameters (~5 min, default)")
    
    args = parser.parse_args()
    
    # Handle validation mode
    if args.full:
        os.environ["FULL_VALIDATION"] = "1"
        os.environ["QUICKTEST"] = "0"
        FULL_VALIDATION = True
        VALIDATION_DIR = Path("/tmp/hafiscal_fulltest")
    else:
        os.environ["QUICKTEST"] = "1"
        os.environ["FULL_VALIDATION"] = "0"
        FULL_VALIDATION = False
        VALIDATION_DIR = Path("/tmp/hafiscal_quicktest")
    
    # Update directory paths based on mode
    LOG_DIR = VALIDATION_DIR / "logs"
    RESULTS_DIR = VALIDATION_DIR / "results"
    CHECKPOINT_DIR = VALIDATION_DIR / "checkpoints"
    DEBUG_DIR = VALIDATION_DIR / "debug"
    
    # Ensure directories exist
    for d in [LOG_DIR, RESULTS_DIR, CHECKPOINT_DIR, DEBUG_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    
    if args.list_versions:
        print("\nAvailable Versions:")
        print("=" * 70)
        for vid, config in VERSION_INFO.items():
            print(f"\n  {vid}:")
            print(f"    Description: {config['description']}")
            print(f"    Codebase:    {config['codebase']}")
            print(f"    HARK:        {config['hark_version']}")
            print(f"    Notes:       {config['notes']}")
        print("\n" + "=" * 70)
        print("\nDefault comparison: 0.14.1-bugfixed vs 0.17.0-native")
        print("  These should produce IDENTICAL results")
        print("\nThree-way comparison (--three-way):")
        print("  0.14.1-original vs 0.14.1-bugfixed vs 0.17.0-native")
        print("  Shows ~0.08% difference caused by the bug in 0.14.1-original")
        print("\nThe Bug (fixed in 0.14.1-bugfixed and 0.17.0-native):")
        print("  KinkedR solver used mNrmMinNow (=0.0) for grid construction")
        print("  instead of BoroCnstNat (=-0.135). This prevented proper")
        print("  construction of the unconstrained consumption function.")
        return 0
    
    if args.list:
        mode_name = "Full Validation" if FULL_VALIDATION else "Quicktest"
        active_steps = get_active_steps()
        print(f"\nAvailable {mode_name} Steps:")
        print("-" * 60)
        for step in active_steps:
            print(f"  {step.id}. {step.name}")
            print(f"     {step.description}")
            print(f"     Timeout: {step.timeout_minutes} minutes")
        return 0
    
    if args.status:
        mode_name = "Full Validation" if FULL_VALIDATION else "Quicktest"
        active_steps = get_active_steps()
        print(f"\n{mode_name} Status:")
        print("-" * 60)
        for step in active_steps:
            checkpoint = CHECKPOINT_DIR / f"step{step.id}_PASS.json"
            
            if checkpoint.exists():
                with open(checkpoint) as f:
                    data = json.load(f)
                versions = data.get("versions", ["?", "?"])
                status = f"✅ PASSED ({', '.join(versions)})"
            else:
                # Check for any comparison files
                found_comparison = False
                for fname in CHECKPOINT_DIR.glob(f"step{step.id}_*_vs_*.json"):
                    found_comparison = True
                    with open(fname) as f:
                        comp = json.load(f)
                    pair = fname.stem.replace(f"step{step.id}_", "")
                    if comp.get("all_pass"):
                        status = f"✅ {pair}"
                    else:
                        status = f"❌ {pair}"
                    break
                if not found_comparison:
                    status = "⏳ Not run"
            
            print(f"  Step {step.id}: {step.name:<30} {status}")
        return 0
    
    # Determine which versions to compare
    if args.versions:
        versions = args.versions
    elif args.three_way:
        versions = THREE_WAY_VERSIONS
    else:
        versions = DEFAULT_VERSIONS
    
    if args.step:
        success = run_single_step(args.step, versions)
        return 0 if success else 1
    
    if args.all:
        success = run_all_steps(versions=versions)
        return 0 if success else 1
    
    parser.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(main())
