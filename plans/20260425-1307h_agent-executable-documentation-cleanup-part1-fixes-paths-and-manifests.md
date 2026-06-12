# Plan: agent-executable documentation cleanup — Part 1 (fixes, paths, manifests)

**Date:** 2026-04-25
**Status:** Planned
**Scope:** Documentation updates the agent can execute independently — the mechanical text-fix half (defers all consolidated reference artifacts — timing table, mode-validity matrix, artifact map — to Part 2)
**Parent plan:** `plans/20260425-1301h_documentation-only-reproduction-cleanup.md`
**Companion plan:** `plans/20260425-1307h_judgment-sensitive-documentation-decisions.md`
**Part 2 (sibling):** `plans/20260425-1409h_agent-executable-documentation-cleanup-part2-timing-modes-and-artifact-map.md`

## 1. Goal

Fix documentation errors and stale material that can be resolved from repository evidence alone, without requiring publication-policy, QE-handoff, or coauthor-sensitive judgment.

The work should make the documented reproduction path match the actual code path, especially for:

```bash
./reproduce.sh --comp full
```

This plan covers the mechanical text-fix tasks: broken links, factual reproduction-path descriptions, and the historical-vs-current status of manifest notes. The three consolidated reference artifacts — a timing table across all modes, a mode-validity matrix, and a paper-figure artifact map — are deferred to Part 2 because they are synthesis-heavy and benefit from this plan's evidence-gathering being done first (the corrected reproduction-path text in 2.2 informs all three Part 2 artifacts).

## 2. Agent Can Do This Independently

These tasks are factual, local to the repository, and safe for the agent to execute end-to-end.

### 2.1 Fix broken local links and placeholders

- Replace the root README link to missing `reproduce/benchmarks/TIMING-ESTIMATES.md` with the actual benchmark documentation path(s).
- Replace template placeholders `{{REPO_URL}}` and `{{REPO_NAME}}` in `README/QUICK-REFERENCE.md` with repository-specific text or remove the one-line install snippets if they cannot be made accurate.
- Check links among `README.md`, `README/GETTING-STARTED.md`, `README/REPLICATION.md`, `README/provenance.md`, `Code/README.md`, and `reproduce/README.md`.

Validation:

- Confirm every changed local path exists.
- Run a lightweight markdown link check if available.

Estimated agent time: 0.5-1 day.
Estimated user time: none, except optional review.

### 2.2 Correct factual reproduction-path descriptions

Update docs so they consistently state:

- Default `--comp full` dispatches through `reproduce/reproduce_computed.sh` to `Code/HA-Models/do_all.py`.
- Default `do_all.py` runs Steps 1, 2, 4, and 5; Step 3 is off unless enabled by `--comp max` or `HAFISCAL_RUN_STEP_3=true`.
- Step 5 currently uses `AggFiscalMAIN_reduced.py --baseline` and `run_welfare6_parallel.py --baseline`.
- `--comp full --tm-only`, `--comp full --mc-only`, and `--comp TM-and-MC` are distinct variant workflows, not aliases for default `--comp full`.

Likely files:

- `README.md`
- `README/REPLICATION.md`
- `Code/README.md`
- `reproduce/README.md`
- comments in `Code/HA-Models/do_all.py`
- comments in `reproduce/reproduce_computed_tm_only.sh`
- comments in `Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py`

Validation:

- Compare all documented commands against `reproduce.sh`, `reproduce/reproduce_computed.sh`, and `Code/HA-Models/do_all.py`.
- Do not run full computation.

Estimated agent time: 0.5-1 day.
Estimated user time: none, except optional review.

### 2.3 Clarify historical status of manifest notes

Update `reproduce/run-manifests/decisions.md` so readers can distinguish historical implementation notes from current manifest status.

This can be done factually by comparing the decisions log to current `reproduce.sh`.

Validation:

- Confirm current statements about manifest wiring match `reproduce.sh`.

Estimated agent time: 0.5 day.
Estimated user time: optional review only.

## 3. Deliverables

- Updated documentation files with corrected local links.
- Correct description of default full, max, tm-only, mc-only, and TM-and-MC workflows.
- Updated historical/current-status note for run manifests.

## 4. Estimated Time Split

Agent time: 1.5-2.5 days.

User time: 0-1 hour, mostly final review.

The agent can complete this plan independently unless it discovers an ambiguity that is not resolvable from repository evidence.

## 5. Relationship to Part 2

Part 2 (`plans/20260425-1409h_agent-executable-documentation-cleanup-part2-timing-modes-and-artifact-map.md`) covers the three consolidated reference artifacts:

- Normalize factual timing presentation (one consolidated table across all modes).
- Add a mode-validity matrix (which modes generate which output classes).
- Draft a documentation-only artifact map (paper figures/tables → generator scripts and modes).

Part 2 is conceptually independent of Part 1, but both consume similar evidence (reproduction-path mapping, output-gate inspection). Running Part 1 first means Part 2 can reference Part 1's corrected reproduction-path documentation and link descriptions rather than re-deriving them.