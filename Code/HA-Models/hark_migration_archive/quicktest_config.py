"""
Quicktest Configuration for HAFiscal

This module provides shared configuration for quicktest mode, which allows
rapid validation of computational machinery without running full optimizations.

Quicktest mode is activated by:
- Command line: --quicktest flag
- Environment: QUICKTEST=1

Usage:
    from quicktest_config import QUICKTEST, quicktest_params, setup_quicktest_logging
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# =============================================================================
# VALIDATION MODE DETECTION
# =============================================================================

def is_quicktest_mode() -> bool:
    """Check if quicktest mode is enabled via environment or CLI."""
    # Check environment variable
    if os.environ.get('QUICKTEST', '0') in ('1', 'true', 'True', 'TRUE'):
        return True
    # Check command line arguments
    if '--quicktest' in sys.argv:
        return True
    return False

def is_full_validation_mode() -> bool:
    """Check if full validation mode is enabled via environment or CLI."""
    # Check environment variable
    if os.environ.get('FULL_VALIDATION', '0') in ('1', 'true', 'True', 'TRUE'):
        return True
    # Check command line arguments
    if '--full' in sys.argv:
        return True
    return False

QUICKTEST = is_quicktest_mode()
FULL_VALIDATION = is_full_validation_mode()

# =============================================================================
# PARAMETER CONFIGURATIONS
# =============================================================================

# Full production parameters (used by actual HAFiscal estimation)
FULL_PARAMS = {
    # Simulation parameters (from Estimation_BetaNablaSplurge.py)
    'T_sim': 800,             # Full simulation length
    'AgentCount': 5000,       # Full agent count
    'T_age': 400,             # Full agent lifespan
    
    # Optimization parameters
    'max_optimizer_iter': 1000,  # Full optimizer iterations
    'optimizer_ftol': 1e-8,      # Tight tolerance
    'optimizer_xtol': 1e-8,
    
    # Type/distribution parameters
    'TypeCount': 7,           # Full education types
    'DiscFacCount': 7,        # Full discount factor distribution
    
    # Solver parameters
    'solver_max_iter': 50,    # Full solver iterations
    'aXtraCount': 48,         # Full asset grid
}

# Quicktest parameters (reduced for rapid validation)
QUICKTEST_PARAMS = {
    # Simulation parameters
    'T_sim': 10,              # Normal: 800, Quicktest: 10 periods
    'AgentCount': 200,        # Normal: 5000, Quicktest: 200 agents
    'T_age': 50,              # Normal: 400, Quicktest: 50
    
    # Optimization parameters
    'max_optimizer_iter': 3,  # Normal: 1000+, Quicktest: 3 iterations
    'optimizer_ftol': 1e-2,   # Looser tolerance for quick convergence
    'optimizer_xtol': 1e-2,
    
    # Type/distribution parameters
    'TypeCount': 2,           # Normal: 7, Quicktest: 2 types
    'DiscFacCount': 3,        # Normal: 7, Quicktest: 3 discount factors
    
    # Solver parameters
    'solver_max_iter': 5,     # Max solver iterations in quicktest
    'aXtraCount': 24,         # Reduced asset grid (normal: 48)
}

# Tolerance for numerical comparisons (1% = 0.01 log points)
COMPARISON_TOLERANCE = 0.01

# =============================================================================
# DIRECTORY STRUCTURE
# =============================================================================

QUICKTEST_BASE_DIR = Path('/tmp/hafiscal_quicktest')
QUICKTEST_DIRS = {
    'checkpoints': QUICKTEST_BASE_DIR / 'checkpoints',
    'logs': QUICKTEST_BASE_DIR / 'logs',
    'debug': QUICKTEST_BASE_DIR / 'debug',
    'results': QUICKTEST_BASE_DIR / 'results',
}

def ensure_quicktest_dirs():
    """Create quicktest directory structure."""
    for dir_path in QUICKTEST_DIRS.values():
        dir_path.mkdir(parents=True, exist_ok=True)
    return QUICKTEST_DIRS

# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_quicktest_logging(script_name: str, version: str = 'unknown') -> logging.Logger:
    """
    Set up logging for quicktest mode with both file and console output.
    
    Args:
        script_name: Name of the script (e.g., 'Estimation_BetaNablaSplurge')
        version: HARK version ('0.14.1' or '0.17.0')
    
    Returns:
        Logger instance configured for quicktest
    """
    ensure_quicktest_dirs()
    
    # Create logger
    logger = logging.getLogger(f'quicktest.{script_name}')
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler - detailed log
    log_file = QUICKTEST_DIRS['logs'] / f'{script_name}_{version}.log'
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # Console handler - important messages only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(levelname)-8s | %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # Also update master log
    master_log = QUICKTEST_DIRS['logs'] / 'quicktest_master.log'
    master_handler = logging.FileHandler(master_log, mode='a')
    master_handler.setLevel(logging.INFO)
    master_format = logging.Formatter(
        '%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    master_handler.setFormatter(master_format)
    logger.addHandler(master_handler)
    
    logger.info(f"Quicktest logging initialized for {script_name} (HARK {version})")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Master log: {master_log}")
    
    return logger

# =============================================================================
# CHECKPOINT MANAGEMENT
# =============================================================================

class QuicktestCheckpoint:
    """Manage quicktest checkpoints for tracking progress and results."""
    
    def __init__(self, step_name: str, version: str):
        self.step_name = step_name
        self.version = version
        self.checkpoint_dir = QUICKTEST_DIRS['checkpoints']
        self.debug_dir = QUICKTEST_DIRS['debug']
        self.results_dir = QUICKTEST_DIRS['results']
        ensure_quicktest_dirs()
        
    def _get_checkpoint_path(self, suffix: str = 'complete') -> Path:
        return self.checkpoint_dir / f'{self.step_name}_{self.version}_{suffix}.json'
    
    def save_checkpoint(self, data: Dict[str, Any], status: str = 'complete'):
        """Save a checkpoint with results and metadata."""
        checkpoint = {
            'step_name': self.step_name,
            'version': self.version,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        
        checkpoint_path = self._get_checkpoint_path(status)
        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint, f, indent=2, default=str)
        
        return checkpoint_path
    
    def load_checkpoint(self, status: str = 'complete') -> Optional[Dict[str, Any]]:
        """Load a checkpoint if it exists."""
        checkpoint_path = self._get_checkpoint_path(status)
        if checkpoint_path.exists():
            with open(checkpoint_path, 'r') as f:
                return json.load(f)
        return None
    
    def save_debug_state(self, state: Any, error_msg: str = ''):
        """Save intermediate state for debugging on failure."""
        import pickle
        
        debug_path = self.debug_dir / f'{self.step_name}_{self.version}_state.pkl'
        with open(debug_path, 'wb') as f:
            pickle.dump(state, f)
        
        # Also save error info
        error_info = {
            'step_name': self.step_name,
            'version': self.version,
            'error': error_msg,
            'timestamp': datetime.now().isoformat(),
            'debug_state_path': str(debug_path)
        }
        
        error_path = self.debug_dir / f'{self.step_name}_{self.version}_error.json'
        with open(error_path, 'w') as f:
            json.dump(error_info, f, indent=2)
        
        return debug_path, error_path
    
    def save_results(self, results: Dict[str, Any]):
        """Save numerical results for comparison."""
        results_path = self.results_dir / f'{self.step_name}_{self.version}_results.json'
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        return results_path

# =============================================================================
# PARAMETER OVERRIDE HELPER
# =============================================================================

def get_active_params() -> Dict[str, Any]:
    """
    Get the active parameter set based on validation mode.
    
    Returns:
        FULL_PARAMS if in full validation mode
        QUICKTEST_PARAMS if in quicktest mode
        FULL_PARAMS otherwise (production default)
    """
    if FULL_VALIDATION:
        return FULL_PARAMS
    elif QUICKTEST:
        return QUICKTEST_PARAMS
    else:
        return FULL_PARAMS

def get_quicktest_param(param_name: str, normal_value: Any) -> Any:
    """
    Get parameter value, using quicktest override if in quicktest mode.
    
    Args:
        param_name: Name of the parameter
        normal_value: Normal (non-quicktest) value
        
    Returns:
        Quicktest value if QUICKTEST mode, else normal_value
    """
    if QUICKTEST and param_name in QUICKTEST_PARAMS:
        return QUICKTEST_PARAMS[param_name]
    return normal_value

def apply_quicktest_overrides(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply quicktest parameter overrides to a parameter dictionary.
    
    Args:
        params: Original parameter dictionary
        
    Returns:
        Modified dictionary with quicktest overrides applied
    """
    if not QUICKTEST:
        return params
    
    result = params.copy()
    for key, quicktest_value in QUICKTEST_PARAMS.items():
        if key in result:
            result[key] = quicktest_value
    
    return result

