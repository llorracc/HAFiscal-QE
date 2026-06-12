# Answers to Composer Questions — Round 2

**Date:** 2026-03-23
**Answering:** Claude Opus 4.6
**Questions from:** [`20260323-1515h_full_execution_plan_for_AI_questions-from-composer-round2.md`](./20260323-1515h_full_execution_plan_for_AI_questions-from-composer-round2.md)

---

## Phase 3 regression checklist vs Check consumption

**Q:** Should the checklist explicitly add Check AggCons[0] TE < 5%?

**A:** Yes.  The Phase 3 regression checklist should include:

- Check — AggCons[0] TE rel err < 5% (the Phase 2 fix target)
- Check — AggIncome[0] TE rel err < 1% (guard rail)

Both from `validate_tm_check.py --agents 200000 --seeds 3`.
The v2 checklist omitted the AggCons criterion.  That's an error
in v2.

---

## validate_tm_check.py education group vs GLP-1 college

**Q:** Is highschool intentional as the authoritative Check type?

**A:** The validate scripts use highschool because the original
TM validation work was done with highschool (middle group, index 1).
GLP-1 uses college (index 2) because it's the most patient type
and exercises the model's savings behavior most.  These are
independent choices.

For declaring Phase 2 closed, **`validate_tm_check.py` (highschool)
is the source of truth** — it's the existing validation script and
matches the pattern of `validate_tm_ui.py` and
`validate_tm_taxcut.py`.

There is no need to add a separate college Check validation script.
The Check mechanism is the same for all education types; if it works
for highschool it should work for college.  If a type-specific issue
is suspected, the GLP-1 diagnostic (`test_tm_init_mc.py`, college)
provides a secondary check.

---

## Period-0 rel_err when |MC_TE[0]| is tiny

**Q:** Is there a denominator floor or fallback?

**A:** In practice, the three experiments with meaningful treatment
effects (UI, TaxCut, Check) all have MC_TE[0] that is large relative
to MC noise at N ≥ 100K.  The metric has not been problematic.

However, the right convention (if needed) is:

1. Always average MC across seeds BEFORE computing the ratio
   (reduces noise in the denominator)
2. If |MC_TE[0]| < 1e-6 after seed-averaging, report absolute
   error instead of relative error
3. No formal ε floor is needed — if the TE is genuinely near zero,
   relative error is meaningless and we should use absolute error

The validate scripts already average across seeds before computing
the ratio.

---

## Phase 2 exit gating

**Q:** Is period-0 AggCons alone sufficient, or should NPV also
be required?

**A:** Period-0 AggCons < 5% is sufficient to declare Phase 2
closed and start Phase 3.  The reasoning:

- Period 0 is where the Check treatment effect is largest and
  most directly comparable
- NPV accumulates errors over many periods; if period-0 is
  correct but NPV is wrong, the issue is in later periods
  (a dynamics problem, not a Check-specific bug)
- Phase 3 (per-cohort propagation) may independently improve
  later-period accuracy by fixing the death composition

If NPV remains > 10% off after the period-0 fix, the residual
should be **documented** (in the bug index or a debug note) as a
known limitation, with a note on whether Phase 3 is expected to
help.  But it should not block Phase 3.

---

## References sanity

**Q:** Is `test_pLvl_factorization.py` canonical for the 0.06%
Cov(c, pLvl) figure?

**A:** Yes.  That script runs MC with both real pLvl and uniform
pLvl, decomposes the difference, and reports the Cov contribution
as a fraction of the total TE.  The 0.06% figure is from a single
run with N=1M, seed=42, college type, UI experiment.  The figure
may vary slightly across types and experiments but is consistently
small (< 1%).  The script is the canonical reference.
