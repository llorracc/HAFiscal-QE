'''
This file extends AggIndMrkvConsumerType (a MarkovConsumerType with hierarchical
macro+micro Markov decomposition) for the Fiscal project.

Math reference (shorthand "math-derive"):
    history/20260331-mathematical-derivations-TM-MC-convergence.md
Appendix reference (shorthand "math-derive-appendix"):
    history/20260331-mathematical-derivations-appendix.md
'''
import warnings
import numpy as np
import scipy.sparse as sp
import os
import sys
import time as _time_module

# Lognormal._approx_equiprobable compatibility patch
# HARK 0.17.0 uses scipy.special.erfc (vectorized C/Cephes) while 0.14.1 used
# math.erf (scalar libm).  They compute the same function but differ at ~1e-15
# per call, accumulating to ~1e-11 over 1,200 simulation periods.
# When _RNG_SYNC_WITH_014 is True we monkey-patch the Lognormal method to use
# math.erf so the income-shock atoms are bitwise-identical to 0.14.1.
import math as _math
from HARK.distributions import DiscreteDistribution, Uniform
from HARK.ConsumptionSaving.ConsMarkovModel import MarkovConsumerType
from HARK.ConsumptionSaving.ConsAggIndMarkovModel import AggIndMrkvConsumerType
from HARK.ConsumptionSaving.ConsIndShockModel import ConsumerSolution
from HARK.ConsumptionSaving.ConsAggShockModel import AggShockConsumerType, make_aggshock_solution_terminal
from HARK.interpolation import MargValueFuncCRRA as MargValueFunc2D
from HARK.interpolation import LinearInterp, BilinearInterp, VariableLowerBoundFunc2D, \
                                LinearInterpOnInterp1D, LowerEnvelope2D, UpperEnvelope, ConstantFunction
from HARK import Market
from HARK.metric import distance_metric
from HARK.core import Model

from copy import copy, deepcopy
import matplotlib.pyplot as plt

from Parameters import return_parameters
from income_process_sst import tile_PermGroFac_composite

# Import progress tracking
_parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)
# PermGroFac matched-pair: single source of truth tying the BUG-047 solver fix to
# the calibration + the solutions the simulator consumes. See _permgrofac.py.
from _permgrofac import permgrofac_fix_on, stamp_regime, assert_regime
try:
    from hafiscal_progress import profiler, progress, profile_function
    _PROFILING_ENABLED = True
except ImportError:
    _PROFILING_ENABLED = False
    def progress(*args, **kwargs): pass
    def profile_function(*args, **kwargs):
        from contextlib import contextmanager
        @contextmanager
        def dummy_ctx(*a, **kw):
            yield
        return dummy_ctx()
    class _DummyProfiler:
        def record_time(self, *args, **kwargs): pass
        def log_convergence(self, *args, **kwargs): pass
    profiler = _DummyProfiler()
[make_macro_mrkv_array_recession, make_cond_mrkv_arrays_recession, make_full_mrkv_array, T_sim, make_cond_mrkv_arrays_base, make_cond_mrkv_arrays_recession_ui] = return_parameters(OutputFor='_Model.py')

# RNG Synchronization toggle for version comparison testing
# Set to True to synchronize RNG with HARK 0.14.1 behavior (for validation)
# Set to False to use default HARK 0.17.0 RNG behavior (for production)
# Can be overridden at class level or per-instance via __init__ kwarg
_RNG_SYNC_WITH_014 = True  # Default: synchronized for validation

# ---------------------------------------------------------------------------
# Monkey-patch Lognormal._approx_equiprobable to use math.erf (0.14.1 parity)
# ---------------------------------------------------------------------------
if _RNG_SYNC_WITH_014:
    from HARK.distributions import Lognormal as _Lognormal
    from scipy.stats import norm as _norm

    _original_approx_equiprobable = _Lognormal._approx_equiprobable

    def _approx_equiprobable_erf(self, N, endpoints=False,
                                  tail_N=0, tail_bound=None, tail_order=np.e):
        """Drop-in replacement that uses math.erf instead of scipy.special.erfc."""
        tail_bound = tail_bound or [0.02, 0.98]

        if self.sigma == 0.0:
            pmv = np.ones(N) / N
            atoms = np.exp(self.mu) * np.ones(N)
        else:
            if tail_N > 0:
                lo_cut = tail_bound[0]
                hi_cut = tail_bound[1]
            else:
                lo_cut = 0.0
                hi_cut = 1.0
            inner_size = hi_cut - lo_cut
            inner_CDF_vals = [
                lo_cut + x * N ** (-1.0) * inner_size for x in range(1, N)
            ]
            if inner_size < 1.0:
                scale = 1.0 / tail_order
                mag = (1.0 - scale**tail_N) / (1.0 - scale)
            lower_CDF_vals = [0.0]
            if lo_cut > 0.0:
                for x in range(tail_N - 1, -1, -1):
                    lower_CDF_vals.append(lower_CDF_vals[-1] + lo_cut * scale**x / mag)
            upper_CDF_vals = [hi_cut]
            if hi_cut < 1.0:
                for x in range(tail_N):
                    upper_CDF_vals.append(
                        upper_CDF_vals[-1] + (1.0 - hi_cut) * scale**x / mag
                    )
            CDF_vals = np.array(lower_CDF_vals + inner_CDF_vals + upper_CDF_vals)
            CDF_vals[-1] = 1.0
            CDF_vals[0] = 0.0

            pmv = CDF_vals[1:] - CDF_vals[:-1]
            pmv /= np.sum(pmv)

            z_cuts = _norm.ppf(CDF_vals)
            q_cuts = (z_cuts - self.sigma) / np.sqrt(2)

            # Use scalar math.erf: erfc(x) == 1 - erf(x)
            erf_q = np.array([1.0 - _math.erf(float(q)) for q in q_cuts])
            erf_q_neg = np.array([1.0 - _math.erf(float(-q)) for q in q_cuts])

            vals_base = erf_q[:-1] - erf_q[1:]
            these = q_cuts[:-1] < -2.0
            vals_base[these] = erf_q_neg[1:][these] - erf_q_neg[:-1][these]

            norm_fac = 0.5 * np.exp(self.mu + 0.5 * self.sigma**2) / pmv
            atoms = vals_base * norm_fac

        if endpoints:
            atoms = np.r_[0.0, atoms, np.inf]
            pmv = np.r_[0.0, pmv, 0.0]

        limit = {
            "dist": self,
            "method": "equiprobable",
            "N": N,
            "endpoints": endpoints,
            "tail_N": tail_N,
            "tail_bound": tail_bound,
            "tail_order": tail_order,
        }

        return DiscreteDistribution(
            pmv, atoms, seed=self.random_seed(), limit=limit,
        )

    _Lognormal._approx_equiprobable = _approx_equiprobable_erf
# ---------------------------------------------------------------------------

# CDC-MOD-BUG031 helper (extracted from AggFiscalType.get_poststates body for the
# CDC/ESC configurable refactor; see plans/20260426-0706h_pre-refactor-prep.md
# item 2c). The ESC counterpart landed INLINE in get_poststates (the
# interpretation=='ESC' branch: aNrm = mNrm - cNrm, HARK's default rule, which IS
# (eq:budget-ESC) per BUGS_private/HAFiscal_splurge_budget_inconsistency/
# models_CDC_and_ESC.md §5.2) — no separate `_esc_asset_rule` helper was needed.
# implements (eq:budget-CDC) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md
def _cdc_asset_rule(state_now, shocks, AggDemandFac, splurge):
    """Compute (aNrm, aLvl) under CDC's splurge-in-budget asset rule.

    Per (eq:budget-CDC) of models_CDC_and_ESC.md §4.2 (alias: (CDC-1)):
        a_nrm = m_nrm - c_actual_nrm
        c_actual_nrm = (1 - ς)·cFunc(m) + ς·ξ·ADF
                     = (1 - ς)·state_now['cNrm'] + ς·shocks['TranShk']·AggDemandFac

    The HARK solver is splurge-unaware (it solves for cFunc as if all income
    were the optimizer's), so state_now['cNrm'] = cFunc(mNrm) is correct;
    the splurge-in-budget shift only enters the asset update, not the policy.

    Returns (aNrm_arr, aLvl_arr). Caller assigns to state_now['aNrm'] /
    state_now['aLvl'].
    """
    cNrm_actual = (1.0 - splurge) * state_now['cNrm'] + \
        splurge * shocks['TranShk'] * AggDemandFac
    aNrm = state_now['mNrm'] - cNrm_actual
    aLvl = aNrm * state_now['pLvl']
    return aNrm, aLvl


