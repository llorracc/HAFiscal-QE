# Freeze QE numbers as source-of-truth; candidate-suffix regeneration + git-native lock

**Status:** DONE — authored 2026-06-11, executed 2026-06-11/12. **Phase 1 DONE** (deliverable: `conclusions_private/20260611_qe-vs-repo-numeric-diff.md`). **Phase 2 DONE** (infra built + validated). **Phase-1 gate resolved 2026-06-12** (CDC judgments: copy QE bytes for the 6 metadata-only HANK figures; candidate-suffix intermediates AND non-rendered tables; full revert scope approved). **Phase 3 DONE** (baseline locked to `HAFiscal-QE@5aa25fb`; 45-file `LOCKED_TABLES.manifest`; `HAFiscal.pdf` rebuilt with QE values, zero unresolved refs; commits `12f06cc3`, `cb7871ea`, `b1c9e6c8`). **Phase 4 DONE** (workflow documented in `Code/HA-Models/README.md` + `CLAUDE.md`; INDEX updated). Supersedes the *direction* of `20260611_complete-numbers-reconciliation-vs-regenerated-tables_plan.md` (which assumed prose should be updated to the regenerated tables; CDC has decided the **QE proof is the source of truth** instead). That plan's diff-enumeration work feeds Phase 1 here; its coordinated prose update is deferred to the eventual "promote" step.

## TL;DR
The validation branch has a **whole re-estimated family of result numbers** checked in that differ from the QE-published values, and the paper prose still matches QE. CDC's decision: **QE numbers are the source of truth**; freeze them; make the in-progress codebase write **`_candidate` siblings** instead of clobbering the frozen files; protect the frozen files with a **git-native lock**; and substitute the new numbers only via a **deliberate, reviewed promote** when the revised codebase is complete. This plan designs that system and the gated revert-to-QE baseline. **No result file is touched until CDC approves the full diff (Phase 1).**

---

## 1. Motivation

### 1a. Results — the drift is a re-estimation, not two tables
Comparing **values** (formatting ignored) of the current repo against the faithful QE source (`/Volumes/Sync/GitHub/llorracc/HAFiscal-QE`, whose `Multiplier.tex` = 0.878/1.228/1.153, 73.6% — identical to the `qe2442.tex` proof), the **discount-factor estimates themselves changed**, and the change cascades:

| artifact | QE (truth) | current repo |
|---|---|---|
| `CRRA2/estimBetas.ltx` (β,∇) D/H/C | (0.719,0.318)/(0.929,0.072)/(0.983,0.014) | (0.663,0.384)/(0.900,0.107)/(0.978,0.025) |
| `CRRA2/nonTargetedMoments.ltx` (model wealth shares) | 1.2/17.5/81.3 | 1.1/15.5/83.3 |
| `…/Target_AggMPCX_LiquWealth/Figures/MPC_WealthQuartiles_Table.tex` | 0.60/0.66/6.58 … | 0.59/0.65/6.59 … |
| `Tables/Comparison_Splurge_Table.tex` (hardcoded) | (splurge MPCs differ) | — |
| `CRRA2/Multiplier.tex` | 0.878/1.228/…, 73.6% | 0.936/1.143/…, 72.1% |
| `CRRA2/welfare6.tex` | 0.96/0.85/0.99 … | 0.99/1.00/0.99 … |
| generated **figures** (LorenzPts, splurge fit, IRFs, …) | QE plots | likely re-plotted — **inventory in Phase 1** |

**Unchanged from QE** (no number drift): `calibration`, `calibrationRecession`, `Splurge0/welfare6-SplurgeComp`, `Splurge0/Multiplier_SplurgeComp`, HANK `tabular/Calibration.ltx`.

Source of the drift: the discount factors were re-estimated on this branch (cf. `prompts_local/20260609-1120h_followup-bug053-gpf-shave-reestimation.md`), plus the TM-AD multiplier regen (2026-04, `e17193da`) and the BUG-046/043 Jensen welfare regen (2026-05, `516fc12f`).

