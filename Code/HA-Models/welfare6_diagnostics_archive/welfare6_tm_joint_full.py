"""
Full multi-duration joint-kernel driver for ui_rec welfare-6 cell at HS_Only
bug_fix.

Loops over all recession durations, weights by rec_probs, applies the
welfare-6 cell formula, compares to MC reference.

Standalone — uses existing T.2 pickle for AggCons/AggIncome denominators.
"""
from __future__ import annotations
import os, sys, time, pickle
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint import compute_joint_welfare
from tm_methods import compute_baseline_tm_data, calculate_NPV


def _build_econ_mrkv_path(act_T, num_experiment_periods, is_recession,
                          recession_duration=None, is_base=False):
    """Mirror welfare6_tm._build_econ_mrkv_path."""
    if is_base:
        return [0] * act_T
    path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    if is_recession:
        if recession_duration is None:
            recession_duration = num_experiment_periods
        for t in range(min(recession_duration, len(path))):
            path[t] = path[t] + 1
    return path


def main():
    print("=== welfare6_tm_joint_full: ui_rec multi-duration aggregation ===")
    print(f"  HAFISCAL_UI_STATE_ENCODING = {os.environ.get('HAFISCAL_UI_STATE_ENCODING', 'legacy')}")
    print()

    t0 = time.time()
    print("[1/5] Loading T.2 pickle for AggCons/AggIncome denominators...")
    T2_PKL = ("reproduce/logs/tm_a_phase3/T2_smoke_HS_Only_bugfix.pkl")
    with open(T2_PKL, 'rb') as f:
        t2 = pickle.load(f)
    AC_pol = np.asarray(t2['results_summary']['recessionUI']['AggCons'])
    AC_none = np.asarray(t2['results_summary']['recession']['AggCons'])
    AI_pol = np.asarray(t2['results_summary']['recessionUI']['AggIncome'])
    AI_none = np.asarray(t2['results_summary']['recession']['AggIncome'])
    _rf = t2['results_summary']['recessionUI']['Rfree']
    Rfree_t = float(_rf if np.isscalar(_rf) else _rf[0])
    print(f"      Rfree = {Rfree_t}, act_T = {len(AC_pol)}")

    print("[2/5] Building HS_Only context + solving 3 scenarios...")
    ctx = build_and_solve('HS_Only')
    nep = ctx['num_experiment_periods']
    act_T = ctx['act_T']
    print(f"      cohorts: {len(ctx['AggEco'].agents)}, act_T={act_T}, nep={nep}")

    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
    AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
    for ag in AggEco_pol.agents: ag.tm_a_indexed = True
    for ag in AggEco_none.agents: ag.tm_a_indexed = True
    for ag in AggEco_base.agents: ag.tm_a_indexed = True
    print(f"      solved in {time.time() - t0:.1f}s")

    print("[3/5] Computing baseline_tm_data (aCount=50)...")
    aCount = 50
    base_baseline_tm_data = compute_baseline_tm_data(AggEco_base, mCount=aCount)

    print("[4/5] Joint kernel: iterating over all 12 recession durations...")
    cohort_idx = 0
    agent_pol = AggEco_pol.agents[cohort_idx]
    agent_none = AggEco_none.agents[cohort_idx]
    agent_base = AggEco_base.agents[cohort_idx]
    bd = base_baseline_tm_data[cohort_idx]

    # Recession durations: same as welfare6_tm.py (max_dur ~ nep, R_persist=1-1/Rspell)
    Rspell = ctx.get('Rspell', 4.0)
    max_dur = ctx.get('max_recession_duration', nep)
    R_persist = 1.0 - 1.0 / Rspell
    rec_probs = np.array([R_persist**t * (1 - R_persist) for t in range(max_dur)])
    rec_probs[-1] = 1.0 - np.sum(rec_probs[:-1])
    print(f"      max_dur={max_dur}, rec_probs[:5]={rec_probs[:5]}, sum={rec_probs.sum():.4f}")

    welfare_num_b2_total = np.zeros(act_T)
    welfare_num_b3_total = np.zeros(act_T)

    t1 = time.time()
    for d_idx, dur in enumerate(range(1, max_dur + 1)):
        path = _build_econ_mrkv_path(act_T, nep, is_recession=True,
                                      recession_duration=dur)
        res = compute_joint_welfare(
            agent_pol, agent_none, agent_base, bd,
            EconomyMrkv_path=path, act_T=act_T,
        )
        welfare_num_b2_total += rec_probs[d_idx] * res['welfare_num_b2_series']
        welfare_num_b3_total += rec_probs[d_idx] * res['welfare_num_b3_series']
        if dur <= 3 or dur == max_dur:
            print(f"      dur={dur:2d}, prob={rec_probs[d_idx]:.4f}, "
                  f"sum(b2)={res['welfare_num_b2_series'].sum():.2e}, "
                  f"sum(b3)={res['welfare_num_b3_series'].sum():.2e}, "
                  f"wall={time.time() - t1:.1f}s")

    print(f"      total joint kernel wall: {time.time() - t1:.1f}s")

    print("[5/5] Computing welfare-6 cell formula...")
    Add_Inc = AI_pol - AI_none
    Add_Cons = AC_pol - AC_none
    def _npv_scalar(s):
        v = calculate_NPV(s, act_T, Rfree_t)
        return float(v[-1]) if hasattr(v, '__len__') else float(v)
    NPV_w_b2 = _npv_scalar(welfare_num_b2_total)
    NPV_w_b3 = _npv_scalar(welfare_num_b3_total)
    NPV_AI = _npv_scalar(Add_Inc)
    NPV_AC = _npv_scalar(Add_Cons)
    print(f"      NPV(welfare_b2)  = {NPV_w_b2:.2e}")
    print(f"      NPV(welfare_b3)  = {NPV_w_b3:.2e}")
    print(f"      NPV(AddInc)      = {NPV_AI:.2e}")
    print(f"      NPV(AddCons)     = {NPV_AC:.2e}")

    if abs(NPV_AI) < 1e-10:
        print("      AddInc near-zero; cannot form cell ratio")
    else:
        ui_rec_b2 = NPV_w_b2 / NPV_AI + (NPV_AI - NPV_AC) / NPV_AI
        ui_rec_b3 = NPV_w_b3 / NPV_AI + (NPV_AI - NPV_AC) / NPV_AI
        print()
        print("=== Results ===")
        print(f"  ui_rec (joint, b2 anchor):  {ui_rec_b2:.4f}")
        print(f"  ui_rec (joint, b3 anchor):  {ui_rec_b3:.4f}")
        print(f"  ui_rec (T.2 bucket):        {t2['welfare6_cells_bucket']['ui_rec']:.4f}")
        print(f"  ui_rec (T.2 percell):       {t2['welfare6_cells_percell']['ui_rec']:.4f}")
        print(f"  ui_rec (MC nshuf 6-seed):   1.6168 ± 0.0027")

    print(f"\nTotal wall: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
