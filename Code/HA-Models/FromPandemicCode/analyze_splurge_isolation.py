"""ς-isolation analyzer: compare W_6 at ς=0.2461 vs ς=0.2609.

Both runs use splurge-in-budget asset update (BUG-031 fixed) and identical
(β, ∇) — the only difference is the splurge parameter. This isolates
the ς channel from the BUG-031 and (β, ∇) channels.

Reads /tmp/welfare_diag/{S0246,S0261}.npz produced by
mc_welfare_diagnostic.py with HAFISCAL_SPLURGE_OVERRIDE={0.2461,0.2609}.

Usage:
    cd Code/HA-Models/FromPandemicCode
    python analyze_splurge_isolation.py
"""
import os, numpy as np

diag_dir = "/tmp/welfare_diag"
report_path = os.path.join(diag_dir, "splurge_isolation_report.txt")


def npv_sum(x, R):
    T = len(x)
    disc = R ** (-np.arange(T))
    return np.sum(x * disc)


def compute_scenario(d, pol_key, base_key, ss_key='base'):
    CRRA = float(d['CRRA']); R = float(d['Rfree']); T = int(d['act_T'])
    wt = R ** (-np.arange(T))

    c_pol  = d[f'{pol_key}_cLvl_all_splurge']
    c_base = d[f'{base_key}_cLvl_all_splurge']
    c_ss   = d[f'{ss_key}_cLvl_all_splurge']
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

    cb  = np.maximum(c_base, 1e-16)
    css = np.maximum(c_ss,   1e-16)
    mu_ss = css ** (-CRRA)

    # γ=2 closed form: u(c) = -1/c
    dU = (-1.0 / np.maximum(c_pol, 1e-16) + 1.0 / cb)
    W_U = np.sum(np.sum(dU / mu_ss, axis=1) * wt) / NPV_cost
    W_B = 1.0 - M_inf
    W_6 = W_U + W_B

    return dict(M_10y=M_10y, M_inf=M_inf, W_U=W_U, W_B=W_B, W_6=W_6,
                NPV_cost=NPV_cost, NPV_dCons=NPV_dCons)


def report(label, a, b, name_a, name_b):
    lines = [
        "",
        "=" * 80,
        f"Scenario: {label}   ({name_a} vs {name_b}, CRN-paired, only ς differs)",
        "=" * 80,
        "{:<16} {:>14} {:>14} {:>14} {:>10}".format(
            "Quantity", name_a, name_b, f"{name_b}-{name_a}", "% chg"),
        "-" * 80,
    ]
    for k in ['M_10y', 'M_inf', 'W_U', 'W_B', 'W_6', 'NPV_cost', 'NPV_dCons']:
        va, vb = a[k], b[k]
        pct = 100.0 * (vb - va) / max(abs(va), 1e-12)
        lines.append("{:<16} {:>14.4f} {:>14.4f} {:>+14.4f} {:>+9.1f}%".format(
            k, va, vb, vb - va, pct))
    return lines


def main():
    p246 = os.path.join(diag_dir, "S0246.npz")
    p261 = os.path.join(diag_dir, "S0261.npz")
    if not (os.path.exists(p246) and os.path.exists(p261)):
        raise SystemExit(f"Need both {p246} and {p261}")

    s246 = np.load(p246)
    s261 = np.load(p261)

    out = ["ς-isolation diagnostic: varying only Splurge (BUG-031 fix active in both)",
           f"  S0246: ς = 0.2461 (QE published)",
           f"  S0261: ς = 0.2609 (bugfix re-estimate)",
           f"  CRRA={float(s261['CRRA'])}  R={float(s261['Rfree']):.4f}  T={int(s261['act_T'])}"]

    scenarios = [('UI Rec=1 AD=0', 'recUI', 'rec'),
                 ('UI Rec=1 AD=1', 'recUIAD', 'recAD')]

    for label, pol, bas in scenarios:
        if f'{pol}_cLvl_all_splurge' not in s261.files:
            out.append(f"\n(skipping {label} — panels missing)")
            continue
        a = compute_scenario(s246, pol, bas, 'base')
        b = compute_scenario(s261, pol, bas, 'base')
        out += report(label, a, b, "S0246", "S0261")

    text = "\n".join(out)
    print(text)
    with open(report_path, 'w') as f:
        f.write(text + "\n")
    print(f"\nReport: {report_path}")


if __name__ == '__main__':
    main()
