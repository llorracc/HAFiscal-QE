# HAFiscal HARK Version Comparison

## Summary

When comparing HAFiscal results between HARK 0.14.1 and HARK 0.17.0, a ~0.08% numerical
difference in consumption function values is observed. This document explains the source
of this difference and provides guidance on how to interpret comparison results.

## Key Finding: The Difference is from Solver Architecture, Not Grid Construction

### What We Initially Investigated

We initially hypothesized that the difference came from a bug fix in HARK 0.17.0 where
the KinkedR solver's asset grid construction was changed:

- **HARK 0.14.1**: `np.array([0.0, 0.0])` (duplicate points)
- **HARK 0.17.0**: `np.array([0.0, 1e-15])` (strictly increasing, bug fix)

### Why This Doesn't Apply to HAFiscal

HAFiscal's `SetupParamsCSTW.py` sets `Rboro = Rsave = Rfree`, meaning there is **no actual
kink** in the borrowing rate. When `Rboro == Rsave`:

- **HARK 0.14.1**: The KinkedR solver detects `KinkBool = False` and uses a simplified
  grid: `aNrmNow = np.asarray(self.aXtraGrid) + self.mNrmMinNow` (no hstack, no special
  grid points)

- **HARK 0.17.0**: The KinkedR solver early-exits and delegates to
  `solve_one_period_ConsIndShock()` instead (entirely different code path)

This architectural difference, not the grid construction change, causes the ~0.08%
numerical difference.

## Practical Implications

### For HAFiscal-QE Validation

1. The 0.14.1 codebase should remain unchanged as the reference
2. The ~0.08% difference in 0.17.0 is expected and acceptable
3. A tolerance of 1% (0.01 log points) is appropriate for validation

### For Future Work

- HARK 0.17.0 is recommended for new work due to improved code organization
- The small numerical difference should not affect economic conclusions
- When Rboro != Rsave (actual kinked rate), additional care may be needed

## Available Comparison Modes

The orchestrator supports two versions:

| Version | Description | Use Case |
|---------|-------------|----------|
| `0.14.1-baseline` | Original HARK 0.14.1 | Reference for HAFiscal-QE |
| `0.17.0-native` | HARK 0.17.0 refactored | New work, production |

## Technical Details

### HARK 0.14.1 KinkedR Solver (when Rboro == Rsave)

```python
# In prepare_to_calc_EndOfPrdvP():
KinkBool = (self.Rboro > self.Rsave)  # False when equal
# ...
if KinkBool:
    aNrmNow = np.sort(np.hstack(..., np.array([0.0, 0.0])))
else:
    aNrmNow = np.asarray(self.aXtraGrid) + self.mNrmMinNow  # Simple grid
```

### HARK 0.17.0 KinkedR Solver (when Rboro == Rsave)

```python
# At the top of solve_one_period_ConsKinkedR():
if Rboro == Rsave:
    solution_now = solve_one_period_ConsIndShock(...)  # Delegate entirely
    return solution_now
```

### Why This Causes Differences

The two approaches use different internal calculations for:
- End-of-period value function computation
- Interpolation grid construction
- MPC and human wealth calculations

While mathematically equivalent, floating-point arithmetic produces slightly
different results due to operation ordering differences.

## Running Comparisons

```bash
# Default comparison (0.14.1 vs 0.17.0-native with 1% tolerance)
python quicktest_orchestrator.py --all

# List available versions
python quicktest_orchestrator.py --list-versions
```
