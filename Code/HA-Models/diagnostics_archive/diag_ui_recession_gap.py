"""Track B diagnostics for the UI-recession W_6 gap investigation.

Reads the 4-seed combined panel at welfare6_scenario_results_Baseline
(symlink currently → _combined_S4) and writes four diagnostic reports
to history/20260420_ui_recession_gap/.

B1. Per-education-group decomposition of W_6 shortfall for UI Rec=1 and UI Rec=1 AD=1.
B2. UI-affected-agent mass over time.  (Agents whose j^pol != j^none under CRN.)
B3. Per-agent consumption-response distribution for UI-affected agents.
B4. Per-seed stability of W_6 estimates (confirms gap is not sampling noise).
"""
import os
import pickle
import sys
from pathlib import Path
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

OUT_DIR = Path("/home/shared/github/llorracc/HAFiscal-Latest/history/20260420_ui_recession_gap")
OUT_DIR.mkdir(parents=True, exist_ok=True)

R, T, CRRA = 1.01, 40, 2.0
DISC = R ** (-np.arange(T))

# For education-group split, need type boundaries from Parameters
from Parameters import return_parameters
r = return_parameters(Parametrization="Baseline", OutputFor="_Main.py")
DiscFacCount   = r[5]
AgentCountTotal = r[6]
data_EducShares = r[12]

# Per-type count at a single seed's AgentCountTotal; for S=4 combined, it's 4× that
per_type_count_single = []
for e in range(3):
    for d in range(DiscFacCount):
        cnt = int(np.floor(AgentCountTotal * data_EducShares[e] / DiscFacCount))
        per_type_count_single.append({'edu': e, 'bin': d, 'count': cnt})


def load_combined(name):
    p = Path(f"welfare6_scenario_results_Baseline_combined_S4/{name}.pkl")
    return pickle.load(open(p, "rb"))


def load_seed(seed, name):
    p = Path(f"welfare6_scenario_results_Baseline_seed{seed}/{name}.pkl")
    return pickle.load(open(p, "rb"))


EDU_NAMES = ["dropout", "HS", "college"]


def _compute_per_agent_A(c_pol, c_none, c_base):
    du = (c_pol ** (1 - CRRA) - c_none ** (1 - CRRA)) / (1 - CRRA)
    mu = c_base ** (-CRRA)
    return ((du / mu) * DISC[:, None]).sum(axis=0)


def _edu_slices_for_combined(N_combined):
    """Return list of (edu, start_idx, end_idx) for the combined S=4 panel.

    Combined layout: [seed0: type0, type1, ..., type20, seed1: type0, ..., type20, ...]
    For each seed, 21 types concatenated in (edu=0..2, bin=0..6) order.
    """
    N_per_seed = N_combined // 4
    # Check the actual split. Per-seed count of agents is sum of per_type_count_single.
    type_boundaries_single = [0]
    for t in per_type_count_single:
        type_boundaries_single.append(type_boundaries_single[-1] + t["count"])
    # Sum to a per-seed total
    assert type_boundaries_single[-1] == N_per_seed, \
        f"mismatch: expected {type_boundaries_single[-1]}, got {N_per_seed}"
    # Build per-edu slices for the combined panel
    edu_slices = []
    for e in range(3):
        # For this education group, collect agent indices from all 4 seeds
        idx_list = []
        for seed in range(4):
            seed_start = seed * N_per_seed
            # bins in this edu: per_type_count_single indices [e*DiscFacCount : (e+1)*DiscFacCount]
            for b in range(DiscFacCount):
                type_idx = e * DiscFacCount + b
                t_start = seed_start + type_boundaries_single[type_idx]
                t_end   = seed_start + type_boundaries_single[type_idx + 1]
                idx_list.append(np.arange(t_start, t_end))
        all_idx = np.concatenate(idx_list)
        edu_slices.append((EDU_NAMES[e], all_idx))
    return edu_slices


