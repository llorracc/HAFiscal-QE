# Plan: Drive College cohort-init MC drift below 1% — systematic test of math doc §24-25 convergence

**Author:** Claude Opus (max effort)
**Date:** 2026-05-01
**Status:** awaiting user approval before execution
**Source-of-truth math doc:** `history/20260331-mathematical-derivations-harmenberg.md` §24 (cohort-age decomposition), §25 (Q-twisted construction under cap)
**Predecessor work:** BUG-038 (branch `bug038-restore-T_age-cap`, commits 9484a503 through bbb56c79). The drift test under BUG-038 (commit `ee841013` baseline) currently shows College drift ~7-8% with `unemp_shocks='employed'` (counterfactual mode). Current measurement is contaminated by a model-mismatch between cohort init and MC dynamics — see §0.1 below.

---

## 0. Self-contained problem statement

Under math doc §24.5 (within-cohort lognormality), the cohort-age decomposition produces an MC initialization that, in the joint limit (`N → ∞`, `aCount → ∞`, continuous shocks), drives MC drift to zero. We want to test whether this convergence is empirically observable in HAFiscal at the College β=0.99 atom — currently the worst case for cohort drift (~8%).

### 0.1 The model-mismatch bug — and why we need a NEW IncShkDstn mode

#### The original mismatch

`harmenberg_cohort_drift_test.py` line ~110-114 calls `compute_cohort_age_decomposition_a(..., unemp_shocks='employed', ...)`. This **overrides** the unemployed-state IncShkDstn — including the transitory shock ξ — to use the employed distribution. The MC then runs the production model where unemployed states have degenerate ξ at `IncUnemp = 0.7`. So:

- **Init**: samples from a counterfactual "all-employed-shocks" model (model A)
- **MC dynamics**: production "degenerate-ξ-during-unemployment" model (model B)

Drift measures the discrepancy between models A and B, not the cohort method's intrinsic error.

#### What I initially proposed and why it's wrong

I initially thought the fix was to call `compute_cohort_age_decomposition_a(..., unemp_shocks='degenerate', ...)` — production-faithful, both init and MC use the same model. **But empirically the production agent's IncShkDstn has DEGENERATE ψ for all unemployed states** (verified):

| State | ψ atoms | ξ atoms |
|---|---|---|
| j=0 (employed) | 49 stochastic, σ²(ψ)=0.0028 | 49 stochastic |
| j=1,2 (unemployed w/ benefits) | 1 atom (ψ≡1) | 1 atom (ξ=IncUnemp) |
| j=3 (unemployed w/o benefits) | 1 atom (ψ≡1) | 1 atom (ξ=IncUnempNoBenefits) |

Despite `perm_shocks_during_unemployment = True` in EstimParameters.py, the IncShkDstn built by the test pipeline has degenerate ψ everywhere unemployed.

**Consequence for §24.5**: ψ is **NOT** iid across all states. log p | (K=k) depends on j-path: an all-employed agent has log p variance k·σ²_ψ; an all-unemployed agent has log p variance 0; mixed agents are between. The within-cohort lognormality is therefore an **approximation** in production, not exact.

#### The corrected fix: a new IncShkDstn mode

To test §24.5's math, we need to override ψ for unemployed states (make it stochastic with the employed distribution) WITHOUT overriding ξ (keep degenerate at IncUnemp). The `unemp_shocks='employed'` mode overrides both; the `unemp_shocks='degenerate'` mode overrides neither. We need a third option.

**Proposed new mode: `unemp_shocks='perm_only'`** — for each unemployed state j ∈ {1,2,3}, construct a new IncShkDstn:
- ψ atoms = employed ψ atoms (49 atoms, stochastic)
- ξ = single atom at the production unemployment income (IncUnemp for j ∈ {1,2}, IncUnempNoBenefits for j=3)
- joint atoms = `(ψ_i, ξ_unemp)` with employed ψ probabilities

Under this mode, ψ is iid across all states (§24.5 condition met), but ξ during unemployment is still the low value the paper specifies.

#### And the MC must use the same model

To eliminate the model mismatch, the MC's `agent.IncShkDstn` must also be modified to use this hybrid distribution. The test driver will:

