---
date: 2026-05-01
status: draft
keywords: [CDC, ESC, mirror, BUG-034, BUG-035, Parameters.py, file-path-routing, suffix_path, dispatch]
related_bugs: [BUG-034, BUG-035]
related_plans: [20260501-1032h_cdc-esc-parity-audit-plan.md]
---

# ESC mirror plan: bring ESC interpretation back to runnable parity with CDC

## Background

The CDC-vs-ESC parity audit (plan `20260501-1032h_*`, executed 2026-05-01) found
that ESC has been silently broken since 2026-04-26 because two CDC bug fixes
(BUG-034, BUG-035) were applied **unconditionally** despite their CDC-MOD-*
tags indicating they are CDC-only fixes. ESC also cannot load its own
estimation files because `Parameters.py` reads un-suffixed file paths.

This plan applies three mirror changes to restore ESC runnability without
re-estimating ESC parameters.

## Goal

ESC interpretation is **runnable end-to-end** under `HAFISCAL_INTERPRETATION=ESC`,
loading its own (suffixed) estimation files and using its own (1-ς) wealth
aggregation and stock `KinkedRconsumerType` Step-1 dynamics.

## Out of scope

- **Re-estimating ESC parameters** (separate decision after this plan lands).
- **Changing CDC behavior** — every change here is purely additive: ESC gets
  dispatch branches; CDC keeps current behavior via the default path.
- **Any changes to `tm_methods.py`** (audit found it's already fully
  dispatch-aware via the `interpretation` parameter chain).

## Constraints

- All changes must preserve existing CDC behavior bit-identically (CDC is the
  default branch in every dispatch).
- All file-path changes must use `_interpretation.resolve_path()` fallback
  semantics so legacy un-suffixed files continue to work.
- Tag every new dispatch site with `ESC-MOD-BUG0XX:` cross-reference comment.
- Don't introduce new env vars or refactor the dispatch architecture.

## Phase A: Parameters.py file-path routing (~30 min)

**Why first**: foundational. Without this, ESC code paths can't even reach
their own estimation files; mirror changes B and C would be exercised against
CDC data.

**Change**: route the DiscFacEstim and Splurge file paths through
`_interpretation.resolve_path()` (which returns the suffixed file if it exists,
else falls back to un-suffixed for backward-compat).

**File**: `Code/HA-Models/FromPandemicCode/Parameters.py`

**Sites**: lines 38-39 plus the 6 Parametrization-variant overrides (lines 48-49,
52-53, 56, 59, 63, 67-68). Total: 12 file-path assignments.

**Pattern**:
```python
# Before:
betas_txt_location = Abs_Path_Results+'/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt'

# After:
from _interpretation import resolve_path
betas_txt_location = resolve_path(Abs_Path_Results+'/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt')
```

**ESC-MOD comment** at first site:
```python
# ESC-MOD-PHASE3: route estimation file paths through _interpretation.resolve_path
# so ESC loads _ESC.txt suffixed files. Falls back to un-suffixed (legacy CDC)
# files if the suffixed variant doesn't exist — preserves CDC bit-identity.
```

**Acceptance**:
- Under `HAFISCAL_INTERPRETATION=CDC` (default), every Parametrization variant
  loads exactly the same files as before.
- Under `HAFISCAL_INTERPRETATION=ESC`, Parameters loads `*_ESC.txt` for
  `DiscFacEstim` and `Result_AllTarget` if they exist.

## Phase B: BUG-034 mirror in EstimAggFiscalMAIN.py (~1h)

**Goal**: re-introduce the (1-ς) factor for ESC at the 11 wealth-aggregation
sites that BUG-034 removed for CDC.

**File**: `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py`

**Sites** (per BUG-034 commit 93412daf):
- Lines 117 (aLvlAll for Lorenz)
- Line 132 (aNrmAll_byEd for avgLWPI)
- Line 140 (aLvlAll_byEd for LWoPI per cohort)
- Line 170 (aLvlAll for calc_wealth_share_by_ed aggregate)
- Line 175 (aLvlAll_byEd for calc_wealth_share_by_ed per-cohort)
- Line 203 (aLvlAll for calc_lorenz_pts)
- Line 287 (WealthNow for calc_MPC_by_quartile)
- Line 296 (WealthQ quartile assignment in calc_MPC_by_quartile)
- Line 415 (WealthNow for calc_wealth_distribution)
- Line 428 (WealthQ quartile assignment in calc_wealth_distribution)
- Line 432 (wealth_list for calc_wealth_distribution)

**Pattern** (apply per site):
```python
# Before (current — CDC-MOD-BUG034 form):
aLvlAll = np.concatenate([ThisType.state_now["aLvl"] for ThisType in Agents])

# After (interpretation-dispatched):
def _aLvl_for(ThisType):
    """Helper: return aLvl scaled per interpretation. Inline to keep diff small."""
    if getattr(ThisType, 'interpretation', 'CDC') == 'CDC':
        return ThisType.state_now["aLvl"]
    else:  # ESC
        return (1 - ThisType.Splurge) * ThisType.state_now["aLvl"]
aLvlAll = np.concatenate([_aLvl_for(ThisType) for ThisType in Agents])
```

