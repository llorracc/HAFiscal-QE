"""Diagnostic: verify shuffle is doing what it should.

User's claims (to verify):
  (a) with income_shuffle, per-period mean of transitory and permanent
      shocks should be exactly 1.000 (up to FP rounding)
  (b) with mc_shuffle, during burn-in the count of agents in each micro
      (employment) state should be EXACTLY CONSTANT across periods
  (c) the only residual aggregate stochasticity should come from the
      death-and-replacement process

These should hold at "quota-exact N" — the smallest N such that every
probability × N is an integer. For HS that's LCM of denominators of:
  - Urate_h = 0.044 = 11/250     -> 250
  - 1/Rspell = 1/6                -> 6
  - PermShk atoms = 1/7           -> 7
  - TranShk atoms = 1/7           -> 7
  - LivPrb = 1 - 1/160            -> 160
LCM(250, 6, 7, 7, 160) = ~84,000. So single-beta minimum for a no-leftover
shuffle is ~84k agents, not 1,200. The doc's "1,200" figure relied on
Rspell*(1/s_min) = 6/0.005 = 1,200, which is the minimum to get J_min
per state - BUT doesn't give exact quota under the actual probabilities.

This version uses eco.make_history() so Markov transitions fire properly.
Earlier version called sim_one_period() manually, which bypassed the
economy sow/mill_rule loop and kept all agents frozen in state 0.

Usage:
    cd Code/HA-Models/FromPandemicCode
    python diag_shuffle_working.py
"""
import os, sys
from copy import deepcopy
import numpy as np

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith("FromPandemicCode"):
    os.chdir(cwd + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, os.getcwd())

os.environ["MPLBACKEND"] = "Agg"
import matplotlib; matplotlib.use("Agg")  # noqa: E702

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy  # noqa: E402
from HARK.distributions import DiscreteDistribution  # noqa: E402
from Parameters import return_parameters  # noqa: E402

(
    init_dropout, init_highschool, init_college,
    init_ADEconomy, DiscFacDstns, DiscFacCount, AgentCountTotal,
    base_dict, num_max_iterations_solvingAD, convergence_tol_solvingAD,
    UBspell_normal, num_base_MrkvStates, data_EducShares,
    max_recession_duration, num_experiment_periods,
    recession_changes, UI_changes, recession_UI_changes,
    TaxCut_changes, recession_TaxCut_changes,
    Check_changes, recession_Check_changes,
) = return_parameters(Parametrization="Baseline", OutputFor="_Main.py")


def build_and_simulate(N, mc_shuffle, income_shuffle, seed=0, T_sim=60):
    """Run HS-only simulation for T_sim periods using eco.make_history(),
    record per-period aggregates from history arrays."""
    a = AggFiscalType(**init_highschool)
    a.cycles = 0
    a.DiscFac = 0.9298
    a.AgentCount = int(N)
    a.seed = int(seed)
    a.mc_shuffle = bool(mc_shuffle)
    a.income_shuffle = bool(income_shuffle)
    a.T_sim = int(T_sim)
    # track_vars defaults to [] in this path (only set by switch_to_counterfactual_mode)
    a.track_vars = ['MicroMrkvNow', 'MacroMrkvNow', 'PermShk', 'TranShk']

    eco = AggregateDemandEconomy(**init_ADEconomy)
    eco.agents = [a]
    a.get_economy_data(eco)

    # Minimal IncShkDstn setup
    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([a.IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([a.IncUnempNoBenefits])])
    a.IncShkDstn[0].seed = 763607780 + seed
    a.IncShkDstn[0].reset()
    a.IncShkDstn = [
        [a.IncShkDstn[0]]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]
    ]
    a.IncShkDstn_base = a.IncShkDstn
    eco.solve()
    eco.reset()
    a.initialize_sim()
    a.AggDemandFac = 1.0
    a.RfreeNow = 1.0
    a.CaggNow = 1.0
    eco.make_history()          # runs full economy simulation loop

    # history shape: (T_sim, AgentCount). Shocks are tracked in `history`
    # because make_shock_history isn't pre-populated in this path.
    mrkv_hist = np.asarray(a.history['MicroMrkvNow'])
    tran_hist = np.asarray(a.history['TranShk'])
    perm_hist = np.asarray(a.history['PermShk'])

    # per-period state counts (4 states)
    state_counts = np.zeros((T_sim, 4), dtype=int)
    for t in range(T_sim):
        row = mrkv_hist[t].astype(int)
        row = row[row >= 0]                 # drop NaN-filled (dead) slots
        c = np.bincount(row, minlength=4)[:4]
        state_counts[t] = c

    tran_means = np.array([float(tran_hist[t][~np.isnan(tran_hist[t])].mean())
                            for t in range(T_sim)])
    perm_means = np.array([float(perm_hist[t][~np.isnan(perm_hist[t])].mean())
                            for t in range(T_sim)])

    return {
        'N': N,
        'mc_shuffle': mc_shuffle,
        'income_shuffle': income_shuffle,
        'state_counts': state_counts,
        'tran_means': tran_means,
        'perm_means': perm_means,
    }


