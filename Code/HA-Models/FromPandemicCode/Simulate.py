def Simulate(Run_Dict,figs_dir,Parametrization='Baseline'):
    """
    Math reference (shorthand "math-derive"):
        history/20260331-mathematical-derivations-TM-MC-convergence.md
    Appendix reference (shorthand "math-derive-appendix"):
        history/20260331-mathematical-derivations-appendix.md
    Harmenberg / BST (Type A--B aggregates):
        history/20260402-reduced-run-harmenberg-output-type-map.md
    Harmenberg math (shorthand "math-derive-harm"):
        history/20260331-mathematical-derivations-harmenberg.md

    Optional ``Run_Dict`` keys for ``sim_method`` TM paths:
        ``tm_mCount`` (int, default 50) — grid points for 1D TM.
        ``tm_neutral_measure`` (bool, default False) — if True, build TM and
        propagate under Harmenberg's neutral measure Q while solving under P.
        This makes 1D TM aggregation exact for p-linear quantities:
            E_P[p * f(m)] = E_P[p] * E_Q[f(m)]
        — math-derive-harm (neutral-identity); BST ApndxHarKmenberg Theorem 1.
        Default False preserves legacy behavior; ``AggFiscalMAIN_reduced.py``
        sets True for the reduced reproduce path.
        ``tm_compute_welfare`` (bool, default False) — if True, baseline
        ``run_experiment_tm`` also computes ``mean_uprime_kernel`` and
        ``mean_felicity_kernel`` (``tm_methods.compute_kernels``). Policy /
        ``Welfare.py`` integration is not wired yet; see
        ``plans/kernel-integration-spec.md``.
    """
    
    import os as _os_early
    from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
    try:
        from AggFiscalModel import DualAggFiscalType
        _HAS_DUAL = True
    except ImportError:
        _HAS_DUAL = False
    # Optional: per-period E[pLvl] normalization mixin to remove the
    # MC permanent-income-shock drift identified in
    # runs/phase_a2_baseline_drift_findings.md. Activate by setting
    # HAFISCAL_NORMALIZE_PLVL=1 in the environment.
    _USE_NORMALIZED = _os_early.environ.get('HAFISCAL_NORMALIZE_PLVL', '').strip() in ('1', 'true', 'yes')
    _NormalAggCls = None
    _NormalDualCls = None
    if _USE_NORMALIZED:
        try:
            from AggFiscalModel import NormalizedAggFiscalType as _NormalAggCls
        except ImportError:
            _USE_NORMALIZED = False
        try:
            from AggFiscalModel import NormalizedDualAggFiscalType as _NormalDualCls
        except ImportError:
            _NormalDualCls = None
    from HARK.distributions import DiscreteDistribution
    from income_process_sst import (
        build_unemployed_inc_shk_dstn,
        effective_pLvl_growth,
        effective_perm_shock_periods_for_t_age,
    )
    from time import time
    import numpy as np
    from copy import deepcopy
    from OtherFunctions import save_as_pickle_under_var_name, save_as_pickle
    from tm_methods import (
        calculate_NPV,
        compute_baseline_tm_data,
        run_ad_tm,
        run_experiment_tm,
        run_experiment_tm_nonbase,
        unemployment_rate_for_tm_synthetic_pLvl,
    )
    import os
    import sys
    
    # Import progress tracking
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from hafiscal_progress import profiler, substep, progress, profile_function
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
        class DummyProfiler:
            def sample_memory(self, *args): pass
            def record_time(self, *args, **kwargs): pass
        profiler = DummyProfiler()
    
    from Parameters import return_parameters 
    
    [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,\
    DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,\
    convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates, \
    data_EducShares, max_recession_duration, num_experiment_periods,\
    recession_changes, UI_changes, recession_UI_changes,\
    TaxCut_changes, recession_TaxCut_changes, Check_changes, recession_Check_changes] = return_parameters(Parametrization=Parametrization,OutputFor='_Main.py')
              
    
    mystr = lambda x : '{:.2f}'.format(x)

    # GLP-1 mode: maximally reduced run — single college type, point discount
    # factor, fixed recession duration, TM only.
    # AD flags are now respected from Run_Dict (not forced off).
    GLP1 = Run_Dict.get('GLP1', False)
    if GLP1:
        sim_method = 'TM'
        Run_Dict['sim_method'] = 'TM'

    ## Which experiments to run / plots to show
    Run_Baseline            = Run_Dict['Run_Baseline']
    Run_Recession           = Run_Dict['Run_Recession ']
    Run_Check_Recession     = Run_Dict['Run_Check_Recession'] 
    Run_UB_Ext_Recession    = Run_Dict['Run_UB_Ext_Recession']
    Run_TaxCut_Recession    = Run_Dict['Run_TaxCut_Recession']
    Run_Check               = Run_Dict['Run_Check'] 
    Run_UB_Ext              = Run_Dict['Run_UB_Ext'] 
    Run_TaxCut              = Run_Dict['Run_TaxCut']
    Run_AD                  = Run_Dict['Run_AD ']
    Run_1stRoundAD          = Run_Dict['Run_1stRoundAD']
    Run_NonAD               = Run_Dict['Run_NonAD']
    sim_method              = Run_Dict.get('sim_method', 'MC')  # 'MC', 'TM', or 'both'

    # TM / Harmenberg — see docstring for math-derive-harm and BST references.
    # neutral_measure must be consistent across baseline, experiments, and AD
    # so that the Q-ergodic feeds into Q-experiment propagation correctly
    # (math-derive-harm §3, §7; tm_methods._build_period_tm).
    tm_mCount = int(Run_Dict.get('tm_mCount', 50))
    tm_neutral_measure = bool(Run_Dict.get('tm_neutral_measure', False))
    tm_compute_welfare = bool(Run_Dict.get('tm_compute_welfare', False))

    use_dual_MC = sim_method == 'dual_MC'
    use_MC = sim_method in ('MC', 'both') or use_dual_MC
    use_TM = sim_method in ('TM', 'both')
    if use_dual_MC and not _HAS_DUAL:
        raise ImportError(
            "sim_method='dual_MC' requires HARK with DualMeasureMixin. "
            "Install with: uv pip install -e /path/to/HARK"
        ) 
    
    
    if Parametrization.find('PVSame')>0:
        Run_Recession           = False
        Run_UB_Ext_Recession    = False
        Run_1stRoundAD          = False
        Run_UB_Ext              = False
    
    try:
        os.mkdir(figs_dir)
    except OSError:
        print ("Directory %s already exists" % figs_dir)
    else:
        print ("Successfully created the directory %s " % figs_dir)
    
    
    #%% 
    
    # Count total shock types to run for progress tracking
    shock_types_count = sum([
        Run_Recession, Run_Check_Recession, Run_UB_Ext_Recession, 
        Run_TaxCut_Recession, Run_Check, Run_UB_Ext, Run_TaxCut
    ])
    shock_types_done = [0]  # Mutable container for closure
    
    # Setting up AggDemandEconmy
    
    substep("Setting up agent types and economy", expected_duration_min=1)
    progress(f"Parametrization: {Parametrization}")
    progress(f"Number of shock types to simulate: {shock_types_count}")
    
    # Make education types
    num_types = 3
    # This is not the number of discount factors, but the number of household types
    
    with profile_function("setup_agent_types"):
        if _USE_NORMALIZED and _NormalAggCls is not None:
            _AgentCls = (_NormalDualCls if (use_dual_MC and _NormalDualCls is not None)
                         else _NormalAggCls)
            for _d in (init_dropout, init_highschool, init_college):
                _d['normalize_pLvl'] = True
            print(f"[normalize_pLvl] using {_AgentCls.__name__} (HAFiscalNormalizationMixin active)")
        else:
            _AgentCls = DualAggFiscalType if use_dual_MC else AggFiscalType
        InfHorizonTypeAgg_d = _AgentCls(**init_dropout)
        InfHorizonTypeAgg_d.cycles = 0
        InfHorizonTypeAgg_h = _AgentCls(**init_highschool)
        InfHorizonTypeAgg_h.cycles = 0
        InfHorizonTypeAgg_c = _AgentCls(**init_college)
        InfHorizonTypeAgg_c.cycles = 0
        AggDemandEconomy = AggregateDemandEconomy(**init_ADEconomy)
        InfHorizonTypeAgg_d.get_economy_data(AggDemandEconomy)
        InfHorizonTypeAgg_h.get_economy_data(AggDemandEconomy)
        InfHorizonTypeAgg_c.get_economy_data(AggDemandEconomy)
        BaseTypeList = [InfHorizonTypeAgg_d, InfHorizonTypeAgg_h, InfHorizonTypeAgg_c ]
          
    # Fill in the Markov income distribution for each base type
    # NOTE: THIS ASSUMES NO LIFECYCLE
    # HARK 0.17.0 FIX: Sync IncShkDstn seeds to match HARK 0.14.1 (763607780)
    # The IncShkDstn distributions use their own RNG for draw_events(), which must
    # produce identical draws between HARK versions for numerical identity.
    for BaseType in BaseTypeList:
        _p0 = BaseType.IncShkDstn[0]
        if isinstance(_p0, (list, tuple)):
            for _d in _p0:
                _d.seed = 763607780
                _d.reset()
        else:
            _p0.seed = 763607780
            _p0.reset()

    for ThisType in BaseTypeList:
        _p0 = ThisType.IncShkDstn[0]
        # Markov: period-0 entry is a list of state-specific dstns; otherwise HARK BufferStockIncShkDstn.
        emp_src = _p0[0] if isinstance(_p0, (list, tuple)) else _p0
        EmployedIncShkDstn = deepcopy(emp_src)
        emp0 = emp_src
        p_on = getattr(ThisType, 'perm_shocks_during_unemployment', False)
        t_on = getattr(ThisType, 'tran_shocks_during_unemployment', False)
        IncShkDstn_unemp = build_unemployed_inc_shk_dstn(
            emp0, ThisType.IncUnemp, p_on, t_on)
        IncShkDstn_unemp_nobenefits = build_unemployed_inc_shk_dstn(
            emp0, ThisType.IncUnempNoBenefits, p_on, t_on)
        IncShkDstn_unemp.seed = 763607780
        IncShkDstn_unemp.reset()
        IncShkDstn_unemp_nobenefits.seed = 763607780
        IncShkDstn_unemp_nobenefits.reset()
        # Phase 1 consistency check: unemployed PermShk variance must match the flag.
        # Catches drift between perm_shocks_during_unemployment (Harmenberg vs QE-matching)
        # and the actual atom data, in case a future code path bypasses build_unemployed_inc_shk_dstn.
        _u_perm_atoms = np.asarray(IncShkDstn_unemp.atoms[0], dtype=float).ravel()
        _u_has_perm_var = bool(np.var(np.log(np.where(_u_perm_atoms > 0, _u_perm_atoms, 1.0))) > 1e-10)
        if bool(p_on) != _u_has_perm_var:
            raise ValueError(
                f"perm_shocks_during_unemployment={p_on} but unemployed IncShkDstn "
                f"PermShk variance > 0 is {_u_has_perm_var} (atoms={_u_perm_atoms.tolist()}). "
                f"Set HAFISCAL_PERM_DURING_UNEMP={'on' if _u_has_perm_var else 'off'} or "
                f"rebuild the unemployed IncShkDstn to match the flag."
            )
        # bug_fix (6-state): U3/U4 extension slots pay no-benefits income in non-UI scenarios.
        # (num_base_MrkvStates-2-UBspell_normal) == Policy_ExtraBenefitQuarters (=2 bug_fix, 0 legacy
        # -> byte-identical legacy). Matches the validated welfare6_scenario.py construction.
        ThisType.IncShkDstn = [[emp_src] + [IncShkDstn_unemp]*UBspell_normal + [IncShkDstn_unemp_nobenefits]*(num_base_MrkvStates - 2 - UBspell_normal) + [IncShkDstn_unemp_nobenefits]]
        ThisType.IncShkDstn_base = ThisType.IncShkDstn
        
        IncShkDstn_recession = [ThisType.IncShkDstn[0]*(2*(num_experiment_periods+1))] # for normal, rec, recovery  
        ThisType.IncShkDstn_recession = IncShkDstn_recession
        # BUG-050: recessionUI income == recession income. Under LEGACY (4-state) encoding this is
        # fine because the UI extension is delivered via a different MrkvArray_recessionUI (the
        # freeze-window keeps agents in benefit-paying states longer). Under the BUG_FIX (6-state)
        # encoding, the extension must instead be delivered as INCOME — the U3/U4 extension states
        # should pay WITH-benefits income (IncShkDstn_unemp) during the UI window — but this copies
        # the plain-recession assignment where U3/U4 pay no-benefits. Result: recessionUI ≡ recession
        # ⇒ the UI multiplier is 0/0 = nan (guarded loudly in Output_Results.py). Proper fix: build a
        # UIStatesIncShkDstn overlay analogous to the TaxCutStatesIncShkDstn block below. This
        # bug_fix-encoding MULTIPLIER income wiring is a separately-tracked OPEN behavior item — see
        # BUGS_private/HAFiscal_BUG-050_recessionUI_income_not_wired.md (guarded 2026-06-04, proper
        # fix deferred). NOTE (2026-06-10): UI WELFARE is reportable — ui_rec/ui_rec_AD ARE headline
        # cells via MC+CRN+stratified-shuffle (see conclusions_private/
        # 2026-06-10_welfare_method_unified_MC.md); only ui_norec is excluded (0/0 by construction).
        ThisType.IncShkDstn_recessionUI = IncShkDstn_recession

        # BUG-023 fix: was `atoms[0][1] *= TaxCutIncFactor`, which mutated
        # ONE element of the PermShk atom array (atoms[0] = PermShk,
        # atoms[1] = TranShk per HARK convention). Intended behavior is
        # to scale every joint atom's TranShk by TaxCutIncFactor.
        # See BUGS_private/HAFiscal_BUG-023_taxcut_atoms_typo.md
        EmployedIncShkDstn.atoms = (
            np.asarray(EmployedIncShkDstn.atoms[0], dtype=np.float64),
            np.asarray(EmployedIncShkDstn.atoms[1], dtype=np.float64) * ThisType.TaxCutIncFactor,
        )
        TaxCutStatesIncShkDstn = [EmployedIncShkDstn] + [IncShkDstn_unemp]*UBspell_normal + [IncShkDstn_unemp_nobenefits]*(num_base_MrkvStates - 2 - UBspell_normal) + [IncShkDstn_unemp_nobenefits]
        IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
        # Tax states are 2,3 (q1) 4,5 (q2) ... 16,17 (q8)
        for i in range(2*num_base_MrkvStates,18*num_base_MrkvStates,1):
            IncShkDstn_recessionTaxCut[0][i] =  TaxCutStatesIncShkDstn[np.mod(i,num_base_MrkvStates)]
        ThisType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
        
        ThisType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

    if use_dual_MC:
        for ThisType in BaseTypeList:
            ThisType.setup_Q_measure()

    # Make the overall list of types
    TypeList = []
    n = 0
    if GLP1:
        # GLP-1: single college type with point discount factor
        glp1_educ_idx = 2  # college
        glp1_DiscFac = DiscFacDstns[glp1_educ_idx].atoms[0][0]
        ThisType = deepcopy(BaseTypeList[glp1_educ_idx])
        ThisType.AgentCount = 1  # TM doesn't need agents, but structure requires it
        ThisType.DiscFac = glp1_DiscFac
        ThisType.seed = 0
        TypeList.append(ThisType)
        n = 1
        progress(f"GLP-1 mode: 1 college type, DiscFac={glp1_DiscFac:.4f}")
    else:
      # HAFISCAL_AGENTCOUNT_{D,H,C} env-var overrides for per-cohort N
      # (Phase H-0 shuffle diagnostic). When set, overrides the
      # AgentCountTotal × data_EducShares[e] product for cohort e; per-bin
      # split via DiscFacDstns[e].pmv[b] still applies.
      _per_cohort_N_env = {
          0: _os_early.environ.get('HAFISCAL_AGENTCOUNT_D', '').strip(),
          1: _os_early.environ.get('HAFISCAL_AGENTCOUNT_H', '').strip(),
          2: _os_early.environ.get('HAFISCAL_AGENTCOUNT_C', '').strip(),
      }
      _per_cohort_N = {e: int(v) for e, v in _per_cohort_N_env.items() if v}
      if _per_cohort_N:
          print(f'[agentcount-override] per-cohort N: {_per_cohort_N}')
      # HAFISCAL_SEED_OFFSET: adds an offset to ThisType.seed for multi-seed
      # diagnostic runs (Phase H-0 shuffle validation needs 3+ seed variants).
      _seed_offset = int(_os_early.environ.get('HAFISCAL_SEED_OFFSET', '0'))
      if _seed_offset:
          print(f'[seed-offset] HAFISCAL_SEED_OFFSET={_seed_offset}')
      for e in range(num_types):
        for b in range(DiscFacCount):
            DiscFac = DiscFacDstns[e].atoms[0][b]
            # Standard-config AgentCount (the floored value used when no override).
            standard_AgentCount = int(np.floor(AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[b]))
            if e in _per_cohort_N:
                AgentCount = int(np.floor(_per_cohort_N[e]*DiscFacDstns[e].pmv[b]))
            else:
                AgentCount = standard_AgentCount
            ThisType = deepcopy(BaseTypeList[e])
            ThisType.AgentCount = AgentCount
            ThisType.DiscFac = DiscFac
            ThisType.seed = n + _seed_offset
            # Population-rescale factor for edu-share-respecting aggregation.
            # = standard_AgentCount / actual_AgentCount.
            # Under standard config, AgentCount = standard_AgentCount → factor = 1.0
            # exactly (so behavior matches when no override is in effect).
            # Under cohort-N override, factor != 1 and corrects the per-cohort
            # weight to match population proportions.
            # See plans/20260506-1640h_edu_share_aggregation_correction.md.
            ThisType.pop_rescale_factor = (
                standard_AgentCount / AgentCount if AgentCount > 0 else 1.0
            )
            TypeList.append(ThisType)
            n += 1
    #base_dict['Agents'] = TypeList    
    
    progress(f"Created {len(TypeList)} agent types ({DiscFacCount} discount factors x {num_types} education types)")

    # MC variance-reduction shuffle (opt-in via env vars). Sets agent attributes
    # that HARK 0.17's simulate path reads (HARK/core.py: hasattr checks for
    # income_shuffle / mc_shuffle). When on, replaces stochastic Markov-state
    # transitions and per-period income-shock draws with deterministic ones
    # matching expected frequencies. Pattern from EstimAggFiscalMAIN.py:761-773.
    # Per plans/20260408-1213h_single-cohort-plus-shuffle-implementation.md,
    # shuffle requires N >= per-cohort minimum-occupancy threshold for full
    # determinism (Smoke_Test N=100 may be below threshold for some cohorts).
    _mc_shuffle = _os_early.environ.get('HAFISCAL_MC_SHUFFLE', '') == '1'
    _income_shuffle = _os_early.environ.get('HAFISCAL_INCOME_SHUFFLE', '') == '1'
    _markov_shuffle = _os_early.environ.get('HAFISCAL_MARKOV_SHUFFLE', '') == '1'
    if _mc_shuffle or _income_shuffle or _markov_shuffle:
        for _t in BaseTypeList + TypeList:
            _t.mc_shuffle = _mc_shuffle
            _t.income_shuffle = _income_shuffle
            _t.markov_shuffle = _markov_shuffle
        print(f'[shuffle] mc_shuffle={_mc_shuffle}  income_shuffle={_income_shuffle}  markov_shuffle={_markov_shuffle}')

    # CDC-MOD-BUG033: Dispatch wiring for the a-indexed TM. Reads Run_Dict['tm_a_indexed'] and propagates the flag onto each agent type. ESC version: same dispatch (the flag itself is interpretation-independent); the agent attribute would route to ESC-faithful kernels under that future runnable path. See plans/20260425-2102h_cdc-implementation-map.md row 33.2.
    # BUG-033: a-indexed TM dispatch (splurge-in-budget budget-identity fix).
    # The a-indexed TM is the CANONICAL production method (m-indexed is
    # structurally biased under splurge-in-budget; see
    # BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md). Routed here via
    # Run_Dict['tm_a_indexed'] = True, set from the HAFISCAL_TM_A_INDEXED env
    # var by AggFiscalMAIN_reduced.py — which do_all.py Step-5a exports (since
    # 2026-06-11) unless HAFISCAL_QE_FIDELITY=1. Default False is kept for
    # non-production callers.
    _tm_a_indexed = bool(Run_Dict.get('tm_a_indexed', False))
    if _tm_a_indexed:
        for _ag in TypeList:
            _ag.tm_a_indexed = True
        progress("tm_a_indexed=True: routing baseline + experiments through a-indexed TM (BUG-033)")

    AggDemandEconomy.agents = TypeList
    
    substep("Initial agent solve", expected_duration_min=5)
    t0 = time()
    with profile_function("initial_economy_solve", input_size=len(TypeList)):
        AggDemandEconomy.solve()
    t1 = time()
    progress(f"Initial solve completed in {t1-t0:.1f}s for {len(TypeList)} agents")

    # Compute TM baseline BEFORE MC setup, because switch_to_counterfactual_mode
    # deletes agent.solution (it's designed for MC which re-solves per experiment).
    # The TM baseline needs the base solution to extract consumption policies.
    # Also needed when MC uses TM-initialized agents (mc_use_tm_init).
    baseline_tm_data = None
    need_tm_baseline = use_TM or (use_MC and Run_Dict.get('mc_use_tm_init', True))
    if need_tm_baseline:
        substep("Computing TM baseline data", expected_duration_min=1)
        t0 = time()
        with profile_function("tm_baseline_compute"):
            baseline_tm_data = compute_baseline_tm_data(
                AggDemandEconomy,
                mCount=tm_mCount,
                neutral_measure=tm_neutral_measure,
            )
        t1 = time()
        progress(f"TM baseline data computed in {t1-t0:.1f}s")

    if use_MC:
        AggDemandEconomy.reset()
        for agent in AggDemandEconomy.agents:
            agent.initialize_sim()
            agent.AggDemandFac = 1.0
            agent.RfreeNow = 1.0
            agent.CaggNow = 1.0

        # If TM baseline data is available, initialize MC agents from the
        # TM ergodic distribution instead of running a long burn-in.
        # Then run a short warmup (24 periods ≈ 2 business cycles) to let
        # any residual distributional mismatch settle.
        mc_warmup = Run_Dict.get('mc_warmup', 24)
        if baseline_tm_data is not None and Run_Dict.get('mc_use_tm_init', True):
            substep("Initializing MC from TM ergodic + warmup", expected_duration_min=0.5)
            t0 = time()
            for i, agent in enumerate(AggDemandEconomy.agents):
                bd_i = baseline_tm_data[i]
                tm_a_init = bd_i.get('tm_a_indexed', False)

                if tm_a_init:
                    # MC ⇄ TM-a Phase 1 init: sample (j, aNrm) DIRECTLY from
                    # the TM-a ergodic distribution. The aNrm grid IS what
                    # TM-a tracks — no cFunc inversion needed (unlike the
                    # TM-m path which samples mNrm and converts).
                    # See plans/20260503-1437h_mc_tma_companion_and_drift.md.
                    erg = bd_i['ergodic']
                    grid = bd_i['dist_aGrid']
                    A_i = len(grid)
                    J_i = agent.num_base_MrkvStates

                    rng_i = np.random.RandomState(agent.seed)
                    N_i = agent.AgentCount
                    flat_probs = np.asarray(erg) / np.sum(erg)

                    # Sample (j, aNrm) on exact grid points
                    bins = rng_i.choice(len(flat_probs), size=N_i, p=flat_probs)
                    agent_j = bins // A_i
                    agent_aNrm = grid[bins % A_i]
                else:
                    # TM-m init path (existing): sample (j, mNrm), invert via cFunc
                    erg = bd_i.get('cohort_ergodic')
                    if erg is None:
                        erg = bd_i['ergodic']
                    grid = bd_i['dist_mGrid']
                    M_i = len(grid)
                    J_i = agent.num_base_MrkvStates

                    rng_i = np.random.RandomState(agent.seed)
                    N_i = agent.AgentCount
                    flat_probs = erg / np.sum(erg)

                    # Sample (j, mNrm) on exact grid points (no jitter)
                    bins = rng_i.choice(len(flat_probs), size=N_i, p=flat_probs)
                    agent_j = bins // M_i
                    agent_mNrm = grid[bins % M_i]

                    # Convert mNrm → aNrm via base cFunc
                    sol_i = agent.solution[0]
                    agent_aNrm = np.zeros(N_i)
                    for j in range(J_i):
                        mask = agent_j == j
                        if np.any(mask):
                            c = sol_i.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
                            agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)

                # Draw ages from ergodic age distribution
                L = agent.LivPrb[0][0]
                T_ag = agent.T_age
                age_probs = np.array([L**(k-1) for k in range(1, T_ag + 1)])
                age_probs /= np.sum(age_probs)
                agent_ages = rng_i.choice(T_ag, size=N_i, p=age_probs) + 1

                # Draw log(pLvl) from the ergodic cross-sectional distribution.
                #
                # Model structure: PermShk has variance σ²_ψ in employed state (j=0)
                # but PermShk=1 (zero variance) in all unemployment states (j>0).
                # So only employed periods contribute to pLvl dispersion:
                #   log(pLvl) = log(pLvl_init) + t·log(G)
                #               + Σ_{s ∈ employed} log(PermShk_s)
                # Cohort with HARK ``t_age == t`` has ``t-1`` stochastic perm-shock
                # draws (BUG-003: first growth step is deterministic). Unemployed
                # periods add no shock variance, so scale by ``(1-u)`` per
                # ``compute_pLvl_distribution`` / ``effective_perm_shock_periods_for_t_age``.
                u_p = unemployment_rate_for_tm_synthetic_pLvl(bd_i, agent)
                g_lvl = effective_pLvl_growth(agent, u_p)
                pLogMean = agent.pLogInitMean
                pLogStd = getattr(agent, 'pLogInitStd',
                                  getattr(agent, 'pLvlInitStd', 0.0))
                PermShkDstn_0 = agent.IncShkDstn_base[0][0]
                log_ps = np.log(PermShkDstn_0.atoms[0])
                ps_var = (np.dot(PermShkDstn_0.pmv, log_ps**2)
                          - np.dot(PermShkDstn_0.pmv, log_ps)**2)
                effective_emp_periods = effective_perm_shock_periods_for_t_age(
                    agent_ages, agent, u_p)
                log_pLvl = rng_i.normal(pLogMean, pLogStd, N_i)
                log_pLvl += agent_ages * np.log(g_lvl)
                log_pLvl += effective_emp_periods * (-ps_var / 2.0)
                log_pLvl += rng_i.normal(0, np.sqrt(ps_var * effective_emp_periods))
                agent_pLvl = np.exp(log_pLvl)

                # Inject into agent state
                agent.state_now['aNrm'][:] = agent_aNrm
                agent.state_now['pLvl'][:] = agent_pLvl
                # aLvl = aNrm * pLvl (BUG-031: state_now['aLvl'] is household-total
                # under CDC; for ESC the (1-Splurge) factor is applied at READ time
                # via _aLvl_for, so we set aLvl as the unfactored product here).
                # Without this line, aLvl stays at NaN from agent.initialize_sim()
                # → first sim_one_period reads NaN → propagates → drift test
                # immediately-post-init shows safe_log(NaN→1e-12)=-27.6 instead
                # of the actual init distribution. Discovered 2026-05-03 in the
                # first companion-mode MC run.
                if 'aLvl' in agent.state_now:
                    agent.state_now['aLvl'][:] = agent_aNrm * agent_pLvl
                agent.shocks['Mrkv'][:] = agent_j
                if hasattr(agent, 't_age') and agent.t_age is not None:
                    agent.t_age[:] = agent_ages
                agent.Cratio = 1.0
                agent.state_now['PlvlAgg'] = 1.0

                if use_dual_MC and hasattr(agent, 'state_now_Q'):
                    for k, v in agent.state_now.items():
                        if isinstance(v, np.ndarray):
                            agent.state_now_Q[k] = v.copy()
                        else:
                            agent.state_now_Q[k] = v

            # Diagnostic: capture moments IMMEDIATELY post-init (pre-warmup) so
            # we can distinguish "init is wrong" from "warmup drifts away".
            if os.environ.get('HAFISCAL_DRIFT_DIAG_POST_INIT', '0') == '1':
                try:
                    import _tm_a_drift as _diag_drift
                    for i_diag, agent_diag in enumerate(AggDemandEconomy.agents):
                        bd_di = baseline_tm_data[i_diag]
                        if not bd_di.get('tm_a_indexed', False):
                            continue
                        mc_post_init = _diag_drift.compute_mc_empirical_moments(
                            agent_diag.state_now['aLvl'], agent_diag.state_now['pLvl'],
                        )
                        print(f"[diag agent_{i_diag} POST-INIT pre-warmup] "
                              f"mean_log_a={mc_post_init['mean_log_a']:.4f}  "
                              f"var_log_a={mc_post_init['var_log_a']:.4f}  "
                              f"mass_at_zero={mc_post_init['mass_at_zero']:.3f}  "
                              f"mean_log_p={mc_post_init['mean_log_p']:.4f}  "
                              f"var_log_p={mc_post_init['var_log_p']:.4f}")
                        # Also show what we *intended* to init with
                        print(f"[diag agent_{i_diag} POST-INIT intended] "
                              f"aNrm samples (first 5): {agent_diag.state_now['aNrm'][:5]}  "
                              f"aLvl samples (first 5): {agent_diag.state_now['aLvl'][:5]}  "
                              f"pLvl samples (first 5): {agent_diag.state_now['pLvl'][:5]}")
                except Exception as _de:
                    print(f"[diag] post-init diagnostic failed: {_de!r}")

            # Short warmup to let distributional mismatch settle
            for t in range(mc_warmup):
                for agent in AggDemandEconomy.agents:
                    agent.sim_one_period()
            t1 = time()
            progress(f"TM-initialized MC with {mc_warmup}-period warmup in {t1-t0:.1f}s")

            # MC ⇄ TM-a Phase 2: drift measurement.
            # Compare empirical MC moments to TM-a's analytical ergodic.
            # Per user direction 2026-05-03: HARD-FAIL on |drift| > 0.03.
            # Disable via HAFISCAL_DRIFT_HARD_FAIL=0 (downgrades to WARN).
            # Skip via HAFISCAL_SKIP_DRIFT_TEST=1 (e.g., for debugging).
            if os.environ.get('HAFISCAL_SKIP_DRIFT_TEST', '0') != '1':
                try:
                    import _tm_a_drift as _drift_mod
                    print('[drift] Computing MC ⇄ TM-a drift after warmup…')
                    _all_pass = True
                    for i, agent in enumerate(AggDemandEconomy.agents):
                        bd_i = baseline_tm_data[i]
                        if not bd_i.get('tm_a_indexed', False):
                            continue   # TM-m branch: drift test not yet wired (Phase 2.5)
                        tma_moments = _drift_mod.compute_tma_analytical_moments(
                            bd_i['ergodic'], bd_i['dist_aGrid'],
                            J=agent.num_base_MrkvStates,
                            agent=agent, unemployment_rate=bd_i.get('u_ergodic'),
                        )
                        # Diagnostic: confirm T_age + analytical pLvl variance
                        print(f"[diag agent_{i}] agent.T_age={getattr(agent, 'T_age', 'N/A')}  "
                              f"u_ergodic={bd_i.get('u_ergodic'):.4f}  "
                              f"analytical mean_log_p={tma_moments.get('mean_log_p', 'N/A'):.4f}  "
                              f"var_log_p={tma_moments.get('var_log_p', 'N/A'):.4f}")
                        mc_moments = _drift_mod.compute_mc_empirical_moments(
                            agent.state_now['aLvl'], agent.state_now['pLvl'],
                        )
                        drift = _drift_mod.measure_drift(tma_moments, mc_moments)
                        ok = _drift_mod.assess_and_report(
                            drift, label=f"agent_{i}", agent=agent,
                        )
                        _all_pass = _all_pass and ok

                        # Extra diagnostic: distribution of aNrm
                        if os.environ.get('HAFISCAL_DRIFT_DIAG_DIST', '0') == '1':
                            import numpy as _np
                            aLvl = agent.state_now['aLvl']
                            pLvl = agent.state_now['pLvl']
                            aNrm_emp = aLvl / _np.where(pLvl > 1e-12, pLvl, 1e-12)
                            for thresh in [1e-9, 1e-6, 1e-3, 1e-2, 0.1, 1.0]:
                                frac = _np.mean(aNrm_emp <= thresh)
                                print(f'[diag agent_{i}] MC fraction with aNrm <= {thresh:g}: {frac:.4f}')
                            qs = _np.percentile(aNrm_emp, [10, 25, 50, 75, 90])
                            print(f'[diag agent_{i}] MC aNrm percentiles 10/25/50/75/90: {qs}')
                            # TM-a percentiles for comparison
                            erg_2d = _np.asarray(bd_i["ergodic"]).reshape(
                                agent.num_base_MrkvStates, len(bd_i["dist_aGrid"]))
                            aNrm_marg = erg_2d.sum(axis=0)
                            aNrm_marg /= aNrm_marg.sum()
                            cdf = _np.cumsum(aNrm_marg)
                            grid = bd_i["dist_aGrid"]
                            tma_qs = [grid[_np.searchsorted(cdf, q)] for q in [0.10, 0.25, 0.50, 0.75, 0.90]]
                            print(f'[diag agent_{i}] TM-a aNrm percentiles 10/25/50/75/90: {tma_qs}')
                    if _all_pass:
                        print('[drift] ✓ all agents within drift threshold')
                except Exception as _drift_err:
                    # If hard_fail is enabled, the assess_and_report raises
                    # RuntimeError and we want it to propagate (hard-fail the run).
                    if isinstance(_drift_err, RuntimeError):
                        raise
                    print(f'[drift] WARNING: drift module failed: {_drift_err!r}')
        else:
            # Standard burn-in (act_T periods)
            substep("MC burn-in", expected_duration_min=5)
            t0 = time()
            AggDemandEconomy.make_history()
            t1 = time()
            progress(f"MC burn-in ({AggDemandEconomy.act_T} periods) in {t1-t0:.1f}s")

        AggDemandEconomy.save_state()
        AggDemandEconomy.switch_to_counterfactual_mode("base")
        AggDemandEconomy.make_idiosyncratic_shock_histories()
    
    output_keys = ['NPV_AggIncome', 'NPV_AggCons', 'AggIncome', 'AggCons']
    if use_dual_MC:
        output_keys += ['AggCons_Q', 'NPV_AggCons_Q']
    
    
    base_dict_agg = deepcopy(base_dict)
    
    # See math-derive-appendix (recession-duration): geometric recession probs
    Rspell = AggDemandEconomy.agents[0].Rspell
    R_persist = 1.-1./Rspell
    recession_prob_array = np.array([R_persist**t*(1-R_persist) for t in range(max_recession_duration)])
    recession_prob_array[-1] = 1.0 - np.sum(recession_prob_array[:-1])
   
    x = np.zeros(len(AggDemandEconomy.agents))
    for i in range(len(AggDemandEconomy.agents)):
        x[i] = AggDemandEconomy.agents[i].AgentCount
       
        
    if Run_Baseline:   
        substep("Running baseline consumption", expected_duration_min=2)

        if use_MC:
            t0 = time()
            with profile_function("baseline_experiment_MC"):
                base_results = AggDemandEconomy.run_experiment(**base_dict_agg, Full_Output = 'ForWelfare')
                save_as_pickle_under_var_name(base_results,figs_dir,locals())
                base_results_full = AggDemandEconomy.run_experiment(**base_dict_agg, Full_Output = True)
                save_as_pickle_under_var_name(base_results_full,figs_dir,locals())
                AggDemandEconomy.store_baseline(base_results['AggCons'])     
            t1 = time()
            print('MC baseline took ' + mystr(t1-t0) + ' seconds.')
            profiler.record_time("baseline_consumption_MC", t1-t0)

        if use_TM:
            t0 = time()
            with profile_function("baseline_experiment_TM"):
                base_results_tm = run_experiment_tm(
                    AggDemandEconomy,
                    shock_type="base",
                    mCount=tm_mCount,
                    neutral_measure=tm_neutral_measure,
                    compute_welfare=tm_compute_welfare,
                )
                if sim_method == 'both':
                    save_as_pickle('base_results_TM', base_results_tm, figs_dir)
                else:
                    save_as_pickle('base_results', base_results_tm, figs_dir)
                if not use_MC:
                    AggDemandEconomy.store_baseline(base_results_tm['AggCons'])
            t1 = time()
            print('TM baseline took ' + mystr(t1-t0) + ' seconds.')
            profiler.record_time("baseline_consumption_TM", t1-t0)
        
        
    #%%         
             
        
    def _fork_dispatch_durations(n_dur, worker, label="dur"):
        """Run worker(t) for t in range(n_dur) in parallel via os.fork.

        Returns a list of results indexed by t. Each child writes its
        result to a tempfile and exits; parent waits and collects.
        Parallelism is bounded so the total inner-worker count does not
        oversubscribe the machine, given that this routine may itself
        be running inside an outer shock-type fork worker.

        Disable with HAFISCAL_NO_FORK=1 (sequential fallback) or
        HAFISCAL_DUR_WORKERS=1.
        """
        # Sequential fallback: no fork support, env override, or n_dur=1.
        if (not hasattr(os, 'fork')
                or os.environ.get('HAFISCAL_NO_FORK', '').strip() in ('1', 'true', 'yes')
                or n_dur <= 1):
            return [worker(t) for t in range(n_dur)]

        env_cap = os.environ.get('HAFISCAL_DUR_WORKERS', '').strip()
        if env_cap.isdigit():
            max_workers = int(env_cap)
        else:
            # Default: assume up to 7 outer shock-type fork workers may
            # be active concurrently (4 recession + 3 norec); divide
            # cores among them. Floor at 1, ceiling at n_dur.
            ncpu = os.cpu_count() or 1
            max_workers = max(1, min(n_dur, ncpu // 8))

        if max_workers <= 1:
            return [worker(t) for t in range(n_dur)]

        import tempfile
        import pickle as _pkl
        import shutil
        tmpdir = tempfile.mkdtemp(prefix=f'hafiscal_{label}_')
        try:
            results = [None] * n_dur
            idx = 0
            while idx < n_dur:
                batch = list(range(idx, min(idx + max_workers, n_dur)))
                child_pids = {}
                for t in batch:
                    pid = os.fork()
                    if pid == 0:
                        try:
                            r = worker(t)
                            with open(os.path.join(tmpdir, f'r_{t}.pkl'), 'wb') as f:
                                _pkl.dump(r, f)
                            os._exit(0)
                        except BaseException as _e:
                            sys.stderr.write(f"[{label}:{t}] FAILED: {_e!r}\n")
                            os._exit(1)
                    else:
                        child_pids[pid] = t
                _failures = []
                for _ in range(len(child_pids)):
                    _pid, _status = os.waitpid(-1, 0)
                    if _status != 0:
                        _failures.append(child_pids.get(_pid, _pid))
                if _failures:
                    raise RuntimeError(
                        f"Duration workers failed: {_failures}. "
                        f"Re-run with HAFISCAL_DUR_WORKERS=1 to debug.")
                for t in batch:
                    with open(os.path.join(tmpdir, f'r_{t}.pkl'), 'rb') as f:
                        results[t] = _pkl.load(f)
                idx += max_workers
            return results
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def run_experiments_all_recessions(dict_changes, AggDemandEconomy):
        t0 = time()
        all_results = []
        avg_results = dict()
        progress(f"Running {max_recession_duration} recession duration variants")

        def _worker(t):
            dictt = base_dict_agg.copy()
            dictt.update(**dict_changes)
            dictt['EconomyMrkv_init'] = list(np.arange(1, AggDemandEconomy.num_experiment_periods + 1) * 2) + [0] * 20
            dictt['EconomyMrkv_init'][0:t + 1] = (np.array(dictt['EconomyMrkv_init'][0:t + 1]) + 1).tolist()
            return AggDemandEconomy.run_experiment(**dictt, Full_Output=True)

        all_results = _fork_dispatch_durations(max_recession_duration, _worker, label="mc_rec")
        for key in output_keys:
            avg_results[key] = np.sum(
                np.array([all_results[t][key] * recession_prob_array[t]
                          for t in range(max_recession_duration)]),
                axis=0,
            )
        t1 = time()
        print('Calculating took ' + mystr(t1 - t0) + ' seconds.')
        profiler.record_time("run_experiments_all_recessions", t1 - t0)
        return [avg_results, all_results]
    
    def run_experiments_no_recessions(dict_changes,AggDemandEconomy):
        
        t0 = time()
        dictt = base_dict_agg.copy()
        dictt.update(**dict_changes)
        dictt['EconomyMrkv_init'] = list(np.arange(1,AggDemandEconomy.num_experiment_periods+1)*2) + [0]*20 
        results = AggDemandEconomy.run_experiment(**dictt, Full_Output = True)
        t1 = time()
        print('Calculating took ' + mystr(t1-t0) + ' seconds.') 
        profiler.record_time("run_experiments_no_recessions", t1-t0)
        return results

    GLP1_recession_duration = Run_Dict.get('GLP1_recession_duration', None)

    def run_experiments_all_recessions_tm(dict_changes, AggDemandEconomy_Routine, baseline_tm_data):
        t0 = time()
        shock_type = dict_changes['shock_type']
        all_results = []
        avg_results = dict()

        if GLP1_recession_duration is not None:
            # Fixed single recession duration (nano-TM mode)
            dur = GLP1_recession_duration
            EconomyMrkv_init = list(np.arange(1, AggDemandEconomy_Routine.num_experiment_periods+1)*2) + [0]*20
            EconomyMrkv_init[0:dur] = (np.array(EconomyMrkv_init[0:dur]) + 1).tolist()
            this_result = run_experiment_tm_nonbase(
                AggDemandEconomy_Routine, shock_type, EconomyMrkv_init,
                baseline_tm_data,
                mCount=tm_mCount,
                neutral_measure=tm_neutral_measure,
            )
            # No averaging needed — just use the single result
            avg_results = this_result
            all_results = [this_result]
        else:
            progress(f"TM: Running {max_recession_duration} recession duration variants")

            def _tm_worker(t):
                EconomyMrkv_init = list(np.arange(1, AggDemandEconomy_Routine.num_experiment_periods + 1) * 2) + [0] * 20
                EconomyMrkv_init[0:t + 1] = (np.array(EconomyMrkv_init[0:t + 1]) + 1).tolist()
                return run_experiment_tm_nonbase(
                    AggDemandEconomy_Routine, shock_type, EconomyMrkv_init,
                    baseline_tm_data,
                    mCount=tm_mCount,
                    neutral_measure=tm_neutral_measure,
                )

            all_results = _fork_dispatch_durations(max_recession_duration, _tm_worker, label="tm_rec")
            for key in output_keys:
                avg_results[key] = np.sum(
                    np.array([all_results[t][key] * recession_prob_array[t]
                              for t in range(max_recession_duration)]),
                    axis=0,
                )
        t1 = time()
        print('TM calculating took ' + mystr(t1-t0) + ' seconds.')
        profiler.record_time("run_experiments_all_recessions_tm", t1-t0)
        return [avg_results, all_results]

    def run_experiments_no_recessions_tm(dict_changes, AggDemandEconomy_Routine, baseline_tm_data):
        t0 = time()
        shock_type = dict_changes['shock_type']
        EconomyMrkv_init = list(np.arange(1, AggDemandEconomy_Routine.num_experiment_periods+1)*2) + [0]*20
        results = run_experiment_tm_nonbase(
            AggDemandEconomy_Routine, shock_type, EconomyMrkv_init,
            baseline_tm_data,
            mCount=tm_mCount,
            neutral_measure=tm_neutral_measure,
        )
        t1 = time()
        print('TM calculating took ' + mystr(t1-t0) + ' seconds.')
        profiler.record_time("run_experiments_no_recessions_tm", t1-t0)
        return results
    
    def run_experiments_all_recessions_ad_tm(dict_changes, AggDemandEconomy_Routine,
                                              baseline_tm_data, AggCons_baseline,
                                              num_max_iterations=10, convergence_tol=0.004,
                                              mCount=50, neutral_measure=False):
        """TM-based AD iteration, averaged over recession durations."""
        t0 = time()
        shock_type = dict_changes['shock_type']
        ADelasticity = AggDemandEconomy_Routine.demand_ADelasticity
        all_results = []
        avg_results = dict()

        if GLP1_recession_duration is not None:
            dur = GLP1_recession_duration
            EconomyMrkv_init = list(np.arange(1, AggDemandEconomy_Routine.num_experiment_periods+1)*2) + [0]*20
            EconomyMrkv_init[0:dur] = (np.array(EconomyMrkv_init[0:dur]) + 1).tolist()
            this_result = run_ad_tm(
                AggDemandEconomy_Routine, shock_type, EconomyMrkv_init,
                baseline_tm_data, AggCons_baseline,
                ADelasticity=ADelasticity,
                num_max_iterations=num_max_iterations,
                convergence_tol=convergence_tol,
                mCount=mCount,
                neutral_measure=neutral_measure,
            )
            avg_results = this_result
            all_results = [this_result]
        else:
            progress(f"TM-AD: Running {max_recession_duration} recession duration variants (cached Phase 1)")

            def _tm_ad_mrkv_path(t):
                EconomyMrkv_init = list(np.arange(1, AggDemandEconomy_Routine.num_experiment_periods+1)*2) + [0]*20
                EconomyMrkv_init[0:t+1] = (np.array(EconomyMrkv_init[0:t+1]) + 1).tolist()
                return EconomyMrkv_init

            # t=0 runs INLINE: Phase-1 CFunc training mutates the economy
            # (economy.CFunc + agent re-solves), and all later durations
            # evaluate against that trained CFunc — so it must complete first.
            first_result = run_ad_tm(
                AggDemandEconomy_Routine, shock_type, _tm_ad_mrkv_path(0),
                baseline_tm_data, AggCons_baseline,
                ADelasticity=ADelasticity,
                num_max_iterations=num_max_iterations,
                convergence_tol=convergence_tol,
                mCount=mCount,
                neutral_measure=neutral_measure,
                skip_training=False,
            )

            # t>=1 are pure Phase-2 evaluations (skip_training=True): each only
            # READS the trained CFunc, so they are independent of one another →
            # dispatch through the same fork helper as the non-AD loop above
            # (children inherit the trained economy via fork copy-on-write).
            # Results come back indexed by t, so the probability-weighted sum
            # below runs in the same fixed order as the sequential loop →
            # FP-identical output (verified by the HS_Only sequential-vs-forked
            # bit-compare gate, 2026-06-10).
            def _tm_ad_worker(s):
                t = s + 1
                return run_ad_tm(
                    AggDemandEconomy_Routine, shock_type, _tm_ad_mrkv_path(t),
                    baseline_tm_data, AggCons_baseline,
                    ADelasticity=ADelasticity,
                    num_max_iterations=num_max_iterations,
                    convergence_tol=convergence_tol,
                    mCount=mCount,
                    neutral_measure=neutral_measure,
                    skip_training=True,
                )

            rest_results = _fork_dispatch_durations(
                max_recession_duration - 1, _tm_ad_worker, label="tm_ad_rec")
            all_results = [first_result] + rest_results
            for key in output_keys:
                avg_results[key] = np.sum(
                    np.array([all_results[t][key] * recession_prob_array[t]
                              for t in range(max_recession_duration)]),
                    axis=0,
                )
        t1 = time()
        print('TM-AD calculating took ' + mystr(t1-t0) + ' seconds.')
        profiler.record_time("run_experiments_all_recessions_ad_tm", t1-t0)
        return [avg_results, all_results]

    def Run_FullRoutineNoRecessions(shock_type):
        shock_types_done[0] += 1
        substep(f"Shock: {shock_type} (no recession) [{shock_types_done[0]}/{shock_types_count}]", expected_duration_min=30)
        
        AggDemandEconomy_Routine = deepcopy(AggDemandEconomy)
        if shock_type == 'Check':
            changes = Check_changes    
        elif shock_type == 'UI':
            changes = UI_changes    
        elif shock_type == 'TaxCut':     
            changes = TaxCut_changes
        if shock_type=='Check' or shock_type=='UI' or shock_type=='TaxCut':   
            print('Calculating no recession effects for shock_type: ', shock_type)
            AggDemandEconomy_Routine.switch_shock_type(shock_type)
            AggDemandEconomy_Routine.solve()

            if use_MC:
                with profile_function(f"shock_{shock_type}_norecession_MC"):
                    results = run_experiments_no_recessions(changes, AggDemandEconomy_Routine)
                suffix = '_MC' if sim_method == 'both' else ''
                save_as_pickle(shock_type + '_results' + suffix, results, figs_dir)

            if use_TM:
                with profile_function(f"shock_{shock_type}_norecession_TM"):
                    results_tm = run_experiments_no_recessions_tm(changes, AggDemandEconomy_Routine, baseline_tm_data)
                suffix = '_TM' if sim_method == 'both' else ''
                save_as_pickle(shock_type + '_results' + suffix, results_tm, figs_dir)

            progress(f"Completed shock type {shock_type} (no recession, {sim_method})")
            
    def Run_FullRoutine(shock_type):
        shock_types_done[0] += 1
        substep(f"Shock: {shock_type} [{shock_types_done[0]}/{shock_types_count}]", expected_duration_min=120)
        
        AggDemandEconomy_Routine = deepcopy(AggDemandEconomy)
        
        if shock_type == 'recession':
            changes = recession_changes
        elif shock_type == 'recessionCheck':
            changes = recession_Check_changes    
        elif shock_type == 'recessionUI':
            changes = recession_UI_changes    
        elif shock_type == 'recessionTaxCut':     
            changes = recession_TaxCut_changes
            
            
        if Run_NonAD:   
            AggDemandEconomy_Routine.switch_shock_type(shock_type)
            AggDemandEconomy_Routine.solve()

            if use_MC:
                print('Calculating no AD effects (MC) for shock_type: ', shock_type)
                with profile_function(f"shock_{shock_type}_noAD_MC"):
                    [results, all_results] = run_experiments_all_recessions(changes, AggDemandEconomy_Routine)
                suffix = '_MC' if sim_method == 'both' else ''
                save_as_pickle(shock_type + '_results' + suffix, results, figs_dir)
                save_as_pickle(shock_type + '_all_results' + suffix, all_results, figs_dir)

            if use_TM:
                print('Calculating no AD effects (TM) for shock_type: ', shock_type)
                with profile_function(f"shock_{shock_type}_noAD_TM"):
                    [results_tm, all_results_tm] = run_experiments_all_recessions_tm(changes, AggDemandEconomy_Routine, baseline_tm_data)
                suffix = '_TM' if sim_method == 'both' else ''
                save_as_pickle(shock_type + '_results' + suffix, results_tm, figs_dir)
                save_as_pickle(shock_type + '_all_results' + suffix, all_results_tm, figs_dir)
        
        if Run_AD:
            if use_TM:
                print(f'Calculating AD effects (TM) for shock_type: {shock_type}')
                AggDemandEconomy_Routine.switch_shock_type(shock_type)
                AggDemandEconomy_Routine.solve()
                AggCons_base = base_results_tm['AggCons']
                with profile_function(f"shock_{shock_type}_AD_TM"):
                    [results_AD_tm, all_results_AD_tm] = run_experiments_all_recessions_ad_tm(
                        changes, AggDemandEconomy_Routine, baseline_tm_data,
                        AggCons_base,
                        num_max_iterations=num_max_iterations_solvingAD,
                        convergence_tol=convergence_tol_solvingAD,
                        mCount=tm_mCount,
                        neutral_measure=tm_neutral_measure,
                    )
                suffix = '_AD_TM' if sim_method == 'both' else '_AD'
                save_as_pickle(shock_type + '_results' + suffix, results_AD_tm, figs_dir)
                save_as_pickle(shock_type + '_all_results' + suffix, all_results_AD_tm, figs_dir)
                progress(f"AD effects (TM) calculated for {shock_type}")

            if use_MC:
                t0 = time()
                AggDemandEconomy_Routine.switch_shock_type(shock_type)
                progress(f"Starting AD solve for {shock_type} (max {num_max_iterations_solvingAD} iterations)")
                with profile_function(f"shock_{shock_type}_AD_solve"):
                    if shock_type == 'recession':
                        AggDemandEconomy_Routine.solve_ad_recession(num_max_iterations=num_max_iterations_solvingAD,convergence_cutoff=convergence_tol_solvingAD, name = shock_type)
                    elif shock_type == 'recessionCheck':
                        AggDemandEconomy_Routine.solve_ad_check_recession(num_max_iterations=num_max_iterations_solvingAD,convergence_cutoff=convergence_tol_solvingAD, name = shock_type)
                    elif shock_type == 'recessionUI':
                        AggDemandEconomy_Routine.solve_ad_ui_extension_recession(num_max_iterations=num_max_iterations_solvingAD,convergence_cutoff=convergence_tol_solvingAD, name = shock_type)
                    elif shock_type == 'recessionTaxCut':
                        AggDemandEconomy_Routine.solve_ad_recession_taxcut(num_max_iterations=num_max_iterations_solvingAD,convergence_cutoff=convergence_tol_solvingAD, name = shock_type)
                t1 = time()
                print('Solving took ' + mystr(t1-t0) + ' seconds for shock_type: ', shock_type)
                profiler.record_time(f"AD_solve_{shock_type}", t1-t0, f"max_iter={num_max_iterations_solvingAD}")

                print('Calculating AD effects (MC) for shock_type: ', shock_type)
                with profile_function(f"shock_{shock_type}_AD_experiment"):
                    AggDemandEconomy_Routine.switch_shock_type(shock_type)
                    AggDemandEconomy_Routine.restore_ADsolution(name = shock_type)
                    [results_AD,all_results_AD] = run_experiments_all_recessions(changes,AggDemandEconomy_Routine)
                suffix = '_AD_MC' if sim_method == 'both' else '_AD'
                save_as_pickle(shock_type + '_results' + suffix,results_AD,figs_dir)
                save_as_pickle(shock_type + '_all_results' + suffix,all_results_AD,figs_dir)
                progress(f"AD effects (MC) calculated for {shock_type}")

        if Run_1stRoundAD:
            if use_TM:
                print(f'Calculating 1st round AD effects (TM) for shock_type: {shock_type}')
                AggDemandEconomy_Routine.switch_shock_type(shock_type)
                AggDemandEconomy_Routine.solve()
                AggCons_base = base_results_tm['AggCons']
                with profile_function(f"shock_{shock_type}_1stRoundAD_TM"):
                    [results_1stAD_tm, all_results_1stAD_tm] = run_experiments_all_recessions_ad_tm(
                        changes, AggDemandEconomy_Routine, baseline_tm_data,
                        AggCons_base,
                        num_max_iterations=1,
                        convergence_tol=convergence_tol_solvingAD,
                        mCount=tm_mCount,
                        neutral_measure=tm_neutral_measure,
                    )
                suffix = '_firstRoundAD_TM' if sim_method == 'both' else '_firstRoundAD'
                save_as_pickle(shock_type + '_results' + suffix, results_1stAD_tm, figs_dir)
                save_as_pickle(shock_type + '_all_results' + suffix, all_results_1stAD_tm, figs_dir)

            if use_MC:
                t0 = time()
                AggDemandEconomy_Routine.switch_shock_type(shock_type)

                with profile_function(f"shock_{shock_type}_1stRoundAD_solve"):
                    if shock_type == 'recession':
                        AggDemandEconomy_Routine.solve_ad_recession(num_max_iterations=1,convergence_cutoff=convergence_tol_solvingAD, name = shock_type + '1stRoundAD')
                    elif shock_type == 'recessionCheck':
                        AggDemandEconomy_Routine.solve_ad_check_recession(num_max_iterations=1,convergence_cutoff=convergence_tol_solvingAD, name = shock_type + '1stRoundAD')
                    elif shock_type == 'recessionUI':
                        AggDemandEconomy_Routine.solve_ad_ui_extension_recession(num_max_iterations=1,convergence_cutoff=convergence_tol_solvingAD, name = shock_type + '1stRoundAD')
                    elif shock_type == 'recessionTaxCut':
                        AggDemandEconomy_Routine.solve_ad_recession_taxcut(num_max_iterations=1,convergence_cutoff=convergence_tol_solvingAD, name = shock_type + '1stRoundAD')
                t1 = time()
                print('Solving took ' + mystr(t1-t0) + ' seconds for 1st round AD for shock_type: ', shock_type)
                profiler.record_time(f"1stRoundAD_solve_{shock_type}", t1-t0)

                print('Calculating 1st round AD effects (MC) for shock_type: ', shock_type)
                with profile_function(f"shock_{shock_type}_1stRoundAD_experiment"):
                    AggDemandEconomy_Routine.switch_shock_type(shock_type)
                    AggDemandEconomy_Routine.restore_ADsolution(name = shock_type + '1stRoundAD')
                    [results_firstRoundAD,all_results_firstRoundAD] = run_experiments_all_recessions(changes,AggDemandEconomy_Routine)
                suffix = '_firstRoundAD_MC' if sim_method == 'both' else '_firstRoundAD'
                save_as_pickle(shock_type + '_results' + suffix,results_firstRoundAD,figs_dir)
                save_as_pickle(shock_type + '_all_results' + suffix,all_results_firstRoundAD,figs_dir)
    

         
        
    #%% Simulation

    progress("Starting shock simulations")

    # Build the dispatch list. Each entry is (runner, arg, label).
    _shock_jobs = []
    if Run_Recession:        _shock_jobs.append((Run_FullRoutine, 'recession', 'recession'))
    if Run_Check_Recession:  _shock_jobs.append((Run_FullRoutine, 'recessionCheck', 'recessionCheck'))
    if Run_UB_Ext_Recession: _shock_jobs.append((Run_FullRoutine, 'recessionUI', 'recessionUI'))
    if Run_TaxCut_Recession: _shock_jobs.append((Run_FullRoutine, 'recessionTaxCut', 'recessionTaxCut'))
    if Run_Check:            _shock_jobs.append((Run_FullRoutineNoRecessions, 'Check', 'Check'))
    if Run_UB_Ext:           _shock_jobs.append((Run_FullRoutineNoRecessions, 'UI', 'UI'))
    if Run_TaxCut:           _shock_jobs.append((Run_FullRoutineNoRecessions, 'TaxCut', 'TaxCut'))

    # Parallelize via os.fork(): each shock_type job is independent
    # (each call deepcopies AggDemandEconomy, trains its own CFunc, and
    # writes its own pickle filenames into figs_dir). Fork inherits all
    # closure state via copy-on-write so no pickling is required.
    #
    # Disable with HAFISCAL_NO_FORK=1 (sequential fallback) for
    # debugging or on platforms without fork.
    _use_fork = (
        hasattr(os, 'fork')
        and os.environ.get('HAFISCAL_NO_FORK', '').strip() not in ('1', 'true', 'yes')
        and len(_shock_jobs) > 1
    )

    if _use_fork:
        progress(f"Forking {len(_shock_jobs)} parallel shock workers")
        _child_pids = {}
        for runner, arg, label in _shock_jobs:
            _pid = os.fork()
            if _pid == 0:
                # Child: run one shock type and exit. Use os._exit to
                # avoid running parent atexit handlers (which would
                # try to write profile data twice).
                try:
                    runner(arg)
                    os._exit(0)
                except BaseException as _e:
                    sys.stderr.write(f"[fork:{label}] FAILED: {_e!r}\n")
                    os._exit(1)
            else:
                _child_pids[_pid] = label
        # Parent: wait for all children, collect any failures.
        _failures = []
        for _ in range(len(_child_pids)):
            _pid, _status = os.waitpid(-1, 0)
            _label = _child_pids.get(_pid, f"pid{_pid}")
            if _status != 0:
                _failures.append(f"{_label} (status={_status})")
        if _failures:
            raise RuntimeError(
                f"Parallel shock workers failed: {', '.join(_failures)}. "
                f"Re-run with HAFISCAL_NO_FORK=1 to debug sequentially.")
    else:
        progress(f"Running {len(_shock_jobs)} shock jobs sequentially")
        for runner, arg, _label in _shock_jobs:
            runner(arg)

    progress("All shock simulations complete")

    # GLP-1 summary: print multipliers to stdout
    if GLP1:
        import pickle as _pkl
        def _load(name):
            with open(figs_dir + name + '.csv', 'rb') as f:
                return _pkl.load(f)
        Rfree = AggDemandEconomy.agents[0].Rfree[0]
        act_T = AggDemandEconomy.act_T
        print("\n" + "=" * 60)
        print("GLP-1 RESULTS (1 college type, TM, no AD)")
        print("=" * 60)
        try:
            # See math-derive (NPV-def) and math-derive-appendix (fiscal-multiplier)
            base = _load('base_results')
            for shock in ['UI', 'TaxCut', 'Check']:
                res = _load(shock + '_results')
                npv_y = calculate_NPV(np.array(res['AggIncome']) - np.array(base['AggIncome']), act_T, Rfree)[-1]
                npv_c = calculate_NPV(np.array(res['AggCons']) - np.array(base['AggCons']), act_T, Rfree)[-1]
                mult = npv_c / npv_y if abs(npv_y) > 1e-10 else float('nan')
                print(f"  {shock:20s}  NPV multiplier (C/Y) = {mult:.4f}")
            base_rec = _load('recession_results')
            for shock in ['recessionUI', 'recessionTaxCut', 'recessionCheck']:
                res = _load(shock + '_results')
                npv_y = calculate_NPV(np.array(res['AggIncome']) - np.array(base_rec['AggIncome']), act_T, Rfree)[-1]
                npv_c = calculate_NPV(np.array(res['AggCons']) - np.array(base_rec['AggCons']), act_T, Rfree)[-1]
                mult = npv_c / npv_y if abs(npv_y) > 1e-10 else float('nan')
                label = shock.replace('recession', 'rec.')
                print(f"  {label:20s}  NPV multiplier (C/Y) = {mult:.4f}")
        except Exception as e:
            print(f"  Error computing multipliers: {e}")
            import traceback; traceback.print_exc()
        print("=" * 60)


