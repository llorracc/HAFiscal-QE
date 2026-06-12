"""Analyze OLD vs NEW welfare gap from mc_welfare_diagnostic.py panels.

Tests the corrected central identity for CRRA=2:

    W_6 = 1 + (M_inf^w - M_inf) - Q^w + O(Δ^3)

where Δ_{t,i} = c^pol - c^base (both CRN-paired),
      R_{t,i} = (c_ss/c_base)^2                 (recession-rescaling factor)
      M_inf   = Σ Δ R^{-t} / NPV_cost          (aggregate multiplier)
      M_inf^w = Σ R · Δ R^{-t} / NPV_cost      (u'(c_ss)-weighted multiplier)
      Q^w     = Σ R · Δ^2/c_base · R^{-t} / NPV_cost

Derivation (see plans/20260417-1242h_welfare-vs-multiplier-asymmetry-hypothesis.md —
superseded by the _v3 plan, 20260418-0653h; the derivation section is unchanged):
  For γ=2, (u(c_pol)-u(c_base))/u'(c_ss) = (c_ss/c_base)^2 · Δ/(1+Δ/c_base)
  Expand:                                  = R·[Δ - Δ^2/c_base + O(Δ^3)]
  Summing:                       W_U = M_inf^w - Q^w + O(Δ^3)
  And W_B = 1 - M_inf, so W_6 = W_U + W_B as above.

This matches run_hybrid_welfare6.py's welfare6_mc(pol, none, base) with
base = no-policy no-recession steady-state run.

Usage:
    cd Code/HA-Models/FromPandemicCode
    python analyze_welfare_gap.py
"""
import os, numpy as np

diag_dir = "/tmp/welfare_diag"
report_path = os.path.join(diag_dir, "report.txt")


def npv_sum(x, R):
    T = len(x)
    disc = R ** (-np.arange(T))
    return np.sum(x * disc)


def compute_scenario(d, pol_key, base_key, ss_key='base'):
    """Returns diagnostic dict for one scenario."""
    CRRA = float(d['CRRA']); R = float(d['Rfree']); T = int(d['act_T'])
    wt = R ** (-np.arange(T))

    c_pol  = d[f'{pol_key}_cLvl_all_splurge']    # (T, N)
    c_base = d[f'{base_key}_cLvl_all_splurge']   # (T, N) — CRN same shocks
    c_ss   = d[f'{ss_key}_cLvl_all_splurge']     # steady state (no-policy, no-rec)
    Agg_pol  = d[f'{pol_key}_AggCons']
    Agg_base = d[f'{base_key}_AggCons']
    Y_pol    = d[f'{pol_key}_AggIncome']
    Y_base   = d[f'{base_key}_AggIncome']

    NPV_cost = npv_sum(Y_pol - Y_base, R)
    NPV_dCons = npv_sum(Agg_pol - Agg_base, R)
    M_inf = NPV_dCons / NPV_cost
    T_10y = min(40, T)
    disc10 = R ** (-np.arange(T_10y))
    M_10y = np.sum((Agg_pol[:T_10y] - Agg_base[:T_10y]) * disc10) / NPV_cost

    # Per-(t,i) building blocks
    dc   = c_pol - c_base
    cb   = np.maximum(c_base, 1e-16)
    css  = np.maximum(c_ss,   1e-16)
    Rfac = (css / cb) ** 2                    # (T, N) recession-rescaling
    mu_ss = css ** (-CRRA)

    # Exact utility part (γ=2 closed form via u(c)=-1/c)
    dU = (-1.0 / np.maximum(c_pol, 1e-16) + 1.0 / cb)
    W_U = np.sum(np.sum(dU / mu_ss, axis=1) * wt) / NPV_cost
    W_B = 1.0 - M_inf
    W_6 = W_U + W_B

    # Leading-order decomposition
    M_inf_w = np.sum(np.sum(Rfac * dc, axis=1) * wt) / NPV_cost
    Q_per_ti = Rfac * (dc ** 2) / cb          # (T, N)
    Q_w = np.sum(np.sum(Q_per_ti, axis=1) * wt) / NPV_cost
    W_6_pred = 1.0 + (M_inf_w - M_inf) - Q_w

    # Decomposition diagnostics
    # H1a: Q by c_ss (steady-state) quintile, ranked at t=0
    rank = css[0, :]
    bins = np.percentile(rank, [20, 40, 60, 80])
    qidx = np.digitize(rank, bins)
    Q_by_q = np.zeros(5)
    for q in range(5):
        mask = qidx == q
        if mask.any():
            Q_by_q[q] = np.sum(Q_per_ti[:, mask].sum(axis=1) * wt) / NPV_cost

    # H1b: inter-temporal concentration of aggregate Δc in policy-active window
    agg_dc = dc.sum(axis=1)
    T_win = min(40, T)
    mdc = agg_dc[:T_win].mean()
    C_t = agg_dc[:T_win].var() / (mdc ** 2 + 1e-30)

    # H1a: cross-sectional concentration of per-agent cumulative Δc
    dc_i = dc[:T_win].sum(axis=0)
    C_x = dc_i.var() / (dc_i.mean() ** 2 + 1e-30)

    # ρ(Δc, 1/c_base) at t=0
    rho = np.corrcoef(dc[0, :], 1.0 / cb[0, :])[0, 1]

    return dict(
        M_10y=M_10y, M_inf=M_inf, M_inf_w=M_inf_w,
        W_U=W_U, W_B=W_B, W_6=W_6, W_6_pred=W_6_pred,
        Q_w=Q_w, Q_by_q=Q_by_q,
        C_t=C_t, C_x=C_x, rho=rho,
        NPV_cost=NPV_cost, NPV_dCons=NPV_dCons,
    )


