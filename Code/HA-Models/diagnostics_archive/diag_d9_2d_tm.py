"""
D-9: 2D TM-a (a × mrkv × p) — explicit pLvl-tracking diagnostic.

Tests whether the MC-vs-TM-a multiplier residual is from TM-a's
pLvl-marginalization assumption. Builds a full (a, mrkv, p) joint
transition matrix (instead of (a, mrkv) with pLvl handled analytically
via Q-twist), solves for ergodic, computes baseline aggregate consumption
+ Check-shock response, compares to standard TM-a and MC.

If 2D TM-a matches MC asymptotically: the bias IS specifically from
pLvl marginalization in the standard TM-a path.
If 2D TM-a STILL differs from MC: the bias is elsewhere (per-step
operator difference, discretization, etc.).

See conclusions_private/2026-05-05_mc-tm-residual-root-cause-pLvl-mrkv-conditional-bias.md
for the diagnostic chain leading here.

Usage:
    python diag_d9_2d_tm.py
"""

import os, sys
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from copy import deepcopy

# --- Bootstrap ---
sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode' if 'HAFiscal-Latest' in cwd
             else cwd)
sys.path.insert(0, os.getcwd())
os.environ['MPLBACKEND'] = 'Agg'

# Match qe_fidelity friendly-urate config (treat_seed100)
os.environ.setdefault('HAFISCAL_INTERPRETATION', 'ESC')
os.environ.setdefault('HAFISCAL_PERM_DURING_UNEMP', 'off')
os.environ.setdefault('HAFISCAL_URATE_NORMAL_H', '0.045')
os.environ.setdefault('HAFISCAL_TM_A_INDEXED', '1')
os.environ.setdefault('HAFISCAL_SPLURGE_OVERRIDE', '0')  # cleaner signal

from HARK.utilities import make_grid_exp_mult
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import (
    build_tm_agg_fiscal_a, find_ergodic_distribution,
    compute_type_aggregates_tm_a, compute_pi_q_via_cohort_age,
    _make_newborn_dist_a,
)


# ============================================================
# 2D TM (a × mrkv × p) construction
# ============================================================