# =============================================================================
# COMPARISON UTILITIES
# =============================================================================

import numpy as np

def compare_values(val1: float, val2: float, name: str = 'value') -> Dict[str, Any]:
    """
    Compare two numerical values and check if within tolerance.
    
    Returns dict with comparison details.
    """
    if val1 == 0 and val2 == 0:
        log_diff = 0.0
    elif val1 == 0 or val2 == 0:
        log_diff = float('inf')
    else:
        log_diff = abs(np.log(abs(val2)) - np.log(abs(val1)))
    
    pct_diff = 100 * (val2 - val1) / val1 if val1 != 0 else float('inf')
    is_pass = log_diff <= COMPARISON_TOLERANCE
    
    return {
        'name': name,
        'val1': val1,
        'val2': val2,
        'log_diff': log_diff,
        'pct_diff': pct_diff,
        'tolerance': COMPARISON_TOLERANCE,
        'pass': is_pass
    }

def compare_arrays(arr1: np.ndarray, arr2: np.ndarray, name: str = 'array') -> Dict[str, Any]:
    """Compare two arrays element-wise and return summary statistics."""
    if arr1.shape != arr2.shape:
        return {
            'name': name,
            'pass': False,
            'error': f'Shape mismatch: {arr1.shape} vs {arr2.shape}'
        }
    
    # Avoid division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        log_diffs = np.abs(np.log(np.abs(arr2)) - np.log(np.abs(arr1)))
        log_diffs = np.nan_to_num(log_diffs, nan=0.0, posinf=float('inf'))
    
    max_log_diff = np.max(log_diffs)
    mean_log_diff = np.mean(log_diffs[np.isfinite(log_diffs)])
    
    return {
        'name': name,
        'shape': arr1.shape,
        'max_log_diff': max_log_diff,
        'mean_log_diff': mean_log_diff,
        'tolerance': COMPARISON_TOLERANCE,
        'pass': max_log_diff <= COMPARISON_TOLERANCE
    }

