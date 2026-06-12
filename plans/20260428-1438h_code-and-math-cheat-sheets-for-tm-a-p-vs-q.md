# Sub-plan: paired code-cheat-sheet + math-cheat-sheet for TM-a P/Q (Harmenberg neutral measure)

**Date:** 2026-04-28
**Parent investigation:** TM-Q downward bias discovered today (~0.12% HS, ~0.4% CO) — see `conclusions_private/2026-04-28_mc-confirms-tm-p-is-accurate-tm-q-has-unexpected-bias.md`.
**Companion math reference:** `history/20260331-mathematical-derivations-harmenberg.md` (994 lines, ~30 sections, multiple existing labeled equations).
**Predecessor cheat-sheet sub-plans (template lineage):**
- `plans/20260427-1512h_code-and-math-cheat-sheets-for-tm-a-esc.md` — produced `code_cheatsheet_tm_a_kernel.md` + `math_cheatsheet_tm_a_kernel.md` (the model for this plan).
- `plans/20260427-1656h_code-and-math-cheat-sheets-for-phase-1-convergence.md` — produced the Phase 1 convergence cheat-sheets.

## 1. Purpose

Apply the **same paired-cheat-sheet methodology** that was used for the CDC/ESC TM-a kernel comparison, but now for the **P-measure vs Q-measure (Harmenberg neutral)** variants of the TM-a kernel. The motivation is the empirical TM-Q downward bias finding (today): the analytical claim from `history/20260331-mathematical-derivations-harmenberg.md` §14.5 ("TM-Q exact for p-linear, TM-P biased upward by Cov(p,c)") is contradicted by direct MC verification, which shows TM-P matches MC almost exactly while TM-Q is biased downward. The bias scales monotonically with β (DO 0.025% → HS 0.114% → CO 0.398%) and is grid-resolution-invariant. Source unknown.

The cheat-sheet exercise will:

1. **Inventory every equation** in `history/20260331-mathematical-derivations-harmenberg.md` and any related companion docs (BST `ApndxHarKmenberg`, `Harmenberg-Four-Way-Comparison.ipynb`, archived harmenberg memos in `history/archive/`).

2. **Map each equation to all code instances** in `tm_methods.py` (and downstream call sites in `Simulate.py`, `AggFiscalModel.py`, etc.) where it is implemented under both `neutral_measure=False` (P) and `neutral_measure=True` (Q).

3. **Identify gaps** — code operations under either P or Q that lack an explicit math justification; equations in the math docs that have no code counterpart.

4. **Derive missing math** — for any code operation lacking a justification, derive the underlying math, give it a label, add it to the appropriate doc, and **test mathematical validity** (with both an analytical proof attempt and an empirical numerical check).

5. **Use the audit to locate the TM-Q bias** — the gap inventory in step 3 is the most likely place to find the source of the ~0.12-0.4% TM-Q downward bias. Candidates include: the level-scaling step (`scale = N_agent · E_pLvl · pLvl_factor` at line 3747 — does Q need a different `E_pLvl`?), the `pLvl_factor` recurrence (line 3489 — is the Q-version of the unemployment rate the right input?), or the construction of `π_Q(a, j)` in the ergodic step.

This sub-plan also formalizes the **pause-and-derive discipline** from the prior cheat-sheet plan: every time we encounter a code operation we cannot find an explicit math justification for, we stop, derive it, and only then continue.

## 2. Deliverables

### 2.1 Code-cheat-sheet

