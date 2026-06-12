"""Quantify the theGICfactor 0.999-vs-0.9995 tradeoff: per-solve TIME vs College FIT, side by side.

Standalone diagnostic (run with the numpy<2 .venv):
    .venv/bin/python Code/HA-Models/measure_gicfactor_tradeoff.py

Always runs fix-on (GPF-shave). Built 2026-06-10 to settle whether theGICfactor=0.9995 carries a
per-solve cost vs 0.999. RESULT (HS/College cap atom): it does NOT — per-solve EGM time is EQUAL
(2.82s @0.999 vs 2.12s @0.9995, ratio 0.8x; both GPF~=0.999, far from the boundary), and 0.9995
fits College ~20% BETTER (common-grid aMax=1300 distance 5.21 vs 6.52). So 0.9995 = better fit at
no per-solve cost. (This retracts an in-session "0.9995 ~10x slower" hypothesis.)
"""
import os, sys, time
sys.argv = [sys.argv[0]]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "FromPandemicCode"))
os.environ.setdefault("HAFISCAL_INTERPRETATION", "ESC")
os.environ["HAFISCAL_GIC_SHAVE_ON_GPF"] = "1"
os.environ["HAFISCAL_GICX_MODE"] = "hardcoded"
os.environ["HAFISCAL_EDTYPES"] = ""        # import the objective without running NM
os.environ["HAFISCAL_SKIP_ESTIMATION"] = "1"
os.environ["HAFISCAL_QUIET_BETADISTR"] = "1"
import numpy as np
import EstimParameters as ep
from EstimParameters import (init_college, init_ADEconomy, gic_capped_beta,
                             GICmaxBetas, CRRA, UBspell_normal)
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution


def single_college():
    ag = AggFiscalType(**init_college); ag.cycles = 0
    eco = AggregateDemandEconomy(**init_ADEconomy); ag.get_economy_data(eco)
    Du = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnemp])])
    Dn = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnempNoBenefits])])
    ag.IncShkDstn = [[ag.IncShkDstn[0]] + [Du] * UBspell_normal + [Dn]]
    ag.IncShkDstn_base = ag.IncShkDstn
    ag.AgentCount = 1; ag.tm_a_indexed = True; ag.interpretation = "ESC"
    eco.agents = [ag]
    return ag, eco


ag, eco = single_college()
ag.DiscFac = 0.95
eco.solve()  # JIT warmup so timings exclude first-call numba compile

print("=== SOLVE TIME: single college cap atom under each GIC margin (fix on) ===")
times = {}
for shave in (0.999, 0.9995):
    cap = gic_capped_beta(2, shave)
    gpf = (cap / GICmaxBetas[2]) ** (1.0 / CRRA)
    ag.DiscFac = cap
    t0 = time.time(); eco.solve(); dt = time.time() - t0
    times[shave] = dt
    print(f"  theGICfactor={shave}: cap beta={cap:.6f} GPF={gpf:.5f}  solve={dt:.2f}s", flush=True)
print(f"  RATIO (0.9995/0.999) = {times[0.9995] / max(times[0.999], 1e-9):.1f}x")

print("\n=== COLLEGE FIT under each GIC margin (aMax=1300, common grid; lower=better) ===")
import estim_phase2_tm_a as E
os.environ["HAFISCAL_TM_AMAX"] = "1300.0"
opt = {0.999: (0.9921, 0.0214), 0.9995: (0.9920, 0.0233)}  # each margin's known optimum
for shave in (0.999, 0.9995):
    GICx = float(np.log(shave / (1 - shave)))
    b, n = opt[shave]
    d = float(E.betas_obj_func_educ_tm_a(b, n, GICx, educ_type=2))
    print(f"  theGICfactor={shave}: GICx={GICx:.4f}  college distance at optimum "
          f"(beta={b},nabla={n}) = {d:.3f}", flush=True)
