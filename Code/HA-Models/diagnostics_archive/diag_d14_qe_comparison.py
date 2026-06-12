"""D-14: Comprehensive comparison of post-BUG-041-fix multipliers vs QE published.

QE published numbers come from:
  conclusions_private/2026-05-04_qe_fidelity_full_vs_QE_published.md

Current numbers come from bug041_fix runs (3 seeds: 0, 100, 200).
"""
import pickle, numpy as np

SEEDS = {
    0: 'Reduced_Run_diag_bug041_fix',
    100: 'Reduced_Run_diag_bug041_seed100',
    200: 'Reduced_Run_diag_bug041_seed200',
}
ROOT = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Figures'

# QE Jan 2026 published values (from 2026-05-04_qe_fidelity_full_vs_QE_published.md)
QE_PUBLISHED = {
    'Check': {
        'noAD': 0.879,
        '1stAD': 1.157,
        'AD': 1.234,
    },
    'UI': {
        'noAD': 0.906,
        '1stAD': 1.148,
        'AD': 1.211,
    },
    'TaxCut': {
        'noAD': 0.847,
        '1stAD': 0.951,
        'AD': 0.978,
    },
}

def load(d, name):
    return pickle.load(open(f'{ROOT}/{d}/{name}', 'rb'))

def npv_mult_paper(rec_alt_AD, rec_AD, rec_alt_noAD, rec_noAD, idx=19):
    """Paper definition: ΔC(any) / gov, where gov = ΔY(noAD)."""
    gov = rec_alt_noAD['NPV_AggIncome'][idx] - rec_noAD['NPV_AggIncome'][idx]
    dC = rec_alt_AD['NPV_AggCons'][idx] - rec_AD['NPV_AggCons'][idx]
    return dC / gov if gov != 0 else float('nan')

def get_one_seed_all(dirname, method='MC'):
    """Return {shock: {scope: mult}} for one seed."""
    suf = '_MC' if method == 'MC' else '_TM'
    rec = {
        'AD': load(dirname, f'recession_results_AD{suf}.csv'),
        '1stAD': load(dirname, f'recession_results_firstRoundAD{suf}.csv'),
        'noAD': load(dirname, f'recession_results{suf}.csv'),
    }
    out = {}
    for shock in ['Check', 'UI', 'TaxCut']:
        alt = {
            'AD': load(dirname, f'recession{shock}_results_AD{suf}.csv'),
            '1stAD': load(dirname, f'recession{shock}_results_firstRoundAD{suf}.csv'),
            'noAD': load(dirname, f'recession{shock}_results{suf}.csv'),
        }
        out[shock] = {}
        for scope in ['noAD', '1stAD', 'AD']:
            out[shock][scope] = npv_mult_paper(
                alt[scope], rec[scope], alt['noAD'], rec['noAD']
            )
    return out

# Collect per-seed results for both MC and TM
seed_results = {'MC': {}, 'TM': {}}
for method in ['MC', 'TM']:
    for seed, dirname in SEEDS.items():
        seed_results[method][seed] = get_one_seed_all(dirname, method)

def mean_se(vals):
    """Mean and standard error across seeds (assumed independent)."""
    arr = np.asarray(vals)
    n = len(arr)
    return arr.mean(), arr.std(ddof=1) / np.sqrt(n) if n > 1 else 0.0

