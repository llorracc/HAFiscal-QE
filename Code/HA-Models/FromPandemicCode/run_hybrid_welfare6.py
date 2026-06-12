"""Hybrid welfare6: TM for multipliers, standard MC for welfare6 table.

Runs standard MC (no shuffle, CRN-paired) for welfare6 computation.
TM results for multiplier tables and figures must already exist.

The welfare6 formula requires individual-level matching across experiments
(same agent i in policy vs base), which TM cannot provide (as of the
2026-04-12 analysis; the joint-5D TM kernel, welfare6_tm_joint5d.py, later
provided CRN-coupled joint distributions — MC remains canonical per the
2026-06-10 unified-MC decision). MC with CRN
gives precise welfare6 at moderate N (~0.5% SE at N=10K) because:
  1. CRN cancels idiosyncratic noise in the treatment effect Δu
  2. The denominator (NPV of policy spending) is always large and positive
  3. Numerator-denominator correlation stabilizes the ratio
See history/20260412-welfare6-TM-analysis.md for the full analysis.

Usage:
    cd Code/HA-Models/FromPandemicCode
    python run_hybrid_welfare6.py              # Reduced_Run (3 types)
    python run_hybrid_welfare6.py --baseline   # Baseline (21 types)
"""

import os, sys, numpy as np
from copy import deepcopy
from time import time

sys.argv_orig = sys.argv[:]
sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith("FromPandemicCode"):
    os.chdir(cwd + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, os.getcwd())

os.environ["MPLBACKEND"] = "Agg"
import matplotlib; matplotlib.use("Agg")  # noqa: E702

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy  # noqa: E402
from Parameters import return_parameters  # noqa: E402
from OtherFunctions import load_pickle  # noqa: E402
from tm_methods import calculate_NPV  # noqa: E402
from HARK.distributions import DiscreteDistribution  # noqa: E402

use_baseline = '--baseline' in sys.argv_orig
_param = 'Baseline' if use_baseline else 'Reduced_Run'
print(f"Hybrid welfare6: {_param}")

# ============================================================
# Load parameters
# ============================================================
(
    init_dropout, init_highschool, init_college,
    init_ADEconomy, DiscFacDstns, DiscFacCount, AgentCountTotal,
    base_dict, num_max_iterations_solvingAD, convergence_tol_solvingAD,
    UBspell_normal, num_base_MrkvStates, data_EducShares,
    max_recession_duration, num_experiment_periods,
    recession_changes, UI_changes, recession_UI_changes,
    TaxCut_changes, recession_TaxCut_changes,
    Check_changes, recession_Check_changes,
) = return_parameters(Parametrization=_param, OutputFor="_Main.py")

[max_recession_duration_out, Rspell, Rfree_base, figs_dir_out, CRRA] = \
    return_parameters(Parametrization=_param, OutputFor='_Output_Results.py')

J = num_base_MrkvStates
Rfree = Rfree_base[0]
beta_SP = 1.0 / Rfree

if _param == 'Baseline':
    figs_dir = os.path.join(os.getcwd(), 'Figures', 'Baseline') + '/'
    table_dir = os.path.join(os.getcwd(), 'Tables', 'Baseline') + '/'
else:
    figs_dir = os.path.join(os.getcwd(), 'Figures', 'Reduced_Run') + '/'
    table_dir = os.path.join(os.getcwd(), 'Tables', 'Reduced_Run') + '/'

_table_dir_override = os.environ.get('HAFISCAL_TABLE_DIR')
if _table_dir_override:
    table_dir = _table_dir_override.rstrip('/') + '/'
    os.makedirs(table_dir, exist_ok=True)
    print(f"  HAFISCAL_TABLE_DIR → {table_dir}")


def felicity(c):
    c = np.maximum(c, 1e-16)
    if abs(CRRA - 1.0) < 1e-12:
        return np.log(c)
    return c**(1 - CRRA) / (1 - CRRA)


# ============================================================
# Build economy for MC
# ============================================================
print(f"\nBuilding economy ({_param})...")
t0_total = time()

init_params = [init_dropout, init_highschool, init_college]
AgentTypes = []
for e in range(3):
    for d in range(DiscFacCount):
        ThisType = AggFiscalType(**init_params[e])
        ThisType.cycles = 0
        ThisType.DiscFac = DiscFacDstns[e].atoms[0][d]
        ThisType.seed = e * DiscFacCount + d
        ThisType.AgentCount = int(np.floor(
            AgentCountTotal * data_EducShares[e] / DiscFacCount))
        AgentTypes.append(ThisType)

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
print(f"  {len(AgentTypes)} types, solved in {time()-t0_total:.0f}s")

