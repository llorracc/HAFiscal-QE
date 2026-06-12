"""D-13: Verify BUG-041 fix closes the residual.

Compares MC vs TM-a Check multipliers across:
- D-10 (BUG-040 fix only, pre-BUG-041): expected ~13% residual
- bug041_fix (BUG-041 fix applied, MC convention): expected residual closes
- bug041_legacy (BUG-041 legacy mode = pre-fix TM): expected ≈ D-10
"""
import pickle, os, numpy as np

CONFIGS = {
    'D-10 (pre-BUG-041)': 'Reduced_Run_diag_bug040_off',
    'bug041_fix (MC default)': 'Reduced_Run_diag_bug041_fix',
    'bug041_legacy (TM legacy)': 'Reduced_Run_diag_bug041_legacy',
}
ROOT = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Figures'

def load(d, name):
    return pickle.load(open(f'{ROOT}/{d}/{name}', 'rb'))

def npv_mult_paper(rec_chk_AD, rec_AD, rec_chk_noAD, rec_noAD, idx=19):
    """Paper definition: ΔC(AD) / gov, where gov = ΔY(noAD)."""
    gov = rec_chk_noAD['NPV_AggIncome'][idx] - rec_noAD['NPV_AggIncome'][idx]
    dC = rec_chk_AD['NPV_AggCons'][idx] - rec_AD['NPV_AggCons'][idx]
    return dC / gov if gov != 0 else float('nan')

print("MC vs TM-a CHECK multiplier (paper def: ΔC(AD) / gov_addinc, NPV at h=19)")
print("="*100)
print(f"{'Config':<30} {'MC AD':<10} {'TM AD':<10} {'rel diff %':<12} {'MC noAD':<10} {'TM noAD':<10} {'noAD diff %':<12}")
for label, dirname in CONFIGS.items():
    try:
        rec_chk_mc_AD = load(dirname, 'recessionCheck_results_AD_MC.csv')
        rec_chk_tm_AD = load(dirname, 'recessionCheck_results_AD_TM.csv')
        rec_mc_AD = load(dirname, 'recession_results_AD_MC.csv')
        rec_tm_AD = load(dirname, 'recession_results_AD_TM.csv')
        rec_chk_mc_noAD = load(dirname, 'recessionCheck_results_MC.csv')
        rec_chk_tm_noAD = load(dirname, 'recessionCheck_results_TM.csv')
        rec_mc_noAD = load(dirname, 'recession_results_MC.csv')
        rec_tm_noAD = load(dirname, 'recession_results_TM.csv')

        mult_mc = npv_mult_paper(rec_chk_mc_AD, rec_mc_AD, rec_chk_mc_noAD, rec_mc_noAD)
        mult_tm = npv_mult_paper(rec_chk_tm_AD, rec_tm_AD, rec_chk_tm_noAD, rec_tm_noAD)
        rel = (mult_mc - mult_tm) / mult_tm * 100 if mult_tm != 0 else float('nan')

        mult_mc_no = npv_mult_paper(rec_chk_mc_noAD, rec_mc_noAD, rec_chk_mc_noAD, rec_mc_noAD)
        mult_tm_no = npv_mult_paper(rec_chk_tm_noAD, rec_tm_noAD, rec_chk_tm_noAD, rec_tm_noAD)
        rel_no = (mult_mc_no - mult_tm_no) / mult_tm_no * 100 if mult_tm_no != 0 else float('nan')

        print(f"{label:<30} {mult_mc:<10.4f} {mult_tm:<10.4f} {rel:<+12.2f} {mult_mc_no:<10.4f} {mult_tm_no:<10.4f} {rel_no:<+12.2f}")
    except Exception as e:
        print(f"{label:<30} ERROR: {e}")

print()
print("Per-period decomposition: ΔY (Check - Recession) at t=1..3 (FULL AD)")
print("="*100)
print(f"{'Config':<30} {'t=0 MC':<8} {'t=0 TM':<8} {'t=1 MC':<8} {'t=1 TM':<8} {'MC/TM ratio':<12}")
for label, dirname in CONFIGS.items():
    try:
        rec_chk_mc_AD = load(dirname, 'recessionCheck_results_AD_MC.csv')
        rec_chk_tm_AD = load(dirname, 'recessionCheck_results_AD_TM.csv')
        rec_mc_AD = load(dirname, 'recession_results_AD_MC.csv')
        rec_tm_AD = load(dirname, 'recession_results_AD_TM.csv')

        yc_mc = np.asarray(rec_chk_mc_AD['AggIncome']).flatten()
        yr_mc = np.asarray(rec_mc_AD['AggIncome']).flatten()
        yc_tm = np.asarray(rec_chk_tm_AD['AggIncome']).flatten()
        yr_tm = np.asarray(rec_tm_AD['AggIncome']).flatten()
        dy_mc = yc_mc - yr_mc
        dy_tm = yc_tm - yr_tm
        ratio_t1 = dy_mc[1] / dy_tm[1] if dy_tm[1] != 0 else float('nan')
        print(f"{label:<30} {dy_mc[0]:<8.0f} {dy_tm[0]:<8.0f} {dy_mc[1]:<8.0f} {dy_tm[1]:<8.0f} {ratio_t1:<12.3f}")
    except Exception as e:
        print(f"{label:<30} ERROR: {e}")
