#!/usr/bin/env python
"""check_rec via BUCKETED-5D — the Plan A closure for the income-dependent Check.

The 5-D joint kernel tracks (aᵖ,aⁿ,aᵇ,jᵖ⁼ⁿ,jᵇ) but NOT pLvl, while the stimulus
check CheckStimLvl·φ(pLvl)/pLvl depends on pLvl (the phase-out). So we partition by
pLvl bucket (where the check is ~constant), run the 5-D joint WITHIN each bucket —
which closes the within-cell (a,j) Jensen gap the bucket-MEAN method leaves
(+1.76% vs MC at HS_Only) — and aggregate over buckets (which capture φ(pLvl)).

Reuses tm_methods._compute_check_buckets (per-bucket check TranShk_addition + weight)
and welfare6_tm_joint5d.compute_joint_welfare5d, with the same recessionCheck /
recession / base solve + duration weighting as the UI 5-D baseline driver.

  python welfare6_check_rec_bucketed5d.py --parametrization HS_Only --n-buckets 10 --workers 8
  (JOINT5D_ACOUNT controls the asset grid; default 50.)
"""
import argparse
import os
import sys
import time
from copy import deepcopy
from multiprocessing import Pool

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_FPC = os.path.join(_HERE, "FromPandemicCode")
_MY_ARGV = sys.argv[1:]            # capture before neutralizing
sys.path.insert(0, _FPC)
os.chdir(_FPC)
sys.argv = [sys.argv[0]]           # neutralize argv for FromPandemicCode module parsers

from welfare6_scenario import build_and_solve              # noqa: E402
from welfare6_tm_joint5d import compute_joint_welfare5d    # noqa: E402
from tm_methods import (compute_baseline_tm_data,          # noqa: E402
                        calculate_NPV, _compute_check_buckets)

# fork-COW globals (set in main before the Pool; read by workers)
_POL = _NONE = _BASE = _BD = None
_ACT_T = _NEP = None
_BUCKET_ADD = None  # _BUCKET_ADD[c][b] -> (J,) TranShk_addition for cohort c bucket b


def _path(act_T, nep, dur):
    p = list(np.arange(1, nep + 1) * 2) + [0] * (act_T + 5)
    p = p[:act_T]
    for t in range(min(dur, len(p))):
        p[t] += 1
    return p


