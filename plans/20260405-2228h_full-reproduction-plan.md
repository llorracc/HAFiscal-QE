# Full reproduction plan: TM-first, MC-validate, best-estimate

**Date:** April 5, 2026  
**Goal:** Reproduce every paper result, using the best available method for each, and compare to published values.

---

## Phase 1: TM-only results (fast, overnight or less)

These are Class A (p-linear) results that the TM computes exactly (no MC noise, no kernel needed). They comprise the bulk of the paper's tables and figures.

### What to compute

| Paper output | Method | File | Notes |
|-------------|--------|------|-------|
| **Consumption multipliers (non-AD)** — Check, UI, TaxCut | TM | `Multiplier.tex` row 1 | `run_experiment_tm_nonbase` per policy, averaged over recession durations |
| **Consumption multipliers (AD)** | TM-AD | `Multiplier.tex` row 2 | `run_ad_tm` per policy |
| **Consumption multipliers (1st-round AD)** | TM-AD (1 iter) | `Multiplier.tex` row 3 | `run_ad_tm(num_max_iterations=1)` |
| **Share of policy during recession** | TM | `Multiplier.tex` rows 4-5 | Ratio of recession-period NPV to total NPV |
| **IRFs: ΔC/C for each policy** | TM | `recession_*.pdf` | `get_simulation_percent_diff` on TM AggCons |
| **Cumulative multiplier paths** | TM | `Cumulative_multipliers.pdf` | Time path of NPV ratio |
| **Recession-duration multipliers** | TM | `Multiplier_RecLengths.tex` | Per-duration (2q, 4q, 8q) |
| **Robustness (CRRA, Rfree, etc.)** | TM | `Multiplier_SplurgeComp.tex` | Same pipeline, different parametrizations |

### How to run

Modify `AggFiscalMAIN.py` (or create a wrapper) to:
1. Set `sim_method = 'TM'`
2. Run all experiments: baseline, recession, recessionUI, recessionTaxCut, recessionCheck
3. Run AD variants: `run_ad_tm` for each policy
4. Call `Output_Results` to generate figures and tables

**Expected time:** ~30-60 minutes (TM is fast; the AD iterations are the bottleneck).

### Comparison to paper

For each multiplier value, compute `|TM_new - paper_published| / |paper_published|`. The paper's published values were computed with MC at N=10,000. Differences of 1-3% are expected (MC noise in the original). Differences > 5% warrant investigation.

---

## Phase 2: MC-only results (slow, multi-hour)

These are Class C (distributional) results that require per-agent data, plus validation of Phase 1.

### What to compute

| Paper output | Method | File | Notes |
|-------------|--------|------|-------|
| **Lorenz curve (estimation targets)** | MC | Step 2 output | Already computed during calibration; verify reproducibility |
| **MPC by education** | MC | Step 2 output | Same |
| **Welfare tables** | MC + kernel | `WelfareStimulus.tex`, `Welfare.tex`, `ConsEquivWelfare.tex`, `WelfareByWPercentile.tex` | Need `cLvl_all_splurge` per agent; kernel provides TM cross-check for aggregate welfare |
| **MC validation of TM multipliers** | MC | — | Run same experiments as Phase 1 with MC, compare |

### How to run

1. Set `sim_method = 'MC'` (or `'both'` for direct comparison)
2. Use `Full_Output='ForWelfare'` to store per-agent consumption
3. Run `Welfare_Results` on the MC output
4. Compare MC multipliers to Phase 1 TM multipliers

**Expected time:** ~6-12 hours at Baseline scale (N=10,000 × 21 types). Can be shortened with Reduced_Run (N=5,000) for a first pass.

### Comparison

- MC multipliers vs TM multipliers (Phase 1): should agree within 1-3%
- MC welfare vs TM kernel welfare: kernel provides ~0.5% accurate aggregate welfare; per-percentile welfare is MC-only

---

## Phase 3: Best-estimate results

For each paper output, use the **best available method**:

| Result category | Best method | Rationale |
|----------------|-------------|-----------|
| **Consumption multipliers, NPVs, IRFs** | **TM** (Phase 1) | Exact for p-linear; no MC noise. Grid convergence verified at 0.01%. |
| **AD multipliers** | **TM-AD** (Phase 1) | AD loop converges; CFunc dynamics match MC. TM avoids MC noise in the Cratio path. |
| **Aggregate welfare (E[u], E[u'], welfare-per-dollar)** | **TM + kernel** | Kernel gives +0.15% accuracy for E_P[u'] and -0.5% for E_P[u]. No MC noise. |
| **Per-percentile welfare** | **MC** (Phase 2) | Needs per-agent data. TM can't compute distributional welfare by wealth bin. |
| **Lorenz curves, wealth shares** | **MC** (Phase 2) | Class C: needs per-agent level wealth. |
| **Check stimulus (with phase-out)** | **TM + p-buckets** | Phase-out is non-p-linear; `_compute_check_buckets` handles it. |

### Best-estimate table

For each paper table entry:

```
| Table | Row | Paper value | Best estimate | Method | |Δ|/paper |
```

### How to run

1. Run Phase 1 (TM) → get exact multipliers, IRFs
2. Run Phase 2 (MC) → get welfare, Lorenz, validation
3. For aggregate welfare: compute kernel from TM ergodic at each experiment's time-varying distribution
4. Assemble best-estimate tables using TM for Class A, kernel for Class B, MC for Class C
5. Compare every entry to the published paper values

---

## Implementation

### Script: `reproduce_best_estimate.py`

```python
"""
Reproduce all paper results using best available method per Class.
Phase 1 (TM): multipliers, IRFs, NPVs — fast
Phase 2 (MC): welfare, Lorenz, validation — slow
Phase 3: assemble best-estimate tables, compare to published
"""
```

This script:
1. Loads parameters (`Baseline` parametrization)
2. Creates the 21-type economy
3. Runs TM baseline + all experiments + AD (Phase 1)
4. Generates Phase 1 tables and figures
5. Optionally runs MC (Phase 2) if `--include-mc` flag is set
6. Compares Phase 1 and Phase 2 where both exist
7. Assembles best-estimate tables (Phase 3)
8. Outputs a comparison report: `history/reproduction-comparison-YYYYMMDD.md`

### Flags

```
python reproduce_best_estimate.py                  # Phase 1 only (~1h)
python reproduce_best_estimate.py --include-mc      # Phases 1+2 (~12h)
python reproduce_best_estimate.py --include-mc --parametrization Reduced_Run  # Fast test (~1h)
```

---

## Timeline

| Phase | Scale | Time | What you get |
|-------|-------|------|-------------|
| **Quick test** | Reduced_Run, TM only | ~10 min | Verify pipeline works, directional multipliers |
| **Phase 1** | Baseline, TM only | ~1 hour | All multiplier/IRF tables, exact |
| **Phase 2** | Baseline, MC | ~6-12 hours | Welfare tables, Lorenz validation |
| **Phase 3** | Assembly | ~5 min | Best-estimate comparison report |

**Recommendation:** Run Phase 1 tonight (~1 hour). Review the TM-vs-published comparison in the morning. If the multipliers match within 1-3%, proceed with Phase 2 (MC overnight) and Phase 3 assembly.

---

## What the `AggFiscalMAIN_reduced.py` sanity check just showed

The Reduced_Run (N=5000, TM-only, 3 education × 1 β) completed in 4 minutes and produced:

| Policy | AD Multiplier (Reduced_Run) | Paper (Baseline, MC) |
|--------|:--------------------------:|:--------------------:|
| Check | 1.21 | 1.23 |
| UI | 1.28 | 1.21 |
| Tax Cut | 1.03 | 0.98 |

These are close but not identical — expected since Reduced_Run uses 1 β per education (not 7) and N=5000 (not 10,000). The full Baseline run should be closer.
