#!/usr/bin/env python3
"""
Verify four-way agreement (Harmenberg notebook framing) for a single education
type and baseline ('base') shock:

  (A) MC — physical measure P: ``AggCons`` from ``run_experiment``
  (B) MC — Harmenberg Q reconstruction: ``AggCons_Q`` (same run as A if dual agent)
  (C) TM — 2D transition matrix under P: ``run_experiment_tm(..., neutral_measure=False)``
  (D) TM — 1D TM under neutral Q: ``run_experiment_tm(..., neutral_measure=True)``

For a stationary baseline, ``AggCons`` is flat in (C) and (D); for (A)/(B) we
compare the time-series mean to (C)/(D). **All consumption comparisons use
mean aggregate consumption per capita** (period mean of economy ``AggCons``
divided by ``AgentCount``), so reported levels do not scale with population
size. Relative tolerances are unchanged (numerator and denominator share the
same scale factor). MC noise scales ~ 1/sqrt(N); default ``--agents`` is
40,000. TM-initialized **burn-in** defaults to **24** inner
``sim_one_period`` steps after drawing the TM ergodic cross-section (see
``--warmup``).

After the four-way table, the script prints a **TM init stability** block: it
tracks mean ``mNrm``, mean ``pLvl``, and the employed share across early
experiment periods. Large jumps right after ``t=0`` would suggest the restored
state (``save_state`` / ``use_prestate`` / ``restore_state``) is not a good
match to short-run dynamics. Use ``--no-diagnose-init`` to hide it.

**Marginal utility / welfare (paper-facing):** A second table compares
cross-sectional **mean marginal utility** ``E[u'(cLvl_splurge)]`` with
``u'(c)=c^{-CRRA}`` (same object as ``base_MU`` in ``Welfare.py``) across
**MC-P, MC-Q, TM-P, TM-Q**. TM values **do not** add a ``pLvl`` grid to the
Markov chain: states remain ``(m,j)`` on ``mCount`` (see ``build_tm_agg_fiscal``).
TM expectations for ``E[u']`` and ``E[u(c)]`` use the **covariance kernel**
(``tm_methods.compute_kernels``) on ``(m,j)`` with the same marginal for ``pLvl``
from ``compute_pLvl_distribution`` (approximate ``p_{t-1}``–``a`` independence;
see ``TM_MC_Marginal_Utility_Convergence_revised.ipynb`` §3). The older
product-measure TM shortcut (``mean_marginal_utility_tm_independent_p``) is
retained for diagnostics only. For **full** joint ``(p,m)`` welfare objects,
see BST ``ApndxHarKmenberg`` *When the Joint Distribution Is Required* and
``history/20260331-mathematical-derivations-harmenberg.md`` §13.

References:
  Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb
  history/20260331-mathematical-derivations-harmenberg.md (neutral identity)

Examples:
  cd Code/HA-Models/FromPandemicCode && python verify_four_methods_agreement.py
  python verify_four_methods_agreement.py --m-count 100 --rtol 0.02
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import warnings
from copy import deepcopy

warnings.filterwarnings("ignore")

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_HA_MODELS_DIR = os.path.dirname(_THIS_DIR)
if _HA_MODELS_DIR not in sys.path:
    sys.path.insert(0, _HA_MODELS_DIR)

_orig_argv = sys.argv[:]
sys.argv = [sys.argv[0], "1.01", "2.0", "0.7"]

import numpy as np

from income_process_sst import (
    build_unemployed_inc_shk_dstn,
    effective_perm_shock_periods_for_t_age,
    effective_pLvl_growth,
)
from Parameters import return_parameters
from tm_methods import (
    _to_neutral_measure,
    compute_baseline_tm_data,
    compute_kernels,
    compute_pLvl_distribution,
    compute_pLvl_distribution_Q,
    find_ergodic_distribution,
    run_experiment_tm,
    unemployment_rate_for_tm_synthetic_pLvl,
)

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy

try:
    from AggFiscalModel import DualAggFiscalType

    HAS_DUAL = True
except ImportError:
    HAS_DUAL = False

sys.argv = _orig_argv

_EDUC_INDEX = {"dropout": 0, "highschool": 1, "college": 2}


def _build_single_type_economy(
    educ: str = "highschool",
    agent_count: int = 8000,
    seed: int = 42,
    act_T: int = 100,
    agent_cls: type = AggFiscalType,
):
    educ = educ.lower()
    if educ not in _EDUC_INDEX:
        raise ValueError(f"educ must be one of {list(_EDUC_INDEX)}, got {educ!r}")

    params = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
    (
        init_dropout,
        init_highschool,
        init_college,
        init_ADEconomy,
        DiscFacDstns,
        DiscFacCount,
        _AgentCountTotal,
        base_dict,
        _num_max_iterations_solvingAD,
        _convergence_tol_solvingAD,
        UBspell_normal,
        num_base_MrkvStates,
        _data_EducShares,
        _max_recession_duration,
        num_experiment_periods,
        _recession_changes,
        _UI_changes,
        _recession_UI_changes,
        _TaxCut_changes,
        _recession_TaxCut_changes,
        _Check_changes,
        _recession_Check_changes,
    ) = params

    init_map = (init_dropout, init_highschool, init_college)
    e_idx = _EDUC_INDEX[educ]
    init_dict = init_map[e_idx]

    init_AD = deepcopy(init_ADEconomy)
    init_AD["act_T"] = int(act_T)

    BaseType = agent_cls(**init_dict)
    BaseType.cycles = 0
    BaseType.AgentCount = int(agent_count)
    BaseType.seed = int(seed)
    BaseType.DiscFac = DiscFacDstns[e_idx].atoms[0][0]

    economy = AggregateDemandEconomy(**init_AD)
    BaseType.get_economy_data(economy)

    _p0 = BaseType.IncShkDstn[0]
    if isinstance(_p0, (list, tuple)):
        for _d in _p0:
            _d.seed = 763607780
            _d.reset()
    else:
        _p0.seed = 763607780
        _p0.reset()

    emp_src = _p0[0] if isinstance(_p0, (list, tuple)) else _p0
    emp0 = emp_src
    p_on = getattr(BaseType, "perm_shocks_during_unemployment", False)
    t_on = getattr(BaseType, "tran_shocks_during_unemployment", False)
    IncShkDstn_unemp = build_unemployed_inc_shk_dstn(
        emp0, BaseType.IncUnemp, p_on, t_on
    )
    IncShkDstn_unemp_nobenefits = build_unemployed_inc_shk_dstn(
        emp0, BaseType.IncUnempNoBenefits, p_on, t_on
    )
    IncShkDstn_unemp.seed = 763607780
    IncShkDstn_unemp.reset()
    IncShkDstn_unemp_nobenefits.seed = 763607780
    IncShkDstn_unemp_nobenefits.reset()

    EmployedIncShkDstn = deepcopy(emp_src)
    BaseType.IncShkDstn = [
        [emp_src]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]
    ]
    BaseType.IncShkDstn_base = BaseType.IncShkDstn
    IncShkDstn_recession = [BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
    BaseType.IncShkDstn_recession = IncShkDstn_recession
    BaseType.IncShkDstn_recessionUI = IncShkDstn_recession

    EmployedIncShkDstn.atoms[0][1] = EmployedIncShkDstn.atoms[0][1] * BaseType.TaxCutIncFactor
    TaxCutStatesIncShkDstn = (
        [EmployedIncShkDstn]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]
    )
    IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
    for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
        IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
    BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
    BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

    if HAS_DUAL and isinstance(BaseType, DualAggFiscalType):
        BaseType.setup_Q_measure()

    economy.agents = [BaseType]
    return economy, base_dict


def _mc_burnin_tm_init(
    economy,
    warmup: int,
    neutral_measure: bool,
    use_dual: bool,
    record_trace: bool = False,
):
    """Burn-in with optional TM-ergodic initialization (matches test_asymptotic_equality_revised).

    If ``record_trace`` is True, returns a dict with arrays keyed by ``step`` (0 = after TM draw,
    before first ``sim_one_period``; then one row per inner burn-in step) and cross-section
    summaries from ``_burnin_cross_section_snapshot``. Otherwise returns ``None``.
    """
    tm_data = compute_baseline_tm_data(
        economy, mCount=50, neutral_measure=neutral_measure, verbose=False
    )
    economy.reset()
    for agent in economy.agents:
        agent.initialize_sim()
        agent.AggDemandFac = 1.0
        agent.RfreeNow = 1.0
        agent.CaggNow = 1.0

    for i, agent in enumerate(economy.agents):
        bd_i = tm_data[i]
        erg = bd_i.get("cohort_ergodic", bd_i.get("ergodic"))
        grid = bd_i["dist_mGrid"]
        J_i = agent.num_base_MrkvStates

        rng_i = np.random.RandomState(agent.seed)
        N_i = agent.AgentCount
        flat_probs = erg / np.sum(erg)

        bins = rng_i.choice(len(flat_probs), size=N_i, p=flat_probs)
        M_i = len(grid)
        agent_j = bins // M_i
        agent_mNrm = grid[bins % M_i]

        sol_i = agent.solution[0]
        agent_aNrm = np.zeros(N_i)
        for j in range(J_i):
            mask = agent_j == j
            if np.any(mask):
                c = sol_i.cFunc[j](agent_mNrm[mask], np.ones(np.sum(mask)))
                agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - c, 0.0)

        L = agent.LivPrb[0][0]
        T_ag = agent.T_age
        age_probs = np.array([L ** (k - 1) for k in range(1, T_ag + 1)])
        age_probs /= np.sum(age_probs)
        agent_ages = rng_i.choice(T_ag, size=N_i, p=age_probs) + 1

        pLogMean = agent.pLogInitMean
        pLogStd = getattr(agent, "pLogInitStd", getattr(agent, "pLvlInitStd", 0.0))
        PermShkDstn_0 = agent.IncShkDstn_base[0][0]
        log_ps = np.log(PermShkDstn_0.atoms[0])
        ps_var = np.dot(PermShkDstn_0.pmv, log_ps**2) - np.dot(
            PermShkDstn_0.pmv, log_ps
        ) ** 2
        u_p = unemployment_rate_for_tm_synthetic_pLvl(bd_i, agent)
        g_lvl = effective_pLvl_growth(agent, u_p)
        effective_emp_periods = effective_perm_shock_periods_for_t_age(
            agent_ages, agent, u_p
        )
        log_pLvl = rng_i.normal(pLogMean, pLogStd, N_i)
        log_pLvl += agent_ages * np.log(g_lvl)
        log_pLvl += effective_emp_periods * (-ps_var / 2.0)
        log_pLvl += rng_i.normal(0, np.sqrt(ps_var * effective_emp_periods))
        agent_pLvl = np.exp(log_pLvl)

        agent.state_now["aNrm"][:] = agent_aNrm
        agent.state_now["pLvl"][:] = agent_pLvl
        agent.shocks["Mrkv"][:] = agent_j
        if hasattr(agent, "t_age") and agent.t_age is not None:
            agent.t_age[:] = agent_ages
        agent.Cratio = 1.0
        agent.state_now["PlvlAgg"] = 1.0

        if use_dual and hasattr(agent, "state_now_Q"):
            for k, v in agent.state_now.items():
                if isinstance(v, np.ndarray):
                    agent.state_now_Q[k] = v.copy()
                else:
                    agent.state_now_Q[k] = v

            # BUG-020 follow-up: initialize pLvl_Q from the Q-stationary
            # distribution, not a copy of pLvl_P.  Under Q, permanent
            # shocks are reweighted by psi/E[psi], making p_Q grow faster
            # than p_P.  The Q-stationary pLvl has higher mean and slightly
            # different variance.  Using the P distribution causes MC-Q to
            # need hundreds of extra periods to converge for p-nonlinear
            # functionals.
            #
            # Q growth: g_Q = (1-u)*G*E_Q[psi] + u = (1-u)*G*E_P[psi^2] + u
            # Q shock variance: Var_Q[log psi] from Q-reweighted distribution.
            q_probs_emp = PermShkDstn_0.pmv * PermShkDstn_0.atoms[0]
            q_probs_emp = q_probs_emp / q_probs_emp.sum()
            G_emp = float(np.asarray(agent.PermGroFac[0], float)[0])
            E_Q_psi = float(np.sum(q_probs_emp * PermShkDstn_0.atoms[0]))
            g_Q = (1.0 - u_p) * G_emp * E_Q_psi + u_p
            E_Q_log_psi = float(np.sum(q_probs_emp * log_ps))
            ps_var_Q = float(np.sum(q_probs_emp * log_ps**2)) - E_Q_log_psi**2

            log_pLvl_Q = rng_i.normal(pLogMean, pLogStd, N_i)
            log_pLvl_Q += agent_ages * np.log(g_Q)
            eff_emp_Q = effective_perm_shock_periods_for_t_age(
                agent_ages, agent, u_p)
            log_pLvl_Q += eff_emp_Q * (-ps_var_Q / 2.0)
            log_pLvl_Q += rng_i.normal(0, np.sqrt(ps_var_Q * eff_emp_Q))
            agent.state_now_Q["pLvl"][:] = np.exp(log_pLvl_Q)

    trace_rows = None
    if record_trace:
        ag0 = economy.agents[0]
        j0 = int(ag0.num_base_MrkvStates)
        crra0 = float(ag0.CRRA)
        trace_rows = [_burnin_cross_section_snapshot(ag0, j0, crra0)]

    for _t in range(warmup):
        for agent in economy.agents:
            agent.sim_one_period()
        if record_trace:
            trace_rows.append(
                _burnin_cross_section_snapshot(ag0, j0, crra0)
            )

    if record_trace and trace_rows:
        out = {"step": np.arange(len(trace_rows), dtype=int)}
        for k in trace_rows[0]:
            out[k] = np.array([float(r[k]) for r in trace_rows], dtype=float)
        return out
    return None


def _fix_act_T_after_switch(economy, periods: int):
    """
    ``switch_to_counterfactual_mode`` sets ``economy.act_T`` to module-level
    ``T_sim`` (Baseline _Model); override to the requested experiment length.
    """
    economy.act_T = int(periods)
    for a in economy.agents:
        a.get_economy_data(economy)


def _cross_section_stats(mNrm_row, pLvl_row, mrkv_row, num_base_MrkvStates: int):
    """Single-period cross-sectional summaries (1-D arrays length N)."""
    mean_m = float(np.nanmean(mNrm_row))
    med_m = float(np.nanmedian(mNrm_row))
    mean_p = float(np.nanmean(pLvl_row))
    micro = mrkv_row % int(num_base_MrkvStates)
    frac_emp = float(np.mean(micro == 0))
    return mean_m, med_m, mean_p, frac_emp


def _varlog_cross_section(x_row, floor: float = 1e-16, ddof: int = 1) -> float:
    """Sample variance of log(x) across agents (ddof=1)."""
    x = np.asarray(x_row, dtype=float).ravel()
    x = np.maximum(x, floor)
    if x.size <= ddof:
        return float("nan")
    return float(np.var(np.log(x), ddof=ddof))


def _burnin_cross_section_snapshot(agent, num_base_J: int, CRRA: float) -> dict:
    """One row of burn-in diagnostics for a single agent (cross-section means / dispersions)."""
    p = np.asarray(agent.state_now["pLvl"], dtype=float)
    a = np.asarray(agent.state_now["aNrm"], dtype=float)
    mk = np.asarray(agent.shocks["Mrkv"], dtype=int)
    micro = mk % int(num_base_J)
    frac_emp = float(np.mean(micro == 0))
    mean_p = float(np.mean(p))
    mean_a = float(np.mean(a))
    m_arr = agent.state_now.get("mNrm")
    if m_arr is not None:
        m_arr = np.asarray(m_arr, dtype=float)
        mean_m = float(np.nanmean(m_arr))
        vlm = _varlog_cross_section(m_arr)
    else:
        mean_m = float("nan")
        vlm = float("nan")
    vlp = _varlog_cross_section(p)
    cs = agent.state_now.get("cLvl_splurge")
    if cs is not None:
        cs = np.asarray(cs, dtype=float)
        mean_c = float(np.mean(cs))
        mean_mu = float(np.mean(_marginal_utility_crra(cs, CRRA)))
    else:
        mean_c = float("nan")
        mean_mu = float("nan")
    return {
        "mean_mNrm": mean_m,
        "mean_aNrm": mean_a,
        "mean_pLvl": mean_p,
        "frac_employed": frac_emp,
        "var_log_mNrm": vlm,
        "var_log_pLvl": vlp,
        "mean_cLvl_splurge": mean_c,
        "mean_mu": mean_mu,
    }


def _marginal_utility_crra(c_lvl: np.ndarray, CRRA: float, floor: float = 1e-16) -> np.ndarray:
    """u'(c) = c^{-CRRA} (CRRA != 1); matches Welfare.py base_MU convention."""
    c = np.asarray(c_lvl, dtype=float)
    c = np.maximum(c, floor)
    return c ** (-float(CRRA))


