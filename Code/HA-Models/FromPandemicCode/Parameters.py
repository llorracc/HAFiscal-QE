"""Calibration parameters for the HAFiscal policy experiments.

`return_parameters(Parametrization, OutputFor)` is the single entry point: it
assembles the agent/economy constructor dicts, Markov-array builders, policy
(experiment) change-dicts, and simulation settings for a named parametrization.
Numeric calibration inputs (splurge, discount-factor distributions, GIC caps)
are loaded — via EstimParameters — from the Results/ estimation files.

NOTE: importing this module imports EstimParameters, which parses sys.argv at
import time (argv[1]=Rfree, argv[3]=IncUnemp, argv[4]=IncUnempNoBenefits,
argv[5]=Splurge) — patch sys.argv before importing in tests (see CLAUDE.md).
"""

def return_parameters(Parametrization='Baseline',OutputFor='_Main.py'):
    """Return the calibration/parameter bundle for one named parametrization.

    Parametrization: 'Baseline' (paper scale), 'Reduced_Run', 'HS_Only',
        'College_Beta_Het', 'Smoke_Test', or a sensitivity name (CRRA1, CRRA3,
        ADElas, Rfree_1005, Rfree_1015, Rspell_4, LowerUBnoB, Splurge0, and
        their *_PVSame variants).
    OutputFor: selects which list is returned — '_Main.py' (constructor dicts,
        DiscFacDstns, AD-loop settings, policy change-dicts), '_Model.py'
        (Markov-array builders, T_sim, ...), or '_Output_Results.py'
        ([max_recession_duration, Rspell, Rfree_base, figs_dir_FullRun, CRRA]).

    Side effects: reads DiscFacEstim_*.txt / Result_AllTarget.txt calibration
    files (overridable via HAFISCAL_DISCFAC_FILE / HAFISCAL_SPLURGE_FILE) and
    prints the loaded-calibration betaDistr diagnostic (suppress with
    HAFISCAL_QUIET_BETADISTR=1). Importing this module triggers
    EstimParameters' sys.argv parsing — see the module docstring.
    """
    import os
    
    # for output
    cwd             = os.getcwd()
    folders         = cwd.split(os.path.sep)
    top_most_folder = folders[-1]
    if top_most_folder == 'FromPandemicCode':
        Abs_Path_Results = "".join([x + "//" for x in folders[0:-1]],)
        Abs_Path = cwd
    else:
        Abs_Path_Results = cwd
        Abs_Path = cwd + '/FromPandemicCode'

    import numpy as np
    from HARK.distributions import Uniform
    from HARK.ConsumptionSaving.ConsAggIndMarkovModel import make_hierarchical_mrkv_array
    from OtherFunctions import load_pickle, get_simulation_diff
    

    
    from EstimParameters import data_EducShares, Urate_normal_d, Urate_normal_h, Urate_normal_c,\
    Uspell_normal, UBspell_normal, PopGroFac, PermGroFacAgg, IncUnemp,\
    pLogInitMean_d, pLogInitMean_h, pLogInitMean_c,\
    pLogInitStd_d, pLogInitStd_h, pLogInitStd_c,\
    PermGroFac_base_d, PermGroFac_base_h, PermGroFac_base_c,\
    PermGroFac_unemp, perm_shocks_during_unemployment, tran_shocks_during_unemployment,\
    unemp_pLvl_grows_like_employed,\
    TranShkStd, PermShkStd, LivPrb_base, num_types, GICmaxBetas, gic_capped_beta, minBeta, DiscFacCount
    
    from income_process_sst import build_PermGroFac_micro

    # ESC-MOD-PHASE3: route estimation file paths through _interpretation.resolve_path
    # so ESC loads _ESC.txt suffixed files. Falls back to un-suffixed (legacy CDC)
    # files if the suffixed variant doesn't exist — preserves CDC bit-identity.
    import sys as _sys
    _parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if _parent_dir not in _sys.path:
        _sys.path.insert(0, _parent_dir)
    from _interpretation import resolve_path

    CRRA = 2.0
    Rfree_base = [1.01]
    Rspell = 6            # Expected length of recession, in quarters. If R_shared = True, must be an integer
    betas_txt_location = resolve_path(Abs_Path_Results+'/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt')
    Splurge_txt_location = resolve_path(Abs_Path_Results+'/Target_AggMPCX_LiquWealth/Result_AllTarget.txt')
    IncUnempNoBenefits = 0.5   # Unemployment income when benefits run out (proportion of permanent income)
    ADelasticity = 0.3

    # make changes according to robustness run
    if Parametrization == 'ADElas' or Parametrization == 'ADElas_PVSame':
        ADelasticity = 0.5
    elif Parametrization == 'CRRA1' or Parametrization == 'CRRA1_PVSame':
        CRRA = 1.0
        betas_txt_location = resolve_path(Abs_Path_Results+'/Results/DiscFacEstim_CRRA_1.0_R_1.01.txt')
        Splurge_txt_location = resolve_path(Abs_Path_Results+'/Target_AggMPCX_LiquWealth/Result_CRRA_1.0.txt')
    elif Parametrization == 'CRRA3' or Parametrization == 'CRRA3_PVSame':
        CRRA = 3.0
        betas_txt_location = resolve_path(Abs_Path_Results+'/Results/DiscFacEstim_CRRA_3.0_R_1.01.txt')
        Splurge_txt_location = resolve_path(Abs_Path_Results+'/Target_AggMPCX_LiquWealth/Result_CRRA_3.0.txt')
    elif Parametrization == 'Rfree_1005' or Parametrization == 'Rfree_1005_PVSame':
        Rfree_base = [1.005]
        betas_txt_location = resolve_path(Abs_Path_Results+'/Results/DiscFacEstim_CRRA_2.0_R_1.005.txt')
    elif Parametrization == 'Rfree_1015' or Parametrization == 'Rfree_1015_PVSame':
        Rfree_base = [1.015]
        betas_txt_location = resolve_path(Abs_Path_Results+'/Results/DiscFacEstim_CRRA_2.0_R_1.015.txt')
    elif Parametrization == 'Rspell_4' or Parametrization == 'Rspell_4_PVSame':
        Rspell = 4
    elif Parametrization == 'LowerUBnoB' or Parametrization == 'LowerUBnoB_PVSame':
        betas_txt_location = resolve_path(Abs_Path_Results+'/Results/DiscFacEstim_CRRA_2.0_R_1.01_altBenefits.txt')
        IncUnempNoBenefits = 0.15
        IncUnemp = 0.3
    elif Parametrization == 'Splurge0' or Parametrization == 'Splurge0_PVSame':
        betas_txt_location = resolve_path(Abs_Path_Results+'/Results/DiscFacEstim_CRRA_2.0_R_1.01_Splurge0.txt')
        Splurge_txt_location = resolve_path(Abs_Path_Results+'/Target_AggMPCX_LiquWealth/Result_AllTarget_Splurge0.txt')

    # PermGroFac matched-pair: the SAME flag (HAFISCAL_PERMGROFAC_FIX) that selects
    # the solver math (AggFiscalModel.py) also selects the calibration FILE here, so a
    # beta estimated under one PermGroFac regime cannot be silently paired with the
    # other regime's solver. FIX=1 -> canonical (fixed-solver) calibration; FIX=0 ->
    # Results/_pgf_legacy/ (raises if absent rather than mismatching). See _permgrofac.py
    # and memory feedback_calibration_solver_matched_pair.
    from _permgrofac import permgrofac_calib_path
    betas_txt_location = permgrofac_calib_path(betas_txt_location)

    # Welfare-attribution overrides (plans/20260417-1242h_welfare-vs-multiplier-asymmetry-hypothesis_v2.md §6):
    # HAFISCAL_DISCFAC_FILE  — absolute path to a DiscFacEstim_*.txt to use instead of the default
    # (explicit override: the SAME matched-pair discipline applies — point it at the file
    #  estimated under the solver regime you are running).
    # HAFISCAL_SPLURGE_FILE  — absolute path to a Result_AllTarget*.txt for the Splurge dict
    _discfac_override = os.environ.get('HAFISCAL_DISCFAC_FILE')
    if _discfac_override:
        betas_txt_location = _discfac_override
    _splurge_override = os.environ.get('HAFISCAL_SPLURGE_FILE')
    if _splurge_override:
        Splurge_txt_location = _splurge_override

    # Set some default values to use if loading from files doesn't work
    betaDefaults = [0.72, 0.91, 0.98]
    nablaDefaults = [0.32, 0.1, 0.014]
    # FALLBACK-ONLY GICx values: used iff loading DiscFacEstim_*.txt fails
    # (readCount < 3 below); normal runs take (beta, nabla, GICx) from the
    # estimation file. Purpose of the cap (still true as of BUG-053,
    # theGICfactor=0.9995, 2026-06-09): the GICfactor multiplier, applied
    # against the GIC-Mod-with-Liv boundary (`(Γ/(L·E[1/ψ]))^ρ/R`), excludes
    # very-high-β atoms whose chain mixing time is comparable to T_sim=350.
    # Stated invariant: **Reduced_Run central betas (0.72, 0.91, 0.98) MUST
    # pass un-clipped** — CO's central β=0.98 is the binding constraint.
    # ORIGINAL DERIVATION (pre-BUG-053 LINEAR β-shave, cap = GICmax·factor —
    # no longer the default): cap_CO=1.0064 × factor > 0.98 ⇒ factor > 0.9737
    # ⇒ GICx > 3.61; 4.0 was chosen with margin (per-edu caps then:
    # DO≈0.986, HS≈0.958, CO≈0.988).
    # CURRENT FAILURE MODE (BUG-053 default is the GPF-shave,
    # cap = GICmax·factor^CRRA with CRRA=2 — see EstimParameters.gic_capped_beta):
    # the CO invariant now requires factor² > 0.9737 ⇒ factor > 0.9868
    # ⇒ GICx > 4.31. The shipped fallback GICx=4.0 gives factor=0.982
    # ⇒ cap_CO ≈ 1.0064×0.982² ≈ 0.9705 < 0.98 — i.e. whenever the fallback
    # fires it CLIPS the central College β, violating the invariant above.
    # BEHAVIOR FLAG: fallback value needs updating — see COMMENT_AUDIT_FINDINGS.md.
    # (Changing the GICxDefaults VALUES is a behavior change, out of scope for
    # the comment-only pass.)
    # CO Baseline still has 0.98, 0.984, 0.988 atoms whose mixing-time is
    # ≥1/3 of T_sim=350 — Doob accurately reflects the *stationary* truth
    # for these, while MC at T_sim=350 underestimates. This is documented
    # behavior, not a defect; see conclusions log.
    GICxDefaults = [4.0, 3.0, 4.0]
  
    myEstim = [[],[],[]]
    readCount = 0
    if os.path.exists(betas_txt_location):
        betFile = open(betas_txt_location, 'r')
        readStr = betFile.readline().strip()
        while readStr != '' :
            dictload = eval(readStr)
            edType = dictload['EducationGroup']
            beta = dictload['beta']
            nabla = dictload['nabla']
            GICx = dictload['GICx']
            GICfactor = np.exp(GICx)/(1+np.exp(GICx))
            myEstim[edType] = [beta,nabla,GICx, GICfactor]
            readStr = betFile.readline().strip()
            readCount += 1
        betFile.close()
    else:
        print('Parameters.py: Failed to open ' + betas_txt_location)

    if readCount < 3: 
        print('Using default values for beta, nabla, GICx for education groups not found in ' + betas_txt_location)
        for edType in range(readCount,3):
            beta = betaDefaults[edType]
            nabla = nablaDefaults[edType]
            GICx = GICxDefaults[edType]
            GICfactor = np.exp(GICx)/(1+np.exp(GICx))
            myEstim[edType] = [beta,nabla,GICx, GICfactor]

    if os.path.exists(Splurge_txt_location):
        f = open(Splurge_txt_location, 'r')
        if f.mode=='r':
            contents= f.read()
        dictload= eval(contents)
        Splurge = dictload['splurge']
    else:
        print('Parameters.py: Failed to open ' + Splurge_txt_location)
        print('Using default value for Splurge')
        Splurge = 0.25

    # Direct scalar override for ς (takes precedence over Splurge_txt_location).
    # Used by the welfare-attribution experiment (v2 §6) to isolate the
    # ς contribution without needing a matching Result_AllTarget*.txt file.
    _splurge_val_override = os.environ.get('HAFISCAL_SPLURGE_OVERRIDE')
    if _splurge_val_override is not None and _splurge_val_override != '':
        try:
            Splurge = float(_splurge_val_override)
            print(f'Parameters.py: HAFISCAL_SPLURGE_OVERRIDE → Splurge = {Splurge}')
        except ValueError:
            print(f'Parameters.py: ignoring invalid HAFISCAL_SPLURGE_OVERRIDE={_splurge_val_override!r}')
    
    figs_dir_FullRun = ''
    if Parametrization == 'CRRA2_PVSame':
        figs_dir_FullRun = Abs_Path+'/Figures/CRRA2/'
    elif Parametrization == 'ADElas_PVSame':
        figs_dir_FullRun = Abs_Path+'/Figures/ADElas/'           
    elif Parametrization == 'CRRA1_PVSame':
        figs_dir_FullRun = Abs_Path+'/Figures/CRRA1/'
    elif Parametrization == 'CRRA3_PVSame':
        figs_dir_FullRun = Abs_Path+'/Figures/CRRA3/'
    elif Parametrization == 'Rfree_1005_PVSame':
        figs_dir_FullRun = Abs_Path+'/Figures/Rfree_1005/'
    elif Parametrization == 'Rfree_1015_PVSame':
        figs_dir_FullRun = Abs_Path+'/Figures/Rfree_1015/'
    elif Parametrization == 'Rspell_4_PVSame':
        figs_dir_FullRun = Abs_Path+'/Figures/Rspell_4/'
    elif Parametrization == 'LowerUBnoB_PVSame':
        figs_dir_FullRun = Abs_Path+'/Figures/LowerUBnoB/'
    elif Parametrization == 'Splurge0_PVSame':
        figs_dir_FullRun = Abs_Path+'/Figures/Splurge0/'

        
    if Parametrization.find('PVSame')>0:
        base_results                    = load_pickle('base_results',figs_dir_FullRun,locals())
        check_results                   = load_pickle('Check_results',figs_dir_FullRun,locals())
        UI_results                      = load_pickle('UI_results',figs_dir_FullRun,locals())
        TaxCut_results                  = load_pickle('TaxCut_results',figs_dir_FullRun,locals())
        NPV_AddInc_Check                = get_simulation_diff(base_results,check_results,'NPV_AggIncome') 
        NPV_AddInc_UI                   = get_simulation_diff(base_results,UI_results,'NPV_AggIncome') # Policy expenditure
        NPV_AddInc_TaxCut               = get_simulation_diff(base_results,TaxCut_results,'NPV_AggIncome')
        
        TaxCutAdjFactor = NPV_AddInc_UI[-1]/NPV_AddInc_TaxCut[-1]
        CheckAdjFactor =  NPV_AddInc_UI[-1]/NPV_AddInc_Check[-1]
    else:
        TaxCutAdjFactor = 1
        CheckAdjFactor = 1

    
    if not OutputFor == '_Model.py':
        print('CRRA = ',CRRA)
        print('Rfree_base = ',Rfree_base)
        print('Rspell = ',Rspell)
        
        print('Splurge = ',Splurge)
        print('beta/nablas = ',myEstim)
        
        print('TaxCutAdjFactor = ',TaxCutAdjFactor)
        print('CheckAdjFactor = ',CheckAdjFactor)
        
        print('IncUnempNoBenefits = ', IncUnempNoBenefits)
        print('IncUnemp = ', IncUnemp)
        print('ADelasticity = ', ADelasticity)

       
    # # Targets in the estimation of the discount factor distributions for each 
    # # education level. 
    # # From SCF 2004: [20,40,60,80]-percentiles of the Lorenz curve for liquid wealth
    # data_LorenzPts_d = np.array([0, 0.01, 0.60, 3.58])    # \
    # data_LorenzPts_h = np.array([0.06, 0.63, 2.98, 11.6]) # -> units: % 
    # data_LorenzPts_c = np.array([0.15, 0.92, 3.27, 10.3]) # /
    # data_LorenzPts = [data_LorenzPts_d, data_LorenzPts_h, data_LorenzPts_c]
    # data_LorenzPtsAll = np.array([0.03, 0.35, 1.84, 7.42])
    # # From SCF 2004: Average liquid wealth to permanent income ratio 
    # data_avgLWPI = np.array([15.7, 47.7, 111])*4 # weighted average of fractions in percent
    # # From SCF 2004: Total LW over total PI by education group
    # data_LWoPI = np.array([28.1, 59.6, 162])*4 # units: %
    # # From SCF 2004: Weighted median of liquid wealth to permanent income ratio
    # data_medianLWPI = np.array([1.16, 7.55, 28.2])*4 # weighted median of fractions in percent
    
    # # Parameters concerning the distribution of discount factors
    # DiscFacMeanD = myEstim[0][0]  # Mean intertemporal discount factor for dropout types
    # DiscFacMeanH = myEstim[1][0]  # Mean intertemporal discount factor for high school types
    # DiscFacMeanC = myEstim[2][0]  # Mean intertemporal discount factor for college types
    # # DiscFacInit = [DiscFacMeanD, DiscFacMeanH, DiscFacMeanC]
    # DiscFacSpreadD = myEstim[0][1]
    # DiscFacSpreadH = myEstim[1][1]
    # DiscFacSpreadC = myEstim[2][1] 
    
    # # Define the distribution of the discount factor for each eduation level
    # DiscFacCount = 7
    # DiscFacDstnD = Uniform(DiscFacMeanD-DiscFacSpreadD, DiscFacMeanD+DiscFacSpreadD).approx(DiscFacCount)
    # DiscFacDstnH = Uniform(DiscFacMeanH-DiscFacSpreadH, DiscFacMeanH+DiscFacSpreadH).approx(DiscFacCount)
    # DiscFacDstnC = Uniform(DiscFacMeanC-DiscFacSpreadC, DiscFacMeanC+DiscFacSpreadC).approx(DiscFacCount)
    # DiscFacDstns = [DiscFacDstnD, DiscFacDstnH, DiscFacDstnC]
    

    
    # for e in range(num_types):
    #     for thedf in range(DiscFacCount):
    #         if DiscFacDstns[e].X[thedf] > GICmaxBetas[e]*GICfactor: 
    #             DiscFacDstns[e].X[thedf] = GICmaxBetas[e]*GICfactor
    #         elif DiscFacDstns[e].X[thedf] < minBeta:
    #             DiscFacDstns[e].X[thedf] = minBeta


     
    # Recession
    Urate_recession_d = 2 * Urate_normal_d # Unemployment rate in recession
    Urate_recession_h = 2 * Urate_normal_h 
    Urate_recession_c = 2 * Urate_normal_c
    
    Uspell_recession = 4         # Average duration of unemployment spell in recession, in quarters
    R_shared = False             # Indicator for whether the recession shared (True) or idiosyncratic (False)
    # UI extension
    UBspell_extended = 5         # Average duration of unemployment benefits when extended and assuming policy remains in place, in quarters
    PolicyUBspell = 2            # Average duration that policy of extended unemployment benefits is in place
    # Tax Cut parameter
    PolicyTaxCutspell = 2        # Average duration that policy of payroll tax cuts
    TaxCutIncFactor = 1 + 0.02*TaxCutAdjFactor
    TaxCutPeriods = 8            # Deterministic duTrueration of tax cut 
    TaxCutContinuationProb_Rec = 0.5   # Probability that tax cut is continued after tax cut periods run out, when recession in q8
    TaxCutContinuationProb_Bas = 0.0   # Probability that tax cut is continued after tax cut periods run out, when baseline in q8
    #Check experiment parameter
    CheckStimLvl = 1200/1000 * CheckAdjFactor
    CheckStimLvl_PLvl_Cutoff_start = 100/4/1 #100 k yearly income #At this Level of permanent inc, Stimulus beings to fall linearly
    CheckStimLvl_PLvl_Cutoff_end = 150/4/1 #150k yearly income #At this Level of permanent inc, Stimulus is zero
    
    
    # UpdatePrb = 0.25    # probability of updating macro state (when sticky expectations is on)
 
  

    # Parameters concerning grid sizes: assets, permanent income shocks, transitory income shocks
    aXtraMin = 0.001        # Lowest non-zero end-of-period assets above minimum gridpoint
    aXtraMax = 40           # Highest non-zero end-of-period assets above minimum gridpoint
    aXtraCount = 48         # Base number of end-of-period assets above minimum gridpoints
    aXtraExtra = [0.002,0.003] # Additional gridpoints to "force" into the grid
    aXtraNestFac = 3        # Exponential nesting factor for aXtraGrid (how dense is grid near zero)
    PermShkCount = 7        # Number of points in equiprobable discrete approximation to permanent shock distribution
    TranShkCount = 7        # Number of points in equiprobable discrete approximation to transitory shock distribution
    T_age = 200             # 50 years; QE-era cap (Crawley 2022, commit 770d4d04).
                            # BUG-038 restoration (2026-04-30): see math doc §25 for
                            # the rigorous Q-twisted Harmenberg construction under cap.
                            # NOTE: T=200 with L=1-1/160 yields E[lifetime] ≈ 28 years
                            # (vs L's calibrated 40 years uncapped); this is a known
                            # mismatch inherited from the QE setup. Choosing a
                            # different T to better match the L calibration is a
                            # separate workflow, not part of BUG-038.

    import os as _os
    if _os.environ.get('HAFISCAL_FAST_GRIDS', '').lower() in ('1', 'true', 'yes'):
        aXtraCount = 24
        PermShkCount = 5
        TranShkCount = 5
        print(f"FAST_GRIDS: aXtraCount={aXtraCount}, PermShkCount={PermShkCount}, TranShkCount={TranShkCount}")
    
    
    # Size of simulations
    AgentCountTotal = 10000     # Total simulated population
    T_sim = 40                  # Number of quarters to simulate in counterfactuals
    

    
    # Basic lifecycle length parameters (don't touch these)
    T_cycle = 1
    
    # Define grid of aggregate assets to labor
    CgridBase = np.array([0.8, 1.0, 1.2])

    # BUG-043 fix: see EstimParameters.py for full documentation of
    # HAFISCAL_UI_STATE_ENCODING. The value is determined at import time
    # and shared with EstimParameters.py.
    from EstimParameters import (
        HAFISCAL_UI_STATE_ENCODING,
        Policy_ExtraBenefitQuarters,
        num_base_MrkvStates,
    )
    num_experiment_periods = 20
    max_recession_duration = 21
    
    # Shorter horizons, one beta per education (3 types). Smoke_Test uses the
    # same structure but AgentCountTotal=100 for crash-only runs; Reduced_Run
    # uses a larger MC minimum for meaningful aggregate moments. HS_Only is
    # an intermediate parametrization with a single education cohort (HS)
    # that gets 100% of the agent count — useful for tests where the
    # minority-cohort sample size dominates the noise floor (see
    # plans/20260408-1213h_single-cohort-plus-shuffle-implementation.md for the full
    # rationale, including the future shuffle integration).
    if Parametrization in ('Reduced_Run', 'Smoke_Test', 'HS_Only'):
        num_experiment_periods = 10
        max_recession_duration = 11
        T_age = 100  # 25 years; pre-dc6390e3 Reduced_Run value (BUG-038 restoration)
        DiscFacCount = 1

    DiscFacDstns = [None]*3
    for e in [0,1,2]:
        dfs = Uniform(myEstim[e][0]-myEstim[e][1], myEstim[e][0]+myEstim[e][1]).discretize(DiscFacCount)
        
        # Check GIC:
        for thedf in range(DiscFacCount):
            if dfs.atoms[0][thedf] > gic_capped_beta(e, myEstim[e][3]):
                dfs.atoms[0][thedf] = gic_capped_beta(e, myEstim[e][3])
            elif dfs.atoms[0][thedf] < minBeta:
                dfs.atoms[0][thedf] = minBeta
        theDFs = np.round(dfs.atoms[0],4)
        # betaDistr DIAGNOSTIC of the LOADED (on-disk) calibration. This fires on EVERY
        # return_parameters() call — including transitively at AggFiscalModel import
        # (AggFiscalModel.py:65) — so during a RE-ESTIMATION it prints the STALE pre-run
        # calibration that is about to be overwritten, NOT the distribution being estimated.
        # That stale print is what cost time chasing a phantom cap inconsistency (BUG-053
        # followup, 2026-06-09). Two changes so it can't mislead again:
        #   (a) labelled "[loaded calibration ...]" — never mistakable for the newly-estimated
        #       distribution, which the estimator now prints "[newly estimated ...]" after it is
        #       constructed (estim_phase2_tm_a.py); and
        #   (b) suppressible via HAFISCAL_QUIET_BETADISTR=1 (set by the re-estimation orchestrator)
        #       so the stale load-time print does not appear at all during re-estimation.
        # The clip above correctly uses THIS calibration's OWN saved GICfactor (myEstim[e][3]),
        # not the module theGICfactor — a saved calibration carries the GIC cap it was estimated
        # under; the cap/GPF/GICx are shown so the source is explicit.
        if os.environ.get('HAFISCAL_QUIET_BETADISTR', '0') != '1':
            _gic_cap = gic_capped_beta(e, myEstim[e][3])
            _n_at_cap = int(np.sum(dfs.atoms[0] >= _gic_cap - 1e-12))
            print(f'[loaded calibration: EducationGroup {e}] betaDistr :', theDFs.tolist(),
                  f'  [GIC cap={_gic_cap:.5f} (GPF={myEstim[e][3]:.5f}) from saved GICx={myEstim[e][2]:.4f}; '
                  f'{_n_at_cap}/{DiscFacCount} at cap]')
        DiscFacDstns[e] = dfs
    
    def make_macro_mrkv_array_recession(Rspell, num_experiment_periods):
        # See math-derive-appendix (recession-duration): R_persist = 1 - 1/Rspell
        R_persist = 1.-1./Rspell
        recession_transitions = np.array([[1.0, 0.0],[1-R_persist, R_persist]])
        MacroMrkvArray = np.zeros((2*(num_experiment_periods+1), 2*(num_experiment_periods+1)))
        MacroMrkvArray[0:2,0:2] = recession_transitions
        for i in np.array(range(num_experiment_periods-1))+1:
            MacroMrkvArray[2*i:2*i+2, 2*i+2:2*i+4] = recession_transitions
        MacroMrkvArray[2*num_experiment_periods:2*num_experiment_periods+2, 0:2] = recession_transitions 
        return MacroMrkvArray
    
    def small_MrkvArray(e,u,ub,transition_ub=True):
        small_MrkvArray = np.zeros((ub+2, ub+2))
        small_MrkvArray[0,0] = e
        small_MrkvArray[0,1] = 1-e
        for i in np.array(range(ub))+1:
            if transition_ub:
                small_MrkvArray[i,i+1] = u
            else:
                small_MrkvArray[i,i] = u
            small_MrkvArray[i,0] = 1-u
        small_MrkvArray[ub+1,ub+1] = u
        small_MrkvArray[ub+1,0] = 1-u
        return small_MrkvArray 
    
    def make_cond_mrkv_arrays_base(Urate_normal, Uspell_normal, UBspell_normal):
        U_persist_normal = 1.-1./Uspell_normal
        # See math-derive-appendix (emp-persist): E_persist = 1 - u*(1-U_persist)/(1-u)
        E_persist_normal = 1.-Urate_normal*(1.-U_persist_normal)/(1.-Urate_normal)
        # _ub_chain_length is set below per HAFISCAL_UI_STATE_ENCODING; use it
        # so the base scenario also picks up 6-state encoding under bug_fix.
        MrkvArray_normal         = small_MrkvArray(E_persist_normal,    U_persist_normal,    _ub_chain_length)
        CondMrkvArrays = [MrkvArray_normal]
        return CondMrkvArrays
    
    # Effective UB chain length used by small_MrkvArray:
    #   legacy:  ub = UBspell_normal (= 2) → 4-state Markov array
    #   bug_fix: ub = UBspell_normal + Policy_ExtraBenefitQuarters (= 4) → 6-state
    # See BUG-043 for the rationale: the extra states (u3Q, u4Q) make the
    # extension benefit period explicit in the state space, so the policy
    # difference can be encoded in income (not transitions). This eliminates
    # the freeze-window trick that under-delivered for Case 1 agents.
    if HAFISCAL_UI_STATE_ENCODING == 'bug_fix':
        _ub_chain_length = UBspell_normal + Policy_ExtraBenefitQuarters
    else:
        _ub_chain_length = UBspell_normal

    def make_cond_mrkv_arrays_recession(Urate_normal, Uspell_normal, UBspell_normal, Urate_recession, Uspell_recession, num_experiment_periods):
        U_persist_normal = 1.-1./Uspell_normal
        E_persist_normal = 1.-Urate_normal*(1.-U_persist_normal)/(1.-Urate_normal)
        U_persist_recession = 1.-1./Uspell_recession
        E_persist_recession = 1.-Urate_recession*(1.-U_persist_recession)/(1.-Urate_recession)
        MrkvArray_normal         = small_MrkvArray(E_persist_normal,    U_persist_normal,    _ub_chain_length)
        MrkvArray_recession      = small_MrkvArray(E_persist_recession, U_persist_recession, _ub_chain_length)
        CondMrkvArrays = [MrkvArray_normal, MrkvArray_recession]*(num_experiment_periods+1)
        return CondMrkvArrays

    def make_cond_mrkv_arrays_recession_ui(Urate_normal, Uspell_normal, UBspell_normal, Urate_recession, Uspell_recession, num_experiment_periods, ExtraUBperiods):
        U_persist_normal = 1.-1./Uspell_normal
        E_persist_normal = 1.-Urate_normal*(1.-U_persist_normal)/(1.-Urate_normal)
        U_persist_recession = 1.-1./Uspell_recession
        E_persist_recession = 1.-Urate_recession*(1.-U_persist_recession)/(1.-Urate_recession)
        if HAFISCAL_UI_STATE_ENCODING == 'bug_fix':
            # BUG-043 fix: no freeze. cond_mrkv is identical to recession scenario.
            # The policy difference is encoded entirely in IncShkDstn (which has
            # macro-state-conditional income at u3Q/u4Q under recessionUI).
            MrkvArray_normal      = small_MrkvArray(E_persist_normal,    U_persist_normal,    _ub_chain_length)
            MrkvArray_recession   = small_MrkvArray(E_persist_recession, U_persist_recession, _ub_chain_length)
            CondMrkvArrays = [MrkvArray_normal, MrkvArray_recession]*(num_experiment_periods+1)
        else:
            # Legacy: freeze-window mechanism (BUG-043 present)
            MrkvArray_normal         = small_MrkvArray(E_persist_normal,    U_persist_normal,    _ub_chain_length)
            MrkvArray_recession      = small_MrkvArray(E_persist_recession, U_persist_recession, _ub_chain_length)
            MrkvArray_normalUI       = small_MrkvArray(E_persist_normal,    U_persist_normal,    _ub_chain_length, transition_ub=False)
            MrkvArray_recessionUI    = small_MrkvArray(E_persist_recession, U_persist_recession, _ub_chain_length, transition_ub=False)
            CondMrkvArrays = [MrkvArray_normal, MrkvArray_recession] + [MrkvArray_normalUI, MrkvArray_recessionUI]*ExtraUBperiods + [MrkvArray_normal, MrkvArray_recession]*(num_experiment_periods-ExtraUBperiods)
        return CondMrkvArrays


    
    def make_full_mrkv_array(MacroMrkvArray, CondMrkvArrays):
        return [make_hierarchical_mrkv_array(MacroMrkvArray, CondMrkvArrays)]
    
    MacroMrkvArray_base = np.array([[1.0]])
    CondMrkvArrays_base_d = make_cond_mrkv_arrays_base(Urate_normal_d, Uspell_normal, UBspell_normal)
    CondMrkvArrays_base_h = make_cond_mrkv_arrays_base(Urate_normal_h, Uspell_normal, UBspell_normal)
    CondMrkvArrays_base_c = make_cond_mrkv_arrays_base(Urate_normal_c, Uspell_normal, UBspell_normal)
    MrkvArray_base_d = make_full_mrkv_array(MacroMrkvArray_base, CondMrkvArrays_base_d)
    MrkvArray_base_h = make_full_mrkv_array(MacroMrkvArray_base, CondMrkvArrays_base_h)
    MrkvArray_base_c = make_full_mrkv_array(MacroMrkvArray_base, CondMrkvArrays_base_c)
    
    MacroMrkvArray_recession = make_macro_mrkv_array_recession(Rspell, num_experiment_periods)
    CondMrkvArrays_recession_d = make_cond_mrkv_arrays_recession(Urate_normal_d, Uspell_normal, UBspell_normal, Urate_recession_d, Uspell_recession, num_experiment_periods)
    CondMrkvArrays_recession_h = make_cond_mrkv_arrays_recession(Urate_normal_h, Uspell_normal, UBspell_normal, Urate_recession_h, Uspell_recession, num_experiment_periods)
    CondMrkvArrays_recession_c = make_cond_mrkv_arrays_recession(Urate_normal_c, Uspell_normal, UBspell_normal, Urate_recession_c, Uspell_recession, num_experiment_periods)
    MrkvArray_recession_d = make_full_mrkv_array(MacroMrkvArray_recession, CondMrkvArrays_recession_d)
    MrkvArray_recession_h = make_full_mrkv_array(MacroMrkvArray_recession, CondMrkvArrays_recession_h)
    MrkvArray_recession_c = make_full_mrkv_array(MacroMrkvArray_recession, CondMrkvArrays_recession_c)
    
    MacroMrkvArray_recessionCheck = MacroMrkvArray_recession
    CondMrkvArrays_recessionCheck_d = CondMrkvArrays_recession_d
    CondMrkvArrays_recessionCheck_h = CondMrkvArrays_recession_h
    CondMrkvArrays_recessionCheck_c = CondMrkvArrays_recession_c
    MrkvArray_recessionCheck_d = make_full_mrkv_array(MacroMrkvArray_recessionCheck, CondMrkvArrays_recessionCheck_d)
    MrkvArray_recessionCheck_h = make_full_mrkv_array(MacroMrkvArray_recessionCheck, CondMrkvArrays_recessionCheck_h)
    MrkvArray_recessionCheck_c = make_full_mrkv_array(MacroMrkvArray_recessionCheck, CondMrkvArrays_recessionCheck_c)
    
    MacroMrkvArray_recessionTaxCut = MacroMrkvArray_recession
    CondMrkvArrays_recessionTaxCut_d = CondMrkvArrays_recession_d
    CondMrkvArrays_recessionTaxCut_h = CondMrkvArrays_recession_h
    CondMrkvArrays_recessionTaxCut_c = CondMrkvArrays_recession_c
    MrkvArray_recessionTaxCut_d = make_full_mrkv_array(MacroMrkvArray_recessionTaxCut, CondMrkvArrays_recessionTaxCut_d)
    MrkvArray_recessionTaxCut_h = make_full_mrkv_array(MacroMrkvArray_recessionTaxCut, CondMrkvArrays_recessionTaxCut_h)
    MrkvArray_recessionTaxCut_c = make_full_mrkv_array(MacroMrkvArray_recessionTaxCut, CondMrkvArrays_recessionTaxCut_c)
    
    MacroMrkvArray_recessionUI = MacroMrkvArray_recession
    CondMrkvArrays_recessionUI_d = make_cond_mrkv_arrays_recession_ui(Urate_normal_d, Uspell_normal, UBspell_normal, Urate_recession_d, Uspell_recession, num_experiment_periods, UBspell_extended-UBspell_normal)
    CondMrkvArrays_recessionUI_h = make_cond_mrkv_arrays_recession_ui(Urate_normal_h, Uspell_normal, UBspell_normal, Urate_recession_h, Uspell_recession, num_experiment_periods, UBspell_extended-UBspell_normal)
    CondMrkvArrays_recessionUI_c = make_cond_mrkv_arrays_recession_ui(Urate_normal_c, Uspell_normal, UBspell_normal, Urate_recession_c, Uspell_recession, num_experiment_periods, UBspell_extended-UBspell_normal)
    MrkvArray_recessionUI_d    = make_full_mrkv_array(MacroMrkvArray_recessionUI, CondMrkvArrays_recessionUI_d)
    MrkvArray_recessionUI_h    = make_full_mrkv_array(MacroMrkvArray_recessionUI, CondMrkvArrays_recessionUI_h)
    MrkvArray_recessionUI_c    = make_full_mrkv_array(MacroMrkvArray_recessionUI, CondMrkvArrays_recessionUI_c)
    
    
    
  


    # See math-derive Section 4: ergodic distribution via eigenvector of Markov matrix
    vals_d, vecs_d = np.linalg.eig(np.transpose(MrkvArray_base_d[0])) 
    dist_d = np.abs(np.abs(vals_d) - 1.)
    idx_d = np.argmin(dist_d)
    init_mrkv_dist_d = vecs_d[:,idx_d].real/np.sum(vecs_d[:,idx_d].real)
    
    vals_h, vecs_h = np.linalg.eig(np.transpose(MrkvArray_base_h[0])) 
    dist_h = np.abs(np.abs(vals_h) - 1.)
    idx_h = np.argmin(dist_h)
    init_mrkv_dist_h = vecs_h[:,idx_h].real/np.sum(vecs_h[:,idx_h].real)
    
    vals_c, vecs_c = np.linalg.eig(np.transpose(MrkvArray_base_c[0])) 
    dist_c = np.abs(np.abs(vals_c) - 1.)
    idx_c = np.argmin(dist_c)
    init_mrkv_dist_c = vecs_c[:,idx_c].real/np.sum(vecs_c[:,idx_c].real)
    
    
    
    # Define a parameter dictionary for dropout type
    init_dropout = {"cycles": 0, # 00This will be overwritten at type construction
                    "T_cycle": T_cycle,
                    'T_sim': T_age * 2,  # Burn-in length = 2 × cap, matches pre-dc6390e3 QE-era convention
                    'T_age': T_age,
                    'AgentCount': 1000, #number overwritten later
                    "PermGroFacAgg": PermGroFacAgg,
                    "PopGroFac": PopGroFac,
                    "CRRA": CRRA,
                    "DiscFac": 0.98, # This will be overwritten at type construction
                    "Rfree_base" : Rfree_base,
                    "PermGroFac_base": PermGroFac_base_d,
                    "LivPrb_base": LivPrb_base,
                    "MrkvArray_recession" : MrkvArray_recession_d,
                    "MacroMrkvArray_recession" : MacroMrkvArray_recession,
                    "CondMrkvArrays_recession" : CondMrkvArrays_recession_d,
                    "MrkvArray_recessionUI" : MrkvArray_recessionUI_d,
                    "MacroMrkvArray_recessionUI" : MacroMrkvArray_recessionUI,
                    "CondMrkvArrays_recessionUI" : CondMrkvArrays_recessionUI_d,
                    "MrkvArray_recessionTaxCut" : MrkvArray_recessionTaxCut_d,
                    "MacroMrkvArray_recessionTaxCut" : MacroMrkvArray_recessionTaxCut,
                    "CondMrkvArrays_recessionTaxCut" : CondMrkvArrays_recessionTaxCut_d,
                    "MrkvArray_recessionCheck" : MrkvArray_recessionCheck_d,
                    "MacroMrkvArray_recessionCheck" : MacroMrkvArray_recessionCheck,
                    "CondMrkvArrays_recessionCheck" : CondMrkvArrays_recessionCheck_d,
                    "Rfree" : np.array(num_base_MrkvStates*Rfree_base),
                    "PermGroFac": [np.array(build_PermGroFac_micro(PermGroFac_base_d[0], num_base_MrkvStates, PermGroFac_base_d[0] if unemp_pLvl_grows_like_employed else PermGroFac_unemp))],
                    "LivPrb": [np.array(LivPrb_base*num_base_MrkvStates)],
                    "MrkvArray_base" : MrkvArray_base_d, 
                    "MacroMrkvArray_base" : MacroMrkvArray_base,
                    "CondMrkvArrays_base" : CondMrkvArrays_base_d,
                    "MrkvArray" : MrkvArray_base_d, 
                    "MacroMrkvArray" : MacroMrkvArray_base,
                    "CondMrkvArrays" : CondMrkvArrays_base_d,
                    "BoroCnstArt": 0.0,
                    # Income-process parameters below populate the inputs to (eq:income) and (eq:perm-income) of
                    # BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md.
                    # PermShkStd / TranShkStd parameterize the (ψ, ξ) shock distributions of (eq:perm-income); IncUnemp / IncUnempNoBenefits are the (ρ_b, ρ_nb) replacement rates of (eq:income).
                    # implements (eq:perm-income) and (eq:income) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
                    "PermShkStd": PermShkStd,
                    "PermShkCount": PermShkCount,
                    "TranShkStd": TranShkStd,
                    "TranShkCount": TranShkCount,
                    "UnempPrb": 0.0, # Unemployment is modeled as a Markov state
                    "IncUnemp": IncUnemp,
                    "IncUnempNoBenefits": IncUnempNoBenefits,
                    "aXtraMin": aXtraMin,
                    "aXtraMax": aXtraMax,
                    "aXtraCount": aXtraCount,
                    "aXtraExtra": aXtraExtra,
                    "aXtraNestFac": aXtraNestFac,
                    "CubicBool": False,
                    "vFuncBool": False,
                    'kLogInitMean': np.log(0.00001), # Initial assets are zero
                    'kLogInitStd': 0.0,
                    'pLogInitMean': pLogInitMean_d,  # SCF: avg quarterly perm income at age 25 (per group)
                    'pLogInitStd': pLogInitStd_d,       # σ_g kept group-specific
                    "MrkvPrbsInit" : np.array(list(init_mrkv_dist_d)),
                    'Urate_normal' : Urate_normal_d,
                    'Uspell_normal' : Uspell_normal,
                    'UBspell_normal' : UBspell_normal,
                    'num_base_MrkvStates' : num_base_MrkvStates,
                    'PermGroFac_unemp': PermGroFac_unemp,
                    'perm_shocks_during_unemployment': perm_shocks_during_unemployment,
                    'tran_shocks_during_unemployment': tran_shocks_during_unemployment,
                    'unemp_pLvl_grows_like_employed': unemp_pLvl_grows_like_employed,
                    'Urate_recession' : Urate_recession_d,
                    'Uspell_recession' : Uspell_recession,
                    'num_experiment_periods' : num_experiment_periods,
                    'Rspell' : Rspell,
                    'R_shared' : R_shared,
                    'UBspell_extended' : UBspell_extended,
                    'PolicyUBspell' : PolicyUBspell,
                    'PolicyTaxCutspell' : PolicyTaxCutspell,
                    'TaxCutIncFactor' : TaxCutIncFactor,
                    'TaxCutPeriods' : TaxCutPeriods,
                    'TaxCutContinuationProb_Rec' : TaxCutContinuationProb_Rec,
                    'TaxCutContinuationProb_Bas' : TaxCutContinuationProb_Bas,
                    'CheckStimLvl' : CheckStimLvl,
                    'CheckStimLvl_PLvl_Cutoff_start' : CheckStimLvl_PLvl_Cutoff_start,
                    'CheckStimLvl_PLvl_Cutoff_end' : CheckStimLvl_PLvl_Cutoff_end,
                    'UpdatePrb' : 1.0,
                    'Splurge' : Splurge,
                    'track_vars' : [],
                    'EducType': 0
                    }
    
    adj_highschool = {
        "PermGroFac_base": PermGroFac_base_h,
        "PermGroFac": [np.array(build_PermGroFac_micro(PermGroFac_base_h[0], num_base_MrkvStates, PermGroFac_base_h[0] if unemp_pLvl_grows_like_employed else PermGroFac_unemp))],
        "MrkvArray_base" : MrkvArray_base_h, 
        "CondMrkvArrays_base" : CondMrkvArrays_base_h,
        "MrkvArray" : MrkvArray_base_h, 
        "CondMrkvArrays" : CondMrkvArrays_base_h,
        "MrkvArray_recession" : MrkvArray_recession_h,
        "CondMrkvArrays_recession" : CondMrkvArrays_recession_h,
        "MrkvArray_recessionUI" : MrkvArray_recessionUI_h,
        "CondMrkvArrays_recessionUI" : CondMrkvArrays_recessionUI_h,
        "MrkvArray_recessionTaxCut" : MrkvArray_recessionTaxCut_h,
        "CondMrkvArrays_recessionTaxCut" : CondMrkvArrays_recessionTaxCut_h,
        "MrkvArray_recessionCheck" : MrkvArray_recessionCheck_h,
        "CondMrkvArrays_recessionCheck" : CondMrkvArrays_recessionCheck_h,  
        'pLogInitMean': pLogInitMean_h,  # SCF: avg quarterly perm income at age 25 (per group)
        'pLogInitStd': pLogInitStd_h,       # σ_g kept group-specific
        "MrkvPrbsInit" : np.array(list(init_mrkv_dist_h)),
        'Urate_normal' : Urate_normal_h,
        'Urate_recession' : Urate_recession_h,
        'EducType' : 1}
    init_highschool = init_dropout.copy()
    init_highschool.update(adj_highschool)
    
    adj_college = {
        "PermGroFac_base": PermGroFac_base_c,
        "PermGroFac": [np.array(build_PermGroFac_micro(PermGroFac_base_c[0], num_base_MrkvStates, PermGroFac_base_c[0] if unemp_pLvl_grows_like_employed else PermGroFac_unemp))],
        "MrkvArray_base" : MrkvArray_base_c, 
        "CondMrkvArrays_base" : CondMrkvArrays_base_c,
        "MrkvArray" : MrkvArray_base_c, 
        "CondMrkvArrays" : CondMrkvArrays_base_c,
        "MrkvArray_recession" : MrkvArray_recession_c,
        "CondMrkvArrays_recession" : CondMrkvArrays_recession_c,
        "MrkvArray_recessionUI" : MrkvArray_recessionUI_c,
        "CondMrkvArrays_recessionUI" : CondMrkvArrays_recessionUI_c,
        "MrkvArray_recessionTaxCut" : MrkvArray_recessionTaxCut_c,
        "CondMrkvArrays_recessionTaxCut" : CondMrkvArrays_recessionTaxCut_c,
        "MrkvArray_recessionCheck" : MrkvArray_recessionCheck_c,
        "CondMrkvArrays_recessionCheck" : CondMrkvArrays_recessionCheck_c, 
        'pLogInitMean': pLogInitMean_c,  # SCF: avg quarterly perm income at age 25 (per group)
        'pLogInitStd': pLogInitStd_c,       # σ_g kept group-specific
        "MrkvPrbsInit" : np.array(list(init_mrkv_dist_c)),
        'Urate_normal' : Urate_normal_c,
        'Urate_recession' : Urate_recession_c,
        'EducType' : 2}
    init_college = init_dropout.copy()
    init_college.update(adj_college)
    
        
    # Population share of each type (at present only one type)    
    # TypeShares = [1.0]
    
    # Define a dictionary to represent the baseline scenario
    base_dict = {'shock_type' : "base",
                 'UpdatePrb' : 1.0,
                 'Splurge' : Splurge
                 }
    # Define a dictionary to mutate baseline for the recession
    recession_changes = {
                 'shock_type' : "recession",
                 }
    UI_changes = {
                 'shock_type' : "UI",
                 }
    recession_UI_changes = {
                 'shock_type' : "recessionUI",
                 }
    TaxCut_changes = {
                 'shock_type' : "TaxCut",
                 }
    recession_TaxCut_changes = {
                 'shock_type' : "recessionTaxCut",
                 }
    Check_changes = {
                 'shock_type' : "Check",
                 }
    recession_Check_changes = {
                 'shock_type' : "recessionCheck",
                 }
    # sticky_e_changes = {
    #              'UpdatePrb' : UpdatePrb
    #              }
    # frictionless_changes = {
    #              'UpdatePrb' : 1.0
    #              }
    
    
        
    # Parameters for AggregateDemandEconomy economy
    intercept_prev = np.ones((num_base_MrkvStates,num_base_MrkvStates ))    # Intercept of aggregate savings function
    slope_prev = np.zeros((num_base_MrkvStates,num_base_MrkvStates ))       # Slope of aggregate savings function
                                                    # Elasticity of productivity to consumption
    
    num_max_iterations_solvingAD = 15
    convergence_tol_solvingAD = 1E-3
    Cfunc_iter_stepsize       = 1
    act_T = 400

    if Parametrization in ('Reduced_Run', 'Smoke_Test', 'HS_Only'):
        T_sim = 22
        num_max_iterations_solvingAD = 5
        convergence_tol_solvingAD = 1E-2
        act_T = 100

    # Speedup test (Idea F): allow env-var override of AD convergence tol for
    # qe_fidelity_fast experiments. Loosening from 1e-3 to 1e-2 typically cuts
    # AD iters from ~5 to ~3. Per plans/20260504-1300h_qe_fidelity_speedup_systematic_test.md.
    import os as _os_ad_tol
    _ad_tol_env = _os_ad_tol.environ.get('HAFISCAL_AD_CONVERGENCE_TOL', '').strip()
    if _ad_tol_env:
        try:
            convergence_tol_solvingAD = float(_ad_tol_env)
            print(f'[ad-tol] HAFISCAL_AD_CONVERGENCE_TOL override: convergence_tol_solvingAD = {convergence_tol_solvingAD}')
        except ValueError:
            print(f'[ad-tol] WARNING: HAFISCAL_AD_CONVERGENCE_TOL={_ad_tol_env!r} not a number; ignoring')
    _ad_iter_env = _os_ad_tol.environ.get('HAFISCAL_AD_MAX_ITER', '').strip()
    if _ad_iter_env:
        try:
            num_max_iterations_solvingAD = int(_ad_iter_env)
            print(f'[ad-tol] HAFISCAL_AD_MAX_ITER override: num_max_iterations_solvingAD = {num_max_iterations_solvingAD}')
        except ValueError:
            print(f'[ad-tol] WARNING: HAFISCAL_AD_MAX_ITER={_ad_iter_env!r} not an int; ignoring')
        if Parametrization == 'Smoke_Test':
            # Total MC agents across types; too small for moment stability.
            AgentCountTotal = 100
        elif Parametrization == 'HS_Only':
            # Single HS cohort (100% population share). 1500 leaves a 25%
            # margin above the ~1200 minimum for the Markov shuffle to be
            # in the "every state has J_min agents" regime (when shuffle
            # is later wired in). Without the shuffle, 1500 already gives
            # a per-cohort N comparable to MC-med per-type at full
            # Reduced_Run scale (1054 / type), but with all the agents
            # concentrated in HS instead of split across the 3 cohorts.
            AgentCountTotal = 1500
        else:
            # Minimum for reduced validation / method comparison (not full Baseline 10k).
            AgentCountTotal = 5000
    
    # Make a dictionary to specify a Cobb-Douglas economy
    init_ADEconomy = {'intercept_prev': intercept_prev,
                         'slope_prev': slope_prev,
                         'ADelasticity' : 0.0,
                         'demand_ADelasticity' : ADelasticity,
                         'Cfunc_iter_stepsize' : Cfunc_iter_stepsize,
                         'MrkvArray' : MrkvArray_base_h,
                         'MrkvArray_recession' : MrkvArray_recession_h,
                         'MrkvArray_recessionUI' : MrkvArray_recessionUI_h,
                         'MrkvArray_recessionTaxCut' : MrkvArray_recessionTaxCut_h,
                         'MrkvArray_recessionCheck' : MrkvArray_recessionCheck_h,
                         'num_base_MrkvStates' : num_base_MrkvStates,
                         'num_experiment_periods' : num_experiment_periods,
                         "MrkvArray_base" : MrkvArray_base_h, 
                         'CgridBase' : CgridBase,
                         'EconomyMrkvNow_init': 0,
                         'act_T' : act_T,
                         'TaxCutContinuationProb_Rec' : TaxCutContinuationProb_Rec,
                         'TaxCutContinuationProb_Bas' : TaxCutContinuationProb_Bas
                         }
    
    # HS_Only override: mask out dropout and college cohorts so the HS
    # cohort gets 100% of AgentCountTotal. The 3-cohort BaseTypeList
    # infrastructure stays intact downstream; consumers must skip the
    # masked cohorts when AgentCount==0 (test_asymptotic_equality_revised
    # already does this in setup_economy after this commit).
    # College_Beta_Het (added 2026-05-13): like HS_Only but for College
    # cohort, AND keeps Baseline's DiscFacCount=7 (= full beta heterogeneity).
    # Used for binding TM-a aCount/aMax grid-sufficiency tests since College
    # high-beta agents reach high aNrm and stress the asset grid upper end.
    # See feedback_grid_convergence_test_in_college_beta_het.md.
    effective_EducShares = data_EducShares
    if Parametrization == 'HS_Only':
        effective_EducShares = [0.0, 1.0, 0.0]
    elif Parametrization == 'College_Beta_Het':
        effective_EducShares = [0.0, 0.0, 1.0]

    if OutputFor=='_Main.py':

        return [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,\
                 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,\
                 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates, \
                 effective_EducShares, max_recession_duration, num_experiment_periods,\
                 recession_changes, UI_changes, recession_UI_changes,\
                 TaxCut_changes, recession_TaxCut_changes, Check_changes, recession_Check_changes]
            
    elif OutputFor=='_Model.py':

        return [make_macro_mrkv_array_recession, make_cond_mrkv_arrays_recession, make_full_mrkv_array, T_sim, \
                 make_cond_mrkv_arrays_base, make_cond_mrkv_arrays_recession_ui]            
            
    elif OutputFor=='_Output_Results.py':

        return [max_recession_duration, Rspell, Rfree_base, figs_dir_FullRun, CRRA] 