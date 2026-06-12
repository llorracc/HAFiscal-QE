# Response to Plan 2: Baseline-work refactor

**Reviewer:** Claude (Opus 4.6)
**Reviewing:** `plans/20260408-1026h_asymptotic-equality-driver-baseline-cache-refactor.md`
**Date:** 2026-04-08

---

## Headline concern: the regression check is too weak to catch RNG-ordering shifts

The plan's acceptance criterion is:

> No change in **default numerical results** beyond floating-point
> noise for the same CLI and seed.

and the regression check (Task 5) compares "key scalars (e.g. TM ref
multiplier, MC-tiny multiplier)". This is **not strong enough** to
catch the most likely failure mode of the proposed refactor.

**The failure mode.** If `run_mc_baseline_then_policy` reorganizes
the order of `setup_economy → solve → save_state → run_experiment →
switch_shock_type → solve → run_experiment`, it can change which RNG
draw is consumed at which step, even when the *number* of draws is
preserved. The result is that AggCons series shift by an amount that
is below MC noise at N=100/1 seed (MC-tiny) but is **not** numerical
noise — it is a real RNG-ordering bug. Comparing only NPV multipliers
under MC-tiny will not see it because the per-seed standard error at
N=100 is way larger than the shift.

Worse, comparing the **TM ref multiplier** before and after the
refactor is meaningless — TM doesn't use any of the MC RNG state, so
that comparison tests nothing about the refactor.

**Stronger regression check.**

1. Run with a *fixed* seed and capture the **full** AggCons time
   series (not just the NPV scalar) before and after the refactor.
   Assert bit-identity (or differ only in the last 1–2 ULPs).
2. Do this at **N ≥ 4000** (`MC-large`), not at MC-tiny — the shift
   has to stand out above noise.
3. Capture per-type, not just population aggregates: per-type
   `AggCons` and `AggIncome` for each of the 3 education types for
   the first ~10 periods. RNG ordering bugs often manifest first as
   per-type drift.
4. Repeat with a recession phase (act_T is restored differently
   after `switch_to_counterfactual_mode`) — this is the most fragile
   surface for ordering bugs.

The plan should make these explicit in Task 5 rather than leave the
"key scalars" phrasing.

---

## Other issues

### 1. The plan acknowledges the `save_state` / `restore_state` pattern but doesn't require it

The Risks section says:

> Refactors that share mutable economy state between baseline and
> policy can introduce subtle bugs; prefer **immutable snapshots** or
> explicit `save_state`/`restore_state` patterns already used elsewhere
> in HAFiscal.

This is right, but it's framed as a preference. It should be a hard
requirement of the helper signature: `run_mc_baseline_then_policy`
**must** call `save_state()` before the baseline run and
`restore_state()` (or a deepcopy) before `switch_shock_type`. Without
this, the function silently mutates the caller's `economy` object.

The current code does this in some places and not others; the
refactor should regularize it, not leave it implicit.

### 2. Profiling under the wrong default could hide hot paths

Plan 2 says:

> Plan 1 may land first so default runs are cheap and profiling uses
> representative invocations (`--ladder tiny`, etc.).

This is exactly backwards. If Plan 1 lands first and strips the
multi-grid TM sweep from the default, then profiling under the new
default won't exercise the multi-grid loop, and any duplication
*inside* that loop will go unnoticed. Profile against the **current**
multi-grid default, find duplication, fix it, then let Plan 1
re-default.

(This compounds with my main concern about Plan 1 — collapsing the
TM sweep to a single grid hides exactly the kind of duplicated
TM-side work Task 4 of Plan 2 wants to look for.)

### 3. Plan 2 doesn't account for the new TM-P baseline computation

I just re-added a TM-P baseline computation to Phase 1
(`_run_baseline_phase`) as the same-measure replacement for the
deleted UNPROVEN per-type comparison. That's an *extra*
`compute_baseline_tm_data(neutral_measure=False)` call per phase
invocation, alongside the existing `neutral_measure=True` call.

If Plan 2's profiling pre-dates that change, it will not see this
extra TM call and will miss the most obviously cacheable item: the
TM-P and TM-Q ergodic computations share most of their work
(transition matrix construction, ergodic solve), differing only in
the shock reweighting. Plan 2 should explicitly call out this pair
as a profile target.

### 4. The helper extraction risks losing the `[math-deriv]` citations

The driver now prints inline `[math-deriv]` references at every
comparison site (per the rule the user requested). If
`run_mc_baseline_then_policy` is extracted, the citation prints have
to either move into the helper or be re-added at every caller.
Plan 2 doesn't mention this.

### 5. "Apply the same structural clarity to the TM side only if duplication exists"

This is hedged correctly, but the only TM duplication I'm aware of
in the current driver is the very thing I just added (TM-P + TM-Q
both for Phase 1 baseline) — which is *intentional* duplication
because the two measures answer different questions. A casual
refactor might collapse them and break the per-type proven
comparison. Add a "do not merge" comment at the relevant call site,
or document this exception in Plan 2's Non-goals.

### 6. Changes to `--mc-tiny` MC-tiny path interact with the seed-1 minimum

`MC_CONFIGS["MC-tiny"] = {"seeds": [0]}` (single seed, smoke check).
Several Task 5 verification ideas implicitly assume multiple seeds
("compare on a fixed seed"). With one seed there's no per-seed
variation to test against. The regression check needs to use
`MC-small` (2 seeds) or above, or temporarily override
`MC-tiny["seeds"]` to `[0, 1]` for the test only.

### 7. Per-seed `setup_economy` is intentional, not waste

The current code calls `setup_economy(...)` once per seed. The plan
hints at "duplicate setup_economy calls where one would suffice".
**Be careful here:** the per-seed `setup_economy` re-seeds the agent
RNG so that each seed produces an *independent* MC sample. Caching
the economy across seeds and only re-seeding the RNG is possible but
fragile — HARK agents store RNG state in multiple places (per-agent
draws, per-type shock histories, init draws). A naive
"setup_economy once, re-seed N times" refactor will quietly produce
correlated seeds that look like independent ones, inflating apparent
seed-to-seed agreement.

This is exactly the trap the Risks section warns about, but the
"Potential waste" enumeration (item 1, "duplicate setup_economy
calls where one would suffice") invites the bug. The plan should
explicitly say "do not cache `setup_economy` across seeds" as a
non-goal.

---

## Summary

Plan 2's methodology (profile first, refactor only where profiling
shows duplication) is sound. The concerns above are mostly about
what to enforce in code review and the regression test, not about
the goal:

1. **Strengthen the regression check**: full AggCons series at
   `MC-large`, per-type, including a recession phase. NPV-multiplier-
   only is not enough.
2. **Reverse the dependency on Plan 1**: profile against the *current*
   multi-grid default, not after Plan 1 strips it.
3. **Make `save_state` / `restore_state` a hard requirement** of the
   helper, not a preference.
4. **Add `setup_economy`-across-seeds caching** to the Non-goals
   list to forestall the most likely RNG-correlation bug.
5. **Note the new TM-P + TM-Q baseline pair** as an intentional
   duplicate that should be left alone (or carefully cached *together*,
   not collapsed).
6. **Don't lose the `[math-deriv]` print sites** when extracting helpers.
