# TM-only Baseline run vs published HAFiscal-QE multipliers

**Run:** `runs/tm_only_baseline_parallel_20260409T1533.log` (26.3 min wall clock,
parallelized via the os.fork dispatch in 3ceacebb).
**Output table (fresh):** `Code/HA-Models/FromPandemicCode/Tables/Baseline/Multiplier.tex`
**Reference values:** `Private/Submissions/QE/HAFiscal_Apr11_2025.pdf` page 31
(conditionally accepted version, Table 6).

## Comparison

| Row | Policy | Our run | Paper | Δ (abs) | Δ (%) |
|---|---|---|---|---|---|
| **no AD** | Stimulus check | 0.889 | 0.854 | +0.035 | +4.1% |
|  | UI extension | 0.928 | 0.893 | +0.035 | +3.9% |
|  | Tax cut | 0.878 | 0.826 | +0.052 | +6.3% |
| **AD** | Stimulus check | 1.088 | 1.199 | −0.111 | **−9.3%** |
|  | UI extension | 1.166 | 1.175 | −0.009 | **−0.8% ✓** |
|  | Tax cut | 0.999 | 0.952 | +0.047 | +4.9% |
| 1st round AD¹ | Stimulus check | 1.101 | 1.125 | −0.024 | −2.1% |
|  | UI extension | 1.128 | 1.119 | +0.009 | +0.8% |
|  | Tax cut | 0.947 | 0.926 | +0.021 | +2.3% |

¹ The "1st round AD" row in our `Tables/Baseline/Multiplier.tex` was
generated from STALE `_firstRoundAD.csv` pickles dated Apr 7 (see
`Figures/Baseline/recession*_results_firstRoundAD.csv` mtimes), not from
this run. `AggFiscalMAIN_reduced.py:39` sets `Run_1stRoundAD = False`,
so the current run did not regenerate the first-round-AD pickles.
Output_Results.py loaded the old ones and the table was written with
stale values in that row. The no-AD and AD rows ARE fresh from this
run.

## Honest interpretation

- **UI matches the paper essentially exactly on the AD line** (1.166 vs
  1.175, 0.8% off). UI was not affected by BUG-022 (Check bucket
  discretization) or BUG-023 (TaxCut atoms typo), so it is the
  cleanest end-to-end test of the underlying solver after the
  HARK 0.14.1 → 0.17.0 upgrade. The match within rounding suggests
  the upgrade is sound for the recession-policy machinery proper.

- **All three no-AD multipliers are systematically ~4–6% HIGH vs paper.**
  Uniform direction across all three policies points to a baseline-
  solver drift between HARK 0.14 (paper era) and HARK 0.17 (current),
  not a policy-specific bug. This drift propagates into the AD line
  but is partially cancelled by AD's amplification recalibration.

- **Stimulus check AD is 9.3% LOW vs paper.** This is the largest gap.
  No-AD is +4.1% but AD is −9.3%, so the AD/noAD ratio is
  ~1.224 in our run vs ~1.404 in the paper — AD amplification is
  noticeably suppressed for Check. Consistent with BUG-022's bucket
  fix (5 → 50 buckets) materially changing MPCs at the corners of
  the check distribution, which feed back through the AD CFunc.

- **Tax cut AD is 4.9% HIGH vs paper.** Both no-AD (+6.3%) and AD
  (+4.9%) are high in similar proportion, so the AD/noAD ratio is
  comparable to the paper. The drift here looks baseline-level, not
  AD-specific. BUG-023's TaxCut atoms typo fix (now in Simulate.py
  line 212-220, see ff82e837 / 0cc56cd1) is part of the picture.

## What was NOT validated by this run

- Per-wealth-percentile welfare tables (TM cannot produce — requires MC).
- Lorenz / wealth-share figures (produced by the parameter estimation
  step, not the simulation).
- The Check AD line specifically warrants follow-up investigation
  before claiming the TM-only pipeline reproduces the paper. Same for
  TaxCut to a lesser extent.
- The "1st round AD" line is currently stale-derived in the table.
  Either delete the stale pickles before the next run, or set
  Run_1stRoundAD = True to regenerate them (~6 min extra wall clock).

## Reproducibility note

I previously quoted "paper" values of Check 1.143 / UI 1.167 / TaxCut
0.962, sourced from `Code/HA-Models/FromPandemicCode/Tables/CRRA2/Multiplier.tex`.
That file is dated Apr 1, 2026 — i.e., from a previous local run, NOT
from the published paper. The actual paper values (table above) are
from the Apr 11, 2025 conditionally-accepted PDF. The lesson is that
files under `Code/HA-Models/FromPandemicCode/Tables/*/` are
simulation OUTPUTS that get overwritten by every run, not paper
references. Always pull paper values from `Private/Submissions/QE/*.pdf`.
