"""
Compare results between HARK 0.14.1 and HARK 0.17.0 versions.

This script compares the numerical results from --comp min runs
to validate that the HARK 0.17.0 migration maintains numerical accuracy.
"""

import json
import os
import sys

# Paths to result files
BASELINE_0141_DIR = "/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-baseline"
CURRENT_0170_DIR = "/home/econ-ark/GitHub/llorracc/HAFiscal-Latest"

def read_result_file(filepath):
    """Read a result file and parse the dictionary."""
    try:
        with open(filepath, 'r') as f:
            content = f.read().strip()
            # The file contains a Python dict literal, use eval (safe for our controlled files)
            return eval(content)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def compare_values(val1, val2, name, tolerance=1e-6):
    """Compare two numerical values with tolerance."""
    if val1 is None or val2 is None:
        return False, "Missing value"
    
    abs_diff = abs(val1 - val2)
    rel_diff = abs_diff / abs(val1) if val1 != 0 else abs_diff
    
    passed = abs_diff < tolerance or rel_diff < tolerance
    
    return passed, f"{val1:.10f} vs {val2:.10f} (diff: {abs_diff:.2e}, rel: {rel_diff:.2e})"

def main():
    print("="*70)
    print("HARK Version Comparison: 0.14.1 vs 0.17.0")
    print("="*70)
    
    # Define result files to compare
    result_files = [
        ("Result_AllTarget.txt", "Code/HA-Models/Target_AggMPCX_LiquWealth"),
        ("Result_AllTarget_Splurge0.txt", "Code/HA-Models/Target_AggMPCX_LiquWealth"),
    ]
    
    all_passed = True
    tolerance = 1e-6  # Strict tolerance for numerical identity
    
    for filename, subpath in result_files:
        print(f"\n--- Comparing {filename} ---")
        
        path_0141 = os.path.join(BASELINE_0141_DIR, subpath, filename)
        path_0170 = os.path.join(CURRENT_0170_DIR, subpath, filename)
        
        # Check if files exist
        if not os.path.exists(path_0141):
            print(f"  ⚠️  0.14.1 result not found: {path_0141}")
            all_passed = False
            continue
            
        if not os.path.exists(path_0170):
            print(f"  ⚠️  0.17.0 result not found: {path_0170}")
            all_passed = False
            continue
        
        # Read results
        result_0141 = read_result_file(path_0141)
        result_0170 = read_result_file(path_0170)
        
        if result_0141 is None or result_0170 is None:
            all_passed = False
            continue
        
        print(f"  0.14.1: {result_0141}")
        print(f"  0.17.0: {result_0170}")
        
        # Compare each key
        all_keys = set(result_0141.keys()) | set(result_0170.keys())
        
        for key in sorted(all_keys):
            val_0141 = result_0141.get(key)
            val_0170 = result_0170.get(key)
            
            passed, details = compare_values(val_0141, val_0170, key, tolerance)
            
            status = "✅" if passed else "❌"
            print(f"    {status} {key}: {details}")
            
            if not passed:
                all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("🎉 All comparisons PASSED - results are numerically identical!")
        print("   The HARK 0.17.0 migration maintains numerical accuracy.")
    else:
        print("⚠️  Some comparisons FAILED - results differ between versions.")
        print("   Review the differences above.")
    print("="*70)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