**Note**: extracting a `_aLvl_for(ThisType)` and `_aNrm_for(ThisType)` pair
of helper functions at the top of the module avoids 11 inline `if/else` blocks
and lets the dispatch be tested in isolation. The helpers are CDC-default
via `getattr(..., 'CDC')` so any agent without `interpretation` set behaves
as CDC (matching current code behavior).

**ESC-MOD comment** at the first site (line 112 region, replacing/extending
the existing CDC-MOD-BUG034 long-form comment):
```python
# CDC-MOD-BUG034 + ESC-MOD-BUG034: Step-2 wealth aggregation dispatched by
# self.interpretation. Under CDC (default), state_now["aLvl"] IS already
# household-total assets per BUG-031 — use directly. Under ESC, aLvl is
# optimizer-per-capita, so multiply by (1-ς) to get household-total.
# See _aLvl_for / _aNrm_for helpers at top of module.
```

**Acceptance**:
- With CDC default agents (no `.interpretation` attribute or `'CDC'`), every
  call to `_aLvl_for` returns the same value as the current code → bit-identical
  CDC behavior.
- With ESC agents, every call returns `(1-ς) * aLvl` matching the pre-BUG-034
  ESC formula.

## Phase C: BUG-035 mirror in Estimation_BetaNablaSplurge.py (~30 min)

**Goal**: dispatch the Step-1 simulator agent type by interpretation. CDC uses
the BUG-035-introduced `CDCKinkedRConsumerType`; ESC uses the stock
`KinkedRconsumerType`.

**File**: `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py`

**Site**: line ~716, currently `BaseType = CDCKinkedRConsumerType(**base_params)`

**Pattern**:
```python
# Before (current — CDC-MOD-BUG035 form):
BaseType = CDCKinkedRConsumerType(**base_params)

# After (interpretation-dispatched):
import sys, os
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))
from _interpretation import get_interpretation
# CDC-MOD-BUG035 + ESC-MOD-BUG035: Step-1 simulator agent type dispatched
# by HAFISCAL_INTERPRETATION. CDC uses CDCKinkedRConsumerType (subclass with
# CDC household-bargain get_poststates override); ESC uses HARK's stock
# KinkedRconsumerType with optimizer-per-capita asset rule (matches the
# pre-BUG-035 behavior).
if get_interpretation() == 'CDC':
    BaseType = CDCKinkedRConsumerType(**base_params)
else:  # ESC
    BaseType = KinkedRconsumerType(**base_params)
```

**Note**: `KinkedRconsumerType` is already in scope (it's the parent class of
`CDCKinkedRConsumerType` and is imported earlier in the file). The
`_interpretation` import requires path manipulation since this file is in
a different directory than the module.

**Acceptance**:
- Under `HAFISCAL_INTERPRETATION=CDC` (default), `BaseType` is
  `CDCKinkedRConsumerType` — bit-identical to current.
- Under `HAFISCAL_INTERPRETATION=ESC`, `BaseType` is the stock
  `KinkedRconsumerType` — matches pre-BUG-035 behavior.

## Phase D: Verification (no re-estimation, ~1h)

Cascade-gated. Halt at first failure.