print("=" * 105)
print("COMPREHENSIVE COMPARISON: Current (BUG-040+041 fixes) vs HAFiscal-QE Published")
print("=" * 105)
print()
print("**QE BASELINE characterization** (from 2026-05-04_qe_fidelity_full_vs_QE_published.md):")
print("  Tag/Commit:          v2026-01-09-18-17 (commit e93c8092)")
print("  Interpretation:      ESC")
print("  Step-2 method:       MC, NM tol 1e-4 from-scratch, legacy 3-D GICx, single-start")
print("  Step-5 method:       MC throughout (HAFISCAL_SIM_METHOD=MC)")
print("  perm_shocks_unemp:   off (PermShk=1 for unemployed)")
print("  Cohort N:            uniform default (10000 per cohort)")
print("  Profile:             qe_fidelity")
print()
print("**CURRENT VERSION characterization** (bug041_fix, 3 seeds):")
print("  Branch/HEAD:         0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC (post-BUG-041 fix)")
print("  Interpretation:      ESC")
print("  Step-2 method:       NOT re-run; uses cached DiscFac (post-BUG-039 Phase G defaults)")
print("  Step-5 method:       BOTH (sim_method='both', so we have MC and TM-a in parallel)")
print("  perm_shocks_unemp:   off (HAFISCAL_PERM_DURING_UNEMP=off, matches QE)")
print("  Cohort N:            4900/9800/17640 (D/HS/C, shuffle-friendly + quota-exact)")
print("  Methodology:         shuffle (mc_shuffle=1, income_shuffle=1, markov_shuffle=1)")
print("  TM-a:                tm_a_indexed=1 (BUG-033 splurge-in-budget refactor)")
print("  BUG-040:             FIXED (HAFISCAL_PLVL_GROWS_DURING_UNEMP=off default = QE conv.)")
print("  BUG-041:             FIXED (HAFISCAL_TM_CFUNC_OFFSET=mc default = QE conv.)")
print("  Seeds:               0, 100, 200 (cross-seed SE reported)")
print()

print("=" * 105)
print("MULTIPLIER COMPARISON (NPV at 5-year horizon, ΔC(scope) / gov_addinc)")
print("=" * 105)
print()
print(f"{'Shock':<8} {'Scope':<8} | {'QE pub':<8} | {'MC mean±SE':<18} {'Δ vs QE %':<12} | "
      f"{'TM mean±SE':<18} {'Δ vs QE %':<12} | {'MC vs TM %':<10}")
print("-" * 105)
for shock in ['Check', 'UI', 'TaxCut']:
    for scope in ['noAD', '1stAD', 'AD']:
        qe = QE_PUBLISHED[shock][scope]
        mc_vals = [seed_results['MC'][s][shock][scope] for s in SEEDS]
        tm_vals = [seed_results['TM'][s][shock][scope] for s in SEEDS]
        mc_mean, mc_se = mean_se(mc_vals)
        tm_mean, tm_se = mean_se(tm_vals)
        mc_dq = (mc_mean - qe) / qe * 100
        tm_dq = (tm_mean - qe) / qe * 100
        mc_tm = (mc_mean - tm_mean) / tm_mean * 100
        print(f"{shock:<8} {scope:<8} | {qe:<8.3f} | {mc_mean:.4f}±{mc_se:.4f}      "
              f"{mc_dq:<+12.2f} | {tm_mean:.4f}±{tm_se:.4f}      {tm_dq:<+12.2f} | "
              f"{mc_tm:<+10.2f}")
    print()

print("=" * 105)
print("HEADLINES")
print("=" * 105)
print()

# Compute pass/fail criteria for AD multiplier (the headline)
print("AD multiplier (most-cited paper metric):")
for shock in ['Check', 'UI', 'TaxCut']:
    qe = QE_PUBLISHED[shock]['AD']
    mc_vals = [seed_results['MC'][s][shock]['AD'] for s in SEEDS]
    tm_vals = [seed_results['TM'][s][shock]['AD'] for s in SEEDS]
    mc_mean, mc_se = mean_se(mc_vals)
    tm_mean, tm_se = mean_se(tm_vals)

    # MC vs QE: t-statistic
    t_mc = (mc_mean - qe) / mc_se if mc_se > 0 else float('inf')
    t_tm = (tm_mean - qe) / tm_se if tm_se > 0 else float('inf')

    # Within ±3% threshold (QE-fidelity criterion)
    mc_within_3pc = abs((mc_mean - qe)/qe) < 0.03
    tm_within_3pc = abs((tm_mean - qe)/qe) < 0.03

    print(f"  {shock:<8}: QE={qe:.3f}  MC={mc_mean:.4f} ({'OK' if mc_within_3pc else 'OUT'} ±3%, t_vs_QE={t_mc:+.1f})  "
          f"TM={tm_mean:.4f} ({'OK' if tm_within_3pc else 'OUT'} ±3%, t_vs_QE={t_tm:+.1f})")
print()
