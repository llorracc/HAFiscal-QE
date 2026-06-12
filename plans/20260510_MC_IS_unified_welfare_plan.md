---
date: 2026-05-10
status: REVISED 2026-05-11 — Phase 3 found IS bias; brute-force 5×N recommended instead
keywords: [welfare-6, MC, CRN, importance-sampling, stratified-sampling, unified-method]
related_conclusions:
  - 2026-05-10_FINAL_welfare6_tm_repagent_works.md
  - 2026-05-10_UI_welfare_analysis_REVISED.md
  - 2026-05-10_harmenberg_IS_unified_analysis.md
  - _USER_RETURNS_README_2026-05-11.md  # autonomous overnight result
related_memory:
  - feedback_ui_norec_never_report.md
  - feedback_ui_multiplier_unreliable.md
  - project_welfare6_brute_force_5x_paper_precision.md
  - project_welfare6_is_bias_diagnosis.md
---

# REVISED 2026-05-11 — Phase 3 result and revised recommendation

Autonomous overnight work on 2026-05-10/11 ran a feasibility test of active IS via forced-unemployed intake. Phase 3 outcome:

1. **IS prototype works mechanically** but produces +10% systematic bias on ui_rec (1.94 vs converged brute-force 1.77 at HS_Only).
2. **Bias is NOT just from aNrm distribution mismatch**: forcing aNrm = 0.5 in addition to Markov did not close the gap.
3. **True fix requires joint (aNrm, pLvl, Markov-substate) sampling** from natural-unemp agents in a paired sim A run. This is ~1-2 weeks of dev with no guarantee the resulting variance reduction beats brute-force 5×N.
4. **Brute-force MC at 5× cohort-N already gives paper precision** at HS_Only: SE ≤0.11% rel for all welfare cells (4-seed N=49k).
5. **Existing 32-seed Baseline 1×N data on disk** (Apr 19-22) gives SE 0.44% rel for ui_rec — already paper-precision. Caveat: pre-bug-fix; verification run in progress.

**Revised recommendation**: pursue brute-force MC at 5×N (or use the 32-seed 1×N data if post-fix verification matches). IS dev held indefinitely.

See `conclusions_private/_USER_RETURNS_README_2026-05-11.md` for full details.

---

# Original plan (kept for reference, status superseded)


# Plan: MC + CRN + IS as unified welfare-6 method

## Goal

Replace the current welfare pipeline (mixed: TM-a rep-agent for Check + TaxCut,
MC for UI) with a **single unified MC + CRN + IS method** that handles all
nine welfare cells (Check, UI, TaxCut × {Rec=0/AD=0, Rec=1/AD=0, Rec=1/AD=1})
at paper precision.

Note: ui_norec is excluded entirely (0/0 by construction; see
`feedback_ui_norec_never_report.md`). The pipeline must still skip this cell
in all outputs.

## Why this approach over alternatives

After extensive analysis (see related conclusions), MC + CRN + IS is the
unified solution:

| Method | UI feasibility | Check feasibility | Notes |
|---|---|---|---|
| TM-a rep-agent | dilutes (~50% off) | matches MC ~3% | works for Check/TaxCut only |
| TM-a per-bucket | dilutes (no buckets for UI) | matches MC ~2% | bucket only helps Check |
| TM-a stratified | wrong-signed | doesn't apply | per-state stratification breaks cross-policy match |
| TM-a joint distribution | infeasible (~10¹⁴ cells; needs joint Markov J²) | feasible (~10⁹ cells) | UI's different Markov chains explode the joint state |
| **MC + CRN + IS** | **paper-precision via ~50× variance reduction** | **paper-precision** | **unified for all welfare cells** |

The decisive factor for UI: pol (recessionUI) and none (recession) use
**DIFFERENT Markov chains**. Cross-policy Markov-state coupling under CRN
handles this automatically via shared random uniforms; TM-a joint would
require tracking $J_{\text{pol}} \times J_{\text{none}} \times J_{\text{base}} = 88 \times 88 \times 4$
joint Markov state pairs, which combined with $A^3$ asset joints gives
~$10^{14}$ cells per (cohort, period) — infeasible.

## Mathematical framework

