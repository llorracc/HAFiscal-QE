# Plan: Implement control-variate welfare6 estimator (MC + TM)

**Date:** 2026-04-19
**Status:** Ready to implement
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_explore-further-speedups`
**Estimated effort:** 1–2 days focused work

---

## 1. Goal

Implement an unbiased, low-variance estimator of welfare6 that combines Monte Carlo (MC) sampling with the Transition Matrix (TM) analytical approximation via the **control variate** method. Deliver:

$$\hat{\mathcal{W}}^{\text{CV}} = \hat{\mathcal{W}}^{\text{MC}} - \beta \cdot \bigl(\hat{\mathcal{W}}^{\text{MC, formula}} - \mathcal{W}^{\text{TM, formula}}\bigr)$$

The output is a reported welfare6 value per cell with a measured standard error that should be 5–100× smaller than the current raw-MC SE at the same agent count, without requiring larger simulations.

**Why this matters**: Current Phase 6-prime MC welfare6 at N = 9,982 per education group has single-seed relative SE of 6–12% on UI cells (measured — see `diag_welfare6_se.py`). Reaching <1% SE via MC alone requires 430K–1.5M agents per group. Control variates deliver that precision cheaply.

## 2. Required reading before starting

Read these in order. Don't try to re-derive what's already been established.

1. **`history/20260419-welfare6-TM-within-state-cross-scenario-bias.md`** — the full mathematical framing. Pay particular attention to:
   - §1.2: CRRA factorization showing welfare6's $p$-linearity.
   - §1.4: per-group homogeneity assumption (**critical** — this is what makes the approach work).
   - §4: decomposition hierarchy L1 / L2 / L3.
   - §12: the motivation for the control variate approach; has the cost table and the specific recommendation this plan implements.
2. **`history/20260412-welfare6-TM-analysis.md`** — the original L2 decomposition argument. §3 (CRRA factorization), §6 (what TM can compute), §7 (between-state vs. within-state).
3. **`Code/HA-Models/FromPandemicCode/Welfare.py`** — the current MC welfare6 implementation, lines 259–299 (Method 6, the full W6 formula). This is the ground-truth definition to match.
4. **`Code/HA-Models/FromPandemicCode/diag_welfare6_se.py`** — the diagnostic that measured current MC SE. It shows how to load the Phase 6-prime pickles, compute per-agent $A_i$, and form the welfare6 estimate. Your new estimator will extend this.
5. **`Code/HA-Models/FromPandemicCode/tm_methods.py`** — particularly `run_experiment_tm(compute_welfare=True)` at lines 995–1125. This is the existing TM path that computes per-capita $\mathbb{E}[u']$ and $\mathbb{E}[u]$ via the `compute_kernels` machinery. You will call into this.

## 3. Core mathematics

### 3.1 The welfare6 utility part

From the paper and `Welfare.py:259–281`:

$$\mathcal{W}^U = \frac{1}{\text{NPV}_{\text{cost}}} \sum_t R^{-t} \sum_i \frac{u(c^{\text{pol}}_{it}) - u(c^{\text{none}}_{it})}{u'(c^{\text{base}}_{it})}$$

and $\mathcal{W}_6 = \mathcal{W}^U + \mathcal{W}^B$ where $\mathcal{W}^B = (\text{NPV}_{\text{cost}} - \text{NPV}_{\Delta c})/\text{NPV}_{\text{cost}}$. $\mathcal{W}^B$ is deterministic in MC (ratio of aggregate NPVs) — focus all effort on $\mathcal{W}^U$.

### 3.2 CRRA-factored form

For CRRA utility with $c = pX$ (splurge-included normalized consumption $X = (1-S) c_{\text{norm}}(m, j) + S\theta$):

$$\frac{u(c^{\text{pol}}_{it}) - u(c^{\text{none}}_{it})}{u'(c^{\text{base}}_{it})} = p_{it} \cdot \underbrace{\frac{(X^{\text{pol}}_{it})^{1-\rho} - (X^{\text{none}}_{it})^{1-\rho}}{(1-\rho)\,(X^{\text{base}}_{it})^{-\rho}}}_{\equiv \Phi_{it}}$$

$p$ appears linearly (the $p^{1-\rho}$ from the utility difference cancels with $p^{-\rho}$ from the baseline marginal utility). Under $p \perp (m, j)$:

$$\mathbb{E}[h_t] = \mathbb{E}[p_t] \cdot \mathbb{E}[\Phi_t]$$

### 3.3 L2 approximation (for use as the control variate)

Condition on a single Markov state $j$, treating it as the shared state across scenarios for each agent:

$$\mathcal{W}^{U, \text{L2}}_t = \mathbb{E}[p_t] \cdot \sum_j f_j(t) \cdot \frac{\mathbb{E}[(X^{\text{pol}})^{1-\rho} \mid j] - \mathbb{E}[(X^{\text{none}})^{1-\rho} \mid j]}{(1-\rho)} \cdot \mathbb{E}[(X^{\text{base}})^{\rho} \mid j]$$

Sum over $t$ with discount $R^{-t}$ and divide by $\text{NPV}_{\text{cost}}$ to get $\mathcal{W}^{U, \text{L2}}$.

This is computable from:
- MC panel (to get per-scenario $\mathbb{E}[(X^{\text{scen}})^{\alpha} \mid j]$ and $f_j$ at each $t$)
- OR TM marginals per scenario (same quantities, different estimator)

The **difference** is that:
- MC-L2 uses the MC panel realizations.
- TM-L2 uses the TM analytical marginals; the existing `compute_welfare=True` path emits these.

### 3.4 The control variate estimator

$$\hat{\mathcal{W}}^{U, \text{CV}} = \hat{\mathcal{W}}^{U, \text{MC}} - \beta \cdot \bigl(\hat{\mathcal{W}}^{U, \text{MC-L2}} - \mathcal{W}^{U, \text{TM-L2}}\bigr)$$

Optimal $\beta = \text{Cov}(\hat{\mathcal{W}}^{U, \text{MC}}, \hat{\mathcal{W}}^{U, \text{MC-L2}}) / \text{Var}(\hat{\mathcal{W}}^{U, \text{MC-L2}})$, estimable by bootstrap.

Variance reduction: $\text{Var}(\hat{\mathcal{W}}^{U, \text{CV}}) = (1 - \rho^2) \cdot \text{Var}(\hat{\mathcal{W}}^{U, \text{MC}})$ where $\rho$ is correlation.

**Unbiasedness**: holds regardless of whether TM-L2 is a good or bad approximation. The control variate trick only shifts variance; never bias.

## 4. Implementation phases

### Phase 0: Add Markov state tracking to MC welfare pickles (hours)

The existing pickles at `Code/HA-Models/FromPandemicCode/welfare6_scenario_results_Baseline/` contain `cLvl_all_splurge` but **not** per-agent per-period Markov state. L2 needs `MicroMrkvNow` to condition on $j$.

Edit `welfare6_scenario.py` to save `Mrkv_hist` (already extracted by AggregateDemandEconomy.run_experiment) into the output pickle. Regenerate the pickles by re-running `run_welfare6_parallel.py`. Estimated cost: the original pickle generation took ~1 hour; should be similar.

*Cheaper alternative*: if regeneration is too slow, prototype with L1 (no conditioning, just ratio of aggregates). L1 will give a smaller variance reduction than L2 but requires no new simulation.

### Phase 1: Compute MC-L2 from extended pickles (half-day)

Write a post-processing module that:

1. Loads `cLvl_all_splurge` and `Mrkv_hist` for each scenario.
2. For each (cell, time $t$, Markov state $j$), computes $\mathbb{E}[(X^{\text{scen}})^{\alpha} \mid j^{\text{scen}} = j]$ by averaging over agents currently in state $j$ in scenario *scen*.
3. Computes $\hat{f}_j(t)$ as the fraction of agents in state $j$ at time $t$ (use $j^{\text{pol}}$ for policy-side aggregates, $j^{\text{base}}$ for baseline-side — or try both and see which gives higher correlation).
4. Forms the L2 estimate per cell.
5. Also recomputes the full MC estimate for reference (should match `diag_welfare6_se.py` output exactly).

### Phase 2: Compute TM-L2 analytically (half-day)

Extend or call into `tm_methods.py:run_experiment_tm(compute_welfare=True)` to produce analytical $\mathcal{W}^{U, \text{TM-L2}}$ for each cell. The existing code emits per-capita `mean_uprime_kernel` and `mean_felicity_kernel`; you need the L2 decomposition at the per-state level.

**Note**: `tm_methods.py:1115` raises `NotImplementedError` for a-indexed agents. For this validation the m-indexed path suffices — the existing production welfare runs are m-indexed. Use the m-indexed TM here.

If building the full L2 formula analytically inside `tm_methods.py` is too invasive, an acceptable shortcut: use the MC estimate of $\mathbb{E}[(X^{\text{scen}})^{\alpha} \mid j]$ (from Phase 1) paired with an analytical $f_j(t)$ from the TM's own state-fraction propagation. This hybrid gives most of the variance-reduction benefit with less code.

### Phase 3: Form the control variate estimator (half-day)

1. For each welfare cell, compute:
   - $\hat{\mathcal{W}}^{U, \text{MC}}$ (done in `diag_welfare6_se.py`)
   - $\hat{\mathcal{W}}^{U, \text{MC-L2}}$ (Phase 1)
   - $\mathcal{W}^{U, \text{TM-L2}}$ (Phase 2)
2. Bootstrap: resample agents with replacement, recompute both MC and MC-L2 for each bootstrap, estimate $\text{Cov}(\hat{\mathcal{W}}^{\text{MC}}, \hat{\mathcal{W}}^{\text{MC-L2}})$ and $\text{Var}(\hat{\mathcal{W}}^{\text{MC-L2}})$.
3. Compute optimal $\beta$, form $\hat{\mathcal{W}}^{U, \text{CV}}$, report its bootstrap SE.
4. Emit a summary table analogous to `diag_welfare6_se.py`'s, adding columns for the control-variate estimate, $\beta$, correlation, and the variance-reduction factor.

### Phase 4: Validation (half-day)

1. For Check and TaxCut cells, MC SE is already < 2%; the CV estimator should not introduce bias. Check $|\hat{\mathcal{W}}^{U, \text{CV}} - \hat{\mathcal{W}}^{U, \text{MC}}| < $ a few MC SEs.
2. For UI cells, check SE reduction: target < 1% relative SE from the CV estimator.
3. Sanity check: measure $\rho$ directly. If $\rho > 0.95$, variance reduction is $> 90\%$, good. If $\rho < 0.7$, something is off (the L2 formula may be badly misaligned with full MC — diagnose before reporting).

## 5. Key parameters and conventions (HAFiscal-specific)

- **$\rho$ (CRRA)** = 2.0 (from pickle). **$R$ (Rfree)** = 1.01.
- **T_sim = 40** periods (from pickle).
- **Education groups**: dropout / high school / college. Phase 6-prime run was on Baseline parametrization; pickles are in `welfare6_scenario_results_Baseline/`.
- **Current N per group**: ~9,982 (from pickle shapes).
- **Welfare cells**: 9 total — 3 policies (Check, UI, TaxCut) × 3 contexts (Rec=0 AD=0, Rec=1 AD=0, Rec=1 AD=1). All already in `diag_welfare6_se.py`'s output.
- **Per-group homogeneity assumption**: required for L2/L3 to be correct. Phase 6-prime runs with a single β per group (since β was estimated separately per group); for 7-β-bin runs, homogeneity assumption needs revisiting.

## 6. Measured results from `diag_welfare6_se.py` (for reference)

Current single-seed MC SE on welfare6 $\mathcal{W}^U$ (N = 9,982):

```
cell                       W_6     W^U     W^B       N   f_aff   CV(A) rel.SE  N→<1%
Check,  Rec=0, AD=0      0.966   0.826   0.139    9982   0.801    0.64  0.64%   4,149
UI,     Rec=0, AD=0      0.855   0.723   0.132    9982   0.036   12.28 12.29% 1,506,905
TaxCut, Rec=0, AD=0      0.990   0.878   0.112    9982   1.000    1.92  1.92%  36,868
Check,  Rec=1, AD=0      1.006   0.868   0.139    9982   0.801    0.71  0.71%   5,101
UI,     Rec=1, AD=0      1.460   1.320   0.141    9982   0.085    7.86  7.87%  618,182
TaxCut, Rec=1, AD=0      0.996   0.885   0.112    9982   1.000    1.94  1.94%  37,514
Check,  Rec=1, AD=1      1.011   0.862   0.149    9982   1.000    0.60  0.60%   3,569
UI,     Rec=1, AD=1      1.356   1.208   0.148    9982   0.692    6.56  6.57%  430,833
TaxCut, Rec=1, AD=1      0.999   0.880   0.120    9982   1.000    1.93  1.93%  37,335
```

**Target for the CV estimator**: push rel.SE below 1% on all rows, including the UI cells.

## 7. Non-obvious gotchas (context from the session that produced this plan)

- **Harmenberg neutral measure (`tm_neutral_measure`)** is inconsistently applied across TM runners. `AggFiscalMAIN_reduced.py` sets `True`; `run_reduced_tm_a_indexed.py` sets `False`. For the MC comparison in this plan, use whichever matches the MC generation (the Phase 6-prime pickles came from `welfare6_scenario.py`/`run_welfare6_parallel.py`, which inherit from the base simulation setup — check that setup and match).

- **`compute_welfare=True` is m-indexed only**. `tm_methods.py:1115` raises for a-indexed. The existing Phase 5 production runs are TM_a (a-indexed), but the Phase 6-prime welfare MC pickles are NOT dependent on a- vs. m-indexing (they're pure MC). The TM-L2 analytical value we need is m-indexed, consistent with the legacy `compute_welfare=True` path. This is fine — the control variate only needs *any* unbiased-by-construction TM approximation, not the "best" one.

- **CRN is essential.** The MC panel uses Common Random Numbers across scenarios (same idiosyncratic draws in base / policy / recession). This is what makes the per-agent matching work. Do not accidentally recompute with independent seeds per scenario.

- **Splurge term's $\theta$ coupling.** $X_{it} = (1-S) c(m, j) + S\theta$ shares $\theta$ across scenarios under CRN. This creates a correlation in the per-agent welfare integrand that may or may not survive the L2 conditioning. The homogeneity argument in §4.5 of the companion doc says this collapses after the Markov chain mixing time (~10 quarters), but early periods carry a residual. Monitor whether the CV estimator has a transient-period bias; if so, might need to handle early periods separately.

- **Welfare.py has 6 distinct welfare formulas** (`Method 1` through `Method 6`), only one of which (Method 6) is the paper's published W6. Do not accidentally implement one of the others. See `Welfare.py:259` for the Method 6 reference line.

- **The `recession*.pkl` files are already probability-weighted** over max_recession_duration = 20 durations. No need to re-weight; `welfare6_scenario.py:_prob_weighted_rec` does this inside each subprocess.

## 8. Deliverables checklist

- [ ] Phase 0: `welfare6_scenario.py` emits `Mrkv_hist` in output pickles. Regenerated pickles at `welfare6_scenario_results_Baseline/`.
- [ ] Phase 1: New script `compute_welfare6_mc_l2.py` that reads pickles, computes MC-L2 estimates per cell, and matches MC full estimates as a reference.
- [ ] Phase 2: TM-L2 analytical values per cell. Either via extending `tm_methods.py` or a standalone wrapper that calls `run_experiment_tm(compute_welfare=True)` and extracts per-state aggregates.
- [ ] Phase 3: `compute_welfare6_control_variate.py` producing the CV estimator per cell with bootstrap SE. Output table includes MC / CV / TM-L2 / $\beta$ / $\rho$ / variance-reduction factor / bootstrap SE.
- [ ] Phase 4: Validation: CV estimator SE < 1% on all cells; no >2-MC-SE drift from MC point estimate; $\rho > 0.7$ on all cells.

## 9. Outcome decision tree

After Phase 4 completes, interpret results:

1. **All cells < 1% SE, $\rho > 0.9$**: ship the CV estimator as the primary welfare6 precision tool. TM L3 not needed.
2. **Most cells < 1%, UI-Rec cells in the 1–3% range with $\rho \sim 0.8$**: ship for Check/TaxCut; flag UI cells as "improved but not fully precise"; consider TM L3 as a follow-up.
3. **UI cells still > 3% SE with $\rho < 0.7$**: the L2 formula is structurally misaligned with MC — the within-cell residual ($\theta$-coupling or other) is large. Diagnose before building TM L3; the L3 may inherit the same residual.

## 10. Kickoff prompt for new Claude session

```
I want to implement the control-variate welfare6 estimator described in plans/20260421-0744h_welfare6-control-variate-implementation.md.

Start by reading that plan in full. Then read, in order:
  - history/20260419-welfare6-TM-within-state-cross-scenario-bias.md (§12 in particular)
  - history/20260412-welfare6-TM-analysis.md (§3, §6, §7)
  - Code/HA-Models/FromPandemicCode/Welfare.py (lines 259-299, Method 6)
  - Code/HA-Models/FromPandemicCode/diag_welfare6_se.py
  - Code/HA-Models/FromPandemicCode/tm_methods.py (lines 995-1160, the compute_welfare path)

When you've read these, propose the concrete Phase 0 change to welfare6_scenario.py (adding Mrkv_hist to the output pickle) and confirm where in run_welfare6_parallel.py the regeneration should be triggered. Do not start coding until I've approved that proposal.

The goal is an unbiased welfare6 estimator with <1% relative SE on all 9 cells (currently 0.6-12% single-seed). Details are in §6 of the plan for current numbers and §8 for the deliverables checklist.
```
