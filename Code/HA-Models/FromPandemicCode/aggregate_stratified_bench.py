"""Aggregate stratified-shuffle MC benchmark across seeds."""
import sys, os, numpy as np, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_welfare6_parallel as r

CELLS = ['check_norec','ui_norec','taxcut_norec',
         'check_rec','ui_rec','taxcut_rec',
         'check_rec_AD','ui_rec_AD','taxcut_rec_AD']

def aggregate(parent_dir, n_seeds=4):
    seed_dirs = [f'{parent_dir}/seed{s}' for s in range(n_seeds)]
    seed_dirs = [d for d in seed_dirs if os.path.isdir(d)]
    print(f'Found {len(seed_dirs)} seed dirs under {parent_dir}')
    all_seeds = []
    for d in seed_dirs:
        try:
            w6, _ = r.compute_welfare6_table(d)
            all_seeds.append(w6)
        except Exception as e:
            print(f'  ERROR loading {d}: {e}')
    n = len(all_seeds)
    print()
    print(f'{"cell":<16} ' + ' '.join(f's{s:<7}' for s in range(n)) + f'  {"mean":>8} {"SE":>8} {"SE%":>6}')
    print('-' * (16 + 9*n + 30))
    rows = {}
    for c in CELLS:
        vals = np.array([s.get(c, np.nan) for s in all_seeds])
        mean = np.nanmean(vals)
        se = np.nanstd(vals, ddof=1) / np.sqrt(np.isfinite(vals).sum()) if np.isfinite(vals).sum() > 1 else float('nan')
        sep = abs(se / mean * 100) if mean and not np.isnan(mean) else float('nan')
        rows[c] = (mean, se, sep, vals)
        vals_str = ' '.join(f'{v:7.4f}' if np.isfinite(v) else '    nan' for v in vals)
        print(f'{c:<16} {vals_str}  {mean:7.4f} {se:7.4f} {sep:5.2f}%')
    return rows


if __name__ == '__main__':
    parent = sys.argv[1] if len(sys.argv) > 1 else 'welfare6_stratified_bench_HS_Only'
    aggregate(parent)
