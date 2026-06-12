# Documentation rationalization — overview (umbrella for 4 plans)

**Status:** ACTIVE

**Date:** 2026-06-11
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (the canonical integration target — see `plans/20260610_integration-target-TM-vs-MC.md`)
**Premise:** The computational codebase has become hard to understand. Exploration (3 parallel agents, 2026-06-11) found the two dominant obstacles: (1) **130 `HAFISCAL_*` env flags, 94% undocumented**; (2) **file sprawl** — 278 .py in `FromPandemicCode/` of which ~13 are production core, with duplicate families (7+ welfare6 variants, 63+ jax_mc_*, 19 phase*) and no manifest saying which member is canonical. Secondary: pipeline docs duplicated in ≥5 places with drift; ~119 untagged `plans/`; stale/contradicted code comments.
**Scope:** codebase only — never `.tex` / paper materials.

## The four plans

| plan | scope | risk |
|---|---|---|
| `20260611_env-flag-registry.md` | Single-source registry of all 130 flags + permanent guard pytest | low |
| `20260611_docs-dedup-and-navigation.md` | Pipeline single-source-of-truth; stale root-md → `history/`; `plans/INDEX.md`; CLAUDE.md documentation map | low |
| `20260611_family-manifests-and-archival-sweep.md` | `FILE_FAMILIES.md` manifest (which file is production/live/closed); **Tier-1-certain** moves only | manifest zero-risk; moves gated |
| `20260611_code-comment-hygiene.md` | Stale/contradicted comment fixes, comment-only-proven (AST gate); contradictions → owner triage | medium→low (AST gate) |

**Recommended order:** env-flag-registry ∥ docs-dedup first (purely additive; they create the reference targets the others point at) → family-manifests → comment-hygiene (over the then-smaller live set). **Any order is legal** — each plan is standalone; the only interactions: (i) family-manifest moves flip registry entries to `archived-only` (re-run the guard test as that plan's final step); (ii) comment-hygiene compresses flag-comment blocks to registry pointers only if the registry exists.

## OWNER PRE-AUTHORIZATION (2026-06-11) — Mandate 1 executes UNATTENDED under these rulings

1. **Branch (owner-refined 2026-06-11):** execute on side branch
   **`0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_doc-rationalization`** — the name deliberately
   embeds the parent's name + a purpose suffix (same convention as `…_TM-vs-MC_permgrofac-reestimation`)
   so no session can mistake the lineage.
   - **Creation MUST be explicitly from the parent, never master:**
     `git fetch origin && git checkout -b 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_doc-rationalization origin/0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
   - **Verify the branch point before any work:**
     `git merge-base --is-ancestor origin/0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC HEAD && echo PARENT-OK`
     plus `git log --oneline -1 origin/0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` == the branch's base. Abort if not.
   - **Merge-back is a GATE, not automatic:** at completion, ASK the owner whether to merge into
     `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (the ONLY merge target — NEVER master, NEVER
     `0.14.1-to-0.17.0-upgrade-validation`; see plans/20260610_integration-target-TM-vs-MC.md).
     Rebase the side branch onto the parent before the ask if the parent has advanced.
2. **Archival:** trust-the-bar — Tier-1 quadruple-bar .py moves happen without per-list review (gates logged in the manifest; one revertible commit per batch); doc-consumer-grep hits auto-keep; HARVEST-flagged files stay.
3. **Root-md:** session debris only (HANDOFF*, session_starter_*); external-user test mandatory; agenda/TODO audited (done/open/superseded) + a DRAFT updated agenda produced; ARCHITECTURE.md refreshed-and-kept as the human-facing navigation doc.
4. **Trim license:** granted — duplicated detail replaced by pointers after merging into the canonical README.
5. **Comment hygiene:** the four pre-approved actions (UI rewrite, tm_a_indexed rewrite, GICx re-derive+stamp, docstring backfill on the NAMED entry points only — other gaps counted in findings, not filled); anything new = log-only.
6. **Defaults:** ambiguous flags → `diagnostic`+`Needs-owner-review`; INDEX ambiguity → `RECORD?`; conflicting old facts → both recorded with dates; archive destinations per established pattern; BUG-050 stays a logged OPEN item (never touched); safe to run alongside the Baseline welfare chain.

## Shared execution contract (binding on all four)

1. **Standalone + idempotent:** each plan leaves the repo working; safe to re-run; one revertible commit per batch.
2. **Green acceptance gate per plan:** `pytest Code/ reproduce/ -m "not slow" -q` green + `bash reproduce_min.sh` smoke at plan completion.
3. **Documentation-only hard rule:** these plans change docs and comments, never behavior. Any discovered *behavior question* (e.g. a comment contradicting a decided default) goes to `Code/HA-Models/docs/COMMENT_AUDIT_FINDINGS.md` for owner triage — never a silent fix.
4. **Multi-agent execution:** phases are decomposed into parallel agent tasks with disjoint write-sets. The only shared file is `CLAUDE.md`; every CLAUDE.md edit is a marked idempotent insert ("add line X under section Y if absent").

## Archival policy (owner-decided 2026-06-11) — binding

**Certainty-tiered, harvest-first.** Don't move a file until certain it's redundant/useless; certainty mostly arrives at execution time.
- **Tier 1 (movable during plan execution):** quadruple bar — (a) explicitly superseded by a documented decision OR pure iteration-history with a named successor; (b) zero reverse imports incl. tests; (c) zero active-doc references; (d) no unique technique worth harvesting. Stale root **markdown** is Tier-1-eligible (prose; zero import risk; same doc-consumer grep gate).
- **Tier 2 (default — everything else):** stays in place; the manifest records role + evidence + a **preservation-value note** (does it embody a technique/result worth lifting into working tools?). Moves deferred to a future decision.
- **Harvest step:** anything flagged valuable is extracted into working tools/docs before any future move.

## New artifacts created across the four plans

- `Code/HA-Models/docs/` (new dir): `ENV_FLAGS.md`, `FILE_FAMILIES.md`, `COMMENT_AUDIT_FINDINGS.md`
- `Code/HA-Models/test_env_flag_registry.py` (guard pytest; new .py here is allowed — the no-new-files rule applies to `FromPandemicCode/` only)
- `plans/INDEX.md`
- CLAUDE.md "Documentation map" section (which file owns which facts)

## Verification (umbrella)

After all four: `pytest Code/ reproduce/ -q` green; `bash reproduce_min.sh` green; `python Code/HA-Models/compare_result_pickles.py <archived-affected-results-dir-if-any> <Results_canonical equivalent>` where applicable; `git log --oneline` shows one-commit-per-batch revertibility.
