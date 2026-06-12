"""
Estimation_BetaNablaSplurge.py

This script estimates the beta (discount factor) distribution and splurge factor
to match Norwegian lottery winner consumption data from Fagereng et al.

DESIGN CHOICES:
---------------
**Single splurge common to all consumers.** This estimation imposes a single
varsigma applied identically to every consumer, regardless of education group
or within-group discount-factor type. An earlier exploration allowed
heterogeneous splurge (per education cohort, and as a within-cohort
distribution). The lottery-MPC moments from Fagereng et al. and the SCF
wealth-distribution moments did not provide evidence to reject the null of
a single varsigma. Imposing this restriction reduces the parameter
dimensionality of the joint optimization and tightens identification of
(beta-center, beta-spread). Step 2 (`EstimAggFiscalMAIN.py`) takes this
single varsigma as exogenously given and estimates per-cohort
(beta-center, beta-spread) only. See `Subfiles/Parameterization.tex`
section `sec:splurge` (and the footnote on the "all households have the
same propensity to splurge" assumption) for the corresponding paper-side
discussion of this choice.

HISTORICAL NOTE ON CONSUMER TYPE:
---------------------------------
This code uses KinkedRconsumerType (which allows different interest rates for
borrowing vs saving) rather than the simpler IndShockConsumerType.

History:
- March 2020: Original code by Edmund Crawley used IndShockConsumerType
- July 2020: Ivan Frankovic added "kinkyR functionality" as an experimental
  variation to explore how different borrowing vs saving rates affect results.
  The kinkyR version allowed borrowing (BoroCnstArt = -0.8) with a higher
  borrowing rate (Rboro ~20% annual) vs saving rate (Rsave ~2% annual).
- January 2024: BoroCnstArt was changed to 0, disabling borrowing. With
  BoroCnstArt = 0, agents cannot borrow, so Rboro is never used in practice.
  
Current state: KinkedRconsumerType is retained (rather than reverting to
IndShockConsumerType) to allow future robustness checks where researchers
can enable borrowing by setting BoroCnstArt < 0. To enable borrowing:
    base_params['BoroCnstArt'] = -0.8  # Allow borrowing up to 80% of income
    
With the current settings (BoroCnstArt = 0, Rsave = Rfree), the model is
mathematically equivalent to using IndShockConsumerType with a single
interest rate.
"""

# Import python tools
import sys 
import os
import numpy as np
import random
from copy import deepcopy
import pandas as pd

# Import needed tools from HARK
from HARK.distributions import Uniform, Lognormal
from HARK.utilities import get_percentiles, get_lorenz_shares

# Candidate-routing (QE-baseline freeze): rendered figures/tables are written
# as `_candidate` siblings unless HAFISCAL_PROMOTE=1. See generated_output.py.
_FROM_PANDEMIC_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'FromPandemicCode')
if _FROM_PANDEMIC_DIR not in sys.path:
    sys.path.insert(0, _FROM_PANDEMIC_DIR)
from generated_output import make_figs_generated as make_figs, open_generated
# Use parallel execution (same as 0.14.1) for performance
# NOTE: This means RNG sequences may differ, but final estimated parameters
# should converge to the same values due to optimization
from HARK.core import multi_thread_commands
from scipy.optimize import minimize

# =============================================================================
# OPTIMIZATION: Loky Worker Pool Warmup (0.17.0-loky-warmup branch)
# =============================================================================
# Import the pool warmup utility. Set HARK_WARM_POOL=1 to enable.
# This pre-compiles Numba functions in worker processes, avoiding ~4s cold-start.
# See parallel_warmup.py and numba_jit_overhead_mwe/ for details.
try:
    from parallel_warmup import maybe_warm_pool, is_warmup_enabled
    WARMUP_AVAILABLE = True
except ImportError:
    WARMUP_AVAILABLE = False
    def maybe_warm_pool(*args, **kwargs): pass
    def is_warmup_enabled(): return False
# Add parent directory to path for imports (rng_synchronized_consumer, matplotlib_config)
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# =============================================================================
# RNG-SYNCHRONIZED CONSUMER TYPE (for numerical reproducibility with 0.14.1)
# =============================================================================
# We use RNGSyncKinkedRconsumerType which fully replicates HARK 0.14.1's RNG
# consumption pattern, including:
#   - sim_birth(): Lognormal draws with fresh seeds (not pre-built distributions)
#   - reset_rng(): Synchronizes IncShkDstn seed to match 0.14.1
#   - sim_death(): Matches 0.14.1's RNG consumption during death events
#
# This ensures that simulation results are IDENTICAL to 0.14.1 when using
# the same random seed, which is essential for validation.
#
# NOTE: The solver patch in ConsIndShockModel.py must also be applied for
# the consumption functions to match exactly.
#
# See rng_synchronized_consumer.py for implementation details.
# =============================================================================
from rng_synchronized_consumer import RNGSyncKinkedRconsumerType as KinkedRconsumerType
from SetupParamsCSTW import init_infinite


# CDC-MOD-BUG035: Step-1 agent type with CDC household-bargain asset rule.
# Sibling to AggFiscalModel.AggFiscalType.get_poststates (BUG-031 patch);
# needed for Step-1 estimation simulator state evolution to be CDC-correct
# in the same sense Step-2/5 already are post-BUG-031. See
# BUGS_private/HAFiscal_BUG-035_step1_agent_state_dynamics_not_cdc.md.
class CDCKinkedRConsumerType(KinkedRconsumerType):
    """KinkedR consumer with CDC household-bargain asset rule.

    Identical to KinkedRconsumerType (= RNGSyncKinkedRconsumerType) except
    `get_poststates` applies the CDC household-bargain asset rule

        a_nrm = m_nrm - c_household_nrm
              = m_nrm - [(1 - ς) * cFunc(m) + ς * ξ]

    instead of HARK's default optimizer-only rule a_nrm = m_nrm - cFunc(m).

    Requires `.Splurge` attribute (the current ς guess during the joint
    estimation) to be set on the instance before `simulate()` is called.
    `FagerengObjFunc` sets `BaseType.Splurge = SplurgeEstimate` at the top
    of each evaluation, and `EstTypeList[j].Splurge` inherits via deepcopy.
    """

    def get_poststates(self):
        # CDC household consumption (normalized by pLvl):
        # c_household = (1-ς)·cFunc(m) + ς·ξ
        cNrm_household = ((1.0 - self.Splurge) * self.controls["cNrm"]
                          + self.Splurge * self.shocks["TranShk"])
        # CDC asset rule: a = m - c_household
        self.state_now["aNrm"] = self.state_now["mNrm"] - cNrm_household
        self.state_now["aLvl"] = self.state_now["aNrm"] * self.state_now["pLvl"]
        # Preserve HARK's standard PlvlAgg update if the parent uses it
        if hasattr(self, "PermShkAggNow") and "PlvlAgg" in (self.state_prev or {}):
            self.state_now["PlvlAgg"] = self.state_prev["PlvlAgg"] * self.PermShkAggNow


# for plotting
import matplotlib.pyplot as plt
from matplotlib_config import show_plot     # located in the parent directory

# for output
cwd             = os.getcwd()
folders         = cwd.split(os.path.sep)
top_most_folder = folders[-1]
if top_most_folder == 'Target_AggMPCX_LiquWealth':
    Abs_Path = cwd
else:
    Abs_Path = cwd + '/Code/HA-Models/Target_AggMPCX_LiquWealth'

