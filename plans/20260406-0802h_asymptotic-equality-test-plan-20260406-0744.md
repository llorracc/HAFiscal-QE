# Validation plan: TM vs MC agreement (parity-map–driven, three tiers)

**Date:** 2026-04-06  
**Supersedes snapshot:** `plans/asymptotic-equality-test-plan_20260405-1606.md` (same lineage)  
**Authority for “what should agree”:** [`plans/method-parity-map.md`](method-parity-map.md)  
**Companion ladder (reports / progress naming):** [`plans/20260404-1746h_asymptotic-equality-test-plan_revised.md`](asymptotic-equality-test-plan_revised.md)

---

## 1. Objective

Run **focused tests** only for equivalences that **`method-parity-map.md`** documents: same mathematical object, same measure (P vs Q), same class (A–D). Do **not** treat invalid comparisons (e.g. MC-P vs MC-Q on $p$-nonlinear welfare) as failures.

Every **named scenario** (Gatekeeper, Harness, multi-type baseline, policy steps, …) should be exercised in **three tiers**, in order:

| Tier | Name | Primary goal | Agents (typical) | `mCount` | Parity tolerance |
|------|------|--------------|------------------|----------|------------------|
| **1** | **Smoke** | **Debugging:** code runs end-to-end; imports, TM build, MC path, optional notebooks complete without error. | **Minimum:** `Smoke_Test` (`AgentCountTotal = 100` per `Parameters.py`) or smallest cohort count that still builds a TM. | **50** (fixed for this plan) | *None* — pass/fail = execution only. |
| **2** | **Dev** | **Equivalence check (loose):** for objects the parity map marks as agreeing, differences should be **≤ 5%** (relative to reference defined per class below). | **Nontrivial:** e.g. `Reduced_Run` (**5,000** total agents across types, or scaled single-type `AgentCount` of that order). | **50** (same as smoke) | **5%** max rel. error on declared parity pairs. |
| **3** | **Gate** | **Equivalence check (tight):** same parity pairs as Tier 2, **≤ 2%** after adequate MC noise reduction and a finer TM grid. | **Large:** e.g. **≥ 40,000** single-type (Gatekeeper scale) or enough agents **per cohort** that rare states are not noise-dominated. | **≥ 100** (e.g. 100–150) | **2%** max rel. error on declared parity pairs. |

**Order:** Tier **1 → 2 → 3** for each scenario. Skip Tier 3 until Tier 2 passes.

---

## 2. What to test (from `method-parity-map.md`)

### 2.1 Class **A** ($p$-linear)

**Parity map:** MC-P = MC-Q = TM-P = TM-Q for aggregates built from $\mathbb{E}[p \cdot f(\cdot)]$.

**Concrete checks (paper-facing):**

- Mean **AggCons per capita** (and analogously **AggIncome** where used) — baseline and policy experiments where TM is available.
- **NPV-style multipliers and IRF paths** in `method-parity-map.md` (Step 5 / `Output_Results.py`): same class as consumption aggregates; include when the harness reproduces those experiments.

**Reference for relative error (Tier 2/3):** e.g. average of TM-P and TM-Q period-means (or documented single TM reference), consistent with `verify_four_methods_agreement.py`. Report **max over the four methods** vs ref.

**Tier 1 (smoke):** run the same code paths with minimal `N`; do **not** assert 5% or 2%.

### 2.2 Class **B** / **B′** ($p$-nonlinear, **within measure**)

**Parity map:** MC-P ≈ TM-P + **kernel**; MC-Q ≈ TM-Q + **kernel**; **P ≠ Q** (do not compare across measures).

**Concrete checks:**