# ============================================================
# Burn-in and counterfactual mode
# ============================================================
print("Burning in...")
t0 = time()
AggEco.reset()
for a in AggEco.agents:
    a.initialize_sim()
    a.AggDemandFac = 1.0
    a.RfreeNow = 1.0
    a.CaggNow = 1.0
AggEco.make_history()
# [2026-06-08] BUG-052: ergodic warm-start (DEFAULT ON), same fix as welfare6_scenario.py.
# Inject AFTER make_history / BEFORE save_state so run_experiment's use_prestate restores the
# ergodic prestate (the wealth the beta-calibration targets), not the cold a~=0 init.
# HAFISCAL_WELFARE6_TM_INIT=0 toggles off (cold-start) for isolation only. See
# BUGS_private/HAFiscal_BUG-052_welfare6_cold_start_vs_ergodic_calibration.md
if os.environ.get('HAFISCAL_WELFARE6_TM_INIT', '1') != '0':
    from tm_methods import (compute_baseline_tm_data as _cbtd,
                            initialize_mc_from_tm_ergodic as _imc)
    for _a in AggEco.agents:
        _a.tm_a_indexed = True
    _bd = _cbtd(AggEco, mCount=int(os.environ.get('HAFISCAL_TM_MCOUNT', '200')),
                neutral_measure=(os.environ.get('HAFISCAL_WELFARE6_TM_INIT_MEASURE', 'P') == 'Q'))
    _imc(AggEco.agents, _bd, mc_warmup=int(os.environ.get('HAFISCAL_WELFARE6_MC_WARMUP', '24')))
AggEco.save_state()
AggEco.switch_to_counterfactual_mode("base")
act_T = AggEco.act_T
for a in AggEco.agents:
    a.T_sim = act_T
    a.EconomyMrkvNow_hist = [0] * act_T
AggEco.make_idiosyncratic_shock_histories()
print(f"  Done in {time()-t0:.0f}s")

base_dict_agg = deepcopy(base_dict)
norec_path = (
    list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 20
)
periods = act_T

# ============================================================
# MC experiments for welfare6
# ============================================================
print(f"\nRunning MC experiments (standard, no shuffle)...")

# Base
t0 = time()
base_mc = AggEco.run_experiment(**base_dict_agg, Full_Output='ForWelfare')
AggEco.store_baseline(base_mc['AggCons'])
print(f"  Base: {time()-t0:.0f}s")


def run_norec(shock_type, changes):
    t0 = time()
    eco = deepcopy(AggEco)
    eco.switch_shock_type(shock_type)
    eco.solve()
    d = base_dict_agg.copy()
    d.update(changes)
    d['EconomyMrkv_init'] = norec_path
    r = eco.run_experiment(**d, Full_Output='ForWelfare')
    print(f"  {shock_type}: {time()-t0:.0f}s")
    return r


def run_recession(shock_type, changes):
    """Run all recession durations, return prob-weighted average."""
    t0 = time()
    eco = deepcopy(AggEco)
    eco.switch_shock_type(shock_type)
    eco.solve()

    R_persist = 1.0 - 1.0 / Rspell
    recession_prob = np.array([
        R_persist**t * (1 - R_persist) for t in range(max_recession_duration)
    ])
    recession_prob[-1] = 1.0 - np.sum(recession_prob[:-1])

    all_results = []
    for dur in range(max_recession_duration):
        d = base_dict_agg.copy()
        d.update(changes)
        rec_path = (
            list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 20
        )
        rec_path[0 : dur + 1] = (
            np.array(rec_path[0 : dur + 1]) + 1
        ).tolist()
        d['EconomyMrkv_init'] = rec_path
        r = eco.run_experiment(**d, Full_Output='ForWelfare')
        all_results.append(r)

    # Prob-weighted average of cLvl_all_splurge
    # BUG-046 fix: also preserve per-duration cLvl_all_splurge so welfare6_mc
    # can compute u-per-dur then weight (avoiding Jensen bias).
    avg = {}
    for key in ['cLvl_all_splurge', 'AggIncome', 'AggCons']:
        avg[key] = np.sum(
            np.array([all_results[t][key] * recession_prob[t]
                       for t in range(max_recession_duration)]),
            axis=0,
        )
    # BUG-046: preserve per-dur cLvl and rec_probs for correct welfare aggregation
    avg['per_dur_cLvl_all_splurge'] = [all_results[t]['cLvl_all_splurge']
                                        for t in range(max_recession_duration)]
    avg['rec_probs'] = recession_prob
    print(f"  {shock_type} ({max_recession_duration} durations): {time()-t0:.0f}s")
    return avg