# Set key problem-specific parameters
TypeCount = 7       # Number of consumer types with heterogeneous discount factors
AdjFactor = 1.0     # Factor by which to scale all of MPCs in Table 9
T_kill    = 400     # Don't let agents live past this age (expressed in quarters)
drop_corner = True  # If True, ignore upper left corner when calculating distance

# Set standard HARK parameter values (from stickyE paper)
base_params = deepcopy(init_infinite)
base_params['LivPrb']       = [0.995]       #from stickyE paper
base_params['Rfree']        = 1.015         #from stickyE paper
base_params['Rsave']        = 1.015         #from stickyE paper
base_params['Rboro']        = 1.025         #from stickyE paper
base_params['PermShkStd']   = [0.001**0.5]  #from stickyE paper
base_params['TranShkStd']   = [0.132**0.5]  #from stickyE paper
base_params['T_age']        = 400           # Kill off agents if they manage to achieve T_kill working years
base_params['AgentCount']   = 5000          # Number of agents per instance of IndShockConsType
base_params['pLogInitMean'] = np.log(23.72) 
base_params['T_sim']        = 800


Parametrization = 'NOR' 
if  Parametrization == 'NOR':    
    base_params['LivPrb']       = [1-1/160]     
    base_params['Rfree']        = 1.02**0.25
    # Interest rate settings for KinkedRconsumerType:
    # - Rsave: Interest rate earned on positive assets (set = Rfree for baseline)
    # - Rboro: Interest rate paid on debt (only matters if BoroCnstArt < 0)
    # With BoroCnstArt = 0, agents cannot borrow so Rboro has no effect.
    base_params['Rsave']        = 1.02**0.25    # Same as Rfree (no kink when saving)
    base_params['Rboro']        = 1.137**0.25   # ~13.7% annual (only used if borrowing enabled)
    base_params['pLogInitMean'] = 0 
    base_params['UnempPrb']     = 0.044
    base_params['IncUnemp']     = 0.60
    base_params['PermShkStd']   = [0.001**0.5] #from Crawley,Moll,Tretvoll
    base_params['TranShkStd']   = [0.132**0.5]
    # Borrowing constraint: 0 = no borrowing allowed (baseline)
    # To check robustness with borrowing, set to negative value, e.g.:
    #   base_params['BoroCnstArt'] = -0.8  # Allow borrowing up to 80% of perm income
    # When BoroCnstArt < 0, agents can borrow and will face Rboro on debt.
    base_params['BoroCnstArt']  = 0  # No borrowing (was -0.8 before Jan 2024)
    base_params['PermGroFacAgg']= 1.01**0.25     
    base_params['CRRA']         = 2.0
    base_params['T_age']        = None
    
    
    

## TARGETS
# implements (eq:targets) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
# (the calibration targets the spec lists in §3: K/Y ≈ 6.60, four Lorenz percentiles
#  20/40/60/80, and the aggregate Fagereng-Holm-Natvik lottery MPC at horizons 0–4)

# Define the MPC targets from Fagereng et al Table 9; element i,j is lottery quartile i, deposit quartile j
MPC_target_base = np.array([[1.047, 0.745, 0.720, 0.490],
                            [0.762, 0.640, 0.559, 0.437],
                            [0.663, 0.546, 0.390, 0.386],
                            [0.354, 0.325, 0.242, 0.216]])
MPC_target = AdjFactor*MPC_target_base

# Define the agg MPCx targets from Fagereng et al. Figure 2; first element is same-year response, 2nd element, t+1 response etcc
Agg_MPCX_target = np.array([0.5056845, 0.1759051, 0.1035106, 0.0444222, 0.0336616])

# Define the four lottery sizes, in thousands of USD; these are eyeballed centers/averages
# 5th element is used as rep. lottery win to get at aggregate MPC / MPCX
lottery_size_USD = np.array([1.625, 3.3741, 7.129, 40.0, 7.129])
lottery_size_NOK = lottery_size_USD * (10/1.1) #in Fagereng et al it is mentioned that 1000 NOK = 110 USD
lottery_size = lottery_size_NOK / (270/4); # Income after tax according to Table 1 is approx. 24k USD.
RandomLotteryWin = True #if True, then the 5th element will be replaced with a random lottery size win draw from the 1st to 4th element for each agent

# Liquid wealth target from US
lorenz_target = np.array([0.029, 0.354, 1.84, 7.42])/100
KY_target = 6.60




#%%  Interpretation-specific helpers (extracted from inline closures during the
# CDC/ESC configurable refactor; see plans/20260426-0706h_pre-refactor-prep.md
# item 2a and plans/20260425-2137h_cdc-esc-configurable-refactor.md — both DONE).
# CURRENT REALITY (2026-06-11): the ESC sibling helpers promised in the
# docstrings below (`_wealth_under_esc`, `_lottery_consumption_under_esc`) were
# never built. The CDC wealth/lottery path below runs UNCONDITIONALLY under both
# interpretations (only the agent TYPE dispatches on HAFISCAL_INTERPRETATION);
# whether that is intended under ESC is an open owner-triage question — see
# Code/HA-Models/docs/COMMENT_AUDIT_FINDINGS.md (orchestration partition, row 19).

# implements (eq:budget-CDC) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
def _wealth_under_cdc(agent, splurge):
    """CDC-MOD-BUG032: splurge-in-budget wealth correction under the CDC household-bargain reading.

    Under (eq:budget-CDC) of models_CDC_and_ESC.md §4.2 (alias: (CDC-1)):
        a_actual = m - c_actual = m - (1-ς)·cFunc(m) - ς·y
                                = aLvl_HARK - ς·pLvl·(TranShk - cNrm).

    HARK's state_now["aLvl"] = pLvl·(mNrm - cNrm) = aLvl_HARK. Correction
    applies a ς·(y - cFunc)·pLvl shift: agents who would under-spend
    (cNrm < TranShk) have LESS actual wealth (they forced extra spending
    via splurge); agents who over-spend (cNrm > TranShk) have MORE.

    See plans/20260425-2102h_cdc-implementation-map.md row 32.2. The future
    ESC version (planned in plans/20260425-2137h_cdc-esc-configurable-refactor.md
    Phase B) will be a sibling helper `_wealth_under_esc(agent, splurge)`
    returning `(1 - splurge) * agent.state_now["aLvl"]` instead.
    """
    aLvl_hark = agent.state_now["aLvl"]
    # cNrm may live in controls or state_now depending on HARK type
    cNrm = agent.controls.get("cNrm", agent.state_now.get("cNrm"))
    return aLvl_hark - splurge * agent.state_now["pLvl"] * \
        (agent.shocks["TranShk"] - cNrm)


# implements (eq:total-CDC) and (eq:budget-CDC) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
def _lottery_consumption_under_cdc(cFunc, m_base, m_lottery, splurge, xi_hark, TotIncNrm):
    """CDC-MOD-BUG032: splurge-in-budget lottery-MPC formula under the CDC household-bargain reading.

    Both baseline and lottery trajectories implement (eq:total-CDC) for the
    consumption side and (eq:budget-CDC) for the asset side (per
    models_CDC_and_ESC.md §4.1-4.2; aliases (CDC-1)):
        c = (1 - ς)·cFunc(m) + ς·income       — (eq:total-CDC)
        a = m - c                              — (eq:budget-CDC)

    cFunc is evaluated at the original (pre-splurge) market resources because
    the HARK solver is splurge-unaware. Under splurge-in-budget, the asset
    update subtracts the realized weighted consumption (CDC-1). See
    BUGS_private/HAFiscal_BUG-032_lottery_splurge_formula.md.

    The future ESC version (planned in
    plans/20260425-2137h_cdc-esc-configurable-refactor.md Phase B) will be a
    sibling `_lottery_consumption_under_esc(...)` that evaluates cFunc at
    m_opt = m / (1-ς) (per-Optimizer normalization) and tracks the Optimizer's
    a, not household-total a.

    Returns (c_base_nrm, a_base_nrm, c_actu_nrm, a_actu_nrm) — all normalized
    by pLvl. Caller multiplies by pLvl for level versions.
    """
    c_base_nrm = (1 - splurge) * cFunc(m_base) + splurge * xi_hark
    a_base_nrm = m_base - c_base_nrm
    c_actu_nrm = (1 - splurge) * cFunc(m_lottery) + splurge * TotIncNrm
    a_actu_nrm = m_lottery - c_actu_nrm
    return c_base_nrm, a_base_nrm, c_actu_nrm, a_actu_nrm


