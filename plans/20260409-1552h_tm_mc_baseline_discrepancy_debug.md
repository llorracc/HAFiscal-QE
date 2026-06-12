# Debugging the TM↔MC Baseline Multiplier Gap

## The puzzle

In the asymptotic-equality test driver work (Phases 1–7) we confirmed
that TM and MC agree to ≤1% on every shock type at Reduced_Run /
HS_Only / Smoke_Test scale, including the full AD pipeline. Yet at
**Baseline scale** the production multipliers disagree:

| Policy | TM Baseline AD | MC Baseline AD | Δ |
|---|---|---|---|
| Check | 1.088 | 1.230 | **−11.5%** |
| UI | 1.166 | 1.212 | −3.8% |
| Tax cut | 0.999 | 1.014 | −1.5% |

The Check gap is the standout. UI and TaxCut are within plausible
sampling/discretization noise, but Check is much larger than anything
we saw at smaller scale. This plan attacks the puzzle in **strict
cheapest-first order** so we don't waste hours on a slow rerun when
the answer is already in the pickles on disk.

## What changed between the asymptotic-equality tests and the Baseline run

| Dimension | Asymp. tests | Baseline production | Note |
|---|---|---|---|
| Parametrization | HS_Only / Reduced_Run | Baseline | 1–3 types vs 21 types |
| `max_recession_duration` | capped at 2 (`TEST_DRIVER_MAX_RECESSION_DURATION`) | 21 | 10× longer averaging window |
| `mCount` | 100 | 100 | same |
| AD multiplier formula | `NPV(ΔC_AD)/NPV(ΔY_noAD)` (after BUG-024 fix) | same (`Output_Results.py:210`) | should match |
| AD code path | `run_ad_tm` (TM) / `solve_ad_recession` (MC) | same | should match |
| Number of agent types | 1 (HS_Only) or 3 (Reduced_Run) | 21 (3 cohorts × 7 β) | 7–21× more types |
| MC `AgentCountTotal` | 100–2000 | ~10 000 | 5–100× more agents |

The two big-suspect differences are **recession-duration averaging
window (2 → 21)** and **type count (1–3 → 21)**. Bucket discretization
at Baseline scale is also suspect for Check specifically.

## Investigation order (cheapest first)

### Phase A — Zero-compute analysis from existing pickles (~5 min)

Both the TM and MC Baseline runs left their full per-duration result
pickles in `Code/HA-Models/FromPandemicCode/Figures/Baseline/`:

- `recession_all_results_AD.csv` (recession baseline, AD)
- `recessionCheck_all_results_AD.csv`
- `recessionUI_all_results_AD.csv`
- `recessionTaxCut_all_results_AD.csv`
- and the `_results.csv` (no-AD) variants

These are pickles of `list[dict]` with one entry per duration index
0..20. Each dict contains `AggCons`, `AggIncome`, `NPV_AggCons`, etc.

**Step A1:** Load the TM and MC pickles for `recessionCheck_all_results_AD`
and `recession_all_results_AD`. For each duration t = 0..20, compute
the per-duration policy multiplier:

```
M_t^Check = NPV(C^Check_t - C^rec_t) / NPV(Y^Check_t_noAD - Y^rec_t_noAD)
```

(using the no-AD denominator from the corresponding `_results.csv`
files). Compare TM vs MC duration-by-duration.

**What this answers in 5 minutes:**

- Does the gap come from a small subset of durations (e.g. only the
  long ones t ≥ 10) or is it uniform across all durations?
- A uniform gap suggests a systematic per-period TM bias on Check.
  A duration-concentrated gap suggests either a long-recession
  numerical issue or a duration-weighting bug.
- If MC and TM agree at t = 0..2 but diverge at t ≥ 3, the asymptotic
  tests (capped at max_rec=2) would have missed it — direct
  explanation of the discrepancy.

**Step A2:** From the same pickles, look at the recession-baseline
trajectory (`recession_all_results_AD`) per-duration. Do TM and MC
agree on the no-policy recession path? If they disagree on the
baseline more than on the policy run, the gap is in the rec_baseline
denominator subtraction, not the Check policy.

