# TM vs MC: Mortality, Rebirth, and Drift — Problem Summary and Composer-Proposed Fixes

**Date:** 2026-03-23  
**Author:** Composer (Cursor) — maintainer-facing note, not paper text  
**Related context:** TM–MC initialization drift (`test_joint_distribution_quality.py`), period-1 trace (`trace_period1_tm_init_vs_tm_operator_composer.py`), `tm_methods.py` death/rebirth blocks.

---

## 1. Problem recap

### 1.1 What was observed

When Monte Carlo agents are **initialized from the TM ergodic** over **(micro state `j`, normalized market resources `m`)** and **`pLvl` is drawn independently** from an analytical age-conditional law (see `test_tm_init_mc.py`, including BUG-014 correction), **mean `aNrm` can drift** noticeably over a short horizon (e.g. ~20 periods) while a **post–long-burn-in** MC path shows **stable** mean `aNrm` over the same window.

A **period-1 diagnostic** (`trace_period1_tm_init_vs_tm_operator_composer.py`) showed:

- The **TM operator** satisfies **`P π ≈ π`** for the stationary **`π`** (numerically ~1e−12), so **within the TM model** death/rebirth is **not “missing”** from the transition.
- The **injected MC ensemble** can still have **mean `mNrm`** **above** TM **`E[m]`** by **~0.14** in a representative run, largely from **uniform jitter within each `m` grid cell** (upward bias in mean `m`).
- **One** `sim_one_period` moves means only modestly; **multi-period** drift accumulates from **ongoing dynamics**, **birth/death**, and **joint-law** mismatch.

### 1.2 User hypothesis: “Does the TM get death and newborns wrong?”

**Not in the sense of omitting them.** In `tm_methods._build_period_tm`, for each source micro state **`j`**:

- **`death_prb = 1 − LivPrb_j`** sends mass into **`NewBornDist`** over **`(j′, m)`** (same newborn pattern for every `m` column in block `j`).
- **Surviving** mass is scaled by **`LivPrb_j`** and then undergoes **income shocks** and **micro transitions** as usual.

Because the TM state does **not** track **age**, **`_effective_LivPrb`** replaces per-period **`LivPrb`** with an **`L_eff`** so that **aggregate death/rebirth flow** matches **stochastic death plus forced exit at `T_age`** in MC. The docstring there states this is **exact for total turnover** but an **approximation for *who* dies** (boundary cohort vs random death) — a **second-order** composition effect.

### 1.3 Where TM and MC still disagree (real discrepancies)

Even with death/rebirth **present** in **`P`**, the **replacement distribution** need not match **MC `sim_birth`**:

| Aspect | TM (`NewBornDist`, `_make_newborn_dist`) | MC (`AggFiscalType.sim_birth`) |
|--------|------------------------------------------|--------------------------------|
| **Normalized wealth at birth** | Mass on **`m`** from **TranShk** jumped to **`dist_mGrid`**, mixed by **micro stationary weights** | **`aNrm`** (and then **`mNrm`**) from **lognormal init** parameters |
| **`pLvl`** | **Not** a TM state; handled via **`E[pLvl]`** (or MC override) elsewhere | **Redrawn** for every newborn from **lognormal** |
| **`Mrkv` / micro state** at birth | Embedded via **stationary micro weights** in **`NewBornDist`** | **Birth** code sets **`aNrm`/`pLvl`/`t_age`**; **Mrkv** evolves via shock/Markov logic in simulation |

So drift can reflect **different newborn economics** and **different coupling to `pLvl`**, not only “TM forgot mortality.”

### 1.4 Independence of `(j, m)` and `pLvl` at injection

The TM-init recipe **samples `(j, m)` and `pLvl` independently**. The **true** MC steady state generally has **correlation** between **normalized assets/resources** and **`pLvl`**. That **alone** can cause **evolution of joint moments** over a few periods even if **marginals** were tuned.

---

## 2. Inherent vs fixable

- **Inherent:** A **finite** **`(j, m)`** Markov chain **cannot** reproduce the **full** infinite-dimensional MC steady state **exactly** without **extra state** (e.g. age buckets, `pLvl` buckets) or an **external** bridge.
- **Fixable without a massive rewrite:** Several **targeted** changes reduce **bias** and **misalignment**; they trade a **little** complexity for **better** TM–MC agreement.

---

## 3. Proposed solutions (ordered by invasiveness)

### 3.1 Remove or fix **within-cell jitter** when sampling from TM ergodic (**low cost, high leverage**)