#%%  Objective function

def FagerengObjFunc(SplurgeEstimate,center,spread,verbose=False,estimation_mode=True,target='AGG_MPC',investigate=False):
    '''
    Objective function for the quick and dirty structural estimation to fit
    Fagereng, Holm, and Natvik's Table 9 results with a basic infinite horizon
    consumption-saving model (with permanent and transitory income shocks).

    Parameters
    ----------
    center : float
        Center of the uniform distribution of discount factors.
    spread : float
        Width of the uniform distribution of discount factors.
    verbose : bool
        When True, print to screen MPC table for these parameters.  When False,
        print (center, spread, distance).

    Returns
    -------
    distance : float
        Euclidean distance between simulated MPCs and (adjusted) Table 9 MPCs.
    '''
    
    # Give our consumer types the requested discount factor distribution
    for j in range(TypeCount):
        EstTypeList[j].reset_rng()
    random.seed(55)
    beta_set = Uniform(bot=center-spread, top=center+spread).discretize(TypeCount).atoms[0]
    
    # Taper off toward the growth impatience condition 
    GICmaxBeta = (1-base_params['LivPrb'][0]) + (base_params['PermGroFacAgg']**base_params['CRRA'])/base_params['Rfree']
    minBeta = 0.01
    for thedf in range(TypeCount):
        taper_threshold = 0.01
        if beta_set[thedf] > GICmaxBeta-taper_threshold:
            beta_set[thedf] = GICmaxBeta-taper_threshold + (np.arctan((beta_set[thedf] - GICmaxBeta + taper_threshold)/taper_threshold))*taper_threshold/np.pi*2
        elif beta_set[thedf] < minBeta:
            beta_set[thedf] = minBeta
    
      
    
    for j in range(TypeCount):
        EstTypeList[j].DiscFac = beta_set[j]
        # CDC-MOD-BUG035: set the current candidate ς on each agent so the
        # CDCKinkedRConsumerType.get_poststates override uses the right value.
        # Each evaluation of FagerengObjFunc tries a different SplurgeEstimate;
        # the agents' simulator dynamics must reflect the current candidate.
        EstTypeList[j].Splurge = SplurgeEstimate

    # Solve and simulate all consumer types, then gather their wealth levels
    # HARK 0.17.0: unpack_cFunc() no longer exists - cFunc is directly accessible from solution
    multi_thread_commands(EstTypeList,['solve()','initialize_sim()','simulate()'])
    # Wealth correction = CDC-MOD-BUG032 anchor; the ` _wealth_under_cdc`
    # helper at module level encapsulates the splurge-in-budget rule. ESC
    # version (planned) will be a sibling helper that multiplies by (1-ς).
    # See plans/20260425-2102h_cdc-implementation-map.md row 32.2.
    WealthNow = np.concatenate([_wealth_under_cdc(ThisType, SplurgeEstimate) for ThisType in EstTypeList])


    # Get wealth quartile cutoffs and distribute them to each consumer type
    quartile_cuts = get_percentiles(WealthNow,percentiles=[0.25,0.50,0.75])
    wealth_list = np.array([])
    for ThisType in EstTypeList:
        a_actual = _wealth_under_cdc(ThisType, SplurgeEstimate)
        WealthQ = np.zeros(ThisType.AgentCount,dtype=int)
        for n in range(3):
            WealthQ[a_actual > quartile_cuts[n]] += 1
        ThisType.WealthQ = WealthQ
        wealth_list = np.concatenate((wealth_list, a_actual))
            

         
    # Get lorenz curve
    order = np.argsort(WealthNow)
    WealthNow_sorted = WealthNow[order]
    Lorenz_Data = get_lorenz_shares(WealthNow_sorted,percentiles=np.arange(0.01,1.00,0.01),presorted=True) 
    Lorenz_Data = np.hstack((np.array(0.0),Lorenz_Data,np.array(1.0))) 
    Wealth_adj = WealthNow_sorted - WealthNow_sorted[0] # add lowest possible value to everyone
    Lorenz_Data_Adj = get_lorenz_shares(Wealth_adj,percentiles=np.arange(0.01,1.00,0.01),presorted=True) 
    Lorenz_Data_Adj = np.hstack((np.array(0.0),Lorenz_Data_Adj,np.array(1.0))) 
    lorenz_Model = np.array([Lorenz_Data_Adj[20], Lorenz_Data_Adj[40], Lorenz_Data_Adj[60], Lorenz_Data_Adj[80]])
    
    # Get K to Y
    # implements (eq:KY-CDC) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
    # The K/Y aggregator is the second step of a two-step CDC pattern:
    #   step 1 (line ~244-248):  WealthNow = [_wealth_under_cdc(t, ς) for t in EstTypeList]
    #                            implements (eq:budget-CDC) rearranged for wealth
    #   step 2 (here):            CapAgg = Σ WealthNow ;  K/Y = CapAgg / Σ (pLvl·TranShk)
    #                            implements (eq:KY-CDC) — the K/Y aggregator under CDC
    # The interpretive choice (CDC vs ESC) is encapsulated in step 1; this sum
    # is then interpretation-agnostic (just summing whatever the chosen wealth
    # rule produced). See plans/20260425-2102h_cdc-implementation-map.md row 32.2.
    CapAgg      = np.sum(WealthNow)
    TransNow    = np.concatenate([ThisType.shocks["TranShk"] for ThisType in EstTypeList])
    permNow     = np.concatenate([ThisType.state_now["pLvl"] for ThisType in EstTypeList])
    IncAgg      = np.sum(permNow*TransNow)
    KY_Model    = CapAgg/IncAgg
    
