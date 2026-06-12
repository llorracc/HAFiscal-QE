# Plan: documentation response to 2026-04-23 coauthor meeting

**Date:** 2026-04-23
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
**Audience for the deliverables:** Edmund, Håkon, Ivan; intended for the Apr 24 follow-up meeting.

## 1. Goal

Produce a coherent set of documents that, taken together, constitute Chris's substantive response to the Apr 23 coauthor meeting. The set must:

- Place at the center two pieces, in this order:
  1. **The explanation for why the results do not change very much** — i.e., why the non-welfare aggregates (multipliers, policy-share decompositions, MPC fit, calibration moments) coincide so tightly between the bound-pair (ESC) and bargain (CDC) interpretations once each is calibrated to its own targeted moments.
  2. **The single-parameter target-level identity** — the technical foundation of (1): if both models were calibrating only one parameter (β) to one moment (target household wealth), then at each model's own target the household-level consumption would be algebraically identical, by the buffer-stock target identity `C = (R·E[1/(G·Ψ)] − 1)·A + Y`.
- Address the specific action item assigned to Chris-JHU at the meeting to write down the alternative household-bargaining model interpretation explicitly.
- Supersede or clarify earlier same-day documents that contain partially-retracted arguments.
- Be self-contained: each document is readable on its own; the set has a top-level README that establishes reading order.