def summarize(tag, r, burn=10):
    """Summarize after discarding first `burn` periods (transient)."""
    sc = r['state_counts'][burn:]
    t = r['tran_means'][burn:]
    p = r['perm_means'][burn:]
    print(f"\n--- {tag}  (N={r['N']}, shuffle_mrkv={r['mc_shuffle']}, "
          f"shuffle_inc={r['income_shuffle']}; post-burn t>={burn}) ---")
    print(f"  state counts per period:")
    print(f"    emp : mean={sc[:,0].mean():9.2f}  SD={sc[:,0].std():7.3f}  "
          f"min={sc[:,0].min():5d}  max={sc[:,0].max():5d}")
    print(f"    ub1 : mean={sc[:,1].mean():9.2f}  SD={sc[:,1].std():7.3f}  "
          f"min={sc[:,1].min():5d}  max={sc[:,1].max():5d}")
    print(f"    ub2 : mean={sc[:,2].mean():9.2f}  SD={sc[:,2].std():7.3f}  "
          f"min={sc[:,2].min():5d}  max={sc[:,2].max():5d}")
    print(f"    noUB: mean={sc[:,3].mean():9.2f}  SD={sc[:,3].std():7.3f}  "
          f"min={sc[:,3].min():5d}  max={sc[:,3].max():5d}")
    print(f"  tran shock: per-period mean mu={t.mean():.8f}  "
          f"SD(mu_t)={t.std():.8f}  range=[{t.min():.6f},{t.max():.6f}]")
    print(f"  perm shock: per-period mean mu={p.mean():.8f}  "
          f"SD(mu_t)={p.std():.8f}  range=[{p.min():.6f},{p.max():.6f}]")


# N choices to isolate each claim.
# Shock-atom count = 7 (tran and perm); Urate denominator 250; Rspell=6;
# LivPrb 1-1/160. LCM(250,6,7,160) = 84,000 is full quota-exact.
configs = [
    ("N=1200   (div by none of 7/250/160)",        1200),
    ("N=8400   (div by 7 only)",                   8400),
    ("N=5250   (div by 7,250,6; not 160)",         5250),
    ("N=84000  (quota-exact everywhere)",         84000),
]

results = {}
for label, N in configs:
    for mc_sh, inc_sh in [(False, False), (True, True)]:
        tag = f"{label}  shuffle={(mc_sh, inc_sh)}"
        print(f"\nrunning {tag}...")
        r = build_and_simulate(N, mc_sh, inc_sh)
        results[(label, mc_sh, inc_sh)] = r
        summarize(tag, r)

print("\n" + "=" * 72)
print("SUMMARY - user's claims")
print("=" * 72)
print("Claim (a): per-period shock means = 1.000 exactly with income_shuffle")
print("Claim (b): state counts constant across periods with mc_shuffle")
print("Claim (c): only residual aggregate noise from death-and-replacement")
print()
print("If claims hold at this N:  SD(mu_t) ~ 0 and state-count SD ~ 0 with shuffle.")
print("If N is not quota-exact:    some residual SD from leftover-agents assignment.")
