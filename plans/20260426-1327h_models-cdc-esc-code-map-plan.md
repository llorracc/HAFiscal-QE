# Plan: anchor `models_CDC_and_ESC.md` to the codebase via named equations

**Date:** 2026-04-26
**Status:** Planned (revised; supersedes earlier draft of this same file)
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (the CDC anchor branch; the docs go in `BUGS_private/HAFiscal_splurge_budget_inconsistency/`)
**Predecessor:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md` — the canonical CDC↔ESC formal spec; this work *expands* it (adds equation labels) and adds code-side cross-references.

## Goal

Build a stable spec↔code cross-reference scheme using **named equation labels** as the primary key. Four phases:

1. **Add named labels to all major equations in `models_CDC_and_ESC.md`** — additive edit to the existing canonical spec; the equations themselves are unchanged, only the `\qquad\qquad (LABEL)` annotation is added at the right of each.
2. **Add code-side reference comments** at every implementation site, of the form `# implements (LABEL) of models_CDC_and_ESC.md`. The labels become the stable cross-reference key. After this step, `grep -rn '(CDC-1)' Code/` finds every code site that implements that equation.
3. **Produce `models_CDC_and_ESC-with-code-map.md`** — for each labeled equation, list every code site that implements it with verbatim snippets. Becomes a derived view assembled from the grep results, not hand-curated content.
4. **Produce `models_CDC_and_ESC-with-code-map_missing-stuff-to-add.md`** — code constructs that lack a corresponding labeled equation in the spec; proposes new labels + spec text. Once accepted, those new labels go back to step 1 and the missing constructs get code-side comments per step 2.

## Why this approach is better than a single-pass code-map walk

- The named labels are a **stable, greppable, forward-compatible** primary key. Refactoring the spec doesn't break code-side references because the labels stay; refactoring the code doesn't break the spec because the spec only references labels, not file:line.
- The "with-code-map" doc becomes **partially mechanical**: once labels exist on both sides, building the doc is largely "for each label, grep for its code references and paste a snippet from each site." Less judgment-heavy, less prone to drift over time.
- The "missing stuff" doc becomes a **proposal-for-new-labels** doc rather than free-form prose — concrete deliverables.
- The in-code marker scheme already started (`# CDC-MOD-BUG<NN>:`) is anchor-to-bug; the new `(LABEL)` references are anchor-to-equation. They're complementary: a single line of code can have both, e.g. `# CDC-MOD-BUG031 — implements (CDC-1)`.

## Phase 1 — Add named labels to `models_CDC_and_ESC.md`

### Labeling scheme — *use the paper's labels where they exist*

Per coauthor guidance: where an equation in `models_CDC_and_ESC.md` has a labeled counterpart in the main HAFiscal paper (`Subfiles/*.tex`, `\label{...}` directives), **use the paper's label verbatim**. Where no counterpart exists, make up a name following the same `eq:<name>` convention, with `-CDC` or `-ESC` suffix when the equation is interpretation-specific.

#### Inventory of existing paper labels

Grep'd from `Subfiles/Model.tex` and `Subfiles/Comparing-policies.tex` (only files with `\label{eq:...}` or `\label{welfare6}`):

