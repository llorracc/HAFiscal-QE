#!/usr/bin/env python
"""
Full Comparison Script for HAFiscal 0.14.1-bugfixed vs 0.17.0-native-adjusted

This runs the complete reproduction workflow for both versions and compares
results after each step. Can be interrupted and resumed.

Steps:
1. Splurge estimation (~30 min each, ~1 hour total)
2. Discount factor estimation (~48 hours each) 
3. Robustness (optional, set RUN_STEP_3=True)
4. HANK/SAM Jacobians (~12 hours each)
5. Policy comparisons (~12 hours each)

Usage:
    python full_compare.py [--step N] [--quick]
    
    --step N    Run only step N (1-5)
    --quick     Use reduced parameters for faster testing (~1 hour total)
"""

import subprocess
import json
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
import shutil

# Configuration
VERSIONS = {
    '0.14.1-bugfixed': {
        'base': '/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed',
        'python': '/home/econ-ark/GitHub/llorracc/HAFiscal-0.14.1-bugfixed/.venv/bin/python',
    },
    '0.17.0-loky-warmup': {
        'base': '/home/econ-ark/GitHub/llorracc/HAFiscal-Latest',
        'python': '/home/econ-ark/GitHub/llorracc/HAFiscal-Latest/.venv/bin/python',
    }
}

OUTPUT_DIR = Path('/tmp/hafiscal_full_compare')
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR = OUTPUT_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)
RESULTS_DIR = OUTPUT_DIR / 'results'
RESULTS_DIR.mkdir(exist_ok=True)

# Step definitions
STEPS = {
    1: {
        'name': 'splurge_estimation',
        'description': 'Estimating splurge factor (Section 3.1)',
        'script': 'Estimation_BetaNablaSplurge.py',
        'cwd': 'Target_AggMPCX_LiquWealth',
        'expected_hours': 0.5,
        'outputs': [
            'Target_AggMPCX_LiquWealth/Result_AllTarget.txt',
            'Target_AggMPCX_LiquWealth/Result_AllTarget_Splurge0.txt',
        ],
    },
    2: {
        'name': 'discount_factor_estimation',
        'description': 'Estimating discount factor distributions (Section 3.3.3)',
        'script': 'EstimAggFiscalMAIN.py',
        'cwd': 'FromPandemicCode',
        'expected_hours': 48,
        'outputs': [
            'Results/DiscFacEstim_CRRA_2.0_R_1.01.txt',
            'Results/AllResults_CRRA_2.0_R_1.01.txt',
        ],
    },
    3: {
        'name': 'robustness_splurge0',
        'description': 'Robustness: Splurge=0 estimation',
        'script': 'EstimAggFiscalMAIN.py',
        'args': ['1.01', '2.0', '0.7', '0.5', '0'],
        'cwd': 'FromPandemicCode',
        'expected_hours': 48,
        'outputs': [
            'Results/DiscFacEstim_CRRA_2.0_R_1.01_Splurge0.txt',
            'Results/AllResults_CRRA_2.0_R_1.01_Splurge0.txt',
        ],
    },
    4: {
        'name': 'hank_sam_jacobians',
        'description': 'HANK/SAM Jacobians and experiments (Section 5)',
        'script': 'HA-Fiscal-HANK-SAM.py',
        'cwd': 'FromPandemicCode',
        'expected_hours': 12,
        'outputs': [
            'Results/Jacobians/',  # Directory
        ],
    },
    5: {
        'name': 'policy_comparisons',
        'description': 'Comparing fiscal stimulus policies (Section 4)',
        'script': 'AggFiscalMAIN.py',
        'cwd': 'FromPandemicCode',
        'expected_hours': 12,
        'outputs': [
            'Figures/',
            'Tables/',
        ],
    },
}

def log(msg, level='INFO'):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {level:8} | {msg}")
    
    # Also write to master log
    with open(OUTPUT_DIR / 'master.log', 'a') as f:
        f.write(f"[{timestamp}] {level:8} | {msg}\n")

