# USactuarial.txt

## Overview

This file contains US Social Security Administration (SSA) actuarial life tables with age-specific mortality and survival probabilities.

## File Format

Tab-delimited text file with columns:

- Age
- Male mortality rate
- Male population
- Male life expectancy
- Female mortality rate
- Female population  
- Female life expectancy

## Current Status: **NOT USED IN ACTIVE CODE**

### Historical Usage (Archived)

This file was used by older versions of the parameter setup code:

- `Archive/SetupParamsCSTW.py`
- `Archive/MinExample_Error/SetupParamsCSTW.py`

The archived code implemented detailed lifecycle mortality modeling:

```python
# Old approach (Archive/SetupParamsCSTW.py, line ~95)
f = open(data_location + '/' + 'USactuarial.txt','r')
actuarial_reader = csv.reader(f,delimiter='\t')
raw_actuarial = list(actuarial_reader)
base_death_probs = []
for j in range(len(raw_actuarial)):
    # Assumes everyone is a white woman (column 4)
    base_death_probs += [float(raw_actuarial[j][4])]
```

The code then adjusted these base mortality rates by education level using `EducMortAdj.txt`.

### Current Approach

The current active code (`SetupParamsCSTW.py`) uses a simplified approach with a hardcoded constant survival probability:

```python
# Current approach (SetupParamsCSTW.py, line ~70)
LivPrb_i = [1.0 - 1.0/160.0]  # ~99.375% quarterly survival probability
```

### Why the Change?

Possible reasons for simplification:

- Model parsimony and computational efficiency
- HARK toolkit now provides built-in mortality data
- Detailed lifecycle mortality not critical for paper's main results
- Calibration found constant survival probability adequate

## File Classification

**Type:** Source input data (NOT a generated computational result)

**Repository treatment:**

- ✅ Kept in HAFiscal-Latest
- ✅ Copied to HAFiscal-Public  
- ✅ Copied to HAFiscal-QE (stays on main branch, NOT moved to `including-generated-objects`)
- **Rationale:** This is archived reference data that documents the original model calibration approach

## Related Files

- `EducMortAdj.txt` - Education-based mortality rate adjustments (also archived, not currently used)
- `SCFwealthDataReduced.txt` - SCF wealth distribution data (also archived, not currently used)
- `Archive/SetupParamsCSTW.py` - Archived parameter setup code that used these files

## Source

Original data source: US Social Security Administration

- Actuarial life tables
- Public domain data

## Notes

This file is preserved for:

- Historical reference and reproducibility of earlier model versions
- Potential future extensions requiring detailed lifecycle mortality
- Documentation of calibration evolution
- Robustness checks with age-varying survival probabilities

The `Archive/` directory location indicates this is preserved historical material, not actively used in current computational workflows.
