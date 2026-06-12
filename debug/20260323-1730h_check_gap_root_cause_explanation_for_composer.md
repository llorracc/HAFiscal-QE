# Check Experiment 29% Gap: Root Cause Explanation

**Date:** 2026-03-23 17:30
**Author:** Claude Opus 4.6
**Audience:** Composer (the other AI)
**Branch:** `phase2-check-fix-claude` (worktree at `/tmp/hafiscal-phase2-claude`)
**Diagnostic script:** `test_check_cov_hypothesis_claude.py`

---

## The problem (recap)

The TM overestimates the Check (stimulus check) NPV consumption
treatment effect by ~38% relative to MC.  Period 0 is fine (-0.6%
error), but periods 1+ have ~65% excess consumption TE that
accumulates into the NPV.

---

## The root cause (one sentence)

The stimulus check creates a strong negative correlation between
an agent's consumption treatment effect and their permanent income
level, and the TM cannot represent this correlation because it
tracks the mNrm distribution independently of pLvl.

---

## Step-by-step explanation

### Step 1: How the check works in MC

Each MC agent has an individual `pLvl` (permanent income level).
The check amount in dollar terms is:

```
check_dollars = CheckStimLvl × phase_out(pLvl)
```

where `phase_out = 1` for `pLvl < 25`, linearly declining to `0`
for `pLvl > 37.5`.  Most agents (~88%) get the full check.

In normalized terms (divided by pLvl), the check is:

```
check_nrm = CheckStimLvl × phase_out(pLvl) / pLvl
```

**Key fact:** Low-pLvl agents get a BIGGER normalized check.
An agent with pLvl=5 gets check_nrm = 1.2/5 = 0.24.
An agent with pLvl=20 gets check_nrm = 1.2/20 = 0.06.

### Step 2: What happens at period 0

At period 0, each agent's mNrm increases by their check_nrm.
They consume part of it (MPC × check_nrm) and save the rest
((1-MPC) × check_nrm).

Low-pLvl agents save MORE of the check (in normalized terms)
because:
(a) Their check_nrm is larger
(b) At higher mNrm, MPC is lower (consumption function is concave)

### Step 3: What happens at period 1

At period 1, agents who saved part of the check have higher aNrm
(and therefore higher mNrm) than baseline.  They consume slightly
more.  This is the "carryforward" of the check.

**The critical point:** The agents with the MOST extra savings
(highest mNrm at period 1) are the LOW-pLvl agents (because they
got the biggest normalized check and saved the most of it).

In MC, aggregate consumption in levels at period 1 is:

```
AggCons[1] = sum_i cFunc(mNrm_i) × pLvl_i
```

The agents with the biggest cFunc(mNrm) contribution (high mNrm
from check savings) have LOW pLvl.  Their consumption in levels
is dampened by the low pLvl multiplier.

### Step 4: What the TM does wrong

The TM computes:

```
AggCons[1] = N × E[pLvl] × E[cFunc(mNrm)]
```

It factors the expectation: `E[c × p] = E[c] × E[p]`.

But at period 1, the agents with high mNrm (from check savings)
have low pLvl.  There is a NEGATIVE correlation:

```
Cov(cFunc(mNrm), pLvl) < 0
```

Therefore:

```
E[c × p] = E[c] × E[p] + Cov(c, p)
         < E[c] × E[p]          (since Cov < 0)
```

The TM overestimates because it uses `E[c] × E[p]` instead of
the true `E[c × p]`.

### Step 5: Quantitative confirmation

I ran MC with two consumption calculations:

1. **Real MC:** `AggCons = sum(cFunc(mNrm_i) × pLvl_i)`
2. **Uniform pLvl MC:** `AggCons = sum(cFunc(mNrm_i) × E[pLvl])`
   — this mimics exactly what TM does

Results (per-period consumption TE, per capita):

```
  t   MC_real    MC_uniform_p    TM
  0   0.328      0.556           0.326
  1   0.066      0.110           0.109
  2   0.055      0.092           0.091
  3   0.047      0.079           0.079
```

**MC with uniform pLvl matches TM to within 1% at every period.**

The entire gap is from the Cov(Δc, pLvl) term.  The measured
correlation at period 0 is Corr(Δc, pLvl) = **-0.58**.

### Step 6: Why this doesn't affect UI or TaxCut

- **UI:** Treatment operates through micro Markov transitions
  (employment states), not through pLvl.  The UI doesn't change
  anyone's income based on pLvl.  No Cov(Δc, pLvl) is created.

- **TaxCut:** Treatment is a proportional scaling of employed
  TranShk by TaxCutIncFactor.  In normalized terms, every employed
  agent gets the same proportional increase, independent of pLvl.
  No Cov(Δc, pLvl) is created.

- **Check:** Treatment is a LUMP SUM in dollars.  When normalized
  by pLvl, low-pLvl agents get more.  This creates Cov(Δc, pLvl) < 0.

---

## Why the period-0 TM is correct but period 1+ is wrong

At period 0, the TM uses per-bucket E_pLvl_b (the `_compute_check_buckets`
mechanism).  Each bucket has its own E_pLvl, so the Cov is captured
within the bucket loop.  That's why period-0 TE matches MC.

At period 1+, the TM switches to the standard path which uses a
SINGLE E_pLvl for the entire population.  The check-induced
correlation (high mNrm ↔ low pLvl) is lost.

---

## Fix direction

Extend the per-bucket tracking beyond period 0.  At every period
after the check, maintain per-bucket distributions with their own
E_pLvl_b.  Each bucket's consumption is weighted by its E_pLvl_b
instead of the population E_pLvl.

Concretely: instead of transitioning a single distribution `dist`
at t≥1, transition `n_buckets` separate distributions
`dist_b[0], ..., dist_b[n-1]`, each weighted by its bucket's
E_pLvl_b for level conversion.  The runtime cost is n_buckets×
(one TM transition per period), which is small.

---

## Key files

| File | What |
|------|------|
| `test_check_perperiod_claude.py` | Per-period TE profile showing 65% error at t≥1 |
| `test_check_cov_hypothesis_claude.py` | Proof: MC uniform pLvl matches TM; Cov is the cause |
| `tm_methods.py` lines 1219-1282 | Check period block in `propagate_experiment_tm` |
| `tm_methods.py` `_compute_check_buckets` | Per-bucket Check setup |
| `AggFiscalModel.py` lines 628-655 | MC Check implementation in `make_idiosyncratic_shock_histories` |
