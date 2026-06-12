---
date: 2026-05-03
status: phases-1-4-implemented-2026-05-03; phase-5-deferred (see memory feedback_deferred_followups.md)
keywords: [perm_shocks_during_unemployment, pLvl, Harmenberg, QE-matching, drift, config-management, profile]
related_bugs: []
related_plans: [20260503-1437h_mc_tma_companion_and_drift.md, 20260502-1256h_reproduce-sh-profile-machinery.md]
related_conclusions:
  - 2026-05-03_var-log-p-drift-investigation.md
---

> **Implementation status (2026-05-03):**
> - **Phase 1 (consistency assertion):** DONE — `Simulate.py` raises if rebuilt unemployed PermShk variance disagrees with the flag.
> - **Phase 2 (env-var selection):** DONE — `EstimParameters.py` reads `HAFISCAL_PERM_DURING_UNEMP={on,off,1,0,true,false,yes,no}`; default = on (Harmenberg). Each `reproduce.sh` profile sets it explicitly: `qe_fidelity` → off; `production_current`, `production_fast`, `tm_throughout_fast`, `mc_throughout_validation` → on.
> - **Phase 3 (config-aware drift threshold):** DONE — `_tm_a_drift.assess_and_report` now takes `agent=...`; Config A uses `threshold` (3% default), Config B uses `max(threshold*4, 0.12)` (12% floor) for var log(p) only.
> - **Phase 4 (Config B documentation note):** DONE — drift report prepends a note explaining the (1-u) approximation when Config B is active.
> - **Phase 5 (exact non-lognormal analytical):** DEFERRED + tracked in memory `feedback_deferred_followups.md` item #1, plus a near-term follow-up (item #2) for cohort-specific numerical pLvl distributions under Config B.

> **User directives 2026-05-03 (post-draft):**
> 1. Do NOT pick a single default in EstimParameters.py. Instead, the
>    setting must DIFFER between `reproduce.sh` profiles:
>    - `qe_fidelity` (matching published QE) → `perm_shocks_during_unemp = OFF`
>    - All non-QE profiles → `perm_shocks_during_unemp = ON` (so Harmenberg
>      analytical calculations are correct)
> 2. Threshold 12% is fine as an interim. But ALSO need to numerically
>    compute cohort-specific approximate pLvl distributions for Config B
>    (QE-matching) — added as a tracked follow-up.
> 3. Same as #1 — default DIFFERS between profiles, not a single value.
> 4. Defer the exact-analytical Phase 5, but track it explicitly so we
>    revisit. (Saved in `feedback_deferred_followups.md` memory.)

# Two-config support: Harmenberg-style vs QE-matching, with consistent flag/data + appropriate drift thresholds

## Goal

Make the MC ⇄ TM-a companion infrastructure correctly handle two distinct configurations of the income process for unemployed agents, each with its own analytical pLvl distribution, init formula, and drift threshold.

## The two configurations

### Config A: Harmenberg-style (`perm_shocks_during_unemployment = True`)

