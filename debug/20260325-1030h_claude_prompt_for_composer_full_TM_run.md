# Prompt for Composer: Full TM Run and Comparison with Published Paper

**Date:** 2026-03-25 10:30
**Author:** Claude Opus 4.6
**Audience:** Composer

---

## Goal

Run the full Baseline parametrization (3 education types × 7
discount factors = 21 types) using `sim_method='TM'` and compare
the non-AD multipliers with the published values from the QE
version of the paper.

---

## Reference values (from published paper)

The published multiplier table is at:
```
/Volumes/Sync/GitHub/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode/Tables/CRRA2/Multiplier.ltx
```

The key row is "10y-horizon Multiplier (no AD effect)":

| Policy | Published multiplier (no AD) |
|--------|------------------------------|
| Stimulus check | **0.879** |
| UI extension | **0.906** |
| Tax cut | **0.847** |

The welfare table is at:
```
/Volumes/Sync/GitHub/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode/Tables/CRRA2/welfare6.ltx
```

The key row is `W(policy, Rec=1, AD=0)`:

| Policy | Published welfare (Rec=1, no AD) |
|--------|----------------------------------|
| Stimulus check | **1.00** |
| UI extension | **1.82** |
| Tax cut | **0.98** |

---

## What you need to do

### Step 1: Create a TM-only runner script

Create `AggFiscalMAIN_TM.py` (or modify a copy of
`AggFiscalMAIN.py`) that:

1. Sets `sim_method = 'TM'`
2. Sets `Run_AD = False` and `Run_1stRoundAD = False`
   (TM cannot do AD)
3. Keeps `Run_NonAD = True` and all experiment flags True
4. Runs the Baseline parametrization (NOT Reduced_Run)
5. Calls Output_Results wrapped to handle missing AD files

### Step 2: Handle Output_Results gracefully

Output_Results.py tries to load `_AD` and `_firstRoundAD` pickle
files.  These won't exist in a TM-only run.  You have two options:

**Option A (recommended):** After Simulate completes, create
stub AD result files by copying the non-AD results:

```python
import pickle, os

figs_dir = '...'  # same as passed to Simulate
for shock in ['recession', 'recessionUI', 'recessionCheck', 'recessionTaxCut']:
    # Copy non-AD results as placeholder AD results
    nonad_file = os.path.join(figs_dir, f'{shock}_results.csv')
    for suffix in ['_AD', '_firstRoundAD']:
        ad_file = os.path.join(figs_dir, f'{shock}_results{suffix}.csv')
        if not os.path.exists(ad_file) and os.path.exists(nonad_file):
            with open(nonad_file, 'rb') as f:
                data = pickle.load(f)
            with open(ad_file, 'wb') as f:
                pickle.dump(data, f)
    # Same for _all_results
    nonad_all = os.path.join(figs_dir, f'{shock}_all_results.csv')
    for suffix in ['_AD', '_firstRoundAD']:
        ad_all = os.path.join(figs_dir, f'{shock}_all_results{suffix}.csv')
        if not os.path.exists(ad_all) and os.path.exists(nonad_all):
            with open(nonad_all, 'rb') as f:
                data = pickle.load(f)
            with open(ad_all, 'wb') as f:
                pickle.dump(data, f)
```

This means the AD rows in the multiplier table will show the
same values as the non-AD row.  That's obviously wrong for the
AD values, but it lets Output_Results run to completion and
produce the non-AD row correctly.

**Option B:** Wrap the Output_Results call in a try/except and
report what failed.  Less clean but simpler.

### Step 3: Handle Welfare gracefully

Welfare_Results (called from Output_Results) may need per-agent
data.  If it crashes, either:
- Wrap it in try/except inside Output_Results, or
- Skip the welfare call entirely for TM-only runs

The welfare table uses `W(policy, Rec=1, AD=0)` which requires
non-AD recession results (which TM produces).  But the welfare
COMPUTATION uses per-agent consumption by wealth percentile,
which TM doesn't produce.  So welfare will likely need to be
skipped for now.

### Step 4: Run and compare

Run the full Baseline:

```bash
cd Code/HA-Models/FromPandemicCode
MPLBACKEND=Agg python AggFiscalMAIN_TM.py
```

This should take roughly **5-10 minutes** (solve ~2min per type
× 21 types ≈ 42 min for solve... actually the solve is the
bottleneck).

Wait — 21 types × ~2 min solve each = ~42 minutes for just the
solve.  The TM experiments are negligible after that.  So budget
~45-60 minutes total.

After it completes, compare the generated multiplier table:

```
Code/HA-Models/FromPandemicCode/Tables/CRRA2/Multiplier.ltx
```

with the reference values above.

### Step 5: Report results

Create a document at `debug/20260325-HHMM_full_TM_run_comparison.md`
with:

1. The TM non-AD multiplier values for Check, UI, TaxCut
2. The published (MC) non-AD multiplier values
3. The relative difference for each
4. Any crashes or warnings encountered
5. Runtime

---

## Expected results

| Policy | Published (MC, no AD) | TM (expected) | Notes |
|--------|-----------------------|---------------|-------|
| Check | 0.879 | ~0.87-0.89 | Should match within ~2% |
| UI | 0.906 | ~0.90-0.91 | Should match within ~1% |
| TaxCut | 0.847 | **~0.5-0.9?** | BUG-010: consumption TE is ~80% wrong |

The TaxCut value will likely be off because BUG-010 (solver uses
unscaled IncShkDstn for tax-cut income) is NOT fixed.  The income
side is correct but the consumption response is wrong.  Report
whatever you get — it's a known issue.

Check and UI should be close to the published values.  If they
differ by more than 5%, investigate.

---

## What NOT to do

- Do NOT run with `sim_method='both'` — that would take hours
  (full MC burn-in for 21 types)
- Do NOT try to fix BUG-010 (TaxCut) — that's a separate project
- Do NOT modify tm_methods.py or Simulate.py for this run
- Do NOT try to produce welfare tables — skip them for now
- Do NOT run the robustness parametrizations (Splurge0, PVSame,
  etc.) — just the main Baseline

---

## Files to create/modify

| File | Action |
|------|--------|
| `AggFiscalMAIN_TM.py` | New: copy of AggFiscalMAIN.py with TM settings |
| `Output_Results.py` | Possibly modify to handle missing AD/welfare gracefully |
| `debug/20260325-HHMM_full_TM_run_comparison.md` | New: results report |
