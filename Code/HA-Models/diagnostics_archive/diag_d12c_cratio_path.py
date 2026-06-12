"""
D-12c diagnostic: Compare per-period AggCons, AggIncome, Cratio, ADF
between MC and TM-a using D-10 (BUG-040 fix) pickles.

Key question: Where does the AD-loop divergence originate?
  - Per-period AggCons identical between MC and TM-a? → Then divergence is in Cratio_path → CFunc → ADF computation
  - Per-period AggCons differs → Then ADF differences trace back to *different empirical Cratio* fed to CFunc
"""
import pickle
import numpy as np
import os
import sys

DIR = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Figures/Reduced_Run_diag_bug040_off'

def load(name):
    """Load pickle stored with .csv extension."""
    with open(os.path.join(DIR, name), 'rb') as f:
        return pickle.load(f)

def safe_get(d, key, default=None):
    return d[key] if isinstance(d, dict) and key in d else default

def first_periods(name, d, n=8):
    print(f"\n=== {name} (first {n} periods) ===")
    for k in ['AggIncome', 'AggCons']:
        v = safe_get(d, k)
        if v is not None:
            arr = np.asarray(v).flatten()[:n]
            print(f"  {k:<12}: {arr}")

def compute_multiplier(d_chk, d_rec):
    """Compute multiplier from NPV values."""
    nc = safe_get(d_chk, 'NPV_AggCons')
    nr_c = safe_get(d_rec, 'NPV_AggCons')
    ny = safe_get(d_chk, 'NPV_AggIncome')
    ny_r = safe_get(d_rec, 'NPV_AggIncome')
    if any(x is None for x in [nc, nr_c, ny, ny_r]):
        return None, None, None, None

    nc = np.asarray(nc).flatten()
    nr_c = np.asarray(nr_c).flatten()
    ny = np.asarray(ny).flatten()
    ny_r = np.asarray(ny_r).flatten()

    # NPV diff at t=20 (~5 years for quarterly)
    if len(nc) >= 20:
        dC = nc[19] - nr_c[19]
        dY = ny[19] - ny_r[19]
        return dC, dY, dC/dY if dY != 0 else None, len(nc)
    return None, None, None, len(nc)

