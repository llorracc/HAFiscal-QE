---
date: 2026-05-11
status: STALLED — never executed; pure documentation/naming refactor; behavior unchanged
keywords: [UI-extension, naming, documentation, transition_ub, clarity]
related_conclusions:
  - 2026-05-11_shuffle_ui_welfare_crn_breakdown.md
related_memory:
  - project_shuffle_breaks_ui_welfare_crn.md
---

# Plan: revise UI-extension code + comments for unambiguous interpretation

**Status:** STALLED

## Motivation

In a recent code-reading session, I (Claude) made repeated errors interpreting the UI extension implementation:

1. **Confused `UBspell_extended = 5` with "5 quarters of benefits"**, when it's actually a calibration-related "average if policy were permanent" value. This led to claiming the proposed state expansion needs 7 states when it only needs 6.

2. **Misread `ExtraUBperiods = 3` as "3 extra quarters of benefits"**, when it's the extension window length in macro periods. Due to the freeze-and-resume mechanic, the actual MAX benefits per agent is `ExtraUBperiods + 1 = 4` quarters (matching paper's "up to 4 quarters").

3. **Was unclear about how the `transition_ub=False` trick works** — agents stay frozen at their benefits state during the extension window, which means the state label (`u1Q`, `u2Q`) decouples from "quarter of unemployment". A reader who assumes "u1Q = first quarter of unemployment" will get the dynamics wrong.

4. **Couldn't decide whether `PolicyUBspell = 2` was the right parameter** — it's defined and stored in init dicts but never actually consumed by the simulation. Looks like a parameter; behaves like dead code.

These errors cost time during this session and would cost more time for future readers / maintainers. Goal: revise variable names and comments so a fresh reader can correctly interpret the policy implementation without external explanation.

## Non-goals

- **No behavior change.** This refactor must be bit-identical to current outputs at every existing call site.
- **No state-space expansion.** That's a separate (larger) refactor; see `project_shuffle_breaks_ui_welfare_crn.md` for the rationale.
- **No removal of legacy variable names** if they're imported elsewhere — add deprecation aliases instead.

## Specific changes

### Change 1: Fix the misordered comment on `num_base_MrkvStates`

**File**: `Code/HA-Models/FromPandemicCode/EstimParameters.py:171`

**Current**:
```python
num_base_MrkvStates = 2 + UBspell_normal #employed, unemployed with 2 quarters benefits, unemployed with 1 quarter benefit, unemployed no benefits
```

The comment lists "unemployed with 2 quarters benefits" before "unemployed with 1 quarter benefit", which is the reverse of the actual state ordering (state 1 is u1Q = "1st quarter of benefits", state 2 is u2Q = "2nd quarter of benefits", state 3 is no_benefits).

**Proposed**:
```python
# Micro-state space (per macro state):
#   index 0:           employed
#   indices 1..UBspell_normal: unemployed with benefits, indexed by # quarters elapsed
#                              (e.g., for UBspell_normal=2: state 1 = u1Q, state 2 = u2Q)
#   index UBspell_normal+1:    unemployed with NO benefits ("noBen" — exhausted UI)
# Total: UBspell_normal + 2 states.
num_base_MrkvStates = 2 + UBspell_normal
```

### Change 2: Rename `UBspell_extended` and clarify its role

**File**: `Code/HA-Models/FromPandemicCode/Parameters.py:259`

**Current**:
```python
UBspell_extended = 5         # Average duration of unemployment benefits when extended and assuming policy remains in place, in quarters
```

This name and comment misleadingly suggest "an agent under extended UI gets 5 quarters of benefits." The simulation does NOT produce that — max benefits per agent is 4 quarters (= `Policy_ExtraBenefitQuarters + UBspell_normal`).

