---
date: 2026-05-06
status: plan-resolved-partially
keywords: [edu_share, aggregation, cohort-N-override, shuffle-friendly, MC-TM-convergence, BUG-042]
resolution_summary: |
  Implemented HAFISCAL_AGGREGATE_BY_EDU_SHARE switch (default auto, activates
  when HAFISCAL_AGENTCOUNT_* override is in effect). Smoke test confirmed
  pop_rescale_factor=1 under standard config (bit-identical to no-rescale).
  Re-ran convergence study: aggregation fix closed the noAD residual to ~zero
  (Check noAD +0.14% → +0.01%) but the bulk of the AD residual remained
  (Check AD +1.70% → +1.59%, only -0.11pp closed; TaxCut similarly).
  Diagnosis: the AD-loop iteration mechanism (MC trains CFunc from agent
  sample, TM from analytical ergodic) converges to different fixed points
  beyond the aggregation issue. Multipliers themselves shifted +3-5% from
  the population reweighting (HS now properly weighted at 52.7%).
related_conclusions:
  - 2026-05-06_RESOLVED_per_cohort_drift_is_mc_sampling_noise.md
related_memory:
  - project_shuffle_friendly_recalibration.md
  - feedback_no_default_reestimation.md
---

# Plan: edu-share-respecting aggregation when cohort-N is overridden

## Context

The 1.7% MC-vs-TM AD-multiplier residual under the shuffle-friendly cohort-N
override (D=4900, HS=9800, C=17640) traces to an aggregation bug:

- HAFiscal aggregates per-cohort contributions weighted by raw `AgentCount`
  (`tm_methods.py:1247`: `level_scale = tr['AgentCount'] * tr['E_pLvl']`).
- This works correctly under the standard config because
  `AgentCount = AgentCountTotal × data_EducShares[e] × beta_pmv` makes
  AgentCount proportional to data_EducShares by construction.
- Under the shuffle-friendly cohort-N override (set via
  `HAFISCAL_AGENTCOUNT_{D,H,C}` env vars), AgentCount no longer respects
  data_EducShares: implicit weights become (15.1%, 30.3%, 54.6%) vs true
  edu shares (9.3%, 52.7%, 38.0%).
- Result: aggregates compute averages over a fictitious population mix.
  D over-represented 5.5×, HS under-represented 3.6×, C over-represented 1.7×.

This affects both MC and TM aggregation. The 1.7% AD-multiplier residual
in the convergence study (2026-05-06) is mostly this aggregation issue,
not a true MC-vs-TM method gap.

## Math: what the correct aggregate should be

The correct population aggregate for any per-period quantity X (income,
consumption, etc.) is:

    AggX_population = N_pop_ref × Σ_e edu_share_e × E[X | cohort e]

where E[X | cohort e] is estimated from the per-cohort sample/analytical:

    E[X | cohort e] = (1/AgentCount_e) × Σ_{i in cohort e} X_i      (MC)
    E[X | cohort e] = E_p[X_e]                                       (TM)

The current code computes:

    AggX_current = Σ_e Σ_{i in cohort e} X_i = Σ_e AgentCount_e × E[X | cohort e]

For `AgentCount_e ∝ edu_share_e`, current = correct (up to a constant factor).
Under cohort-N override, current ≠ correct.

The correction: replace `AgentCount_e` weights with `N_pop_ref × edu_share_e ×
beta_pmv` weights at the aggregation sites.

Equivalent: leave AgentCount weights alone, but introduce a per-cohort
**rescale factor** `r_e = (N_pop_ref × edu_share_e × beta_pmv) / AgentCount_e`
applied at the aggregation site.

When AgentCount = N_pop_ref × edu_share_e × beta_pmv (standard config),
r_e = 1 and nothing changes. When AgentCount is overridden, r_e ≠ 1
and the correction takes effect.

## Implementation

### Step 1: Audit aggregation sites

Identify every place in the code where per-cohort aggregates get summed
into population totals. Search terms:
- `tr['AgentCount']`
- `level_scale`
- `agent.AgentCount` followed by aggregate summation
- `AggCons +=`, `AggIncome +=`, `AggCons[t] +=`
- `level_scale = N * E_pLvl` patterns

Likely locations:
- `tm_methods.py` baseline aggregator (around line 1247) and experiment
  aggregator (around line 2525)
- `AggFiscalModel.py` `AggregateDemandEconomy.mill_rule` and related
- Any welfare aggregation paths (Step-5b, but out of scope for this plan)

For each site, document:
- Which quantity is being aggregated
- Whether the rescale needs to apply

