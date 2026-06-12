# Plan: coauthor update — one short email + a forward-looking, revised set of existing docs

**Date (combined, revised plan):** 2026-04-24 (supersedes earlier separate email plan at `plans/20260424_email-coauthors-QE-timeline-acceptance.md`, and the prior "create new mashup docs in a subdirectory" version of this plan).
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
**Audience for the deliverables:** Edmund, Håkon, Ivan.

## 1. Goal and approach

Produce two deliverables, both for the coauthors:

- **A short email** (~80–120 words of body) that (i) accepts the group's QE-timeline consensus, (ii) explains the one-line technical reason I'm now comfortable with proceeding, and (iii) briefly characterizes the interpretation question in a softened form.
- **A small set of canonical, linkable documents** — *revised versions of existing files, modified in place* — that the email refers to for anyone who wants depth.

**Key change from the prior version of this plan.** Rather than creating new mashup/derivative documents in a new subdirectory, this plan **modifies existing docs in place** to serve the email's purposes, and **archives/moves the docs that would otherwise clutter the dir**. The reason: the existing docs already contain the substance; creating shadow copies would (a) duplicate content, (b) leave stale versions lying around, (c) force a cross-reference net that is hard to maintain.

The scope of "modify in place" deliberately excludes `history/` (records of past meetings/exchanges) and `_archive/` (already-archived material).

## 2. Inventory: what's in `BUGS_private/HAFiscal_splurge_budget_inconsistency/`

Top-level markdown docs and their current content, April 2026 state:

| File | LOC | Content (one-line summary) | Written for | Date written |
|---|---:|---|---|---|
| `README.md` | 19 | Reading guide. "In one sentence" framing of the bug; points to distilled-summary → results → what-to-do → bound-pair-assessment → mwe.py. | Pre-meeting (Apr 18) | 2026-04-18 |
| `distilled-summary.md` | 108 | The bug, the fix, the bound-pair reading (as a rejected alternative), the quantitative consequences. The anchor doc from the April 14–17 exchange. | Pre-meeting | 2026-04-18 |
| `results.md` | 60 | Baseline CRRA2 multiplier and welfare-6 tables: bugfix vs HAFiscal-QE. Contains the large (−25 %, −35 %) welfare-6 deltas that **were later understood to be dominated by QE-side MC noise**, not a real model difference. | Pre-meeting | 2026-04-17 |
| `what-to-do.md` | 73 | Three publication-timeline options (pause, proceed-and-correct, proceed-with-pointer) with a recommendation for "pause and ask QE to delay." | Pre-meeting | 2026-04-18 |
| `bound-pair-assessment.md` | 55 | Rejects the bound-pair reading on two grounds: internal code inconsistency and K/Y-target. Appended withdrawal note on Lorenz/welfare arguments. | Pre-meeting (defensive memo) | 2026-04-18 |
| `notes_on_distilled_summary_response.md` | 346 | Detailed response to Edmund's `maintain_bound_pair_fix_splurge` branch; acknowledges the equivalence proof, re-frames the dispute as estimation-convention-vs-budget-identity. | Mid-exchange (Apr 20-ish) | 2026-04-20 |
| `notes_on_bound_pair_equivalence.md` | 133 | Walks through the question "is ESC = CDC mathematically?"; answers "no, they differ in what `m` goes into `cFunc`." Largely superseded by the target-level argument in `results_dont_change_much.md`. | Mid-exchange | 2026-04-22 |
| `notes_on_section6_correction.md` | 53 | Chris's polite-but-forceful response to Edmund's `section6_correction.md`; partially retracted on Apr 23. Still contains useful framing (household-economics literature on public-good consumption; y → 0 problem). | Pre-meeting | 2026-04-22 |
| `models_CDC_and_ESC.md` | 245 | **Canonical reference** defining CDC and ESC side-by-side with common `tot`/`opt`/`spl` notation; exposes the single distinguishing equation `(CDC-1)` / `(ESC-1)` (asset update); states what they share (utility, buffer-stock form, state transition form, welfare aggregator A, calibration targets). | Post-meeting | 2026-04-24 |
| `welfare_code_and_paper_text_on_interpretation.md` | 317 | 13-quote paper-text audit; establishes that code implements welfare aggregator A; establishes that paper text outside the welfare formula leans CDC; includes proposed disambiguating rewrites. | Post-meeting | 2026-04-23 |
| `results_dont_change_much.md` | 91 | Draft memo: why non-welfare results barely move across the two interpretations. Contains both the target-level identity and its application. | Post-meeting | 2026-04-23 |
| `why_one_parameter_one_moment_suffices.md` | 70 | Cleanest one-parameter, one-moment statement of the target-level identity. | Post-meeting | 2026-04-23 |
| `email_coauthor_update_20260423.md` | 28 | Earlier draft coauthor-update email; largely superseded by the email this plan proposes. | Post-meeting | 2026-04-23 |
| `email_draft_response.md` | 40 | Cover note that accompanied the `notes_on_distilled_summary_response.md` handoff (pre-meeting). | Mid-exchange | 2026-04-20 |
| `email/` | dir | April 14–17 coauthor email thread (raw archive). | — | 2026-04-14-17 |
| `_archive/` | dir | Already-archived scratch material. | — | various |
| `mwe.py` | — | Two-household minimum working example (Python) reproducing the budget-identity violation. | Pre-meeting | 2026-04-18 |