**File:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/code_cheatsheet_tm_a_p_vs_q.md` (new)

**Scope:** every function in `tm_methods.py` that takes a `neutral_measure` parameter or is involved in P↔Q dispatching. Tentative function list (verify during step 3 of the plan):

- `_to_neutral_measure` (line 406) — Q reweighting of IncShkDstn pmv
- `build_tm_agg_fiscal_a` (line 2963) — main TM constructor, passes neutral_measure through
- `_build_period_tm_a` (lines around 2715) — single-period TM builder
- `compute_baseline_tm_data` (line 2169) — baseline ergodic + E_pLvl computation
- `compute_period_aggregates_tm_a` (line 3187) — within-period aggregation
- `compute_type_aggregates_tm_a` (lines around 2987-3098) — per-type ergodic aggregation
- `propagate_experiment_tm_a` (line 3401) — experiment-period propagation, uses pLvl_factor
- `run_experiment_tm_nonbase` (line 2256) — wrapper that dispatches to a-indexed
- `run_ad_tm` (line 2455) — AD-amplification wrapper
- (`_build_period_tm`, `compute_period_aggregates_tm`, etc. — m-indexed analogs; include if they share the Q machinery, otherwise out of scope)

**Structure (per function):**

```markdown
## NN.X — `function_name`  (lines NNNN-MMMM of tm_methods.py)

**Purpose:** one-paragraph description.

**Key state variables and their interpretation under each measure:**
- `var1`: under P = ...; under Q = ...
- ...

**Operation-by-operation walkthrough:**

| Lines | Operation | Math justification | Q counterpart |
|---|---|---|---|
| NNNN-NNN+k | (e.g.) compute m_next from a + ξ shock | `(eq:m-from-a)` of `mathematical-derivations-harmenberg.md §X` | identical (Q-shared) |
| NNN+k+1 | (e.g.) Q-reweight pmv: q_s = p_s · ψ_s / Σ(p·ψ) | `(Q-reweight-emp)` of `…harmenberg.md §2.1` | only applied when `neutral_measure=True` |
| NNN+k+2 | level scale: `scale = N · E_pLvl · pLvl_factor` | `(level-scale-P)` ← labeled in this exercise; needs Q analog | **GAP — needs derivation**; current code uses same `E_pLvl` under both, but TM-Q empirically biased ~0.1-0.4% |
| ... | ... | ... | ... |

**Q port summary for this function:** which lines change, which are P-Q-shared, and any newly-discovered gap.
```

Estimated size: ~50-80 lines per function × ~10 functions = ~500-800 lines total.

### 2.2 Math-cheat-sheet

**File:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/math_cheatsheet_tm_a_p_vs_q.md` (new)

**Structure (per labeled equation):**

```markdown
## (Q-reweight-emp) — Q-measure income-shock reweighting (employed states)

**Statement:** $q_s = p_s \cdot \psi_s \,/\, \sum_{s'} p_{s'} \cdot \psi_{s'}$

**Source doc:** `history/20260331-mathematical-derivations-harmenberg.md §2.1`

**Code sites implementing this:**
- `tm_methods.py:425-428` — `_to_neutral_measure`, the canonical implementation.
- `tm_methods.py:629` — `_build_period_tm` calls `_to_neutral_measure` on IncShkDstn list.
- `tm_methods.py:1134` — `compute_type_aggregates_tm` calls `_to_neutral_measure` for Q-aware aggregation.
- ... (all sites that invoke `_to_neutral_measure` directly)

**P counterpart:** P-measure = identity (no reweighting); the same IncShkDstn atoms are used as-is.

**Notes:** pmv normalized to sum to 1 explicitly (line 426-428) because discretization may give Σ(p·ψ) ≠ 1 even though mean-one shocks have E_P[ψ]=1.
```

**Inventory targets** (all to be itemized with code-site lists):

- `(neutral-identity)` — `E_P[p · c(m, z)] = E_Q[c(m, z)] · E_P[p]` (§1)
- `(Q-reweight-emp)`, `(Q-reweight-unemp)` — §2.1 / §2.2
- `(Q-newborn)` — §4
- `(P-state-frac)`, `(Q-state-frac)`, `(Q-P-frac-equal)` — §5
- `(pLvl-recurrence)`, `(pLvl-factor-init)` — §6
- Aggregation identities — §7
- `(splurge-Q)` — §8
- `(income-Q)` — §9
- `(adapted-init)` — §10
- Error decomposition — §11
- Covariance kernel γ(a) — §14.1
- `(TM-P-bias-formula)` — §14.5: `TM-P − truth = −N · Cov_P(p, c)`
- MC-Q aggregation — §15

