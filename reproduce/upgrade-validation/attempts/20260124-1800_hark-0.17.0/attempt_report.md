# HARK 0.14.1 → 0.17.0 Upgrade Attempt Report

**Date:** 2026-01-24  
**Status:** ✅ VALIDATED  
**Duration:** ~2 hours (--comp min)

## Summary

Successfully upgraded HAFiscal from HARK 0.14.1 to HARK 0.17.0 with verified numerical
equivalence of all primary quantitative outputs.

## Version Information

| Component | Before | After |
|-----------|--------|-------|
| HARK | 0.14.1 | 0.17.0.post1-broadcasting-fix |
| Python | 3.9.x | 3.10.x |
| NumPy | 1.26.4 | 1.26.4 |

## Validation Results

### Primary Estimation Parameters

| Parameter | HARK 0.14.1 | HARK 0.17.0 | Difference | Status |
|-----------|-------------|-------------|------------|--------|
| splurge | 0.24611389 | 0.24664554 | +0.22% | ✅ |
| beta | 0.96755116 | 0.96754368 | -0.0008% | ✅ |
| nabla | 0.05780500 | 0.05780761 | +0.0045% | ✅ |

### Splurge=0 Parameters

| Parameter | HARK 0.14.1 | HARK 0.17.0 | Difference | Status |
|-----------|-------------|-------------|------------|--------|
| beta | 0.92139437 | 0.92141358 | +0.0021% | ✅ |
| nabla | 0.11626459 | 0.11624820 | -0.0141% | ✅ |

**All differences are within 0.3% relative tolerance - VALIDATED.**

## Fixes Applied

### Fix 1: `unpack_cFunc()` Removal
- **Locations:** 3 files
- **Issue:** `unpack_cFunc()` method removed in HARK 0.17.0
- **Solution:** Access cFunc directly via `solution[0].cFunc`

### Fix 2: `t_sim` Reset
- **Locations:** 2 files (EstimAggFiscalMAIN.py, Estimation_BetaNablaSplurge.py)
- **Issue:** After `simulate()`, `t_sim == T_sim`; subsequent `simulate(1)` raises IndexError
- **Solution:** Reset `t_sim = 0` before additional simulate() calls

### Fix 3: `solution[0].cFunc` Access Pattern
- **Locations:** 4 code paths
- **Issue:** `agent.cFunc` no longer exists directly
- **Solution:** Use `agent.solution[0].cFunc[markov_state](m)` pattern

### Fix 4: `initialize_sim()` Rename (FiscalTools.py)
- **Location:** 1 file (dead code)
- **Issue:** Method renamed from camelCase to snake_case
- **Note:** File is not imported anywhere; fix is cosmetic

## Validation Methodology

### Phase 1: Baseline Capture
1. Created clone of repository at commit 94c02b07 (HARK 0.14.1 compliance)
2. Created separate virtual environment with HARK 0.14.1
3. Ran `./reproduce.sh --comp min` (~2 hours)
4. Captured results to `snapshots/baseline_0.14.1_20260124-1800`

### Phase 2: MWE Validation
1. Created `validation_mwe.py` with 4 targeted tests
2. Verified each HARK API change independently
3. All tests passed

### Phase 3: Integration Validation  
1. Created `validation_phase3.py` to test untested code paths
2. Simulated `calc_mpc_by_wealth_q` pattern from EstimAggFiscalMAIN.py
3. Verified profiler additions are neutral
4. All tests passed

### Phase 4: FiscalTools.py Investigation
1. Confirmed file is orphaned (never imported)
2. Methods it calls don't exist in current agent types
3. Documented as legacy code

## Files Modified

```
Code/HA-Models/FromPandemicCode/AggFiscalModel.py       (profiler additions)
Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py   (HARK 0.17.0 fixes)
Code/HA-Models/FromPandemicCode/FiscalTools.py         (dead code - minor fix)
Code/HA-Models/FromPandemicCode/Simulate.py            (profiler additions)
Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py (HARK fixes)
Code/HA-Models/do_all.py                               (profiler additions)
Code/HA-Models/reproduce_min.py                        (profiler additions)
reproduce.sh                                           (profiler integration)
```

## New Files Created

```
Code/HA-Models/hafiscal_monitor.sh                     (monitoring tool)
Code/HA-Models/hafiscal_progress.py                    (profiling system)
Code/HA-Models/validation_mwe.py                       (Phase 2 tests)
Code/HA-Models/validation_phase3.py                    (Phase 3 tests)
monitor.sh                                             (symlink)
reproduce/upgrade-validation/                          (this validation framework)
```

## Recommendations

1. **Merge Ready:** Code is ready to merge to main branch
2. **Full Validation:** Consider running `--comp full` (4-5 days) for complete verification
3. **FiscalTools.py:** Consider removing or archiving this dead code
4. **Documentation:** Update any HARK version documentation

## Appendix: Log Files

- Baseline run: `/tmp/hafiscal_0.14.1_min_run.log`
- MWE validation: Console output from `validation_mwe.py`
- Phase 3 validation: Console output from `validation_phase3.py`
