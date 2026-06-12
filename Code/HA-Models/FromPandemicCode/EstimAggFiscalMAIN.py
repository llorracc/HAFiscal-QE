# %%
'''
This is the main script for estimating the discount factor distributions.

For each education group (dropout, highschool, college) it runs Nelder-Mead
over (β, ∇) — GICx handling governed by HAFISCAL_GICX_MODE (BUG-039) — to
match the SCF 2004 liquid-wealth calibration targets, then writes the
estimates to Results/DiscFacEstim_CRRA_*_R_*.txt. Executed top-to-bottom as
a script (do_all.py Step 2 runs `python EstimAggFiscalMAIN.py`); control
flags select which education groups / analyses run. Estimation runs under
the canonical solution-approach defaults set in EstimParameters.py, and the
resulting calibration is regime-matched to those flags (BUG-051/BUG-053
matched-pair discipline).
'''
import time
import sys 
import os 
from importlib import reload 
import numpy as np
import matplotlib.pyplot as plt
from copy import deepcopy
from collections import namedtuple 
import pickle
import random 
from HARK.distributions import DiscreteDistribution, Uniform
from HARK import multi_thread_commands, multi_thread_commands_fake
from HARK.utilities import get_percentiles, get_lorenz_shares
from HARK.estimation import minimize_nelder_mead

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from matplotlib_config import show_plot
# Module-level: HAFISCAL_INTERPRETATION suffix helper. Used by both the
# estimation block (df_resFileStr write) and the calcAllResults block
# (df_resFileStr + ar_resFileStr reads/writes). Importing here ensures
# both paths see it regardless of which top-level switches are active.
from _interpretation import interp_suffix as _interp_suffix

# Import progress tracking
try:
    from hafiscal_progress import profiler, substep, progress, profile_function, track_loop
    PROFILING_ENABLED = True
except ImportError:
    PROFILING_ENABLED = False
    def substep(*args, **kwargs): pass
    def progress(*args, **kwargs): pass
    def profile_function(*args, **kwargs):
        from contextlib import contextmanager
        @contextmanager
        def dummy_ctx(*a, **kw):
            yield
        return dummy_ctx()
    def track_loop(*args, **kwargs):
        class DummyLoop:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def iteration(self, *a, **kw): pass
        return DummyLoop()
    class DummyProfiler:
        def sample_memory(self, *args): pass
        def record_time(self, *args, **kwargs): pass
        def log_convergence(self, *args, **kwargs): pass
    profiler = DummyProfiler()

# Track Nelder-Mead iteration count globally
_nelder_mead_iter_count = [0, 0, 0]  # For each education type

cwd             = os.getcwd()
folders         = cwd.split(os.path.sep)
top_most_folder = folders[-1]
if top_most_folder == 'FromPandemicCode':
    Abs_Path = cwd
    figs_dir = '../../../Figures'
    res_dir = '../Results'
else:
    Abs_Path = cwd + '/Code/HA-Models/FromPandemicCode'
    figs_dir = '../../Figures'
    res_dir = 'Results'
    os.chdir(Abs_Path)
sys.path.append(Abs_Path)

import EstimParameters as ep
reload(ep)  # Force reload in case the code is running from commandline for different values 

from EstimParameters import init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,\
     DiscFacCount, CRRA, Splurge, IncUnemp, IncUnempNoBenefits, AgentCountTotal, base_dict, \
     UBspell_normal, data_LorenzPts, data_LorenzPtsAll, data_avgLWPI, data_LWoPI, \
     data_medianLWPI, data_EducShares, data_WealthShares, Rfree_base, \
     GICmaxBetas, gic_capped_beta, theGICfactor, minBeta
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
mystr = lambda x : '{:.2f}'.format(x)
mystr4 = lambda x : '{:.4f}'.format(x)

print('Parameters: R = '+str(round(Rfree_base[0],3))+', CRRA = '+str(round(CRRA,2))
      +', IncUnemp = '+str(round(IncUnemp,2))+', IncUnempNoBenefits = '+str(round(IncUnempNoBenefits,2))
      +', Splurge = '+str(Splurge))


# CDC-MOD-BUG034 + ESC-MOD-BUG034: Step-2 wealth aggregation dispatched on
# agent.interpretation. Under CDC (default), state_now["aLvl"] IS already
# household-total assets per BUG-031 — use directly. Under ESC, aLvl is
# optimizer-per-capita, so multiply by (1-ς) to get household-total. The
# 11 (1-ς)-factored aggregation sites in this module call _aLvl_for or
# _aNrm_for instead of branching inline. CDC default via getattr ensures
# bit-identical CDC behavior even for agents constructed without the
# `interpretation` attribute set.
def _aLvl_for(ThisType):
    """Return aLvl scaled per ThisType.interpretation. CDC default."""
    if getattr(ThisType, 'interpretation', 'CDC') == 'CDC':
        return ThisType.state_now["aLvl"]
    return (1 - ThisType.Splurge) * ThisType.state_now["aLvl"]


def _aNrm_for(ThisType):
    """Return aNrm scaled per ThisType.interpretation. CDC default."""
    if getattr(ThisType, 'interpretation', 'CDC') == 'CDC':
        return ThisType.state_now["aNrm"]
    return (1 - ThisType.Splurge) * ThisType.state_now["aNrm"]


# %%
# -----------------------------------------------------------------------------
def calc_estim_stats(Agents):
    '''
    Calculate the average LW/PI-ratio and total LW / total PI for each education
    type. Also calculate the 20th, 40th, 60th, and 80th percentile points of the
    Lorenz curve for (liquid) wealth for all agents. 
    Assumption: Agents is organized by EducType and there are DiscFacCount
    AgentTypes of each EducType. 
    
    Parameters
    ----------
    Agents : [AgentType]
        List of AgentTypes in the economy.
        
    Returns
    -------
    Stats : namedtuple("avgLWPI", "LWoPI", "LorenzPts")
    avgLWPI : [float] 
        The weighted average of LW/PI-ratio for each education type.
    LWoPI : [float]
        Total liquid wealth / total permanent income for each education type. 
    LorenzPts : [float]
        The 20th, 40th, 60th, and 80th percentile points of the Lorenz curve for 
        (liquid) wealth.
    '''

    # CDC-MOD-BUG034 + ESC-MOD-BUG034: dispatched via _aLvl_for helper at top
    # of module. CDC: state_now["aLvl"] is household-total per BUG-031; use
    # directly. ESC: aLvl is optimizer-per-capita; multiply by (1-ς).
    aLvlAll = np.concatenate([_aLvl_for(ThisType) for ThisType in Agents])
    numAgents = 0
    for ThisType in Agents:
        numAgents += ThisType.AgentCount
    weights = np.ones(numAgents) / numAgents      # equal weights (permanent design — no agent weighting was ever added)

    # Lorenz points:
    LorenzPts = 100*get_lorenz_shares(aLvlAll, weights=weights, percentiles = [0.2, 0.4, 0.6, 0.8] )

    avgLWPI = [0]*num_types
    LWoPI = [0]*num_types
    medianLWPI = [0]*num_types
    for e in range(num_types):
        aNrmAll_byEd = []
        # CDC-MOD-BUG034 + ESC-MOD-BUG034: dispatched via _aNrm_for helper.
        aNrmAll_byEd = np.concatenate([_aNrm_for(ThisType) for ThisType in \
                          Agents[e*DiscFacCount:(e+1)*DiscFacCount]])
        weights = np.ones(len(aNrmAll_byEd))/len(aNrmAll_byEd)
        avgLWPI[e] = np.dot(aNrmAll_byEd, weights) * 100

        aLvlAll_byEd = []
        # CDC-MOD-BUG034 + ESC-MOD-BUG034: dispatched via _aLvl_for helper.
        aLvlAll_byEd = np.concatenate([_aLvl_for(ThisType) for ThisType in \
                          Agents[e*DiscFacCount:(e+1)*DiscFacCount]])
        pLvlAll_byEd = []
        pLvlAll_byEd = np.concatenate([ThisType.state_now['pLvl'] for ThisType in \
                          Agents[e*DiscFacCount:(e+1)*DiscFacCount]])
        LWoPI[e] = np.dot(aLvlAll_byEd, weights) / np.dot(pLvlAll_byEd, weights) * 100

        medianLWPI[e] = 100*get_percentiles(aNrmAll_byEd,weights=weights,percentiles=[0.5])

    Stats = namedtuple("Stats", ["avgLWPI", "LWoPI", "medianLWPI", "LorenzPts"])

    return Stats(avgLWPI, LWoPI, medianLWPI, LorenzPts) 
# -----------------------------------------------------------------------------
def calc_wealth_share_by_ed(Agents):
    '''
    Calculate the share of total wealth held by each education type. 
    Assumption: Agents is organized by EducType and there are DiscFacCount
    AgentTypes of each EducType. 
    
    Parameters
    ----------
    Agents : [AgentType]
        List of all AgentTypes in the economy. They are assumed to differ in 
        their EducType attribute.

    Returns
    -------
    WealthShares : np.array(float)
        The share of total liquid wealth held by each education type. 
    '''
    # CDC-MOD-BUG034 + ESC-MOD-BUG034: dispatched via _aLvl_for helper.
    aLvlAll = np.concatenate([_aLvl_for(ThisType) for ThisType in Agents])
    totLiqWealth = np.sum(aLvlAll)

    WealthShares = [0]*num_types
    for e in range(num_types):
        aLvlAll_byEd = []
        # CDC-MOD-BUG034 + ESC-MOD-BUG034: dispatched via _aLvl_for helper.
        aLvlAll_byEd = np.concatenate([_aLvl_for(ThisType) for ThisType in \
                                       Agents[e*DiscFacCount:(e+1)*DiscFacCount]])
        WealthShares[e] = np.sum(aLvlAll_byEd)/totLiqWealth * 100
    
    return np.array(WealthShares)
# -----------------------------------------------------------------------------
def calc_lorenz_pts(Agents):
    '''
    Calculate the 20th, 40th, 60th, and 80th percentile points of the
    Lorenz curve for (liquid) wealth for the given set of Agents. 

    Parameters
    ----------
    Agents : [AgentType]
        List of AgentTypes.

    Returns
    -------
    LorenzPts : [float]
        The 20th, 40th, 60th, and 80th percentile points of the Lorenz curve for 
        (liquid) wealth.
    '''
    # CDC-MOD-BUG034 + ESC-MOD-BUG034: dispatched via _aLvl_for helper.
    aLvlAll = np.concatenate([_aLvl_for(ThisType) for ThisType in Agents])
    numAgents = 0
    for ThisType in Agents:
        numAgents += ThisType.AgentCount
    weights = np.ones(numAgents) / numAgents      # equal weights (permanent design — no agent weighting was ever added)

    # Lorenz points:
    LorenzPts = 100*get_lorenz_shares(aLvlAll, weights=weights, percentiles = [0.2, 0.4, 0.6, 0.8] )

    return LorenzPts
# -----------------------------------------------------------------------------
def calc_mpc_by_ed_simple(Agents):
    '''
    Calculate the average MPC for each education type. 
    Assumption: Agents is organized by EducType and there are DiscFacCount
    AgentTypes of each EducType. 
    
    Parameters
    ----------
    Agents : [AgentType]
        List of all AgentTypes in the economy. They are assumed to differ in 
        their EducType attribute.

    Returns
    -------
    MPCs : namedtuple("MPCsQ", "MPCsA")    
    MPCsQ : [float]
        The average MPC for each education type - Quarterly, ignores splurge.
    MPCsA : [float]
        The average MPC for each education type - Annualized, taking splurge into account. 
        (Only splurge in the first quarter.)
    '''
    MPCsQ = [0]*(num_types+1)   # MPC for each eduation type + for whole population
    MPCsA = [0]*(num_types+1)   # Annual MPCs with splurge (each ed. type + population)
    for e in range(num_types):
        MPC_byEd_Q = []
        MPC_byEd_Q = np.concatenate([ThisType.MPCNow for ThisType in \
                                       Agents[e*DiscFacCount:(e+1)*DiscFacCount]])

        MPC_byEd_A = Splurge + (1-Splurge)*MPC_byEd_Q
        for qq in range(3):
            MPC_byEd_A += (1-MPC_byEd_A)*MPC_byEd_Q
        
        MPCsQ[e] = np.mean(MPC_byEd_Q)
        MPCsA[e] = np.mean(MPC_byEd_A)
        
    MPC_all_Q = np.concatenate([ThisType.MPCNow for ThisType in Agents])
    MPC_all_A = Splurge + (1-Splurge)*MPC_all_Q
    for qq in range(3):
        MPC_all_A += (1-MPC_all_A)*MPC_all_Q
    
    MPCsQ[e+1] = np.mean(MPC_all_Q)
    MPCsA[e+1] = np.mean(MPC_all_A)

    MPCs = namedtuple("MPCs", ["MPCsQ", "MPCsA"])
 
    return MPCs(MPCsQ,MPCsA)
 