def _work(arg):
    c, b, d_idx = arg
    J = _POL[c].num_base_MrkvStates
    tr = np.zeros((_ACT_T, J))
    tr[0, :] = _BUCKET_ADD[c][b]          # check is a one-shot t=0 transfer
    res = compute_joint_welfare5d(
        _POL[c], _NONE[c], _BASE[c], _BD[c],
        EconomyMrkv_path_pn=_path(_ACT_T, _NEP, d_idx + 1), act_T=_ACT_T,
        shock_type_pol='recessionCheck',
        TranShk_addition_pol_series=tr,
    )
    return (c, b, d_idx,
            np.asarray(res['welfare_num_series']),
            np.asarray(res['AggInc_pol_series']) - np.asarray(res['AggInc_none_series']),
            np.asarray(res['AggCons_pol_series']) - np.asarray(res['AggCons_none_series']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--parametrization', default='HS_Only')
    ap.add_argument('--n-buckets', type=int, default=10)
    ap.add_argument('--workers', type=int, default=8)
    args, _ = ap.parse_known_args(_MY_ARGV)
    aCount = int(os.environ.get('JOINT5D_ACOUNT', 50))
    nb = args.n_buckets

    print(f"=== check_rec bucketed-5D: {args.parametrization}, A={aCount}, "
          f"n_buckets={nb}, workers={args.workers} ===", flush=True)
    t0 = time.time()
    ctx = build_and_solve(args.parametrization)
    pol = deepcopy(ctx['AggEco']); pol.switch_shock_type('recessionCheck'); pol.solve()
    none = deepcopy(ctx['AggEco']); none.switch_shock_type('recession'); none.solve()
    base = deepcopy(ctx['AggEco']); base.switch_shock_type('base'); base.solve()
    for ag in list(pol.agents) + list(none.agents) + list(base.agents):
        ag.tm_a_indexed = True
    bd = compute_baseline_tm_data(base, mCount=aCount, neutral_measure=True)

    act_T = ctx['act_T']; nep = ctx['num_experiment_periods']
    Rspell = ctx.get('Rspell', 4.0); max_dur = ctx.get('max_recession_duration', nep)
    Rp = 1.0 - 1.0 / Rspell
    rec_probs = np.array([Rp**t * (1 - Rp) for t in range(max_dur)])
    rec_probs[-1] = 1.0 - np.sum(rec_probs[:-1])
    n_coh = len(pol.agents)
    counts = np.array([ag.AgentCount for ag in pol.agents], dtype=float)
    cohort_w = counts / counts.sum()

    bucket_add, bucket_w = [], []
    for c in range(n_coh):
        bks = _compute_check_buckets(pol.agents[c], n_buckets=nb)
        bucket_add.append([float(bk['E_check_nrm_b']) for bk in bks])  # scalar per bucket; _work broadcasts to (J,)
        bucket_w.append([float(bk['weight']) for bk in bks])
    print(f"      buckets/cohort: {[len(b) for b in bucket_add]}  "
          f"weight-sums: {[round(sum(w), 4) for w in bucket_w]}", flush=True)

    global _POL, _NONE, _BASE, _BD, _ACT_T, _NEP, _BUCKET_ADD
    _POL, _NONE, _BASE, _BD = pol.agents, none.agents, base.agents, bd
    _ACT_T, _NEP, _BUCKET_ADD = act_T, nep, bucket_add

    items = [(c, b, d) for c in range(n_coh)
             for b in range(len(bucket_add[c])) for d in range(max_dur)]
    print(f"      {len(items)} (cohort,bucket,dur) work items", flush=True)
    t1 = time.time()
    if args.workers > 1:
        with Pool(args.workers) as pool:
            results = pool.map(_work, items)
    else:
        results = [_work(it) for it in items]
    print(f"      kernel wall: {time.time() - t1:.1f}s", flush=True)

    welfare_num = np.zeros(act_T); AddInc = np.zeros(act_T); AddCons = np.zeros(act_T)
    from collections import defaultdict as _dd
    _pbw = _dd(lambda: np.zeros(act_T)); _pbi = _dd(lambda: np.zeros(act_T)); _pbc = _dd(lambda: np.zeros(act_T))
    for c, b, d, wn, ai, ac in results:
        w = cohort_w[c] * bucket_w[c][b] * rec_probs[d]
        welfare_num += w * wn; AddInc += w * ai; AddCons += w * ac
        wb = cohort_w[c] * rec_probs[d]   # per-bucket (no bucket_w) -> within-bucket cell
        _pbw[(c, b)] += wb * wn; _pbi[(c, b)] += wb * ai; _pbc[(c, b)] += wb * ac

    R = float(np.asarray(pol.agents[0].Rfree).flatten()[0])

    def npv(s):
        v = calculate_NPV(s, act_T, R)
        return float(v[-1]) if hasattr(v, '__len__') else float(v)

    # [deep dive] per-bucket within-bucket cell for MC-vs-TM localization
    _pb = {}
    for k in _pbw:
        _nw, _ni, _nc = npv(_pbw[k]), npv(_pbi[k]), npv(_pbc[k])
        _pb[k] = dict(NPV_w=_nw, NPV_AI=_ni, NPV_AC=_nc, cell=_nw/_ni + (_ni-_nc)/_ni,
                      weight=bucket_w[k[0]][k[1]])
    import pickle as _pk
    _pk.dump(_pb, open('../Results/tmp/bucketed5d_perbucket.pkl', 'wb'))
    print("    [per-bucket cells] " + " ".join(f"b{k[1]}={v['cell']:.4f}" for k, v in sorted(_pb.items())), flush=True)

    NPV_w, NPV_AI, NPV_AC = npv(welfare_num), npv(AddInc), npv(AddCons)
    cell = NPV_w / NPV_AI + (NPV_AI - NPV_AC) / NPV_AI
    mc = 1.0140
    print(f"\n=== check_rec bucketed-5D (A={aCount}, nb={nb}) = {cell:.4f} ===")
    print(f"    [tm-comp] NPV_w={NPV_w:.5f} NPV_AddInc={NPV_AI:.5f} NPV_AddCons={NPV_AC:.5f} "
          f"term1={NPV_w/NPV_AI:.5f} term2={(NPV_AI-NPV_AC)/NPV_AI:.5f}", flush=True)
    print(f"    MC = {mc:.4f}   bias(MC-5D) = {100 * (mc - cell) / cell:+.2f}%   "
          f"(bucket-MEAN TM was +1.76%)")
    print(f"    total wall: {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
