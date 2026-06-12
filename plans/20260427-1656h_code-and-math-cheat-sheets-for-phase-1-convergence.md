# Sub-plan: paired code-cheat-sheet + math-cheat-sheet for Phase 1 convergence validation

**Date:** 2026-04-27
**Parent plan:** `plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md` (Phase 1)
**Predecessor pattern:** `plans/20260427-1512h_code-and-math-cheat-sheets-for-tm-a-esc.md` (the Phase 0.1 sub-plan that this one mirrors)
**Companion math reference:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/why_TM_a_kernel.md`

## 1. Purpose

Apply the same paired-cheat-sheet pattern that worked for Phase 0.1 to Phase 1's convergence validation work, with one important inversion of workflow:

- **Phase 0.1** mapped existing kernel CODE → existing MATH (and added math labels for unlabeled operations).
- **Phase 1** maps validation CLAIMS (which start as math) → tests TO BE WRITTEN (the cascade-gated MC↔TM convergence harness). Math labels exist or get derived first; test design then references them.

The sub-plan produces:
1. **Math-cheat-sheet** for convergence claims (`math_cheatsheet_phase1_convergence.md`): per labeled equation related to MC↔TM convergence, the test(s) that validate it, plus the tier (L3a/b/c/d) at which validation happens.
2. **Code-cheat-sheet** for test harnesses (`code_cheatsheet_phase1_convergence.md`): per test function/harness, which labeled equations it validates and the pass/fail criterion.
3. **Updates to math docs** for any convergence-related claim a test exercises that lacks a labeled equation. Pause-and-derive discipline (per Phase 0.1 sub-plan §3) applies here too.

The cheat-sheets are the **specification** for the Phase 1 test harness implementation work, and the **reference** for diagnosing failures.

## 2. Deliverables

### 2.1 Math-cheat-sheet (convergence claims)

**File:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/math_cheatsheet_phase1_convergence.md`

For each labeled convergence-related equation, document:
- Label, statement, source doc + section
- Validation strategy (MC sweep on N, TM sweep on grid, cross-method comparison, etc.)
- Tier at which the validation runs (L3a / L3b / L3c / L3d)
- HALT criterion if validation fails

Likely equations to cover (some exist; others to be labeled in step 5.4 below):

| Label | Statement | Validates |
|---|---|---|
| `(eq:mc-mean)` | $\bar X_N = (1/N) \sum X_i$ — MC ergodic-mean estimator | MC point estimate |
| `(eq:asymptotic-rate)` | $\text{std}/\sqrt{N} \to 0$ — MC SE shrinks like $1/\sqrt{N}$ | MC sweep convergence |
| `(eq:tm-discretization-error)` | $|M_{\text{TM}}(\text{grid}) - M_{\text{TM}}^{*}| \to 0$ as grid → fine | TM grid-refinement convergence |
| `(eq:cross-method-convergence)` | $\|M_{\text{MC}}^{*} - M_{\text{TM}}^{*}\| < \epsilon$ — the gate criterion | MC↔TM agreement at the limit |
| `(eq:welfare-aggregator-tm)` | $W = \sum_{a, j} p(a, j) \int u(\cdot)\,dF_{(\psi, y)\|j}$ | Welfare aggregator from TM ergodic |
| `(eq:lorenz-tm)` | Lorenz-percentiles aggregator over TM ergodic | Wealth distribution moments from TM |
| `(eq:K-Y-cross-method)` | MC and TM agree on K/Y at the limit | Tier-3 sign-off claim |

Some of these (`(eq:K-Y-aggregator)` etc.) may already exist; others need to be derived and added to `why_TM_a_kernel.md` or a new `why_convergence_validation.md` doc.

### 2.2 Code-cheat-sheet (test harness)

**File:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/code_cheatsheet_phase1_convergence.md`

For each test function or harness in the Phase 1 implementation:
- Function name, source file, purpose
- Configuration parameters (cohort scope, AgentCount range, TM grid range)
- Math equation(s) it validates (cross-reference to math-cheat-sheet)
- Pass criterion (specific tolerance, threshold)
- HALT criterion (what failure looks like)
- Tier (L3a/b/c/d)
- Estimated cost

Typical entry skeleton:

```markdown
## test_mc_sweep_convergence_HS  (L3a; ~hr compute)

**File:** `Code/HA-Models/FromPandemicCode/test_phase1_l3a_mc_sweep.py`
**Purpose:** verify MC ergodic-mean estimator converges as N → ∞ for HS cohort.

**Configuration:**
- Cohort: HS (edType=1) only
- N ∈ {500, 1k, 5k}
- 5 random seeds per N
- Moments tracked: mean wealth, K/Y, mean consumption

**Math equations validated:**
- `(eq:mc-mean)` — point estimate convergence
- `(eq:asymptotic-rate)` — SE shrinks as 1/√N

**Pass criterion:** for each moment M, observed std-across-seeds at each
N satisfies `std(M | N) ≈ const · 1/√N` within 20%; mean(M | N) appears
to stabilize as N grows.

**HALT criterion:** SE doesn't shrink with N (MC noise non-i.i.d.); OR
mean(M) drifts >5% across N (something is wrong with the simulator).

