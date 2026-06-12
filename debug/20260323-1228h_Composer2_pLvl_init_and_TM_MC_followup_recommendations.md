# HAFiscal: Permanent-Income Initialization and TM–MC Follow-Up Recommendations

**Document type:** Extended recommendations for independent AI or human review  
**Authoring context:** Composer (Cursor) in conversation with repository maintainers  
**Date prefix in filename:** 2026-03-23  
**Repository:** HAFiscal-Latest (`Code/HA-Models/FromPandemicCode/`, `BUGS_private/`, `HARK/`)

---

## 1. Purpose and audience

This document collects **technical recommendations** about:

1. How **Monte Carlo (MC)** simulation **initializes permanent income (`pLvl`)** and related state, versus what a **long burn-in** or **transition-matrix (TM)** machinery assumes.
2. What has **already been implemented or documented** in this codebase (as of the conversation that produced this file).
3. What **optional next steps** remain, with **scope, risk, and implementation hints** so another AI can evaluate tradeoffs or implement changes.

**Intended reader:** An AI or developer who has **not** read the prior chat but can open the cited paths.

---

## 2. Background: what “ergodic” means in two different pipelines

### 2.1 TM side (`tm_methods.py`)

- **Wealth / employment (normalized):** `build_tm_agg_fiscal`, ergodic over **(micro Markov state × `mNrm` grid)**. This is a **large sparse transition matrix**; `find_ergodic_distribution` yields the stationary mass.
- **Permanent income level:** Not a full Markov matrix over `pLvl` bins. Instead:
  - **`compute_analytical_mean_pLvl(agent)`** returns scalar **E[pLvl]** under a **deterministic growth-by-age** story (plus truncated geometric ages when `T_cycle == 1`).
  - **`compute_pLvl_distribution(agent, n_points=...)`** builds a **discrete law** (`pLvl_grid`, `weights`): mixture over age cohorts of **lognormals**, with **`μ_k`**, **`σ_k²`** including **permanent-shock variance** accumulated over **`k`** idiosyncratic shock periods and a **BUG-003** convention: the **first** `PermGroFac` step has **no** idiosyncratic shock variance (see comments in `tm_methods.py`).

### 2.2 Default MC side (HARK + `AggFiscalType`)

**Entry point:** `AggFiscalType.initialize_sim` → `IndShockConsumerType.initialize_sim` → then HAFiscal-specific **`Mrkv`** initialization.

**`pLvl` and age (typical `cycles == 0`):**

1. **`AgentType.initialize_sim`** calls **`sim_birth(all_agents)`** once. For `AggFiscalType`, **`pLvl`** is drawn from a **lognormal** parameterized by **`pLogInitMean` / `pLogInitStd`** (and aggregate scaling if applicable).
2. **`IndShockConsumerType.initialize_sim`** then calls **`_initialize_ergodic_ages()`** when **`init_ages_ergodic`** is true (HARK default): **`t_age`** is redrawn from the **truncated geometric** steady state on **`{1, …, T_age}`**, and **`pLvl` is multiplied in place by `PermGroFac ** t_age`**.

**Important:** That scaling is **deterministic in `G` only**. It does **not** replicate a cross section that has lived **`t_age`** periods with **stochastic `PermShk`** each period, nor does it account for **unemployment** spells where **`PermShk` may be fixed at 1** in HAFiscal’s shock history logic.

**`Mrkv` at `t = 0` (HAFiscal, unless `use_prestate` / `Mrkv_univ`):** each agent is drawn i.i.d. to combined states **0 (employed)** or **1** with probabilities **`1 - Urate_normal`** and **`Urate_normal`**. This matches a **target unemployment rate** in a **binary** sense; it is **not** the **full stationary distribution** over all **`num_base_MrkvStates`** micro states (e.g. longer UB exhaustion, no-benefits state).

**Documentation status:** `AggFiscalType.initialize_sim` now has a **docstring** (added in this workstream) stating explicitly that default init is **not** the infinite-horizon MC ergodic joint distribution, and summarizing **`pLvl`** and **`Mrkv`** behavior with pointers to **`tm_methods`**, **`test_tm_init_mc.py`**, and **`BUGS_private/`**.

---

## 3. Known discrepancy: analytical vs MC `pLvl` (non-exhaustive)

Reasons **`compute_analytical_mean_pLvl`** (and the `pLvl` mixture in **`compute_pLvl_distribution`**) can differ from **MC cross-sectional `E[pLvl]`** after burn-in include:

- **Unemployment:** TM’s **`compute_pLvl_distribution`** docstring notes unemployment effects on `pLvl` growth are **ignored** (~second order). MC applies **state-dependent `PermShk`** (e.g. **1** when unemployed in some HAFiscal paths).
- **Finite `T_age` and newborn replacement:** stationary **age** mass can match the geometric model, but **conditional `pLvl` given age** in MC reflects **realized shock paths**, not **`G^t_age` × single newborn draw**.
- **Discrete shock grids** (`PermShkCount`, etc.): finite support vs continuous lognormal assumptions.
- **Initialization vs true stochastic steady state:** even with ergodic ages, **`pLvl *= G**t_age`** is a **shortcut**, not a draw from the **marginal of `pLvl` at age `t_age`** under the full model.

These are **modeling / approximation** issues, not necessarily bugs.

---

## 4. BUG-014 and `test_tm_init_mc.py` (implemented fix)

**Changelog reference:** `BUGS_private/HARK+HAFiscal_TM_vs_MC_changelog.md` — item **“13. Lognormal mean correction in pLvl initialization (BUG-014)”**.

**Scope:** **`Code/HA-Models/FromPandemicCode/test_tm_init_mc.py`** only (TM-ergodic sampling of `(j, m)` plus age-based **`pLvl`** for injected MC state).

**Problem (documented):** `log(pLvl)` was augmented with **`Normal(0, σ√k)`**-style noise **without** the **lognormal mean correction** **`−σ²k/2`** in the accumulated shock component, implying **`E[PermShk] > 1`** per period in expectation and compounding to roughly **~7% `E[pLvl]` overshoot** at typical ages.

**Fix (implemented):** add **`agent_ages * (-PermShk_var / 2.0)`** (and equivalent in seed loops) alongside **`Normal(0, sqrt(PermShk_var * agent_ages))`**, with in-file comments referencing **BUG-014**.

**Important distinction for evaluators:**

- This **does not** change **`AggFiscalType.initialize_sim`** or **`IndShockConsumerType._initialize_ergodic_ages`** for **standard** paper simulations.
- The **`test_tm_init_mc.py`** construction uses **`t_age`** for both the drift correction and **`sqrt(σ² * t_age)`**. **`compute_pLvl_distribution`** uses cohort index **`k = 0,…,T−1`** with **`μ_k = pLogInitMean + (k+1) log G − k σ²/2`** and **`σ_k² = pLogInitStd² + k σ²`**. There may be an **off-by-one / newborn-convention** difference between the **script** and **`tm_methods`** unless deliberately unified.

---

## 5. Full recommendation set (extended)

### R1 — **Unify optional MC `pLvl` init with `tm_methods` cohort law (production path)**

**Goal:** Allow **standard MC** (not only `test_tm_init_mc.py`) to optionally initialize **`pLvl` conditional on `t_age`** using the **same mathematical object** as **`compute_pLvl_distribution`**, via a **single shared helper** (e.g. in `tm_methods.py`).

**Motivation:**

- Reduces **TM vs MC** tension when comparing level aggregates that scale by **`E[pLvl]`** or use **`pLvl`**-dependent policies (e.g. stimulus check phase-out).
- Prevents reintroducing **BUG-014**-class mistakes in **another** file by duplicating log-sum logic.

**Suggested design:**

- Add something like **`draw_log_pLvl_conditional_on_age(agent, t_age, rng)`** or **`cohort_pLvl_log_params(agent, k)`** returning **`(mu, sigma)`** for **`k`** consistent with **`compute_pLvl_distribution`** (including **BUG-003**).
- Gate with an **explicit attribute or flag**, e.g. **`init_pLvl_method ∈ {'legacy', 'analytical_cohort'}`**, default **`legacy`** until validated against **`validate_pLvl_distribution.py`** and selected MC burn-in benchmarks.

**Risks:**

- **Behavior change** for existing papers if default is flipped without full replication checks.
- Must align **`t_age`** (HARK: **1…`T_age` in `state_now` after init convention) with **`k`** in **`tm_methods`**.

**Complexity:** Moderate — one helper + thin wiring in HARK init path (subclass override or post-pass after `_initialize_ergodic_ages`).

---

### R2 — **Align `test_tm_init_mc.py` with shared helper (diagnostic path)**

**Goal:** Replace duplicated formulas in **`test_tm_init_mc.py`** with calls to the **same helper** as R1 so **BUG-014** and **BUG-003** conventions live in **one place**.

**Motivation:** The script is currently **correct in spirit** for BUG-014 but **may diverge** from **`compute_pLvl_distribution`** by indexing.

**Complexity:** Low once R1 helper exists.

---

### R3 — **Optional scalar rescaling of `pLvl` to match `compute_analytical_mean_pLvl`**