### 1b. Why the substantive review caught only 2 of 6
The prose *quotes* the multiplier (1.234) and the welfare narrative ("UI noticeably less than one"), so those showed up as prose⇄table contradictions. The prose **never restates** the β estimates, the non-targeted moments, or the MPC-quartile cells — it just points at the tables — so an internal prose⇄table coherence check finds nothing wrong. **Only a comparison against an external source-of-truth (QE) reveals them.** This is the core justification for this system: a coherence review cannot police numbers the prose doesn't repeat; a frozen QE baseline + lock can.

### 1c. Why the candidate-suffix scheme
The 2026-04/2026-05 regenerations silently overwrote the canonical generated files (multiple `open(...,'w')` sites). If regeneration instead writes `_candidate` siblings and the build reads frozen by default, accidental clobbering becomes **structurally impossible**, and truth-vs-regenerated diffs become trivial. The frozen numbers only change through a deliberate, reviewed promote.

---

## 2. Design decisions (settled with CDC 2026-06-11)
1. **Build default = frozen; candidate via flag.** `\fetchgeneratedtabular` reads the frozen QE-truth file by default; a build flag makes it read the `_candidate` sibling for a preview PDF. ⇒ **read-side is one macro change; build scripts/wrappers/`latexmk` untouched.**
2. **Central write helper** for the generators (route the ~8 `open(...,'w')` sites through it).
3. **Figures get the same** freeze + candidate-suffix treatment as tables.
4. **Git-native enforcement** (SHA-256 manifest + pre-commit reject + pytest) — **no `chmod`.**
5. **Revert held:** produce the full QE-vs-repo value diff first; touch no result file until CDC approves.

---

## 3. Architecture

### 3a. File roles
- **Wrapper** (hand-maintained; `Tables/*.tex`, `Figures/*.tex`): calls `\fetchgeneratedtabular{<generated>}`. Unchanged except the macro it calls is upgraded.
- **Frozen/canonical generated file** (the truth, locked): e.g. `…/CRRA2/welfare6.tex`. Read by default; = QE values after Phase 3.
- **Candidate generated file** (transient): e.g. `…/CRRA2/welfare6_candidate.tex`. Written by the in-progress codebase; **gitignored**; read only under the build flag.

### 3b. Read-side — one macro (LaTeX-native, no shell-escape)
Upgrade `\fetchgeneratedtabular` (in the resources/`subfile-setup` `.ltx` that defines it) to:
```
\newif\ifusecandidatetables \usecandidatetablesfalse
% optional, gitignored: @local/use-candidate-tables.ltx sets \usecandidatetablestrue
\IfFileExists{\latexroot/@local/use-candidate-tables.ltx}{\input{...}}{}
\newcommand{\fetchgeneratedtabular}[1]{%
  \ifusecandidatetables
    \edef\@cand{<dir>/<base>_candidate.<ext> from #1}%
    \IfFileExists{\@cand}{\input{\@cand}}{\input{#1}}%   % fall back to frozen
  \else \input{#1}\fi}
```
- Official `HAFiscal.pdf`: nothing set ⇒ reads frozen. To preview candidates: `make pdf-candidate` creates `@local/use-candidate-tables.ltx` (gitignored), builds, then removes it. (Equivalent figure handling: a `\frozenORcandidate{<path>}` helper for `\includegraphics`.)

### 3c. Write-side — central helper
New module `Code/HA-Models/FromPandemicCode/generated_output.py`:
- `write_generated(canonical_path, content)` → writes `canonical_path` with `_candidate` inserted before the extension, **never** the canonical, unless `HAFISCAL_PROMOTE=1`.
- `save_generated_figure(canonical_path, fig/bytes)` → same policy for PDFs/PNGs.
- Refactor the writer sites to call it: `Output_Results.py:475`, `Welfare.py:323`, `run_welfare6_parallel.py:608`, `run_hybrid_welfare6.py:483`, `welfare6_hybrid_table.py`, `estimBetas_tabular_generate.py:180`, `nonTargetedMoments_tabular_generate.py:190`, the MPC-table generator, and the figure savers. (Inventory the full set in Phase 1 — there may be a few more.)
- Net: a normal `do_all`/pipeline run emits `_candidate` files and cannot clobber frozen truth.

