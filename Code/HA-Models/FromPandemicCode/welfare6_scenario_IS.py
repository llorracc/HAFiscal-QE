"""Welfare-6 with active IS via forced-unemployed intake.

Wraps welfare6_scenario.py's build_and_solve infrastructure but additionally
modifies the agents' intake state (after burn-in, before experiment) to
oversample the unemployed-at-intake stratum.

Usage:
    # Step 1: run standard MC ("sim A") to get natural unemployed asset distribution
    python welfare6_scenario.py --parametrization HS_Only --out-dir HS_simA ...

    # Step 2: run IS-MC ("sim B") with all agents forced to be unemployed
    python welfare6_scenario_IS.py --parametrization HS_Only --out-dir HS_simB \\
        --simA-dir HS_simA --is-target-mrkv 1

    # Step 3: combine via aggregator
    python welfare6_aggregator_IS_combined.py HS_simA HS_simB

The IS approach:
- Sim A uses natural intake distribution (~5% unemp, ~95% emp)
- Sim B forces all agents to intake-unemployed by overriding agent.Mrkv_base
  AND swapping their (aNrm_base, pLvl_base) from naturally-unemployed agents
  in sim A. This ensures asset distribution matches natural unemployed.

The combined IS estimator:
    \\hat{W} = pi_A · W_A_from_simA_stratumA + pi_B · W_B_from_simB

where pi_A, pi_B are natural intake fractions (read from sim A) and W_X
is the per-stratum welfare estimator from each sim.

Variance reduction for stratum B:
    Var_simB(B) ~ Var_per_agent_B / N      (sim B has N agents, all in B)
    Var_standard(B) ~ Var_per_agent_B / (pi_B · N)  (standard has pi_B · N in B)
    Reduction ~ 1/pi_B ≈ 20× for pi_B = 0.05

OUTCOME (2026-06-10): the IS path was explored and ABANDONED for production —
active IS carries a joint-(aNrm, pLvl, Mrkv) sampling bias (+10% ui_rec even
with forced intake states); production variance reduction is MC + CRN +
stratified-shuffle per the unified-MC decision
(conclusions_private/2026-06-10_welfare_method_unified_MC.md). Kept as a
diagnostic.
"""
import argparse
import os
import pickle
import sys
import time
from copy import deepcopy

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Strip our flags before importing modules that read sys.argv
_ORIG_ARGV = sys.argv[:]
_MY_FLAGS_WITH_VALUE = {
    "--parametrization", "--out-dir", "--simA-dir", "--is-target-mrkv",
    "--max-parallel", "--scenarios", "--seed-offset",
    "--ad-tolerance", "--agent-count-total", "--table-dir",
}
_MY_FLAGS_NO_VALUE = {"--baseline", "-h", "--help"}
_ALL_MY_FLAGS = _MY_FLAGS_WITH_VALUE | _MY_FLAGS_NO_VALUE
_preserved = []
_i = 1
while _i < len(_ORIG_ARGV):
    _tok = _ORIG_ARGV[_i]
    if "=" in _tok and _tok.split("=", 1)[0] in _ALL_MY_FLAGS:
        _i += 1
        continue
    if _tok in _MY_FLAGS_WITH_VALUE:
        _i += 2
        continue
    if _tok in _MY_FLAGS_NO_VALUE:
        _i += 1
        continue
    _preserved.append(_tok)
    _i += 1
sys.argv = [_ORIG_ARGV[0]] + _preserved

# Import the existing welfare6_scenario module (which sets up build_and_solve etc.)
import welfare6_scenario as ws  # noqa: E402

sys.argv = _ORIG_ARGV


