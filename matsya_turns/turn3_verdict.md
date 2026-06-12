# Turn 3 verdict — Γ̂^(1-γ) normalization & marginal-value form

| # | Reviewer | Verdict | Reason |
|---|----------|---------|--------|
| 1 | Value-factor inside E | PASS | matsya confirms (and derives) `V[<] = E[G^(1-rho)*V]` — Γ̂^(1-γ) inside the expectation; matches spec §7.2 line 185 and `ConsIndShock_stage.yaml:72`. ConsMarkov's omission = transcription error (internally inconsistent vs its own `G^(-rho)` on dV). |
| 2 | Euler reproduction | PASS | matsya derives `dV[<] = Rfree*E[G^(-rho)*dV]` via envelope; with `dV=c^(-rho)` + InvEuler reproduces spec §7.4 line 247 Euler `c^-γ = β(1-D)R·E[Γ̂^-γ c'^-γ]`. Under ESC the Euler is exact (no splurge). |
| 3 | PermGroFac scalar vs z-indexed | **FAIL → CORRECTED** | matsya answered SCALAR, valid only for `unemp_pLvl_grows_like_employed=True`. But the QE-published default is `HAFISCAL_PLVL_GROWS_DURING_UNEMP=off` (`Parameters.py:525` builds PermGroFac via `build_PermGroFac_micro(..., PermGroFac_unemp)`; `diag_d14_qe_comparison.py:101` confirms off=QE conv). Paper-faithful encoding is **z-indexed `PermGroFac[z_d]`**. My prompt fed matsya the wrong premise. CORRECTED in fragment. |
| 4 | RNrmByG naming | PASS | Not a DDSL symbol; inline `b = Rfree * k / G` (ConsIndShock style). |

HALT criteria (Turn 3): "Γ̂^(1-γ) missing from expectation" / "Euler disagrees with §7.4" —
NEITHER triggered. The PermGroFac scalar/vector issue is not a Turn-3 HALT criterion and
is authoritatively resolved from source code (z-indexed), so we proceed with the
correction recorded rather than halting.

OPEN for user (see matsya_turns/OPEN_QUESTIONS.md #1): confirm we want the QE-published
default (PLVL_GROWS_DURING_UNEMP=off → z-indexed PermGroFac). One-line switch to scalar
if Harmenberg-compatible (grows=on) is preferred instead.

NOTE: the matsya session now holds the wrong scalar premise from my Q3. Turn 7 assembly
will explicitly specify z-indexed `PermGroFac[z_d]`, overriding it.

RESULT: value/marginal/Euler PASS; PermGroFac corrected to z-indexed → proceed to Turn 4.
