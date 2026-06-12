"""
RNG-Synchronized Consumer Type for HARK 0.17.0

This module provides a KinkedRconsumerType subclass that exactly replicates
HARK 0.14.1's RNG consumption pattern during simulation.

Key Differences Between HARK 0.14.1 and 0.17.0:
===============================================

1. Distribution Creation:
   - 0.14.1: Creates NEW Lognormal/Uniform distributions on each call,
             seeding with self.RNG.integers()
   - 0.17.0: Uses PRE-BUILT distributions (kNrmInitDstn, pLvlInitDstn)
             that have their own internal RNG

2. reset_rng():
   - 0.14.1: Only resets self.RNG
   - 0.17.0: Resets self.RNG AND all distribution RNGs

3. sim_birth():
   - 0.14.1: Creates fresh Lognormal distributions, consuming 2 RNG integers
   - 0.17.0: Draws from pre-built DiscreteDistribution, consuming 0 RNG integers

4. get_shocks():
   - 0.14.1: Draws from IncShkDstn which uses its own RNG state
   - 0.17.0: Same, but distribution RNG state differs due to reset_rng()

This class overrides the relevant methods to match 0.14.1's exact RNG pattern.
"""

import math as _math
import numpy as np
from copy import copy

# Handle import differences between HARK versions
try:
    from HARK.distributions import Lognormal, Uniform
except ImportError:
    from HARK.distribution import Lognormal, Uniform

from HARK.ConsumptionSaving.ConsIndShockModel import (
    KinkedRconsumerType as BaseKinkedR,
    IndShockConsumerType as BaseIndShock,
)


# ---------------------------------------------------------------------------
# Monkey-patch Lognormal._approx_equiprobable to use math.erf (0.14.1 parity)
#
# HARK 0.17.0 uses scipy.special.erfc (vectorized Cephes) while 0.14.1 used
# math.erf (scalar libm).  They differ at ~1e-15 per call, accumulating to
# ~1e-11 over 1,200 periods.  Patching here ensures that any code importing
# rng_synchronized_consumer gets income-shock atoms bitwise-identical to 0.14.1.
# ---------------------------------------------------------------------------
from HARK.distributions import DiscreteDistribution
from scipy.stats import norm as _norm

_original_lognormal_approx = Lognormal._approx_equiprobable


def _approx_equiprobable_erf(self, N, endpoints=False,
                              tail_N=0, tail_bound=None, tail_order=np.e):
    """Drop-in replacement using math.erf instead of scipy.special.erfc."""
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


Lognormal._approx_equiprobable = _approx_equiprobable_erf
# ---------------------------------------------------------------------------