### 3d. Lock — git-native
- `LOCKED_TABLES.manifest` (git-tracked): one row per frozen file — `path  sha256  lock-date  qe-source-rev  reason`. Captures the QE numbers **durably** (the HAFiscal-QE repo is ephemeral per memory).
- **Pre-commit hook** (extend the existing `pre-commit`): reject a commit that stages a manifest-listed frozen file whose new hash ≠ the manifest hash, unless `HAFISCAL_UNLOCK=1` **and** the manifest row is updated in the same commit.
- **`test_locked_tables.py`** (pytest/CI): assert each frozen file's current hash == manifest hash (catches working-tree drift before commit). Model on the existing `Code/HA-Models/welfare6_tm_vs_mc_guard_test.py` and `reproduce/build_manifest.py`.
- `.gitignore`: `*_candidate.tex`, `*_candidate.ltx`, `*_candidate.pdf`, `*_candidate.png`, `@local/use-candidate-tables.ltx`.

### 3e. Promote — the deliberate substitution
`promote_candidates.py` (`make promote-tables`): for each frozen file with a `_candidate` sibling — show the value diff (frozen vs candidate), require confirmation, copy candidate→frozen, recompute + update the manifest row (new date/rev/reason), and **flag every wrapper NOTE and prose line that quotes a changed cell** (so prose is re-coordinated in the same reviewed commit). Run under `HAFISCAL_UNLOCK=1`. This is the one-and-only path that changes the paper's numbers, and it forces the prose/NOTE coherence step that was missed in 2026-04/05.

---

## 4. Frozen-file inventory ("everything numeric")
- **Generated tabulars (candidate scheme + lock):** `CRRA2/{Multiplier.tex, welfare6.tex, estimBetas.ltx, nonTargetedMoments.ltx}`, `Splurge0/{welfare6-SplurgeComp.tex, Multiplier_SplurgeComp.tex}`, `Target_AggMPCX_LiquWealth/Figures/MPC_WealthQuartiles_Table.tex`, HANK `tabular/Calibration.ltx`.
- **Generated figures (candidate scheme + lock):** the `\includegraphics` targets under `Code/HA-Models/.../Figures/` — **enumerate in Phase 1** (LorenzPts, splurge_estimation, untargetedMoments, Policyrelrecession, cumulative multipliers, HANK IRFs/multipliers, splurge0/LorenzPtsSplZero/robustness_CRRA, etc.).
- **Hardcoded wrappers with numbers (lock-only — NOT generated, so no `_candidate`):** `Tables/{calibration, calibrationRecession, Comparison_Splurge_Table, Multiplier_SplurgeComp, nonTargetedMoments_wSplZero}.tex`, and any table NOTE that quotes cell values (welfare6/Multiplier/etc.). These change only by hand-edit; the lock makes that deliberate.

---

## 5. Phases

