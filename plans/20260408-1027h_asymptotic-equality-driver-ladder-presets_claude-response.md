# Response to Plan 1: Ladder presets / single-grid defaults

**Reviewer:** Claude (Opus 4.6)
**Reviewing:** `plans/20260408-1026h_asymptotic-equality-driver-ladder-presets.md`
**Date:** 2026-04-08

---

## Headline concern: collapsing to a single TM grid breaks the convergence demonstration

This is the most important issue and I want to flag it prominently.

The driver `test_asymptotic_equality_revised.py` is **a convergence
test**. The point of running TM at *multiple* `mCount` values
(`TM-default=50`, `TM-medium=75`, `TM-fine=100`) is **not** to make the
default invocation expensive — it is to *demonstrate* that the TM has
converged, by showing the user a column like:

```
    Method    Mult  vs TM-ref  Time
TM-default  0.9741      0.05%  30.6s
 TM-medium  0.9744      0.01%  31.0s
   TM-fine  0.9745      0.00%  32.4s
```

That table is the convergence proof. The user reads down the err
column and sees `0.05% → 0.01% → 0.00%` and concludes "TM is grid-
converged at this scale". With a single TM grid, the corresponding row
becomes:

```
    Method    Mult  vs TM-ref  Time
   TM-fine  0.9745      0.00%  32.4s   ← tautology
```

The error column is mechanically zero because TM-fine *is* the
reference. **The convergence claim disappears.** A new user running
the driver under the new default would see a number with no internal
evidence that it's correct.

**Recommendation.** Keep the default as a multi-grid TM sweep. If the
goal of Plan 1 is to make smoke runs cheap, change the default
**parametrization** (Smoke_Test) and the default **MC config**
(MC-tiny), but **do not** strip the TM ladder from the default. The
TM ladder is what distinguishes this driver from a generic
"run-and-print" script.

A milder version of Plan 1 that I would endorse: keep the default
TM list but make the cheapest level the default. For phases that
currently default to `["TM-default", "TM-fine", "TM-xfine"]`, change
to `["TM-coarse", "TM-default"]` for a fast smoke ladder, or to
`["TM-coarse", "TM-default", "TM-fine"]` for a medium ladder. The
key invariant is **at least two grid points**, so the err column
carries information.

The same argument applies, with less force, to MC. If the user
passes only one MC config, you have no SE estimate from seed
variation (already enforced for `MC-small` upward via the 2-seed
minimum). The single-MC default would silently regress that.

---

## Other issues

### 1. Ladder names collide visually with MC names

`MC_CONFIGS` already has `MC-tiny`, `MC-small`, `MC-med`,
`MC-large`, `MC-xlarge`. The proposed `--ladder {tiny,small,
medium,large}` will be confused with these by every reader. After
this lands, two different people will say "tiny" and mean two
different things ("the MC config" vs "the joint MC+TM preset").

**Fix:** name the ladder differently — e.g. `--preset
{quick,parity,careful,deep}` or `--scale {S0,S1,S2,S3}`. Avoid the
`tiny/small/med/large` quartet entirely.

### 2. Ladder table is missing a level

`MC_CONFIGS` has 5 sizes (tiny → xlarge); the proposed ladder
table has 4 (tiny → large). `MC-xlarge` becomes unreachable via
`--ladder`. Either add a fifth row or document the omission as
intentional.

### 3. MC and TM scaling are orthogonal — don't bind them prematurely

A common diagnostic invocation is `MC-large` (precise MC) with
`TM-coarse` (cheap, to check that the TM grid is *not* the
bottleneck). Or `MC-tiny` with `TM-xfine` (cheap MC noise check
against an essentially exact TM). The proposed ladder collapses
this 2D space into a 1D curve.

The plan does say "explicit `--mc`/`--tm` win, per chosen
precedence rules", which preserves the escape hatch. Good. But the
**default** invocation is the one most users will use, so the 1D
projection becomes the de-facto recommended workflow. Worth a
sentence in the docstring acknowledging that the 2D space exists
and `--ladder` is just one cut through it.

### 4. argparse "absent vs. empty list" footgun is unmentioned

The plan's logic ("if `--ladder` is set and `--mc`/`--tm` are
absent") relies on distinguishing "user didn't pass it" from "user
passed it as an empty list". With `nargs="+"`, `default=None` is
the safe pattern; with `nargs="*"`, `default=None` and `default=[]`
behave differently. This is a footgun the plan should explicitly
call out as a Task, otherwise the next implementer will write
`default=[]` and silently break the precedence rule.

### 5. Task 4 (Parametrization → default --ladder mapping) should be cut

The plan hedges this ("only if predictable; otherwise skip"). The
honest answer is "skip". An invocation like
`--parametrization Smoke_Test` with no `--ladder` should error or
use a documented hard-coded default — *not* infer a ladder level.
Implicit inference creates the worst kind of bug: the user runs
the same command twice with different `Parametrization` and gets
results that disagree at scales they didn't realize were
different.

### 6. The "sweep" semantics break the meaning of `--mc` / `--tm`

Currently `--mc MC-tiny MC-small` runs both as a *sweep*. After
Plan 1, the same flag runs as a *sweep* only when length > 1, and
as an *override* when length == 1. That's inconsistent — the same
argument has different semantics depending on its length.

**Fix:** introduce explicit `--mc-sweep` for the multi-tier
behavior, and have `--mc` always be a single override. Or vice
versa. Either way, don't overload one flag with two semantics.

### 7. CI / downstream consumers

The "Rollout / risk" section mentions grepping for the driver in
CI. It does not mention the **plans documents** themselves
(`plans/20260405-2228h_full-reproduction-plan.md`, `plans/asymptotic-equality-
test-plan_revised.md`, the ladder-medium scripts under `history/`)
that bake in invocation strings. Several of those reference
`--mc MC-med --tm TM-default TM-medium TM-fine` etc. After Plan 1
lands, those invocations will silently change behavior unless they
are also updated.

---

## Summary

Plan 1's biggest problem is that it would turn the convergence test
into a non-convergence test by stripping the TM grid sweep from the
default. That alone is a blocker. The other issues are smaller and
fixable in a revision. Recommended changes before implementation:

1. **Keep multi-grid TM default**, just at cheaper levels.
2. **Rename `--ladder`** to avoid the `tiny/small/med/large`
   collision with `MC_CONFIGS`.
3. **Add `MC-xlarge`** to the table (or document the omission).
4. **Drop Task 4** (Parametrization-implies-ladder magic).
5. **Disambiguate the `--mc` / `--mc-sweep` semantics** instead of
   length-based overloading.
6. **Document the `--mc-sweep` / `default=None`** argparse pattern
   as an explicit Task, not an aside.
7. **Update plan documents and ladder scripts** under `history/`
   alongside the code change.