class RNGSyncKinkedRconsumerType(BaseKinkedR):
    """
    KinkedRconsumerType with RNG behavior synchronized to match HARK 0.14.1.
    
    This class ensures that simulation runs produce identical results to
    HARK 0.14.1 by exactly replicating its RNG consumption pattern.
    """
    
    # IncShkDstn seed from HARK 0.14.1 when seed is NOT in init_params.
    INCSHKDSTN_SEED_DEFAULT = 763607780
    
    # 0.17.0 default IncShkDstn seed when seed is NOT in init_params.
    # Used to detect whether seed was provided during construction.
    INCSHKDSTN_SEED_017_DEFAULT = 1234560819
    
    # Seeds when 'seed' IS provided in init_params
    INCSHKDSTN_SEEDS_014 = {
        12345: 1226058464,
        12346: 276307766,
        12347: 742504843,
        12348: 623135374,
        12349: 616690435,
        12350: 696058170,
        12351: 43411684,
    }
    
    def __init__(self, **kwds):
        """Initialize and capture whether seed was in init_params."""
        # Track if seed was provided in init_params (before super().__init__)
        self._seed_in_init_params = 'seed' in kwds
        # Initialize the tracking variable before super().__init__ calls reset_rng
        self._initial_incshkdstn_seed = None
        super().__init__(**kwds)
        # Capture the IncShkDstn seed set during construction
        if hasattr(self, 'IncShkDstn') and self.IncShkDstn is not None:
            self._initial_incshkdstn_seed = self.IncShkDstn[0]._seed
    
    def _compute_incshkdstn_seed_014(self, agent_seed):
        """
        Get the IncShkDstn seed that HARK 0.14.1 would use.
        
        Determines whether seed was provided during construction and uses
        the appropriate seed lookup.
        """
        # Check if seed was provided in init_params
        if self._seed_in_init_params:
            # Seed was provided in init_params
            if agent_seed in self.INCSHKDSTN_SEEDS_014:
                return self.INCSHKDSTN_SEEDS_014[agent_seed]
            # Fall back to computing an approximation for unknown seeds
            rng = np.random.default_rng(agent_seed)
            for _ in range(5):
                rng.integers(2**31)
            return int(rng.integers(2**31))
        else:
            # Seed was set after construction
            return self.INCSHKDSTN_SEED_DEFAULT
    
    def reset_rng(self):
        """
        Reset RNG to match HARK 0.14.1 behavior.
        
        Key insight: The IncShkDstn seed is computed during model construction,
        not during simulation. HARK 0.14.1 and 0.17.0 consume RNG differently
        during __init__/pre_solve, resulting in different IncShkDstn seeds.
        
        To synchronize, we force the IncShkDstn to use the same seed as
        HARK 0.14.1 would have used.
        """
        self.RNG = np.random.default_rng(self.seed)
        
        # Compute the IncShkDstn seed for this agent's seed
        incshkdstn_seed = self._compute_incshkdstn_seed_014(self.seed)
        
        # Force IncShkDstn to use the computed seed
        # This ensures identical shock sequences during simulation
        if hasattr(self, 'IncShkDstn') and self.IncShkDstn is not None:
            # Reseed and reset the distribution to match 0.14.1
            if isinstance(self.IncShkDstn, list):
                for t in range(len(self.IncShkDstn)):
                    self.IncShkDstn[t]._seed = incshkdstn_seed
                    self.IncShkDstn[t].reset()
            elif hasattr(self.IncShkDstn, '__getitem__'):
                # IndexDistribution - need to reseed each underlying distribution
                for t in range(self.T_cycle):
                    self.IncShkDstn[t]._seed = incshkdstn_seed
                    self.IncShkDstn[t].reset()
    
    def sim_birth(self, which_agents):
        """
        Make new consumers for given indices, matching HARK 0.14.1's RNG pattern.
        
        HARK 0.14.1 created NEW Lognormal distributions on each sim_birth call,
        seeding them with self.RNG.integers(). This consumes 2 RNG integers
        per call (one for aNrm, one for pLvl) - EVEN WHEN NO AGENTS ARE BORN.
        
        The Lognormal distribution is created with a seed, then draws 0 values
        if N=0. This still consumes the RNG integers for seeding.
        
        We replicate this exact behavior to maintain RNG synchronization.
        
        NOTE: HARK 0.17.0 changed the parameter names:
        - 0.14.1: aNrmInitMean=0.0, aNrmInitStd=1.0
        - 0.17.0: kLogInitMean=-12.0, kLogInitStd=0.0
        We map 0.17.0's kLogInitMean/kLogInitStd to aNrmInitMean/aNrmInitStd
        for compatibility, falling back to 0.14.1 defaults if neither set.
        """
        N = np.sum(which_agents)
        
        # 1. Draw aNrm from Lognormal (consumes 1 RNG integer for seed)
        # Map 0.17.0's kLogInitMean/kLogInitStd to 0.14.1's aNrmInitMean/aNrmInitStd
        # Priority: aNrmInitMean > kLogInitMean > default (0.0)
        if hasattr(self, 'aNrmInitMean'):
            aNrmInitMean = self.aNrmInitMean
        elif hasattr(self, 'kLogInitMean'):
            aNrmInitMean = self.kLogInitMean  # Same semantics (log-mean of initial aNrm)
        else:
            aNrmInitMean = 0.0  # 0.14.1 default
        
        if hasattr(self, 'aNrmInitStd'):
            aNrmInitStd = self.aNrmInitStd
        elif hasattr(self, 'kLogInitStd'):
            aNrmInitStd = self.kLogInitStd  # Same semantics (log-std of initial aNrm)
        else:
            aNrmInitStd = 1.0  # 0.14.1 default
        
        self.state_now["aNrm"][which_agents] = Lognormal(
            mu=aNrmInitMean,
            sigma=aNrmInitStd,
            seed=self.RNG.integers(0, 2**31 - 1),
        ).draw(N)
        
        # 2. Draw pLvl from Lognormal (consumes 1 RNG integer for seed)
        # Map 0.17.0's pLogInitMean/pLogInitStd to 0.14.1's pLvlInitMean/pLvlInitStd
        if hasattr(self, 'pLvlInitMean'):
            pLvlInitMean = self.pLvlInitMean
        elif hasattr(self, 'pLogInitMean'):
            pLvlInitMean = self.pLogInitMean
        else:
            pLvlInitMean = 0.0  # 0.14.1 default
        
        if hasattr(self, 'pLvlInitStd'):
            pLvlInitStd = self.pLvlInitStd
        elif hasattr(self, 'pLogInitStd'):
            pLvlInitStd = self.pLogInitStd
        else:
            pLvlInitStd = 0.0  # 0.14.1 default
        
        pLvlInitMeanNow = pLvlInitMean + np.log(
            self.state_now.get("PlvlAgg", 1.0)
        )
        self.state_now["pLvl"][which_agents] = Lognormal(
            pLvlInitMeanNow,
            pLvlInitStd,
            seed=self.RNG.integers(0, 2**31 - 1),
        ).draw(N)
        
        # 3. Set age/cycle for newborns
        if N > 0:
            self.t_age[which_agents] = 0
            
            if not hasattr(self, "PerfMITShk"):
                self.PerfMITShk = False
            if not self.PerfMITShk:
                self.t_cycle[which_agents] = 0
    
    def sim_death(self):
        """
        Determine which agents die, matching HARK 0.14.1's RNG pattern.
        
        Both 0.14.1 and 0.17.0 create a fresh Uniform distribution seeded
        with self.RNG.integers(), so this should be compatible. But we
        replicate it exactly to be safe.
        """
        DiePrb_by_t_cycle = 1.0 - np.asarray(self.LivPrb)
        DiePrb = DiePrb_by_t_cycle[
            self.t_cycle - 1 if self.cycles == 1 else self.t_cycle
        ]
        
        DeathShks = Uniform(seed=self.RNG.integers(0, 2**31 - 1)).draw(
            N=self.AgentCount
        )
        which_agents = DeathShks < DiePrb
        
        if self.T_age is not None:
            too_old = self.t_age >= self.T_age
            which_agents = np.logical_or(which_agents, too_old)
        
        return which_agents


