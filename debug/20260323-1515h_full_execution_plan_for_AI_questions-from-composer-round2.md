# Questions on the TM-vs-MC full execution plan — round 2 (from Composer)

**Date:** 2026-03-23  
**Prior round:** [`20260323-1508h_full_execution_plan_for_AI_questions-from-composer.md`](./20260323-1508h_full_execution_plan_for_AI_questions-from-composer.md) (addressed in [`20260323-1511h_full_execution_plan_for_AI_answers-from-ClaudeOpus4p6.md`](./20260323-1511h_full_execution_plan_for_AI_answers-from-ClaudeOpus4p6.md))  
**Current plan under review:** [`20260323-1512h_full_execution_plan_for_AI_v2.md`](./20260323-1512h_full_execution_plan_for_AI_v2.md)  
**Context:** Follow-up clarifications after v2 + answers; same audience as round 1 (implementer human or AI).

---

## Phase 3 regression checklist vs Check **consumption**

Phase 2 states the primary Check pass as **period-0 AggCons treatment-effect relative error &lt; 5%**, and the substantive discrepancy is **consumption NPV** (income already ~1%).

In **v2 §Regression checklist** (and in the answers doc), the bullet for **`validate_tm_check.py`** only specifies **AggIncome[0] TE rel err &lt; 1%**, which mirrors UI/TaxCut income checks but **does not restate** the Check-specific **AggCons[0]** criterion.

- Should the checklist **explicitly add** something like: **Check — AggCons[0] TE rel err &lt; 5%** (and keep AggIncome[0] &lt; 1% as a guard), so Phase 3 cannot “pass” while the original Check **consumption** issue regresses?

---

## **`validate_tm_check.py` education group vs GLP-1 college**

`validate_tm_check.py` uses **`init_highschool`** and **`DiscFacDstns[1]`**, while much of the plan refers to **GLP-1 / single college** for diagnostics and `AggFiscalMAIN_reduced.py --glp1`.

- Is **high school** intentional as the **authoritative** Check validation type?
- Should Phase 2 eventually add a **college** Check path (flags or a separate script) so Check validation **aligns** with GLP-1?
- If both matter, which script is the **source of truth** for declaring “Phase 2 closed”?

---

## Period-0 **`rel_err`** when **`|MC_TE[0]|`** is tiny

v2 defines **`rel_err = |TM_TE[0] - MC_TE[0]| / |MC_TE[0]|`** for pass/fail.

- For some experiments or seeds, **MC_TE[0]** could be very small or unstable; the ratio can **blow up** or be ill-defined.
- Is there a documented **denominator floor** (e.g. divide by **`max(|MC_TE[0]|, ε)`**), a fallback to **absolute** error below a threshold, or a rule to **aggregate across seeds** before forming the ratio?

---

## Phase 2 **exit / gating** if NPV stays bad after period-0 is fixed

Answers already say: fix **period-0 AggCons** first; if **NPV** is still off, investigate **per-period TE profiles**.

- For **gating** (when Phase 2 is allowed to be “complete” and Phase 3 may start): is **period-0 AggCons alone** sufficient?
- Or should there be a **secondary** requirement on **NPV consumption TE** (even a loose bound, or “document residual gap”) before Phase 3?

---

## References sanity (no action required if confirmed)

- **`test_pLvl_factorization.py`** is cited in v2 for the **~0.06%** Cov\((c,\text{pLvl})\) figure — confirm it remains the **canonical** reference for that claim as the codebase evolves.

---

*End of round-2 questions document.*
