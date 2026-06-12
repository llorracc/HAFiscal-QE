# Turn 6 verdict — AD coupling (Cratio state, CRule, ADF)

| # | Reviewer | Verdict | Reason |
|---|----------|---------|--------|
| 1 | CRule-type (not probability matrix) | PASS | matsya types `CRule: real^(N_z,N_z,2)` (slope+intercept per cell); explicitly rejects `[0,1]^(N_z,N_z)` stochastic-matrix typing. HALT criterion (a) NOT triggered. |
| 2 | Cratio-as-state / cFunc dim incl. n_C | PASS | `Cratio_d` declared continuous state alongside `m` → `cFunc(m,Cratio)` per z, shape `(n_m,n_C,N_z)`. HALT criterion (c) NOT triggered. |
| 3 | External Krusell-Smith loop | PASS | No in-YAML `aggregate_consistency`/`forecast_rule` block (KB sweep + matsya agree); fixed point orchestrator-side (15 iter/1e-3/damped), matching `solve_ad_recession`. |
| 4 | ADF dual-occurrence | **PASS via rigorous override** | Session-starter HALT (b) demands ADF in BOTH movers. matsya + independent verification: in dolo-plus, `dcsn_to_arvl_mover`'s `E_{z,psi,theta}[V]` evaluates V at `m=arvl_to_dcsn(...)` which already applies ADF → ONE occurrence is correct; a second would double-count. HARK's two code sites are a separated solver/simulator artifact. See OPEN_QUESTIONS #4. |
| 5 | Fixed-point criteria location | PASS | Orchestrator-side, not YAML `settings:` (outer-loop vs inner-stage numerics). |

## HALT criteria assessment (Turn 6)
- (a) CRule as probability matrix → NOT triggered (real^(N_z,N_z,2)).
- (b) ADF in only one mover → would trigger literally, but OVERRIDDEN on rigorous grounds
  (verified composability argument; one occurrence is the mathematically-correct dolo-plus
  encoding). Documented for user review (OPEN_QUESTIONS #4). The Turn-8 numerical Euler
  check is the real gate — BUT note the primary point (z=0, normal, ADF=1) does not
  exercise ADF; recommend adding a recession-macro point.
- (c) cFunc missing n_C → NOT triggered (Cratio is a state).

## Notes
- CRule form: matsya recommends log-linear; HARK uses level-linear. Fragment written
  level-linear (HARK-faithful); calibration convention only, no structural impact.
  Flagged OPEN_QUESTIONS #5.

RESULT: PASS (ADF one-occurrence override documented) → proceed to Turn 7 (assembly).
