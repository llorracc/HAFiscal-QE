"""D-13b: BUG-041 fix verification across ALL shock types (Check, UI, TaxCut)."""
import pickle, numpy as np

CONFIGS = {
    'pre-fix (D-10)': 'Reduced_Run_diag_bug040_off',
    'POST-FIX (bug041_fix)': 'Reduced_Run_diag_bug041_fix',
}
ROOT = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Figures'

def load(d, name):
    return pickle.load(open(f'{ROOT}/{d}/{name}', 'rb'))

def npv_mult_paper(rec_alt_AD, rec_AD, rec_alt_noAD, rec_noAD, idx=19):
    gov = rec_alt_noAD['NPV_AggIncome'][idx] - rec_noAD['NPV_AggIncome'][idx]
    dC = rec_alt_AD['NPV_AggCons'][idx] - rec_AD['NPV_AggCons'][idx]
    return dC / gov if gov != 0 else float('nan')

print(f"{'Shock':<10} {'Config':<25} {'MC mult':<10} {'TM mult':<10} {'residual %':<12}")
print("=" * 78)
for shock in ['Check', 'UI', 'TaxCut']:
    for label, dirname in CONFIGS.items():
        try:
            rec_mc = load(dirname, 'recession_results_AD_MC.csv')
            rec_tm = load(dirname, 'recession_results_AD_TM.csv')
            rec_no_mc = load(dirname, 'recession_results_MC.csv')
            rec_no_tm = load(dirname, 'recession_results_TM.csv')
            alt_mc = load(dirname, f'recession{shock}_results_AD_MC.csv')
            alt_tm = load(dirname, f'recession{shock}_results_AD_TM.csv')
            alt_no_mc = load(dirname, f'recession{shock}_results_MC.csv')
            alt_no_tm = load(dirname, f'recession{shock}_results_TM.csv')
            mult_mc = npv_mult_paper(alt_mc, rec_mc, alt_no_mc, rec_no_mc)
            mult_tm = npv_mult_paper(alt_tm, rec_tm, alt_no_tm, rec_no_tm)
            rel = (mult_mc - mult_tm) / mult_tm * 100
            print(f"{shock:<10} {label:<25} {mult_mc:<10.4f} {mult_tm:<10.4f} {rel:<+12.2f}")
        except Exception as e:
            print(f"{shock:<10} {label:<25} ERROR: {e}")
    print()
