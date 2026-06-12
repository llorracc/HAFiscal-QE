---
date: 2026-05-11
status: PROPOSED
keywords: [BUG-043, state-expansion, UI-extension, shuffle-CRN, micro-states, transition_ub, per-scenario-encoding]
related_bugs:
  - HAFiscal_BUG-043_ui_extension_under_delivers_for_during_recession_unemployment.md
related_conclusions:
  - 2026-05-11_shuffle_ui_welfare_crn_breakdown.md
related_memory:
  - project_shuffle_breaks_ui_welfare_crn.md
  - project_welfare6_brute_force_5x_paper_precision.md
---

# Plan: fix BUG-043 by expanding micro state space and switching to payout-based UI extension

## Goal

Bring the published code into compliance with the policy described in paper Model.tex line 167-168 ("extended from two quarters to four quarters... up to four quarters including quarters leading up to the recession"). The current encoding under-delivers by 1 quarter for the largest single eligible group of agents (those who become unemployed during the recession — "Case 1" agents).

The fix is the user's earlier proposal: **expand the micro state space and shift the policy difference from transitions to payouts.** But to avoid imposing the larger state space on policies that don't need it, the encoding is applied **per-scenario** rather than globally (see "Scope" section below).

## Side benefit (important enough to call out separately)

The proposed fix has a meaningful **methodological side benefit beyond just fixing the bug**: it makes the Markov dynamics (cond_mrkv) **identical across the recession and recessionUI scenarios**. The only difference between scenarios becomes the income vector. This means:

1. **Shuffle CRN works correctly for UI welfare cells.** Currently shuffle MC inflates UI welfare variance ~5× because the deterministic permutation breaks per-agent CRN coupling when pol/none have different cond_mrkv (see `conclusions_private/2026-05-11_shuffle_ui_welfare_crn_breakdown.md`). After this fix, the cond_mrkv is the same across pol/none for UI scenarios, so shuffle preserves per-agent CRN naturally.

2. **The variance reduction techniques become uniformly applicable across all welfare cells (Check, UI, TaxCut)** — currently we'd need different methods for UI vs the others.

3. **Future production runs at smaller N become viable** — shuffle's variance reduction at quota-exact N would let us achieve paper precision at lower N than brute-force MC requires. This matters for computationally-expensive sensitivity analyses (CRRA1, CRRA3, Splurge0, etc.) where we'd otherwise need to do Baseline 5×N for each variant.

## Scope: per-scenario encoding (NEW — important)

The fix applies the 6-state encoding ONLY to scenarios that involve the UI extension policy. All other scenarios (Check, TaxCut, recession, base, and their AD variants) continue to use the legacy 4-state encoding.

| Welfare-6 cell | pol scenario (encoding) | none scenario (encoding) | base scenario (encoding) |
|---|---|---|---|
| check_norec | Check (**4-state**) | base (4-state) | base (4-state) |
| check_rec | recessionCheck (**4-state**) | recession (4-state) | base (4-state) |
| check_rec_AD | recessionCheck_AD (**4-state**) | recession_AD (4-state) | base (4-state) |
| taxcut_norec | TaxCut (**4-state**) | base (4-state) | base (4-state) |
| taxcut_rec | recessionTaxCut (**4-state**) | recession (4-state) | base (4-state) |
| taxcut_rec_AD | recessionTaxCut_AD (**4-state**) | recession_AD (4-state) | base (4-state) |
| **ui_rec** | **recessionUI (6-state)** | **recession (4-state)** | base (4-state) |
| **ui_rec_AD** | **recessionUI_AD (6-state)** | **recession_AD (4-state)** | base (4-state) |
| ui_norec | SKIPPED (per `feedback_ui_norec_never_report.md`) | — | — |

**Rationale**:
- The 6-state encoding adds ~50% to CFunc backward induction cost per scenario. For Check and TaxCut, the extra states (u3Q, u4Q) provide no behavioral difference (their income = noBen income in non-UI scenarios), so running them at 6-state would be wasted compute.
- For UI scenarios, the 6-state encoding is necessary for the bug fix (without it, Case 1 agents under-receive by 1 quarter).
- The "none" scenario in UI welfare cells (recession or recession_AD) can stay at 4-state because the 4-state encoding correctly delivers 2 quarters of benefits to all unemployed agents — which matches what an agent would receive in the absence of the extension policy. There's no bug to fix on the "none" side.

