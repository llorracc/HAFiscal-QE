# Reorganize `BUGS_private/HAFiscal_splurge_budget_inconsistency/` for the coauthor email

**Created:** 2026-04-18
**Goal:** Produce a short, self-contained, up-to-date set of documents in the splurge-bug directory that can be pointed to in an email to coauthors (Edmund, Håkon, Ivan) without burying them in layers of now-superseded drafts, partial results, or historical working notes.

## Starting state (2026-04-18)

~200 KB across 20 markdown / Python / JSON / notebook files, accumulated over the April 14-18 investigation. Several files overlap in content; several contain claims that were later revised or withdrawn. A coauthor opening the directory today would not know which doc is current and which is superseded.

```
README.md                                        29 KB   original long bug report (pre-distillation)
distilled-summary.md                             13 KB   CURRENT primary reference
what-to-do.md                                     9 KB   CURRENT decision doc (option a recommendation)
baseline-crra2-bugfix-vs-qe.md                   21 KB   CURRENT results + bisection + attribution
bound-pair-assessment.md                         10 KB   rebuttal of Edmund's alt-reading
bound-pair-interpretation.md                      4 KB   Edmund's alt-reading (historical)
bound-pair-interpretation_response.ipynb         42 KB   response notebook
splurge-accounting.md                            11 KB   earlier summary (superseded by distilled-summary)
splurge-accounting_math-and-code.ipynb           37 KB   math derivations + MWE
splurge-accounting-preliminary-MC-results.md     10 KB   preliminary MC results (superseded)
complete_qe_vs_splurge-in-budget.md               7 KB   older comparison tables
overnight_comparison_report.md                    7 KB   email draft (historical)
overnight_comparison_report_splurge-in-budget.md 7 KB   overnight run report (historical)
welfare_quick_preview_results.md                  8 KB   preview diagnostic (historical)
welfare_quick_preview_*.json                     ~7 KB   diagnostic outputs
welfare_quick_preview_hs_only.py                 20 KB   diagnostic script
welfare_quick_parallel.py                         4 KB   diagnostic script
mwe_clean_example.py                              3 KB   MWE
verify_budget_identity.py                         8 KB   cross-sectional verification
email/                                                  actual email thread (historical)
```

## Target state

A directory a coauthor can open and find six files, in this order of priority:

```
README.md                          ~3 KB   index / roadmap — what each file is and when to read it
distilled-summary.md               ~8 KB   the bug, the fix, and why it matters (the main read)
what-to-do.md                      ~6 KB   the recommendation and the options table
results.md                         ~8 KB   headline multiplier + welfare numbers, vs QE
bound-pair-assessment.md           ~6 KB   rebuttal of the alt-reading, kept for skeptics
mwe.py                             ~3 KB   runnable minimum working example
email/                                     the thread, as-is
_archive/                                  everything superseded, moved here verbatim
```

Everything not in the six-file list moves to `_archive/` — nothing is deleted, but nothing in the top level is stale either. Total top-level content goes from ~200 KB to ~35 KB.

## Per-file disposition

### Keep at top level (edit down to size)

1. **`README.md`** — rewrite from scratch as a short index. ~3 KB target. Content: one-paragraph summary of the bug, a numbered reading list (distilled-summary → what-to-do → results → bound-pair-assessment, with one-line descriptions), and a pointer to `_archive/` for historical material.
2. **`distilled-summary.md`** — already current as of 2026-04-18. Trim if possible. Tighten §3 (bound-pair section) to remove any residual detail that duplicates `bound-pair-assessment.md`. Target: ~8 KB (currently 13 KB).
3. **`what-to-do.md`** — already current, already has the table and the advocacy. Minor clean-up only. Target: ~6 KB (currently 9 KB).
4. **`results.md`** (new, replaces `baseline-crra2-bugfix-vs-qe.md`) — shorter version. Keep the headline multiplier and welfare-6 tables (§1, §4 of the current file). Keep §2, §6, §8 (the "what changes," "what survives," and "summary"). **Cut** §3 (`Source of the drift` — prose conjecture), §4.1 and §4.1.1 / §4.1.2 (bisection attribution — this is preserved in the upstream fork and breadcrumb, not needed in the coauthor-facing doc), §5 (calibration-target minutiae), §7 (internal task list). Rename `baseline-crra2-bugfix-vs-qe.md` → `results.md` on the way out. Target: ~8 KB (currently 21 KB).
5. **`bound-pair-assessment.md`** — already current. Retain as the defensive doc Edmund's objections would be answered with. Content should flow: state Edmund's position, state ours, give the three tests with the Test 3 caveat already added, conclude. Target: ~6 KB (currently 10 KB).
6. **`mwe.py`** — rename `mwe_clean_example.py` → `mwe.py`. Keep as-is; it is the runnable proof of the budget-identity violation.

### Move to `_archive/` (no content edits)