def run_step(step_num: int, version: str, quick: bool = False) -> dict:
    """Run a single step for a single version."""
    
    step = STEPS[step_num]
    config = VERSIONS[version]
    
    log(f"[{version}] Starting step {step_num}: {step['name']}")
    
    # Prepare command
    cwd = Path(config['base']) / 'Code/HA-Models' / step['cwd']
    script = step['script']
    args = step.get('args', [])
    
    cmd = [config['python'], script] + args
    
    # Set environment
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    
    if quick:
        env['HAFISCAL_QUICK_MODE'] = '1'
        env['HAFISCAL_AGENT_COUNT'] = '500'
        env['HAFISCAL_T_SIM'] = '200'
    
    # Log file
    log_file = LOGS_DIR / f"step{step_num}_{version.replace('.', '_')}.log"
    
    log(f"[{version}] Command: {' '.join(cmd)}")
    log(f"[{version}] CWD: {cwd}")
    log(f"[{version}] Log: {log_file}")
    
    start_time = time.time()
    
    try:
        with open(log_file, 'w') as f:
            f.write(f"Step {step_num}: {step['name']}\n")
            f.write(f"Version: {version}\n")
            f.write(f"Started: {datetime.now().isoformat()}\n")
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write(f"CWD: {cwd}\n")
            f.write("=" * 60 + "\n\n")
            f.flush()
            
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdout=f,
                stderr=subprocess.STDOUT,
            )
            
            proc.wait()
            
            elapsed = time.time() - start_time
            
            f.write(f"\n\n{'='*60}\n")
            f.write(f"Completed: {datetime.now().isoformat()}\n")
            f.write(f"Exit code: {proc.returncode}\n")
            f.write(f"Duration: {elapsed/3600:.2f} hours\n")
        
        return {
            'version': version,
            'step': step_num,
            'status': 'success' if proc.returncode == 0 else 'failed',
            'exit_code': proc.returncode,
            'elapsed_hours': elapsed / 3600,
            'log_file': str(log_file),
        }
        
    except Exception as e:
        return {
            'version': version,
            'step': step_num,
            'status': 'error',
            'error': str(e),
        }

def compare_outputs(step_num: int) -> dict:
    """Compare outputs between versions for a step."""
    
    step = STEPS[step_num]
    comparison = {
        'step': step_num,
        'name': step['name'],
        'files': [],
        'all_match': True,
    }
    
    v1, v2 = list(VERSIONS.keys())
    base1, base2 = VERSIONS[v1]['base'], VERSIONS[v2]['base']
    
    for output_path in step['outputs']:
        file1 = Path(base1) / 'Code/HA-Models' / output_path
        file2 = Path(base2) / 'Code/HA-Models' / output_path
        
        file_comp = {
            'path': output_path,
            'v1_exists': file1.exists(),
            'v2_exists': file2.exists(),
        }
        
        if file1.exists() and file2.exists():
            if file1.is_file() and file2.is_file():
                # Compare file contents
                content1 = file1.read_text()
                content2 = file2.read_text()
                
                if content1 == content2:
                    file_comp['status'] = 'identical'
                else:
                    file_comp['status'] = 'different'
                    file_comp['diff_preview'] = compare_text_files(content1, content2)
                    comparison['all_match'] = False
            elif file1.is_dir() and file2.is_dir():
                # Compare directories
                files1 = set(f.name for f in file1.iterdir())
                files2 = set(f.name for f in file2.iterdir())
                
                if files1 == files2:
                    file_comp['status'] = 'same_structure'
                else:
                    file_comp['status'] = 'different_structure'
                    file_comp['only_in_v1'] = list(files1 - files2)
                    file_comp['only_in_v2'] = list(files2 - files1)
                    comparison['all_match'] = False
        else:
            file_comp['status'] = 'missing'
            comparison['all_match'] = False
        
        comparison['files'].append(file_comp)
    
    return comparison

def compare_text_files(content1: str, content2: str, max_lines: int = 20) -> str:
    """Generate a preview of differences between two text files."""
    
    lines1 = content1.strip().split('\n')
    lines2 = content2.strip().split('\n')
    
    diffs = []
    for i, (l1, l2) in enumerate(zip(lines1, lines2)):
        if l1 != l2:
            diffs.append(f"Line {i+1}:")
            diffs.append(f"  v1: {l1[:100]}")
            diffs.append(f"  v2: {l2[:100]}")
            if len(diffs) > max_lines * 3:
                diffs.append("... (truncated)")
                break
    
    if len(lines1) != len(lines2):
        diffs.append(f"Line count: v1={len(lines1)}, v2={len(lines2)}")
    
    return '\n'.join(diffs)