### Mixed-encoding welfare integrand: still well-defined under per-agent CRN

For UI welfare cells, the pol scenario (recessionUI) uses 6-state and the none scenario (recession) uses 4-state. Per-agent CRN is preserved across these because:
- Each agent has the same shock seeds in both scenarios
- The "stay employed / stay unemp" decision at each period is the same (driven by the same uniform random draw compared to the same 1-u threshold)
- Agents who stay unemployed end up at different micro-state LABELS (`u3Q` in 6-state vs `noBen` in 4-state for an agent unemp 3 quarters), with different INCOME (0.7 vs 0.5) — and this difference is exactly the policy effect

The welfare integrand `(u(c_pol) - u(c_none)) / u'(c_base)` is therefore correctly capturing the bug-fixed policy difference, with `c_base` from the 4-state base scenario (which is the right denominator regardless of pol encoding).

## Non-goals

- **No change to the model's economic content beyond fixing the bug.** The fix should make the simulation match the paper's stated policy more accurately, not introduce a new model variant.
- **No retraining of the calibration** (β/∇ Step-2 estimation) unless the wealth-fit is materially affected. Step-2 uses base scenario (4-state) — unaffected by the bug fix.
- **No removal of the legacy `transition_ub=False` path** in `small_MrkvArray` immediately — keep it for backward-compat regression testing during the transition.

## Welfare invariance for non-UI cells (theoretical argument + regression test)

A key property of the proposed encoding is that **welfare values for Check and TaxCut cells should be exactly unchanged** by this fix (modulo numerical precision). Since these cells use 4-state encoding throughout (per the scope section), the encoding switch doesn't touch their code paths at all.

