# filename: do_all_reduced.py
"""Reduced-scope runner of do_all.py for fast validation.

Runs the same five pipeline steps as do_all.py but at Reduced_Run
scope wherever the underlying scripts support it. Used to verify
that the pipeline is end-to-end runnable before committing to a
~72 h Baseline run.

Behavioral differences vs do_all.py:
  - Step 5 (policy comparison) runs on Reduced_Run (3 types × 7 β atoms)
    instead of Baseline (21 types).
  - Step 2 (discount-factor estimation) is configurable via
    HAFISCAL_EDTYPES=<ids> to run a subset of education types
    (default: all three; HAFISCAL_EDTYPES=1 for the HS cohort only).
  - Steps 1, 3, 4 are unchanged (already small or don't have a
    Reduced_Run equivalent).

Expected wall time on a 16-core laptop: ~2 h total.

Usage:
    cd Code/HA-Models
    python do_all_reduced.py
"""

from builtins import exec
import sys
import os
from time import time

try:
    from hafiscal_progress import profiler, start_step, complete_step, substep, progress
    PROFILING_ENABLED = True
except ImportError:
    PROFILING_ENABLED = False
    def start_step(*args, **kwargs): pass
    def complete_step(*args, **kwargs): pass
    def substep(*args, **kwargs): pass
    def progress(*args, **kwargs): pass
    class DummyProfiler:
        def sample_memory(self, *args): pass
    profiler = DummyProfiler()

# Control panel (same flags as do_all.py; step 3 opt-in)
run_step_1 = True
run_step_2 = True
run_step_3 = os.environ.get('HAFISCAL_RUN_STEP_3', 'false').lower() in ('true', '1', 'yes')
run_step_4 = True
run_step_5 = True

total_steps = sum([run_step_1, run_step_2, run_step_3, run_step_4, run_step_5])
current_step_num = 0

def next_step():
    global current_step_num
    current_step_num += 1
    return current_step_num


# ---------------------------------------------------------------------
# Step 1: Splurge-factor estimation
# (no Reduced_Run equivalent; runs as in do_all.py)
# ---------------------------------------------------------------------
if run_step_1:
    step_num = next_step()
    start_step(step_num, "Estimating splurge factor (Section 3.1)", total_steps)
    substep("Running Estimation_BetaNablaSplurge.py", expected_duration_min=30)
    profiler.sample_memory("step1_start")

    print('Step 1: Estimating the splurge factor\n')
    t0 = time()
    os.chdir('Target_AggMPCX_LiquWealth')
    os.system("python Estimation_BetaNablaSplurge.py")
    os.chdir('../')
    progress(f"Splurge estimation completed in {(time()-t0)/60:.1f} minutes")

    profiler.sample_memory("step1_end")
    complete_step(step_num)
    print('Concluded Step 1. \n')


# ---------------------------------------------------------------------
# Step 2: discount-factor estimation
# Runs EstimAggFiscalMAIN.py. Honors HAFISCAL_EDTYPES to restrict
# education types (e.g. '1' for HS only). Does not run the table/figure
# generators because they assume all three types are estimated.
# ---------------------------------------------------------------------
if run_step_2:
    step_num = next_step()
    start_step(step_num, "Estimating discount factor distributions (Section 3.3.3) [reduced]",
               total_steps)
    ed = os.environ.get('HAFISCAL_EDTYPES', '0,1,2')
    substep(f"Running EstimAggFiscalMAIN.py (edtypes={ed})",
            expected_duration_min=60 if ed == '1' else 240)
    profiler.sample_memory("step2_start")

    print(f'Step 2 (reduced): Estimating discount factor distributions for edtypes {ed}\n')
    t0 = time()
    os.chdir('FromPandemicCode')
    os.system("python EstimAggFiscalMAIN.py")
    os.chdir('../')
    progress(f"EstimAggFiscalMAIN.py completed in {(time()-t0)/60:.1f} minutes")

    profiler.sample_memory("step2_end")
    complete_step(step_num)
    print('Concluded Step 2 (reduced). \n')


