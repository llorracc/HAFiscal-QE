# Experiment results: TM-init “mortality / drift” fixes (PoC)

**Date:** 2026-03-23  
**Companion problem note:** [`20260323-1312h_composer-fixes-for-mortality-discrepancy.md`](./20260323-1312h_composer-fixes-for-mortality-discrepancy.md)  
**Implementing script (PoC, not production):** `Code/HA-Models/FromPandemicCode/test_mortality_fix_poc_composer.py`  
**Machine-generated outputs:** `debug/mortality_fix_poc_composer.csv`, `debug/mortality_fix_poc_composer_assessment.txt`

This document is written so another AI (or human) can **audit what was done**, **reproduce it**, and **judge what was accomplished** without reading the full chat history.

---

## 1. Goal of the experiment

The problem note argues that TM–MC “drift” after injecting agents from the **TM ergodic over `(j, m)`** is **not** primarily explained by “TM forgot mortality” (the period-1 trace shows **`Pπ ≈ π`**). Real issues include **within-cell `m` jitter biasing `E[m]`**, **independent `(j, m)` vs `pLvl`**, and **different newborn laws** in TM vs MC.

This PoC **does not change** `tm_methods.py`, `initialize_sim`, or production TM code. It **isolates** a few **low-invasiveness mitigations** from section 3 of the problem note:

1. **§3.1** — Remove or correct **`m`** sampling: no jitter vs jitter; **mean-match** injected **`mNrm`** to TM **`E[m]`** (beginning-of-period, ergodic-weighted grid expectation).
2. **§3.2-style** — Scale injected **`pLvl`** so **cross-sectional mean** matches **MC after long burn-in** (tests whether **scalar `E[pLvl]`** misalignment drives **mean `aNrm`** drift in this diagnostic).
3. **§3.5** — Optional **`K`** periods of **`sim_one_period`** **after** inject **before** measuring drift (“warmup”).

**Success criterion (operational):** Over a fixed short window, **mean `aNrm`** should move **less** if the inject is closer to the **MC stationary joint law**. A **reference** is: same economy, **400-period MC burn-in**, then **20-period** continuation — mean `aNrm` drift ≈ **0.006%** in the recorded run.

---

## 2. What was built (artifact summary)

| Artifact | Purpose |
|----------|---------|
| `test_mortality_fix_poc_composer.py` | Standalone script: builds economy, TM baseline data, runs scenarios A–H, writes CSV + summary text |
| `mortality_fix_poc_composer.csv` | One row per scenario; numeric fields for reproduction and plotting |
| `mortality_fix_poc_composer_assessment.txt` | Human-readable echo of key scalars and drift lines |

**Naming:** Filenames include **`composer`** by request for traceability.

---

## 3. Methodology (precise enough to re-implement)

### 3.1 Economy and calibration

- **`return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")`** — college agent only (`DiscFacDstns[2]`), **`AggFiscalType`** + **`AggregateDemandEconomy`**, same **`IncShkDstn` / recession plumbing** pattern as other FromPandemicCode diagnostics (mirrors setup in related tests).
- **`BaseType.cycles = 0`**, **`AgentCount = N`** with **`N = 80_000`**.
- Economy is **solved** once; each scenario uses **`deepcopy(AggEco)`** of the **solved** economy so the **consumption policy** is fixed across scenarios.

### 3.2 TM ergodic and grids

- **`compute_baseline_tm_data(AggEco, mCount=50, verbose=False)`** — baseline transition-matrix pipeline; **`mCount`** → **`M = 50`** **`m`** grid points.
- **`ergodic`** — stationary distribution over **flat index** `bin = j * M + m_idx` (length **`J * M`**).
- **`dist_mGrid`** — TM **`m`** grid (same length **`M`**).
- **TM expected `m` (BOP under π):**  
  `E_m_tm = Σ_j ( Σ_{m_idx} π_{j,m_idx} * dist_mGrid[m_idx] )`  
  Implemented as `_tm_Em_bop(ergodic, dist_mGrid, M, J)`.

