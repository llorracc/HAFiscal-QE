"""
Period-1 trace: TM-init MC vs one-step TM operator on the same baseline.

Compares mean mNrm / cNrm / aNrm (normalized) before and after one MC
sim_one_period from a TM-ergodic injection, versus the TM ergodic and
one application of TranMatrix @ pi (pi should equal pi if pi is stationary).

Outputs: debug/trace_period1_tm_mc_composer.txt (name includes 'composer').
"""

from __future__ import annotations

import os
import sys
from copy import deepcopy
from time import time

import numpy as np

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith("FromPandemicCode"):
    os.chdir(cwd + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, os.getcwd())

os.environ["MPLBACKEND"] = "Agg"

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from income_process_sst import effective_perm_shock_periods_for_t_age, effective_pLvl_growth, effective_perm_shock_variance_periods
from tm_methods import build_tm_agg_fiscal, find_ergodic_distribution

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_OUT_LOG = os.path.join(_REPO_ROOT, "debug", "trace_period1_tm_mc_composer.txt")

N = 80000
MCOUNT = 50


def _tm_moments_from_dist(pi: np.ndarray, dist_mGrid: np.ndarray, cPol, aPol, J: int):
    """BOP-weighted means: E[m], E[c], E[a] where a = m - c on grid."""
    M = len(dist_mGrid)
    em = ec = ea = 0.0
    for j in range(J):
        sl = pi[j * M : (j + 1) * M]
        em += float(np.dot(sl, dist_mGrid))
        ec += float(np.dot(sl, np.asarray(cPol[j])))
        ea += float(np.dot(sl, np.asarray(aPol[j])))
    return em, ec, ea


def _log(lines: list, msg: str) -> None:
    lines.append(msg)
    print(msg, flush=True)


