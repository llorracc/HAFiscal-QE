"""Phase 3: Control-variate welfare6 estimator with bootstrap SE.

Combines:
  - Full MC estimator W^U_MC from prob-weighted cLvl_all_splurge.
  - MC-L2 estimator W^U_L2 from the bootstrap-source panels (_bs keys),
    bucketing by j^pol (policy scenario's Markov state) per companion
    doc §12.2 bullet 3.

Bootstrap over agents (resampled with replacement, same indices for all
three scenarios per cell to respect CRN). Per resample b:
  - ŵ_MC,b  = W^U_MC applied to resampled prob-weighted panel
  - ŵ_L2,b  = W^U_L2 applied to resampled modal-duration (_bs) panel
Plug-in TM-L2: the full-panel W^U_L2 (i.e., center MC-L2 on itself, so
the CV only reduces the *reported SE*, not the point estimate).

Report per cell: W^U_MC, W^U_L2, corr(ŵ_MC, ŵ_L2), β̂, bootstrap SE of
ŵ_MC, bootstrap SE of ŵ_CV = ŵ_MC - β̂(ŵ_L2 - W^U_L2), variance-reduction
factor (1 - ρ²).

Usage:
    cd Code/HA-Models/FromPandemicCode
    python compute_welfare6_control_variate.py
    python compute_welfare6_control_variate.py --n-boot 500 --seed 42
"""
import argparse
import pickle
from pathlib import Path

import numpy as np

from compute_welfare6_mc_l2 import (
    CELLS, CRRA, DIR, R, T, compute_full_mc_WU, compute_mc_l2_WU,
    load_scenarios,
)


def _bootstrap_indices(N, n_boot, rng):
    """(n_boot, N) matrix of bootstrap indices."""
    return rng.integers(0, N, size=(n_boot, N))


def _apply_indices_panel(panel, idx):
    """panel (T, N) → panel[:, idx] (T, N) using bootstrap indices idx (N,)."""
    return panel[:, idx]


