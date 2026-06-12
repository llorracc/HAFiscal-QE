"""
Phase R.1 diagnostic: capture per-capita Mrkv distributions in
shuffle vs non-shuffle paths after the spike + first transition.

Strategy:
1. Build identical setup for both paths (same seed, same pre-state)
2. Run hit_with_recession_shock for both
3. Compare shock_history['Mrkv'][0] (= post-1st-transition)
4. If they differ, replicate the spike code separately to compare
   post-spike state (= input to first transition)
"""
import os, sys
import numpy as np
from pathlib import Path
from collections import Counter

sys.argv = ['diag', '1.01', '2.0', '0.7', '0.0', '0.0']
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

os.environ.setdefault('HAFISCAL_AGENTCOUNT_H', '49000')
os.environ.setdefault('HAFISCAL_URATE_NORMAL_H', '0.045')
os.environ.setdefault('HAFISCAL_UI_STATE_ENCODING', 'bug_fix')

import AggFiscalModel as M
import Parameters

def report_dist(label, mrkv_array, J, N):
    micro = mrkv_array.astype(int) % J
    macro = mrkv_array.astype(int) // J
    cnt_micro = Counter(micro.tolist())
    cnt_macro = Counter(macro.tolist())
    print(f"  {label}:")
    print(f"    macro: {dict(sorted(cnt_macro.items()))}")
    fracs = {}
    for j in range(J):
        c = cnt_micro.get(j, 0)
        p = c / N
        fracs[j] = p
        print(f"    micro={j}: {p*100:>7.3f}%  ({c} agents)")
    return fracs

def build_agent(seed, mc_shuffle):
    init_list = Parameters.return_parameters('HS_Only')
    init_d = init_list[0]
    init_d['AgentCount'] = 49000

    agent = M.AggFiscalType(**init_d)
    agent.seed = seed
    agent.RNG = np.random.default_rng(seed)
    if mc_shuffle:
        agent.mc_shuffle = True
        agent.income_shuffle = True
        agent.markov_shuffle = True

    agent.update_mrkv_array("recessionUI")
    agent.act_T = 40
    agent.T_sim = 40

    N = agent.AgentCount
    agent.shock_history = {
        'Mrkv': np.zeros((40, N), dtype=int),
        'PermShk': np.ones((40, N)),
        'TranShk': np.ones((40, N)),
        'who_dies': np.zeros((40, N), dtype=int),
        'update_draw': np.zeros((40, N), dtype=int),
        'unemployment_draw': np.zeros((40, N)),
    }

    # Initialize all agents at micro=0 employed (controlled initial state)
    agent.shocks = {'Mrkv': np.zeros(N, dtype=int)}

    agent.t_age = np.zeros(N, dtype=int)
    rs99 = np.random.default_rng(99)
    rs98 = np.random.default_rng(98)
    agent.who_dies_fixed_hist = np.zeros((40, N), dtype=int)
    agent.unemployment_draw_fixed_hist = rs99.random((40, N))
    agent.perm_shock_fixed_hist = np.ones((40, N))
    agent.tran_shock_fixed_hist = np.ones((40, N))
    agent.update_draw_fixed_hist = rs98.integers(0, 1000, (40, N))

    # Recession-onset path: macro 3 (= recession active) for first periods, then back to 0
    # Need at least T_sim=40 entries
    agent.EconomyMrkvNow_hist = ([3] * 11) + [0] * 29  # 40 entries; macro=3 for first 11
    agent.state_now = {'pLvl': np.ones(N)}
    return agent

print("=" * 80)
print("Phase R.1: Shuffle vs non-shuffle Mrkv distribution after spike + 1 step")
print("=" * 80)
print(f"Encoding: {os.environ.get('HAFISCAL_UI_STATE_ENCODING')}")
print(f"Initial state: ALL agents at micro=0 (employed), macro=0 (normal)")
print(f"EconomyMrkvNow_hist[0] = 3 (= recession active at t=0)")
print()

print("Building two identical agents with same seed=12345...")
agent_n = build_agent(seed=12345, mc_shuffle=False)
agent_s = build_agent(seed=12345, mc_shuffle=True)