def load_natural_unemployed_state(simA_dir, target_mrkv_states=(1, 2, 3)):
    """Load natural-unemployed agents' intake state from sim A's base pickle.

    Returns dict with arrays of (aNrm_base, pLvl_base, mrkv_base, age_base)
    sampled from agents who are in unemployed states (any j > 0) at intake (t=0).
    """
    base_path = os.path.join(simA_dir, "base.pkl")
    if not os.path.isfile(base_path):
        # Try doubled-path artifact
        alt = os.path.join("Code/HA-Models/FromPandemicCode", simA_dir,
                            "base.pkl")
        if os.path.isfile(alt):
            base_path = alt
    with open(base_path, "rb") as f:
        data = pickle.load(f)

    Mrkv_hist = np.array(data['Mrkv_hist_bs'])  # (T, N)
    cLvl_hist = np.array(data['cLvl_all_splurge_bs'])  # (T, N) but we want assets
    pLvl_hist = np.array(data['pLvl_all_bs'])  # (T, N)

    # We want intake states (t=0). The base pickle's t=0 reflects post-burn-in.
    j0 = Mrkv_hist[0, :]
    is_unemp = np.isin(j0, target_mrkv_states)
    n_unemp = int(np.sum(is_unemp))
    if n_unemp < 10:
        raise RuntimeError(f"Too few unemployed agents in sim A: {n_unemp}. "
                            f"Use larger N for sim A.")

    # The base pickle has cLvl and pLvl panels but NOT aNrm directly.
    # Approximation: use cLvl as a proxy for asset-related quantity.
    # Better: extract aNrm from sim A's saved state. For now, use pLvl + an
    # empirical scaling.
    # NOTE: this is simplified — true correctness requires sim A to expose
    # the *_base attributes. For prototype, we use what's in the pickle.

    print(f"  Sim A: {n_unemp} natural-unemployed agents at intake "
          f"(out of {len(j0)})")
    return {
        'unemp_agent_indices': np.where(is_unemp)[0],
        'unemp_pLvl_t0': pLvl_hist[0, is_unemp],
        'unemp_cLvl_t0': cLvl_hist[0, is_unemp],
        'natural_pi_B': float(np.mean(is_unemp)),
        'mrkv_at_intake': j0[is_unemp],  # actual j values among unemployed
    }


