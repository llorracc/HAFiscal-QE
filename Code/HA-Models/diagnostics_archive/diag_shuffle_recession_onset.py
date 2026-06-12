"""
Diagnostic: identify whether the recession-onset divergence between shuffle
and non-shuffle MC is in the spike code or the first transition step.

Strategy:
1. Build a minimal HAFiscal AggFiscalType with HS-only parameters
2. Initialize two instances with IDENTICAL seeds: one shuffle, one non-shuffle
3. Set identical pre-spike state (load from base.pkl t=10 = ergodic-warmed up)
4. Call hit_with_recession_shock (which: (a) applies urate spike, (b) sets
   macro to recession, (c) runs T_sim transitions and records shock_history)
5. Inspect:
   (a) The post-spike state (= what the loop sees at t=0 entry)
   (b) The post-1st-transition state (= shock_history['Mrkv'][0])
6. Compare per-state per-capita fractions

This pinpoints whether the bug is in the spike code or the first transition.

Usage:
    HAFISCAL_UI_STATE_ENCODING=bug_fix \\
    HAFISCAL_AGENTCOUNT_H=49000 \\
    HAFISCAL_URATE_NORMAL_H=0.045 \\
    python Code/HA-Models/FromPandemicCode/diag_shuffle_recession_onset.py
"""
import os, sys, copy, pickle
import numpy as np
from collections import Counter
from pathlib import Path

# Patch sys.argv for HAFiscal imports
sys.argv = ['diag', 'Baseline', 'TM', 'False', 'False', 'False']
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

# Force HS_Only and quota-friendly urate
os.environ['HAFISCAL_AGENTCOUNT_H'] = '49000'
os.environ['HAFISCAL_URATE_NORMAL_H'] = '0.045'
os.environ.setdefault('HAFISCAL_UI_STATE_ENCODING', 'bug_fix')

import Parameters
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy

print(f"[config] HAFISCAL_UI_STATE_ENCODING={os.environ.get('HAFISCAL_UI_STATE_ENCODING')}")
print(f"[config] HAFISCAL_AGENTCOUNT_H={os.environ.get('HAFISCAL_AGENTCOUNT_H')}")
print(f"[config] HAFISCAL_URATE_NORMAL_H={os.environ.get('HAFISCAL_URATE_NORMAL_H')}")
print()

def build_agent(shuffle):
    """Build minimal HAFiscal AggFiscalType for HS-only at urate H=0.045."""
    init_list = Parameters.return_parameters('HS_Only')
    init_d = init_list[0]  # HS only

    # Force the agent count for HS
    init_d['AgentCount'] = 49000

    agent = AggFiscalType(**init_d)
    agent.seed = 12345
    agent.RNG = np.random.RandomState(agent.seed)
    if shuffle:
        agent.mc_shuffle = True
        agent.income_shuffle = True
        agent.markov_shuffle = True

    return agent

def setup_economy(agent):
    """Wire up agent + economy for a given shock_type."""
    # Don't actually solve — we only need shock-history machinery
    return agent

def initialize_identical_pre_spike(agent):
    """Set the agent's pre-spike Mrkv state to a known controlled distribution."""
    # All employed at micro=0
    N = agent.AgentCount
    agent.shocks = {'Mrkv': np.zeros(N, dtype=int)}
    return agent.shocks['Mrkv'].copy()

# =========================================================================
# Per the AggFiscalModel.hit_with_recession_shock structure, we need to:
# - Have a working agent with shock_history initialized
# - Call hit_with_recession_shock(shock_type='recessionUI')
# - Inspect the result

# But hit_with_recession_shock does the FULL simulation (T_sim steps).
# To inspect the post-spike state in isolation, we need to either:
#   (a) Modify the method to expose intermediate state, OR
#   (b) Read the shock_history at t=0 and reverse-engineer the spike

# Approach: just run hit_with_recession_shock in a controlled setup and
# compare shock_history['Mrkv'][0] (= post-1st-transition state) under both
# shuffle and non-shuffle.

# But that's exactly what we already saw in the existing pickles! What we
# need NOW is to also see the POST-SPIKE PRE-TRANSITION state.

# Minimal path: monkeypatch the get_micro_markv_states_guts and the shuffle
# loop to record the state BEFORE applying the transition.

print("=" * 70)
print("Diagnostic plan: monkey-patch hit_with_recession_shock to expose")
print("the post-spike, pre-1st-transition state.")
print("=" * 70)
print()