def build_tm_2d(agent, aGrid, pGrid, Cratio=1.0,
                interpretation='ESC', neutral_measure=False,
                ad_tran_shk_scale=1.0, employed_tran_shk_scale=1.0,
                TranShk_addition=None, include_death=True):
    """
    Build a sparse (A*J*P) x (A*J*P) column-stochastic transition matrix
    for the joint state (a_idx, j, p_idx).

    Layout: cell_idx = j * (A * P) + a_idx * P + p_idx
            (j-major, then a, then p — matches how TM-a uses j*A indexing)

    Mortality: agent at (a, j, p) dies with prob (1-LivPrb), is replaced
    by newborn at NewBornDist (a=aGrid[0]=0, j ~ markov_ergodic,
    p ~ Lognormal(pLogInitMean, pLogInitStd)).
    """
    A = len(aGrid)
    J = agent.MrkvArray[0].shape[0]
    P = len(pGrid)
    N = A * J * P

    Splurge = float(agent.Splurge)
    Rfree_arr = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    LivPrb_arr = np.asarray(agent.LivPrb[0][:J], dtype=np.float64)
    MrkvArray = np.asarray(agent.MrkvArray[0], dtype=np.float64)
    cFuncs = [agent.solution[0].cFunc[j] for j in range(J)]
    IncShkDstn_list = agent.IncShkDstn[0]

    if TranShk_addition is None:
        TranShk_addition_arr = np.zeros(J)
    else:
        TranShk_addition_arr = np.asarray(TranShk_addition, dtype=np.float64)

    # --- Newborn distribution on (a, j, p) ---
    # Newborn lands at a=aGrid[0] (constraint), j ~ markov_ergodic
    # Newborn pLvl ~ Lognormal(pLogInitMean, pLogInitStd) → discretized on pGrid
    pLogInitMean = float(getattr(agent, 'pLogInitMean',
                                  getattr(agent, 'pLvlInitMean', 0.0)))
    pLogInitStd = float(getattr(agent, 'pLogInitStd',
                                 getattr(agent, 'pLvlInitStd', 0.0)))
    # Discretize via quantile-aligned points: probability mass at each pGrid[k]
    # = density of Lognormal at log(pGrid[k]) × bin_width, normalized
    log_pGrid = np.log(pGrid)
    if pLogInitStd > 0:
        from scipy.stats import norm as _norm
        # CDF-based mass assignment (avoids density × bin-width approximation)
        edges_log = 0.5 * (log_pGrid[:-1] + log_pGrid[1:])
        edges_log_full = np.concatenate([[-np.inf], edges_log, [np.inf]])
        cdfs = _norm.cdf(edges_log_full, loc=pLogInitMean, scale=pLogInitStd)
        nb_pLvl_probs = cdfs[1:] - cdfs[:-1]
    else:
        # Degenerate: place at nearest grid point
        nb_pLvl_probs = np.zeros(P)
        idx = np.argmin(np.abs(log_pGrid - pLogInitMean))
        nb_pLvl_probs[idx] = 1.0
    nb_pLvl_probs = nb_pLvl_probs / nb_pLvl_probs.sum()

    # Markov-ergodic for newborn j-distribution
    eigvals, eigvecs = np.linalg.eig(MrkvArray.T)
    idx_one = np.argmin(np.abs(eigvals - 1))
    markov_ergodic = np.real(eigvecs[:, idx_one])
    markov_ergodic = markov_ergodic / markov_ergodic.sum()

    # Newborn distribution: P(j) × P(p_idx) at a_idx=0
    NewBornDist = np.zeros(N)
    a_idx_nb = 0
    for jp in range(J):
        for p_idx_nb in range(P):
            cell = jp * (A * P) + a_idx_nb * P + p_idx_nb
            NewBornDist[cell] = markov_ergodic[jp] * nb_pLvl_probs[p_idx_nb]
    nb_nz_idx = np.nonzero(NewBornDist > 1e-18)[0]
    nb_nz_val = NewBornDist[nb_nz_idx]

    # --- Sparse matrix construction ---
    rows_list, cols_list, data_list = [], [], []

    for j in range(J):
        LivPrb_j = float(LivPrb_arr[j])
        death_prb = 1.0 - LivPrb_j

        # Death/rebirth (only if include_death=True; otherwise mass is lost,
        # used by forward-iterate-by-age cohort-decomposition path)
        if include_death and death_prb > 1e-18 and len(nb_nz_idx) > 0:
            for a_idx in range(A):
                for p_idx in range(P):
                    src_cell = j * (A * P) + a_idx * P + p_idx
                    rows_list.append(nb_nz_idx)
                    cols_list.append(np.full(len(nb_nz_idx), src_cell))
                    data_list.append(death_prb * nb_nz_val)

        # Survival: for each destination state j', integrate over (psi, xi)
        for jp in range(J):
            markov_prob = MrkvArray[j, jp]
            if markov_prob < 1e-15:
                continue

            dstn_jp = IncShkDstn_list[jp]
            shk_prbs = dstn_jp.pmv
            perm_shks = dstn_jp.atoms[0]
            tran_shks_raw = dstn_jp.atoms[1]
            S = len(shk_prbs)

            emp_fac = employed_tran_shk_scale if jp == 0 else 1.0
            tran_shks = (ad_tran_shk_scale * emp_fac * tran_shks_raw
                         + TranShk_addition_arr[jp])

            # Iterate over source (a, p) and shock atoms
            inv_pG = 1.0 / (perm_shks * PermGroFac_arr[jp])  # (S,)
            for a_idx in range(A):
                a_src = aGrid[a_idx]
                # m_next for each shock atom (same for all source p_idx)
                m_next = Rfree_arr[jp] * a_src * inv_pG + tran_shks  # (S,)
                c_star = cFuncs[jp](m_next, np.full_like(m_next, Cratio))  # (S,)
                xi_arr = tran_shks  # (S,)
                if interpretation == 'CDC':
                    c_actual = (1.0 - Splurge) * c_star + Splurge * xi_arr
                else:  # ESC
                    c_actual = c_star
                a_next = np.maximum(m_next - c_actual, 0.0)  # (S,)

                # a' lottery on aGrid (clamped at boundaries — all mass to corner)
                a_idx_next = np.searchsorted(aGrid, a_next, side='right') - 1
                a_below = a_next <= aGrid[0]
                a_above = a_next >= aGrid[-1]
                a_idx_next = np.clip(a_idx_next, 0, A - 2)
                a_lo = a_idx_next
                a_hi = a_idx_next + 1
                a_grid_lo = aGrid[a_lo]
                a_grid_hi = aGrid[a_hi]
                a_span = a_grid_hi - a_grid_lo
                a_span = np.where(a_span < 1e-30, 1.0, a_span)
                a_upper_wt_interior = np.clip((a_next - a_grid_lo) / a_span, 0.0, 1.0)
                a_lower_wt_interior = 1.0 - a_upper_wt_interior

                # Construct safe (lo_idx, hi_idx, lo_wt, hi_wt) per atom:
                # below: all to grid[0]   (lo_idx=0, hi_idx=0, lo_wt=1, hi_wt=0)
                # above: all to grid[-1]  (lo_idx=A-1, hi_idx=A-1, lo_wt=1, hi_wt=0)
                # interior: lottery
                a_lo_safe = np.where(a_below, 0,
                                     np.where(a_above, A - 1, a_lo))
                a_hi_safe = np.where(a_below, 0,
                                     np.where(a_above, A - 1, a_hi))
                a_low_w = np.where(a_below | a_above, 1.0, a_lower_wt_interior)
                a_up_w = np.where(a_below | a_above, 0.0, a_upper_wt_interior)

                for p_idx in range(P):
                    p_src = pGrid[p_idx]
                    # p_next = G * psi * p_src for each shock atom
                    p_next = PermGroFac_arr[jp] * perm_shks * p_src  # (S,)

                    # p' lottery on log(pGrid) (clamped at boundaries — all mass to corner)
                    log_p_next = np.log(p_next)
                    p_idx_next = np.searchsorted(log_pGrid, log_p_next, side='right') - 1
                    p_below = log_p_next <= log_pGrid[0]
                    p_above = log_p_next >= log_pGrid[-1]
                    p_idx_next = np.clip(p_idx_next, 0, P - 2)
                    p_lo = p_idx_next
                    p_hi = p_idx_next + 1
                    p_grid_lo = log_pGrid[p_lo]
                    p_grid_hi = log_pGrid[p_hi]
                    p_span = p_grid_hi - p_grid_lo
                    p_span = np.where(p_span < 1e-30, 1.0, p_span)
                    p_upper_wt_interior = np.clip((log_p_next - p_grid_lo) / p_span, 0.0, 1.0)
                    p_lower_wt_interior = 1.0 - p_upper_wt_interior
                    p_lo_safe = np.where(p_below, 0,
                                         np.where(p_above, P - 1, p_lo))
                    p_hi_safe = np.where(p_below, 0,
                                         np.where(p_above, P - 1, p_hi))
                    p_low_w = np.where(p_below | p_above, 1.0, p_lower_wt_interior)
                    p_up_w = np.where(p_below | p_above, 0.0, p_upper_wt_interior)

                    src_cell = j * (A * P) + a_idx * P + p_idx
                    weight_base = markov_prob * LivPrb_j * shk_prbs

                    # 4 lottery cells per shock: (a_lo, p_lo), (a_lo, p_hi),
                    # (a_hi, p_lo), (a_hi, p_hi)
                    for a_use, a_w in [(a_lo_safe, a_low_w), (a_hi_safe, a_up_w)]:
                        for p_use, p_w in [(p_lo_safe, p_low_w), (p_hi_safe, p_up_w)]:
                            wt = weight_base * a_w * p_w
                            mask = wt > 1e-20
                            if not np.any(mask):
                                continue
                            dst_cells = jp * (A * P) + a_use[mask] * P + p_use[mask]
                            rows_list.append(dst_cells)
                            cols_list.append(np.full(int(mask.sum()), src_cell))
                            data_list.append(wt[mask])

    all_rows = np.concatenate(rows_list)
    all_cols = np.concatenate(cols_list)
    all_data = np.concatenate(data_list)

    T = sp.csc_matrix((all_data, (all_rows, all_cols)), shape=(N, N))
    return T, NewBornDist