################## Can return K/Y here
    if target != "Liqu_Wealth_plusKY":

        N_Quarter_Sim = 20; # Needs to be dividable by four
        N_Year_Sim = int(N_Quarter_Sim/4)
        N_Lottery_Win_Sizes = 5 # 4 lottery size bin + 1 representative one for agg MPCX
    
        
        EmptyList = [[],[],[],[],[]]
        MPC_set_list = [deepcopy(EmptyList),deepcopy(EmptyList),deepcopy(EmptyList),deepcopy(EmptyList)]
        MPC_Lists    = [deepcopy(MPC_set_list),deepcopy(MPC_set_list),deepcopy(MPC_set_list),deepcopy(MPC_set_list),deepcopy(MPC_set_list)]    
        # additional list for 5th Lottery bin, just need for elements for four years
        MPC_List_Add_Lottery_Bin = EmptyList
        
        MPC_this_type = np.zeros((TypeCount, ThisType.AgentCount,N_Lottery_Win_Sizes,N_Year_Sim)) #Empty array, MPC for each Lottery size and agent
            
        for type_num, ThisType in zip(range(TypeCount), EstTypeList):
            # HARK 0.17.0: Reset simulation index to allow additional simulate() calls
            # The initial simulate() ran for T_sim periods; reset to allow MPC calculation
            ThisType.t_sim = 0
            
            c_base = np.zeros((ThisType.AgentCount,N_Quarter_Sim))                        #c_base (in case of no lottery win) for each quarter
            c_base_Lvl = np.zeros((ThisType.AgentCount,N_Quarter_Sim))                    #same in levels
            a_base = np.zeros((ThisType.AgentCount,N_Quarter_Sim))                        #a_base: splurge-in-budget-consistent baseline assets (no lottery ever)
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
                

            for period in range(N_Quarter_Sim): #Simulate for 4 quarters as opposed to 1 year
                
                # Simulate forward for one quarter (draws shocks; HARK's internal asset
                # update uses a = m - cFunc(m), which we ignore — splurge-in-budget requires us
                # to track a_base and a_actu manually with a = m - c_actual.)
                ThisType.simulate(1)

                xi_hark = ThisType.shocks["TranShk"]
                psi_hark = ThisType.shocks["PermShk"]
                pLvl_now = ThisType.state_now["pLvl"]

                k = 4; # do not loop to save time
                Llvl = lottery_size[k]*LotteryWin[:,period]

                if RandomLotteryWin and k == 5:
                    for i in range(ThisType.AgentCount):
                        Llvl[i] = lottery_size[random.randint(0,3)]*LotteryWin[i,period]
                        if LotteryWin[i,period]==1 and i==0:
                            print(Llvl[i])

                Lnrm = Llvl/pLvl_now
                TotIncNrm = xi_hark + Lnrm  # total income this period (splurge applies to all of it)

                if period == 0:
                    # Period 0: initialize from HARK's post-init m (= a_initial*R/psi_0 + xi_0)
                    m_base = ThisType.state_now["mNrm"]
                    m_lottery = m_base + Lnrm
                else:
                    T_hist[:,period] = xi_hark
                    P_hist[:,period] = psi_hark
                    # Death: reset both baseline and lottery-path a_prev for dead agents
                    for i_agent in range(ThisType.AgentCount):
                        if xi_hark[i_agent] == 1.0:
                            a_base[i_agent,period-1] = np.exp(base_params['kLogInitMean'])
                            a_actu[i_agent,period-1,k] = np.exp(base_params['kLogInitMean'])
                    R_kink_base = np.where(a_base[:,period-1] < 0, base_params['Rboro'], base_params['Rsave'])
                    R_kink_actu = np.where(a_actu[:,period-1,k] < 0, base_params['Rboro'], base_params['Rsave'])
                    m_base = a_base[:,period-1]*R_kink_base/psi_hark + xi_hark
                    m_lottery = a_actu[:,period-1,k]*R_kink_actu/psi_hark + xi_hark + Lnrm

                # CDC-MOD-BUG032 [central anchor]. The lottery-MPC formula
                # under CDC is encapsulated in `_lottery_consumption_under_cdc`
                # (module-level helper). See plans/20260425-2102h_cdc-implementation-map.md
                # row 32.5 and BUGS_private/HAFiscal_BUG-032_lottery_splurge_formula.md.
                # ESC version (planned) will be a sibling helper.
                cFunc = ThisType.solution[0].cFunc
                c_base[:,period], a_base[:,period], c_actu[:,period,k], a_actu[:,period,k] = \
                    _lottery_consumption_under_cdc(cFunc, m_base, m_lottery, SplurgeEstimate, xi_hark, TotIncNrm)
                c_base_Lvl[:,period] = c_base[:,period] * pLvl_now
                c_actu_Lvl[:,period,k] = c_actu[:,period,k] * pLvl_now
                    
                if period%4 + 1 == 4: #if we are in the 4th quarter of a year
                    year = int((period+1)/4)
                    c_actu_Lvl_year = c_actu_Lvl[:,(year-1)*4:year*4,k]
                    c_base_Lvl_year = c_base_Lvl[:,(year-1)*4:year*4]
                    MPC_this_type[type_num,:,k,year-1] = (np.sum(c_actu_Lvl_year,axis=1) - np.sum(c_base_Lvl_year,axis=1))/(lottery_size[k])
                        
            
            # Sort the MPCs into the proper MPC sets
            for q in range(4):
                these = ThisType.WealthQ == q
                for k in range(N_Lottery_Win_Sizes):
                    for y in range(N_Year_Sim):
                        MPC_Lists[k][q][y].append(MPC_this_type[type_num,these,k,y])
                        
            # sort MPCs for addtional Lottery bin
            for y in range(N_Year_Sim):
                MPC_List_Add_Lottery_Bin[y].append(MPC_this_type[type_num,:,4,y])

                
        #Create a list of wealth and MPCs
        MPC_list = np.array([])
        for type_num, ThisType in zip(range(TypeCount), EstTypeList):
            MPC_list = np.concatenate((MPC_list, MPC_this_type[type_num, :, 4, 0] ))
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
        simulated_MPC_means_smoothed = np.zeros(4)
        simulated_MPC_means_smoothed[0] = np.average(sorted_wealth_MPC[1],weights=quartile1_weights)
        simulated_MPC_means_smoothed[1] = np.average(sorted_wealth_MPC[1],weights=quartile2_weights)
        simulated_MPC_means_smoothed[2] = np.average(sorted_wealth_MPC[1],weights=quartile3_weights)
        simulated_MPC_means_smoothed[3] = np.average(sorted_wealth_MPC[1],weights=quartile4_weights)
        
        #if estimation_mode==False or target == 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC':     
        # Calculate average within each MPC set
        simulated_MPC_means = np.zeros((N_Lottery_Win_Sizes,4,N_Year_Sim))
        for k in range(N_Lottery_Win_Sizes):
            for q in range(4):
                for y in range(N_Year_Sim):
                    MPC_array = np.concatenate(MPC_Lists[k][q][y])
                    simulated_MPC_means[k,q,y] = np.mean(MPC_array)
                    
        # Calculate aggregate MPC and MPCx
        simulated_MPC_mean_add_Lottery_Bin = np.zeros((N_Year_Sim))
        for y in range(N_Year_Sim):
            MPC_array = np.concatenate(MPC_List_Add_Lottery_Bin[y])
            simulated_MPC_mean_add_Lottery_Bin[y] = np.mean(MPC_array)
                
        # Calculate Euclidean distance between simulated MPC averages and Table 9 targets
        
       
        # MPC for representative lottery win (k=4), which corresponds to third row in MPC_target
        diff_MPC = simulated_MPC_means_smoothed - MPC_target[2,:] 
        distance_MPC = 0.1*np.sum((diff_MPC)**2) 
          
        diff_Agg_MPC = simulated_MPC_mean_add_Lottery_Bin - Agg_MPCX_target
        distance_Agg_MPC = np.sum((diff_Agg_MPC)**2)     
        distance_Agg_MPC_24 = np.sum((diff_Agg_MPC[2:4])**2)
        distance_Agg_MPC_01 = np.sum((diff_Agg_MPC[0:1])**2)
    else:
        distance_MPC = 0
        diff_Agg_MPC = 0
        distance_Agg_MPC = 0
        distance_Agg_MPC_24 = 0
        distance_Agg_MPC_01 = 0
        simulated_MPC_means = 0
        simulated_MPC_mean_add_Lottery_Bin = 0
        c_actu_Lvl = 0
        c_base_Lvl = 0
        LotteryWin = 0
        
        
        
    diff_lorenz = lorenz_Model - lorenz_target
    distance_lorenz = np.sum((diff_lorenz)**2)
    
    distance_KY = 1.0*((KY_target - KY_Model)/KY_target)**2 
    

    if target == 'MPC':
        distance = distance_MPC + distance_Agg_MPC
    elif target == 'AGG_MPC':
        distance = distance_Agg_MPC
    elif target == 'AGG_MPC_234':
        distance = distance_Agg_MPC_24
    elif target == 'MPC_plus_AGG_MPC_1':
        distance = distance_MPC + distance_Agg_MPC_01
    elif target == 'AGG_MPC_plus_Liqu_Wealth':
        distance = distance_Agg_MPC + distance_lorenz
    elif target == 'AGG_MPC_plus_Liqu_Wealth_plusKY':
        distance = distance_Agg_MPC + distance_lorenz + distance_KY
    elif target == 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC':
        distance = distance_MPC + distance_Agg_MPC + distance_lorenz + distance_KY
    elif target == "Liqu_Wealth_plusKY":
        distance = distance_lorenz + distance_KY
    elif target == "test":
        distance = distance_MPC
        
    if estimation_mode==False:   
        print(distance_Agg_MPC,distance_lorenz,distance_KY)
        
    if verbose:
        print(simulated_MPC_means)
        print(simulated_MPC_means_smoothed)
    else:
        print (SplurgeEstimate, center, spread, distance)
        
    if investigate:
        print("distance_MPC", distance_MPC) 
        print("distance_Agg_MPC", distance_Agg_MPC)
        print("distance_lorenz", distance_lorenz)
        print("distance_KY", distance_KY)
        print (beta_set)
        
    if investigate:
        # Per-DF-group K/Y for diagnostic printing. Note: this sums HARK's
        # raw aLvl (no splurge-in-budget correction), unlike the production
        # K/Y at line ~303 which sums the CDC-corrected WealthNow. The
        # two will differ by ~ς·(y - cFunc) per agent; for whole-population
        # comparisons use the production CapAgg/IncAgg instead. (Investigate
        # is debug-only; not load-bearing for the published estimation.)
        for j in range(TypeCount):
            CapAggj = np.sum(EstTypeList[j].state_now["aLvl"])
            permNowj = EstTypeList[j].state_now["pLvl"]
            TransNowj = EstTypeList[j].shocks["TranShk"]
            KY_Modelj = CapAggj/np.sum(permNowj*TransNowj)
            print("K/Y for DF group ", str(j), ": ",  KY_Modelj)
        print("K/Y for whole pop : ",  KY_Model)
        print("")
        
    if estimation_mode:
        return distance
    else:
        Output = dict()
        Output['distance'] = distance
        Output['distance_MPC'] = distance_MPC
        Output['distance_Agg_MPC'] = distance_Agg_MPC
        Output['distance_lorenz'] = distance_lorenz
        Output['distance_KY'] = distance_KY
        Output['simulated_MPC_means_smoothed'] = simulated_MPC_means_smoothed
        Output['simulated_MPC_mean_add_Lottery_Bin'] = simulated_MPC_mean_add_Lottery_Bin
        Output['c_actu_Lvl'] = c_actu_Lvl
        Output['c_base_Lvl'] = c_base_Lvl
        Output['LotteryWin'] = LotteryWin
        Output['Lorenz_Data'] = Lorenz_Data
        Output['Lorenz_Data_Adj'] = Lorenz_Data_Adj
        Output['KY_Model'] = KY_Model
        return Output