**Proposed**:
```python
# UI EXTENSION POLICY PARAMETERS
# ----------------------------------------------------------------------------
# The extension policy increases the maximum number of quarters an agent can
# collect UI benefits, from `UBspell_normal` (= 2 in the published baseline)
# to `UBspell_normal + Policy_ExtraBenefitQuarters` (= 4 in the published
# baseline). See paper Model.tex line 167-168.
#
# In the published paper this is "up to four quarters (including quarters
# leading up to the recession)".
Policy_ExtraBenefitQuarters = 2   # # of EXTRA benefit-eligible quarters under extension
                                   # (above UBspell_normal). Per published paper Model.tex:167.

# DEPRECATED naming (kept for backward compatibility; do not use in new code):
UBspell_extended = UBspell_normal + Policy_ExtraBenefitQuarters + 1  # = 5; legacy
# Note: the prior name "UBspell_extended" with value 5 was a misleading
# calibration-derived quantity (related to expected benefit duration if the
# extension policy were permanent). It is NOT the maximum benefits any agent
# receives — that's UBspell_normal + Policy_ExtraBenefitQuarters = 4. Use
# `Policy_ExtraBenefitQuarters` for any policy-design-related code.
```

### Change 3: Remove or document `PolicyUBspell`

**File**: `Code/HA-Models/FromPandemicCode/Parameters.py:260`

**Current**:
```python
PolicyUBspell = 2            # Average duration that policy of extended unemployment benefits is in place
```

This is documented as a policy parameter but never consumed. A future reader will reasonably assume it's used somewhere and get confused.

**Proposed (Option A — remove)**:
```python
# PolicyUBspell variable removed (was previously defined but never consumed).
# The policy duration is now derived as Policy_ExtraBenefitQuarters + 1
# (extension window in macro periods); see make_cond_mrkv_arrays_recession_ui.
```

**Proposed (Option B — keep with explicit dead-code marker)**:
```python
PolicyUBspell = 2            # NOTE: defined for documentation only; NOT consumed by
                              # any simulation code. The actual extension policy duration
                              # is determined by Policy_ExtraBenefitQuarters; see
                              # make_cond_mrkv_arrays_recession_ui.
```

Recommend Option A unless `PolicyUBspell` is referenced in plot annotations or tables (will need to grep before deciding).

### Change 4: Rename `ExtraUBperiods` and document the +1 relationship

**File**: `Code/HA-Models/FromPandemicCode/Parameters.py:389, 398, 438-440`

**Current**:
```python
def make_cond_mrkv_arrays_recession_ui(..., ExtraUBperiods):
    ...
    CondMrkvArrays = [...] + [normalUI, recessionUI]*ExtraUBperiods + [...]
```

The name `ExtraUBperiods` strongly suggests "extra unemployment-benefits periods (= extra quarters of benefits per agent)". But it's actually the **extension window length in macro periods**, and due to the freeze-and-resume mechanic, the max extra benefits per agent is `ExtraUBperiods - 1`.

Wait — let me verify the formula before committing to a rename. Going back to the trace:

Agent enters u1Q at period 1 (start of extension window of length W = ExtraUBperiods):
- Periods 1..W: frozen at u1Q (W quarters of benefits)
- Period W+1: u1Q → u2Q (1 more quarter)
- Period W+2: u2Q → noBen
- Total benefits = W + 1 quarters

With W=3: max benefits = 4 quarters = `UBspell_normal + Policy_ExtraBenefitQuarters` = `2 + 2` ✓

So the relationship is: `extension_window_length = Policy_ExtraBenefitQuarters + (UBspell_normal - 1)` = `2 + 1 = 3`.

For the published baseline: `extension_window_length = 3`, `Policy_ExtraBenefitQuarters = 2`, max benefits per agent = 4. ✓