### Phase 1 — Full diff report + inventory (NO file changes) → **CDC gate**
- Produce `conclusions_private/<date>_qe-vs-repo-numeric-diff.md`: every numeric artifact (tables + figures), QE value vs repo value, drift/same, formatting-only vs value, and for figures a hash/visual comparison.
- Inventory all code-generated outputs (the writer sites + `\includegraphics`/`\fetchgeneratedtabular` targets) → the provisional frozen-file list.
- Inventory **other generated numeric inputs** (numbers `\input`/`\newcommand`'d into prose from a generated file, if any) and present each to CDC for a per-item judgment (full candidate+lock / lock-only / leave alone).
- **Gate:** CDC reviews the diff + inventory, makes the per-item judgments, and confirms the QE-baseline reversion scope (especially the discount-factor revert) before Phase 3.

### Phase 2 — Build the lock + candidate infrastructure (no number changes)
- `generated_output.py` helper + refactor the writer sites.
- Upgrade `\fetchgeneratedtabular` (read-side) + the figure include helper + `make pdf-candidate`.
- `LOCKED_TABLES.manifest`, pre-commit hook extension, `test_locked_tables.py`, `.gitignore` entries, `promote_candidates.py`/`make promote-tables`.
- Validate on a scratch file: a regen run writes `_candidate`, frozen untouched; pre-commit rejects a frozen edit; `make pdf-candidate` reads candidates.

### Phase 3 — Establish the QE baseline (gated on Phase 1) — revert + populate manifest
- Set frozen generated tabulars = QE: copy from HAFiscal-QE where format matches; for the hardcoded `Comparison_Splurge_Table.tex`, a **numbers-only** revert preserving branch cosmetics. Revert drifted figures from QE.
- Populate `LOCKED_TABLES.manifest` with the QE-baseline hashes + provenance (HAFiscal-QE rev / `qe2442` proof).
- Rebuild `HAFiscal.pdf`: confirm it now matches QE numbers and is internally coherent with the (QE-faithful) prose; zero "??".
- Commit as the locked baseline (under `HAFISCAL_UNLOCK=1`).

### Phase 4 — Docs + close-out
- Document the workflow (how to preview candidates, how to promote, how to unlock) in `Code/HA-Models/README.md` + `CLAUDE.md` map.
- Update `plans/INDEX.md`; flip this plan to DONE; mark the prior reconciliation plan SUPERSEDED(→this).

---

## 6. Settled conventions (confirmed with CDC 2026-06-11)
- **Suffix = `_candidate`** (not `_debug`).
- **Candidates are gitignored** (transient regen outputs); review them via the Phase-1 diff report and `make pdf-candidate`.
- **Heavy candidate regeneration runs on econ-mw**; the lock/infra/promote edits + LaTeX verification are local.
- **Other generated numeric inputs** (beyond tables+figures — e.g. a number `\input` into prose from a generated `.tex`, or a `\newcommand`/macro value pulled from a generated file): **not a pre-decision.** Phase 1 *inventories* every such input; CDC then makes a **per-item judgment call, one at a time** — full candidate+lock / lock-only / leave alone. The frozen-file list (§4) is provisional until those judgments are made.

## 7. Acceptance criteria
- A normal pipeline run writes only `_candidate` files; frozen files are byte-stable; `test_locked_tables.py` green.
- `HAFiscal.pdf` (default) builds from frozen QE numbers and is coherent with prose; `make pdf-candidate` builds from candidates.
- A commit that changes a frozen file without an unlock+manifest update is rejected by pre-commit.
- `promote_candidates.py` performs a reviewed swap, updates the manifest, and flags affected prose/NOTEs.
- QE-baseline established (Phase 3) and documented; provenance recorded.

## 8. References
- **Execution prompt (self-contained handoff):** `prompts_local/20260611-1808h_execute-qe-baseline-freeze-and-candidate-lock.md`
- `conclusions_private/20260611_final-substantive-review.md` — review findings + §E (why the QE-sync deferred this).
- `20260611_complete-numbers-reconciliation-vs-regenerated-tables_plan.md` — superseded direction; diff-matrix source.
- `conclusions_private/2026-06-10_welfare_method_unified_MC.md` — canonical method (governs the *future* promote).
- QE source: `/Volumes/Sync/GitHub/llorracc/HAFiscal-QE` (faithful to `/tmp/skylatex_src/qe2442.tex`); ephemeral — capture values in the manifest.
- Existing patterns to extend: `reproduce/build_manifest.py`, `Code/HA-Models/welfare6_tm_vs_mc_guard_test.py`, the repo `pre-commit` hook, `\fetchgeneratedtabular` macro.
- Memory: `project_tm_vs_mc_validation` (drift note), `project_dev_on_econ_mw`, `project_bib_regeneration_addrefs` (QE repo ephemeral).
