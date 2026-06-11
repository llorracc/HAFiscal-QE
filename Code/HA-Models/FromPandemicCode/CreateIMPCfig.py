import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from matplotlib_config import show_plot

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
from HARK.utilities import make_figs

cwd             = os.getcwd()
folders         = cwd.split(os.path.sep)
top_most_folder = folders[-1]
if top_most_folder == 'FromPandemicCode':
    Abs_Path = cwd
    figs_dir = '.'  # Save figures in FromPandemicCode directory
    res_dir = '../Results'
else:
    Abs_Path = cwd + '/Code/HA-Models/FromPandemicCode'
    figs_dir = Abs_Path  # Save figures in FromPandemicCode directory
    res_dir = 'Results'
sys.path.append(Abs_Path)

plt.style.use('classic')
# ============================================================================
# HELPER FUNCTION: Save figure in multiple formats (PNG, JPG, SVG)
# ============================================================================
def save_all_formats(basename, target_dir='.'):
    """
    Save the current matplotlib figure in PNG, JPG, and SVG formats.
    Call this immediately after make_figs() which saves the PDF.
    
    Parameters:
    -----------
    basename : str
        Base filename without extension (e.g., 'IMPCs_both')
    target_dir : str
        Directory where files should be saved
    """
    filepath = os.path.join(target_dir, basename)
    
    # Save in PNG format (high resolution for web)
    plt.savefig(f'{filepath}.png', format='png', dpi=300, bbox_inches='tight')
    
    # Save in JPG format (compressed for web)
    # Note: matplotlib uses PIL backend for JPG, quality is set via pil_kwargs
    plt.savefig(f'{filepath}.jpg', format='jpg', dpi=300, bbox_inches='tight', pil_kwargs={'quality': 95})
    
    # Save in SVG format (vector graphics for web)
    plt.savefig(f'{filepath}.svg', format='svg', bbox_inches='tight')
    
    print(f"   Saved: {basename}.{{png,jpg,svg}}")

# ============================================================================


plotToMake = [0,1,2]
# 0 = Data + model with Splurge = 0
# 1 = Data + model with Splurge = estimated
# 2 = Data + both models

# Define the agg MPCx targets from Fagereng et al. Figure 2; first element is same-year response, 2nd element, t+1 response etcc
Agg_MPCX_data = np.array([0.5056845, 0.1759051, 0.1035106, 0.0444222, 0.0336616])

resFileSplEst = open(res_dir+'/AllResults_CRRA_2.0_R_1.01.txt', 'r')  

for line in resFileSplEst:
    if "IMPCs" in line:
        theIMPCstr = line[line.find('[')+1:line.find(']')].split(', ')
        IMPCsSplEst = []
        for ii in range(0,len(theIMPCstr)):
            IMPCsSplEst.append(float(theIMPCstr[ii]))

resFileSplZero = open(res_dir+'/AllResults_CRRA_2.0_R_1.01_Splurge0.txt', 'r')

for line in resFileSplZero:
    if "IMPCs" in line:
        theIMPCstr = line[line.find('[')+1:line.find(']')].split(', ')
        IMPCsSplZero = []
        for ii in range(0,len(theIMPCstr)):
            IMPCsSplZero.append(float(theIMPCstr[ii]))

for thePlots in plotToMake:
    fig = plt.figure(figsize=(7,6))
    xAxis = np.arange(0,5)
    
    theLegend = []
    if thePlots==0 or thePlots==2:
        plt.plot(xAxis, IMPCsSplZero, 'r:', linewidth=2)
        theLegend.append('Model w/splurge=0')
    if thePlots == 1 or thePlots==2:
        plt.plot(xAxis, IMPCsSplEst, 'b-', linewidth=2)
        theLegend.append('Model w/estimated splurge')
    
    plt.scatter(xAxis, Agg_MPCX_data, c='black', marker='o')
    theLegend.append('Fagereng, Holm and Natvik (2021)')
    plt.xticks(np.arange(min(xAxis), max(xAxis)+1, 1.0))
    plt.xlabel('Year')
    plt.ylabel('% of lottery win spent')
    plt.legend(theLegend, loc='upper right', fontsize=12)
    plt.grid(True)

    if thePlots==0:
        make_figs('IMPCs_wSplZero', True , False, target_dir=figs_dir)
        save_all_formats('IMPCs_wSplZero', target_dir=figs_dir)
    elif thePlots==1:
        make_figs('IMPCs_wSplEstimated', True , False, target_dir=figs_dir)
        save_all_formats('IMPCs_wSplEstimated', target_dir=figs_dir)
    else:
        make_figs('IMPCs_both', True , False, target_dir=figs_dir)
        save_all_formats('IMPCs_both', target_dir=figs_dir)

show_plot()