**Proposed**:
```python
def make_cond_mrkv_arrays_recession_ui(
    Urate_normal, Uspell_normal, UBspell_normal,
    Urate_recession, Uspell_recession, num_experiment_periods,
    extension_window_macro_periods,  # renamed from ExtraUBperiods
):
    """Build the time-varying CondMrkvArrays for the UI-extension scenario.

    Mechanism: during the extension window, the cond_mrkv uses transition_ub=False
    (agents stay frozen at their current benefits state instead of progressing).
    After the window, dynamics revert to transition_ub=True (agents progress
    u1Q→u2Q→noBen).

    The number of EXTRA benefit-eligible quarters per agent is:
        Policy_ExtraBenefitQuarters = extension_window_macro_periods - (UBspell_normal - 1)
    For the published baseline with UBspell_normal=2 and window=3:
    extra_quarters = 3 - 1 = 2 → total max benefits = 2 + 2 = 4 quarters.

    Example agent trajectory under this encoding (extension window = 3 periods):
        Period 0  pre-extension : u1Q (income 0.7)
        Period 1  extension     : u2Q (income 0.7) — normal progression
        Period 2  extension     : u2Q (income 0.7) — frozen (transition_ub=False)
        Period 3  extension     : u2Q (income 0.7) — frozen
        Period 4  post-extension: noBen (income 0.5) — u2Q→noBen progression resumes
    """
    ...
    CondMrkvArrays = (
        [MrkvArray_normal, MrkvArray_recession]                                                   # period 0 (pre-extension)
        + [MrkvArray_normalUI, MrkvArray_recessionUI] * extension_window_macro_periods           # extension window
        + [MrkvArray_normal, MrkvArray_recession] * (num_experiment_periods - extension_window_macro_periods)  # post-extension
    )
    return CondMrkvArrays
```

And at the call sites (lines 438-440):
```python
# extension window length: needs to be Policy_ExtraBenefitQuarters + (UBspell_normal - 1)
# so that an agent who enters at u1Q at start of window gets the full
# Policy_ExtraBenefitQuarters extra quarters before progressing to noBen.
_ext_window = Policy_ExtraBenefitQuarters + (UBspell_normal - 1)  # = 3 in baseline
CondMrkvArrays_recessionUI_d = make_cond_mrkv_arrays_recession_ui(
    Urate_normal_d, Uspell_normal, UBspell_normal,
    Urate_recession_d, Uspell_recession, num_experiment_periods,
    extension_window_macro_periods=_ext_window,
)
# (same for _h, _c)
```

### Change 5: Add a docstring to `small_MrkvArray` explaining the `transition_ub` trick

**File**: `Code/HA-Models/FromPandemicCode/EstimParameters.py:174` (and the duplicate in `Parameters.py`)

**Proposed**:
```python
def small_MrkvArray(e, u, ub, transition_ub=True):
    """Build a (ub+2)-state Markov transition matrix for unemployment dynamics.

    States: index 0 = employed, indices 1..ub = benefit-eligible unemployed
    (e.g., u1Q at index 1, u2Q at index 2 for ub=2), index ub+1 = no-benefits
    unemployed.

    Transitions:
      employed → employed:  e
      employed → u1Q:        1-e
      ui      → ui+1 (or stay at ui — see transition_ub):  u
      ui      → employed:    1-u    (for i in 1..ub)
      noBen   → noBen:       u
      noBen   → employed:    1-u

    The `transition_ub` flag controls how unemployed-with-benefits agents
    progress through the benefits chain:

      transition_ub=True (default; used in baseline recession dynamics):
        u_i → u_{i+1} with probability u   (agent advances through benefits chain)
        After ub quarters at benefits states, agent transitions to noBen.

      transition_ub=False (used during the UI-extension window):
        u_i → u_i with probability u       (agent FROZEN at current benefits state)
        Agent stays at u_i collecting benefits indefinitely until employed.

    The `transition_ub=False` path is the mechanism by which UI extension is
    encoded WITHOUT expanding the state space. During the extension window,
    setting transition_ub=False suspends the natural benefits-chain progression;
    after the window ends, transition_ub=True resumes progression. This is a
    space-efficient encoding but has a non-obvious consequence: state labels
    (u1Q, u2Q) decouple from "literal quarter of unemployment" during the
    extension window. See the trace example in make_cond_mrkv_arrays_recession_ui.

    For an alternative encoding that uses an EXPANDED state space (one state
    per quarter of unemployment, with policy-difference encoded purely in the
    income vector), see plans/20260511_ui_extension_naming_clarity.md and
    project_shuffle_breaks_ui_welfare_crn.md.
    """
    ...
```

