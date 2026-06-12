# Plan: Extend BST Harmenberg Appendix and Revise HAFiscal Math Document

**Date**: 2026-04-01
**Status**: Draft
**Prerequisite**: `history/20260401-harmenberg-notebook-creation.md` (notebook is validated)
**Source material**: `history/20260331-mathematical-derivations-harmenberg.md` (Sections 13–14)

---

## Overview

The HAFiscal `math-deriv-harm` document (Sections 13–14) contains new derivations on:

1. **When the joint distribution is required** (§13): Which aggregate statistics are linear in permanent income $p$ (computable from 1D Harmenberg objects) vs nonlinear in $p$ (requiring the full joint distribution).
2. **Balanced growth and serial correlation of the covariance** (§14): The covariance $\text{Cov}(c_{\text{nrm}}, p)$ can be computed exactly from the 1D Harmenberg distribution, has deterministic balanced growth, and has serial correlation of exactly 1 in the invariant economy.

These results are general — they apply to any buffer-stock model, not just HAFiscal. They belong in the *BufferStockTheory* (BST) paper's Harmenberg appendix as the single source of truth (SST). Once in BST, the HAFiscal document should be revised to *reference* the BST appendix rather than independently derive the results.

---

## Phase 1: Create BST Branch and Add New Appendix Content

### Step 1.1: Create the branch and initial commit

```bash
cd /home/shared/github/llorracc/BufferStockTheory-Latest
git checkout -b apndx-harmenberg
git commit --allow-empty -m "$(cat <<'EOF'
Begin extending ApndxHarKmenberg with material from HAFiscal Harmenberg implementation

This branch adds new sections to the Harmenberg appendix, drawing on
derivations produced during the implementation of the Harmenberg
permanent-income-neutral measure in the HAFiscal project (HAFiscal-Latest,
branch 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC) and on updated
Harmenberg documentation in the HARK toolkit.

The new material covers:
  (A) When the joint distribution of (p, m) is required vs when
      the 1D Harmenberg distribution suffices
  (B) The covariance kernel: exact computation of Cov(c_nrm, p)
      from the 1D Harmenberg distribution
  (C) Higher-order moments from analytical p-structure

These results are general to any buffer-stock model and belong in
this appendix as the single source of truth (SST). The HAFiscal
and DemARK documents will be revised to reference this appendix.
EOF
)"
```

**Branch name**: `apndx-harmenberg`
**Base**: `master`

### Step 1.2: Map math-deriv-harm notation to BST notation

The BST appendix `ApndxHarKmenberg.tex` uses a specific notation system defined via `\newcommand` at the top of the file. The translation table is:

| math-deriv-harm (markdown) | BST LaTeX |
|---------------------------|-----------|
| $p$ (permanent income level) | `\permLvl` or `\permLvlPrb` |
| $\psi$ (permanent shock) | `\permShk` |
| $\theta$ (transitory shock) | `\tranShk` |
| $c(m,z)$ (consumption function) | `\cFunc(\mNrm)` or `\cNrm(\mNrm)` |
| $m$ (normalized market resources) | `\mNrm` |
| $a(m,z)$ (end-of-period assets) | `\aNrm(\mNrm)` |
| $G$ (permanent income growth factor) | `\PermGroFac` |
| $R$ (interest factor) | `\Rfree` |
| $L$ (survival probability) | `\LivPrb` |
| $P$-measure (standard) | subscript $P$ or "raw" |
| $Q$-measure (neutral) | $\tilde{\cdot}$ ("weighted") |
| $\pi_Q$ (neutral ergodic distribution) | `\mpPrbMargWgt` |
| $\pi_P$ (standard marginal distribution) | `\mpPrbMargRaw` |
| $\text{Cov}(c, p)$ | `\cov(\cNrm, \permLvl)` |
| $\bar{c}$ (mean consumption ratio) | `\cNrmAvg` |
| $\Omega_{\text{cov}}$ (cov growth factor) | `\GroFac_{\cov}` |