### Tier 0: Static + import checks (~5 min) [PARALLEL]
Run in parallel:
- **Bash 1**: `HAFISCAL_INTERPRETATION=CDC pytest Code/HA-Models/FromPandemicCode/test_*.py` — must all pass identically
- **Bash 2**: `HAFISCAL_INTERPRETATION=ESC pytest Code/HA-Models/FromPandemicCode/test_*.py` — most should still pass; some may fail on ESC-specific paths that need separate ESC-baseline updates (flag but don't halt unless an *interpretation-agnostic* test fails)

### Tier 1: Path-resolution smoke (~2 min)
- Print which files Parameters.py would load under each interpretation:
  ```python
  HAFISCAL_INTERPRETATION=CDC python -c "import sys; sys.path.insert(0, 'Code/HA-Models/FromPandemicCode'); sys.argv=['x','1.01','2.0','0.7']; from Parameters import return_parameters; p = return_parameters('Baseline'); print(p)"
  ```
  Repeat with `HAFISCAL_INTERPRETATION=ESC` and verify the file paths show `_ESC.txt` suffixes (or fallback to un-suffixed if the suffixed file is missing).

### Tier 2: Agent instantiation smoke (~2 min) [PARALLEL]
- **Bash 1**: under CDC, instantiate `AggFiscalType` and `CDCKinkedRConsumerType`; verify `agent.interpretation == 'CDC'`
- **Bash 2**: under ESC, instantiate `AggFiscalType` and `KinkedRconsumerType` (the dispatch should give us this); verify `agent.interpretation == 'ESC'`

### Tier 3: Single-iteration estimation dry-run (~10 min)
**NOT a re-estimation** — just confirms the pipeline runs end-to-end.
- Run `estim_phase2_tm_a.py` with `HAFISCAL_EDTYPES=1 HAFISCAL_INTERPRETATION=ESC`, but with `HAFISCAL_NM_XTOL=10` (huge tolerance) so NM converges in 1-2 iterations.
- Verify: no crash, output file produced, dispatch fires on ESC.
- This proves ESC is end-to-end runnable; numeric correctness is deferred to a future actual re-estimation.

### Tier 4 (DEFERRED): Full ESC re-estimation
Out of scope for this plan; user authorization required separately.

## Phase E: Documentation (~20 min) [PARALLEL with Phase D]

- Update `BUGS_private/HAFiscal_BUG-034_*.md` with note: "ESC mirror landed in
  commit <X> on YYYY-MM-DD; sites now dispatch via `_aLvl_for`/`_aNrm_for`
  helpers."
- Update `BUGS_private/HAFiscal_BUG-035_*.md` with similar note.
- Update `_interpretation.py` docstring with a usage example for `resolve_path()`
  if it isn't already there.

## Sequencing summary

```
Phase A (Parameters.py)   ────┐
                              ├─→ Phase D Tier 0 (parallel CDC + ESC test runs)
Phase B (EstimAggFiscalMAIN)──┤   ─→ Tier 1 (path smoke)
                              │   ─→ Tier 2 (agent instantiation, parallel)
Phase C (Estimation_BNS)  ────┘   ─→ Tier 3 (1-iter ESC dry-run)
                                                  ↓
Phase E (docs) — interleave with Phase D ─────────┘
```

## Estimated total: ~3-4 hours wall clock

| Phase | Wall time | Parallelizable? |
|---|---|---|
| A: Parameters.py | 30 min | No (single file) |
| B: EstimAggFiscalMAIN | 1 h | Yes — parallel with C |
| C: Estimation_BetaNablaSplurge | 30 min | Yes — parallel with B |
| D: Verification (cascade) | ~1 h total | Tier 0 and Tier 2 parallel |
| E: Docs | 20 min | Yes — interleave with D |

## Commit strategy

Three separate commits, each landing one phase:
1. `Phase A: route Parameters.py file paths through _interpretation.resolve_path`
2. `Phase B (BUG-034 ESC mirror): dispatch wealth aggregation in EstimAggFiscalMAIN.py`
3. `Phase C (BUG-035 ESC mirror): dispatch Step-1 BaseType in Estimation_BetaNablaSplurge.py`

Each commit includes the corresponding BUGS_private update from Phase E.

This three-commit structure lets us bisect any future issue back to a specific
mirror change cleanly.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `getattr` default of 'CDC' silently masks an agent that should be ESC | Low | Tier 2 asserts `agent.interpretation == 'ESC'` under ESC env var; would catch this immediately |
| `resolve_path()` fallback masks a missing _ESC.txt file silently (loads CDC by accident) | Med | Tier 1 explicitly prints loaded paths; could add an assertion that requires explicit suffix when interpretation != CDC if needed |
| `_interpretation` import path breaks in Estimation_BetaNablaSplurge.py (different dir) | Low | Use `sys.path.insert` pattern that's already established elsewhere in the codebase |
| ESC-mode tests fail on ESC-baseline issues unrelated to these mirror changes | Med | Tier 0 explicitly tolerates ESC-test failures unless they're interpretation-agnostic; flag those separately for follow-up |
| The 1-iteration dry-run in Tier 3 doesn't catch a deeper ESC bug | Med | This is a known limitation; real ESC validation requires Phase 4 (full re-estimation), deferred to user |

## What this plan does NOT do

- Doesn't run any actual re-estimation under ESC
- Doesn't compare CDC vs ESC numerical results (that requires re-estimation)
- Doesn't pre-stage `_ESC.txt` files (the existing Apr-26 ESC files become the
  initial ESC anchor; if you want fresher ESC files, that's the deferred Tier 4)
- Doesn't touch `tm_methods.py` or any file the audit confirmed is already
  dispatch-aware

## References

- Audit plan: `plans/20260501-1032h_cdc-esc-parity-audit-plan.md`
- Audit conclusions: `conclusions_private/2026-05-01_cdc-esc-parity-audit-results.md`
  (to be written next)
- BUG-034 dossier: `BUGS_private/HAFiscal_BUG-034_step2_wealth_aggregation_inconsistency.md`
- BUG-035 dossier: `BUGS_private/HAFiscal_BUG-035_step1_agent_state_dynamics_not_cdc.md`
- `_interpretation.py` (the dispatch module)
