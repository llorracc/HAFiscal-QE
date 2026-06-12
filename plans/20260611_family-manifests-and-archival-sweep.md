# File-family manifests + certainty-tiered archival sweep

**Status:** ACTIVE

**Date:** 2026-06-11 · **Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` · **Umbrella:** `20260611_doc-rationalization-overview.md`
**Premise:** `FromPandemicCode/` holds 278 .py files; ~13 are production core. Duplicate families have no manifest: welfare6 (7 entry points + 6 joint5d variants), jax_mc_* (63+, incl. `diagnose1..8` iteration history), phase* (19), harmenberg (mostly archived; `harmenberg_doob_tier1{,_esc}.py` are LIVE, imported by phase2/4), diag_/run_/bench_ singletons. A reviewer cannot tell canonical from exploratory. Precedent: `Code/HA-Models/{diagnostics_archive (74, verified 0 external imports), welfare6_diagnostics_archive (22), hark_migration_archive (18)}`, each with a README.
**Owner policy (2026-06-11, binding):** **certainty-tiered, harvest-first** — see the umbrella plan. Tier-1 moves only; Tier-2 stays, classified with preservation-value notes; harvest before any future move.
**OWNER RULING (2026-06-11): trust-the-bar.** Files passing the full quadruple bar move UNATTENDED (no per-list owner review); the manifest logs the gates per move; one revertible commit per batch. Doc-consumer-grep hits auto-demote to keep (no escalation); HARVEST-flagged files stay Tier-2 this round.
**Execution contract:** standalone, idempotent; Phase 0 is zero-risk and **the plan explicitly authorizes stopping after Phase 0/1 with full value**.

## Phases

### Phase 0 — the manifest (3 agents ∥ by family, ~3 h). Deliverable stands alone.
New `Code/HA-Models/docs/FILE_FAMILIES.md`: per family, list members with:
- **role** ∈ {production, live-support, closed-candidate, unknown} — production claims MUST cite evidence; `unknown` is allowed.
- **evidence**: who imports it (incl. tests) / which conclusion-doc, CLAUDE.md line, or do_all step reaches it / git-recency.
- **preservation-value note** (owner requirement): does the file embody a unique technique/result worth lifting into working tools or docs? (e.g. a clever comparison harness, a variance-reduction trick). Anything non-trivially unique → flagged `HARVEST`.

Seed knowledge (verify, don't trust): welfare6 production = `welfare6_scenario.py` (MC canonical) + `welfare6_tm.py`/`welfare6_tm_aggregate.py` + `welfare6_tm_joint5d{,_baseline,_batch}.py` (TaxCut backup) + `welfare6_hybrid_table.py`, `welfare6_tm_make_tex.py`; the TM `bucket`/`stratified` welfare methods were DEPRECATED 2026-06-10 (`conclusions_private/2026-06-10_welfare_method_unified_MC.md`) — but deprecation ≠ archival-certainty (they back the multiplier-side and diagnostics). jax_mc production = `jax_mc_ad_multicohort.py` (per CLAUDE.md); `jax_mc_ad_bl_diagnose1..8` = iteration history (8 = final). HA-Models-level strays to classify too: `welfare6_ajpLvl_build.py`, `welfare6_jpLvl.py`, `welfare6_jensen_test.py`, `welfare6_reconcile_sweep.py`, `welfare6_check_rec_bucketed5d.py`, `welfare6_shuffle_eval.py`.

### Phase 1 — evidence confirmation (2 agents ∥, ~2 h)
For each `closed-candidate`, run the triple grep gate:
1. **Reverse-import closure** over `Code/**` *including test files* (a test importing the candidate blocks the move or moves with it).
2. **String/subprocess grep**: `grep -rn "<basename>" Code/ reproduce/ scripts/ Makefile` (catches exec/subprocess/sys.path uses).
3. **Doc-consumer grep** over `conclusions_private/`, `plans/` (ACTIVE+STALLED per INDEX), `CLAUDE.md`, all `README*` — **this is the gate whose absence caused the welfare6_aggregator_stratified archive-then-restore mistake**; any hit = demote to live-support or owner sign-off.
Output: per-batch Tier-1 lists appended to the manifest, each member annotated with its passed gates + harvest-check result.

### Phase 2 — Tier-1 moves only (1 agent per batch, sequential, ~1 h/batch)
A file moves ONLY on the quadruple bar: (a) superseded-by-documented-decision OR iteration-history-with-named-successor; (b) gate 1 clean; (c) gate 3 clean; (d) no `HARVEST` flag (or harvest already done). Explicit expected Tier-1 batch: `jax_mc_ad_bl_diagnose1..7` (8 is final). Everything failing any bar **stays in place** as Tier-2 with its manifest row — that is the normal outcome, not a failure.
Per batch: `git mv` (+ co-archived tests) → archive README append (what/why/verification/restore-path, per the `diagnostics_archive/README.md` template) → `pytest Code/ reproduce/ -m "not slow" -q` green → one revertible commit.

### Phase 3 — reconcile + smoke (1 agent, ~1 h)
If the env-flag registry exists: re-run `test_env_flag_registry.py`; flags whose only read sites moved → Status `archived-only`. Update `FILE_FAMILIES.md` final state + CLAUDE.md pointer line. `bash reproduce_min.sh`. If anything results-adjacent moved: `python Code/HA-Models/compare_result_pickles.py` vs `Results_canonical/`.

## File targets
New: `Code/HA-Models/docs/FILE_FAMILIES.md`. Appends: archive READMEs. Moves: Tier-1 only. Read-only use: `compare_result_pickles.py`.

## Verification
Per batch: triple grep gate + pytest green. Plan-final: `pytest Code/ reproduce/ -q` + `reproduce_min.sh` + registry guard green; `git log` one-revertible-commit-per-batch.

## Risks / rollback
The archive-then-restore failure mode → gate 3 mandatory; conservative-keep always acceptable (the manifest alone delivers the legibility win). Archived scripts assume `FromPandemicCode/` cwd/sys.path (known constraint, documented in archive READMEs). Rollback: revert the batch commit / `git mv` back. **Effort:** ~10-16 agent-hours; manifest ~5 of those. **Risk:** Phase 0-1 zero; Phase 2 gated.