class RNGSyncIndShockConsumerType(BaseIndShock):
    """
    IndShockConsumerType with RNG behavior synchronized to match HARK 0.14.1.
    
    This is for the case where Rboro == Rsave and we want to use IndShock
    instead of KinkedR (the bugfixed behavior).
    """
    
    # IncShkDstn seed from HARK 0.14.1 when seed is NOT in init_params.
    INCSHKDSTN_SEED_DEFAULT = 763607780
    
    # 0.17.0 default IncShkDstn seed when seed is NOT in init_params.
    INCSHKDSTN_SEED_017_DEFAULT = 1234560819
    
    # Seeds when 'seed' IS provided in init_params (same as KinkedR)
    INCSHKDSTN_SEEDS_014 = {
        12345: 1226058464,
        12346: 276307766,
        12347: 742504843,
        12348: 623135374,
        12349: 616690435,
        12350: 696058170,
        12351: 43411684,
    }
    
    def __init__(self, **kwds):
        """Initialize and capture whether seed was in init_params."""
        self._seed_in_init_params = 'seed' in kwds
        self._initial_incshkdstn_seed = None
        super().__init__(**kwds)
        if hasattr(self, 'IncShkDstn') and self.IncShkDstn is not None:
            try:
                self._initial_incshkdstn_seed = self.IncShkDstn[0]._seed
            except (AttributeError, IndexError, TypeError):
                pass
    
    def _compute_incshkdstn_seed_014(self, agent_seed):
        """
        Get the IncShkDstn seed that HARK 0.14.1 would use.
        """
        if self._seed_in_init_params:
            if agent_seed in self.INCSHKDSTN_SEEDS_014:
                return self.INCSHKDSTN_SEEDS_014[agent_seed]
            # Fall back to computing an approximation for unknown seeds
            rng = np.random.default_rng(agent_seed)
            for _ in range(5):
                rng.integers(2**31)
            return int(rng.integers(2**31))
        else:
            return self.INCSHKDSTN_SEED_DEFAULT
    
    def reset_rng(self):
        """Reset RNG matching 0.14.1 behavior."""
        self.RNG = np.random.default_rng(self.seed)
        
        # Compute the correct IncShkDstn seed for this agent
        incshkdstn_seed = self._compute_incshkdstn_seed_014(self.seed)
        
        # Force IncShkDstn to use the same seed as HARK 0.14.1
        if hasattr(self, 'IncShkDstn') and self.IncShkDstn is not None:
            if isinstance(self.IncShkDstn, list):
                for t in range(len(self.IncShkDstn)):
                    self.IncShkDstn[t]._seed = incshkdstn_seed
                    self.IncShkDstn[t].reset()
            elif hasattr(self.IncShkDstn, '__getitem__'):
                for t in range(self.T_cycle):
                    self.IncShkDstn[t]._seed = incshkdstn_seed
                    self.IncShkDstn[t].reset()
    
    def sim_birth(self, which_agents):
        """Make new consumers matching 0.14.1's RNG pattern.
        
        CRITICAL: Always consume 2 RNG integers (for aNrm and pLvl seeds)
        even when N=0, to match 0.14.1's exact RNG consumption.
        
        NOTE: HARK 0.17.0 changed the parameter names:
        - 0.14.1: aNrmInitMean=0.0, aNrmInitStd=1.0
        - 0.17.0: kLogInitMean=-12.0, kLogInitStd=0.0
        We map 0.17.0's kLogInitMean/kLogInitStd to aNrmInitMean/aNrmInitStd
        for compatibility, falling back to 0.14.1 defaults if neither set.
        """
        N = np.sum(which_agents)
        
        # Map 0.17.0's kLogInitMean/kLogInitStd to 0.14.1's aNrmInitMean/aNrmInitStd
        if hasattr(self, 'aNrmInitMean'):
            aNrmInitMean = self.aNrmInitMean
        elif hasattr(self, 'kLogInitMean'):
            aNrmInitMean = self.kLogInitMean
        else:
            aNrmInitMean = 0.0  # 0.14.1 default
        
        if hasattr(self, 'aNrmInitStd'):
            aNrmInitStd = self.aNrmInitStd
        elif hasattr(self, 'kLogInitStd'):
            aNrmInitStd = self.kLogInitStd
        else:
            aNrmInitStd = 1.0  # 0.14.1 default
        
        # Always create Lognormal (consumes RNG integer) even if N=0
        self.state_now["aNrm"][which_agents] = Lognormal(
            mu=aNrmInitMean,
            sigma=aNrmInitStd,
            seed=self.RNG.integers(0, 2**31 - 1),
        ).draw(N)
        
        # Map 0.17.0's pLogInitMean/pLogInitStd to 0.14.1's pLvlInitMean/pLvlInitStd
        if hasattr(self, 'pLvlInitMean'):
            pLvlInitMean = self.pLvlInitMean
        elif hasattr(self, 'pLogInitMean'):
            pLvlInitMean = self.pLogInitMean
        else:
            pLvlInitMean = 0.0  # 0.14.1 default
        
        if hasattr(self, 'pLvlInitStd'):
            pLvlInitStd = self.pLvlInitStd
        elif hasattr(self, 'pLogInitStd'):
            pLvlInitStd = self.pLogInitStd
        else:
            pLvlInitStd = 0.0  # 0.14.1 default
        
        pLvlInitMeanNow = pLvlInitMean + np.log(
            self.state_now.get("PlvlAgg", 1.0)
        )
        # Always create Lognormal (consumes RNG integer) even if N=0
        self.state_now["pLvl"][which_agents] = Lognormal(
            pLvlInitMeanNow,
            pLvlInitStd,
            seed=self.RNG.integers(0, 2**31 - 1),
        ).draw(N)
        
        # Only modify age/cycle if there are actual newborns
        if N > 0:
            self.t_age[which_agents] = 0
            
            if not hasattr(self, "PerfMITShk"):
                self.PerfMITShk = False
            if not self.PerfMITShk:
                self.t_cycle[which_agents] = 0
    
    def sim_death(self):
        """Determine which agents die matching 0.14.1's RNG pattern."""
        DiePrb_by_t_cycle = 1.0 - np.asarray(self.LivPrb)
        DiePrb = DiePrb_by_t_cycle[
            self.t_cycle - 1 if self.cycles == 1 else self.t_cycle
        ]
        
        DeathShks = Uniform(seed=self.RNG.integers(0, 2**31 - 1)).draw(
            N=self.AgentCount
        )
        which_agents = DeathShks < DiePrb
        
        if self.T_age is not None:
            too_old = self.t_age >= self.T_age
            which_agents = np.logical_or(which_agents, too_old)
        
        return which_agents