def save_checkpoint(step_num: int, results: dict, comparison: dict):
    """Save checkpoint after completing a step."""
    
    checkpoint = {
        'step': step_num,
        'completed_at': datetime.now().isoformat(),
        'results': results,
        'comparison': comparison,
    }
    
    checkpoint_file = OUTPUT_DIR / f'checkpoint_step{step_num}.json'
    with open(checkpoint_file, 'w') as f:
        json.dump(checkpoint, f, indent=2)
    
    log(f"Checkpoint saved: {checkpoint_file}")

def main():
    parser = argparse.ArgumentParser(description='Full HAFiscal comparison')
    parser.add_argument('--step', type=int, help='Run only this step (1-5)')
    parser.add_argument('--quick', action='store_true', help='Quick mode with reduced parameters')
    parser.add_argument('--skip-step3', action='store_true', help='Skip step 3 (robustness)')
    args = parser.parse_args()
    
    log("=" * 70)
    log("HAFiscal FULL COMPARISON")
    log("=" * 70)
    log(f"Output directory: {OUTPUT_DIR}")
    log(f"Quick mode: {args.quick}")
    
    # Determine which steps to run
    if args.step:
        steps_to_run = [args.step]
    else:
        steps_to_run = [1, 2, 4, 5]  # Skip step 3 by default
        if not args.skip_step3:
            steps_to_run = [1, 2, 3, 4, 5]
    
    log(f"Steps to run: {steps_to_run}")
    
    # Run each step
    for step_num in steps_to_run:
        step = STEPS[step_num]
        
        log("")
        log("=" * 70)
        log(f"STEP {step_num}: {step['description']}")
        log(f"Expected duration: {step['expected_hours']} hours per version")
        log("=" * 70)
        
        results = {}
        
        # Run both versions in PARALLEL using threading
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        log("Starting both versions in parallel...")
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(run_step, step_num, version, args.quick): version
                for version in VERSIONS
            }
            
            for future in as_completed(futures):
                version = futures[future]
                result = future.result()
                results[version] = result
                
                if result['status'] == 'success':
                    log(f"[{version}] ✅ Completed in {result['elapsed_hours']:.2f} hours", 'SUCCESS')
                else:
                    log(f"[{version}] ❌ {result['status']}: {result.get('error', result.get('exit_code'))}", 'ERROR')
        
        # Compare outputs
        log("")
        log("Comparing outputs...")
        comparison = compare_outputs(step_num)
        
        if comparison['all_match']:
            log(f"✅ Step {step_num} outputs MATCH", 'SUCCESS')
        else:
            log(f"⚠️ Step {step_num} outputs DIFFER", 'WARNING')
            for file_comp in comparison['files']:
                if file_comp.get('status') != 'identical':
                    log(f"  {file_comp['path']}: {file_comp['status']}")
        
        # Save checkpoint
        save_checkpoint(step_num, results, comparison)
        
        # Stop if there's a failure
        if any(r['status'] != 'success' for r in results.values()):
            log("Stopping due to failure. Check logs for details.", 'ERROR')
            return 1
    
    # Final summary
    log("")
    log("=" * 70)
    log("FINAL SUMMARY")
    log("=" * 70)
    
    all_checkpoints = list(OUTPUT_DIR.glob('checkpoint_step*.json'))
    all_match = True
    
    for cp_file in sorted(all_checkpoints):
        with open(cp_file) as f:
            cp = json.load(f)
        
        step_num = cp['step']
        match_status = "✅ MATCH" if cp['comparison']['all_match'] else "⚠️ DIFFER"
        log(f"Step {step_num}: {match_status}")
        
        if not cp['comparison']['all_match']:
            all_match = False
    
    if all_match:
        log("")
        log("✅ ALL STEPS PRODUCE MATCHING OUTPUTS", 'SUCCESS')
        return 0
    else:
        log("")
        log("⚠️ SOME OUTPUTS DIFFER - review checkpoints for details", 'WARNING')
        return 1

if __name__ == '__main__':
    sys.exit(main())