def report_scenario(label, old, new):
    lines = [
        "",
        "=" * 72,
        f"Scenario: {label}   (OLD vs NEW splurge, CRN-paired)",
        "=" * 72,
        "{:<20} {:>14} {:>14} {:>14}".format("Quantity", "OLD", "NEW", "NEW−OLD"),
        "-" * 72,
    ]
    for k in ['M_10y', 'M_inf', 'M_inf_w', 'W_U', 'W_B', 'W_6', 'W_6_pred',
              'Q_w', 'C_t', 'C_x', 'rho', 'NPV_cost', 'NPV_dCons']:
        o, n = old[k], new[k]
        lines.append("{:<20} {:>14.4f} {:>14.4f} {:>+14.4f}".format(k, o, n, n - o))

    # Identity test at the difference level
    dW = new['W_6'] - old['W_6']
    dM_w_gap = (new['M_inf_w'] - new['M_inf']) - (old['M_inf_w'] - old['M_inf'])
    dQ_w = new['Q_w'] - old['Q_w']
    pred_dW = dM_w_gap - dQ_w
    resid = dW - pred_dW
    ratio = abs(resid) / max(abs(dW), 1e-12)
    lines += [
        "",
        "Identity test:  ΔW_6  ≈  Δ(M_w - M) − ΔQ_w     (leading order)",
        f"  ΔW_6                 = {dW:+.4f}",
        f"  Δ(M_inf_w - M_inf)   = {dM_w_gap:+.4f}",
        f"  −ΔQ_w                = {-dQ_w:+.4f}",
        f"  predicted ΔW_6       = {pred_dW:+.4f}",
        f"  residual             = {resid:+.4f}   ({ratio*100:.1f}% of |ΔW_6|)",
        "",
        "Absolute identity test:  W_6  ≈  1 + (M_w - M) − Q_w",
        f"  W_6^OLD                 = {old['W_6']:.4f}   predicted: {old['W_6_pred']:.4f}   diff: {old['W_6']-old['W_6_pred']:+.4f}",
        f"  W_6^NEW                 = {new['W_6']:.4f}   predicted: {new['W_6_pred']:.4f}   diff: {new['W_6']-new['W_6_pred']:+.4f}",
        "",
        "Q_w decomposition by c_ss quintile (H1a):",
        "  quintile       OLD         NEW     NEW−OLD",
    ]
    for q in range(5):
        o, n = old['Q_by_q'][q], new['Q_by_q'][q]
        lines.append(f"  q{q}           {o:>8.4f}   {n:>8.4f}   {n-o:+.4f}")
    dQ_lo = new['Q_by_q'][0] - old['Q_by_q'][0]
    dQ_hi = new['Q_by_q'][4] - old['Q_by_q'][4]
    lines += [
        f"  |ΔQ_lo|/|ΔQ_w| = {abs(dQ_lo)/max(abs(dQ_w),1e-12):.3f}   "
        f"|ΔQ_hi|/|ΔQ_w| = {abs(dQ_hi)/max(abs(dQ_w),1e-12):.3f}",
    ]
    return lines


def main():
    if not (os.path.exists(os.path.join(diag_dir, "OLD.npz")) and
            os.path.exists(os.path.join(diag_dir, "NEW.npz"))):
        raise SystemExit("Run mc_welfare_diagnostic.py first (OLD and NEW)")

    old = np.load(os.path.join(diag_dir, "OLD.npz"))
    new = np.load(os.path.join(diag_dir, "NEW.npz"))

    all_lines = ["Welfare-gap diagnostic: OLD splurge vs NEW splurge-in-budget",
                 f"CRRA={float(old['CRRA'])}  Rfree={float(old['Rfree']):.4f}  act_T={int(old['act_T'])}"]

    # Scenarios:
    #  Rec=1 AD=0  UI:  pol=recUI    base=rec      ss=base
    #  Rec=1 AD=1  UI:  pol=recUIAD  base=recAD    ss=base
    scenarios = [('UI Rec=1 AD=0', 'recUI', 'rec'),
                 ('UI Rec=1 AD=1', 'recUIAD', 'recAD')]

    for label, pol, bas in scenarios:
        if f'{pol}_cLvl_all_splurge' not in new.files:
            all_lines.append(f"\n(skipping {label} — panels not saved)")
            continue
        o = compute_scenario(old, pol, bas, 'base')
        n = compute_scenario(new, pol, bas, 'base')
        all_lines += report_scenario(label, o, n)

    report = "\n".join(all_lines)
    print(report)
    with open(report_path, 'w') as f:
        f.write(report + "\n")
    print(f"\nReport: {report_path}")


if __name__ == '__main__':
    main()