Estimated size: ~20-30 entries × ~20 lines each = ~400-600 lines.

### 2.3 Math-doc updates

For every code operation discovered to lack an explicit math justification, derive it and update the appropriate math doc. Likely candidates (subject to discovery during the work):

- **`history/20260331-mathematical-derivations-harmenberg.md`** — likely needs additional labeled equations:
  - `(level-scale-P)` and `(level-scale-Q)` — the `scale = N · E_pLvl · pLvl_factor` formula and what (if anything) should differ under Q.
  - `(pLvl-factor-recurrence-P)` and `(pLvl-factor-recurrence-Q)` — explicit equations for the per-period growth of pLvl_factor under each measure.
  - **Most likely GAP:** an equation specifying whether `E_pLvl` (the steady-state mean of pLvl) is the same value under P and Q in HAFiscal's calibration. If they should differ but the code uses the same value, that's the bias source.
  - `(splurge-aggregation-Q)` — formal derivation of how splurge-on-income (`ς·y`) is aggregated under Q. The §8 sketch may not cover the splurge fully.

- **Specific bias-investigation derivation:** define `(eq:tm-q-bias-decomposition)` that decomposes the empirical TM-Q − MC gap into named components (Q-reweighting term, level-scaling term, pLvl-factor term, etc.) so we can localize the source.

- **`Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb` §8j** referenced in the docstring — extract any equations there into the main math doc with labels.

### 2.4 Investigation report