def _felicity_crra(c_lvl: np.ndarray, CRRA: float, floor: float = 1e-16) -> np.ndarray:
    """u(c) from ``Welfare.py`` felicity: log if CRRA==1 else c^(1-CRRA)/(1-CRRA)."""
    c = np.asarray(c_lvl, dtype=float)
    c = np.maximum(c, floor)
    rho = float(CRRA)
    if abs(rho - 1.0) < 1e-12:
        return np.log(c)
    return (c ** (1.0 - rho)) / (1.0 - rho)


def _mc_mean_marginal_utility_path(c_lvl_TN: np.ndarray, CRRA: float) -> np.ndarray:
    """Per-period cross-sectional mean E[u'(cLvl_splurge)], shape (T,)."""
    x = np.asarray(c_lvl_TN, dtype=float)
    mu = _marginal_utility_crra(x, CRRA)
    return np.mean(mu, axis=1)


def _mc_mean_felicity_path(c_lvl_TN: np.ndarray, CRRA: float) -> np.ndarray:
    """Per-period cross-sectional mean E[u(cLvl_splurge)], shape (T,)."""
    x = np.asarray(c_lvl_TN, dtype=float)
    u = _felicity_crra(x, CRRA)
    return np.mean(u, axis=1)


def mean_marginal_utility_tm_independent_p(
    agent,
    tm_data: dict,
    ergodic_flat: np.ndarray,
    CRRA: float,
    n_p_points: int = 120,
) -> float:
    """
    E[u'(cLvl_splurge)] under TM stationary pi(m,j) and marginal f(p) for pLvl.

    cLvl_splurge = (1-S)*p*c_nrm + S*p*E[TranShk|j] (baseline ADF=1), matching
    the *expectation* of AggFiscalType's splurge term given j.

    Uses pi(m,j) from ``ergodic_flat`` (length M*J, layout j slow, m fast) and
    ``compute_pLvl_distribution`` for f(p), with p independent of (m,j).
    """
    dist_mGrid = tm_data["dist_mGrid"]
    M = len(dist_mGrid)
    J = int(agent.num_base_MrkvStates)
    erg = np.asarray(ergodic_flat, dtype=float).ravel()
    if erg.size != M * J:
        raise ValueError(f"ergodic length {erg.size} != M*J={M * J}")
    s = erg.sum()
    if s <= 0 or not np.isfinite(s):
        return float("nan")
    erg = erg / s
    erg2 = erg.reshape(J, M)

    u_rate = float(1.0 - np.sum(erg2[0, :]))
    p_grid, p_w = compute_pLvl_distribution(
        agent, n_points=int(n_p_points), unemployment_rate=u_rate
    )

    sol = agent.solution[0]
    c_nrm = np.empty((J, M), dtype=np.float64)
    for j in range(J):
        c_nrm[j, :] = sol.cFunc[j](dist_mGrid, np.ones(M, dtype=np.float64))

    Splurge = float(agent.Splurge)
    E_TranShk = np.zeros(J, dtype=np.float64)
    for j in range(J):
        d = agent.IncShkDstn[0][j]
        E_TranShk[j] = float(np.dot(d.pmv, d.atoms[1]))
    ADF = 1.0

    Pn = len(p_grid)
    c_lvl = (1.0 - Splurge) * p_grid[:, None, None] * c_nrm[None, :, :]
    c_lvl += Splurge * p_grid[:, None, None] * E_TranShk[None, :, None] * ADF
    mu = _marginal_utility_crra(c_lvl, CRRA)
    weights = p_w[:, None, None] * erg2[None, :, :]
    return float(np.sum(weights * mu) / np.sum(weights))


