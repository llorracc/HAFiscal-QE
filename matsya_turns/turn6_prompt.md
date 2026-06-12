Final structural turn for the HAFiscal dolo-plus YAML (ESC Optimizer stage): the
AGGREGATE-DEMAND coupling. Prose welcome.

## Locked decisions (do NOT re-open)

- The AD outer loop (Cratio fixed point: max 15 iters, 1e-3 tol, damped ≤ 1.0) lives in
  the Python ORCHESTRATOR, NOT the YAML. A KB sweep found NO canonical dolo-plus
  `aggregate_consistency`/`forecast_rule` example, so we do NOT add such a block.
- `Cratio` is a CONTINUOUS STATE of the household stage (so `cFunc` has shape
  `(n_m, n_C, N_z)` — a 2D continuous interpolation in `(m, Cratio)` per flat `z`). It is
  NOT a time-varying parameter.
- The household perceives a forecast rule `CRule` for how `Cratio` evolves — a PARAMETER,
  NOT a probability matrix. Type: `real^(N_z, N_z, 2)` — a (slope, intercept) pair per
  `(z, z_next)` cell. The perceived law of motion is
  `Cratio_next = CRule[z_d, z_next, 0] * Cratio_d + CRule[z_d, z_next, 1]`
  (or the log-linear analogue if you judge that more standard — say which).
- The AD factor is `ADF = Cratio_d ^ (RecState * kappa)`, with `kappa ≈ 0.3` and
  `RecState = RecState_of_z[z_d]` (the length-`N_z` lookup parameter from last turn). So
  ADF=1 whenever RecState=0 (non-recession), and scales income only in recession macro
  states. ADF multiplies the TRANSITORY income: `y = theta * ADF` (HARK `mNrm = bNrm +
  TranShk*AggDemandFac`, AggFiscalModel.py:1215).

## The key structural question (Critique-1 dual-occurrence)

In HARK's CODE, ADF appears in TWO places: the budget/forward sim (`mNrm = bNrm +
TranShk*ADF`, line 1215) AND inside the backward expectation (`TranShkValsNext *=
AggDemandFacnext`, line 1785). That is because HARK codes the forward simulation and the
backward expectation SEPARATELY.

But in the dolo-plus PERCH structure there is a SINGLE `arvl_to_dcsn_transition`, and the
backward expectation in `dcsn_to_arvl_mover` integrates over next-period ARRIVAL values —
which are themselves built by that same `arvl_to_dcsn_transition` (applying ADF to the
next-period `theta` from the next-period `Cratio`/`z`). So I believe ONE occurrence of ADF
(in `arvl_to_dcsn_transition`) suffices, and it is correctly applied each period through
the recursive composition — NOT a missing second occurrence.

## Questions (label Q1..Q5 + VERDICT)

Q1. Confirm the external-Krusell-Smith pattern is right here: `Cratio` is a state, `CRule`
    a perceived-forecast PARAMETER, the consistency fixed point is solved OUTSIDE the YAML,
    and there is NO in-YAML `aggregate_consistency`/`forecast_rule` block. (We found no KB
    example of such a block — confirm or cite one.)

Q2. Confirm `Cratio_d` must be declared as a continuous STATE (alongside `m`), giving a 2D
    continuous `cFunc(m, Cratio)` per `z`. Confirm this is the right way to get the
    `(n_m, n_C, N_z)` policy, vs treating Cratio as a parameter.

Q3. Confirm `CRule` typed `real^(N_z, N_z, 2)` (slope+intercept per cell) is correct, and
    that typing it as a `[0,1]^(N_z,N_z)` probability/stochastic matrix would be WRONG
    (CRule is a deterministic forecast map, not a transition kernel). Give the exact
    `Cratio_next = ...` evolution line (level-linear vs log-linear — recommend one).

Q4. THE DUAL-OCCURRENCE QUESTION. In the dolo-plus recursive composition, does ADF need to
    appear EXPLICITLY in `dcsn_to_arvl_mover` (the expectation), or does a SINGLE occurrence
    in `arvl_to_dcsn_transition` correctly propagate to the expectation (because the
    expectation integrates next-period arrival values built by the same transition)? If a
    second explicit occurrence IS needed, show exactly where and why; if not, confirm one
    occurrence is correct and complete.

Q5. Should the Cratio fixed-point convergence criterion (15 iters, 1e-3, damped) live in a
    YAML `settings` block, or strictly out-of-YAML in the orchestrator? Recommend.

## Deliverable

Verbatim YAML fragments integrating Cratio/ADF:
  - `symbols`: `states.Cratio_d`, `prestate.Cratio_prev`, `parameters.CRule`
    (`real^(N_z,N_z,2)`), `parameters.kappa`, and the `Cratio` continuous space.
  - `arvl_to_dcsn_transition`: the ADF line and `y = theta * ADF` (replacing the earlier
    `y = theta` placeholder), plus `Cratio_d` passthrough.
  - the Cratio EVOLUTION (perceived-rule) line wherever it belongs (likely
    `dcsn_to_cntn_transition`: `Cratio_nxt[>] = CRule[...]`), and confirm whether ADF must
    also appear in `dcsn_to_arvl_mover` per Q4.

End with a VERDICT: Cratio-state (yes/no); CRule type (exact); ADF occurrence count and
locations; fixed-point in settings vs orchestrator.
