---
date: 2026-05-01
status: draft
keywords: [CDC, ESC, parity, audit, BUG-034, BUG-035, BUG-036, BUG-038, mirror-changes, validation]
related_bugs: [BUG-034, BUG-035, BUG-036, BUG-037-retracted, BUG-038]
---

# CDC-vs-ESC parity audit: identify and apply ESC mirror changes

## Background

ESC was last validated/regenerated on 2026-04-26 (per timestamps on
`Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt` and
`Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget_ESC.txt`).
Since then the CDC interpretation has had a substantial chain of changes:
BUG-034 (Step-2 wealth aggregation), BUG-035 (Step-1 CDC dynamics),
BUG-036 (multistart Nelder-Mead for dropout), BUG-037 (made + retracted),
BUG-038 (T_age cap restoration), Run_1stRoundAD flag fix, q_method='cohort'
default, plus various test/diagnostic additions.

We need to determine, for each of those changes, whether ESC needs a
corresponding mirror change — so that ESC can be re-run and compared
meaningfully against current CDC.

## Goal

Produce two deliverables:

1. **Audit report** (a conclusions log): per-change classification of the
   post-2026-04-26 CDC changes, identifying which need ESC mirrors and which
   don't.
2. **Mirror PRs** (commits): the actual ESC-side code changes (if any) to
   bring ESC back into a runnable, internally-consistent state.

Re-estimation of ESC is **opt-in**: only triggered if mirror changes alter
behavior in a way that requires re-estimation. (Per project default: no
re-estimation unless explicitly required.)

## Constraints / non-goals

- Don't re-estimate ESC unless Phase 4 validation indicates it's required
  for internal consistency.
- Don't change the ESC interpretation's *design* — only mirror CDC bug
  fixes whose underlying issue exists in both interpretations.
- Don't expand scope to refactor the CDC/ESC dispatch architecture itself.
- This audit is read-mostly until Phase 3; Phases 0-2 produce no code
  changes.

## Approach

### Phase 0 — Establish ESC baseline and diff scope (~5 min, sequential)

- Pin the "last ESC anchor" commit. Candidates:
  - The commit on 2026-04-26 that produced the saved `_ESC.txt` files
  - Or the merge-base of bug034-035 with the upgrade-validation branch
    (`6c1642c1`) — the parent's tip from before the BUG-034+035 cascade
- Run `git log --name-only <esc-anchor>..HEAD` to enumerate file changes.
- Filter to interpretation-relevant files:
  ```
  Code/HA-Models/FromPandemicCode/{tm_methods.py,
    EstimAggFiscalMAIN.py, EstimAggFiscalModel.py, AggFiscalModel.py,
    Simulate.py, AggFiscalMAIN_reduced.py, EstimParameters.py,
    Parameters.py}
  Code/HA-Models/_interpretation.py
  Code/HA-Models/Estimation_BetaNablaSplurge.py (if exists)
  ```
- **Output**: A markdown table `commit | file | hunk-summary` for every
  diff in the filtered set. Save to `audit_workdir/phase0_diffs.md`
  (a temporary working file; not committed).

### Phase 1 — Categorize each change [PARALLELIZABLE via Explore subagents]

For each change, classify into one of:

| Category | Meaning | ESC action |
|---|---|---|
| **A** | CDC-only by design — explicit `CDC-MOD-*` tag with companion comment saying ESC keeps the original behavior | None |
| **B** | Cross-cutting — affects both interpretations identically (no interpretation-specific dispatch needed) | None — already applies to ESC via shared code |
| **C** | CDC-only fix that has a different form for ESC | Mirror — write ESC-specific change |
| **D** | Already-mirrored — change is in interpretation-aware code that already handles both branches via existing dispatch | Verify the dispatch is correct |
| **E** | Test/diagnostic/doc-only — no production behavior change | None |

**Parallelism**: spawn 3-4 Explore subagents in parallel, each given
~5-10 commits to classify. Each subagent reads the diff + the surrounding
code context (especially looking for `CDC-MOD-*` / `ESC-MOD-*` tags and
the `interpretation` parameter dispatch in functions touched).

**Subagent prompt template**:
> For each commit listed below, read the diff, then read enough of the
> surrounding code to determine the classification (A/B/C/D/E per the
> categorization table in `plans/20260501-1032h_cdc-esc-parity-audit-plan.md`).
> Report a single-row entry per commit: `commit | category | one-sentence justification`.
> Pay particular attention to: (1) presence/absence of `CDC-MOD-*` tags,
> (2) the function signature's `interpretation` parameter and how it's
> dispatched, (3) comments explicitly mentioning ESC.

**Output**: `audit_workdir/phase1_categorization.md` with every change
classified. Working file; review before Phase 2.

**User decision point**: review the categorization. Correct any
miscategorized items before moving on. (If subagents disagree on a change,
flag it for manual review.)

### Phase 2 — Verify ESC paths for B and C changes (~30 min, sequential)

For each Category B (cross-cutting) change:
- Read the changed code with `HAFISCAL_INTERPRETATION=ESC` semantics in mind.
- Confirm the change is correct under ESC (not just under CDC).
- If it's not correct under ESC, downgrade to Category C.

For each Category C (mirror-needed) change:
- Locate the ESC-side code that should mirror it.
- Determine whether the mirror change is already in place, missing,
  or partially applied.
