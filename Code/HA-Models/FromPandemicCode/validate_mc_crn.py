"""Validate CRN determinism across Python subprocess boundaries.

Runs a minimal MC pipeline (build economy, solve, burn-in, run base +
one recession-UI scenario) and pickles the shock histories and
experiment outputs. Two independent subprocess invocations of this
script, with the same parameters, should produce byte-identical
pickles — that is the CRN guarantee we need for subprocess-level
parallelism of run_hybrid_welfare6.py.

If this script produces identical outputs across subprocess runs, the
determinism assumption holds and the subprocess-parallel wrapper is
safe. If not, we need to investigate what state is leaking.

Usage:
    python validate_mc_crn.py --run-tag A --parametrization HS_Only
    python validate_mc_crn.py --run-tag B --parametrization HS_Only
    # then diff validation_mc_crn_A.pkl  validation_mc_crn_B.pkl
"""

import argparse
import os
import pickle
import sys
from copy import deepcopy
from time import time

import numpy as np

os.environ["MPLBACKEND"] = "Agg"
import matplotlib  # noqa: E402
matplotlib.use("Agg")

# Allow running from the repo root or from FromPandemicCode/.
HERE = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != HERE:
    os.chdir(HERE)
sys.path.insert(0, HERE)

_ORIG_ARGV = sys.argv[:]
sys.argv = ["validate_mc_crn"]

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy  # noqa: E402
from HARK.distributions import DiscreteDistribution  # noqa: E402
from Parameters import return_parameters  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--parametrization", default="HS_Only",
                        choices=("HS_Only", "Reduced_Run", "Baseline"))
    parser.add_argument("--with-ad", action="store_true",
                        help="Run recessionUI with AD convergence (slower; "
                             "tests AD-iteration determinism).")
    parser.add_argument("--out-dir", default=HERE)
    args = parser.parse_args(_ORIG_ARGV[1:])

    t0 = time()
    (
        init_dropout, init_highschool, init_college,
        init_ADEconomy, DiscFacDstns, DiscFacCount, AgentCountTotal,
        base_dict, num_max_iterations_solvingAD,
        convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
        data_EducShares, max_recession_duration, num_experiment_periods,
        recession_changes, UI_changes, recession_UI_changes,
        TaxCut_changes, recession_TaxCut_changes,
        Check_changes, recession_Check_changes,
    ) = return_parameters(Parametrization=args.parametrization,
                          OutputFor="_Main.py")

    init_params = [init_dropout, init_highschool, init_college]
    AgentTypes = []
    for e in range(3):
        if data_EducShares[e] <= 0.0:
            continue
        for d in range(DiscFacCount):
            t = AggFiscalType(**init_params[e])
            t.cycles = 0
            t.DiscFac = DiscFacDstns[e].atoms[0][d]
            t.seed = e * DiscFacCount + d
            t.AgentCount = int(np.floor(
                AgentCountTotal * data_EducShares[e] / DiscFacCount
            ))
            AgentTypes.append(t)

    AggEco = AggregateDemandEconomy(**init_ADEconomy)
    AggEco.agents = AgentTypes

    for a in AggEco.agents:
        a.get_economy_data(AggEco)
        IncShkDstn_unemp = DiscreteDistribution(
            np.array([1.0]), [np.array([1.0]), np.array([a.IncUnemp])])
        IncShkDstn_unemp_nobenefits = DiscreteDistribution(
            np.array([1.0]),
            [np.array([1.0]), np.array([a.IncUnempNoBenefits])])
        a.IncShkDstn[0].seed = 763607780
        a.IncShkDstn[0].reset()
        EmployedIncShkDstn = deepcopy(a.IncShkDstn[0])
        a.IncShkDstn = [
            [a.IncShkDstn[0]]
            + [IncShkDstn_unemp] * UBspell_normal
            + [IncShkDstn_unemp_nobenefits]
        ]
        a.IncShkDstn_base = a.IncShkDstn
        IncShkDstn_recession = [
            a.IncShkDstn[0] * (2 * (num_experiment_periods + 1))
        ]
        a.IncShkDstn_recession = IncShkDstn_recession
        a.IncShkDstn_recessionUI = IncShkDstn_recession

        EmployedIncShkDstn_tc = deepcopy(EmployedIncShkDstn)
        EmployedIncShkDstn_tc.atoms[0][1] = (
            EmployedIncShkDstn_tc.atoms[0][1] * a.TaxCutIncFactor
        )
        TaxCutStatesIncShkDstn = (
            [EmployedIncShkDstn_tc]
            + [IncShkDstn_unemp] * UBspell_normal
            + [IncShkDstn_unemp_nobenefits]
        )
        IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
        for i in range(
            2 * num_base_MrkvStates,
            2 * (num_experiment_periods + 1) * num_base_MrkvStates,
        ):
            IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[
                np.mod(i, num_base_MrkvStates)
            ]
        a.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
        a.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

    AggEco.solve()
    print(f"[{args.run_tag}] solved in {time() - t0:.0f}s")

    # Burn-in + switch to counterfactual mode
    AggEco.reset()
    for a in AggEco.agents:
        a.initialize_sim()
        a.AggDemandFac = 1.0
        a.RfreeNow = 1.0
        a.CaggNow = 1.0
    AggEco.make_history()
    AggEco.save_state()
    AggEco.switch_to_counterfactual_mode("base")
    act_T = AggEco.act_T
    for a in AggEco.agents:
        a.T_sim = act_T
        a.EconomyMrkvNow_hist = [0] * act_T
    AggEco.make_idiosyncratic_shock_histories()

    # Capture the idiosyncratic shock histories for the first agent type
    # (all types have deterministic seeds; checking one is sufficient and
    # keeps the pickle small). HARK stores these in agent.shock_history
    # as a dict of arrays.
    a0 = AggEco.agents[0]
    shocks = {
        "PermShk":  np.array(a0.shock_history["PermShk"]),
        "TranShk":  np.array(a0.shock_history["TranShk"]),
        "who_dies": np.array(a0.shock_history["who_dies"]),
        "unemployment_draw": np.array(a0.shock_history["unemployment_draw"]),
        "Mrkv": np.array(a0.shock_history["Mrkv"]),
    }

    # Base MC
    base_dict_agg = deepcopy(base_dict)
    base_mc = AggEco.run_experiment(**base_dict_agg, Full_Output="ForWelfare")
    AggEco.store_baseline(base_mc["AggCons"])
    print(f"[{args.run_tag}] base in {time() - t0:.0f}s")

    # One recession scenario: recessionUI. Optionally with AD convergence
    # (iterative cFunc training — tests whether the convergence loop
    # introduces floating-point-order non-determinism across subprocesses).
    eco = deepcopy(AggEco)
    eco.switch_shock_type("recessionUI")
    if args.with_ad:
        eco.solve_ad_ui_extension_recession(
            num_max_iterations=num_max_iterations_solvingAD,
            convergence_cutoff=convergence_tol_solvingAD,
            name="recessionUI",
        )
        eco.switch_shock_type("recessionUI")
        eco.restore_ADsolution(name="recessionUI")
        print(f"[{args.run_tag}] solved AD in {time() - t0:.0f}s")
    else:
        eco.solve()
    d = base_dict_agg.copy()
    d.update(recession_UI_changes)
    rec_path = (
        list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 20
    )
    rec_path[0] += 1  # single-period recession
    d["EconomyMrkv_init"] = rec_path
    ui_mc = eco.run_experiment(**d, Full_Output="ForWelfare")
    tag = "recessionUI_AD" if args.with_ad else "recessionUI"
    print(f"[{args.run_tag}] {tag} in {time() - t0:.0f}s")

    out_path = os.path.join(
        args.out_dir, f"validation_mc_crn_{args.run_tag}.pkl")
    with open(out_path, "wb") as f:
        pickle.dump({
            "run_tag": args.run_tag,
            "parametrization": args.parametrization,
            "shocks": shocks,
            "base": {
                "cLvl_all_splurge": np.array(base_mc["cLvl_all_splurge"]),
                "AggCons":          np.array(base_mc["AggCons"]),
                "AggIncome":        np.array(base_mc["AggIncome"]),
            },
            "ui": {
                "cLvl_all_splurge": np.array(ui_mc["cLvl_all_splurge"]),
                "AggCons":          np.array(ui_mc["AggCons"]),
                "AggIncome":        np.array(ui_mc["AggIncome"]),
            },
            "total_runtime_s": time() - t0,
        }, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"[{args.run_tag}] saved: {out_path} ({time() - t0:.0f}s total)")


if __name__ == "__main__":
    main()