**Step A3:** If the per-cohort `AggCons` decomposition is in the
pickles (some HARK output structures keep per-type lists), compute
per-cohort multipliers for Check. Identify which cohort drives the
gap. Likely the dropout cohort (highest MPC) is most sensitive to
bucket discretization.

### Phase B — Targeted single-duration TM rerun (~10–20 min)

If Phase A points to a long-duration issue, rerun the TM-only
production pipeline at Baseline scale but with `max_recession_duration`
forced to a small value (e.g. 3) via a one-line patch in `Parameters.py`
or an env override. Compare the resulting Check multiplier to the
existing MC value at the corresponding duration window.

If TM agrees with MC at the short-duration cap, the gap is from
duration-averaging. If TM still disagrees, the gap is per-period.

### Phase C — Bucket sweep at Baseline (~30–60 min)

If Phase A points specifically to Check (which is most likely given
its 11.5% gap vs UI/TaxCut's 1–4%), rerun the TM-only Baseline with
`HAFISCAL_CHECK_BUCKETS=200` (4× the post-BUG-022 default of 50).
The BUG-022 sweep (5/20/50/200) on Reduced_Run showed Check converging
toward MC as buckets increased. If 50 buckets is sufficient at
Reduced_Run but not at Baseline, the convergence rate is sensitive
to the pLvl distribution which is broader at Baseline (21 types
across 3 cohorts). This is a plausible mechanism.

If 200 buckets closes the gap → BUG-022 fix needs to be revisited
for the Baseline case (set default n_buckets higher, or scale with
N_types). If 200 buckets still leaves a gap → bucket scheme isn't
the root cause and we move to Phase D.

### Phase D — Rerun the test driver Phase 7 at Reduced_Run with all 3 policies and FULL duration support (~45 min)

The Phase 7 results we trusted were capped at `max_rec=2`. Rerun
Phase 7 on Reduced_Run (3 cohorts) with `TEST_DRIVER_MAX_RECESSION_DURATION
= 21` (or `None`) for all three policies. This replicates the
production run's averaging window in the validation harness, where
we have richer instrumentation (per-iter Cratio, per-duration
trajectories). If TM↔MC agreement holds here, the gap is specific
to the type-count expansion (3 → 21). If it fails here too, the
gap is from full-duration averaging interacting with the AD CFunc
training in a way the cap=2 tests didn't expose.

### Phase E — Full Baseline test driver pass (~2–4 hours)

Last resort: run the test driver's Phases 1–7 at Baseline
parametrization (21 types). If we get here, the cheaper diagnostics
have already pointed at the mechanism and Phase E is just final
confirmation.

## Decision tree

```
Phase A1: per-duration Check gap
├── Concentrated at high-t → Phase B (single-duration rerun)
├── Uniform across durations → Phase C (bucket sweep)
└── Not in policy leg → Phase A2 (recession-baseline check)
                       └── Then Phase B or D

Phase B result
├── Closes gap → root cause = duration averaging interaction → Phase D for confirmation
└── Doesn't close gap → Phase C

Phase C result
├── 200 buckets closes gap → BUG-022 follow-up: scale n_buckets with N_types
└── Doesn't close → Phase D

Phase D result
├── TM↔MC agree at 21-duration Reduced_Run → gap is from 3→21 type expansion → Phase E
└── Disagree → root cause is in AD CFunc training under full averaging
```

## Success criteria

We've understood the puzzle when we can answer:
1. Why does TM Check at Baseline give 1.088 vs MC's 1.230?
2. Why was this NOT visible in the Phase 1–7 asymptotic-equality work?
3. Is there a code change that brings TM Check at Baseline to within
   ~3% of MC (the same agreement we see for UI and TaxCut)?

## Time budget

Phase A: 5–15 min (mostly file I/O + numpy)
Phase B: 10–20 min (one Baseline TM rerun with capped duration)
Phase C: 30–60 min (one Baseline TM rerun with HAFISCAL_CHECK_BUCKETS=200)
Phase D: 30–45 min (test driver Phase 7 on Reduced_Run with full durations)
Phase E: 2–4 hours (full Baseline test driver pass)

If Phase A points clearly at a mechanism, phases B–E may not all be
needed. Aim to spend the 5–15 min on A first and let the data direct
the next move.
