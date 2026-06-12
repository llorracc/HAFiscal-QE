# Plan: judgment-sensitive documentation decisions

**Date:** 2026-04-25
**Status:** Planned
**Scope:** Documentation updates requiring user, publication, QE, or coauthor judgment
**Parent plan:** `plans/20260425-1301h_documentation-only-reproduction-cleanup.md`
**Prerequisites:** Both parts of the agent-executable cleanup should be complete or nearly complete:
- `plans/20260425-1307h_agent-executable-documentation-cleanup-part1-fixes-paths-and-manifests.md`
- `plans/20260425-1409h_agent-executable-documentation-cleanup-part2-timing-modes-and-artifact-map.md`

## 1. Goal

Resolve documentation questions that cannot be decided purely from repository inspection because they affect publication-facing claims, QE/public repository promises, coauthor-sensitive wording, or the intended audience of the replication package.

The agent can prepare evidence and draft options, but the user should make or approve these decisions.

## 2. Why This Is Separate

Some documentation problems are factual: a path is broken, a command description is stale, or a script comment names the wrong entry point. Those belong in the agent-executable cleanup plan.

Other problems are policy questions. For example:

- Should a missing QE-specific README be removed, restored, or described as external to this repository?
- Should public documentation emphasize the current branch's improved reproduction machinery or the QE submission's historical replication path?
- How should the docs phrase known limitations around welfare sensitivity, TM validity, splurge interpretation, or pre-generated results?
- Which audiences should the root README prioritize: casual readers, QE replicators, maintainers, or coauthors?

Those choices can affect how the paper, replication package, and coauthor history are perceived.

## 3. Decisions Requiring User Input

### 3.1 QE and public-repository references

Issue:

`reproduce/README.md` links to `../README-QE.md`, which is not present in this tree. The correct action depends on the intended relationship among `HAFiscal-Latest`, `HAFiscal-Public`, and `HAFiscal-QE`.

Options:

1. Remove the QE link from this repository's docs.
2. Replace it with a note that QE-specific replication instructions live only in the QE/public repository.
3. Add or regenerate a `README-QE.md` in this repository.
4. Keep the link but mark it as expected only after export to another repository.

Agent role:

- Gather current links and repository-flow docs.
- Draft wording for each option.

User role:

- Choose which repository promise is correct.

Estimated user time: 10-20 minutes.
Estimated agent time after decision: 0.25-0.5 day.

### 3.2 Publication-facing description of current versus historical workflows

Issue:

The current code has evolved from older reproduction paths. Some docs may need to describe the historically submitted QE path, while others should describe the current `Latest` path. Mixing these creates confusion, but deleting historical context may also be wrong.

Questions:

- Should public-facing docs describe only the current branch behavior?
- Should they also explain older QE or published-output behavior?
- Should historical workflows move to an archive section?

Agent role:

- Identify places where historical and current workflows are mixed.
- Draft a "current workflow" section and an "historical notes" section.

User role:

- Decide how much historical detail belongs in public-facing docs.

Estimated user time: 20-40 minutes.
Estimated agent time after decision: 0.5-1 day.

### 3.3 Wording around known limitations and sensitive technical caveats

Issue:

Documentation may need to mention limitations around:

- welfare table sensitivity;
- MC versus TM validity;
- splurge interpretation and recent bug investigations;
- pre-generated outputs;
- branch-specific improvements not present in published or QE versions.

These are technically important but publication-sensitive. The wrong wording could overstate a bug, understate a limitation, or create confusion for coauthors and replicators.

Agent role:

- Prepare neutral wording options.
- Keep claims tied to factual code behavior.
- Avoid adding new scientific claims without approval.

User role:

- Approve exact wording for sensitive caveats.

Estimated user time: 30-60 minutes.
Estimated agent time after decision: 0.5-1 day.

### 3.4 Audience hierarchy for the README path

Issue:

The docs currently serve multiple audiences: casual paper readers, dashboard users, replication-package users, maintainers, coauthors, QE/public repository maintainers, and AI agents. A technical cleanup can route these audiences better, but the priority order is a user decision.

Options:

1. Root README optimized for external replicators.
2. Root README optimized for maintainers of the single source of truth repository.
3. Root README optimized for paper readers, with maintainer detail pushed down.
4. Separate audience-specific entry points with a short root routing table.

Agent role:

- Draft an audience map and proposed reading order.

User role:

- Decide the priority audience and tone.

Estimated user time: 15-30 minutes.
Estimated agent time after decision: 0.5-1 day.

### 3.5 Whether to document or suppress branch-local experimental paths

Issue:

The repository contains many plans, diagnostics, and experimental scripts. Some may be useful for maintainers but confusing or alarming for external replicators.

Questions:

- Should branch-local diagnostics be documented in maintainer docs only?
- Should bug-investigation material under private/history folders be omitted from public-facing docs?
- Should README paths point to plans/history at all?

Agent role:

- Inventory references to plans, history, and private bug material in public docs.
- Propose a split between public-facing and maintainer-facing references.

User role:

- Decide what should be visible in the main documentation path.

Estimated user time: 20-40 minutes.
Estimated agent time after decision: 0.5-1 day.

## 4. Suggested Workflow

1. Agent completes the factual cleanup plan.
2. Agent prepares a short decision memo with the unresolved questions above.
3. User chooses among options or edits suggested wording.
4. Agent applies approved wording to the docs.
5. User reviews only the judgment-sensitive diff, not the whole factual cleanup.

## 5. Deliverables

- A short decision memo listing policy-sensitive documentation choices.
- Approved wording for QE/public repository references.
- Approved wording for current versus historical workflow distinctions.
- Approved caveats for MC/TM validity, welfare sensitivity, splurge interpretation, and pre-generated results where needed.
- Final README audience hierarchy.

## 6. Estimated Time Split

Agent preparation time: 1-3 days, mostly drafting options and applying approved edits.

User decision/review time: 1-3 hours total, depending on how carefully publication-sensitive wording is reviewed.

The agent should not finalize these changes without user approval where the wording affects publication claims, QE/public repository promises, or coauthor-sensitive technical framing.