def B1_per_edu_decomposition():
    """Per-education-group W_6 decomposition."""
    report = ["# B1. Per-education-group W_6 decomposition",
              "",
              "Shows how each education group contributes to W_6(UI Rec=1) and",
              "W_6(UI Rec=1 AD=1) in the current-branch S=4 combined panel.",
              "Compares per-group share of the welfare numerator.",
              ""]

    # Load all scenarios
    sc = {s: load_combined(s) for s in
          ["base", "recession", "recessionUI", "recession_AD", "recessionUI_AD"]}
    N = sc["base"]["cLvl_all_splurge"].shape[1]
    edu_slices = _edu_slices_for_combined(N)

    for label, pol_k, none_k, base_k, pol_cost_k, none_cost_k in [
        ("UI Rec=1",      "recessionUI",    "recession",    "base", "recessionUI", "recession"),
        ("UI Rec=1 AD=1", "recessionUI_AD", "recession_AD", "base", "recessionUI", "recession"),
    ]:
        c_p = np.asarray(sc[pol_k]["cLvl_all_splurge"])
        c_n = np.asarray(sc[none_k]["cLvl_all_splurge"])
        c_b = np.asarray(sc[base_k]["cLvl_all_splurge"])
        A_i = _compute_per_agent_A(c_p, c_n, c_b)  # (N,)
        # Fixed AD=0 NPV_cost per paper formula
        Ip = np.asarray(sc[pol_cost_k]["AggIncome"])
        In = np.asarray(sc[none_cost_k]["AggIncome"])
        Cp = np.asarray(sc[pol_cost_k]["AggCons"])
        Cn = np.asarray(sc[none_cost_k]["AggCons"])
        NPV_cost = float(((Ip - In) * DISC).sum())
        NPV_dc   = float(((Cp - Cn) * DISC).sum())
        W_U_total = A_i.sum() / NPV_cost
        W_B = (NPV_cost - NPV_dc) / NPV_cost
        W_6_total = W_U_total + W_B

        report.append(f"## {label}")
        report.append(f"Total N = {N}, NPV_cost (AD=0 fixed) = {NPV_cost:.1f}")
        report.append(f"W_6 = {W_6_total:.4f}  (W^U = {W_U_total:.4f}  W^B = {W_B:.4f})")
        report.append("")
        report.append(f"  {'edu':10s} {'N':>7s} {'pop_share':>10s} "
                      f"{'ΣA':>12s} {'A_share':>10s} "
                      f"{'mean(A)':>10s} {'std(A)':>10s} "
                      f"{'group W^U':>10s}")
        for edu, idx in edu_slices:
            A_group = A_i[idx]
            sum_A = A_group.sum()
            report.append(
                f"  {edu:10s} {len(idx):7d} {len(idx)/N*100:9.1f}% "
                f"{sum_A:12.1f} {sum_A/A_i.sum()*100:9.1f}% "
                f"{A_group.mean():10.4f} {A_group.std():10.4f} "
                f"{sum_A/NPV_cost:10.4f}")
        report.append("")

    # If one edu group is responsible for most of the WU, calibration shift on
    # that group is the high-probability cause of the gap.
    report.append("Interpretation:")
    report.append("- If dropouts are >> pop-share in A_share, their calibration")
    report.append("  matters disproportionately. β_dropout shifted 0.719→0.700,")
    report.append("  ∇_dropout shifted 0.318→0.340 between HAFiscal-QE and this branch.")
    report.append("- The dropout β drop makes them MORE impatient: typically consume")
    report.append("  more early, accumulate less wealth, so by the time unemployment")
    report.append("  hits they have high MU and UI extension's per-$ welfare IMPACT")
    report.append("  should be LARGER, not smaller.  So H3 does not naturally explain")
    report.append("  a downward gap unless the sign of the effect is contrary to intuition.")
    (OUT_DIR / "B1_per_edu_decomposition.md").write_text("\n".join(report))
    return True


