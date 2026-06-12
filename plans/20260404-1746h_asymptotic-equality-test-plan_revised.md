<!-- Status: DONE (superseded by implementation) -->
# Revised phased plan: TM vs MC vs Harmenberg (method agreement)

**Date:** 2026-04-04  
**Revises:** `plans/20260403-1253h_asymptotic-equality-test-plan.md` (phase descriptions and ordering)  
**Aligns with:** `plans/20260329-1853h_tm_scaleup_plan.md` (scaling dimensions), `test_asymptotic_equality_revised.py` (phase CLI)  
**Outcomes & lessons already captured:** `history/20260404-hafiscal-four-way-verification-and-tm-init-report.md`

This document is the **updated named ladder** for building confidence from simple to full HAFiscal comparisons. Use it when extending tests or when an AI agent needs a single roadmap.

**Markdown reports:** Every named step in §2 must produce **one** Markdown report file when the step is executed for validation. See **§2.1** for the exact basename pattern and the full list of filenames.

**Progress & timing:** While the ladder runs, a single **ongoing progress tracker** file (§2.2) must be updated so a user can see what finished, what is running, and elapsed time. Each step report **must end** with a **Step timing** section giving wall-clock duration for that step (§2.1).

## Rule: no hybrid ratios

**Never** compute a ratio whose numerator and denominator live under
different measures (P-track vs Q-track / Harmenberg neutral). In
particular:

- `NPV(ΔAggCons_Q) / NPV(ΔAggIncome_P)` — a hybrid multiplier, **forbidden**
- `NPV_C_Q / NPV_C_P` — a hybrid scaling check, **forbidden**
- `E_Q[f(m)] / E_P[g(m)]` more generally — **forbidden**

Under Harmenberg, `E_P[p·f(m)] = E_P[p] · E_Q[f(m)]`, so Q-track
aggregates are just P-track aggregates rescaled by `E_P[p]`. A hybrid
ratio silently embeds that scale factor and cannot be compared to a
same-measure multiplier. A 54% "error" against a TM reference almost
always means `E_P[p] ≠ 1`, not a bug.

A Q-track multiplier is only meaningful if **both** legs (consumption
and income response) are computed under the same Q-track; until the
Q-income leg is wired through the dual-MC shocks, test code must
report P-only multipliers and nothing else.

## Rule: every comparison must cite a math derivation

For **every** comparison the test driver makes between two computed
quantities (TM↔MC, P↔Q, TM-grid↔TM-grid, etc.), the test code must
print and the report must cite the specific section(s) of the math
derivation that establishes asymptotic equality of those quantities
as `AgentCount → ∞` and TM `mCount → ∞`.

Reference files (relative to repo root):
- `history/20260331-mathematical-derivations-TM-MC-convergence.md` (TMMC)
- `history/20260331-mathematical-derivations-harmenberg.md` (HARM)
- `history/20260331-mathematical-derivations-appendix.md` (APX)

If no derivation exists for a given comparison:

1. Pause and attempt the derivation inline.
2. If the derivation succeeds, add it to the appropriate math file and
   cite it.
3. If the derivation fails or is incomplete, the comparison must be
   labeled **UNPROVEN** (or **PARTIALLY PROVEN** if a partial result
   exists), prominently flagged at the print site, and recorded in the
   "Comparison registry" docstring at the top of
   `test_asymptotic_equality_revised.py`. Reports must repeat the
   warning whenever the comparison is summarized.

Status of all comparisons in `test_asymptotic_equality_revised.py`:

- **Phase 0 init-drift, Phase 1 baseline AggCons, TM ladder, Phase 5
  recession baseline** — ✓ PROVEN, see TMMC §3, §6.5, §7–10, §14.