def mean_marginal_utility_tm_kernel(
    agent,
    tm_data: dict,
    ergodic_flat: np.ndarray,
    CRRA: float,
    n_p_points: int = 120,
    IncShkDstn_override=None,
    E_pk_override=None,
) -> float:
    r"""
    E[u'(cLvl_splurge)] using the covariance kernel kappa(a, j).

    Instead of the product-measure approximation (``mean_marginal_utility_tm_independent_p``),
    this evaluates from savings a = m - c(m, j) and integrates forward over
    all period-t shocks (Psi, theta, j'), keeping theta explicit in both
    m = R*a/(G*Psi) + theta  and the splurge  S*theta.

    The approximate factorization is:

        E[u'] ≈ E[p^{-rho}] * sum_{m,j} pi(m,j) * kappa(a(m,j), j)

    where kappa(a, j) = sum_{j'} P(j->j') * sum_{Psi,theta} Pr(Psi,theta|j')
                        * (G_{j'} Psi)^{-rho}
                        * [(1-S) c(R*a/(G_{j'}*Psi) + theta, j') + S*theta]^{-rho}

    This resolves:
      - the theta-m coupling (~6% error in the plugin estimator)
      - Jensen's inequality from replacing theta with E[theta]
      - the psi-channel within-period covariance (via the (G*Psi)^{-rho} factor)

    The residual (~0.2%) is from the approximate p-a independence in the ergodic.

    See TM_MC_Marginal_Utility_Convergence_revised.ipynb §3 for the derivation.

    Implementation delegates to ``tm_methods.compute_kernels`` (single source of truth).

    Parameters
    ----------
    agent : AggFiscalType (solved)
    tm_data : dict from build_tm_agg_fiscal
    ergodic_flat : np.ndarray, length M*J
    CRRA : float
    n_p_points : int
        Grid points for compute_pLvl_distribution (E[p^{-rho}] factor).

    Returns
    -------
    float — estimate of E[u'(cLvl_splurge)]
    """
    rho = float(CRRA)
    if abs(rho - 1.0) < 1e-12:
        kdict = compute_kernels(
            agent, tm_data, ergodic_flat, [], rho,
            n_p_points=int(n_p_points), include_splurge=True,
            IncShkDstn_override=IncShkDstn_override,
            E_pk_override=E_pk_override,
        )
        return float(kdict[-1.0]["estimate"])
    kdict = compute_kernels(
        agent, tm_data, ergodic_flat, [-rho], rho,
        n_p_points=int(n_p_points), include_splurge=True,
        IncShkDstn_override=IncShkDstn_override,
        E_pk_override=E_pk_override,
    )
    return float(kdict[float(-rho)]["estimate"])