**File:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/tm_q_bias_investigation.md` (new)

After the cheat-sheet pass, produce a short report (~50-100 lines) on what the audit revealed about the TM-Q downward bias source. The report cites the specific equation(s) where the implementation diverges from the math, the empirical magnitude of the divergence per cohort, and a proposed fix.

## 3. Plan steps

Modeled on the prior cheat-sheet sub-plan's 7-step structure (§5.1-5.7 in `20260427-1512h_…tm-a-esc.md`).

### Step 3.1 — Equation-label inventory

Read `history/20260331-mathematical-derivations-harmenberg.md` end-to-end. List every existing labeled equation (those with `\tag{...}` or section anchors) in a working scratch file. Note any equations that are present but unlabeled (these get labels in Step 3.4).

Companion docs to scan: `history/archive/20260401-harmenberg-appendix-and-revision-plan.md`, `history/archive/20260402-reduced-run-harmenberg-output-type-map.md`, `history/archive/20260402-harmenberg-reduced-reproduce-acceleration-plan.md`, `Harmenberg-Four-Way-Comparison.ipynb` §8j (markdown text only — extract any equations).

**Deliverable:** scratch list of ~30-50 equations with current label (or "unlabeled") and source doc/section.

**Cost:** ~1 hr.

### Step 3.2 — Scan tm_methods.py for P↔Q operations

For each function in §2.1's list, walk through the lines and identify every operation that depends on `neutral_measure` either directly (e.g., `if neutral_measure:`) or via a function it calls. Record line ranges + brief operation descriptions.

**Deliverable:** scratch table of operations × functions, ~80-150 entries.

**Cost:** ~2 hr.

### Step 3.3 — Lookup math justification, flag gaps

For each operation in Step 3.2's table, find the corresponding equation in Step 3.1's inventory. Mark gaps where no equation exists.

**Deliverable:** annotated operation table; gap list.

**Cost:** ~2 hr.

### Step 3.4 — Derive missing math, test validity, update docs

For each gap, derive the underlying math:
1. State the operation in math terms.
2. Provide an analytical justification (BST identity, change-of-variable, etc.).
3. **Test mathematical validity:**
   - Sanity check: does the derivation reduce to a known identity in the limit?
   - Numerical check: implement the derived formula directly in a small test script (numpy on a specific case) and compare to what the code produces. If they agree to numerical precision, the derivation is consistent with the code; if they disagree, we have either found a bug or made a derivation error.
4. Add the equation with a label to the appropriate math doc.
5. Update Step 3.3's table with the new label.

Also assign labels to existing-but-unlabeled equations in Step 3.1.

**Deliverable:** updated math docs with new labels and any newly-derived equations.

**Cost:** ~3-5 hr (depends on number of gaps and complexity).

### Step 3.5 — Write code-cheat-sheet

Following the Step 3.3 annotated table, write `code_cheatsheet_tm_a_p_vs_q.md` per the §2.1 structure.

**Deliverable:** the code-cheat-sheet file.

**Cost:** ~2-3 hr.

### Step 3.6 — Write math-cheat-sheet

Following the Step 3.1 inventory + Step 3.4 additions, write `math_cheatsheet_tm_a_p_vs_q.md` per the §2.2 structure. Each entry lists all code sites implementing the equation.

**Deliverable:** the math-cheat-sheet file.

**Cost:** ~2-3 hr.

### Step 3.7 — Final consistency pass + bias investigation report

Final pass over both cheat-sheets to ensure:
- Every code op has a math entry; every math entry has a code list.
- The line numbers in code-cheat-sheet match current `tm_methods.py`.
- The Q-counterpart column is filled in for every entry.

Then write `tm_q_bias_investigation.md` (§2.4): synthesize what the cheat-sheet exercise revealed about the TM-Q bias source. Propose a fix or, if no fix is identified, list the candidate hypotheses with the empirical evidence supporting/refuting each.

**Deliverable:** the consistency-pass commit + investigation report.

**Cost:** ~1-2 hr.

## 4. Total cost estimate

~14-20 hours focused work, no compute. Roughly equivalent to the prior cheat-sheet sub-plan; this one has more equations to enumerate (~30-50 vs CDC/ESC's ~20) but the function list is shorter (~10 vs ~6 + their interpretation-shared variants).

## 5. Pause-and-derive discipline

Same as the prior cheat-sheet plan. Every "code does X without obvious math justification" entry must be either:
- Pointed to an existing labeled equation, or
- Replaced by a fresh derivation that is added to the math doc with a new label

with the additional constraint introduced in this plan: **test the new derivation numerically before accepting it**. The TM-Q bias likely lives precisely in a place where the derivation is "obvious enough that nobody checked it", so the numerical-verification step is essential.

## 6. Success criteria

1. Every line of `tm_methods.py` that depends on `neutral_measure` has a labeled-equation reference in the code-cheat-sheet.
2. Every labeled equation in the math-cheat-sheet has at least one code-site reference.
3. The bias investigation report identifies the source of the TM-Q downward bias, OR enumerates the candidate sources with the evidence for/against each.
4. Mathematical-validity tests for any newly-derived equations pass numerically against direct numpy implementations.

## 7. Out of scope

- **Fixing the TM-Q bias.** The cheat-sheet exercise diagnoses; a separate plan implements any code change.
- **Welfare-by-percentile** (sub-task 2.4). The Harmenberg machinery for p-nonlinear aggregates is a different (richer) topic — handle in a separate cheat-sheet pass when that work resumes.
- **MC↔TM convergence under shocks.** That's the still-unstarted sub-plan #1 from the Phase 2 ordering. The current cheat-sheet pass focuses on P↔Q identity, not MC↔TM.
- **Production Baseline switch to TM-Q.** Out of scope; depends on the bias investigation outcome.

## 8. Conclusion-log entry

When the cheat-sheet pass completes, add an entry to `CONCLUSIONS_private.md` summarizing:
- The cheat-sheet docs are now the canonical P↔Q kernel reference.
- The bias source identified (if found), with file:line and equation reference.
- Any new labeled equations added to the math doc as part of the audit.
