# Plan: a-indexed Transition Matrix for splurge-in-budget splurge correction

**Status:** Revised 2026-04-15 (in light of the bound-pair vs. within-household clarification)
**Context:** splurge-in-budget (the paper's eq (4) with budget-identity fix) has been implemented for MC in `AggFiscalType.get_poststates`. The TM path remains `m`-indexed and needs updating to match. This plan describes how and why.

Prior drafts omitted the interpretation discussion and framed the construction in a way that led to reasonable confusion about whether N separate transition matrices are needed (they are not). This revision clarifies both.

---

## 0. Why do this at all, and why this way?

### 0.1 Why we need the TM under splurge-in-budget (not just MC)

MC naturally handles splurge-in-budget because each agent's realized transitory shock $\xi_t$ is available at the moment of the `get_poststates` call, so the per-agent savings rule $a_t = m_t - (1-\varsigma)c^*(m_t) - \varsigma\xi_t$ is implemented directly. We already have this working (`AggFiscalType.get_poststates` override).

But MC is not a substitute for the TM for three reasons:

1. **Speed.** The 21-type CRRA2 Baseline on MC takes ~5 hours. The TM on the same problem runs in minutes. For the welfare and sensitivity re-runs this matters a lot.
2. **Cross-check.** TM and MC should agree to MC-sampling tolerance; systematic disagreement flags a bug. We lose that check if only MC is available under splurge-in-budget.
3. **Deterministic reference for targeted experiments.** AD iteration, per-bucket Check aggregation, and welfare integrals are all easier to reason about on a deterministic grid than on a noisy 10K-agent simulation.

### 0.2 Why splurge-in-budget is interpretation A (summary — full argument in the notebook)

The bound-pair reading of the codebase (`BUGS_private/.../bound-pair-interpretation.md`) argues that the code's `aNrm` is the *optimizer's* per-capita wealth in a $(1{-}\varsigma)$ optimizer + $\varsigma$ HtM pair, in which case the asset-update line $a = m - c^*(m)$ is fine at the optimizer level and splurge-in-budget would be "subtracting HtM consumption from the optimizer's assets."

That reading is internally consistent for the asset-update line in isolation, but it is not what the estimation code does at the calibration layer. `Estimation_BetaNablaSplurge.py:166` sets `KY_target = 6.60` (SCF *household* K/Y), and `:258–262` computes `CapAgg = np.sum(aLvl)` with no $(1{-}\varsigma)$ rescaling. Under the bound-pair reading this would miss the SCF target by $1/(1{-}\varsigma) \approx 33\%$; the fact that the estimation hits `KY_Model = 6.58 ≈ 6.60` demonstrates that `aNrm` is being treated as full household wealth — i.e., interpretation A. (The Lorenz and felicity tests are either scale-invariant or ambiguous and don't discriminate; K/Y is the decisive test.)

Since the code is implicitly A, the per-household asset-update line $a = m - c^*(m)$ violates eq (4), which says $a = m - c_\text{reported}$. The splurge-in-budget fix is the one-line change. The full argument with line references is in `BUGS_private/HAFiscal_splurge_budget_inconsistency/bound-pair-interpretation_response.ipynb`.

**Implication for the TM.** Under interpretation A, the per-household savings rule depends on the realized $\xi_t$, because $c_\text{reported} = (1{-}\varsigma)c^*(m_t) + \varsigma\xi_t$. So post-consumption savings $a_t$ cannot be read off from $m_t$ alone. This is what breaks the standard m-indexed TM and motivates the refactor below.

### 0.3 Why a-indexed rather than alternatives

> **Decision (2026-04-15):** a-indexed is the chosen approach; no staged $(m, \xi) \to$ a-indexed hybrid. For the careful per-criterion comparison (speed, code complexity, exposition), see `plans/20260418-1136h_splurge-in-budget-TM-approach-comparison.md` §5. Summary: $(m, \xi)$ would be slower than MC for HAFiscal Baseline (~10h vs. MC's 5h), which defeats the purpose of having a TM. Development correctness is anchored on MC as ground truth, using narrow asymptotic-style tests (see `plans/20260403-1253h_asymptotic-equality-test-plan.md` and `Code/HA-Models/Gatekeeper_Asymptotic_Equality.ipynb`) to keep iteration fast.


Four candidate strategies, in increasing order of refactor size:

| Strategy | Refactor | Correctness | Verdict |
|---|---|---|---|
| **m-indexed + $E[\xi]$ plug-in** | tiny | **wrong** (15–25% bias vs MC) | reject |
| **m-indexed + $\xi_t$-correction term** | small | approximate (error depends on $\text{Cov}(\xi_t, m_t)$) | reject for a published result |
| **joint $(m, \xi)$ state** | medium | exact | viable fallback |
| **a-indexed TM** | medium | exact | **chosen** |

Detail on each:

- **m-indexed + $E[\xi]$:** What the earlier flawed attempt did. Replaces $\varsigma\,\xi_t$ in the asset update with $\varsigma\,E[\xi]$. Loses the ξ-variance in savings and gives 15–25% biases vs MC. Not fixable by small corrections.
- **m-indexed + correction term:** Algebraically,
  $$m_{t+1}^\text{splurge-in-budget} = m_{t+1}^\text{old} + (R/\Gamma)\,\varsigma\bigl[c^*(m_t) - \xi_t\bigr].$$
  Approximating $E[\xi_t \mid m_t] \approx E[\xi]$ and $\text{Var}[\xi_t \mid m_t] \approx \text{Var}[\xi]$, this becomes a deterministic m-shift plus an extra Gaussian convolution. Implementable as a post-processing step on the existing m-indexed TM. But the approximation error is from treating $\xi_t$ as independent of $m_t$, which it is not (since $m_t = (R/\Gamma)a_{t-1} + \xi_t$), and quantifying that error for a policy paper is awkward.
- **Joint $(m, \xi)$ state:** State space doubles to $N_m \cdot N_\xi$. The existing m-indexed structure carries over with one extra state coordinate. Exact, no approximation. Downside: $N_\xi \times$ slower than a-indexed, and most code paths need to be updated to handle the extra dimension anyway.
- **a-indexed TM:** State is $a_{t-1}$. Kernel integrates over $\xi_t$ in construction. One final sparse matrix of size $(N_a \cdot J) \times (N_a \cdot J)$. Exact. The refactor is mostly re-indexing existing code paths — `cFunc` is still evaluated on $m$ and the m-space math still applies, but the ergodic lives on $a$ and the transition is built by computing $m_t$ inside the kernel loop.

### 0.4 Important: this is ONE matrix, not N

The confusion would otherwise arise from reading "for each ξ atom, compute the deterministic map $g(a, \xi)$" as "build N matrices". It is not. The kernel is

$$T(a, a') = \sum_{\xi}\, p_{\xi}\cdot \mathbf{1}\{a' = g(a, \xi)\}$$

stored as **a single sparse matrix**. The sum over $\xi$ happens in the inner loop during construction and collapses into the final `T`. The representation never materializes a per-$\xi$ family of matrices. The rest of the plan uses this framing consistently.

---

## 1. Problem statement

Under splurge-in-budget, the savings rule (interpretation A, per-household) is

$$a_t = m_t - c_\text{actual}(m_t, \xi_t), \quad c_\text{actual}(m_t, \xi_t) = (1-\varsigma)\,c^*(m_t) + \varsigma\,\xi_t$$

so $a_t$ depends on the **realized transitory shock** $\xi_t$, not just on $m_t$. Consequently $m_t$ is **not a sufficient state** for next-period dynamics: the distribution of $a_t \mid m_t, j_t$ has genuine variance across agents whose $(m_t, j_t)$ coincide but whose $\xi_t$ differ.

The current TM (`tm_methods.py::build_tm_agg_fiscal`) indexes states by $(m, j)$ and uses $aPol(m, j) = m - (1-\varsigma)\,c^*(m) - \varsigma\,E[\xi \mid j]$, which **collapses ξ-variance to zero** within each $(m, j)$ cell. This is the source of the ~15–25% multiplier bias that appeared in the earlier flawed TM attempt. The fix is to make $a$ the state rather than $m$.

**Orthogonal note.** For the standard model (no splurge) and for the original buggy code (where $a = m - c^*(m)$ doesn't depend on $\xi$), $m$-indexing is correct. The switch to $a$-indexing is specific to splurge-in-budget.

---

## 2. Proposed solution: a-indexed TM

Index the TM by $(a, j)$ where $a$ is end-of-period savings and $j$ is the current Markov state. Under the timing convention

$$
a_t \;\xrightarrow{\text{j-transition + ξ draw}}\; (m_{t+1},\,j_{t+1},\,\xi_{t+1}) \;\xrightarrow{\text{policy}}\; a_{t+1}
$$

the transition kernel is

$$
P(a_{t+1}, j_{t+1} \mid a_t, j_t) = \text{MrkvArray}[j_t, j_{t+1}] \cdot \sum_{\xi} p_{\xi \mid j_{t+1}} \cdot \mathbf{1}\!\left[a_{t+1} = g_{j_{t+1}}(a_t, \xi)\right]
$$

with

$$
g_j(a, \xi) = \tfrac{R}{\Gamma_j}\,a + \xi - (1-\varsigma)\,c^*\!\left(\tfrac{R}{\Gamma_j}\,a + \xi,\,j\right) - \varsigma\,\xi
= \tfrac{R}{\Gamma_j}\,a + (1-\varsigma)\bigl[\xi - c^*_j\bigl(\tfrac{R}{\Gamma_j}\,a + \xi\bigr)\bigr].
$$

**One sparse matrix.** Dimensions: $(N_a \cdot J) \times (N_a \cdot J)$. Populated by summing contributions from $N_\xi$ atoms per $(a, j, j_{t+1})$ triple during construction — one matrix in memory, not $N_\xi$ matrices.

**Aggregation** — per-period quantities are computed by integrating over the post-arrival joint:

$$
C_\text{period} = \sum_{a_t, j_t} \pi(a_t, j_t) \sum_{j_{t+1}} \text{MrkvArray}[j_t, j_{t+1}] \sum_\xi p_{\xi \mid j_{t+1}} \cdot \big[(1-\varsigma)\,c^*(m_{t+1}, j_{t+1}) + \varsigma\,\xi\big]
$$

with $m_{t+1} = (R/\Gamma_{j_{t+1}})\,a_t + \xi$.

Income aggregate: $Y_\text{period} = \sum_{j_{t+1}} \pi_{j_{t+1}} \cdot E[\xi \mid j_{t+1}]$ (no $m$-interaction, unchanged).

---

## 3. File-by-file implementation plan

### 3.1 `Code/HA-Models/FromPandemicCode/tm_methods.py`

#### `build_tm_agg_fiscal` (line 574) — **major rewrite**

**Current signature:**

```python
def build_tm_agg_fiscal(agent, mCount=50, mMin=0.001, mMax=None, mFac=3,
                        Cratio=1.0, neutral_measure=False):
```

Returns dict with keys: `TranMatrix`, `dist_mGrid`, `cPol`, `aPol`, `markov_ergodic`, `mMax`, `cohort_ergodic`.

**New a-indexed version:**

- Accept `aCount, aMin, aMax, aFac` (or rename). Grid on `a` (not `m`).
- For each `(a_i, j_t)` in grid, for each `j_{t+1}` in MrkvArray[j_t,:], for each `ξ_k` in IncShkDstn[j_{t+1}]:
  - Compute `m_ij = (R/Γ_{j_{t+1}}) · a_i + ξ_k` (joint (m, ξ, j) tuple).
  - Evaluate `c*_ij = cFunc_{j_{t+1}}(m_ij, Cratio)`.
  - Compute `c_actual_ij = (1−ς)·c*_ij + ς·ξ_k`.
  - Compute `a'_ij = m_ij − c_actual_ij`.
  - Lottery-distribute `a'_ij` onto the a-grid with weight `MrkvArray[j_t, j_{t+1}] · p_ξ`.
- Accumulate into `TranMatrix[(a', j'), (a, j)]`. (**One matrix.** The $\xi$ sum happens inside the loop.)
- Return same dict format, but keys updated: `dist_aGrid` (instead of `dist_mGrid`); policy is integrated so there's no separate `cPol` / `aPol` in the return — consumers use the aggregators (see §3.2).

**Key sub-decisions:**
- **Newborn distribution** in `a`: a newborn has no assets, so `a = 0` (or minimum). Mass assigned to `a_min` with Markov-stationary distribution.
- **LivPrb**: death still replaces with newborn dist. Multiply kernel by LivPrb before adding newborn injection.
- **AD scaling** (`Cratio`): enters both the cFunc evaluation (2nd argument) and the ξ atoms (scaled by ADF in `build_experiment_period_tm`). In baseline TM, Cratio=1 so ADF=1; ξ atoms unscaled.

#### `_build_period_tm` (line 435) — **deprecate or rewrite**

Currently builds m-indexed transition from `aPol_2d` and `IncShkDstn_list`. Under a-indexing, subsumed into `build_tm_agg_fiscal`'s inner loop. Can keep as helper if still useful for multi-period recession experiments (likely rewrite).

#### `compute_type_aggregates_tm` (line 730) — **rewrite**

Currently:
```python
C_nrm = sum_j sum_m π(m,j) · cPol[j](m)    # HARK policy integral
C_splurge_nrm = (1-S) * C_nrm + S * Σ_j state_fractions[j] * E[ξ|j]   # eq (4) at aggregate
```

Under a-indexing:
```python
C_splurge_nrm = Σ_{a, j_t, j_{t+1}, ξ} π(a, j_t) · MrkvArray[j_t, j_{t+1}] · p_{ξ|j_{t+1}}
              · [(1-ς) · c*((R/Γ)·a + ξ, j_{t+1}) + ς · ξ]
```

Implementation note: can be factored into two passes over the ergodic, or precomputed as a weighted sum over `(a, j_t) × (j_{t+1}, ξ)` tuples.

#### `compute_period_aggregates_tm` (line 1579) — **rewrite**

Used in `propagate_experiment_tm` for per-period accounting. Takes `dist` and cPol, returns `C_splurge_nrm, Income_nrm`. Needs similar rewrite: aggregate over post-arrival (m, ξ, j) tuples.

#### `build_experiment_period_tm` (line 1387) — **rewrite**

Currently builds experiment TM with `mNrm_shift` for Check. Under a-indexing:
- `mNrm_shift` becomes the transformation `m = (R/Γ)·a + ξ + shift_{j_{t+1}}`. Check adds directly to m (not a), entering the next-period computation after `a_t` plus realized ξ.
- For the splurge portion: `c_actual` includes `ς·(ξ + shift)` since check is income-like (subject to splurge).
- `ad_tran_shk_scale` (AD scaling): multiply ξ atoms before computing `m = (R/Γ)·a + ad_scale·ξ`.
- Return TM and integrated per-period C/Y aggregates.

#### `propagate_experiment_tm` (line 1706) — **rewrite the Check inline block**

Current Check block does per-bucket aggregation with custom formulas. Under a-indexing, each bucket provides a different `shift`; for each bucket, compute `C_level_b` and `Y_level_b` using the integrated aggregator. Then weight by bucket probability.

**AD iteration**: `propagate_experiment_tm` computes Cratio path, which feeds back into the ξ scaling in `build_experiment_period_tm`. No structural change — just need aggregation to correctly integrate over ξ.

#### `_make_newborn_dist` (line 377) — **rewrite**

Currently places newborns on dist_mGrid based on IncShkDstn. Under a-indexing, newborns have `a = 0` (or `a_min`), Markov stationary `j`. This simplifies: `NewBornDist(a, j) = δ(a = a_min) · markov_ergodic[j]`.

#### `_compute_check_buckets` (line 1237) — **review but minor changes**

Bucket math itself (phase-out, pLvl quantiles) is unchanged. Rename fields if needed.

#### `compute_kernels` (line 840+) — **review**

Welfare kernels iterate over `(m, j)` ergodic. Under a-indexing, iterate over `(a, j_t)` ergodic and integrate over the arrival `(j_{t+1}, ξ)`. The existing `include_splurge=True` formula `(1-S)*c_next + S*th_s` is already the integrated aggregate; it just needs to be applied over the a-indexed ergodic.

#### `_to_neutral_measure`, `_apply_micro_transition`, `_solve_markov_ergodic`, etc.

Most helpers stay the same. `_apply_micro_transition` may need review if it assumes m-indexing.

### 3.2 `Code/HA-Models/FromPandemicCode/AggFiscalModel.py`

**No changes to MC path.** The `get_poststates` override already uses realized `self.shocks['TranShk']`, which is correct. MC naturally handles the ξ-dependence of savings.

### 3.3 `Code/HA-Models/FromPandemicCode/Simulate.py`

- Driver passes `dist_mGrid` as input to some functions; should pass `dist_aGrid` (or rename).
- `base_results_tm`, `baseline_tm_data`: contents change structure (now keyed on `a`, not `m`). Downstream consumers (Output_Results, figures) need to handle.

### 3.4 `Code/HA-Models/FromPandemicCode/Output_Results.py`

- Probably no change if TM output continues to provide `AggCons`, `AggIncome`, `NPV_AggCons`, `NPV_AggIncome` arrays. Those are what Output_Results consumes.
- Cumulative-multiplier figures depend on per-period dict, not on state-space indexing.

### 3.5 Tests / validation

- `test_tm_baseline.py`, `test_tm_microsteps.py`, `test_perstate_decomp.py`, etc. — many tests assume m-indexed state. Several will need rewriting.
- **New test**: verify that TM-`a` ≈ MC at CRRA=2 baseline (both use splurge-in-budget dynamics; should match within MC standard error).
- **Consistency test**: under ς=0 (splurge off), TM-`a` results should equal TM-`m` results exactly (both are standard HARK). This is a guaranteed equivalence check and the cheapest sanity test.

---

## 4. Grid design for `a`

- Range: `a ∈ [0, a_max]` with `a_min = 0` (borrowing constraint).
- Spacing: exp-multiple (same pattern as `dist_mGrid`) to concentrate near the constraint.
- `aCount`: start with ~100 (matches current `tm_mCount=100`); increase if aggregate moments don't stabilize.
- Lottery onto a-grid: linear interpolation (HARK convention). Ensure mass preservation to 1e-10 per period.

**Subtlety**: the a-grid should cover the support of the ergodic. Current `mMax=50` corresponds to ~m=50; `a_max` should be similar or slightly smaller (since c > 0 always).

---

## 5. Sequencing and migration strategy

Because the TM refactor is large, a staged migration:

**Stage 1: Parallel implementation** (~2 days)

Keep existing m-indexed functions intact. Add new a-indexed versions with `_a` suffix: `build_tm_agg_fiscal_a`, `compute_type_aggregates_tm_a`, etc. A flag `agent.tm_a_indexed = True` switches.

**Stage 2: Validation** (~1 day)

- Verify `tm_a_indexed=True, Splurge=0` matches `tm_a_indexed=False, Splurge=0` within numerical tolerance.
- Compare TM-`a` vs MC under splurge-in-budget at CRRA=2 baseline. Both should agree.
- Run Reduced_Run (3 types) with TM-`a` under splurge-in-budget to verify end-to-end.

**Stage 3: Baseline CRRA2 production run** (~4 hours)

Produce the corrected CRRA2 Baseline multipliers under a-indexed TM + splurge-in-budget. Compare to QE published and to MC Baseline under splurge-in-budget.

**Stage 4: Sensitivity + welfare** (~1-2 weeks)

Re-run sensitivity parametrizations under a-indexed TM + splurge-in-budget. MC welfare runs. Full reproduction.

**Stage 5: Migration and deprecation** (~1 day)

Once a-indexed TM validated and equivalent for ς=0, make it the default. Keep m-indexed as `_legacy` for back-compat or remove.

---

## 6. Estimated effort

| Stage | Effort | Cumulative |
|-------|--------|-----------|
| Stage 1: parallel a-indexed implementation | 16-24 h | 2-3 days |
| Stage 2: validation | 8 h | 3-4 days |
| Stage 3: CRRA2 production run | 4 h | 4-5 days |
| Stage 4: sensitivity + welfare | 80-120 h (mostly compute) | 2-3 weeks |
| Stage 5: migration/deprecation | 4 h | 3 weeks |

---

## 7. Open questions

1. **AD iteration stability**: Under a-indexing, the AD iteration (Cratio → ADF → scaled ξ → new aPol → new Cratio) has the same convergence structure but with different numerics. Verify no new instabilities.

2. **Harmenberg neutral measure**: Current code supports Q-measure via `neutral_measure=True`. Verify Harmenberg construction still works with a-indexing, and that the Q-ergodic π_Q(a, j) has the desired properties.

3. **Cohort-wise ergodic** (`cohort_ergodic`): currently built in `build_tm_agg_fiscal` for T_age-style death models. Needs to translate to a-indexing. (T_age is currently None globally, so this is lower priority.)

4. **Per-state fractions for splurge under AD**: the original aggregation uses `state_fracs[j]` (marginal π over m) to weight `E[ξ|j]`. Under a-indexing, the analogous weight is `π_j` (marginal of Markov state). Same answer — this may simplify.

5. **Checking the math with first-principles MC**: crucial. The MC simulation under splurge-in-budget gives the unambiguous reference. The a-indexed TM must match MC to confirm correctness.

6. **Welfare integration**: `compute_kernels` currently uses m-indexed ergodic. A-indexed kernels may simplify (since ξ is treated as an exogenous shock, not embedded in state).

---

## 8. Risks

- **Backwards compatibility**: existing test suites and regression tests (test_tm_*.py) assume m-indexing. Non-trivial migration.
- **Grid choice sensitivity**: a-grid resolution may need to be tuned; may differ from current mGrid settings (mCount=100).
- **Per-education heterogeneity**: 3 education types × 7 discount factors = 21 agents. Each has its own cFunc. Multiplied by Markov state J and atom count n_ξ, per-agent TM construction is ~J·n_ξ times more expensive than currently (acceptable).
- **Recession/policy experiments** have J expanded (J_micro=4 per macro state, typically 22+ macro states → J≈88-168). TM size `(n_a · J)² = (100·88)²` = 77M entries. Sparse storage essential — the kernel is sparse (each (a,j) maps to J_next · n_ξ destinations only).

---

## 9. References within repo

- `BUGS_private/HAFiscal_splurge_budget_inconsistency/bound-pair-interpretation_response.ipynb` — full argument for why splurge-in-budget is interpretation A with explicit line references to the estimation code
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/bound-pair-interpretation.md` — Edmund's defense of the original code
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/splurge-accounting_math-and-code.ipynb` — Section 8 derives the revised TM math under splurge-in-budget
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/splurge-accounting-preliminary-MC-results.md` — Reduced_Run MC results under splurge-in-budget
- `Code/HA-Models/FromPandemicCode/tm_methods.py` — current TM implementation
- `Code/HA-Models/FromPandemicCode/AggFiscalModel.py::AggFiscalType.get_poststates` — MC splurge-in-budget patch (already correct)
- `plans/20260418-1136h_splurge-in-budget-implementation-sequence.md` — concrete phased implementation with acceptance criteria