def save_betanabla_res_txt(filename,res):
    with open(Abs_Path+filename, 'w') as f:
        str1 = repr(res)
        f.write(str1)
        f.close
        
def load_betanabla_res_txt(filename):
    f = open(Abs_Path+filename, 'r')
    if f.mode=='r':
        contents= f.read()
    dictload= eval(contents)
    splurge = dictload['splurge']
    beta    = dictload['beta']
    nabla   = dictload['nabla']
    return [splurge,beta,nabla]


def find_Opt(target='', startpoint = [0.27,0.96,0.03], check_maximum = False):
    
    bounds = [(0.0,0.9),(0.7,1.1),(0.0,0.4)]
        
    f_temp = lambda x : FagerengObjFunc(x[0],x[1],x[2],target=target)
    #opt = minimizeNelderMead(f_temp, startpoint2, verbose=1, xtol=0.001, ftol=0.001)
    opt_output = minimize(f_temp, startpoint,method="Powell", bounds =bounds)
    opt = opt_output.x
    obs = opt_output.fun
    beta = opt[1]
    nabla = opt[2]
    print('Finished estimating')
    print('Optimal splurge is ' + str(opt[0]) )
    print('Optimal (beta,nabla) is ' + str(beta) + ',' + str(nabla))
    
    if check_maximum:
        check_start = [opt[0],opt[2]]
        check_obs = [0.0, 0.0]
        for i,deviation in zip(range(2), [-0.0001, 0.0001]):
            f_temp = lambda y : FagerengObjFunc(y[0],opt[1]+deviation,y[1],target=target)
            check_opt = minimize(f_temp, check_start,method="Powell", bounds = [(0.0,0.9),(0.0,0.4)])
            check_obs[i] = check_opt.fun
        print("Objective around minimum:")
        print([check_obs[0], obs, check_obs[1]])
        if check_obs[0]<obs or check_obs[1] < obs :
            print("Didn't find minimum - check what is going on")
            return {'splurge' : opt[0], 'beta' : beta, 'nabla': nabla, 'Error': 'Not a maximum'}
        else:
            print("Local minimum check passed")
    
    return {'splurge' : opt[0], 'beta' : beta, 'nabla': nabla}

def find_Opt_splurge0(target='', startpoint = [0.96,0.03], check_maximum = False):
        

    f_temp = lambda x : FagerengObjFunc(0,x[0],x[1], target=target)
    opt_output = minimize(f_temp, startpoint,method="Powell", bounds = [(0.7,1.01),(0.0,0.4)])
    opt = opt_output.x
    obs = opt_output.fun
    beta = opt[0]
    nabla = opt[1]
    print('Optimal (beta,nabla) is ' + str(beta) + ',' + str(nabla)) 
    
    if check_maximum:
        check_start = [opt[1]]
        check_obs = [0.0, 0.0]
        for i,deviation in zip(range(2), [-0.0001, 0.0001]):
            f_temp = lambda y : FagerengObjFunc(0,opt[0]+deviation,y[0],target=target)
            check_opt = minimize(f_temp, check_start,method="L-BFGS-B", bounds = [(0.0,0.4)])
            check_obs[i] = check_opt.fun
            print([opt[0]+deviation,check_opt.x,check_opt.fun])
        print("Objective around minimum:")
        print([check_obs[0], obs, check_obs[1]])
        if check_obs[0]<obs or check_obs[1] < obs :
            print("Didn't find minimum - check what is going on")
            return {'splurge' : 0, 'beta' : beta, 'nabla': nabla, 'Error': 'Not a maximum'}
        else:
            print("Local minimum check passed")
    
    return {'splurge' : 0, 'beta' : beta, 'nabla': nabla}


# Make several consumer types to be used during estimation
# CDC-MOD-BUG035 + ESC-MOD-BUG035: Step-1 simulator agent type dispatched by
# HAFISCAL_INTERPRETATION. CDC uses CDCKinkedRConsumerType (subclass with CDC
# household-bargain get_poststates override — sibling fix to AggFiscalType's
# BUG-031 patch on the Step-2/5 side). ESC uses the stock KinkedRconsumerType
# (RNGSyncKinkedRconsumerType) with the optimizer-per-capita asset rule, which
# matches the pre-BUG-035 behavior. The .Splurge attribute is set in
# FagerengObjFunc per-evaluation; deepcopy in EstTypeList propagates it.
from _interpretation import get_interpretation
if get_interpretation() == 'CDC':
    BaseType = CDCKinkedRConsumerType(**base_params)
