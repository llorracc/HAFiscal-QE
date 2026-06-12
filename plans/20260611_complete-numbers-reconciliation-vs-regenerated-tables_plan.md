# Complete the prose ⇄ regenerated-table number reconciliation

**Status:** ACTIVE — authored 2026-06-11 from the substantive review (`conclusions_private/20260611_final-substantive-review.md`).

## TL;DR

The branch's TM-vs-MC validation regenerated the main result tables (Table 6 multipliers, Table 7 welfare) but the paper **prose still carries the QE-published numbers**, so the current `HAFiscal.pdf` shows QE-faithful prose next to recomputed tables. The QE-proof-compatibility pass deliberately excluded recomputed numbers, so this internal prose⇄table incoherence was never checked. This plan (1) establishes the **authoritative canonical numbers** by regenerating under the blessed method, (2) builds a **complete** prose/table/figure reconciliation matrix (the review only sampled the number-dense cells), and (3) applies a **single coordinated update** of prose + table NOTEs + the splurge-comparison tables to those numbers — or, if a number set is not yet blessed, records exactly what is pending.

---

## 1. Motivation (why this is needed)

### 1a. What the review found (results)
The prose is **unchanged from the QE-submitted version** (`/tmp/skylatex_src/qe2442.tex`); two generated result tables were regenerated **on this branch** and now diverge:

| file | last changed | commit | what moved |
|---|---|---|---|
| `Code/HA-Models/FromPandemicCode/Tables/CRRA2/Multiplier.tex` (Table 6) | 2026-04-01 | `e17193da` "full TM-AD Baseline simulation" | Check 10y AD **1.228→1.143**, no-AD **0.878→0.936**, cons-stim share **73.6%→72.1%** |
| `Code/HA-Models/FromPandemicCode/Tables/CRRA2/welfare6.tex` (Table 7) | 2026-05-16 | `516fc12f` "BUG-046/043 cutover, Jensen canonical" | UI welfare `Rec=0` **0.85→1.00**; NOTE `1.82/2.13`→`1.81/2.20` |
| `Code/HA-Models/FromPandemicCode/Tables/Splurge0/welfare6-SplurgeComp.tex` | 2025-12-19 | — | **NOT regenerated** — still holds QE values (UI `Rec=0` with-splurge = 0.85) |

Reader-visible consequences (full detail in the review doc, §A):
- **A1** `Comparing-policies.tex:99` "total multiplier of **1.234**" vs Table 6 **1.143**.
- **A2** `Comparing-policies.tex:100` "**0.879**" vs Table 6 **0.936**.
- **A3** `Comparing-policies.tex:103` "**74.2%**" vs Table 6 **72.1%**.
- **A4** `Comparing-policies.tex:172–174` narrative "UI … in normal times is noticeably less than one" + concavity explanation — **false** now that Table 7 UI `Rec=0` = **1.00** (the *highest* of the three). This is a paragraph rewrite, not a number swap.
- **B1** splurge quoted **0.25** (estimation sentence `Parameterization.tex:55`, figure note `Figures/splurge_estimation.tex:34`, Table 3) vs **0.246** (`Parameterization.tex:102`, which calls 0.246 "the value estimated in [the section]" that reports 0.25). Pre-existing in QE; harmonize.

### 1b. Why the QE-proof sync didn't catch it (the gap to close)
The QE-proof-compatibility pass (`plans/20260610_master-QE-proof-compatibility_plan.md`) was scoped as a **cosmetic/terminology/reference** sync and **explicitly excluded** the recomputed numbers:
> "excluding the TM-vs-MC validation work and the welfare-number recomputation" (l.40–41);
> "**Excluded:** welfare numbers (do NOT touch …) · TM-vs-MC content changes (recomputed numbers, splurge 0.246→0.25 …)" (l.48–50).

Its acceptance test diffed **repo prose ↔ QE proof** (l.143) — which passes by design, because the prose still matches QE. It never compared **repo prose ↔ the repo's own regenerated tables** (internal coherence), the only axis on which this contradiction appears. The prose half of each mismatch is *invisible* to a repo-vs-proof diff (the prose matches the proof); and the narrative consequence (A4) is an argument, not a number a diff pairs up. **Closing this deferred reconciliation is the purpose of this plan.**