def run_recession_AD(shock_type, changes):
    """Run AD recession: CFunc training + all recession durations."""
    t0 = time()
    eco = deepcopy(AggEco)
    eco.switch_shock_type(shock_type)

    # CFunc training (matches MC's solve_ad_* methods)
    if shock_type == 'recession':
        eco.solve_ad_recession(
            num_max_iterations=num_max_iterations_solvingAD,
            convergence_cutoff=convergence_tol_solvingAD,
            name=shock_type)
    elif shock_type == 'recessionUI':
        eco.solve_ad_ui_extension_recession(
            num_max_iterations=num_max_iterations_solvingAD,
            convergence_cutoff=convergence_tol_solvingAD,
            name=shock_type)
    elif shock_type == 'recessionCheck':
        eco.solve_ad_check_recession(
            num_max_iterations=num_max_iterations_solvingAD,
            convergence_cutoff=convergence_tol_solvingAD,
            name=shock_type)
    elif shock_type == 'recessionTaxCut':
        eco.solve_ad_recession_taxcut(
            num_max_iterations=num_max_iterations_solvingAD,
            convergence_cutoff=convergence_tol_solvingAD,
            name=shock_type)

    eco.switch_shock_type(shock_type)
    eco.restore_ADsolution(name=shock_type)

    R_persist = 1.0 - 1.0 / Rspell
    recession_prob = np.array([
        R_persist**t * (1 - R_persist) for t in range(max_recession_duration)
    ])
    recession_prob[-1] = 1.0 - np.sum(recession_prob[:-1])

    all_results = []
    for dur in range(max_recession_duration):
        d = base_dict_agg.copy()
        d.update(changes)
        rec_path = (
            list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 20
        )
        rec_path[0 : dur + 1] = (
            np.array(rec_path[0 : dur + 1]) + 1
        ).tolist()
        d['EconomyMrkv_init'] = rec_path
        r = eco.run_experiment(**d, Full_Output='ForWelfare')
        all_results.append(r)

    avg = {}
    for key in ['cLvl_all_splurge', 'AggIncome', 'AggCons']:
        avg[key] = np.sum(
            np.array([all_results[t][key] * recession_prob[t]
                       for t in range(max_recession_duration)]),
            axis=0,
        )
    # BUG-046 fix: preserve per-dur cLvl for correct welfare aggregation
    avg['per_dur_cLvl_all_splurge'] = [all_results[t]['cLvl_all_splurge']
                                        for t in range(max_recession_duration)]
    avg['rec_probs'] = recession_prob
    print(f"  {shock_type} AD ({max_recession_duration} dur): {time()-t0:.0f}s")
    return avg


# No-recession experiments
check_mc = run_norec('Check', Check_changes)
ui_mc = run_norec('UI', UI_changes)
taxcut_mc = run_norec('TaxCut', TaxCut_changes)

# Recession experiments (prob-weighted over durations)
rec_mc = run_recession('recession', recession_changes)
recUI_mc = run_recession('recessionUI', recession_UI_changes)
recCheck_mc = run_recession('recessionCheck', recession_Check_changes)
recTaxCut_mc = run_recession('recessionTaxCut', recession_TaxCut_changes)

# Recession with AD effects
rec_AD_mc = run_recession_AD('recession', recession_changes)
recUI_AD_mc = run_recession_AD('recessionUI', recession_UI_changes)
recCheck_AD_mc = run_recession_AD('recessionCheck', recession_Check_changes)
recTaxCut_AD_mc = run_recession_AD('recessionTaxCut', recession_TaxCut_changes)

# ============================================================
# Compute welfare6 (Method 6 from Welfare.py)
# ============================================================
print(f"\nComputing welfare6...")


