#!/usr/bin/env python3
"""
YAML <-> HAFiscal-code consistency check (#1), on the _TM-vs-MC branch, ESC mode.

Builds a baseline single-cohort AggFiscalType (interpretation='ESC'), solves with
HAFiscal's actual solver, extracts its EXACT calibration (DiscFac, CRRA, Rfree, LivPrb
vector, PermGroFac vector, joint MrkvArray, per-state IncShkDstn), then runs the
independent textbook EGM (the same equations the dolo-plus YAML encodes) with that
EXACT calibration and compares the employed-state consumption policy cFunc[0](m).

Rationale: under ESC the optimizer-stage cFunc is HARK's standard Markov buffer-stock
(a = m - c); ESC/CDC differ only in the out-of-YAML simulation asset update. So this
check validates that the YAML's optimizer-stage EQUATIONS reproduce HAFiscal's solved
policy, decoupled from calibration-value choices.

PASS: max relative |cFunc_HAFiscal(m) - cFunc_EGM(m)| over a set of m probe points < 1e-3.
"""
import os, sys
from pathlib import Path
import numpy as np

os.environ.setdefault("HAFISCAL_INTERPRETATION", "ESC")
FPC = Path(__file__).resolve().parents[1] / "FromPandemicCode"
sys.path.insert(0, str(FPC))
os.chdir(FPC)                       # Parameters loads files relative to cwd
sys.argv = ["check", "1.01", "2.0", "0.7", "0.5"]   # Rfree, CRRA, IncUnemp, IncUnempNoBenefits

from copy import deepcopy
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters

# ---- 1. build + solve a baseline HS cohort in ESC mode ----------------------
P = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
(init_dropout, init_highschool, init_college, init_ADEconomy,
 DiscFacDstns, DiscFacCount, AgentCountTotal, base_dict,
 num_max_iterations_solvingAD, convergence_tol_solvingAD,
 UBspell_normal, num_base_MrkvStates, *_rest) = P

econ = AggregateDemandEconomy(**init_ADEconomy)
hs = AggFiscalType(**init_highschool)
hs.interpretation = "ESC"
hs.cycles = 0
hs.get_economy_data(econ)
from HARK.distributions import DiscreteDistribution
IncShk_u  = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([hs.IncUnemp])])
IncShk_un = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([hs.IncUnempNoBenefits])])
Emp = deepcopy(hs.IncShkDstn[0])
hs.IncShkDstn = [[Emp] + [IncShk_u] * (num_base_MrkvStates - 2) + [IncShk_un]]
hs.IncShkDstn_base = hs.IncShkDstn
hs.DiscFac = float(DiscFacDstns[1].atoms[0][0])
econ.agents = [hs]
hs.update_mrkv_array("base")
hs.solve()

# ---- 2. extract HAFiscal's EXACT calibration --------------------------------
cFuncs = hs.solution[0].cFunc
J = len(cFuncs)
beta = float(hs.DiscFac); rho = float(hs.CRRA)
Rvec = np.asarray(hs.Rfree).ravel()
Rfree = float(Rvec[0]); assert np.allclose(Rvec, Rfree), Rvec
LivPrb = np.asarray(hs.LivPrb[0]).ravel()[:J]
PermGroFac = np.asarray(hs.PermGroFac[0]).ravel()[:J]
Mrkv = np.asarray(hs.MrkvArray[0])[:J, :J]
IncShk = hs.IncShkDstn[0]                       # list length J of DiscreteDistribution
print(f"[HAFiscal ESC solve] J={J}  beta={beta:.6f}  rho={rho}  Rfree={Rfree}")
print(f"  PermGroFac = {np.round(PermGroFac,6)}")
print(f"  LivPrb[:3] = {np.round(LivPrb[:3],6)}   Splurge={hs.Splurge:.4f}")
print(f"  MrkvArray row0 = {np.round(Mrkv[0],4)}")

def shock_nodes(z):
    d = IncShk[z]
    return np.asarray(d.atoms[0]), np.asarray(d.atoms[1]), np.asarray(d.pmv)
SH = [shock_nodes(z) for z in range(J)]

# ---- 3. independent EGM with HAFiscal's EXACT calibration -------------------
# factor_mode: 'standard' uses (PermGroFac*psi)^(-rho) in the marginal value (spec 7.4,
#   standard HARK, the dolo-plus YAML); 'hafiscal_code' uses psi^(-rho) only, matching
#   AggFiscalModel.py:1803 (which omits PermGroFac^(-rho) — likely a bug).
FACTOR_MODE = os.environ.get("EGM_FACTOR_MODE", "standard")
def solve_egm():
    aGrid = np.concatenate([[0.0], np.exp(np.linspace(np.log(0.01), np.log(2000.0), 220))])
    m0 = np.concatenate([[0.0], np.exp(np.linspace(np.log(0.01), np.log(2100.0), 260))])
    mPol = [m0.copy() for _ in range(J)]; cPol = [m0.copy() for _ in range(J)]
    ce = lambda m, z: np.interp(m, mPol[z], cPol[z])
    for it in range(4000):
        nm, nc, chg = [], [], 0.0
        for z in range(J):
            E = np.zeros_like(aGrid)
            for zp in range(J):
                pz = Mrkv[z, zp]
                if pz == 0.0: continue
                psi, theta, pr = SH[zp]; Gp = PermGroFac[zp] * psi
                mp = Rfree * np.outer(aGrid, 1.0 / Gp) + theta[None, :]
                cp = ce(mp, zp)
                fac = (Gp if FACTOR_MODE == "standard" else psi)[None, :] ** (-rho)
                E += pz * (fac * (cp ** (-rho)) * pr[None, :]).sum(1)
            E *= beta * LivPrb[z] * Rfree
            c = E ** (-1.0 / rho); m = aGrid + c
            m = np.concatenate([[0.0], m]); c = np.concatenate([[0.0], c])
            nm.append(m); nc.append(c)
            chg = max(chg, abs(np.interp(5.0, m, c) - ce(5.0, z)))
        mPol, cPol = nm, nc
        if chg < 1e-12: break
    return (lambda m, z: float(np.interp(m, mPol[z], cPol[z]))), it + 1
egm, it = solve_egm()

# ---- 4. compare cFunc[0] (employed) across probe points ---------------------
probes = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 20.0, 50.0, 100.0, 300.0, 1000.0]
print(f"\n[EGM converged it={it}, FACTOR_MODE={FACTOR_MODE}]  comparison of employed-state cFunc[0](m):")
print(f"  {'m':>6} {'HAFiscal':>12} {'EGM':>12} {'rel.diff':>10}")
maxrel = 0.0
for m in probes:
    ch = float(cFuncs[0](np.array([m]), np.array([1.0]))[0]); ce_ = egm(m, 0)  # 2D cFunc(m,Cratio=1)
    rel = abs(ch - ce_) / abs(ch); maxrel = max(maxrel, rel)
    print(f"  {m:>6.1f} {ch:>12.6f} {ce_:>12.6f} {rel:>10.2e}")
PASS = maxrel < 1e-3
print(f"\nmax rel diff (employed cFunc) = {maxrel:.3e}   RESULT: {'PASS (<1e-3)' if PASS else 'FAIL'}")
sys.exit(0 if PASS else 1)