**Economic assumption:** Permanent productivity shocks apply even during unemployment (i.e., a worker's "human capital" continues to evolve while unemployed). Transitory shocks may or may not apply.

**Why anyone uses this:** Required for the pLvl ⊥ Markov-state factorization that underlies the Harmenberg neutral-measure analytical machinery. Without it, the joint distribution `(pLvl, j)` cannot be cleanly factored.

**Implications:**
- `compute_pLvl_distribution` is **exact** — a mixture of lognormals over age cohorts.
- Init formula in `Simulate.py` matches the analytical mixture exactly (modulo sampling noise).
- MC steady-state matches the analytical to within sampling tolerance.
- **Tight drift threshold (0.03) is appropriate** for var log(p).

**IncShkDstn requirement:** unemployed-state `IncShkDstn[j>0]` must have the SAME PermShk distribution as employed (per `build_unemployed_inc_shk_dstn` line 110-113 — the `p_on=True, t_on=False` branch).

### Config B: QE-matching (`perm_shocks_during_unemployment = False`)

**Economic assumption:** When unemployed, the worker receives no permanent productivity revision (PermShk = 1). This is the assumption made in the published HAFiscal-QE paper.

**Why anyone uses this:** To reproduce the published HAFiscal-QE multipliers and welfare numbers, which use the QE income process.

**Implications:**
- pLvl distribution is **NOT lognormal** — it's a complicated mixture that depends on the agent's full Markov-state history.
- `compute_pLvl_distribution` with `(1-u)` scaling is an **approximation**, not exact.
- Init formula in `Simulate.py` uses the same approximation.
- MC simulates the true non-lognormal dynamics; will have systematic differences from the analytical approximation.
- **Looser drift threshold (≥ 0.10) is needed** for var log(p) — the analytical is an approximation, not a ground truth.

**IncShkDstn requirement:** unemployed-state `IncShkDstn[j>0]` must have PermShk = 1 (no variance) — the `p_on=False` branch of `build_unemployed_inc_shk_dstn` lines 104-108.

## Current state (the bug)

`EstimParameters.py:241` sets `perm_shocks_during_unemployment = True` (the Harmenberg flag).

But the actual IncShkDstn data has PermShk = 1 for unemployed states (the QE-matching data).

**Result:** flag and data CONTRADICT. The analytical formula reads the flag and uses Config A semantics; the MC and TM-a kernel use the data and effectively use Config B semantics. The companion drift test catches this as a -16% drift on D's var log(p) — which the test correctly flagged as a problem.

This contradiction has gone unnoticed because the only consumer of the analytical pLvl distribution prior to the drift test was Simulate.py's init formula — which uses the SAME (broken) flag-based formula and so is internally consistent (init produces ~analytical variance), even though both then diverge from MC reality.

## Plan

### Phase 1: enforce flag/data consistency (~1 hr)

Add an assertion in `Parameters.py` (or wherever IncShkDstn is constructed) that the unemployed-state PermShk distribution matches the flag:

```python
# After IncShkDstn is built:
psdu = getattr(agent, 'perm_shocks_during_unemployment', False)
unemployed_isd = agent.IncShkDstn[0][1]   # j=1 = first unemployed state
unemployed_perm_atoms = unemployed_isd.atoms[0]
unemployed_has_perm_var = (np.var(np.log(unemployed_perm_atoms)) > 1e-10)
if psdu != unemployed_has_perm_var:
    raise ValueError(
        f"Inconsistency: agent.perm_shocks_during_unemployment={psdu} "
        f"but unemployed IncShkDstn perm_var > 0 is {unemployed_has_perm_var}. "
        f"Either rebuild IncShkDstn to match the flag, or change the flag."
    )
```

This catches the existing contradiction immediately on import.

### Phase 2: explicit config selection (~1 hr)

Add an env var / Run_Dict entry to select the config:

```bash
HAFISCAL_PERM_DURING_UNEMP=on   # Harmenberg config (Config A)
HAFISCAL_PERM_DURING_UNEMP=off  # QE-matching config (Config B; current default per QE paper)
```

In `Parameters.py`, this env var sets BOTH `perm_shocks_during_unemployment` AND triggers the appropriate `build_unemployed_inc_shk_dstn` branch — guaranteeing flag/data consistency.

Default: **off** (QE-matching) — preserves current QE-published semantics. To opt into Harmenberg, set explicitly.

### Phase 3: config-aware drift thresholds (~30 min)

Update `_tm_a_drift.py` to apply different thresholds based on the config:

```python
def assess_and_report(drift, *, threshold=None, hard_fail=None, label="", agent=None):
    ...
    psdu = getattr(agent, 'perm_shocks_during_unemployment', False) if agent else None
    if psdu is True:
        # Harmenberg config — analytical is exact
        var_log_p_threshold = threshold   # tight (default 0.03)
    elif psdu is False:
        # QE-matching config — analytical is approximate; loosen
        var_log_p_threshold = max(threshold * 4, 0.12)   # at least 12%, or 4x base
    ...
```

The 4× factor + 0.12 floor is chosen so that:
- D's currently-observed -16% drift would be within tolerance (flagged but not HARD-FAIL)
- A real bug that doubles or halves variance would still trip the threshold

### Phase 4: documentation in the drift report (~30 min)

When the drift test runs and flag = False, prepend the report with a note:

```
[drift agent_0] NOTE: perm_shocks_during_unemployment=False (QE-matching config).
                 The analytical pLvl distribution is an approximation; some
                 var log(p) drift up to ~15% is expected and not a bug.
                 var log(p) threshold loosened from 3% to 12% for this config.
```

### Phase 5: optional — exact non-lognormal pLvl analytical (~LATER, deferred)

The `(1-u)` approximation in `compute_pLvl_distribution` is a first-order approximation. A more accurate analytical formula could be derived by:
- Tracking the joint (age × Markov state × pLvl) distribution
- The pLvl distribution conditional on (age k, employed for k_emp of those periods) is lognormal
- Marginalize over the binomial distribution of k_emp given k

This would make the analytical exact under Config B too, eliminating the need for looser thresholds. But it's a significant derivation + implementation; deferred unless the looser-threshold approach proves insufficient.

## What "doing the right thing" looks like

After this plan:

- **Anyone running an MC drift test** automatically gets the right config behavior. No flag-vs-data contradictions.
- **Reproducing QE numbers** uses Config B (default). Drift tests still run but with appropriate looser thresholds.
- **Doing Harmenberg-style analysis** opts into Config A explicitly via env var. Drift tests use tight thresholds because the analytical is exact.
- **A new contributor** sees the env var documentation and knows the two configurations exist + when to use each.

## Implementation choices for the existing bug

When Phase 1 lands, the existing config (flag=True but data=False) will fail the consistency check. Two ways to resolve:

**Option A (recommended):** Set flag=False in EstimParameters.py to match the actual QE-matching data. Update the comment to say "QE-matching default; set HAFISCAL_PERM_DURING_UNEMP=on for Harmenberg-style runs". This is the right fix because:
- The actual published QE multipliers were generated with flag-effectively-False semantics
- Setting flag=True without rebuilding IncShkDstn was the original mistake
- QE-matching is the typical use case

**Option B (alternative):** Set flag=True AND rebuild IncShkDstn via build_unemployed_inc_shk_dstn(...,perm_shocks_during_unemployment=True). This switches the model to Config A semantics. **WARNING:** doing this would change the simulated multipliers — this is NOT a no-op fix.

Recommend Option A. Anyone running a Config-A analysis (Harmenberg neutral measure, etc.) needs to opt in explicitly.

## Test plan

1. After Phase 1: existing run should fail consistency check. Confirms detection works.
2. After Phase 2 + Option A applied: run companion-mode MC again. Expect:
   - Flag/data consistent (passes Phase 1 check)
   - Analytical formula uses (1-u) scaling
   - D var log(p) drift much smaller (~5-7% instead of 16%)
   - With Phase 3 looser threshold (12%), drift passes
3. With `HAFISCAL_PERM_DURING_UNEMP=on`: confirm IncShkDstn gets rebuilt; analytical formula switches mode; drift remains tight.

## What this plan does NOT do

- Does not modify multiplier results. Both configs run with their existing IncShkDstn data; we just enforce the flag matches.
- Does not require re-anchoring the cal. β/∇/GICx are unchanged.
- Does not remove the `compute_pLvl_distribution` function. It's still used; just the threshold against its output gets config-aware.

## Open questions for user

1. **Confirm Option A** (set flag=False to match QE-matching data) is the right resolution for the existing contradiction?
2. **Drift threshold for Config B (QE-matching)** — is 12% / 4× factor reasonable? Or do you want a different value?
3. **Default config** — Option A keeps QE-matching as default. Confirm?
4. **Should Phase 5 (exact non-lognormal formula) be in scope now or deferred?** I recommend deferring — the looser threshold should suffice for practical drift detection.
