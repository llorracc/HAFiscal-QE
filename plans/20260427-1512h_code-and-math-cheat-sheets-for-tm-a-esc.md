# Sub-plan: paired code-cheat-sheet + math-cheat-sheet for the TM-a ESC kernel build

**Date:** 2026-04-27
**Parent plan:** `plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md` (Phase 0.1)
**Companion math reference:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/why_TM_a_kernel.md`
**Predecessor plans / docs in this lineage:** `plans/20260418-1136h_splurge-in-budget-a-indexed-TM.md`; `BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md`; `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md`.

## 1. Purpose

Replace Phase 0.1 ("read CDC `_a` kernel + write cheat-sheet") with a more rigorous version that produces TWO paired reference documents and a corresponding pass over the math docs:

- **Code-cheat-sheet** — for each operation in the CDC `_a` kernel functions (anchors 33.4-33.9, `tm_methods.py:2715-3268`), specify exact lines, what changes for ESC, and a labeled-equation cross-reference to the math derivation that justifies it.
- **Math-cheat-sheet** — the reverse index. For each labeled equation in our math docs that has a TM-a code counterpart, list the code site(s) that implement it.
- **Math-doc updates** — for any code operation that lacks an existing labeled-equation justification, derive the math, add the equation to the appropriate doc with a label, then cross-reference. As a side product, every equation in the math docs that has a code counterpart gets a label.

The result is durable, audit-quality documentation that:

1. Serves as the specification for Phase 0.2-0.5 implementation (working from the code-cheat-sheet's per-function entries as a checklist).
2. Surfaces any "code without math" gaps that would otherwise hide as unaudited assumptions.
3. Survives Phase 0 as the canonical CDC↔ESC kernel reference.

This sub-plan also formalizes a **pause-and-derive discipline:** every time we encounter a code operation we cannot find an explicit math justification for, we stop and derive it before continuing. No "the code does X, presumably for some good reason" entries — every entry must point to a labeled derivation.

## 2. Deliverables

### 2.1 Code-cheat-sheet

**File:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/code_cheatsheet_tm_a_kernel.md`

**Structure (per function in 33.4-33.9):**

```markdown
## 33.X — `function_name`  (lines NNNN-MMMM of tm_methods.py)

**Purpose:** one-paragraph description.

**Key state variables and their interpretation under each reading:**
- `var1`: under CDC = ...; under ESC = ...
- ...

**Operation-by-operation walkthrough:**

| Lines | Operation | Math justification | ESC counterpart |
|---|---|---|---|
| NNNN-NNN+k | (e.g.) compute m_next from a + ξ shock | `(eq:m-from-a)` of `models_CDC_and_ESC.md §X` | identical (interpretation-shared) |
| NNN+k+1 | (e.g.) compute c_actual = (1-ς)·c*(m) + ς·ξ | `(eq:budget-CDC)` of `models_CDC_and_ESC.md §4.2` | replaced by `(eq:budget-ESC)`: `c_actual = c*(m)` |
| ... | ... | ... | ... |

**ESC port summary for this function:** which lines change, which are interpretation-shared, what the new code looks like.
```

Estimated size: ~50-80 lines per function × 6 functions = ~300-500 lines total.

### 2.2 Math-cheat-sheet

**File:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/math_cheatsheet_tm_a_kernel.md`

**Structure (per labeled equation):**

```markdown
## (eq:budget-CDC) — household-bargain asset update

**Statement:** $a_t = m_t - (1-\varsigma)\,c^{*}(m_t) - \varsigma\,y_t$

**Source doc:** `models_CDC_and_ESC.md §4.2`

**Code sites implementing this:**
- `tm_methods.py:2849-2852` — inside `_build_period_tm_a` (CDC asset update in inner loop)
- `EstimAggFiscalMAIN.py:117` — Step-2 wealth aggregator (BUG-034 fix site, post-fix uses aLvl directly)
- `AggFiscalModel.py:1110-1113` — `_cdc_asset_rule` helper inside `AggFiscalType.get_poststates`

**ESC counterpart:** `(eq:budget-ESC)` — drops `(1-ς)·` factor and `ς·y_t` term

