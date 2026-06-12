"""Extract & compare Check AD multipliers across D-10 (TM-lagged) and D-12b (TM-contemp)."""
import pickle, os, numpy as np

DIR_D10 = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Figures/Reduced_Run_diag_bug040_off'
DIR_D12B = '/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Figures/Reduced_Run_diag_tm_contemp'

def load(d, name):
    with open(os.path.join(d, name), 'rb') as f:
        return pickle.load(f)

def safe(d, k):
    return d.get(k) if isinstance(d, dict) else None

def npv_at(d, idx=19):
    arr = np.asarray(safe(d, 'NPV_AggCons')).flatten()
    return float(arr[idx]) if len(arr) > idx else None

def npv_inc(d, idx=19):
    arr = np.asarray(safe(d, 'NPV_AggIncome')).flatten()
    return float(arr[idx]) if len(arr) > idx else None

def show(label, dirname):
    try:
        recC = load(dirname, 'recessionCheck_results_AD_MC.csv')
        recC_TM = load(dirname, 'recessionCheck_results_AD_TM.csv')
        # Recession-only baseline
        rec_files = ['recession_results_AD_MC.csv', 'recession_results_AD_TM.csv']
        recM_paths = [os.path.join(dirname, f) for f in rec_files]
        if not all(os.path.exists(p) for p in recM_paths):
            # Fallback: use no-AD recession or check available files
            print(f"\n{label}: recession AD pickles not found. Files in dir:")
            for f in sorted(os.listdir(dirname))[:30]:
                print(f"  {f}")
            return
        rec_MC = load(dirname, 'recession_results_AD_MC.csv')
        rec_TM = load(dirname, 'recession_results_AD_TM.csv')

        # Multipliers
        for which in ['MC', 'TM']:
            chk = recC if which == 'MC' else recC_TM
            rec = rec_MC if which == 'MC' else rec_TM
            dC = npv_at(chk) - npv_at(rec)
            dY = npv_inc(chk) - npv_inc(rec)
            print(f"  {label} {which}: ΔC={dC:.2f}, ΔY={dY:.2f}, Mult={dC/dY:.4f}")
    except Exception as e:
        print(f"{label} ERROR: {e}")

print("D-10 (TM-lagged, default):")
show("D-10", DIR_D10)
print("\nD-12b (TM-contemporaneous):")
show("D-12b", DIR_D12B)

print("\nList D-12b files:")
for f in sorted(os.listdir(DIR_D12B)):
    print(f"  {f}")