**Key observation.** The dir has accumulated ~14 top-level markdown files over ten days, several of which were written when the welfare-difference story was believed to be load-bearing — a belief that was later invalidated (the welfare differences were sampling noise in the published QE values, not real model differences). Forward-looking coauthor-facing material needs to be separable from that exchange-specific history.

## 3. The email

### 3.1 Length and structure

- **Target length: ~80–120 words of body.**
- Single email (not two). Supersedes any earlier plan that split the technical note from the QE-timeline note.
- Links into the modified document set; does not embed substantive content itself.

### 3.2 Points it carries

- **QE timeline.** Accept the consensus — I came in preferring to pause but have landed comfortable with proceeding.
- **Why I'm comfortable.** A target-level identity explains why the non-welfare results barely move across the revision. (Link to the revised [`why_results_match_at_target.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/why_results_match_at_target.md) — centerpiece; see §4.1.)
- **The interpretation question.** I've made a side-by-side doc of the two interpretations (link to [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md)). Briefly push back on the framing that the household-bargain reading is a new model — it's a disambiguation of the existing text, aligned with the paper's welfare criterion; Edmund's reading is equally legitimate. For the extent to which the paper text points toward one or the other, and proposed disambiguating rewrites, link [`welfare_code_and_paper_text_on_interpretation.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/welfare_code_and_paper_text_on_interpretation.md).

### 3.3 Tone

- Conciliatory, not contrite.
- Substantive reason for the shift, not capitulation under pressure.
- Gracious on the interpretation framing — no triumph, no scoreboard. Explicitly offer ESC and CDC as both legitimate; stress the team doesn't need to pick one to go to QE.
- Forward-looking: closes a loop rather than opening one.

### 3.4 Where to save the email draft

```
BUGS_private/HAFiscal_splurge_budget_inconsistency/email/drafts/email_coauthors_20260424.md
```

## 4. Documents to modify in place (three)

### 4.1 Centerpiece: the "why the non-welfare results barely move" memo

**Flip from the prior plan.** The prior plan proposed keeping `results_dont_change_much.md` as the centerpiece and archiving `why_one_parameter_one_moment_suffices.md`. Reversed: `why_one_parameter_one_moment_suffices.md` contains the essence of the argument in a way that is substantially easier for a first-time reader to follow (setup → identity → why both models produce the same `C_target` → caveats), whereas `results_dont_change_much.md` gets to the same place by a longer, more narrative path that is harder to navigate. The clearer doc should be the skeleton.

**Approach.** Use `why_one_parameter_one_moment_suffices.md` as the base; fold in only the genuinely value-adding material from `results_dont_change_much.md` (the two-calibration (β̄, ∇, ς) table; a one-paragraph multi-parameter extension; the pointer to the empirical synopsis). Archive `results_dont_change_much.md` with a one-line note.

**Renaming.** The current title "Why the results don't change much — the simple version" implies a companion doc that will no longer exist. Preference: rename the file to `why_results_match_at_target.md`, since the merged doc will contain both the one-parameter essence and the multi-parameter extension.

**Modifications to `why_one_parameter_one_moment_suffices.md`:**

1. **Retitle** to reflect broader scope: `# Why the results don't change much`. Drop the "the simple version" subtitle.
2. **Drop the companion-to sentence** in the frontmatter ("Companion to `results_dont_change_much.md`") since that doc is being absorbed.
3. **Fold in** from `results_dont_change_much.md`, placed after the existing "Why this matters" section but before "What this argument does NOT say":
   - The two-calibration (β̄, ∇, ς) table (CDC: 0.9611/0.0668/0.2609; ESC: 0.9715/0.0589/0.2672).
   - A one-paragraph multi-parameter extension explaining that the actual HAFiscal calibration matches K/Y + four Lorenz percentiles + aggregate MPC via (β̄, ∇, ς), and the same target-level reasoning extends to that case by construction.
   - A pointer to `history/20260422_coauthor-meeting-synopsis_no-welfare.md` for the empirical evidence (multipliers, policy-activity shares, MPC fit all matching within a few percent).
4. **Cross-reference** `models_CDC_and_ESC.md` for the `(CDC-1)` / `(ESC-1)` asset-update equations.
5. **Preserve** the existing "What this argument does NOT say" section — it already correctly notes target-level-only, not ergodic, not tails, not welfare-in-tails.

**Outcome.** A ~95-line standalone memo using the clearer exposition as the skeleton, with the minimum useful additions from `results_dont_change_much.md` folded in. The email links to this doc (under its new name `why_results_match_at_target.md`) as the single pointer for "why I'm now comfortable proceeding."

**Sources absorbed:**
- `results_dont_change_much.md` → parameter table + multi-parameter extension + empirical pointer folded in; original file moved to `_archive/` (see §6).

### 4.2 [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md) — the canonical side-by-side

**Current state.** 245 lines. Already in good canonical shape: common notation, economic setup for each, single distinguishing equation labelled `(CDC-1)` / `(ESC-1)`, code mapping for each, side-by-side differences table, calibration triple table, "what this doesn't resolve" section.

**Modifications needed:**

1. **Small tightening pass.** Re-read for stale references, e.g. "see companion memo `notes_on_bound_pair_equivalence.md`" (that memo is being archived per §6).
2. **Add a short "how to read this" top-note for coauthors** who haven't followed the prior exchange in detail: one paragraph saying "this doc formalizes the two interpretations side-by-side in common notation; both are internally consistent; the practical question is which one to write down for the paper."
3. **Verify the §8 "how to cite" cross-references resolve** after this plan's archive moves.
4. **Add a new final section — "Why the bargain interpretation seemed natural to CDC"** — briefly incorporating the surviving strands from `notes_on_section6_correction.md`: (a) the household-economics literature (Chiappori, Browning–Chiappori, Lundberg–Pollak, etc.) treats household consumption as largely a public good, which matches CDC's `u(c_actual)` aggregator rather than a pure-private split; (b) the y → 0 sensitivity — under CRRA a welfare aggregator with `u(y)` as an additive term has unbounded marginal utility exactly in the states (job loss, benefit exhaustion) a UI paper is about. This is *not* a disqualifying argument against ESC as Edmund means it (aggregator A is what both interpretations use), but it is the reason CDC gravitated to the bargain reading rather than the Campbell–Mankiw reading. Target length: ~25 lines.

**Outcome.** Substantively unchanged except for the new final section; minor polish for a first-time reader.

### 4.3 [`welfare_code_and_paper_text_on_interpretation.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/welfare_code_and_paper_text_on_interpretation.md) — the paper-text audit + proposed rewrites

**Current state.** 317 lines. Already in good shape: 13 quotes from `Model.tex`, `Intro.tex`, `Comparing-policies.tex`; "Because:" justifications; proposed disambiguating rewrites for each passage in both directions (toward CDC and toward ESC); synthesis table showing 5 CDC-leaning, 0 ESC-leaning, 2 ambiguous.

**Modifications needed:**

1. **Re-read for stale framing** referring to the ESC-leans-aggregator-B misattribution that Edmund's Apr 23 clarification corrected. Most of that is already cleaned up in the current version, but verify.
2. **Add a short top-note** pointing the coauthor-reader to what's actionable: "if the team elects CDC, apply the CDC-pointing rewrites in Q2/Q3/Q4/Q5/Q8/Q9/Q10; if ESC, apply the ESC-pointing rewrites to the same set. The document does not advocate an outcome; it makes both outcomes available as copy-pasteable paper-text revisions."
3. **Final § (the "action item for Edmund's consumption-calc flag")** — keep, but soften the call-to-action to "I'll ask Edmund directly when we next talk" rather than a public challenge.

**Outcome.** Essentially unchanged in content; minor tone adjustment on the closing call-to-action.

## 5. Documents to archive or demote

These docs served the pre-meeting or mid-exchange phase of the discussion and don't need to be in the forward-looking coauthor-facing surface. The plan is to **move them to `_archive/`** (in place of deleting — we may still want to cite them in footnotes). Each gets a one-line note at the *new* location explaining why it was archived.

| File | Why archived | Successor / substitute |
|---|---|---|
| `distilled-summary.md` | **Don't archive.** Still the anchor for the bug-and-fix story; it's what a reader reaching the dir for the first time should read. Keep in place. But add a short top-note: "this doc was written pre-meeting and framed the interpretation question as 'ESC vs CDC: which is right?'; the Apr 23 meeting has moved that framing toward 'both are internally consistent; the practical question is which to adopt as canonical.'" | — |
| `README.md` | **Don't archive; rewrite.** Current reading guide points to pre-meeting docs. Update to point to: distilled-summary (for the bug), models_CDC_and_ESC (for the two interpretations), why_results_dont_change_much (for why it doesn't much matter), welfare_code_and_paper_text_on_interpretation (for the paper-text audit). | — |
| `results.md` | Multipliers table survives; welfare-6 table is **misleading** without the context that the QE-side numbers are dominated by MC noise. Archive the file; the multiplier-table content has a successor in `history/20260422_coauthor-meeting-synopsis_no-welfare.md`. | `history/20260422_coauthor-meeting-synopsis_no-welfare.md` |
| `what-to-do.md` | Recommends "ask QE to pause publication." That recommendation has been **overturned** by the Apr 23 consensus to proceed. Keep for the record; archive to `_archive/` with a one-line note "recommendation in §3 overturned by Apr 23 coauthor consensus; see `history/20260423_coauthor-meeting-ai-summary.md`." | `history/20260423_coauthor-meeting-ai-summary.md` (captures the decision) |
| `bound-pair-assessment.md` | Written under the pre-Apr-23 framing where the bound-pair reading was the alternative-to-argue-against. Post-meeting, both interpretations are on equal standing. Archive with a note. | `models_CDC_and_ESC.md` (canonical side-by-side) |
| `notes_on_distilled_summary_response.md` | A mid-exchange reaction to Edmund's new branch; useful as a record, but the substantive content has been absorbed by `models_CDC_and_ESC.md` and `why_results_match_at_target.md`. Archive with a note. | `models_CDC_and_ESC.md` + `why_results_match_at_target.md` |
| `notes_on_bound_pair_equivalence.md` | Substantially superseded by the target-level argument in the revised `why_results_match_at_target.md`; also by the `(CDC-1)` vs `(ESC-1)` framing in `models_CDC_and_ESC.md`. Archive with a note. | `why_results_match_at_target.md` + `models_CDC_and_ESC.md` |
| `notes_on_section6_correction.md` | Three of five strands retracted on Apr 23. Surviving strands (public-good-consumption / household-economics-literature framing; y → 0 sensitivity) are lifted into a new final section of `models_CDC_and_ESC.md` — "Why the bargain interpretation seemed natural to CDC" — per §4.2 step 4. After the lift, the original is archived. | `models_CDC_and_ESC.md` (final §, "Why the bargain interpretation seemed natural to CDC") |
| `results_dont_change_much.md` | Longer narrative version of the "results don't change much" argument; the cleaner `why_one_parameter_one_moment_suffices.md` is being used as the centerpiece skeleton instead (per §4.1). Absorb parameter table + multi-parameter extension + empirical pointer; then archive. | `why_results_match_at_target.md` (the renamed centerpiece) |
| `email_coauthor_update_20260423.md` | Earlier email draft; superseded by the new email this plan produces. Archive. | `email_coauthors_20260424.md` |
| `email_draft_response.md` | Cover note from the mid-exchange handoff; purely historical. Archive. | — |
| `mwe.py` | Two-household MWE; keep — still useful as a runnable demonstration of the original bug. No change. | — |

