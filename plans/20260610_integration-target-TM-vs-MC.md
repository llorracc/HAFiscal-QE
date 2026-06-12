# Integration target is `_TM-vs-MC` — NO upward merge

**Status:** ACTIVE

**Date:** 2026-06-10. **This file supersedes/retracts** its earlier content (which planned merging
`_TM-vs-MC` → `0.14.1-to-0.17.0-upgrade-validation`). That plan was wrong; this records the correction.

## Correction (retraction of the upgrade-validation merge)
The earlier version proposed promoting `_TM-vs-MC` into its parent
`0.14.1-to-0.17.0-upgrade-validation`. **Retracted — it was a misunderstanding:**
- The session *label* is `bug053-gpf-reestimation_followup`, so it was assumed we were on a `bug053-*`
  child branch that needed merging into a `_TM-vs-MC` "parent." We are not.
- We are **on `_TM-vs-MC`**, and `_TM-vs-MC` **is** the canonical working/integration branch. This
  session's three commits (`3a76ab2b`, `c2848ba8`, `0720403f`) are already on it and pushed.
- The short `0.14.1-to-0.17.0-upgrade-validation` is merely `_TM-vs-MC`'s **frozen 2026-03-21 ancestor**
  (0 commits since the spin-off). It is **not** a target.

## The target — for ALL current plans
> **`0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`.**

Everything — this session's commits, the canonicalization (Plan A), and the follow-ups (B–I) — **lands
on and targets `_TM-vs-MC`.** There is **NO upward merge** to plan: **ABSOLUTELY NOT to
`upgrade-validation`** (user, emphatic 2026-06-10), and not to `master` either. `_TM-vs-MC` is where the
work lives and stays.

## Consequences
- The former "pre-merge readiness gate" is **not** a precondition for promoting `_TM-vs-MC` anywhere
  (there is no promotion). Its items are still worth doing — but as **ongoing health/coherence of
  `_TM-vs-MC` itself**: reconcile the calibration (Plan E), land/record the pending Baseline multiplier,
  canonicalize the defaults (Plan A), keep the reproduction smoke green.
- Leave the frozen `upgrade-validation` branch alone.
- Any *eventual* trunk integration (e.g., publishing from `master`) is a **separate, future decision,
  explicitly out of scope here** — and even then, not `upgrade-validation`.

## Forward work
`plans/20260610_post_merge_canonicalize_default_solution.md` — Plan A (canonicalize the default solution
approach **on `_TM-vs-MC`**) + follow-ups B–I, sequenced from Plan E (calibration reconcile).