def _bootstrap_cell(pol, none, base, pol_cost, none_cost,
                    discount, n_boot, rng, cond="j_pol", formula="l2"):
    """Bootstrap both MC and MC-L2 (or L3-joint) estimators on the same
    resampled agent indices. Returns arrays of shape (n_boot,).

    cond: "j_pol" to bucket by policy scenario's state (default, per
    companion doc §12.2 bullet 3), or "j_base" to bucket by baseline
    scenario's state (per plan §3.3 "shared state" framing).
    IGNORED when formula="joint".

    formula:
      - "l2":    L2 factorization — bucket by single state (per `cond`),
                 factorize Num and Base within each bucket:
                   W = Σ_j f_j · E[Num|j] · E[Base|j] / (1-ρ)
      - "joint": L3-like joint (j^pol, j^base) bucketing:
                   W = Σ_{(j^p, j^b)} f_{(j^p,j^b)} · E[Num|j^p] · E[Base|j^b] / (1-ρ)
                 Captures companion doc §6 policy-vs-baseline state
                 mismatch (e.g., noUB agents split by chronic/induced).
    """
    c_pol_pw  = np.asarray(pol["cLvl_all_splurge"])
    c_none_pw = np.asarray(none["cLvl_all_splurge"])
    c_base_pw = np.asarray(base["cLvl_all_splurge"])
    # Paper-consistent fixed AD=0 denominator (Welfare.py:277,284)
    agg_pol   = np.asarray(pol_cost["AggIncome"])
    agg_none  = np.asarray(none_cost["AggIncome"])
    agg_cons_pol  = np.asarray(pol_cost["AggCons"])
    agg_cons_none = np.asarray(none_cost["AggCons"])

    c_pol_bs  = np.asarray(pol["cLvl_all_splurge_bs"])
    c_none_bs = np.asarray(none["cLvl_all_splurge_bs"])
    c_base_bs = np.asarray(base["cLvl_all_splurge_bs"])
    p_pol_bs  = np.asarray(pol["pLvl_all_bs"])
    p_none_bs = np.asarray(none["pLvl_all_bs"])
    p_base_bs = np.asarray(base["pLvl_all_bs"])
    j_pol_bs_raw  = np.asarray(pol["Mrkv_hist_bs"])
    j_base_bs_raw = np.asarray(base["Mrkv_hist_bs"])

    if formula == "l2":
        if cond == "j_pol":
            j_cond_bs = j_pol_bs_raw
        elif cond == "j_base":
            j_cond_bs = j_base_bs_raw
        else:
            raise ValueError(f"unknown cond {cond!r}")
    elif formula == "joint":
        j_cond_bs = None  # not used; we use j_pol_bs_raw and j_base_bs_raw directly
    else:
        raise ValueError(f"unknown formula {formula!r}")

    N = min(c_pol_pw.shape[1], c_none_pw.shape[1], c_base_pw.shape[1],
            c_pol_bs.shape[1], c_none_bs.shape[1], c_base_bs.shape[1])
    c_pol_pw  = c_pol_pw[:, :N];   c_none_pw = c_none_pw[:, :N];  c_base_pw = c_base_pw[:, :N]
    c_pol_bs  = c_pol_bs[:, :N];   c_none_bs = c_none_bs[:, :N];  c_base_bs = c_base_bs[:, :N]
    p_pol_bs  = p_pol_bs[:, :N];   p_none_bs = p_none_bs[:, :N];  p_base_bs = p_base_bs[:, :N]
    if j_cond_bs is not None:
        j_cond_bs = j_cond_bs[:, :N]
    j_pol_bs_raw  = j_pol_bs_raw[:, :N]
    j_base_bs_raw = j_base_bs_raw[:, :N]

    # Pre-compute per-agent per-period quantities.
    #
    # MC integrand (per agent): A_pw_i = Σ_t R^{-t} [u(c_pol_pw) - u(c_none_pw)] / u'(c_base_pw)
    rho = CRRA
    du_pw    = (c_pol_pw ** (1-rho) - c_none_pw ** (1-rho)) / (1-rho)
    mu_pw    = c_base_pw ** (-rho)
    A_pw_i   = ((du_pw / mu_pw) * discount[:, None]).sum(axis=0)   # (N,)
    # Paper-consistent fixed AD=0 denominator per Welfare.py:277,284.
    # NPV_cost and NPV_Δc come from the pol_cost/none_cost scenarios
    # (always the AD=0 pair for a given policy). Held constant across
    # bootstrap resamples — captures numerator-only SE.
    NPV_cost = float(((agg_pol - agg_none) * discount).sum())
    NPV_Dc   = float(((agg_cons_pol - agg_cons_none) * discount).sum())
    if NPV_cost == 0:
        return None
    W_B_fixed = (NPV_cost - NPV_Dc) / NPV_cost   # budget residual, cell-invariant within a policy

    # MC-L2 quantities — precompute per-agent per-period X^α
    X_pol  = c_pol_bs  / p_pol_bs
    X_none = c_none_bs / p_none_bs
    X_base = c_base_bs / p_base_bs
    Xpol_alpha  = X_pol  ** (1 - rho)  # (T, N)
    Xnone_alpha = X_none ** (1 - rho)
    Xbase_beta  = X_base ** rho
    # Use unified n_states covering both j^pol and j^base for simplicity
    n_states = int(max(j_pol_bs_raw.max(), j_base_bs_raw.max())) + 1

    def _mc_l2_estimate(resample_idx):
        """Compute W^U_L2 on a resampled panel via vectorized bincount.
        Bucketing uses j_cond_bs (either j^pol or j^base per cond flag)."""
        j_p = j_cond_bs[:, resample_idx]   # (T, N_rs)
        Xp  = Xpol_alpha[:, resample_idx]
        Xn  = Xnone_alpha[:, resample_idx]
        Xb  = Xbase_beta[:, resample_idx]
        p_b = p_base_bs[:, resample_idx]
        E_pt = p_b.mean(axis=1)           # (T,)
        N_rs = len(resample_idx)
        L2_t = np.zeros(T)
        for t in range(T):
            jt = j_p[t]
            counts = np.bincount(jt, minlength=n_states).astype(float)
            s_Xp   = np.bincount(jt, weights=Xp[t], minlength=n_states)
            s_Xn   = np.bincount(jt, weights=Xn[t], minlength=n_states)
            s_Xb   = np.bincount(jt, weights=Xb[t], minlength=n_states)
            active = counts > 0
            m_Xp = np.zeros(n_states); m_Xp[active] = s_Xp[active] / counts[active]
            m_Xn = np.zeros(n_states); m_Xn[active] = s_Xn[active] / counts[active]
            m_Xb = np.zeros(n_states); m_Xb[active] = s_Xb[active] / counts[active]
            f_j = counts / N_rs
            L2_t[t] = float(((m_Xp - m_Xn) / (1 - rho) * m_Xb * f_j).sum())
        return N_rs * float((discount * E_pt * L2_t).sum()) / NPV_cost

    def _mc_joint_estimate(resample_idx):
        """Compute W^U_L3 with proper joint conditioning:
           W = N · Σ_t R^{-t} · E[p_t] · (1/(1-ρ)) · Σ_{j^p, j^b} f_{(j^p,j^b)}
                · E[Num | j^p, j^b] · E[Base | j^b]
        This captures within-bucket chronic-vs-induced heterogeneity that
        the single-state L2 misses (companion doc §6 mechanism)."""
        jp = j_pol_bs_raw[:,  resample_idx]
        jb = j_base_bs_raw[:, resample_idx]
        Xp  = Xpol_alpha[:, resample_idx]
        Xn  = Xnone_alpha[:, resample_idx]
        Xb  = Xbase_beta[:, resample_idx]
        p_b = p_base_bs[:, resample_idx]
        E_pt = p_b.mean(axis=1)
        N_rs = len(resample_idx)
        L_t = np.zeros(T)
        n_sq = n_states * n_states
        for t in range(T):
            combo = jp[t].astype(np.int64) * n_states + jb[t].astype(np.int64)
            # Joint counts / fractions
            cnt_joint = np.bincount(combo, minlength=n_sq).astype(float)
            # Num numerator sums per (j^p, j^b)
            s_Xp = np.bincount(combo, weights=Xp[t], minlength=n_sq)
            s_Xn = np.bincount(combo, weights=Xn[t], minlength=n_sq)
            act_j = cnt_joint > 0
            Num_joint = np.zeros(n_sq)
            Num_joint[act_j] = (s_Xp[act_j] - s_Xn[act_j]) / cnt_joint[act_j]
            # Base per j^b (marginal)
            cnt_b = np.bincount(jb[t], minlength=n_states).astype(float)
            s_Xb  = np.bincount(jb[t], weights=Xb[t], minlength=n_states)
            act_b = cnt_b > 0
            Base = np.zeros(n_states)
            Base[act_b] = s_Xb[act_b] / cnt_b[act_b]
            # f_{(j^p, j^b)} · Num_{j^p,j^b} · Base_{j^b}
            f_joint = cnt_joint / N_rs
            # Broadcast Base over j^p axis: NumReshape is (n_p, n_b), Base is (n_b,)
            Num_2d = Num_joint.reshape(n_states, n_states)
            F_2d   = f_joint.reshape(n_states, n_states)
            # Σ_{j^p, j^b} F · Num · Base[j^b] = Σ_{j^b} Base[j^b] · Σ_{j^p} F · Num
            # = Σ_{j^b} Base[j^b] · (F * Num_2d).sum(axis=0)[j^b]
            inner = (F_2d * Num_2d).sum(axis=0)  # (n_b,) — Σ_{j^p} F · Num_{j^p,j^b}
            L_t[t] = float((inner * Base).sum()) / (1 - rho)
        return N_rs * float((discount * E_pt * L_t).sum()) / NPV_cost

    _estimate = _mc_joint_estimate if formula == "joint" else _mc_l2_estimate

    # Full-panel (unresampled) values — used as centering for the plug-in TM-L2.
    full_idx = np.arange(N)
    W_MC_full = float(A_pw_i.sum()) / NPV_cost
    W_L2_full = _estimate(full_idx)

    # Bootstrap
    idx_mat = _bootstrap_indices(N, n_boot, rng)
    boot_MC = np.empty(n_boot)
    boot_L2 = np.empty(n_boot)
    for b in range(n_boot):
        idx = idx_mat[b]
        boot_MC[b] = A_pw_i[idx].sum() / NPV_cost
        boot_L2[b] = _estimate(idx)

    return {
        "N": N,
        "W_MC_full":  W_MC_full,      # W^U (utility part only)
        "W_L2_full":  W_L2_full,      # L2 proxy for W^U
        "W_B_fixed":  W_B_fixed,      # budget residual (fixed at AD=0)
        "W_6_MC":     W_MC_full + W_B_fixed,
        "W_6_L2":     W_L2_full + W_B_fixed,
        "boot_MC":    boot_MC,
        "boot_L2":    boot_L2,
        "NPV_cost":   NPV_cost,
    }


