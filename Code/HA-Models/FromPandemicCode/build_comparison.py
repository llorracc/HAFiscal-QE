#!/usr/bin/env python3
"""Build comprehensive comparison: QE published vs current-branch Option C.

Extracts multipliers from pickles (bypassing Output_Results' plotting crash)
and assembles a side-by-side table for each parametrization.
"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['MPLBACKEND'] = 'Agg'
os.environ['MATPLOTLIB_BACKEND'] = 'agg'
sys.path.insert(0, '.')
sys.argv = ['build_comparison']

from OtherFunctions import load_pickle, get_simulation_diff

PARAMS = ['CRRA2', 'CRRA1', 'CRRA3', 'Rfree_1005', 'Rfree_1015',
          'ADElas', 'Rspell_4', 'LowerUBnoB', 'Splurge0']

QE_BASE = '/Volumes/Sync/GitHub/llorracc/HAFiscal-QE/Code/HA-Models/FromPandemicCode/Tables'
LATEST_BASE = '/Volumes/Sync/GitHub/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Tables'

def parse_multiplier_tex(path):
    """Return dict: 'check_noad','check_ad','ui_noad','ui_ad','tc_noad','tc_ad' or None."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        txt = f.read()
    out = {}
    import re
    def extract_three_nums(line):
        # split on & and extract first float in each cell
        parts = line.split('&')[1:4]
        nums = []
        for p in parts:
            m = re.search(r'[-+]?\d*\.?\d+', p)
            if m:
                nums.append(float(m.group()))
            else:
                return None
        return nums if len(nums) == 3 else None

    for line in txt.splitlines():
        if 'no AD effect' in line:
            nums = extract_three_nums(line)
            if nums:
                out['check_noad'], out['ui_noad'], out['tc_noad'] = nums
        elif '(AD effect)' in line and '1st round' not in line and '10y' in line:
            nums = extract_three_nums(line)
            if nums:
                out['check_ad'], out['ui_ad'], out['tc_ad'] = nums
        elif 'Long-run Multiplier (AD effect)' in line and '1st round' not in line:
            nums = extract_three_nums(line)
            if nums:
                out['check_ad'], out['ui_ad'], out['tc_ad'] = nums
    return out if out else None


def extract_from_pickles(fig_base):
    """Compute 10y NoAD/AD multipliers from pickles."""
    loc = locals()
    try:
        rec    = load_pickle('recession_results', fig_base, loc)
        rec_AD = load_pickle('recession_results_AD', fig_base, loc)
    except Exception as e:
        return None
    out = {}
    for name, npoA, npAD in [
        ('check', 'recessionCheck_results',  'recessionCheck_results_AD'),
        ('ui',    'recessionUI_results',     'recessionUI_results_AD'),
        ('tc',    'recessionTaxCut_results', 'recessionTaxCut_results_AD'),
    ]:
        try:
            p    = load_pickle(npoA, fig_base, loc)
            p_AD = load_pickle(npAD, fig_base, loc)
            dY = get_simulation_diff(rec, p, 'NPV_AggIncome')[-1]
            dC_NoAD = get_simulation_diff(rec, p, 'NPV_AggCons')[-1]
            dC_AD   = get_simulation_diff(rec_AD, p_AD, 'NPV_AggCons')[-1]
            out[f'{name}_noad'] = dC_NoAD / dY
            out[f'{name}_ad']   = dC_AD / dY
        except Exception:
            pass
    return out if out else None


def fmt(d, k):
    v = d.get(k) if d else None
    return f'{v:.3f}' if v is not None else '  -  '


print()
print('=' * 95)
print('HAFiscal-QE published vs current-branch Option C (TM, 10y-horizon multipliers)')
print('=' * 95)
print()
header = f"{'Param':<12s} | {'Policy':<7s} | {'(1) QE pub':>10s} | {'(2) Latest preOC':>16s} | {'(3) OptC+pub est':>16s} | Δ(3-1)"
print(header); print('-' * len(header))

for p in PARAMS:
    qe = parse_multiplier_tex(f'{QE_BASE}/{p}/Multiplier.tex')
    latest = parse_multiplier_tex(f'{LATEST_BASE}/{p}/Multiplier.tex')
    optc = extract_from_pickles(f'Figures/{p}/')
    for pol_label, suffix in [('Check', 'check'), ('UI', 'ui'), ('TaxCut', 'tc')]:
        for ad_label, ad_key in [('NoAD', '_noad'), ('AD', '_ad')]:
            k = suffix + ad_key
            q = qe.get(k) if qe else None
            l = latest.get(k) if latest else None
            o = optc.get(k) if optc else None
            if q is None and l is None and o is None:
                continue
            delta = f'{o-q:+.3f}' if (q is not None and o is not None) else '  -  '
            print(f'{p:<12s} | {pol_label+" "+ad_label:<7s} | {fmt({"x":q} if q is not None else None, "x"):>10s} | '
                  f'{fmt({"x":l} if l is not None else None, "x"):>16s} | {fmt({"x":o} if o is not None else None, "x"):>16s} | {delta}')
    print()

print()
print('Legend:')
print('  (1) HAFiscal-QE published (from Code/HA-Models/FromPandemicCode/Tables/<param>/Multiplier.tex)')
print('  (2) HAFiscal-Latest committed (pre-Option-C, but with other fixes)')
print('  (3) Option C code running with published estimates (this run)')
print()
print('Note: Sensitivity params (CRRA1, CRRA3, Rfree_*, ADElas, Rspell_4, LowerUBnoB)')
print('      publish "Long-run" multipliers, not directly comparable to my 10y-horizon.')
print('      CRRA2 is the paper Baseline; comparison is apples-to-apples.')
print()
