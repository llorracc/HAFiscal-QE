Continuing the HAFiscal dolo-plus YAML (ESC bound-pair optimizer stage, confirmed last
turn as a pure canonical buffer-stock). This turn settles the PERMANENT-INCOME
NORMALIZATION — the `Γ̂^(1-γ)` factor and the marginal-value form. Prose welcome.

## Context recap (already settled)

- Stage = the Optimizer sub-household's standard CRRA buffer-stock, Markov state `z`,
  single control `c_opt`, asset rule `a = m - c_opt`, effective discount `β·LivPrb`,
  normalized by `p_opt` (so the transitory shock symbol `theta` = ξ_tot). No splurge.
- Realized permanent-income growth: `Γ̂ = ψ·Γ_e` (here `G = PermGroFac·psi`).
- Next-period normalized resources: `m' = (R/Γ̂)·a + ŷ(z', θ')` (spec §7.2 line 197).
- The HAFiscal spec §7.2 (lines 185-189) puts the factor INSIDE the expectation on the
  value: `J_t[v^arr](a,z) = E[Γ̂^(1-γ) · v^arr(m', z')]`. Euler (spec §7.4 line 247):
  `c_opt^(-γ) = β(1-D)·R·E[Γ̂^(-γ)·c_opt'^(-γ)]`.

## Two canonical DDSL exemplars disagree — please adjudicate

`ConsIndShock_stage.yaml` (lines 71-74) writes the factor EXPLICITLY on the value:
    dcsn_to_arvl_mover:
      Bellman:       V[<]  = E_{PermShk,TranShk}[ G^(1-rho) * V ]
      ShadowBellman: dV[<] = Rfree * E_{PermShk,TranShk}[ G^(-rho) * dV ]
with `G = PermGroFac * PermShk` and `b = Rfree * k / G` in arvl_to_dcsn_transition.

`ConsMarkov_stage.yaml` (lines 84-86) OMITS the `G^(1-rho)` on the value:
      Bellman:       V[<]  = E_{z,psi,theta}[ V ]                # no G^(1-rho) !
      ShadowBellman: dV[<] = E_{z,psi,theta}[ Rfree[z] * G^(-rho) * dV ]

For HAFiscal the spec demands the EXPLICIT `Γ̂^(1-γ)` on the value (ConsIndShock form).

## Questions (label Q1..Q4 + VERDICT)

Q1. Confirm the HAFiscal value connector must be `V[<] = E_{z,psi,theta}[ G^(1-rho) * V ]`
    — i.e. the ConsIndShock form, with `Γ̂^(1-γ)` INSIDE the expectation. Is the
    `ConsMarkov_stage.yaml` omission an error/abbreviation, or a legitimate alternative
    convention (e.g. value pre-scaled elsewhere)? Which should we adopt and why?

Q2. Confirm the marginal-value (ShadowBellman) form
    `dV[<] = Rfree * E_{z,psi,theta}[ G^(-rho) * dV ]` is canonical and reproduces the
    spec §7.4 Euler when combined with `dV = c^(-rho)` and the InvEuler
    `c = (β·LivPrb·dV[>])^(-1/rho)`.

Q3. In HAFiscal, permanent-income growth `Γ_e` is EDUCATION/COHORT-specific and does NOT
    depend on the labor-market Markov state `z` (one calibration file per cohort). So
    `PermGroFac` should be a SCALAR parameter, not a `z`-indexed vector
    (`PermGroFac[z_d]`). Likewise `Rfree` is a scalar `R`. Confirm scalar typing is correct
    and that `G = PermGroFac * psi` (no `[z_d]` subscript) is right here.

Q4. Is `RNrmByG` (or `R/G`) a recognized dolo-plus symbol/name, or purely documentation?
    Should the YAML write `b = Rfree * k / G` inline (ConsIndShock style) or introduce a
    named `RNrmByG = Rfree/G`?

## Deliverable

Verbatim YAML fragments (ConsIndShock/ConsMarkov style) for:
  - `arvl_to_dcsn_transition` (defining `G`, `p`, `b`, `y`, `m`; use scalar Rfree/PermGroFac;
    leave income as `y = theta` for now — the AD factor on income comes in a later turn),
  - `dcsn_to_arvl_mover` (`Bellman` with `G^(1-rho)` inside E, and `ShadowBellman`).
End with a VERDICT: the exact value- and marginal-value lines HAFiscal should use, and
the scalar-vs-vector `PermGroFac` call.