def forward_iterate_cohort_2d(agent, aGrid, pGrid, T_age, Cratio=1.0,
                               interpretation='ESC',
                               TranShk_addition=None,
                               return_per_age=False):
    """
    Forward-iterate 2D (a, j, p) distribution for T_age cohort ages.

    For each age k = 0, ..., T_age-1:
      π[age=k+1] = T_survive @ π[age=k]   (renormalized to sum=1)
    where T_survive is the 2D kernel WITH mortality removed (so column sums
    to LivPrb_j, not 1; the lost mass represents agents who died at this age).

    Returns the truncated-geometric-weighted steady-state distribution:
      π_steady = sum_k P(age=k) × π[age=k]
    where P(age=k) ∝ L^k for k=0..T_age-1.

    This handles T_age cap exactly (matching MC's deterministic cap at T_age).
    """
    A = len(aGrid)
    J = agent.MrkvArray[0].shape[0]
    P = len(pGrid)
    N = A * J * P

    # Survival-only kernel (mortality removed; mass leaks to represent deaths)
    T_surv, NewBornDist = build_tm_2d(agent, aGrid, pGrid, Cratio=Cratio,
                                       interpretation=interpretation,
                                       TranShk_addition=TranShk_addition,
                                       include_death=False)

    # Initial distribution: newborns at age 0
    pi_age = NewBornDist.copy()
    pi_age = pi_age / pi_age.sum()

    pi_per_age = [pi_age.copy()] if return_per_age else None

    # Truncated-geometric age weights
    LivPrb = float(np.asarray(agent.LivPrb[0][:J]).max())  # uniform across j
    age_weights = np.array([LivPrb**k for k in range(T_age)])
    age_weights = age_weights / age_weights.sum()

    pi_steady = age_weights[0] * pi_age

    for k in range(1, T_age):
        pi_age = T_surv @ pi_age
        # Conditional on survival: renormalize to sum=1
        s = pi_age.sum()
        if s > 0:
            pi_age = pi_age / s
        pi_steady = pi_steady + age_weights[k] * pi_age
        if return_per_age:
            pi_per_age.append(pi_age.copy())

    return pi_steady, pi_per_age