### Change 6: Add a high-level "policy structure" comment block to Parameters.py

**File**: `Code/HA-Models/FromPandemicCode/Parameters.py` near line 250

**Proposed (insert before the recession+UI parameter definitions)**:
```python
# ============================================================================
# UI EXTENSION POLICY — SUMMARY
# ============================================================================
#
# The published paper specifies (Model.tex line 167-168):
#   "Extended unemployment benefits... unemployment benefits are extended from
#    two quarters to four quarters... up to four quarters (including quarters
#    leading up to the recession)."
#
# This is implemented via a "freeze-and-resume" mechanic on the existing 4-state
# Markov chain (employed, u1Q, u2Q, noBen) — NOT via state-space expansion.
#
# During an extension window of duration `extension_window_macro_periods`,
# the conditional Markov array uses transition_ub=False, which causes agents
# at u1Q or u2Q to stay frozen at their current state (collecting benefits)
# instead of progressing to noBen. After the window ends, transition_ub=True
# resumes natural progression.
#
# Maximum extra benefits per agent = extension_window_macro_periods - (UBspell_normal - 1)
# Maximum total benefits per agent  = UBspell_normal + Policy_ExtraBenefitQuarters
#
# For the published baseline:
#   UBspell_normal              = 2  (paper's "two quarters")
#   Policy_ExtraBenefitQuarters = 2  (paper's "extended... to four quarters")
#   extension_window_macro_periods = 3  (= 2 + (2-1); set so eligible agents get full extension)
#   Maximum total benefits per agent = 4 quarters ✓ matches paper
#
# A SAMPLE TRAJECTORY for an agent who becomes unemployed at the start of the
# extension window (showing the freeze mechanic at work):
#
#   Period 1: u1Q (income IncUnemp)         enters unemployment, extension starts
#   Period 2: u1Q (income IncUnemp)         FROZEN — transition_ub=False
#   Period 3: u1Q (income IncUnemp)         still frozen
#   Period 4: u2Q (income IncUnemp)         post-extension, normal u1Q→u2Q progression
#   Period 5: noBen (income IncUnempNoBenefits)  u2Q→noBen
#                                             total benefits = 4 quarters ✓
#
# CAVEAT: under this encoding, the state label (u1Q, u2Q) does NOT correspond
# to the literal number of quarters the agent has been unemployed during the
# extension window. The agent above is labeled "u1Q" for periods 1-3 even
# though they've been unemployed for 3 quarters by period 3.
# ============================================================================
```

### Change 7: Add a regression test pinning the policy mechanics

**File**: `Code/HA-Models/FromPandemicCode/test_ui_extension_policy_mechanics.py` (new)

**Purpose**: assert that the encoding actually delivers the documented behavior, so any future code change that breaks the "max benefits = 4 quarters" property is caught immediately.

**Proposed test**:
```python
"""Regression test: UI extension delivers max 4 quarters of benefits per agent
as documented in paper (Model.tex line 167-168) and the policy summary block
in Parameters.py.
"""
import numpy as np
from EstimParameters import UBspell_normal, num_base_MrkvStates
# Import refactored Policy_ExtraBenefitQuarters (post-Change 2)
from Parameters import Policy_ExtraBenefitQuarters

def test_published_baseline_policy_parameters():
    """Verify published baseline parameters match paper Model.tex line 167-168."""
    assert UBspell_normal == 2, "Published baseline: 2 normal benefits quarters"
    assert Policy_ExtraBenefitQuarters == 2, "Published baseline: 2 extra"
    max_benefits = UBspell_normal + Policy_ExtraBenefitQuarters
    assert max_benefits == 4, f"Paper says 'up to 4 quarters', got {max_benefits}"

def test_agent_trajectory_at_window_start():
    """An agent who becomes unemployed at the start of the extension window
    should collect benefits for exactly Policy_ExtraBenefitQuarters + UBspell_normal
    quarters."""
    # Use the published parametrization, simulate one agent through the
    # recessionUI scenario starting unemployed at period 1, verify income
    # trajectory matches: 4 quarters at IncUnemp, then IncUnempNoBenefits.
    # (Full implementation TBD in Phase 2 — needs a minimal scenario harness.)
    pass

def test_freeze_mechanic_state_labels():
    """During extension window, agents at u1Q stay labeled u1Q under
    transition_ub=False; the state index decouples from quarters-unemployed."""
    # Synthetic check: build a 4-state recessionUI MrkvArray with
    # transition_ub=False, verify the diagonal at u1Q is non-zero (agent
    # stays at u1Q with positive probability).
    pass
```