def B2_affected_mass():
    """UI-affected-agent mass at each t (j^pol != j^none under CRN)."""
    report = ["# B2. UI-affected-agent mass over time",
              "",
              "Count at each t: agents where j^recessionUI != j^recession (modal-duration, bs panel).",
              "High mass = UI extension reaches many agents.  Low mass = few.",
              ""]

    for seed in range(4):
        recUI = load_seed(seed, "recessionUI")
        rec   = load_seed(seed, "recession")
        jUI  = np.asarray(recUI["Mrkv_hist_bs"])
        jrec = np.asarray(rec["Mrkv_hist_bs"])
        N = min(jUI.shape[1], jrec.shape[1])
        jUI, jrec = jUI[:, :N], jrec[:, :N]
        # Micro state only (modulo num_base_MrkvStates); need num_base to compute.
        # Baseline: num_base_MrkvStates=4.
        num_base = 4
        mUI, mrec = jUI % num_base, jrec % num_base
        diff = (mUI != mrec)          # (T, N): True where agents diverge
        diff_ever = diff.any(axis=0)  # (N,): True if agent ever affected
        frac_ever = diff_ever.mean()
        frac_per_t = diff.mean(axis=1)  # (T,)
        # Typical affected state under UI (should be UB-extended = 1 or 2, not noUB=3)
        UI_state_dist = np.bincount(mUI[diff].flatten(), minlength=num_base) / max(diff.sum(), 1)
        rec_state_dist = np.bincount(mrec[diff].flatten(), minlength=num_base) / max(diff.sum(), 1)
        report.append(f"## Seed {seed}")
        report.append(f"N={N}, affected-ever fraction = {frac_ever:.4f}")
        report.append(f"  j^UI micro-state distribution among (t,i) where agents diverge: "
                      f"emp={UI_state_dist[0]:.3f} UB1={UI_state_dist[1]:.3f} "
                      f"UB2={UI_state_dist[2]:.3f} noUB={UI_state_dist[3]:.3f}")
        report.append(f"  j^rec micro-state distribution among (t,i) where agents diverge: "
                      f"emp={rec_state_dist[0]:.3f} UB1={rec_state_dist[1]:.3f} "
                      f"UB2={rec_state_dist[2]:.3f} noUB={rec_state_dist[3]:.3f}")
        report.append(f"  affected-mass per t[0:10]: {[f'{x:.4f}' for x in frac_per_t[:10]]}")
        report.append(f"  peak affected-mass: {frac_per_t.max():.4f} (t={frac_per_t.argmax()})")
        report.append("")

    report.append("Interpretation:")
    report.append("- Expected UI-extension behaviour: agents who'd be noUB=3 under recession")
    report.append("  are KEPT in UB=2 (extended benefits) under recessionUI.")
    report.append("  So j^UI=2 while j^rec=3 for affected agents.")
    report.append("  Check that j^UI state dist. is concentrated in UB states (1 or 2),")
    report.append("  and j^rec state dist. in noUB (3).")
    report.append("- HAFiscal-QE's expected affected-ever fraction under UI Rec=1 is ~0.08")
    report.append("  (from plan §6 f_aff).  Current fractions ≥ 0.08 → mass reaches OK,")
    report.append("  gap is NOT H4.  Fractions much lower → H4 in play.")
    (OUT_DIR / "B2_affected_mass.md").write_text("\n".join(report))
    return True


def B3_affected_consumption_response():
    """Per-agent consumption response distribution on UI-affected agents."""
    report = ["# B3. Per-agent consumption response on UI-affected agents",
              "",
              "For agents with j^UI != j^rec at some time t (modal-duration bs panel):",
              "- Δc_it = c_recessionUI - c_recession",
              "- Sum over t with R^-t discount → per-agent welfare-related consumption gain.",
              "- Compared to their base-scenario consumption (for u'(c_base) weighting).",
              ""]

    for seed in range(4):
        recUI  = load_seed(seed, "recessionUI")
        rec    = load_seed(seed, "recession")
        base   = load_seed(seed, "base")
        c_UI  = np.asarray(recUI["cLvl_all_splurge_bs"])
        c_rec = np.asarray(rec["cLvl_all_splurge_bs"])
        c_bs  = np.asarray(base["cLvl_all_splurge_bs"])
        jUI   = np.asarray(recUI["Mrkv_hist_bs"])
        jrec  = np.asarray(rec["Mrkv_hist_bs"])
        N = min(c_UI.shape[1], c_rec.shape[1], c_bs.shape[1])
        c_UI, c_rec, c_bs = c_UI[:, :N], c_rec[:, :N], c_bs[:, :N]
        jUI, jrec = jUI[:, :N], jrec[:, :N]
        num_base = 4
        diff_ever = ((jUI % num_base) != (jrec % num_base)).any(axis=0)
        N_aff = diff_ever.sum()
        if N_aff == 0:
            report.append(f"## Seed {seed}: no affected agents")
            report.append("")
            continue
        # per-agent discounted Δc
        dc = (c_UI - c_rec) * DISC[:, None]
        per_agent_dc = dc.sum(axis=0)      # NPV of per-agent Δc
        # among affected vs unaffected
        dc_aff   = per_agent_dc[diff_ever]
        dc_unaff = per_agent_dc[~diff_ever]
        # welfare-weighted per agent Δc × 1/u'(c_base) averaged over t (rough)
        # Actually h_i = discounted (u(c_UI) - u(c_rec)) / u'(c_base).  Compute.
        du = (c_UI ** (1 - CRRA) - c_rec ** (1 - CRRA)) / (1 - CRRA)
        mu = c_bs ** (-CRRA)
        A_i = ((du / mu) * DISC[:, None]).sum(axis=0)
        A_aff = A_i[diff_ever]
        A_unaff = A_i[~diff_ever]
        report.append(f"## Seed {seed}")
        report.append(f"N = {N}, affected-ever = {N_aff} ({N_aff/N*100:.2f}%)")
        report.append(f"Per-agent NPV Δc:")
        report.append(f"  affected:   mean={dc_aff.mean():.3f} std={dc_aff.std():.3f} "
                      f"ΣΔc={dc_aff.sum():.1f}")
        report.append(f"  unaffected: mean={dc_unaff.mean():.3e} std={dc_unaff.std():.3f} "
                      f"ΣΔc={dc_unaff.sum():.1f}")
        report.append(f"Per-agent welfare integrand A_i (discounted Δu/u'):")
        report.append(f"  affected:   mean={A_aff.mean():.3f} std={A_aff.std():.3f} "
                      f"ΣA={A_aff.sum():.1f}  median={np.median(A_aff):.3f}")
        report.append(f"  unaffected: mean={A_unaff.mean():.3e} std={A_unaff.std():.3f} "
                      f"ΣA={A_unaff.sum():.1f}")
        # What fraction of Σ A comes from affected?
        frac_A_from_aff = A_aff.sum() / A_i.sum() if A_i.sum() else float("nan")
        report.append(f"Share of Σ A_i from affected agents: {frac_A_from_aff*100:.1f}%")
        report.append("")

    report.append("Interpretation:")
    report.append("- Affected Δc should be positive on average (UI extension delivers")
    report.append("  extra benefits, agents consume some).  Unaffected should be ~0.")
    report.append("- Under splurge-in-budget, Δc magnitude for affected agents may be")
    report.append("  small because the UI benefit flows through the budget rather than")
    report.append("  through transitory consumption.  Check magnitude against reasonable")
    report.append("  expectation: IncUnemp×pLvl×(avg extension periods) per affected.")
    (OUT_DIR / "B3_affected_consumption_response.md").write_text("\n".join(report))
    return True