1. Construct the hybrid IncShkDstn per unemployed state
2. Assign it to `agent.IncShkDstn` BEFORE the MC runs
3. Pass the same hybrid into `compute_cohort_age_decomposition_a` via the new `unemp_shocks='perm_only'` mode

This is a **counterfactual model** (paper specifies no ψ shocks during unemployment). The test is: does drift go to zero in this counterfactual where §24.5 holds exactly? If yes, the math is empirically validated; we then know production's residual drift comes from the degenerate-ψ approximation, which is a model choice rather than a method bug.

---

## 1. What we expect to find

If the math doc §24-25 is right and the implementation is correct:

1. **With production-faithful `unemp_shocks='degenerate'`**: drift drops dramatically (because the model mismatch is eliminated). Predicted drift floor ~MC sample noise (`σ(a)/√N`), which at N=200k is sub-percent.

2. **Increasing N**: drift scales as `1/√N`. Going from N=200k to N=2M should reduce drift by ~3×.

3. **Increasing aCount (TM grid)**: tighter bound on TM discretization. Going from 200 to 500 grid points should reduce TM-side discretization error.

4. **Increasing T_age (cap)**: minor effect (cap-truncation tail for sub-1% should already be negligible at T=200; tail mass at age 200 is ~28% of population so cap matters for moments but not for cell-level distributions).

5. **Increasing PermShkCount (shock atoms)**: moves toward continuous-shock limit; should make the within-cohort lognormality even tighter.

If actual results don't match these predictions, that's diagnostic — points to either an implementation issue or a misstatement in the math.

---

## 2. Tier-gated test cascade (College only)

All tests run on College β=atom[5] (current β=0.9908) with CDC interpretation only (saves ~50% time vs CDC+ESC). Pass criterion at each tier: cohort drift |E_Q[a]_t=200 / E_Q[a]_t=0 - 1| < threshold.

Halt cascade if a tier fails — investigate before proceeding.

### Tier 0: counterfactual where §24.5 holds exactly

Setup:
- N = 200k (current default)
- aCount = 200 (current default)
- T_age = 200 (current production)
- PermShkCount = 7 (current default)
- T_sim = 205 (current default)
- **New `unemp_shocks='perm_only'` mode** (ψ stochastic in all states, ξ degenerate at IncUnemp during unemployment)
- **MC's `agent.IncShkDstn` modified to match** (using the same hybrid distribution)

Hypothesis: drift drops from ~8% to <2% — to MC sample noise + TM grid discretization floor.

Pass criterion: drift < 2%.

Time: ~1 min after the test script + mode addition.

If FAIL: §24.5 math doesn't hold even under the counterfactual where its conditions are met — implementation bug, or the propagation of the new mode isn't actually consistent between cohort dec and MC.

If PASS: §24.5 math empirically validated. Proceed to Tier 1 to test the `1/√N` scaling prediction.

If we then want to compare to PRODUCTION (degenerate ψ everywhere unemployed): a separate "Tier 0p" run with `unemp_shocks='degenerate'` and unmodified MC would tell us how much of the 8% drift was the model-mismatch fix vs. the structural lognormality approximation. Optional add-on, not gating.

### Tier 1: scale up N (tests `1/√N` MC noise floor)

Setup: as Tier 0, but vary N ∈ {200k, 500k, 1M, 2M}.

Hypothesis: drift scales as `1/√N` (LLN-bounded). Going 200k → 2M should reduce drift by ~`√10 ≈ 3.2×`. Empirical fit of drift vs `1/√N` should be linear.

Pass criterion: 
- Linear fit `drift = a/√N + b` with R² > 0.9
- Intercept `b` < 1% (the structural floor, independent of MC sampling noise)

Time: ~10 min total (4 runs × ~2.5 min each at N=2M).

If FAIL with low R²: drift not bounded by MC noise alone — look for systematic source (e.g., burn-in, init bug).

If FAIL with intercept > 1%: structural error from grid/discretization/etc. dominates MC noise — proceed to Tier 2.

### Tier 2: TM grid resolution (aCount)

Setup: N = 1M (sub-percent MC noise), vary aCount ∈ {200, 500, 1000}.

Hypothesis: drift converges as aCount increases. Saturation curve.

Pass criterion: drift at aCount=1000 within 0.2% of drift at aCount=500 (saturated).