def welfare6_mc(pol_r, none_r, base_r, cost_pol_r=None, cost_none_r=None):
    """Welfare6 Method 6.

    Paper formula (Welfare.py:277/284): NPV_AddInc denominator is held
    fixed at the AD=0 pair for a given policy.  ``cost_pol_r`` and
    ``cost_none_r`` supply the AD=0 scenarios for the denominator and the
    budget-residual term; for AD=0 cells they equal pol_r / none_r (and
    default to that if omitted).

    Calling with ``cost_pol_r is None`` gives legacy cell-specific
    denominator behaviour (kept only for debugging; all cells should
    now pass the AD=0 cost pair explicitly).

    BUG-046 fix (2026-05-16): The welfare integrand
    `(u(c_p) - u(c_n)) / u'(c_b)` is NONLINEAR in cLvl. Computing it on
    the duration-probability-weighted average cLvl is biased by Jensen's
    inequality vs computing per-duration welfare then weighting.
    Empirical bias at HS_Only N=49000 bug_fix is −23% on `ui_rec`
    (1.86 biased vs 2.41 correct). The fix below computes welfare per
    duration then weights. Activated by HAFISCAL_WELFARE6_FIX_DUR_AVG=on
    (default `on`). Set to `off` to restore legacy buggy behavior.
    """
    if cost_pol_r is None:
        cost_pol_r = pol_r
    if cost_none_r is None:
        cost_none_r = none_r

    # NPV_AddInc and NPV_AddCons are LINEAR in cLvl, so dur-weighted
    # averages are unaffected by Jensen. Unchanged.
    NPV_pol_Y = calculate_NPV(np.array(cost_pol_r['AggIncome']), periods, Rfree)[-1]
    NPV_none_Y = calculate_NPV(np.array(cost_none_r['AggIncome']), periods, Rfree)[-1]
    NPV_AddInc = NPV_pol_Y - NPV_none_Y

    NPV_pol_C = calculate_NPV(np.array(cost_pol_r['AggCons']), periods, Rfree)[-1]
    NPV_none_C = calculate_NPV(np.array(cost_none_r['AggCons']), periods, Rfree)[-1]
    NPV_AddCons = NPV_pol_C - NPV_none_C

    if abs(NPV_AddInc) < 1e-10:
        return np.nan

    # BUG-046: compute welfare integrand per-duration then weight by rec_probs.
    _fix_mode = os.environ.get('HAFISCAL_WELFARE6_FIX_DUR_AVG', 'on').lower()
    use_per_dur = (
        _fix_mode in ('on', '1', 'true') and
        'per_dur_cLvl_all_splurge' in pol_r and
        'per_dur_cLvl_all_splurge' in none_r
    )

    if use_per_dur:
        # CORRECT: per-duration welfare numerator, then weight by rec_probs.
        rec_probs = pol_r['rec_probs']
        n_dur = len(pol_r['per_dur_cLvl_all_splurge'])
        # base scenario: no recession, so single panel (use base_r['cLvl_all_splurge'])
        # since base has no per-dur structure.
        base_cLvl = base_r['cLvl_all_splurge']
        if 'per_dur_cLvl_all_splurge' in base_r:
            base_per_dur = base_r['per_dur_cLvl_all_splurge']
        else:
            base_per_dur = [base_cLvl] * n_dur

        sum_per_t = np.zeros(periods)
        for dur in range(n_dur):
            pol_c = pol_r['per_dur_cLvl_all_splurge'][dur]
            none_c = none_r['per_dur_cLvl_all_splurge'][dur]
            base_c = base_per_dur[dur]
            pol_w_d = felicity(pol_c)
            none_w_d = felicity(none_c)
            base_MU_d = np.maximum(base_c, 1e-16)**(-CRRA)
            sum_per_t += rec_probs[dur] * np.sum(
                (pol_w_d - none_w_d) / base_MU_d, 1)
        w6 = (
            np.sum(sum_per_t / NPV_AddInc / Rfree ** np.arange(periods))
            + (NPV_AddInc - NPV_AddCons) / NPV_AddInc
        )
    else:
        # LEGACY (buggy): u(dur-averaged cLvl).
        # Used when:
        #   - HAFISCAL_WELFARE6_FIX_DUR_AVG=off (explicit opt-out)
        #   - OR per-dur data not in pol_r/none_r (no-recession cells)
        pol_w = felicity(pol_r['cLvl_all_splurge'])
        none_w = felicity(none_r['cLvl_all_splurge'])
        base_MU = np.maximum(base_r['cLvl_all_splurge'], 1e-16)**(-CRRA)
        w6 = (
            np.sum(
                np.sum((pol_w - none_w) / base_MU, 1)
                / NPV_AddInc
                / Rfree ** np.arange(periods)
            )
            + (NPV_AddInc - NPV_AddCons) / NPV_AddInc
        )
    return w6


# Rec=0, AD=0
w6_check_norec = welfare6_mc(check_mc, base_mc, base_mc)
w6_ui_norec = welfare6_mc(ui_mc, base_mc, base_mc)
w6_taxcut_norec = welfare6_mc(taxcut_mc, base_mc, base_mc)