# -----------------------------------------------------------------------------
def calc_mpc_by_wealth_q_simple(Agents):
    '''
    Calculate the average annual MPC for each wealth quartile. 
    Assumption: Agents is organized by EducType and there are DiscFacCount
    AgentTypes of each EducType. 
    
    Parameters
    ----------
    Agents : [AgentType]
        List of all AgentTypes in the economy. They are assumed to differ in 
        their EducType attribute.

    Returns
    -------
    MPCs : namedtuple("MPCsQ", "MPCsA", "MPCsFYL")    
    MPCsQ : [float]
        The average MPC for each wealth quartile - Quarterly, ignores splurge.
    MPCsA : [float]
        The average MPC for each wealth quartile - Annualized, taking splurge into account. 
        (Only splurge in the first quarter.)
    MPCsFYL : [float]
        The average MPC for each wealth quartile - MPC in the year of a lottery win, 
        taking the splurge into account. For different individuals the lottery win happens
        in different quarters.
    '''
    # CDC-MOD-BUG034 + ESC-MOD-BUG034: dispatched via _aLvl_for helper.
    WealthNow = np.concatenate([_aLvl_for(ThisType) for ThisType in Agents])

    # Get wealth quartile cutoffs and distribute them to each consumer type
    quartile_cuts = get_percentiles(WealthNow,percentiles=[0.25,0.50,0.75])
    WealthQsAll = np.array([])
    for ThisType in Agents:
        WealthQ = np.zeros(ThisType.AgentCount,dtype=int)
        for n in range(3):
            # CDC-MOD-BUG034 + ESC-MOD-BUG034: dispatched via _aLvl_for helper.
            WealthQ[_aLvl_for(ThisType) > quartile_cuts[n]] += 1
        ThisType.WealthQ = WealthQ
        WealthQsAll = np.concatenate([WealthQsAll, WealthQ])

    MPC_agents_Q = np.concatenate([ThisType.MPCNow for ThisType in Agents])
    # Annual MPC: first Q includes Splurge, other three Qs do not
    MPC_agents_A = Splurge+(1-Splurge)*MPC_agents_Q
    for qq in range(3):
        MPC_agents_A += (1-MPC_agents_A)*MPC_agents_Q

    # Vector of how many quarters of spending each agent has after a lottery win
    SpendAfterLW_all = np.array([])
    for ThisType in Agents: 
        SpendQs = np.random.randint(0,4,ThisType.AgentCount)
        ThisType.SpendQs = SpendQs
        SpendAfterLW_all = np.concatenate([SpendAfterLW_all, SpendQs])
    
    MPC_agents_FYL = Splurge + (1-Splurge)*MPC_agents_Q
    for qq in range(1,4):
        MPC_agents_FYL[SpendAfterLW_all >= qq] += (1-MPC_agents_FYL[SpendAfterLW_all >= qq])*MPC_agents_Q[SpendAfterLW_all >= qq]
    
    MPCsQ = [0]*(4+1)       # MPC for each quartile + for whole population
    MPCsA = [0]*(4+1)       # Annual MPCs with splurge (each quartile + population)
    MPCsFYL = [0]*(4+1)     # First-year MPC in the year of a lottery win that occurs in a random quarter
    # Mean MPCs for each of the 4 quartiles of wealth + all agents         
    for qq in range(4):
        MPCsQ[qq] = np.mean(MPC_agents_Q[WealthQsAll==qq])
        MPCsA[qq] = np.mean(MPC_agents_A[WealthQsAll==qq])
        MPCsFYL[qq] = np.mean(MPC_agents_FYL[WealthQsAll==qq])
    MPCsQ[4] = np.mean(MPC_agents_Q)
    MPCsA[4] = np.mean(MPC_agents_A)
    MPCsFYL[4] = np.mean(MPC_agents_FYL)
    
    MPCs = namedtuple("MPCs", ["MPCsQ", "MPCsA", "MPCsFYL"])
 
    return MPCs(MPCsQ,MPCsA,MPCsFYL)    
 
# -----------------------------------------------------------------------------
def check_disc_fac_distribution(beta, nabla, GICfactor, educ_type, print_mode=False, print_file=False, filename='DefaultResultsFile.txt'):
    '''
    Calculate max and min discount factors in discrete approximation to uniform 
    distribution of discount factors. Also report if most patient agents satisfies 
    the growth impatience condition. 
    
    Parameters
    ----------
    beta : float
        Central value of the discount factor distribution for this education group.
    nabla : float
        Half the width of the discount factor distribution.
    GICfactor : float
        How close to the GIC-imposed upper bound the highest beta is allowed to be.
    educ_type : int 
        Denotes the education type (either 0, 1 or 2). 
    print_mode : boolean, optional
        If true, results are printed to the screen. The default is False.
    print_file : boolean, optional
        If true, statistics are appended to the file filename. The default is False. 
    filename : str
        Filename for printing calculated statistics. The default is DefaultResultsFile.txt.
    
    Returns
    -------
    dfCheck : namedtuple("betaMin", "betaMax", "GICsatisfied")    
    betaMin : float
        Minimum value in discrete approximation to discount factor distribution.
    betaMax : float
        Maximum value in discrete approximation to discount factor distribution.
    GICsatisfied : boolean
        True if betaMax satisfies the GIC for this education group. 
    '''
    DiscFacDstnBase = Uniform(beta-nabla, beta+nabla).discretize(DiscFacCount)
    betaMin = DiscFacDstnBase.atoms[0][0]
    betaMax = DiscFacDstnBase.atoms[0][DiscFacCount-1]
    GICsatisfied = (betaMax < gic_capped_beta(educ_type, GICfactor))

    DiscFacDstnActual = DiscFacDstnBase.atoms[0].copy()
    for thedf in range(DiscFacCount):
        if DiscFacDstnActual[thedf] > gic_capped_beta(educ_type, GICfactor):
            DiscFacDstnActual[thedf] = gic_capped_beta(educ_type, GICfactor)
        elif DiscFacDstnActual[thedf] < minBeta:
            DiscFacDstnActual[thedf] = minBeta

    if print_mode:
        print('Base approximation to beta distribution:\n'+str(np.round(DiscFacDstnBase.atoms[0],4))+'\n')
        print('Actual approximation to beta distribution:\n'+str(np.round(DiscFacDstnActual,4))+'\n')
        print('GIC satisfied = '+str(GICsatisfied)+'\tGICmaxBeta = '+str(round(GICmaxBetas[educ_type],4))+'\n')
        print('Imposed GIC consistent maximum beta = ' + str(round(gic_capped_beta(educ_type, GICfactor),5))+'\n\n')
        
    if print_file:
        with open(filename, 'a') as resFile: 
            resFile.write('\tBase approximation to beta distribution:\n\t'+str(np.round(DiscFacDstnBase.atoms[0],4))+'\n')
            resFile.write('\tActual approximation to beta distribution:\n\t'+str(np.round(DiscFacDstnActual,4))+'\n')
            resFile.write('\tGIC satisfied = '+str(GICsatisfied)+'\tGICmaxBeta = '+str(round(GICmaxBetas[educ_type],4))+'\n')
            resFile.write('\tImposed GIC-consistent maximum beta = ' + str(round(gic_capped_beta(educ_type, GICfactor),5))+'\n\n')
    
    dfCheck = namedtuple("dfCheck", ["betaMin", "betaMax", "GICsatisfied"])
    return dfCheck(betaMin, betaMax, GICsatisfied)    

# -----------------------------------------------------------------------------
def calc_mpc_by_wealth_q(Agents,lotterySize):
    '''
    Modified objective function to calculate MPCs by wealth in a consistent way. 

    Parameters
    ----------
    Agents : [AgentType]
        List of all AgentTypes in the economy. They are assumed to differ in 
        their EducType attribute.
    lotterySize : int 
        Size of lottery win in thousands of USD.

    Returns
    -------
    MPCsByWealthQ : [float]
        Array with MPCs for each wealth quartile for these agents. 
    '''

    TypeCount = len(Agents)