**Recorded values (one run):**

- **`E_m_tm ≈ 2.289923`**
- **`J`** = number of base Markov states from parameters (college baseline).

### 3.3 Fair cross-scenario randomness (critical for A/B)

To compare scenarios **only** on **`m`** handling (and warmup / `pLvl` scale), the script:

1. Draws **`agent_bins ~ Categorical(π)`** with **`np.random.RandomState(42)`** (module-level **`RNG`**).
2. Precomputes **four `mNrm` vectors** of length **`N`** from the **same** `agent_bins` and **`RandomState(42)`** for jitter:
   - **`jitter`:** uniform in **`[grid[idx], grid[idx+1])`**, last bin extended by **1%** (same rule as prior jitter recipe).
   - **`no_jitter`:** **`dist_mGrid[agent_bins % M]`**.
   - **`mean_match`:** **`jitter * (E_m_tm / mean(jitter))`** — exact mean match to **`E_m_tm`** (up to float noise).
   - **`no_jitter_mean_match`:** **`no_jitter * (E_m_tm / mean(no_jitter))`** — removes tiny grid-weight vs sample mismatch.
3. Draws **`pLvl`** and **`t_age`** **once** with **`RandomState(999)`** via **`_pLvl_draws`**, and **reuses** across **all** scenarios that do not rescale `pLvl`.

**Consequence:** Differences in outcomes between A/B/C/D are **not** confounded by independent **`pLvl`** redraws.

### 3.4 Analytical `pLvl` draw (`_pLvl_draws`)

Matches the **test-style** construction (including **BUG-014-style** lognormal correction): age distribution from **`LivPrb`**, **`PermGroFac`**, **`pLogInitMean` / `pLogInitStd`**, permanent shock variance from **`IncShkDstn_base[0][0]`**, **`−σ²/2`** and normal draws per age. **Not** identical to every production `initialize_sim` branch — this PoC is **aligned with TM-init test philosophy**, not a full HARK init audit.

### 3.5 Injection into MC state

For each scenario, a **fresh** copied agent:

- **`initialize_sim()`** then **overwrite**:
  - **`state_now['aNrm']`** from **`mNrm − c(mNrm, j)`** via **`_aNrm_from_m`** (per-`j` **`cFunc`** from **`solution[0]`**).
  - **`state_now['pLvl']`** (optionally **scaled** — see scenarios E/F/H).
  - **`shocks['Mrkv']`** from **`agent_j = agent_bins // M`**.
  - **`t_age`** from the shared draw.
- **`_prepare_agent`:** sets **`PlvlAgg`**, **`RfreeNow`**, **`AggDemandFac`**, etc., to neutral constants for this diagnostic.

### 3.6 Optional `pLvl` scaling (tests §3.2 hypothesis in inject space)

If **`scale_pLvl`:** multiply all injected **`pLvl`** by **`mc_mean_pLvl / mean(agent_pLvl)`** where **`mc_mean_pLvl`** is measured **once** from a **separate** long burn-in (below). **Mean `pLvl` after scaling** matches burn-in mean (**≈ 20.99048** in the recorded run); pre-scale mean was **≈ 21.04467** (see CSV).

### 3.7 Burn-in reference path

- **`deepcopy`** of solved economy, **`initialize_sim()`**, **`_prepare_agent`**, then **`BURN_IN_PERIODS = 400`** × **`sim_one_period`**.
- **`mc_mean_pLvl = mean(pLvl)`** at end of burn-in.
- **Continuation drift (sanity benchmark):** from that state, **`TRACK_PERIODS - 1`** additional **`sim_one_period`** (total **20**-period window aligned with scenario metric — see next).

### 3.8 Primary outcome: mean `aNrm` drift

For each scenario:

1. **`warmup`** times **`sim_one_period`** (may be **0**).
2. **`aNrm_mean_t0 = mean(state_now['aNrm'])`**.
3. **`TRACK_PERIODS - 1`** further **`sim_one_period`** (so **20** periods span **t0 → tEnd** inclusive in the same sense as the script’s loop).
4. **`aNrm_mean_tEnd = mean(...)`**.
5. **`aNrm_drift_pct = (tEnd - t0) / max(|t0|, 1e-12) * 100`**.

