# Plan: Prompt for a new AI session — bound-pair vs TM/MC equivalence analysis

**Date:** 2026-04-21
**Status:** Planned; deliverable is a prompt to paste into a fresh AI session on another machine
**Branch target:** user to specify — Edmund's latest bound-pair work is on a separate branch not merged into `_TM-vs-MC` as of this writing

---

## 1. What this plan produces

A copy-pasteable prompt (§5 below) that starts a fresh AI session with enough context to:

1. Understand the bound-pair vs. within-household interpretation debate without re-litigating it.
2. Answer this specific question: **is Edmund's latest bound-pair analysis substantively different — in the sense of producing different numerical results — from the calculations the current TM/MC code performs?**
3. If they're equivalent as mathematical specifications, the bound-pair analysis + the existing TM and MC can serve as three independent implementations that cross-check each other. If they're substantively different, document exactly where and why.
4. Write the answer up as a `…_response-further.md` companion to Edmund's notebook and the existing response doc.

## 2. Context summary (so the plan is self-contained without having to dig)

### 2.1 The dispute in one paragraph

HAFiscal's code reports per-household consumption as `c_reported = (1−ς)·cFunc(m) + ς·y` (optimizer rule plus a splurge tied to income) but evolves assets as `a_next = m − cFunc(m)` — omitting the splurge from the asset update. The identity `c_reported + a_next = m` therefore fails by `ς·(y − cFunc(m))` per household per period. The splurge-in-budget fix makes the asset update consistent with `c_reported`. Edmund's bound-pair interpretation argues that each code "agent" is not one household but a weighted pair of (1−ς) optimizer + ς hand-to-mouth; under that reading `aNrm` tracks only the optimizer, `cLvl_splurge` is pair-aggregate consumption, and the economy-wide budget identity holds. The existing response (`bound-pair-assessment.md`) argues B doesn't rescue the code because the internal inconsistency is interpretation-independent. **The new question the user wants asked is more specific:** regardless of which interpretation is "right", does Edmund's *implementation* of the bound-pair analysis produce the same numbers as the current TM and MC code? If yes, they're equivalent specifications. If no, which is doing what the other isn't?

### 2.2 Where things live in the tree (this branch)

- `BUGS_private/HAFiscal_splurge_budget_inconsistency/00-README.md` — reading order, overview.
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/distilled-summary.md` — the distilled argument for the splurge-in-budget fix.
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/bound-pair-assessment.md` — the current (summary) response to the bound-pair argument.
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/_archive/bound-pair-interpretation.md` — Edmund's original bound-pair memo.
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/_archive/bound-pair-interpretation_response.ipynb` — the prior-session AI response notebook.
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/_archive/splurge-accounting_math-and-code.ipynb` — the math+code notebook underlying the bug analysis.
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/mwe.py` — 30-line minimum working example exhibiting the budget-identity violation and the fix.
- `Code/HA-Models/FromPandemicCode/AggFiscalModel.py` — lives the asset-update logic (`cLvl_splurge` at line 1054; splurge-in-budget vs splurge_old toggle at line 1071).
- `Code/HA-Models/FromPandemicCode/tm_methods.py` — TM side of the model.

**NOT in this tree:** Edmund's latest revised bound-pair analysis. It lives on the remote branch `origin/maintain_bound_pair_fix_splurge`, in three new files (none of which are in the current branch):

- `BUGS_private/HAFiscal_splurge_budget_inconsistency/notes_on_distilled_summary.md` — the core bound-pair argument, including a Campbell-Mankiw equivalence proof (commit `f96a77b1`) and subsequent edits / restructuring (commits `a217f4ca`, `7863459c`, `12659e98`).
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/plan_fix_splurge_estimation.md` — Edmund's plan (commit `874a24d6`).
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/comparison_splurge_estimation.md` — results he obtained after running the plan (commit `8e1ab0a6`), with a later methodology switch (commit `180d7561` — "Changes method to MC for welfare tables").

The **prior `_response`** is a pair: `bound-pair-assessment.md` (the text response, already in this tree) and `_archive/bound-pair-interpretation_response.ipynb` (the earlier-session notebook, also in this tree). These respond to *earlier* Edmund material (the original `_archive/bound-pair-interpretation.md`), NOT to his latest `notes_on_distilled_summary.md`. So the gap is: there is no existing response to the Campbell-Mankiw-equivalence argument + Edmund's re-estimation with the bound-pair interpretation held constant. That's what the new session fills.

### 2.3 What's been decided so far and what the new session should NOT re-litigate