### 1c. Canonical-method caveat (do not freeze to an intermediate table)
The welfare method was settled **2026-06-10** — MC+CRN+stratified-shuffle for all welfare cells (`conclusions_private/2026-06-10_welfare_method_unified_MC.md`; flags `HAFISCAL_MC_SHUFFLE=1 HAFISCAL_SHUFFLE_MRKV_TRANSITION=stratified HAFISCAL_SHUFFLE_NEWBORN_FIX=transition`, applied as `os.environ.setdefault` defaults in `EstimParameters.py`). But `CRRA2/welfare6.tex` was regenerated **2026-05-16**, *before* that decision (possibly under the now-rejected IS variance reduction, which had a +10% `ui_rec` bias). **Therefore the checked-in welfare6 table is not certified to be the blessed method's output.** Multipliers (Table 6) come from TM a-indexed (do_all Step 5a); welfare (Table 7) from MC welfare-6 (Step 5b). The reconciliation must use **freshly regenerated** canonical tables as the authoritative reference, not the 2026-04/2026-05 snapshots.

---

## 2. Goal & non-goals

**Goal:** every numeric claim in the compiled paper (prose, table cell, table NOTE, figure-derived percentage) equals its authoritative source under the blessed method, with provenance recorded; the result is a single coherent, QE-superseding number set.

**Non-goals / out of scope (verified clean in the review — do NOT re-litigate):**
- Calibration Tables 3 & 4 prose ⇄ tables (all match); estimBetas / nonTargetedMoments / MPC-WQ / "92.6%"/"6.60"/"18%"; HANK calibration; all `\eqref` targets; figure panel↔prose mappings; no "??" in PDF; the three `fig:LorenzPts*` labels resolve; `tab:robustness_benefit_splurge` is commented out; **Appendix-Robustness numbers are disclaimed** (`:12`) and stay frozen. See review §D.
- Terminology "wage tax cut" (Intro) vs "payroll tax cut" — leave (QE-synced); review §C1.

---

## 3. Phases

### Phase 0 — Establish authoritative numbers (regenerate under blessed method) — **run on econ-mw**
This is heavy compute; do it on `econ-mw` (ssh econ-mw), not the local mac.
1. Regenerate Table 6 multipliers: do_all **Step 5a** (`AggFiscalMAIN_reduced.py --baseline`, TM a-indexed) → `CRRA2/Multiplier.tex`.
2. Regenerate Table 7 welfare: do_all **Step 5b** (`run_welfare6_parallel.py --baseline`, MC) with the 2026-06-10 canonical defaults → `CRRA2/welfare6.tex`.
3. Diff the freshly regenerated `CRRA2/Multiplier.tex` & `welfare6.tex` against the checked-in 2026-04/2026-05 versions. **Record any change.** If they differ, the checked-in tables were intermediate; the fresh output is authoritative.
4. Decide the fate of the `Splurge0/` comparison tables (`welfare6-SplurgeComp.tex`, `Multiplier_SplurgeComp.tex`): regenerate the splurge=0 vs splurge model under the same method so their "(with splurge)" column matches the new main tables, **or** document them as a frozen separate-run comparison with a NOTE clarifying provenance. (Today the main `welfare6` with-splurge = 1.00 but `welfare6-SplurgeComp` with-splurge = 0.85 — they must be reconciled or explicitly explained.)
5. **Gate:** confirm with CDC that the regenerated `CRRA2/` numbers are the blessed, QE-superseding set. If not blessed, stop here and record the pending items; do not edit prose.

### Phase 1 — Complete reconciliation matrix
Build a table with one row per numeric claim: `claim | location (file:line) | QE value (qe2442.tex) | current-repo-table value | regenerated-canonical value | source file | status (match / drift / narrative) | action`.
- Enumerate **all** prose numbers, not just the sampled ones: every multiplier mention (check **and** UI **and** taxcut), every welfare row/cell reference, every share/%/NPV, the splurge values, the "1.8 dollars" / "close to one" qualitative claims (verify the qualitative direction still holds under new numbers).
- Include every **table NOTE** (welfare6, Multiplier, welfare6-SplurgeComp, Multiplier-SplurgeComp, Comparison-Splurge) — NOTEs are prose and must match their own regenerated cells.
- Cross-table: main `welfare6` ⇄ `welfare6-SplurgeComp` "(with splurge)"; `MPC_WQ` Model row ⇄ `Comparison-Splurge` "Splurge≥0" row (off by 0.01 — confirm intended or reconcile).