#    multi_thread_commands_fake(Agents, ['solve()', 'initialize_sim()', 'simulate()', 'unpack_cFunc()'])
    # CDC-MOD-BUG034 + ESC-MOD-BUG034: dispatched via _aLvl_for helper.
    WealthNow = np.concatenate([_aLvl_for(ThisType) for ThisType in Agents])

    # Get wealth quartile cutoffs and distribute them to each consumer type
    quartile_cuts = get_percentiles(WealthNow,percentiles=[0.25,0.50,0.75])
    WealthQsAll = np.array([])
    wealth_list = np.array([])
    betasAll = np.array([])
    PIsAll = np.array([])
    UnempAll = np.array([])
    educAll = np.array([])
    for ThisType in Agents:
        WealthQ = np.zeros(ThisType.AgentCount,dtype=int)
        for n in range(3):
            # CDC-MOD-BUG034 + ESC-MOD-BUG034: dispatched via _aLvl_for helper.
            WealthQ[_aLvl_for(ThisType) > quartile_cuts[n]] += 1
        ThisType.WealthQ = WealthQ
        WealthQsAll = np.concatenate([WealthQsAll, WealthQ])
        # CDC-MOD-BUG034 + ESC-MOD-BUG034: dispatched via _aLvl_for helper.
        wealth_list = np.concatenate((wealth_list, _aLvl_for(ThisType) ))
        betasAll = np.concatenate((betasAll, ThisType.DiscFac*np.ones(ThisType.AgentCount)))
        PIsAll = np.concatenate((PIsAll, ThisType.state_now["pLvl"]))
        UnempAll = np.concatenate((UnempAll, ThisType.MicroMrkvNow))
        educAll = np.concatenate((educAll, ThisType.EducType*np.ones(ThisType.AgentCount)))
    
    N_Quarter_Sim = 20; # Needs to be dividable by four
    N_Year_Sim = int(N_Quarter_Sim/4)
    N_Lottery_Win_Sizes = 5 # 4 lottery size bin + 1 representative one for agg MPCX
    
    # Calculate average PI and store the AgentCount for each education type
    PI_list_d = np.array([])
    PI_list_h = np.array([])
    PI_list_c = np.array([])
    agCount = np.zeros(3,dtype=int)
    for ThisType in Agents :
        if ThisType.EducType == 0:
            PI_list_d = np.concatenate((PI_list_d, ThisType.state_now["pLvl"]))
            agCount[0] = ThisType.AgentCount
        elif ThisType.EducType == 1:
            PI_list_h = np.concatenate((PI_list_h, ThisType.state_now["pLvl"]))
            agCount[1] = ThisType.AgentCount
        elif ThisType.EducType == 2:
            PI_list_c = np.concatenate((PI_list_c, ThisType.state_now["pLvl"]))
            agCount[2] = ThisType.AgentCount
    avgPI = [np.mean(PI_list_d), np.mean(PI_list_h), np.mean(PI_list_c)]

    # Lottery size in thousands of USD. This code only uses one lottery size
    lottery_size_vec = np.array([0, 0, 0, 0, lotterySize])
    lottery_size = np.zeros(5)  # Fill this in when needed

    EmptyList = [[],[],[],[],[]]
    MPC_set_list = [deepcopy(EmptyList),deepcopy(EmptyList),deepcopy(EmptyList),deepcopy(EmptyList)]
    MPC_Lists    = [deepcopy(MPC_set_list),deepcopy(MPC_set_list),deepcopy(MPC_set_list),deepcopy(MPC_set_list),deepcopy(MPC_set_list)]    
    # additional list for 5th Lottery bin, just need for elements for four years
    MPC_List_Add_Lottery_Bin = EmptyList
    MPC_this_type_d = np.zeros((TypeCount, agCount[0],N_Lottery_Win_Sizes,N_Year_Sim)) #Empty array, MPC for each Lottery size and agent
    MPC_this_type_h = np.zeros((TypeCount, agCount[1],N_Lottery_Win_Sizes,N_Year_Sim)) #Empty array, MPC for each Lottery size and agent
    MPC_this_type_c = np.zeros((TypeCount, agCount[2],N_Lottery_Win_Sizes,N_Year_Sim)) #Empty array, MPC for each Lottery size and agent

    k = 4 # Only one lottery size considered

    for type_num, ThisType in zip(range(TypeCount), Agents):
            
        c_base = np.zeros((ThisType.AgentCount,N_Quarter_Sim))                        #c_base (in case of no lottery win) for each quarter
        c_base_Lvl = np.zeros((ThisType.AgentCount,N_Quarter_Sim))                    #same in levels
        c_actu = np.zeros((ThisType.AgentCount,N_Quarter_Sim,N_Lottery_Win_Sizes))    #c_actu (actual consumption in case of lottery win in one random quarter) for each quarter and lottery size
        c_actu_Lvl = np.zeros((ThisType.AgentCount,N_Quarter_Sim,N_Lottery_Win_Sizes))#same in levels
        a_actu = np.zeros((ThisType.AgentCount,N_Quarter_Sim,N_Lottery_Win_Sizes))    #a_actu captures the actual market resources after potential lottery win (last index) was added and c_actu deducted
        T_hist = np.zeros((ThisType.AgentCount,N_Quarter_Sim))
        P_hist = np.zeros((ThisType.AgentCount,N_Quarter_Sim)) 
                
        # LotteryWin is an array with AgentCount x 4 periods many entries; there is only one 1 in each row indicating the quarter of the Lottery win for the agent in each row
        # This can be coded more efficiently
        LotteryWin = np.zeros((ThisType.AgentCount,N_Quarter_Sim))   
        for i in range(ThisType.AgentCount):
            LotteryWin[i,random.randint(0,3)] = 1
            
        # Scale lottery win with the average PI for this education group
        # lottery_size = lottery_size_vec/avgPI[ThisType.EducType]     
        lottery_size = lottery_size_vec   

        # HARK 0.17.0: Reset simulation index to allow additional simulate() calls
        # The initial simulate() ran for T_sim periods; reset to allow MPC calculation
        ThisType.t_sim = 0

        for period in range(N_Quarter_Sim): #Simulate for 4 quarters as opposed to 1 year
            
            # Simulate forward for one quarter
            ThisType.simulate(1)           
            
            # capture base consumption which is consumption in absence of lottery win
            c_base[:,period] = ThisType.controls["cNrm"] 
            c_base_Lvl[:,period] = c_base[:,period] * ThisType.state_now["pLvl"]
            
            # #for k in range(N_Lottery_Win_Sizes): # Loop through different lottery sizes, only this will produce values in simulated_MPC_means
            # k = 4; # do not loop to save time 
            
            Llvl = lottery_size[k]*LotteryWin[:,period]  #Lottery win occurs only if LotteryWin = 1 for that agent
            Lnrm = Llvl/ThisType.state_now["pLvl"]
            SplurgeNrm = ThisType.Splurge*Lnrm  #Splurge occurs only if LotteryWin = 1 for that agent
    
            R_kink = np.zeros((ThisType.AgentCount))       
            for i in range(ThisType.AgentCount):
                if a_actu[i,period-1,k] < 0:
                    R_kink[i] = Rfree_base[0] #base_params['Rboro']
                else:
                    R_kink[i] = Rfree_base[0] #base_params['Rsave']  
            
            if period == 0:
                m_adj = ThisType.state_now["mNrm"]  + Lnrm - SplurgeNrm
                for aa in range(0,ThisType.AgentCount):
                    # HARK 0.17.0: Access cFunc via solution[0].cFunc[markov_state]
                    c_actu[aa,period,k] = ThisType.solution[0].cFunc[ThisType.MicroMrkvNow[aa]](m_adj[aa],1) + SplurgeNrm[aa]
                # c_actu[:,period,k] = ThisType.solution[0].cFunc(m_adj) + SplurgeNrm
                c_actu_Lvl[:,period,k] = c_actu[:,period,k] * ThisType.state_now["pLvl"]
                a_actu[:,period,k] = ThisType.state_now["mNrm"] + Lnrm - c_actu[:,period,k] #save for next periods
            else:
                T_hist[:,period] = ThisType.shocks["TranShk"] 
                P_hist[:,period] = ThisType.shocks["PermShk"]
                for i_agent in range(ThisType.AgentCount):
                    if ThisType.shocks["TranShk"][i_agent] == 1.0: # indicator of death
                        a_actu[i_agent,period-1,k] = np.exp(np.log(0.00001)) #base_params['kLogInitMean']
                m_adj = a_actu[:,period-1,k]*R_kink/ThisType.shocks["PermShk"] + ThisType.shocks["TranShk"] + Lnrm - SplurgeNrm #continue with resources from last period
                for aa in range(0,ThisType.AgentCount):
                    # HARK 0.17.0: Access cFunc via solution[0].cFunc[markov_state]
                    c_actu[aa,period,k] = ThisType.solution[0].cFunc[ThisType.MicroMrkvNow[aa]](m_adj[aa],1) + SplurgeNrm[aa]
                # c_actu[:,period,k] = ThisType.solution[0].cFunc(m_adj) + SplurgeNrm
                c_actu_Lvl[:,period,k] = c_actu[:,period,k] * ThisType.state_now["pLvl"]
                a_actu[:,period,k] = a_actu[:,period-1,k]*R_kink/ThisType.shocks["PermShk"] + ThisType.shocks["TranShk"] + Lnrm - c_actu[:,period,k] 
                
            if period%4 + 1 == 4: #if we are in the 4th quarter of a year
                year = int((period+1)/4)
                c_actu_Lvl_year = c_actu_Lvl[:,(year-1)*4:year*4,k]
                c_base_Lvl_year = c_base_Lvl[:,(year-1)*4:year*4]
                if ThisType.EducType == 0:
                    MPC_this_type_d[type_num,:,k,year-1] = (np.sum(c_actu_Lvl_year,axis=1) - np.sum(c_base_Lvl_year,axis=1))/(lottery_size[k])
                elif ThisType.EducType == 1:
                    MPC_this_type_h[type_num,:,k,year-1] = (np.sum(c_actu_Lvl_year,axis=1) - np.sum(c_base_Lvl_year,axis=1))/(lottery_size[k])
                elif ThisType.EducType == 2:
                    MPC_this_type_c[type_num,:,k,year-1] = (np.sum(c_actu_Lvl_year,axis=1) - np.sum(c_base_Lvl_year,axis=1))/(lottery_size[k])
                    
            # Sort the MPCs into the proper MPC sets
            for q in range(4):
                these = ThisType.WealthQ == q
                
                # for k in range(N_Lottery_Win_Sizes):
                #     for y in range(N_Year_Sim):
                #         MPC_Lists[k][q][y].append(MPC_this_type[type_num,these,k,y])
                for y in range(N_Year_Sim):
                    if ThisType.EducType == 0:
                        MPC_Lists[k][q][y].append(MPC_this_type_d[type_num,these,k,y])
                    elif ThisType.EducType == 1:
                        MPC_Lists[k][q][y].append(MPC_this_type_h[type_num,these,k,y])
                    elif ThisType.EducType == 2:
                        MPC_Lists[k][q][y].append(MPC_this_type_c[type_num,these,k,y])
                        
            # sort MPCs for addtional Lottery bin
            for y in range(N_Year_Sim):
                if ThisType.EducType == 0:
                    MPC_List_Add_Lottery_Bin[y].append(MPC_this_type_d[type_num,:,k,y])
                elif ThisType.EducType == 1:
                    MPC_List_Add_Lottery_Bin[y].append(MPC_this_type_h[type_num,:,k,y])
                elif ThisType.EducType == 2:
                    MPC_List_Add_Lottery_Bin[y].append(MPC_this_type_c[type_num,:,k,y])

    # Calculate aggregate MPC and MPCx
    simulated_IMPCs = np.zeros((N_Year_Sim))
    for y in range(N_Year_Sim):
        MPC_array = np.concatenate(MPC_List_Add_Lottery_Bin[y])
        simulated_IMPCs[y] = np.mean(MPC_array)

    #Create a list of wealth and MPCs
    MPC_list = np.array([])
    for type_num, ThisType in zip(range(TypeCount), Agents):
        if ThisType.EducType == 0:
            MPC_list = np.concatenate((MPC_list, MPC_this_type_d[type_num, :, k, 0] ))
        elif ThisType.EducType == 1:
            MPC_list = np.concatenate((MPC_list, MPC_this_type_h[type_num, :, k, 0] ))
        elif ThisType.EducType == 2:
            MPC_list = np.concatenate((MPC_list, MPC_this_type_c[type_num, :, k, 0] ))

    MPCbyWQ = np.zeros(5)
    betaByWQ = np.zeros(5)
    PIbyWQ = np.zeros(5)
    wealthByWQ = np.zeros(5)
    pctWealthByWQ = np.zeros(5)
    UnempByWQ = np.zeros(5)
    UnempAll = UnempAll > 0
    educByWQ = np.zeros(5)
    numWQ = np.zeros(5)
    totalWealth = np.sum(wealth_list)
    for qq in range(4):
        MPCbyWQ[qq] = np.mean(MPC_list[WealthQsAll==qq])
        betaByWQ[qq] = np.mean(betasAll[WealthQsAll==qq])
        PIbyWQ[qq] = np.mean(PIsAll[WealthQsAll==qq])
        wealthByWQ[qq] = np.mean(wealth_list[WealthQsAll==qq])
        pctWealthByWQ[qq] = np.sum(wealth_list[WealthQsAll==qq])/totalWealth*100
        UnempByWQ[qq] = np.sum(UnempAll[WealthQsAll==qq])/np.sum(WealthQsAll==qq)
        educByWQ[qq] = np.mean(educAll[WealthQsAll==qq])
        numWQ[qq] = np.sum(WealthQsAll==qq)
    MPCbyWQ[4] = np.mean(MPC_list)
    betaByWQ[4] = np.mean(betasAll)
    PIbyWQ[4] = np.mean(PIsAll)
    wealthByWQ[4] = np.mean(wealth_list)
    pctWealthByWQ[4] = np.sum(wealth_list)/totalWealth*100
    UnempByWQ[4] = np.sum(UnempAll)/len(UnempAll)
    educByWQ[4] = np.mean(educAll)
    numWQ[4] = len(WealthQsAll)
    
    MPCbyEd = np.zeros(4)
    for edType in range(3):
        MPCbyEd[edType] = np.mean(MPC_list[educAll==edType])
    MPCbyEd[3] = np.mean(MPC_list)
    
    sorted_wealth_MPC = np.stack((wealth_list, MPC_list))[:,wealth_list.argsort()]
    total_agents = len(MPC_list)
    quartile1_weights = np.zeros(total_agents)
    quartile1_weights[0:int(np.floor(total_agents*9/40))] = 1.0
    quartile1_slope_length = (int(np.floor(total_agents*11/40)-np.floor(total_agents*9/40)))
    quartile1_weights[int(np.floor(total_agents*9/40)):int(np.floor(total_agents*11/40))] = (quartile1_slope_length-np.arange(quartile1_slope_length))/quartile1_slope_length
    quartile2_weights = np.zeros(total_agents)
    quartile2_weights[0:int(np.floor(total_agents*19/40))] = 1- quartile1_weights[0:int(np.floor(total_agents*19/40))]
    quartile2_slope_length = (int(np.floor(total_agents*21/40)-np.floor(total_agents*19/40)))
    quartile2_weights[int(np.floor(total_agents*19/40)):int(np.floor(total_agents*21/40))] = (quartile2_slope_length-np.arange(quartile2_slope_length))/quartile2_slope_length
    quartile3_weights = np.flip(quartile2_weights)
    quartile4_weights = np.flip(quartile1_weights)
    simulated_MPC_means_smoothed = np.zeros(5)
    simulated_MPC_means_smoothed[0] = np.average(sorted_wealth_MPC[1],weights=quartile1_weights)
    simulated_MPC_means_smoothed[1] = np.average(sorted_wealth_MPC[1],weights=quartile2_weights)
    simulated_MPC_means_smoothed[2] = np.average(sorted_wealth_MPC[1],weights=quartile3_weights)
    simulated_MPC_means_smoothed[3] = np.average(sorted_wealth_MPC[1],weights=quartile4_weights)
    simulated_MPC_means_smoothed[4] = np.average(sorted_wealth_MPC[1])

    # #if estimation_mode==False or target == 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC':     
    # # Calculate average within each MPC set
    # simulated_MPC_means = np.zeros((N_Lottery_Win_Sizes,k,N_Year_Sim))
    
    # for q in range(4):
    #     for y in range(N_Year_Sim):
    #         MPC_array = np.concatenate(MPC_Lists[k][q][y])
    #         simulated_MPC_means[k,q,y] = np.mean(MPC_array)
            
    # # Calculate aggregate MPC and MPCx
    # simulated_MPC_mean_add_Lottery_Bin = np.zeros((N_Year_Sim))
    # for y in range(N_Year_Sim):
    #     MPC_array = np.concatenate(MPC_List_Add_Lottery_Bin[y])
    #     simulated_MPC_mean_add_Lottery_Bin[y] = np.mean(MPC_array)
            
    
    # MPCs = namedtuple("MPCs", ["simulated_MPC_means_smoothed", "sorted_wealth_MPC", 
    #                            "quartile_cuts", "q1w", "q2w", "q3w", "q4w"])
    # return MPCs(simulated_MPC_means_smoothed, sorted_wealth_MPC, quartile_cuts,
    #             quartile1_weights, quartile2_weights, quartile3_weights, quartile4_weights) 

    print('Average PIs: ['+str(np.round(avgPI[0],3))+', '+str(np.round(avgPI[1],3))+', '+str(np.round(avgPI[2],3))+']\n' )

    sMPCs = simulated_MPC_means_smoothed
    print('Wealth by WQ = ['+str(round(wealthByWQ[0],4))+', '+str(round(wealthByWQ[1],4))+', '+str(round(wealthByWQ[2],4))+', '
              +str(round(wealthByWQ[3],4))+', '+str(round(wealthByWQ[4],4))+']')
    print('Wealth share by WQ = ['+str(round(pctWealthByWQ[0],4))+', '+str(round(pctWealthByWQ[1],4))+
          ', '+str(round(pctWealthByWQ[2],4))+', '+str(round(pctWealthByWQ[3],4))+']')
    print('sMPCs = ['+str(round(sMPCs[0],3))+', '+str(round(sMPCs[1],3))+', '+str(round(sMPCs[2],3))+', '
                  +str(round(sMPCs[3],3))+', '+str(round(sMPCs[4],3))+']')
    print('betas by WQ = ['+str(round(betaByWQ[0],4))+', '+str(round(betaByWQ[1],4))+', '+str(round(betaByWQ[2],4))+', '
                  +str(round(betaByWQ[3],4))+', '+str(round(betaByWQ[4],4))+']')
    print('PIs by WQ = ['+str(round(PIbyWQ[0],4))+', '+str(round(PIbyWQ[1],4))+', '+str(round(PIbyWQ[2],4))+', '
                  +str(round(PIbyWQ[3],4))+', '+str(round(PIbyWQ[4],4))+']')
    print('Unemp frac by WQ = ['+str(round(UnempByWQ[0],4))+', '+str(round(UnempByWQ[1],4))+', '+str(round(UnempByWQ[2],4))+', '
                  +str(round(UnempByWQ[3],4))+', '+str(round(UnempByWQ[4],4))+']')
    print('Education by WQ = ['+str(round(educByWQ[0],2))+', '+str(round(educByWQ[1],2))+', '+str(round(educByWQ[2],2))+', '
                  +str(round(educByWQ[3],2))+', '+str(round(educByWQ[4],2))+']')
    print('Num in each WQ = ['+str(numWQ[0])+', '+str(numWQ[1])+', '+str(numWQ[2])+', '
                  +str(numWQ[3])+', '+str(numWQ[4])+']\n')
    
    
    calculatedMPCs = namedtuple("calculatedMPCs", ["MPCbyWQ", "MPCbyEd", "simulated_IMPCs", "pctWealthByWQ"])
    return calculatedMPCs(MPCbyWQ, MPCbyEd, simulated_IMPCs, pctWealthByWQ)