Time: ~15 min total. The TM kernel build at aCount=1000 is ~25× slower than at aCount=200 (sparse matrix grows quadratically), and the cohort sum needs more matvecs.

If FAIL: TM grid discretization is a real bottleneck — the `aCount` choice is more constraining than expected.

### Tier 3: cap value T_age (mild expected effect)

Setup: as Tier 2 best (N=1M, aCount=500), vary T_age ∈ {200, 480, 800}.

Hypothesis: drift mostly invariant (cap-truncation tail at T=200 is L^200 ≈ 28% of population; for the (a,j) marginal at age 200 this is mass that exists in MC and gets force-killed; init samples from same truncated distribution; consistent).

Pass criterion: drift varies by less than 0.5% across T_age values.

Time: ~20 min total.

If FAIL: cap value materially affects drift even at consistent settings — would require deeper investigation.

### Tier 4: shock discretization (PermShkCount)

Setup: as Tier 3 best, vary PermShkCount ∈ {7, 11, 15}.

Hypothesis: drift mildly improves as PermShkCount → ∞ (within-cohort lognormality becomes tighter against discrete-shock approximation).

Pass criterion: drift at PermShkCount=15 within 0.3% of PermShkCount=11.

Time: ~30 min total.

If FAIL: shock discretization is a primary error source — would suggest matching first 13 moments isn't enough.

### Tier 5: combine best settings

Setup: best (N, aCount, T_age, PermShkCount) from Tiers 1-4.

Hypothesis: combined effect drives CO drift below 1%.

Pass criterion: **CO cohort drift < 1%**.

If PASS: §24-25 math empirically validated; report the parameter recipe.

If FAIL: report the residual drift sources and propose follow-up investigation.

Time: ~5 min for the single combined run.

---

## 3. Implementation

### 3.1 Add new `unemp_shocks='perm_only'` mode to `compute_cohort_age_decomposition_a`

`tm_methods.py:3503-3508` currently has:
```python
IncShkDstn_list = list(agent.IncShkDstn[0])
if unemp_shocks == 'employed':
    for jp in range(1, J):
        IncShkDstn_list[jp] = IncShkDstn_list[0]
```

Add a third branch:
```python
elif unemp_shocks == 'perm_only':
    # Construct hybrid: employed ψ atoms × degenerate ξ at IncUnemp / IncUnempNoBenefits
    # for each unemployed state. ψ is iid across all states (§24.5 condition met),
    # ξ stays at the production unemployment income.
    employed_dist = IncShkDstn_list[0]
    psi_atoms = employed_dist.atoms[0]
    psi_probs = employed_dist.pmv  # marginal over psi (since employed has joint psi×xi)
    # ... compute marginal ψ probs, build hybrid joint dist with degenerate ξ
    for jp in range(1, J):
        old_xi = IncShkDstn_list[jp].atoms[1][0]  # the production ξ for state jp
        IncShkDstn_list[jp] = build_joint(psi_atoms, [old_xi], psi_probs)
```

Update the docstring and the `if unemp_shocks not in (...)` validation at line 3486.

### 3.2 Helper to construct the hybrid IncShkDstn for use in MC

A small helper function (in test script or as a utility) that builds the hybrid IncShkDstn list and assigns it to `agent.IncShkDstn` so the MC dynamics match.

### 3.3 Test driver (single new script)

`Code/HA-Models/FromPandemicCode/test_co_drift_sweep.py` (new): standalone script that runs the cascade. Takes env vars for which tier to run.

```python
# Pseudocode
for tier in [0, 1, 2, 3, 4, 5]:
    if tier in tiers_to_run:
        configs = tier_configs[tier]
        results = []
        for cfg in configs:
            agent = build_agent_for(2, beta_co_atom5, ctx)
            # Modify MC's IncShkDstn to match the cohort dec's perm_only mode
            install_perm_only_IncShkDstn(agent)
            tm_data = build_tm_agg_fiscal_a(agent, aCount=cfg['aCount'])
            cohort_dec = compute_cohort_age_decomposition_a(
                agent, tm_data,
                unemp_shocks='perm_only',  # NEW: psi stochastic, xi degenerate
                T_age=cfg['T_age'],
                # ... PermShkCount, etc.
            )
            results.append(run_drift_mc(agent, cohort_dec, N=cfg['N'], T_sim=cfg['T_sim']))
        report_tier(tier, results)
        if not tier_passed(tier, results):
            break  # halt cascade
```