- **Phases 2–4 no-recession multipliers, Phase 7 recession + policy
  multipliers** — ✓ PROVEN, see **TMMC §13.5** ("TM-Q ↔ MC-P
  multiplier identity"). The TM-Q track multiplies `E_Q[c_t]` by
  `E[p_t] = E[p_0]·F_t` period-by-period, where `F_t` is the exact
  `pLvl_factor` recurrence (BUG-015 fix in `tm_methods.py:1767-1786`).
  Harmenberg's identity gives `E_P[p_t·c_t] = E[p_t]·E_Q[c_t]` at
  every `t`; NPV is linear so the limits commute. **No uniform-G
  assumption is required** — `F_t` handles arbitrary state-dependent
  growth (employed vs. unemployed) exactly.
- **REMOVED — Phase 1 per-type baseline moments TM-Q vs MC**
  (was UNPROVEN; TM-Q reports `E_Q[m] = E_P[p·m]/E_P[p]`, MC reports
  `E_P[m]`; not asymptotically equal in general).
- **REMOVED — Phase 1 TM-P vs TM-Q ergodic moments diagnostic**
  (HARM §1 makes explicit that they're supposed to differ; not a
  convergence test).

---

## 0. What changed vs the original phased plan

| Topic | Original plan tendency | Revised stance (post–Apr 2026 baseline exercise) |
|-------|------------------------|--------------------------------------------------|
| Methods compared | Often **three-way**: P-MC, Q-MC, TM-Q; TM-P sometimes described as unavailable | For **baseline** in HAFiscal, **four-way** is implemented: add **TM-P** via `run_experiment_tm(..., neutral_measure=False)`. Non-base experiments may still be TM-Q–only until `run_experiment_tm` is extended. |
| Reference | TM-Q fine or MC large | For baseline single-type checker: reference = average of TM-P and TM-Q means (or either TM with explicit grid). Full paper: keep TM-xfine + multi-seed MC as in original plan. |
| Experiment horizon | Assumed `act_T` follows `Reduced_Run` | **`switch_to_counterfactual_mode` overwrites `act_T`** with module `T_sim` from `AggFiscalModel`; every harness must **re-apply** intended `act_T` and `get_economy_data` (see history report). |
| TM-initialized MC | Burn-in mentioned | **Mechanism is explicit:** `save_state` after per-type state is set → `run_experiment(use_prestate=True)` → `restore_state()` inside `initialize_sim`. Init quality should be checked with **early-period drift** (means + **Var(log mNrm)**, **Var(log pLvl)**), not only aggregate C. |
| MC population | Sweeps down to small N | **`Smoke_Test`:** N = 100 (crash / wiring only). **`Reduced_Run`:** **`AgentCountTotal = 5000`** as the reduced default for meaningful MC moments (see `Parameters.py`). **Gatekeeper / publication-quality gates:** still prefer **N ≥ 20k** single-type or enough mass **per cohort** in multi-type runs. |
| Multi-type structure | Described as “3 types” | **Clarified architecture:** there is no single pooled MC vector with heterogeneous parameters per row. There is **`economy.agents` = list of homogeneous cohorts** (education × β bin). TM builds **one transition matrix per list entry**. |
| Step deliverables | Logs / ad hoc notes | Each named step **must** emit a **Markdown report** whose basename is `<plan_stem>_<step_name>_<YYYYMMDDTHHMM>.md` (§2.1): creation-time stamp in UTC, minute resolution, **no seconds** in the filename. Commit or attach alongside other validation artefacts. |
| Observability | Console only | Maintain **`history/asymptotic-equality-test-plan_revised_progress.md`** during execution (§2.2): status per step, timestamps, and durations so far. Each step report **ends** with **Step timing** (wall-clock for that step only). |
| Level variables & welfare | Often implicit | Objects **nonlinear in permanent income** $p$ (welfare, inequality, progressive tax bases, variance of level consumption) need the **joint** distribution of $(m, z, p)$ under the **physical** measure—or an explicitly equivalent P-consistent construction. The neutral measure $Q$ is designed for **$p$-linear** aggregates. **Theory:** BST **`ApndxHarKmenberg`**, section *When the Joint Distribution Is Required*; `history/20260331-mathematical-derivations-harmenberg.md` §13; companions `history/20260331-mathematical-derivations-TM-MC-convergence.md` (“math-derive”) and `history/20260331-mathematical-derivations-appendix.md`. **Gatekeeper** must extend to these objects (see **Gatekeeper** in §2). |

---

## 1. Core principle: per-type initialization and simulation

**Lesson (non-negotiable for multi-type work):**

- Each **element** `economy.agents[i]` is a **separate** economic type (same prefs and shocks within the cohort, different from other indices).
- **Transition matrix:** `build_tm_agg_fiscal(agent_i, …)` uses **that** type’s solution and shock structure. There is **no** merged TM across education groups.
- **Monte Carlo:** Each type simulates **its own** `AgentCount` agents with **its own** `seed` and parameters. Shocks are **not** shared across types except through **aggregate** objects (e.g. AD feedback).
- **TM-initialized MC:** `compute_baseline_tm_data` returns **`baseline_tm_data[i]`** aligned with **`economy.agents[i]`**. Initialization and any burn-in loop must use **the matching index** — never draw states for type `j` from type `k`’s ergodic.

**Anti-patterns**

- Applying one type’s TM ergodic histogram to another type’s agents “to save time.”
- Concatenating all agents into one array and running one shock process with mixed β or mixed income calibration.
- Building one Markov chain whose states encode `(type, m, j)` unless you have explicitly engineered that (the production code does **not** do this; it loops types).

**Aggregation to economy totals**

- **MC:** `concatenate` histories across types, then sum levels (as in `run_experiment`).
- **TM:** Sum `AgentCount_i * E[p]_i * (normalized aggregate)` over `i` (as in `run_experiment_tm`).

---

## 2. Named validation ladder

Steps are **ordered by complexity** and **dependency**. Earlier steps are gatekeepers for later ones.

**Names (use these in prose):**

| Name | Role (short) |
|------|----------------|
| **Gatekeeper** | Single-type four-way TM/MC + init diagnostics; **extend** to level/welfare (esp. marginal utility / marginal welfare) and burn-in stability thereof |
| **Harness** | Multi-type wiring: `act_T`, TM index ↔ agents |
| **Multi-type baseline** | Per-type + economy baseline ergodic / AggCons |
| **No-recession policies** | Check, UI, TaxCut without recession |
| **Recession suite** | Recession baseline + recession × policy |
| **AD feedback loop** | Aggregate-demand fixed point (TM vs MC) |
| **Convergence sweep** | Grid / N scaling tables |

---

### 2.1 Markdown report files (mandatory per step)

**Requirement:** Running a named step for validation (human or CI) **must** write **one** `.md` file summarising that run.

**Basename pattern**

```text
<plan_stem>_<step_name>_<YYYYMMDDTHHMM>.md
```

- **`plan_stem`** (fixed for this document): `asymptotic-equality-test-plan_revised`
- **`step_name`:** the step title as in the §2 subsection heading — the text **before** the em dash `—`, or the full heading if there is no em dash — with **only** ASCII **spaces replaced by hyphens** (keep existing hyphens, e.g. **Multi-type** stays hyphenated).
- **`<YYYYMMDDTHHMM>`:** a **datetime stamp for the moment the report file is created** (when the writer first creates/opens the file for this report), formatted as **four-digit year, two-digit month, two-digit day**, literal **`T`**, **two-digit hour, two-digit minute** — all digits, **no** separators inside the date or time parts, and **no seconds** (example: `20260403T0708` for 2026-04-03 07:08). Use **UTC** when generating the suffix so paths are comparable across machines. Full example basename: `asymptotic-equality-test-plan_revised_Gatekeeper_20260403T0708.md`.

**Directory:** Default **`history/`** at the repository root (same family as dated outcome notes). A runner may document a different directory **only** if it stays a single agreed location for the whole ladder.

**Content (minimum):** date/time; parametrization / CLI; environment note if relevant (e.g. HARK pin); pass/fail; key numbers or tables (or pointers to logs); tolerances used; one short interpretation. If a step maps to several CLI phases (e.g. **No-recession policies**), **one** report still covers the whole step for that run.

**Measure labels (TM-P vs TM-Q) — mandatory in reports and in originating logs:** Any table or summary that reports Transition-Matrix (TM) results must state which **measure** is used: **TM-P** (physical; `neutral_measure=False` in `run_experiment_tm` / `compute_baseline_tm_data`) or **TM-Q** (Harmenberg neutral; `neutral_measure=True`). Labels such as “TM” or “TM ref” **without** **`-P`** or **`-Q`** are **not** sufficient—they are ambiguous because economy-level **p-linear** aggregates are normally **TM-Q**, while **P-ergodic** per-type moments may be **TM-P** for apples-to-apples comparison to MC-P. Step reports and the drivers/notebooks that generate them (`test_asymptotic_equality_revised.py`, `verify_four_methods_agreement.py`, Gatekeeper/Harness notebooks) must use explicit names in headers and row labels (e.g. **“TM-Q ref (AggCons per capita)”**, **“TM-P ergodic (per-type)”**). See also `plans/20260408-1026h_asymptotic-equality-driver-ladder-presets.md` §C (implementation checklist).

**Footer (mandatory, last section in the file):** The report **must** end with a Markdown section titled exactly **`## Step timing`** (nothing substantive after it except a blank line). Include at least:

- **Step:** the same name as in the §2 heading (before `—` if present).
- **Wall-clock start** and **wall-clock end:** ISO-8601 in UTC (e.g. `2026-04-04T18:32:01Z`), recorded when the step actually begins and ends.
- **Duration:** the difference as **human-readable** text (e.g. `12m 34s`) **and** **seconds** (e.g. `754.2 s`) for easy parsing.

Optional second paragraph under the same heading: **Sub-timings** (e.g. per `--phase` or per heavy subroutine) if the runner already measures them—do not block the step on perfect granularity.

**Filename templates** (under `history/` by default; replace `<YYYYMMDDTHHMM>` with the UTC creation stamp as above):

| Step (§2 heading) | Report basename pattern |
|-------------------|-------------------------|
| Gatekeeper | `asymptotic-equality-test-plan_revised_Gatekeeper_<YYYYMMDDTHHMM>.md` |
| Harness | `asymptotic-equality-test-plan_revised_Harness_<YYYYMMDDTHHMM>.md` |
| Multi-type baseline | `asymptotic-equality-test-plan_revised_Multi-type-baseline_<YYYYMMDDTHHMM>.md` |
| No-recession policies | `asymptotic-equality-test-plan_revised_No-recession-policies_<YYYYMMDDTHHMM>.md` |
| Recession suite | `asymptotic-equality-test-plan_revised_Recession-suite_<YYYYMMDDTHHMM>.md` |
| AD feedback loop | `asymptotic-equality-test-plan_revised_AD-feedback-loop_<YYYYMMDDTHHMM>.md` |
| Convergence sweep | `asymptotic-equality-test-plan_revised_Convergence-sweep_<YYYYMMDDTHHMM>.md` |

Each successful run **creates a new file** (do not overwrite undated basenames). If two reports for the same step start in the same UTC minute, disambiguate (e.g. append `_2`, `_3` after the time token, or wait one minute—**do not** add seconds to the filename). The **progress tracker** (**§2.2**) records the **actual path** chosen for each step so “latest” is always discoverable.

---

### 2.2 Ongoing progress tracker (mandatory during execution)

**Purpose:** One file that answers, at a glance: *which steps are done, which is running, when they started/ended, how long they took,* and *where the step report lives.*

**Path (default):** `history/asymptotic-equality-test-plan_revised_progress.md`  
(same `plan_stem` as §2.1; suffix `_progress` before `.md`.)

**When to update:** The runner **must** touch this file:

1. **At the start of a ladder run** — create or truncate/rewrite with a header (run id or date, parametrization, hostname optional) and mark all steps `pending` (or `skipped` if not in scope).
2. **When a step starts** — set that row to `running`, record **started at** (UTC ISO-8601), and set **Currently running** in a short summary line at the top.
3. **When a step finishes** — set status to `done` or `failed`, record **ended at**, **duration** (match the step report’s **Step timing**), and the **path** to the step’s Markdown report. Clear **Currently running** or point to the next step.
4. **On crash / interrupt** — leave the row `running` or set `interrupted` with last known time so the file still tells the truth.

**Shape (recommended):** Markdown with:

- A **top block** (5–10 lines): last update time (UTC), overall run status (`in progress` / `complete` / `failed`), **Currently running:** step name or `none`, optional **Elapsed since run start**.
- A **table** with one row per named step (same seven as §2): columns **Step**, **Status**, **Started (UTC)**, **Ended (UTC)**, **Duration**, **Report** (relative path into repo).

**How to monitor:** Refresh the file in an editor, or from a terminal use `watch -n 5 sed -n '1,80p' history/asymptotic-equality-test-plan_revised_progress.md`, or run `tail -f` only if the implementation chooses an **append-only event log** section at the bottom (then the table at the top should still be rewritten so the “current state” stays obvious).

**Orchestrator vs ad hoc:** If steps are run manually on different days, each run should either start a **new** tracker file with a run-specific name (same `YYYYMMDDTHHMM` convention as step reports, e.g. `…_progress_20260404T1832.md`) **or** append a new **Run** section at the end of the canonical `…_progress.md` so history is preserved without losing the latest state at the top.

---

### Gatekeeper — baseline, single type

**Runner (mandatory path for the plan):** Execute the standalone notebook **`Code/HA-Models/Gatekeeper_Asymptotic_Equality.ipynb`** (Run all, or non-interactive execution below). It calls **`compare_four_methods`** in **`verify_four_methods_agreement.py`**, prints the same diagnostics to the notebook log, writes the §2.1 Markdown report under **`history/`**, and refreshes **`history/asymptotic-equality-test-plan_revised_progress.md`** for the Gatekeeper row.

```bash
cd Code/HA-Models
MPLBACKEND=Agg uv run jupyter nbconvert --to notebook --execute Gatekeeper_Asymptotic_Equality.ipynb --output Gatekeeper_Asymptotic_Equality.ipynb
```

Add `--ExecutePreprocessor.timeout=3600` if needed. **CLI equivalent** (without automatic report): `cd Code/HA-Models/FromPandemicCode && python verify_four_methods_agreement.py` with flags matching the notebook’s `GATEKEEPER_PARAMS`.

**Status:** **Aggregates.** Four-way **mean `AggCons` per capita** (economy total ÷ `AgentCount`; and related timing / init-stability diagnostics for means and `Var(log mNrm)`, `Var(log pLvl)`) are implemented in **`verify_four_methods_agreement.py`** / **`test_verify_four_methods_agreement.py`** — treat as **DONE** for that slice. **Level / welfare gatekeeping** (mean marginal utility four-way + early **MU** drift in the init-stability block) is implemented in the same script and exercised by the Gatekeeper notebook. Further quantiles / variance of MU remain optional extensions per §2.

**Report (required):** `history/asymptotic-equality-test-plan_revised_Gatekeeper_<YYYYMMDDTHHMM>.md` (UTC at file creation; §2.1). The notebook creates this file; manual runs must still follow the same basename pattern.

**Artifacts:** `Code/HA-Models/Gatekeeper_Asymptotic_Equality.ipynb`, `FromPandemicCode/verify_four_methods_agreement.py`, `FromPandemicCode/test_verify_four_methods_agreement.py`

**Setup (existing):** One education group, `shock_type="base"`, default **N = 20 000**, **T = 100**, **warmup = 24**, **mCount = 100**.

**A. Aggregates (implemented)**  
Compare **TM-P, TM-Q, MC-P, MC-Q** on **mean aggregate consumption per capita**; timing table; **init stability** (mean mNrm, mean pLvl, frac employed, Var(log mNrm), Var(log pLvl)) over early periods. **Pass:** four-way means within documented `rtol`; init drift within documented thresholds; P–Q MC reconstruction within `pq_rtol`.

**B. Level distribution & welfare — marginal utility / marginal welfare (required extension)**  
The math notes (BST **`ApndxHarKmenberg`**, *When the Joint Distribution Is Required*; `history/20260331-mathematical-derivations-harmenberg.md` §13) stress that **welfare** and other **nonlinear-in-$p$** questions are not captured by neutral-measure shortcuts alone: implementations must agree on **physical**, $p$-aware objects (or a documented TM enumeration that recovers the same moments). For HAFiscal, the **most universally important** paper-facing object is the **distribution of marginal welfare**, proxied in practice by **marginal utility** (e.g. under CRRA, $u'(c_{\text{lvl}})$ with $c_{\text{lvl}} = p \cdot c_{\text{nrm}}$, or the exact scalar(s) **`Welfare.py`** uses for marginal-welfare comparisons — **document the chosen definition** in the Gatekeeper report).

1. **Four-way agreement:** For **each** of **MC-P, MC-Q, TM-P, TM-Q**, compute the **same** welfare-relevant marginal-utility summary(ies) (at minimum: **population mean** marginal utility, optionally variance / selected quantiles if stable at moderate $N$). Report a comparison table analogous to the `AggCons` block. **Pass:** differences within tolerances **documented separately** from aggregate consumption (TM discretization and Q reconstruction may warrant **looser** `rtol` than for $p$-linear aggregates; justify in the report).

2. **Burn-in / post-init stability:** For **each** method, plot or tabulate the same marginal-utility summary(ies) over **early experiment periods** after TM ergodic initialization and the **inner burn-in** (`warmup` loop), in parallel with the existing init-stability block. **Pass:** no **material** systematic drift (e.g. monotonic trend or fluctuations large relative to cross-method disagreement). Thresholds should flag when longer burn-in, larger $N$, or finer `mCount` is needed for welfare moments — not only when **mean `mNrm`** drifts.

**Role:** Any change to aggregation, `act_T`, `use_prestate`, dual-measure plumbing, **`Welfare.py`**, or TM treatment of level consumption should re-run **Gatekeeper** (including **B** once implemented) before touching multi-type steps.

---

### Harness — multi-type wiring **IN PROGRESS**

**Runner (notebook, same pattern as Gatekeeper):** `Code/HA-Models/Harness_Asymptotic_Equality.ipynb` — Run all; writes the §2.1 report and updates the Harness row in `history/asymptotic-equality-test-plan_revised_progress.md`.

**Report (required):** `history/asymptotic-equality-test-plan_revised_Harness_<YYYYMMDDTHHMM>.md` (UTC at file creation; §2.1)

**Target:** `test_asymptotic_equality_revised.py` (and any sibling drivers)

**Requirements**

1. **Horizon guard:** After every `switch_to_counterfactual_mode`, set `economy.act_T` and refresh `agent.get_economy_data(economy)` for all agents (implemented via `restore_intended_act_T_after_counterfactual_switch` in the revised script).
2. **argv guard:** Parameters imports before `AggFiscalModel` import (pattern in `verify_four_methods_agreement.py`); this script already sets argv before importing `AggFiscalModel` via `setup_economy` import order — keep that invariant if restructuring imports.
3. **Indexing contract:** Any loop over types uses `for i, agent in enumerate(economy.agents)` and pairs `baseline_tm_data[i]` with `agent` only. **`--phase harness`** (legacy `--phase 0`) asserts `len(baseline_tm_data) == len(economy.agents)`.
4. **Optional:** Emit **per-type** init-stability summary (same metrics as **Gatekeeper**) when `len(agents) > 1`, then a population-weighted aggregate drift score. **Implemented** in `test_asymptotic_equality_revised.py` as `--phase harness` (continued): calls `diagnose_tm_init_stability` per cohort after the harness path; use `--parametrization Smoke_Test` for a fast run.

**Pass criteria:** `python test_asymptotic_equality_revised.py --phase harness` succeeds on **`Reduced_Run`** (default MC total **5000** unless overridden); use **`Smoke_Test`** or **`--smoke-test`** on `AggFiscalMAIN_reduced.py` only for crash checks. CLI phases after **harness** assume restored `act_T` after counterfactual switch.

---

### Multi-type baseline — ergodic & aggregates

**Report (required):** `history/asymptotic-equality-test-plan_revised_Multi-type-baseline_<YYYYMMDDTHHMM>.md` (UTC at file creation; §2.1)

**Maps to:** original **Phase 1**, expanded.

**What**

- For **each** `i`, compare TM-derived moments (from type `i` ergodic) to MC cross-section for type `i` after TM-init + burn-in: **E[mNrm]**, **E[cNrm]**, **Var(log mNrm)**, **Var(log pLvl)** (or variances as in original plan), **employment share**, plus **type-i contribution** to aggregate C/Y.
- **Then** compare **economy** aggregate C/Y across methods (sum over types).

**Methods**

- **TM-P and TM-Q** per type (baseline only) where `run_experiment_tm` supports `base` — **`--phase baseline`** (legacy `--phase 1`) now builds both with `compute_baseline_tm_data(..., neutral_measure=False/True)` at the reference `mCount`, prints **economy TM-P vs TM-Q `AggCons_pc`**, and a **per-type TM-P vs TM-Q ergodic** table; the **TM-Q vs MC** table is unchanged in role.
- **MC:** `DualAggFiscalType` for P vs Q on the same path per type.

**Pass criteria**

- Per-type: same order of tolerance as single-type **Gatekeeper** unless documented (e.g. smallest cohort has higher MC noise).
- Economy aggregate: original plan target (e.g. &lt; 1–2% vs reference) once per-type weights are correct.

**Diagnostics if failing**

- First **split by i**: which education / β bin fails?
- Verify **AgentCount** and **data_EducShares** weighting for that bin.
- Check **PermGroFac** / SST helpers differ by education as expected.

---

### No-recession policies

**Report (required):** `history/asymptotic-equality-test-plan_revised_No-recession-policies_<YYYYMMDDTHHMM>.md` (UTC at file creation; §2.1)

**Maps to:** original **Phases 2–3** (Check, UI, TaxCut without recession).

- Keep **per-type** breakdown for at least one MC seed when debugging; publish economy-level multipliers for regression tracking.
- Expect **Check** to show P vs Q MC divergence (non-p-linear); TM comparison per original math notes.

---

### Recession suite

**Report (required):** `history/asymptotic-equality-test-plan_revised_Recession-suite_<YYYYMMDDTHHMM>.md` (UTC at file creation; §2.1)

**Maps to:** original **Phases 4–5**.

- **Per-type** TM solve and non-base TM propagation already follow `economy.agents` loops in `tm_methods`; MC uses `hit_with_recession_shock` per type. Re-validate **index alignment** for `baseline_tm_data` when switching shock types.
- Optional audit: `hit_with_recession_shock` / fixed shock histories vs ergodic intent (open item in history report).

---

### AD feedback loop

**Report (required):** `history/asymptotic-equality-test-plan_revised_AD-feedback-loop_<YYYYMMDDTHHMM>.md` (UTC at file creation; §2.1)

**Maps to:** original **Phase 6**.

- Highest sensitivity to small differences in aggregate C; confirm **same** aggregation formula for TM and MC inputs to AD update.
- If multi-type, confirm AD uses **economy-wide** sums, not accidental single-type feed.

---

### Convergence sweep

**Report (required):** `history/asymptotic-equality-test-plan_revised_Convergence-sweep_<YYYYMMDDTHHMM>.md` (UTC at file creation; §2.1)

**Maps to:** original **Phase 7**.

- Update tables to include, where available: **TM-P vs TM-Q** delta at fixed `mCount`, and **MC N** scaling with **minimum per-type** agent count constraint (e.g. no type below 2 000 agents for publication-quality rows).

---

## 3. Mapping plan names → `test_asymptotic_equality_revised.py --phase <name>`

The CLI uses **stable named phases** (preferred). Legacy **digits `0`–`7`** and tokens **`phase0`…`phase7`** remain aliases for the same ordered steps.

| Plan name | How to run | Markdown report (default pattern under `history/`) |
|-----------|------------|-----------------------------------------------------|
| **Gatekeeper** | **`Code/HA-Models/Gatekeeper_Asymptotic_Equality.ipynb`** (`nbconvert --execute`) — wraps `verify_four_methods_agreement.compare_four_methods` (**per-capita** AggCons + mean MU + init / MU drift); CLI-only alternative: `python verify_four_methods_agreement.py` from `FromPandemicCode` | `asymptotic-equality-test-plan_revised_Gatekeeper_<YYYYMMDDTHHMM>.md` |
| **Harness** | `--phase harness` — TM index alignment + `act_T` restore after `switch_to_counterfactual_mode`; optional per-cohort init drift | `asymptotic-equality-test-plan_revised_Harness_<YYYYMMDDTHHMM>.md` |
| **Multi-type baseline** | `--phase baseline` — economy `AggCons`, per-type TM-P/Q/MC tables | `asymptotic-equality-test-plan_revised_Multi-type-baseline_<YYYYMMDDTHHMM>.md` |
| **No-recession policies** | `--phase norec-check` (Check), `--phase norec-ui` (UI), `--phase norec-taxcut` (TaxCut) | `asymptotic-equality-test-plan_revised_No-recession-policies_<YYYYMMDDTHHMM>.md` |
| **Recession suite** | `--phase recession-baseline`, `--phase recession-policies` | `asymptotic-equality-test-plan_revised_Recession-suite_<YYYYMMDDTHHMM>.md` |
| **AD feedback loop** | `--phase ad-loop` (stub until TM/MC AD parity is wired) | `asymptotic-equality-test-plan_revised_AD-feedback-loop_<YYYYMMDDTHHMM>.md` |
| **Convergence sweep** | `--phase all` or a dedicated sweep mode (to be defined) | `asymptotic-equality-test-plan_revised_Convergence-sweep_<YYYYMMDDTHHMM>.md` |

**Aliases:** `check` → `norec-check`, `ui` → `norec-ui`, `taxcut` → `norec-taxcut`, `ad` → `ad-loop`, `multi-type-baseline` → `baseline`. **Result dict keys** in Python match the canonical names (`harness`, `baseline`, …).

`tm_scaleup_plan.md` uses its own “Phase 1–2” wording for production scaling; that is **unrelated** to these names.

Each row’s report follows **§2.1**: `<plan_stem>_<step_name>_<YYYYMMDDTHHMM>.md` under `history/` by default (UTC stamp at file creation, no seconds in the filename). **Live progress:** `history/asymptotic-equality-test-plan_revised_progress.md` (**§2.2**). Each completed report ends with **`## Step timing`** (**§2.1**).

---

## 4. Spec tracking (initial revision)

**Reduced vs full scale (2026-04):** `Reduced_Run` (N=5000) is the default **reduced** calibration for multi-type scripts and `AggFiscalMAIN_reduced.py`; it sits between **smoke** (100) and **Baseline** (10 000). The ladder below is unchanged—only the default floor for “reduced but not smoke” moved from 100 to 5000.

Bump minimum MC scale for **method agreement** rows (single-type evidence supports 20k; multi-type = ensure **each** type has enough mass):

| Scenario | MC note | TM note |
|----------|---------|---------|
| Baseline gate | N ≥ 20k single type; `warmup` 24; init drift check | mCount ≥ 100 for gate; finer for sweeps |
| 3 edu × 1 β | Split `AgentCountTotal` by shares; validate per-type moments | One TM per type; same mCount or document per-type mCount if ever varied |
| 21 types | Smallest cohort is limiting; increase `AgentCountTotal` or accept looser per-type stats | Watch grid edge cases for extreme β |

---

## 5. Related documents

- `Code/HA-Models/Gatekeeper_Asymptotic_Equality.ipynb` — **Gatekeeper** step runner (reports + progress tracker)  
- `plans/20260403-1253h_asymptotic-equality-test-plan.md` — full methodology, error protocol, original phase text  
- `plans/20260329-1853h_tm_scaleup_plan.md` — production scaling (1 → 3 → 21 types, horizons, AD)  
- `plans/20260403-1253h_phase0-1-revalidation-plan.md` — TM-P vs TM-Q focused script plan  
- `history/20260404-hafiscal-four-way-verification-and-tm-init-report.md` — baseline exercise outcomes  
- `history/20260331-mathematical-derivations-harmenberg.md` — neutral measure, §13 joint distribution / welfare vs $p$-linear aggregates  

---

## 6. One-line summary for AI agents

**Build validation in order:** Gatekeeper → Harness → Multi-type baseline → No-recession policies → Recession suite → AD feedback loop → Convergence sweep. **Gatekeeper** is run via **`Code/HA-Models/Gatekeeper_Asymptotic_Equality.ipynb`** (see §2 Gatekeeper subsection); it must cover $p$-linear aggregates and marginal-utility agreement plus init / early **MU** drift across MC-P, MC-Q, TM-P, TM-Q (§2). While running, maintain `history/asymptotic-equality-test-plan_revised_progress.md` (§2.2). Each step must write its Markdown report as `asymptotic-equality-test-plan_revised_<Step>_<YYYYMMDDTHHMM>.md` in `history/` by default (UTC at file creation, minute resolution, no seconds in the name; §2.1) and end the file with `## Step timing` (wall-clock duration). Always use separate TM and separate MC pools per `economy.agents[i]` with index-matched `baseline_tm_data[i]`.

---

## 7. Recommended next steps in testing

The §2 ladder is solid for **TM-vs-MC method agreement** but has gaps when measured against the full reproduction pipeline (`do_all.py` → Steps 1–5). See `plans/20260405-0849h_full-pipeline-component-map.md` for the complete component inventory.

### High priority (add before scaling up)

**Gap 1: Estimation pipeline (Steps 1–3) is completely untested.**
The calibrated discount factors are the foundation of everything. If HARK changes break the estimation, correct simulation code produces wrong paper results. The test plan assumes Step 2 output is correct. At minimum, add a smoke test: run `EstimAggFiscalMAIN.py` with very loose tolerance and 1 Nelder-Mead iteration to verify the estimation loop doesn't crash with current HARK, and that the target-computation functions (`calc_lorenz_pts`, `calc_mpc_by_ed_simple`, etc.) return finite values of the expected shape.

**Gap 2: Income shock construction is untested.**
`IncShkDstn` is built manually (`construct=False`) with per-state unemployed distributions from the SST module (`build_unemployed_inc_shk_dstn`). A wrong distribution affects both MC and TM identically, so method-agreement tests won't catch it. Add a unit test that, for each education type and shock type, verifies: `E[PermShk]=1` for employed states, `E[TranShk]` matches the calibrated value, unemployed distributions match the SST flags (`perm_shocks_during_unemployment`, `tran_shocks_during_unemployment`), and the number of shock atoms per state is consistent.

**Gap 3: Welfare.py is untested.**
The paper's welfare results are a primary output. `Welfare_Results()` takes `cLvl_all_splurge` (agent-level consumption, not AggCons), computes CRRA felicity per agent per period, averages over recession durations with `recession_prob_array` weights, and produces welfare-impact tables. None of this is exercised by the current plan. The plan mentions "level distribution & welfare" as a required extension of the Gatekeeper (§2, item B), but that focuses on marginal-utility *agreement across methods*, not on the actual `Welfare.py` calculations. Add an integration test: run a minimal `Simulate` + `Welfare_Results` pipeline (Reduced_Run, baseline + one policy) and verify welfare is finite, has the correct sign, and the felicity function matches CRRA.

### Medium priority (add for full confidence)

**Gap 4: Output_Results.py is untested.**
Multiplier and IRF computations (`get_npv_multiplier`, `get_simulation_percent_diff`) are simple arithmetic but depend on the pickle result-dict structure. Feed known synthetic results through these functions and verify output.

**Gap 5: Recession duration averaging is unverified.**
`Simulate.py` runs multiple recession durations and averages with `recession_prob_array` weights. Verify the array sums to 1 and that a weighted average of known constant results recovers the constant.

**Gap 6: Shock-type switching is only partially tested.**
The Harness step tests that `act_T` is restored after `switch_to_counterfactual_mode`, but not that `MrkvArray`, `IncShkDstn`, and shock histories are correctly transformed per shock type. Each shock type (UI, TaxCut, Check) modifies different parameters in different ways. After each switch, verify MrkvArray dimensions, IncShkDstn structure, and that the per-state income levels match the policy specification.

**Gap 7: Parameter consistency across parametrizations is not checked.**
The plan uses `Reduced_Run` and `Smoke_Test` for speed, but doesn't verify these produce the same qualitative structure as `Baseline`. Key structural parameters (`num_base_MrkvStates`, `T_age`, `PermGroFac` structure, number of education types) should be identical across parametrizations; only scale parameters (`AgentCount`, `act_T`, `mCount`) should differ. A simple assertion test would catch accidental structural divergence.