# =============================================================================
#%% Initialize economy
# Make education types
num_types = 3
# This is not the number of discount factors, but the number of household types

InfHorizonTypeAgg_d = AggFiscalType(**init_dropout)
InfHorizonTypeAgg_d.cycles = 0
InfHorizonTypeAgg_h = AggFiscalType(**init_highschool)
InfHorizonTypeAgg_h.cycles = 0
InfHorizonTypeAgg_c = AggFiscalType(**init_college)
InfHorizonTypeAgg_c.cycles = 0
AggDemandEconomy = AggregateDemandEconomy(**init_ADEconomy)
InfHorizonTypeAgg_d.get_economy_data(AggDemandEconomy)
InfHorizonTypeAgg_h.get_economy_data(AggDemandEconomy)
InfHorizonTypeAgg_c.get_economy_data(AggDemandEconomy)
BaseTypeList = [InfHorizonTypeAgg_d, InfHorizonTypeAgg_h, InfHorizonTypeAgg_c ]
      
# Fill in the Markov income distribution for each base type
# NOTE: THIS ASSUMES NO LIFECYCLE
IncomeDstn_unemp = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([InfHorizonTypeAgg_d.IncUnemp])])
IncomeDstn_unemp_nobenefits = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([InfHorizonTypeAgg_d.IncUnempNoBenefits])])
    
for ThisType in BaseTypeList:
    EmployedIncomeDstn = deepcopy(ThisType.IncShkDstn[0])
    ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncomeDstn_unemp]*UBspell_normal + [IncomeDstn_unemp_nobenefits]]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn  # HARK 0.17.0: renamed from IncomeDstn_base
    
# Make the overall list of types
TypeList = []
n = 0
for e in range(num_types):
    for b in range(DiscFacCount):
        DiscFac = DiscFacDstns[e].atoms[0][b]
        AgentCount = int(np.floor(AgentCountTotal*data_EducShares[e]*DiscFacDstns[e].pmv[b]))
        ThisType = deepcopy(BaseTypeList[e])
        ThisType.AgentCount = AgentCount
        ThisType.DiscFac = DiscFac
        ThisType.seed = n
        # No cohort-N override path here; rescale factor is identity by construction.
        # See plans/20260506-1640h_edu_share_aggregation_correction.md
        ThisType.pop_rescale_factor = 1.0
        TypeList.append(ThisType)
        n += 1
base_dict['Agents'] = TypeList

# Variance-reduction shuffle flags (opt-in via env vars).
# HAFISCAL_MC_SHUFFLE=1       → deterministic Markov-state transitions
# HAFISCAL_INCOME_SHUFFLE=1   → deterministic per-period shock frequencies
# See plans/20260408-1024h_minimum-replicates-for-shuffle.md for the minimum-N requirements
# and BUGS/commits a3ec91af for the implementation. Both flags default off
# (match scipy-compatible MC behavior).
_mc_shuffle = os.environ.get('HAFISCAL_MC_SHUFFLE', '') == '1'
_income_shuffle = os.environ.get('HAFISCAL_INCOME_SHUFFLE', '') == '1'
if _mc_shuffle or _income_shuffle:
    for _t in BaseTypeList + TypeList:
        _t.mc_shuffle = _mc_shuffle
        _t.income_shuffle = _income_shuffle
    print(f'[shuffle] mc_shuffle={_mc_shuffle}  income_shuffle={_income_shuffle}')

AggDemandEconomy.agents = TypeList
AggDemandEconomy.solve()

AggDemandEconomy.reset()
for agent in AggDemandEconomy.agents:
    agent.initialize_sim()
    agent.AggDemandFac = 1.0
    agent.RfreeNow = 1.0
    agent.CaggNow = 1.0

AggDemandEconomy.make_history()   
AggDemandEconomy.save_state()   
#AggDemandEconomy.switch_to_counterfactual_mode("base")
#AggDemandEconomy.make_idiosyncratic_shock_histories()

# HARK 0.17.0: unpack_cFunc() no longer exists - cFunc is accessible via solution[0].cFunc
baseline_commands = ['solve()', 'initialize_sim()', 'simulate()', 'save_state()']
# Speedup: parallel over agents (joblib). Falls back to sequential inside HARK if
# only one agent. Override via HAFISCAL_SERIAL=1 for bisection / debugging.
_mtc = multi_thread_commands_fake if os.environ.get('HAFISCAL_SERIAL', '') == '1' else multi_thread_commands
_mtc(TypeList, baseline_commands)


output_keys = ['NPV_AggIncome', 'NPV_AggCons', 'AggIncome', 'AggCons']


