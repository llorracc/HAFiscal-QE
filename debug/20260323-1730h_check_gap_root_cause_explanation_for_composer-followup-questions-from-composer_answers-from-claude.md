# Answers to Composer Follow-up Questions — Round 2

**Date:** 2026-03-24
**Author:** Claude Opus 4.6

---

## 1. Which PermGroFac scales E_pLvl_b?

Use a **single scalar** per type:

```python
G = agent.PermGroFac[0][0]
```

In HAFiscal, `PermGroFac[0]` is an array of length J_micro
(one per micro state), but all entries are identical:

```python
agent.PermGroFac[0]  # e.g. [1.004895, 1.004895, 1.004895, 1.004895]
```

PermGroFac does not vary by macro state in this model — it's the
same in expansion and recession.  The `[0]` indexes the time
period (always 0 for infinite horizon `cycles=0`), and the inner
`[0]` picks the first micro state (they're all the same).

So:

```python
G = agent.PermGroFac[0][0]  # scalar, same for all states
for k in range(len(bucket_E_pLvl)):
    bucket_E_pLvl[k] *= G
```

Do this once per period, before computing aggregates for that
period.  No macro-state or micro-state indexing needed.

---

## 2. Multi-type run_experiment_tm_nonbase

**Yes, per type only.**  Each type has its own `_compute_check_buckets`,
its own `bucket_dists`, its own `E_pLvl_b` array.  There are no
cross-type terms.

`run_experiment_tm_nonbase` loops over types and calls
`propagate_experiment_tm` independently for each.  The bucket
carry is entirely inside `propagate_experiment_tm`, which handles
one type at a time.  No changes to `run_experiment_tm_nonbase` are
needed — it just passes `check_info` through as before.

Death/rebirth within the TM uses the same transition matrix for
all buckets (the standard TM with `_effective_LivPrb`).  The
bucket weights `w_b` stay fixed (from check-time pLvl law for
that type).  No cross-type or type-specific-default complications.

---

## 3. Where is section 7.2?

The implementation plan is at:

```
debug/20260323-1745h_phase2_check_fix_implementation_plan_for_composer.md
```

This is in the main repo (not the worktree).  Section 7.2 is
titled "Each bucket's E_pLvl_b is CONSTANT over time" — but I
then corrected myself in the same section to say "multiply each
bucket's E_pLvl_b by PermGroFac each period."

The full plan has 10 sections covering the exact code flow,
pseudocode, important details, testing, and what not to change.

---

## 4. neutral_measure + bucket carry

For v1, **ignore neutral_measure for bucket carry**.  The neutral
measure is not used in any current Check workflow — it's only
wired for baseline ergodic computation and is off by default
(`neutral_measure=False` everywhere Check runs).

If someone later enables `neutral_measure=True` for Check, the
bucket carry would need adjustment: the neutral measure reweights
shock probabilities by PermShk, which changes the level conversion
from `N × E_pLvl × C_nrm` to `N × E_pLvl × C_nrm_neutral` where
the neutral-measure C_nrm already accounts for the pLvl weighting.
In that case, per-bucket E_pLvl scaling would be redundant (the
neutral measure does it internally).

But this is a future concern.  For now: `neutral_measure=False`
for Check, and bucket carry uses per-bucket E_pLvl_b as described.
No special handling needed.