The MC welfare-6 estimator is:
$$\hat{W} = \frac{1}{N \cdot \text{NPV\_AddInc}}\sum_t \beta^t \sum_i \frac{u(c^{\text{pol}}_i(t)\cdot p_i(t)) - u(c^{\text{none}}_i(t)\cdot p_i(t))}{u'(c^{\text{base}}_i(t)\cdot p_i(t))} + \text{savings term}$$

where agents $i$ are sampled from the population.

**CRN** (already in HAFiscal MC, verified by `validate_mc_crn.py`):
agent $i$'s shock seeds $(u_i^M, u_i^\psi, u_i^\xi)$ are shared across pol/none/base
runs. The joint state $(s_{\text{pol},i}, s_{\text{none},i}, s_{\text{base},i})$ is
captured per-agent automatically.

**IS** (to be implemented): reweight the population sampling via a proposal
distribution $Q$ that oversamples rare events:
$$\hat{W}_{\text{IS}} = \frac{1}{\sum_i L_i}\sum_t \beta^t \sum_i L_i \cdot \Phi_i(t)$$

where $L_i = \pi(X_i)/Q(X_i)$ is the importance weight per agent.

For UI specifically, the rare event is "agent reaches extension state."
Proposal $Q$: stratify the initial population by intake employment status,
then sample more agents from the "intake-unemployed" stratum (which has
high probability of reaching extension state).

## Stratification design

For HAFiscal's welfare scenarios, the natural stratification is by
**intake state at recession onset (t=0)**:

- Stratum A: intake-employed (probability ~95%)
- Stratum B: intake-unemployed (probability ~5%, but encompasses ~all UI-affected)

Sample $N_A$ agents in stratum A, $N_B$ agents in stratum B, with
$N_A + N_B = N_{\text{total}}$. Set $N_A : N_B$ to oversample stratum B
(e.g., $N_A = N_B = N_{\text{total}}/2$, dramatic oversampling vs the natural
$N_A : N_B = 0.95 : 0.05$).

Importance weights:
- $L_A = (N_{\text{total}} \cdot 0.95) / N_A$
- $L_B = (N_{\text{total}} \cdot 0.05) / N_B$

Per-agent contribution to welfare estimator: weighted by $L_i$ for their
stratum.

For Check welfare: this stratification doesn't help (Check affects all
employed, not a rare event). But it doesn't hurt either — it just adds
some IS-weight noise. Variance reduction primarily benefits UI; Check
welfare from MC is already converged at production N.

For TaxCut welfare: similar to Check — not a rare event, but stratification
doesn't hurt.

**Refinement** (consider in Phase 2): for UI specifically, finer stratification
within the unemployed stratum (e.g., by initial unemployment duration) could
provide additional variance reduction.

## Phased implementation

### Phase 1: Implement initial-state stratification (~3 days)

**Where**: Modify `Code/HA-Models/FromPandemicCode/welfare6_scenario.py`

**What**:
1. Add `--strata-fraction-unemployed` CLI arg (default: natural rate ~5%; IS:
   higher e.g. 50%)
2. Modify agent initialization to oversample unemployed-at-intake agents
3. Compute per-agent IS weights $L_i$ based on actual stratum vs natural rate
4. Save IS weights alongside per-agent panel data in pickle output

**Compatibility**: standard MC (no IS) should still work as `--strata-fraction-unemployed=natural`,
producing weights $L_i = 1$ for all agents. This preserves backward-compat.

**Validation in Phase 1**: with `--strata-fraction-unemployed=natural`, the
welfare estimator should match the existing MC pipeline bit-identically
(same agent selection, $L_i = 1$).

### Phase 2: IS-weighted welfare aggregator (~1 day)

**Where**: Modify `Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py`

**What**:
1. `compute_welfare6_table` reads per-agent IS weights from pickle
2. Replace agent sums with weight-aware sums:
   - Old: $\sum_i \Phi_i(t)$
   - New: $\sum_i L_i \cdot \Phi_i(t)$, normalized appropriately
3. Update NPV_AddInc and NPV_AddCons to use IS-weighted aggregates
4. Validate: with $L_i = 1$, output should match existing aggregator bit-identically

### Phase 3: Validate at Reduced_Run (~1 day)

**What**:
1. Run standard MC (no IS) at Reduced_Run, multiple seeds, get UI welfare SE
   - Expected: 27% swings (per existing data) → SE ~5% relative for ui_rec
2. Run MC + IS (50% oversampled unemployed) at Reduced_Run, multiple seeds
   - Expected: SE drops to <1% relative for ui_rec