| Paper label | Equation form | Where in paper |
|---|---|---|
| `eq:model` | `c_{i,t} = c_{sp,i,t} + c_{opt,i,t}` (consumption decomposition) | `Subfiles/Model.tex:33` |
| `eq:splurge` | `c_{sp,i,t} = ς · y_{i,t}` (splurge formula) | `Subfiles/Model.tex:46` |
| `eq:utility` | `Σ β^t (1-D)^t E[u(c_{opt,i,t})]` (lifetime utility objective) | `Subfiles/Model.tex:61` |
| `eq:budget` | `a = m - c; m_{t+1} = R·a + y_{t+1}; a ≥ 0` (budget constraint) | `Subfiles/Model.tex:78` |
| `eq:perm_income` | `p_{i,t+1} = ψ_{i,t+1} · Γ · p_{i,t}` (permanent income evolution) | `Subfiles/Model.tex:99` |
| `eq:income` | `y_{i,t} = ξ·p` (employed) / `ρ_b·p` (UI) / `ρ_{nb}·p` (no UI) | `Subfiles/Model.tex:124` |
| `eq:ad_feedback` | `AD(C_t) = (C_t/C̃)^κ` if recession, else 1 | `Subfiles/Model.tex:209` |
| `eq:ad_income` | `y_{AD,i,t} = AD(C_t) · y_{i,t}` (AD-adjusted income) | `Subfiles/Model.tex:225` |
| `welfare6` | `W(policy, Rec, AD) = Σ R^{-t}[u(c^pol) - u(c^none)]/u'(c^normal) / NPV` | `Subfiles/Comparing-policies.tex:155` |

Note: `welfare6` is the only label without an `eq:` prefix in the paper; we preserve that asymmetry (no harmonization).

#### Convention for new labels

For equations in `models_CDC_and_ESC.md` that are **not** in the paper, invent labels following these rules:

- Prefix with `eq:` (matching paper convention; only `welfare6` is exempt).
- Use a short descriptive suffix (e.g., `eq:bellman`, `eq:targets`, `eq:opt-proposal`).
- **No underscores in label names** — hyphens only. Underscores cause markdown italic-rendering bugs (per the `feedback_github_markdown_math.md` memory and the multi-commit math-rendering fix iteration on this same `BUGS_private/HAFiscal_splurge_budget_inconsistency/` directory). Use `eq:perm-income`, not `eq:perm_income`.
- For an equation that's interpretation-specific (i.e., CDC-specific or ESC-specific), append `-CDC` or `-ESC` to the label suffix: e.g., `eq:budget-CDC`, `eq:budget-ESC`. This keeps `grep -rn '(eq:budget-CDC)' Code/` distinct from ESC sites.
- For an equation that's shared between CDC and ESC, no `-CDC`/`-ESC` suffix.

#### Hyphen-conversion for paper labels containing underscores

Three paper labels contain underscores: `eq:perm_income`, `eq:ad_feedback`, `eq:ad_income`. Markdown renderers can italicize the substring between underscores depending on context, so the spec uses a **hyphen-converted** form:

| Paper label (TeX) | Spec label (markdown-safe) |
|---|---|
| `eq:perm_income` | `eq:perm-income` |
| `eq:ad_feedback` | `eq:ad-feedback` |
| `eq:ad_income` | `eq:ad-income` |

The spec's first occurrence of each notes the conversion explicitly: e.g., `(eq:perm-income; paper TeX label: eq:perm_income)`. After that, the spec uses the hyphen form. Code-side `# implements (...)` comments use the hyphen form too (so the same string greps both spec and code).

The other six paper labels (`eq:model`, `eq:splurge`, `eq:utility`, `eq:budget`, `eq:income`, `welfare6`) have no underscores and are used verbatim.

### Equations to label — proposed mapping

Walking the existing `models_CDC_and_ESC.md`:

**§2 Common notation** — most are plain symbol introductions (no equation label needed). The few derived definitions get labels matching paper where possible:
- `(eq:income)` — `Y_tot,t = ξ·p_tot,t` (the employed case of the paper's `eq:income`)
- `(eq:perm-income)` — `p_{t+1} = ψ·Γ·p` (matches paper)
- `(eq:bank-balance)` — `B_tot,t = R·A_{t-1}/(Γ·ψ)` (no paper counterpart; derived from `eq:budget`'s state transition)
- `(eq:market-resources)` — `M_tot,t = B + Y` (no paper counterpart)
- `(eq:utility-fn)` — `u(c) = c^{1-γ}/(1-γ)` (no paper label — paper introduces this inline at line 70 of Model.tex without a `\begin{equation}`)

**§3 Shared equations:**
- `(eq:bellman)` — the buffer-stock Bellman defining `c^std(m)` (no paper counterpart — paper has `eq:utility` for the *objective* but no labeled Bellman)
- `(eq:budget)` — the household-level state transition `M_{t+1} = R·A/(Γψ') + Y'` (matches the second line of paper's `eq:budget`)
- `(welfare6)` — the welfare aggregator (matches paper exactly)
- `(eq:targets)` — calibration targets (no paper counterpart — bullet-list label)
- `(eq:model)` — `c = c_sp + c_opt` decomposition (matches paper) — applies to §3 if the spec gains an explicit decomposition statement; currently the spec elides this
- `(eq:splurge)` — `c_sp = ς·y` (matches paper) — same caveat
- `(eq:utility)` — `Σ β^t (1-D)^t E[u(c_opt)]` (matches paper) — the objective the optimizer maximizes

**§4 CDC** — relabel `(CDC-1)` to its paper-derived form; introduce new labels for CDC-specific framings:
- `(eq:opt-proposal-CDC)` — optimizer voice's proposal: `c_opt^proposal = c^std(m_tot)·p_tot` (no paper counterpart — CDC-specific reading)
- `(eq:spl-proposal-CDC)` — splurger voice's proposal: `c_spl^proposal = Y_tot` (no paper counterpart — CDC-specific reading)
- `(eq:total-CDC)` — total household consumption: `C_tot = (1−ς)·c_opt^proposal + ς·c_spl^proposal` (CDC's reading of the paper's `eq:model` + `eq:splurge` combined; CDC-specific *interpretation* of the same identity)
- `(eq:budget-CDC)` — **was `(CDC-1)`** — asset-update rule under CDC reading of `eq:budget`: `A_tot = M_tot − C_tot = M_tot − (1−ς)·c^std·p − ς·Y_tot`
- `(eq:KY-CDC)` — K/Y aggregator under CDC: `K/Y = Σ A_tot / Σ Y_tot`

**§5 ESC** — relabel `(ESC-1)` similarly; introduce new labels for ESC-specific framings:
- `(eq:y-opt-ESC)` — Optimizer's income share: `Y_opt = (1−ς)·Y_tot`, `A_opt = A_tot`
- `(eq:y-spl-ESC)` — Splurger's income share: `Y_spl = ς·Y_tot`, `A_spl = 0`
- `(eq:c-opt-ESC)` — Optimizer's consumption: `c_opt = c^std(m_opt)·p_opt`
- `(eq:c-spl-ESC)` — Splurger's consumption: `c_spl = Y_spl = ς·Y_tot`
- `(eq:total-ESC)` — household-total consumption: `C_tot = c_opt + c_spl`
- `(eq:assets-ESC)` — household-total assets: `A_tot = A_opt + A_spl = A_opt`
- `(eq:budget-ESC)` — **was `(ESC-1)`** — Optimizer's asset-update rule under ESC reading of `eq:budget`: `A_opt = M_opt − c_opt`
- `(eq:conv1-ESC)` — Convention 1 normalization: `a_opt = A_opt/p_opt = a_tot/(1−ς)`
- `(eq:conv2-ESC)` — Convention 2 normalization: `a_opt = A_opt/p_tot = a_tot`
- `(eq:KY-ESC)` — K/Y aggregator under ESC: `K/Y = (1−ς)·Σ A_opt / Σ Y_tot`

#### Backward-compatibility note for existing `(CDC-1)` and `(ESC-1)` labels

The two existing labels in `models_CDC_and_ESC.md` are `(CDC-1)` and `(ESC-1)`. They are replaced by `(eq:budget-CDC)` and `(eq:budget-ESC)` respectively, but the existing `(CDC-1)` / `(ESC-1)` should be retained in parentheses as **aliases** for at least one revision cycle, since they're already referenced by:
- `BUGS_private/HAFiscal_BUG-031_splurge_not_in_budget.md`
- `plans/20260425-2102h_cdc-implementation-map.md`
- The 8 in-code `# CDC-MOD-BUG<NN>:` markers
- `plans/20260425-2137h_cdc-esc-configurable-refactor.md`

Format: `(eq:budget-CDC, formerly (CDC-1))`. Once those references are updated to the new labels (out of scope for this plan), the alias can be dropped.

### How labels are added in the spec

For block-math equations (` ```math ` fenced blocks), append `\qquad\qquad (eq:label)` to the last line of the math expression (matches the existing `(CDC-1)` style at line 116-118 of the current spec).

For variable definitions in §2 (currently bullet items), the label can be appended in `\qquad (eq:label)` form at the end of the line for the few non-trivial derived definitions; trivial single-symbol introductions (`R`, `β_i`, `ς`) don't need labels.

For interpretation-shared equations whose label matches the paper's: the spec annotation explicitly says "(eq:budget; cf. paper Subfiles/Model.tex eq (4))" or similar, so a reader can trace from spec back to paper directly.

### Output of Phase 1

A modified `models_CDC_and_ESC.md` with ~20-25 new labels (some matching paper's `\label{eq:...}` directly; others freshly minted with `-CDC`/`-ESC` suffixes). The equations are unchanged; only annotations added. Existing `(CDC-1)` / `(ESC-1)` labels retained as aliases in parentheses for one revision cycle to avoid breaking the existing references in BUG-031 dossier, code-side markers, and the implementation-map plan.

Single commit, with commit message listing every new label introduced.

## Phase 2 — Add code-side reference comments

### Comment format

Above each line (or block) of code that implements a labeled equation, add a single-line comment:

```python
# implements (eq:budget-CDC) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
```

If multiple labels apply to the same site (e.g., a line that implements both `(eq:total-CDC)` and `(eq:budget-CDC)` together), list both:

```python
# implements (eq:total-CDC) and (eq:budget-CDC) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
```

The path is given in full (relative to repo root) so a reader can click straight to the spec from the code.

When the same equation also has a labeled counterpart in the paper (e.g., `(eq:budget)` — the shared form), it is sufficient to reference the spec label, since the spec is the canonical disambiguation. The spec itself notes the paper-side cross-reference (per the formatting guidance in Phase 1's "How labels are added in the spec").

### Compatibility with existing paper-side `RAG_METADATA` comments

The paper TeX files already contain `% RAG_METADATA: code_location=AggFiscalModel.py:getIncome()` style comments at most labeled equations (e.g., `Subfiles/Model.tex:50, 65, 82, 103, 128, 213, 229`). These point from paper-side to code; the new in-code `# implements (eq:...)` comments point from code to spec. They're orthogonal — the paper-side metadata can stay untouched. (As a follow-up beyond this plan's scope, the RAG_METADATA `code_location` fields could be updated to match the actually-relevant file:line pairs uncovered during Phase 2; some of the existing paths look stale, e.g., `EstimAggFiscalModel.py` instead of the actual `Estimation_BetaNablaSplurge.py`.)

### Combining with existing `# CDC-MOD-BUG<NN>:` markers

The existing markers stay where they are (they document *interpretive* sites — places where CDC differs from ESC). The new `# implements (LABEL)` comments document *which equation* the line implements. They're complementary:

```python
# CDC-MOD-BUG031 [central anchor]. Override of HARK's default a = m - cFunc(m) ...
# implements (CDC-1) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
def get_poststates(self):
    ...
```

Sites that implement a labeled equation but are *shared* between CDC and ESC (no interpretive choice) get only the `# implements (LABEL)` comment, not a `# CDC-MOD-` marker.

### Sites to annotate (initial inventory)

**`AggFiscalModel.py`:**
- Line ~1054 (`cLvl_splurge` formula) — implements `(eq:total-CDC)` (the household-total weighted-average consumption); also references paper's `(eq:model) + (eq:splurge)` combined under CDC reading
- Line 1059 (`get_poststates`) — implements `(eq:budget-CDC)` (asset-update rule under CDC reading of paper's `(eq:budget)`)
- The `cFunc` solver call (`solve_one_period`) — implements `(eq:bellman)` and `(eq:utility)` (the optimizer's objective from paper)
- The state transition (HARK's internal mNrm computation) — implements `(eq:budget)` (state-transition line of paper's budget eq)
- Income process construction — implements `(eq:income)` and `(eq:perm-income)`

**`tm_methods.py`:**
- `_build_period_tm_a` kernel — implements vectorized forms of `(eq:budget-CDC)` + `(eq:budget)` (state transition)
- The check-period decomposition — implements `(eq:total-CDC)` integrated against the bucket distribution
- AD-experiment kernel — implements `(eq:ad-feedback)` and `(eq:ad-income)`

**`Estimation_BetaNablaSplurge.py`:**
- `_wealth_under_cdc` (module-level helper) — implements `(eq:budget-CDC)` rearranged for the wealth correction
- `_lottery_consumption_under_cdc` — implements `(eq:total-CDC)` + `(eq:budget-CDC)`
- The K/Y aggregator (line ~303) — implements `(eq:KY-CDC)` (downstream of `_wealth_under_cdc`)
- `FagerengObjFunc` Lorenz / MPC calculations — implements `(eq:targets)` (matching against the calibration targets)

**`Welfare.py`:**
- The `felicity()` function applied to `cLvl_all_splurge` — implements `(welfare6)`

**`Parameters.py`:**
- Calibration targets dict — implements `(eq:targets)` (loads K/Y, Lorenz, MPC values)
- Income process parameters (`ρ_b`, `ρ_{nb}`) — implements `(eq:income)`'s parameter set

For ESC-side sites (on `origin/maintain_bound_pair_fix_splurge`), the analogous annotations would be added in Phase 2 of the eventual ESC-runnable refactor (out of scope for this plan, which only covers `_TM-vs-MC`).

### Process

For each labeled equation:
1. Grep the codebase for the equation's component variables and operators.
2. Identify the canonical implementation site(s).
3. Add the `# implements (LABEL)` comment above the relevant line(s).

Single commit per file (so each file's annotations are reversible in isolation).

### Validation after Phase 2

`grep -rn '# implements (' Code/` should return ~15-25 hits, distributed across the files above. Each labeled equation in the spec should appear in at least one code-side `# implements` comment. Conversely, every `# implements (LABEL)` comment should reference a label that exists in the spec (no orphans).

## Phase 3 — Produce `models_CDC_and_ESC-with-code-map.md`

### Structure

Mirror the section structure of the spec. For each labeled equation, immediately after the equation, add a "**Code map**" subsection listing every site `grep -rn '(LABEL)' Code/` returns:

```
### (CDC-1) Asset-update rule

$$
\mathbf{A}_{\text{tot},t} = \mathbf{M}_{\text{tot},t} - (1-\varsigma)\,c^{\text{std}}(m_{\text{tot},t})\,p_{\text{tot},t} - \varsigma\,\mathbf{Y}_{\text{tot},t}
\qquad\qquad (\text{CDC-1})
$$

#### Code map

- `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1086` — `_cdc_asset_rule(...)` helper
  ```python
  cNrm_actual = (1.0 - splurge) * state_now['cNrm'] + \
      splurge * shocks['TranShk'] * AggDemandFac
  aNrm = state_now['mNrm'] - cNrm_actual
  ```

- `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1059` — `AggFiscalType.get_poststates` calls `_cdc_asset_rule`
  ```python
  self.state_now['aNrm'], self.state_now['aLvl'] = _cdc_asset_rule(
      self.state_now, self.shocks, self.AggDemandFac, self.Splurge
  )
  ```

- `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py:341` — `_lottery_consumption_under_cdc(...)` body, computing `a_base` and `a_actu`
  ```python
  a_base_nrm = m_base - c_base_nrm
  a_actu_nrm = m_lottery - c_actu_nrm
  ```

- `Code/HA-Models/FromPandemicCode/tm_methods.py:_build_period_tm_a` — vectorized form across the a-grid
```

### Process

Largely mechanical once labels exist:
1. For each label, run `grep -rn '(LABEL)' Code/` to collect sites.
2. For each site, extract a 3-10-line snippet around the cited line.
3. Compose the doc section with the formula + code-map subsection.

### Output

A new file `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC-with-code-map.md`. Single commit.

## Phase 4 — Produce `models_CDC_and_ESC-with-code-map_missing-stuff-to-add.md`

### Goal

Find code constructs that *ought* to have a labeled equation in the spec but currently don't. Three classes of finding:

- **(A) Load-bearing assumptions** — things the spec implicitly relies on but doesn't state. Including them would make CDC vs ESC unambiguous in cases the current spec leaves murky.
- **(B) Computational details that affect the interpretation** — e.g., `AggDemandFac` multiplier on realized income, `R_kink` borrow-vs-save rate distinction, the Markov state machine for employment transitions.
- **(C) Variants and diagnostics worth cross-referencing** — `HAFISCAL_SPLURGE_OLD` env var (provides ESC-equivalent rule for diagnostics), Q-track Harmenberg neutral measure, `tm_a_indexed` flag, `mc_shuffle`/`income_shuffle` variance-reduction.

### Output structure for each missing item

```
### Item: AggDemandFac scaling on realized income

**Class:** B (computational detail that affects the CDC↔ESC interpretation)
**Code site(s):** `AggFiscalModel.py:1054-1055` (in the `cLvl_splurge` formula)
  ```python
  self.state_now['cLvl_splurge'] = (1.0-self.Splurge)*self.state_now['cLvl'] \
      + self.Splurge*self.state_now['pLvl']*self.shocks['TranShk']*self.AggDemandFac
  ```

**What it does:** During AD-amplified recession scenarios, `AggDemandFac` (≥1)
scales realized transitory income, capturing the demand multiplier. Under
baseline (no AD), `AggDemandFac = 1` and the scaling is invisible.

**Why it ought to be in the spec:** The spec's `(CDC-2)` and `(ESC-4)` both
write the splurge piece as `ς·Y_tot`. In code, this becomes `ς·p·ξ·ADF`
under CDC and (presumably) the same under ESC, but the ADF modifier isn't
in the spec. A reader trying to verify the AD-scenario behavior against
the spec would conclude the code has an extra factor.

**Suggested spec addition:** Add a new section §3.5 or §X "Aggregate-demand
scaling" defining `AggDemandFac_t` and revising `Y_tot,t` (and hence
`(SHR-Y)`, `(CDC-2)`, `(ESC-3)`) to read `Y_tot,t = ξ_tot,t · p_tot,t · ADF_t`.
Propose label `(SHR-ADF)`.
```

### Items the discovery walk should at least cover

(Not exhaustive; populate during execution.)

- `AggDemandFac` (above)
- `R_kink` (different `Rfree` for `a < 0` vs `a > 0`) — affects `(SHR-STATE)`
- `LivPrb` / `(1−D)` mechanics (death-and-replacement) — `(SHR-BELLMAN)` mentions `D` but the simulation-side reset to `kLogInitMean` is unstated
- Markov state machine for employment / UB-spell / unemployed-no-benefits — spec uses scalar `ξ` with replacement rates
- `IncShkDstn` discretization — spec treats `ψ`, `ξ` as continuous
- TM (transition matrix) discretization — entire computational approach absent from spec
- `_a` vs `_m` indexed kernels (BUG-033) — interpretation-shared infrastructure
- `cLvl_splurge_Q` (Q-track Harmenberg neutral measure variant) — spec has no Q-track
- `HAFISCAL_SPLURGE_OLD` env var — provides ESC-equivalent rule for CDC-side diagnostic
- `mc_shuffle` / `income_shuffle` variance-reduction flags
- The 4-state employment Markov machine
- `kLogInitMean` (initial wealth distribution at birth/death-replacement)
- The Fagereng lottery-MPC moment-matching scheme
- `AggregateDemandEconomy` market structure + AD feedback iteration

### Output

A new file `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC-with-code-map_missing-stuff-to-add.md`. Single commit.

## Process flow / order of operations

1. **Phase 1** (add labels to spec) → commit.
2. **Phase 2** (add `# implements (LABEL)` comments in code) → one commit per file (~5-7 commits total).
3. **Phase 3** (build code-map doc) → commit.
4. **Phase 4** (build missing-stuff doc) → commit.

Phases 1 and 2 can be treated as one logical batch (they together establish the cross-reference scheme). Phases 3 and 4 are derived views.

If during phase 4 a missing item is identified that warrants a new spec label, the loop is:
- Add the label to the spec (mini-Phase 1).
- Add `# implements` comments in the code where it's implemented (mini-Phase 2).
- Update the code-map doc (mini-Phase 3) to include the new label's section.

## Estimated effort

| Phase | Estimate |
|---|---|
| 1 — add labels to spec | 30-60 min |
| 2 — add code references | 1-2 hours |
| 3 — code-map doc | 1-2 hours |
| 4 — missing-stuff doc | 2-3 hours |
| **Total** | **~5-8 hours** |

A bit less than the original plan's 6-9 hours because the labels-first approach makes phases 3 and 4 partly mechanical.

## Validation per phase

- **Phase 1:** every equation in the spec that has a code-side implementation has a label. Phase-1 commit message lists the new labels added.
- **Phase 2:** `grep -rn '# implements (' Code/` returns all expected sites; every label referenced in code exists in the spec.
- **Phase 3:** every label in the spec has a "Code map" subsection in the new doc. Every code site cited in the doc has the corresponding `# implements (LABEL)` comment.
- **Phase 4:** every "missing item" has a concrete code site (not just a theoretical concern) and a concrete suggested-spec-addition.

## Open questions

1. **Label-name finalization** — the proposed labels (e.g., `eq:opt-proposal-CDC`, `eq:KY-ESC`, `eq:bellman`) are draft. Where they invent names, the names become permanent once code-side `# implements (eq:...)` comments reference them. Confirm before Phase 1.

2. **Granularity of variable-definition labels** — should every `ξ`, `ψ`, `R` get a label, or only the derived ones (`Y = ξ·p`, `M = B + Y`, `B = R·A/(Γψ)`)? Proposed default: only derived quantities and equations, not raw symbol introductions.

3. **Backward-compatibility window for `(CDC-1)` / `(ESC-1)`** — these are already referenced from BUG-031 dossier, the implementation-map plan, the configurable-refactor plan, and 8 in-code markers. Proposed default: keep them as aliases (e.g., `(eq:budget-CDC, formerly (CDC-1))`) for one revision cycle; drop after the references are updated. Updating the existing references is *out of scope for this plan* — would be a follow-up sweep.

4. **Phase 4 output: draft text vs description-only?** Proposed default: draft text included for each missing-item suggested spec addition (so applying it is copy-paste, not "write something new").

5. **What if Phase 4 surfaces issues with Phase 1's label set?** Allowed — the label set can grow during Phase 4 with the loop described above. Just adds incremental commits.

6. **Branch / commit strategy** — all on `_TM-vs-MC`. Each phase its own commit (or per-file for Phase 2). The original `models_CDC_and_ESC.md` IS modified in Phase 1 (additive labels only).

7. **Existing `RAG_METADATA` comments in paper TeX** — should be left alone as a separate cross-reference layer, OR updated as a follow-up to match what Phase 2 uncovers (some look stale). Proposed default: leave alone; flag as follow-up.

## Deliverables

- `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md` (modified — Phase 1 adds labels)
- ~5-7 source files modified to add `# implements (LABEL)` comments (Phase 2)
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC-with-code-map.md` (new, Phase 3)
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC-with-code-map_missing-stuff-to-add.md` (new, Phase 4)
- This planning doc (records methodology choices).