### Step 2: Implement the env-controlled rescale

Add an env var: `HAFISCAL_AGGREGATE_BY_EDU_SHARE` (default: `auto`).

- `off` / `0` / `false`: no rescale (current behavior)
- `on` / `1` / `true`: explicit rescale by `r_e = N_ref × edu_share_e ×
  beta_pmv / AgentCount_e` at each aggregation site
- `auto` (default): rescale ONLY when any `HAFISCAL_AGENTCOUNT_*` override
  env var is set (otherwise standard config; rescale = identity)

The factor `r_e` needs to be available wherever aggregation happens.
Either pass it as a per-agent attribute (`agent.edu_share_rescale_factor`)
or compute it at aggregation time from cached config.

`N_ref` is the implied total population for the standard config:
`AgentCountTotal` (10000 for Baseline, 5000 for Reduced_Run). With the
override, we want the aggregate to behave AS IF AgentCount per cohort
were `N_ref × edu_share × beta_pmv`.

### Step 3: Smoke test — identity check under standard config

Run a smoke test at the standard config (no AgentCount overrides). With
the new switch on, results MUST match with the switch off. This verifies
the rescale factor is exactly 1 under the standard config.

Cell: 1 seed at AgentCountTotal=5000 (Reduced_Run default) with
sim_method='both'. Compare two runs:
- With `HAFISCAL_AGGREGATE_BY_EDU_SHARE=off`: baseline
- With `HAFISCAL_AGGREGATE_BY_EDU_SHARE=on`: should match exactly

If results differ (within numerical precision), there's a bug.

### Step 4: Re-run the convergence study with rescale on

Re-run the same 8-cell convergence study from earlier today, but with the
edu-share rescale active. Cells:

- 6 'both' runs at shuffle-friendly cohort N (D=4900/9800, HS=9800/19600,
  C=17640/35280) × 3 seeds × 2 quotas
- 2 TM-only runs at mCount=100, 200

Same other settings (ESC, perm_shocks=off, AD tol 1e-3 + 15 iter, all
shuffles ON, friendly urates).

Wall: ~80 min parallel (limited by mCount=200).

### Step 5: Compare to pre-correction results

Tabulate Check / TaxCut multipliers at noAD/1stAD/AD scopes:
- Without rescale (today's results): MC-TM AD residual ~+1.7%
- With rescale: expected residual MUCH smaller (likely <0.5%)

If residual closes to <0.5%, the methods converge under correct edu-share
aggregation. Hypothesis confirmed.

If residual stays large, there's a deeper issue beyond aggregation
(perhaps: per-cohort within-cohort sampling-vs-analytical bias, the
phase-out non-linearity I flagged earlier, or a different bug).

### Step 6: Document and commit

If Step 5 closes the residual:
- Move this plan to `status: resolved`
- Add a memory entry pointing to this resolution
- Add the finding to a conclusions doc
- Land the env var as default-on (or change it to default-on under
  any AgentCount override)

If Step 5 doesn't close:
- Phase D-2: investigate the within-cohort residual
- Likely path: per-cohort MC sample pLvl distribution vs analytical;
  test whether the Check phase-out non-linearity creates within-cohort
  artifacts even at large per-cohort N.

## Wall budget

- Step 1 (audit): ~30 min
- Step 2 (implement): ~45 min
- Step 3 (smoke test): ~30 min wall (1 cell at standard config)
- Step 4 (re-run convergence): ~80 min wall (8 cells in parallel)
- Step 5 (analysis): ~30 min
- Step 6 (write up): ~30 min

Total: ~3-4 hr engineering + ~1.5 hr re-run wall.

## Decision point

If at Step 3 the smoke test fails (results differ between `off` and `on`
under standard config), HALT and debug — the rescale factor isn't
correctly computing 1.0 in the no-override case.

If at Step 5 the residual doesn't close, this plan is partially
successful (corrected the aggregation, identified the remaining gap).
Open follow-up plan for the within-cohort issue.

## Risks

- The audit (Step 1) might miss aggregation sites. Mitigation: write a
  unit test that exercises a known case where edu_share != AgentCount
  proportions and verifies all aggregate paths give correct results.
- Per-cohort-N path might exist that already does the right thing
  (e.g., welfare-6 might already use `edu_share` weights). Check for
  inconsistency between paths.
- The `N_ref` choice is a methodology decision. `N_ref = AgentCountTotal`
  preserves backward-compat with standard-config results. Document this.

## Linkage

This is BUG-042 (proposed). After resolution, candidate for memory entry
analogous to BUG-040 / BUG-041.