**Notes:** under CDC interpretation, `a` is household-bargain end-of-period asset; under ESC, `(eq:budget-ESC)` defines the optimizer's per-Optimizer asset only and household wealth is computed via separate `(eq:wealth-ESC)`.
```

Estimated size: ~15-25 entries × ~20 lines each = ~300-500 lines.

### 2.3 Math-doc updates

For every code operation discovered to lack an explicit math justification, derive it and update the appropriate math doc. Likely candidates for updates (subject to discovery during the work):

- **`models_CDC_and_ESC.md`** — likely needs additional labeled equations:
  - `(eq:m-from-a)` for `m_t = (R/(Γψ))·a_{t-1} + y_t` if not already labeled
  - Aggregator equations: `(eq:KY-CDC)`, `(eq:KY-ESC)`, `(eq:lorenz)`, etc.
  - Interpretation-of-`a` equations (when does `a` mean `a_tot`? when `a_opt`?)

- **`why_TM_a_kernel.md`** (just created): may need additional labeled lemmas or aggregator-formula labels.

- **`why_results_match_at_target.md`**: may need labels on the χFunc-at-target identity equations.

- **Potentially new doc:** if we discover the kernel implements a non-trivial operation (e.g., the lottery interpolation, the Harmenberg neutral-measure transform) whose math derivation is scattered or absent, we might add a small standalone math doc for it.

## 3. Process — for each CDC `_a` function

```
For each function F in {33.4, 33.5, 33.6, 33.7, 33.8, 33.9}:
    1. Read F end-to-end (~20-30 min)
    2. Identify each "operation of interest" in F
       (skip pure boilerplate: variable unpacking, array allocation, etc.)
    3. For each operation O:
        a. Identify which math derivation justifies O
        b. Search math docs for a labeled equation matching O
        c. If found:
            - cross-reference in code-cheat-sheet entry for F
            - add entry to math-cheat-sheet for that equation, listing F as a code site
        d. If NOT found:
            STOP.
            - Derive the math
            - Decide which math doc the derivation belongs in
            - Add labeled equation to that doc (with derivation, in correct section)
            - Then proceed: cross-reference in code-cheat-sheet, add to math-cheat-sheet
    4. Identify ESC counterpart of each operation O:
        - if there's an existing ESC labeled equation, cross-reference it
        - else derive and label
    5. Write the per-function entry in the code-cheat-sheet
    6. Commit incremental progress (one commit per function preferred)
