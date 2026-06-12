# Questions on the TM-vs-MC full execution plan (from Composer)

**Date:** 2026-03-23  
**Source document:** [`20260323-1504h_full_execution_plan_for_AI.md`](./20260323-1504h_full_execution_plan_for_AI.md)  
**Context:** These are clarifications an implementer (human or AI) would need so the plan is unambiguous and testable.

---

## Phase 1 vs observed validation

- **UI “consumption TE &lt; 4%”:** A run of `validate_tm_ui.py --agents 200000 --seeds 3 --mcount 100` reported **AggCons treatment effect max-rel vs TM ≈ 60.7%**, while period-0 **levels** were ~0.07% apart. Should the plan spell out **which scalar** must be &lt;4% (e.g. only **AggCons[0]**, or **full-path max rel on levels**, not on the **difference series**)? Should Phase 1 “pass” be updated or tied to a **commit after** further fixes?

---

## Phase 2 (Check)

- **Units:** “TM NPV consumption TE = **1.28** vs MC = **0.91**” — are these **NPV multipliers (C/Y)**, **ΔC/Y**, or something else? How exactly is the **29%** gap computed (e.g. relative to TM, MC, or baseline)?
- **“Independent of initialization”:** Which runs establish that (script names / flags)? Same `validate_tm_check.py` with two init modes, or custom diagnostics?
- **Success metric:** Target “**&lt;5% consumption TE rel error**” — clarify: **max over horizons** on the **effect path**, **period 0 only**, or an **NPV scalar**?

---

## Phase 3 (per-cohort TM propagation)

- **Half-step vs raw `LivPrb`:** The plan keeps the **standard ergodic** for **half-step TM** while per-cohort uses a **different** TM (**raw `LivPrb`**). If per-cohort mode **drops the half-step**, how do you avoid **reopening** experiment-boundary / timing issues the half-step addressed? What is the **regression checklist** (which `validate_*` / `test_*` must pass)?
- **`E[pLvl|age_k]`:** Using **`E[pLvl_init] × G^k`** ignores **employment/Mrkv** and shock-driven **pLvl** dynamics. Is that intentional **only for aggregation**, or should the design allow **MC-estimated** conditional means per `(age, j)`?
- **Interaction with Check buckets:** Phase 2 may change bucket logic; Phase 3 adds cohorts. Should **Check** be fixed **before** cohort propagation, or should APIs be designed so both changes can land independently?

---

## Phase 4

- **Priority:** Confirm nothing in Phases 2–3 should **pre-design** hooks (e.g. abstract simulation backend) or that Phase 4 remains **out of scope** until Phases 2–3 are closed.

---

## Environment / repo hygiene

- **HARK path:** The plan hard-codes **`/Volumes/Sync/GitHub/econ-ark/HARK`** and symlink expectations. Is the rule “editable HARK from branch `main_improve-tm-vs-mc-sim-infra-and-examples`” regardless of path, or is this **machine-specific** and should be generalized for other agents/CI?
- **Placeholder paths:** `cd /path/to/HAFiscal-Latest` appears in the source plan — should it be standardized (e.g. repo root or `$HAFISCAL_ROOT`)?

---

## Script inventory

- **`test_first_period_trace.py`** exists in `FromPandemicCode/` but the plan does not say **when** to run it relative to Phase 2 vs 3. Should it be part of **Phase 2** Check debugging, or reserved for after cohort work?

---

*End of questions document.*