- Mean marginal utility $\mathbb{E}[u'(c_{\text{lvl}})]$ (and related **felicity** $\mathbb{E}[u(c)]$ if tracked).
- Welfare objects in `Welfare.py` rows marked **yes** for TM-P + kernel vs MC-P (and separately Q vs Q).

**Reference:** within-measure only; use `compute_kernels` / `compute_pLvl_distribution`(_Q) as in production. **Tier 2/3:** |TM·kernel − MC| / ref ≤ **5%** then **2%** *within each measure*.

### 2.3 Class **C** (distributional)

**Parity map:** Lorenz, wealth shares, MPC by group → **MC-P** (or specialized TM convolution, not the default ladder).

**Tiers:** Smoke may **omit** or run a **single** sanity statistic; Dev/Gate **optional** unless explicitly extending the ladder. Do not demand four-way TM/MC agreement.

### 2.4 Class **D** (check phase-out)

**Parity map:** Check **consumption** multiplier: all four with **p-buckets**; check **welfare**: kernel + p-buckets, P vs Q split as in map.

**Tiers:** After baseline Class A passes Tier 2, add policy-specific smoke → dev → gate; document TM path uses `_compute_check_buckets` where required.

### 2.5 Invalid comparisons (never gate failures)

- MC-Q vs MC-P on Class **B** welfare / MU (different definitions).
- “Average of all four” as reference for Class **B**.
- TM **without** kernel vs MC on Class **B**.

---

## 3. Per-type architecture (unchanged)

- `economy.agents[i]` = homogeneous cohort (education × $\beta$ bin).
- TM: `build_tm_agg_fiscal(agent_i, …)` per `i`.
- MC: own `AgentCount`, own `seed`; shocks not shared across types except aggregates.
- **`baseline_tm_data[i]`** ↔ **`economy.agents[i]`** always.
- Economy totals: MC sum of level histories; TM $\sum_i \text{AgentCount}_i \, \mathbb{E}[p]_i \times$ normalized aggregate.

---

## 4. Applying the three tiers to the validation ladder

For **each** step below, run **Tier 1 (smoke)** with **`mCount = 50`**, then **Tier 2 (dev)** with **`mCount = 50`** and **5%** tolerances on parity-map objects, then **Tier 3 (gate)** with **finer TM** and **2%** tolerances.

| Step | Focus | Primary runner(s) | Parity classes exercised |
|------|--------|-------------------|---------------------------|
| **Gatekeeper** | Single type, baseline | `Gatekeeper_Asymptotic_Equality.ipynb`, `verify_four_methods_agreement.compare_four_methods` | **A**, **B** / **B′** |
| **Harness** | Multi-type wiring | `Harness_Asymptotic_Equality.ipynb`, `test_asymptotic_equality_revised.py --phase harness` | **A** (and indexing); **B** optional extension |
| **Multi-type baseline** | `--phase baseline` | `test_asymptotic_equality_revised.py` | **A** (+ planned per-type **B**) |
| **No-recession policies** | `norec-check`, `norec-ui`, `norec-taxcut` | same | **A**; **D** for check |
| **Recession suite** | `recession-baseline`, `recession-policies` | same | **A** |
| **AD loop** | `--phase ad-loop` | same | **A** (after `act_T` fix) |
| **Convergence sweep** | Optional automation | future `convergence_sweep.py` | Confirms Tier 2 → Tier 3 tightening with $N$ and `mCount` |

**Implementation note:** Today, **`compare_four_methods`** encodes Tier **3**-style defaults (`agents`, `m_count`, `rtol`, MU/felicity tolerances). To implement this plan literally:

- Add or document a **wrapper** (or CLI flags) for **Tier 1** (`Smoke_Test`, `m_count=50`, skip strict gates) and **Tier 2** (`Reduced_Run` scale, `m_count=50`, rtol / MU / felicity at **0.05**).
- Keep current Gatekeeper notebook parameters as **Tier 3** unless renamed.

---

## 5. Scale configuration table (this plan)

| Tier | Parametrization hint | Total / single-type `N` | `mCount` | `warmup` (TM-init MC) | `t_start` (Class B MC) | Pass criterion |
|------|----------------------|-------------------------|----------|------------------------|-------------------------|----------------|
| **1 Smoke** | `Smoke_Test` | **100** (total) | **50** | minimal (e.g. 0–2) | 0 | No exception; logs complete. |
| **2 Dev** | `Reduced_Run` | **5,000** (total) | **50** | e.g. 24 | ≥ 1 (prefer **50–100** if periods allow) | Parity-map pairs **≤ 5%** rel. err. |
| **3 Gate** | `Reduced_Run` + large `AgentCount` or notebook defaults | **≥ 40,000** (single-type) or per-cohort mass rule | **≥ 100** | 24 | **100** (if `periods` ≥ 200) | Parity-map pairs **≤ 2%** rel. err. |

Adjust `periods` so `t_start < periods` for Class B tail means. Single-type Gatekeeper already uses **300** periods in the notebook for `t_start=100`.

---

## 6. Reporting and progress (canonical names)

- **Step reports:** `history/asymptotic-equality-test-plan_revised_<StepName>_<YYYYMMDDTHHMM>.md` (UTC, minute resolution, no seconds), with **`## Step timing`** at end. See `asymptotic-equality-test-plan_revised.md` §2.1.
- **Progress tracker:** `history/asymptotic-equality-test-plan_revised_progress.md` (§2.2).
- Each report should state **tier** (Smoke / Dev / Gate), **tolerances**, and a **table keyed by parity class** (A vs B vs …), not a single blended “pass.”

---

## 7. Open implementation gaps (unchanged roadmap)

These do **not** block defining Tier 1–3; they block full coverage of every parity-map row.

| Gap | Blocks full parity on |
|-----|------------------------|
| `compute_welfare` / kernel on time-varying $\pi_t$ in `run_experiment_tm_nonbase` | Class **B** on non-baseline experiments |
| Shared `_mc_burnin_tm_init` vs `mc_burnin` (Q `pLvl` init) | Multi-type **B′** |
| Per-type `compute_kernels` in phases 1+ | Multi-type **B** |
| Class **D** check welfare (kernel + p-buckets) | Check welfare row |
| Automated `convergence_sweep.py` | Empirical Tier 2 → Tier 3 monotonicity |

---

## 8. Key files

| File | Role |
|------|------|
| [`plans/method-parity-map.md`](method-parity-map.md) | Defines which methods must agree on which results |
| `verify_four_methods_agreement.py` | `compare_four_methods` — Class **A** + **B** single-type (Tier 2/3 parameters TBD) |
| `tm_methods.py` :: `compute_kernels` | Class **B** TM side |
| `tm_methods.py` :: `compute_pLvl_distribution`(_Q) | $\mathbb{E}[p^k]$ for kernels |
| `Gatekeeper_Asymptotic_Equality.ipynb` | Tier 3-style Gatekeeper runner (adjust for Tier 1/2) |
| `Harness_Asymptotic_Equality.ipynb` | Harness runner (parity: wiring + optional drift) |
| `test_asymptotic_equality_revised.py` | Named phases (`harness` … `ad-loop`); legacy `0`–`7`, multi-type |
| `income_process_sst.py` :: `effective_perm_shock_periods_for_t_age` | Synthetic `pLvl` init (BUG-021); affects burn-in / Class **B** MC paths |
| [`plans/kernel-integration-spec.md`](kernel-integration-spec.md) | Kernel architecture |

---

## 9. Summary

1. **`method-parity-map.md`** is the checklist of **which** quantities must agree and **under which methods**.
2. **Three tiers:** **Smoke** (`N≈100`, `mCount=50`) → **Dev** (`N≈5000`, `mCount=50`, **5%**) → **Gate** (large `N`, `mCount≥100`, **2%**).
3. **Class A** and **within-measure Class B / B′** are the default automated gates; **C** optional; **D** when check experiments are in scope.
4. Wire **Tier 1/2** into scripts or notebooks explicitly; current Gatekeeper defaults are closest to **Tier 3** only.
