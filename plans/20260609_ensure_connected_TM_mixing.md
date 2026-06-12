# Ensure-connected TM: sufficient mixing between adjacent aNrm/mNrm grid cells

**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_ensure-connected-TM` (worktree).
**Status:** CLOSED 2026-06-10 — mission accomplished as a PROOF, not a fix: the production TM
(exp-mult 200, current calibration) is verified mixing/irreducible/upward-connected/forward-filling,
and the calibration is grid-converged at the β level (N=1600 re-estimation moved β <0.01% for HS/C).
No production numbers change. Merged deliverables: the a_next<0 hard guard in the TM-a kernel; the
mixing diagnostic + connectivity toolkit (point-mass criterion, min_aCount_for_mixing, fan-out
constructor, downward_cells_report); the default-on auto-repair safety net WITH user-facing warnings
(too-coarse aCount auto-repaired + warned; coarse custom grids warned, not modified); opt-in
HAFISCAL_TM_FANOUT_GRID (tail studies only — bulk-starved for calibration) and HAFISCAL_TM_ACOUNT.
Closed rabbit holes recorded in memory (project_tm_mixing_ensure_connected,
project_tm_ergodic_single_stationary_not_backward). Read alongside
`Code/HA-Models/tm_mixing_diagnostic.py`; historical sections below retain their in-place corrections.

> **Worst-case-shock criterion + joint-shock grid (2026-06-09, latest).**
> The downward-robustness criterion ("each node should reach ≥2 — ideally exactly 2 — distinct lower
> aNrm gridpoints") is evaluated on the actual joint shock atoms, not the ψ-marginal at mean θ. The two
> binding worst-case income realizations are region-dependent:
> - **Permanent channel (binds in the TAIL):** the two largest employed permanent shocks ψ_max, ψ_2
>   shrink *normalized* assets via the rising-permanent-income denominator.
> - **Benefit-cliff channel (binds in LOW WEALTH):** the two unemployment income levels — `IncUnemp`
>   (a UI-benefit spell, θ=0.70) and `IncUnempNoBenefits` (benefits exhausted, θ=0.50, the lowest
>   θ | unemployed) — each at ψ=1, with that state's own cFunc.
>
> **Two documented design choices (user asked to record both):**
> 1. *ψ-pairing.* (a) conservative bound = worst ψ × the unemployment incomes (a non-occurring combo,
>    since ψ≡1 during unemployment); (b) **actual realizations** = ψ atoms in the employed state, the
>    unemployment incomes at ψ=1. **Chose (b)** — the TM uses actual atoms; pairing ψ_max with
>    unemployment over-refines for a realization that cannot occur.
> 2. *Region of dominance.* (a) unemployment cliff governs throughout; (b) **two anchors by region** —
>    ψ governs the tail, the cliff governs low wealth. **Chose (b)**, via a single rule: step to the
>    second-deepest worst-case landing, so whichever channel gives the two deepest sub-node landings
>    sets the local spacing. (`make_worstcase_landings` + `make_fanout_grid_jointshock`.)
>
> **Empirical finding (the decisive one):** the joint-shock grid is fully robust (0 nodes with <2
> downward cells; production has 40) and accurate (E[a] 0.06% off the 705-node ref), but costs
> **aCount=464 vs the ψ-only fan-out's 131 — for no accuracy gain.** The landing trace shows why: the
> benefit cliff only becomes the *deepest* downward reach at **a ≲ 5**, i.e. deep in the
> low-wealth region — which is ALSO where the TM already mixes abundantly (employed↔unemployed Markov
> transitions + ξ are all live there). So the cliff binds the grid only where grid-resolution is least
> needed, and "step to second-deepest landing" over-refines low wealth (resolving coincidentally-close
> cross-channel landings) without buying accuracy. **The binding GRID constraint is the permanent
> channel in the TAIL** — exactly the ψ-only fan-out (`make_fanout_grid`, s=2, a_handoff=20 → aCount=131,
> 0 nodes <2 downward, E[a] 0.01% off ref). With any handoff ≳10, min-over-channels ≡ the ψ-only grid.
> **Implementation choice for production: the ψ-only fan-out (131 pts).** The joint-shock constructor is
> kept as the faithful full-robustness tool and the vehicle that PROVED the cliff is non-binding for the
> grid. (This vindicates the "region of dominance" caveat: the cliff is the right worst-case income, but
> it lives where mixing is abundant, so it does not size the grid.)

> **⚠️ CORRECTION 2026-06-09 (read first — supersedes the ½-criterion sections below).**
> The mixing criterion was over-strict by a factor ½. For irreducibility a ψ-operative TM row need only
> NOT be a point mass (≥1 atom in a different cell) ⇒ `Δlog(grid) < FULL log(ψ_max/ψ_min)` (no ½; the ½
> demanded two-sided per-node connectivity). Consequences:
> - The **production exp-mult grid already mixes** (0 point-mass rows; spectral gap 0.0116, never
>   near-reducible). `make_mixing_grid` at the corrected default `HAFISCAL_MIXING_SAFETY=1.0` adds **0
>   nodes**, so the default-on `HAFISCAL_TM_MIXING_GRID` wiring is a **byte-identical no-op**. The
>   "+27 nodes / +0.45% E[a] / −2.4% tail / calibration mismatch / QE-divergence" written below is
>   **RETRACTED** (ledger entry corrected; deferred re-estimation #11 retracted).
> - **Connectivity headroom:** production aCount=200 is only ~1.25× above the guarantee threshold
>   (aCount≈160; `min_aCount_for_mixing(safety)`), binding at m≈915 (deep tail).
> - **Fan-out-matched grid (user design, OPT-IN, validated, NOT adopted):** `make_fanout_grid` builds
>   aNrm top-down from aMax stepping 1/s of the worst-case ψ down-reach `a′_lo(a)` → every node has ≥s
>   accessible downward cells by construction; hands off to dense packing below `a_handoff`.
>   **s=2, a_handoff=20 → aCount=131, 0 nodes with <2 downward cells, E[a]=37.0036 (0.01% off a 705-node
>   ref) / q99.99=1075 (0.9% off)** — vs production (200, 25 nodes <2 downward, 0.60%/5.4% off). More
>   robust + more accurate at FEWER points. Faithful a-indexed check: `downward_cells_report`. Adopting
>   it as production IS a real Type-B convergence change (E[a] 36.786→37.004) → needs the ledger + a
>   matched re-estimation. **DECISION PENDING.** Commits: `7573b044` (constructor), corrected criterion.

## The idea, in one paragraph
The discretized transition matrix must *mix* — be irreducible / strongly connected on the grid — so
its computed ergodic is the unique, faithful approximation of the continuous model's stationary
distribution rather than a grid artifact. In the normalized recursion
`mNext = Rfree·aPol/(ψ·Γ) + ξ` (exactly tm_methods._build_period_tm), the **permanent shock ψ** is the
engine: mNext is strictly decreasing in ψ, so for a fixed source cell the spread of ψ fans next-period
resources across a band of nodes, connecting adjacent cells. If the grid is too coarse relative to that
fan-out, every ψ-realization lands on the *same* node (after the 2-point lottery) → that TM row is a
near-point-mass → the discretization loses the mixing the continuous problem has.

## Why it matters (math)
Ergodic = unit-eigenvalue left eigenvector of stochastic `P` (`πP=π`), via power iteration. Uniqueness
+ a well-posed limit require `P` **irreducible** (directed graph strongly connected) and aperiodic
(Perron–Frobenius). The shock fan-out supplies the off-diagonal edges; systematic collapse fragments
`P` into non-communicating classes → reducible → `π` non-unique / initial-condition-dependent / an
artifact. Short of reducibility, weak fan-out drives the spectral gap → 0 → `π` ill-conditioned and
hypersensitive to node placement.

## Two-level check (atoms are interior to [inf, sup])
- **(A) continuous (bounded):** inf/sup of the k·σ-truncated lognormal reach nodes **adjacent to, not
  identical to**, the median-ψ node → the true bounded model has local connectivity.
- **(B) discretized (BINDING):** min/max ψ *atoms* reach nodes **different from** the median atom →
  the *computed* TM mixes. (B) binds because the extreme atoms sit inside [inf, sup].
  (A) ok & (B) fails ⇒ shock discretization too coarse (**Alt 1**). (A) fails ⇒ grid too coarse (**Alt 3**).

## Methodization parameterization
Numerical-method params (not economics): **SIGMA_BOUND k** (truncation radius of ψ in σ-units — needed
to *define* inf/sup; tighter k = cleaner bounds, more discarded tail), the m-grid (aCount/aMax/aFac),
and the shock atom counts. Use this terminology throughout.

## Resolved clarifications
1. **Diagnostic is ψ-only, holding ξ at its mean.** ξ also fans mNext but *additively & a-independently*;
   ψ's fan-out is *multiplicative in aPol* (dominant in the high-wealth tail). The fan-out *width* is
   ξ-independent; ξ only shifts *where* it lands. (Open: optionally require it for every ξ atom, stricter.)
2. **"Adjacent" = contiguous neighbour** (the band around the median is contiguous, no skipped cells),
   not merely "somewhere else."
3. **HAFiscal: ψ fires only in the employed Markov state** (unemployment IncShkDstn atoms have ψ≡1), so
   the diagnostic is per-(Markov-state, node) on employed rows; unemployed rows mix via Markov
   transitions + ξ.
4. **Near the constraint ψ's fan-out → 0** (aPol→0), so no grid is fine enough — but ξ mixes there.
   Gate the ψ-remedies to the ψ-operative region (`aPol > APOL_CONSTRAINT_TOL`).

## Remedies if the condition fails (the design)
- **Alt 1 — add ψ atoms** (turn the *other* knob). Raising N_ψ pushes the extreme atoms toward the
  bounds, widening the discretized fan-out **without** growing the N×N matrix. Fix for "(A) ok, (B) fails."
- **Alt 2 — variance-preserving assignment.** HARK's `jump_to_grid_1D` is a *mean*-preserving 2-point
  lottery; collapse loses the *across-atom variance*. A 2-moment-matched stencil reproduces the fan-out's
  mean **and** variance → guaranteed off-diagonal mass, no grid growth, no spurious diffusion beyond the
  true 2nd moment. Cost: non-local stencil; guard against negative weights. Held in reserve for stubborn
  local collapses.
- **Alt 3 — DEFAULT REPAIR: design the grid, don't patch it.** Closed form: in the ψ-dominated region
  `log(mNext)` shifts by `−log ψ`, so the fan-out's log-width is `log(ψ_max/ψ_min)` (= `2kσ` continuous).
  ⇒ on a log grid the requirement is simply
  `Δ_log(grid) < log(ψ_max/ψ_min)` (discretized, binding) ≤ `2kσ` (continuous).
  Build the m-grid to satisfy this everywhere (keep the exp/constraint region; tighten the tail).
- **Fallback — ε-regularize** `P̃=(1−ε)P+εM` (teleportation). Guarantees irreducibility/aperiodicity but
  injects non-model diffusion and only fixes connectivity, not the under-represented spread. Last resort
  to keep the power iteration well-posed — not a substitute for Alts 1–3.
- **User's local refinement** (bisect between the last-pass and first-fail node) works for *localized*
  violations but (i) a single insertion can't cure a *global* one (on a log grid Δm and Δgrid both ∝ a, so
  failures tend to be near-uniform), and (ii) it can fail to terminate where Δm→0 near the constraint.

## What's built + the finding (`cc883243`)
`Code/HA-Models/tm_mixing_diagnostic.py`: per-(state, node) ψ fan-out check (continuous + discretized),
aPol-gated (constraint vs ψ-operative), + the Alt-3 log-spacing criterion. Run:
```
cd Code/HA-Models
/home/shared/github/llorracc/HAFiscal-Latest/.venv/bin/python \
  HAFISCAL_INTERPRETATION=ESC HAFISCAL_TM_AMAX=1300 python tm_mixing_diagnostic.py