#%% Objective functions
# -----------------------------------------------------------------------------
def betas_obj_func(betas, spreads, GICfactors, target_option=1, print_mode=False, print_file=False, filename='DefaultResultsFile.txt'):
    '''
    Objective function for the estimation of discount factor distributions for the 
    three education groups. The groups can differ in the centering of their discount 
    factor distributions, and in the spread around the central value.
    
    Parameters
    ----------
    betas : [float]
        Central values of the discount factor distributions for each education
        level.
    spreads : [float]
        Half the width of each discount factor distribution. If we want the same spread
        for each education group we simply impose that the spreads are all the same.
        That is done outside this function.
    GICfactors : [float]
        How close to the GIC-imposed upper bound the highest betas are allowed to be. 
        If we want the same GICfactor for each education group we simply impose that 
        the GICfactors are all the same.
    target_option : integer
        = 1: Target medianLWPI and LorenzPtsAll 
        = 2: Target avgLWPI and LorenzPts_d, _h and _c
    print_mode : boolean, optional
        If true, statistics for each education level are printed. The default is False.
    print_file : boolean, optional
        If true, statistics are appended to the file filename. The default is False. 
    filename : str
        Filename for printing calculated statistics. The default is DefaultResultsFile.txt.
    
    Returns
    -------
    distance : float
        The distance of the estimation targets between those in the data and those
        produced by the model. 
    '''
    # # Set seed to ensure distance only changes due to different parameters 
    # random.seed(1234)

    beta_d, beta_h, beta_c = betas
    spread_d, spread_h, spread_c = spreads

    # # Overwrite the discount factor distribution for each education level with new values
    dfs_d = Uniform(beta_d-spread_d, beta_d+spread_d).discretize(DiscFacCount)
    dfs_h = Uniform(beta_h-spread_h, beta_h+spread_h).discretize(DiscFacCount)
    dfs_c = Uniform(beta_c-spread_c, beta_c+spread_c).discretize(DiscFacCount)
    dfs = [dfs_d, dfs_h, dfs_c]

    # Check GIC for each type:
    for e in range(num_types):
        for thedf in range(DiscFacCount):
            if dfs[e].atoms[0][thedf] > gic_capped_beta(e, GICfactors[e]):
                dfs[e].atoms[0][thedf] = gic_capped_beta(e, GICfactors[e])
            elif dfs[e].atoms[0][thedf] < minBeta:
                dfs[e].atoms[0][thedf] = minBeta

    # Make a new list of types with updated discount factors 
    TypeListNew = []
    n = 0
    for e in range(num_types):
        for b in range(DiscFacCount):
            AgentCount = int(np.floor(AgentCountTotal*data_EducShares[e]*dfs[e].pmv[b]))
            ThisType = deepcopy(BaseTypeList[e])
            ThisType.AgentCount = AgentCount
            ThisType.DiscFac = dfs[e].atoms[0][b]
            ThisType.seed = n + 100
            TypeListNew.append(ThisType)
            n += 1
    base_dict['Agents'] = TypeListNew

    AggDemandEconomy.agents = TypeListNew
    AggDemandEconomy.solve()

    AggDemandEconomy.reset()
    for agent in AggDemandEconomy.agents:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0

    AggDemandEconomy.make_history()   
    AggDemandEconomy.save_state()   

    # Simulate each type to get a new steady state solution 
    # solve: done in AggDemandEconomy.solve(), initializeSim: done in AggDemandEconomy.reset() 
    # baseline_commands = ['solve()', 'initializeSim()', 'simulate()', 'saveState()']
    # baseline_commands = ['simulate()', 'save_state()']
    # HARK 0.17.0: unpack_cFunc() no longer exists - cFunc is accessible via solution[0].cFunc
    baseline_commands = ['solve()', 'initialize_sim()', 'simulate()', 'save_state()']
    _mtc(TypeListNew, baseline_commands)

    Stats = calc_estim_stats(TypeListNew)
    
    if target_option == 1:
        sumSquares = 10*np.sum((Stats.medianLWPI-data_medianLWPI)**2)
        sumSquares += np.sum((np.array(Stats.LorenzPts) - data_LorenzPtsAll)**2)
    elif target_option == 2:
        lp_d = calc_lorenz_pts(TypeListNew[0:DiscFacCount])
        lp_h = calc_lorenz_pts(TypeListNew[DiscFacCount:2*DiscFacCount])
        lp_c = calc_lorenz_pts(TypeListNew[2*DiscFacCount:3*DiscFacCount])
        sumSquares = np.sum((np.array(Stats.avgLWPI)-data_avgLWPI)**2)
        sumSquares += np.sum((np.array(lp_d)-data_LorenzPts[0])**2)
        sumSquares += np.sum((np.array(lp_h)-data_LorenzPts[1])**2)
        sumSquares += np.sum((np.array(lp_c)-data_LorenzPts[2])**2)
    
    distance = np.sqrt(sumSquares)

    if print_mode or print_file:
        WealthSharesByEd = calc_wealth_share_by_ed(TypeListNew)
        MPCsByEdSimple = calc_mpc_by_ed_simple(TypeListNew)
        MPCsByWQsimple = calc_mpc_by_wealth_q_simple(TypeListNew)
        calculatedMPCs = calc_mpc_by_wealth_q(TypeListNew, 5)
        MPCsByWQ = calculatedMPCs.MPCbyWQ
        MPCsByEd = calculatedMPCs.MPCbyEd
        IMPCs = calculatedMPCs.simulated_IMPCs
        WealthSharesByWQ = calculatedMPCs.pctWealthByWQ

    # If not estimating, print stats by education level
    if print_mode:
        print('Dropouts: beta = ', mystr(beta_d), ' spread = ', mystr(spread_d))
        print('Highschool: beta = ', mystr(beta_h), ' spread = ', mystr(spread_h))
        print('College: beta = ', mystr(beta_c), ' spread = ', mystr(spread_c))
        print('Median LW/PI-ratios: D = ' + mystr(Stats.medianLWPI[0][0]) + ' H = ' + mystr(Stats.medianLWPI[1][0]) \
              + ' C = ' + mystr(Stats.medianLWPI[2][0])) 
        print('Lorenz shares - all:')
        print(Stats.LorenzPts)
        if target_option == 2:
            print('Lorenz shares - Dropouts:')
            print(lp_d)
            print('Lorenz shares - Highschool:')
            print(lp_h)
            print('Lorenz shares - College:')
            print(lp_c) 
        
        print('Distance = ' + mystr(distance))
        print('Average LW/PI-ratios: D = ' + mystr(Stats.avgLWPI[0]) + ' H = ' + mystr(Stats.avgLWPI[1]) \
              + ' C = ' + mystr(Stats.avgLWPI[2])) 
        print('Total LW/Total PI: D = ' + mystr(Stats.LWoPI[0]) + ' H = ' + mystr(Stats.LWoPI[1]) \
              + ' C = ' + mystr(Stats.LWoPI[2]))
        print('Wealth Shares by Ed.: D = ' + mystr(WealthSharesByEd[0]) + \
              ' H = ' + mystr(WealthSharesByEd[1]) + ' C = ' + mystr(WealthSharesByEd[2]))
        print('Wealth Shares by Wealth Q = ['+mystr(WealthSharesByWQ[0])+', '+mystr(WealthSharesByWQ[1])+ \
              ', '+mystr(WealthSharesByWQ[2])+ ', '+mystr(WealthSharesByWQ[3])+']')
        print('Average MPCs by Ed. (incl. splurge) = ['+str(round(MPCsByEdSimple.MPCsA[0],3))+', '
                      +str(round(MPCsByEdSimple.MPCsA[1],3))+', '+str(round(MPCsByEdSimple.MPCsA[2],3))+', '
                      +str(round(MPCsByEdSimple.MPCsA[3],3))+']')
        print('Average annual MPCs by Wealth Q (incl. splurge) = ['+str(round(MPCsByWQsimple.MPCsA[0],3))+', '
                      +str(round(MPCsByWQsimple.MPCsA[1],3))+', '+str(round(MPCsByWQsimple.MPCsA[2],3))+', '
                      +str(round(MPCsByWQsimple.MPCsA[3],3))+', '+str(round(MPCsByWQsimple.MPCsA[4],3))+']\n')
        print('Average lottery-win-year MPCs by Wealth Q (simple, incl. splurge) = ['+str(round(MPCsByWQsimple.MPCsFYL[0],3))+', '
                      +str(round(MPCsByWQsimple.MPCsFYL[1],3))+', '+str(round(MPCsByWQsimple.MPCsFYL[2],3))+', '
                      +str(round(MPCsByWQsimple.MPCsFYL[3],3))+', '+str(round(MPCsByWQsimple.MPCsFYL[4],3))+']\n')
        print('Average lottery-win-year MPCs by Wealth Q (incl. splurge) = ['+str(round(MPCsByWQ[0],3))+', '
                      +str(round(MPCsByWQ[1],3))+', '+str(round(MPCsByWQ[2],3))+', '
                      +str(round(MPCsByWQ[3],3))+', '+str(round(MPCsByWQ[4],3))+']\n')
        print('Average lottery-win-year MPCs by Education (incl. splurge) = ['+str(round(MPCsByEd[0],3))+', '
                      +str(round(MPCsByEd[1],3))+', '+str(round(MPCsByEd[2],3))+', '
                      +str(round(MPCsByEd[3],3))+']\n')
        print('IMPCs over time = ['+str(round(IMPCs[0],3))+', '+str(round(IMPCs[1],3))+', '
                      +str(round(IMPCs[2],3))+', '+str(round(IMPCs[3],3))+', '+str(round(IMPCs[4],3))+']\n')

    if print_file:
        with open(filename, 'a') as resFile: 
            resFile.write('Population calculations:\n')
            resFile.write('\tMedian LW/PI-ratios = ['+mystr(Stats.medianLWPI[0][0])+', '+ 
                          mystr(Stats.medianLWPI[1][0])+', '+mystr(Stats.medianLWPI[2][0])+']\n')
            resFile.write('\tLorenz Points = ['+str(round(Stats.LorenzPts[0],4))+', '
                          +str(round(Stats.LorenzPts[1],4))+', '+str(round(Stats.LorenzPts[2],4))+', '
                          +str(round(Stats.LorenzPts[3],4))+']\n')
            resFile.write('\tWealth shares by Ed.= ['+str(round(WealthSharesByEd[0],3))+', '
                          +str(round(WealthSharesByEd[1],3))+', '+str(round(WealthSharesByEd[2],3))+']\n')
            resFile.write('\tWealth Shares by Wealth Q = ['+mystr(WealthSharesByWQ[0])+', '+mystr(WealthSharesByWQ[1])+ 
                          ', '+mystr(WealthSharesByWQ[2])+ ', '+mystr(WealthSharesByWQ[3])+']\n')
            resFile.write('\tAverage LW/PI-ratios: D = ' + mystr(Stats.avgLWPI[0]) + ' H = ' + mystr(Stats.avgLWPI[1]) \
                  + ' C = ' + mystr(Stats.avgLWPI[2])+'\n') 
            resFile.write('\tTotal LW/Total PI: D = ' + mystr(Stats.LWoPI[0]) + ' H = ' + mystr(Stats.LWoPI[1]) \
                  + ' C = ' + mystr(Stats.LWoPI[2])+'\n')
            
            resFile.write('\tAverage MPCs by Ed. (simple, incl. splurge) = ['+str(round(MPCsByEdSimple.MPCsA[0],3))+', '
                          +str(round(MPCsByEdSimple.MPCsA[1],3))+', '+str(round(MPCsByEdSimple.MPCsA[2],3))+', '
                          +str(round(MPCsByEdSimple.MPCsA[3],3))+']\n')
            resFile.write('\tAverage annual MPCs by Wealth (incl. splurge) = ['+str(round(MPCsByWQsimple.MPCsA[0],3))+', '
                          +str(round(MPCsByWQsimple.MPCsA[1],3))+', '+str(round(MPCsByWQsimple.MPCsA[2],3))+', '
                          +str(round(MPCsByWQsimple.MPCsA[3],3))+', '+str(round(MPCsByWQsimple.MPCsA[4],3))+']\n')
            resFile.write('\tAverage lottery-win-year MPCs by Wealth (simple, incl. splurge) = ['+str(round(MPCsByWQsimple.MPCsFYL[0],3))+', '
                          +str(round(MPCsByWQsimple.MPCsFYL[1],3))+', '+str(round(MPCsByWQsimple.MPCsFYL[2],3))+', '
                          +str(round(MPCsByWQsimple.MPCsFYL[3],3))+', '+str(round(MPCsByWQsimple.MPCsFYL[4],3))+']\n')
            resFile.write('\tAverage lottery-win-year MPCs by Wealth (incl. splurge) = ['+str(round(MPCsByWQ[0],3))+', '
                          +str(round(MPCsByWQ[1],3))+', '+str(round(MPCsByWQ[2],3))+', '
                          +str(round(MPCsByWQ[3],3))+', '+str(round(MPCsByWQ[4],3))+']\n')
            resFile.write('\tAverage lottery-win-year MPCs by Education (incl. splurge) = ['+str(round(MPCsByEd[0],3))+', '
                          +str(round(MPCsByEd[1],3))+', '+str(round(MPCsByEd[2],3))+', '
                          +str(round(MPCsByEd[3],3))+']\n')
            resFile.write('\tIMPCs over time = ['+str(round(IMPCs[0],3))+', '+str(round(IMPCs[1],3))+', '
                          +str(round(IMPCs[2],3))+', '+str(round(IMPCs[3],3))+', '+str(round(IMPCs[4],3))+']\n')
        
    return distance 
# -----------------------------------------------------------------------------
def betas_obj_func_educ(beta, spread, GICx, educ_type=2, print_mode=False, print_file=False, filename='DefaultResultsFile.txt'):
    '''
    Objective function for the estimation of a discount factor distribution for
    a single education group.
    
    Parameters
    ----------
    beta : float
        Central value of the discount factor distribution.
    spread : float
        Half the width of the discount factor distribution.
    GICx : float
        Number that determines how close to the GIC-imposed upper bound the highest beta is allowed to be.
    educ_type : integer
        The education type to estimate a discount factor distribution for.     
        Targets are avgLWPI[educ_type] and LorenzPts[educ_type]
    print_mode : boolean, optional
        If true, statistics are printed. The default is False.
    print_file : boolean, optional
        If true, statistics are appended to the file filename. The default is False. 
    filename : str
        Filename for printing calculated statistics. The default is DefaultResultsFile.txt.
    
    Returns
    -------
    distance : float
        The distance of the estimation targets between those in the data and those
        produced by the model. 
    '''
    # Track iteration
    _nelder_mead_iter_count[educ_type] += 1
    iter_start = time.time()
    
    # # Set seed to ensure distance only changes due to different parameters 
    # random.seed(1234)

    dfs = Uniform(beta-spread, beta+spread).discretize(DiscFacCount)
    
    # Check GIC:
    for thedf in range(DiscFacCount):
        if dfs.atoms[0][thedf] > gic_capped_beta(educ_type, np.exp(GICx)/(1+np.exp(GICx))):
            dfs.atoms[0][thedf] = gic_capped_beta(educ_type, np.exp(GICx)/(1+np.exp(GICx)))
        elif dfs.atoms[0][thedf] < minBeta:
            dfs.atoms[0][thedf] = minBeta

    # Make a new list of types with updated discount factors for the given educ type.
    #
    # Default path: in-place mutation of the existing agents in AggDemandEconomy.
    # agents. Preserves each agent's .solution attribute across NM iterations so
    # the warm-start path in AggregateDemandEconomy.solve() (warm_start=True; the
    # method is defined in AggFiscalModel.py) fires for the education type currently
    # being estimated too — not only for the other two groups. Validated 2026-04-18
    # across all three edtypes (DO N=30 1.35×, HS N=5 1.27×, COL N=10 1.28×) with
    # max |Δβ|=0 vs the deepcopy path; see plans/results/20260418_phase1.2-
    # warmstart-validation.md.
    #
    # HAFISCAL_NM_IN_PLACE=0 falls back to the original deepcopy+splice pattern.
    # Use this if a regression vs prior calibration results ever needs to be
    # bisected against this change.
    if os.environ.get('HAFISCAL_NM_IN_PLACE', '1') == '1':
        TypeListAll = AggDemandEconomy.agents
        for b in range(DiscFacCount):
            agent = TypeListAll[educ_type*DiscFacCount + b]
            agent.AgentCount = int(np.floor(AgentCountTotal*data_EducShares[educ_type]*dfs.pmv[b]))
            agent.DiscFac = dfs.atoms[0][b]
            agent.seed = b
        TypeListNewEduc = TypeListAll[educ_type*DiscFacCount:(educ_type+1)*DiscFacCount]
    else:
        TypeListNewEduc = []
        n = 0
        for b in range(DiscFacCount):
            AgentCount = int(np.floor(AgentCountTotal*data_EducShares[educ_type]*dfs.pmv[b]))
            ThisType = deepcopy(BaseTypeList[educ_type])
            ThisType.AgentCount = AgentCount
            ThisType.DiscFac = dfs.atoms[0][b]
            ThisType.seed = n
            TypeListNewEduc.append(ThisType)
            n += 1
        TypeListAll = AggDemandEconomy.agents
        TypeListAll[educ_type*DiscFacCount:(educ_type+1)*DiscFacCount] = TypeListNewEduc
            
    base_dict['Agents'] = TypeListAll
    AggDemandEconomy.agents = TypeListAll
    AggDemandEconomy.solve()

    AggDemandEconomy.reset()
    for agent in AggDemandEconomy.agents:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0

    AggDemandEconomy.make_history()   
    AggDemandEconomy.save_state()   

    # Simulate each type to get a new steady state solution 
    # solve: done in AggDemandEconomy.solve(), initializeSim: done in AggDemandEconomy.reset() 
    # baseline_commands = ['solve()', 'initializeSim()', 'simulate()', 'saveState()']
    # baseline_commands = ['simulate()', 'save_state()']
    baseline_commands = ['solve()', 'initialize_sim()', 'simulate()', 'save_state()']
    _mtc(TypeListAll, baseline_commands)

    Stats = calc_estim_stats(TypeListAll)

    sumSquares = np.sum((Stats.medianLWPI[educ_type]-data_medianLWPI[educ_type])**2)
    lp = calc_lorenz_pts(TypeListNewEduc)
    sumSquares += np.sum((np.array(lp) - data_LorenzPts[educ_type])**2)
