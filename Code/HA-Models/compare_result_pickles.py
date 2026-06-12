"""Content-level comparison of HAFiscal result pickles (the *_results*.csv files
written by Simulate.py's save_as_pickle — pickles despite the .csv extension).

Byte-compare (cmp/diff) FALSE-FAILS on these: pickle serialization is not
canonical (memoization order), and HARK distribution objects lack __eq__.
This walks the object tree and compares VALUES exactly:
  - ndarrays: np.array_equal (NaN==NaN for float dtypes)
  - HARK distributions: .pmv/.atoms arrays
  - rich objects: comparable members of __dict__
  - scalars/strings: ==

Used for the 2026-06-10 Gate-1 validation of the TM-AD durations-loop forking
(sequential vs forked: bit-exact PASS at HS_Only).

Usage:
    python compare_result_pickles.py DIR_A DIR_B [--glob '*.csv']
"""
import argparse
import glob as _glob
import os
import pickle
import sys

import numpy as np


def cmp_obj(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [(path, f"keys differ: {set(a) ^ set(b)}")]
        for k in a:
            out += cmp_obj(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return [(path, f"len {len(a)} vs {len(b)}")]
        for i, (x, y) in enumerate(zip(a, b)):
            out += cmp_obj(x, y, f"{path}[{i}]")
    elif isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        a_ = np.asarray(a); b_ = np.asarray(b)
        if a_.shape != b_.shape:
            out.append((path, f"shape {a_.shape} vs {b_.shape}"))
        elif not np.array_equal(a_, b_, equal_nan=(a_.dtype.kind == 'f')):
            d = np.abs(a_.astype(float) - b_.astype(float))
            out.append((path, f"VALUES DIFFER maxabs {np.nanmax(d):.3e}"))
    elif hasattr(a, 'pmv') and hasattr(a, 'atoms'):  # HARK distribution
        out += cmp_obj(np.asarray(a.pmv), np.asarray(b.pmv), f"{path}.pmv")
        out += cmp_obj(np.asarray(a.atoms), np.asarray(b.atoms), f"{path}.atoms")
    elif isinstance(a, (int, float, np.floating, str, bool, type(None))):
        eq = (a == b) or (isinstance(a, (float, np.floating))
                          and isinstance(b, (float, np.floating))
                          and np.isnan(a) and np.isnan(b))
        if not eq:
            out.append((path, f"{a!r} vs {b!r}"))
    else:
        da, db = getattr(a, '__dict__', None), getattr(b, '__dict__', None)
        if da is not None and db is not None:
            for k in set(da) & set(db):
                if isinstance(da[k], (np.ndarray, int, float, np.floating,
                                      list, tuple, dict)):
                    out += cmp_obj(da[k], db[k], f"{path}.{k}")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dir_a")
    p.add_argument("dir_b")
    p.add_argument("--glob", default="*.csv")
    args = p.parse_args()
    fail = False
    files = sorted(_glob.glob(os.path.join(args.dir_a, args.glob)))
    if not files:
        print(f"No files matched {args.glob} in {args.dir_a}"); sys.exit(2)
    for f in files:
        b = os.path.basename(f)
        fb_path = os.path.join(args.dir_b, b)
        if not os.path.exists(fb_path):
            print(f"*** MISSING in dir_b: {b}"); fail = True; continue
        try:
            ga = pickle.load(open(f, 'rb')); gb = pickle.load(open(fb_path, 'rb'))
        except Exception as e:
            print(f"*** UNREADABLE {b}: {e}"); fail = True; continue
        mm = cmp_obj(ga, gb, b)
        if mm:
            fail = True
            print(f"*** {b}: {len(mm)} mismatches")
            for pth, d in mm[:5]:
                print(f"      {pth}: {d}")
        else:
            print(f"  CONTENT-IDENTICAL {b}")
    print("\nRESULT:", "FAIL" if fail else "PASS (all values exactly equal)")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