### Phase 2 — Figure provenance & figure-derived prose
The §Impulse-responses prose quotes percentages read off the IRF figures: stimulus check "5%" / "2.5%" / "6%" (`Comparing-policies.tex:46,48,50`); UI "0.7%" / "0.3%" (`:60,62`); tax cut "2%" / "1%" / "2.3%" (`:70,72,75`).
- Determine whether `Figures/Policyrelrecession`, `Figures/cumulativemultipliers_SplurgeComp`, `Figures/HANK_IRFs`, `Figures/HANK_multipliers` (and their underlying generated PDFs under `Code/HA-Models/.../Figures/`) were regenerated on this branch (git log the included graphics).
- If regenerated, verify each quoted percentage still matches the plotted curve (read the figure data/PDF). Add any drift to the matrix.

### Phase 3 — Coordinated prose/NOTE update (only after Phase 0 gate passes)
Apply, in clearly-scoped commits (one logical group each), the changes the matrix marks "drift" or "narrative":
- Prose numbers in `Comparing-policies.tex` (A1–A3) → regenerated values.
- Rewrite the UI-normal-times welfare paragraph `Comparing-policies.tex:172–174` (A4) to the new reality (if UI `Rec=0`≈1.00: "all three policies are close to one in normal times, as expected for marginal policies," and drop the concavity explanation — exact wording per CDC).
- Table NOTEs to match their regenerated cells.
- Harmonize the splurge display (B1) to one value across `Parameterization.tex:55,102`, `Figures/splurge_estimation.tex:34`, Table 3.
- Any figure-derived percentages flagged in Phase 2.
**Frozen-results discipline:** never edit a generated table cell by hand; change prose to match the (regenerated) table, or regenerate the table — never the reverse.

### Phase 4 — Re-verify
- Rebuild `HAFiscal.pdf` (`latexmk -pdf HAFiscal.tex`).
- Re-run the substantive-review checks: pair every prose number with its rendered table value; confirm zero "??"; confirm the qualitative narrative (policy ranking, "UI is the bang-for-buck winner") still reads correctly with the new numbers.
- Confirm internal coherence across the now-updated set (main vs SplurgeComp tables; NOTE vs cells).

### Phase 5 — Provenance & close-out
- Update `PROVENANCE.md` and a dated `conclusions_private/` note: the paper now reports the validated TM-AD/MC numbers, **intentionally superseding** the QE-published values; list the superseded→new deltas. This makes future QE-vs-repo diffs expected-to-differ on these cells (so the next proof-compatibility pass adds them to its documented-exclusions with a pointer here).
- Flip this plan's `**Status:**` to `DONE` and update the `plans/INDEX.md` row.

---

## 4. Acceptance criteria
- Freshly regenerated `CRRA2/Multiplier.tex` & `welfare6.tex` exist, are confirmed blessed by CDC, and are the reference for all prose.
- Reconciliation matrix complete; every row is `match` or has an applied action.
- `HAFiscal.pdf` rebuilds; no prose number contradicts its table; A4 narrative true; zero "??".
- `welfare6` ⇄ `welfare6-SplurgeComp` consistency resolved (reconciled or documented).
- Provenance recorded; QE-supersession documented; INDEX updated.

## 5. Key references
- `conclusions_private/20260611_final-substantive-review.md` — full findings (§A drifts, §D cleared non-issues, §E why-the-sync-missed-it).
- `conclusions_private/2026-06-10_welfare_method_unified_MC.md` — canonical welfare method + flags.
- `plans/20260610_master-QE-proof-compatibility_plan.md` — the sync that excluded these numbers (l.40–50, 143).
- `CLAUDE.md` §"Canonical solution approach (Plan A, 2026-06-10)" — env defaults; do_all Step 5a/5b roles.
- `Code/HA-Models/README.md` — canonical pipeline (steps, runtimes, outputs).
- QE reference source: `/tmp/skylatex_src/qe2442.tex` (Table 6 l.1808–1812; Table 7 l.1982–1987; prose l.1827–1834, 1998).
- Memory: `project_tm_vs_mc_validation` (updated 2026-06-11 with this drift); `project_dev_on_econ_mw` (run heavy regen there).

## 6. Risks / notes
- Do **not** reconcile prose to the 2026-05-16 `welfare6.tex` if Phase 0 shows the blessed method yields different numbers — that would freeze prose to an intermediate.
- The QE↔repo prose mismatch is tiny and pre-existing (QE prose 1.234 vs QE table 1.228); the new canonical numbers will differ from *both*. Reconcile prose to the **new** numbers, not to QE.
- Heavy regeneration belongs on `econ-mw`; the local mac session is for the document-side reconciliation/edits and verification.