#    sumSquares = np.sum((Stats.avgLWPI[educ_type]-data_avgLWPI[educ_type])**2)
   
    distance = np.sqrt(sumSquares)

    # If not estimating, print stats by education level
    if print_mode:
        print('Median LW/PI-ratio for group e = ' + mystr(educ_type) + ' is: ' \
              + mystr(Stats.medianLWPI[educ_type][0]))
        if educ_type == 0:
            print('Lorenz shares - Dropouts:')
        elif educ_type == 1:
            print('Lorenz shares - Highschool:')
        elif educ_type == 2:
            print('Lorenz shares - College:')
        print(lp)
        print('Distance = ' + mystr(distance))
        print('Non-targeted moments:')
        print('Average LW/PI-ratios for group e = ' + mystr(educ_type) + ' is: ' \
              + mystr(Stats.avgLWPI[educ_type]))
    
    if print_file:
        with open(filename, 'a') as resFile: 
            resFile.write('Education group = '+mystr(educ_type)+': beta = '+mystr4(beta)+
                          ', nabla = '+mystr4(spread)+', GICfactor = '+mystr4(np.exp(GICx)/(1+np.exp(GICx)))+'\n')
            resFile.write('\tMedian LW/PI-ratio = '+mystr(Stats.medianLWPI[educ_type][0])+'\n')
            resFile.write('\tLorenz Points = ['+str(round(lp[0],4))+', '+str(round(lp[1],4))+', '
                          +str(round(lp[2],4))+', '+str(round(lp[3],4))+']\n')
    
    # Log iteration timing and metrics
    iter_time = time.time() - iter_start
    educ_names = ['Dropout', 'Highschool', 'College']
    profiler.log_convergence(
        _nelder_mead_iter_count[educ_type],
        f"distance_{educ_names[educ_type]}",
        distance
    )
    profiler.record_time(f"nelder_mead_iter_{educ_names[educ_type]}", iter_time,
                         f"beta={beta:.4f}, spread={spread:.4f}")

    # HAFISCAL_NM_TRAJECTORY=<jsonl-path>: append one JSON record per NM iteration.
    # Used by validate_nm_warmstart.py for before/after comparison.
    _traj_path = os.environ.get('HAFISCAL_NM_TRAJECTORY', '')
    if _traj_path:
        import json as _json
        _rec = {
            'iter': _nelder_mead_iter_count[educ_type],
            'edtype': int(educ_type),
            'beta': float(beta),
            'spread': float(spread),
            'GICx': float(GICx),
            'distance': float(distance),
            'iter_sec': float(iter_time),
            'in_place': os.environ.get('HAFISCAL_NM_IN_PLACE', '0') == '1',
        }
        with open(_traj_path, 'a') as _tf:
            _tf.write(_json.dumps(_rec) + '\n')
    
    return distance 
# -----------------------------------------------------------------------------

#%% MC Determinism Test Mode
# When HAFISCAL_MC_DETERMINISM_TEST=1 or --mc-test is passed, we evaluate the 
# objective function at fixed parameter points (the optimizer's initial values)
# and save detailed results to a JSON file for cross-version comparison.
# This confirms that both HARK versions produce identical Monte Carlo results 
# when running single-threaded with synchronized RNG.
MC_DETERMINISM_TEST = (os.environ.get('HAFISCAL_MC_DETERMINISM_TEST', '') == '1'
                       or '--mc-test' in sys.argv)

#%% Estimate discount factor distributions separately for each education type
estimateDiscFacs = True
if MC_DETERMINISM_TEST:
    estimateDiscFacs = False  # Skip full optimization in MC test mode
if os.environ.get('HAFISCAL_SKIP_ESTIMATION', '') == '1':
    estimateDiscFacs = False  # Profile harness: import without running estimation
if os.environ.get('HAFISCAL_SKIP_ESTIMATION_OPTIMIZE', '') == '1':
    estimateDiscFacs = False  # run_phase2_parallel.py final pass: only calcAllResults
if estimateDiscFacs:
    substep("Starting discount factor estimation", expected_duration_min=2880)  # ~48 hours
    profiler.sample_memory("estimation_start")
    
    if IncUnemp == 0.7 and IncUnempNoBenefits == 0.5:
        # Baseline unemployment system: 
        print('Estimating for CRRA = '+str(round(CRRA,1))+' and R = ' + str(round(Rfree_base[0],3))+':\n')
        df_resFileStr = res_dir+'/DiscFacEstim_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])
    else:
        print('Estimating for an alternativ unemployment system with IncUnemp = '+str(round(IncUnemp,2))+
              ' and IncUnempNoBenefits = ' + str(round(IncUnempNoBenefits,2))+':\n')
        df_resFileStr = res_dir+'/DiscFacEstim_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])+'_altBenefits'
    
    if Splurge == 0:
        print('Estimating for special case of Splurge = 0\n')
        df_resFileStr = df_resFileStr + '_Splurge0'
    # ESC-MOD-PHASE3-write: tag output filename with interpretation suffix.
    # CDC stays unsuffixed (preserves byte-identity with legacy reads); ESC
    # gets _ESC. Cross-interpretation registry isolation — see _interpretation.py.
    # _interp_suffix imported at module level (not here) so the calcAllResults
    # block sees it even when this estimation block is skipped via
    # HAFISCAL_SKIP_ESTIMATION_OPTIMIZE.
    df_resFileStr = df_resFileStr + _interp_suffix() + '.txt'

    print('Estimation results saved in ' + df_resFileStr)
    progress(f"Results file: {df_resFileStr}")
    
    educ_names = ['Dropout', 'Highschool', 'College']
    educ_expected_duration = [960, 960, 960]  # ~16 hours each

    # Speedup: optionally run only a subset of edTypes (e.g., one per
    # subprocess in run_phase2_parallel.py). Default = all three.
    _edtypes_env = os.environ.get('HAFISCAL_EDTYPES', '0,1,2')
    edtypes_to_run = [int(s) for s in _edtypes_env.split(',') if s.strip() != '']
    # When filtering to a subset, write to a per-subset file to avoid races
    # between concurrent subprocesses. The wrapper merges them afterward.
    _single_edtype = (len(edtypes_to_run) == 1)
    if _single_edtype:
        # Insert _edType{N} BEFORE the trailing _ESC.txt (CDC: trailing is just .txt).
        # Preserves ESC suffix at the end of the filename.
        _trailing = _interp_suffix() + '.txt'
        df_resFileStr = df_resFileStr[:-len(_trailing)] + f'_edType{edtypes_to_run[0]}' + _trailing
        print(f'[HAFISCAL_EDTYPES] estimating only edType={edtypes_to_run[0]}; writing to {df_resFileStr}')

    # BUG-036 multi-start support. HAFISCAL_NUM_STARTS=N (default 1) runs
    # Nelder-Mead from N curated starting points per cohort and keeps the
    # global-best basin's parameters. Backward-compat: NUM_STARTS=1 reproduces
    # the old single-start estimation exactly. See BUGS_private/HAFiscal_BUG-036
    # for the dropout local-minima discovery that motivates this.
    _NUM_STARTS = int(os.environ.get('HAFISCAL_NUM_STARTS', '1'))
    print(f"\n[multi-start] HAFISCAL_NUM_STARTS={_NUM_STARTS}  "
          f"(1 = backward-compat single-start; >1 = run multi and pick best)")

    # Per-cohort multi-start grids — see BUG-036 §6.1. Position 0 is always
    # the legacy single-start point so NUM_STARTS=1 is bit-for-bit unchanged.
    _multistart_grid = {
        0: [  # Dropout — high-∇, multimodal (BUG-036)
            [0.75, 0.30, 6.0],   # legacy default
            [0.70, 0.34, 6.0],   # near-ESC anchor
            [0.65, 0.40, 5.0],   # low-β / wide-∇ probe (best basin in BUG-036 diag)
            [0.80, 0.20, 6.5],   # high-β / narrow-∇ probe
        ],
        1: [  # Highschool — narrow ∇
            [0.93, 0.07, 5.0],   # legacy default
            [0.90, 0.11, 4.5],   # post-fix-CDC-like
            [0.95, 0.05, 5.5],   # tighter
        ],
        2: [  # College — very narrow ∇
            [0.98, 0.015, 6.0],  # legacy default
            [0.97, 0.030, 7.0],  # mild perturbation
        ],
    }
    _legacy_default = {0: [0.75, 0.3, 6], 1: [0.93, 0.07, 5], 2: [0.98, 0.015, 6]}

    for edType in edtypes_to_run:
        substep(f"Estimating {educ_names[edType]} (edType={edType})",
                expected_duration_min=educ_expected_duration[edType] * max(1, _NUM_STARTS))
        progress(f"Starting Nelder-Mead optimization for {educ_names[edType]}")

        # Reset iteration counter for this education type
        _nelder_mead_iter_count[edType] = 0

        # BUG-039 dispatch: HAFISCAL_GICX_MODE = legacy | hardcoded | twophase.
        # See BUGS_private/HAFiscal_BUG-039_GICx_unconditionally_optimized.md
        # and plans/20260502-1145h_fix-BUG-039-GICx-NM-options.md.
        #   hardcoded: 2-D NM (β, ∇); cap pinned at module-load theGICfactor=0.9995 (BUG-053, 2026-06-09). (DEFAULT post-Phase G)
        #   legacy:    3-D NM (β, ∇, GICx); GICx is a free fit knob. Pre-Phase G default; opt-in for verification.
        #   twophase:  2-D first; if cap binds at converged (β, ∇), refine with 3-D NM.
        # GICx is mapped from a logit factor: factor = exp(GICx)/(1+exp(GICx)).
        # For factor = theGICfactor (0.9995 since BUG-053, 2026-06-09), the pinned value
        # computed below is logit(0.9995) ≈ 7.6004 (was logit(0.999) ≈ 6.9068). The variable
        # name _GICx_for_factor_0999 predates the 0.999→0.9995 change (rename = code edit,
        # out of scope for the comment-only pass).
        # Default flipped 2026-05-03 per Phase G: Phase F evidence (GICx 10× spread with
        # negligible (β,∇) impact) confirms cap is non-load-bearing for all 3 cohorts.
        from EstimParameters import theGICfactor as _theGICfactor
        from HARK.distributions import Uniform as _Uniform
        _GICX_MODE = os.environ.get('HAFISCAL_GICX_MODE', 'hardcoded')
        _GICx_for_factor_0999 = float(np.log(_theGICfactor / (1 - _theGICfactor)))
        if _GICX_MODE not in ('legacy', 'hardcoded', 'twophase'):
            raise ValueError(f"HAFISCAL_GICX_MODE must be 'legacy', 'hardcoded', or 'twophase'; got {_GICX_MODE!r}")
        print(f"[BUG-039] HAFISCAL_GICX_MODE = {_GICX_MODE}")
        if _GICX_MODE == 'hardcoded':
            print(f"[BUG-039 hardcoded] GICx pinned at logit(theGICfactor={_theGICfactor}) = {_GICx_for_factor_0999:.4f}; NM is 2-D (β, ∇)")
            f_temp = lambda x : betas_obj_func_educ(x[0], x[1], _GICx_for_factor_0999, educ_type=edType)
        elif _GICX_MODE == 'twophase':
            print(f"[BUG-039 twophase] phase 1 = 2-D with GICx pinned; phase 2 fires per-start if cap binds")
            f_temp = lambda x : betas_obj_func_educ(x[0], x[1], _GICx_for_factor_0999, educ_type=edType)
        else:  # 'legacy'
            f_temp = lambda x : betas_obj_func_educ(x[0], x[1], x[2], educ_type=edType)

        # Build starting-point list for this cohort.
        if _NUM_STARTS > 1 and edType in _multistart_grid:
            _starts = _multistart_grid[edType][:_NUM_STARTS]
        else:
            _starts = [_legacy_default.get(edType, [0.90, 0.02, 6])]

        # BUG-039 Phase E: HAFISCAL_NM_START_FROM_SAVED=1 prepends the saved
        # (β, ∇, GICx) from DiscFacEstim_*.txt as an additional starting point.
        # Combined with multistart so other points still get tried (no stale-
        # basin lock-in). If saved file or per-cohort row not found, silently
        # skip — fall back to existing behavior.
        # Default flipped 2026-05-03 per Phase G: Phase E validated round-trip
        # preservation (warm-start from saved → re-converged identical), so
        # warm-start is on by default. Set =0 to opt out.
        # Registry-aware (Phase 3 of registry plan): prefer the registry's
        # saved step2_cal for the matching configuration over the suffix-named
        # file. Falls back to suffix-named file when no registry entry exists.
        if os.environ.get('HAFISCAL_NM_START_FROM_SAVED', '1') == '1':
            _saved_path = df_resFileStr   # default = canonical suffix-named file
            try:
                import sys as _sys_reg_ws
                _ha_root_reg_ws = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                if _ha_root_reg_ws not in _sys_reg_ws.path:
                    _sys_reg_ws.path.insert(0, _ha_root_reg_ws)
                import _registry as _reg_ws
                _reg_path = _reg_ws.find_warm_start_cal()
                if _reg_path is not None and _reg_path.exists():
                    _saved_path = str(_reg_path)
                    print(f"[BUG-039 Phase E + registry] warm-start source: {_reg_path}")
            except Exception as _ws_err:
                print(f"[BUG-039 Phase E] registry lookup failed ({_ws_err!r}); using suffix-named file")
            try:
                _saved_text = open(_saved_path).read()
                import re as _re
                _row_pattern = _re.compile(
                    r"'EducationGroup':\s*" + str(edType) +
                    r".*?'beta':\s*([\d.eE+-]+).*?'nabla':\s*([\d.eE+-]+).*?'GICx':\s*([\d.eE+-]+)"
                )
                _m = _row_pattern.search(_saved_text)
                if _m:
                    _saved_start = [float(_m.group(1)), float(_m.group(2)), float(_m.group(3))]
                    if _NUM_STARTS == 1:
                        # Single-start mode + warm-start: REPLACE legacy default with saved
                        # (otherwise we'd run TWO NM passes and lose the speedup)
                        _starts = [_saved_start]
                        print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1: replaced single-start "
                              f"default with saved start β={_saved_start[0]:.4f}, ∇={_saved_start[1]:.4f}, "
                              f"GICx={_saved_start[2]:.4f} (from {os.path.basename(_saved_path)})")
                    else:
                        # Multi-start: prepend saved as additional start, cap at NUM_STARTS so
                        # we don't increase the total NM-run count
                        _starts.insert(0, _saved_start)
                        _starts = _starts[:_NUM_STARTS]
                        print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1: prepended saved start "
                              f"β={_saved_start[0]:.4f}, ∇={_saved_start[1]:.4f}, GICx={_saved_start[2]:.4f} "
                              f"(from {os.path.basename(_saved_path)}; capped to {_NUM_STARTS} starts)")
                else:
                    print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1 set but no edType={edType} row in {_saved_path}; using legacy starts only")
            except (FileNotFoundError, IOError):
                print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1 set but {_saved_path} not readable; using legacy starts only")

        # BUG-039: for 2-D modes, drop GICx from each starting point.
        if _GICX_MODE in ('hardcoded', 'twophase'):
            _starts = [list(s)[:2] for s in _starts]

        # BUG-039 Phase F: HAFISCAL_PIN_START_INDEX selects a single multistart
        # point (used by run_phase2_parallel.py to launch per-(cohort, start)
        # subprocesses). When set, only that start is run and output goes to
        # *_start{K}.txt (so multiple parallel workers don't clobber each other).
        _PIN_START_INDEX = os.environ.get('HAFISCAL_PIN_START_INDEX', None)
        if _PIN_START_INDEX is not None:
            _PIN_START_INDEX = int(_PIN_START_INDEX)
            if _PIN_START_INDEX < 0 or _PIN_START_INDEX >= len(_starts):
                raise ValueError(f"HAFISCAL_PIN_START_INDEX={_PIN_START_INDEX} out of range; cohort {edType} has {len(_starts)} starts available")
            _starts = [_starts[_PIN_START_INDEX]]
            print(f"[BUG-039 Phase F] HAFISCAL_PIN_START_INDEX={_PIN_START_INDEX}: running only this single start for cohort {edType}")

        t0_estim = time.time()
        # HAFISCAL_NM_VALIDATE_N_ITERS=N: cap Nelder-Mead at N function calls.
        _nm_kwargs = {}
        _nm_cap = os.environ.get('HAFISCAL_NM_VALIDATE_N_ITERS', '').strip()
        if _nm_cap:
            try:
                _nm_kwargs['maxfun'] = int(_nm_cap)
                _nm_kwargs['maxiter'] = int(_nm_cap)
                print(f'[NM cap] limiting to {_nm_cap} function calls / iterations')
            except ValueError:
                pass
        # Nelder-Mead convergence tolerances.
        #
        # HAFiscal default: xtol = ftol = 1e-2. Validated at Baseline scale
        # in the 2026-04-18 overnight speedup session: max |ΔW6| = 0.01 vs
        # the m-TM Phase 6 reference across all 9 welfare-6 cells, with a
        # 3× wall-time reduction over scipy's legacy 1e-4 default. A paired
        # test at 1e-3 gave identical converged β/∇ as 1e-2 but at 2.3× the
        # wall — tighter tolerance bought no precision, so 1e-2 is the
        # production-recommended default (plans/results/20260419_overnight-
        # digest.md §4 and §6).
        #
        # HAFISCAL_NM_XATOL / HAFISCAL_NM_FATOL env vars override. Set to
        # 1e-4 to restore scipy's legacy behavior; set to 1e-3 for the
        # intermediate setting.
        #
        # scipy.optimize.fmin takes xtol/ftol — not xatol/fatol (those are
        # on scipy.optimize.minimize's options dict).
        _nm_xatol_env = os.environ.get('HAFISCAL_NM_XATOL', '').strip()
        _nm_kwargs['xtol'] = float(_nm_xatol_env) if _nm_xatol_env else 1e-2
        if _nm_xatol_env:
            print(f'[NM tol] xtol = {_nm_xatol_env} (override of default 1e-2)')
        else:
            print(f'[NM tol] xtol = 1e-2 (HAFiscal default)')
        _nm_fatol_env = os.environ.get('HAFISCAL_NM_FATOL', '').strip()
        _nm_kwargs['ftol'] = float(_nm_fatol_env) if _nm_fatol_env else 1e-2
        if _nm_fatol_env:
            print(f'[NM tol] ftol = {_nm_fatol_env} (override of default 1e-2)')
        else:
            print(f'[NM tol] ftol = 1e-2 (HAFiscal default)')
        # Multi-start optimization. For NUM_STARTS=1, exactly one iteration
        # of this loop runs and behavior matches the legacy single-start.
        _best_params = None
        _best_dist = float('inf')
        _best_idx = None
        _all_starts_results = []
        for _k, _x0 in enumerate(_starts):
            if _NUM_STARTS > 1:
                print(f"\n  --- Start {_k+1}/{len(_starts)} for {educ_names[edType]}: x0={_x0} ---")
            with profile_function(f"nelder_mead_{educ_names[edType]}_start{_k}"):
                _opt = minimize_nelder_mead(
                    f_temp, _x0,
                    verbose=(_NUM_STARTS == 1),  # quiet inside multi-start to keep log scannable
                    **_nm_kwargs,
                )
            # BUG-039: assemble full (β, ∇, GICx) from the (possibly 2-D) NM result
            if _GICX_MODE == 'hardcoded':
                _opt = np.array([_opt[0], _opt[1], _GICx_for_factor_0999])
            elif _GICX_MODE == 'twophase':
                _beta_p, _spread_p = float(_opt[0]), float(_opt[1])
                _dfs_p = _Uniform(_beta_p - _spread_p, _beta_p + _spread_p).discretize(DiscFacCount)
                _cap_p = gic_capped_beta(edType, _theGICfactor)
                if max(_dfs_p.atoms[0]) > _cap_p:
                    print(f"  [BUG-039 twophase] cap binding at converged (β={_beta_p:.4f}, ∇={_spread_p:.4f}); running phase 2 (3-D)")
                    _f_3d = lambda x : betas_obj_func_educ(x[0], x[1], x[2], educ_type=edType)
                    _opt = minimize_nelder_mead(
                        _f_3d, [_beta_p, _spread_p, _GICx_for_factor_0999],
                        verbose=(_NUM_STARTS == 1),
                        **_nm_kwargs,
                    )
                else:
                    print(f"  [BUG-039 twophase] cap non-binding at converged (β={_beta_p:.4f}, ∇={_spread_p:.4f}); skipping phase 2; reporting GICx_default")
                    _opt = np.array([_beta_p, _spread_p, _GICx_for_factor_0999])
            _dist = betas_obj_func_educ(_opt[0], _opt[1], _opt[2], educ_type=edType)
            _all_starts_results.append((_k, _x0, list(_opt), _dist))
            if _NUM_STARTS > 1:
                print(f"    β={_opt[0]:.4f} ∇={_opt[1]:.4f} GICx={_opt[2]:.3f} | distance={_dist:.4f}")
            if _dist < _best_dist:
                _best_dist = _dist
                _best_params = _opt
                _best_idx = _k

        opt_params = _best_params  # publish-named variable for the rest of the block
        t1_estim = time.time()

        if _NUM_STARTS > 1:
            print(f"\n  Best basin: start #{_best_idx+1} (distance {_best_dist:.4f})")
            _dist_range = max(r[3] for r in _all_starts_results) - min(r[3] for r in _all_starts_results)
            print(f"  Distance range across {_NUM_STARTS} starts: {_dist_range:.4f}")
            if _dist_range > 0.1:
                print(f"  ⚠ STRONG basin variation (range > 0.1) — confirms BUG-036 risk for {educ_names[edType]}")

        progress(f"{educ_names[edType]} estimation complete: {_nelder_mead_iter_count[edType]} total iterations across "
                 f"{len(_starts)} start(s), {(t1_estim-t0_estim)/60:.1f} minutes")
        print('Finished estimating for education type = '+str(edType)+'. Optimal beta, spread and GIC factor are:')
        print('Beta = ' + mystr4(opt_params[0]) +'  Nabla = ' + mystr4(opt_params[1]) +
              ' GIC factor = ' + mystr4(np.exp(opt_params[2])/(1+np.exp(opt_params[2]))))

        # Single-edType mode: always overwrite (one record per file)
        # Multi-edType mode: original behavior (overwrite on first, append on rest)
        if _single_edtype:
            mode = 'w'
        else:
            mode = 'w' if edType == edtypes_to_run[0] else 'a'
        # BUG-039 Phase F: when pinned to a single start (parallel-multistart
        # subprocess mode), write to *_start{K}.txt instead of the canonical
        # per-edType file, and include 'distance' in the dict so the wrapper
        # can pick the best basin across pinned-start subprocesses.
        if _PIN_START_INDEX is not None:
            # Insert _start{K} BEFORE the trailing _ESC.txt (CDC: just .txt).
            _trailing_pin = _interp_suffix() + '.txt'
            _output_file = df_resFileStr[:-len(_trailing_pin)] + f'_start{_PIN_START_INDEX}' + _trailing_pin
            _output_dict = {'EducationGroup': edType, 'beta': opt_params[0], 'nabla': opt_params[1], 'GICx': opt_params[2], 'distance': float(_best_dist)}
        else:
            _output_file = df_resFileStr
            _output_dict = {'EducationGroup' : edType, 'beta' : opt_params[0], 'nabla' : opt_params[1], 'GICx' : opt_params[2]}
        with open(_output_file, mode) as f:
            outStr = repr(_output_dict)
            f.write(outStr+'\n')
            f.close()

        profiler.sample_memory(f"after_{educ_names[edType]}_estimation")

    # Footer with run parameters: only emit when running the full sweep in
    # one process (in single-edtype mode, the wrapper writes the merged
    # footer instead).
    if not _single_edtype:
        with open(df_resFileStr, 'a') as f:
            f.write('\nParameters: R = '+str(round(Rfree_base[0],2))+', CRRA = '+str(round(CRRA,2))
                  +', IncUnemp = '+str(round(IncUnemp,2))+', IncUnempNoBenefits = '+str(round(IncUnempNoBenefits,2))
                  +', Splurge = '+str(Splurge) +'\n')