else:  # ESC
    BaseType = KinkedRconsumerType(**base_params)
# =============================================================================
# OPTIMIZATION: Disable history tracking to reduce memory usage (0.17.0-loky-warmup)
# 0.17.0 defaults to tracking ['aNrm', 'cNrm', 'mNrm', 'pLvl'] which uses ~32MB/agent
# Setting track_vars=[] reduces memory by 60% and prevents Loky worker recycling
# =============================================================================
BaseType.track_vars = []
EstTypeList = []
for j in range(TypeCount):
    EstTypeList.append(deepcopy(BaseType))
    EstTypeList[-1].seed = j




#%% Estimation
Run_estimation      = True
Run_SplurgeZero     = False  # splurge-in-budget overnight: skip Splurge=0 to save time

RunLoopofStarpoints = False 
# Running the Loop of startpoints shows that that the algorithm converges to the same
# solution independent of startpoint and thus strongly suggests that the global minimum was found

    
if Run_estimation:
    # =========================================================================
    # OPTIMIZATION: Pre-warm Loky pool (0.17.0-loky-warmup branch)
    # =========================================================================
    # Warming the pool pre-compiles Numba in workers, avoiding ~4s cold-start.
    # Enable with: export HARK_WARM_POOL=1
    # Without warmup: first call ~4s, subsequent ~0.3s
    # With warmup: all calls ~0.3s (warmup cost ~4s paid once upfront)
    # IMPORTANT: num_agents must match TypeCount for proper worker pool reuse!
    if WARMUP_AVAILABLE:
        maybe_warm_pool(KinkedRconsumerType, num_agents=TypeCount, verbose=True)
    # =========================================================================
    
    print("RUNNING RUN KY AND INIT MPC ESTIMATION")
    target = 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC'
    
    if RunLoopofStarpoints:
        # Loop over starting points with splurge in (0.10,0.3,0.5), beta in (0.85, 0.925, 1) and nabla in (0.05, 0.10)
        startpoints = [ [0.10, 0.85, 0.05],#
                        [0.10, 0.85, 0.10],
                        [0.10, 0.925, 0.05],#
                        [0.10, 0.925, 0.10],
                        [0.10, 1, 0.05],
                        [0.10, 1, 0.10],
                        [0.30, 0.85, 0.05],#
                        [0.30, 0.85, 0.10],
                        [0.30, 0.925, 0.05],#
                        [0.30, 0.925, 0.10],
                        [0.30, 1, 0.05],
                        [0.30, 1, 0.10],
                        [0.50, 0.85, 0.05],#
                        [0.50, 0.85, 0.10],
                        [0.50, 0.925, 0.05],
                        [0.50, 0.925, 0.10],
                        [0.50, 1, 0.05],
                        [0.50, 1, 0.10]]
    else:
        startpoints = [ [0.24906992981618237, 0.9675474591463475, 0.05782806961924406] ]
    
    for i,startpoint in enumerate(startpoints):
        print("Startpoint run no. ",i+1)
        print("Startpoint used: ", startpoint)

        
        if RunLoopofStarpoints:
            filename = '/Result_AllTarget_startpoint'+str(i+1)+'.txt'
        else:
            filename = '/Result_AllTarget.txt'  
        res = find_Opt(target=target, startpoint=startpoint)   
        save_betanabla_res_txt(filename,res)
        

if Run_SplurgeZero:
    print("RUNNING RUN KY AND INIT MPC ESTIMATION, SPLURGE = 0")
    target = 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC'
    
    if RunLoopofStarpoints:
        # Loop over starting points with beta in (0.85, 0.925, 1) and nabla in (0.05, 0.10, 0.20)
        startpoints = [ [0.00, 0.85, 0.05],
                        [0.00, 0.85, 0.10],
                        [0.00, 0.85, 0.20],
                        [0.00, 0.925, 0.05],
                        [0.00, 0.925, 0.10],
                        [0.00, 0.925, 0.20],
                        [0.00, 1, 0.05],
                        [0.00, 1, 0.10],
                        [0.00, 1, 0.20]]
    else:
        startpoints = [ [0, 0.9215203827041509, 0.11625829523973752] ]
        
    for i,startpoint in enumerate(startpoints):
        print("Startpoint run no. ",i+1)
        print("Startpoint used: ", startpoint)
    
        
        if RunLoopofStarpoints:
            filename = '/Result_AllTarget_Splurge0_startpoint'+str(i+1)+'.txt'  
        else:
            filename = '/Result_AllTarget_Splurge0.txt'  
        res = find_Opt_splurge0(target=target, startpoint=startpoint[1:3])  
        save_betanabla_res_txt(filename,res)

#%% Output results for paper

