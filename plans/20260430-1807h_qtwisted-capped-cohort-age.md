# Implementation plan: Restore QE-era T_age cap with rigorous Q-twisted Harmenberg machinery (BUG-038)

**Author:** Claude Opus (max effort)
**Date:** 2026-04-30
**Status:** awaiting user approval before execution
**Source-of-truth math doc:** `history/20260331-mathematical-derivations-harmenberg.md` §25
**Predecessor work:** §24 cohort-age decomposition (commit `f38d8567`); commit `dc6390e3` (the bug being addressed: removed `T_age` cap without replacement); BUG-037 misdiagnosis arc (commits `6a9db744`, `3c5b88cd`, `c4b663a5`) — to be mostly reverted here.
**Branch:** new branch `bug038-restore-T_age-cap` off `bug034-035-cdc-consistency-cleanup`.

---

## 0. Self-contained problem statement

The QE-era HAFiscal code was internally consistent: perpetual youth dynamics + `T_age = 200` cap (50 years) + `PermGroFacAgg = 1` + per-group `pLogInitMean_g` + MC-only simulation. The cap acted as a numerical guard rail that converted the heavy-tailed perpetual-youth cross-section's divergent moment integrals into finite truncated sums.

Commit `dc6390e3` (April 2026) removed the cap on grounds that it was undocumented and inconsistent with `EstimParameters.py`'s `T_age = None` default. **This was the actual bug.** Removing the cap exposed the heavy-tailed cross-section: $\mathbb{E}_P[p^k]$ becomes infinite for $k \geq 2$ at HAFiscal's calibration. The Doob $v_2$ machinery introduced with the HARK 0.17.0 TM-a_Q kernel then became ill-conditioned at high $\beta$.

The chase that followed (BUG-037) misdiagnosed the situation: it identified per-group `pLogInitMean_g` and `PermGroFacAgg = 1` as the underlying defects and proposed three coordinated changes (a)+(b)+(c). Per the user's review:
- Change (a): not a bug — group-specific newborn incomes are intentional SCF earnings calibration.
- Change (b): not strictly a bug — a model-spec choice; the QE setup was internally consistent.
- Change (c): genuine code cleanup but numerically inert when `PermGroFacAgg = 1`.

**This plan restores the QE-era model setup** (Changes (a) and (b) reverted; Change (c) kept for code cleanliness) **and adds the rigorous Q-twisted Harmenberg machinery** for the cap, derived in math doc §25. The result: a model that matches the QE paper's setup numerically while supporting the post-upgrade TM-a_Q machinery on a rigorous footing.

---

## 0.1 What's salvaged from the BUG-037 workflow

These outputs of the BUG-037 chase are kept (they are independently valuable):

| Salvaged | Why it's valuable |
|---|---|
| Cohort-age decomposition framework (`compute_cohort_age_decomposition_a` + tests) | Required infrastructure for this plan; works equally well in capped and uncapped models |
| BUG-036 discovery (Step-2 multistart Nelder-Mead) | Real bug; produced 15× wealth-fit improvement; stands on its own |
| BUG-037 §1.7 agent-side GIC derivation | Correct math; useful reference even though the bug it claimed didn't exist |
| Math doc §25 (Q-twisted construction under cap) | Just derived; foundation of this plan |
| Conclusions log `2026-04-30_step2-wealthfit-15x-improvement-is-multistart-not-gic.md` | Already correctly attributes the wealth-fit gain to BUG-036, not BUG-037 |
| Heavy-tail / Pareto / mortality understanding | Now properly documented; useful for future work |

Things that get reverted:
- Change (a): per-group `pLogInitMean_g` restored in init dicts.
- Change (b): `PermGroFacAgg = 1.0` restored.
- Change (c): kept (corrected formula); numerically inert when `PermGroFacAgg = 1` so no behavioral effect.

---

## 1. Phase structure overview

| Phase | Subject | Predecessors | Output |
|---|---|---|---|
| 0 | Pre-flight: create branch `bug038-restore-T_age-cap`; verify clean working tree | — | New branch ready |
| 0.5 | **REVERT BUG-037 Changes (a) and (b)**: restore per-group `pLogInitMean_g`; restore `PermGroFacAgg = 1.0`. Keep Change (c). | Phase 0 | Code state matches QE-era model spec (modulo `T_age` cap which arrives in Phase 6) |
| 1 | Code: extend `compute_cohort_age_decomposition_a` with `measure='Q'` and `T_age` truncation | math doc §25.4–25.6 | New optional kwargs + Q-mode output dict keys |
| 2 | Code: new `init_mc_from_cohort_age_decomposition_qtwisted` | Phase 1 | Q-measure MC initialization helper |
| 3 | Code: new `compute_pi_q_via_cohort_age` analytical aggregator | Phase 1 | $\pi_Q(s)$ as a single array, no $v_2$ dependence |
| 4 | Tests: structural unit tests for size-bias + truncation | Phases 1–3 | New `test_qtwisted_cohort_capped.py` |
| 5 | Tests: cross-check identities (mass-balance, Harmenberg aggregation, $T \to \infty$ recovery) | Phase 4 | Identity tests integrated into existing test suite |
| 6 | Restore `T_age = 200` in `Parameters.py` and `EstimParameters.py` (literal QE value) | Phases 0.5 + 5 (cascade-gate) | Cap active; production model = QE setup + new Q-twisted machinery |
| 7 | Replace $v_2$-based call sites with new `compute_pi_q_via_cohort_age` | Phase 6 | Production code uses new construction |
| 8 | Validation: drift test under cap; sign-off | Phases 6–7 | Empirical confirmation: drift should match pre-BUG-037 numbers tightly (CO cohort drift ~0.9%, HS ~5%, etc.) |
| 9 | Documentation: file `BUG-038`; mark BUG-037 superseded; conclusions log entry | Phase 8 | Narrative continuity; clean record |

