# filename: do_all.py

# Import the exec function
from builtins import exec
import sys 
import os

# Control panel:
run_step_1 = True
run_step_2 = True
# This step produces robustness results in the Online appendix
# Check environment variable, default to False if not set
run_step_3 = os.environ.get('HAFISCAL_RUN_STEP_3', 'false').lower() in ('true', '1', 'yes')
run_step_4 = True
run_step_5 = True 

#%%
# Step 1: Estimation of the splurge factor: 
# This file replicates the results from section 3.1 in the paper, creates Figure 1 (in Target_AggMPCX_LiquWealth/Figures),
# and saves results in Target_AggMPCX_LiquWealth as .txt files to be used in the later steps.
if run_step_1:
    print('Step 1: Estimating the splurge factor\n')
    os.chdir('Target_AggMPCX_LiquWealth')
    script_path = "Estimation_BetaNablaSplurge.py"
    os.system("python " + script_path)
    os.chdir('../')
    print('Concluded Step 1.\n\n')


#%%
# Step 2: Baseline results. Estimate the discount factor distributions and plot figure 2. This replicates results from section 3.3.3 in the paper. 
if run_step_2:
    print('Step 2: Estimating discount factor distributions (this takes a while!)\n')
    os.chdir('FromPandemicCode')
    os.system("python " + "EstimAggFiscalMAIN.py")
    os.system("python " + "CreateLPfig.py")
    os.system("python " + "CreateIMPCfig.py")
    os.chdir('../')
    print('Concluded Step 2.\n\n')


#%%
# Step 3: Robustness results. Estimate discount factor distributions with Splurge = 0. The results for Splurge = 0 are in the Online Appendix.
if run_step_3:
    print('Step 3: Robustness results (note: this repeats step 2)\n')  
    os.chdir('FromPandemicCode')
    # Order of input arguments: interest rate, risk aversion, replacement rate w/benefits, replacement rate w/o benefits, Splurge   
    # For robustness, keep basline parameters, but set splurge to 0

    args = ['1.01', '2.0', '0.7', '0.5', '0']
    cmd = "python EstimAggFiscalMAIN.py " + " ".join(args)
    os.system(cmd)
    os.chdir('../')
    print('Concluded Step 3.\n\n')


#%%
# Step 4: Solves the HANK and SAM model in Section 5 and creates Figure 5.
if run_step_4:
    print('Step 4: HANK Robustness Check\n')
    os.chdir('FromPandemicCode')

    # compute household Jacobians
    script_path = 'HA-Fiscal-HANK-SAM.py'
    os.system("python " + script_path) 

    # run HANK-SAM experiments
    script_path = 'HA-Fiscal-HANK-SAM-to-python.py'
    os.system("python " + script_path)  
    os.chdir('../')
    print('Concluded Step 4. \n')


#%%
# Step 5: Comparing fiscal stimulus policies: This file replicates the results from section 4 in the paper, 
# creates Figure 4 (located in FromPandemicCode/Figures), creates tables (located in FromPandemicCode/Tables)
# and creates robustness results for the case where the Splurge = 0 (for the Online appendix). 
# This also creates Figure 6 which uses results from Step 4 (hence, the order is different than in the presentation in the paper). 
if run_step_5:
    print('Step 5: Comparing policies\n')
    os.chdir('FromPandemicCode')
    os.system("python " + "AggFiscalMAIN.py")
    os.chdir('../')
    print('Concluded Step 5. \n')