def B4_per_seed_stability():
    """Per-seed W_6 stability for UI cells under paper formula."""
    report = ["# B4. Per-seed stability of W_6 estimates (paper formula)",
              "",
              "Records per-seed W_6 for UI Rec=1 and UI Rec=1 AD=1 cells,",
              "confirming the 10-12σ gap against HAFiscal-QE is not sampling noise.",
              ""]
    per_seed_data = {"UI Rec=1": [], "UI Rec=1 AD=1": []}
    for seed in range(4):
        for label, pol_k, none_k, base_k, pol_cost_k, none_cost_k in [
            ("UI Rec=1",      "recessionUI",    "recession",    "base", "recessionUI", "recession"),
            ("UI Rec=1 AD=1", "recessionUI_AD", "recession_AD", "base", "recessionUI", "recession"),
        ]:
            pol = load_seed(seed, pol_k)
            none = load_seed(seed, none_k)
            base = load_seed(seed, base_k)
            pol_c = load_seed(seed, pol_cost_k)
            none_c = load_seed(seed, none_cost_k)
            c_p = np.asarray(pol["cLvl_all_splurge"])
            c_n = np.asarray(none["cLvl_all_splurge"])
            c_b = np.asarray(base["cLvl_all_splurge"])
            A_i = _compute_per_agent_A(c_p, c_n, c_b)
            NPV_cost = float(((np.asarray(pol_c["AggIncome"]) - np.asarray(none_c["AggIncome"])) * DISC).sum())
            NPV_dc   = float(((np.asarray(pol_c["AggCons"]) - np.asarray(none_c["AggCons"])) * DISC).sum())
            W_U = A_i.sum() / NPV_cost
            W_B = (NPV_cost - NPV_dc) / NPV_cost
            W_6 = W_U + W_B
            per_seed_data[label].append((seed, W_U, W_B, W_6))

    for label, rows in per_seed_data.items():
        report.append(f"## {label}  (HAFiscal-QE = " +
                      ("1.82" if "AD=1" not in label else "2.13") + ")")
        report.append(f"  {'seed':>4s} {'W^U':>8s} {'W^B':>8s} {'W_6':>8s}")
        for seed, wu, wb, w6 in rows:
            report.append(f"  {seed:>4d} {wu:8.4f} {wb:8.4f} {w6:8.4f}")
        w6_vals = np.array([r[3] for r in rows])
        report.append(f"  mean ± SD across {len(w6_vals)} seeds: {w6_vals.mean():.4f} ± "
                      f"{w6_vals.std(ddof=1):.4f}")
        qe = 1.82 if "AD=1" not in label else 2.13
        z = (qe - w6_vals.mean()) / (w6_vals.std(ddof=1) / np.sqrt(len(w6_vals)))
        report.append(f"  z-score vs HAFiscal-QE ({qe}): {z:.2f}")
        report.append("")
    (OUT_DIR / "B4_per_seed_stability.md").write_text("\n".join(report))
    return True


def main():
    print("B1: per-education decomposition...")
    B1_per_edu_decomposition()
    print("B2: affected-mass over time...")
    B2_affected_mass()
    print("B3: affected-agent consumption response...")
    B3_affected_consumption_response()
    print("B4: per-seed stability...")
    B4_per_seed_stability()
    print(f"Done.  Reports in {OUT_DIR}")


if __name__ == "__main__":
    main()