```

## 4. Equation-naming convention

Use existing labels where they exist (`(CDC-1)`, `(ESC-1)`, `(eq:budget-CDC)`, `(eq:budget-ESC)`, `(eq:m-evolve)`, `(eq:agg)`).

For new equations, follow the convention `(eq:<topic>[-<variant>])` with variant in {CDC, ESC, generic}. Examples:

| Label | Statement |
|---|---|
| `(eq:m-from-a)` | $m_t = \frac{R}{\Gamma\psi_t}\,a_{t-1} + y_t$ |
| `(eq:budget-CDC)` | $a^{\text{CDC}}_t = m_t - (1-\varsigma)\,c^{*}(m_t) - \varsigma\,y_t$ |
| `(eq:budget-ESC)` | $a^{\text{opt,ESC}}_t = m^{\text{opt}}_t - c^{*}(m^{\text{opt}}_t)$ |
| `(eq:wealth-CDC)` | household wealth = $a^{\text{CDC}}$ |
| `(eq:wealth-ESC)` | household wealth = $(1-\varsigma)\,a^{\text{opt}}$ |
| `(eq:KY-aggregator)` | $K/Y = \mathbb{E}[\text{wealth}] / \mathbb{E}[y]$ |
| `(eq:lorenz-shares)` | Lorenz percentile formula |
| `(eq:ergodic-defn)` | $p^{*} = T \cdot p^{*}$ where $T$ is the column-stochastic kernel |
| `(eq:lottery-update)` | $w_{\text{lo}} = (a' - a_{\text{lo}})/(a_{\text{hi}} - a_{\text{lo}}),\; w_{\text{hi}} = 1 - w_{\text{lo}}$ |
| `(eq:death-rebirth)` | newborn redistribution at death rate $1-L$ |
| `(eq:ad-channel-A)` | $\xi_{\text{eff}} = \text{ad\_tran\_shk\_scale} \cdot \xi$ for AD channel A |
| `(eq:taxcut-emp-fac)` | employed-only AD scaling for tax-cut scenarios |
| `(eq:tranShk-addition)` | additive transitory shock for stimulus check |

These are *examples*; the actual list emerges from the audit. The principle: every operation that has math content gets a stable label, so cross-references are readable and durable.

## 5. Plan steps

| Step | What | Cost |
|---|---|---|
| 5.1 | Inventory existing labeled equations across `models_CDC_and_ESC.md`, `why_TM_a_kernel.md`, `why_results_match_at_target.md`, `welfare_code_and_paper_text_on_interpretation.md` | ~1 hr |
| 5.2 | Scan `tm_methods.py:2715-3268` for "operations of interest" — produce a flat list of distinct math operations to be cross-referenced | ~30 min |
| 5.3 | For each operation: lookup math justification; flag gaps | ~1 hr |
| 5.4 | **Pause-and-derive:** for each gap, derive the math and update the appropriate doc with labeled equation | ~1-3 hr (variable; depends on gap count) |
| 5.5 | Write code-cheat-sheet (per-function entries with cross-references, function 33.4 → 33.9 in order) | ~2 hr |
| 5.6 | Write math-cheat-sheet (reverse index over labeled equations) | ~1 hr |
| 5.7 | Final consistency pass: every code operation has a math reference; every math equation with a code counterpart has a code reference | ~30 min |
| 5.8 | Commit + push (one commit per function during 5.5; final wrap-up commit at 5.7) | as we go |

**Total estimated cost:** ~6-9 hours, dominated by step 5.4 (derivation of any missing math). The high-end estimate assumes ~3-4 non-trivial gaps requiring derivation.

## 6. Sign-off criteria

The sub-plan is complete when ALL of the following hold:

1. Every meaningful operation in `tm_methods.py:2715-3268` (functions 33.4-33.9) has a labeled-equation cross-reference in the code-cheat-sheet.
2. Every labeled equation in the math docs that has a code counterpart appears in the math-cheat-sheet with code references.
3. No code operation in the cheat-sheet entries has a "TBD" or "no math reference" entry — every operation has been audited and either matched to existing math or backed by a newly-derived labeled equation.
4. The math docs contain no implicit derivations that justify code: everything that touches `tm_methods.py:2715-3268` is explicitly labeled.

## 7. Post-completion impact

After this sub-plan executes, Phase 0.2-0.5 of the parent plan (the actual ESC kernel build) has a concrete specification: each function in 33.4-33.9 has a code-cheat-sheet entry with explicit "for ESC, replace lines NNN with..." instructions, all backed by labeled math equations. Implementation becomes mechanical translation, with greatly reduced surprise-bug risk.

The cheat-sheets and the augmented math docs also become the **debugging reference** for Phase 1 (validation) — when MC and TM disagree, the cheat-sheets tell us which operation to inspect first, and the math doc tells us what the operation should be doing.

## 8. Open design choices

1. **One file per cheat-sheet, or two paired files?** Recommend two (separation of forward and reverse indices reads more cleanly). Both live in `BUGS_private/HAFiscal_splurge_budget_inconsistency/`.

2. **Equation labels: `(eq:foo)` vs `(CDC-1)`-style numeric?** Recommend `(eq:foo)` because the code grows; numeric labels go stale fast. Existing `(CDC-1)`, `(ESC-1)` are preserved as aliases.

3. **Where do new math derivations live?** Default to the existing doc whose subject best matches. New `(eq:budget-*)` additions go in `models_CDC_and_ESC.md`. New aggregator-formula derivations go in `why_TM_a_kernel.md`. Topic-orthogonal derivations might warrant a new short doc; decide case-by-case.

## 9. Scope NOT included

- This sub-plan does NOT modify `tm_methods.py` itself. That happens in Phase 0.2-0.5 of the parent plan.
- This sub-plan does NOT touch the m-indexed TM code (which is broken under any splurge-in-budget reading per BUG-033 — not part of the CDC↔ESC active surface).
- This sub-plan does NOT cover MC code (`Simulate.py`, `AggFiscalModel.py::AggFiscalType.get_poststates`, etc.). Those are a separate (smaller) audit if needed; the priority is the TM kernel that Phase 0 builds the ESC sibling of.