**Goal:** After any draw, multiply all agents’ **`pLvl`** by a constant so **`mean(pLvl) == compute_analytical_mean_pLvl(agent)`**.

**Motivation:** Cheap **level** alignment for aggregates; useful as a **stopgap**.

**Limitation:** Does **not** fix **dispersion**, **tails**, or **covariance** with **`mNrm` / Mrkv**.

**Complexity:** Very low.

---

### R4 — **Employment-conditioned analytical correction (only if needed)**

**Goal:** Nudge **`pLvl`** (or **`log pLvl`**) for agents starting in **unemployed** micro states to reflect **fewer** employed-period **`G·ψ`** steps, using a **closed-form** correction from parameters — **not** from MC.

**Motivation:** Default **`Mrkv ∈ {0,1}`** means some agents start unemployed; their **`pLvl`** distribution might differ from **employed** at the same **`t_age`**.

**Risk:** Easy to become **ad hoc**; should only follow evidence from **`validate_*`** or controlled diagnostics.

**Complexity:** Low to moderate depending on how carefully the correction is derived and tested.

---

### R5 — **Documentation (light)**

**Status:** **Partially complete.**

- **`AggFiscalType.initialize_sim`** docstring: **done** (this workstream).
- **Optional:** Add a **one-line cross-link** in `README_IF_YOU_ARE_AN_AI/060_CODE_NAVIGATION.md` or `Code/HA-Models/FromPandemicCode/README_table_generation.md`-level doc pointing to that docstring — **only if** maintainers want discoverability outside the class.

---

### R6 — **Explicitly out of scope for “low complexity”**

- Full analytical **joint** stationary **`(Mrkv, mNrm, pLvl)`** for MC init without either **TM sampling** (as in **`test_tm_init_mc`**) or **long burn-in**.
- Exact **four-state** **`Mrkv`** initial mass matching the **micro chain** steady state, unless paired with **tests** and **changelog** entries.

---

## 6. Evaluation checklist (for another AI)

Use this to score or prioritize proposals:

| Criterion | Question |
|-----------|----------|
| **Correctness** | Does the change preserve **known TM–MC validations** (`validate_tm_check.py`, `validate_tm_taxcut.py`, `validate_tm_ui.py`, `test_tm_baseline.py`)? |
| **Scope** | Is the default behavior unchanged unless a **flag** is set? |
| **Single source of truth** | Does **`pLvl`** log-mean / variance logic live in **one** module shared by TM and MC? |
| **BUG-014 / BUG-003** | Are **lognormal drift** **`−σ²/2`** per shock period and **newborn shock count** conventions **explicit and tested**? |
| **Documentation** | Are **assumptions** visible in **docstrings** or maintainer docs? |

---

## 7. Primary file references

| Path | Relevance |
|------|-----------|
| `Code/HA-Models/FromPandemicCode/AggFiscalModel.py` | `AggFiscalType.initialize_sim` docstring; `sim_birth`; shock / Check logic |
| `HARK/HARK/ConsumptionSaving/ConsIndShockModel.py` | `_initialize_ergodic_ages`, `transition` (`pLvl` × `PermShk`) |
| `Code/HA-Models/FromPandemicCode/tm_methods.py` | `compute_analytical_mean_pLvl`, `compute_pLvl_distribution`, `_get_perm_shock_var`, Check buckets |
| `Code/HA-Models/FromPandemicCode/test_tm_init_mc.py` | TM ergodic inject + **BUG-014** fix |
| `Code/HA-Models/FromPandemicCode/validate_pLvl_distribution.py` | Analytical vs MC **pLvl** distribution check |
| `BUGS_private/HARK+HAFiscal_TM_vs_MC_changelog.md` | §13 BUG-014 |
| `BUGS_private/HARK+HAFiscal_TM_vs_MC_bug_index.md` | TM–MC bug index |
| `debug/20260323-1138h_tm_init_mc_and_check_gap.md` | Experiment note on TM-init MC and Check TE gap |

---

## 8. Summary table

| ID | Recommendation | Default MC affected? | Status |
|----|----------------|----------------------|--------|
| R1 | Shared analytical cohort `pLvl` init (optional flag) | Only if enabled | Not implemented |
| R2 | Refactor `test_tm_init_mc.py` to use shared helper | N/A (diagnostic) | Not implemented |
| R3 | Mean rescale to `compute_analytical_mean_pLvl` | Only if enabled | Not implemented |
| R4 | Unemployment-conditioned `pLvl` tweak | Only if enabled | Not implemented |
| R5 | Light documentation | N/A | **Partial** (`initialize_sim` docstring done) |
| R6 | Avoid full joint analytical init without TM/MC | — | Guideline |

---

*End of document.*
