# filename: do_all.py

# Import matplotlib configuration before any other imports
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from matplotlib_config import show_plot

# Import the exec function
from builtins import exec


#%% This script is a reduced version of do_all.py
# It only executes half of Step 4 and Step 5 of do_all.py 
# It thus skips the estimation of the splurge and discount factors (and robustness estimations)
# For step 4, we take the Jacobians computed by HA-Fiscal-HANK-SAM.py as given
# and only conduct the policy experiements. Execution only takes seconds.
# The whole code should take roughly one hour to execute (using a laptop computer)
# For step 5, we consider a simpler setup and reduce the number of discount factors per education group to 1
# Furthermore, we only run N=100 rather than 10000 agents.
# Finally, the Aggregate Demand solution is run calculated with fewer iterations (reducing accuracy)
# The code creates IRF for the simulations in FromPandemicCode\Figures\Reduced_Run
# and a table of the Multipliers in  FromPandemicCode\Tables\Reduced_Run


print('Step 4: HANK Robustness Check\n')
os.chdir('FromPandemicCode')
script_path = 'HA-Fiscal-HANK-SAM-to-python.py'
os.system("python " + script_path)  
os.chdir('../')
print('Concluded Step 4. \n')


print('Step 5: Comparing policies\n')
# Change to the FromPandemicCode directory first
original_dir = os.getcwd()
os.chdir('FromPandemicCode')
script_path = "AggFiscalMAIN_reduced.py"
exec(open(script_path).read())
# Change back to original directory
os.chdir(original_dir)
print('Concluded Step 5. \n')


