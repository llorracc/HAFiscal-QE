#!/usr/bin/env python
"""T_sim convergence sweep — does brute-force MC reach the stationary truth?

Tests the hypothesis (Parameters.py:102-114; user 2026-06-05) that the MC<->TM
wealth gap is MC UNDER-CONVERGENCE: high-beta agents have a mixing time >= T_sim,
so brute MC at finite T_sim underestimates stationary wealth, while TM and the
Harmenberg-Doob method reflect the true stationary distribution.

For a fixed high-beta agent, compute E_Q[a] (permanent-income-weighted mean
wealth = the Harmenberg neutral-measure aggregate) via brute MC at growing
T_sim, against TWO stationary-truth references: the TM-Q ergodic and Doob. If
MC climbs toward them, the hypothesis is confirmed; if TM-Q == Doob, Doob is a
validated fast stationary method.

Reuses the harmenberg_doob_tier1 building blocks. Legacy UI encoding (the
building blocks predate the 6-state bug_fix; the encoding is orthogonal to
mixing). New driver in Code/HA-Models/ (not FromPandemicCode/).

OUTCOME (2026-06-05, BUG-051 investigation): hypothesis REFUTED. The MC<->TM
wealth gap was TM-a omitting the (1-varsigma) ESC household-spending (splurge)
correction — see BUGS_private/HAFiscal_BUG-051_tm_a_ESC_missing_splurge_correction.md
— not MC under-convergence; with the fix, MC matches TM to ~1-2%. In RATIOS,
stationarity is the GIC (with G and E[1/psi]), not beta*R, so MC ratios do
converge. Doob was NOT adopted. Kept as the historical test harness.

Usage: python mc_tsim_convergence.py --educ 1 --beta 0.98 --tsims 400,800,1600,3200,6400
"""
import os
import sys
import argparse
import time

ap = argparse.ArgumentParser()
ap.add_argument('--educ', type=int, default=1)
ap.add_argument('--beta', type=float, default=0.98)
ap.add_argument('--tsims', default='400,800,1600,3200,6400')
ap.add_argument('--nmc', type=int, default=200000)
ap.add_argument('--seed', type=int, default=30000)
args = ap.parse_args()

sys.argv = [sys.argv[0]]  # estimators read argv positionally -> fall back to defaults
os.environ['HAFISCAL_UI_STATE_ENCODING'] = 'legacy'   # building blocks expect 4-state
os.environ.setdefault('HAFISCAL_PERMGROFAC_FIX', '1')
# BUG-051 guard: require an explicit interpretation, no silent default. (CDC is
# the Doob-validated choice for this diagnostic — set HAFISCAL_INTERPRETATION=CDC.)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _interpretation import get_interpretation as _gi
_gi(require=True)

HERE = os.path.dirname(os.path.abspath(__file__))
FPC = os.path.join(HERE, 'FromPandemicCode')
sys.path.insert(0, FPC)
os.chdir(FPC)

import numpy as np
from harmenberg_doob_tier1 import setup_context, build_agent_for, run_mc_capture_aj
from tm_methods import (build_tm_agg_fiscal_a, find_ergodic_distribution,
                        compute_doob_pi_q_a)

INTERP = os.environ['HAFISCAL_INTERPRETATION']
print(f"=== T_sim convergence: educ={args.educ} beta={args.beta:.4f} "
      f"(betaR={args.beta*1.01:.4f}) interp={INTERP} ===", flush=True)

ctx = setup_context('Baseline')
agent = build_agent_for(args.educ, args.beta, ctx)

# Stationary-truth references (A=500, aMax=5000): TM-Q ergodic + Doob
tm_P = build_tm_agg_fiscal_a(agent, aCount=500, aMax=5000, aFac=3,
                             neutral_measure=False, interpretation=INTERP)
pi_P = find_ergodic_distribution(tm_P['TranMatrix'])
tm_Q = build_tm_agg_fiscal_a(agent, aCount=500, aMax=5000, aFac=3,
                             neutral_measure=True, interpretation=INTERP)
pi_Q_TM = find_ergodic_distribution(tm_Q['TranMatrix'])
doob = compute_doob_pi_q_a(agent, tm_P, pi_P, interpretation=INTERP)['pi_Q_doob']

ag = tm_P['dist_aGrid']
J = pi_P.shape[0] // len(ag)
A = len(ag)
E_TM = float(np.sum(pi_Q_TM.reshape(J, A) * ag[None, :]))
E_doob = float(np.sum(doob.reshape(J, A) * ag[None, :]))


def _wmedian(grid, w):
    """Weighted median of `grid` with weights `w` (the estimation's statistic)."""
    w = np.asarray(w, float)
    w = w / w.sum()
    order = np.argsort(grid)
    g = np.asarray(grid)[order]
    c = np.cumsum(w[order])
    return float(np.interp(0.5, c, g))


# TM-P (population-measure) ergodic median of aNrm — the ACTUAL estimation target
a_marg_P = pi_P.reshape(J, A).sum(axis=0)          # marginal over Markov state j
med_TM_P = 100.0 * _wmedian(ag, a_marg_P)

print(f"  AGGREGATE (Q-measure):  TM-Q E_Q[a]={E_TM:.4f}  Doob E_Q[a]={E_doob:.4f}  "
      f"(Doob vs TM {100*(E_doob-E_TM)/E_TM:+.2f}%)", flush=True)
print(f"  MEDIAN (P-measure):     TM-P median(aNrm)={med_TM_P:.3f}  <- estimation target", flush=True)
print(f"  {'T_sim':>7} {'MC E_Q[a]':>11} {'%TM-Q':>7} {'MC median':>11} {'%TM-P':>7} {'time':>7}", flush=True)
for T_sim in [int(x) for x in args.tsims.split(',')]:
    t0 = time.time()
    aNrm, j_arr, pLvl = run_mc_capture_aj(
        agent, args.nmc, seed=args.seed, T_sim=T_sim, capture_T=T_sim - 50)
    E_MC = float(np.average(aNrm, weights=pLvl))
    med_MC = 100.0 * float(np.median(aNrm))         # unweighted, as in the estimation
    print(f"  {T_sim:>7} {E_MC:>11.4f} {100*E_MC/E_TM:>6.1f}% {med_MC:>11.3f} "
          f"{100*med_MC/med_TM_P:>6.1f}% {time.time()-t0:>6.1f}s", flush=True)
print("SWEEP_DONE", flush=True)