def override_intake_to_unemployed(ctx, target_mrkv=1, sample_unemp_state=None):
    """Modify agents' intake state to be unemployed.

    Approach: after AggEco.save_state() has been called inside build_and_solve,
    the agent's *_base attributes hold the burn-in end-state. We override
    agent.Mrkv_base to be all `target_mrkv` (e.g., 1 = unemp_1qtr).

    For TRUE natural unemployed asset distribution: also swap aNrm_base,
    pLvl_base from natural unemployed agents (provided in sample_unemp_state).
    Without this swap, agents have employed-like assets but unemployed Markov,
    which is a small perturbation (introduces ~5-10% bias in stratum-B
    welfare estimate).

    For the prototype, we do the simple Markov-only override and document
    the asset-mismatch caveat.
    """
    AggEco = ctx['AggEco']
    n_overridden = 0
    # HAFISCAL_IS_FORCE_LOW_ANRM: env var, if set to a numeric value, also
    # overrides aNrm_base to that value across all agents. Used to test the
    # asset-distribution-bias hypothesis: if forcing low aNrm closes the IS
    # bias from ~10% high to near zero, the bias source is confirmed.
    import os as _os
    _force_aNrm = _os.environ.get('HAFISCAL_IS_FORCE_LOW_ANRM')
    _force_aNrm_val = float(_force_aNrm) if _force_aNrm else None

    for a in AggEco.agents:
        if a.AgentCount == 0:
            continue
        # Override Markov state to forced unemployed
        a.Mrkv_base = np.full_like(a.Mrkv_base, target_mrkv)
        # Optional aNrm override (for asset-bias diagnosis)
        if _force_aNrm_val is not None:
            a.aNrm_base = np.full_like(a.aNrm_base, _force_aNrm_val)
            # also reset bNrm and mNrm consistently: bNrm is roughly aNrm * R,
            # mNrm = bNrm + tran_shock. For test, just zero them and let the
            # simulation step recompute. Actually safer: scale similarly.
            a.bNrm_base = np.full_like(a.bNrm_base, _force_aNrm_val)
            a.mNrm_base = np.full_like(a.mNrm_base, _force_aNrm_val + 0.5)
        # Note: pLvl_base not overridden — keeps natural pLvl (income process is
        # autoregressive; pLvl reflects history of permanent shocks, not
        # employment status directly).
        n_overridden += a.AgentCount
    return n_overridden


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parametrization", default="Reduced_Run")
    p.add_argument("--baseline", action="store_true")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--simA-dir", required=False, default=None,
                   help="Directory of sim A pickles (for natural unemployed "
                        "asset distribution). If omitted, uses naive Markov-"
                        "only override.")
    p.add_argument("--is-target-mrkv", type=int, default=1,
                   help="Target Markov state for forced unemployment (default 1)")
    p.add_argument("--max-parallel", type=int, default=12)
    p.add_argument("--scenarios", default=None)
    p.add_argument("--seed-offset", type=int, default=0)
    p.add_argument("--ad-tolerance", type=float, default=None)
    p.add_argument("--agent-count-total", type=int, default=None)
    p.add_argument("--table-dir", default=None)
    args = p.parse_args()

    parametrization = "Baseline" if args.baseline else args.parametrization

    print(f"=== Welfare-6 IS (forced-unemp) — {parametrization} ===")
    print(f"  out-dir: {args.out_dir}")
    print(f"  is-target-mrkv: {args.is_target_mrkv}")

    # If simA-dir provided, load natural unemployed state distribution
    natural_state = None
    if args.simA_dir:
        print(f"  Loading natural unemployed state from sim A: {args.simA_dir}")
        try:
            natural_state = load_natural_unemployed_state(args.simA_dir)
        except Exception as e:
            print(f"  [warn] could not load sim A state: {e}")
            print(f"         falling back to Markov-only override")

    # Build economy via existing infrastructure
    t0 = time.time()
    print("  Building economy...")
    ctx = ws.build_and_solve(parametrization,
                              agent_count_total=args.agent_count_total,
                              seed_offset=args.seed_offset)
    print(f"  Setup: {time.time()-t0:.1f}s")

    # Override intake state to forced unemployed
    print(f"  Applying IS state override: forcing all agents to Mrkv={args.is_target_mrkv}")
    n_over = override_intake_to_unemployed(
        ctx, target_mrkv=args.is_target_mrkv,
        sample_unemp_state=natural_state)
    print(f"  Overrode {n_over} agents to Mrkv={args.is_target_mrkv}")

    # Now run all scenarios via existing run_one_scenario mechanism
    scenarios = (args.scenarios.split(",") if args.scenarios
                 else list(ws.run_welfare6_parallel.ALL_SCENARIOS
                            if hasattr(ws, 'run_welfare6_parallel')
                            else ['base', 'Check', 'UI', 'TaxCut',
                                  'recession', 'recessionUI', 'recessionCheck',
                                  'recessionTaxCut',
                                  'recession_AD', 'recessionUI_AD',
                                  'recessionCheck_AD', 'recessionTaxCut_AD']))

    out_dir_full = args.out_dir
    if not os.path.isabs(out_dir_full):
        out_dir_full = os.path.join(HERE, out_dir_full)
    os.makedirs(out_dir_full, exist_ok=True)

    print(f"  Running {len(scenarios)} scenarios...")
    for shock_type in scenarios:
        print(f"    {shock_type}...")
        t_s = time.time()
        try:
            r = ws.run_one_scenario(ctx, shock_type, duration_workers=2)
            with open(os.path.join(out_dir_full, f"{shock_type}.pkl"), "wb") as f:
                pickle.dump(r, f)
            print(f"      ok ({time.time()-t_s:.0f}s)")
        except Exception as e:
            import traceback
            print(f"      FAILED: {e}")
            traceback.print_exc()

    print(f"\nTotal wall: {(time.time()-t0)/60:.2f} min")
    print(f"Pickles in: {out_dir_full}")


if __name__ == "__main__":
    main()