**Reported burn-in continuation:** same formula on the **burn-in** agent after **400** periods, over **20** periods — **≈ +0.006%** (essentially flat).

### 3.9 Secondary metrics

- **`mean_mNrm_inject`**, **`mean_m_err = mean_mNrm_inject - E_m_tm`** — checks whether **`m`** fixes hit the TM **marginal** target.
- **`mean_pLvl_inject`** — confirms scaling row matches CSV.

---

## 4. Scenario definitions (labels A–H)

| Label | `m` recipe | `scale_pLvl` | `warmup` | Maps to problem note |
|-------|------------|--------------|----------|----------------------|
| **A** | jitter | no | 0 | Baseline biased jitter (§3.1 “bad” recipe) |
| **B** | grid only | no | 0 | No jitter |
| **C** | jitter + mean-match to **`E_m_tm`** | no | 0 | §3.1 post-scale / mean-fix |
| **D** | grid + mean-match | no | 0 | Strict grid + tiny correction |
| **E** | same as A | **yes** | 0 | §3.2-style mean `pLvl` align |
| **F** | same as D | **yes** | 0 | D + `pLvl` scale |
| **G** | same as D | no | **10** | §3.5 warmup |
| **H** | same as D | **yes** | **10** | D + scale + warmup |

---

## 5. Numerical results (recorded run)

Source of truth: **`debug/mortality_fix_poc_composer.csv`**. Values below are from that file (full precision available in CSV).

### 5.1 Summary table

| label | mean_m_err | mean_pLvl_inject | warmup | scale_pLvl | aNrm_mean_t0 | aNrm_mean_tEnd | **aNrm_drift_pct** |
|-------|------------|------------------|--------|------------|--------------|----------------|---------------------|
| A_baseline_jitter | **+0.17928** | 21.0447 | 0 | 0 | 1.4757 | 1.3268 | **−10.089** |
| B_no_jitter | +0.00054 | 21.0447 | 0 | 0 | 1.3064 | 1.2775 | −2.209 |
| C_jitter_mean_match_m | ~0 | 21.0447 | 0 | 0 | 1.3106 | 1.2856 | **−1.903** |
| D_no_jitter_mean_match_m | ~0 | 21.0447 | 0 | 0 | 1.3059 | 1.2774 | −2.181 |
| E_baseline_jitter_scale_pLvl | +0.17928 | **20.9905** | 0 | 1 | 1.4757 | 1.3268 | **−10.089** |
| F_no_jitter_mean_match_scale_pLvl | ~0 | **20.9905** | 0 | 1 | 1.3059 | 1.2774 | −2.181 |
| G_no_jitter_mean_match_warmup10 | ~0 | 21.0447 | 10 | 0 | 1.2858 | 1.2716 | **−1.103** |
| H_no_jitter_mean_match_scale_pLvl_warmup10 | ~0 | **20.9905** | 10 | 1 | 1.2858 | 1.2716 | **−1.103** |

**Burn-in continuation (same script):** **`aNrm_drift_pct ≈ +0.006%`** over **20** periods (from `mortality_fix_poc_composer_assessment.txt`).

**Wall time (logged):** ~**48 s** for the full script on the machine that produced `assessment.txt`.

### 5.2 Pairwise implications (what moved, what did not)