def diagnose_tm_init_stability(
    mc_res: dict,
    num_base_MrkvStates: int,
    act_T: int,
    use_burnin: bool,
    warmup_periods: int = 24,
    drift_m_rel: float = 0.05,
    drift_p_rel: float = 0.12,
    drift_u_pp: float = 2.0,
    drift_vlog_m_rel: float = 0.15,
    drift_vlog_p_rel: float = 0.15,
    CRRA: float = 2.0,
    drift_mu_rel: float = 0.25,
    verbose: bool = True,
):
    """
    After ``run_experiment``, check whether cross-sections stay close to the
    period-0 distribution in early periods.

    If TM ergodic init + burn-in + ``save_state`` / ``use_prestate`` /
    ``restore_state`` (see ``AggFiscalType.initialize_sim``) is aligned with
    one-step dynamics, mean ``mNrm`` and the employed share should not jump
    sharply after t=0. Mean ``pLvl`` can move a bit more (permanent shocks);
    thresholds are looser.     We also track **Var(log mNrm)** and **Var(log pLvl)**
    (cross-sectional, ddof=1): large shifts in dispersion vs t=0 flag a bad
    match to ergodic shape, not just location.

    When ``cLvl_all_splurge`` is present, tracks **mean marginal utility**
    ``mean(u'(cLvl_splurge))`` each period (same definition as ``Welfare.py``
    ``base_MU`` factor) and warns if it drifts materially vs ``t=0`` over early
    periods (burn-in adequacy for welfare moments).

    Returns
    -------
    dict with per-period rows, max drifts, and ``init_looks_stable`` bool.
    """
    m_all = mc_res["mNrm_all"]
    p_all = mc_res["pLvl_all"]
    mk_all = mc_res["Mrkv_hist"]
    T, N = m_all.shape

    c_lvl_all = mc_res.get("cLvl_all_splurge")
    if c_lvl_all is not None:
        mu_path = _mc_mean_marginal_utility_path(c_lvl_all, CRRA)
    else:
        mu_path = None

    want = sorted(
        set(
            [0, 1, 2, 3, 4, 5, 10, 20, min(50, T - 1), T - 1]
        )
    )
    want = [t for t in want if 0 <= t < T]

    rows_out = []
    m0, _, p0, u0 = _cross_section_stats(m_all[0], p_all[0], mk_all[0], num_base_MrkvStates)
    vlm0 = _varlog_cross_section(m_all[0])
    vlp0 = _varlog_cross_section(p_all[0])

    max_m_drift = 0.0
    max_p_drift = 0.0
    max_u_drift_pp = 0.0
    max_vlm_drift = 0.0
    max_vlp_drift = 0.0
    max_mu_drift = 0.0
    horizon = min(25, T - 1)

    mu0 = float(mu_path[0]) if mu_path is not None else float("nan")

    for t in want:
        mt, medt, pt, ut = _cross_section_stats(
            m_all[t], p_all[t], mk_all[t], num_base_MrkvStates
        )
        vlm = _varlog_cross_section(m_all[t])
        vlp = _varlog_cross_section(p_all[t])
        if abs(m0) > 1e-14:
            dm = abs(mt - m0) / abs(m0)
        else:
            dm = float("nan")
        if abs(p0) > 1e-14:
            dp = abs(pt - p0) / abs(p0)
        else:
            dp = float("nan")
        du_pp = abs(ut - u0) * 100.0
        if vlm0 > 1e-14 and np.isfinite(vlm0):
            dvlm = abs(vlm - vlm0) / vlm0
        else:
            dvlm = float("nan")
        if vlp0 > 1e-14 and np.isfinite(vlp0):
            dvlp = abs(vlp - vlp0) / vlp0
        else:
            dvlp = float("nan")
        if mu_path is not None and abs(mu0) > 1e-20:
            mu_t = float(mu_path[t])
            dmu_rel = abs(mu_t - mu0) / abs(mu0)
        else:
            mu_t = float("nan")
            dmu_rel = float("nan")
        rows_out.append(
            (t, mt, medt, pt, ut, dm, dp, du_pp, vlm, vlp, dvlm, dvlp, mu_t, dmu_rel)
        )
        if t >= 1 and t <= horizon:
            max_m_drift = max(max_m_drift, dm)
            max_p_drift = max(max_p_drift, dp)
            max_u_drift_pp = max(max_u_drift_pp, du_pp)
            max_vlm_drift = max(max_vlm_drift, dvlm)
            max_vlp_drift = max(max_vlp_drift, dvlp)
            if mu_path is not None and np.isfinite(dmu_rel):
                max_mu_drift = max(max_mu_drift, dmu_rel)

    init_looks_stable = (
        (max_m_drift <= drift_m_rel or np.isnan(max_m_drift))
        and (max_p_drift <= drift_p_rel or np.isnan(max_p_drift))
        and (max_u_drift_pp <= drift_u_pp)
        and (max_vlm_drift <= drift_vlog_m_rel or np.isnan(max_vlm_drift))
        and (max_vlp_drift <= drift_vlog_p_rel or np.isnan(max_vlp_drift))
        and (
            mu_path is None
            or np.isnan(max_mu_drift)
            or max_mu_drift <= drift_mu_rel
        )
    )

    if verbose:
        print("=" * 70)
        print("TM-style init stability (cross-section vs experiment time)")
        print("=" * 70)
        if use_burnin:
            print(
                "Burn-in: TM ergodic draw for (m, Mrkv) + synthetic pLvl, then "
                f"{warmup_periods} ``sim_one_period`` warmup steps, then "
                "save_state → run_experiment(use_prestate) → restore_state."
            )
        else:
            print(
                "Burn-in was off: default HARK initialize_sim distribution; "
                "large early drift vs ergodic may be expected."
            )
        print(
            f"Employed = micro state 0 (Mrkv % {num_base_MrkvStates} == 0). "
            f"Drift scan: periods 1..{horizon} vs t=0.\n"
        )
        hdr = (
            f"{'t':>4} {'mean(mNrm)':>11} {'mean(pLvl)':>11} {'frac emp':>9} "
            f"{'|dm|/m0':>9} {'|dp|/p0':>9} {'Var ln m':>10} {'|dVm|/V0':>9} "
            f"{'Var ln p':>10} {'|dVp|/V0':>9} {'mean_MU':>12} {'|dMU|/MU0':>10}"
        )
        print(hdr)
        print("-" * len(hdr))
        for row in rows_out:
            (
                t,
                mt,
                medt,
                pt,
                ut,
                dm,
                dp,
                du_pp,
                vlm,
                vlp,
                dvlm,
                dvlp,
                mu_t,
                dmu_rel,
            ) = row
            mus = f"{mu_t:10.6e}" if np.isfinite(mu_t) else f"{'n/a':>10}"
            dmu_s = f"{dmu_rel:9.5f}" if np.isfinite(dmu_rel) else f"{'n/a':>9}"
            print(
                f"{t:4d} {mt:11.5f} {pt:11.5f} {ut:9.4f} "
                f"{dm:9.5f} {dp:9.5f} {vlm:10.6f} {dvlm:9.5f} "
                f"{vlp:10.6f} {dvlp:9.5f} {mus} {dmu_s}"
            )
        print("-" * len(hdr))
        print(
            f"Var ln m / Var ln p = cross-sectional sample variance of log(mNrm), log(pLvl) (ddof=1)."
        )
        print(
            f"Max |Δ mean(mNrm)|/mean(mNrm)_0 over t=1..{horizon}: {max_m_drift:.5f} "
            f"(warn if > {drift_m_rel})"
        )
        print(
            f"Max |Δ mean(pLvl)|/mean(pLvl)_0 over t=1..{horizon}: {max_p_drift:.5f} "
            f"(warn if > {drift_p_rel})"
        )
        print(
            f"Max |Δ frac employed| over t=1..{horizon}: {max_u_drift_pp:.3f} pp "
            f"(warn if > {drift_u_pp} pp)"
        )
        print(
            f"Max |Δ Var(ln m)|/Var(ln m)_0 over t=1..{horizon}: {max_vlm_drift:.5f} "
            f"(warn if > {drift_vlog_m_rel})"
        )
        print(
            f"Max |Δ Var(ln p)|/Var(ln p)_0 over t=1..{horizon}: {max_vlp_drift:.5f} "
            f"(warn if > {drift_vlog_p_rel})"
        )
        if mu_path is not None:
            print(
                f"Max |Δ mean(MU)|/mean(MU)_0 over t=1..{horizon}: {max_mu_drift:.5f} "
                f"(warn if > {drift_mu_rel}); MU=u'(cLvl_splurge)=c^(-CRRA), CRRA={CRRA}"
            )
        if init_looks_stable:
            print("\nInit check: no large early drift vs t=0 (within thresholds).")
        else:
            print(
                "\nInit check: WARNING — cross-section moved sharply in early periods; "
                "TM init / dynamics mismatch or strong MC noise (try larger N)."
            )
        print()

    return {
        "period_rows": rows_out,
        "varlog_mNrm_0": vlm0,
        "varlog_pLvl_0": vlp0,
        "max_m_drift_early": max_m_drift,
        "max_p_drift_early": max_p_drift,
        "max_u_drift_pp_early": max_u_drift_pp,
        "max_varlog_m_drift_early": max_vlm_drift,
        "max_varlog_p_drift_early": max_vlp_drift,
        "mean_marginal_utility_0": mu0,
        "max_mu_drift_early": max_mu_drift,
        "init_looks_stable": init_looks_stable,
    }


