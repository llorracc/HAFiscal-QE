# Plan: compare MC variance reduction techniques on Gatekeeper + Harness

**Date:** 2026-04-06  
**Goal:** Measure how `income_shuffle` and `PermanentIncomeNormalizationMixin` affect MC precision on the 1-Gatekeeper and 2-Harness steps, using the small tier (N=1000, 3 seeds).

---

## 1. What to compare

Three MC configurations, all using `DualAggFiscalType` (P + Q measures simultaneously):

| Label | `income_shuffle` | `normalize_pLvl` | Description |
|-------|:----------------:|:-----------------:|-------------|
| **baseline** | False | False | Current default |
| **shuffle** | True | False | Income shock shuffling only |
| **shuffle+norm** | True | True | Income shuffling + per-cohort pLvl normalization |

All three use the same seeds, same N, same TM grid, same warmup (1/pDeath ≈ 160).

## 2. Metrics to report

For each configuration, report:

### 2.1 Cross-seed SE (primary metric)

For each quantity (AggCons/N, multiplier), compute the cross-seed standard error `SE = std(seeds) / sqrt(n_seeds)`. Compare SE across configurations:

| Quantity | SE (baseline) | SE (shuffle) | SE (shuffle+norm) | Ratio baseline/shuffle | Ratio baseline/shuffle+norm |
|----------|:-------------:|:------------:|:------------------:|:----------------------:|:---------------------------:|

### 2.2 Harmenberg precision (P vs Q)

For each configuration, report `SE_P / SE_Q`. The neutral measure should reduce SE for p-linear aggregates. The normalization should help further by stabilizing E[p].

### 2.3 Time-series variance of period-by-period AggCons

For a single seed, compute `var(AggCons_t)` over the post-warmup periods. This directly measures the period-to-period noise that the normalization should eliminate.

| Config | var(AggCons_t) P | var(AggCons_t) Q | P/Q ratio |
|--------|:----------------:|:----------------:|:---------:|

### 2.4 TM agreement (3-SE criterion)

For each configuration, does TM still fall within 3 SE of MC? The SE should shrink with shuffle+norm, making the test stricter but still passing if TM-MC agreement is genuine.

## 3. Steps

### Step A: 1-Gatekeeper (single type, baseline shock)

Run `compare_four_methods` three times with the three configurations. This tests Class A (AggCons per capita) and Class B (marginal utility, felicity).

**Runner:** `verify_four_methods_agreement.py` with:
- `--agents 1000 --periods 200 --m-count 50 --warmup 160`
- Seeds: run 3 times with `--seed 42`, `--seed 43`, `--seed 44`, collect results

**Configuration flags:**
- baseline: default (no extra flags)
- shuffle: set `agent.income_shuffle = True` after economy creation
- shuffle+norm: use `NormalizedDualAggFiscalType` with `income_shuffle=True, normalize_pLvl=True`

**Note:** `compare_four_methods` currently runs a single seed. To get cross-seed SE, either:
- (a) Call it 3 times with different `--seed` values and aggregate, or
- (b) Use `compare_four_methods_multi_seed` if available

### Step B: 2-Harness (multi-type, baseline shock)

Run `test_asymptotic_equality_revised.py --phase baseline` (baseline ergodic) three times with MC-small (N=1000, 3 seeds). The phase already runs multiple seeds internally.

**Configuration:** Modify `setup_economy` or the agent creation loop to enable shuffle/normalization per config.

### Step C: Compile comparison report

Write `history/variance-reduction-comparison_<YYYYMMDDTHHMM>.md` with:
- Side-by-side SE tables for all three configs
- Time-series variance tables
- TM agreement status
- Recommendation: which config(s) to enable by default

## 4. Implementation

### 4.1 Script: `parity_variance_reduction_comparison.py`

Location: `Code/HA-Models/FromPandemicCode/`

```
python parity_variance_reduction_comparison.py --tier small
```

The script:
1. Imports `compare_four_methods` and `phase1_baseline_ergodic`
2. For each of the 3 configs:
   a. Patches agent creation to set `income_shuffle` and/or use `NormalizedDualAggFiscalType`
   b. Runs the Gatekeeper with 3 seeds
   c. Runs the Harness **baseline** phase with MC-small
   d. Collects SE, time-series variance, TM agreement
3. Writes comparison report

### 4.2 What needs to change in existing code

| Change | File | Scope |
|--------|------|-------|
| `setup_economy` accepts `income_shuffle` and `normalize_pLvl` flags | `test_asymptotic_equality_revised.py` | Add parameters, set on agents after creation |
| `_build_single_type_economy` accepts same flags | `verify_four_methods_agreement.py` | Same |
| `HAFiscalNormalizationMixin` uses `post_state_hook` (not `sim_one_period`) | `hafiscal_normalization.py` | Already done via HARK commit b9f81caa |
| `NormalizedDualAggFiscalType` available | `AggFiscalModel.py` | Already exists |

### 4.3 Expected outcomes

| Config | Expected SE change (Class A) | Expected SE change (Class B) | Risk |
|--------|:--------------------------:|:--------------------------:|------|
| shuffle | 2–5x reduction | Modest (MU depends on p^k, not just p) | None — zero-bias, zero-cost |
| shuffle+norm | Large for AggCons (eliminates pLvl drift) | Moderate (pins E[p^k] analytically) | Small: normalization adjusts mNrm, could slightly perturb wealth dynamics |

## 5. Timeline

| Task | Time |
|------|------|
| Add `income_shuffle`/`normalize_pLvl` flags to `setup_economy` | 15 min |
| Write `parity_variance_reduction_comparison.py` | 30 min |
| Run small tier (3 configs × Gatekeeper + Harness) | ~20 min |
| Write comparison report | 10 min |

Total: ~1.5 hours including coding + running.

## 6. Decision criteria

- **Enable `income_shuffle=True` by default** if SE shrinks by ≥ 1.5x on Class A and there is no detectable bias (TM still within 3 SE).
- **Enable `normalize_pLvl=True` by default** if it provides additional SE reduction beyond shuffle alone and the time-series variance of AggCons drops substantially (≥ 3x), with no detectable bias.
- **Do not enable** if the SE reduction is < 1.2x or if TM falls outside 3 SE (suggesting bias).