**Net effect on the dir** after this plan:

- Kept, revised: `README.md`, `distilled-summary.md`, `why_results_match_at_target.md` (renamed from `why_one_parameter_one_moment_suffices.md` with content folded in), `models_CDC_and_ESC.md`, `welfare_code_and_paper_text_on_interpretation.md`, `mwe.py`, `email/`, `_archive/`.
- Kept, unchanged: (none — everything is at least lightly touched).
- Archived to `_archive/` with a top-note explaining why: `results.md`, `what-to-do.md`, `bound-pair-assessment.md`, `notes_on_distilled_summary_response.md`, `notes_on_bound_pair_equivalence.md`, `notes_on_section6_correction.md` (after lifting surviving strands to `models_CDC_and_ESC.md` §9), `results_dont_change_much.md` (after folding its parameter table and multi-parameter extension into the centerpiece), `email_coauthor_update_20260423.md`, `email_draft_response.md`.
- New: `email_coauthors_20260424.md`.

Dir goes from ~14 top-level `.md` files to ~5 forward-looking `.md` files plus the email.

## 6. Execution order

Depends (earlier steps first):

0. **Reread `distilled-summary.md`** before touching anything. CDC plans to revise it before this plan is executed; the revised content may change how (i) the `README.md` reading-guide rewrite (step 6) should describe it, (ii) the `distilled-summary.md` top-note (step 7) should be worded, and (iii) whether cross-references in the other docs still resolve to the right anchors. If the revision is substantive, adjust this plan before proceeding.
1. **Lift surviving strands of `notes_on_section6_correction.md`** (household-economics-literature framing; y → 0 sensitivity) into a new final section of `models_CDC_and_ESC.md` titled "Why the bargain interpretation seemed natural to CDC" (see §4.2 step 4).
2. **Revise `models_CDC_and_ESC.md`** (§4.2 steps 1–3): small polish, top-note, verify cross-refs.
3. **Build the centerpiece** (§4.1): take `why_one_parameter_one_moment_suffices.md` as the skeleton; fold in the two-calibration (β̄, ∇, ς) table, the multi-parameter extension paragraph, and the empirical-synopsis pointer from `results_dont_change_much.md`; retitle; rename the file to `why_results_match_at_target.md`. Archive `results_dont_change_much.md` per §5.
4. **Revise `welfare_code_and_paper_text_on_interpretation.md`** (§4.3): top-note, soften closing call-to-action.
5. **Move docs to `_archive/`** per §5, adding one-line explanatory notes at the top of each moved file.
6. **Rewrite `README.md`** as a forward-looking reading guide (§5 table, "kept, revised" row). Do this *after* the archive moves so the new reading guide reflects the final surface.
7. **Add a short top-note** to `distilled-summary.md` noting the post-meeting context shift (adjusted for whatever revisions CDC made in step 0).
8. **Draft the email** (§3).

