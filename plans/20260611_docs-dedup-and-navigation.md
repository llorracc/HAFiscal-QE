# Docs dedup + navigation: pipeline SSOT, stale-md sweep, plans/INDEX.md, documentation map

**Status:** ACTIVE

**Date:** 2026-06-11 · **Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` · **Umbrella:** `20260611_doc-rationalization-overview.md`
**Premise:** The 5-step pipeline is documented in ≥5 places with drift (`Code/HA-Models/README.md`, `do_all.py` comments, `CLAUDE.md`, `ARCHITECTURE.md` [stale, Dec 2025], `do_all-README.md` [very stale, Mar 2024]). The repo root carries ~20 md files including dead session/handoff docs. `plans/` has ~119 files with no status tags — agents cannot tell active from historical. There is no map of which doc owns which facts.
**Execution contract:** standalone, idempotent, markdown-only (one exception: `do_all.py` comment trim, AST-gated), green gate at end.
**OWNER RULINGS (2026-06-11) — execute unattended under these:** (1) **Trim allowed** — duplicated detail may be removed where a pointer to the canonical README replaces it (unique content merged there first). (2) **External-user test is mandatory** for every sweep candidate: "is this file useful to an external user of this public repo?" — any doubt = keep. (3) **ARCHITECTURE.md = refresh-and-keep** as a first-class human-facing navigation doc (NOT a stub/banner). (4) **agenda/TODO files are live working documents** — audit items done/open/superseded, never archive while items may be open; **draft an updated agenda** from the old template for owner review.

## Phases

### Phase A — pipeline single-source-of-truth (1 agent, ~2 h)
**Winner: `Code/HA-Models/README.md`** (most detailed, closest to code, most recently maintained). Diff the five copies claim-by-claim against `do_all.py`'s actual code (steps, `HAFISCAL_RUN_STEP_{1..5,5B}` toggles, runtimes). Dispositions:
| file | disposition |
|---|---|
| `Code/HA-Models/README.md` | **Canonical.** Absorbs unique step↔table/figure mapping from `do_all-README.md`; gains "Authoritative for: pipeline steps, runtimes, outputs" banner. |
| `CLAUDE.md` | Keeps ≤10-line pipeline summary + pointer (it is agent onboarding; do NOT gut its canonical-decision content). |
| `do_all.py` | Step comments → one banner line per step + "see ../README.md §Step N" (comment-only; AST gate). |
| `ARCHITECTURE.md` | **Refresh-and-keep (owner ruling):** verify + update the directory map and narrative against reality; keep as the human-facing navigation entry point (CLAUDE.md = AI-facing); pipeline *detail* still owned by the canonical README and pointed to; add `**Last verified:**` line. |
| `do_all-README.md` | Unique content merged out, then 5-line pointer stub. **Keep the filename** (external/REMARK links). |
Factual conflicts code can't adjudicate (e.g. runtime claims) → record both with dates, or flag to owner.

### Phase B — stale root-markdown sweep (1 agent, ~1 h, ∥ with A) — REVISED per owner rulings 2026-06-11
**Move list (pure session debris only):** `HANDOFF.md`, `HANDOFF_PHASE2_RESUME.md`, `session_starter_*.md` → `history/` with date-prefix rename from `git log -1`.
**Keep + audit (live working documents):** `agenda_2026_06_03.md` (recent, items possibly open) and `TODO_HARK_0171_UPDATE.md` — classify each item done/open/superseded with evidence links (findings doc), and **draft `agenda_<today>.md`** from the old agenda as template: carried-over open items + newly-surfaced items, clearly marked DRAFT for owner edit. Old files untouched.
**Keep (external-facing):** `INTERIM_REPRODUCTION_INSTRUCTIONS.md` — reproduction docs serve external users; currency-check only (+ pointer if superseded by `reproduce/README.md`).
**Evaluate under BOTH tests (external-user + open-items), default keep:** `FromPandemicCode/CLEANUP-*.md` ×3, `MIGRATION_PLAN.md`, root `docs/`.
**Gate per move:** repo-wide `grep -rn "<oldname>"` over `*.md`, `Makefile`, `reproduce/` → fix inbound links. **Never touch:** `README.md`, `REMARK.md`, `CITATION.cff`, `README_IF_YOU_ARE_AN_AI`.

### Phase C — `plans/INDEX.md` (4 classifier agents ∥ + 1 integrator, ~3 h)
Strict table: `| file | date | status | one-liner | superseded-by/outcome |`. Status vocabulary: `ACTIVE`, `DONE`, `SUPERSEDED(→file)`, `STALLED`, `RECORD` (analysis/record docs: `*_status.md`, `*_claude-response.md`, `plans/results*`). Each classifier takes ~30 plans: read header + `git log -1 --format=%ai` + grep mentions in newer plans/conclusions. `**Status:**` headers added **only** to ACTIVE/STALLED files (~10-20) — rewriting ~100 closed historical plans is churn with no reader. Going-forward convention in the INDEX preamble: new plans carry a `**Status:**` line; whoever closes a plan updates INDEX.md. Classification uncertainty → `RECORD?`, never guessed.

### Phase D — CLAUDE.md documentation map (1 agent, ~30 min, after A-C)
Insert ownership map: pipeline → `Code/HA-Models/README.md`; env flags → `Code/HA-Models/docs/ENV_FLAGS.md`; file families → `docs/FILE_FAMILIES.md`; plan status → `plans/INDEX.md`; bug status → `BUGS_private/`; methodology decisions → `conclusions_private/`; model spec → `HAFiscal-doloplus-draft.yaml` + `HAFiscal-bellman-for-matsya.md` (+ orchestrator spec when it exists). Verify CLAUDE.md's pipeline summary is ≤10 lines + pointer.

## Verification

```
# every moved filename: only history/ + INDEX hits remain
for f in <moved>; do grep -rn "$f" --include="*.md" --include="Makefile" . | grep -v history/ | grep -v INDEX; done   # empty
pytest Code/ reproduce/ --collect-only -q       # unchanged (md-only; do_all.py via AST gate)
python -c "<AST comment-only gate>" Code/HA-Models/do_all.py
test $(ls plans/*.md | wc -l) -eq $(grep -c '^|' plans/INDEX.md status-rows)   # INDEX covers all
```

## Risks / rollback

External links to `do_all-README.md` → kept as stub, never deleted. Misclassified status → INDEX is cheap to amend. Rollback: `git mv` back; all md. **Effort:** ~6-9 agent-hours (Phase C is the long pole, parallelized). **Risk: low.**
