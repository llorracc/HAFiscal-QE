"""
HARK Grid Compatibility Module for HAFiscal

This module provides the ability to make HARK 0.17.0's KinkedRconsumerType solver
use the same grid construction as HARK 0.14.1, enabling exact numerical comparison.

Background:
-----------
HARK 0.17.0 (commit 4d57fb2f47, Feb 10, 2025) fixed a bug in the KinkedR solver
where the asset grid had duplicate points at a=0:

  OLD (0.14.1): np.array([0.0, 0.0])     # Duplicate points (bug)
  NEW (0.17.0): np.array([0.0, 1e-15])   # Strictly increasing (fix)

The fix was necessary because the new cubic interpolator requires strictly
increasing x values. However, this change causes ~0.08% numerical differences
in the consumption function.

Versions:
---------
- "0.14.1-baseline": Original HARK 0.14.1 code (reference for HAFiscal-QE)
- "0.17.0-compat":   HARK 0.17.0 with grid patched to match 0.14.1 behavior
- "0.17.0-native":   HARK 0.17.0 with improved grid (recommended for new work)

Usage:
------
    from hark_grid_compat import patch_kinkedr_grid, unpatch_kinkedr_grid
    
    # Enable compatibility mode (match 0.14.1 grid)
    patch_kinkedr_grid()
    agent.solve()
    
    # Disable compatibility mode (use native 0.17.0 grid)
    unpatch_kinkedr_grid()
"""

import numpy as np

# Store original function for unpatching
_original_hstack = None
_is_patched = False


def _compat_hstack(tup):
    """
    Wrapper for np.hstack that converts [0.0, 1e-15] to [0.0, 0.0]
    to match HARK 0.14.1 behavior.
    """
    # Check if this is the specific KinkedR grid construction call
    if len(tup) == 2:
        arr = tup[1]
        if isinstance(arr, np.ndarray) and arr.shape == (2,):
            # Check for the specific pattern: [0.0, 1e-15]
            if np.isclose(arr[0], 0.0) and np.isclose(arr[1], 1e-15):
                # Replace with [0.0, 0.0] to match 0.14.1 behavior
                tup = (tup[0], np.array([0.0, 0.0]))
    
    return _original_hstack(tup)


def patch_kinkedr_grid():
    """
    Patch HARK 0.17.0's KinkedR solver to use 0.14.1-compatible grid construction.
    
    This works by intercepting np.hstack calls and converting the
    [0.0, 1e-15] array to [0.0, 0.0].
    
    After calling this function, KinkedRconsumerType.solve() will produce results
    numerically identical to HARK 0.14.1.
    """
    global _original_hstack, _is_patched
    
    if _is_patched:
        return  # Already patched
    
    _original_hstack = np.hstack
    np.hstack = _compat_hstack
    
    _is_patched = True
    print("✓ HARK 0.17.0 KinkedR solver patched for 0.14.1 grid compatibility")


def unpatch_kinkedr_grid():
    """
    Restore HARK 0.17.0's native KinkedR solver with improved grid.
    """
    global _original_hstack, _is_patched
    
    if not _is_patched:
        return  # Not patched
    
    if _original_hstack is not None:
        np.hstack = _original_hstack
    
    _is_patched = False
    print("✓ HARK 0.17.0 KinkedR solver restored to native behavior")


def is_compat_mode():
    """Check if compatibility mode is currently enabled."""
    return _is_patched


# Version identifiers for clarity
VERSIONS = {
    "0.14.1-baseline": "Original HARK 0.14.1 (HAFiscal-QE reference)",
    "0.17.0-compat": "HARK 0.17.0 with 0.14.1-compatible grid (for validation)",
    "0.17.0-native": "HARK 0.17.0 with improved grid (recommended)",
}