def aggregate_2d_consumption(ergodic_2d, agent, aGrid, pGrid, Cratio=1.0,
                              interpretation='ESC',
                              ad_tran_shk_scale=1.0, employed_tran_shk_scale=1.0,
                              TranShk_addition=None):
    """
    Aggregate consumption × pLvl using the 2D ergodic.

    E[C_actual] = sum_{(a, j, p)} π(a, j, p) × E_{j', psi, xi}[c_actual × p']
    where c_actual = (1-S)*c* + S*xi (CDC) or c* (ESC), p' = G*psi*p.
    """
    A = len(aGrid)
    J = agent.MrkvArray[0].shape[0]
    P = len(pGrid)
    Splurge = float(agent.Splurge)
    Rfree_arr = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac_arr = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    LivPrb_arr = np.asarray(agent.LivPrb[0][:J], dtype=np.float64)
    MrkvArray = np.asarray(agent.MrkvArray[0], dtype=np.float64)
    cFuncs = [agent.solution[0].cFunc[j] for j in range(J)]
    IncShkDstn_list = agent.IncShkDstn[0]

    if TranShk_addition is None:
        TranShk_addition_arr = np.zeros(J)
    else:
        TranShk_addition_arr = np.asarray(TranShk_addition, dtype=np.float64)

    # Reshape ergodic to (J, A, P)
    erg = ergodic_2d.reshape(J, A, P)

    C_total = 0.0  # E[c_actual × p_lvl]
    Y_total = 0.0  # E[xi_eff × p_lvl] (for income)

    for j in range(J):
        for jp in range(J):
            markov_prob = MrkvArray[j, jp]
            if markov_prob < 1e-15:
                continue
            dstn_jp = IncShkDstn_list[jp]
            shk_prbs = dstn_jp.pmv
            perm_shks = dstn_jp.atoms[0]
            tran_shks_raw = dstn_jp.atoms[1]
            S = len(shk_prbs)

            emp_fac = employed_tran_shk_scale if jp == 0 else 1.0
            tran_shks = (ad_tran_shk_scale * emp_fac * tran_shks_raw
                         + TranShk_addition_arr[jp])

            inv_pG = 1.0 / (perm_shks * PermGroFac_arr[jp])  # (S,)
            for a_idx in range(A):
                a_src = aGrid[a_idx]
                m_next = Rfree_arr[jp] * a_src * inv_pG + tran_shks  # (S,)
                c_star = cFuncs[jp](m_next, np.full_like(m_next, Cratio))
                xi_arr = tran_shks
                if interpretation == 'CDC':
                    c_actual = (1.0 - Splurge) * c_star + Splurge * xi_arr
                else:
                    c_actual = c_star

                # For each source p_idx, the new pLvl is G * psi * p_src
                p_factor_per_shock = PermGroFac_arr[jp] * perm_shks  # (S,)

                for p_idx in range(P):
                    p_src = pGrid[p_idx]
                    if erg[j, a_idx, p_idx] < 1e-20:
                        continue
                    p_next_arr = p_factor_per_shock * p_src  # (S,)
                    weight = markov_prob * LivPrb_j(LivPrb_arr, j) * erg[j, a_idx, p_idx] * shk_prbs
                    C_total += float(np.sum(weight * c_actual * p_next_arr))
                    Y_total += float(np.sum(weight * xi_arr * p_next_arr))

    return C_total, Y_total


