# Sources for `estimBetas.tex` (Table 4)

## Overview

**Table 4** shows the estimated discount factor distributions for each education group and the estimation targets used to identify them.

## Generation Method

**⚠️ Partially Computed** - Values are computed but **manually transcribed** into the table.

### Data Source

- **Computation**: `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py`
- **Output file**: `Code/HA-Models/Results/AllResults_CRRA_2.0_R_1.01.txt`
- **Output lines**: Lines 4, 10, 14, 20, 24, 30 (Panel A); Lines 5, 15, 25 (Panel B, model values)
- **Table file**: `Tables/estimBetas.tex` (values manually transcribed)

## Panel A: Estimated Discount Factor Distributions

### Beta and Nabla Parameters

**Source**: Lines 4, 14, and 24 of `AllResults_CRRA_2.0_R_1.01.txt`

| Education  | (β, ∇) | AllResults Lines |
|------------|--------|------------------|
| Dropout    | (0.719, 0.318) | Line 4 |
| Highschool | (0.925, 0.077) | Line 14 |
| College    | (0.983, 0.014) | Line 24 |

The discount factor for each agent type is drawn from a uniform distribution:

```
DiscFac ~ Uniform(β - ∇, β + ∇)
```

### Min and Max in Approximation

**Source**: Lines 10, 20, and 30 of `AllResults_CRRA_2.0_R_1.01.txt`

These are the minimum and maximum discount factors used in the discrete approximation (7 points per education group):

| Education  | (Min, Max) | Calculation |
|------------|------------|-------------|
| Dropout    | (0.447, 0.991) | (0.719 - 0.318, 0.719 + 0.318) |
| Highschool | (0.859, 0.990) | (0.925 - 0.077, 0.925 + 0.077) |
| College    | (0.971, 0.995) | (0.983 - 0.014, 0.983 + 0.014) |

## Panel B: Estimation Targets

### Median LW/Quarterly PI (Data)

**Source**: SCF 2004, computed by `Code/Empirical/make_liquid_wealth.py`

| Education  | Median LW/PI (%) |
|------------|------------------|
| Dropout    | 4.64 |
| Highschool | 30.2 |
| College    | 112.8 |

**Note**: Annual PI from SCF divided by 4 to obtain quarterly PI.

### Median LW/Quarterly PI (Model)

**Source**: Lines 5, 15, and 25 of `AllResults_CRRA_2.0_R_1.01.txt`

| Education  | Median LW/PI (%) | AllResults Line |
|------------|------------------|-----------------|
| Dropout    | 4.64 | Line 5 |
| Highschool | 30.2 | Line 15 |
| College    | 112.8 | Line 25 |

The model is estimated to match these median wealth-to-income ratios exactly.

## Estimation Method

### What is Estimated

For each education group, the estimation finds (β_e, ∇_e) that minimize:

```python
distance = ||median_LW_PI_model - median_LW_PI_data||
```

### Estimation Script

**File**: `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py`

**Method**: Simulated Method of Moments (SMM)

- Simulates heterogeneous agent economy
- Computes median liquid wealth / permanent income ratio
- Uses optimization to find (β, ∇) that match empirical targets

### Additional Constraints

The estimation also uses information from consumption drops upon UI expiration (see `EvalConsDropUponUILeave.py`), which helps pin down the impatience of each education group.

## Discount Factor Interpretation

### Why Education Groups Differ

- **Dropout**: Low β (0.719) and high ∇ (0.318) → Very impatient on average, high heterogeneity
- **Highschool**: Medium β (0.925) and medium ∇ (0.077) → Moderately patient, moderate heterogeneity  
- **College**: High β (0.983) and low ∇ (0.014) → Very patient, low heterogeneity

This reflects that:

1. Higher education correlates with greater patience
2. Higher education groups have more homogeneous time preferences
3. Lower education groups include both very impatient and moderately patient households

## Runtime

**~21 hours** to run the full estimation for all three education groups (~7 hours per group).

## To Regenerate

### Step 1: Run Estimation

```bash
cd Code/HA-Models/FromPandemicCode
python EstimAggFiscalMAIN.py
```

This generates `Results/AllResults_CRRA_2.0_R_1.01.txt`

### Step 2: Extract Values
Open `Results/AllResults_CRRA_2.0_R_1.01.txt` and extract:

- Lines 4, 10 (dropout β, ∇, and min/max)
- Lines 14, 20 (highschool β, ∇, and min/max)  
- Lines 24, 30 (college β, ∇, and min/max)
- Lines 5, 15, 25 (model median LW/PI)

### Step 3: Update Table
Manually update `Tables/estimBetas.tex` with the new values.

## Proposed Improvement

**Current**: Manual transcription from AllResults file  
**Better**: Generate this table programmatically

**Suggested implementation**:

```python
# In EstimAggFiscalMAIN.py or a post-processing script
def write_estimBetas_table(results_dict, output_path):
    """Generate estimBetas.ltx table from estimation results"""
    # Extract values from results dictionary
    # Format as LaTeX tabular
    # Write to .ltx file
```

## Related Files

- **Estimation script**: `EstimAggFiscalMAIN.py`
- **Results file**: `Results/AllResults_CRRA_2.0_R_1.01.txt`
- **Empirical moments**: `Code/Empirical/make_liquid_wealth.py`
- **Parameter definitions**: `EstimParameters.py`
- **UI exit analysis**: `EvalConsDropUponUILeave.py`
- **Table file**: `Tables/estimBetas.tex`

## References

- SCF 2004: Survey of Consumer Finances, Federal Reserve Board (<https://www.federalreserve.gov/econres/scf_2004.htm>)
- Liquid wealth definition excludes illiquid assets (housing, retirement accounts) and the "splurge" portion of liquid assets
