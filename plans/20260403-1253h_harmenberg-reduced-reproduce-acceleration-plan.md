# Plan: Accelerating HAFiscal Reduced Reproduction Using Harmenberg / BST Appendix Results

**Date**: 2026-04-02  
**Context**: `reproduce_min.py` (invoked by `./reproduce.sh --comp min`) runs a **reduced** pipeline: Step 4 uses precomputed HANK-SAM Jacobians; Step 5 runs `AggFiscalMAIN_reduced.py` with `Parametrization='Reduced_Run'` (fewer discount factors, `N=100` agents in the MC branch, looser AD iteration settings when AD is on). The notebook `Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb` and BufferStockTheory `ApndxHarKmenberg` formalize when 1D Harmenberg methods are exact, when covariance matters, and when approximations (copula, independence) are acceptable.

This plan outlines **analysis and engineering work** to make that reduced path faster without silently changing economic conclusions beyond documented tolerances.

**See also**: `history/20260404-hafiscal-four-way-verification-and-tm-init-report.md` — report on baseline single-type agreement across MC P/Q and TM P/Q, TM-initialized MC burn-in, and init stability metrics (companion to Type A/B acceleration work below).

---

## 1. Baseline inventory (what the reduced run actually does)

| Component | Role | Primary cost driver today |
|-----------|------|---------------------------|
| `AggFiscalMAIN_reduced.py` | Policy experiments under `Reduced_Run` | TM build + ergodic + experiment paths; AD fixed-point if `Run_AD` |
| `Simulate.py` / `tm_methods.py` | `sim_method='TM'` (default in reduced) | Grid sizes (`mCount`, `pLev` buckets), Markov state count, AD inner loops |
| `Output_Results.py` | Tables/figures from simulation output | Some statistics may assume MC-shaped outputs |
| Step 4 (`HA-Fiscal-HANK-SAM-to-python.py`) | Uses downloaded `.obj` Jacobians | Already amortized in `min` scope |

**Deliverable for Phase 0**: A short internal map (spreadsheet or markdown table) listing each **output object** the reduced run produces (multipliers, IRF series, welfare entries, quartile MPC tables if any) and classifying it as:

- **Type A**: $p$-linear aggregate (mean $C$, income, assets, fiscal multipliers as currently defined) → Harmenberg 1D identity applies; covariance corrections **not** required for the level.
- **Type B**: Depends on $\mathbb{E}[p \cdot g(m)]$ with nonlinear $g$ (e.g. $g=c'$ for weighted MPC as in notebook §8j) → still $p$-linear in the integrand; 1D $Q$-measure sufficient under theory; validate numerically.
- **Type C**: Nonlinear in $p$ (inequality, Gini, welfare, tail shares) → joint $(m,p)$ or reconstruction (2D TM, MC, or copula) per appendix “When the Joint Distribution Is Required”.

---

## 2. Theory → implementation levers (from `ApndxHarKmenberg` + notebook)

### 2.1 Exact 1D aggregation (no extra covariance term)

For Type A and Type B statistics that are expectations of $p \times (\text{function of } m \text{ only})$, the appendix gives

$$\mathbb{E}_P[p\, g(m)] = \mathbb{E}_P[p]\cdot \mathbb{E}_Q[g(m)]$$

when the consumption problem is solved under **measure $P$** and simulation/TM aggregation uses the **neutral measure $Q$** on $m$.

**Action items**

- Audit `tm_methods.py` and `AggFiscalModel` aggregation paths for reduced runs: confirm every Type A/B aggregate uses $Q$-consistent weights (already partly documented in `math-deriv-harm` / code comments).
- Identify any remaining “accidental” use of physical-measure $m$-marginals scaled by $\mathbb{E}[p]$ (notebook §8j labels this **uncorrected 1D** and shows it can diverge from truth).

### 2.2 When covariance machinery matters

- $\mathrm{Cov}(c_{\text{nrm}}, p)$ and the covariance kernel $\gamma(a)$ matter for **decompositions** and for statistics where explicit separation of within-shock vs between-agent terms is needed (notebook §8, BST §Covariance Kernel).
- For **scalar multipliers** that are ratios of $p$-linear objects, these covariances often cancel or need not be computed if both numerator and denominator use the same correct aggregation.

**Action items**

- List reduced-run **published numbers** that are *not* simple ratios of $p$-linear totals; for those only, assess whether notebook-style covariance or copula addenda are needed.

### 2.3 Nonlinear-in-$p$ outputs (Type C)

Appendix + notebook §8g–8h: Lorenz / Gini / welfare require joint $(p,m)$ or a reconstruction strategy.

**Action items**

- For `Reduced_Run`, decide policy: (i) **omit** Type C tables in the fastest path; (ii) **copula + 1D $Q$** + short MC calibration of $\rho$ (notebook pattern); (iii) **small dedicated MC** (fixed seed, $N$ larger than 100 only for those rows).

### 2.4 Stability of $\mathbb{E}[p^2]$ (calibration sanity)

Notebook + appendix material on $\mathbb{E}[p^2]$ finiteness under Blanchard–Yaari (cstwMPC-style parameters): avoid accidental parameter combinations that push $\text{LivPrb}\cdot \Gamma^2 e^{\sigma_\psi^2} \to 1$ (knife-edge variance). Reduced run should inherit production $\sigma_\psi$; document that “fast test” calibrations are not used in reproduce.

---

## 3. Computational levers specific to reduced reproduction

### 3.1 TM grid and state space

- **Harmenberg 1D**: shrink $n_m$ with error tracking against a **reference** reduced run (current defaults); notebook shows TM error vs $n_m$ often flattens past modest $n_m$.
- **Standard 2D TM**: only where Type C cannot be avoided; otherwise forbid in reduced path.
- **Markov dimension**: recession paths blow up state count; reduced run already trims experiments—ensure TM builds reuse warm-starts (`AggFiscalModel` state-count checks) and avoid rebuilding large TMs when switching scenarios if possible.

### 3.2 Aggregate demand (AD) loop

Reduced run uses fewer AD iterations; this is orthogonal to Harmenberg but dominates wall time when `Run_AD` is true.

**Action items**

- Profile Step 5 with `Run_AD` on/off separately.
- Test whether Harmenberg 1D ergodic + cheaper inner products reduce **per-iteration** cost enough to allow **tighter AD tolerance** in the same wall time (trade study).

### 3.3 Harmenberg MC (if any MC fallback remains)

Notebook: variance reduction for estimators of $\mathbb{E}[p\,c(m)]$-type objects. If reduced run still invokes MC for diagnostics or Type C:

- Use **solve under $P$, simulate under $Q$** workflow.
- Compare variance of aggregate consumption estimator vs standard MC at same $N$ (and consider lowering $N$ while preserving CI width).

### 3.4 `N=100` MC path (if `sim_method` includes MC or hybrid)

Reduced run comment: MC uses $N=100$. For Type A aggregates, Harmenberg MC or TM is preferable; if MC is kept for regression testing only, document that it is **noisy**, not timing-critical.

---

## 4. Validation protocol (must not break `reproduce.sh --comp min`)

1. **Golden references**: Freeze current `Reduced_Run` outputs (tables/figures hashes) as baseline on a pinned commit.
2. **Tiered tolerances**  
   - Type A/B: tight tolerance (e.g. relative error $<0.5\%$ on multipliers) when only grid/coarsening changes.  
   - Type C: looser or separate acceptance rules if copula used.
3. **Automated checks**: extend or add a pytest module (pattern: existing `test_tm_baseline.py`) that runs a **micro** subset of reduced scenarios with fast settings and compares to stored benchmarks.
4. **Regression against full TM**: periodically compare reduced fast path to a **non-reduced TM** reference on one scenario (overnight job), not part of `min`.

---

## 5. Phased work plan

| Phase | Goal | Key tasks | Risk |
|-------|------|-----------|------|
| **0** | Map outputs → Type A/B/C | Table in repo; agree with paper authors which tables are mandatory for `min` | Low |
| **1** | Aggregation audit | Trace `tm_methods` / `Output_Results` for uncorrected 1D; fix or document | Medium |
| **2** | Grid / TM optimization | Sweeps on $n_m$ (and AD settings) with validation protocol | Medium |
| **3** | Type C policy | Implement copula path or explicit omission for reduced | Medium (interpretation) |
| **4** | Docs & reproduce UX | Update `reproduce_min.py` comments / README with “fast path” flags and warnings | Low |

---

## 6. Deliverables

1. **Technical note** (optional `history/`): summarizes findings from Phases 0–2 for journal / replication appendix.  
2. **Code**: feature flags in `AggFiscalMAIN_reduced.py` or `Parameters` (e.g. `FastReproduce=True`) wired to validated grid/AD settings.  
3. **Tests**: fast regression tests preventing Harmenberg workflow regressions (solve measure vs simulation measure).

---

## 7. References in repo

- `Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb` — empirical sensitivity, Lorenz/MPC/covariance experiments.  
- `history/20260331-mathematical-derivations-harmenberg.md` — HAFiscal-specific notes pointing to BST as SST.  
- `BufferStockTheory-Latest` / `ApndxHarKmenberg.tex` — general derivations (joint distribution boundary, covariance kernel, higher-order moments).  
- `Code/HA-Models/FromPandemicCode/tm_methods.py` — production TM implementation and comments linking to math notes.

---

## 8. Out of scope (for this plan)

- Replacing precomputed HANK-SAM Jacobians (Step 4) with on-the-fly computation in `min` scope.  
- GPU batching of MC (separate track; notebook already discusses MC variance vs Harmenberg).  
- Changing **published** paper tables generated from **full** (`--comp full`) runs; this plan targets **reduced** verification path only unless explicitly promoted after validation.
