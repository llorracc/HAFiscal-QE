# filename: reproduce_min.py
# Minimal reproduction script - runs Step 4 (partial) and Step 5 (reduced)

# Import matplotlib configuration before any other imports
import os
import sys
from time import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from matplotlib_config import show_plot

# Import the exec function
from builtins import exec

# Import progress tracking
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

#%% This script is a reduced version of do_all.py
# It only executes half of Step 4 and Step 5 of do_all.py 
# It thus skips the estimation of the splurge and discount factors (and robustness estimations)
# For step 4, we take the Jacobians computed by HA-Fiscal-HANK-SAM.py as given
# and only conduct the policy experiements. Execution only takes seconds.
# The whole code should take roughly one hour to execute (using a laptop computer)
# For step 5, we consider a simpler setup and reduce the number of discount factors per education group to 1
# Step 5 uses Parametrization='Reduced_Run' (1 beta per education, N=5000 agents).
# For a crash-only path with N=100, run: python AggFiscalMAIN_reduced.py --smoke-test
# Finally, the Aggregate Demand solution is run calculated with fewer iterations (reducing accuracy)
# Step 5 TM path: AggFiscalMAIN_reduced.py sets tm_neutral_measure=True so the 1D TM
# uses Harmenberg's neutral measure Q for p-linear aggregation:
#   E_P[p * f(m)] = E_P[p] * E_Q[f(m)]   — BST ApndxHarKmenberg Theorem 1
# See history/archive/20260402-reduced-run-harmenberg-output-type-map.md (Type A/B classification).
# Optional: pass --fast-reproduce to that script for tm_mCount=40 (validate multipliers first).
# The code creates IRF for the simulations in FromPandemicCode\Figures\Reduced_Run
# and a table of the Multipliers in  FromPandemicCode\Tables\Reduced_Run

total_steps = 2

# Step 4 (partial): HANK-SAM experiments only (Jacobians pre-computed)
start_step(4, "HANK-SAM Policy Experiments (using pre-computed Jacobians)", total_steps)
substep("Running HA-Fiscal-HANK-SAM-to-python.py", expected_duration_min=5)
profiler.sample_memory("step4_start")

print('Step 4: HANK Robustness Check\n')
t0 = time()
os.chdir('FromPandemicCode')
script_path = 'HA-Fiscal-HANK-SAM-to-python.py'
os.system("python " + script_path)  
progress(f"HANK-SAM experiments completed in {(time()-t0)/60:.1f} minutes")
os.chdir('../')

profiler.sample_memory("step4_end")
complete_step(4)
print('Concluded Step 4. \n')


# Step 5 (reduced): Policy comparison with reduced agents and iterations
start_step(5, "Comparing Policies (Reduced Run - 1 beta per education, N=5000)", total_steps)
substep("Running AggFiscalMAIN_reduced.py", expected_duration_min=60)
profiler.sample_memory("step5_start")

print('Step 5: Comparing policies\n')
# Change to the FromPandemicCode directory first
original_dir = os.getcwd()
os.chdir('FromPandemicCode')
t0 = time()
script_path = "AggFiscalMAIN_reduced.py"
exec(open(script_path).read())
progress(f"Policy comparison (reduced) completed in {(time()-t0)/60:.1f} minutes")
# Change back to original directory
os.chdir(original_dir)

profiler.sample_memory("step5_end")
complete_step(5)
print('Concluded Step 5. \n')