3. Compute the variance reduction factor (target: ~25-50×)
4. Cross-check that the IS-weighted MEAN is unbiased (matches standard MC mean
   within standard MC SE)
5. Report findings

**Pass criterion**:
- IS gives same MEAN as standard MC (within standard MC's SE)
- IS gives substantially lower SE for UI (target: SE < 1% relative)
- Code is robust (no NaN, no negative weights, etc.)

If Phase 3 passes: proceed to Phase 4.
If Phase 3 fails: diagnose, iterate.

### Phase 4 (HELD pending Phase 3): Baseline production run (~half day wall + analysis)

**What**:
1. Run MC + IS at Baseline scope, single seed (or multi-seed for headline SE)
2. Compute final welfare-6 table
3. Update paper LaTeX (`Tables/Baseline/welfare6.tex`) using IS-corrected MC values
4. Compare to published paper UI values for sanity

**Hold rationale**: don't burn Baseline wall hours until variance reduction
is demonstrated at Reduced_Run.

## Files to be created / modified

### New files (Phase 1-2)
- `Code/HA-Models/FromPandemicCode/welfare6_scenario_IS.py` (or extend existing)
- `Code/HA-Models/FromPandemicCode/welfare6_aggregator_IS.py` (or extend existing)
- `conclusions_private/2026-05-10_MC_IS_design.md` (this plan)
- `conclusions_private/2026-05-XX_MC_IS_phase3_validation.md` (Phase 3 results)

### Modified files (Phase 1-2)
- `Code/HA-Models/FromPandemicCode/welfare6_scenario.py` — add IS stratification
- `Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py` — IS-aware aggregator

### Files NOT to touch (preserved as alternative analytics)
- `Code/HA-Models/FromPandemicCode/welfare6_tm.py` (TM-a welfare research code)
- `Code/HA-Models/FromPandemicCode/welfare6_tm_bucket.py` (per-bucket aggregator)
- `Code/HA-Models/FromPandemicCode/welfare6_tm_stratified.py` (stratified rep-agent)
- `Code/HA-Models/FromPandemicCode/welfare6_tm_repagent.py` (rep-agent)
- These remain available for sensitivity analysis or alternative validation

## Key invariants to maintain

1. **CRN preservation**: agent $i$'s seed must be identical across pol/none/base
   under IS (just as in standard MC). IS only changes which agents are SAMPLED;
   CRN coupling within each sampled agent is preserved.

2. **Backward compatibility**: `--strata-fraction-unemployed=natural` (or
   default) must reproduce existing MC output bit-identically. This enables
   regression testing.

3. **Unbiased mean**: $\mathbb{E}_Q[L \cdot \Phi] = \mathbb{E}_\pi[\Phi]$ by IS construction.
   The IS estimator should converge to the same true value as standard MC.

4. **Skip ui_norec**: per `feedback_ui_norec_never_report.md`, ui_norec must
   be omitted from all welfare outputs regardless of method.

5. **Test infrastructure preservation**: `validate_mc_crn.py` should still
   pass — IS doesn't break CRN.

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| IS weights blow up if Q has near-zero mass where π has mass | Low (we control Q) | Choose Q to envelope π well; cap $L_i$ if needed |
| Stratification breaks HARK's RNG seeding convention | Medium | Phase 1 includes regression test that natural-rate IS = standard MC |
| UI welfare SE doesn't drop as much as expected | Medium | Try finer stratification (path-conditional) in Phase 2/3 iteration |
| Standard MC vs IS-MC means differ (bias indicator) | Low | Phase 3 explicitly tests this; bias is alarm signal to iterate |
| Phase 3 wall-time exceeds expectations | Low | Reduced_Run is small; should be ~minutes per run |

## Success criteria

After Phase 3:
- IS variance reduction factor for UI: **≥25×** (target: ~50×)
- IS-MC mean matches standard-MC mean within standard MC's 95% CI
- Code is clean, documented, regression-tested
- Decision can be made on Phase 4 with confidence

## What I'm NOT doing in this plan

- TM-a infrastructure remains intact (welfare6_tm*.py kept as reference)
- HARK's MC core not modified (only welfare6_scenario.py wraps it)
- No changes to multipliers / spending pipeline (orthogonal)
- No paper LaTeX updates until Phase 4 complete
- ui_norec stays excluded throughout (memory-enforced rule)