# =============================================================================
# QUICKTEST DECORATOR
# =============================================================================

def quicktest_step(step_name: str):
    """
    Decorator to wrap a quicktest step with logging, checkpointing, and error handling.
    
    Usage:
        @quicktest_step('agent_initialization')
        def test_agent_init(version):
            # ... test code ...
            return {'result': value}
    """
    def decorator(func):
        def wrapper(version: str = 'unknown', *args, **kwargs):
            logger = setup_quicktest_logging(step_name, version)
            checkpoint = QuicktestCheckpoint(step_name, version)
            
            logger.info(f"Starting quicktest step: {step_name}")
            start_time = datetime.now()
            
            try:
                result = func(version, *args, **kwargs)
                
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"Step completed in {elapsed:.1f}s")
                
                # Save checkpoint
                checkpoint.save_checkpoint(result, status='complete')
                checkpoint.save_results(result)
                
                return result
                
            except Exception as e:
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.error(f"Step FAILED after {elapsed:.1f}s: {e}")
                
                # Save debug state
                import traceback
                error_details = traceback.format_exc()
                checkpoint.save_checkpoint(
                    {'error': str(e), 'traceback': error_details},
                    status='failed'
                )
                
                # Try to save any intermediate state
                if 'state' in kwargs:
                    checkpoint.save_debug_state(kwargs['state'], str(e))
                
                raise
        
        return wrapper
    return decorator

# =============================================================================
# PRINT QUICKTEST STATUS ON IMPORT
# =============================================================================

if QUICKTEST:
    print("=" * 60)
    print("🧪 QUICKTEST MODE ENABLED")
    print("=" * 60)
    print(f"  Tolerance: {COMPARISON_TOLERANCE * 100}% ({COMPARISON_TOLERANCE} log points)")
    print(f"  T_sim: {QUICKTEST_PARAMS['T_sim']} (reduced from 800)")
    print(f"  AgentCount: {QUICKTEST_PARAMS['AgentCount']} (reduced from 5000)")
    print(f"  TypeCount: {QUICKTEST_PARAMS['TypeCount']} (reduced from 7)")
    print(f"  Max optimizer iterations: {QUICKTEST_PARAMS['max_optimizer_iter']}")
    print(f"  Log directory: {QUICKTEST_DIRS['logs']}")
    print("=" * 60)