Plot_Output = True
if Plot_Output:
    target = 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC'
    # Splurge=0 solution 
    [splurge,beta,nabla] = load_betanabla_res_txt('/Result_AllTarget_Splurge0.txt')
    Splurge0_Sol=FagerengObjFunc(splurge,beta,nabla,estimation_mode=False,target=target)
    
    # Splurge>0 solution
    [splurge,beta,nabla] = load_betanabla_res_txt('/Result_AllTarget.txt')
    SplurgeNot0_Sol=FagerengObjFunc(splurge,beta,nabla,estimation_mode=False,target=target)
    
    # Plot Lorentz curve
    plt.figure()
    LorenzAxis = np.arange(101,dtype=float)
    plt.plot(LorenzAxis,SplurgeNot0_Sol['Lorenz_Data_Adj'] ,'b-',linewidth=2)
    plt.scatter(np.array([20,40,60,80,100]),np.hstack([lorenz_target,1]),c='black', marker='o')
    plt.xlabel('Liquid wealth percentile',fontsize=12)
    plt.ylabel('Cumulative liquid wealth share',fontsize=12)
    plt.legend(['Model','Data'])
    make_figs('LiquWealth_Distribution_comparison', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot()  
    
    # Plot Lorentz curve
    plt.figure()
    LorenzAxis = np.arange(101,dtype=float)
    plt.plot(LorenzAxis,SplurgeNot0_Sol['Lorenz_Data_Adj'] ,'b-',linewidth=2)
    plt.plot(LorenzAxis,Splurge0_Sol['Lorenz_Data_Adj']    ,'r:',linewidth=2)
    plt.scatter(np.array([20,40,60,80,100]),np.hstack([lorenz_target,1]),c='black', marker='o')
    plt.xlabel('Liquid wealth percentile',fontsize=12)
    plt.ylabel('Cumulative liquid wealth share',fontsize=12)
    plt.legend(['Model, splurge $\geq$ 0','Model, splurge = 0','Data'])
    make_figs('LiquWealth_Distribution_comparison_splurge0', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot() 
    
    # Plot Agg MPCx
    plt.figure()
    xAxis = np.arange(0,5)
    plt.plot(xAxis,SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin'] ,'b-',linewidth=2)
    plt.plot(xAxis,Splurge0_Sol['simulated_MPC_mean_add_Lottery_Bin']    ,'r:',linewidth=2)
    plt.scatter(xAxis,Agg_MPCX_target,c='black', marker='o')
    plt.legend(['Model, splurge $\geq$ 0','Model, splurge = 0','Fagereng, Holm and Natvik (2021)'])
    plt.xticks(np.arange(min(xAxis), max(xAxis)+1, 1.0))
    plt.xlabel('year')
    plt.ylabel('% of lottery win spent')
    make_figs('AggMPC_LotteryWin_comparison_splurge0', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot()  
    
    # Plot Agg MPCx
    plt.figure()
    xAxis = np.arange(0,5)
    plt.plot(xAxis,SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin'] ,'b-',linewidth=2)
    plt.scatter(xAxis,Agg_MPCX_target,c='black', marker='o')
    plt.legend(['Model','Fagereng, Holm and Natvik (2021)'])
    plt.xticks(np.arange(min(xAxis), max(xAxis)+1, 1.0))
    plt.xlabel('year')
    plt.ylabel('% of lottery win spent')
    make_figs('AggMPC_LotteryWin_comparison', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot() 
    
    # Table initial MPCs along wealth q
    
    def mystr2(number):
        if not np.isnan(number):
            out = "{:.2f}".format(number)
        else:
            out = ''
        return out
    
        
    output  ="\\begin{tabular}{@{}lcccccc@{}} \n"
    output +="\\toprule \n"
    output +="                  & \multicolumn{5}{c}{MPC} &   \\\\   \n"
    output +="                  &  1st WQ  & 2nd WQ  & 3rd WQ & 4th WQ  & Agg  &  K/Y  \\\\  \\midrule \n"
    output +="Splurge $\geq$ 0 &"+mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][3])      + " & "+ mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][2])+ " & "+  \
                                mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][1])      + " & "+ mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][0]) + " & "+  \
                                mystr2(SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin'][0])+ " & "+ mystr2(SplurgeNot0_Sol['KY_Model'])  + " \\\\ \n"
    output +="Splurge = 0 &"+   mystr2(Splurge0_Sol['simulated_MPC_means_smoothed'][3])         + " & "+ mystr2(Splurge0_Sol['simulated_MPC_means_smoothed'][2])+ " & "+  \
                                mystr2(Splurge0_Sol['simulated_MPC_means_smoothed'][1])         + " & "+ mystr2(Splurge0_Sol['simulated_MPC_means_smoothed'][0]) + " & "+  \
                                mystr2(Splurge0_Sol['simulated_MPC_mean_add_Lottery_Bin'][0])   + " & "+ mystr2(Splurge0_Sol['KY_Model'])  + " \\\\ \n"
    output +="Data &"+          mystr2(MPC_target[2,3])                                         + " & "+ mystr2(MPC_target[2,2])+ " & "+  \
                                mystr2(MPC_target[2,1])                                         + " & "+ mystr2(MPC_target[2,0]) + " & "+  \
                                mystr2(Agg_MPCX_target[0])                                      + " & "+ mystr2(KY_target)  + " \\\\ \\bottomrule \n"
    output +="\\end{tabular}  \n"
    
    
    with open(Abs_Path+'/Figures/Comparison_Splurge_Table.tex','w') as f:
        f.write(output)
        f.close()   
        
    
    output  ="\\begin{tabular}{@{}lcccccc@{}} \n"
    output +="\\toprule \n"
    output +="                  & \multicolumn{5}{c}{MPC} &   \\\\   \n"
    output +="                  &  1st WQ  & 2nd WQ  & 3rd WQ & 4th WQ  & Agg  &  K/Y  \\\\  \\midrule \n"
    output +="Model &"+mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][3])      + " & "+ mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][2])+ " & "+  \
                                mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][1])      + " & "+ mystr2(SplurgeNot0_Sol['simulated_MPC_means_smoothed'][0]) + " & "+  \
                                mystr2(SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin'][0])+ " & "+ mystr2(SplurgeNot0_Sol['KY_Model'])  + " \\\\ \n"
    output +="Data &"+          mystr2(MPC_target[2,3])                                         + " & "+ mystr2(MPC_target[2,2])+ " & "+  \
                                mystr2(MPC_target[2,1])                                         + " & "+ mystr2(MPC_target[2,0]) + " & "+  \
                                mystr2(Agg_MPCX_target[0])                                      + " & "+ mystr2(KY_target)  + " \\\\ \\bottomrule \n"
    output +="\\end{tabular}  \n"
    
    
    with open_generated(Abs_Path+'/Figures/MPC_WealthQuartiles_Table.tex') as f:
        f.write(output)
        f.close()   
    
    
    
    Output_to_Excel = False
    if Output_to_Excel:
        x = np.vstack(( xAxis, SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin'], Splurge0_Sol['simulated_MPC_mean_add_Lottery_Bin'] , Agg_MPCX_target) )
        df = pd.DataFrame(x.T,columns=['Year','Model, splurge > 0','Model, splurge = 0','Fagereng, Holm and Natvik (2021)'])
        df.to_excel(Abs_Path+'/Data_AggMPC_LotteryWin.xlsx')
        
        x = np.vstack(( LorenzAxis, SplurgeNot0_Sol['Lorenz_Data_Adj'], Splurge0_Sol['Lorenz_Data_Adj'] ) )
        df = pd.DataFrame(x.T,columns=['Percentile','Model, splurge > 0','Model, splurge = 0'])
        df.to_excel(Abs_Path+'/LiquWealth_Distribution_a.xlsx')
        
        x = np.vstack(( np.array([20,40,60,80,100]), np.hstack([lorenz_target,1]) ) )
        df = pd.DataFrame(x.T,columns=['Percentile','Data'])
        df.to_excel(Abs_Path+'/LiquWealth_Distribution_b.xlsx')
        
        
def error_two_arrays(x,y):
    return np.linalg.norm(x-y);

print('Errors for MPC over time: ')
print('Splurge > 0:', error_two_arrays(Agg_MPCX_target,SplurgeNot0_Sol['simulated_MPC_mean_add_Lottery_Bin']))
print('Splurge = 0:', error_two_arrays(Agg_MPCX_target, Splurge0_Sol['simulated_MPC_mean_add_Lottery_Bin']))

print('Errors for MPC across wealth: ')
print('Splurge > 0:', error_two_arrays(MPC_target[2,:], SplurgeNot0_Sol['simulated_MPC_means_smoothed']))
print('Splurge = 0:', error_two_arrays(MPC_target[2,:], Splurge0_Sol['simulated_MPC_means_smoothed']))
 
print('Errors for Lorentz curve: ')
print('Splurge > 0:', error_two_arrays(np.hstack([lorenz_target,1]), SplurgeNot0_Sol['Lorenz_Data_Adj'][[20,40,60,80,100]]))
print('Splurge = 0:', error_two_arrays(np.hstack([lorenz_target,1]), Splurge0_Sol['Lorenz_Data_Adj'][[20,40,60,80,100]]))
   
print('Errors for K/Y: ')
print('Splurge > 0:', error_two_arrays(KY_target, SplurgeNot0_Sol['KY_Model']))
print('Splurge = 0:', error_two_arrays(KY_target, Splurge0_Sol['KY_Model']))
     
   


#%%
Run_other_CRRA_values = False
if Run_other_CRRA_values:
    CRRA_values = [1,3]
    
    RunLoopofStarpoints = True 
    startpoints = [ [0.10, 0.85, 0.10],
                    [0.10, 0.95, 0.15],
                    [0.30, 0.85, 0.10],
                    [0.30, 0.95, 0.15] ]
    
    for el in range(0,len(CRRA_values)):
        print('Running CRRA = ', CRRA_values[el])
        base_params['CRRA'] = CRRA_values[el]
    
        # Make several consumer types to be used during estimation
        del EstTypeList
        BaseTypeCRRA = KinkedRconsumerType(**base_params)
        EstTypeList = []
        for j in range(TypeCount):
            EstTypeList.append(deepcopy(BaseTypeCRRA))
            EstTypeList[-1].seed = j
    
    
    
        if RunLoopofStarpoints:
            for i,startpoint in enumerate(startpoints):
                print("Startpoint run no. ",i+1)
                print("Startpoint used: ", startpoint)
         
                target = 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC'
                filename = '/Result_AllTarget_CRRA_'+str(CRRA_values[el])+'_startpoint'+str(i)+'.txt'  
                res = find_Opt(target=target, startpoint=startpoint)
                save_betanabla_res_txt(filename,res)
        else:
            if CRRA_values[el] == 1:
                startpoint  = [0.14936532325901916, 0.9768205536148804, 0.09086039551142643]
            else:
                startpoint  = [0.2660514984112632, 0.9549940464615455, 0.06597517675173052]    
            
            target = 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC'
            filename = '/Result_AllTarget_CRRA_'+str(CRRA_values[el])+'.txt'  
            res = find_Opt(target=target, startpoint=startpoint)
            save_betanabla_res_txt(filename,res)


Plot_other_CRRA_values = False
if Plot_other_CRRA_values:
    target = 'AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC'
    # CRRA=1 
    del EstTypeList
    base_params['CRRA'] = 1
    BaseType = KinkedRconsumerType(**base_params)
    EstTypeList = []
    for j in range(TypeCount):
        EstTypeList.append(deepcopy(BaseType))
        EstTypeList[-1].seed = j
    [splurge,beta,nabla] = load_betanabla_res_txt('/Result_AllTarget_CRRA_1.txt')
    CRRA1=FagerengObjFunc(splurge,beta,nabla,estimation_mode=False,target=target)
    
    # CRRA=2
    del EstTypeList
    base_params['CRRA'] = 3
    BaseType = KinkedRconsumerType(**base_params)
    EstTypeList = []
    for j in range(TypeCount):
        EstTypeList.append(deepcopy(BaseType))
        EstTypeList[-1].seed = j
    [splurge,beta,nabla] = load_betanabla_res_txt('/Result_AllTarget_CRRA_3.txt')
    CRRA3=FagerengObjFunc(splurge,beta,nabla,estimation_mode=False,target=target)
    
    # Plot Lorentz curve
    plt.figure()
    LorenzAxis = np.arange(101,dtype=float)
    plt.plot(LorenzAxis,CRRA1['Lorenz_Data_Adj'] ,'b-',linewidth=2)
    plt.plot(LorenzAxis,CRRA3['Lorenz_Data_Adj']    ,'r:',linewidth=2)
    plt.scatter(np.array([20,40,60,80,100]),np.hstack([lorenz_target,1]),c='black', marker='o')
    plt.xlabel('Liquid wealth percentile',fontsize=12)
    plt.ylabel('Cumulative liquid wealth share',fontsize=12)
    plt.legend(['CRRA=1','CRRA = 3','Data'])
    make_figs('LiquWealth_Distribution_comparison_CRRA', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot()  
    
    # Plot Agg MPCx
    plt.figure()
    xAxis = np.arange(0,5)
    plt.plot(xAxis,CRRA1['simulated_MPC_mean_add_Lottery_Bin'] ,'b-',linewidth=2)
    plt.plot(xAxis,CRRA3['simulated_MPC_mean_add_Lottery_Bin']    ,'r:',linewidth=2)
    plt.scatter(xAxis,Agg_MPCX_target,c='black', marker='o')
    plt.legend(['CRRA=1','CRRA = 3','Fagereng, Holm and Natvik (2021)'])
    plt.xticks(np.arange(min(xAxis), max(xAxis)+1, 1.0))
    plt.xlabel('year')
    plt.ylabel('% of lottery win spent')
    make_figs('AggMPC_LotteryWin_comparison_CRRA', True , False, target_dir=Abs_Path+'/Figures/')
    show_plot()  
    
    # Table initial MPCs along wealth q
    
    def mystr2(number):
        if not np.isnan(number):
            out = "{:.2f}".format(number)
        else:
            out = ''
        return out
    
        
    output  ="\\begin{tabular}{@{}lcccccc@{}} \n"
    output +="\\toprule \n"
    output +="                  & \multicolumn{5}{c}{MPC} &   \\\\   \n"
    output +="                  &  1st WQ  & 2nd WQ  & 3rd WQ & 4th WQ  & Agg  &  K/Y  \\\\  \\midrule \n"
    output +="CRRA=1 &"+mystr2(CRRA1['simulated_MPC_means_smoothed'][3])      + " & "+ mystr2(CRRA1['simulated_MPC_means_smoothed'][2])+ " & "+  \
                                mystr2(CRRA1['simulated_MPC_means_smoothed'][1])      + " & "+ mystr2(CRRA1['simulated_MPC_means_smoothed'][0]) + " & "+  \
                                mystr2(CRRA1['simulated_MPC_mean_add_Lottery_Bin'][0])+ " & "+ mystr2(CRRA1['KY_Model'])  + " \\\\ \n"
    output +="CRRA=3 &"+   mystr2(CRRA3['simulated_MPC_means_smoothed'][3])         + " & "+ mystr2(CRRA3['simulated_MPC_means_smoothed'][2])+ " & "+  \
                                mystr2(CRRA3['simulated_MPC_means_smoothed'][1])         + " & "+ mystr2(CRRA3['simulated_MPC_means_smoothed'][0]) + " & "+  \
                                mystr2(CRRA3['simulated_MPC_mean_add_Lottery_Bin'][0])   + " & "+ mystr2(CRRA3['KY_Model'])  + " \\\\ \n"
    output +="Data &"+          mystr2(MPC_target[2,3])                                         + " & "+ mystr2(MPC_target[2,2])+ " & "+  \
                                mystr2(MPC_target[2,1])                                         + " & "+ mystr2(MPC_target[2,0]) + " & "+  \
                                mystr2(Agg_MPCX_target[0])                                      + " & "+ mystr2(KY_target)  + " \\\\ \n"
    output +="\\end{tabular}  \n"
    
    
    with open(Abs_Path+'/Figures/Comparison_CRRA_Table.tex','w') as f:
        f.write(output)
        f.close()   
    


    
 
    
    



    #%% For testing purposes

Run_3D_Plot         = False
Run_Investigation   = False


if Run_Investigation:
    for this_beta in np.linspace(0.925,0.932,10):
        FagerengObjFunc(0,this_beta ,0.086, target='AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC',investigate=True)
        

if Run_3D_Plot:
    # Define the function to be evaluated
    def my_function(x,y):
        return FagerengObjFunc(0,x,y, target='AGG_MPC_plus_Liqu_Wealth_plusKY_plusMPC')
      
          
    x_range = np.linspace(0.925, 0.95, 10)
    y_range = np.linspace(0.006, 0.01, 10)
     
    # Create empty arrays to store the results
    z_values = np.zeros((len(x_range), len(y_range)))
     
    # Evaluate the function using loops
    for i, x in enumerate(x_range):
        for j, y in enumerate(y_range):
            if (x + y > 1.05) or  (x + y < 0.98):
                z_values[i, j] = None
            else:
                z_values[i, j] = my_function(x, y)
                
          
                
    # Create a 3D plot
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
     
    # Create meshgrid for plotting
    x_grid, y_grid = np.meshgrid(x_range, y_range)
     
    # Plot the surface
    surf = ax.plot_surface(x_grid, y_grid, z_values.T, cmap='viridis')
     
    # Add labels and title
    ax.set_xlabel('X-axis')
    ax.set_ylabel('Y-axis')
    ax.set_zlabel('Z-axis')
    ax.set_title('Function Evaluation over 2D Grid (using loops)')
     
    # Add color bar
    fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10)
     
    # Show the plot
    show_plot()




    




    