The BST paper already uses `\cov(\cNrm, \permLvl)` in Section 4.3 (`subsec:Covariances`) and the appendix `ApndxBalancedGrowthcNrmAndCov`. New content should be consistent with these.

### Step 1.3: Add new subsections to `ApndxHarKmenberg.tex`

Insert new content **before** the `\end{document}` but **after** the existing material (which ends after the proof of the weighted distribution law of motion, around line 208). The existing content covers:

- The joint measure transition (`\mpPrb_{t+1}` law of motion)
- The marginal (unweighted) distribution `\mpPrbMargRaw` definition
- The permanent-income-weighted distribution `\mpPrbMargWgt` definition
- Harmenberg's Theorem 1: law of motion for `\mpPrbMargWgt` with tilted shocks
- The discrete version of the proof

The new subsections to add:

#### Subsection A: "When the Joint Distribution Is Required"

Translate math-deriv-harm §13 into BST notation. Key content:

- The Q-factorization identity: statistics linear in $p$ are computable from `\mpPrbMargWgt` alone
- Precise characterization of which statistics are linear in $p$ (aggregate $\CLvl$, $\YLvl$, $\ALvl$) vs nonlinear (variance, Gini, welfare)
- **Proposition**: For non-affine $h$, $\mathbb{E}_P[h(\permLvl \cdot f(\mNrm))]$ cannot be computed from `\mpPrbMargWgt` and $\mathbb{E}_P[\permLvl]$ alone
- Summary table of statistics and their computability from 1D objects
- The three approaches: 2D TM, Standard MC, Harmenberg + Reconstruction

#### Subsection B: "The Covariance Kernel and 1D Computability"

Translate math-deriv-harm §14.4 into BST notation. Key content:

- Law of total covariance decomposition
- The conditional covariance: $p$ factors out linearly
- The covariance kernel $\gamma_{z'}(a)$ definition and its independence from $p$
- The complete formula: $\text{Cov}(c, p)$ from 1D objects (the "boxed" equation (cov-complete) in math-deriv-harm)
- Cost comparison: $O(MJS)$ vs $O((MN_p J)^2)$
- Connection to the existing §4.3 and `ApndxBalancedGrowthcNrmAndCov` content on balanced growth

#### Subsection C: "Higher-Order Moments from Analytical $p$-Structure"

Translate math-deriv-harm §14.8. Key content:

- For $k \geq 2$, $\mathbb{E}_P[p^k]$ can be computed analytically from the age distribution and shock variance
- This opens the door to approximating $\text{Var}(A)$ from 1D objects + analytical $p$-moments
- The approximation is not exact because mixed terms $\text{Cov}(p^{k-1}, g(m))$ are not absorbed by the neutral measure

### Step 1.4: Verify standalone compilation

```bash
cd /home/shared/github/llorracc/BufferStockTheory-Latest
latexmk -pdf Appendices/ApndxHarKmenberg.tex
```

Ensure no compilation errors. Fix any missing macros by adding `\providecommand` declarations or importing from the parent document's preamble.

### Step 1.5: Commit on the branch

```bash
git add Appendices/ApndxHarKmenberg.tex
git commit -m "Add subsections on joint-distribution requirements and 1D covariance computability"
```

---

## Phase 2: Integration with BST via Matsya

### Step 2.1: Add references to `BufferStockTheory-Add-Refs.bib`

Any new citations introduced in the appendix (beyond the existing `harmenbergInvariant` entry in `ApndxHarKmenberg.bib`) should be added to `BufferStockTheory-Add-Refs.bib`. In particular, if the new subsections cite results from Carroll (2022) *BufferStockTheory* itself, Szeidl (2013), or other sources not already in the bib files, add them here.

### Step 2.2: Use `matsya-local` for notation review and notebook assessment

The BST paper body (§4.3 "Aggregate Balanced Growth and Idiosyncratic Covariances") already discusses the covariance dynamics and references `ApndxBalancedGrowthcNrmAndCov`. The new appendix material should be cross-referenced appropriately.

Use the `matsya-local` tool from `HARK_ask-your-project/scripts/rag-cli/` to:

1. Feed the new appendix content + the existing body §4.3 + `ApndxBalancedGrowthcNrmAndCov.tex` + the DemARK notebook to the RAG system
2. Ask matsya to review for:
   - Notation consistency with the rest of BST
   - Whether any content currently in `ApndxBalancedGrowthcNrmAndCov` should be reorganized now that the Harmenberg appendix has expanded
   - **Whether any of the mathematical exposition or derivations in the DemARK notebook** (`Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb`) should be migrated into the appendix

```bash
cd /home/shared/github/llorracc/BufferStockTheory-Latest
matsya-local \
  "Review the new subsections in ApndxHarKmenberg.tex for notation consistency \
   with the body text Section 4.3 (subsec:Covariances) and the existing \
   ApndxBalancedGrowthcNrmAndCov appendix. Also review the mathematical \
   exposition in the Harmenberg-Four-Way-Comparison notebook and advise: \
   (1) whether any derivations or mathematical content currently in the \
   notebook should be migrated into the ApndxHarKmenberg appendix, and \
   (2) whether any content in ApndxBalancedGrowthcNrmAndCov should be \
   reorganized now that the Harmenberg appendix has expanded." \
  --files Appendices/ApndxHarKmenberg.tex \
          Appendices/ApndxBalancedGrowthcNrmAndCov.tex \
          BufferStockTheory-NoAppendix.tex \
          /home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb \
  --k 30
```

### Step 2.3: Implement matsya's recommendations

Based on matsya's review:
- Fix any notation inconsistencies in the new appendix subsections
- Add appropriate cross-references in `BufferStockTheory-Add-Refs.bib`
- Migrate any notebook derivations into the appendix if matsya recommends it
- Commit the integrated changes

### Step 2.4: Verify standalone and full-document compilation

```bash
latexmk -pdf Appendices/ApndxHarKmenberg.tex
latexmk -pdf BufferStockTheory.tex
```

---

## Phase 3: Revise HAFiscal `math-deriv-harm` and the DemARK Notebook

### Goal

Transform both the HAFiscal math document and the DemARK notebook so that the BST `ApndxHarKmenberg` appendix is treated as the **single source of truth** (SST) for all general Harmenberg derivations. Each downstream document retains only material specific to its purpose.

### Step 3.1: Revise `math-deriv-harm`

Transform `history/20260331-mathematical-derivations-harmenberg.md` from a self-contained set of independent derivations into a **summary document** that:

1. States the key results needed for HAFiscal implementation
2. References the BST `ApndxHarKmenberg` appendix as the SST
3. Retains only HAFiscal-specific material (splurge term, state fraction propagation, pLvl_factor interaction, validation results)

#### Disposition table

| Section | Disposition |
|---------|------------|
| §1 (Change of Measure) | **Replace** with brief statement + BST reference |
| §2 (Shock Reweighting) | **Keep** — HAFiscal-specific (unemployed states, `_to_neutral_measure()`) |
| §3 (Neutral TM + Aggregation) | **Replace** core derivation with BST reference; keep HAFiscal code pointers |
| §4 (Newborn Distribution Under Q) | **Keep** — HAFiscal-specific |
| §5 (State Fractions Under Q) | **Keep** — HAFiscal-specific |
| §6 (Standard State Fraction Propagation) | **Keep** — HAFiscal-specific |
| §7 (Aggregation Under Q) | **Replace** derivation with BST reference; keep code pointers |
| §8 (Splurge Term Under Q) | **Keep** — HAFiscal-specific |
| §9 (Income Under Q) | **Keep** — brief, HAFiscal-specific |
| §10 (Adapted Initial Distribution) | **Keep** — HAFiscal-specific |
| §11 (Error Decomposition) | **Keep** — HAFiscal-specific |
| §12 (Validation Results) | **Keep** — HAFiscal-specific |
| §13 (Joint Distribution Required) | **Replace** with summary + BST reference |
| §14 (Balanced Growth + Covariance) | **Replace** with summary + BST reference |

Add a header note:

> The general mathematical results underlying the Harmenberg neutral measure are derived in the *BufferStockTheory* paper's appendix (Carroll 2022, `ApndxHarKmenberg`, Sections X–Z). This document summarizes the results relevant to HAFiscal's implementation and provides HAFiscal-specific derivations that extend the general theory.

For each "Replace" section, write ~1 paragraph stating the result and citing the specific BST equation/section, followed by any HAFiscal-specific implementation notes.

### Step 3.2: Revise the DemARK notebook

Revise `Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb` so that:

1. The "Mathematical Framework" section (§1 of the notebook) references the BST `ApndxHarKmenberg` appendix as the SST for the formal derivations, rather than independently re-deriving the key identity and aggregation formulas
2. Any mathematical exposition that matsya identified (Phase 2, Step 2.2) as belonging in the appendix is removed from the notebook and replaced with a reference
3. The notebook retains its computational focus: the four method implementations, sensitivity analysis, and visualizations remain unchanged
4. The "Summary" section (§9) notes that the theory is developed in the BST appendix and the notebook serves as computational validation

The notebook should open with something like:

> The mathematical theory underlying the Harmenberg permanent-income-neutral measure is developed in Carroll (2022, *BufferStockTheory*, Appendix: Harmenberg's Method). This notebook provides computational validation of the key results using four parallel implementations.

### Step 3.3: Commit in HAFiscal

```bash
cd /home/shared/github/llorracc/HAFiscal-Latest
git add history/20260331-mathematical-derivations-harmenberg.md \
        Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb
git commit -m "Revise math-deriv-harm and DemARK notebook to reference BST appendix as SST"
```

---

## Execution Order and Dependencies

```
Phase 1 (BST branch)
  ├── 1.1 Create branch + initial --allow-empty commit
  ├── 1.2 Notation mapping
  ├── 1.3 Write new subsections
  ├── 1.4 Verify compilation
  └── 1.5 Commit content
      │
      ▼
Phase 2 (Matsya integration)
  ├── 2.1 Add references to BufferStockTheory-Add-Refs.bib
  ├── 2.2 matsya-local review (notation + notebook assessment)
  ├── 2.3 Implement recommendations (incl. migrate notebook derivations if advised)
  └── 2.4 Verify compilation (standalone + full document)
      │
      ▼
Phase 3 (HAFiscal revision)
  ├── 3.1 Revise math-deriv-harm (replace general derivations with BST references)
  ├── 3.2 Revise DemARK notebook (reference BST appendix as SST for theory)
  └── 3.3 Commit both
```

Phases 1 and 2 operate on `BufferStockTheory-Latest` (branch `apndx-harmenberg`).
Phase 3 operates on `HAFiscal-Latest` (current branch).

---

## Risks and Mitigation

| Risk | Mitigation |
|------|-----------|
| BST LaTeX macro compatibility | Test standalone compilation of `ApndxHarKmenberg.tex` before full-document build |
| Notation drift between BST and math-deriv-harm | Use the translation table in Step 1.2; have matsya verify |
| matsya unavailable or uninstalled | Fall back to manual review of notation consistency using grep + side-by-side reading |
| Large new appendix sections dwarf existing content | Structure as subsections so the existing proof remains the logical starting point; new material extends it |
| Notebook loses mathematical context after revision | Retain enough inline summary that the notebook is self-contained for a reader who has not read the appendix; use "see BST Appendix X for derivation" rather than removing all math |

---

## Estimated Effort

| Phase | Estimated Time |
|-------|---------------|
| 1.1–1.2 (Branch + empty commit + notation mapping) | 15 min |
| 1.3 (Write LaTeX subsections) | 2–3 hours |
| 1.4–1.5 (Compile + commit) | 15 min |
| 2.1 (Add bib references) | 15 min |
| 2.2–2.3 (Matsya review + integration + notebook migration) | 1–2 hours |
| 2.4 (Compilation verification) | 15 min |
| 3.1 (Revise math-deriv-harm) | 1–2 hours |
| 3.2 (Revise DemARK notebook) | 30 min–1 hour |
| 3.3 (Commit) | 5 min |
| **Total** | **~6–8 hours** |
