# Phase 2 Check Diagnosis: Per-Period TE Profile

**Date:** 2026-03-23
**Author:** Claude Opus 4.6
**Branch:** `phase2-check-fix-claude` (worktree at `/tmp/hafiscal-phase2-claude`)
**Script:** `test_check_perperiod_claude.py`

---

## Key Finding

The Check consumption TE has a **period-0 error of only -0.6%** but
a **period 1+ error of ~65%** consistently.  The TM's consumption TE
decays much more slowly than MC's, accumulating to **~38% NPV error**
over 20 periods.

```
  t     TM_TE       MC_TE     rel_err
  0   0.326056    0.328118      -0.6%
  1   0.108834    0.066084     +64.7%
  2   0.091357    0.054917     +66.4%
  ...
 19   0.016881    0.010567     +59.8%
```

## What this means

The period-0 consumption response to the check is correct.  The
problem is the **carryforward**: the TM transitions too much extra
wealth from period 0 to period 1.

## Mechanism analysis

In `propagate_experiment_tm`, the check period builds a per-bucket
TM with `mNrm_shift` via `build_experiment_period_tm`:

```python
TM_b, cPol_b = build_experiment_period_tm(
    agent, macro_t, macro_next, dist_mGrid, Cratio,
    mNrm_shift=bucket['mNrm_shift'], ...)
```

Inside `build_experiment_period_tm`, `mNrm_shift` shifts the
evaluation grid: `m_eff = dist_mGrid + shift`.  This affects BOTH:
1. **Consumption**: `cPol_b = cFunc(m_eff)` — correct, agents
   consume at the higher mNrm
2. **Savings/transition**: `aPol_b = m_eff - cFunc(m_eff)` — the
   savings policy also uses the shifted grid

The `TM_b` then maps `dist @ aPol_b → income → next_dist`.  The
shifted `aPol_b` produces higher savings than the unshifted version:
`aPol_shifted(m) = (m + shift) - cFunc(m + shift)` vs
`aPol_base(m) = m - cFunc(m)`.

The extra savings = `shift * (1 - MPC)`, where MPC is the marginal
propensity to consume at the shifted mNrm.

## The puzzle

This carryforward is CORRECT in principle: agents who receive a
check do save part of it, and the extra savings produce higher
consumption in subsequent periods.  MC does the same thing.

But the TM's carryforward is **65% too large**.  Why?

## Hypotheses (not yet tested)

**H1: The mNrm_shift applies to the wrong quantity.**
The shift should add to TranShk (income), not to the mNrm grid.
In MC: `mNrm = bNrm + TranShk + check_nrm`.  The bNrm part depends
on prior savings and PermShk; the check adds to TranShk.  In TM:
`m_eff = dist_mGrid + shift` shifts the entire grid, which includes
bNrm.  This means the TM treats the check as increasing both the
income AND the bank balance, not just the income.

But wait — the TM distribution `dist` is over mNrm = bNrm + TranShk.
Shifting the grid by check_nrm is equivalent to adding check_nrm to
TranShk.  The savings from the TM should be:
`aPol(m + shift) = (m + shift) - cFunc(m + shift)`

This is the savings at the NEW mNrm including the check.  The savings
in the NEXT period's mNrm would be:
`mNrm_next = aPol(m + shift) * R / (PermShk * G) + TranShk_next`

vs MC:
`mNrm_next = (mNrm_0 - cFunc(mNrm_0)) * R / (PermShk * G) + TranShk_next`

where `mNrm_0 = bNrm + base_TranShk + check_nrm`.

These should be equivalent: `aPol(m + shift) = (m + shift) - cFunc(m + shift)`
and MC's aNrm = mNrm_0 - cFunc(mNrm_0) where mNrm_0 = m + shift.

So the savings should match... unless the distribution over m
is different.

**H2: The per-bucket weighted TM averaging introduces error.**
The check produces `dist_next = sum_b w_b * (TM_b @ dist)`.
Each bucket has a different shift, so a different `TM_b`.  The
weighted average might not equal what you'd get from a single
shift at the population level.  This is the discretization of
the pLvl distribution into buckets.

**H3: The shifted TM's aPol evaluation is at the wrong grid points.**
`build_experiment_period_tm` evaluates `aPol` at `m_eff = grid + shift`.
But the distribution `dist` lives on `grid` (unshifted).  So the
TM applies `aPol(m + shift)` to mass at `m` — the savings at
`m + shift` for agents at `m`.  In MC, agents at mNrm = m + shift
save aPol(m + shift).  These are consistent.

**H4 (most likely): The baseline uses a different scaling.**
The check period uses per-bucket E_pLvl_b for level conversion,
while the baseline uses the single E_pLvl.  At later periods
(t >= 1), both Check and baseline use the standard (non-check)
path.  But the distribution at t=1 from the Check experiment
differs from baseline's.  If the E_pLvl used to convert
the t>=1 consumption back to levels is wrong, the TE could
be systematically biased.

Actually — the standard path at t>=1 uses:
```
C_series[t] = N * E_pLvl * C_splurge_nrm
```
This uses the SAME E_pLvl for both Check and baseline at t>=1.
The TE at t>=1 is: `N * E_pLvl * (C_nrm_check[t] - C_nrm_base[t])`.
This is correct as long as the distributions are correct.

## Next steps

1. Compare the period-1 distributions directly: TM dist after
   check vs MC histogram at period 1.  This will show whether
   the TM has too much mass at high mNrm.
2. Test with a single bucket (n_buckets=1) to eliminate H2.
3. Compare the unshifted TM transition at the check period with
   a shifted TM to quantify how much of the carryforward is
   from the shift vs other factors.