# Rec=1, AD=0
w6_check_rec = welfare6_mc(recCheck_mc, rec_mc, base_mc)
w6_ui_rec = welfare6_mc(recUI_mc, rec_mc, base_mc)
w6_taxcut_rec = welfare6_mc(recTaxCut_mc, rec_mc, base_mc)

# Rec=1, AD=1 — denominator held fixed at the corresponding AD=0 pair
w6_check_rec_AD = welfare6_mc(recCheck_AD_mc, rec_AD_mc, base_mc,
                              cost_pol_r=recCheck_mc, cost_none_r=rec_mc)
w6_ui_rec_AD = welfare6_mc(recUI_AD_mc, rec_AD_mc, base_mc,
                           cost_pol_r=recUI_mc, cost_none_r=rec_mc)
w6_taxcut_rec_AD = welfare6_mc(recTaxCut_AD_mc, rec_AD_mc, base_mc,
                               cost_pol_r=recTaxCut_mc, cost_none_r=rec_mc)

# ============================================================
# Write welfare6 table
# ============================================================
def mystr2dp(number):
    if not np.isnan(number):
        return "{:.2f}".format(number)
    return ''

os.makedirs(table_dir, exist_ok=True)

output = "\\begin{tabular}{@{}lccc@{}} \n"
output += "\\toprule \n"
output += "                          & Stimulus check      & UI extension    & Tax cut    \\\\  \\midrule \n"
output += "$\\mathcal{W}(\\text{policy}, Rec=0, AD=0)$ & " + mystr2dp(w6_check_norec) + "  & " + mystr2dp(w6_ui_norec) + "  & " + mystr2dp(w6_taxcut_norec) + "     \\\\ \n"
output += "$\\mathcal{W}(\\text{policy}, Rec=1, AD=0)$ & " + mystr2dp(w6_check_rec) + "  & " + mystr2dp(w6_ui_rec) + "  & " + mystr2dp(w6_taxcut_rec) + "     \\\\ \n"
output += "$\\mathcal{W}(\\text{policy}, Rec=1, AD=1)$ & " + mystr2dp(w6_check_rec_AD) + "  & " + mystr2dp(w6_ui_rec_AD) + "  & " + mystr2dp(w6_taxcut_rec_AD) + "     \\\\ \\bottomrule \n"
output += "\\end{tabular}  \n"

# Candidate-routing (QE-baseline freeze): writes welfare6_candidate.tex
# unless HAFISCAL_PROMOTE=1. See generated_output.py.
from generated_output import open_generated
with open_generated(table_dir + 'welfare6.tex') as f:
    f.write(output)

# ============================================================
# Summary
# ============================================================
elapsed = time() - t0_total

# Reference values depend on parametrization
if _param == 'Baseline':
    ref_label = "HAFiscal-QE published (Baseline, 21 types)"
    ref = {'check': [0.96, 1.00, 1.35], 'ui': [0.85, 1.82, 2.13], 'taxcut': [0.99, 0.98, 1.11]}
else:
    ref_label = "(no prior reference for Reduced_Run)"
    ref = None

print(f"\n{'='*60}")
print(f"HYBRID WELFARE6 ({_param}, MC standard, N={AgentCountTotal})")
print(f"{'='*60}")
print(f"\n  {'':>35} {'Check':>8} {'UI':>8} {'TaxCut':>8}")
print(f"  {'Rec=0, AD=0':>35} {w6_check_norec:8.2f} {w6_ui_norec:8.2f} {w6_taxcut_norec:8.2f}")
print(f"  {'Rec=1, AD=0':>35} {w6_check_rec:8.2f} {w6_ui_rec:8.2f} {w6_taxcut_rec:8.2f}")
print(f"  {'Rec=1, AD=1':>35} {w6_check_rec_AD:8.2f} {w6_ui_rec_AD:8.2f} {w6_taxcut_rec_AD:8.2f}")
if ref:
    print(f"\n  {ref_label}:")
    print(f"  {'':>35} {'Check':>8} {'UI':>8} {'TaxCut':>8}")
    print(f"  {'Rec=0, AD=0':>35} {ref['check'][0]:8.2f} {ref['ui'][0]:8.2f} {ref['taxcut'][0]:8.2f}")
    print(f"  {'Rec=1, AD=0':>35} {ref['check'][1]:8.2f} {ref['ui'][1]:8.2f} {ref['taxcut'][1]:8.2f}")
    print(f"  {'Rec=1, AD=1':>35} {ref['check'][2]:8.2f} {ref['ui'][2]:8.2f} {ref['taxcut'][2]:8.2f}")
else:
    print(f"\n  {ref_label}")
print(f"\n  Table: {table_dir}welfare6.tex")
print(f"  Total time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
