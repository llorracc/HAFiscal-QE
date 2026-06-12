# Post-merge plan — canonicalize the default solution approach (+ follow-ups)

**Status:** ACTIVE

**Date:** 2026-06-10. **Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`, after merging this
session's commits (`3a76ab2b` tradeoff diagnostic, `c2848ba8` welfare-method decision, `b0fab4ce`
wind-down) on top of the `ensure-connected-TM` merge (`59450e67`).

**Premise:** this session settled *which method is canonical* for welfare and multipliers, but the code
still defaults to the OLD / opt-in behavior. Plan A canonicalizes + wires the decisions; Plans B–I stage
the follow-ups they imply. Each plan below carries a **Considerations** block: the findings and reasoning
that motivate it, the alternatives weighed, and the risks — so it can be picked up cold.
Decision source: `conclusions_private/2026-06-10_welfare_method_unified_MC.md`.

**Target branch for everything here: `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`** (the canonical
working branch). All of this lands on and targets `_TM-vs-MC`; there is **no upward merge** to a parent
(the earlier "merge into upgrade-validation" idea is retracted — see
`plans/20260610_integration-target-TM-vs-MC.md`). "Post-merge" in the title just means *after this
session's commits landed on `_TM-vs-MC`*, which they have.

## What we decided (the canonical solution approach)
- **Welfare:** MC + CRN + **stratified-shuffle** for ALL cells. Report `check_*`, `taxcut_*`, `ui_rec`,
  `ui_rec_AD`; exclude only `ui_norec` (0/0). TM-a is a TaxCut-only backup cross-check.
- **Multiplier:** TM a-indexed for Check + TaxCut; the UI multiplier wants MC + stratified-shuffle.
- **Solution config:** interpretation **ESC**; UI encoding **bug_fix** (6-state); **theGICfactor 0.9995**;
  production grid **aMax=1300 / aCount=200**; matched-triple {PermGroFac-fix, calibration, ESC}.
- **Why MC for Check:** the fixed-dollar check needs the permanent-income LEVEL (`C/pLvl`); Harmenberg
  can't supply it; the bucketed-5D TM biases it (`φ(pLvl)` bucketing).

## Current-state audit (2026-06-10)
- `HAFISCAL_MC_SHUFFLE` opt-in, default off (`Simulate.py:351`, `welfare6_scenario.py:344`).
- `HAFISCAL_SHUFFLE_MRKV_TRANSITION` defaults to **`'shuffle'`** — the BIASED plain variant (+8.26% UI),
  NOT `'stratified'` (`AggFiscalModel.py:921`). **Footgun.**
- `aMax` default **500** (`tm_methods.py:4808`, env override); cal at **1300** → matched-pair gap.
- Welfare = do_all **Step 5b** (default on); multipliers = Step 5a (`do_all.py:38-41`).
- `HAFISCAL_UI_STATE_ENCODING` already defaults `bug_fix` (`EstimParameters.py:191`). ✓
- **Calibration ambiguous:** merge's `f29aacd9` N=1600-warm re-est vs BUG-053 cold-multistart → Plan E.

---

# Execution contract — each plan is standalone + idempotent (given its preconditions)

Every plan below is written to satisfy three properties so the repo is **working after each one**:
1. **Preconditions stated.** True dependencies are explicit. "Standalone" here = *self-contained given
   its preconditions*, NOT dependency-free — there is a real chain (E→A; G→A/F; A→H; H→I), so the plans
   are NOT runnable in arbitrary order.
2. **Green acceptance gate.** Each plan ENDS by confirming the repo works. Shared baseline:
   `reproduce_min.sh` (or the HS_Only→Reduced_Run cascade) passes, plus the standing-rule checks where
   MC is involved (CRN within a seed-offset, MULTIPLE seed-offsets for the SE, the TM-a drift companion).
   Any result-moving change is CLASSIFIED (error vs sample — `feedback_error_vs_sample_changes`) and
   logged in the QE-divergence ledger before the plan is "done."
3. **Idempotent / reversible.** Re-running is a no-op or deterministic; config flips are guarded
   (already-set → no change); every change is revertible via a toggle or git.

| Plan | Preconditions | Acceptance (everything-works gate) | Idempotent / rollback |
|---|---|---|---|
| **A** canonicalize | E (named cal), G (HARK PR) | smoke green under new defaults; welfare table has `ui_rec`/`ui_rec_AD`, no `ui_norec`; multiplier table present; `qe_fidelity` toggle still reproduces legacy; moved numbers classified+ledgered | flips guarded (already-canonical = no-op); revert via `qe_fidelity`/`LEGACY` env |
| **B** a-indexed perf | a reference timing + reference multiplier numbers captured first | optimized path bit-identical (or within stated tol) to reference; smoke green; speedup measured | deterministic output; ship behind a flag (default off until validated); revert = flag off |
| **C** 6-D TM-check | MC Check welfare exists (the thing it validates) | 6-D TM Check welfare matches MC within the bar; smoke green | read-only validator; re-run reproduces |
| **D** aMax wiring | none | downstream TM-a actually uses aMax=1300; cal-grid matches; smoke green; grid-change classified+ledgered | 500→1300 idempotent (already = no-op); revert via `HAFISCAL_TM_AMAX`/default |
| **E** cal reconcile | Baseline multiplier landed (or explicitly marked pending) | exactly ONE named canonical cal; matched-triple verified; downstream `_ESC.txt` consistent; ledger has Baseline mult vs 1.20/0.99; smoke green | a decision (re-run = no-op once named); NO accidental re-estimation (opt-in only); cal files git-versioned |
| **F** UI multiplier (MC+shuffle) | G, A2 (stratified default) | UI multiplier via MC+stratified-shuffle; multi-seed SE below bar; smoke green | CRN → same seeds = same result; method selectable |
| **G** HARK PR #1776 | none | PR #1776 confirmed in pin (stratified-shuffle reproduces ui_rec +0.05%); clean-clone `uv sync` works | verify is read-only; re-pin idempotent (already = no-op); revert the pin |
| **H** QE-matching | A (+`qe_fidelity` hatch), E | QE-comparison report (QE-baseline + current-version characterization); divergences classified+ledgered; `qe_fidelity` reproduces published within bar | analysis; deterministic under fixed config/seeds |
| **I** friendly urates | H (gate lifted) | friendly-urate cal meets the adoption rule (fit ≤~5%, mult ±3%); decision recorded | gated; parallel Step-2; cold-multistart deterministic |

**Caveat (honest):** "standalone + idempotent" as encoded above means *explicit preconditions + a green
acceptance gate + safe re-run* — it does NOT mean dependency-free. Respect the chain.

---

# Plan A (PRIMARY) — canonicalize + implement the default solution approach

**Action.** A0 audit-delta → A1 single canonical-config source of truth → A2 flip defaults (with revert
toggles) → A3 welfare/multiplier table generation → A4 cascade-gated validation smoke → A5 docs.
Concrete A2 changes: `SHUFFLE_MRKV_TRANSITION` default `'shuffle'`→`'stratified'`; welfare default
shuffle-on + newborn-fix=transition; `aMax` 500→1300; explicit `qe_fidelity`/`LEGACY` escape hatch.

**Considerations.**
- *Why now, why at all.* The welfare method is the END of a months-long arc, not a fresh idea: the
  2026-05-10 user-approved MC+CRN+**IS** decision → IS found to carry a **+10% `ui_rec`** joint-state
  bias (`project_welfare6_is_bias_diagnosis`) → **stratified-shuffle** (BUG-044 / HARK PR #1776)
  validated as the production variance reduction (`ui_rec` +0.05%) → brute-force 5×N as the unbiased
  fallback. Encoding the endpoint as the default stops that arc being re-litigated and stops the repo
  silently doing something we've already rejected.
- *The decisions aren't in the code.* They live in conclusions docs + session memory; the standard
  pipeline (do_all Step 5b) still runs the opt-in/old behavior. A third party reproducing the paper
  would **not** get the canonical method. Canonicalization is what makes "the default run" == "the
  decided method."
- *The footgun is a correctness hazard, not convenience.* `SHUFFLE_MRKV_TRANSITION='shuffle'` (the
  default) is the variant that scrambles per-agent identity, breaks CRN, and biased UI **+8.26%**.
  Anyone who turns shuffle on for speed, without knowing to also set `stratified`, gets silently-wrong
  UI. This alone justifies A2.
- *Matched-triple (BUG-051).* The config bundles {PermGroFac-fix, calibration, ESC}; they must move as a
  unit (a β estimated under one regime must never be paired with another regime's solver/encoding). A
  single source of truth (A1) is the mechanism that keeps them coupled; scattered env flags across
  `Simulate`/`welfare6_scenario`/`AggFiscalModel`/`tm_methods` are exactly what produced the footgun and
  the aMax mismatch.
- *The governance risk that shapes A2.* Per `feedback_error_vs_sample_changes`, a default change that
  MOVES a published number must be CLASSIFIED (error-fix vs sample/convergence) and logged in the
  QE-divergence ledger — never silently flipped. So A2 is not a blind switch: each default that shifts a
  result gets the error-vs-sample treatment, and we keep revert toggles + the `qe_fidelity` escape hatch
  because the QE-matching runs (Plan H) need the legacy behavior to reproduce the published numbers.
- *Scope guard.* A is wiring + tables + validation + docs — no new science. The science was this
  session's; A just makes it the default.

**Dependencies:** Plan E (canonical calibration — blocks A1), Plan G (PR #1776 — blocks the shuffle
default), Plan D (aMax — folds into A2). **Effort:** medium.

---

# Other candidate plans (proposed)

## Plan B — a-indexed Baseline multiplier performance (HIGH)
**Action.** Make the a-indexed Baseline multiplier practical. Options: (1) profile + optimize the
`recessionCheck` AD TM build; (2) fast/slow-path policy (m-indexed for iteration, a-indexed for the
final number); (3) a **coarser `pLvl` grid for the multiplier TM only**.

**Considerations.**
- *The trigger.* This session's Baseline multiplier ran **~22 hr**. Diagnosed (memory
  `project_aindexed_baseline_multiplier_slow`): `recessionCheck` AD alone = 10.5 hr, **~29× per-iteration**
  vs the other recession policies, but it **converges cleanly** (5 iters) — so it's cost, not
  non-convergence.
- *Root cause, and what it is NOT.* The cost is the a-indexed TM build at the Check's `pLvl`-laden state
  space. It is **not** the calibration (per-solve EGM ~2–3 s; the new (β,∇) are irrelevant) — an earlier
  "0.9995 made it slow" hypothesis was measured false (commit `3a76ab2b`). The decomposition: a-indexed
  Baseline is **inherently ~9 hr** (known since 2026-04-29, `..._aindexed-too-slow.md`) × **~2.25×** from
  the `bug_fix` 6-state encoding (squares the state space) + ESC. Also corrects an in-session error of
  mine ("m-indexed is the baseline / first a-indexed run") — a-indexed IS the production method.
- *Why option (3) is the interesting one.* The **multiplier** is a linear aggregate and is far less
  sensitive to `pLvl` bucketing than the **welfare** (convex, MU-weighted) — BUG-040/041 already closed
  the Check *multiplier* MC-vs-TM gap to paper-precision (+1.6%) even with TM's `pLvl` handling. So a
  *coarser* `pLvl` axis may be fine for the multiplier TM while welfare still needs the fine joint (which
  is why welfare goes to MC). That asymmetry is the lever.
- *Tradeoffs.* (1) addresses the root but unknown payoff + correctness risk; (2) zero code risk but
  m-indexed collapses ξ (not the "right" method) — fine for iteration, not the final; (3) most targeted
  but needs a convergence study of the multiplier in `pLvl` resolution.
**Effort:** medium–large.

## Plan C — 6-D provable TM-check for Check welfare (validation luxury, DEFERRED)
**Action.** Build the 6-D TM-check (`pLvl` a real grid axis, per-agent check, no bucketing) as an
independent validator of the MC Check welfare.

**Considerations.**
- *The gap it fills.* Check welfare currently has **no TM cross-check** — TM's bucketed-5D carries a
  structural `φ(pLvl)` bucketing bias (+0.86–0.95%, diagnosed 2026-06-09, memory
  `project_bucketed5d_check_bucketing_structural_limit`), so MC is the *only* method. For TaxCut the 5-D
  TM converged (−0.14%) and serves as a second method; Check has nothing equivalent.
- *Why it's a "luxury."* MC is canonical for Check regardless, and MC with CRN + multi-seed SE is itself
  defensible. The 6-D would give a second, independent confirmation — valuable mainly if a referee asks
  "how do you know the MC Check welfare is right?" without a non-MC corroborator.
- *Why deferred.* It's a large build (the 6th dimension is a real `pLvl` grid axis → big object), and it
  buys confirmation, not a new result. Reassess if/when a second-method Check validation is demanded.
**Effort:** large. **Value:** medium (confirmation, not a result).

## Plan D — aMax=1300 downstream wiring (SMALL; folds into A2)
**Action.** Production `aMax` default 500 → 1300, or set `HAFISCAL_TM_AMAX=1300` in the Step-5/reproduce
scripts.

**Considerations.**
- *Matched-pair correctness.* The canonical calibration is estimated at **aMax=1300**; any downstream
  TM-a that falls back to **500** truncates the high-β tail the cal was fit to → distorted ergodics for
  the most-patient atoms. A cal and the grid it's used on are a matched pair.
- *Where 1300 came from.* The bucketed-5D tail-truncation diagnostic: the old aMax=500 truncates the
  College most-patient support (to ~867); production `aMax = 1.5×max ≈ 1300` (memory
  `project_tm_a_production_grid`). So 1300 is not arbitrary — it's the tail-coverage decision.
**Effort:** small.

## Plan E — calibration reconciliation + pending Baseline multiplier (PREREQUISITE; blocks A1)
**Action.** Decide THE canonical calibration (reconcile BUG-053 cold-multistart 0.9995 vs the merge's
`f29aacd9` N=1600-warm). Retrieve the pending a-indexed Baseline multiplier (running) and record it vs
BUG-047's 1.20/0.99 in the QE-divergence ledger.

**Considerations.**
- *Why it blocks everything.* A1 must NAME a single canonical calibration; right now there are two on the
  branch and it's ambiguous which the default config should point at.
- *Which is authoritative, and the principle.* `feedback_no_warmstart_when_validating_solver_fix`: the
  re-estimation of a *fix* must be **cold multi-start** (warm-starting risks lock-in to the pre-fix
  basin). BUG-053 was cold-multistart → it's the validated one. The N=1600-warm ("beta moves
  negligibly") is plausibly a confirming refinement, but that must be checked, not assumed — and if it
  differs materially, the cold result wins. Output: one named calibration + a note on the warm result.
- *The pending number.* The Baseline multiplier run was left running (detached) and writes to
  `Tables/Baseline/Multiplier.tex`; retrieving + recording it closes the deferred item and gives the
  Check/TaxCut "multipliers unchanged" confirmation the BUG-053 work hinged on.
**Effort:** small–medium.

## Plan F — UI multiplier via MC + stratified-shuffle (HIGH; parallels the welfare UI fix)
**Action.** Implement/validate the UI multiplier via MC + stratified-shuffle so it is reportable like UI
welfare. Can fold into A3's multiplier handling.

**Considerations.**
- *Driven by a hard requirement.* UI must be reported (user directive) — UI extensions are one of the
  paper's three policies, on BOTH the multiplier and welfare sides.
- *Why TM doesn't do it.* The UI multiplier is sample-noise-dominated (the extension reaches only ~5–10%
  of agents); the historical "UI multiplier unreliable" finding was exactly this. TM's a-indexed
  multiplier inherits the small-affected-population problem.
- *Why the same fix works.* Stratified-shuffle's exact urate quotas make the count of UI-extension agents
  *exact*, killing the rare-event variance — the same mechanism that made UI *welfare* reportable
  (+0.05%). So the UI multiplier and UI welfare share one root and one fix.
- *Caveat.* The near-zero-variance (quota-exact) regime wants the friendly urates (Plan I, gated); at the
  current SCF-2004 urates stratified-shuffle reduces but isn't perfectly quota-exact, so validate the
  multi-seed SE before headlining.
**Effort:** medium.

## Plan G — HARK PR #1776 verification (SMALL, BLOCKING; folds into A0)
**Action.** Confirm the stratified-shuffle fix (HARK PR #1776) is in the pinned HARK ref; if not, re-pin
or cherry-pick.

**Considerations.**
- *Why blocking.* The entire canonical welfare method rests on stratified-shuffle. If PR #1776 isn't in
  the pin, `SHUFFLE_MRKV_TRANSITION='stratified'` either errors or silently falls back to the biased
  plain shuffle — i.e., the footgun fires even after we "fix" the default.
- *The re-pin coupling.* The pin has been moving (memory `project_release_v0170_reproduction`: HARK
  advanced d15660d5 → ce0cb5d6, and a clean clone ImportErrors if the rev isn't bumped). So verifying
  PR #1776 is in the pin must be done against the *current* `pyproject` rev, and any re-pin must clear
  the existing import-compatibility bar.
**Effort:** small.

## Plan H — QE / original-paper-matching analysis (the GATING priority / destination)
**Action.** Complete the QE-matching under the canonical approach (at the CURRENT SCF-2004 urates).

**Considerations.**
- *It's the destination.* This is the user's stated near-term goal ("the analysis that tries to match the
  original paper"), and it's what the urate gate (Plan I) explicitly waits on.
- *The subtlety that ties it to Plan A.* Matching the *published* QE numbers may require the **legacy**
  config/method, not the new canonical one — a canonical-method run can legitimately DIVERGE from
  published (that's the error-vs-sample story). So QE-matching likely runs through Plan A2's `qe_fidelity`
  escape hatch, and every divergence from published gets the QE-divergence ledger treatment. This is the
  reason A2 must preserve a clean revert path rather than delete the old behavior.
- *The procedure is fixed.* Use the QE baseline tag `v2026-01-09-18-17` (NOT `resubmitted-to-QE`), and
  open every comparison with explicit "QE baseline" vs "current version" characterization (memories
  `reference_hafiscal_qe_baseline`, `procedure_qe_comparison_report`).
**Effort:** large.

## Plan I — shuffle-friendly urate recalibration (GATED on H)
**Action.** Prepare a parallel Step-2 with friendly urates (D 0.090 / HS 0.045 / C 0.025) → quota-exact
shuffle at moderate N. Adoption gated.

**Considerations.**
- *The leverage.* Quota-exact shuffle gives near-zero sampling variance on aggregates IF N is quota-exact;
  the current SCF urates push quota-exact N far above 10k. The friendly urates drop it to ~5k–18k (18× /
  11× / 2.78×) with sub-6% urate changes (memory `project_shuffle_friendly_recalibration`; the math:
  `π_noUB = Urate/9`, quota-exact `N` divisible by `LCM(denom, 49)`).
- *Why gated.* User decision 2026-06-10: do NOT adopt until the QE-matching analysis is complete —
  because QE-matching must use the published urates first, and the urates are calibration-coupled
  (changing them needs a discount-factor re-estimation, so adoption can't be casual).
- *The adoption rule.* Only adopt if the friendly-urate calibration achieves Step-2 fit within ~5% AND
  Check+TaxCut multipliers within ±3% of the current calibration (UI deprecated for that comparison).
**Effort:** medium.

---

## Recommended sequencing
1. **Prereqs (small, first):** G (PR #1776), E (calibration reconcile + retrieve the Baseline
   multiplier), D (aMax) — all fold into Plan A's early phases.
2. **Plan A** — canonicalize + implement, with **F** (UI multiplier via MC+shuffle) as part of A3.
3. **Plan H** — QE-matching, on the canonical config / via the escape hatch (the priority destination).
4. **Plan B** — a-indexed multiplier speed, in parallel / once the ~day-long runs become blocking.
5. **Gated/optional:** **I** (friendly urates) after H; **C** (6-D TM-check) if the paper wants a
   second-method Check-welfare validation.

**The one judgment call to flag up front:** Plan E is a true prerequisite — A1 cannot name "the canonical
calibration" until BUG-053 (cold) and the merge's N=1600-warm are reconciled. Start there.

---

## Prerequisite status (2026-06-10 walk-through)
- **G (HARK PR #1776): ✅ PASS here.** `'stratified'` is routed correctly — `AggFiscalModel.py:945`
  implements rank-based stratified locally (CRN-coupled); the default `'shuffle'` takes the biased
  `else` path (footgun confirmed → A2's flip is right). HARK `ce0cb5d6` has the stratified mode
  committed. **Follow-up (non-blocking):** HARK is wired as a local editable path
  (`../../econ-ark/HARK`), NOT a public git-rev pin → for clean-clone reproducibility/release, pin a
  public `econ-ark/HARK` rev ≥ the stratified merge.
- **E (calibration reconcile): ✅ RESOLVED — no ambiguity.** Canonical cal = BUG-053 cold-multistart
  (`d1a06a9c`). The merge's `f29aacd9` N=1600-warm was a grid-convergence VALIDATION (β moves negligible:
  D +0.15%, HS/C <0.01%; "re-canonicalization NOT warranted"; canonical files restored byte-identical;
  warm archived under `Results/_fanout_explorations/`). Baseline multiplier LANDED (22.5 hr): Check
  rec+AD **1.235**, TaxCut **1.012** (~+2–3% vs BUG-047 1.20/0.99 — close, not identical; UI blank = TM
  can't do it; recorded in the QE-divergence ledger). **→ A1 is unblocked.**

(The earlier "Start there [E]" line is superseded — E is done. Next gate is **Plan A**.)
