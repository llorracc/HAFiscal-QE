# Composer’s summary of the TM-vs-MC mission (for Claude review)

**Date:** 2026-03-23  
**Purpose:** This document states **my (Composer’s) understanding** of the work ahead on branch `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`. Please confirm or correct any point that is wrong or incomplete.

**Canonical plan:** `debug/20260323-1512h_full_execution_plan_for_AI_v2.md`  
**Clarifications:** `debug/20260323-1511h_full_execution_plan_for_AI_answers-from-ClaudeOpus4p6.md`, `debug/20260323-1517h_full_execution_plan_for_AI_answers-from-ClaudeOpus4p6-round2.md`

---

## 1. Overall mission

HAFiscal runs fiscal experiments (UI, TaxCut, Check, etc.) with **Monte Carlo (MC)** and a faster **transition matrix (TM)** implementation. The mission is to **validate TM against MC**, **fix real discrepancies**, and **document** what remains inherently approximate (finite `(j,m)` state, scalar or bucketed `pLvl`, etc.). Success is defined by **agreed numerical criteria** and **regression scripts**, not by eliminating every possible divergence.

---

## 2. What is already done (Phase 1)

I understand Phase 1 (through commit `be9a8914` per v2) as **complete**, including roughly:

- **Half-step TM** at the experiment boundary so period-0 treatment effects align with MC (addresses the large UI consumption TE issue that came from timing/mixing ages in one distribution).
- **Per-cohort ergodic** for **MC initialization** (`cohort_ergodic`), while **TM propagation** still used the **standard eigenvector ergodic** with effective death — so composition bias in **levels** can remain until Phase 3.
- **`mCount` default 100**, **BUG-014** `pLvl` init correction, **`base_aPol`** consistency across validate scripts.
- **TM-initialized MC** with **24-period warmup** replacing a long burn-in in `Simulate.py` for that path.

**Phase 1 smoke / regression** (from v2): `AggFiscalMAIN_reduced.py --glp1`, `validate_tm_ui.py` with large N/seeds/mCount, `test_cohort_ergodic.py`, `test_tm_init_mc.py`, `reproduce.sh --comp mini`.

---

## 3. Metric doctrine (critical)

- **Treatment effect:** `TE[t] = experiment_AggX[t] - baseline_AggX[t]` for AggCons / AggIncome.
- **Primary pass/fail:** **Period-0 relative error**  
  `rel_err = |TM_TE[0] - MC_TE[0]| / |MC_TE[0]|`  
  using **MC averaged across seeds before** forming the ratio.
- **Do not** use **full-path max relative error on the TE series** as pass/fail: later periods have TE near zero, so the ratio is unstable and can look huge while period-0 is fine.
- **NPV (per-capita consumption or income TE):** discounted sum of `experiment - baseline` per path, divided by `N_agents`; levels not multipliers. The **Check** problem is often stated as **~29%** TM vs MC on **NPV consumption TE** with income TE still ~1%.
- **Tiny denominator convention (round-2):** If after seed-averaging **|MC_TE[0]| < 1e-6**, use **absolute** error instead of relative; otherwise the ratio is meaningless.

---

## 4. Phase 2 — Check experiment (next, before Phase 3)

**Ordering:** **Phase 2 must finish (or be explicitly closed per gating below) before Phase 3.**

**Problem:** TM **overstates** MC on **NPV per-capita consumption treatment effect** (e.g. TM ~1.28 vs MC ~0.91 in the documented run; gap computed as `(TM - MC) / MC`). **Income** TE matches well. The gap is **not** explained by MC init: `test_tm_init_mc.py` shows TM-init vs burn-in MC Check NPV consumption TE agree (~0.91), so the bug is **TM vs MC methodology** for Check, not init.

**Hypothesis (v2):** TM **pLvl buckets** (`_compute_check_buckets`, check period block in `propagate_experiment_tm`) — phase-out, timing (t=0), or **E[pLvl] per bucket** vs MC distribution.

**Work:** Read TM + MC Check paths (`tm_methods.py`, `AggFiscalModel.py`, `Simulate.py`, `Parameters.py`), build diagnostics (GLP-1-style single type where useful), use **`test_first_period_trace.py`** as a Phase 2 MC period-0 diagnostic template.