#%% MC Determinism Test: evaluate at fixed points and save results
if MC_DETERMINISM_TEST:
    import json
    print('\n' + '='*70)
    print('MC DETERMINISM TEST: Evaluating objective function at fixed points')
    print(f'AgentCountTotal = {AgentCountTotal}')
    print('='*70 + '\n')
    
    mc_test_results = {
        'version': '0.17.0',
        'AgentCountTotal': AgentCountTotal,
        'Splurge': Splurge,
        'CRRA': CRRA,
        'Rfree': Rfree_base[0],
        'DiscFacCount': DiscFacCount,
        'evaluations': []
    }
    
    # Test points: the optimizer's initial values for each education type
    test_points = {
        0: {'beta': 0.75, 'nabla': 0.3, 'GICx': 6.0, 'name': 'Dropout'},
        1: {'beta': 0.93, 'nabla': 0.07, 'GICx': 5.0, 'name': 'Highschool'},
        2: {'beta': 0.98, 'nabla': 0.015, 'GICx': 6.0, 'name': 'College'},
    }
    
    for edType in [0, 1, 2]:
        tp = test_points[edType]
        print(f'\n--- Evaluating {tp["name"]} (edType={edType}) ---')
        print(f'    beta={tp["beta"]}, nabla={tp["nabla"]}, GICx={tp["GICx"]}')
        
        t0 = time.time()
        distance = betas_obj_func_educ(
            tp['beta'], tp['nabla'], tp['GICx'], 
            educ_type=edType, print_mode=True
        )
        elapsed = time.time() - t0
        
        # Now extract detailed statistics by re-evaluating internals
        # (The print_mode=True above already printed them, but we need them in structured form)
        # Re-create the agent list to extract stats
        GICfactor = np.exp(tp['GICx']) / (1 + np.exp(tp['GICx']))
        dfs = Uniform(tp['beta'] - tp['nabla'], tp['beta'] + tp['nabla']).discretize(DiscFacCount)
        for thedf in range(DiscFacCount):
            if dfs.atoms[0][thedf] > gic_capped_beta(edType, GICfactor):
                dfs.atoms[0][thedf] = gic_capped_beta(edType, GICfactor)
            elif dfs.atoms[0][thedf] < minBeta:
                dfs.atoms[0][thedf] = minBeta
        
        TypeListNewEduc = []
        n = 0
        for b in range(DiscFacCount):
            AgentCount = int(np.floor(AgentCountTotal * data_EducShares[edType] * dfs.pmv[b]))
            ThisType = deepcopy(BaseTypeList[edType])
            ThisType.AgentCount = AgentCount
            ThisType.DiscFac = dfs.atoms[0][b]
            ThisType.seed = n
            TypeListNewEduc.append(ThisType)
            n += 1
        TypeListAll = AggDemandEconomy.agents
        TypeListAll[edType*DiscFacCount:(edType+1)*DiscFacCount] = TypeListNewEduc
        
        base_dict['Agents'] = TypeListAll
        AggDemandEconomy.agents = TypeListAll
        AggDemandEconomy.solve()
        AggDemandEconomy.reset()
        for agent in AggDemandEconomy.agents:
            agent.initialize_sim()
            agent.AggDemandFac = 1.0
            agent.RfreeNow = 1.0
            agent.CaggNow = 1.0
        AggDemandEconomy.make_history()
        AggDemandEconomy.save_state()
        baseline_commands = ['solve()', 'initialize_sim()', 'simulate()', 'save_state()']
        _mtc(TypeListAll, baseline_commands)
        
        Stats = calc_estim_stats(TypeListAll)
        WealthSharesByEd = calc_wealth_share_by_ed(TypeListAll)
        
        # Collect per-agent state snapshots for detailed comparison
        agent_snapshots = []
        for i, agent in enumerate(TypeListAll):
            snap = {
                'idx': i,
                'AgentCount': int(agent.AgentCount),
                'DiscFac': float(agent.DiscFac),
                'seed': int(agent.seed),
                'mean_aNrm': float(np.mean(agent.state_now['aNrm'])),
                'mean_cNrm': float(np.mean(agent.state_now['cNrm'])),
                'mean_pLvl': float(np.mean(agent.state_now['pLvl'])),
                'mean_mNrm': float(np.mean(agent.state_now['mNrm'])),
                'std_aNrm': float(np.std(agent.state_now['aNrm'])),
            }
            agent_snapshots.append(snap)
        
        eval_result = {
            'educ_type': edType,
            'name': tp['name'],
            'beta': tp['beta'],
            'nabla': tp['nabla'],
            'GICx': tp['GICx'],
            'distance': float(distance),
            'elapsed_sec': elapsed,
            'medianLWPI': [float(x[0]) if hasattr(x, '__len__') else float(x) for x in Stats.medianLWPI],
            'avgLWPI': [float(x) for x in Stats.avgLWPI],
            'LWoPI': [float(x) for x in Stats.LWoPI],
            'LorenzPts': [float(x) for x in Stats.LorenzPts],
            'WealthSharesByEd': [float(x) for x in WealthSharesByEd],
            'discount_factors': dfs.atoms[0].tolist(),
            'agent_counts': [int(np.floor(AgentCountTotal * data_EducShares[edType] * dfs.pmv[b])) for b in range(DiscFacCount)],
            'agent_snapshots': agent_snapshots,
        }
        mc_test_results['evaluations'].append(eval_result)
        
        print(f'    Distance = {distance:.10f}')
        print(f'    Elapsed = {elapsed:.1f}s')
    
    # Also evaluate the population-level objective function at these parameters
    print('\n--- Evaluating population-level objective ---')
    t0 = time.time()
    pop_distance = betas_obj_func(
        [test_points[0]['beta'], test_points[1]['beta'], test_points[2]['beta']],
        [test_points[0]['nabla'], test_points[1]['nabla'], test_points[2]['nabla']],
        [np.exp(test_points[0]['GICx'])/(1+np.exp(test_points[0]['GICx'])),
         np.exp(test_points[1]['GICx'])/(1+np.exp(test_points[1]['GICx'])),
         np.exp(test_points[2]['GICx'])/(1+np.exp(test_points[2]['GICx']))],
        target_option=1, print_mode=True
    )
    pop_elapsed = time.time() - t0
    mc_test_results['population_distance'] = float(pop_distance)
    mc_test_results['population_elapsed_sec'] = pop_elapsed
    
    # Save results to JSON
    mc_output_file = os.path.join(res_dir, 'mc_determinism_test_results.json')
    with open(mc_output_file, 'w') as f:
        json.dump(mc_test_results, f, indent=2)
    print(f'\n[MC DETERMINISM TEST] Results saved to {mc_output_file}')
    print(f'[MC DETERMINISM TEST] Done.')
    sys.exit(0)