## 7. Sign-off criteria

- The email is ≤120 words of body, folded into one message, softened on interpretation framing, and links into the modified document set.
- The forward-looking surface of the dir is ~5 top-level `.md` files: `README.md`, `distilled-summary.md`, `why_results_match_at_target.md`, `models_CDC_and_ESC.md`, `welfare_code_and_paper_text_on_interpretation.md`. Plus `mwe.py`, `email/`, `_archive/`, and the new email.
- Every archived doc has a one-line top-note explaining why it was archived and what replaces it.
- Surviving strands of `notes_on_section6_correction.md` are preserved in a new final section of `models_CDC_and_ESC.md` titled "Why the bargain interpretation seemed natural to CDC."
- No cross-reference is broken by the archive moves.
- The three in-place-modified docs read standalone (no "I'll write this up more formally" artifacts from when they were drafts).

## 8. Estimated effort

- Step 0: Reread (possibly revised) `distilled-summary.md`; adjust plan if needed: 10 minutes.
- Lift surviving strands of `notes_on_section6_correction.md` into the new final section of `models_CDC_and_ESC.md`: 30 minutes.
- Revise `models_CDC_and_ESC.md` (polish + top-note, steps 1–3): 20 minutes.
- Build centerpiece `why_results_match_at_target.md` from `why_one_parameter_one_moment_suffices.md` skeleton + folded-in material from `results_dont_change_much.md`: 45 minutes.
- Revise `welfare_code_and_paper_text_on_interpretation.md` (top-note + closing): 15 minutes.
- Archive moves + one-line notes on each: 30 minutes.
- Rewrite `README.md` as forward-looking reading guide: 20 minutes.
- Top-note on `distilled-summary.md`: 10 minutes.
- Email draft: 20 minutes.