# ---------------------------------------------------------------------
# Step 3: Splurge=0 robustness (opt-in; same as do_all.py)
# ---------------------------------------------------------------------
if run_step_3:
    step_num = next_step()
    start_step(step_num, "Robustness: Splurge=0 estimation (Online Appendix)", total_steps)
    substep("Running EstimAggFiscalMAIN.py with Splurge=0", expected_duration_min=2880)
    profiler.sample_memory("step3_start")

    print('Step 3: Robustness results\n')
    os.chdir('FromPandemicCode')
    t0 = time()
    args = ['1.01', '2.0', '0.7', '0.5', '0']
    os.system("python EstimAggFiscalMAIN.py " + " ".join(args))
    progress(f"Robustness estimation completed in {(time()-t0)/60:.1f} minutes")
    os.chdir('../')

    profiler.sample_memory("step3_end")
    complete_step(step_num)
    print('Concluded Step 3.\n\n')


# ---------------------------------------------------------------------
# Step 4: HANK/SAM (no Reduced_Run equivalent; runs as in do_all.py)
# ---------------------------------------------------------------------
if run_step_4:
    step_num = next_step()
    start_step(step_num, "HANK/SAM Model - Jacobians and experiments (Section 5)", total_steps)
    profiler.sample_memory("step4_start")

    print('Step 4: HANK Robustness Check\n')
    os.chdir('FromPandemicCode')

    substep("Computing household Jacobians (HA-Fiscal-HANK-SAM.py)", expected_duration_min=720)
    t0 = time()
    os.system("python HA-Fiscal-HANK-SAM.py")
    progress(f"Jacobian computation completed in {(time()-t0)/60:.1f} minutes")

    substep("Running HANK-SAM policy experiments", expected_duration_min=60)
    t0 = time()
    os.system("python HA-Fiscal-HANK-SAM-to-python.py")
    progress(f"HANK-SAM experiments completed in {(time()-t0)/60:.1f} minutes")

    os.chdir('../')
    profiler.sample_memory("step4_end")
    complete_step(step_num)
    print('Concluded Step 4. \n')


# ---------------------------------------------------------------------
# Step 5 (reduced): policy comparison at Reduced_Run scope
#   5a. TM multipliers:  AggFiscalMAIN_reduced.py   (no --baseline flag)
#   5b. MC welfare-6:    run_hybrid_welfare6.py     (defaults to Reduced_Run)
# Outputs land at Tables/Reduced_Run/ rather than Tables/Baseline/
# ---------------------------------------------------------------------
if run_step_5:
    step_num = next_step()
    start_step(step_num, "Comparing fiscal stimulus policies (Section 4) [reduced]",
               total_steps)
    profiler.sample_memory("step5_start")

    print('Step 5 (reduced): Comparing policies (TM multipliers + MC welfare-6)\n')
    t0 = time()
    os.chdir('FromPandemicCode')

    substep("Running AggFiscalMAIN_reduced.py (TM multipliers, Reduced_Run)",
            expected_duration_min=10)
    t_tm = time()
    rc_tm = os.system("python AggFiscalMAIN_reduced.py")
    progress(f"Step 5a (TM multipliers) completed in {(time()-t_tm)/60:.1f} minutes (rc={rc_tm})")

    substep("Running run_hybrid_welfare6.py (MC welfare-6, Reduced_Run)",
            expected_duration_min=10)
    t_mc = time()
    rc_mc = os.system("python run_hybrid_welfare6.py")
    progress(f"Step 5b (MC welfare-6) completed in {(time()-t_mc)/60:.1f} minutes (rc={rc_mc})")

    progress(f"Step 5 (reduced) total: {(time()-t0)/60:.1f} minutes")
    os.chdir('../')
    profiler.sample_memory("step5_end")
    complete_step(step_num)
    print('Concluded Step 5 (reduced). \n')