### 3.4 What's modified vs. not

**Modified:**
- `tm_methods.py`: add `unemp_shocks='perm_only'` mode to `compute_cohort_age_decomposition_a` (~15 LOC)

**Not modified:**
- Production parameters (`Parameters.py`, `EstimParameters.py`) — no behavior change
- `harmenberg_cohort_drift_test.py` — stays with `unemp_shocks='employed'` for backward comparability
- Production agent's IncShkDstn — modified ONLY in the test script's local scope

The `unemp_shocks='perm_only'` mode is a **test-only counterfactual** — it's not the production model. We use it to validate §24.5's math empirically.

### 3.3 Cost

| Tier | Wall-clock | Cumulative |
|---|---|---|
| 0 | ~1 min | 1 min |
| 1 (4 runs) | ~10 min | 11 min |
| 2 (3 runs at N=1M) | ~15 min | 26 min |
| 3 (3 runs) | ~20 min | 46 min |
| 4 (3 runs at PermShkCount=15) | ~30 min | 76 min |
| 5 (1 run) | ~5 min | 81 min |

Worst case ~80 min total if all tiers run.

---

## 4. Output deliverables

1. **Test script**: `Code/HA-Models/FromPandemicCode/test_co_drift_sweep.py`
2. **Conclusions log**: `conclusions_private/2026-05-01_co-drift-sub-1pct-validation.md` — reports tier-by-tier results, fitted scaling laws, parameter recipe (if found) for sub-1% drift, and any anomalies.
3. **(Optional) Math doc cross-reference**: if Tier 0 confirms model-mismatch was the cause, add a brief note to math doc §24.14 / §25.10 clarifying the production-faithful settings to use.

---

## 5. What this is NOT

- NOT a production calibration change (no Parameters.py / EstimParameters.py edits)
- NOT a recalibration (β, ∇ stay where they are)
- NOT a re-run of Step 5 multipliers
- NOT pursuing higher-moment per-cell fits (per user feedback: §24.5 lognormality is exact under the counterfactual model where ψ is iid across all states, so 2-moment fit is theoretically optimal; higher-moment fits would only inject estimation noise)
- NOT modifying the existing `harmenberg_cohort_drift_test.py` (it stays for backward comparability)
- The new `unemp_shocks='perm_only'` mode added to `tm_methods.py` is a **test-only counterfactual** — not the production model, not used by any production code path. The `Parametrization='Baseline'` Step 5 pipeline continues to use the production IncShkDstn unchanged.

---

## 5.1 Theoretical clarification

The user's intuition was correct: we want ψ stochastic in all states (so §24.5 lognormality applies exactly) WITHOUT modifying ξ in unemployment (which legitimately captures the low-income economics of unemployment spells). The TM-a kernel handles state-dependent ξ correctly; the §24.5 proposition does not require state-independent ξ. The `unemp_shocks='employed'` existing mode overrides BOTH ψ and ξ — too aggressive. The `unemp_shocks='degenerate'` mode overrides NEITHER (uses production IncShkDstn as-is). Production has degenerate ψ in unemployment, so neither existing mode meets §24.5's exact condition. Hence the need for `unemp_shocks='perm_only'`.

---

## 6. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Tier 0 doesn't drop drift much (model-mismatch wasn't the issue) | High | Investigation before continuing — could indicate other init-vs-dynamics inconsistencies |
| Drift floor > 1% even at best settings | Medium | Document the residual and the parameter values that minimize it; report what's blocking sub-1% |
| Compute exceeds 80 min (e.g., aCount=1000 turns out to be 100× slower than expected) | Low | Drop highest-aCount config; report partial results |
| Bug in test script (gives misleading drift values) | Medium | Sanity-check against Tier 0 result matching `harmenberg_cohort_drift_test.py` if same `unemp_shocks` is used |

---

## 7. Authorization

Not yet authorized. Awaiting user "go" to proceed with execution.

If authorized, I'll:
1. Write the test script
2. Run Tier 0 (1 min) and report
3. Run Tier 1 (10 min) and report  
4. Continue cascading or halt per pass/fail at each tier
5. Write up final conclusions log

If a tier fails unexpectedly, I'll halt and report rather than push through.