def main() -> None:
    t0 = time()
    lines: list[str] = []

    [
        _id,
        _ih,
        init_college,
        init_ADEconomy,
        DiscFacDstns,
        _dfc,
        _act,
        _bd,
        _nmi,
        _ct,
        UBspell_normal,
        num_base_MrkvStates,
        _des,
        _mrd,
        num_experiment_periods,
        *_pc,
    ] = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
    J = num_base_MrkvStates

    BaseType = AggFiscalType(**init_college)
    BaseType.cycles = 0
    BaseType.AgentCount = N
    BaseType.DiscFac = DiscFacDstns[2].atoms[0][0]

    AggEco = AggregateDemandEconomy(**init_ADEconomy)
    BaseType.get_economy_data(AggEco)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])]
    )
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])],
    )
    BaseType.IncShkDstn[0].seed = 763607780
    BaseType.IncShkDstn[0].reset()
    EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
    BaseType.IncShkDstn = [
        [BaseType.IncShkDstn[0]]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]
    ]
    BaseType.IncShkDstn_base = BaseType.IncShkDstn
    IncShkDstn_recession = [
        BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))
    ]
    BaseType.IncShkDstn_recession = IncShkDstn_recession
    BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
    EmployedIncShkDstn.atoms[0][1] = (
        EmployedIncShkDstn.atoms[0][1] * BaseType.TaxCutIncFactor
    )
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

    AggEco.agents = [BaseType]
    AggEco.solve()

    rng = np.random.RandomState(42)
    tm_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
    P = tm_data["TranMatrix"]
    dist_mGrid = tm_data["dist_mGrid"]
    cPol = tm_data["cPol"]
    aPol = tm_data["aPol"]
    M = len(dist_mGrid)

    ergodic = find_ergodic_distribution(P)
    pi1 = P @ ergodic
    if hasattr(pi1, "A1"):
        pi1 = np.asarray(pi1).ravel()
    diff_pi = float(np.max(np.abs(pi1 - ergodic)))

    em0, ec0, ea0 = _tm_moments_from_dist(ergodic, dist_mGrid, cPol, aPol, J)
    em1, ec1, ea1 = _tm_moments_from_dist(pi1, dist_mGrid, cPol, aPol, J)

    _log(lines, "=" * 72)
    _log(lines, "A. TM operator on stationary pi (sanity)")
    _log(lines, "=" * 72)
    _log(lines, f"  mCount={MCOUNT}, M={M}, J={J}")
    _log(lines, f"  ||P @ pi - pi||_inf = {diff_pi:.3e}  (should be ~0)")
    _log(lines, "  BOP moments from pi (E[m], E[c], E[a=m-c] on TM grid):")
    _log(lines, f"    t=0:  E[m]={em0:.6f}  E[c]={ec0:.6f}  E[a]={ea0:.6f}")
    _log(lines, f"    t=1:  E[m]={em1:.6f}  E[c]={ec1:.6f}  E[a]={ea1:.6f}")
    _log(lines, f"    delta: dE[m]={em1-em0:+.6e}  dE[a]={ea1-ea0:+.6e}")

    # --- MC: TM ergodic sample + analytical pLvl (same as test_tm_init_mc) ---
    flat_probs = ergodic / np.sum(ergodic)
    bins = rng.choice(len(flat_probs), size=N, p=flat_probs)
    agent_j = bins // M
    agent_m_idx = bins % M
    agent_mNrm = dist_mGrid[agent_m_idx].copy()
    for i in range(N):
        idx = agent_m_idx[i]
        if idx < M - 1:
            lo, hi = dist_mGrid[idx], dist_mGrid[idx + 1]
        else:
            lo, hi = dist_mGrid[idx], dist_mGrid[idx] * 1.01
        agent_mNrm[i] = rng.uniform(lo, hi)

    sol = BaseType.solution[0]
    cFuncs = [sol.cFunc[j] for j in range(J)]
    agent_aNrm = np.zeros(N)
    for j in range(J):
        mask = agent_j == j
        if np.any(mask):
            cj = cFuncs[j](agent_mNrm[mask], np.ones(np.sum(mask)))
            agent_aNrm[mask] = np.maximum(agent_mNrm[mask] - cj, 0.0)

    LivPrb = BaseType.LivPrb[0][0]
    T_age = BaseType.T_age
    age_probs = np.array([LivPrb ** (k - 1) for k in range(1, T_age + 1)])
    age_probs /= np.sum(age_probs)
    agent_ages = rng.choice(T_age, size=N, p=age_probs) + 1
    pLogInitMean = BaseType.pLogInitMean
    pLogInitStd = getattr(
        BaseType, "pLogInitStd", getattr(BaseType, "pLvlInitStd", 0.0)
    )
    log_pLvl_init = rng.normal(pLogInitMean, pLogInitStd, size=N)
    PermShkDstn = BaseType.IncShkDstn_base[0][0]
    log_psi = np.log(PermShkDstn.atoms[0])
    PermShk_var = np.dot(PermShkDstn.pmv, log_psi**2) - np.dot(
        PermShkDstn.pmv, log_psi
    ) ** 2
    g_lvl = effective_pLvl_growth(BaseType, getattr(BaseType, "Urate_normal", 0.0))
    eff_perm = effective_perm_shock_periods_for_t_age(
        agent_ages, BaseType, getattr(BaseType, "Urate_normal", 0.0))
    log_pLvl = log_pLvl_init + agent_ages * np.log(g_lvl)
    log_pLvl += eff_perm * (-PermShk_var / 2.0)
    log_pLvl += rng.normal(0, np.sqrt(PermShk_var * eff_perm))
    agent_pLvl = np.exp(log_pLvl)

    eco = deepcopy(AggEco)
    ag = eco.agents[0]
    ag.AgentCount = N
    ag.seed = 0
    eco.solve()
    eco.reset()
    ag.initialize_sim()
    ag.state_now["aNrm"][:] = agent_aNrm
    ag.state_now["pLvl"][:] = agent_pLvl
    ag.shocks["Mrkv"][:] = agent_j
    if hasattr(ag, "t_age") and ag.t_age is not None:
        ag.t_age[:] = agent_ages
    ag.AggDemandFac = 1.0
    ag.RfreeNow = 1.0
    ag.CaggNow = 1.0
    ag.Cratio = 1.0
    ag.state_now["PlvlAgg"] = 1.0

    m_pre_mc = agent_mNrm.copy()
    a_pre = np.array(ag.state_now["aNrm"], copy=True)
    p_pre = np.array(ag.state_now["pLvl"], copy=True)
    c_pre = np.zeros(N)
    for j in range(J):
        mask = agent_j == j
        if np.any(mask):
            c_pre[mask] = cFuncs[j](m_pre_mc[mask], np.ones(np.sum(mask)))

    _log(lines, "")
    _log(lines, "=" * 72)
    _log(lines, "B. MC ensemble BEFORE sim_one_period (TM-init injection)")
    _log(lines, "=" * 72)
    _log(
        lines,
        f"  mean(mNrm) sample BOP={np.mean(m_pre_mc):.6f}  "
        f"TM E[m] grid={em0:.6f}  diff={np.mean(m_pre_mc)-em0:+.6f}",
    )
    _log(lines, f"  mean(aNrm) EOP      ={np.mean(a_pre):.6f}  TM E[a]={ea0:.6f}")
    _log(lines, f"  mean(cNrm) at BOP   ={np.mean(c_pre):.6f}  TM E[c]={ec0:.6f}")
    _log(lines, f"  mean(pLvl)          ={np.mean(p_pre):.6f}")
    _log(
        lines,
        f"  Corr(aNrm,cNrm|BOP) ={np.corrcoef(a_pre, c_pre)[0,1]:.6f}  (within-sample)",
    )

    ag.sim_one_period()

    m_post = np.array(ag.state_now["mNrm"], copy=True)
    a_post = np.array(ag.state_now["aNrm"], copy=True)
    p_post = np.array(ag.state_now["pLvl"], copy=True)
    c_post = np.array(ag.controls["cNrm"], copy=True)

    _log(lines, "")
    _log(lines, "=" * 72)
    _log(lines, "C. MC ensemble AFTER one sim_one_period")
    _log(lines, "=" * 72)
    _log(lines, f"  mean(mNrm) BOP next ={np.mean(m_post):.6f}  d={np.mean(m_post)-np.mean(m_pre_mc):+.6f}")
    _log(lines, f"  mean(aNrm) EOP      ={np.mean(a_post):.6f}  d={np.mean(a_post)-np.mean(a_pre):+.6f}")
    _log(lines, f"  mean(cNrm)          ={np.mean(c_post):.6f}  d={np.mean(c_post)-np.mean(c_pre):+.6f}")
    _log(lines, f"  mean(pLvl)          ={np.mean(p_post):.6f}")
    _log(
        lines,
        f"  Corr(aNrm,pLvl)     ={np.corrcoef(a_post, p_post)[0,1]:.6f}",
    )

    _log(lines, "")
    _log(lines, "=" * 72)
    _log(lines, "D. Readout (for aNrm drift question)")
    _log(lines, "=" * 72)
    _log(
        lines,
        "  TM: Under exact stationary pi, one column-stochastic step leaves pi "
        "unchanged; E[m],E[c],E[a] on the fixed grid repeat (up to numerical tol).",
    )
    _log(
        lines,
        "  MC: Injection uses jittered m within cells + iid pLvl; ensemble mean m "
        "may differ slightly from TM E[m]. One MC period applies drawn shocks and "
        "continuous policies — not identical to one sparse TM multiply.",
    )
    _log(
        lines,
        "  If mean(aNrm) moves sharply after one period, decompose: (1) injection vs "
        "TM E[a], (2) mortality/birth in sim_one_period, (3) shock draws vs TM expectations.",
    )
    _log(lines, f"  Wall time: {time()-t0:.1f}s")

    os.makedirs(os.path.dirname(_OUT_LOG), exist_ok=True)
    with open(_OUT_LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