Even if we were to run Check/TaxCut scenarios under the 6-state encoding (which we won't, per the scope decision), welfare invariance would hold because:

For non-UI scenarios, the income at every micro state is:

| State | Income (all non-UI scenarios, both encodings) |
|---|---|
| employed | wage |
| u1Q | IncUnemp (0.7) |
| u2Q | IncUnemp (0.7) |
| u3Q (6-state only) | IncUnempNoBenefits (0.5) |
| u4Q (6-state only) | IncUnempNoBenefits (0.5) |
| noBen | IncUnempNoBenefits (0.5) |

u3Q, u4Q, and noBen all pay 0.5 — identical to what an agent unemp 3+ quarters receives in the 4-state encoding.

**Value function invariance**: by Bellman backward induction, V(u3Q, a) = V(u4Q, a) = V(noBen, a) for all asset levels `a`, because all three states have the same per-period income (0.5) and the future income distributions converge to the same fixed point (= the value of being permanently unemployed at IncUnempNoBenefits, with stochastic exit to employed).

**Consequence**: an agent with the same shock seeds under both encodings follows the same income trajectory and makes the same consumption decisions. Aggregate welfare values are identical.

### Regression test (added as a hard requirement in Phase 4)

This invariance must be VERIFIED empirically. If Check/TaxCut welfare cells shift between encodings, there's a bug in the implementation. The test is straightforward:

1. Run Check and TaxCut scenarios under 6-state encoding (using a temporary debug flag to force expanded encoding for these scenarios).
2. Compute welfare-6 cells.
3. Compare to legacy 4-state values.
4. Pass criterion: **bit-identical** or within 1e-6 numerical precision. Larger differences indicate an implementation bug.

This test is run once during validation; once it passes, the production pipeline uses 4-state for these scenarios (per scope).

## Proposed encoding (technical specification)

### Micro state space: 4 → 6 states (for UI scenarios only)

Current: `{employed, u1Q, u2Q, noBen}` (4 states; `num_base_MrkvStates = 2 + UBspell_normal = 4`).

For UI scenarios under the bug fix: `{employed, u1Q, u2Q, u3Q, u4Q, noBen}` (6 states). Each unemployment state explicitly tracks the agent's quarter of unemployment up to the maximum extension duration.

`num_base_MrkvStates_ui = 2 + UBspell_normal + Policy_ExtraBenefitQuarters = 2 + 2 + 2 = 6` (with `Policy_ExtraBenefitQuarters = 2`).

For non-UI scenarios: `num_base_MrkvStates_main = 2 + UBspell_normal = 4` (unchanged).

### Markov transitions: identical across UI scenarios under the bug fix

For UI scenarios (recessionUI, recessionUI_AD), both implicitly use `transition_ub=True` (deterministic forward progression u1Q → u2Q → u3Q → u4Q → noBen at rate `u`, with stochastic exit to employed at rate `1-u` from each unemployment state).

This unifies the cond_mrkv across the recessionUI scenario's macro states — no more `transition_ub=False` in the recessionUI path. Combined with the same dynamics at base (4-state) for the "none" comparison, the UI welfare integrand is well-defined per-agent under CRN.

### Income rule (the 5-row table from earlier discussion)

For an agent at any micro state in period t, the income is determined by:

| Scenario | State | Macro state at t | Income |
|---|---|---|---|
| Any non-UI scenario | u1Q, u2Q | any | IncUnemp (0.7) |
| Any non-UI scenario | u3Q, u4Q | n/a (state doesn't exist in 4-state) | — |
| Any non-UI scenario | noBen | any | IncUnempNoBenefits (0.5) |
| Recession (none for UI) | u1Q, u2Q, noBen | any | per the row above |
| Recession (none for UI) | u3Q, u4Q | n/a | — |
| RecessionUI (pol for UI) | u1Q, u2Q | any | IncUnemp (0.7) |
| **RecessionUI (pol for UI)** | **u3Q, u4Q** | **recession** | **IncUnemp (0.7)** ← extension |
| **RecessionUI (pol for UI)** | **u3Q, u4Q** | **normal (recession ended)** | **IncUnempNoBenefits (0.5)** |
| RecessionUI (pol for UI) | noBen | any | IncUnempNoBenefits (0.5) |

**Key rule**: extension benefits at u3Q/u4Q are available **only if both** (a) we're in the recessionUI scenario, AND (b) the macro state at t is in the "recession" half of the macro-Markov chain (= odd-indexed macro states, indicating economy currently in recession).

If the recession ends, the macro state transitions to the "normal" half, the extension benefits cease (u3Q/u4Q income drops to 0.5), and the agent receives the same benefits a non-extension recession scenario would have provided.

### The `normalUI` MrkvArray becomes unused

The published code has `MrkvArray_normalUI` (with `transition_ub=False`) used at *normal* macro states during the fixed extension window. Under the bug fix, this path becomes unused: the extension is tied to "recession ongoing" rather than to a fixed time window. The `normalUI` construction can be deleted (in a follow-up cleanup) or left as dead code with a deprecation comment.

Similarly, the unused `PolicyUBspell = 2` parameter (which was already dead code) becomes truly meaningless — the policy duration is now "however long the recession lasts in this realization", not a separate parameter.

### What changes per agent (illustrative trace)

**Case 1 agent (employed at recession onset, becomes unemp during t=0)** in recessionUI:

| t | macro state | macro classification | micro | income (proposed) | income (current/buggy) |
|---|---|---|---|---|---|
| 0 | 3 | recession | employed | wage | wage |
| 1 | 5 | recession | u1Q | IncUnemp (0.7) | IncUnemp (0.7) |
| 2 | 7 | recession | u2Q | IncUnemp (0.7) | IncUnemp (0.7, frozen at u1Q) |
| 3 | 9 | recession | u3Q | **IncUnemp (0.7)** ← extension | IncUnemp (0.7, advanced to u2Q) |
| 4 | 11 | recession | u4Q | **IncUnemp (0.7)** ← extension | IncUnempNoBenefits (0.5, at noBen) |
| 5 | 13 | recession | noBen | IncUnempNoBenefits (0.5) | IncUnempNoBenefits (0.5) |

Total benefits in proposed encoding: **4 quarters** (matches paper Model.tex line 167-168). Total in current encoding: 3 quarters (under-delivers by 1).

If the recession ends before t=5 (e.g., at t=3), the agent's u3Q income at t=3 reverts to `IncUnempNoBenefits` (0.5) — the recession-ongoing cap binds. This matches the user's reading that "up to 4 quarters" is bounded by recession duration.

## Implementation phases

### Phase 1 — Audit + safety net (~2 hours)

Before changing anything, establish a regression test baseline.

1. Run a single Baseline 5×N seed at the current encoding. Save the welfare-6 output as `pre_fix_welfare6_seed0.json` (a small JSON with the 8 welfare cells, taken from the existing pickles).
2. Run the BUG-043 test scripts to verify they reproduce the documented under-delivery. This becomes the "before" snapshot.
3. `git grep` for every use of `num_base_MrkvStates`, `UBspell_normal`, `UBspell_extended`, `ExtraUBperiods`, `transition_ub`. Build a list of all call sites that need updating. (Estimate: 15-25 sites across `EstimParameters.py`, `Parameters.py`, `AggFiscalModel.py`, `tm_methods.py`, `Simulate.py`, `welfare6_scenario.py`, plotting code, and any tests.)

### Phase 2 — Add per-scenario encoding infrastructure (~5 hours)

The per-scenario approach is slightly more invasive than a global encoding switch — but it's worth the extra hour or two to avoid slowing down Check/TaxCut compute.

1. Add `HAFISCAL_UI_STATE_ENCODING={legacy,bug_fix}` env var in `EstimParameters.py`, default `legacy` (= current 4-state encoding throughout, bit-identical to current). Under `bug_fix`, UI scenarios use 6-state, non-UI use 4-state.

2. Refactor `EstimParameters.py` to expose `num_base_MrkvStates_for_scenario(scenario_name)` that returns 6 for UI scenarios under `bug_fix`, 4 otherwise. Avoid hardcoding `num_base_MrkvStates` as a module-level constant.

3. In `Parameters.py`, make `MrkvArray_recessionUI_*` and `MrkvArray_recessionUI_AD_*` build the 6-state versions under `bug_fix` mode. Other MrkvArrays remain 4-state.

4. Refactor `welfare6_scenario.py` and `AggFiscalModel.py` to construct agents with the appropriate `num_base_MrkvStates` for the scenario being simulated. Each scenario gets a fresh agent setup with the right state count.

5. The MC simulation step must dispatch to the right CFunc / IncShkDstn structure based on the scenario's encoding.

6. Implement the income rule (5-row table above) for UI scenarios: `IncShkDstn[u3Q]` and `IncShkDstn[u4Q]` depend on macro state. Add macro-state-conditional income for these states under `bug_fix` mode for UI scenarios only.

### Phase 3 — Update TM-a code (~3 hours)

The TM-a code (`tm_methods.py`) has its own state-space handling and needs to be brought in sync.

1. Update bucket discretization, distribution computation, and aggregation sites to handle the 6-micro-state case for UI scenarios.
2. Non-UI scenarios continue using 4-state TM-a.
3. Verify that under `legacy` encoding, TM-a output is bit-identical to current.
4. Under `bug_fix` encoding, TM-a should match the new MC welfare values within MC sampling noise for UI cells; should be bit-identical for non-UI cells.

### Phase 4 — Validate (~3 hours)

1. **Bit-identity in legacy mode**: Run a Baseline 5×N seed at `HAFISCAL_UI_STATE_ENCODING=legacy`. Output pickles must be bit-identical to the pre-refactor pickles (= safety net regression test).

2. **Non-UI welfare invariance under bug_fix mode**: Run Check and TaxCut welfare cells under `bug_fix` mode. These cells **must** match legacy values bit-identically (or within 1e-6 numerical precision) — they use 4-state encoding throughout under the scope decision. **If they differ at all, there's a bug in the per-scenario dispatch logic.**

3. **Optional extra check (welfare invariance under forced 6-state for non-UI)**: For developer confidence, temporarily force Check / TaxCut scenarios to use 6-state encoding (= a debug flag). Compute welfare cells; they should still match legacy values within 1e-6 (per the theoretical invariance argument). This is not part of the production code path but validates that the encoding choice is truly invariant for non-UI cells.

4. **UI welfare empirical validation under bug_fix mode**: Run UI welfare cells under `bug_fix` mode. Verify:
   - Case 1 agents now receive 4 quarters of benefits in their primary unemployment episode (= bug fixed). Confirm via the BUG-043 test scripts adapted for the new encoding.
   - All other cases (already at u1Q at onset, already at u2Q at onset, already at noBen at onset) deliver the same benefits as in legacy mode.
   - Welfare values shift upward for ui_rec and ui_rec_AD; magnitude is the bug fix amount.

5. **Wealth-distribution invariance check**: Run Step-2 simulation. Since Step-2 uses base scenario (4-state under both modes), wealth distribution must be bit-identical. If not, the per-scenario dispatch logic has a bug affecting base-scenario simulation.

### Phase 5 — Test shuffle CRN under bug_fix encoding for UI (~1 hour)

This is the side-benefit validation.

1. Run a shuffle-MC Baseline 5×N seed at `HAFISCAL_UI_STATE_ENCODING=bug_fix` with `HAFISCAL_MC_SHUFFLE=1`.
2. Compare seed-to-seed UI welfare variance to the current 4-state shuffle (which had ~5× variance amplification for UI).
3. Verify variance reduction matches the non-UI cells' behavior under shuffle (= shuffle correctly preserves per-agent CRN now for UI scenarios because cond_mrkv is unified across pol and none).
4. If the variance reduction works, this opens the door to using shuffle for ALL welfare cells in production.

### Phase 6 — Cutover and documentation (~2 hours)

1. Once validated, change the `HAFISCAL_UI_STATE_ENCODING` default from `legacy` to `bug_fix`. The previous values in published pickles will no longer be reproducible without setting the env var, but the new values are correct (= match paper text).

2. Update paper text or appendix to note the methodology change if the welfare values shift meaningfully (TBD based on Phase 4 results).

3. Update memory entries:
   - `project_shuffle_breaks_ui_welfare_crn.md` becomes obsolete — replace with `project_shuffle_works_for_ui_welfare_after_BUG-043_fix.md`
   - `project_welfare6_brute_force_5x_paper_precision.md` add note that shuffle is now usable as a faster alternative for UI welfare
   - Update `MEMORY.md` index

4. Update `BUGS_private/HAFiscal_BUG-043_*.md` status from `open` to `fixed`.

5. Add an entry to `BUGS_private/HARK+HAFiscal_TM_vs_MC_changelog.md` documenting the encoding change and the welfare value shifts.

## Total estimated effort

~16 hours of focused work (was 14; +2 for per-scenario encoding infrastructure and the additional Phase 4 invariance test), plus background compute time for validation runs (~2 hours wall for the 5×N validation runs).

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Bit-identity in legacy mode breaks (= refactor introduced a regression) | Medium | The feature flag + bit-identity test catches this immediately. Don't proceed past Phase 4 step 1 if it fails. |
| Non-UI welfare invariance fails (= Check/TaxCut cells shift) | Low (if scope decision is followed, this can't happen because they're 4-state throughout) | Phase 4 step 2 explicitly checks this. If it fails, the per-scenario dispatch logic has a bug. |
| Wealth-distribution shift in bug_fix mode (= base scenario simulation changed accidentally) | Low (base uses 4-state in both modes) | Phase 4 step 5 explicitly checks bit-identity. |
| UI welfare values shift more than expected (e.g., changes by >10% rather than the expected few%) | Low | Acceptable — that's the bug fix. Document the shift and update paper values. |
| Shuffle CRN doesn't actually fix UI variance under the new encoding | Low | Phase 5 explicitly tests this. If it doesn't work, the bug fix still stands; we just don't get the side benefit. |
| Some downstream code references the 4-state assumption directly (e.g., hard-coded `[0, 1, 2, 3]` indexing) | Medium | Phase 1 audit catches this. May extend the refactor by 1-2 hours per such site. |
| Per-scenario dispatch logic is buggy (= UI scenario uses 4-state encoding by mistake, or vice versa) | Medium | The bit-identity tests in Phase 4 catch this from both directions. |

## What this fix does NOT address

- **The naming/comment refactor** in `plans/20260511_ui_extension_naming_clarity.md`: that plan's renames (e.g., `ExtraUBperiods` → `extension_window_macro_periods`) become moot under the new encoding because the freeze-window mechanism is gone. Most of that plan can be retracted; the `num_base_MrkvStates` comment fix (its Change 1) and the `small_MrkvArray` docstring (Change 5) should still happen as historical-context documentation.
- **The published HAFiscal-QE numbers** are not retroactively corrected by this fix. They reflect the buggy encoding. Any paper revision that includes the new welfare values should note the methodology change.

## Success criteria

After Phase 4:
- Bit-identical Baseline 5×N output at `HAFISCAL_UI_STATE_ENCODING=legacy` → no regression.
- **Bit-identical Check/TaxCut welfare cells in `bug_fix` mode vs `legacy` mode** (within 1e-6 numerical precision) → the bug fix is targeted only at UI.
- Case 1 agents in `bug_fix` mode receive 4 quarters of benefits in their primary episode → bug fixed.
- Wealth distribution bit-identical in both modes → base scenario unaffected by bug fix.

After Phase 5:
- Shuffle-MC seed-to-seed UI welfare variance drops from ~5× the non-shuffle SE down to comparable to the non-UI cells (~0.1× the non-shuffle SE) → side benefit confirmed.