**Total:** ~3.2 hours of writing/reorganization.

## 9. What this plan does NOT include

- A "retractions memo." Absorbed by the one-line notes on archived documents.
- A "consumption-calculation-bug investigation." Waiting on Edmund's specific line reference; the placeholder in `welfare_code_and_paper_text_on_interpretation.md` §4 documents the hold.
- A "path-forward proposal." Better handled live; the `history/20260423_coauthor-meeting-ai-summary.md` captures the current consensus.

Out of scope:

- Modifications to `history/`.
- Modifications to `_archive/`'s existing contents.
- Modifications to `email/` (the raw April 14–17 thread).
- Running the ESC parallel-estimation pipeline (`plans/20260423-1934h_estimate-ESC-in-parallel.md`).
- Paper-text revision in `Subfiles/`.

## 10. Resolved decisions (2026-04-24)

1. **Subject line:** "OK, I'm mostly on board with proceeding with QE ..." (starts as the email's opener; final subject is the lead clause).
2. **Surviving strands of `notes_on_section6_correction.md`:** briefly mentioned in a new final section of `models_CDC_and_ESC.md` titled "Why the bargain interpretation seemed natural to CDC" — framed as the reason CDC gravitated to the bargain reading, not as a disqualifier against ESC. See §4.2 step 4 and §5 row for `notes_on_section6_correction.md`.
3. **`distilled-summary.md`:** CDC will revise it *before* this plan is executed. The plan's step 0 in §6 therefore requires rereading the revised doc before proceeding, and adjusting downstream steps (README rewrite in step 6; top-note in step 7) if the revision is substantive.
4. **Email and the reorg:** the email just links to the revised docs; the directory reorganization is visible from the dir listing and doesn't need to be mentioned in the email.