**Issue:** Uniform jitter inside each **`m`** bin can **raise** **`E[m]`** vs **`π`-weighted grid mean** (seen ~**+0.14** in one run).

**Options:**

- Sample **`m`** **exactly** on **`dist_mGrid`** using **`π`** (no jitter), or  
- Use **symmetric** jitter **centered** on the bin so the **conditional mean** remains the grid point, or  
- **Post-scale** sampled **`m`** so **`mean(m)`** matches TM **`E[m]`** under **`π`**.

**Complexity:** Small, localized to TM-init scripts / one helper.

---

### 3.2 Use **MC-measured `E[pLvl]`** in TM aggregates (**already wired**)

**Issue:** Analytical **`compute_analytical_mean_pLvl`** ≠ MC cross-section after burn-in (unemployment, shock discretization, selection).

**Mitigation:** `compute_baseline_tm_data(..., mc_E_pLvl=[...])` (per type) already allows **replacing** analytical **`E[pLvl]`** with **`np.mean(agent.state_now['pLvl'])`** after burn-in.

**Complexity:** Low; policy choice + plumbing in callers.

---

### 3.3 **Calibrate `NewBornDist`** to MC newborn **`mNrm`** (or **`aNrm`**) distribution (**moderate, one-off**)

**Issue:** TM newborns use **TranShk-on-grid** + **stationary `j`**; MC uses **lognormal `aNrm`/`pLvl`** and simulation timing.

**Mitigation:** Run a **short auxiliary MC**, histogram **newborns’** first-relevant **`mNrm`** (or **`aNrm`**), fit a **discrete distribution on `dist_mGrid`** (or adjust **`markov_weights`**) so TM **`NewBornDist`** matches **MC** under baseline parameters. Store as **table** or **fitted weights** checked into `Results/` or built at runtime once.

**Complexity:** Medium **once**; keeps TM **(j, m)** form.

---

### 3.4 **Few `pLvl` buckets** for baseline (reuse Check pattern) (**moderate**)

**Issue:** Scalar **`E[pLvl]`** ignores **concavity** / **heterogeneity** (Check path already uses **`_compute_check_buckets`**).

**Mitigation:** Optional **`n_buckets`** for **baseline** TM aggregation (mirror Check), weighted average of **per-bucket TMs** or **per-bucket `E[pLvl]_b`**.

**Complexity:** Moderate; multiplies work by **buckets** but reuses existing bucket machinery conceptually.

---

### 3.5 **Short MC “warmup” after TM injection (**low algorithmic complexity**, uses MC)

**Issue:** Any remaining **joint-law** error.

**Mitigation:** After TM-init, run **`K` `sim_one_period`** steps (**small `K`**, e.g. 5–20) before experiments; tune **`K`** using **`test_joint_distribution_quality.py`**-style metrics.

**Complexity:** Small code change; **pays** **`K`** periods of MC.

---

### 3.6 **Diagnostic toggles** (for attribution, not production)

- **`mortality_off`** (if available on agent): compare drift **with vs without** deaths to see how much is **rebirth** vs **grid/jitter/policy**.
- Compare **empirical newborn `(j, m)`** histogram from MC to **`NewBornDist`** mass — direct visual on **rebirth** mismatch.

**Complexity:** Low; helps decide whether to invest in 3.3.

---

## 4. What not to claim

- The TM transition matrix **does** include **death and replacement**; the open question is **calibration and dimension reduction**, not a **boolean bug** “mortality = 0 in TM.”
- **Eliminating all** TM–MC gap **without** extra state or a **MC bridge** is **not** realistic; the goal is **controlled** error and **documented** approximations.

---

## 5. File references

| File | Role |
|------|------|
| `Code/HA-Models/FromPandemicCode/tm_methods.py` | `_effective_LivPrb`, `_make_newborn_dist`, `_build_period_tm` death/rebirth |
| `Code/HA-Models/FromPandemicCode/test_tm_init_mc.py` | TM ergodic inject + analytical `pLvl` |
| `Code/HA-Models/FromPandemicCode/test_joint_distribution_quality.py` | 20-period marginal/joint drift vs burn-in |
| `Code/HA-Models/FromPandemicCode/trace_period1_tm_init_vs_tm_operator_composer.py` | Period-1 TM vs MC means |
| `Code/HA-Models/FromPandemicCode/AggFiscalModel.py` | `sim_birth` |

---

*End of document.*
