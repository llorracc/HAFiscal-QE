# Sources for `MPC_WQ.tex` (Table 1)

## Overview

**Table 1** in the paper shows MPCs (Marginal Propensities to Consume) across wealth quartiles, comparing model predictions to empirical data.

## Generation Method

**✅ Fully Computed** - This table is **programmatically generated**.

### Source Location

- **Generator script**: `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py`
- **Generation line**: Line 680
- **Output file**: `Code/HA-Models/Target_AggMPCX_LiquWealth/Figures/MPC_WealthQuartiles_Table.ltx`
- **Wrapper file**: `Tables/MPC_WQ.tex` (includes the generated `.ltx` file)

## Code Reference

From `Estimation_BetaNablaSplurge.py` (lines 672-687):

```python
output  ="\\begin{tabular}{@{}lcccccc@{}} \n"
output +="\\toprule \n"
output +="                  & \multicolumn{5}{c}{MPC} &   \\\\   \n"
output +="                  &  1st WQ  & 2nd WQ  & 3rd WQ & 4th WQ  & Agg  &  K/Y  \\\\  \\midrule \n"
output +="Model &"+mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][3])      + " & "+ mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][2])+ " & "+  \
                            mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][1])      + " & "+ mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][0]) + " & "+  \
                            mystr2(SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin'][0])+ " & "+ mystr2(SplurgeNot0_Sol['KY_Model'])  + " \\\\ \n"
output +="Data &"+          mystr2(MPC_target[2,3])                                         + " & "+ mystr2(MPC_target[2,2])+ " & "+  \
                            mystr2(MPC_target[2,1])                                         + " & "+ mystr2(MPC_target[2,0]) + " & "+  \
                            mystr2(Agg_MPCX_target[0])                                      + " & "+ mystr2(KY_target)  + " \\\\ \\bottomrule \n"
output +="\\end{tabular}  \n"

with open(Abs_Path+'/Figures/MPC_WealthQuartiles_Table.tex','w') as f:
    f.write(output)
    f.close()
```

## Data Sources

### Model Row
- **Source**: Simulated model with estimated splurge parameter
- **Parameters from**: `Result_AllTarget.txt` (estimated splurge, beta, nabla)
- **Method**: `FagerengObjFunc()` simulates the model and computes:
  - `simulated_MPC_means_smoothed[0-3]`: MPCs by wealth quartile (reverse order)
  - `simulated_MPC_mean_add_Lottery_Bin[0]`: Aggregate MPC
  - `KY_Model`: Model-implied capital-to-income ratio

### Data Row
- **MPC by wealth quartile**: From `MPC_target[2,:]` 
  - Original source: **Fagereng, Holm, and Natvik (2021)**, Table 9
  - Norwegian lottery winner data, 3rd lottery quartile
  - Defined in `Estimation_BetaNablaSplurge.py` lines 76-80
  
- **Aggregate MPC**: From `Agg_MPCX_target[0]`
  - Original source: **Fagereng, Holm, and Natvik (2021)**, Figure 2
  - Same-year consumption response to lottery win
  - Value: 0.5056845 (line 83)
  
- **K/Y ratio**: From `KY_target`
  - Original source: US capital-to-income ratio
  - Value: 6.60 (line 94)

## Estimation Targets

The model parameters are estimated to match these empirical moments:
1. Aggregate MPC over time (5 periods)
2. Liquid wealth distribution (Lorenz curve, 4 points)
3. Capital-to-income ratio (K/Y = 6.60)
4. MPCs by wealth quartile

## Table Structure

The table compares:
- **Row 1**: Model predictions with estimated splurge ≥ 0
- **Row 2**: Empirical data targets

Columns show:
1. MPC for 1st wealth quartile (poorest)
2. MPC for 2nd wealth quartile
3. MPC for 3rd wealth quartile
4. MPC for 4th wealth quartile (richest)
5. Aggregate MPC
6. Capital-to-income ratio (K/Y)

## Runtime

**~20 minutes** to run the full estimation and table generation script.

## To Regenerate

```bash
cd Code/HA-Models/Target_AggMPCX_LiquWealth
python Estimation_BetaNablaSplurge.py
```

## Related Files

- **Parameter estimation**: `Estimation_BetaNablaSplurge.py`
- **Estimated parameters**: `Result_AllTarget.txt`
- **Setup parameters**: `SetupParamsCSTW.py`
- **Generated table**: `Figures/MPC_WealthQuartiles_Table.ltx`
- **Wrapper table**: `../../Tables/MPC_WQ.tex`

## References

- Fagereng, Andreas, Martin B. Holm, and Gisle J. Natvik (2021). "MPC Heterogeneity and Household Balance Sheets." *American Economic Journal: Macroeconomics*, 13(4): 1-54.
- SCF 2004: Survey of Consumer Finances, Federal Reserve Board

