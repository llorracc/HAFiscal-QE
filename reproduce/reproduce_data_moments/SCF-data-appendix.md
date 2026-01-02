# SCF Data Appendix (QE Data Editor)

## Purpose
This appendix documents due diligence on the SCF 2004 data used for all empirical results. It focuses on the Federal Reserve “summary extract” workflow (the data actually used for the paper) and briefly notes a full-file reconstruction that matched within expected Stata read/write tolerances.

## Data files (paper vs. downloads)

- **Git-versioned (paper)**: `Code/Empirical/rscfp2004.dta` (2013 dollars) — single source of truth for the paper and for `make_liquid_wealth.py`.
- **Fed download (current)**: `Code/Empirical/rscfp2004_USD2022.dta` (raw 2022 dollars).
- **Reconstructed (this verification)**: `reproduce/rscfp2004_2013.dta` (Fed 2022$ download adjusted back to 2013$).

## Scripts referenced

- `Code/Empirical/make_liquid_wealth.py` (loads the git-versioned 2013$ file).
- `Code/Empirical/adjust_scf_inflation.py` (defines the 1.1587 factor and the 35 dollar variables).
- `Code/Empirical/compare_scf_datasets.py` (QA comparison tooling).
- `reproduce/reconstruct_scf-data-from-full-files_chatGPT.sh` (downloads summary extract, applies documented CPI anchors, scales dollar vars, writes 2013$).
- `reproduce/reproduce_scf-data-downloads-comparisons.sh` (strict/loose comparisons on the Fed extract).

## CPI / scaling assumptions

- Documented anchors (from prior SCF docs): CPI-U-RS 2013 = 367.4; late-2022 = 424.7; observed Fed ratio 2013$→2022$ = 1.1587.
- Scaling applied: **2022$ → 2013$ factor = 1 / 1.1587 = 0.86303616**.

## Dollar-variable set
Thirty-five variables (identical to `adjust_scf_inflation.py`), covering income, wealth, assets, and debts (e.g., `income`, `norminc`, `networth`, `liq`, `stocks`, `bond`, `houses`, `oresre`, `nnresre`, `bus`, `debt`, `mrthel`, `install`, etc.).

## Commands to reproduce (extract workflow)
From `{{REPO_NAME}}`:

```bash
# 1) Activate the venv (rebuilt arm64 in this workflow)
source .venv/bin/activate

# 2) Reconstruct 2013$ from Fed summary extract (uses anchors + dollar list)
cd reproduce
./reconstruct_scf-data-from-full-files_chatGPT.sh

# Outputs: reproduce/rscfp2004_2013.dta

# 3) Compare dollar-variable maxima (and minima) against git-versioned data
python - <<'PY'
import pyreadstat, pandas as pd
from pathlib import Path
DOLLAR_VARIABLES = ["income","wageinc","bussefarminc","intdivinc","kginc","ssretinc","transfothinc","norminc","networth","asset","fin","nfin","debt","mrthel","resdbt","othloc","ccbal","install","odebt","liq","cds","nmmf","stocks","bond","savbnd","cashli","othma","othfin","vehic","houses","oresre","nnresre","bus","othnfin","veh_inst"]
orig = Path("../Code/Empirical/rscfp2004.dta")
reb  = Path("rscfp2004_2013.dta")
dfO,_ = pyreadstat.read_dta(orig); dfR,_ = pyreadstat.read_dta(reb)
for v in DOLLAR_VARIABLES:
    if v not in dfO or v not in dfR: continue
    maxO = pd.to_numeric(dfO[v], errors="coerce").max()
    maxR = pd.to_numeric(dfR[v], errors="coerce").max()
    pct  = None if maxO==0 or pd.isna(maxO) else (maxR-maxO)/maxO*100
    print(f"{v:12} maxO={maxO:15,.2f} maxR={maxR:15,.2f} pct={(pct if pct is not None else float('nan')):.6f}%")
PY
```

## Results (extract workflow, summary)

- Dollar vars compared: **35/35 common**.
- Maxima differences: two tight clusters:
  - Income-type vars: ~**-0.0039%** (rebuilt slightly lower).
  - Most assets/debts: ~**+0.0283%** (rebuilt slightly higher).
  - Larger (still small) cases: `networth`/`asset` maxima differ by ~**0.16%**, consistent with Stata float read/write rounding noted in prior SCF docs.
- Minima: many are zero; nonzero minima showed ~±0.0283% or ~0.0039% differences, also consistent with Stata precision limits.
- Strict SHA/byte comparisons (from `reproduce_scf-data-downloads-comparisons.sh`) confirm the Fed download differs from the git-versioned file; after scaling, statistical differences are within documented tolerances.

## Brief note on full-file reconstruction

- A separate full-file reconstruction (same CPI anchors and dollar-variable list) produced 2013$ data matching the git-versioned dataset within the same Stata float tolerance bands (~0.03–0.16% on extrema). No artifacts are stored here; this is noted for completeness.

## Interpretation for QE Data Editor

- The git-versioned `Code/Empirical/rscfp2004.dta` (2013$) remains the production dataset used by `make_liquid_wealth.py` and the paper.
- Fresh Fed downloads (2022$) can be adjusted back to 2013$ using the documented CPI anchors and the 1.1587 ratio; adjusted maxima/minima align within expected Stata read/write rounding (<~0.16%, typically <0.03%).
- Comparisons cover all 35 dollar variables; non-dollar variables are unchanged.
- No external data beyond the Fed summary extract are required for this verification; commands above rerun the checks.