Out-of-scope for this plan: retractions memo, consumption-calculation-bug investigation, and path-forward document (see [§9](#9-what-this-plan-does-not-include)).

## 2. Inventory: what exists, status

| Path | Status | Disposition |
|---|---|---|
| [`BUGS_private/HAFiscal_splurge_budget_inconsistency/distilled-summary.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/distilled-summary.md) | Original Apr 18 bug report, on which the entire exchange is built. | KEEP unchanged. |
| [`BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_section6_correction.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_section6_correction.md) | Retracted on three of five strands (welfare aggregator, y → 0, lit critique) after Edmund's Apr 23 clarification. | MARK SUPERSEDED — retain as historical record with header note pointing to (1) and (3). |
| [`BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_bound_pair_equivalence.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_bound_pair_equivalence.md) | Claims ESC ≠ CDC in dynamics. Argument was correct for the same-β case, but with proper β re-calibration the two match at the target (first-order). Framing overstated. | MARK SUPERSEDED with header note pointing to (1) and (2). |
| [`BUGS_private/HAFiscal_splurge_budget_inconsistency/results_dont_change_much.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/results_dont_change_much.md) | Current synthesis (just renamed from `results_dont_change_much.md`); will be reworked into (1). | MERGE into (1); keep file with header note "superseded by". |
| [`BUGS_private/HAFiscal_splurge_budget_inconsistency/why_one_parameter_one_moment_suffices.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/why_one_parameter_one_moment_suffices.md) | Cleanest standalone; will be polished into (2). | MERGE into (2); keep file with header note. |
| [`BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md) | Canonical reference document with `(CDC-N)` / `(ESC-N)` labelled equations. | LINK from (1), (2), and (3). |
| [`history/20260422_coauthor-meeting-synopsis.md`](../history/20260422_coauthor-meeting-synopsis.md) | Pre-meeting synopsis with welfare comparison. | KEEP. |
| [`history/20260422_coauthor-meeting-synopsis_no-welfare.md`](../history/20260422_coauthor-meeting-synopsis_no-welfare.md) | Non-welfare data tables. | LINK from (1). |
| [`history/20260423_coauthor-meeting-ai-summary.md`](../history/20260423_coauthor-meeting-ai-summary.md) | Zoom-call AI summary; the action items live here. | LINK from (3) as context for the action item. |
| [`plans/20260423_estimate-ESC-in-parallel.md`](20260423_estimate-ESC-in-parallel.md) | Plan for ESC parallel-estimation. | LINK from (1) and (3). |
| [`BUGS_private/HAFiscal_splurge_budget_inconsistency/email_draft_response.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/email_draft_response.md) | Older pre-session untracked draft. | LEAVE alone. |
| [`BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_distilled_summary_response.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_distilled_summary_response.md) | Older pre-session untracked draft. | LEAVE alone. |

## 3. Proposed new document set

Create a subdirectory for the post-meeting response:

```
BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/
```

Four documents, numbered to suggest reading order (links will resolve once the files are created):

- [`00_README.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/00_README.md)
- [`01_results_dont_change_much.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/01_results_dont_change_much.md) — Centerpiece 1
- [`02_target_level_identity.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/02_target_level_identity.md) — Centerpiece 2
- [`03_household_bargaining_model_writeup.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/03_household_bargaining_model_writeup.md) — Action item

Justification for the subdirectory: the parent folder already contains ~12 files; lumping three more into the same flat space makes it harder to find anything. Grouping the post-meeting response keeps it self-contained, easy to circulate as a unit, and easy for a reader (coauthor or future reviewer) to know which documents reflect the current state of Chris's thinking vs. the historical record.

## 4. For each new document: purpose, contents, sources

### 4.1 [`00_README.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/00_README.md)

**Purpose:** Top-level orientation. Names the three substantive documents, recommends reading order, notes the out-of-scope items, points to the Zoom-call summary for meeting context.

**Contents:** ~25 lines. One sentence per document. Acknowledges the meeting summary ([`history/20260423_coauthor-meeting-ai-summary.md`](../history/20260423_coauthor-meeting-ai-summary.md)) for the meeting record. Explicitly lists the action items the set does *not* address (retractions memo, consumption-calc check, path-forward proposal) with short justifications.

**Sources:**
- None — written from scratch as table-of-contents, with explicit link to the Zoom AI summary ([`history/20260423_coauthor-meeting-ai-summary.md`](../history/20260423_coauthor-meeting-ai-summary.md)).

### 4.2 [`01_results_dont_change_much.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/01_results_dont_change_much.md) — Centerpiece 1

**Purpose:** State the structural reason why the non-welfare aggregates match HAFiscal-QE so tightly across the bound-pair and bargain interpretations once each is calibrated to its own targeted moments.

**Contents (~150 lines):**

- One-paragraph framing of the puzzle (the "why don't the results change?" opening).
- Reference to [(2)](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/02_target_level_identity.md) for the technical foundation.
- Reference to the canonical [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md) for the precise model definitions and the `(CDC-1)` / `(ESC-1)` asset-update equations.
- The three-input identity `C = (R·E[1/(G·Ψ)] − 1)·A + Y` and why both models share all three inputs at calibration.
- Explicit treatment of the multi-parameter case: (β̄, ∇, ς) are estimated to hit K/Y, four Lorenz percentiles, and aggregate MPC. Both calibrations match these *targeted* moments by construction.
- Specific table of (β̄, ∇, ς) under each calibration with a one-line interpretation of each gap.
- What the argument covers: aggregates that depend on targeted moments.
- What the argument does NOT cover: non-targeted percentiles, tails, welfare-in-tails. Explicitly *not* a claim about full-distribution agreement.
- Pointer to [`history/20260422_coauthor-meeting-synopsis_no-welfare.md`](../history/20260422_coauthor-meeting-synopsis_no-welfare.md) for the empirical confirmation that aggregates do match.
- Pointer to [`plans/20260423_estimate-ESC-in-parallel.md`](20260423_estimate-ESC-in-parallel.md) for how an ESC calibration on the current branch could be produced for a direct side-by-side.

**Sources:**

- [`results_dont_change_much.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/results_dont_change_much.md) (full body, after edits to incorporate the single-parameter / single-moment framing and the ∇ caveat).
- [`why_one_parameter_one_moment_suffices.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/why_one_parameter_one_moment_suffices.md) (the one-parameter argument summarized; full version lives in (2)).
- [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md) (reference for equation numbers).

**Key edits relative to the sources:**

- Frame the target-level argument explicitly as the single-parameter thought experiment.
- Be precise that the multi-parameter case extends to *targeted* moments only.
- Drop any implicit claim that the full distribution matches.

### 4.3 [`02_target_level_identity.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/02_target_level_identity.md) — Centerpiece 2

**Purpose:** Standalone technical statement of the single-parameter, single-moment target-level identity. The cleanest version of the mechanism that drives [Centerpiece 1](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/01_results_dont_change_much.md).

**Contents (~100 lines):**

- Setup of the one-parameter calibration thought experiment.
- Derivation of `C_target = (R·E[1/(G·Ψ)] − 1)·A_target + Y_target` from the buffer-stock target condition (using the first-order Taylor expansion worked out on the evening of Apr 23).
- Application to both ESC and CDC: same `R·E[1/(G·Ψ)]`, same `Y_target`, same `A_target` by calibration ⇒ same `C_target`.
- Caveat: this is target-level only, not off-target; not a statement about the full distribution.
- One-line summary of the technical mechanism.
- Cross-reference to [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md) for the `(CDC-1)` / `(ESC-1)` asset-update equations from which the identity follows.

**Sources:**

- [`why_one_parameter_one_moment_suffices.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/why_one_parameter_one_moment_suffices.md) (the body, with light editing for clarity and to add an explicit Taylor-expansion derivation step the current memo glosses).
- [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md) (reference for equation numbers).

### 4.4 [`03_household_bargaining_model_writeup.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/03_household_bargaining_model_writeup.md)

**Purpose:** Explicit formalization of the CDC ("household bargaining") interpretation. This is the action item assigned to Chris at the meeting: *"Write down the alternative household-bargaining model interpretation explicitly before the next meeting"* (see item 1 of [`history/20260423_coauthor-meeting-ai-summary.md`](../history/20260423_coauthor-meeting-ai-summary.md)).

**Contents (~150 lines):**

- The economic setup: one household, one income stream `y_tot`, one asset `A_tot`, one budget `m_tot`. Two preference voices (the optimizer and the splurger), each making a *proposal* for total consumption.
- The bargaining rule: actual consumption is the weighted compromise `(1−ς)·c_opt_proposal + ς·c_spl_proposal`, where the optimizer proposes `cFunc_std(m_tot)·p_tot` and the splurger proposes `y_tot`.
- The optimizer's cognition: naive — proposes `cFunc_std(m_tot)` without modelling the bargain. Acknowledged as a bounded-rationality feature.
- The asset update: `A_tot' = M_tot − C_tot` (the household's actual saving, which differs from what the naive optimizer believes it is saving by `ς·(c_opt_proposal − y_tot)`). Reference to `(CDC-1)` in [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md).
- The welfare aggregator: `u(C_tot)` for the household — the standard public-good default in the household-economics literature and the aggregator the code implements.
- Side-by-side comparison table with ESC: what each one identifies `aNrm` with, what each evaluates cFunc at, what each treats as the welfare aggregator, what each requires for internal consistency. (Reference the fuller table in [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md) §6.)
- Honest acknowledgment: the paper text is consistent with both readings, with leans in different places. Section 2 of the paper needs an explicit choice and a clarifying paragraph.

**Sources:**

- [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md) (primary — the CDC section is the formal content; this document elaborates in prose).
- [`history/20260423_coauthor-meeting-ai-summary.md`](../history/20260423_coauthor-meeting-ai-summary.md) (context for the action item — specifically items 1, 2, and 8 of the Zoom summary).
- [`notes_on_section6_correction.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_section6_correction.md) (the bargain framing, retained from the parts not retracted).
- [`plans/20260423_estimate-ESC-in-parallel.md`](20260423_estimate-ESC-in-parallel.md) (referenced as the path to producing an ESC counterpart calibration for comparison).

## 5. Mapping: old → new

| Old document | What happens to it |
|---|---|
| [`results_dont_change_much.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/results_dont_change_much.md) | Header note added: "Superseded by [`response_to_20260423_meeting/01_results_dont_change_much.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/01_results_dont_change_much.md)". File retained for historical record. |
| [`why_one_parameter_one_moment_suffices.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/why_one_parameter_one_moment_suffices.md) | Header note added: "Superseded by [`response_to_20260423_meeting/02_target_level_identity.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/02_target_level_identity.md)". File retained. |
| [`notes_on_section6_correction.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_section6_correction.md) | Header note added: "Three of five strands retracted; see [`response_to_20260423_meeting/01_results_dont_change_much.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/01_results_dont_change_much.md) for the current positive account and [`03_household_bargaining_model_writeup.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/03_household_bargaining_model_writeup.md) for the surviving CDC framing." File retained. |
| [`notes_on_bound_pair_equivalence.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_bound_pair_equivalence.md) | Header note added: "Conclusions revised after target-level analysis showed first-order equivalence with proper β re-calibration; see [`response_to_20260423_meeting/01_results_dont_change_much.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/01_results_dont_change_much.md) and [`02_target_level_identity.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/02_target_level_identity.md)." File retained. |

The retained files become a historical record of the day's evolving understanding. The new subdirectory becomes the canonical reference.

## 6. Construction order

Dependencies (write earlier ones first):

1. [`02_target_level_identity.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/02_target_level_identity.md) — purely technical, no dependencies on sibling documents.
2. [`01_results_dont_change_much.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/01_results_dont_change_much.md) — depends on (2) for the technical core.
3. [`03_household_bargaining_model_writeup.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/03_household_bargaining_model_writeup.md) — depends on [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md) and on the CDC framing that survives (1) and (2).
4. [`00_README.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/00_README.md) — written last, after the three substantive documents exist.

Then add the header notes to the four superseded documents.

## 7. Sign-off criteria

The set is complete when:

- All four numbered documents (00, 01, 02, 03) exist and are internally consistent.
- The README orients a fresh reader and explicitly names what is out of scope.
- The specific action item "Write down the alternative household-bargaining model" is addressed by [(3)](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/03_household_bargaining_model_writeup.md).
- The two centerpieces are clearly identified and standalone-readable.
- All superseded documents have header notes pointing to the current canonical version.
- Cross-references between the new documents, and between them and [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md), are correct (no broken internal links).

## 8. Estimated effort

- Centerpieces (1) and (2): 60 minutes each — they exist in draft form, this is mostly polishing and incorporating the multi-parameter caveat and the references to `(CDC-1)` / `(ESC-1)`.
- (3) Household-bargaining write-up: 90 minutes — the substantive new piece; draws heavily on the [`models_CDC_and_ESC.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md) canonical reference.
- (0) README and header notes on superseded files: 30 minutes.

**Total:** ~4 hours of writing time.

## 9. What this plan does NOT include

The earlier version of this plan proposed three further documents: a retractions memo, a consumption-calculation-bug investigation, and a path-forward proposal. They are explicitly dropped from this version:

- **Retractions memo (formerly `04_what_was_retracted_and_why.md`).** The retractions are best absorbed by the header notes on the superseded documents ([`notes_on_section6_correction.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_section6_correction.md) and [`notes_on_bound_pair_equivalence.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_bound_pair_equivalence.md)), which already point the reader to the current canonical version. A standalone retractions memo risks giving them more weight than warranted and lacks a clear positive claim to stand on.
- **Consumption-calculation-bug investigation (formerly `05_consumption_calculation_check.md`).** Edmund's specific concern (from item 6 of [`history/20260423_coauthor-meeting-ai-summary.md`](../history/20260423_coauthor-meeting-ai-summary.md)) was not accompanied by a line reference; the follow-up is waiting on him to point to the exact line of code he has in mind. Writing a speculative investigation before that pointer arrives would produce something that has to be redone.
- **Path-forward proposal (formerly `06_path_forward.md`).** The interpretation decision, the welfare-recompute question, and the QE publication question are collectively material for the live conversation, not something to be unilaterally proposed in a document. Better handled in the meeting than written down.

Other items explicitly not in scope:

- Running the ESC parallel-estimation pipeline. That's a separate plan ([`plans/20260423_estimate-ESC-in-parallel.md`](20260423_estimate-ESC-in-parallel.md)); the writing here can be done before or after the parallel-estimation runs.
- Drafting the actual paper-text revision for Section 2 of HAFiscal. That's a deliverable for after the interpretation decision is made.
- Producing welfare-6 numbers under the chosen interpretation with adequate sample size. That follows the interpretation decision.

## 10. Open question for the user before execution

- Subdirectory or flat layout? The plan above proposes a subdirectory (`response_to_20260423_meeting/`). Alternative: keep the new documents in the existing `HAFiscal_splurge_budget_inconsistency/` with a `20260423_` prefix on each. The subdirectory approach groups the response cleanly; the prefix approach keeps everything findable with a single `ls`.
- Do you want me to circulate [(3)](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/03_household_bargaining_model_writeup.md), the household-bargaining write-up, to coauthors as soon as it's drafted, or hold it until the full set is ready? Edmund and Håkon expect [(3)](../BUGS_private/HAFiscal_splurge_budget_inconsistency/response_to_20260423_meeting/03_household_bargaining_model_writeup.md) by tomorrow's meeting.