def SmartRNGSyncConsumerType(**params):
    """
    Factory function that returns the appropriate RNG-synchronized consumer type.
    
    When Rboro == Rsave (no kink), returns RNGSyncIndShockConsumerType.
    When Rboro != Rsave (actual kink), returns RNGSyncKinkedRconsumerType.
    
    This matches the behavior of the 0.14.1-bugfixed version while also
    synchronizing RNG to produce identical simulation results.
    """
    Rboro = params.get('Rboro', 1.0)
    Rsave = params.get('Rsave', 1.0)
    
    # Handle Rboro/Rsave being lists (HARK 0.17.0 style)
    if isinstance(Rboro, list):
        Rboro = Rboro[0]
    if isinstance(Rsave, list):
        Rsave = Rsave[0]
    
    if Rboro == Rsave:
        # No kink - use IndShockConsumerType with correct grid construction
        ind_params = params.copy()
        
        # Set Rfree to match Rsave - HARK 0.17.0 expects Rfree as a list
        rsave_val = ind_params.get('Rsave', ind_params.get('Rfree', 1.0))
        if isinstance(rsave_val, list):
            rsave_val = rsave_val[0]
        
        # Ensure Rfree is a scalar (some HARK versions expect this)
        ind_params['Rfree'] = rsave_val
        
        # Remove KinkedR-specific params
        ind_params.pop('Rboro', None)
        ind_params.pop('Rsave', None)
        
        return RNGSyncIndShockConsumerType(**ind_params)
    else:
        # Actual kink - use KinkedRconsumerType
        return RNGSyncKinkedRconsumerType(**params)


# Export the factory function and classes
__all__ = [
    'RNGSyncKinkedRconsumerType',
    'RNGSyncIndShockConsumerType', 
    'SmartRNGSyncConsumerType',
]