def main():
    print("="*72)
    print("D-12c: MC vs TM-a per-period decomposition (BUG-040 fixed, default off)")
    print("="*72)

    # Load all relevant pickles
    print("\nLoading pickles...")
    base_mc = load('base_results.csv')
    base_tm = load('base_results_TM.csv')
    rec_mc = load('recession_results_AD_MC.csv') if os.path.exists(os.path.join(DIR, 'recession_results_AD_MC.csv')) else None
    rec_tm = load('recession_results_AD_TM.csv') if os.path.exists(os.path.join(DIR, 'recession_results_AD_TM.csv')) else None
    rec_chk_mc = load('recessionCheck_results_AD_MC.csv')
    rec_chk_tm = load('recessionCheck_results_AD_TM.csv')
    rec_chk_no_ad_mc = load('recessionCheck_results_MC.csv')
    rec_chk_no_ad_tm = load('recessionCheck_results_TM.csv')

    # Available top-level keys
    print(f"\nbase_mc keys: {list(base_mc.keys())[:10] if isinstance(base_mc, dict) else type(base_mc)}")
    print(f"rec_chk_mc keys: {list(rec_chk_mc.keys())[:10] if isinstance(rec_chk_mc, dict) else type(rec_chk_mc)}")

    # First 8 periods
    first_periods("base_MC", base_mc)
    first_periods("base_TM", base_tm)
    first_periods("recCheck_AD_MC", rec_chk_mc)
    first_periods("recCheck_AD_TM", rec_chk_tm)
    first_periods("recCheck_NO-AD_MC", rec_chk_no_ad_mc)
    first_periods("recCheck_NO-AD_TM", rec_chk_no_ad_tm)
    if rec_mc is not None:
        first_periods("recession_AD_MC", rec_mc)
        first_periods("recession_AD_TM", rec_tm)

    # Compute per-period Cratio = AggCons / base_AggCons
    print("\n" + "="*72)
    print("Per-period Cratio = AggCons / base_AggCons (first 12 periods)")
    print("="*72)
    base_c_mc = np.asarray(safe_get(base_mc, 'AggCons')).flatten()
    base_c_tm = np.asarray(safe_get(base_tm, 'AggCons')).flatten()

    for label, d in [
        ('recCheck_AD_MC', rec_chk_mc),
        ('recCheck_AD_TM', rec_chk_tm),
    ]:
        c = np.asarray(safe_get(d, 'AggCons')).flatten()
        base = base_c_mc if 'MC' in label else base_c_tm
        n = min(12, len(c), len(base))
        cratio = c[:n] / base[:n]
        print(f"\n  {label} Cratio (per-period AggCons / per-period base_AggCons):")
        print(f"    {cratio}")

    if rec_mc is not None:
        for label, d in [
            ('recession_AD_MC', rec_mc),
            ('recession_AD_TM', rec_tm),
        ]:
            c = np.asarray(safe_get(d, 'AggCons')).flatten()
            base = base_c_mc if 'MC' in label else base_c_tm
            n = min(12, len(c), len(base))
            cratio = c[:n] / base[:n]
            print(f"\n  {label} Cratio (per-period AggCons / per-period base_AggCons):")
            print(f"    {cratio}")

    # Compute period-by-period AggIncome differences (Check vs recession)
    if rec_mc is not None:
        print("\n" + "="*72)
        print("ΔAggIncome per period: Check - recession (first 8 periods)")
        print("="*72)
        for label, dchk, drec in [
            ('MC', rec_chk_mc, rec_mc),
            ('TM', rec_chk_tm, rec_tm),
        ]:
            yc = np.asarray(safe_get(dchk, 'AggIncome')).flatten()
            yr = np.asarray(safe_get(drec, 'AggIncome')).flatten()
            n = min(8, len(yc), len(yr))
            print(f"\n  {label}: ΔY[t] = AggIncome_chk[t] - AggIncome_rec[t]")
            print(f"    {yc[:n] - yr[:n]}")

            # Per-period AggCons diff
            cc = np.asarray(safe_get(dchk, 'AggCons')).flatten()
            cr = np.asarray(safe_get(drec, 'AggCons')).flatten()
            print(f"  {label}: ΔC[t] = AggCons_chk[t] - AggCons_rec[t]")
            print(f"    {cc[:n] - cr[:n]}")

    # Multipliers
    print("\n" + "="*72)
    print("Multipliers (NPV at t=20, ~5 years)")
    print("="*72)
    if rec_mc is not None:
        dC, dY, mult, _ = compute_multiplier(rec_chk_mc, rec_mc)
        print(f"  MC AD Check: ΔC={dC:.2f}, ΔY={dY:.2f}, Mult={mult:.4f}")
        dC, dY, mult, _ = compute_multiplier(rec_chk_tm, rec_tm)
        print(f"  TM AD Check: ΔC={dC:.2f}, ΔY={dY:.2f}, Mult={mult:.4f}")

        dC, dY, mult, _ = compute_multiplier(rec_chk_no_ad_mc, rec_mc)
        print(f"  MC noAD Check (vs recession_with_AD): ΔC={dC:.2f}, ΔY={dY:.2f}, Mult={mult:.4f}")

    print("\n" + "="*72)
    print("PROPOSED MECHANISM:")
    print("If MC and TM show different per-period Cratio in *recession-only* AD,")
    print("then they have different *trained CFunc intercepts* at convergence,")
    print("which propagates to different ADF, which propagates to different multipliers.")
    print("This holds even when no-AD multipliers agree (they only test NPV equality, not shape).")
    print("="*72)

if __name__ == '__main__':
    main()
