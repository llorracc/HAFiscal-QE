<!-- Status: DONE (superseded by implementation) -->
# Plan: TM P-Measure vs Q-Measure (Harmenberg Neutral) Comparison

**Date**: 2026-04-02  
**Context**: The original `plans/20260329-1853h_tm_scaleup_plan.md` Phases 0–5 validated TM
(physical measure P) against MC. Since MC code is unchanged and MC is expensive,
this plan **skips MC entirely** and just compares P-measure TM vs Q-measure TM
on the same experiments — using the original Phase 0/1 results as the reference.

---

## What this measures

The Harmenberg neutral measure Q eliminates the covariance error terms
ε\_cov,ss and ε\_cov,trans (math-derive-harm §11, (NM-error-decomp)):

| Error term | P-measure TM | Q-measure TM |
|-----------|-------------|-------------|
| ε\_grid (discretization) | present | present |
| ε\_level (E[p] bias) | cancels in diff | cancels in diff |
| ε\_dyn (pLvl\_factor) | present | present |
| ε\_cov,ss (~0.1% of level) | present | **0** |
| ε\_cov,trans (~0.04% transient) | present | **0** |

For differenced policy effects (recessionX − recession), ε\_cov,ss already
cancels. So the Q-measure should improve results by at most ~0.15 pp.
If the difference is larger, the covariance terms were underestimated.

---

## Reference values (from `plans/20260330-0812h_tm_scaleup_status.md`, Phases 0–1)

### Phase 0 (1 highschool type, recession, mCount=100)

| Metric | P-measure (original) |
|--------|---------------------|
| TM recession NPV (mCount=100) | −1.3956 |
| MC 100K×6 mean | −1.2851 |
| \|TM−MC\|/\|MC\| | 8.59% |

### Phase 1 (3 edu types, 4 experiments, mCount=100)

| Experiment | TM NPV | MC mean | Rel Error |
|------------|--------|---------|-----------|
| recession | (see status) | (see status) | ~4.1% |
| recCheck−rec (diff) | +0.957 | +0.945 | 1.28% |

---

## What to run

A single script that builds the Phase 0 and Phase 1 economies once (shared
setup), then runs every TM experiment twice — once with `neutral_measure=False`
(P), once with `neutral_measure=True` (Q) — at **mCount=40** (fast grid).

No MC at all.

### Phase 0 block (1 highschool type)

Experiments: `recession` only (treatment effect = recession − base).

For each of P and Q:
```python
bl = compute_baseline_tm_data(eco, mCount=40, neutral_measure=<flag>)
base = run_experiment_tm(eco, "base", mCount=40, neutral_measure=<flag>)
# switch to recession, solve
rec = run_experiment_tm_nonbase(eco_rec, "recession", rec_path, bl, mCount=40, neutral_measure=<flag>)
```

### Phase 1 block (3 edu types)

Experiments: `recession`, `recessionUI`, `recessionTaxCut`, `recessionCheck`.

Same pattern — run all 4 experiments under P and Q.

### Output

A table like:

```
PHASE 0 (1 type, recession only)
  Measure    TM NPV      Δ(Q−P)     Δ(Q−P)/|P|
  P          −X.XXXX
  Q          −X.XXXX     +X.XXXX    +X.XX%

PHASE 1 (3 types, differenced policy effects)
  Policy          TM-P        TM-Q        Δ(Q−P)     Δ/|P|
  UI ext          +X.XXXX     +X.XXXX     +X.XXXX    X.XX%
  Tax cut         +X.XXXX     +X.XXXX     +X.XXXX    X.XX%
  Check           +X.XXXX     +X.XXXX     +X.XXXX    X.XX%
```

---

## Runtime estimate

TM is fast. The cost drivers are `economy.solve()` (once per shock type)
and TM construction + ergodic finding (once per type per experiment).

From Phase 1 original (mCount=100, 3 types, 4 experiments):
TM total was ~30 seconds. At mCount=40, the TM matrix is ~6× smaller
((40×4)² vs (100×4)²), so TM operations are ~6× faster.

| Component | mCount=100 | mCount=40 (est.) |
|-----------|-----------|-----------------|
| economy.solve() | ~2s per shock type | ~2s (unchanged) |
| TM build + ergodic | ~5s per type×experiment | ~1s |
| Total P (Phase 0) | ~10s | ~5s |
| Total P (Phase 1) | ~30s | ~15s |
| Total Q (same) | ~30s | ~15s |
| **Grand total** | | **~40s** |

The pLvl buckets (n\_buckets=5, hardcoded default) only matter for the
`recessionCheck` experiment. At mCount=40 the pLvl distribution grid
(n\_points=200, separate from mCount) is unchanged, so bucket computation
adds negligible time.

**Estimated wall time: under 1 minute.**

---

## Success criteria

1. **P-measure at mCount=40 is close to P-measure at mCount=100** (grid
   convergence was confirmed in Phase 0c; expect <1% NPV change)
2. **Q−P difference is small** (~0.1–0.2%) for differenced policy effects,
   confirming ε\_cov cancellation in differencing
3. **Q−P difference is measurable** (~0.1%) for raw recession NPV,
   confirming the neutral measure does affect the level even if not the diff

---

## References

- `plans/20260329-1853h_tm_scaleup_plan.md` — original Phase 0–8 plan
- `plans/20260330-0812h_tm_scaleup_status.md` — original Phase 0–5 results (P-measure reference)
- `history/20260331-mathematical-derivations-harmenberg.md` §11 — error decomposition
- BST `ApndxHarKmenberg`, Theorem 1 — neutral measure identity
- `Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb` §8j — uncorrected 1D pitfall