J = agent_n.num_base_MrkvStates
N = agent_n.AgentCount
print(f"J (num_base_MrkvStates) = {J}")
print(f"N = {N}")
print()

print("CHECKPOINT A: pre-spike state (set to all-zero employed)")
chkpt_A_n = report_dist("non-shuffle", agent_n.shocks['Mrkv'], J, N)
chkpt_A_s = report_dist("shuffle    ", agent_s.shocks['Mrkv'], J, N)

print()
print("Calling hit_with_recession_shock('recessionUI') for both paths...")
agent_n.hit_with_recession_shock("recessionUI")
agent_s._hit_with_recession_shock_shuffled("recessionUI")

print()
print("CHECKPOINT C: post-1st-transition state (shock_history['Mrkv'][0])")
chkpt_C_n = report_dist("non-shuffle", agent_n.shock_history['Mrkv'][0], J, N)
chkpt_C_s = report_dist("shuffle    ", agent_s.shock_history['Mrkv'][0], J, N)

print()
print("=" * 80)
print("Per-state divergence at CHECKPOINT C:")
print("=" * 80)
print(f"{'state':<8} {'shuf %':>10} {'nshuf %':>10} {'Δ pp':>10} {'σ':>8}")
for j in range(J):
    p_s = chkpt_C_s[j]
    p_n = chkpt_C_n[j]
    diff_pp = (p_s - p_n) * 100
    se_pp = np.sqrt(p_s*(1-p_s)/N + p_n*(1-p_n)/N) * 100
    sigma = diff_pp / se_pp if se_pp > 0 else float('nan')
    print(f"{j:<8} {p_s*100:>9.3f}% {p_n*100:>9.3f}% {diff_pp:>+9.3f}pp {sigma:>+7.1f}σ")

# Now also capture CHECKPOINT B by replicating the spike code
print()
print("=" * 80)
print("CHECKPOINT B: post-spike, pre-1st-transition state (replicated)")
print("=" * 80)

def replicate_spike(seed, shock_type, agent):
    """Replicate the spike code from hit_with_recession_shock lines 671-694."""
    from HARK.distributions import Uniform
    rng = np.random.default_rng(seed)
    if shock_type in ("recession", "recessionUI", "recessionTaxCut", "recessionCheck"):
        this_Urate = agent.Urate_recession
    else:
        this_Urate = agent.Urate_normal
    pre_state = np.zeros(agent.AgentCount, dtype=int)  # all employed
    draws = Uniform(seed=rng.integers(2**31-1)).draw(agent.AgentCount)
    draws = rng.permutation(draws)
    MrkvNew = pre_state.copy()
    old_Urate = agent.Urate_normal
    draws_empy2umemp = draws > 1.0-(this_Urate-old_Urate)/(1.0-old_Urate)
    MrkvNew[np.logical_and(np.equal(pre_state, 0), draws_empy2umemp)] = 1
    J_local = agent.num_base_MrkvStates
    if shock_type in ("recession", "recessionUI", "recessionTaxCut", "recessionCheck"):
        MrkvNew += 3 * J_local
    elif shock_type in ("UI", "TaxCut", "Check"):
        MrkvNew += 2 * J_local
    return MrkvNew

# Both paths use the SAME spike code, so this should give the same result
# regardless of mc_shuffle
chkpt_B = replicate_spike(seed=12345, shock_type="recessionUI", agent=agent_n)
chkpt_B_dist = report_dist("post-spike (replicated, both paths use same spike code)",
                            chkpt_B, J, N)

print()
print("Expected post-spike: ~95% emp@macro3, ~5% u1Q@macro3 (urate_rec - urate_norm)")
print(f"Urate_normal (HS) = {agent_n.Urate_normal}")
print(f"Urate_recession (HS) = {agent_n.Urate_recession}")
print(f"  Expected u1Q bump fraction = (Urate_rec - Urate_norm) / (1 - Urate_norm) = "
      f"{(agent_n.Urate_recession - agent_n.Urate_normal)/(1 - agent_n.Urate_normal):.4f}")