```
(the worktree has no venv of its own — use the main repo's `.venv/bin/python` by absolute path, or `make sync`.)

**Finding (production college grid, aCount=200, aMax=1300, aFac=3, PermShkStd=0.0548):** mixing holds in
the bulk, **but the exp grid's TOP is too coarse** — max log-spacing 0.70 vs shock log-range 0.173 (disc)
/ 0.329 (cont). **27/130 ψ-operative nodes fail (B), 7 fail even (A)**, all in the high-m saving region up
to m=1300 — the **patient-atom fat tail (the BUG-053 region)**. Constraint-region collapses (70, low m)
are correctly separated as ξ-handled.

## What's built + finding — UPDATE (2026-06-09, session 2): Alt-3 constructor + end-to-end validation
**Alt-3 grid constructor (`tm_mixing_diagnostic.make_mixing_grid`)** — keeps the production exp-mult
grid in the constraint/bulk region and geometrically subdivides any tail interval whose log-spacing
exceeds the target. **Criterion: `Δ_log(grid) < 0.5 · log(ψ_max/ψ_min)`** — the factor ½ (not the
docstring's literal full-range) is required because the fan-out is two-sided about the median, so the
per-side displacement (median→extreme) is HALF the full log-range and the grid must resolve EACH side.
Empirical breakpoint: 0 collapses for safety ≤ 0.6, fails (6/9/14) for 0.7/0.75/0.85. Default
`safety=0.5` (env `HAFISCAL_MIXING_SAFETY`) gives 0 with margin at **+27 nodes (227 vs 200)**.

**Two diagnostic fixes that were masking the success (both committed):**
1. **Gate was wrong, not the grid.** `APOL_CONSTRAINT_TOL=0.05` admitted near-constraint nodes (aPol
   0.1–0.5) where psi is NOT the operative mixer. The principled gate is the additive↔multiplicative
   crossover of `mNext = R·aPol/(G·psi) + xi`: psi only moves mNext multiplicatively once `R·aPol/G ≳ xi`,
   i.e. **`aPol > xi·G/R`** (≈0.995 here) — a structural property of the recursion, grid-independent.
2. **Top-boundary HI-truncation excused.** A HI-side collapse where the median already sits in the top
   cell (`cm==M-2`) is not a failure — there is no grid above aMax for the upward fan-out; the node
   still mixes DOWN, and aMax is the (1-1e-4) tail cutoff so it carries ~0 mass (one-sided connectivity
   preserves irreducibility). Symmetric excusal at the bottom cell.
With both fixes the Alt-3 grid drives saving-region collapses (A and B) to **0**; the production grid
still has 14.

**End-to-end validation (`validate_mixing_ergodic.py`, college GIC-cap atom, the fattest tail):**
the mixing fix is BOTH a correctness guarantee AND a real, directionally-correct tail refinement —
not a fix for a broken/reducible chain.
- Spectral gap is **0.0116 (production) / 0.0110 (mixing)** — both ≫ 0, so neither grid is
  near-reducible. The local tail collapses do NOT shrink the global gap because they sit in the
  low-mass tail and the bulk supplies abundant connectivity. (The "27/130 fail (B)" headline
  overstates practical severity at aCount=200/aMax=1300.)
- Ergodic moves measurably and in the right direction: **E[a] +0.45%, q99.99 −2.4%, edge-mass halved
  (9.7e-5→4.2e-5), required aMax 1123→1096**. Against a 705-node reference, the mixing grid is
  **4× closer on E[a] (0.60%→0.15%) and ~2× closer on q99.99 (5.5%→2.9%)** — confirming refinement
  toward the converged truth, not a different artifact. Ties directly to BUG-053 (aMax/fat-tail sizing).

**Answer to open question #1:** the fix is mainly a correctness guarantee + a modest (~2.4%) tail/aMax
refinement; the production ergodic was already well-mixed in aggregate (gap not near 0).

## Production wiring — LANDED default-on (open Q #3 resolved by user, 2026-06-09)
User chose **"wire it in as default."** `build_tm_agg_fiscal_a` now refines its AUTO-built grid via
`refine_grid_for_mixing` (default-on; toggle off with `HAFISCAL_TM_MIXING_GRID=0`; a custom
`dist_aGrid=` is left untouched). Target = `mixing_logspacing_target(IncShkDstn_list)` =
`HAFISCAL_MIXING_SAFETY(0.5) · log(ψ_max/ψ_min)`. Single-source: `make_mixing_grid` (diagnostic) and the
production path both call `refine_grid_for_mixing`.
- **Governance:** logged as a Type-B CONVERGENCE entry in the QE-divergence ledger
  (`conclusions_private/2026-05-03_HAFiscal-QE-vs-current-comparison.md`, last section), NOT a BUG.
- **Regression-clean:** no NEW failures vs mixing-off in `test_tm_a_indexed.py` (pre-existing stale
  fixture) or `test_saved_calibration_self_consistent.py` (HS+C pass <5%; D-0 XPASS pre-existing).
- **Open matched-pair follow-up:** saved (β,∇) were estimated on the non-mixing grid → ~0.45%-E[a]
  calibration↔grid mismatch (within 5% self-consistency). Re-estimate on the mixing grid at the NEXT
  discount-factor estimation (opt-in per `feedback_no_default_reestimation`; not triggered here).

## Remaining next steps (priority order)
1. **Alt-1 hook** — bump N_ψ where (B) fails but (A) holds. NOT built (Alt-3 covers every observed
   failure; build only if a future agent/grid lands in the "(A) ok, (B) fails" branch).
2. **Welfare-6 spot-check** under mixing-on: confirm the welfare cells move <0.5% (expected — welfare
   weights by c_base², concentrated below the affected tail). Only if welfare-6 is re-run.
3. Alt-2 (variance-preserving stencil) and the ε-fallback only if a STUBBORN local collapse appears that
   refinement can't cure (none seen so far).
4. ξ treatment (open Q #2): mean-only (current) vs per-ξ-atom (stricter) — only if a reviewer wants the
   stricter guarantee; the per-(state,node) psi check + xi-handled gating already covers the mechanism.

## Open questions for the user
- Does the (small) tail mass warrant the fix, or is the finding mainly a correctness guarantee?
- ξ treatment: mean-only (current) vs per-ξ-atom (stricter)?
- Should Alt-3 co-drive the production grid (`adaptive_grid_tm.production_aMax`) — i.e. the grid should
  satisfy BOTH the (1-1e-4) tail-coverage criterion AND the mixing log-spacing criterion?