def compare_four_methods(
    educ: str = "highschool",
    periods: int = 100,
    agents: int = 40000,
    seed: int = 42,
    m_count: int = 100,
    warmup: int = 24,
    t_start: int = 0,
    variance_reduction: bool = False,
    use_burnin: bool = True,
    rtol: float = 0.02,
    atol: float = 0.0,
    pq_rtol: float = 5e-4,
    verbose: bool = True,
    diagnose_init: bool = True,
    drift_m_rel: float = 0.05,
    drift_p_rel: float = 0.12,
    drift_u_pp: float = 2.0,
    drift_vlog_m_rel: float = 0.15,
    drift_vlog_p_rel: float = 0.15,
    drift_mu_rel: float = 0.25,
    check_mu: bool = True,
    mu_rtol: float = 0.14,
    pq_mu_rtol: float = 0.165,
    mu_p_points: int = 120,
    check_felicity: bool = True,
    felicity_rtol: float = 0.07,
    pq_felicity_rtol: float = 0.12,
    record_burnin_trace: bool = False,
):
    """
    Run (C), (D), then (A)+(B) on a fresh solved economy. Return dict of means
    and whether checks passed. Keys ``ref``, ``mean_tm_p``, ``mean_tm_q``,
    ``mean_mc_p``, ``mean_mc_q`` are **mean economy AggCons per capita**
    (time-mean of totals divided by ``agents``).

    When ``diagnose_init`` is True and ``verbose`` is True, print whether early
    cross-sections (means, Var(log mNrm), Var(log pLvl), employment share) stay
    close to period 0 after TM-based initialization (see ``diagnose_tm_init_stability``).

    When ``check_mu`` is True, also compares mean marginal utility
    ``E[u'(cLvl_splurge)]`` (CRRA power) across the four methods; TM side uses
    ``tm_methods.compute_kernels`` / ``mean_marginal_utility_tm_kernel`` (covariance
    kernel on ``(m,j)``, marginal ``p`` from ``compute_pLvl_distribution``).
    When ``check_felicity`` is True, compares mean ``E[u(cLvl_splurge)]`` with
    ``Welfare.py`` felicity across the same four methods.

    Returns also ``mu_time_series_t``, ``mu_time_series_mc_p``, ``mu_time_series_mc_q``:
    cross-sectional mean MU by MC experiment period (aligned length). TM-P and TM-Q
    are stationary scalars for ``shock_type='base'`` — plot as horizontal lines at
    ``mean_mu_tm_p`` and ``mean_mu_tm_q``.

    With ``record_burnin_trace=True`` and ``use_burnin=True``, ``burnin_trace`` holds
    per-step cross-section summaries during TM draw + ``warmup`` ``sim_one_period`` calls
    (see ``_mc_burnin_tm_init``). Otherwise ``burnin_trace`` is ``None``.
    """
    if not HAS_DUAL:
        raise RuntimeError("DualAggFiscalType not available; cannot compute AggCons_Q.")

    periods = int(periods)
    if variance_reduction:
        try:
            from AggFiscalModel import NormalizedDualAggFiscalType
            agent_cls = NormalizedDualAggFiscalType
        except ImportError:
            raise ImportError(
                "variance_reduction=True requires NormalizedDualAggFiscalType "
                "(HARK PermanentIncomeNormalizationMixin + hafiscal_normalization.py)"
            )
    else:
        agent_cls = DualAggFiscalType

    economy, base_dict = _build_single_type_economy(
        educ=educ,
        agent_count=agents,
        seed=seed,
        act_T=periods,
        agent_cls=agent_cls,
    )
    economy.solve()

    if variance_reduction:
        for agent in economy.agents:
            agent.income_shuffle = True
            agent.markov_shuffle = True
            agent.normalize_pLvl = True

    t0 = time.perf_counter()
    tm_p = run_experiment_tm(
        economy, shock_type="base", mCount=m_count, neutral_measure=False, verbose=False
    )
    time_tm_p = time.perf_counter() - t0

    t0 = time.perf_counter()
    tm_q = run_experiment_tm(
        economy, shock_type="base", mCount=m_count, neutral_measure=True, verbose=False
    )
    time_tm_q = time.perf_counter() - t0

    n_agents = float(max(int(agents), 1))
    mean_tm_p = float(np.mean(tm_p["AggCons"])) / n_agents
    mean_tm_q = float(np.mean(tm_q["AggCons"])) / n_agents

    agent0 = economy.agents[0]
    CRRA = float(agent0.CRRA)

    def _tm_ergodic_for_mu(tm_data: dict) -> np.ndarray:
        ce = tm_data.get("cohort_ergodic")
        if ce is not None and np.sum(np.asarray(ce, dtype=float)) > 0:
            return np.asarray(ce, dtype=float).ravel()
        return np.asarray(
            find_ergodic_distribution(tm_data["TranMatrix"]), dtype=float
        ).ravel()

    td_p = tm_p["_type_results"][0]["tm_data"]
    td_q = tm_q["_type_results"][0]["tm_data"]
    erg_mu_p = _tm_ergodic_for_mu(td_p)
    erg_mu_q = _tm_ergodic_for_mu(td_q)

    # BUG-020 fix: build Q-measure overrides for TM-Q kernel calls.
    # TM-P uses P shocks and P E[p^k] (default).
    # TM-Q must use Q-reweighted shocks and Q-measure E[p^k].
    IncShk_Q = _to_neutral_measure(agent0.IncShkDstn[0])
    _erg_q_2d = (erg_mu_q / erg_mu_q.sum()).reshape(
        int(agent0.num_base_MrkvStates), len(td_q["dist_mGrid"]))
    _u_rate_q = float(1.0 - np.sum(_erg_q_2d[0, :]))
    rho_val = float(CRRA)
    if abs(rho_val - 1.0) < 1e-12:
        _q_powers = [-1.0]
    else:
        _q_powers = [-rho_val, 1.0 - rho_val]
    E_pk_Q = compute_pLvl_distribution_Q(
        agent0, _q_powers, n_points=int(mu_p_points), unemployment_rate=_u_rate_q)

    mean_mu_tm_p = mean_marginal_utility_tm_kernel(
        agent0, td_p, erg_mu_p, CRRA, n_p_points=mu_p_points,
    )
    mean_mu_tm_q = mean_marginal_utility_tm_kernel(
        agent0, td_q, erg_mu_q, CRRA, n_p_points=mu_p_points,
        IncShkDstn_override=IncShk_Q, E_pk_override=E_pk_Q,
    )

    def _mean_felicity_tm(agent, tm_data_i, erg_flat, rho, n_pts,
                          IncShkDstn_ov=None, E_pk_ov=None):
        r = float(rho)
        if abs(r - 1.0) < 1e-12:
            kd = compute_kernels(
                agent, tm_data_i, erg_flat, [], r,
                n_p_points=int(n_pts), include_splurge=True,
                IncShkDstn_override=IncShkDstn_ov, E_pk_override=E_pk_ov,
            )
            return float(kd[0.0]["estimate"])
        kd = compute_kernels(
            agent, tm_data_i, erg_flat, [-r, 1.0 - r], r,
            n_p_points=int(n_pts), include_splurge=True,
            IncShkDstn_override=IncShkDstn_ov, E_pk_override=E_pk_ov,
        )
        return float(kd[float(1.0 - r)]["estimate"])

    mean_fel_tm_p = _mean_felicity_tm(
        agent0, td_p, erg_mu_p, CRRA, mu_p_points
    )
    mean_fel_tm_q = _mean_felicity_tm(
        agent0, td_q, erg_mu_q, CRRA, mu_p_points,
        IncShkDstn_ov=IncShk_Q, E_pk_ov=E_pk_Q,
    )

    economy.solve()

    # Gatekeeper / callers may pass warmup=None to mean "one expected lifetime".
    if warmup is None:
        LivPrb = float(economy.agents[0].LivPrb[0][0])
        warmup = int(round(1.0 / (1.0 - LivPrb)))

    burnin_trace = None
    if use_burnin:
        burnin_trace = _mc_burnin_tm_init(
            economy,
            warmup=warmup,
            neutral_measure=True,
            use_dual=True,
            record_trace=record_burnin_trace,
        )
    else:
        economy.reset()
        for agent in economy.agents:
            agent.initialize_sim()
            agent.AggDemandFac = 1.0
            agent.RfreeNow = 1.0
            agent.CaggNow = 1.0
        economy.make_history()

    t0 = time.perf_counter()
    economy.save_state()
    economy.switch_to_counterfactual_mode("base")
    _fix_act_T_after_switch(economy, periods)
    economy.make_idiosyncratic_shock_histories()
    mc_res = economy.run_experiment(**deepcopy(base_dict), Full_Output=True)
    time_mc = time.perf_counter() - t0
    _ts = int(t_start)
    mean_mc_p = float(np.mean(mc_res["AggCons"][_ts:])) / n_agents
    mean_mc_q = float(np.mean(mc_res["AggCons_Q"][_ts:])) / n_agents

    mu_path_mc_p = _mc_mean_marginal_utility_path(mc_res["cLvl_all_splurge"], CRRA)
    mean_mu_mc_p = float(np.mean(mu_path_mc_p[_ts:]))

    c_lvl_p = mc_res["cLvl_all_splurge"]
    c_lvl_q = economy.agents[0].history_Q["cLvl_splurge"]
    T_mu = min(int(c_lvl_p.shape[0]), int(c_lvl_q.shape[0]))
    mu_path_mc_q = _mc_mean_marginal_utility_path(c_lvl_q[:T_mu], CRRA)
    mean_mu_mc_q = float(np.mean(mu_path_mc_q[_ts:]))

    fel_path_mc_p = _mc_mean_felicity_path(mc_res["cLvl_all_splurge"], CRRA)
    mean_fel_mc_p = float(np.mean(fel_path_mc_p[_ts:]))
    fel_path_mc_q = _mc_mean_felicity_path(c_lvl_q[:T_mu], CRRA)
    mean_fel_mc_q = float(np.mean(fel_path_mc_q[_ts:]))

    _t_mu = int(min(mu_path_mc_p.shape[0], mu_path_mc_q.shape[0]))
    mu_ts_t = np.arange(_t_mu, dtype=int)
    mu_ts_mc_p = np.asarray(mu_path_mc_p[:_t_mu], dtype=float)
    mu_ts_mc_q = np.asarray(mu_path_mc_q[:_t_mu], dtype=float)

    num_base_J = int(economy.agents[0].num_base_MrkvStates)

    ref = 0.5 * (mean_tm_p + mean_tm_q)
    if ref <= 0 or not np.isfinite(ref):
        raise RuntimeError(
            f"Non-positive or invalid reference mean AggCons per capita: {ref}"
        )

    def _ok(val):
        err = abs(val - ref) / ref
        pass_ = err <= rtol or abs(val - ref) <= atol
        return pass_, err

    rows = [
        ("TM P (2D)", mean_tm_p, *_ok(mean_tm_p), time_tm_p),
        ("TM Q (neutral)", mean_tm_q, *_ok(mean_tm_q), time_tm_q),
        ("MC P", mean_mc_p, *_ok(mean_mc_p), time_mc),
        ("MC Q (Harmenberg)", mean_mc_q, *_ok(mean_mc_q), time_mc),
    ]

    pq_mc_err = abs(mean_mc_p - mean_mc_q) / ref

    # Within-measure comparisons for p-nonlinear functionals.
    # P and Q give genuinely different answers for k != 1; comparing
    # across measures is meaningless.  Validate TM vs MC within each.
    mu_err_P = abs(mean_mu_tm_p - mean_mu_mc_p) / max(abs(mean_mu_mc_p), 1e-16)
    mu_err_Q = abs(mean_mu_tm_q - mean_mu_mc_q) / max(abs(mean_mu_mc_q), 1e-16)
    mu_ok_P = mu_err_P <= mu_rtol
    mu_ok_Q = mu_err_Q <= mu_rtol

    rows_mu = [
        ("P: TM-P kernel", mean_mu_tm_p, mu_ok_P, mu_err_P),
        ("P: MC-P",        mean_mu_mc_p, mu_ok_P, mu_err_P),
        ("Q: TM-Q kernel", mean_mu_tm_q, mu_ok_Q, mu_err_Q),
        ("Q: MC-Q",        mean_mu_mc_q, mu_ok_Q, mu_err_Q),
    ]

    fel_err_P = abs(mean_fel_tm_p - mean_fel_mc_p) / max(abs(mean_fel_mc_p), 1e-16)
    fel_err_Q = abs(mean_fel_tm_q - mean_fel_mc_q) / max(abs(mean_fel_mc_q), 1e-16)
    fel_ok_P = fel_err_P <= felicity_rtol
    fel_ok_Q = fel_err_Q <= felicity_rtol

    rows_fel = [
        ("P: TM-P kernel", mean_fel_tm_p, fel_ok_P, fel_err_P),
        ("P: MC-P",        mean_fel_mc_p, fel_ok_P, fel_err_P),
        ("Q: TM-Q kernel", mean_fel_tm_q, fel_ok_Q, fel_err_Q),
        ("Q: MC-Q",        mean_fel_mc_q, fel_ok_Q, fel_err_Q),
    ]

    if verbose:
        print(f"\nSingle type: {educ}, N={agents}, T={periods}, mCount={m_count}, seed={seed}")
        print(
            f"Reference mean AggCons per capita (avg TM-P & TM-Q): {ref:.6f}\n"
        )
        print(
            f"{'Method':<22} {'mean C / N':>16} {'rel_err':>12} {'time (s)':>10} {'ok':>5}"
        )
        print("-" * 70)
        for label, val, ok, err, t_s in rows:
            print(
                f"{label:<22} {val:16.6f} {100.0 * err:11.4f}% {t_s:10.4f} {str(ok):>5}"
            )
        print(
            "\nMC timing is one block: save_state, switch to base, shock histories, "
            "run_experiment (AggCons and AggCons_Q together); table is per-capita."
        )
        print(f"\n|P_MC - Q_MC| / ref (per-capita identity check): {100.0 * pq_mc_err:.6f}%")
        print(f"Tolerance: rtol={rtol}, atol={atol} (atol: per-capita level)\n")

        print("=" * 70)
        print(
            "Mean marginal utility E[u'(cLvl_splurge)] (p-nonlinear: "
            "P and Q measures give different answers)"
        )
        print(f"CRRA={CRRA}, t_start={_ts}. "
              "Within-measure: TM kernel vs MC (should agree ~0.5%).")
        print("=" * 70)
        print(f"\n  P-measure:  TM-P = {mean_mu_tm_p:.8e}   MC-P = {mean_mu_mc_p:.8e}   "
              f"|TM-MC|/MC = {100*mu_err_P:.3f}%  {'ok' if mu_ok_P else 'FAIL'}")
        print(f"  Q-measure:  TM-Q = {mean_mu_tm_q:.8e}   MC-Q = {mean_mu_mc_q:.8e}   "
              f"|TM-MC|/MC = {100*mu_err_Q:.3f}%  {'ok' if mu_ok_Q else 'FAIL'}")
        print(f"\n  (P and Q differ by {abs(mean_mu_mc_p-mean_mu_mc_q)/mean_mu_mc_p*100:.1f}% "
              f"-- expected for k != 1)")
        print(f"  Tolerance: mu_rtol={mu_rtol}")
        if not check_mu:
            print("  (Marginal-utility gate disabled; table is informational only.)")
        print()

        print("=" * 70)
        print(
            "Mean felicity E[u(cLvl_splurge)] (p-nonlinear: "
            "P and Q measures give different answers)"
        )
        print(f"CRRA={CRRA}, t_start={_ts}. "
              "Within-measure: TM kernel vs MC (should agree ~1%).")
        print("=" * 70)
        print(f"\n  P-measure:  TM-P = {mean_fel_tm_p:.8e}   MC-P = {mean_fel_mc_p:.8e}   "
              f"|TM-MC|/|MC| = {100*fel_err_P:.3f}%  {'ok' if fel_ok_P else 'FAIL'}")
        print(f"  Q-measure:  TM-Q = {mean_fel_tm_q:.8e}   MC-Q = {mean_fel_mc_q:.8e}   "
              f"|TM-MC|/|MC| = {100*fel_err_Q:.3f}%  {'ok' if fel_ok_Q else 'FAIL'}")
        print(f"\n  (P and Q differ by {abs(mean_fel_mc_p-mean_fel_mc_q)/abs(mean_fel_mc_p)*100:.1f}% "
              f"-- expected for k != 1)")
        print(f"  Tolerance: felicity_rtol={felicity_rtol}")
        if not check_felicity:
            print("  (Felicity gate disabled; table is informational only.)")
        print()

    init_diag = None
    if diagnose_init:
        init_diag = diagnose_tm_init_stability(
            mc_res,
            num_base_J,
            periods,
            use_burnin,
            warmup_periods=warmup,
            drift_m_rel=drift_m_rel,
            drift_p_rel=drift_p_rel,
            drift_u_pp=drift_u_pp,
            drift_vlog_m_rel=drift_vlog_m_rel,
            drift_vlog_p_rel=drift_vlog_p_rel,
            CRRA=CRRA,
            drift_mu_rel=drift_mu_rel,
            verbose=verbose,
        )

    # Same simulated path: AggCons vs AggCons_Q uses cross-sectional means each period;
    # tiny finite-sample mismatch is normal (see run_experiment in AggFiscalModel).
    pq_ok = pq_mc_err <= pq_rtol or abs(mean_mc_p - mean_mc_q) <= max(atol, 1e-9)

    # For p-nonlinear: within-measure TM-vs-MC agreement (not cross-measure).
    mu_gate = True
    if check_mu:
        mu_gate = mu_ok_P and mu_ok_Q

    fel_gate = True
    if check_felicity:
        fel_gate = fel_ok_P and fel_ok_Q

    all_pass = all(r[2] for r in rows) and pq_ok and mu_gate and fel_gate
    return {
        "agents": int(agents),
        "ref": ref,
        "mean_tm_p": mean_tm_p,
        "mean_tm_q": mean_tm_q,
        "mean_mc_p": mean_mc_p,
        "mean_mc_q": mean_mc_q,
        "rel_errs": {rows[i][0]: rows[i][3] for i in range(len(rows))},
        "time_tm_p": time_tm_p,
        "time_tm_q": time_tm_q,
        "time_mc": time_mc,
        "pq_mc_rel_err": pq_mc_err,
        "mean_mu_tm_p": mean_mu_tm_p,
        "mean_mu_tm_q": mean_mu_tm_q,
        "mean_mu_mc_p": mean_mu_mc_p,
        "mean_mu_mc_q": mean_mu_mc_q,
        "mu_err_P": mu_err_P,
        "mu_err_Q": mu_err_Q,
        "mu_time_series_t": mu_ts_t,
        "mu_time_series_mc_p": mu_ts_mc_p,
        "mu_time_series_mc_q": mu_ts_mc_q,
        "burnin_trace": burnin_trace,
        "passed_mu": bool(mu_gate) if check_mu else None,
        "mean_fel_tm_p": mean_fel_tm_p,
        "mean_fel_tm_q": mean_fel_tm_q,
        "mean_fel_mc_p": mean_fel_mc_p,
        "mean_fel_mc_q": mean_fel_mc_q,
        "fel_err_P": fel_err_P,
        "fel_err_Q": fel_err_Q,
        "passed_felicity": bool(fel_gate) if check_felicity else None,
        "passed": all_pass,
        "init_stability": init_diag,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--educ", default="highschool", help="dropout | highschool | college")
    p.add_argument("--periods", type=int, default=100, help="Experiment length act_T")
    p.add_argument(
        "--agents",
        type=int,
        default=40000,
        help="Monte Carlo population (default 40000 for stable moments / variance)",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--m-count", type=int, default=100, help="TM grid points")
    p.add_argument("--warmup", type=int, default=24, help="MC burn-in periods (if --burnin)")
    p.add_argument("--no-burnin", action="store_true", help="Skip TM-initialized burn-in")
    p.add_argument("--rtol", type=float, default=0.02, help="Max rel error vs ref (fraction)")
    p.add_argument(
        "--atol",
        type=float,
        default=0.0,
        help="Absolute tolerance on mean AggCons per capita (level)",
    )
    p.add_argument(
        "--pq-rtol",
        type=float,
        default=5e-4,
        help="Max rel error |mean MC_P - mean MC_Q| / ref (per capita; same-path reconstruction)",
    )
    p.add_argument(
        "--no-diagnose-init",
        action="store_true",
        help="Skip TM init stability table (cross-section drift in early MC periods)",
    )
    p.add_argument(
        "--no-mu-check",
        action="store_true",
        help="Skip marginal-utility / welfare four-way gate (AggCons only)",
    )
    p.add_argument(
        "--mu-rtol",
        type=float,
        default=0.14,
        help="Max rel error vs ref_mu for mean E[u'(cLvl_splurge)] (fraction); "
        "looser than AggCons (nonlinear-in-p functional). MC-Q can be ~13% vs avg TM ref.",
    )
    p.add_argument(
        "--pq-mu-rtol",
        type=float,
        default=0.165,
        help="Max rel error |mean MC_P MU - mean MC_Q MU| / ref_mu "
        "(u' is nonlinear; do not expect AggCons-tight identity).",
    )
    p.add_argument(
        "--drift-mu-rel",
        type=float,
        default=0.25,
        help="Init-stability warn if max |Δ mean(MU)|/mean(MU)_0 exceeds this (early periods)",
    )
    p.add_argument(
        "--mu-p-points",
        type=int,
        default=120,
        help="Grid points for compute_pLvl_distribution in TM mean MU / kernels",
    )
    p.add_argument(
        "--no-felicity-check",
        action="store_true",
        help="Skip mean felicity E[u(c)] four-way gate (kernel-integration-spec)",
    )
    p.add_argument(
        "--felicity-rtol",
        type=float,
        default=0.07,
        help="Max rel error vs average-of-four ref for mean felicity (fraction)",
    )
    p.add_argument(
        "--pq-felicity-rtol",
        type=float,
        default=0.12,
        help="Max rel error |MC_P felicity - MC_Q felicity| / |ref_fel|",
    )
    args = p.parse_args()

    if not HAS_DUAL:
        print("DualAggFiscalType not available.", file=sys.stderr)
        sys.exit(2)

    out = compare_four_methods(
        educ=args.educ,
        periods=args.periods,
        agents=args.agents,
        seed=args.seed,
        m_count=args.m_count,
        warmup=args.warmup,
        use_burnin=not args.no_burnin,
        rtol=args.rtol,
        atol=args.atol,
        pq_rtol=args.pq_rtol,
        verbose=True,
        diagnose_init=not args.no_diagnose_init,
        check_mu=not args.no_mu_check,
        mu_rtol=args.mu_rtol,
        pq_mu_rtol=args.pq_mu_rtol,
        drift_mu_rel=args.drift_mu_rel,
        mu_p_points=args.mu_p_points,
        check_felicity=not args.no_felicity_check,
        felicity_rtol=args.felicity_rtol,
        pq_felicity_rtol=args.pq_felicity_rtol,
    )
    sys.exit(0 if out["passed"] else 1)


if __name__ == "__main__":
    main()
