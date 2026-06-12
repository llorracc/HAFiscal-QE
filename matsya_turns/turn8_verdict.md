# Turn 8 verdict — numerical validation (UPDATED: +recession point, +HARK cross-check)

Script: Code/HA-Models/dolo_plus_validation/test_euler_at_point.py
Report: Code/HA-Models/dolo_plus_validation/validation_report.txt

OVERALL: **PASS** — two independent solvers, two test points (normal + recession).

| test point | ADF | c_opt(5,0) EGM | HARK | |diff|/HARK | Euler resid |
|---|---|---|---|---|---|
| normal   (z=0, Cratio=1.0)        | 1.00000 | 1.290102 | 1.289991 | 8.65e-5 | 1.169e-4 |
| recession(z=0, Cratio=0.9, k=0.3) | 0.96889 | 1.259038 | 1.258911 | 1.01e-4 | 7.96e-5  |

Two independent solvers:
  (A) From-scratch textbook EGM -> evaluates the YAML's STATED Euler residual (<1e-3 both).
  (B) HARK's own low-level solve_one_period_ConsMarkov, driven with explicit 6-state inputs
      (bypasses the 0.17 constructor wrapper that resets MrkvArray/Rfree — same reason
      HAFiscal overrides pre_solve). Independent-codebase cross-check of c_opt(5,0).
EGM and HARK agree to <1.1e-4 at both points (same shock nodes, different algorithms).

What this validates:
  - Core ESC buffer-stock: Gamma_hat normalization, beta*LivPrb, m'=R*a/Ghat+theta*ADF,
    a=m-c_opt. A transcription error (wrong G exponent, missing factor, splurge-in-budget)
    would break both the Euler residual and the EGM-vs-HARK agreement.
  - ADF coupling (Turn 6, was previously untested): the recession point with ADF=0.969<1
    drops c(5,0) 1.290->1.259, passes both the Euler and the HARK cross-check. This
    NUMERICALLY confirms the single-occurrence ADF encoding (OPEN_QUESTIONS #4) is correct.

RESOLVED: OPEN_QUESTIONS #4 (ADF once) and #6 (HARK cross-check) — both now numerically
validated. Remaining open items are confirmations (#1 z-indexed, #5 level-linear) the user
has approved, plus #2 (KB-indexing FYI) and #3 (gate, moot).
