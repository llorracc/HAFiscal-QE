"""TM-a analytical welfare-6 driver.

Computes welfare-6 by leveraging the existing TM-a Step-5 infrastructure,
extended (in tm_methods.py) to also produce per-period normalized felicity
and inverse-marginal-utility moments. Combines per-cohort per-scenario
per-period moments into welfare-6 cells via the formula:

    W = NPV(welfare_num) / NPV(AddInc) + (NPV(AddInc) - NPV(AddCons))/NPV(AddInc)

where (under the "indep state, CRN p" approximation derived in
conclusions_private/2026-05-09_welfare6_tm_a_option_b3_math.md):

    welfare_num(t) = Σ_cohort N_ℓ · pop_rescale_ℓ · E_ℓ[p_t]
                     · MU_inv_base_norm_ℓ(t)
                     · (U_pol_norm_ℓ(t) - U_none_norm_ℓ(t))

The lifecycle factor uses pLvl_factor (matching the multiplier infrastructure),
which preserves the CRN-p coupling exactly while approximating the (mrkv,a)
state coupling via factorization. Bias vs CRN-MC limit: ~1-3% Check/TaxCut,
~5-15% UI (worst case where MC itself is unreliable).

Usage:
    python welfare6_tm.py --parametrization Reduced_Run \\
        --out-pickle welfare6_tm_reduced.pkl \\
        --table-dir Tables/Reduced_Run_welfare6_tm/

    python welfare6_tm.py --parametrization Baseline \\
        --out-pickle welfare6_tm_baseline.pkl \\
        --table-dir Tables/Baseline_welfare6_tm/
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

# Strip our own CLI flags from sys.argv BEFORE importing modules whose import
# paths read positional argv (Parameters.py / EstimParameters.py do).
_ORIG_ARGV = sys.argv[:]
_MY_FLAGS_WITH_VALUE = {
    "--parametrization", "--out-pickle", "--table-dir", "--scenarios",
}
_MY_FLAGS_NO_VALUE = {"--baseline", "--no-ad", "-h", "--help"}
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

from welfare6_scenario import build_and_solve  # noqa: E402
from tm_methods import (  # noqa: E402
    compute_baseline_tm_data,
    propagate_experiment_tm_a,
    _compute_check_buckets,
    calculate_NPV,
)

# Restore argv for our own argparse.
sys.argv = _ORIG_ARGV


# Scenarios mirroring run_welfare6_parallel.py / Welfare.py.
ALL_SCENARIOS = (
    "base",
    "Check", "UI", "TaxCut",
    "recession", "recessionUI", "recessionCheck", "recessionTaxCut",
    "recession_AD", "recessionUI_AD",
    "recessionCheck_AD", "recessionTaxCut_AD",
)


def _shock_changes(ctx, shock_type):
    """Map scenario shock_type to (changes dict, recession flag, AD flag)."""
    base = deepcopy(ctx["base_dict"])
    rec_changes = ctx["recession_changes"]
    ui_changes = ctx["UI_changes"]
    rec_ui = ctx["recession_UI_changes"]
    tc_changes = ctx["TaxCut_changes"]
    rec_tc = ctx["recession_TaxCut_changes"]
    chk_changes = ctx["Check_changes"]
    rec_chk = ctx["recession_Check_changes"]

    is_ad = shock_type.endswith("_AD")
    core = shock_type[:-3] if is_ad else shock_type
    is_rec = core.startswith("recession") and core != "recession_"

    if core == "base":
        d = dict(base)
        d["shock_type"] = "base"
        return d, False, is_ad
    if core == "Check":
        d = dict(base); d.update(chk_changes); d["shock_type"] = "Check"
        return d, False, is_ad
    if core == "UI":
        d = dict(base); d.update(ui_changes); d["shock_type"] = "UI"
        return d, False, is_ad
    if core == "TaxCut":
        d = dict(base); d.update(tc_changes); d["shock_type"] = "TaxCut"
        return d, False, is_ad
    if core == "recession":
        d = dict(base); d.update(rec_changes); d["shock_type"] = "recession"
        return d, True, is_ad
    if core == "recessionUI":
        d = dict(base); d.update(rec_ui); d["shock_type"] = "recessionUI"
        return d, True, is_ad
    if core == "recessionCheck":
        d = dict(base); d.update(rec_chk); d["shock_type"] = "recessionCheck"
        return d, True, is_ad
    if core == "recessionTaxCut":
        d = dict(base); d.update(rec_tc); d["shock_type"] = "recessionTaxCut"
        return d, True, is_ad
    raise ValueError(f"Unknown shock_type: {shock_type}")


def _build_econ_mrkv_path(act_T, num_experiment_periods, is_recession,
                          recession_duration=None, is_base=False):
    """Build EconomyMrkv_init path for a scenario.

    BASE: stay at macro=0 the whole time (no policy, no recession).
    Non-recession non-base (Check / UI / TaxCut): even macro states.
    Recession (single duration): odd macro states for first (duration) periods,
    then even. If recession_duration is None, use num_experiment_periods (the
    "max-duration" path used for averaging).
    """
    if is_base:
        return [0] * act_T
    path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 20
    path = path[:act_T]
    if is_recession:
        if recession_duration is None:
            recession_duration = num_experiment_periods
        for t in range(min(recession_duration, len(path))):
            path[t] = path[t] + 1  # even -> odd
    return path


def _setup_tm_a_agents(ctx):
    """Set tm_a_indexed=True on all agents and compute baseline_tm_data."""
    AggEco = ctx["AggEco"]
    for ag in AggEco.agents:
        ag.tm_a_indexed = True
    baseline_tm_data = []
    aCount = int(os.environ.get("HAFISCAL_TM_MCOUNT", 100))
    for ag in AggEco.agents:
        bd = compute_baseline_tm_data(AggEco, mCount=aCount)
        # Note: compute_baseline_tm_data takes economy and returns list-per-agent
        baseline_tm_data = bd  # since it's a list
        break
    return baseline_tm_data


def _propagate_one(agent, bd, EconomyMrkv_init, shock_type, Cratio, act_T,
                   is_check, neutral_measure, return_dist_history=False):
    check_info_i = None
    if is_check:
        buckets = _compute_check_buckets(
            agent, bd['E_pLvl'],
            unemployment_rate=bd.get('u_ergodic'))
        check_info_i = {'period': 0, 'buckets': buckets}
    res = propagate_experiment_tm_a(
        agent, bd['ergodic'], EconomyMrkv_init, bd['dist_aGrid'],
        bd['E_pLvl'], Cratio=Cratio, act_T=act_T,
        neutral_measure=neutral_measure,
        check_info=check_info_i,
        shock_type=shock_type,
        interpretation=getattr(agent, 'interpretation', 'CDC'),
        compute_welfare=True,
    )
    return res


def _per_period_welfare_per_cell(dist_pol, dist_aGrid,
                                 cFuncs_pol, cFuncs_none, cFuncs_base_emb,
                                 IncShkDstn_pol, IncShkDstn_none,
                                 IncShkDstn_base_emb,
                                 micro_trans_pol, J_base,
                                 Rfree_pol, Rfree_base,
                                 PermGroFac_pol, PermGroFac_base,
                                 Splurge, CRRA,
                                 Cratio_pol=1.0, Cratio_none=1.0,
                                 Cratio_base=1.0,
                                 AggDemandFac_pol=1.0,
                                 AggDemandFac_none=1.0,
                                 AggDemandFac_base=1.0,
                                 TranShk_addition_pol=None,
                                 TranShk_addition_none=None,
                                 TranShk_addition_base=None,
                                 none_J=None,
                                 none_Rfree=None,
                                 none_PermGroFac=None):
    """Compute per-period welfare numerator via per-cell evaluation.

    At each (j_pol, a) cell of pol distribution, integrate over destination
    j_pol_dest and shock realization (psi, xi). For each realized shock,
    compute c_pol_actual / c_none_actual / c_base_actual (with base embedded
    to base's micro-state space via j_pol_dest % J_base) and the per-cell
    integrand (u(c_pol) - u(c_none)) / u'(c_base). Accumulate weighted sum.

    Returns the cohort-level normalized welfare numerator (without N or pLvl
    scaling — the caller applies those).
    """
    A = len(dist_aGrid)
    J = micro_trans_pol.shape[0]
    rho = float(CRRA)
    dist_2d = np.asarray(dist_pol).reshape(J, A)
    if none_J is None:
        none_J = J  # default: same size as pol
    if none_Rfree is None:
        none_Rfree = Rfree_pol
    if none_PermGroFac is None:
        none_PermGroFac = PermGroFac_pol

    if TranShk_addition_pol is None:
        TranShk_addition_pol = np.zeros(J)
    if TranShk_addition_none is None:
        TranShk_addition_none = np.zeros(none_J)
    if TranShk_addition_base is None:
        TranShk_addition_base = np.zeros(J_base)

    welfare_acc = 0.0

    for j in range(J):
        d_j = dist_2d[j, :]
        if d_j.sum() <= 0.0:
            continue
        for jp in range(J):
            trans_pol = micro_trans_pol[j, jp]
            if trans_pol < 1e-15:
                continue
            jp_base = jp % J_base
            jp_none = jp % none_J  # embed pol's destination into none's space

            dstn_pol = IncShkDstn_pol[jp]
            dstn_none = IncShkDstn_none[jp_none]
            dstn_base = IncShkDstn_base_emb[jp_base]

            psi = dstn_pol.atoms[0]
            xi_pol = dstn_pol.atoms[1]
            pmv = dstn_pol.pmv
            n_atoms = len(pmv)

            # If atom counts differ across scenarios, skip (alignment failure).
            # In HAFiscal under default psdu=off, employed states have ~7 atoms
            # uniformly and unemployed states have 1 atom uniformly; the
            # micro-state embedding (jp % 4) preserves employment status, so
            # alignment should hold.
            if (len(dstn_none.pmv) != n_atoms or
                    len(dstn_base.pmv) != n_atoms):
                continue

            # POL c_actual
            xi_eff_pol = AggDemandFac_pol * xi_pol + TranShk_addition_pol[jp]
            inv_pG_pol = 1.0 / (psi * PermGroFac_pol[jp])
            m_next_pol = (Rfree_pol[jp] * dist_aGrid)[:, None] \
                * inv_pG_pol[None, :] + xi_eff_pol[None, :]
            c_star_pol = cFuncs_pol[jp](
                m_next_pol.ravel(),
                np.full_like(m_next_pol.ravel(), Cratio_pol)
            ).reshape(A, n_atoms)
            c_actual_pol = ((1.0 - Splurge) * c_star_pol
                            + Splurge * xi_eff_pol[None, :])

            # NONE c_actual: embedded micro state if needed
            xi_none = dstn_none.atoms[1]
            xi_eff_none = AggDemandFac_none * xi_none \
                + TranShk_addition_none[jp_none]
            # Use NONE's PermGroFac (typically same as pol's at the same
            # employment status under CRN) and Rfree.
            inv_pG_none = 1.0 / (psi * none_PermGroFac[jp_none])
            m_next_none = (none_Rfree[jp_none] * dist_aGrid)[:, None] \
                * inv_pG_none[None, :] + xi_eff_none[None, :]
            c_star_none = cFuncs_none[jp_none](
                m_next_none.ravel(),
                np.full_like(m_next_none.ravel(), Cratio_none)
            ).reshape(A, n_atoms)
            c_actual_none = ((1.0 - Splurge) * c_star_none
                             + Splurge * xi_eff_none[None, :])

            # BASE c_actual: embedded micro state, base's PermGroFac/Rfree
            xi_base = dstn_base.atoms[1]
            xi_eff_base = AggDemandFac_base * xi_base \
                + TranShk_addition_base[jp_base]
            inv_pG_base = 1.0 / (psi * PermGroFac_base[jp_base])
            m_next_base = (Rfree_base[jp_base] * dist_aGrid)[:, None] \
                * inv_pG_base[None, :] + xi_eff_base[None, :]
            c_star_base = cFuncs_base_emb[jp_base](
                m_next_base.ravel(),
                np.full_like(m_next_base.ravel(), Cratio_base)
            ).reshape(A, n_atoms)
            c_actual_base = ((1.0 - Splurge) * c_star_base
                             + Splurge * xi_eff_base[None, :])

            # Per-cell integrand
            c_safe_pol = np.maximum(c_actual_pol, 1e-16)
            c_safe_none = np.maximum(c_actual_none, 1e-16)
            c_safe_base = np.maximum(c_actual_base, 1e-16)
            if abs(rho - 1.0) < 1e-12:
                u_pol = np.log(c_safe_pol)
                u_none = np.log(c_safe_none)
            else:
                u_pol = c_safe_pol ** (1.0 - rho) / (1.0 - rho)
                u_none = c_safe_none ** (1.0 - rho) / (1.0 - rho)
            mu_inv_base = c_safe_base ** rho  # = 1/u'(c_base)
            integrand = (u_pol - u_none) * mu_inv_base

            weights = d_j[:, None] * (trans_pol * pmv[None, :])
            welfare_acc += float(np.sum(weights * integrand))

    return welfare_acc


def run_scenario_tm_full_capture(ctx, base_baseline_tm_data, shock_type,
                                  neutral_measure=True, verbose=True,
                                  AggCons_baseline_for_AD=None):
    """Solve scenario, capture per-cohort agent state + per-cohort per-duration
    series for use in per-cell welfare evaluation.

    For AD scenarios (shock_type ending in '_AD'): trains CFunc beliefs via
    run_ad_tm Phase 1 once, then per-duration Cratio paths are derived from
    CFunc forward propagation (Phase 2 mechanism). Requires
    AggCons_baseline_for_AD (the TM-a base scenario's AggCons trajectory).

    Returns dict with keys including 'per_cohort_agent_state' (cFunc/IncShkDstn
    refs needed for per-cell evaluation) and 'per_cohort_per_dur' (per-cohort
    list of duration-specific results: dist NOT propagated, just AggCons/Income
    series and EconomyMrkv path) for averaging.
    """
    is_base_scenario = (shock_type == "base")
    is_ad = shock_type.endswith("_AD")

    AggEco = deepcopy(ctx["AggEco"])
    if is_base_scenario:
        AggEco.switch_shock_type("base")
    else:
        AggEco.switch_shock_type(
            shock_type[:-3] if shock_type.endswith("_AD") else shock_type
        )
    AggEco.solve()
    for ag in AggEco.agents:
        ag.tm_a_indexed = True

    bd_list = base_baseline_tm_data
    act_T = ctx["act_T"]
    nep = ctx["num_experiment_periods"]
    is_check = shock_type in ("Check", "recessionCheck",
                              "recessionCheck_AD")
    is_rec = "recession" in shock_type

    if is_rec:
        max_dur = ctx.get("max_recession_duration", nep)
        rspell = ctx.get("Rspell", 4.0)
        R_persist = 1.0 - 1.0 / rspell
        rec_probs = np.array([R_persist**t * (1 - R_persist)
                              for t in range(max_dur)])
        rec_probs[-1] = 1.0 - np.sum(rec_probs[:-1])
        durations = list(range(1, max_dur + 1))
    else:
        durations = [None]
        rec_probs = np.array([1.0])

    # AD: train CFunc beliefs once via run_ad_tm Phase 1
    if is_ad:
        if AggCons_baseline_for_AD is None:
            raise ValueError(
                f"shock_type={shock_type} requires AggCons_baseline_for_AD "
                f"(call with the TM-a base scenario's AggCons trajectory)")
        from tm_methods import run_ad_tm
        AggEco.ADelasticity = getattr(AggEco, 'demand_ADelasticity', 0.3)
        placeholder = list(np.arange(1, nep + 1) * 2 + 1) + [1]*12 + [0]*20
        placeholder = placeholder[:act_T]
        _ = run_ad_tm(
            AggEco, shock_type[:-3], placeholder,
            bd_list, np.asarray(AggCons_baseline_for_AD),
            ADelasticity=AggEco.ADelasticity,
            num_max_iterations=10, convergence_tol=0.004,
            neutral_measure=neutral_measure, verbose=verbose,
            skip_training=False)
        if verbose:
            print(f"  [{shock_type}] CFunc trained for AD")

    n_cohorts = len(AggEco.agents)
    per_cohort_per_dur = [[] for _ in range(n_cohorts)]
    AggCons_total = np.zeros(act_T)
    AggIncome_total = np.zeros(act_T)

    for d_idx, dur in enumerate(durations):
        path = _build_econ_mrkv_path(act_T, nep, is_rec, dur,
                                     is_base=is_base_scenario)
        # Derive Cratio path: 1.0 for non-AD, CFunc-propagated for AD
        if is_ad:
            J = AggEco.num_base_MrkvStates
            CFunc = AggEco.CFunc
            Cratio_path = np.ones(act_T)
            m0 = path[0] if 0 < len(path) else 0
            Cratio_path[0] = CFunc[0][m0 * J].intercept
            for t in range(act_T - 1):
                m_now = path[t] if t < len(path) else 0
                m_next = path[t + 1] if t + 1 < len(path) else 0
                Cratio_path[t + 1] = CFunc[m_now * J][m_next * J](Cratio_path[t])
            Cratio_to_pass = Cratio_path
        else:
            Cratio_to_pass = 1.0
        if verbose:
            print(f"  [{shock_type}] duration={dur}, prob={rec_probs[d_idx]:.4f}, "
                  f"path[:6]={path[:6]}")
        for i, agent in enumerate(AggEco.agents):
            bd = bd_list[i]
            res = _propagate_one(
                agent, bd, path,
                shock_type[:-3] if shock_type.endswith("_AD") else shock_type,
                Cratio=Cratio_to_pass, act_T=act_T,
                is_check=is_check, neutral_measure=neutral_measure)
            per_cohort_per_dur[i].append({
                'duration': dur,
                'rec_prob': float(rec_probs[d_idx]),
                'AggCons': res['AggCons'],
                'AggIncome': res['AggIncome'],
                'U_nrm_series': res['U_nrm_series'],
                'MU_inv_nrm_series': res['MU_inv_nrm_series'],
                'pLvl_factor_series': res['pLvl_factor_series'],
                'dist_series': res.get('dist_series', None),
                'EconomyMrkv_init': path,
                # Per-Markov-state series for stratified rep-agent (Path B)
                'C_splurge_per_jp_series': res.get('C_splurge_per_jp_series'),
                'Income_per_jp_series': res.get('Income_per_jp_series'),
                'U_per_jp_series': res.get('U_per_jp_series'),
                'MU_inv_per_jp_series': res.get('MU_inv_per_jp_series'),
                'state_fracs_dest_series': res.get('state_fracs_dest_series'),
                'J_micro': res.get('J_micro'),
                # Per-bucket welfare series (Check progressivity)
                'bucket_welfare_series': res.get('bucket_welfare_series'),
            })
            AggCons_total += rec_probs[d_idx] * res['AggCons']
            AggIncome_total += rec_probs[d_idx] * res['AggIncome']

    # Capture per-cohort agent state for per-cell welfare evaluation.
    per_cohort_agent_state = []
    for i, agent in enumerate(AggEco.agents):
        per_cohort_agent_state.append({
            'cFunc_list': agent.solution[0].cFunc,
            'IncShkDstn_list': agent.IncShkDstn[0],
            'CondMrkvArrays': agent.CondMrkvArrays,
            'PermGroFac': np.asarray(agent.PermGroFac[0], dtype=np.float64),
            'Rfree': np.asarray(agent.Rfree, dtype=np.float64),
            'Splurge': float(agent.Splurge),
            'CRRA': float(agent.CRRA),
            'num_base_MrkvStates': int(agent.num_base_MrkvStates),
            'AgentCount': int(agent.AgentCount),
            'pop_rescale_factor': getattr(agent, 'pop_rescale_factor', 1.0),
            'E_pLvl_init': float(bd_list[i]['E_pLvl']),
            'dist_aGrid': bd_list[i]['dist_aGrid'],
            'baseline_ergodic': bd_list[i]['ergodic'],
        })

    return {
        'shock_type': shock_type,
        'per_cohort_agent_state': per_cohort_agent_state,
        'per_cohort_per_dur': per_cohort_per_dur,
        'rec_probs': rec_probs,
        'durations': durations,
        'AggCons': AggCons_total,
        'AggIncome': AggIncome_total,
        'act_T': act_T,
        'Rfree': ctx['Rfree'],
        'is_base': is_base_scenario,
        'is_rec': is_rec,
        'is_AD': shock_type.endswith('_AD'),
        'is_check': is_check,
    }


def run_scenario_tm_welfare(ctx, baseline_tm_data, shock_type,
                            neutral_measure=True, verbose=True,
                            AggCons_baseline_for_AD=None):
    """Run one scenario with welfare extraction.

    For recession scenarios, averages across recession durations using
    the recession_prob_array (matching production Simulate.py logic).

    For AD scenarios (shock_type ending in '_AD'): trains CFunc beliefs via
    run_ad_tm Phase 1 once, then per-duration Phase 2 computes the
    CFunc-propagated Cratio path which is passed to _propagate_one.

    `AggCons_baseline_for_AD` is required when shock_type ends in '_AD'
    (caller must pre-compute the TM-a base-scenario AggCons trajectory).
    """
    is_base_scenario = (shock_type == "base")

    AggEco = deepcopy(ctx["AggEco"])
    # Switch to the appropriate shock type. AD scenarios use the same Markov
    # state space as their non-AD counterparts (e.g., recessionCheck_AD →
    # recessionCheck), differing only in Cratio path during propagation.
    if is_base_scenario:
        AggEco.switch_shock_type("base")
    else:
        AggEco.switch_shock_type(
            shock_type[:-3] if shock_type.endswith("_AD") else shock_type
        )
    AggEco.solve()
    # Reset welfare-relevant agent attrs after solve.
    for ag in AggEco.agents:
        ag.tm_a_indexed = True

    # Use the BASE baseline_tm_data (passed in, not recomputed under this
    # scenario's MrkvArray). The starting ergodic is always the base economy's
    # no-recession steady state — matches Simulate.py production behavior.
    bd_list = baseline_tm_data

    act_T = ctx["act_T"]
    nep = ctx["num_experiment_periods"]
    is_check = ("Check" in shock_type) and ("recession" in shock_type or
                                            shock_type == "Check")
    # Fix is_check: only Check / recessionCheck (not _AD variants do checks)
    is_check = shock_type in ("Check", "recessionCheck",
                              "recessionCheck_AD")

    is_rec = "recession" in shock_type
    is_ad = shock_type.endswith("_AD")

    if is_rec:
        # Average across durations weighted by recession_prob_array (matches
        # Simulate.py:631-632).
        max_dur = ctx.get("max_recession_duration", nep)
        rspell = ctx.get("Rspell", 4.0)
        R_persist = 1.0 - 1.0 / rspell
        rec_probs = np.array([R_persist**t * (1 - R_persist)
                              for t in range(max_dur)])
        rec_probs[-1] = 1.0 - np.sum(rec_probs[:-1])  # absorb tail
        # Duration index t corresponds to (t+1)-quarter recession.
        durations = list(range(1, max_dur + 1))
    else:
        durations = [None]  # single non-recession run
        rec_probs = np.array([1.0])

    # Per-cohort accumulators across durations.
    per_cohort_avg = []
    for i in range(len(AggEco.agents)):
        per_cohort_avg.append({
            'U_nrm_series': np.zeros(act_T),
            'MU_inv_nrm_series': np.zeros(act_T),
            'pLvl_factor_series': np.zeros(act_T),
            'AggCons_series': np.zeros(act_T),  # for cross-check
            'AggIncome_series': np.zeros(act_T),
        })
    # Aggregate-across-cohorts series.
    AggCons_total = np.zeros(act_T)
    AggIncome_total = np.zeros(act_T)

    # For AD scenarios: train CFunc beliefs ONCE via run_ad_tm Phase 1,
    # then per-duration Cratio is derived from CFunc forward propagation.
    if is_ad:
        if AggCons_baseline_for_AD is None:
            raise ValueError(f"shock_type={shock_type} requires AggCons_baseline_for_AD")
        from tm_methods import run_ad_tm
        AggEco.ADelasticity = getattr(AggEco, 'demand_ADelasticity', 0.3)
        # Run Phase 1: trains CFunc on worst-case path
        # Use a placeholder EconomyMrkv_init (only Phase 2 uses it; we discard P2 here)
        nep_local = ctx['num_experiment_periods']
        placeholder = list(np.arange(1, nep_local + 1) * 2 + 1) + [1]*12 + [0]*20
        placeholder = placeholder[:act_T]
        _ = run_ad_tm(
            AggEco, shock_type[:-3], placeholder,
            bd_list, AggCons_baseline_for_AD,
            ADelasticity=AggEco.ADelasticity,
            num_max_iterations=10, convergence_tol=0.004,
            neutral_measure=neutral_measure, verbose=verbose,
            skip_training=False)
        if verbose:
            print(f"  [{shock_type}] CFunc trained for AD")
        # AggEco.CFunc now holds AD-converged beliefs.

    for d_idx, dur in enumerate(durations):
        path = _build_econ_mrkv_path(
            act_T, nep, is_rec, dur, is_base=is_base_scenario)
        # Cratio path: 1.0 (no AD) or CFunc-propagated for AD
        if is_ad:
            J = AggEco.num_base_MrkvStates
            CFunc = AggEco.CFunc
            Cratio_path = np.ones(act_T)
            Cratio_path[0] = CFunc[0][path[0] * J].intercept
            for t in range(act_T - 1):
                m_now = path[t]
                m_next = path[t + 1] if t + 1 < len(path) else 0
                Cratio_path[t + 1] = CFunc[m_now * J][m_next * J](Cratio_path[t])
            Cratio_to_pass = Cratio_path
        else:
            Cratio_to_pass = 1.0
        if verbose:
            print(f"  [{shock_type}] duration={dur}, prob={rec_probs[d_idx]:.4f}, "
                  f"path[:6]={path[:6]}")
        for i, agent in enumerate(AggEco.agents):
            bd = bd_list[i]
            res = _propagate_one(
                agent, bd, path, shock_type[:-3] if is_ad else shock_type,
                Cratio=Cratio_to_pass, act_T=act_T,
                is_check=is_check, neutral_measure=neutral_measure)

            w = rec_probs[d_idx]
            per_cohort_avg[i]['U_nrm_series'] += w * res['U_nrm_series']
            per_cohort_avg[i]['MU_inv_nrm_series'] += w * res['MU_inv_nrm_series']
            per_cohort_avg[i]['pLvl_factor_series'] += w * res['pLvl_factor_series']
            per_cohort_avg[i]['AggCons_series'] += w * res['AggCons']
            per_cohort_avg[i]['AggIncome_series'] += w * res['AggIncome']
            # Constants (same across durations).
            per_cohort_avg[i]['welfare_CRRA'] = res['welfare_CRRA']
            per_cohort_avg[i]['E_pLvl_init'] = res['E_pLvl_init']
            per_cohort_avg[i]['AgentCount'] = res['AgentCount']
            per_cohort_avg[i]['pop_rescale_factor'] = getattr(
                agent, 'pop_rescale_factor', 1.0)

            AggCons_total += w * res['AggCons']
            AggIncome_total += w * res['AggIncome']

    # NPV aggregates (cohort-aggregated).
    Rfree = ctx["Rfree"]
    NPV_AggCons = calculate_NPV(AggCons_total, act_T, Rfree)
    NPV_AggIncome = calculate_NPV(AggIncome_total, act_T, Rfree)

    return {
        'shock_type': shock_type,
        'per_cohort': per_cohort_avg,
        'AggCons': AggCons_total,
        'AggIncome': AggIncome_total,
        'NPV_AggCons': NPV_AggCons,
        'NPV_AggIncome': NPV_AggIncome,
        'act_T': act_T,
        'Rfree': Rfree,
    }


def compute_per_cell_welfare_for_cell(scenarios_data, pol_key, none_key,
                                       base_key='base'):
    """Compute per-period welfare numerator series via per-cell evaluation.

    For each cohort, for each period t (averaged over recession durations
    weighted by rec_probs), evaluate per-cell integrand using cFunc_pol,
    cFunc_none, cFunc_base at the same (j, a, psi, xi) cell of pol's
    distribution.

    Returns: per-period welfare numerator series (cohort-aggregated).
    """
    pol = scenarios_data[pol_key]
    none = scenarios_data[none_key]
    base = scenarios_data[base_key]
    if pol is None or none is None or base is None:
        return None

    act_T = pol['act_T']
    n_cohorts = len(pol['per_cohort_agent_state'])
    welfare_num_series = np.zeros(act_T)

    for ell in range(n_cohorts):
        agst_pol = pol['per_cohort_agent_state'][ell]
        agst_none = none['per_cohort_agent_state'][ell]
        agst_base = base['per_cohort_agent_state'][ell]

        N = agst_pol['AgentCount']
        rescale = agst_pol['pop_rescale_factor']
        E_init = agst_pol['E_pLvl_init']
        CRRA = agst_pol['CRRA']
        Splurge = agst_pol['Splurge']
        dist_aGrid = agst_pol['dist_aGrid']
        J_pol = agst_pol['num_base_MrkvStates']
        J_base = agst_base['num_base_MrkvStates']

        # Per-duration loop: weighted average across pol's durations.
        for d_entry in pol['per_cohort_per_dur'][ell]:
            d_prob = d_entry['rec_prob']
            mrkv_path = d_entry['EconomyMrkv_init']
            pLvl_factor_series = d_entry['pLvl_factor_series']
            # Find matching duration entry in 'none' (same path index).
            none_d_entry = None
            for nd in none['per_cohort_per_dur'][ell]:
                if nd['duration'] == d_entry['duration']:
                    none_d_entry = nd
                    break
            # Find base entry (base has only 1 duration entry).
            base_d_entry = base['per_cohort_per_dur'][ell][0]

            dist_series_pol = d_entry.get('dist_series', None)
            if dist_series_pol is None:
                # Fall back to None-duration zero (uninitialized)
                continue

            for t in range(act_T):
                if t >= len(dist_series_pol):
                    continue
                dist_t = dist_series_pol[t]

                macro_t = mrkv_path[t] if t < len(mrkv_path) else 0
                # Pol scenario: cFunc + IncShk at macro_t
                src_offset_pol = macro_t * J_pol
                cFuncs_pol_t = [agst_pol['cFunc_list'][src_offset_pol + j]
                                for j in range(J_pol)]
                IncShkDstn_pol_t = [agst_pol['IncShkDstn_list'][src_offset_pol + j]
                                    for j in range(J_pol)]
                # None scenario: detect state-space size; if same as pol, use
                # macro_t offset; if smaller (e.g., none=base), use macro=0
                # offset and embed via jp % J_none.
                J_none = agst_none['num_base_MrkvStates']
                cFunc_none_total_len = len(agst_none['cFunc_list'])
                if cFunc_none_total_len >= src_offset_pol + J_pol:
                    # Same Markov structure; use the same offset.
                    cFuncs_none_t = [agst_none['cFunc_list'][src_offset_pol + j]
                                     for j in range(J_pol)]
                    IncShkDstn_none_t = [agst_none['IncShkDstn_list'][src_offset_pol + j]
                                         for j in range(J_pol)]
                    # Use as-is (length J_pol).
                    none_emb_lookup = lambda jp: jp
                else:
                    # Smaller state space (none=base typically); embed jp → jp % J_none.
                    cFuncs_none_t = [agst_none['cFunc_list'][j] for j in range(J_none)]
                    IncShkDstn_none_t = [agst_none['IncShkDstn_list'][j] for j in range(J_none)]
                    # Caller will embed jp % J_none in the per-cell function.
                # Base: macro=0 always (base has no recession), state space J_base.
                cFuncs_base_emb = [agst_base['cFunc_list'][j]
                                   for j in range(J_base)]
                IncShkDstn_base_emb = [agst_base['IncShkDstn_list'][j]
                                       for j in range(J_base)]

                # micro_trans for pol at this period
                micro_trans_pol = agst_pol['CondMrkvArrays'][macro_t]
                Rfree_pol_arr = agst_pol['Rfree'][:J_pol]
                PermGroFac_pol_arr = agst_pol['PermGroFac'][:J_pol]
                Rfree_base_arr = agst_base['Rfree'][:J_base]
                PermGroFac_base_arr = agst_base['PermGroFac'][:J_base]
                Rfree_none_arr = agst_none['Rfree'][:J_pol if cFunc_none_total_len >= src_offset_pol + J_pol else J_none]
                PermGroFac_none_arr = agst_none['PermGroFac'][:J_pol if cFunc_none_total_len >= src_offset_pol + J_pol else J_none]

                cell_welfare_norm = _per_period_welfare_per_cell(
                    dist_t, dist_aGrid,
                    cFuncs_pol_t, cFuncs_none_t, cFuncs_base_emb,
                    IncShkDstn_pol_t, IncShkDstn_none_t, IncShkDstn_base_emb,
                    micro_trans_pol, J_base,
                    Rfree_pol_arr, Rfree_base_arr,
                    PermGroFac_pol_arr, PermGroFac_base_arr,
                    Splurge, CRRA,
                    none_J=len(cFuncs_none_t),
                    none_Rfree=Rfree_none_arr,
                    none_PermGroFac=PermGroFac_none_arr)

                contrib = (N * rescale * E_init * pLvl_factor_series[t]
                           * cell_welfare_norm)
                welfare_num_series[t] += d_prob * contrib

    return welfare_num_series


def compute_welfare6_cells_per_cell(scenarios_data):
    """Compute the 9 welfare-6 cells via per-cell evaluation."""
    Rfree = scenarios_data['base']['Rfree']
    act_T = scenarios_data['base']['act_T']

    def _npv(scen_key, agg_key):
        scen = scenarios_data.get(scen_key)
        if scen is None:
            return float('nan')
        return float(np.sum(scen[agg_key][:act_T] / (Rfree ** np.arange(act_T))))

    def _w_cell(pol_key, none_key, cost_pol_key=None, cost_none_key=None):
        if cost_pol_key is None:
            cost_pol_key = pol_key
        if cost_none_key is None:
            cost_none_key = none_key
        if scenarios_data.get(pol_key) is None or scenarios_data.get(none_key) is None:
            return float('nan')
        wn_series = compute_per_cell_welfare_for_cell(scenarios_data, pol_key, none_key)
        if wn_series is None:
            return float('nan')
        NPV_num = float(np.sum(wn_series[:act_T] / (Rfree ** np.arange(act_T))))
        NPV_AddInc = _npv(cost_pol_key, 'AggIncome') - _npv(cost_none_key, 'AggIncome')
        NPV_AddCons = _npv(cost_pol_key, 'AggCons') - _npv(cost_none_key, 'AggCons')
        if abs(NPV_AddInc) < 1e-10:
            return float('nan')
        return NPV_num / NPV_AddInc + (NPV_AddInc - NPV_AddCons) / NPV_AddInc

    return {
        'check_norec': _w_cell('Check', 'base'),
        'ui_norec': _w_cell('UI', 'base'),
        'taxcut_norec': _w_cell('TaxCut', 'base'),
        'check_rec': _w_cell('recessionCheck', 'recession'),
        'ui_rec': _w_cell('recessionUI', 'recession'),
        'taxcut_rec': _w_cell('recessionTaxCut', 'recession'),
        'check_rec_AD': _w_cell('recessionCheck_AD', 'recession_AD',
                                'recessionCheck', 'recession'),
        'ui_rec_AD': _w_cell('recessionUI_AD', 'recession_AD',
                             'recessionUI', 'recession'),
        'taxcut_rec_AD': _w_cell('recessionTaxCut_AD', 'recession_AD',
                                 'recessionTaxCut', 'recession'),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parametrization", default="Reduced_Run")
    p.add_argument("--baseline", action="store_true",
                   help="Alias for --parametrization Baseline")
    p.add_argument("--out-pickle", required=True,
                   help="Where to save per-scenario welfare moments")
    p.add_argument("--table-dir", default=None,
                   help="Where to write welfare6 table (.tex/.csv)")
    p.add_argument("--scenarios", default=None,
                   help="Comma-separated subset (default: all 12)")
    p.add_argument("--no-ad", action="store_true",
                   help="Skip AD scenarios (faster prototype)")
    args = p.parse_args()

    parametrization = "Baseline" if args.baseline else args.parametrization
    scenarios = (args.scenarios.split(",") if args.scenarios
                 else list(ALL_SCENARIOS))
    if args.no_ad:
        scenarios = [s for s in scenarios if not s.endswith("_AD")]

    print(f"=== welfare6_tm: parametrization={parametrization} ===")
    print(f"Scenarios: {scenarios}")

    t0 = time.time()
    print("Building economy...")
    ctx = build_and_solve(parametrization)
    print(f"  {len(ctx['AggEco'].agents)} cohorts, "
          f"act_T={ctx['act_T']}, "
          f"num_experiment_periods={ctx['num_experiment_periods']}")
    for ag in ctx['AggEco'].agents:
        print(f"  agent: has solution? {hasattr(ag, 'solution')}; "
              f"len(solution)={len(ag.solution) if hasattr(ag, 'solution') else 'N/A'}")
        break
    # Set tm_a_indexed on every cohort, then re-solve under base shock type
    # (build_and_solve solves once but then switch_to_counterfactual_mode
    # may have invalidated the solution).
    for ag in ctx['AggEco'].agents:
        ag.tm_a_indexed = True
    print("Re-solving under base shock_type with tm_a_indexed=True...")
    ctx['AggEco'].switch_shock_type('base')
    ctx['AggEco'].solve()
    for ag in ctx['AggEco'].agents:
        print(f"  agent: has solution? {hasattr(ag, 'solution')}; "
              f"len(solution)={len(ag.solution) if hasattr(ag, 'solution') else 'N/A'}")
        break
    print(f"Setup wall: {time.time() - t0:.1f}s")

    # Build initial baseline_tm_data for the BASE scenario (used by
    # all scenarios as starting ergodic).
    aCount = int(os.environ.get("HAFISCAL_TM_MCOUNT", 100))
    print(f"Computing baseline_tm_data (mCount={aCount})...")
    t1 = time.time()
    initial_bd = compute_baseline_tm_data(ctx['AggEco'], mCount=aCount)
    print(f"  done in {time.time() - t1:.1f}s")

    # Run each scenario, capturing full agent state + per-period moments.
    # Order matters: run 'base' first so AD scenarios can use its AggCons trajectory
    # as the baseline for run_ad_tm's CFunc training. Then non-AD scenarios. Then AD.
    scenarios_sorted = sorted(scenarios,
        key=lambda s: (s != 'base', s.endswith('_AD'), s))
    all_results = {}
    AggCons_baseline = None  # filled from 'base' run, used for AD training
    for shock_type in scenarios_sorted:
        t_s = time.time()
        print(f"--- Scenario: {shock_type} ---")
        try:
            kwargs = {}
            if shock_type.endswith('_AD'):
                if AggCons_baseline is None:
                    raise RuntimeError(
                        f"{shock_type} needs base AggCons; ensure 'base' runs first")
                kwargs['AggCons_baseline_for_AD'] = AggCons_baseline
            res = run_scenario_tm_full_capture(
                ctx, initial_bd, shock_type,
                neutral_measure=True, verbose=True, **kwargs)
            all_results[shock_type] = res
            if shock_type == 'base' and res is not None:
                AggCons_baseline = np.asarray(res['AggCons'])
                print(f"  captured base AggCons (shape {AggCons_baseline.shape}) for AD training")
            print(f"  {shock_type} OK in {time.time() - t_s:.1f}s")
        except Exception as e:
            import traceback
            print(f"  {shock_type} FAILED: {e}")
            traceback.print_exc()
            all_results[shock_type] = None

    # Compute welfare-6 cells via per-cell evaluation (research approach).
    print(f"\n=== Computing welfare-6 cells (per-cell evaluation) ===")
    t_w = time.time()
    cells_percell = compute_welfare6_cells_per_cell(all_results)
    print(f"  done in {time.time() - t_w:.1f}s")
    print(f"\n{'Cell':<22} {'percell':>12}")
    for k, v in cells_percell.items():
        v_s = 'NaN' if np.isnan(v) else f"{v:.4f}"
        print(f"{k:<22} {v_s:>12}")

    # Compute welfare-6 cells via stratified rep-agent (Path B).
    from welfare6_tm_stratified import compute_welfare6_cells_stratified
    print(f"\n=== Computing welfare-6 cells (stratified rep-agent — Path B) ===")
    t_w = time.time()
    cells_strat = compute_welfare6_cells_stratified(all_results)
    print(f"  done in {time.time() - t_w:.1f}s")
    print(f"{'Cell':<22} {'stratified':>12}")
    for k, v in cells_strat.items():
        v_s = 'NaN' if np.isnan(v) else f"{v:.4f}"
        print(f"{k:<22} {v_s:>12}")

    # Compute welfare-6 cells via BUCKET-AWARE aggregator (per-bucket Check).
    from welfare6_tm_bucket import compute_welfare6_cells_bucket
    print(f"\n=== Computing welfare-6 cells (bucket-aware) ===")
    t_w = time.time()
    cells_bucket = compute_welfare6_cells_bucket(all_results)
    print(f"  done in {time.time() - t_w:.1f}s")
    print(f"{'Cell':<22} {'bucket':>12}")
    for k, v in cells_bucket.items():
        v_s = 'NaN' if np.isnan(v) else f"{v:.4f}"
        print(f"{k:<22} {v_s:>12}")
    cells = cells_bucket  # primary

    # Save per-scenario data + cells.
    # Note: the all_results dict contains cFunc / IncShkDstn references which
    # are NOT picklable. So we save a "compute summary" only.
    print(f"\nSaving pickle to {args.out_pickle}...")
    os.makedirs(os.path.dirname(os.path.abspath(args.out_pickle)) or ".",
                exist_ok=True)
    # Build a picklable subset (drop non-picklable items like cFunc references)
    picklable_results = {}
    for k, v in all_results.items():
        if v is None:
            picklable_results[k] = None
            continue
        picklable_results[k] = {
            'shock_type': v['shock_type'],
            'AggCons': v['AggCons'],
            'AggIncome': v['AggIncome'],
            'act_T': v['act_T'],
            'Rfree': v['Rfree'],
            'is_base': v['is_base'],
            'is_rec': v['is_rec'],
            'is_AD': v['is_AD'],
            'is_check': v['is_check'],
            # Drop per_cohort_agent_state (cFunc refs) and per_cohort_per_dur
            # (dist_series can be large, but keep for the aggregator.)
        }
    # Add stratified welfare cells to the pickle.
    with open(args.out_pickle, "wb") as f:
        pickle.dump({
            'welfare6_cells_percell': cells_percell,
            'welfare6_cells_stratified': cells_strat,
            'welfare6_cells_bucket': cells_bucket,
            'parametrization': parametrization,
            'scenarios': scenarios,
            'results_summary': picklable_results,
            'welfare6_cells': cells,
            'ctx_summary': {
                'act_T': ctx['act_T'],
                'num_experiment_periods': ctx['num_experiment_periods'],
                'CRRA': ctx['CRRA'],
                'Rfree': ctx['Rfree'],
                'Rspell': ctx['Rspell'],
                'n_cohorts': len(ctx['AggEco'].agents),
            },
        }, f)
    print(f"Total wall: {(time.time() - t0)/60:.2f} min")
    print(f"Saved {len([r for r in all_results.values() if r is not None])}/"
          f"{len(scenarios)} scenarios + welfare cells")


if __name__ == "__main__":
    main()