Phases 0.5, 1–5 are pure additions or local reverts (they don't change running production behavior beyond cancelling the BUG-037 changes). Phase 6 is the production calibration restoration. Phases 7–9 propagate the fix.

**Cascade gate after Phase 5**: do not proceed to Phase 6 unless all unit + identity tests pass. Per `feedback_cascade_gating.md`: tier the validation, escalate only on clean pass.

---

## 2. Phase 0 — Pre-flight

```bash
# From parent branch
git checkout bug034-035-cdc-consistency-cleanup
git status   # confirm clean
git checkout -b bug038-restore-T_age-cap
```

**Smoke check:** verify current state on parent (post-merge of BUG-037):
- `EstimParameters.py:280`: `PermShkStd = [np.sqrt(0.003)]` (Carroll 2020 sticky, expected)
- `EstimParameters.py:92` area: `PermGroFacAgg = G_pop_avg ≈ 1.00455` (BUG-037 Change (b), to be reverted)
- `EstimParameters.py` init dicts: `pLogInitMean = pLogInitMean_avg` (BUG-037 Change (a), to be reverted)
- `Parameters.py:278`: `T_age = None` (the underlying bug, to be fixed in Phase 6)
- `EstimParameters.py:323-326`: corrected GIC formula (BUG-037 Change (c), to be KEPT)

---

## 3. Phase 0.5 — Revert BUG-037 Changes (a) and (b)

**Single atomic commit. Title: "BUG-038 prep: revert BUG-037 Changes (a) and (b); keep (c) — restore QE-era model spec"**

### 3.1 Files to edit

**`Code/HA-Models/FromPandemicCode/EstimParameters.py`:**

1. **Revert Change (b)**: locate the line where `PermGroFacAgg` is set to `G_pop_avg`; change back to `PermGroFacAgg = 1.0` with a comment explaining this is the QE-era setup. Remove the `G_pop_avg` calculation.

2. **Revert Change (a)**: locate the three init dicts (`init_dropout`, `init_highschool`, `init_college`) and change `'pLogInitMean': pLogInitMean_avg` back to `'pLogInitMean': pLogInitMean_d` (resp. `_h`, `_c`). Remove the `pLogInitMean_avg` calculation.

3. **Keep Change (c)**: the corrected `GICmaxBetas` formula (without the `* PermGroFacAgg` multiplier) stays. Numerically inert when `PermGroFacAgg = 1` so no behavioral effect; mathematically correct per math doc §1.7. Add a comment cross-referencing math doc §25 noting that this formula is correct under both `PermGroFacAgg = 1` (current) and any future `PermGroFacAgg ≠ 1`.

**`Code/HA-Models/FromPandemicCode/Parameters.py`:**

1. **Revert Change (a) mirror**: in the import list and three init dicts, restore per-group `pLogInitMean` references.

### 3.2 Commit message draft

```
BUG-038 prep: revert BUG-037 Changes (a) and (b); keep (c)

Restores the QE-era model setup ahead of BUG-038's T_age cap restoration.
BUG-037 was a misdiagnosis (see plans/20260430-1807h_qtwisted-capped-
cohort-age.md §0); the QE-era setup was internally consistent.

- Change (a) reverted: pLogInitMean restored to per-group values
  (pLogInitMean_d, pLogInitMean_h, pLogInitMean_c). These are SCF 2004
  earnings calibration targets, not a defect.
- Change (b) reverted: PermGroFacAgg = 1.0 restored (no aggregate
  productivity growth; matches QE paper).
- Change (c) KEPT: corrected GICmaxBetas formula (without spurious
  PermGroFacAgg multiplier) retained for code cleanliness. Numerically
  inert when PermGroFacAgg = 1 (factor of 1^ρ = 1), mathematically
  correct per math doc §1.7 derivation.

T_age cap restoration follows in a separate commit.
```

### 3.3 Smoke validation

After Phase 0.5 commit:
- Run `Parameters.py` standalone (just the import + parameter setup) and confirm:
  - `PermGroFacAgg = 1.0`
  - Three groups have distinct `pLogInitMean` values matching the SCF calibration ($\log 6.2$, $\log 11.1$, $\log 14.5$)
  - `GICmaxBetas` evaluates to the same numerical values as before this commit (because `PermGroFacAgg^ρ = 1^ρ = 1`)

If smoke check fails, halt. Otherwise proceed to Phase 1.

---

## 4. Phase 1 — Extend `compute_cohort_age_decomposition_a`

**File:** `Code/HA-Models/FromPandemicCode/tm_methods.py`

### 4.1 Updated signature

```python
def compute_cohort_age_decomposition_a(
        agent, tm_data, K_max=2000,
        Cratio=1.0, ad_tran_shk_scale=1.0, employed_tran_shk_scale=1.0,
        TranShk_addition=None, interpretation='CDC',
        unemp_shocks='employed',
        measure='P',           # NEW: 'P' (default, current behavior) or 'Q'
        T_age=None,            # NEW: hard cap on cohort sum; if not None, K_max is overridden by T_age - 1
        verify_against_doob=True, doob_tol=None):
```

### 4.2 New behaviors

**`T_age` parameter:**
- If `T_age is not None`: assert `T_age >= 1`; set `K_max = T_age - 1`. Warn if user-passed `K_max != T_age - 1`.
- The cohort sum runs $\tau = 0, \ldots, T - 1$ inclusive, matching $(eq:cap\text{-}piQ\text{-}aggregate)$.

**`measure='Q'` mode:**
1. **Newborn injection** size-biased per $(eq:cap\text{-}tilde\text{-}newborn)$:
   - $\tilde g_k^{(0)}(x) = \mathbb{E}[p_{\text{init}}^{k+1}] / \mathbb{E}[p_{\text{init}}] \cdot \pi_N(x)$
   - $\tilde\pi^{(0)}(x) = \pi_N(x)$ (unchanged because $s_0 \perp p_{\text{init}}$ in HAFiscal — and per-group `pLogInitMean_g` per Phase 0.5 revert means each group has its own $\nu_{p_0,g}$, so the size-biased moments are computed per-group).
2. **Survivor kernel** size-biased $\psi$ per $(eq:cap\text{-}tilde\text{-}TS)$:
   - $\tilde T_S(s \to s')$ replaces $T_S(s \to s')$.
   - $\tilde T_{S, p^k}(s \to s')$ similarly: re-weight $\psi$ atoms by $\psi^{k+1}$ in place of $\psi^k$.
3. **Per-cohort survival rate**: in constant-$L$ HAFiscal with `PermGroFacAgg = 1` (post Phase 0.5), the per-period growth is $G = G_g$ and $L_Q = L \cdot G_g$ — group-specific. Use the closed-form group-specific value.
4. **Cohort weights** group-specific: $Q_g(\tau) = (L G_g)^\tau (1 - L G_g) / (1 - (L G_g)^T)$ from $(eq:cap\text{-}Qtau)$.

### 4.3 New output dict keys (when `measure='Q'`)

| Key | Description |
|---|---|
| `pi_Q_k` | $\pi_Q^{(\tau)}(x)$ per cohort, shape `(K_max+1, A·J)` |
| `g1_Q_k` | $\tilde g_1^{(\tau)}(x) = \mathbb{E}_Q[p \cdot \mathbb{1}\{X=x\} \mid K=\tau]$ |
| `g2_Q_k` | $\tilde g_2^{(\tau)}(x)$ |
| `Q_wt` | $Q(\tau)$ from $(eq:cap\text{-}Qtau)$ |
| `pi_Q_aggregated` | $\pi_Q(x) = \sum_\tau Q(\tau) \pi_Q^{(\tau)}(x)$ |
| `f1_Q_aggregated` | $\sum_\tau Q(\tau) g_1^{(\tau)}(x)$ |
| `f2_Q_aggregated` | $\sum_\tau Q(\tau) g_2^{(\tau)}(x)$ |
| `T_age_used` | The actual $T_{\text{age}}$ (if provided) or $K_{\max} + 1$ |
| `LG_used` | $L \cdot G$ used (for verification; group-specific in HAFiscal) |
| `measure` | `'P'` or `'Q'` |

### 4.4 New helper: `build_size_biased_TS`

Builds the size-biased survivor kernel per $(eq:cap\text{-}tilde\text{-}TS)$:
- For the $\psi$-shock loop, replace `prob_psi[s]` with `prob_psi[s] * psi_atom[s]^(k+1)` (so $k=0$ for $\tilde T_S$ gives a multiplier of $\psi$; $k=1$ for $\tilde T_{S, p}$ gives $\psi^2$; etc.)
- Per-cohort denominator: derive carefully — this is a real implementation subtlety.

**Action item before implementation:** add a numbered equation to math doc §25.6 deriving the precise per-cohort normalization for the $\tilde g_k$ recursion. (Skipped in the math doc draft; needs to be added here.)

### 4.5 Time/cost estimate

For HAFiscal Baseline ($A \cdot J = 800$, $T_{\text{age}} = 200$): $3 \times 200 = 600$ sparse matvecs per cohort decomposition call ≈ 0.2 sec. Three groups × 0.2 sec = 0.6 sec total. Negligible.

---

## 5. Phase 2 — `init_mc_from_cohort_age_decomposition_qtwisted`

**File:** `Code/HA-Models/FromPandemicCode/tm_methods.py`

```python
def init_mc_from_cohort_age_decomposition_qtwisted(
        agent, cohort_dec, dist_aGrid, N, seed,
        use_detrended=True):
    """
    Initialize MC from the Q-twisted cohort-age decomposition.

    Sample N agents from π_Q over (s, p, τ):
      1. Sample τ ~ Q (categorical over {0, ..., T_age - 1})
      2. Sample (s, p) from π_Q^{(τ)} per math doc §25.6
      3. Set agent.t_age = τ, agent.state_now['aNrm'], etc.
    """
    assert cohort_dec.get('measure') == 'Q', \
        "cohort_dec must come from compute_cohort_age_decomposition_a(measure='Q')"
    # ... implementation
```

Sampling steps per agent:
1. **Sample $\tau_i \sim Q$** with weights `Q_wt[0:T_age]`.
2. **Sample $x_i = (a_i, j_i) \sim \pi_Q^{(\tau_i)}$**.
3. **Sample $p_i$ given $(x_i, \tau_i)$** from the size-biased newborn moments + cohort propagation.
4. **Set agent state:** `t_age = τ_i`, `aNrm = a_i`, `MrkvNowPcvd = j_i`, `pLvl = p_i`.

`t_age = τ_i` ensures the cap will be enforced going forward (agent will be force-killed when `t_age = T_age`).

---

## 6. Phase 3 — `compute_pi_q_via_cohort_age` analytical aggregator

**File:** `Code/HA-Models/FromPandemicCode/tm_methods.py`

```python
def compute_pi_q_via_cohort_age(agent, tm_data, T_age, **kwargs):
    """
    Compute π_Q(s) analytically via cohort-age decomposition under the cap.
    Replaces v_2-based compute_doob_pi_q_a in the heavy-tail regime
    (which is now guarded by the T_age cap, but using the cohort
    construction is preferred regardless for theoretical cleanness).
    """
    cohort_dec = compute_cohort_age_decomposition_a(
        agent, tm_data, T_age=T_age, measure='Q',
        verify_against_doob=False, **kwargs)
    return cohort_dec['pi_Q_aggregated'], cohort_dec
```

**Caller-side migration (Phase 7):**
- `harmenberg_cohort_drift_test.py:104`: replace `compute_doob_pi_q_a(...)` with `compute_pi_q_via_cohort_age(agent, tm_data, T_age=200, ...)`.
- Audit other call sites of `compute_doob_pi_q_a` and `compute_doob_v2_a`; replace selectively.

---

## 7. Phase 4 — Structural unit tests

**File:** `Code/HA-Models/FromPandemicCode/test_qtwisted_cohort_capped.py` (new)

| Test | What it checks |
|---|---|
| `test_size_bias_psi_normalization` | $\sum_s \nu_\psi(\psi_s) \cdot \psi_s = 1$ (size-biased $\psi$-distribution sums to 1 since $\mathbb{E}[\psi]=1$) |
| `test_Q_wt_sums_to_one` | $\sum_{\tau=0}^{T-1} Q_g(\tau) = 1$ for each group $g$ and $T = 200$ |
| `test_Q_wt_geometric_form` | $Q_g(\tau)/Q_g(\tau+1) = 1/(L G_g)$ for $\tau \in \{0, ..., T-2\}$ |
| `test_pi_Q_k_sums_to_one_per_cohort` | $\sum_x \pi_Q^{(\tau)}(x) = 1$ for each $\tau$ |
| `test_pi_Q_aggregated_sums_to_one` | $\sum_x \pi_Q(x) = 1$ |
| `test_T_to_infinity_recovers_perpetual_youth` | As $T \to \infty$ (large $K_{\max}$), $\pi_Q$ approaches the perpetual-youth value within $L^T$ tolerance |
| `test_size_bias_Ep_init_correct` | $\tilde\nu_{p_0}$ has mean $\mathbb{E}[p_{\text{init}}^2] / \mathbb{E}[p_{\text{init}}]$ per group |
| `test_expected_lifetime_under_cap` | $\mathbb{E}[\text{lifetime}] = L(1-L^T)/(1-L) \approx 113$ quarters $\approx 28.4$ years for $T=200$, $L=0.99375$ — matches MC empirical mean |

---

## 8. Phase 5 — Cross-check identity tests

| Identity | Check |
|---|---|
| **Harmenberg aggregation** $(eq:cap\text{-}Harmenberg\text{-}identity)$ | For consumption policy $c(s)$: $\sum_x c(x) \pi_Q(x) \cdot \mathbb{E}_P[p] = \sum_x g_1^P(x) \cdot c(x)$. Tolerance $10^{-10}$. |
| **Cap consistency $\mathbb{E}_P[p]$ formula** $(eq:cap\text{-}EP\text{-}p)$ | Closed-form $\mathbb{E}[p_{\text{init}}] (1-L)(1 - (LG)^T) / [(1-L^T)(1-LG)]$ should equal $\sum_x g_1^P(x)$ from the P-measure cohort decomposition. |
| **Q-survival rate** | $Q(\tau+1)/Q(\tau) = LG$ matches the iterated $\tilde L^{(\tau)}$ from code. |
| **Newborn rate identity** $(eq:cap\text{-}newborn\text{-}consistency)$ | $\rho_P(0) \cdot \mathbb{E}[p_{\text{init}}] / \mathbb{E}_P[p] = (1-LG)/(1-(LG)^T)$ — both sides numerical. |

**Tier-gate criterion:**
- Tier 1: structural tests (Phase 4) pass at $10^{-12}$.
- Tier 2: identity tests (this phase) pass at $10^{-10}$.
- Tier 3: empirical drift test (Phase 8) shows reduced cohort drift under cap+Q vs uncapped P, matching pre-BUG-037 numbers.

If any tier fails: HALT before proceeding.

---

## 9. Phase 6 — Restore `T_age = 200` (literal QE)

**Files:**
- `Code/HA-Models/FromPandemicCode/Parameters.py` line 278: `T_age = None` → `T_age = 200`
- `Code/HA-Models/FromPandemicCode/EstimParameters.py` line 362: `'T_age': None` → `'T_age': 200` (same value as Edmund's original 2022-01 commit `770d4d04`)

Both files: update comments to:
```python
T_age = 200             # 50 years; QE-era value (Crawley 2022, commit 770d4d04).
                        # Restored 2026-04-30 to fix BUG-038 (heavy-tail
                        # cross-section exposed by commit dc6390e3 removing
                        # the cap). See math doc §25 for the rigorous
                        # Q-twisted construction under the cap.
                        # NOTE: T=200 with L=1-1/160 yields E[lifetime] ≈ 28
                        # years (vs 40 years uncapped); this is a known
                        # mismatch inherited from the QE setup. Choosing a
                        # different T to better match the L calibration is a
                        # separate workflow, not part of BUG-038.
```

**Justification (in commit message):** Restores the QE-era cap value `T_age = 200` (50 years, matching Crawley's January 2022 commit `770d4d04`) to fix the heavy-tail cross-section issue introduced by `dc6390e3`. The cap value follows the "minimum disruption" principle — choosing a different $T$ to better match the $L = 1 - 1/160$ calibration's implied 40-year expected lifetime is left as a separate (potential future) workflow. With Changes (a) and (b) reverted in Phase 0.5 and Change (c) kept (numerically inert), this commit completes the restoration of the QE-era model setup, now augmented by the rigorous Q-twisted Harmenberg construction of math doc §25 for the new HARK 0.17.0 TM-a_Q machinery.

**Cascade gate before Phase 6:** Phases 4–5 must all pass.

**Reduced_Run parametrization:** restore `T_age = 200` for consistency? Or keep `None` for fast-test? **Decision:** restore for consistency with QE setup (Edmund's original commit had `T_age = 100` for `Reduced_Run`; revert to that exact value).

---

## 10. Phase 7 — Replace v_2-based call sites

Audit and migrate:
```bash
grep -rn "compute_doob_v2_a\|compute_doob_pi_q_a" Code/HA-Models/FromPandemicCode/
```

For each call site:
- **MC initialization of Q-measure agents** → `init_mc_from_cohort_age_decomposition_qtwisted`.
- **Computing $\pi_Q(s)$ for analytical aggregation** → `compute_pi_q_via_cohort_age`.
- **Direct $v_2$ usage** → audit case-by-case; cohort-age machinery can supply via `f2_Q_aggregated`.

**Caveat:** the existing $v_2$ machinery may have call sites I'm not aware of. Replacements should be additive (deprecate + warn) until all call sites are confirmed migrated.

---

## 11. Phase 8 — Validation

### 11.1 Drift test

Re-run `harmenberg_cohort_drift_test.py` with `T_age = 200` active and the new Q-twisted helper.

**Expected results** (these tightly bracket the right answer):

| Config | Pre-BUG-037 (T=200, QE setup) | Post-BUG-037 (T=None, no cap) | Target post-BUG-038 (T=200, Q-twisted) |
|---|---|---|---|
| HS β=0.91 CDC | doob 3.62%, cohort 5.27% | doob 2.17%, cohort 5.58% | should match pre-BUG-037 within MC noise (~few pp) |
| HS β=0.91 ESC | doob 4.98%, cohort 4.73% | doob 3.17%, cohort 5.13% | should match pre-BUG-037 within MC noise |
| **CO β=0.988 CDC** | doob 19.32%, **cohort 0.92%** | doob 48.09%, cohort 13.81% | **cohort should drop back to <2%** |
| **CO β=0.988 ESC** | doob 12.31%, **cohort 2.86%** | doob 37.34%, cohort 10.24% | **cohort should drop back to <5%** |

**The College drift dropping from ~14% (post-BUG-037) back to ~1-3% (target) is the smoking-gun confirmation that BUG-038's restoration is correct.**

### 11.2 Sign-off criteria

- All Phase 4 + 5 tests pass.
- CO cohort drift under cap + Q-twisted < 5% (vs 14% under post-BUG-037 spec).
- HS cohort drift unchanged within MC noise.

If any criterion fails: investigate root cause; do not proceed to Phase 9.

### 11.3 Step 5 smoke run — IN SCOPE (single trial, not re-estimation)

Per user authorization 2026-04-30: include a Step 5 **smoke run** in Phase 8 sign-off — a single-trial computation of multipliers (not the full multistart re-estimation) just to confirm aggregates are sensible. This catches gross errors that the drift test alone might miss (e.g., the new Q-twisted machinery silently producing wrong consumption aggregates that happen to keep $\mathbb{E}_Q[a]$ stable).

**What "smoke run" means concretely:**
- Run `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py` (or equivalent Step-5 entry point) with `HAFISCAL_NUM_STARTS=1` and the production calibration (β, ∇) already saved.
- One pass through the policy experiments (UI extension, tax cut, stimulus check), with the new T_age=200 + Q-twisted dynamics.
- Compare resulting multipliers to the post-BUG-037 saved Step 5 outputs in `conclusions_private/2026-04-29_doob-vs-bst-vs-mc-step5-multipliers-three-way.md` and any other Step 5 result file.

**Pass criterion for smoke run:**
- Multipliers within 5pp of post-BUG-037 baseline. Larger deviations require investigation before sign-off.
- No NaN, infinity, or other numerical pathology in the aggregates.

**Wall-clock cost:** ~1.5 hours for a single Step-5 trial (vs ~9 hours for full multistart re-estimation, which remains out of scope per `feedback_no_default_reestimation.md`).

**What is NOT in scope:** full multistart Step 5 re-estimation, Step 1 (splurge) re-estimation, Step 2 (β, ∇) re-estimation. The wealth-fit objective is in $a_{\text{Nrm}}$ units, invariant to PermGroFacAgg and pLogInitMean changes (per math doc §25.5 footnote and `test_bug037_wealth_fit.py`). The saved (β, ∇) values stay; only the smoke run validates that downstream aggregates respond sensibly to the dynamics changes.

---

## 12. Phase 9 — Documentation

### 12.1 New BUG report: `BUGS_private/HAFiscal_BUG-038_T_age_cap_removal.md`

Structure:
- **Date filed:** 2026-04-30
- **Severity:** Methodological. Removal of the QE-era `T_age` cap exposed heavy-tailed cross-section that the QE setup had been masking.
- **Affected files:** `Parameters.py`, `EstimParameters.py`, `tm_methods.py` (TM-a_Q kernel call sites)
- **Status:** open — fix in this plan.
- §1 Description: `dc6390e3` removed the cap; the perpetual-youth model has heavy tails ($L G^2 \mathbb{E}[\psi^2] > 1$) per math doc §25 / §14; symptoms include Doob $v_2$ ill-conditioning and ~14× MC drift in College cohort.
- §2 Proposed fix: restore `T_age = 200` cap + add Q-twisted Harmenberg machinery for the cap (math doc §25).
- §3 Resolution plan: this plan.
- §4 Connection to BUG-037: BUG-037 was a misdiagnosis of the same underlying issue; salvaged outputs listed.

### 12.2 Mark BUG-037 superseded

Edit `BUGS_private/HAFiscal_BUG-037_pLvl_init_not_economy_average.md` frontmatter:
```yaml
status: superseded — see BUG-038
superseded_by: BUG-038
```

Add a header at the top:
```
> **MISDIAGNOSIS — SUPERSEDED 2026-04-30 by BUG-038.** This bug report
> identified per-group `pLogInitMean_g` and `PermGroFacAgg = 1` as defects.
> Per user review (2026-04-30), neither was a defect: per-group newborn
> incomes are intentional SCF earnings calibration, and `PermGroFacAgg = 1`
> is an internally consistent model spec (the QE paper's setup).
> The actual underlying issue was the removal of the `T_age` cap in
> commit `dc6390e3`, which exposed the heavy-tailed cross-section that
> the QE-era cap had been masking. See `BUGS_private/HAFiscal_BUG-038_T_age_cap_removal.md`
> for the actual diagnosis and fix.
>
> Salvaged from this workflow: cohort-age decomposition framework (§24
> of math doc), §1.7 GIC derivation, BUG-036 multistart discovery,
> heavy-tail/Pareto understanding (math doc §14, §21), and math doc §25
> Q-twisted construction under cap. None of these depend on the
> misdiagnosis being correct.
```

Do **NOT** delete or rewrite the body of the BUG-037 doc; preserve it as the historical record of the misdiagnosis.

### 12.3 Conclusions log

`conclusions_private/2026-04-30_bug038-restore-T_age-cap.md` (new):
```yaml
---
date: 2026-04-30
status: active
supersedes: []
superseded_by: []
keywords: [BUG-037, BUG-038, T_age, cap, heavy-tail, Q-twisted, Harmenberg, cohort-age]
related_bugs: [BUG-036, BUG-037, BUG-038]
related_phases: [QE-restoration, math-doc-§25]
---

# BUG-038 fix: restore QE-era T_age=200 cap + add rigorous Q-twisted machinery

## Claim
The post-`dc6390e3` perpetual-youth model exposed heavy-tailed cross-section
issues (Doob $v_2$ ill-conditioning at high β, MC drift at College cohort).
Restoring the QE-era `T_age = 200` cap fixes the underlying issue. The
BUG-037 chase was a misdiagnosis; restoring the QE setup (Changes (a) and
(b) reverted; Change (c) kept as numerically inert code cleanup) resolves
all symptoms.

## Evidence
- College cohort drift (Q_E[a]): from 14% (post-BUG-037, no cap) back to <2% (BUG-038, cap restored). Empirical verification in Phase 8 of plan.
- All Phase 4 + 5 unit and identity tests pass.
- Math doc §25 derives the rigorous Q-twisted Harmenberg construction under the cap (cohort weights $Q(\tau) \propto (LG)^\tau$ truncated at $T-1$, with size-biased shocks). The construction does NOT require any second-moment finiteness on $p$.
- BUG-037 misdiagnosis pointers preserved in `BUGS_private/HAFiscal_BUG-037_*.md` with the new "MISDIAGNOSIS" header.

## Mechanism
The QE paper used `T_age = 200` (50 years) + `PermGroFacAgg = 1` + per-group `pLogInitMean_g` + MC-only. The cap converted divergent moment integrals to finite truncated sums; with MC-only, the cap's role was a numerical guard rail, no Q-measure machinery to break.

`dc6390e3` removed the cap unilaterally. The HARK 0.17.0 TM-a_Q machinery (introduced post-upgrade) needs Q-measure constructions; without the cap, the constructions encounter the heavy-tailed $v_2$ at high β.

The fix (math doc §25): restore the cap; reframe the Q-measure construction as size-biased Harmenberg dynamics with cohort weights $Q(\tau)$. Works in both perpetual-youth and capped settings; does not require the eigenfunction-based Doob h-transform that breaks at the cap boundary.

## Implications
1. Step 2 wealth-fit calibration is unchanged (the $a_{\text{Nrm}}$ objective is invariant to all of these changes).
2. Step 5 multipliers are expected unchanged within MC noise (saved (β, ∇) is the same; same dynamics modulo the cap, which only removes the heavy-tail $L^{200} \approx 28\%$ of agents from the asymptotic limit — but at $T < 200$ they would have been alive anyway, so the per-period dynamics are identical for the vast majority of the simulation horizon).
3. The TM-a_Q machinery now has a rigorous theoretical underpinning (math doc §25) in the capped model.
4. The expected-lifetime mismatch (T=200 → E[lifetime] ≈ 28 years, vs L's implied 40 years) is inherited from QE; addressing it by choosing a different T or recalibrating L is a future workflow.

## See also
- `BUGS_private/HAFiscal_BUG-038_T_age_cap_removal.md` (this bug)
- `BUGS_private/HAFiscal_BUG-037_pLvl_init_not_economy_average.md` (the misdiagnosis)
- `conclusions_private/2026-04-30_step2-wealthfit-15x-improvement-is-multistart-not-gic.md` (already correctly attributed to BUG-036)
- `history/20260331-mathematical-derivations-harmenberg.md` §25 (the source-of-truth derivation)
- Plan: `plans/20260430-1807h_qtwisted-capped-cohort-age.md` (this plan)
```

### 12.4 Code header note

In `tm_methods.py`, near `compute_cohort_age_decomposition_a`, add:
> **Q-mode under cap:** when called with `measure='Q'` and `T_age` set, this implements math doc §25 — the standard Harmenberg neutral measure adapted to the $T_{\text{age}}$-capped model. See math doc §25 for the derivation; §25.7 for $T_{\text{age}}$ calibration discussion.

---

## 13. Authorization gates

Following `feedback_no_default_reestimation.md` and `feedback_cascade_gating.md`:

- **Phase 0.5 (revert BUG-037 Changes (a) and (b)):** requires explicit user authorization (it's a substantive production-state change). User has provided this in the conversation that produced this plan.
- **Phases 1–5 (code + tests, no production change):** proceed without further authorization once user approves the plan.
- **Phase 6 (T_age cap restoration):** requires explicit user authorization before merge to `bug034-035-cdc-consistency-cleanup`.
- **Phase 7 (replacing $v_2$-based call sites):** proceed under plan authorization but list each call-site swap in commit messages.
- **Phase 8 (drift test ~15 min + Step 5 smoke run ~1.5 hr):** proceed under user authorization 2026-04-30. Full Step 5 multistart re-estimation remains separately authorized only.
- **Phase 9 (documentation):** proceed as part of Phase 8 sign-off.
- **Merge to parent `bug034-035-cdc-consistency-cleanup`:** held for user review after Phase 8. Do NOT auto-merge.

**No re-estimation of (β, ∇) or splurge.** Per user feedback, treat existing calibration files as fixed. Step 1 (splurge) and Step 2 (β, ∇) do not need to be re-run; the wealth-fit objective is invariant to all reverts. The Step 5 smoke run is a single-trial validation, not a re-estimation.

---

## 14. Parallelism opportunities

Per `feedback_parallelism.md`:

- **Subagent parallelism:** Phases 4 (structural tests) and 5 (identity tests) can be developed by separate subagents in parallel after Phase 3.
- **Background-compute parallelism:** none required for the in-scope work (all phases are interactive). Step 5 re-run (out of scope) would be ~9 hours background if authorized.
- **Foreground:** Phases 0.5, 1–3 (sequential dependencies); 6, 7, 8 (sequential).

---

## 15. Estimated total effort

| Phase | Effort | Wall-clock |
|---|---|---|
| 0 | Trivial (git ops) | 5 min |
| 0.5 | Small (3 file edits + smoke check) | 30 min |
| 1 | Medium (~200 LOC + careful size-biased kernel derivation) | 2–3 hours |
| 2 | Small (~50 LOC) | 30 min |
| 3 | Trivial (~20 LOC wrapper) | 15 min |
| 4 | Medium (~10 unit tests, 200 LOC) | 1.5 hours |
| 5 | Medium (~5 identity tests, 150 LOC) | 1 hour |
| 6 | Trivial (2-line config change + comment) | 10 min |
| 7 | Small-medium (depends on call-site count) | 30 min – 2 hours |
| 8 | Drift test ~15 min interactive + Step 5 smoke run ~1.5 hr | ~2 hours |
| 9 | Small (3 short docs + 1 frontmatter edit) | 1 hour |
| **Total interactive** | | **~7–9 hours** |
| **Total wall-clock (incl. Step 5 smoke run)** | | **~9–11 hours** |

Branch held open for user review after Phase 8 sign-off; merge to parent is a separate user action.

Full Step 5 multistart re-estimation (out of scope, separately authorized): +9 hours background if requested.

---

## 16. Open questions — all resolved

All open questions resolved per user responses 2026-04-30:
- $T_{\text{age}} = 200$ (literal QE value).
- Change (c) kept (corrected GIC formula, numerically inert when `PermGroFacAgg = 1`).
- Bug doc structure: new `BUGS_private/HAFiscal_BUG-038_*.md`; mark BUG-037 superseded with frontmatter + header; preserve BUG-037 body.
- Branch: new `bug038-restore-T_age-cap` off parent.
- **Branch lifecycle: hold for review after Phase 8 sign-off** (do NOT auto-merge to parent). User reviews the diff + Phase 8 results before authorizing the merge.
- **Step 5 smoke run: in scope** (single trial, ~1.5 hours; per §11.3). Full multistart re-estimation remains out of scope.

No remaining blockers — plan is ready to execute on user authorization.

---

## 17. Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Size-biased kernel implementation has off-by-one in $\psi$-power | High (silent bug) | Phase 4 unit tests + Phase 5 identity tests |
| `T_age = 200` breaks unrelated downstream code that assumed `T_age = None` | Medium | Phase 6 staged on its own branch; Phase 8 drift test catches symptoms |
| Step 5 multipliers shift more than 1pp under cap restoration | Low | Math claim is they don't shift; would need explicit re-run to verify (out of scope) |
| Heavy-tail issue persists despite cap (math claim wrong) | Very low | Math doc §25.6 confirms truncated sum is finite for any finite $T$ — verified analytically |
| BUG-037 reverts break some test that was added as part of BUG-037 | Medium | Audit BUG-037 test files (`test_bug037_*.py`); update or skip as appropriate |
| Size-biased per-cohort normalization derivation is wrong | High | Add explicit derivation to math doc §25.6 before Phase 1 implementation; cross-check via Phase 5 identity tests |

---

## 18. Out of scope

- Re-deriving Step 1 (splurge) under cap — splurge invariance assumed.
- Recession/AD-loop interaction with cap — flagged in math doc §25.11 as extension; not implemented.
- State-dependent $L_j$ — math doc §25.11; HAFiscal uses constant $L$.
- Modifying or deleting `compute_doob_v2_a` directly (deprecate-and-warn only).
- Choosing a different $T_{\text{age}}$ value to better match $L$ calibration — separate workflow per user.
- Changing Change (c) decision (corrected formula stays — see §3 Phase 0.5).

---

## 19. References

- Math doc: `history/20260331-mathematical-derivations-harmenberg.md` §25
- Predecessor cohort-age plan: `plans/20260429-1641h_cohort-age-decomposition-mc-init.md`
- BUG-037 doc (to be marked superseded): `BUGS_private/HAFiscal_BUG-037_pLvl_init_not_economy_average.md`
- Conclusions log on multistart-driven wealth-fit: `conclusions_private/2026-04-30_step2-wealthfit-15x-improvement-is-multistart-not-gic.md`
- Commit `770d4d04` (Edmund Crawley's original "Kills off old agents" — `T_age=200`)
- Commit `dc6390e3` (the bug — `T_age` removal); to be effectively reverted by Phase 6
- Commit `ee841013` (Tier 3 drift test baseline) — to be re-run in Phase 8