- `README.md` (the current long version) → `_archive/original-bug-report.md` before it is replaced by the new index.
- `splurge-accounting.md` → `_archive/` (superseded by distilled-summary).
- `splurge-accounting_math-and-code.ipynb` → `_archive/` (if the math derivations it contains are not already in distilled-summary or the assessment, extract the one or two load-bearing claims into distilled-summary §1 or §4 first, then archive).
- `splurge-accounting-preliminary-MC-results.md` → `_archive/` (superseded by the final results).
- `complete_qe_vs_splurge-in-budget.md` → `_archive/` (older comparison tables, content now in results.md).
- `overnight_comparison_report.md`, `overnight_comparison_report_splurge-in-budget.md` → `_archive/` (historical campaign outputs).
- `welfare_quick_preview_results.md`, all `welfare_quick_preview_*.json`, `welfare_quick_preview_hs_only.py`, `welfare_quick_parallel.py` → `_archive/` (scratch diagnostics).
- `bound-pair-interpretation.md` → `_archive/` (Edmund's original position; his current position is captured in the assessment's §"The two interpretations, stated precisely").
- `bound-pair-interpretation_response.ipynb` → `_archive/` (the notebook form of the assessment; the concise version is `bound-pair-assessment.md`).
- `verify_budget_identity.py` → `_archive/` (5000-agent cross-sectional verification; not needed in the coauthor-facing flow because `mwe.py` makes the same point in 30 lines).

### Leave as-is

- `email/` — historical thread, do not edit.

## Content edits required

Beyond the relocation, these content changes are needed to purge stale claims:

1. **distilled-summary.md §3** — already revised (Lorenz and Welfare bullets removed, internal-inconsistency framing added). Verify once more on the reorganization pass; in particular, the closing sentence of the sanity check still references "Option D" accounting — check the rename carried through.
2. **distilled-summary.md §5 preamble** — the "Baseline CRRA2 multipliers and welfare-6" bullet now has a table. Verify the surrounding bullets are consistent (no stale "primarily splurge" or "primarily ς re-estimation" claims remain; the ς-isolation finding stands at +0.3 %; check).
3. **what-to-do.md preamble** — already revised; advocacy paragraph and table are current; no stale attribution claim remains. Verify on the pass.
4. **`results.md` (from baseline-crra2-bugfix-vs-qe.md)** — after the §-cuts, re-read the trimmed doc end-to-end to make sure the narrative still closes: the bug, the fix, the re-estimation, the numbers, what survives, what changes. Rewrite intro paragraph to stand alone.
5. **bound-pair-assessment.md** — the Test 3 caveat (added 2026-04-18) stays. Verify the Test 2 (Lorenz) claim is internally consistent with the distilled-summary's revised view (the Lorenz bullet was removed from distilled-summary because the pair-wealth aggregation is ambiguous; the assessment's Test 2 also rests on an atom-at-zero argument that needs the same qualification). Either (a) keep Test 2 with a similar caveat, or (b) remove Test 2 and keep Tests 1 and 3 plus the internal-inconsistency argument.
6. **New README.md** — write from scratch. Structure: 1-paragraph summary of the bug; 1-paragraph "what is settled"; numbered reading list; pointer to `_archive/` with one-line explanation of why things are archived.

## Sequencing

Execute in this order to keep the working directory coherent at each checkpoint:

1. `mkdir BUGS_private/HAFiscal_splurge_budget_inconsistency/_archive/`.
2. Move all files listed for archival into `_archive/` with `git mv` (preserves history).
3. Rename `mwe_clean_example.py` → `mwe.py` and `baseline-crra2-bugfix-vs-qe.md` → `results.md` with `git mv`.
4. Trim `results.md` per §-cut list.
5. Trim `distilled-summary.md` and `what-to-do.md` per verification list.
6. Apply Lorenz-bullet reconciliation in `bound-pair-assessment.md`.
7. Write the new `README.md` as a short index.
8. Final read-through: open the six top-level files in order, read the whole thing, check that a cold reader (coauthor who hasn't been in the thread) can follow from README → distilled-summary → results → what-to-do → assessment without needing anything from `_archive/`.
9. Commit, push, sync fork.

Estimated compute: 0. Estimated wall time: ~1-2 hours of careful editing.

## Acceptance criteria

- Top level contains ≤ 6 .md/.py files plus `email/` and `_archive/`.
- Every top-level file's content reflects the 2026-04-18 state (no withdrawn claims, no stale attribution).
- A coauthor reading top-level-only gets: what the bug is, what the fix is, what the numbers are, what to do.
- `_archive/` preserves every file currently in the directory (nothing deleted).
- No broken cross-references (intra-directory links updated for the rename of `baseline-crra2-bugfix-vs-qe.md` → `results.md`).

## Non-goals

- Do not rewrite `email/*` contents.
- Do not touch the fork (`llorracc/HAFiscal-welfare-drop-investigation`) — its welfare-drop-investigation branch is separate; only the mirror branch `parent-branch-state` will pick up this reorganization automatically on the next sync.
- Do not change the underlying analysis; this is a documentation cleanup only. Any factual updates needed are limited to purging claims that were explicitly withdrawn in earlier edits today.