- Draft the mirror change (don't apply yet).

**Output**: `audit_workdir/phase2_mirror_changes_needed.md` listing the
exact ESC-side changes required (if any). Working file.

**User decision point**: approve the mirror-change list. Could be empty
(meaning ESC is already consistent with current CDC), or could list N
changes to apply.

### Phase 3 — Apply ESC mirror changes (if any; sequential)

For each approved mirror change:
- Make the code edit with an explicit `ESC-MOD-*` tag that cross-references
  the corresponding `CDC-MOD-*` tag (e.g.,
  `# ESC-MOD-BUG034: mirror of CDC-MOD-BUG034 in EstimAggFiscalMAIN.py:112`).
- Add or update a unit test if the change is non-trivial and a test
  doesn't already cover it.

Each mirror change should be a separate commit with a message of the
form: `BUG-XXX ESC mirror: <one-line description>`.

If Phase 2 finds no mirror changes, skip Phase 3 entirely.

### Phase 4 — Tiered ESC validation [CASCADE-GATED]

Run only if Phase 3 made changes (otherwise just rely on Phase 1+2 paper
analysis). Each tier gates the next; halt at the first failure.

| Tier | What | Wall time | Halt-on-fail criterion |
|---|---|---|---|
| **0** | Unit tests with `HAFISCAL_INTERPRETATION=ESC` for ESC-touching tests | ~2 min | Any test fails |
| **1** | Quick smoke: HS-only Step 2 re-evaluation under ESC | ~5 min | β/∇/GICx differ from prior ESC by >5% on HS |
| **2** | Reduced_Run Step 5 with ESC | ~5 min | Step-5 multipliers differ from prior ESC by >10% |
| **3** | Full Baseline Step 5 with ESC | ~30 min | Step-5 multipliers differ from prior ESC by >10% |

**Parallelism**: Tier 1 (HS-only) and Tier 2 (Reduced_Run) could run in
parallel since they exercise different scopes. Tier 3 should follow Tier 2.

If any tier shows large divergence from the prior ESC results, that's
information — it tells us a mirror change had non-trivial effect under ESC.
That doesn't mean the mirror is wrong; it means ESC's saved results need
to be regenerated.

### Phase 5 — Compare and document (~20 min, sequential)

Produce a conclusions log
(`conclusions_private/2026-MM-DD_cdc-esc-parity-audit-results.md`) with:
- Total CDC changes audited (count from Phase 0 output)
- Per-category counts (A/B/C/D/E)
- List of mirror changes applied (from Phase 3)
- Old ESC vs New ESC comparison table (from Phase 4)
- New CDC vs New ESC comparison table (Step 2 fits, Step 5 multipliers,
  wealth shares)
- Conclusion: is ESC now in parity with CDC? If not, what gaps remain?

If parity is achieved, optionally commit the regenerated ESC saved
results (`Result_AllTarget_ESC.txt`, `DiscFacEstim_..._ESC.txt`) so the
ESC anchor is current.

## Estimated total effort

- Phase 0: 5 min
- Phase 1: 30 min wall (parallel subagents); ~2 h sequential
- Phase 2: 30 min (depends on # of B/C changes)
- Phase 3: 0–2 h (depends on # of mirror changes; could be zero)
- Phase 4: ~40 min wall (cascade-gated; longer if early failures need diagnosis)
- Phase 5: 20 min

**Total: ~2 h wall clock if no mirror changes needed; ~5 h if several mirror
changes need careful application + validation.**

## Risks and contingencies

| Risk | Likelihood | Mitigation |
|---|---|---|
| ESC was actually broken before April 26 (unrelated to CDC changes) | Low-Med | Phase 1 will surface this; fix is out of scope (would be its own bug) |
| Mirror change causes ESC to fail Tier 0 (test pipeline issue, not real bug) | Med | Halt at Tier 0; investigate test setup before changing code |
| Phase 4 reveals mirror change was wrong | Med | Roll back the specific mirror commit (each is a separate commit); re-investigate |
| Subagents disagree on categorization | Low | Manual review at user decision point after Phase 1 |
| User wants to defer mirror application but accept the audit report | High | Phases 0-2 produce the audit independently of Phase 3-5; deliverables are decoupled |

## What this plan does NOT do

- Doesn't re-estimate ESC β/∇/splurge unless absolutely required (Phase 4
  Tier 1 may surface that need; that's a separate decision)
- Doesn't change the CDC/ESC architecture or dispatch layer
- Doesn't audit changes from before 2026-04-26 (presumed already in parity)
- Doesn't introduce new tests beyond what mirror changes need
- Doesn't try to make ESC "better" — only to keep it consistent with CDC

## References

- `_interpretation.py` (single source of truth for the CDC/ESC flag)
- Branch name `bug034-035-cdc-consistency-cleanup` (signals CDC-only scope)
- ESC saved results: `_ESC.txt` files in
  `Code/HA-Models/Results/` and `Code/HA-Models/Target_AggMPCX_LiquWealth/`
  (anchor date 2026-04-26)
- Plan `plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md`
  (the design that introduced the CDC/ESC suffix system)
- Conclusions log
  `conclusions_private/2026-04-23_cdc-esc-both-internally-consistent-proceed-with-qe.md`
  (the prior parity baseline — what we're trying to restore at a new commit)