**Phase 2 pass criterion (primary):** **`validate_tm_check.py --agents 200000 --seeds 3`** (and mCount as in v2 checklist, typically 100): **period-0 AggCons TE rel err < 5%.**

**Source of truth for Check validation:** **`validate_tm_check.py` uses the high-school type** (historical choice, consistent with other `validate_tm_*` scripts). **GLP-1 college** is **not** required as a separate Check validator; college can be a **secondary** check via e.g. `test_tm_init_mc.py` if type-specific suspicion arises.

**Gating vs NPV (round-2):** **Period-0 AggCons < 5% is sufficient to declare Phase 2 closed** and start Phase 3. If **NPV** consumption TE remains **>10%** off after that, **document** the residual (bug index or debug note) and note whether Phase 3 might help; **do not block** Phase 3 on NPV alone. If period-0 is fixed but NPV is still wrong, treat the remainder as **later-period dynamics** investigation.

**Phase 3 regression (Check line):** After Phase 2, the checklist must require **both** **AggCons[0] < 5%** and **AggIncome[0] < 1%** for `validate_tm_check.py` (income as guard rail).

---

## 5. Phase 3 — Per-cohort TM experiment propagation

**Ordering:** **After Phase 2.**

**Problem:** TM still propagates a **single** `(j,m)` distribution with **effective** death rate; **per-cohort ergodic** is only for MC init → **~2% level bias** that largely **cancels in TE** but hurts **absolute** AggCons/AggIncome levels.

**Design:** Propagate **T_age** cohort vectors each period: age cohorts, apply experiment TM with **raw `LivPrb`** (not `_effective_LivPrb`) for random death within cohort, **forced exit** at `T_age`, **newborn** cohort 0, aggregate consumption/income using **E[pLvl|age k] = E[pLvl_init] × G^k** under the stated **E[PermShk]=1** argument (mean independent of employment history; variance/covariance handled as second order, with `test_pLvl_factorization.py` as canonical ~0.06% Cov reference for the cited UI/college run).

**Half-step:** In per-cohort mode, **no half-step** — each cohort is already the correct **beginning-of-period** distribution for that age; the half-step fixed a **single-vector mixture** problem.

**Check + cohorts:** Phase 2 should fix **bucket internals** on the **aggregate** distribution; Phase 3 then applies propagation **per cohort** (different **E[pLvl]** by age → different normalized check). APIs should stay separable.

**Regression checklist (my understanding):**  
`validate_tm_ui.py` (AggCons[0] < 4%), `validate_tm_check.py` (**AggCons[0] < 5%** and **AggIncome[0] < 1%**), `validate_tm_taxcut.py` (AggIncome[0] < 1%), `reproduce.sh --comp mini`, `AggFiscalMAIN_reduced.py --glp1` sensible multipliers — all **at current errors or better**.

---

## 6. Phase 4 — TM-based AD solver

**Future / separate project.** No need to add hooks in Phases 2–3; AD loop is “Cratio path in → aggregate consumption out,” and TM can substitute for MC inside that interface later.

---

## 7. Environment and docs

- **HARK** must be from branch **`main_improve-tm-vs-mc-sim-infra-and-examples`** (includes `ConsAggIndMarkovModel`), installed editable into the project venv; path is machine-specific (`uv pip install -e …`). Do not downgrade HARK to hide import issues.
- **Bug trail:** `BUGS_private/HARK+HAFiscal_TM_vs_MC_bug_index.md`, changelog, and `debug/` session notes.

---

## 8. Context I treat as adjacent (not the core Phase 2–3 ticket)

Separate diagnostics showed **within-cell `m` jitter** when drawing from the TM ergodic can bias **E[m]** upward vs **`π`**, inflating short-run **mean `aNrm` drift** in TM-init experiments; **mean-matching `m`** or **no jitter** fixes most of that in PoC tests. I understand this as **initialization / testing hygiene** and **marginal alignment**, **not** a substitute for Phase 2 Check bucket work or Phase 3 cohort TM propagation.

---

## 9. Please confirm

1. Any misstatement of **phase ordering**, **pass criteria**, or **what Phase 1 already changed**.  
2. Whether **`validate_tm_check.py` high school** remains the **sole** official Check gate, or if you want an **explicit** college Check row in CI later.  
3. Whether **NPV** should ever become a **hard** gate (my read: **no**, per round-2 answers, aside from documentation if >10% residual).

---

*End of summary — Composer, for Claude review.*
