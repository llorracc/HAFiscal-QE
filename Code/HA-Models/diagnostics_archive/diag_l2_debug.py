"""Diagnostic: decompose the MC-L2 vs MC discrepancy into:
  (a) bucketing-only (reorder the MC sum by j^pol — should equal MC exactly)
  (b) product-of-means factorization (the L2 approximation)
  (c) p ⊥ Φ factorization (outer L2 step)

Reports per-cell ratios to identify where the discrepancy is.
"""
import pickle
from pathlib import Path
import numpy as np

DIR = Path("welfare6_scenario_results_Baseline")
CRRA = 2.0
R = 1.01
T = 40


def load():
    out = {}
    for f in sorted(DIR.glob("*.pkl")):
        out[f.stem] = pickle.load(open(f, "rb"))
    return out


def cell_diagnostics(pol, none, base, discount):
    # Use _bs panels (modal-duration, or single for non-rec)
    cp = np.asarray(pol["cLvl_all_splurge_bs"])
    cn = np.asarray(none["cLvl_all_splurge_bs"])
    cb = np.asarray(base["cLvl_all_splurge_bs"])
    pp = np.asarray(pol["pLvl_all_bs"])
    pn = np.asarray(none["pLvl_all_bs"])
    pb = np.asarray(base["pLvl_all_bs"])
    jp = np.asarray(pol["Mrkv_hist_bs"])
    ap = np.asarray(pol["AggIncome"])
    an = np.asarray(none["AggIncome"])

    # For _bs panel: use modal-duration aggregates. But AggIncome is prob-weighted.
    # For diagnostics, compute NPV_cost from the _bs panel directly (consistent w/
    # the _bs consumption).
    # NPV_cost via individual-level aggregation from _bs panel:
    # income_it = pLvl_it * TranShk_it * ADF_t — we don't have TranShk stored, so
    # fall back to AggIncome (prob-weighted). For Rec=0 cells, _bs==prob-weighted
    # so this is fine; for Rec=1 cells, mild inconsistency, but bucketing only
    # reorganizes the Σ_i — NPV_cost drops out of the ratio.
    NPV_cost = float(((ap - an) * discount).sum())
    N = min(cp.shape[1], cn.shape[1], cb.shape[1])
    cp, cn, cb = cp[:, :N], cn[:, :N], cb[:, :N]
    pp, pn, pb = pp[:, :N], pn[:, :N], pb[:, :N]
    jp = jp[:, :N]

    rho = CRRA
    # (A) Direct MC on _bs panel (single-duration for recession)
    du = (cp ** (1 - rho) - cn ** (1 - rho)) / (1 - rho)
    mu = cb ** (-rho)
    h_it = du / mu
    A_i = (h_it * discount[:, None]).sum(axis=0)
    W_bs_mc = A_i.sum() / NPV_cost

    # (B) Bucketed MC: organize Σ_i h by j^pol at each t.  Σ_t Σ_i h = Σ_t Σ_j Σ_{i:j^pol=j} h.
    # This should EQUAL (A) since it's just a reordering.
    n_states = int(jp.max()) + 1
    W_bucket = 0.0
    for t in range(T):
        counts = np.bincount(jp[t], minlength=n_states)
        sum_h  = np.bincount(jp[t], weights=h_it[t], minlength=n_states)
        W_bucket += discount[t] * sum_h.sum()
    W_bucket /= NPV_cost

    # (C) Factorize into p × Φ per agent. Verify h_it ≈ p_it · Φ_it.
    # Since p cancels in CRRA, h_it is p-independent by construction; but the
    # "p × Φ" representation requires defining Φ_it = (X^pol^{1-ρ} - X^none^{1-ρ})/(1-ρ) · X^base^ρ
    X_p = cp / pp
    X_n = cn / pn
    X_b = cb / pb
    phi_it = (X_p ** (1 - rho) - X_n ** (1 - rho)) / (1 - rho) * X_b ** rho
    # Verify h_it == p_it · phi_it numerically. Under p_pol=p_none=p_base, this
    # should be exact up to float precision. Under divergent p across scenarios,
    # it only holds approximately.
    lhs = h_it
    rhs = pp * phi_it   # using pp as the "shared" p; should equal h if p_pol=p_base
    err_pPhi = np.abs(lhs - rhs).max()

    # (D) Compute W using N × E[p] × E[Φ_t] (p⊥Φ factorization), where E[p] is from pb.
    E_pt = pb.mean(axis=1)
    E_phi_t = phi_it.mean(axis=1)
    W_pPhi = N * float((discount * E_pt * E_phi_t).sum()) / NPV_cost

    # (E) L2 approximation: product-of-means inside each j^pol bucket.
    # L2_t = Σ_j f_j · [E[X^pol^{1-ρ}|j] - E[X^none^{1-ρ}|j]]/(1-ρ) · E[X^base^ρ|j]
    Xp_a = X_p ** (1 - rho)
    Xn_a = X_n ** (1 - rho)
    Xb_b = X_b ** rho
    L2_t = np.zeros(T)
    for t in range(T):
        jt = jp[t]
        counts = np.bincount(jt, minlength=n_states).astype(float)
        active = counts > 0
        f_j = counts / N
        m_p = np.zeros(n_states); m_p[active] = np.bincount(jt, weights=Xp_a[t], minlength=n_states)[active] / counts[active]
        m_n = np.zeros(n_states); m_n[active] = np.bincount(jt, weights=Xn_a[t], minlength=n_states)[active] / counts[active]
        m_b = np.zeros(n_states); m_b[active] = np.bincount(jt, weights=Xb_b[t], minlength=n_states)[active] / counts[active]
        L2_t[t] = float(((m_p - m_n) / (1 - rho) * m_b * f_j).sum())
    W_L2 = N * float((discount * E_pt * L2_t).sum()) / NPV_cost

    # (F) Bucketed Φ without factorization: E[Φ_t] = Σ_j f_j · E[Φ_t | j^pol=j].
    # Should equal (D) W_pPhi exactly (just reordering).
    E_phi_t_buck = np.zeros(T)
    for t in range(T):
        jt = jp[t]
        counts = np.bincount(jt, minlength=n_states).astype(float)
        active = counts > 0
        f_j = counts / N
        m_phi = np.zeros(n_states); m_phi[active] = np.bincount(jt, weights=phi_it[t], minlength=n_states)[active] / counts[active]
        E_phi_t_buck[t] = float((f_j * m_phi).sum())
    W_phi_buck = N * float((discount * E_pt * E_phi_t_buck).sum()) / NPV_cost

    return {
        "W_MC":       W_bs_mc,
        "W_bucket":   W_bucket,
        "W_pPhi":     W_pPhi,
        "W_phi_buck": W_phi_buck,
        "W_L2":       W_L2,
        "err_pPhi":   err_pPhi,
        "NPV_cost":   NPV_cost,
    }


CELLS = [
    ("Check,  Rec=0", "Check",              "base",          "base"),
    ("UI,     Rec=0", "UI",                 "base",          "base"),
    ("TaxCut, Rec=0", "TaxCut",             "base",          "base"),
]


def main():
    sc = load()
    discount = R ** (-np.arange(T))
    print(f"{'cell':15s} {'W_MC(_bs)':>10s} {'W_bucket':>10s} {'W_phi_buck':>11s} "
          f"{'W_pΦ':>10s} {'W_L2':>10s} {'err[p·Φ]':>10s}")
    print(f"{'':15s} {'(direct)':>10s} {'(reorder)':>10s} {'(E[p·Φ])':>11s} "
          f"{'(E[p]E[Φ])':>10s} {'(fact)':>10s}")
    print("-" * 85)
    for label, pol_k, none_k, base_k in CELLS:
        r = cell_diagnostics(sc[pol_k], sc[none_k], sc[base_k], discount)
        print(f"{label:15s} {r['W_MC']:10.4f} {r['W_bucket']:10.4f} {r['W_phi_buck']:11.4f} "
              f"{r['W_pPhi']:10.4f} {r['W_L2']:10.4f} {r['err_pPhi']:10.2e}")


if __name__ == "__main__":
    main()