# Define a modified AggIndMrkvConsumerType
class AggFiscalType(AggIndMrkvConsumerType):
    time_inv_ = AggIndMrkvConsumerType.time_inv_ 
    
    # Class-level toggle for RNG synchronization (can be overridden per-instance)
    rng_sync_with_014 = _RNG_SYNC_WITH_014
    
    def __init__(self,cycles=1,time_flow=True,**kwds):
        # Handle RNG synchronization toggle (can be passed as kwarg)
        if 'rng_sync_with_014' in kwds:
            self.rng_sync_with_014 = kwds.pop('rng_sync_with_014')
        # Otherwise use class-level default (set above)
        
        # HARK 0.17.0 COMPATIBILITY:
        # Disable automatic construction entirely because:
        # 1. AggIndMrkvConsumerType's IncShkDstn constructor expects numpy arrays with specific shapes
        # 2. HAFiscal uses lists for PermShkStd, TranShkStd which don't match
        # 3. HAFiscal builds its own Markov income structure anyway
        AggIndMrkvConsumerType.__init__(self,cycles=1,time_flow=True,construct=False,**kwds)
        
        # Manually build the required attributes that would normally come from construct()
        from HARK.utilities import make_assets_grid
        from HARK.ConsumptionSaving.ConsIndShockModel import (
            make_lognormal_kNrm_init_dstn,
            make_lognormal_pLvl_init_dstn,
        )
        from HARK.Calibration.Income.IncomeProcesses import (
            construct_lognormal_income_process_unemployment,
            get_PermShkDstn_from_IncShkDstn,
            get_TranShkDstn_from_IncShkDstn,
        )
        
        # Build aXtraGrid
        self.aXtraGrid = make_assets_grid(
            aXtraMin=self.aXtraMin,
            aXtraMax=self.aXtraMax,
            aXtraCount=self.aXtraCount,
            aXtraExtra=self.aXtraExtra if hasattr(self, 'aXtraExtra') else None,
            aXtraNestFac=self.aXtraNestFac if hasattr(self, 'aXtraNestFac') else 3,
        )
        
        # Build initial distributions for simulation
        self.kNrmInitDstn = make_lognormal_kNrm_init_dstn(
            kLogInitMean=self.kLogInitMean,
            kLogInitStd=self.kLogInitStd,
            kNrmInitCount=getattr(self, 'kNrmInitCount', 15),
            RNG=self.RNG,
        )
        self.pLvlInitDstn = make_lognormal_pLvl_init_dstn(
            pLogInitMean=self.pLogInitMean,
            pLogInitStd=self.pLogInitStd,
            pLvlInitCount=getattr(self, 'pLvlInitCount', 15),
            RNG=self.RNG,
        )
        
        # Set num_micro_states as alias for num_base_MrkvStates (activates
        # the base class's hierarchical decomposition helpers)
        if hasattr(self, 'num_base_MrkvStates'):
            self.num_micro_states = self.num_base_MrkvStates
            self.num_macro_states = 1  # updated dynamically by update_mrkv_array
        
        # Build MrkvInitDstn for sim_birth compatibility
        # (HAFiscal overrides this in initialize_sim anyway)
        from HARK.ConsumptionSaving.ConsMarkovModel import make_MrkvInitDstn
        if hasattr(self, 'MrkvPrbsInit'):
            self.MrkvInitDstn = make_MrkvInitDstn(self.MrkvPrbsInit, self.RNG)
        else:
            # Default: uniform over 2 states
            import numpy as np
            from HARK.distributions import DiscreteDistribution
            self.MrkvInitDstn = DiscreteDistribution(
                pmv=np.array([0.5, 0.5]),
                atoms=np.array([0, 1]),
                seed=self.RNG.integers(2**31-1)
            )
        
        # Build income distribution using non-Markov builder (HAFiscal customizes this later)
        IncShkDstn = construct_lognormal_income_process_unemployment(
            T_cycle=self.T_cycle,
            PermShkStd=self.PermShkStd,
            PermShkCount=self.PermShkCount,
            TranShkStd=self.TranShkStd,
            TranShkCount=self.TranShkCount,
            T_retire=0,
            UnempPrb=self.UnempPrb,
            IncUnemp=self.IncUnemp,
            UnempPrbRet=None,
            IncUnempRet=None,
            RNG=self.RNG,
        )
        self.IncShkDstn = IncShkDstn
        
        # RNG Sync: Set IncShkDstn seed to match HARK 0.14.1's construction value.
        # In 0.14.1, the IncShkDstn seed depends on the agent's seed because it's
        # derived from RNG calls during construction. The INCSHKDSTN_SEEDS_014 lookup
        # table maps agent seeds to the correct IncShkDstn seeds (pre-computed from
        # 0.14.1). Agents with the default seed (0) get INCSHKDSTN_SEED_DEFAULT.
        if getattr(self, 'rng_sync_with_014', True):
            agent_seed = getattr(self, 'seed', 0)
            incshk_seed = self.INCSHKDSTN_SEEDS_014.get(
                agent_seed, self.INCSHKDSTN_SEED_DEFAULT
            )
            for dstn_item in self.IncShkDstn:
                if hasattr(dstn_item, '_seed'):
                    dstn_item._seed = incshk_seed
        
        self.PermShkDstn = get_PermShkDstn_from_IncShkDstn(IncShkDstn, self.RNG)
        self.TranShkDstn = get_TranShkDstn_from_IncShkDstn(IncShkDstn, self.RNG)
        self.shock_vars += ['update_draw','unemployment_draw']
        # CDC-MOD-BUG031: Adds cLvl_splurge state var for the realized weighted-average household consumption (CDC-1 RHS). ESC needs the same state var under shared aggregator A; the *value* is the same household-total under either reading. See plans/20260425-2102h_cdc-implementation-map.md row 31.1.
        self.state_vars += ['cNrm', 'cLvl_splurge', 'cLvl']
        self.solve_one_period = solve_agg_cons_markov_alt
        # Add consumer-type specific objects, copying to create independent versions
        self.time_vary = deepcopy(AggIndMrkvConsumerType.time_vary_)
        self.time_inv = deepcopy(AggIndMrkvConsumerType.time_inv_)
        self.del_from_time_inv('vFuncBool', 'CubicBool')
        self.add_to_time_vary('IncShkDstn','PermShkDstn','TranShkDstn')
        self.del_from_time_vary('Rfree')  # HARK 0.17.0 puts Rfree in time_vary by default
        self.add_to_time_inv('aXtraGrid', 'Rfree')
        self.cached_EndOfPrdvP = None

        # CDC-MOD-BUG033: Dispatch flag enabling the a-indexed TM kernel needed because under any splurge-in-budget reading, post-consumption assets depend on realized ξ. ESC version: same flag dispatches to its own ESC-faithful a-indexed kernel (TBD). See plans/20260425-2102h_cdc-implementation-map.md row 33.1 and BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md.
        # BUG-033: dispatch flag for a-indexed vs m-indexed TM. The a-indexed
        # TM is the CANONICAL production method (m-indexed is structurally
        # biased under splurge-in-budget; see
        # BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md). Production
        # runs enable it via HAFISCAL_TM_A_INDEXED → Run_Dict['tm_a_indexed']
        # → this kwarg, which do_all.py Step-5a sets (since 2026-06-11) unless
        # HAFISCAL_QE_FIDELITY=1. Default False here is kept for
        # non-production callers.
        self.tm_a_indexed = bool(kwds.get('tm_a_indexed', False))

        # Phase 0.5 of plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md:
        # interpretation flag for the TM-a kernel chain (33.4-33.9 of
        # tm_methods.py). Read precedence:
        #   1. explicit constructor kwarg (kwds['interpretation'])
        #   2. HAFISCAL_INTERPRETATION env var (via _interpretation.get_interpretation)
        #   3. default 'CDC'
        # Wherever this agent's tm_a_indexed code path invokes the kernel
        # functions in tm_methods.py, the kernel functions read this
        # attribute to dispatch between CDC and ESC asset rules. See
        # BUGS_private/HAFiscal_splurge_budget_inconsistency/why_TM_a_kernel.md
        # for the math; code_cheatsheet_tm_a_kernel.md for the per-line
        # implementation map.
        if 'interpretation' in kwds:
            _interp = str(kwds['interpretation']).upper()
            if _interp not in ('CDC', 'ESC'):
                raise ValueError(
                    f"interpretation must be 'CDC' or 'ESC', got: {kwds['interpretation']!r}"
                )
            self.interpretation = _interp
        else:
            # Defer to env-var helper (handles default + validation).
            try:
                import sys as _sys, os as _os
                _hafiscal_root = _os.path.normpath(_os.path.join(
                    _os.path.dirname(_os.path.abspath(__file__)), '..'
                ))
                if _hafiscal_root not in _sys.path:
                    _sys.path.insert(0, _hafiscal_root)
                from _interpretation import get_interpretation as _get_interp
                self.interpretation = _get_interp()
            except ImportError:
                # Helper not available yet (e.g. test contexts); default 'CDC'.
                self.interpretation = 'CDC'
        
    def update_solution_terminal(self):
        self.solution_terminal = make_aggshock_solution_terminal(self.CRRA)
        # Make replicated terminal period solution
        StateCount = self.MrkvArray[-1].shape[0]
        self.solution_terminal.cFunc = StateCount*[self.solution_terminal.cFunc]
        self.solution_terminal.vPfunc = StateCount*[self.solution_terminal.vPfunc]
        # NOTE: In 0.14.1, mNrmMin was a numpy array of floats (0.0), causing the
        # isinstance(mNrmMinNext, float) check in the solver to take the if-branch
        # for the first iteration. In 0.17.0, mNrmMin is a ConstantFunction(0.0),
        # so the else-branch is always taken. Both branches now have the correct
        # PermGroFac*PermShk/Rfree scaling, so the results are mathematically
        # equivalent (ConstantFunction(0.0)(x) == 0.0 * x == 0.0).
        self.solution_terminal.mNrmMin = StateCount*[self.solution_terminal.mNrmMin]
        
    def pre_solve(self):
        self.MrkvArray = self.MrkvArray
        # HARK 0.17.0: Skip AggIndMrkvConsumerType.pre_solve which has strict Rfree checks
        # that assume Rfree is a list of arrays per period. HAFiscal uses a single array.
        from HARK.core import AgentType
        AgentType.pre_solve(self)
        self.update_solution_terminal()
        



    # IncShkDstn seed synchronization for matching HARK 0.14.1
    # Pre-computed seeds for common agent seeds when 'seed' is in init_params
    # These were extracted by running AggFiscalType in HARK 0.14.1
    INCSHKDSTN_SEEDS_014 = {
        100: 1902228400, 101: 549356314, 102: 1177871788, 103: 1378950034,
        104: 1230253733, 105: 509164674, 106: 1988470685, 107: 603262574,
        108: 1855686417, 109: 408017191, 110: 445705573, 111: 583652748,
        112: 1487769293, 113: 937204012, 114: 1827925878, 115: 111657472,
        116: 1177685198, 117: 2068048752, 118: 1405544672, 119: 1803870488,
        120: 1186260643, 121: 2042881410,
        12345: 1226058464, 12346: 276307766, 12347: 742504843,
    }
    INCSHKDSTN_SEED_DEFAULT = 763607780  # Default when seed NOT in init_params
    
    def reset_rng(self):
        """
        Override reset_rng to match HARK 0.14.1 reset_rng() behavior.
        
        HARK 0.14.1 reset self.RNG and also reset IncShkDstn distributions with 
        specific seeds. HARK 0.17.0 resets ALL distributions with different seeds.
        
        We replicate 0.14.1's exact seed behavior for reproducible results.
        
        If self.rng_sync_with_014 is False, this uses HARK 0.17.0's default behavior.
        """
        import numpy as np
        
        # Reset the main RNG (like PerfForesightConsumerType.reset_rng)
        self.RNG = np.random.default_rng(self.seed)
        
        # If not synchronizing with 0.14.1, use default 0.17.0 behavior
        if not getattr(self, 'rng_sync_with_014', True):
            # Let AggIndMrkvConsumerType handle it the 0.17.0 way
            if hasattr(self, "IncShkDstn"):
                for item in self.IncShkDstn:
                    if isinstance(item, list):
                        for dstn in item:
                            if hasattr(dstn, 'reset'):
                                dstn.reset()
                    elif hasattr(item, 'reset'):
                        item.reset()
            return
        
        # RNG Sync Mode: Reset IncShkDstn distributions to their original seeds.
        # 
        # KEY INSIGHT: In HARK 0.14.1, reset_rng() just calls dstn.reset() which
        # resets each distribution to its _seed (set during base type construction).
        # ALL agents deepcopied from the same base type share the same IncShkDstn seed
        # (763607780 for all education types in HAFiscal).
        #
        # We set the correct 0.14.1 seed in __init__, and deepcopy preserves it.
        # So we just need to call dstn.reset() here — do NOT overwrite _seed.
        if hasattr(self, "IncShkDstn"):
            for item in self.IncShkDstn:
                if isinstance(item, list):
                    # Markov structure: IncShkDstn[t] is a list of distributions
                    for dstn in item:
                        if hasattr(dstn, 'reset'):
                            dstn.reset()
                elif hasattr(item, 'reset'):
                    item.reset()

    def sim_birth(self, which_agents):
        """
        Override sim_birth to replicate HARK 0.14.1 + HAFiscal's ConsMarkovModel behavior.
        
        This replicates the exact RNG consumption sequence:
        1. Lognormal seed for aNrm
        2. Lognormal seed for pLvl  
        3. Uniform seed for intermediate Mrkv draw (from HAFiscal's local ConsMarkovModel.py)
        
        The intermediate Mrkv is later overwritten by AggFiscalType.initialize_sim(),
        but consuming this RNG integer keeps the sequence synchronized.
        
        NOTE: HARK 0.17.0 renamed parameters:
        - 0.14.1: aNrmInitMean, aNrmInitStd, pLvlInitMean, pLvlInitStd
        - 0.17.0: kLogInitMean, kLogInitStd, pLogInitMean, pLogInitStd
        We check both naming conventions for compatibility.
        
        If self.rng_sync_with_014 is False, this uses HARK 0.17.0's default behavior
        (using pre-built kNrmInitDstn/pLvlInitDstn).
        """
        from HARK.distributions import Lognormal, Uniform
        import numpy as np
        
        N = np.sum(which_agents)  # Number of new consumers to make
        
        # If not synchronizing with 0.14.1, use default 0.17.0 behavior
        if not getattr(self, 'rng_sync_with_014', True):
            # Use pre-built distributions (HARK 0.17.0 style)
            self.state_now["aNrm"][which_agents] = self.kNrmInitDstn.draw(N)
            self.state_now["pLvl"][which_agents] = self.pLvlInitDstn.draw(N)
            self.state_now["pLvl"][which_agents] *= self.state_now["PlvlAgg"]
            self.t_age[which_agents] = 0
            if not hasattr(self, "PerfMITShk"):
                self.PerfMITShk = False
            if not self.PerfMITShk:
                self.t_cycle[which_agents] = 0
            return
        
        # RNG Sync Mode: Match HARK 0.14.1 RNG consumption exactly
        
        # 1. Draw aNrm from Lognormal (consumes 1 RNG integer)
        # Check both 0.14.1 naming (aNrmInitMean) and 0.17.0 naming (kLogInitMean)
        aNrmInitMean = getattr(self, 'aNrmInitMean', getattr(self, 'kLogInitMean', 0.0))
        aNrmInitStd = getattr(self, 'aNrmInitStd', getattr(self, 'kLogInitStd', 1.0))
        self.state_now["aNrm"][which_agents] = Lognormal(
            mu=aNrmInitMean,
            sigma=aNrmInitStd,
            seed=self.RNG.integers(0, 2**31 - 1),
        ).draw(N)
        
        # 2. Draw pLvl from Lognormal (consumes 1 RNG integer)
        # Check both 0.14.1 naming (pLvlInitMean) and 0.17.0 naming (pLogInitMean)
        pLvlInitMean = getattr(self, 'pLvlInitMean', getattr(self, 'pLogInitMean', 0.0))
        pLvlInitStd = getattr(self, 'pLvlInitStd', getattr(self, 'pLogInitStd', 0.0))
        pLvlInitMeanNow = pLvlInitMean + np.log(self.state_now["PlvlAgg"])
        self.state_now["pLvl"][which_agents] = Lognormal(
            pLvlInitMeanNow,
            pLvlInitStd,
            seed=self.RNG.integers(0, 2**31 - 1),
        ).draw(N)
        
        # 3. HAFiscal's local ConsMarkovModel.sim_birth() draws intermediate Mrkv
        #    (consumes 1 RNG integer - even though value is overwritten later)
        if not getattr(self, 'global_markov', False):
            _ = self.RNG.integers(0, 2**31 - 1)  # Match HAFiscal's RNG consumption
        
        # How many periods since each agent was born
        self.t_age[which_agents] = 0
        
        # If PerfMITShk not specified, let it be False
        if not hasattr(self, "PerfMITShk"):
            self.PerfMITShk = False
        if not self.PerfMITShk:
            # Which period of the cycle each agent is currently in
            self.t_cycle[which_agents] = 0

    def initialize_sim(self):
        """
        Prepare simulation state for a new run.

        **Default cross section is not the infinite-horizon Monte Carlo ergodic.**
        Do not assume the initial distribution of ``pLvl``, assets, and ``Mrkv``
        matches what you would obtain after a very long burn-in with a huge
        population. In particular:

        * **Permanent income (`pLvl`):** `IndShockConsumerType.initialize_sim` runs
          `sim_birth` (lognormal newborn draws for ``aNrm`` and ``pLvl``), then
          `_initialize_ergodic_ages` when ``cycles == 0`` and ``init_ages_ergodic``
          is true (HARK default): ages are redrawn from the truncated geometric
          steady state and ``pLvl`` is scaled by ``PermGroFac ** t_age`` only.
          That is **not** the distribution after a full history of stochastic
          ``PermShk`` draws and unemployment spells (see ``tm_methods`` for
          analytical ``pLvl`` approximations used in TM / diagnostics).

        * **Markov / employment (`shocks['Mrkv']`):** unless ``use_prestate`` /
          ``Mrkv_univ`` overrides apply, new draws place each agent in combined
          state **0 (employed)** or **1** with probabilities ``1 - Urate_normal``
          and ``Urate_normal``. Mass is **not** initialized to the full stationary
          distribution over all ``num_base_MrkvStates`` micro states (e.g. later UB
          or no-benefit states).

        For TM-initialized MC experiments, see ``test_tm_init_mc.py`` and the
        TM-vs-MC maintainer notes under ``BUGS_private/``.
        """
        # HARK 0.17.0: Skip AggIndMrkvConsumerType.initialize_sim which needs MrkvInitDstn
        # Call IndShockConsumerType.initialize_sim directly since HAFiscal sets up Markov manually
        from HARK.ConsumptionSaving.ConsIndShockModel import IndShockConsumerType
        IndShockConsumerType.initialize_sim(self)
        if hasattr(self,'use_prestate'):
            self.restore_state()
        else:   # set to ergodic unemployment rate during normal times
            init_unemp_dist = DiscreteDistribution(np.array([1.0-self.Urate_normal, self.Urate_normal]), 
                                                   np.array([0,1]), 
                                                   seed=self.RNG.integers(2**31-1))
            self.shocks['Mrkv'] = init_unemp_dist.draw_events(self.AgentCount)
            if not hasattr(self,'mortality_off'):
                if not getattr(self, 'init_ages_ergodic', True):
                    self.calc_age_distribution()
                    self.initialize_ages()
        if (hasattr(self,'Mrkv_univ') and self.Mrkv_univ is not None):
            self.shocks['Mrkv'][:] = self.Mrkv_univ
        self.MacroMrkvNow = (np.floor(self.shocks['Mrkv']/self.num_base_MrkvStates)).astype(int)
        self.MicroMrkvNow = self.shocks['Mrkv']%self.num_base_MrkvStates
        self.EconomyMrkvNow = self.MacroMrkvNow #For aggregate model only
        self.EconomyMrkvNow_hist = [0] * self.T_sim #For aggregate model only
        
    
    def get_Rport(self):
        """
        Returns an array of size self.AgentCount with interest factor that varies with Markov state.
        
        HARK 0.17.0 compatibility: Override get_Rport() because HARK 0.17.0's base class
        expects Rfree[t][state] (time-varying, then by state), but HAFiscal uses Rfree as a simple
        array where Rfree[markov_state] gives the interest rate for that state.
        
        Parameters
        ----------
        None
        
        Returns
        -------
        RfreeNow : np.array
             Array of size self.AgentCount with risk free interest rate for each agent.
        """
        return self.Rfree[self.shocks["Mrkv"]]

    def get_mortality(self):
        '''
        A modified version of getMortality that reads mortality history if the
        attribute read_mortality exists.  This is a workaround to make sure the
        history of death events is identical across simulations.
        '''
        if (self.read_shocks or hasattr(self,'read_mortality')):
            who_dies = self.who_dies_fixed_hist[self.t_sim,:]
        else:
            who_dies = self.sim_death()
        self.sim_birth(who_dies)
        self.who_dies = who_dies
        return None
    
    def sim_death(self):
        if hasattr(self,'mortality_off'):
            return np.zeros(self.AgentCount, dtype=bool)
        else:
            return AggIndMrkvConsumerType.sim_death(self)
        
    def get_economy_data(self, Economy):
        '''
        Imports economy-determined objects into self from a Market.
        Parameters
        ----------
        Economy : Market
            The "macroeconomy" in which this instance "lives".  
        Returns
        -------
        None
        '''
        self.T_sim = Economy.act_T                   # Need to be able to track as many periods as economy runs
        self.Cgrid = Economy.CgridBase               # Ratio of consumption to steady state consumption
        self.CFunc = Economy.CFunc                   # Next period's consumption ratio function
        self.ADFunc = Economy.ADFunc                 # Function that takes aggregate consumption to agg. demand function
        self.add_to_time_inv('Cgrid', 'CFunc','ADFunc','num_experiment_periods','num_base_MrkvStates')
        # self.PermGroFacAgg = Economy.PermGroFacAgg   # Aggregate permanent productivity growth
        #self.addToTimeInv('Cgrid', 'CFunc', 'PermGroFacAgg','ADFunc')
        
    def save_state(self):
        '''
        Record the current state of simulation variables for later use.
        
        HARK 0.17.0 compatibility: Also save bNrm and mNrm because HARK 0.17.0's
        AgentType.initialize_sim() unconditionally resets ALL state variables to NaN,
        whereas HARK 0.14.1 only reset them if they were None.
        '''
        self.aNrm_base = self.state_now['aNrm'].copy()
        self.pLvl_base = self.state_now['pLvl'].copy()
        self.bNrm_base = self.state_now['bNrm'].copy()
        self.mNrm_base = self.state_now['mNrm'].copy()
        self.Mrkv_base = self.shocks['Mrkv'].copy()
        self.cycle_base  = self.t_cycle.copy()
        self.age_base  = self.t_age.copy()
        self.t_sim_base = self.t_sim
        self.PlvlAgg_base = self.state_now['PlvlAgg']

    def restore_state(self):
        '''
        Restore the state of the simulation to some baseline values.
        
        HARK 0.17.0 compatibility: Also restore bNrm and mNrm.
        '''
        self.state_now['aNrm'] = self.aNrm_base.copy()
        self.state_now['pLvl'] = self.pLvl_base.copy()
        self.state_now['bNrm'] = self.bNrm_base.copy()
        self.state_now['mNrm'] = self.mNrm_base.copy()
        self.shocks['Mrkv'] = self.Mrkv_base.copy()
        self.t_cycle = self.cycle_base.copy()
        self.t_age   = self.age_base.copy()
        self.state_now['PlvlAgg'] = self.PlvlAgg_base
        
    def make_idiosyncratic_shock_histories(self):     
        self.Mrkv_univ = 0
        self.read_shocks = False
        self.make_shock_history()
        self.who_dies_fixed_hist    = self.shock_history['who_dies'].copy()
        self.update_draw_fixed_hist = self.shock_history['update_draw'].copy()
        self.perm_shock_fixed_hist  = self.shock_history['PermShk'].copy()
        self.tran_shock_fixed_hist  = self.shock_history['TranShk'].copy()
        self.unemployment_draw_fixed_hist = self.shock_history['unemployment_draw'].copy()
        self.Mrkv_univ = None
        
    def hit_with_recession_shock(self, shock_type):
        '''
        Alter the Markov state of each simulated agent, jumping some people into
        recession states
        '''
        # PHASE-R DIAG: dump pre-spike state for shuffle-bug investigation
        import os as _os_diag
        if _os_diag.environ.get('HAFISCAL_PHASER_DUMP', '') == '1':
            from collections import Counter as _Cnt
            _J = self.num_base_MrkvStates
            _N = self.AgentCount
            _micro = (np.asarray(self.shocks['Mrkv']).astype(int) % _J)
            _macro = (np.asarray(self.shocks['Mrkv']).astype(int) // _J)
            _cm = _Cnt(_micro.tolist())
            _cM = _Cnt(_macro.tolist())
            # Use t.seed to disambiguate cohorts in multi-seed run
            _agent_seed = getattr(self, 'seed', 'NA')
            print(f"[PHASE-R nshuf-entry seed={_agent_seed} N={_N} J={_J} st={shock_type}] "
                  f"macro={dict(sorted(_cM.items()))} micro={dict(sorted(_cm.items()))}",
                  flush=True)
        # Shock unemployment up to ergodic unemployment level in normal or recession state
        if shock_type=="recession" or shock_type=="recessionUI" or shock_type=="recessionTaxCut" or shock_type=="recessionCheck":
            this_Urate = self.Urate_recession
        elif shock_type=="base" or shock_type=="UI" or shock_type=="TaxCut" or shock_type=="Check":
            this_Urate = self.Urate_normal

        # Draw new Markov states for each agents who are employed
        draws = Uniform(seed=self.RNG.integers(2**31-1)).draw(self.AgentCount)
        draws = self.RNG.permutation(draws)
        MrkvNew = self.shocks['Mrkv']
        old_Urate = self.Urate_normal
        draws_empy2umemp = draws > 1.0-(this_Urate-old_Urate)/(1.0-old_Urate)
        MrkvNew[np.logical_and(np.equal(self.shocks['Mrkv'],0), draws_empy2umemp) ] = 1 # Move people from employment to unemployment such that total unemployment rate is as required. Don't touch already unemployed people.
        
        if shock_type=="base":
            MrkvNew = MrkvNew #no shock
        elif shock_type=="recession" or shock_type=="recessionUI" or shock_type=="recessionTaxCut" or shock_type=="recessionCheck": # If the recssion actually occurs,
            MrkvNew += 3*self.num_base_MrkvStates # then put everyone into the recession ???????????????????????
        elif shock_type=="UI" or shock_type=="TaxCut" or shock_type=="Check":
            MrkvNew += 2*self.num_base_MrkvStates # then put everyone into first experiment mrkv state ???????????????????????
        # Move agents to those Markov states
        self.shocks['Mrkv'] = MrkvNew

        # PHASE-R DIAG: dump post-spike state
        if _os_diag.environ.get('HAFISCAL_PHASER_DUMP', '') == '1':
            from collections import Counter as _Cnt
            _J = self.num_base_MrkvStates
            _micro = (np.asarray(self.shocks['Mrkv']).astype(int) % _J)
            _macro = (np.asarray(self.shocks['Mrkv']).astype(int) // _J)
            _agent_seed = getattr(self, 'seed', 'NA')
            print(f"[PHASE-R nshuf-postSpike seed={_agent_seed} st={shock_type}] "
                  f"macro={dict(sorted(_Cnt(_macro.tolist()).items()))} "
                  f"micro={dict(sorted(_Cnt(_micro.tolist()).items()))}", flush=True)

        self.shock_history['Mrkv'] = np.ones_like(self.shock_history['PermShk'])
        t_age_start = copy(self.t_age)
        self.MicroMrkvNow = self.shocks['Mrkv'] % self.num_base_MrkvStates
        self.MacroMrkvNow = np.floor(self.shocks['Mrkv']/self.num_base_MrkvStates).astype(int)
        MicroMrkvNow_start = copy(self.MicroMrkvNow)
        MacroMrkvNow_start = copy(self.MacroMrkvNow)
        for t in range(self.T_sim):
            self.t_age = 1 - self.who_dies_fixed_hist[t] # hack to get newborns have t_age=0
            self.MacroMrkvNow = self.EconomyMrkvNow_hist[t]
            unemployment_draw = self.unemployment_draw_fixed_hist[t]
            self.get_micro_markv_states_guts(unemployment_draw)
            MrkvNow = self.num_base_MrkvStates*self.MacroMrkvNow + self.MicroMrkvNow
            self.shock_history['Mrkv'][t] = MrkvNow.astype(int)
            # PHASE-R DIAG: dump post-1st-transition state
            if t == 0 and _os_diag.environ.get('HAFISCAL_PHASER_DUMP', '') == '1':
                _agent_seed = getattr(self, 'seed', 'NA')
                _Jp = self.num_base_MrkvStates
                _Mp = MrkvNow.astype(int)
                _miP = _Mp % _Jp
                _maP = _Mp // _Jp
                from collections import Counter as _Cnt2
                _newborns = int((self.t_age == 0).sum())
                print(f"[PHASE-R nshuf-postT0 seed={_agent_seed} st={shock_type}] "
                      f"macro={dict(sorted(_Cnt2(_maP.tolist()).items()))} "
                      f"micro={dict(sorted(_Cnt2(_miP.tolist()).items()))} "
                      f"newborns={_newborns}", flush=True)
        self.t_age = t_age_start
        self.MicroMrkvNow = MicroMrkvNow_start
        self.MacroMrkvNow = MacroMrkvNow_start
        self.shocks['Mrkv'] = self.num_base_MrkvStates*self.MacroMrkvNow + self.MicroMrkvNow
        
        tax_cut_multiplier  = np.ones_like(self.shock_history['Mrkv'])
        CheckAmount         = np.zeros_like(self.shock_history['Mrkv'])
        if shock_type=="recessionTaxCut" or shock_type=="TaxCut":
            tax_cut_states = np.logical_and(np.greater(self.shock_history['Mrkv'], 2*self.num_base_MrkvStates-1), np.less(self.shock_history['Mrkv'],9*2*self.num_base_MrkvStates)) # assumes tax cut last 8 periods
            tax_cut_multiplier[tax_cut_states] *= self.TaxCutIncFactor 
        elif shock_type=="recessionCheck" or shock_type=="Check":
            #This only works because check occurs in first period
            CheckAmount[0] = self.CheckStimLvl
            CheckAmount[0] = CheckAmount[0] / self.state_now['pLvl']        
            for agent in range(len(CheckAmount[0])):
                # Stimulus is a function of permanent income
                if self.state_now['pLvl'][agent] < self.CheckStimLvl_PLvl_Cutoff_start:
                    AgentSpecificScalar = 1
                elif self.state_now['pLvl'][agent] > self.CheckStimLvl_PLvl_Cutoff_end:
                    AgentSpecificScalar = 0
                else:
                    AgentSpecificScalar = 1-(self.state_now['pLvl'][agent]-self.CheckStimLvl_PLvl_Cutoff_start)/(self.CheckStimLvl_PLvl_Cutoff_end-self.CheckStimLvl_PLvl_Cutoff_start)
                CheckAmount[0][agent] *= AgentSpecificScalar
                
        employed = np.equal(self.shock_history['Mrkv']%self.num_base_MrkvStates, 0)
        self.shock_history['PermShk'][employed] = self.perm_shock_fixed_hist[employed]
        self.shock_history['TranShk'][employed] = self.tran_shock_fixed_hist[employed]*tax_cut_multiplier[employed] + CheckAmount[employed] / self.perm_shock_fixed_hist[employed]
        unemp_without_benefits = np.equal(self.shock_history['Mrkv']%self.num_base_MrkvStates, self.num_base_MrkvStates-1)
        unemp_with_benefits = np.logical_not(np.logical_or(employed,unemp_without_benefits))
        # 3-way conditional on PermShk for unemployed agents (BUG-040 fix
        # 2026-05-05). PermShk in HARK convention is ψ × G (the realized
        # permanent shock multiplied by the permanent growth factor).
        #
        # 1. perm_shocks_during_unemployment=True: Harmenberg-factorizable;
        #    unemployed agents draw the SAME ψ × G as employed.
        # 2. unemp_pLvl_grows_like_employed=True (with perm_shocks=False):
        #    unemployed get no shock but DO get growth: PermShk = G uniform.
        #    Matches TM-a's PermGroFac=uniform construction; preserves p ⊥ state.
        #    Set via HAFISCAL_PLVL_GROWS_DURING_UNEMP=on.
        # 3. Default (both flags False, "QE MC version"): pLvl FROZEN during
        #    unemployment — no shock AND no growth: PermShk = 1.0. This is what
        #    the published HAFiscal-QE numbers compute.
        # See conclusions_private/2026-05-05_*_pLvl-mrkv-conditional-bias.md
        # and BUGS_private/HAFiscal_BUG-040_*.md
        if getattr(self, 'perm_shocks_during_unemployment', False):
            self.shock_history['PermShk'][unemp_without_benefits] = self.perm_shock_fixed_hist[unemp_without_benefits]
            self.shock_history['PermShk'][unemp_with_benefits] = self.perm_shock_fixed_hist[unemp_with_benefits]
        elif getattr(self, 'unemp_pLvl_grows_like_employed', False):
            G_uniform = float(self.PermGroFac[0][0])
            self.shock_history['PermShk'][unemp_without_benefits] = G_uniform
            self.shock_history['PermShk'][unemp_with_benefits] = G_uniform
        else:
            self.shock_history['PermShk'][unemp_without_benefits] = 1.0
            self.shock_history['PermShk'][unemp_with_benefits] = 1.0
        self.shock_history['TranShk'][unemp_without_benefits] = self.IncUnempNoBenefits + CheckAmount[unemp_without_benefits]
        self.shock_history['TranShk'][unemp_with_benefits] = self.IncUnemp + CheckAmount[unemp_with_benefits]

        # BUG-043 fix: under bug_fix encoding, the micro state space includes
        # u3Q and u4Q as explicit states. By default they are classified as
        # unemp_with_benefits (= micro != 0 and != noBen), but they should only
        # actually receive extension benefits (IncUnemp) under the recessionUI
        # scenario AND when the macro state corresponds to recession.
        # In all other cases (non-UI scenarios, or recessionUI with macro = normal
        # i.e. recession ended), u3Q/u4Q should receive IncUnempNoBenefits.
        #
        # The lines above set u3Q/u4Q TranShk = IncUnemp by default. Override
        # below for the cases where extension is NOT active.
        try:
            from EstimParameters import HAFISCAL_UI_STATE_ENCODING, Policy_ExtraBenefitQuarters
        except ImportError:
            HAFISCAL_UI_STATE_ENCODING = 'legacy'
        if HAFISCAL_UI_STATE_ENCODING == 'bug_fix':
            J = self.num_base_MrkvStates
            ub_normal = self.UBspell_normal
            micro = self.shock_history['Mrkv'] % J
            macro = self.shock_history['Mrkv'] // J
            # u3Q, u4Q micro indices
            extension_micro_min = ub_normal + 1   # = 3 in baseline (u3Q)
            extension_micro_max = ub_normal + Policy_ExtraBenefitQuarters  # = 4 in baseline (u4Q)
            extension_states = (micro >= extension_micro_min) & (micro <= extension_micro_max)
            if shock_type in ('recessionUI', 'UI'):
                # Extension active only at recession macro states (= odd indices).
                # Override u3Q/u4Q at NORMAL macros to no-benefits (extension expired).
                extension_inactive = extension_states & (macro % 2 == 0)
                self.shock_history['TranShk'][extension_inactive] = (
                    self.IncUnempNoBenefits + CheckAmount[extension_inactive]
                )
            else:
                # All other scenarios: u3Q/u4Q never receive extension benefits.
                self.shock_history['TranShk'][extension_states] = (
                    self.IncUnempNoBenefits + CheckAmount[extension_states]
                )

        self.shock_history['who_dies'] = self.who_dies_fixed_hist
        self.shock_history['update_draw'] = self.update_draw_fixed_hist
        self.shock_history['unemployment_draw'] = self.unemployment_draw_fixed_hist
        
    def _hit_with_recession_shock_shuffled(self, shock_type):
        """Shuffled variant of hit_with_recession_shock.

        Uses deterministic state-transition counts (MarkovProcess.draw with
        shuffle=True) instead of independent per-agent random draws. This
        eliminates sampling noise on state counts, making MC aggregates
        match TM's analytical fractions to machine precision.

        Also applies AggDemandFac scaling to TranShk when ad_in_budget=True
        (fixing the AggDemandFac bug where MC agents' mNrm didn't reflect
        the AD income channel).

        Activated by setting mc_shuffle=True on the agent.
        """
        from HARK.distributions import MarkovProcess as _MP

        # PHASE-R DIAG: dump pre-spike state for shuffle-bug investigation
        import os as _os_diag
        if _os_diag.environ.get('HAFISCAL_PHASER_DUMP', '') == '1':
            from collections import Counter as _Cnt
            _J = self.num_base_MrkvStates
            _N = self.AgentCount
            _micro = (np.asarray(self.shocks['Mrkv']).astype(int) % _J)
            _macro = (np.asarray(self.shocks['Mrkv']).astype(int) // _J)
            _cm = _Cnt(_micro.tolist())
            _cM = _Cnt(_macro.tolist())
            _agent_seed = getattr(self, 'seed', 'NA')
            print(f"[PHASE-R shuf-entry seed={_agent_seed} N={_N} J={_J} st={shock_type}] "
                  f"macro={dict(sorted(_cM.items()))} micro={dict(sorted(_cm.items()))}",
                  flush=True)

        J = self.num_base_MrkvStates
        # Base seed for per-period MarkovProcess — deterministic so the
        # random permutation is shared across experiments.
        self._shuffle_base_seed = getattr(self, 'seed', 0) * 131 + 77777

        # --- Initial unemployment spike (same as original) ---
        if shock_type in ("recession", "recessionUI", "recessionTaxCut", "recessionCheck"):
            this_Urate = self.Urate_recession
        else:
            this_Urate = self.Urate_normal

        draws = Uniform(seed=self.RNG.integers(2**31 - 1)).draw(self.AgentCount)
        draws = self.RNG.permutation(draws)
        MrkvNew = self.shocks['Mrkv']
        old_Urate = self.Urate_normal
        draws_empy2umemp = draws > 1.0 - (this_Urate - old_Urate) / (1.0 - old_Urate)
        MrkvNew[np.logical_and(np.equal(self.shocks['Mrkv'], 0), draws_empy2umemp)] = 1

        if shock_type == "base":
            MrkvNew = MrkvNew
        elif shock_type in ("recession", "recessionUI", "recessionTaxCut", "recessionCheck"):
            MrkvNew += 3 * J
        elif shock_type in ("UI", "TaxCut", "Check"):
            MrkvNew += 2 * J
        self.shocks['Mrkv'] = MrkvNew

        # PHASE-R DIAG: dump post-spike state
        if _os_diag.environ.get('HAFISCAL_PHASER_DUMP', '') == '1':
            from collections import Counter as _Cnt
            _micro = (np.asarray(self.shocks['Mrkv']).astype(int) % J)
            _macro = (np.asarray(self.shocks['Mrkv']).astype(int) // J)
            _agent_seed = getattr(self, 'seed', 'NA')
            print(f"[PHASE-R shuf-postSpike seed={_agent_seed} st={shock_type}] "
                  f"macro={dict(sorted(_Cnt(_macro.tolist()).items()))} "
                  f"micro={dict(sorted(_Cnt(_micro.tolist()).items()))}", flush=True)

        # --- Per-period Markov transitions using shuffled draws ---
        self.shock_history['Mrkv'] = np.ones_like(self.shock_history['PermShk'])
        t_age_start = copy(self.t_age)
        self.MicroMrkvNow = self.shocks['Mrkv'] % J
        self.MacroMrkvNow = np.floor(self.shocks['Mrkv'] / J).astype(int)
        MicroMrkvNow_start = copy(self.MicroMrkvNow)
        MacroMrkvNow_start = copy(self.MacroMrkvNow)

        # BUG-044 (RESOLVED 2026-05-10): per-period Mrkv-transition algorithm
        # selector, HAFISCAL_SHUFFLE_MRKV_TRANSITION. Three modes:
        #   'shuffle'    — legacy MarkovProcess shuffle (the code-literal default
        #                  below). FOOTGUN: its assignment step biased ui_rec
        #                  (the +8.26%-UI footgun; HARK-side fix in PR #1776).
        #   'stratified' — rank-based stratified sampling: quota-exact counts +
        #                  CRN-coupled per-agent assignment. PRODUCTION value,
        #                  set by EstimParameters.py's canonical setdefault block
        #                  (Plan A, 2026-06-10) unless HAFISCAL_QE_FIDELITY=1.
        #   'iid'        — nshuf's per-agent searchsorted algorithm; diagnostic
        #                  only (the initial spike code still uses the shuffle path).
        # The original diagnostic question (whether Row 14 of the math-to-code map
        # was the load-bearing asymmetry) was resolved: the bias lived in the
        # shuffle ASSIGNMENT step, fixed by stratified mode + HARK PR #1776. See
        # conclusions_private/2026-06-10_welfare_method_unified_MC.md.
        import os as _os_mt
        _mrkv_mode = _os_mt.environ.get('HAFISCAL_SHUFFLE_MRKV_TRANSITION', 'shuffle')

        for t in range(self.T_sim):
            self.t_age = 1 - self.who_dies_fixed_hist[t]
            self.MacroMrkvNow = self.EconomyMrkvNow_hist[t]

            # Build per-macro CondMrkv and draw with shuffle.
            # Use a DETERMINISTIC seed per period (not per experiment) so
            # that the shuffle's random permutation is shared across
            # experiments (recession vs recessionUI). Only the CondMrkv
            # difference produces different state assignments.
            macro_now = int(self.EconomyMrkvNow_hist[t])
            cond_mrkv = self.CondMrkvArrays[macro_now]
            if _mrkv_mode == 'iid':
                # Use nshuf's per-agent searchsorted algorithm (CRN-coupled via
                # the shared unemployment_draw_fixed_hist vector).
                Cutoffs = np.cumsum(cond_mrkv, axis=1)
                unemp_draw = self.unemployment_draw_fixed_hist[t]
                new_micro = np.zeros(self.AgentCount, dtype=int)
                MicroMrkvPrev = self.MicroMrkvNow.copy()
                for jj in range(J):
                    these_j = (MicroMrkvPrev == jj)
                    new_micro[these_j] = np.searchsorted(
                        Cutoffs[jj, :], unemp_draw[these_j]).astype(int)
            elif _mrkv_mode == 'stratified':
                # FIX: rank-based stratified sampling.
                # Quota-exact counts (= variance reduction benefit of shuffle)
                # AND per-agent assignment determined by per-agent draw rank
                # (= CRN-coupled with iid via shared unemployment_draw_fixed_hist).
                # Asymptotically equivalent to iid as N→∞ (Glivenko-Cantelli).
                unemp_draw = self.unemployment_draw_fixed_hist[t]
                new_micro = np.zeros(self.AgentCount, dtype=int)
                MicroMrkvPrev = self.MicroMrkvNow.copy()
                for jj in range(J):
                    these_j = (MicroMrkvPrev == jj)
                    N_j = int(these_j.sum())
                    if N_j == 0:
                        continue
                    agents_j = np.where(these_j)[0]
                    draws_j = unemp_draw[agents_j]
                    # Sort agents by their per-agent draw u_i.
                    sort_order = np.argsort(draws_j)
                    sorted_agents = agents_j[sort_order]
                    # Exact quota counts via floor + largest-residual leftover.
                    K_exact = N_j * cond_mrkv[jj]
                    K = np.floor(K_exact).astype(int)
                    leftover = N_j - int(K.sum())
                    if leftover > 0:
                        residuals = K_exact - K
                        for _lo in range(leftover):
                            k_max = int(np.argmax(residuals))
                            K[k_max] += 1
                            residuals[k_max] = -1.0
                    # Assign sorted agents in order: first K[0] → target 0, etc.
                    offset = 0
                    for kk in range(J):
                        if K[kk] == 0:
                            continue
                        new_micro[sorted_agents[offset:offset + K[kk]]] = kk
                        offset += int(K[kk])
            else:
                mp = _MP(cond_mrkv, seed=self._shuffle_base_seed + t)
                new_micro = mp.draw(self.MicroMrkvNow, shuffle=True)
                new_micro = np.asarray(new_micro, dtype=int)
            dont_change = self.t_age == 0
            # BUG-044 fix variants (controlled by HAFISCAL_SHUFFLE_NEWBORN_FIX):
            # - 'off' (default): original behavior. Newborns preserved at POST-SPIKE state
            #   (buggy in marginal but works for CRN coupling).
            # - 'transition': skip override, newborns transition normally per cond_mrkv.
            #   Marginals match nshuf, but welfare CRN broken (bias INCREASES on UI cells).
            # - 'emp': set newborns to micro=0 (employed) — natural newborn initialization.
            #   Try as alternative.
            import os as _os_bf
            _newborn_mode = _os_bf.environ.get('HAFISCAL_SHUFFLE_NEWBORN_FIX', 'off')
            if _newborn_mode in ('off', '0', 'false'):
                new_micro[dont_change] = self.MicroMrkvNow[dont_change]
            elif _newborn_mode in ('transition', 'on', '1', 'true'):
                pass  # let them transition normally
            elif _newborn_mode == 'emp':
                new_micro[dont_change] = 0  # set newborns to employed
            else:
                print(f"[WARN] Unknown HAFISCAL_SHUFFLE_NEWBORN_FIX={_newborn_mode!r}; using 'off'", flush=True)
                new_micro[dont_change] = self.MicroMrkvNow[dont_change]
            self.MicroMrkvNow = new_micro

            MrkvNow = J * self.MacroMrkvNow + self.MicroMrkvNow
            self.shock_history['Mrkv'][t] = MrkvNow.astype(int)
            # PHASE-R DIAG: dump post-1st-transition state
            if t == 0 and _os_diag.environ.get('HAFISCAL_PHASER_DUMP', '') == '1':
                from collections import Counter as _Cnt2
                _agent_seed = getattr(self, 'seed', 'NA')
                _Mp = MrkvNow.astype(int)
                _miP = _Mp % J
                _maP = _Mp // J
                _newborns = int((self.t_age == 0).sum())
                _newborn_micros = self.MicroMrkvNow[self.t_age == 0]
                _from_newborns = _Cnt2(_newborn_micros.tolist())
                print(f"[PHASE-R shuf-postT0 seed={_agent_seed} st={shock_type}] "
                      f"macro={dict(sorted(_Cnt2(_maP.tolist()).items()))} "
                      f"micro={dict(sorted(_Cnt2(_miP.tolist()).items()))} "
                      f"newborns={_newborns} "
                      f"newborn_micros={dict(sorted(_from_newborns.items()))}", flush=True)

        self.t_age = t_age_start
        self.MicroMrkvNow = MicroMrkvNow_start
        self.MacroMrkvNow = MacroMrkvNow_start
        self.shocks['Mrkv'] = J * self.MacroMrkvNow + self.MicroMrkvNow

        # --- Income shocks (same logic as original, respecting flags) ---
        tax_cut_multiplier = np.ones_like(self.shock_history['Mrkv'])
        CheckAmount = np.zeros_like(self.shock_history['Mrkv'])
        if shock_type in ("recessionTaxCut", "TaxCut"):
            tax_cut_states = np.logical_and(
                np.greater(self.shock_history['Mrkv'], 2 * J - 1),
                np.less(self.shock_history['Mrkv'], 9 * 2 * J))
            tax_cut_multiplier[tax_cut_states] *= self.TaxCutIncFactor
        elif shock_type in ("recessionCheck", "Check"):
            CheckAmount[0] = self.CheckStimLvl
            CheckAmount[0] = CheckAmount[0] / self.state_now['pLvl']
            for agent_idx in range(len(CheckAmount[0])):
                p = self.state_now['pLvl'][agent_idx]
                if p < self.CheckStimLvl_PLvl_Cutoff_start:
                    s = 1
                elif p > self.CheckStimLvl_PLvl_Cutoff_end:
                    s = 0
                else:
                    s = 1 - (p - self.CheckStimLvl_PLvl_Cutoff_start) / (
                        self.CheckStimLvl_PLvl_Cutoff_end - self.CheckStimLvl_PLvl_Cutoff_start)
                CheckAmount[0][agent_idx] *= s

        employed = np.equal(self.shock_history['Mrkv'] % J, 0)
        self.shock_history['PermShk'][employed] = self.perm_shock_fixed_hist[employed]
        self.shock_history['TranShk'][employed] = (
            self.tran_shock_fixed_hist[employed] * tax_cut_multiplier[employed]
            + CheckAmount[employed] / self.perm_shock_fixed_hist[employed])
        unemp_without_benefits = np.equal(self.shock_history['Mrkv'] % J, J - 1)
        unemp_with_benefits = np.logical_not(np.logical_or(employed, unemp_without_benefits))
        # BUG-040: 3-way conditional for unemployed PermShk. See twin at
        # hit_with_recession_shock for full doc.
        if getattr(self, 'perm_shocks_during_unemployment', False):
            self.shock_history['PermShk'][unemp_without_benefits] = self.perm_shock_fixed_hist[unemp_without_benefits]
            self.shock_history['PermShk'][unemp_with_benefits] = self.perm_shock_fixed_hist[unemp_with_benefits]
        elif getattr(self, 'unemp_pLvl_grows_like_employed', False):
            G_uniform = float(self.PermGroFac[0][0])
            self.shock_history['PermShk'][unemp_without_benefits] = G_uniform
            self.shock_history['PermShk'][unemp_with_benefits] = G_uniform
        else:
            self.shock_history['PermShk'][unemp_without_benefits] = 1.0
            self.shock_history['PermShk'][unemp_with_benefits] = 1.0
        self.shock_history['TranShk'][unemp_without_benefits] = self.IncUnempNoBenefits + CheckAmount[unemp_without_benefits]
        self.shock_history['TranShk'][unemp_with_benefits] = self.IncUnemp + CheckAmount[unemp_with_benefits]

        # BUG-043 fix: under bug_fix encoding, the micro state space includes
        # u3Q and u4Q as explicit states. By default they are classified as
        # unemp_with_benefits (= micro != 0 and != noBen), but they should only
        # actually receive extension benefits (IncUnemp) under the recessionUI
        # scenario AND when the macro state corresponds to recession.
        # In all other cases (non-UI scenarios, or recessionUI with macro = normal
        # i.e. recession ended), u3Q/u4Q should receive IncUnempNoBenefits.
        #
        # The lines above set u3Q/u4Q TranShk = IncUnemp by default. Override
        # below for the cases where extension is NOT active.
        try:
            from EstimParameters import HAFISCAL_UI_STATE_ENCODING, Policy_ExtraBenefitQuarters
        except ImportError:
            HAFISCAL_UI_STATE_ENCODING = 'legacy'
        if HAFISCAL_UI_STATE_ENCODING == 'bug_fix':
            J = self.num_base_MrkvStates
            ub_normal = self.UBspell_normal
            micro = self.shock_history['Mrkv'] % J
            macro = self.shock_history['Mrkv'] // J
            # u3Q, u4Q micro indices
            extension_micro_min = ub_normal + 1   # = 3 in baseline (u3Q)
            extension_micro_max = ub_normal + Policy_ExtraBenefitQuarters  # = 4 in baseline (u4Q)
            extension_states = (micro >= extension_micro_min) & (micro <= extension_micro_max)
            if shock_type in ('recessionUI', 'UI'):
                # Extension active only at recession macro states (= odd indices).
                # Override u3Q/u4Q at NORMAL macros to no-benefits (extension expired).
                extension_inactive = extension_states & (macro % 2 == 0)
                self.shock_history['TranShk'][extension_inactive] = (
                    self.IncUnempNoBenefits + CheckAmount[extension_inactive]
                )
            else:
                # All other scenarios: u3Q/u4Q never receive extension benefits.
                self.shock_history['TranShk'][extension_states] = (
                    self.IncUnempNoBenefits + CheckAmount[extension_states]
                )

        self.shock_history['who_dies'] = self.who_dies_fixed_hist
        self.shock_history['update_draw'] = self.update_draw_fixed_hist
        self.shock_history['unemployment_draw'] = self.unemployment_draw_fixed_hist

    def get_states(self):
        """Extend parent's get_states to include AggDemandFac in the budget.

        When ad_in_budget=True, adjusts mNrm after the parent computes it
        so that income is scaled by AggDemandFac:
          mNrm = bNrm + TranShk * AggDemandFac
        instead of the default:
          mNrm = bNrm + TranShk

        This matches TM's treatment of the AD channel, where
        build_experiment_period_tm scales TranShk by AggDemandFac.
        """
        super().get_states()
        if getattr(self, 'ad_in_budget', False):
            ADF = getattr(self, 'AggDemandFac', 1.0)
            if not np.isscalar(ADF):
                ADF = float(ADF)
            if abs(ADF - 1.0) > 1e-12:
                self.state_now['mNrm'] += self.shocks['TranShk'] * (ADF - 1.0)

    def switch_to_counterfactual_mode(self, shock_type):
        del self.solution
        self.del_from_time_vary('solution')
        self.switch_shock_type(shock_type)
        # Adjust simulation parameters for the counterfactual experiments
        self.T_sim = T_sim
        self.track_vars = ['cNrm','pLvl','aNrm','mNrm','MrkvNowPcvd','MacroMrkvNow','MicroMrkvNow','cLvl','cLvl_splurge']
        self.use_prestate = None
        self.track_vars += ['unemployment_draw']
        
    def switch_shock_type(self, shock_type):
        # Swap in "big" versions of the Markov-state-varying attributes
        if shock_type == "base":
            self.MrkvArray = self.MrkvArray_base
            self.IncShkDstn = self.IncShkDstn_base
            self.CondMrkvArrays = self.CondMrkvArrays_recession
        elif shock_type == "recession":
            self.MrkvArray = self.MrkvArray_recession
            self.IncShkDstn = self.IncShkDstn_recession
            self.CondMrkvArrays = self.CondMrkvArrays_recession
        elif shock_type == "recessionUI" or shock_type == "UI":
            self.MrkvArray = self.MrkvArray_recessionUI
            self.IncShkDstn = self.IncShkDstn_recessionUI
            self.CondMrkvArrays = self.CondMrkvArrays_recessionUI
        elif shock_type == "recessionTaxCut" or shock_type == "TaxCut":
            self.MrkvArray = self.MrkvArray_recessionTaxCut
            self.IncShkDstn = self.IncShkDstn_recessionTaxCut
            self.CondMrkvArrays = self.CondMrkvArrays_recessionTaxCut
        elif shock_type == "recessionCheck" or shock_type == "Check":
            self.MrkvArray = self.MrkvArray_recessionCheck
            self.IncShkDstn = self.IncShkDstn_recessionCheck
            self.CondMrkvArrays = self.CondMrkvArrays_recessionCheck
        num_mrkv_states = self.MrkvArray[0].shape[0]
        self.LivPrb = [np.array(self.LivPrb_base*num_mrkv_states)]
        # Respect unemp_pLvl_grows_like_employed: when True, G_u = G_emp
        # so that PermGroFac is identical across all Markov states (p ⊥ state).
        # Without this, switch_shock_type reverts PermGroFac to [G_emp, 1, 1, 1]
        # even when the agent was initialized with [G_emp, G_emp, G_emp, G_emp],
        # creating a baseline/experiment mismatch in TM that inflates multipliers.
        if getattr(self, 'unemp_pLvl_grows_like_employed', False):
            G_u = float(np.asarray(self.PermGroFac_base).ravel()[0])
        else:
            G_u = float(getattr(self, 'PermGroFac_unemp', 1.0))
        nb = int(getattr(self, 'num_base_MrkvStates', 1))
        self.PermGroFac = [tile_PermGroFac_composite(
            self.PermGroFac_base, G_u, num_mrkv_states, nb)]
        self.Rfree = np.array(num_mrkv_states*self.Rfree_base)
        
    def get_Rfree(self):
        RfreeNow = self.Rfree[self.shocks['Mrkv']]*np.ones(self.AgentCount)
        return RfreeNow
    
    def market_action(self):
        self.simulate(1)
        
    def get_Cratio_now(self):  # This function exists to be overwritten in StickyE model
        return self.Cratio*np.ones(self.AgentCount)
    
    def get_agg_demand_fac_now(self):  
        return self.AggDemandFac*np.ones(self.AgentCount)

    def get_shocks(self):
        AggIndMrkvConsumerType.get_shocks(self)
        if (hasattr(self,'Mrkv_univ') and self.Mrkv_univ is not None):
            self.shocks['Mrkv'] = self.MrkvNow_temp # Make sure real sequence is recorded
        self.shocks['update_draw'] = self.RNG.permutation(np.array(range(self.AgentCount))) # A list permuted integers, low draws will update their aggregate Markov state
        if (hasattr(self,'Mrkv_univ') and self.Mrkv_univ is not None):
            self.shocks['Mrkv'] = self.MrkvNow_temp # Make sure real sequence is recorded
        self.shocks['update_draw'] = self.RNG.permutation(np.array(range(self.AgentCount))) # A list permuted integers, low draws will update their aggregate Markov state
                   
    def get_states(self):
        AggIndMrkvConsumerType.get_states(self)
        
        # Initialize the random draw of Pi*N agents who update
        how_many_update = int(round(self.UpdatePrb*self.AgentCount))
        self.update = self.shocks['update_draw'] < how_many_update
        # Only updaters change their perception of the Markov state
        if hasattr(self,'MrkvNowPcvd'):
            self.MrkvNowPcvd[self.update] = self.shocks['Mrkv'][self.update]
        else: # This only triggers in the first simulated period
            self.MrkvNowPcvd = np.ones(self.AgentCount,dtype=int)*self.shocks['Mrkv']
        # update the idiosyncratic state (employed, unemployed with benefits, unemployed without benefits)
        # but leave the macro state as it is (idiosyncratic state is 'modulo self.num_base_MrkvStates')
        self.MrkvNowPcvd = np.remainder(self.shocks['Mrkv'],self.num_base_MrkvStates) + self.num_base_MrkvStates*np.floor_divide(self.MrkvNowPcvd,self.num_base_MrkvStates)
        # See math-derive-appendix (m-budget): mNrm = bNrm + TranShk * ADF
        self.state_now["mNrm"] = self.state_now["bNrm"] + self.shocks['TranShk']*self.AggDemandFac
        
    def get_macro_markov_states(self):
        self.MacroMrkvNow = self.EconomyMrkvNow*np.ones(self.AgentCount, dtype=int)
        
    def get_micro_markv_states_guts(self, unemployment_draw):
        dont_change = self.t_age == 0 # Don't change Markov state for those who were just born
        # if self.t_sim == 0: # Respect initial distribution of Markov states
        #     dont_change[:] = True

        # Determine which agents are in which states right now
        J = self.CondMrkvArrays[0].shape[0]
        MicroMrkvPrev = copy(self.MicroMrkvNow)
        MicroMrkvNow = np.zeros(self.AgentCount,dtype=int)
        MicroMrkvBoolArray = np.zeros((J,self.AgentCount))
        for j in range(J):
            MicroMrkvBoolArray[j,:] = MicroMrkvPrev == j

        # PHASE-R DIAG: track per-source transition counts
        import os as _os_p
        _dump = _os_p.environ.get('HAFISCAL_PHASER_DUMP', '') == '1' and \
                _os_p.environ.get('HAFISCAL_PHASER_GUTS', '') == '1'
        if _dump:
            from collections import Counter as _Cnt
            _per_src = {}
            _src_counts = {}
            for j in range(J):
                _src_counts[j] = int(MicroMrkvBoolArray[j, :].sum())
        # Draw new Markov states for each agent
        for i in range(self.MacroMrkvArray.shape[0]):
            Cutoffs = np.cumsum(self.CondMrkvArrays[i],axis=1)
            macro_match = self.MacroMrkvNow == i
            for j in range(J):
                these = np.logical_and(macro_match, MicroMrkvBoolArray[j,:]).astype(bool)
                if _dump and these.sum() > 0:
                    assignments = np.searchsorted(Cutoffs[j, :], unemployment_draw[these]).astype(int)
                    _per_src[(i, j)] = dict(sorted(_Cnt(assignments.tolist()).items()))
                MicroMrkvNow[these] = np.searchsorted(Cutoffs[j,:],unemployment_draw[these]).astype(int)
        if _dump:
            print(f"[PHASE-R guts] J={J}, MacroMrkvNow={self.MacroMrkvNow}, "
                  f"src counts={_src_counts}", flush=True)
            # Dump cond_mrkv at MacroMrkvNow (the active one)
            try:
                _macro_active = int(self.MacroMrkvNow) if np.isscalar(self.MacroMrkvNow) else int(np.asarray(self.MacroMrkvNow).flat[0])
                _cm_active = np.asarray(self.CondMrkvArrays[_macro_active])
                print(f"[PHASE-R guts] cond_mrkv at macro={_macro_active}: "
                      f"row0={np.round(_cm_active[0], 4).tolist()}", flush=True)
            except Exception as _e:
                print(f"[PHASE-R guts] could not dump cond_mrkv: {_e}", flush=True)
            for (i, j), out in _per_src.items():
                print(f"[PHASE-R guts] macro={i}, src_micro={j}, n_src={_src_counts.get(j, 0)}, "
                      f"out_dist={out}", flush=True)
        MicroMrkvNow[dont_change] = MicroMrkvNow[dont_change]
        self.MicroMrkvNow = MicroMrkvNow.astype(int)
        
    def get_micro_markov_states(self):
        self.shocks['unemployment_draw'] = Uniform(seed=self.RNG.integers(2**31-1)).draw(self.AgentCount)
        self.get_micro_markv_states_guts(self.shocks['unemployment_draw'])
           
    def get_markov_states(self):
        self.get_macro_markov_states()
        self.get_micro_markov_states()
        MrkvNow = self.num_base_MrkvStates*self.MacroMrkvNow + self.MicroMrkvNow
        self.shocks['Mrkv'] = MrkvNow.astype(int)
        if (hasattr(self,'Mrkv_univ') and self.Mrkv_univ is not None):
            self.MrkvNow_temp = self.shocks['Mrkv']
            self.shocks['Mrkv'] = self.Mrkv_univ*np.ones(self.AgentCount, dtype=int)
            # ^^ Store the real states but force income shocks to be based on one particular state
            
    def update_mrkv_array(self, shock_type):
        if shock_type=="base":
            self.MacroMrkvArray = np.array([[1.0]])
            self.CondMrkvArrays = make_cond_mrkv_arrays_base(self.Urate_normal, self.Uspell_normal, self.UBspell_normal)
            self.MrkvArray = make_full_mrkv_array(self.MacroMrkvArray, self.CondMrkvArrays)
        elif shock_type=="recession":
            self.MacroMrkvArray = make_macro_mrkv_array_recession(self.Rspell, self.num_experiment_periods)
            self.CondMrkvArrays = make_cond_mrkv_arrays_recession(self.Urate_normal, self.Uspell_normal, self.UBspell_normal, self.Urate_recession, self.Uspell_recession, self.num_experiment_periods)
            self.MrkvArray = make_full_mrkv_array(self.MacroMrkvArray, self.CondMrkvArrays)
        elif shock_type=="recessionUI" or shock_type=="UI":
            self.MacroMrkvArray = make_macro_mrkv_array_recession(self.Rspell, self.num_experiment_periods)
            self.CondMrkvArrays = make_cond_mrkv_arrays_recession_ui(self.Urate_normal, self.Uspell_normal, self.UBspell_normal, self.Urate_recession, self.Uspell_recession, self.num_experiment_periods,  self.UBspell_extended-self.UBspell_normal)
            self.MrkvArray = make_full_mrkv_array(self.MacroMrkvArray, self.CondMrkvArrays)
        elif shock_type=="recessionTaxCut" or shock_type=="TaxCut":
            self.MacroMrkvArray = make_macro_mrkv_array_recession(self.Rspell, self.num_experiment_periods)
            self.CondMrkvArrays = make_cond_mrkv_arrays_recession(self.Urate_normal, self.Uspell_normal, self.UBspell_normal, self.Urate_recession, self.Uspell_recession, self.num_experiment_periods)
            self.MrkvArray = make_full_mrkv_array(self.MacroMrkvArray, self.CondMrkvArrays)
        elif shock_type=="recessionCheck" or shock_type=="Check":
            self.MacroMrkvArray = make_macro_mrkv_array_recession(self.Rspell, self.num_experiment_periods)
            self.CondMrkvArrays = make_cond_mrkv_arrays_recession(self.Urate_normal, self.Uspell_normal, self.UBspell_normal, self.Urate_recession, self.Uspell_recession, self.num_experiment_periods)
            self.MrkvArray = make_full_mrkv_array(self.MacroMrkvArray, self.CondMrkvArrays)
        else:
            print("shock_type not recognized")
    
    def solve_if_changed(self):
        '''
        Re-solve the lifecycle model only if the attributes MrkvArray
        do not match those in MrkvArray_prev .
        '''
        # Check whether MrkvArray has changed (and whether they exist at all!)
        try: 
            if self.MrkvArray[0].size == self.MrkvArray_prev[0].size:
                same_MrkvArray = distance_metric(self.MrkvArray, self.MrkvArray_prev) == 0.
                if (same_MrkvArray):
                    return
        except:
            pass
        
        # Re-solve the model, then note the values in MrkvArray
        self.solve()
        self.MrkvArray_prev = self.MrkvArray
    
    def calc_age_distribution(self):
        '''
        Calculates the long run distribution of t_cycle in the population.
        '''
        if self.T_cycle==1:
            T_cycle_actual = self.T_age if self.T_age is not None else 400
            LivPrb_array = [[self.LivPrb[0][0]]]*T_cycle_actual
        else:
            T_cycle_actual = self.T_cycle
            LivPrb_array = self.LivPrb
        AgeMarkov = np.zeros((T_cycle_actual+1,T_cycle_actual+1))
        for t in range(T_cycle_actual):
            p = LivPrb_array[t][0]
            AgeMarkov[t,t+1] = p
            AgeMarkov[t,0] = 1. - p
        AgeMarkov[-1,0] = 1.
        
        AgeMarkovT = np.transpose(AgeMarkov)
        vals, vecs = np.linalg.eig(AgeMarkovT)
        dist = np.abs(np.abs(vals) - 1.)
        idx = np.argmin(dist)
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore") # Ignore warning about casting complex eigenvector to float
            LRagePrbs = vecs[:,idx].astype(float)
        LRagePrbs /= np.sum(LRagePrbs)
        age_vec = np.arange(T_cycle_actual+1).astype(int)
        self.LRageDstn = DiscreteDistribution(LRagePrbs, age_vec,
                                seed=self.RNG.integers(2**31-1))
        
        
    def initialize_ages(self):
        '''
        Assign initial values of t_cycle to simulated agents, using the attribute
        LRageDstn as the distribution of discrete ages.
        '''
        age = self.LRageDstn.draw_events(self.AgentCount)
        age = age.astype(int)
        if self.T_cycle!=1:
            self.t_cycle = age
        self.t_age = age
                   
    def get_controls(self):
        cNrmNow = np.zeros(self.AgentCount) + np.nan
        MPCnow = np.zeros(self.AgentCount) + np.nan
        CratioNow = self.get_Cratio_now()
        J = self.MrkvArray[0].shape[0]
        
        MrkvBoolArray = np.zeros((J,self.AgentCount), dtype=bool)
        for j in range(J):
            MrkvBoolArray[j,:] = j == self.MrkvNowPcvd # agents choose control based on *perceived* Markov state
        
        for t in range(self.T_cycle):
            right_t = t == self.t_cycle
            for j in range(J):
                these = np.logical_and(right_t, MrkvBoolArray[j,:])
                cNrmNow[these] = self.solution[t].cFunc[j](self.state_now['mNrm'][these], CratioNow[these])
                # Marginal propensity to consume
                MPCnow[these]  = self.solution[t].cFunc[j].derivativeX(self.state_now['mNrm'][these], CratioNow[these])
        self.controls['cNrm'] = cNrmNow
        self.state_now['cNrm'] = cNrmNow
        self.MPCNow  = MPCnow
        # See math-derive (homogeneity): C = p * c(m,z)
        self.state_now['cLvl'] = cNrmNow*self.state_now['pLvl']
        # CDC-MOD-BUG031: Per-agent realized consumption under CDC household-bargain reading: weighted-average of optimizer voice's proposal and splurger voice's proposal. ESC version computes the same value but reads it as Optimizer-mass-weighted Optimizer consumption + Splurger-mass-weighted Splurger consumption. See plans/20260425-2102h_cdc-implementation-map.md row 31.4 and BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md §4.1 / §5.1.
        # implements (eq:total-CDC) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md (CDC reading; under ESC the same line implements (eq:total-ESC) — values coincide; interpretation differs)
        # See math-derive (MC-agg) and (splurge): cLvl_splurge = (1-S)*cLvl + S*pLvl*TranShk*ADF
        self.state_now['cLvl_splurge'] = (1.0-self.Splurge)*self.state_now['cLvl'] + self.Splurge*self.state_now['pLvl']*self.shocks['TranShk']*self.AggDemandFac

    def get_poststates(self):
        """CDC-MOD-BUG031 [central anchor]. Override of HARK's default a = m - cFunc(m) with a = m - cLvl_splurge/pLvl (subtract realized weighted consumption per (eq:budget-CDC) of models_CDC_and_ESC.md §4.2; alias (CDC-1)). ESC version: a = m - cFunc(m) (HARK default; subtracts only the Optimizer's cFunc(m) because under ESC's per-Optimizer normalization that *is* the Optimizer's whole consumption — the ς·y is the Splurger's separate ledger and never touches the Optimizer's a — see (eq:budget-ESC) in §5.2; alias (ESC-1)). See plans/20260425-2102h_cdc-implementation-map.md row 31.5 and BUGS_private/HAFiscal_BUG-031_splurge_not_in_budget.md.

        implements (eq:budget-CDC) of BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md

        splurge-in-budget splurge fix: asset update uses actual total consumption
        (cLvl_splurge) not the solver's c_HARK.  Under eq. (5) of the paper,
        the household's actual spending is c_actual = (1-S)*cFunc(m) + S*y,
        so budget identity requires a = m - c_actual.  The ORIGINAL code
        used a = m - cFunc(m) (solver's c), which drops the ς*(y - cFunc)
        wedge and violates the paper's stated budget constraint.

        See BUGS_private/HAFiscal_splurge_budget_inconsistency/ and eq. (5).

        Diagnostic: set HAFISCAL_SPLURGE_OLD=1 to restore the pre-splurge-in-budget
        (buggy) asset update a = m - cFunc(m).  Used only for the
        welfare-gap MC diagnostic (plans/20260417-1242h_welfare-vs-multiplier-asymmetry-hypothesis.md).
        """
        if os.environ.get("HAFISCAL_SPLURGE_OLD", "0") == "1":
            # Pre-splurge-in-budget behavior: asset update drops the ς·(y - cFunc) wedge.
            # (Equivalent to ESC's asset rule; see models_CDC_and_ESC.md §5.2 ESC-1.)
            self.state_now['aNrm'] = self.state_now['mNrm'] - self.state_now['cNrm']
            self.state_now['aLvl'] = self.state_now['aNrm'] * self.state_now['pLvl']
            return
        # ESC interpretation: asset update uses only the optimizer's cFunc(m);
        # the splurger's ς·xi consumption is on a separate ledger (eq:budget-ESC).
        # Per-agent `interpretation` attribute is set in __init__ from kwarg /
        # env / default. CDC default preserves byte-identical legacy behavior.
        if getattr(self, 'interpretation', 'CDC') == 'ESC':
            self.state_now['aNrm'] = self.state_now['mNrm'] - self.state_now['cNrm']
            self.state_now['aLvl'] = self.state_now['aNrm'] * self.state_now['pLvl']
            return
        # CDC asset rule encapsulated in module-level helper `_cdc_asset_rule`.
        self.state_now['aNrm'], self.state_now['aLvl'] = _cdc_asset_rule(
            self.state_now, self.shocks, self.AggDemandFac, self.Splurge
        )
        # Preserve HARK's standard PlvlAggNow handling (see AggShockConsumerType):
        if hasattr(self, 'PlvlAggNow'):
            pass  # PlvlAggNow is managed by parent's aggregate update logic

    def reset(self):
        return # do nothing


# =====================================================================
# Dual-measure (P/Q) variant of AggFiscalType
# =====================================================================

try:
    from HARK.dual_measure import DualMeasureMixin
    _HAS_DUAL_MEASURE = True
except ImportError:
    _HAS_DUAL_MEASURE = False


if _HAS_DUAL_MEASURE:
    class DualAggFiscalType(DualMeasureMixin, AggFiscalType):
        """AggFiscalType with simultaneous P/Q (Harmenberg) MC simulation.

        Overrides Q-pipeline methods for HAFiscal-specific features:
        - AggDemandFac in budget constraint  (math-derive (m-budget))
        - Sticky expectations (MrkvNowPcvd)
        - 2-argument cFunc(mNrm, Cratio)
        - Splurge consumption (cLvl_splurge)  (math-derive (splurge))

        Usage::

            agent = DualAggFiscalType(**params)
            agent.solve()
            agent.setup_Q_measure()
            ...
            agent.simulate()
            Q_splurge = agent.history_Q['cLvl_splurge']
        """

        def _transition_Q(self):
            """Q-measure states: includes AggDemandFac in mNrm."""
            pLvlPrev = self.state_prev_Q["pLvl"]
            kNrm = self.state_prev_Q["aNrm"]
            RportNow = self.get_Rport()

            pLvlNow = pLvlPrev * self.shocks_Q["PermShk"]
            ReffNow = RportNow / self.shocks_Q["PermShk"]
            bNrmNow = ReffNow * kNrm
            mNrmNow = bNrmNow + self.shocks_Q["TranShk"] * self.AggDemandFac

            self.state_now_Q["pLvl"] = pLvlNow
            self.state_now_Q["mNrm"] = mNrmNow

        def _get_controls_Q(self):
            """Q-measure controls: sticky expectations, 2-arg cFunc, splurge."""
            cNrmQ = np.full(self.AgentCount, np.nan)
            CratioNow = self.get_Cratio_now()
            J = self.MrkvArray[0].shape[0]

            MrkvBoolArray = np.zeros((J, self.AgentCount), dtype=bool)
            for j in range(J):
                MrkvBoolArray[j, :] = j == self.MrkvNowPcvd

            for t in range(self.T_cycle):
                right_t = t == self.t_cycle
                for j in range(J):
                    these = np.logical_and(right_t, MrkvBoolArray[j, :])
                    if np.any(these):
                        cNrmQ[these] = self.solution[t].cFunc[j](
                            self.state_now_Q["mNrm"][these],
                            CratioNow[these],
                        )

            self.controls_Q["cNrm"] = cNrmQ
            self.state_now_Q["cNrm"] = cNrmQ
            cLvl_Q = cNrmQ * self.state_now_Q["pLvl"]
            self.state_now_Q["cLvl"] = cLvl_Q
            self.state_now_Q["cLvl_splurge"] = (
                (1.0 - self.Splurge) * cLvl_Q
                + self.Splurge
                * self.state_now_Q["pLvl"]
                * self.shocks_Q["TranShk"]
                * self.AggDemandFac
            )

        def setup_Q_measure(self):
            """Extend: register _base_uniform in shock_vars for history storage."""
            super().setup_Q_measure()
            if "_base_uniform" not in self.shock_vars:
                self.shock_vars.append("_base_uniform")

        def switch_shock_type(self, shock_type):
            """After swapping IncShkDstn, rebuild IncShkDstn_Q."""
            super().switch_shock_type(shock_type)
            if self.dual_measure:
                self.setup_Q_measure()

        def switch_to_counterfactual_mode(self, shock_type):
            """After swapping IncShkDstn, rebuild IncShkDstn_Q."""
            super().switch_to_counterfactual_mode(shock_type)
            if self.dual_measure:
                self.setup_Q_measure()

        def hit_with_recession_shock(self, shock_type):
            """Extend: store per-period TranShk adjustments for Q-track.

            The base method modifies shock_history['TranShk'] directly
            with tax_cut_multiplier and CheckAmount.  Since the Q-track
            draws TranShk_Q from IncShkDstn_Q (not shock_history), we
            store the adjustments to apply during _draw_Q_shocks().
            """
            super().hit_with_recession_shock(shock_type)
            if not self.dual_measure:
                return

            T, N = self.shock_history['Mrkv'].shape
            mult = np.ones((T, N))
            addend = np.zeros((T, N))

            if shock_type in ("recessionTaxCut", "TaxCut"):
                tc_states = np.logical_and(
                    self.shock_history['Mrkv'] > 2 * self.num_base_MrkvStates - 1,
                    self.shock_history['Mrkv'] < 9 * 2 * self.num_base_MrkvStates,
                )
                mult[tc_states] = self.TaxCutIncFactor
            elif shock_type in ("recessionCheck", "Check"):
                check_nrm = np.zeros(N)
                for i in range(N):
                    p = self.state_now['pLvl'][i]
                    if p < self.CheckStimLvl_PLvl_Cutoff_start:
                        phi = 1.0
                    elif p > self.CheckStimLvl_PLvl_Cutoff_end:
                        phi = 0.0
                    else:
                        phi = 1.0 - (p - self.CheckStimLvl_PLvl_Cutoff_start) / (
                            self.CheckStimLvl_PLvl_Cutoff_end - self.CheckStimLvl_PLvl_Cutoff_start
                        )
                    check_nrm[i] = self.CheckStimLvl * phi / p
                addend[0] = check_nrm

            self._Q_TranShk_mult = mult
            self._Q_TranShk_addend_nrm = addend

        def get_shocks(self):
            """Extend: store flat per-agent base draws for Q-replay."""
            super().get_shocks()
            if self.dual_measure:
                base_dict = getattr(self, "_base_shock_draws", {})
                flat = np.full(self.AgentCount, np.nan)

                mrkv_univ = getattr(self, "Mrkv_univ", None)
                if mrkv_univ is not None:
                    j_used = int(mrkv_univ)
                    for t in range(self.T_cycle):
                        draws = base_dict.get((t, j_used))
                        if draws is not None:
                            these = t == self.t_cycle
                            flat[these] = draws
                else:
                    MrkvNow = self.shocks["Mrkv"]
                    for (t, j), draws in base_dict.items():
                        these = np.logical_and(t == self.t_cycle, j == MrkvNow)
                        flat[these] = draws

                newborn = self.t_age == 0
                flat[newborn] = np.nan
                self.shocks["_base_uniform"] = flat

        def _draw_Q_shocks(self):
            """HAFiscal-specific Q-shock drawing with base-draw pairing.

            Chooses the correct IncShkDstn_Q index adaptively:
            - If IncShkDstn_Q covers all composite states, use the full
              composite state j directly.
            - If IncShkDstn_Q only covers micro states (baseline burn-in),
              fall back to j_micro = j % num_base.

            When base uniform draws are available (stored during
            make_shock_history), inverts them through the Q-CDF for
            paired P/Q simulation.  Otherwise draws independently.
            """
            from HARK.dual_measure import _cdf_invert

            MrkvNow = self.shocks["Mrkv"]
            newborn = self.t_age == 0
            J_base = self.num_base_MrkvStates
            base_uniform = self.shocks.get("_base_uniform", None)

            n_Q_states = len(self.IncShkDstn_Q[0])
            use_full_state = n_Q_states > J_base

            unique_j = np.unique(MrkvNow[~newborn]) if np.any(~newborn) else np.array([], dtype=int)

            PermShkQ = np.zeros(self.AgentCount)
            TranShkQ = np.zeros(self.AgentCount)

            for t in range(self.T_cycle):
                right_t = t == self.t_cycle
                for j in unique_j:
                    these = np.logical_and(right_t, MrkvNow == j)
                    N = np.sum(these)
                    if N > 0:
                        j_q = int(j) if use_full_state else int(j % J_base)
                        j_pgf = int(j % J_base)

                        IncShkDstnQ = self.IncShkDstn_Q[t - 1][j_q]
                        PermGroFacNow = self.PermGroFac[t - 1][j_pgf]

                        if base_uniform is not None:
                            draws = base_uniform[these]
                            valid = ~np.isnan(draws)
                            indices_Q = np.zeros(N, dtype=int)
                            if valid.any():
                                indices_Q[valid] = _cdf_invert(
                                    draws[valid], IncShkDstnQ.pmv
                                )
                            if (~valid).any():
                                indices_Q[~valid] = IncShkDstnQ.draw_events(
                                    int((~valid).sum())
                                )
                        else:
                            indices_Q = IncShkDstnQ.draw_events(N)

                        PermShkQ[these] = (
                            IncShkDstnQ.atoms[0][indices_Q] * PermGroFacNow
                        )
                        TranShkQ[these] = IncShkDstnQ.atoms[1][indices_Q]

            for j_micro in range(J_base):
                these_nb = np.logical_and(newborn, (MrkvNow % J_base) == j_micro)
                if np.any(these_nb):
                    PermShkQ[these_nb] = self.PermGroFac[0][j_micro]
            TranShkQ[newborn] = 1.0

            Q_mult = getattr(self, "_Q_TranShk_mult", None)
            Q_add = getattr(self, "_Q_TranShk_addend_nrm", None)
            if Q_mult is not None and self.t_sim < Q_mult.shape[0]:
                employed_Q = (MrkvNow % J_base) == 0
                TranShkQ[employed_Q] *= Q_mult[self.t_sim, employed_Q]
                if Q_add is not None:
                    TranShkQ[employed_Q] += Q_add[self.t_sim, employed_Q] / PermShkQ[employed_Q]
                    unemp_no_ben = (MrkvNow % J_base) == (J_base - 1)
                    TranShkQ[unemp_no_ben] += Q_add[self.t_sim, unemp_no_ben]
                    unemp_w_ben = ~(employed_Q | unemp_no_ben) & ~newborn
                    TranShkQ[unemp_w_ben] += Q_add[self.t_sim, unemp_w_ben]

            self.shocks_Q["PermShk"] = PermShkQ
            self.shocks_Q["TranShk"] = TranShkQ

        def _get_poststates_Q(self):
            """Q-measure post-states: assets + shared Markov/macro states."""
            self.state_now_Q["aNrm"] = (
                self.state_now_Q["mNrm"] - self.controls_Q["cNrm"]
            )
            if "aLvl" in self.state_now:
                self.state_now_Q["aLvl"] = (
                    self.state_now_Q["aNrm"] * self.state_now_Q["pLvl"]
                )
            # Mrkv is in both state_now and shocks; state_now_Q takes priority
            # in recording, so we must write here to avoid stale empty arrays
            if "Mrkv" in self.shocks:
                mrkv_copy = self.shocks["Mrkv"].copy()
                self.state_now_Q["Mrkv"] = mrkv_copy
                self.shocks_Q["Mrkv"] = mrkv_copy
            # MrkvNowPcvd etc. are direct attributes, not in state_now
            for attr_name in ("MrkvNowPcvd", "MacroMrkvNow", "MicroMrkvNow"):
                val = getattr(self, attr_name, None)
                if val is not None:
                    self.state_now_Q[attr_name] = (
                        val.copy() if isinstance(val, np.ndarray) else val
                    )


def solve_agg_cons_markov_alt(solution_next,IncShkDstn,LivPrb,DiscFac,CRRA,Rfree,PermGroFac,
                                 MrkvArray,BoroCnstArt,aXtraGrid, Cgrid, CFunc, ADFunc,
                                 num_experiment_periods, num_base_MrkvStates):
    '''
    Solves a single period consumption-saving problem with risky income and
    stochastic transitions between discrete states, in a Markov fashion.  Has
    identical inputs as solveConsIndShock, except for a discrete
    Markov transitionrule MrkvArray.  Markov states can differ in their interest
    factor, permanent growth factor, and income distribution, so the inputs Rfree,
    PermGroFac, and IncShkDstn are arrays or lists specifying those values in each
    (succeeding) Markov state.
    Parameters
    ----------
    solution_next : ConsumerSolution
        The solution to next period's one period problem.
    IncShkDstn : DiscreteDistribution
        A representation of permanent and transitory income shocks that might
        arrive at the beginning of next period.
    LivPrb : float
        Survival probability; likelihood of being alive at the beginning of
        the succeeding period.
    DiscFac : float
        Intertemporal discount factor for future utility.
    CRRA : float
        Coefficient of relative risk aversion.
    Rfree : np.array
        Risk free interest factor on end-of-period assets for each Markov
        state in the succeeding period.
    PermGroFac : np.array
        Expected permanent income growth factor at the end of this period
        for each Markov state in the succeeding period.
    MrkvArray : np.array
        An NxN array representing a Markov transition matrix between discrete
        states.  The i,j-th element of MrkvArray is the probability of
        moving from state i in period t to state j in period t+1.
    BoroCnstArt: float or None
        Borrowing constraint for the minimum allowable assets to end the
        period with.  If it is less than the natural borrowing constraint,
        then it is irrelevant; BoroCnstArt=None indicates no artificial bor-
        rowing constraint.
    aXtraGrid: np.array
        Array of "extra" end-of-period asset values-- assets above the
        absolute minimum acceptable level.
    Returns
    -------
    solution : ConsumerSolution
        The solution to the single period consumption-saving problem. Includes
        a consumption function cFunc (using cubic or linear splines), a marg-
        inal value function vPfunc, a minimum acceptable level of normalized
        market resources mNrmMin.  All of these attributes are lists or arrays, 
        with elements corresponding to the current Markov state.  E.g.
        solution.cFunc[0] is the consumption function when in the i=0 Markov
        state this period.
    '''
    # Get sizes of grids
    aCount = aXtraGrid.size
    Ccount = Cgrid.size
    StateCount = MrkvArray.shape[0]

    # Loop 1: Build conditional EndOfPrdvP functions for each next-period state.
    EndOfPrdvPfunc_cond = []
    BoroCnstNat_cond = []
    for j in range(StateCount):
            vPfuncNext = solution_next.vPfunc[j]
            mNrmMinNext = solution_next.mNrmMin[j]

            ShkPrbsNext = IncShkDstn[j].pmv
            PermShkValsNext = IncShkDstn[j].atoms[0]
            TranShkValsNext = IncShkDstn[j].atoms[1]
            ShkCount = ShkPrbsNext.size
            aXtra_tiled = np.tile(np.reshape(aXtraGrid, (1, aCount, 1)), (Ccount, 1, ShkCount))

            ShkPrbsNext_tiled = np.tile(np.reshape(ShkPrbsNext, (1, 1, ShkCount)), (Ccount, aCount, 1))
            PermShkValsNext_tiled = np.tile(np.reshape(PermShkValsNext, (1, 1, ShkCount)), (Ccount, aCount, 1))
            TranShkValsNext_tiled_noAD = np.tile(np.reshape(TranShkValsNext, (1, 1, ShkCount)), (Ccount, aCount, 1))

            Cnext_array = np.tile(np.reshape(Cgrid, (Ccount, 1, 1)), (1, aCount, ShkCount))

            AggState = np.floor(j/num_base_MrkvStates)
            RecState = AggState % 2 == 1
            AggDemandFacnext_array = ADFunc(Cnext_array,RecState)
            TranShkValsNext_tiled = AggDemandFacnext_array*TranShkValsNext_tiled_noAD

            # Natural borrowing constraint
            if isinstance(mNrmMinNext, float):
                aNrmMin_candidates = PermGroFac[j]*PermShkValsNext_tiled[:, 0, :] / Rfree[j] * \
                    (mNrmMinNext * Cnext_array[:, 0, :] - TranShkValsNext_tiled[:, 0, :])
            else:
                aNrmMin_candidates = PermGroFac[j]*PermShkValsNext_tiled[:, 0, :] / Rfree[j] * \
                    (mNrmMinNext(Cnext_array[:, 0, :]) - TranShkValsNext_tiled[:, 0, :])

            aNrmMin_vec = np.max(aNrmMin_candidates, axis=1)
            BoroCnstNat_vec = aNrmMin_vec
            aNrmMin_tiled = np.tile(np.reshape(aNrmMin_vec, (Ccount, 1, 1)), (1, aCount, ShkCount))
            aNrmNow_tiled = aNrmMin_tiled + aXtra_tiled

            mNrmNext_array = Rfree[j]*aNrmNow_tiled/(PermGroFac[j]*PermShkValsNext_tiled) + TranShkValsNext_tiled

            # BUG-047 FIX (default ON): include PermGroFac^(-CRRA) in the marginal-value
            # factor — the standard Carroll / standard-HARK form (PermGroFac*PermShk)^(-CRRA),
            # consistent with the transition above which divides by PermGroFac*PermShk. This
            # solver historically omitted it (PermShk^(-CRRA) only), an internal inconsistency.
            # The fix is calibration-absorbed (re-matching K/Y shifts beta +0.004-0.009; matched
            # multipliers change <=0.01), so it does not change published conclusions. Set
            # HAFISCAL_PERMGROFAC_FIX=0 to reproduce the legacy (buggy, pre-BUG-047) behavior.
            # See BUGS_private/HAFiscal_BUG-047_permgrofac_marginal_value_factor.md.
            _pgf_fac = PermGroFac[j]**(-CRRA) if permgrofac_fix_on() else 1.0
            if isinstance(mNrmMinNext, float):
                vPnext_array = Rfree[j]*_pgf_fac*PermShkValsNext_tiled**(-CRRA)*vPfuncNext(mNrmNext_array)
            else:
                vPnext_array = Rfree[j]*_pgf_fac*PermShkValsNext_tiled**(-CRRA)*vPfuncNext(mNrmNext_array, Cnext_array)

            EndOfPrdvP = DiscFac*np.sum(vPnext_array*ShkPrbsNext_tiled, axis=2)

            BoroCnstNat = LinearInterp(Cgrid, BoroCnstNat_vec)
            EndOfPrdvPnvrs = np.concatenate((np.zeros((Ccount, 1)), EndOfPrdvP**(-1./CRRA)), axis=1)
            EndOfPrdvPnvrsFunc_base = BilinearInterp(np.transpose(EndOfPrdvPnvrs), np.insert(aXtraGrid, 0, 0.0), Cgrid)
            EndOfPrdvPnvrsFunc = VariableLowerBoundFunc2D(EndOfPrdvPnvrsFunc_base, BoroCnstNat)
            EndOfPrdvPfunc_cond.append(MargValueFunc2D(EndOfPrdvPnvrsFunc, CRRA))
            BoroCnstNat_cond.append(BoroCnstNat)

    # Prepare some objects that are the same across all current states
    aXtra_tiled = np.tile(np.reshape(aXtraGrid, (1, aCount)), (Ccount, 1))
    cFuncCnst = BilinearInterp(np.array([[0.0, 0.0], [1.0, 1.0]]),
                               np.array([BoroCnstArt, BoroCnstArt+1.0]), np.array([0.0, 1.0]))

    # Now loop through *this* period's discrete states, calculating end-of-period
    # marginal value (weighting across state transitions), then construct consumption
    # and marginal value function for each state.
    cFuncNow = []
    vPfuncNow = []
    mNrmMinNow = []
    for i in range(StateCount):
        # Find natural borrowing constraint for this state by Cratio NOTE THIS CODE IS NOT 100% CHECKED AND SHOULD BE LOOKED OVER
        aNrmMin_candidates = np.zeros((StateCount, Ccount)) + np.nan
        for j in range(StateCount):
            if MrkvArray[i, j] > 0.:  # Irrelevant if transition is impossible
                Cnext = CFunc[i][j](Cgrid)
                aNrmMin_candidates[j, :] = BoroCnstNat_cond[j](Cnext)
        aNrmMin_vec = np.nanmax(aNrmMin_candidates, axis=0)
        BoroCnstNat_vec = aNrmMin_vec

        # Make tiled grids of aNrm and Cratio
        aNrmMin_tiled = np.tile(np.reshape(aNrmMin_vec, (Ccount, 1)), (1, aCount))
        aNrmNow_tiled = aNrmMin_tiled + aXtra_tiled

        
        # # Find the minimum allowable market resources
        # if BoroCnstArt is not None:
        #     mNrmMin = np.maximum(BoroCnstArt, aNrmMin)
        # else:
        #     mNrmMin = aNrmMin
        # mNrmMinNow.append(mNrmMin)
        
        # Loop through feasible transitions and calculate end-of-period marginal value
        EndOfPrdvP = np.zeros((Ccount, aCount))
        for j in range(StateCount):
            if MrkvArray[i, j] > 0.:
                Cnext = CFunc[i][j](Cgrid)
                Cnext_tiled = np.tile(np.reshape(Cnext, (Ccount, 1)), (1, aCount))
                temp = EndOfPrdvPfunc_cond[j](aNrmNow_tiled, Cnext_tiled)
                EndOfPrdvP += MrkvArray[i, j]*temp                    
        EndOfPrdvP *= LivPrb[i] # Account for survival out of the current state
        
        # Calculate consumption and the endogenous mNrm gridpoints for this state
        cNrmNow = EndOfPrdvP**(-1./CRRA)
        mNrmNow = aNrmNow_tiled + cNrmNow

        # Loop through the values in Cgrid and make a piecewise linear consumption function for each
        cFuncBaseByC_list = []
        for n in range(Ccount):
            c_temp = np.insert(cNrmNow[n, :], 0, 0.0)  # Add point at bottom
            m_temp = np.insert(mNrmNow[n, :] - BoroCnstNat_vec[n], 0, 0.0)
            cFuncBaseByC_list.append(LinearInterp(m_temp, c_temp))
            # Add the C-specific consumption function to the list
            
        # Construct the unconstrained consumption function by combining the C-specific functions
        BoroCnstNat = LinearInterp(Cgrid, BoroCnstNat_vec)
        cFuncBase = LinearInterpOnInterp1D(cFuncBaseByC_list, Cgrid)
        cFuncUnc = VariableLowerBoundFunc2D(cFuncBase, BoroCnstNat)

        # Combine the constrained consumption function with unconstrained component
        cFuncNow.append(LowerEnvelope2D(cFuncUnc, cFuncCnst))

        # Make the minimum m function as the greater of the natural and artificial constraints
        mNrmMinNow.append(UpperEnvelope(BoroCnstNat, ConstantFunction(BoroCnstArt)))

        # Construct the marginal value function using the envelope condition
        vPfuncNow.append(MargValueFunc2D(cFuncNow[-1], CRRA))

    # Pack up and return the solution
    solution_now = ConsumerSolution(cFunc=cFuncNow, vPfunc=vPfuncNow, mNrmMin=mNrmMinNow)
    return solution_now


# --- Variance-reduced agent types (optional, see plans/20260405-1924h_hafiscal-pLvl-normalization-mixin.md) ---
try:
    from hafiscal_normalization import HAFiscalNormalizationMixin

    class NormalizedAggFiscalType(HAFiscalNormalizationMixin, AggFiscalType):
        """AggFiscalType with per-cohort pLvl normalization."""
        pass

    class NormalizedDualAggFiscalType(HAFiscalNormalizationMixin, DualAggFiscalType):
        """DualAggFiscalType with per-cohort pLvl normalization."""
        pass
except ImportError:
    pass  # normalization mixin not available; skip silently


class _ADFuncImpl:
    """Picklable replacement for the inline lambda
        lambda C, RecState: C ** (RecState * self.ADelasticity)
    that AggregateDemandEconomy.update() used to install at self.ADFunc.

    A lambda can't be pickled when spawning worker processes (their
    pickled agents carry this attribute), so the parallel-solve switch to
    spawn context required a real class with __reduce__-friendly fields.

    The original lambda captured `self.ADelasticity` via closure, so it
    saw updates that happened AFTER the lambda was created (re-reads on
    each call). The two call sites (Economy.update() at the start of an
    AD outer loop iteration, and inside solve_ad_recession() after
    `self.ADelasticity = self.demand_ADelasticity` + `self.update()`)
    both run update() *after* setting ADelasticity, so capturing the
    value at construction time matches the lambda's effective behavior.
    """
    __slots__ = ("ADelasticity",)

    def __init__(self, ADelasticity):
        self.ADelasticity = float(ADelasticity)

    def __call__(self, C, RecState):
        return C ** (RecState * self.ADelasticity)


class AggregateDemandEconomy(Market):
    '''
    A class to represent an economy in which productivity responds to aggregate
    consumption
    '''
    def __init__(self,
                 agents=None,
                 **kwds):
        '''
        Make a new instance of AggregateDemandEconomy by filling in attributes
        specific to this kind of market.
        '''
        agents = agents if agents is not None else list()

        Market.__init__(self, agents=agents,
                        sow_vars=['Cratio', 'AggDemandFac', 'AggDemandFacPrev','EconomyMrkv'],
                        reap_vars=['cLvl_splurge'],
                        track_vars=['Cratio','CratioPrev', 'AggDemandFac', 'AggDemandFacPrev','EconomyMrkv'],
                        dyn_vars=['CFunc'],
                        **kwds)
        self.update()


    def mill_rule(self, cLvl_splurge):
        if self.Shk_idx==0:
            EconomyMrkvNow = 0
        else:
            EconomyMrkvNow = self.EconomyMrkvNow_hist[self.Shk_idx-1]   
        EconomyMrkvNext = self.EconomyMrkvNow_hist[self.Shk_idx]
        if hasattr(self,'base_AggCons'):
            # Edu-share-respecting aggregation (matches the final-aggregation path).
            # Under standard config (no AgentCount override), per-type factors are 1.0
            # so AggCons is unchanged. Under override, rescales per-type so Cratio
            # matches the population-respecting baseline.
            # See plans/20260506-1640h_edu_share_aggregation_correction.md.
            import os as _os_aggsh_mr
            _agg_mode_mr = _os_aggsh_mr.environ.get('HAFISCAL_AGGREGATE_BY_EDU_SHARE', 'auto').lower()
            _has_co_mr = any(
                _os_aggsh_mr.environ.get(v, '').strip() != ''
                for v in ('HAFISCAL_AGENTCOUNT_D', 'HAFISCAL_AGENTCOUNT_H', 'HAFISCAL_AGENTCOUNT_C')
            )
            if _agg_mode_mr in ('on', '1', 'true') or (_agg_mode_mr == 'auto' and _has_co_mr):
                AggCons = sum(
                    float(np.sum(this_cLvl)) * getattr(a, 'pop_rescale_factor', 1.0)
                    for this_cLvl, a in zip(cLvl_splurge, self.agents)
                )
            else:
                cLvl_all_splurge = np.concatenate([this_cLvl for this_cLvl in cLvl_splurge])
                AggCons = float(np.sum(cLvl_all_splurge))
            self.Cratio = AggCons/self.base_AggCons[self.Shk_idx]
            CratioNext = self.CFunc[EconomyMrkvNow*self.num_base_MrkvStates][EconomyMrkvNext*self.num_base_MrkvStates](self.Cratio)
        else:
            #self.CratioNow = 1.0
            self.sow_state['Cratio'] = 1.0
            CratioNext = 1.0
        self.AggDemandFacPrev = self.sow_state['AggDemandFac']
        self.CratioPrev = self.sow_state['Cratio']
        # AD-timing: which period's RecState determines ADF for period t+1?
        # See BUGS_private/HAFiscal_BUG-030_mill_rule_RecState_timing.md
        ad_timing = getattr(self, 'ad_timing', 'lagged')
        if ad_timing == 'contemporaneous':
            # Period t+1's macro state → period t+1's ADF (no lag)
            if self.Shk_idx + 1 < len(self.EconomyMrkvNow_hist):
                RecState = self.EconomyMrkvNow_hist[self.Shk_idx + 1] % 2 == 1
            else:
                RecState = EconomyMrkvNext % 2 == 1
        else:
            # 'lagged' (default, matches HAFiscal-QE published results):
            # Period t's macro state → period t+1's ADF (one-period lag)
            RecState = EconomyMrkvNext % 2 == 1
        AggDemandFacNext = self.ADFunc(CratioNext, RecState)
        mill_return = Model()
        mill_return.parameters[0] = CratioNext
        mill_return.parameters[1] = AggDemandFacNext
        mill_return.parameters[2] = self.AggDemandFacPrev
        mill_return.parameters[3] = EconomyMrkvNext
        self.Shk_idx += 1
        return mill_return.parameters

    def calc_dynamics(self):
        return self.calc_c_func()

    def update(self):
        '''
        '''
        self.sow_init['Cratio'] = 1.0
        self.sow_init['AggDemandFac'] = 1.0
        self.sow_init['AggDemandFacPrev'] = 1.0
        self.sow_init['EconomyMrkv'] = self.EconomyMrkvNow_init
        # See math-derive-appendix (AD-factor): ADF = C^(RecState * ADelasticity)
        # Picklable class (was: lambda) so agents carrying this attribute
        # can be pickled through spawn-context workers in _parallel_agg_solve.
        self.ADFunc = _ADFuncImpl(self.ADelasticity)
        self.EconomyMrkvNow_hist = [0] * self.act_T
        StateCount = self.MrkvArray[0].shape[0]
        CFunc_all = []
        for i in range(StateCount):
            CFunc_i = []
            for j in range(StateCount):
                CFunc_i.append(CRule(self.intercept_prev[i,j], self.slope_prev[i,j]))
            CFunc_all.append(copy(CFunc_i))
        self.CFunc = CFunc_all
        for agent in self.agents:
            agent.get_economy_data(self)

    def reset(self):
        self.Shk_idx = 0
        Market.reset(self)
        #self.EconomyMrkvNow_hist = [0] * self.act_T
        for agent in self.agents:
            agent.initialize_sim()
        
    def run_experiment(self, shock_type = "recession", UpdatePrb = 1.0, Splurge = 0.0, EconomyMrkv_init = [0], Full_Output = True):
        # matched-pair: refuse to simulate a solution solved under the other PermGroFac regime
        assert_regime(self, "run_experiment")
        # Make the macro markov history
        self.EconomyMrkvNow_hist = [0] * self.act_T
        self.EconomyMrkvNow_hist[0:len(EconomyMrkv_init)] = EconomyMrkv_init
    
        self.sow_init['CratioNow'] = self.CFunc[0][EconomyMrkv_init[0]*self.num_base_MrkvStates].intercept
        RecState = EconomyMrkv_init[0] % 2 == 1
        self.sow_init['AggDemandFac'] = self.ADFunc(self.sow_init['CratioNow'],RecState)
        
        # Make dictionaries of parameters to give to the agents
        experiment_dict = {
                'use_prestate' : True,
                'shock_type' : shock_type,
                'UpdatePrb' : UpdatePrb
                }
          
        # Begin the experiment by resetting each type's state to the baseline values
        PopCount = 0
        for ThisType in self.agents:
            ThisType.read_shocks = True
            ThisType.assign_parameters(**experiment_dict)
            ThisType.update_mrkv_array(shock_type)
            ThisType.solve_if_changed()
            ThisType.initialize_sim()
            ThisType.EconomyMrkvNow_hist = self.EconomyMrkvNow_hist
            if getattr(ThisType, 'mc_shuffle', False):
                ThisType._hit_with_recession_shock_shuffled(shock_type)
            else:
                ThisType.hit_with_recession_shock(shock_type)
            PopCount += ThisType.AgentCount
        self.make_history()
        
        
           
        # Extract simulated consumption, labor income, and weight data
        cNrm_all    = np.concatenate([ThisType.history['cNrm'] for ThisType in self.agents], axis=1)
        Mrkv_hist   = np.concatenate([ThisType.shock_history['Mrkv'] for ThisType in self.agents], axis=1)
        pLvl_all    = np.concatenate([ThisType.history['pLvl'] for ThisType in self.agents], axis=1)
        TranShk_all = np.concatenate([ThisType.shock_history['TranShk'] for ThisType in self.agents], axis=1)
        mNrm_all    = np.concatenate([ThisType.history['mNrm'] for ThisType in self.agents], axis=1)
        aNrm_all    = np.concatenate([ThisType.history['aNrm'] for ThisType in self.agents], axis=1)
        cLvl_all    = np.concatenate([ThisType.history['cLvl'] for ThisType in self.agents], axis=1)
        cLvl_all_splurge = np.concatenate([ThisType.history['cLvl_splurge'] for ThisType in self.agents], axis=1)

        # Per-agent population-rescale factors for edu-share-respecting aggregation.
        # Under standard config (no HAFISCAL_AGENTCOUNT_* override), all factors = 1.0
        # so this is a no-op. Under cohort-N override, rescales each cohort's
        # contribution so the population total respects data_EducShares.
        # See plans/20260506-1640h_edu_share_aggregation_correction.md.
        import os as _os_aggsh
        _agg_mode = _os_aggsh.environ.get('HAFISCAL_AGGREGATE_BY_EDU_SHARE', 'auto').lower()
        _has_count_override = any(
            _os_aggsh.environ.get(v, '').strip() != ''
            for v in ('HAFISCAL_AGENTCOUNT_D', 'HAFISCAL_AGENTCOUNT_H', 'HAFISCAL_AGENTCOUNT_C')
        )
        if _agg_mode in ('on', '1', 'true') or (_agg_mode == 'auto' and _has_count_override):
            agent_weights = np.concatenate([
                np.full(ThisType.AgentCount, getattr(ThisType, 'pop_rescale_factor', 1.0))
                for ThisType in self.agents
            ])
        else:
            agent_weights = np.ones(cLvl_all_splurge.shape[1])

        IndIncome = pLvl_all*TranShk_all*np.array(self.history['AggDemandFacPrev'])[:,None]
        AggIncome = np.sum(IndIncome*agent_weights[None,:], 1)
        # See math-derive (MC-agg): AggCons = sum_i pop_weight_i * cLvl_splurge_i
        AggCons   = np.sum(cLvl_all_splurge*agent_weights[None,:], 1)
        
        # See math-derive (NPV-def): V = sum_t (1/R)^t * X_t
        def calculate_NPV(X,Periods,R):
            NPV_discount = np.zeros(Periods)
            for t in range(Periods):
                NPV_discount[t] = 1/(R**t)
            NPV = np.zeros(Periods)
            for t in range(Periods):
                NPV[t] = np.sum(X[0:t+1]*NPV_discount[0:t+1])    
            return NPV

        # calculate NPV
        NPV_AggIncome = calculate_NPV(AggIncome,self.act_T,ThisType.Rfree[0])
        NPV_AggCons   = calculate_NPV(AggCons,self.act_T,ThisType.Rfree[0])
        
        # calculate Cratio_hist
        if hasattr(self,'base_AggCons'):
            Cratio_hist = np.divide(AggCons,self.base_AggCons)
        else:
            Cratio_hist = np.divide(AggCons,AggCons)
        
                
        # Get initial Markov states
        Mrkv_init = np.concatenate([ThisType.shock_history['Mrkv'][0,:] for ThisType in self.agents])
        
        has_Q = hasattr(self.agents[0], 'history_Q') and 'cNrm' in getattr(self.agents[0], 'history_Q', {})
        if has_Q:
            cNrm_Q_all = np.concatenate([a.history_Q['cNrm'] for a in self.agents], axis=1)
            pLvl_Q_all = np.concatenate([a.history_Q['pLvl'] for a in self.agents], axis=1)
            splurge_Q_all = np.concatenate([a.history_Q['cLvl_splurge'] for a in self.agents], axis=1)
            AggCons_Q_nrm = np.sum(splurge_Q_all / pLvl_Q_all, axis=1)
            E_pLvl = np.mean(pLvl_all, axis=1)
            AggCons_Q = AggCons_Q_nrm * E_pLvl

        if Full_Output==True:
            return_dict = {'cNrm_all' :     cNrm_all,
                           'TranShk_all' :  TranShk_all,
                           'cLvl_all' :     cLvl_all,
                           'pLvl_all' :     pLvl_all,
                           'Mrkv_hist' :    Mrkv_hist,
                           'Mrkv_init' :    Mrkv_init,
                           'mNrm_all' :     mNrm_all,
                           'aNrm_all' :     aNrm_all,
                           'cLvl_all_splurge' : cLvl_all_splurge,
                           'NPV_AggIncome': NPV_AggIncome,
                           'NPV_AggCons':   NPV_AggCons,
                           'AggIncome':     AggIncome,
                           'AggCons':       AggCons,
                           'Cratio_hist' :  Cratio_hist}
        elif Full_Output=='ForWelfare':
            # Also gather PermShk panel for JAX-MC bit-comparable validation.
            # PermShk and who_dies live in `shock_history`, not `history`.
            try:
                PermShk_all = np.concatenate([ThisType.shock_history.get('PermShk', np.zeros_like(ThisType.history['pLvl']))
                                              for ThisType in self.agents], axis=1)
            except Exception:
                PermShk_all = np.zeros_like(pLvl_all)
            try:
                who_dies_all = np.concatenate([ThisType.shock_history.get('who_dies', np.zeros((pLvl_all.shape[0], ThisType.AgentCount), dtype=bool))
                                              for ThisType in self.agents], axis=1)
            except Exception:
                who_dies_all = np.zeros_like(pLvl_all, dtype=bool)
            return_dict = {'cLvl_all_splurge' : cLvl_all_splurge,
                           'pLvl_all' :        pLvl_all,
                           'aNrm_all' :        aNrm_all,
                           'TranShk_all' :     TranShk_all,
                           'PermShk_all' :     PermShk_all,
                           'who_dies_all' :    who_dies_all,
                           'Mrkv_hist' :       Mrkv_hist,
                           'NPV_AggIncome': NPV_AggIncome,
                           'NPV_AggCons':   NPV_AggCons,
                           'AggIncome':     AggIncome,
                           'AggCons':       AggCons,
                           'Cratio_hist' :  Cratio_hist}
        else:
            return_dict = {'NPV_AggIncome': NPV_AggIncome,
                           'NPV_AggCons':   NPV_AggCons,
                           'AggIncome':     AggIncome,
                           'AggCons':       AggCons,
                           'Cratio_hist':   Cratio_hist}

        if has_Q:
            return_dict['AggCons_Q'] = AggCons_Q
            NPV_AggCons_Q = calculate_NPV(AggCons_Q, self.act_T, ThisType.Rfree[0])
            return_dict['NPV_AggCons_Q'] = NPV_AggCons_Q

        return return_dict

    def calc_CFunc(self):
        StateCount = self.MrkvArray[0].shape[0]
        CFunc_all = []
        for i in range(StateCount):
            CFunc_i = []
            for j in range(StateCount):
                CFunc_i.append(CRule(self.intercept_prev[i,j], self.slope_prev[i,j]))
            CFunc_all.append(copy(CFunc_i))
        self.CFunc = CFunc_all
        
    def switch_to_counterfactual_mode(self, shock_type):
        '''
        Very small method that swaps in the "big" Markov-state versions of some
        solution attributes, replacing the "small" two-state versions that are used
        only to generate the pre-recession initial distbution of state variables.
        It then prepares this type to create alternate shock histories so it can
        run counterfactual experiments.
        '''       
        # Adjust simulation parameters for the counterfactual experiments
        self.switch_shock_type(shock_type)
        self.act_T = T_sim
        for agent in self.agents:
            agent.get_economy_data(self)
            agent.switch_to_counterfactual_mode(shock_type)
            
    def switch_shock_type(self, shock_type):
        if shock_type == "base":
            self.MrkvArray = self.MrkvArray_base
        elif shock_type == "recession":
            self.MrkvArray = self.MrkvArray_recession
        elif shock_type == "recessionUI" or shock_type == "UI":
            self.MrkvArray = self.MrkvArray_recessionUI
        elif shock_type == "recessionTaxCut" or shock_type == "TaxCut":
            self.MrkvArray = self.MrkvArray_recessionTaxCut
        elif shock_type == "recessionCheck" or shock_type == "Check":
            self.MrkvArray = self.MrkvArray_recessionCheck
        num_mrkv_states = self.MrkvArray[0].shape[0]
        self.intercept_prev = np.ones((num_mrkv_states,num_mrkv_states ))
        self.slope_prev    = np.zeros((num_mrkv_states,num_mrkv_states ))
        self.calc_CFunc()
        for agent in self.agents:
            agent.switch_shock_type(shock_type)
            agent.get_economy_data(self)
            
    def save_state(self):
        for agent in self.agents:
            agent.save_state()
            
    def store_baseline(self, AggCons):
        self.base_AggCons = copy(AggCons)
        self.stored_solutions = dict()
        self.store_ADsolution('baseline')
            
    def store_ADsolution(self, name):
        self.stored_solutions[name] = Model()
        stamp_regime(self.stored_solutions[name])  # matched-pair: tag the stored solution's regime
        self.stored_solutions[name].CFunc = copy(self.CFunc)
        self.stored_solutions[name].ADelasticity = self.ADelasticity
        self.stored_solutions[name].agent_solutions = []
        for i in range(len(self.agents)):
            self.stored_solutions[name].agent_solutions.append(copy(self.agents[i].solution))
                       
    def restore_ADsolution(self,name):
        # matched-pair: a stored solution from the OTHER PermGroFac regime must not be
        # restored + simulated under this regime's betas.
        assert_regime(self.stored_solutions[name], "restore_ADsolution")
        self.CFunc = self.stored_solutions[name].CFunc
        self.ADelasticity = self.stored_solutions[name].ADelasticity
        # Refresh ADFunc so it captures the restored ADelasticity. The
        # class-based ADFunc (was: lambda) captures the value at creation;
        # without this refresh, agents would carry a stale ADelasticity.
        # (Pre-spawn lambda used closure over self.ADelasticity and re-read
        # at call time, so no explicit refresh was needed.)
        self.ADFunc = _ADFuncImpl(self.ADelasticity)
        for i in range(len(self.agents)):
            self.agents[i].solution = self.stored_solutions[name].agent_solutions[i]
            self.agents[i].get_economy_data(self)
        
    def make_idiosyncratic_shock_histories(self):
        for agent in self.agents:
            agent.make_idiosyncratic_shock_histories()
            
    def solve(self, warm_start=True):
        """Solve all agents. When warm_start=True, use previous converged solution
        as starting point for HARK's infinite-horizon convergence loop, dramatically
        reducing iterations (from ~5-15 to ~1-2 per agent).

        With HAFISCAL_USE_JAX_2B=1, replaces HARK's `solve_agent` iter loop
        entirely with the JAX `lax.while_loop` per-agent solve
        (jax_solver_iterated_drop_in.solve_to_convergence_consumer_solution).
        Warm-start handling and per-cohort iteration are unchanged."""
        import os as _os
        use_2b = _os.environ.get('HAFISCAL_USE_JAX_2B', '').lower() in ('1', 'on', 'true')
        use_2b_vmap = _os.environ.get('HAFISCAL_USE_JAX_2B_VMAP', '').lower() in ('1', 'on', 'true')
        stamp_regime(self)  # matched-pair: record the PermGroFac regime this solve runs under
        if use_2b or use_2b_vmap:
            # BUG-047 matched-pair guard: the JAX-2B EGM kernel applies
            # PermGroFac^(-CRRA) UNCONDITIONALLY (no FIX=0 branch), so using it
            # under FIX=0 (legacy) silently mismatches the HARK solver ~5% — the
            # same silent-matched-pair hazard class as BUG-051. Refuse it.
            if not permgrofac_fix_on():
                raise RuntimeError(
                    "HAFISCAL_USE_JAX_2B requires HAFISCAL_PERMGROFAC_FIX=1: the "
                    "JAX-2B kernel has no legacy (FIX=0) branch and would silently "
                    "mismatch HARK. Set HAFISCAL_USE_JAX_2B=0 for a FIX=0 (legacy) run.")
            import sys as _sys
            _hafiscal_jax = _os.path.abspath(_os.path.join(
                _os.path.dirname(__file__), '..', 'jax_mc_speedup'))
            if _hafiscal_jax not in _sys.path:
                _sys.path.insert(0, _hafiscal_jax)
            _verbose = _os.environ.get('HAFISCAL_USE_JAX_2B_VERBOSE', '').lower() in ('1', 'on', 'true')

            # Gather warm-start solutions per cohort (None if not available)
            from_solutions = []
            for agent in self.agents:
                from_solution = None
                if warm_start and hasattr(agent, 'solution') and len(agent.solution) > 0:
                    prev_sol = agent.solution[0]
                    current_states = agent.MrkvArray[0].shape[0]
                    prev_states = len(prev_sol.vPfunc) if hasattr(prev_sol, 'vPfunc') else 0
                    if prev_states == current_states:
                        from_solution = prev_sol
                from_solutions.append(from_solution)

            if use_2b_vmap:
                from jax_solver_iterated_multicohort import (
                    solve_all_cohorts_to_convergence_consumer_solutions)
                # pre_solve FIRST so agent.solution_terminal is sized for
                # the current state space; THEN resolve warm-start fallbacks.
                for agent in self.agents:
                    agent.pre_solve()
                # Resolve None -> agent.solution_terminal (vmap needs all
                # cohorts to have a starting belief of the same shape)
                from_sols_resolved = [
                    s if s is not None else agent.solution_terminal
                    for s, agent in zip(from_solutions, self.agents)
                ]
                _chunk = _os.environ.get('HAFISCAL_USE_JAX_2B_VMAP_CHUNK', '')
                chunk_size = int(_chunk) if _chunk.isdigit() else None
                per_cohort_sols = solve_all_cohorts_to_convergence_consumer_solutions(
                    self.agents, max_iters=500, tol=1e-7,
                    from_solutions=from_sols_resolved,
                    verbose=_verbose, chunk_size=chunk_size)
                for agent, sol_list in zip(self.agents, per_cohort_sols):
                    agent.solution = sol_list
                    agent.post_solve()
                return

            # Serial 2B path — optionally parallelized via ThreadPoolExecutor
            # when HAFISCAL_USE_JAX_2B_THREADS > 1. JAX kernel calls release the
            # GIL during dispatch + compute, so threads run truly in parallel
            # (vs processes, threads share JAX runtime + JIT cache + memory).
            # At Baseline this can give ~1.5-2x on the solve step.
            from jax_solver_iterated_drop_in import solve_to_convergence_consumer_solution
            n_threads = int(_os.environ.get('HAFISCAL_USE_JAX_2B_THREADS', '1'))
            if n_threads > 1:
                from concurrent.futures import ThreadPoolExecutor

                def _solve_one(agent_and_from):
                    agent, from_solution = agent_and_from
                    agent.pre_solve()
                    sol = solve_to_convergence_consumer_solution(
                        agent, from_solution=from_solution,
                        max_iters=500, tol=1e-7, verbose=_verbose)
                    agent.solution = sol
                    agent.post_solve()

                with ThreadPoolExecutor(max_workers=n_threads) as ex:
                    list(ex.map(_solve_one,
                                zip(self.agents, from_solutions)))
            else:
                for agent, from_solution in zip(self.agents, from_solutions):
                    agent.pre_solve()
                    agent.solution = solve_to_convergence_consumer_solution(
                        agent, from_solution=from_solution, max_iters=500, tol=1e-7,
                        verbose=_verbose)
                    agent.post_solve()
            return

        from HARK.core import solve_agent
        for agent in self.agents:
            from_solution = None
            if warm_start and hasattr(agent, 'solution') and len(agent.solution) > 0:
                prev_sol = agent.solution[0]
                current_states = agent.MrkvArray[0].shape[0]
                prev_states = len(prev_sol.vPfunc) if hasattr(prev_sol, 'vPfunc') else 0
                if prev_states == current_states:
                    from_solution = prev_sol
            agent.pre_solve()
            agent.solution = solve_agent(agent, False, from_solution=from_solution)
            agent.post_solve()
            
    def Macro_2_Micro_CFunc(self, MacroCFunc):
        '''
        Converts the aggregate CFunc for Macro transitions to one for micro transitions
        '''
        dim = len(MacroCFunc)
        MicroCFunc = [[CRule(1.0,0.0) for i in range(dim*self.num_base_MrkvStates)] for j in range(dim*self.num_base_MrkvStates)]
        for i in range(dim*self.num_base_MrkvStates):
            for j in range(dim*self.num_base_MrkvStates):
                MicroCFunc[i][j] = MacroCFunc[int(np.floor(i/self.num_base_MrkvStates))][int(np.floor(j/self.num_base_MrkvStates))]
        return MicroCFunc
    
    def Compare_CFunc_Convergence(self,Old_Cfunc,New_Cfunc):
        dim=len(Old_Cfunc)
        DiffSlopes      = np.zeros((dim,dim))
        DiffIntercepts  = np.zeros((dim,dim))
        for i in range(dim):
            for j in range(dim):
                DiffSlopes[i,j]     = abs(New_Cfunc[i][j].slope - Old_Cfunc[i][j].slope)
                DiffIntercepts[i,j] = abs(New_Cfunc[i][j].intercept - Old_Cfunc[i][j].intercept)
        Slopes_Diff                         = np.linalg.norm(DiffSlopes)
        [i,j]                               = np.unravel_index(DiffSlopes.argmax(),DiffSlopes.shape)
        FromMrkState_Slopes_Largest_Diff    = int(np.floor(i/self.num_base_MrkvStates))
        ToMrkState_Slopes_Largest_Diff      = int(np.floor(j/self.num_base_MrkvStates))
        
        Intercept_Diff                      = np.linalg.norm(DiffIntercepts)
        [i,j]                               = np.unravel_index(DiffIntercepts.argmax(),DiffIntercepts.shape)
        FromMrkState_Intercept_Largest_Diff = int(np.floor(i/self.num_base_MrkvStates))
        ToMrkState_Intercept_Largest_Diff   = int(np.floor(j/self.num_base_MrkvStates))
        
        Total_Diff          = (Slopes_Diff**2 + Intercept_Diff**2)**0.5
        # print('Diff in Slopes in CFunc: ', Slopes_Diff)
        # print('Largest diff', np.max(DiffSlopes))
        # print('Slope: Largest Diff from Mrk State: ', FromMrkState_Slopes_Largest_Diff)
        # print('Slope: Largest Diff to Mrk State: ', ToMrkState_Slopes_Largest_Diff)
        
        # print('Diff in Intercepts in CFunc: ', Intercept_Diff) 
        # print('Largest diff', np.max(DiffIntercepts))
        # print('Intercept: Largest Diff from Mrk State: ', FromMrkState_Intercept_Largest_Diff)
        # print('Intercept: Largest Diff to Mrk State: ', ToMrkState_Intercept_Largest_Diff)
        print('Total Diff in CFunc: ', Total_Diff)
        return Total_Diff
    
    def solve_ad_recession(self, num_max_iterations, convergence_cutoff=1E-3, name = None, shock_type = "recession"):
        #reset Cfunc
        progress(f"Starting AD solve for {shock_type}, max {num_max_iterations} iterations")
        _ad_solve_start = _time_module.time()
        
        dim = len(self.CFunc)
        self.CFunc = [[CRule(1.0,0.0) for i in range(dim)] for j in range(dim)]
        for agent in self.agents:
            agent.CFunc = self.CFunc
        print("Presolving")
        _presolve_start = _time_module.time()
        self.solve()
        profiler.record_time(f"AD_presolve_{shock_type}", _time_module.time() - _presolve_start)
                
        self.ADelasticity = self.demand_ADelasticity
        self.update()    
        recession_dict = {
             'shock_type' : shock_type,
             'UpdatePrb': 1.0,
             'Splurge': 0.32,
             }
        dim = int(len(self.CFunc)/self.num_base_MrkvStates)
        MacroCFunc = [[CRule(1.0,0.0) for i in range(dim)] for j in range(dim)]  
        
        _converged = False
        for i in range(num_max_iterations):
            _iter_start = _time_module.time()
            print("Iteration ", i+1,":")
            progress(f"AD iteration {i+1}/{num_max_iterations} for {shock_type}")
            
            recession_dict['EconomyMrkv_init'] = list(np.arange(1,self.num_experiment_periods+1)*2+1) + [1]*12 + [0]*20
            
            _exp_start = _time_module.time()
            recession_results = self.run_experiment(**recession_dict)
            profiler.record_time(f"AD_iter_{shock_type}_experiment", _time_module.time() - _exp_start)
                
            #Debugging
            # T_plot = 35
            # plt.plot(recession_results['Cratio_hist'][0:T_plot]) 
            # plt.pause(1)
            # plt.show()
            
            MacroCFunc[0][3] = CRule(recession_results['Cratio_hist'][0],0.0)
            for j in range(self.num_experiment_periods-1):
                MacroCFunc[2*j+3][2*j+5] = CRule(recession_results['Cratio_hist'][j+1],0.0)
            MacroCFunc[2*self.num_experiment_periods+1][1] = CRule(recession_results['Cratio_hist'][self.num_experiment_periods],0.0)
            MacroCFunc[1][1] = CRule(np.mean(recession_results['Cratio_hist'][self.num_experiment_periods+1:self.num_experiment_periods+10]),0.0)
            
            self.MacroCFunc = MacroCFunc
            Old_Cfunc  = self.CFunc
            New_Cfunc  = self.Macro_2_Micro_CFunc(MacroCFunc)
            
            step = self.Cfunc_iter_stepsize 
            dim = int(len(self.CFunc))
            Step_Cfunc = [[CRule(1.0,0.0) for i in range(dim)] for j in range(dim)]
            for ii in range(dim):
                for jj in range(dim):
                    Step_Cfunc[ii][jj].slope      = Old_Cfunc[ii][jj].slope     + step*(New_Cfunc[ii][jj].slope-Old_Cfunc[ii][jj].slope)
                    Step_Cfunc[ii][jj].intercept  = Old_Cfunc[ii][jj].intercept + step*(New_Cfunc[ii][jj].intercept-Old_Cfunc[ii][jj].intercept)
                    
            self.CFunc = Step_Cfunc
            for agent in self.agents:
                agent.CFunc = self.CFunc
            print("solving again...")
            _solve_start = _time_module.time()
            self.solve()
            profiler.record_time(f"AD_iter_{shock_type}_solve", _time_module.time() - _solve_start)
            
            
            Total_Diff = self.Compare_CFunc_Convergence(Old_Cfunc,self.CFunc)
            
            # Log iteration timing and convergence
            _iter_time = _time_module.time() - _iter_start
            profiler.record_time(f"AD_iteration_{shock_type}", _iter_time, f"iter={i+1}")
            profiler.log_convergence(i+1, f"CFunc_diff_{shock_type}", Total_Diff, convergence_cutoff)

            if Total_Diff < convergence_cutoff:
                print("Convergence criterion reached.")
                _converged = True
                break
            else:                    
                print("Convergence criterion not reached.")
        
        _total_ad_time = _time_module.time() - _ad_solve_start
        progress(f"AD solve for {shock_type} complete: {i+1} iterations, {_total_ad_time/60:.1f} min, converged={_converged}")
        profiler.record_time(f"AD_solve_total_{shock_type}", _total_ad_time, 
                             f"iters={i+1}, converged={_converged}")
                
        if name != None:
            self.store_ADsolution(name)
            
            
    def solve_ad_check_recession(self, num_max_iterations, convergence_cutoff=1E-3, name = None):
        self.solve_ad_recession(num_max_iterations, convergence_cutoff, name = name, shock_type = "recessionCheck")   
    
    def solve_ad_ui_extension_recession(self, num_max_iterations, convergence_cutoff=1E-3, name = None):
        self.solve_ad_recession(num_max_iterations, convergence_cutoff, name = name, shock_type = "recessionUI")       
                        
    def solve_ad_recession_taxcut(self, num_max_iterations, convergence_cutoff=1E-3, name = None):
        self.solve_ad_recession(num_max_iterations, convergence_cutoff, name = name, shock_type = "recessionTaxCut")
            
            

class CRule(Model):
    '''
    A class to represent agent beliefs about aggregate consumption dynamics.
    '''
    def __init__(self, intercept, slope):
        self.intercept = intercept
        self.slope = slope
        self.distance_criteria = ['slope', 'intercept']

    def __call__(self, Cnow):
        #Cnext = np.exp(self.intercept + self.slope*np.log(Cnow))
        Cnext = self.intercept + self.slope*(Cnow-1.0)        # Not logs!
        return Cnext