def LivPrb_j(LivPrb_arr, j):
    return float(LivPrb_arr[j])


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 70)
    print("D-9: 2D TM-a (a × mrkv × p) diagnostic")
    print("=" * 70)

    # --- Load HS agent (pattern from test_tm_a_indexed.py:38-74) ---
    print("\nLoading HS agent setup...")
    from HARK.distributions import DiscreteDistribution
    (init_dropout, init_highschool, init_college, init_ADEconomy,
     DiscFacDstns, DiscFacCount, AgentCountTotal, base_dict,
     num_max_iterations_solvingAD, convergence_tol_solvingAD,
     UBspell_normal, num_base_MrkvStates, data_EducShares,
     max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes, Check_changes,
     recession_Check_changes) = return_parameters(
        Parametrization='Reduced_Run', OutputFor='_Main.py')

    econ = AggregateDemandEconomy(**init_ADEconomy)
    hs_base = AggFiscalType(**init_highschool)
    hs_base.cycles = 0
    hs_base.get_economy_data(econ)

    # Build IncShkDstn per Markov state (mirrors test_tm_a_indexed.py:57-67)
    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([hs_base.IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([hs_base.IncUnempNoBenefits])])
    EmployedIncShkDstn = deepcopy(hs_base.IncShkDstn[0])
    hs_base.IncShkDstn = [[EmployedIncShkDstn]
                          + [IncShkDstn_unemp] * UBspell_normal
                          + [IncShkDstn_unemp_nobenefits]]
    hs_base.IncShkDstn_base = hs_base.IncShkDstn

    # Use the central beta atom (Reduced_Run uses point beta, index 0)
    hs_base.DiscFac = float(DiscFacDstns[1].atoms[0][0])

    econ.agents = [hs_base]
    hs_base.update_mrkv_array("base")
    hs_base.solve()
    print(f"  HS agent solved. cFunc has {len(hs_base.solution[0].cFunc)} Markov-state branches.")
    print(f"  PermGroFac: {hs_base.PermGroFac[0][:4]}")
    print(f"  LivPrb: {hs_base.LivPrb[0][:4]}")
    print(f"  Splurge: {hs_base.Splurge}")
    print(f"  pLogInitMean: {getattr(hs_base, 'pLogInitMean', getattr(hs_base, 'pLvlInitMean', 'N/A'))}")
    print(f"  pLogInitStd: {getattr(hs_base, 'pLogInitStd', getattr(hs_base, 'pLvlInitStd', 'N/A'))}")

    # --- Set up grids ---
    A = 50  # a-grid bins
    P = 60  # p-grid bins (wider range to avoid right-tail clipping)
    aGrid = make_grid_exp_mult(ming=0.001, maxg=40.0, ng=A, timestonest=3)
    aGrid = np.concatenate([[0.0], aGrid])
    A = len(aGrid)
    # pGrid: log-spaced from 0.5 to 500 to capture right tail of pLvl distribution
    pGrid = np.exp(np.linspace(np.log(0.5), np.log(500.0), P))
    print(f"\nGrids: A={A}, P={P}, J={4}, total cells = {A*4*P}")

    # --- Build standard 1D TM-a for comparison ---
    print("\n--- Building standard 1D TM-a (for comparison) ---")
    tm_1d = build_tm_agg_fiscal_a(hs_base, aCount=A, Cratio=1.0,
                                  neutral_measure=False,
                                  interpretation='ESC')
    erg_1d = find_ergodic_distribution(tm_1d['TranMatrix'])
    print(f"  1D ergodic computed; sum={erg_1d.sum():.6f}")

    # 1D aggregate via existing function
    agg_1d = compute_type_aggregates_tm_a(hs_base, tm_1d, erg_1d,
                                           neutral_measure=False,
                                           interpretation='ESC')
    print(f"  1D base aggregates: C_nrm={agg_1d['C_nrm']:.4f}, Income_nrm={agg_1d['Income_nrm']:.4f}")
    print(f"  Note: these are NORMALIZED (C_nrm = E[c_normalized], not E[c × pLvl])")

    # --- Build 2D TM-a ---
    print("\n--- Building 2D TM-a (a × mrkv × p) ---")
    import time as _time
    t0 = _time.time()
    T_2d, nb_2d = build_tm_2d(hs_base, aGrid, pGrid, Cratio=1.0,
                               interpretation='ESC')
    print(f"  2D TM constructed in {_time.time()-t0:.1f}s; nnz={T_2d.nnz}")
    print(f"  Sparsity: {T_2d.nnz / (T_2d.shape[0]**2) * 100:.4f}%")

    # Solve for ergodic
    print("  Solving for 2D ergodic...")
    t0 = _time.time()
    erg_2d = find_ergodic_distribution(T_2d)
    print(f"  Done in {_time.time()-t0:.1f}s; sum={erg_2d.sum():.6f}")

    # --- Aggregate from 2D ergodic ---
    print("\n--- Aggregating consumption from 2D ergodic ---")
    C_2d, Y_2d = aggregate_2d_consumption(erg_2d, hs_base, aGrid, pGrid,
                                           Cratio=1.0, interpretation='ESC')
    print(f"  E[C × pLvl] (2D, full real $) = {C_2d:.4f}")
    print(f"  E[Y × pLvl] (2D)              = {Y_2d:.4f}")

    # --- Compare to 1D ---
    # 1D's C_nrm is E[c_normalized], to get E[c × pLvl] need to multiply by E[pLvl]
    E_pLvl_marginal = float(np.sum(erg_2d.reshape(4, A, P).sum(axis=(0, 1)) * pGrid))
    print(f"\n  E[pLvl] (from 2D marginal)    = {E_pLvl_marginal:.4f}")
    C_1d_implied = agg_1d['C_nrm'] * E_pLvl_marginal
    print(f"  E[C × pLvl] (1D × E[pLvl])    = {C_1d_implied:.4f}")
    print(f"  Δ (2D − 1D) / 1D              = {(C_2d - C_1d_implied)/C_1d_implied*100:+.3f}%")

    # --- Mean / variance of pLvl from 2D vs analytical ---
    p_marginal = erg_2d.reshape(4, A, P).sum(axis=(0, 1))
    p_marginal /= p_marginal.sum()
    E_log_p = float(np.sum(p_marginal * np.log(pGrid)))
    print(f"\n  Mean log(pLvl) (2D ergodic) = {E_log_p:.4f}")
    print("  MC empirical mean log(p) (HS) = 2.5474")

    # --- Conditional E[pLvl | mrkv state] from 2D ergodic ---
    print("\n  E[pLvl | mrkv] from 2D ergodic:")
    erg_3d = erg_2d.reshape(4, A, P)
    for j_label, jp in [('E', 0), ('UB1', 1), ('UB2', 2), ('noUB', 3)]:
        marg_j = erg_3d[jp].sum()
        if marg_j > 0:
            p_marg_j = erg_3d[jp].sum(axis=0) / marg_j
            mean_log_p_j = float(np.sum(p_marg_j * np.log(pGrid)))
            print(f"    {j_label:<5} π={marg_j:.4f}  mean log(p)={mean_log_p_j:.4f}")

    print("\n=== Sanity check vs MC empirical ===")
    print("  MC HS marginal mean log(p)  = 2.5474")
    print("  MC HS E    mean log(p)      = 2.5484 (Δ = +0.001)")
    print("  MC HS UB1  mean log(p)      = 2.5073 (Δ = -0.040)")
    print("  MC HS UB2  mean log(p)      = 2.5154 (Δ = -0.032)")

    # ============================================================
    # DEBUG: 2D pLvl marginal shape
    # ============================================================
    print("\n=== DEBUG: pLvl marginal from 2D ergodic ===")
    p_marg = erg_2d.reshape(4, A, P).sum(axis=(0, 1))
    p_marg /= p_marg.sum()
    print(f"  pGrid bounds: [{pGrid[0]:.3f}, {pGrid[-1]:.3f}]")
    print(f"  Mass at p_idx=0 (lowest):  {p_marg[0]:.4f}")
    print(f"  Mass at p_idx=P-1 (highest): {p_marg[-1]:.4f}")
    print(f"  Top 5 p-bins by mass:")
    top5 = np.argsort(p_marg)[-5:][::-1]
    for idx in top5:
        print(f"    pGrid[{idx}]={pGrid[idx]:.3f} (log={np.log(pGrid[idx]):.3f}): mass={p_marg[idx]:.4f}")
    print(f"  Cumulative mass at log(p) <= 2.5 (i.e., p <= 12.2): "
          f"{p_marg[np.log(pGrid) <= 2.5].sum():.4f}")
    print(f"  Cumulative mass at log(p) <= 3.0 (i.e., p <= 20.1): "
          f"{p_marg[np.log(pGrid) <= 3.0].sum():.4f}")

    # Predicted analytical: with LivPrb=0.99375 (no T_age cap),
    # E[age] = L/(1-L) = 159 quarters; per-period log growth ≈ 0.00357 (employed weighted)
    # Predicted mean log p = pLogInitMean + 0.00357 × E[age] = 2.41 + 0.57 = 2.98
    print(f"\n  Analytical predicted mean log p (no T_age cap): 2.98")
    print(f"  Analytical predicted mean log p (T_age=100 cap, E[age]≈44): 2.57")
    print(f"  2D TM observed mean log p: 2.40 (close to newborn 2.41 — too low!)")
    print()
    print("=== Full pLvl marginal distribution ===")
    for idx in range(0, P, 2):
        bar = "█" * int(p_marg[idx] * 200)
        print(f"  pGrid[{idx:2d}]={pGrid[idx]:7.3f} (log={np.log(pGrid[idx]):+.3f}): {p_marg[idx]:.4f} {bar}")
    print(f"  Empirical mean log(p) = {(p_marg * np.log(pGrid)).sum():.4f}")
    print(f"  Empirical mean(p)     = {(p_marg * pGrid).sum():.4f}")
    print(f"  Newborn lognormal mean log p = {pLogInitMean if 'pLogInitMean' in dir() else 'N/A'}")
    # Cross-check: actual newborn distribution we used
    log_pg = np.log(pGrid)
    pLogInitMean_val = float(getattr(hs_base, 'pLogInitMean',
                                      getattr(hs_base, 'pLvlInitMean', 0.0)))
    pLogInitStd_val = float(getattr(hs_base, 'pLogInitStd',
                                     getattr(hs_base, 'pLvlInitStd', 0.0)))
    from scipy.stats import norm as _norm
    edges = 0.5 * (log_pg[:-1] + log_pg[1:])
    edges_full = np.concatenate([[-np.inf], edges, [np.inf]])
    cdfs = _norm.cdf(edges_full, loc=pLogInitMean_val, scale=pLogInitStd_val)
    nb_probs = cdfs[1:] - cdfs[:-1]
    nb_probs /= nb_probs.sum()
    print(f"  Newborn dist mean log p (used in TM)    = {(nb_probs * log_pg).sum():.4f}")
    print(f"  Newborn dist mean p (used in TM)        = {(nb_probs * pGrid).sum():.4f}")

    # ============================================================
    # 3D-via-cohort: forward iterate 2D survival kernel by age, then weight
    # by truncated-geometric mortality (T_age cap = 100, matching MC)
    # ============================================================
    print("\n=== 3D-via-cohort: T_age=100 cap (matches MC's deterministic cap) ===")
    T_age = 100
    print(f"  Forward iterating 2D survival kernel for T_age={T_age} ages...")
    import time as _t
    t0 = _t.time()
    pi_3d, _ = forward_iterate_cohort_2d(hs_base, aGrid, pGrid, T_age,
                                          Cratio=1.0, interpretation='ESC')
    print(f"  Done in {_t.time()-t0:.1f}s")

    p_marg_3d = pi_3d.reshape(4, A, P).sum(axis=(0, 1))
    p_marg_3d /= p_marg_3d.sum()
    mean_lp_3d = (p_marg_3d * np.log(pGrid)).sum()
    mean_p_3d = (p_marg_3d * pGrid).sum()
    print(f"  3D-via-cohort mean log(p) = {mean_lp_3d:.4f}")
    print(f"  3D-via-cohort mean(p)     = {mean_p_3d:.4f}")
    print(f"  MC empirical (HS)         = 2.5474 (target)")
    print(f"  Δ from MC                  = {mean_lp_3d - 2.5474:+.4f}")

    # Conditional E[log p | mrkv]
    pi_3d_3 = pi_3d.reshape(4, A, P)
    print(f"\n  E[log p | mrkv] from 3D-via-cohort:")
    for j_label, jp in [('E', 0), ('UB1', 1), ('UB2', 2), ('noUB', 3)]:
        marg_j = pi_3d_3[jp].sum()
        if marg_j > 0:
            p_marg_j = pi_3d_3[jp].sum(axis=0) / marg_j
            mean_log_p_j = (p_marg_j * np.log(pGrid)).sum()
            delta = mean_log_p_j - mean_lp_3d
            print(f"    {j_label:<5} π={marg_j:.4f}  mean log(p)={mean_log_p_j:.4f}  Δ from marginal={delta:+.4f}")
    print()
    print("  MC empirical Δ from marginal:")
    print(f"    E    Δ = +0.001")
    print(f"    UB1  Δ = -0.040")
    print(f"    UB2  Δ = -0.032")


if __name__ == "__main__":
    main()