#%% Read in estimates and calculate all results:
calcAllResults = True
if os.environ.get('HAFISCAL_SKIP_ESTIMATION', '') == '1':
    calcAllResults = False  # Profile harness also skips results-readback
if os.environ.get('HAFISCAL_EDTYPES', '0,1,2') != '0,1,2':
    # Single-edtype subprocess (run_phase2_parallel.py): skip pop-level
    # results readback; the wrapper calls a final full-population pass after
    # merging all edType results.
    calcAllResults = False
if calcAllResults:
    printResToFile  = True
    
    if IncUnemp == 0.7 and IncUnempNoBenefits == 0.5:
        # Baseline unemployment system: 
        print('Calculating all results for CRRA = '+str(round(CRRA,1))+' and R = ' + str(round(Rfree_base[0],3))+':\n')
        df_resFileStr = res_dir+'/DiscFacEstim_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])
        ar_resFileStr = res_dir+'/AllResults_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])
    else:
        print('Calculating all results for an alternativ unemployment system with IncUnemp = '+str(round(IncUnemp,2))+
              ' and IncUnempNoBenefits = ' + str(round(IncUnempNoBenefits,2))+':\n')
        df_resFileStr = res_dir+'/DiscFacEstim_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])+'_altBenefits'
        ar_resFileStr = res_dir+'/AllResults_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])+'_altBenefits'
    
    if Splurge == 0:
        df_resFileStr = df_resFileStr + '_Splurge0'
        ar_resFileStr = ar_resFileStr + '_Splurge0'
    # ESC-MOD-PHASE3-write: tag both files with interpretation suffix.
    # CDC stays unsuffixed; ESC writes/reads its own _ESC files.
    df_resFileStr = df_resFileStr + _interp_suffix() + '.txt'
    ar_resFileStr = ar_resFileStr + _interp_suffix() + '.txt'
    print('Loading estimates from ' + df_resFileStr + '\n')
    
    if printResToFile:
        # Candidate-routing (QE-baseline freeze): writes `_candidate` sibling
        # unless HAFISCAL_PROMOTE=1. See generated_output.py.
        from generated_output import open_generated
        with open_generated(ar_resFileStr) as resFile: 
            print('Saving all model results in ' + ar_resFileStr + '\n')
            resFile.write('Results for parameters:\n')
            resFile.write('R = '+str(round(Rfree_base[0],2))+', CRRA = '+str(round(CRRA,2))
                  +', IncUnemp = '+str(round(IncUnemp,2))+', IncUnempNoBenefits = '+str(round(IncUnempNoBenefits,2))
                  +', Splurge = '+str(Splurge) +'\n\n')
               
    # Calculate results by education group    
    myEstim = [[],[],[]]
    # Candidate-aware read: prefer a fresh `_candidate` sibling from this
    # pipeline run over the frozen canonical file. See generated_output.py.
    from generated_output import input_path
    betFile = open(input_path(df_resFileStr), 'r')
    readStr = betFile.readline().strip()
    while readStr != '' :
        dictload = eval(readStr)
        edType = dictload['EducationGroup']
        beta = dictload['beta']
        nabla = dictload['nabla']
        GICx = dictload['GICx']
        GICfactor = np.exp(GICx)/(1+np.exp(GICx))
        myEstim[edType] = [beta,nabla,GICx, GICfactor]
        betas_obj_func_educ(beta, nabla, GICx, educ_type = edType, print_mode=True, print_file=printResToFile, filename=ar_resFileStr)
        check_disc_fac_distribution(beta, nabla, GICfactor, edType, print_mode=True, print_file=printResToFile, filename=ar_resFileStr)
        readStr = betFile.readline().strip()
    betFile.close()
    
    # Also calculate results for the whole population
    betas_obj_func([myEstim[0][0], myEstim[1][0], myEstim[2][0]], \
                 [myEstim[0][1], myEstim[1][1], myEstim[2][1]], \
                 [myEstim[0][3], myEstim[1][3], myEstim[2][3]], \
                 target_option = 1, print_mode=True, print_file=printResToFile, filename=ar_resFileStr)

    # ---- Registry hook ----
    # Register this run + its outputs + computed GoF metrics in the SQLite
    # registry. No-op if registry import fails (defensive: never break the
    # estimation pipeline because of registry plumbing).
    try:
        import sys as _sys_reg
        _ha_root_reg = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        if _ha_root_reg not in _sys_reg.path:
            _sys_reg.path.insert(0, _ha_root_reg)
        import _registry as _reg
        import _gof as _gof_mod

        _run_id = _reg.register_run(notes="EstimAggFiscalMAIN.py calcAllResults pass")
        # Register outputs that exist
        if os.path.exists(df_resFileStr):
            _reg.register_output(_run_id, "step2_cal", df_resFileStr)
        if os.path.exists(ar_resFileStr):
            _reg.register_output(_run_id, "step5_allresults", ar_resFileStr)
        # Compute GoF + record metrics
        if os.path.exists(ar_resFileStr):
            _metrics = _gof_mod.compute_all_gof(ar_resFileStr)
            _reg.record_metrics(_run_id, _metrics)
            print("\n[registry] GoF metrics:")
            print(_gof_mod.format_summary(_metrics))
        _reg.mark_run_status(_run_id, "complete")
        print(f"[registry] registered run {_run_id}")
    except Exception as _reg_err:
        print(f"[registry] WARNING: registry hook failed: {_reg_err!r}")


#%%
run_additional_analysis = False

#%%
if run_additional_analysis:
    #betas_obj_func_educ(0.9838941233454087, 0.009553568500479719, 6, educ_type = 2, print_mode=True)

    ar_resFileStr = res_dir + 'DEBUG_checkDiscFacDistribution.txt'
    GICx = 6.0832796965018225
    GICfactor = np.exp(GICx)/(1+np.exp(GICx))
    check_disc_fac_distribution(0.7354184459881328, 0.29783637632458415, GICfactor, edType, print_mode=True, print_file=True, filename=ar_resFileStr)

# d - (0.72, 0.5)        
# h - (0.94, 0.7)



#%%
if run_additional_analysis:
    #%% Read in estimates and save resulting discount factor distributions:
    myEstim = [[],[],[]]
    if IncUnemp == 0.7 and IncUnempNoBenefits == 0.5 and Splurge != 0:
        # Baseline unemployment system: 
        betFile = open(res_dir+'/DiscFacEstim_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])+'.txt', 'r')
    elif IncUnemp == 0.7 and IncUnempNoBenefits == 0.5 and Splurge == 0:
        # Baseline unemployment system: 
        betFile = open(res_dir+'/DiscFacEstim_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])+'_Splurge0.txt', 'r')
    else:
        betFile = open(res_dir+'/DiscFacEstim_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])+'_altBenefits.txt', 'r')
    readStr = betFile.readline().strip()
    while readStr != '' :
        dictload = eval(readStr)
        edType = dictload['EducationGroup']
        beta = dictload['beta']
        nabla = dictload['nabla']
        GICx = dictload['GICx']
        GICfactor = np.exp(GICx)/(1+np.exp(GICx))
        myEstim[edType] = [beta,nabla,GICx,GICfactor]
        readStr = betFile.readline().strip()
    betFile.close()

    if IncUnemp == 0.7 and IncUnempNoBenefits == 0.5 and Splurge != 0:
        # Baseline unemployment system: 
        outFileStr = res_dir+'/DiscFacDistributions_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])+'.txt'
    elif IncUnemp == 0.7 and IncUnempNoBenefits == 0.5 and Splurge == 0:
        # Baseline unemployment system: 
        outFileStr = res_dir+'/DiscFacDistributions_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])+'_Splurge0.txt'
    else:
        outFileStr = res_dir+'/DiscFacDistributions_CRRA_'+str(CRRA)+'_R_'+str(Rfree_base[0])+'_altBenefits.txt'
    # Candidate-routing (QE-baseline freeze): see generated_output.py.
    from generated_output import open_generated as _open_generated
    outFile = _open_generated(outFileStr)
    
    for e in [0,1,2]:
        dfs = Uniform(myEstim[e][0]-myEstim[e][1], myEstim[e][0]+myEstim[e][1]).discretize(DiscFacCount)
        
        # Check GIC:
        for thedf in range(DiscFacCount):
            if dfs.atoms[0][thedf] > gic_capped_beta(e, myEstim[e][3]):
                dfs.atoms[0][thedf] = gic_capped_beta(e, myEstim[e][3])
            elif dfs.atoms[0][thedf] < minBeta:
                dfs.atoms[0][thedf] = minBeta
        theDFs = np.round(dfs.atoms[0],4)
        outStr = repr({'EducationGroup' : e, 'betaDistr' : theDFs.tolist()})
        outFile.write(outStr+'\n')
    outFile.close()
    

#%% Plot of MPCs
if run_additional_analysis:
    mpcs = calc_mpc_by_ed_simple(AggDemandEconomy.agents)
    
    show_plot(range(len(mpcs[0])), np.sort(mpcs[0]))
    plt.xlabel('Agents')
    plt.ylabel('MPCs')
    plt.title('Dropout')
    plt.show()
    
    show_plot(range(len(mpcs[1])), np.sort(mpcs[1]))
    plt.xlabel('Agents')
    plt.ylabel('MPCs')
    plt.title('Highschool')
    plt.show()
    
    show_plot(range(len(mpcs[2])), np.sort(mpcs[2]))
    plt.xlabel('Agents')
    plt.ylabel('MPCs')
    plt.title('College')
    plt.show()