## Implementation order

Phase 1 (audit, ~1 hour):
- `git grep` for all uses of `UBspell_extended`, `PolicyUBspell`, `ExtraUBperiods` to identify call sites that need updating
- Confirm no comments in paper LaTeX or other docs reference these names directly

Phase 2 (Changes 1, 5 — comments-only fixes, ~1 hour):
- Add `num_base_MrkvStates` clarified comment
- Add `small_MrkvArray` docstring with `transition_ub` explanation
- These are pure documentation changes; no behavior risk

Phase 3 (Changes 2, 4, 6 — renames + summary block, ~2 hours):
- Add `Policy_ExtraBenefitQuarters = 2` and the summary comment block
- Rename `ExtraUBperiods` → `extension_window_macro_periods` at all call sites
- Keep `UBspell_extended` and `PolicyUBspell` as deprecated aliases (Change 3 Option B for `PolicyUBspell` is safer initially)
- Run full test suite + validate one Baseline simulation gives bit-identical output to a pre-refactor pickle

Phase 4 (Change 3 cleanup, ~30 min):
- After Phase 3 stabilizes, decide whether to fully remove `PolicyUBspell` (Change 3 Option A) — depends on whether anything else references it

Phase 5 (Change 7, regression test, ~1 hour):
- Implement `test_ui_extension_policy_mechanics.py`
- Add to pytest suite

**Total estimated effort: 5-6 hours focused work.**

## Validation

For Phase 3, the critical check is that **a Baseline simulation gives bit-identical output** before vs after the refactor. This proves the renames + comment additions don't change behavior.

Specifically:
1. Run `python Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py --baseline --seed-offset 0 --out-dir welfare6_pre_refactor` BEFORE the refactor
2. Apply the refactor
3. Run the same command with `--out-dir welfare6_post_refactor`
4. Diff the pickle outputs — should be bit-identical (both runs use same RNG seed and same code paths, just renamed identifiers)

If diffs appear, debug before proceeding.

## Risks

1. **Risk: a downstream consumer references the old names** (e.g., a plotting script or a paper-table generator hardcodes `UBspell_extended`). Mitigation: keep deprecated aliases for one cycle; grep thoroughly first.

2. **Risk: renaming `ExtraUBperiods` to `extension_window_macro_periods` is verbose**. Acceptable cost — a long correct name beats a short misleading one. If desired, abbreviate to `ext_window_periods` after-the-fact.

3. **Risk: the `Policy_ExtraBenefitQuarters` formula has a +/- 1 error**. Mitigated by the regression test (Change 7).

## What's deliberately NOT in this plan

- State-space expansion (the larger refactor for shuffle CRN — separate plan)
- Changes to `MrkvArray_normalUI` (used in normal-times extension which is a separate code path)
- Changes to AD-mode handling (works through the same Markov machinery; refactor naturally propagates)
- Updates to TM-a code (`tm_methods.py`) — needs its own pass, but not blocking

## Success criterion

A reviewer reading the refactored Parameters.py + EstimParameters.py for the first time should be able to correctly answer:
- "How many maximum quarters of benefits does an agent get under extended UI?"  → 4
- "How many extra states would I need to add if I wanted to refactor to one-state-per-quarter encoding?" → 2 (u3Q, u4Q)
- "What does `transition_ub=False` actually do?" → freezes agents at their current benefits state during the extension window
- "What is `PolicyUBspell` used for?" → either nothing (post-removal) or "documentation only" (post-clarification)

If a reasonable reader can't answer these from comments + docstrings alone, the refactor isn't done.