def compute_cv_stats(result):
    """Given bootstrap arrays, compute β̂, ρ, and CV-corrected SE."""
    boot_MC = result["boot_MC"]
    boot_L2 = result["boot_L2"]
    W_L2_full = result["W_L2_full"]

    SE_MC = float(boot_MC.std(ddof=1))
    SE_L2 = float(boot_L2.std(ddof=1))
    cov   = float(np.cov(boot_MC, boot_L2, ddof=1)[0, 1])
    rho   = cov / (SE_MC * SE_L2) if SE_MC * SE_L2 > 0 else float("nan")
    beta  = cov / float(np.var(boot_L2, ddof=1)) if SE_L2 > 0 else float("nan")
    boot_CV = boot_MC - beta * (boot_L2 - W_L2_full)
    SE_CV = float(boot_CV.std(ddof=1))
    vr    = 1.0 - (SE_CV / SE_MC) ** 2 if SE_MC > 0 else float("nan")
    return {
        "SE_MC": SE_MC, "SE_L2": SE_L2, "SE_CV": SE_CV,
        "rho": rho, "beta": beta, "variance_reduction": vr,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cond", choices=("j_pol", "j_base"), default="j_pol",
                    help="State used for L2 bucketing (default: j_pol). "
                         "Ignored when --formula=joint.")
    ap.add_argument("--formula", choices=("l2", "joint"), default="l2",
                    help="L2 single-state factorization (default) or "
                         "joint (j^pol, j^base) 2-index bucketing.")
    args = ap.parse_args()

    sc = load_scenarios()
    discount = R ** (-np.arange(T))
    rng = np.random.default_rng(args.seed)

    print(f"Bootstrap: n_boot={args.n_boot}, seed={args.seed}, "
          f"cond={args.cond}, formula={args.formula}")
    print()
    print(f"{'cell':22s} {'W_6':>7s} {'W^U':>7s} {'W^B':>7s} "
          f"{'SE_MC':>7s} {'SE_CV':>7s} "
          f"{'rel_MC':>7s} {'rel_CV':>7s} "
          f"{'ρ':>5s} {'β':>6s} {'VR%':>5s}")
    print("-" * 100)
    for label, pol_k, none_k, base_k, pol_cost_k, none_cost_k in CELLS:
        if not all(k in sc for k in (pol_k, none_k, base_k, pol_cost_k, none_cost_k)):
            print(f"{label:22s}  [skip]")
            continue
        res = _bootstrap_cell(sc[pol_k], sc[none_k], sc[base_k],
                              sc[pol_cost_k], sc[none_cost_k],
                              discount, args.n_boot, rng,
                              cond=args.cond, formula=args.formula)
        if res is None:
            print(f"{label:22s}  [NPV_cost=0]")
            continue
        stats = compute_cv_stats(res)
        W_MC = res["W_MC_full"]
        W_6  = res["W_6_MC"]
        W_B  = res["W_B_fixed"]
        # rel SE defined against W_6 to be paper-comparable
        rel_MC = stats["SE_MC"] / abs(W_6) if W_6 else float("nan")
        rel_CV = stats["SE_CV"] / abs(W_6) if W_6 else float("nan")
        print(f"{label:22s} {W_6:7.3f} {W_MC:7.3f} {W_B:7.3f} "
              f"{stats['SE_MC']:7.4f} {stats['SE_CV']:7.4f} "
              f"{rel_MC*100:6.2f}% {rel_CV*100:6.2f}% "
              f"{stats['rho']:5.2f} {stats['beta']:6.2f} "
              f"{stats['variance_reduction']*100:4.0f}%")

    print()
    print("Legend (Welfare.py:277/284 paper formula; fixed AD=0 NPV_AddInc denominator):")
    print("  W_6      = W^U + W^B  (comparable to HAFiscal-QE published table)")
    print("  W^U      = (1/NPV_AddInc_AD0) · Σ_t R^-t Σ_i [u(c_pol) - u(c_none)] / u'(c_base)")
    print("  W^B      = (NPV_AddInc_AD0 - NPV_AddCons_AD0) / NPV_AddInc_AD0  (constant across AD=0/1)")
    print("  SE_MC/CV = bootstrap SE on W^U (numerator-only; denominator held fixed)")
    print("  ρ, β     = correlation and regression of boot MC vs boot L2")
    print("  VR%      = 100 * (1 - SE_CV² / SE_MC²)")


if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