- Whether interpretation A or B is what the paper's Section 2 *describes*. `bound-pair-assessment.md` and the text of the paper have settled this: A.
- Whether the splurge-in-budget fix should be applied to the code for publication. This is under active coauthor discussion; the new session should not advocate on this.
- Whether HAFiscal-QE's published numbers are bug-inflated on UI-recession cells. Already established and resolved this session: yes, by ~20%; root cause is the catalogue of bug fixes in the current branch (see `history/20260420-ui-recession-gap-resolution.md`).

## 3. The specific analytical question

Frame it as a three-way comparison:

1. **MC implementation** (current code, `AggFiscalModel.py::AggFiscalType.run_experiment`): simulates N agents over T periods; each agent holds a single `aNrm` state that evolves by the buggy or fixed asset-update rule.
2. **TM implementation** (current code, `tm_methods.py::run_experiment_tm`): discretises the distribution of `(m, j)` on a grid, propagates it analytically. Same underlying model, different numerical method.
3. **Bound-pair implementation** (Edmund's latest): treats each code agent as a (1−ς):ς weighted pair of optimizer + HtM; `aNrm` = optimizer wealth; per-period aggregates pool the two.

Under the current code, MC and TM already agree to within ~1–2 % on target moments and multipliers (confirmed by TM-vs-MC validation tests). The question is: **does a bound-pair implementation specifying the same economy produce the same moments and multipliers?**

Four possible outcomes and their implications:

| Outcome | What it means |
|---|---|
| Bound-pair ≡ MC/TM numerically | The three implementations are specifications of the same economy. Semantic / interpretation disagreement only; the code implements a shared mathematical model. The three can be used as independent cross-checks (good for the paper's robustness story). |
| Bound-pair = MC-with-buggy-asset-update, ≠ MC-with-splurge-in-budget-fix | Edmund's bound-pair IS a valid re-interpretation of the unfixed code, and "fixing" the budget identity under A's interpretation is the same as rejecting B's interpretation. The two are the same implementation under different names. |
| Bound-pair ≠ MC in ways that imply different aggregates even under identical parameters | Bound-pair is a genuinely different specification (e.g., different K/Y aggregation, different welfare aggregation). Document exactly where. |
| Bound-pair cannot be defined precisely enough to compute numerical output | The proposal is an interpretive lens, not a runnable alternative. It cannot serve as a numerical cross-check. |

## 4. What the new session should do

**Phase 1 — read** (probably ~30 min):
- All of `BUGS_private/HAFiscal_splurge_budget_inconsistency/` (paths in §2.2).
- Edmund's latest bound-pair notebook (user-supplied path).
- The prior-session `_response` doc (user-supplied path).
- Skim `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1054-1090` (splurge asset-update logic) and `tm_methods.py` top sections.
- `history/20260420-ui-recession-gap-resolution.md` for context on the broader branch state.

**Phase 2 — specify** (probably ~1 h):
- Extract, in math notation, what Edmund's bound-pair analysis *claims* each code variable represents (pLvl, mNrm, cNrm, cLvl_splurge, aNrm) and what the per-period transition rule is.
- Write down the equivalent specification for MC and TM.
- Identify where the three specifications agree and disagree *in principle* (before any numerical test).

**Phase 3 — experimental test** (probably ~2–4 h):
- Implement the bound-pair aggregation rules directly over an existing MC panel (the seed0 pickle from `welfare6_scenario_results_Baseline_seed0/`). Specifically: compute K/Y, Lorenz, welfare, and consumption multipliers under Edmund's bound-pair aggregation (weighted (1−ς) · aNrm + ς · 0; pair-aggregate consumption; etc.) and compare against the existing per-household aggregates.
- If the bound-pair specification is well-defined enough to run end-to-end as an estimation target, attempt a minimal re-estimation under it (ς bound-pair vs ς within-household) using the `mwe.py` style at small N.
- Verify or refute: do the bound-pair-aggregated moments match what the current code emits?

**Phase 4 — write up** (probably ~1 h):
- Produce `<edmund-notebook-dir>/<edmund-notebook-stem>_response-further.md` (exact location determined by where Edmund's notebook lives).
- Structure: executive summary → §1 what each interpretation specifies mathematically → §2 what the code actually computes → §3 experimental comparison with numbers → §4 verdict (same / different / undefined) → §5 implications for the coauthor conversation and paper.

**Stopping criteria for the session:**
- Stop if a single experimental comparison shows bound-pair ≢ MC numerically and documents the discrepancy. No need to exhaust all cell/scenario combinations.
- Stop if the bound-pair specification turns out to be interpretive-only (no well-defined per-period transition) and that's clearly stated.
- Expected total wall: 4–8 hours of focused work.

## 5. The prompt (copy-paste to the new AI session)

Paths and branch name below are already resolved — paste as-is.

```
You are a fresh AI session picking up a task mid-project. I need a
careful, experimentally-backed analysis of whether a new proposal
(Edmund's revised bound-pair analysis) is substantively different from
what the HAFiscal TM and MC code compute today. If they amount to the
same thing, the three implementations can serve as robustness checks on
each other. If they differ, I need to know exactly where and why.

## Repository state

The repo is at /home/shared/github/llorracc/HAFiscal-Latest (adjust if
different on this machine). You are on a fresh checkout; fetch and
switch to Edmund's branch:
    git fetch origin
    git checkout maintain_bound_pair_fix_splurge

## Bootstrap reading (in order, ~30 min)

Read these before any analysis.  Order matters — context first.

1. plans/20260421_bound-pair-vs-TM-MC-equivalence-session.md
   — The plan that led to this task.  §§1–4 for framing; §§2.3 lists
     the points already settled — do NOT re-litigate them.

2. BUGS_private/HAFiscal_splurge_budget_inconsistency/00-README.md
   BUGS_private/HAFiscal_splurge_budget_inconsistency/distilled-summary.md
   BUGS_private/HAFiscal_splurge_budget_inconsistency/bound-pair-assessment.md
   — The prior state of the bound-pair vs within-household debate.
     bound-pair-assessment.md is the prior-session AI response; it
     addresses the earlier Edmund material (_archive/
     bound-pair-interpretation.md), not his latest writeup.

3. BUGS_private/HAFiscal_splurge_budget_inconsistency/_archive/
       bound-pair-interpretation.md
       bound-pair-interpretation_response.ipynb
       splurge-accounting_math-and-code.ipynb
   — Earlier round of the debate, for reference.

4. Edmund's latest bound-pair analysis (all three new files, read
   in this order):
   a. BUGS_private/HAFiscal_splurge_budget_inconsistency/
         notes_on_distilled_summary.md
      — Core argument: Edmund defines the "bound-pair implementation"
        as an optimizer + HtM composite a la Campbell-Mankiw and
        provides a proof of equivalence with the paper's formulation
        (§2).  This is the primary target of the new analysis.
   b. BUGS_private/HAFiscal_splurge_budget_inconsistency/
         plan_fix_splurge_estimation.md
      — Edmund's plan for a revised splurge estimation under the
        bound-pair reading.
   c. BUGS_private/HAFiscal_splurge_budget_inconsistency/
         comparison_splurge_estimation.md
      — Numerical results from running the plan (MC-based welfare
        tables at the revised splurge).

5. Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1054–1090
   — Where the splurge vs splurge-in-budget asset-update logic lives.
   Code/HA-Models/FromPandemicCode/Parameters.py
   — Agent construction; what each "agent" is per the code.

6. history/20260420-ui-recession-gap-resolution.md
   — (On the `_TM-vs-MC` branch, not necessarily on Edmund's branch;
     check this file out if missing.)  Context on why the current
     branch's welfare numbers differ from HAFiscal-QE by ~20% on UI
     recession cells.  Background for the paper's state.

## The task

Answer this question precisely, backed by both derivation and code
experiments:

**Does the bound-pair specification, as implemented or proposed in the
files you read, produce numerical output equivalent to what the current
MC and TM code compute, on:**
  - K/Y calibration target,
  - Lorenz wealth shares at estimation targets,
  - Welfare-6 per cell,
  - Consumption multipliers (10-year horizon, with / without AD)?

If yes, document the equivalence: the bound-pair analysis, TM, and MC
are three implementations of the same economy and can cross-check each
other.

If no, document the substantive differences: which moments differ, by
how much, and why (identify the source in the mathematical specification).

If the bound-pair specification is not well-defined enough to produce
numerical output end-to-end, say that clearly and explain what's missing.

## Expected work

Phase 1 — Read (30 min).
Phase 2 — Write the three specifications (bound-pair, MC, TM) side by
  side in mathematical notation (1 h).
Phase 3 — Experimental tests using the existing MC panel at
  welfare6_scenario_results_Baseline_seed0/ (pickles of cLvl, pLvl,
  Mrkv_hist, AggIncome, AggCons for all 12 scenarios).  Re-aggregate
  per bound-pair rules and compare against per-household aggregation
  (2–4 h).  If bound-pair requires a parameter re-estimation, run a
  minimal estimation via mwe.py at small N.
Phase 4 — Write up findings (1 h).

Expected wall: 4–8 hours.

## Deliverable

A companion document at

  BUGS_private/HAFiscal_splurge_budget_inconsistency/
      notes_on_distilled_summary_response-further.md

(companion to Edmund's notes_on_distilled_summary.md; commit on the
same maintain_bound_pair_fix_splurge branch).

Structure it as:

  - Executive summary (1 paragraph: verdict — equivalent / different /
    undefined, and the key evidence).
  - §1  Specifications side-by-side: what each of bound-pair, MC, TM
    claims about each code variable (pLvl, mNrm, cNrm, cLvl_splurge,
    aNrm) and the per-period transition.
  - §2  What the code actually computes (with file:line references to
    AggFiscalModel.py and tm_methods.py).
  - §3  Experimental comparison: table of (K/Y, Lorenz, Welfare-6,
    multiplier) under bound-pair aggregation vs MC vs TM at Baseline
    calibration, with numerical discrepancies quantified.
  - §4  Verdict and open questions.
  - §5  Implications for the paper and the coauthor conversation:
    - If equivalent: the three can serve as independent robustness
      checks on each other; recommend which to present.
    - If different: which implementation does what the paper describes?
    - If undefined: what would be needed to make bound-pair executable?

## Ground rules

- Do not advocate on the publication question.  This analysis is about
  whether the specifications agree, not which is "right."
- Where possible, back derivations with code experiments.  A
  mathematical argument that reduces to "I think" without a numerical
  check is weaker than one backed by numbers from the existing pickles.
- If the experiment requires data that doesn't exist on the branch, try
  to generate it at small N (≤400 agents) for quick turnaround.
- Cite AggFiscalModel.py / tm_methods.py line numbers when describing
  what the code does.
- Keep the executive summary honest: if the verdict is "equivalent",
  say so plainly; if "different, in favour of MC", say so plainly;
  don't hedge for diplomatic reasons.

Begin with Phase 1 (reading).  Don't start coding before Phase 2
(writing out the specifications in math).  Don't start writing the
response before Phase 3 (experiments).

Good luck.  When you complete, commit the response file and push on the
same maintain_bound_pair_fix_splurge.
```

## 6. Before pasting the prompt — pre-flight checklist

All paths and the branch name are already resolved in the prompt (§5). The target machine needs:

1. The repo cloned; `git fetch origin` so `origin/maintain_bound_pair_fix_splurge` is available. `git checkout maintain_bound_pair_fix_splurge` lands on Edmund's branch.
2. A working Python environment with HARK 0.17.x pinned (`.venv-linux-x86_64` or equivalent; same as this machine).
3. For Phase 3 experiments: either access to `welfare6_scenario_results_Baseline_seed0/` pickles (~250 MB — copy from this machine or `scp` from a known location), or willingness to regenerate them locally at small N (~5 min per scenario at N=400 with auto-parallelism).
4. Optionally: pull the `plans/20260421_bound-pair-vs-TM-MC-equivalence-session.md` file onto the target branch if it's not already there. The plan doc is on `_TM-vs-MC_matsya_explore-further-speedups`, not `maintain_bound_pair_fix_splurge`. `git show _TM-vs-MC_matsya_explore-further-speedups:plans/20260421_bound-pair-vs-TM-MC-equivalence-session.md > /tmp/equiv-plan.md` works as a standalone local read.
5. Time budget: default 4–8 hours (§8 has 1–2h and 2–3h alternatives).

## 7. After the session delivers

The session should have produced `<edmund_notebook_stem>_response-further.md`. When it lands:

1. Read the executive summary; is it a clean verdict?
2. If the verdict is "equivalent", cross-check at least one number from §3 against what you already know.
3. If the verdict is "different", this becomes input for the broader coauthor conversation (see `what-to-do.md`).
4. Decide whether to merge the new doc into the `_TM-vs-MC` branch or keep it on Edmund's branch pending his response.

## 8. Alternative lighter-weight versions

If 4–8 h seems excessive:

- **Lightning version (1–2 h):** skip Phase 3 end-to-end experiments; do Phase 2 derivation only and check *formally* whether the bound-pair specification reduces to MC's transition rule. Output is a short memo, not a full `_response-further.md`. Risk: without numbers, debate can persist indefinitely.
- **Surgical version (2–3 h):** focus Phase 3 only on K/Y (the decisive target per `bound-pair-assessment.md`). Don't look at welfare or multipliers. Output: a focused 2–3 page memo on K/Y equivalence.

Full version is recommended for the "comprehensive writeup" the user requested.
