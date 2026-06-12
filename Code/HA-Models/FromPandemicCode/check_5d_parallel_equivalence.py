"""
Phase 3 equivalence checker for 5D parallel refactor.

Diffs a parallel-run pickle against a sequential-baseline pickle using
strict np.array_equal across:
  - 3 final reduced arrays (welfare_num_total, AddInc_total_5D, AddCons_total_5D)
  - 11 durations × 5 per-duration series (welfare_num, AggInc_pol/none, AggCons_pol/none)

Pass criterion: every array bit-identical (np.array_equal == True).
On any difference, reports the first divergent (d_idx, t) for triage.

Usage:
    python check_5d_parallel_equivalence.py SEQ_PKL PAR_PKL [--label STR]
"""
from __future__ import annotations
import argparse
import pickle
import sys

import numpy as np


def _compare_array(seq, par, name):
    """Return (ok, first_diff_idx_or_None, max_abs_diff)."""
    if not isinstance(seq, np.ndarray):
        seq = np.asarray(seq)
        par = np.asarray(par)
    if seq.shape != par.shape:
        return False, None, float('inf')
    if np.array_equal(seq, par):
        return True, None, 0.0
    diff = np.abs(seq - par)
    first = np.unravel_index(np.argmax(diff > 0), diff.shape)
    return False, first, float(diff.max())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('seq_pkl')
    p.add_argument('par_pkl')
    p.add_argument('--label', default='')
    args = p.parse_args()

    with open(args.seq_pkl, 'rb') as f:
        seq = pickle.load(f)
    with open(args.par_pkl, 'rb') as f:
        par = pickle.load(f)

    print(f"=== Equivalence check {args.label} ===")
    print(f"  seq: {args.seq_pkl} (workers={seq['workers']}, A={seq['aCount']})")
    print(f"  par: {args.par_pkl} (workers={par['workers']}, A={par['aCount']})")
    print()

    if seq['aCount'] != par['aCount']:
        print(f"  FAIL: aCount mismatch ({seq['aCount']} vs {par['aCount']})")
        sys.exit(1)
    if seq['act_T'] != par['act_T']:
        print(f"  FAIL: act_T mismatch ({seq['act_T']} vs {par['act_T']})")
        sys.exit(1)
    if seq['max_dur'] != par['max_dur']:
        print(f"  FAIL: max_dur mismatch ({seq['max_dur']} vs {par['max_dur']})")
        sys.exit(1)

    fails = []

    # Final reduced arrays
    for k in ('welfare_num_total', 'AddInc_total_5D', 'AddCons_total_5D'):
        ok, idx, maxd = _compare_array(seq[k], par[k], k)
        status = 'PASS' if ok else 'FAIL'
        print(f"  [{status}] reduced/{k}: max|diff|={maxd:.3e}"
              + (f", first diff at {idx}" if not ok else ""))
        if not ok:
            fails.append(f"reduced/{k}")

    # rec_probs (constant, but check for sanity)
    ok, idx, maxd = _compare_array(seq['rec_probs'], par['rec_probs'], 'rec_probs')
    status = 'PASS' if ok else 'FAIL'
    print(f"  [{status}] rec_probs: max|diff|={maxd:.3e}")
    if not ok:
        fails.append("rec_probs")

    # Per-duration series
    series_keys = ('welfare_num_series', 'AggInc_pol_series', 'AggInc_none_series',
                   'AggCons_pol_series', 'AggCons_none_series')
    n_dur = len(seq['per_duration'])
    if len(par['per_duration']) != n_dur:
        print(f"  FAIL: per_duration length mismatch ({n_dur} vs {len(par['per_duration'])})")
        sys.exit(1)
    per_dur_pass = True
    for d_idx in range(n_dur):
        seq_d = seq['per_duration'][d_idx]
        par_d = par['per_duration'][d_idx]
        if seq_d['d_idx'] != par_d['d_idx']:
            print(f"  FAIL: per_duration[{d_idx}] d_idx mismatch ({seq_d['d_idx']} vs {par_d['d_idx']})")
            per_dur_pass = False
            continue
        for k in series_keys:
            ok, idx, maxd = _compare_array(seq_d[k], par_d[k], f"per_dur[{d_idx}]/{k}")
            if not ok:
                print(f"  [FAIL] per_dur[d_idx={d_idx}, dur={seq_d['dur']}]/{k}: "
                      f"max|diff|={maxd:.3e}, first diff at t={idx}")
                fails.append(f"per_dur[{d_idx}]/{k}")
                per_dur_pass = False
    if per_dur_pass:
        print(f"  [PASS] all per_duration series ({n_dur} durations × {len(series_keys)} arrays = "
              f"{n_dur * len(series_keys)} arrays bit-identical)")

    print()
    if not fails:
        print(f"=== EQUIVALENCE PASS ===")
        sys.exit(0)
    else:
        print(f"=== EQUIVALENCE FAIL ({len(fails)} array(s) differed) ===")
        for f in fails[:10]:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == '__main__':
    main()