**Cost:** ~1-2 hr compute (parallel-safe across seeds + N values).
```

### 2.3 Math-doc updates

For any convergence claim a test exercises without an existing labeled equation:
- Derive the math
- Add labeled equation to appropriate doc (recommend a new `why_convergence_validation.md` doc for convergence-specific math, OR add to `why_TM_a_kernel.md` §12 for kernel-property claims)
- Then cross-reference

## 3. Process

```
For each tier T in {L3a, L3b, L3c, L3d}:
    For each math claim C this tier needs to validate:
        1. Look up C in existing math docs
        2. If labeled: cross-reference in math-cheat-sheet
           If unlabeled: STOP. Derive. Add labeled equation. Then cross-reference.
        3. Specify the test harness for C at tier T:
           - what configuration (cohort scope, N range, grid range)
           - what to measure
           - what pass/fail criteria
        4. Add code-cheat-sheet entry for the harness
        5. Add reverse entry to math-cheat-sheet
```

The harness CODE itself doesn't get written in this sub-plan — only the SPECIFICATION (what to test, what to validate, what tolerance, what HALT). Implementation lives in subsequent Phase 1 work.

## 4. Equation-naming convention

Reuses the convention from `plans/20260427-1512h` §4. New convergence-specific labels follow `(eq:<topic>-<aspect>)`:
- `(eq:mc-mean)`, `(eq:mc-se)`, `(eq:asymptotic-rate)` — MC estimator properties
- `(eq:tm-discretization-error)`, `(eq:tm-refinement-rate)` — TM convergence
- `(eq:cross-method-convergence)`, `(eq:cross-method-tolerance)` — gate criteria
- `(eq:K-Y-cross-method)`, `(eq:welfare-cross-method)` — moment-specific cross-method claims

## 5. Plan steps

| Step | What | Cost |
|---|---|---|
| 5.1 | Inventory existing convergence-related labels (search Phase 1 / Phase 0 docs + `test_mc_convergence.py`'s implicit math) | ~30 min |
| 5.2 | Enumerate convergence claims that Phase 1 must validate at each tier (L3a-L3d) | ~30 min |
| 5.3 | For each claim: lookup math; flag gaps | ~30 min |
| 5.4 | **Pause-and-derive:** for each gap, derive math, add labeled equation, decide which doc (likely a new `why_convergence_validation.md`) | ~1-2 hr |
| 5.5 | Write code-cheat-sheet for the planned test harness (per-function entries with config, pass/fail, HALT) | ~2 hr |
| 5.6 | Write math-cheat-sheet (reverse index over labeled equations + which test/tier validates each) | ~1 hr |
| 5.7 | Final consistency pass | ~30 min |
| 5.8 | Commit + push | as we go |

**Total: ~5-7 hr.** Same scale as the Phase 0.1 sub-plan. No estimation/compute in the sub-plan itself.

## 6. Sign-off criteria

- Every test harness in the planned Phase 1 implementation has a code-cheat-sheet entry referencing labeled validation claims.
- Every labeled convergence claim has a code-cheat-sheet entry showing which test validates it and at which tier.
- No "TBD math" entries; every claim either matches existing math or is backed by a newly-derived labeled equation.
- The sub-plan output (the cheat-sheets) becomes the SPECIFICATION for the Phase 1 implementation work — `test_phase1_l3a_*.py`, `test_phase1_l3b_*.py`, etc. should be straightforwardly derivable from the per-tier code-cheat-sheet entries.

## 7. Position in parent plan

This sub-plan executes BEFORE the Phase 1 implementation begins. The parent plan's Phase 1 §5.4 sub-tasks (1.0-1.12) are augmented as follows:

```
1.0a   [NEW] Execute the cheat-sheets sub-plan (this file). ~5-7 hr.
       Output: paired math-cheat-sheet + code-cheat-sheet for convergence
       validation, plus any newly-labeled equations in math docs.
1.0b   [WAS 1.0] CDC MC↔TM convergence sanity at L3a (precondition gate)
1.1-1.12   (implementation steps; now driven by cheat-sheets as spec)
```

Alternatively, this sub-plan can be executed in parallel with 1.1-1.4 (test harness scaffolding) — they're code edits in different files. The cheat-sheets then become the spec the harness writers consult.

## 8. Why this sub-plan matters

Phase 0.1's experience showed: paired cheat-sheets caught the four "needs verification under ESC" flags in `compute_type_aggregates_tm_a` / `compute_period_aggregates_tm_a` / `propagate_experiment_tm_a` (the (eq:check-level-decomp) interpretation question, the c_actual semantic question, the A_nrm rescaling question). Without the systematic audit those would have been "discovered" as ESC-vs-CDC test failures during Phase 1, costing hours each to debug.

For Phase 1, the analogous risk is: writing a convergence test harness that asserts the wrong tolerance, OR that validates the wrong moment, OR that misses a structural failure mode. The math-cheat-sheet's rigor (every claim labeled, every test cross-referenced) catches "I assumed this should converge to X but actually the math says Y" before the harness runs.

## 9. What this sub-plan does NOT do

- Does NOT write the actual Phase 1 test harnesses (`test_phase1_l3a_*.py` etc.). That's downstream implementation.
- Does NOT run any compute. Sub-plan output is documentation only.
- Does NOT change the cascade-gating structure (L3a → L3b → L3c → L3d). That's already in the parent plan §5.0.