1. **A vs E (jitter, scale `pLvl` vs not):** **Identical** **`aNrm_*`** and drift. **Uniform rescaling of `pLvl` after `initialize_sim` + overwrite** does **not** change **mean `aNrm`** trajectory in this diagnostic (policies and overwritten states are consistent with scale neutrality for this aggregate).
2. **D vs F (mean-matched grid `m`, scale `pLvl` vs not):** **Identical** drift. Again, **`pLvl` level** shift **did not** fix **mean `aNrm` drift** here.
3. **G vs H:** **Identical** drift. Warmup dominates; **`pLvl` scaling** is redundant with warmup for this metric in this run.
4. **A vs B:** Removing jitter cuts **`mean_m_err`** from **~0.18** to **~5e−4** and reduces |drift| from **~10%** to **~2.2%**. **Order-of-magnitude** improvement.
5. **A vs C:** Mean-matching **jittered** `m` drives **`mean_m_err → 0`** and drift **−1.90%** — **slightly better** than B/D in this run (not guaranteed across seeds; **C** preserves **within-bin dispersion** unlike **B**).
6. **D vs G:** **10** warmup periods cut drift from **−2.18%** to **−1.10%**.

**“Best” in this run:** **G** and **H** (**−1.10%** |drift|); **closest to burn-in 0.006%** among TM-inits is still **~1.1%** away — **large residual**.

---

## 6. Interpretation (causal, tied to the problem note)

### 6.1 What this experiment **establishes**

- **Within-cell jitter** that **does not** preserve **`E[m]`** under **`π`** can inject a **large** upward **`m`** bias (**~0.18** vs **`E_m_tm ≈ 2.29`** here) and produce **very large** spurious **mean `aNrm` drift** (**~−10%** over **20** periods) **even when** death/rebirth is **not** “turned off” in TM.
- **Mean-matching `m`** (and/or **no jitter**) removes most of that **marginal `m`** error and **cuts drift by roughly a factor of ~5** (from **10%** to **~2%**), with **jitter + mean-match** slightly edging **grid-only** in this single run.
- **Scalar mean `pLvl` alignment** via **post-inject rescaling** **did not** improve **mean `aNrm` drift** in this setup — consistent with the idea that the remaining error is **joint law / dynamics**, not **level of `pLvl` alone**.
- **Short MC warmup** after inject **further** reduces measured drift — consistent with **§3.5** (“burn joint-law error”) — but **does not** close the gap to **true** long-run MC on this metric (**still ~1%** vs **~0%**).

### 6.2 What this experiment **does not** establish

- **No** change to **`NewBornDist`** / **`sim_birth`** (problem note **§3.3**) — **not** tested.
- **No** **`pLvl` buckets** or expanded TM state (**§3.4**) — **not** tested.
- **No** proof that **C** always beats **D**; **one seed** for **`(bins, jitter, pLvl)`**; re-run with different **`RNG` / `rng_p` seeds** for robustness.
- **Drift** is **one scalar summary**; it does **not** characterize full **distribution** match (cf. `test_joint_distribution_quality.py`).
- The script uses **college** only — other education groups may differ.

### 6.3 Relation to “mortality bug?”

These results **support** the problem note’s separation:

- Fixing **TM operator mortality** is **orthogonal** to the **largest** effect shown here, which is **inject construction** (**`m`** jitter / mean).
- Remaining **~1–2%** drift plausibly reflects **newborn law mismatch**, **`(m,pLvl)`** dependence, and **age aggregation** in TM — **not** “missing **`death_prb`** row” in **`P`**.

---

## 7. Reproduction

From repository root (with project Python env / `uv` as per `CLAUDE.md`):

```bash
python Code/HA-Models/FromPandemicCode/test_mortality_fix_poc_composer.py
```

Expect **`debug/mortality_fix_poc_composer.csv`** and **`debug/mortality_fix_poc_composer_assessment.txt`** to update. Minor float differences may appear across platforms; **qualitative rankings** should be stable unless RNG or library versions differ.

---

## 8. Changelog relative to earlier PoC drafts

- **Fair comparison fix:** **`pLvl` / `t_age`** draws are **shared** across scenarios (**`RandomState(999)`**); **`m`** variants are **deterministic functions** of the **same** **`agent_bins`** and jitter stream (**`RandomState(42)`**). Earlier drafts that advanced a **single** RNG through **`m`** then **`pLvl`** made **`pLvl`** differ across **`m`** modes and **confounded** comparisons.

---

*End of results document.*