# Strategy: copy the _hit_with_recession_shock_shuffled and hit_with_recession_shock
# methods locally, modify them to expose the post-spike state, and run them
# on the same input.

# Actually the simplest thing: just instrument the existing methods and rerun.
# Add a "post_spike_mrkv" attribute that gets set right after the spike code
# but before the per-period loop.

# Read the existing code and patch it to save self._post_spike_mrkv
import AggFiscalModel as M

# Save original methods
orig_nshuf = M.AggFiscalType.hit_with_recession_shock
orig_shuf = M.AggFiscalType._hit_with_recession_shock_shuffled

def patched_nshuf(self, shock_type):
    """Wrapper: save post-spike state before the per-period loop."""
    # Run the original up to the per-period loop, save state, then resume
    # Actually — simpler: just call the original and infer the post-spike
    # state from the recorded history. But this won't work because
    # hit_with_recession_shock CONSUMES self.shocks['Mrkv'] in-place.

    # Better: save self.shocks['Mrkv'] BEFORE calling the original, then
    # apply just the spike code, save that, then call the original.
    pre_spike = self.shocks['Mrkv'].copy()

    # Apply only the spike portion (employed → u1Q + macro shift)
    # This duplicates the spike logic
    from HARK.distributions import Uniform
    if shock_type in ("recession", "recessionUI", "recessionTaxCut", "recessionCheck"):
        this_Urate = self.Urate_recession
    else:
        this_Urate = self.Urate_normal

    # Save the RNG state before drawing — we'll restore it for the actual call
    rng_state_save = self.RNG.get_state()

    draws = Uniform(seed=self.RNG.integers(2**31-1)).draw(self.AgentCount)
    draws = self.RNG.permutation(draws)
    MrkvNew = pre_spike.copy()
    old_Urate = self.Urate_normal
    draws_empy2umemp = draws > 1.0-(this_Urate-old_Urate)/(1.0-old_Urate)
    MrkvNew[np.logical_and(np.equal(pre_spike, 0), draws_empy2umemp)] = 1
    if shock_type in ("recession", "recessionUI", "recessionTaxCut", "recessionCheck"):
        MrkvNew += 3*self.num_base_MrkvStates
    elif shock_type in ("UI", "TaxCut", "Check"):
        MrkvNew += 2*self.num_base_MrkvStates
    self._post_spike_mrkv_nshuf = MrkvNew.copy()

    # Restore RNG state and run the original
    self.RNG.set_state(rng_state_save)
    self.shocks['Mrkv'] = pre_spike
    return orig_nshuf(self, shock_type)

def patched_shuf(self, shock_type):
    pre_spike = self.shocks['Mrkv'].copy()

    from HARK.distributions import Uniform
    if shock_type in ("recession", "recessionUI", "recessionTaxCut", "recessionCheck"):
        this_Urate = self.Urate_recession
    else:
        this_Urate = self.Urate_normal

    rng_state_save = self.RNG.get_state()

    self._shuffle_base_seed = getattr(self, 'seed', 0) * 131 + 77777

    draws = Uniform(seed=self.RNG.integers(2**31 - 1)).draw(self.AgentCount)
    draws = self.RNG.permutation(draws)
    MrkvNew = pre_spike.copy()
    old_Urate = self.Urate_normal
    draws_empy2umemp = draws > 1.0 - (this_Urate - old_Urate) / (1.0 - old_Urate)
    MrkvNew[np.logical_and(np.equal(pre_spike, 0), draws_empy2umemp)] = 1
    J = self.num_base_MrkvStates
    if shock_type in ("recession", "recessionUI", "recessionTaxCut", "recessionCheck"):
        MrkvNew += 3 * J
    elif shock_type in ("UI", "TaxCut", "Check"):
        MrkvNew += 2 * J
    self._post_spike_mrkv_shuf = MrkvNew.copy()

    self.RNG.set_state(rng_state_save)
    self.shocks['Mrkv'] = pre_spike
    return orig_shuf(self, shock_type)

M.AggFiscalType.hit_with_recession_shock = patched_nshuf
M.AggFiscalType._hit_with_recession_shock_shuffled = patched_shuf

print("Patched hit_with_recession_shock to expose post-spike state.")
print()
print("To use: load this module and run the actual recessionUI scenario.")
print("Then read self._post_spike_mrkv_{shuf,nshuf} for inspection.")
