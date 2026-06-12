# Instructions for Composer: Next Steps

**Date:** 2026-03-25 10:00
**Author:** Claude Opus 4.6
**Audience:** Composer

---

## Summary of where we are

Your Phase 2 work is solid. The NPV fix (E_pLvl_b rescale) works
(~1% error). The period-0 gap (~5%) is explained: it's MC burn-in
under-convergence, not a TM bug. At burn=400 the gap is 0.17%.

There are three things to do now, in priority order.

---

## Task 1: Fix MC burn-in in validate scripts (high priority)

The validate scripts (`validate_tm_check.py`, `validate_tm_ui.py`,
`validate_tm_taxcut.py`) use `act_T` from Parameters as the burn-in
length. For Reduced_Run, `act_T=100`, which is too short — your own
experiments showed TE0 drops from 5% to 0.17% when burn-in goes
from 100 to 400.

**What to do:**

In each validate script, after creating the economy but before
`make_history()`, override `act_T` for the burn-in phase:

```python
# In run_mc_experiment or equivalent MC setup:
eco.act_T = 400  # burn-in: 400 periods for MC ergodic convergence
# ... make_history, save_state ...
eco.act_T = act_T_experiment  # restore for experiment phase
```

Where `act_T_experiment` is the original value from Parameters
(100 for Reduced_Run, 400 for Baseline).

Alternatively, add a `--burn-periods` CLI argument defaulting to
400.

**How to test:** Run `validate_tm_check.py --agents 200000 --seeds 3
--mcount 100` and verify TE0 rel error drops from ~5% to <1%.

**Files to change:** `validate_tm_check.py`, `validate_tm_ui.py`,
`validate_tm_taxcut.py` — the MC setup section in each.

---

## Task 2: Document the Cratio no-op (low priority)

Your finding that `cFunc` ignores the Cratio argument is correct
and well-diagnosed. But it doesn't affect any current result because
non-AD experiments have Cratio=1 everywhere.

**What to do:**

Add a comment in `build_experiment_period_tm` at the line where
Cratio is passed to cFunc:

```python
# NOTE: For AggFiscalType, solution.cFunc[j] is a CRule that
# ignores the second argument (Cratio).  TM operates at Cratio=1
# for all non-AD experiments.  When TM-based AD is implemented
# (Phase 4), the cFunc interface must be updated to accept Cratio.
```

Do NOT try to fix the wiring now. It's a Phase 4 concern.

**Do NOT** remove the Cratio parameter from the function signature —
it's the correct interface for when AD is eventually implemented.

---

## Task 3: Document MC pLvl histogram as diagnostic-only

Add a note to the `--check-mc-pLvl` help text:

```python
parser.add_argument('--check-mc-pLvl', action='store_true',
    help='Use MC pLvl histogram for check buckets (diagnostic only; '
         'analytical buckets are more accurate for TM vs MC validation)')
```

---

## What NOT to do

- Do NOT try to fix the Cratio wiring. It's Phase 4.
- Do NOT add PermGroFac growth to E_pLvl_b. Your finding that it
  blew up to 200% was correct — the baseline uses constant E_pLvl,
  so the Check buckets must too.
- Do NOT switch to MC pLvl histogram buckets. Analytical is better.
- Do NOT investigate the TaxCut consumption TE (BUG-010). That's
  a separate, pre-existing issue unrelated to Phase 2.
- Do NOT change `Simulate.py` or `tm_methods.py` for these tasks.
  Only the validate scripts and comments need updating.

---

## After these tasks

Merge your `phase2-check-fix-composer` changes back to the main
branch. The Phase 2 Check fix is complete:

- Period-0 AggCons TE: ~1% error ✓
- NPV consumption TE: ~1% error (with E_pLvl_b rescale) ✓
- Period-0 gap explained as MC burn-in ✓
- All existing validate scripts pass ✓

Phase 2 can be declared closed once the validate scripts use
burn=400 and the TE0 gate (<5%) is met.
