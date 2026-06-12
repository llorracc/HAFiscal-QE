"""D-13c: Standard error of the post-fix multiplier estimate via 3 seeds.

Computes mean and SE of MC vs TM-a multiplier residuals across:
- bug041_fix       (seed=0, default)
- bug041_seed100   (seed=100)
- bug041_seed200   (seed=200)
"""
import pickle, numpy as np

SEEDS = {
    0: 'Reduced_Run_diag_bug041_fix',
    100: 'Reduced_Run_diag_bug041_seed100',
    200: 'Reduced_Run_diag_bug041_seed200',
}
ROOT = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Figures'

def load(d, name):
    return pickle.load(open(f'{ROOT}/{d}/{name}', 'rb'))

def npv_mult_paper(rec_alt_AD, rec_AD, rec_alt_noAD, rec_noAD, idx=19):
    gov = rec_alt_noAD['NPV_AggIncome'][idx] - rec_noAD['NPV_AggIncome'][idx]
    dC = rec_alt_AD['NPV_AggCons'][idx] - rec_AD['NPV_AggCons'][idx]
    return dC / gov if gov != 0 else float('nan')

def get_multipliers(dirname):
    """Return dict of {shock: (mc_mult, tm_mult)} for one seed's run."""
    rec_mc = load(dirname, 'recession_results_AD_MC.csv')
    rec_tm = load(dirname, 'recession_results_AD_TM.csv')
    rec_no_mc = load(dirname, 'recession_results_MC.csv')
    rec_no_tm = load(dirname, 'recession_results_TM.csv')
    out = {}
    for shock in ['Check', 'UI', 'TaxCut']:
        alt_mc = load(dirname, f'recession{shock}_results_AD_MC.csv')
        alt_tm = load(dirname, f'recession{shock}_results_AD_TM.csv')
        alt_no_mc = load(dirname, f'recession{shock}_results_MC.csv')
        alt_no_tm = load(dirname, f'recession{shock}_results_TM.csv')
        mult_mc = npv_mult_paper(alt_mc, rec_mc, alt_no_mc, rec_no_mc)
        mult_tm = npv_mult_paper(alt_tm, rec_tm, alt_no_tm, rec_no_tm)
        out[shock] = (mult_mc, mult_tm)
    return out

results = {}
for seed, dirname in SEEDS.items():
    try:
        results[seed] = get_multipliers(dirname)
    except Exception as e:
        results[seed] = f"ERROR: {e}"

print("Per-seed multipliers (post-BUG-041-fix, all use cohort N=4900/9800/17640):")
print()
print(f"{'Shock':<10} {'Seed':<8} {'MC mult':<10} {'TM mult':<10} {'residual %':<12}")
print("-" * 60)
for shock in ['Check', 'UI', 'TaxCut']:
    mc_vals, tm_vals, residuals = [], [], []
    for seed in SEEDS:
        if isinstance(results[seed], str):
            print(f"{shock:<10} {seed:<8} {results[seed]}")
            continue
        mc, tm = results[seed][shock]
        rel = (mc - tm) / tm * 100 if tm != 0 else float('nan')
        mc_vals.append(mc)
        tm_vals.append(tm)
        residuals.append(rel)
        print(f"{shock:<10} {seed:<8} {mc:<10.4f} {tm:<10.4f} {rel:<+12.2f}")
    if len(mc_vals) >= 2:
        mc_mean = np.mean(mc_vals); mc_sd = np.std(mc_vals, ddof=1)
        tm_mean = np.mean(tm_vals); tm_sd = np.std(tm_vals, ddof=1)
        rel_mean = np.mean(residuals); rel_sd = np.std(residuals, ddof=1)
        rel_se = rel_sd / np.sqrt(len(residuals))
        print(f"{shock:<10} {'mean±sd':<8} {mc_mean:<.4f}±{mc_sd:.4f}   "
              f"{tm_mean:<.4f}±{tm_sd:.4f}   {rel_mean:+.2f}%±{rel_sd:.2f}pp  "
              f"(SE={rel_se:.2f}pp, t={rel_mean/rel_se:.2f})")
    print()

print("Interpretation:")
print("  |t| < 2 → residual is within sampling noise (multipliers AGREE)")
print("  |t| ≥ 2 → residual is real systematic bias")
