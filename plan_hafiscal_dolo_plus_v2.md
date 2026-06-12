# Plan: HAFiscal → Dolo-Plus YAML via Matsya (workflow-orchestrated, max-effort)
# Generated: 2026-06-03

## Goal

Produce a clean, parseable, HAFiscal-faithful dolo-plus YAML encoding the household-side Bellman problem of `HAFiscal-bellman-for-matsya.md` — using Matsya (the Bellman-DDSL RAG/CLI tool at https://matsya.bright-forest.com) as a DDSL-expert. The deliverable is `/home/shared/github/llorracc/HAFiscal-Latest/HAFiscal-doloplus-draft.yaml`, structurally aligned with the canonical `ConsMarkov_stage.yaml` exemplar from the bellman-ddsl knowledge base, with all dolo-plus extension requests (places where HAFiscal goes beyond the canonical grammar) flagged explicitly in-file rather than silently encoded.

This plan is **substantively different from `plan_hafiscal_dolo_plus_via_matsya.md`** (the assignment-template recipe). It is grounded in the seven-feature HAFiscal-to-DDSL mapping produced in the prior turn, uses workflow-orchestrated adversarial review around each matsya interaction, and treats numerical round-trip — not literary round-trip — as the final validation gate. The prior plan trusted matsya as a primary source; this plan treats matsya as a single (fallible) expert whose answers are cross-checked against canonical DDSL examples, against HARK code at the line level, and against numerical evaluation of the Euler equation.

## Inputs

| Asset | Path |
|---|---|
| Bellman spec | `/home/shared/github/llorracc/HAFiscal-Latest/HAFiscal-bellman-for-matsya.md` (328 lines) |
| Prior matsya YAML draft | `/home/shared/github/llorracc/HAFiscal-Latest/HAFiscal-doloplus-from-matsya.yaml` (lines 40-295 YAML, 313-342 unresolved notes) |
| Prior plan (assignment template) | `/home/shared/github/llorracc/HAFiscal-Latest/plan_hafiscal_dolo_plus_via_matsya.md` |
| Model paper | `/home/shared/github/llorracc/HAFiscal-Latest/Subfiles/Model.tex` (eq. `eq:income`, `eq:perm_income`, eq. (7) `eq:ad_feedback`) |
| HARK 0.17.x solver | `/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/AggFiscalModel.py` (lines 1704-1887 solver, 1185-1395 budget/splurge, 1922-1928 ADFunc, 2418-2517 AD outer loop) |
| Calibration | `/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/Parameters.py` (lines 45-49 AD/recession, 278-312 grids, 353-434 hierarchical Markov, 644-740 economy init) and `EstimParameters.py` (lines 200-208 micro-state count, 260-262 PermGroFac per education, 340 LivPrb) |
| Welfare driver | `/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/FromPandemicCode/welfare6_scenario.py` (lines 578-654 duration weights) |
| Canonical DDSL examples | `/home/shared/github/bright-forest/bellman-ddsl/docs/examples/HARK-models-lean-experimental/ConsMarkov_stage.yaml`, `ConsIndShock_stage.yaml`, `ConsPerfForesight_stage.yaml`, and `docs/examples/buffer_stock.md` |
| Matsya session | `SESSION = "HAFiscal-Latest"` (no `group=`; falls back to default Bellman-DDSL KB) |

The matsya CLI is invoked as:
```
matsya ask "<prompt>" --session HAFiscal-Latest --files HAFiscal-bellman-for-matsya.md
```
For follow-up turns within a session, omit `--files` (history persists). Authentication via `MATSYA_TOKEN` env var or `matsya configure`.

## HAFiscal → DDSL mapping (the analytic core)

This table is the authoritative mapping derived in the prior turn. Each row drives one or more matsya prompts.

| # | HAFiscal feature | Code site | DDSL status | YAML location |
|---|---|---|---|---|
| (a) | Joint Markov state `Mrkv = J·MacroMrkv + MicroMrkv`, J=6 (bug_fix) or 4 (legacy), M ∈ {1,22,42}, RecState gates AD | `Parameters.py:353-434`, `AggFiscalModel.py:551-552` | CANONICAL with FLATTENING (one flat Z of cardinality J·M; per-RAG-KB-3-Q4 two-Markov-chains is UNRESOLVED) | `symbols.spaces.Z`, `arvl_to_dcsn_transition` (derived MicroMrkv/MacroMrkv/RecState) |
| (b) | State-contingent income `y_check(z,ξ) = {ξ if E; ρ_b if UI; ρ_nb if exhaustee}`, `IncShkDstn[z]` | `AggFiscalModel.py:766-830`, `Parameters.py:644-740` | CANONICAL via `IncShkDstn[z].marginal(k)` (matches `ConsMarkov_stage.yaml:20-25`). Dirac point-masses in UI/exhaustee slots are an **open question**. | `exogenous`, `arvl_to_dcsn_transition` |
| (c) | Splurge `c_sp = ς · pLvl · TranShk · ADF` (CDC interpretation, default); not a control, not in utility, in budget only | `AggFiscalModel.py:1393` (`cLvl_splurge`), `:159-178` (`_cdc_asset_rule`) | **NEEDS DDSL EXTENSION** — no canonical example. Encoding A (inline `c_sp` in `dcsn_to_cntn_transition` with `# NOT_OPTIMIZED` annotation) is the v1 workaround. | `dcsn_to_cntn_transition`, `cntn_to_dcsn_transition` (EGM reverse) |
| (d) | Permanent-income normalization, `Γ̂^(1-γ)` factor INSIDE expectation, `b = R·k/G` normalization | Carroll-style throughout solver | CANONICAL (matches `ConsIndShock_stage.yaml:72` exactly: `V[<] = E[G^(1-γ)*V]`, `dV[<] = R·E[G^(-γ)*dV]`) | `arvl_to_dcsn_transition`, `dcsn_to_arvl_mover` |
| (e) | Perpetual youth: `β · LivPrb` discount; T_age=200 forced death + newborn-pool re-injection out-of-YAML | `EstimParameters.py:340` (LivPrb_base), `Parameters.py:285` (T_age), `AggFiscalModel.py:1857` | CANONICAL on discount side. T_age + newborn-injection mass-balance are **OUT-OF-SCOPE** for the YAML (handled by simulation orchestrator). | `cntn_to_dcsn_mover.Bellman`, plus `# NOTE [OUT-OF-SCOPE]` preamble |
| (f) | AD coupling: `ADF = Cratio^(RecState·κ)`, κ=0.3; Cratio is 2nd continuous state on `cFunc[z](m,Cratio)`; AD enters BOTH budget AND expectation; outer Cratio fixed point | `AggFiscalModel.py:1215, 1393, 1785, 1922-1928, 2418-2517` | PE-CONDITIONAL household with EXTERNAL aggregate-consistency loop (per RAG-KB-3-Q5: GE consistency has no canonical dolo-plus encoding). Cratio is canonically a state; CRule is a parameter. Outer loop is Krusell-Smith-style around `solve`. | `symbols.states.Cratio_d`, `symbols.parameters.CRule`, `arvl_to_dcsn_transition` (ADF in budget), `dcsn_to_arvl_mover` (ADF in expectation) |
| (g) | 21-cohort sweep (3 educ × 7 β atoms) | `EstimParameters.py:200-208`, `Parameters.py:339-351` | CANONICAL via PARAMETERIZATION — one YAML stage, 21 calibration files, parallel orchestration (matches CLAUDE.md `--solve-workers 21`) | `parameters` (β, EducType, PermGroFac, Urate_normal, p-dist) |
| (h) | Policy variations: Check (one-shot TranShk add-on), TaxCut (8q multiplicative on employed TranShk), UI extension (J=6 structural) | `AggFiscalModel.py:749-761`, `Parameters.py:410-429` | MIXED. Bake J=6 always; vary calibration only. UI extension expressed via `IncShkDstn` slots for u3Q/u4Q under recession-macro. Check's t=0 one-shot is an **open question** (transient macro state vs orchestrator init). | One YAML, four calibration files (no-policy / Check / UI / TaxCut) |

## Architectural decisions

Three structural choices are forced by the mapping and locked in before any matsya turn:

1. **Single-stage YAML.** One stage `hafiscal_household` modeled directly on `ConsMarkov_stage.yaml`. Rejected: multi-stage decomposition with a "splurge drain" prior stage (since splurge depends on realized ξ, not on m, the prior-stage drain would conflate income-based splurge with wealth-based splurge — flagged in Critique 1 / feature (c)).

2. **One cohort per calibration file.** The 21-cohort (β × education) sweep lives in the Python orchestrator, matching the existing `parallel_solve.parallel_eco_solve()` pattern. Cohort-level parameters (β, EducType, PermGroFac, Urate_normal, pLogInitMean, pLogInitStd) appear as scalar `parameters` in the YAML; the orchestrator emits 21 calibration files.

3. **PE-conditional household with external AD fixed point.** The YAML stage takes `Cratio_d` as a continuous state and `CRule` as a parameter (perceived forecast rule). The outer Cratio fixed-point iteration (max 15 iters, 1e-3 tol, damped at stepsize ≤ 1.0) lives in the Python orchestrator, exactly mirroring `solve_ad_recession` at `AggFiscalModel.py:2418-2517`.

Four items are explicitly **OUT-OF-SCOPE** for the YAML and documented in a `# NOTE [OUT-OF-SCOPE]` block at the file head: T_age=200 forced death, newborn-pool re-injection, AD outer loop, 21-cohort aggregation. Policy switching (Check/UI/TaxCut) is **IN-SCOPE** via per-policy calibration files sharing the same YAML schema.

## Step-by-step execution

Each step lists: purpose, pre-matsya workflow agents (if any), the literal matsya CLI invocation, expected response shape, post-matsya parallel reviewers (the post-critique dimensions), halt criterion, and output artifact.

### Step 0 — Pre-flight (no matsya)

Pre-flight checks before any matsya interaction:
- Verify `matsya` CLI is on PATH; `MATSYA_TOKEN` is configured.
- Verify `yq` (YAML linter) is installed for downstream parse checks.
- Verify the canonical examples are present at `/home/shared/github/bright-forest/bellman-ddsl/docs/examples/HARK-models-lean-experimental/{ConsMarkov_stage.yaml,ConsIndShock_stage.yaml,ConsPerfForesight_stage.yaml}` and `docs/examples/buffer_stock.md`.
- Resume the existing matsya session `HAFiscal-Latest` or create it.

Workflow pattern: none (sequential, single-shot bash checks).

### Step 1 — Architecture confirmation (matsya turn 1)

**Purpose.** Lock in single-stage vs multi-stage, the four explicit out-of-scope delegations, and matsya's KB-references for the chosen architecture. This is the foundational turn — every subsequent step depends on the answers.

**Pre-matsya workflow.** Spawn two **parallel reader subagents** that produce concise digests (one of `HAFiscal-bellman-for-matsya.md` §§1-7, one of `ConsMarkov_stage.yaml` lines 1-100) and surface to the operator the exact ConsMarkov scaffold matsya is being asked to mirror. This guards against matsya silently reframing the scope.

**Matsya invocation.**
```
matsya ask --session HAFiscal-Latest --files HAFiscal-bellman-for-matsya.md "$(cat <<'PROMPT'
I have HAFiscal-bellman-for-matsya.md loaded. I want a CLEAN dolo-plus YAML (not the
prose-wrapped draft from the earlier session turn). Before producing it, settle
architecture: SINGLE-STAGE vs MULTI-STAGE.

My proposal: a SINGLE stage `hafiscal_household` modeled exactly on canonical
`ConsMarkov_stage.yaml`, with the four standard perch movers
(arvl_to_dcsn_transition, dcsn_to_cntn_transition, cntn_to_dcsn_mover,
dcsn_to_arvl_mover). One stage carries: continuous state m_check; flattened joint
Markov state z (cardinality N_z = J*M, where J=6 micro states under bug_fix
encoding and M ∈ {1, 22, 42} macro states); single control c_opt; two shocks (psi,
theta=xi); CRRA reward over c_opt only; the Gamma_hat^(1-gamma) factor inside the
expectation in dcsn_to_arvl_mover.

DELIBERATELY OUT OF YAML, into the Python orchestrator: (i) AD aggregate-consistency
fixed point (CFunc iteration over Cratio_t -> Cratio_{t+1}); (ii) 21-cohort beta*edu
sweep (each cohort = one calibration file); (iii) T_age=200 forced death and
newborn-pool re-injection; (iv) policy-experiment driver (Check / UI / TaxCut = three
calibration files of the same YAML).

Questions (do NOT produce YAML yet):

Q1. Is single-stage canonical for HAFiscal in dolo-plus, or does the splurge mechanic
(c_sp = varsigma*y_check that affects budget but not utility) force a two-stage
decomposition? Cite the closest example in your KB.

Q2. Is pushing the AD outer loop entirely OUT of the YAML the canonical
Krusell-Smith-style pattern, or does dolo-plus have a top-level
`aggregate_consistency` / `forecast_rule` block?

Q3. Is pushing the 21-cohort sweep OUT of the YAML the canonical pattern, or does
dolo-plus support a `population` block for heterogeneous-agent type composition?

For each Q give ONE ranked recommendation (PREFERRED) and ONE alternative (FALLBACK),
plus the closest KB filepath. Answer in this exact structure:
```
Q1: <PREFERRED / FALLBACK / KB-reference>
Q2: <PREFERRED / FALLBACK / KB-reference>
Q3: <PREFERRED / FALLBACK / KB-reference>
Net architecture: <one paragraph stating the agreed YAML scope>
```
PROMPT
)" > /home/shared/github/llorracc/HAFiscal-Latest/matsya_turns/turn1_architecture.md
```

**Expected response shape.** Three labeled answers Q1-Q3 with PREFERRED/FALLBACK/KB-reference, followed by a Net-architecture paragraph. KB-references should be filepaths matsya can cite (e.g. `ConsMarkov_stage.yaml`, `buffer_stock.md`).

**Post-matsya parallel reviewers (verdict subagents, run concurrently).**
1. *KB-citation verifier* — grep `/home/shared/github/bright-forest/bellman-ddsl/` for each filepath matsya cites; flag hallucinated filenames.
2. *Scope-consistency reviewer* — diff matsya's "Net architecture" paragraph against the locked Architectural Decisions above; flag drift.
3. *HARK-implementation cross-checker* — confirm Q2's AD-out-of-YAML answer is consistent with `AggFiscalModel.py:2418-2517` and `welfare6_scenario.solve_ad_recession`.
4. *CLAUDE.md cohort-pattern reviewer* — confirm Q3's 21-cohort answer is consistent with CLAUDE.md "Cohort-parallel HARK solves" section.

These four reviewers produce a single short verdict each (PASS / FAIL with one-line reason). All four PASS → proceed.

**Halt criterion.** HALT if: (i) matsya cannot identify a canonical example for Q1 (splurge inside a single stage) AND falls back to "no canonical pattern, must extend DDSL" — this is a spec-level gap requiring upstream escalation to econ-ark/Matsya before continuing; (ii) any KB-citation is hallucinated; (iii) net architecture diverges materially from the locked scope (e.g. matsya insists on multi-stage and explicitly rejects single-stage).

**Output artifact.** `matsya_turns/turn1_architecture.md` (raw response) and `matsya_turns/turn1_verdict.md` (4 reviewer verdicts).

### Step 2 — Splurge encoding (matsya turn 2)

**Purpose.** Settle the v1 encoding of the non-optimized mechanical consumption flow `c_sp = ς·ξ·ADF`. Mapping confidence is LOW; the prior matsya draft (lines 313-325) flagged this as the "single most structurally awkward" feature. Critique 1 identified a subtle correctness bug: any inline encoding must include the ADF factor (the splurge realized consumption is `ς·pLvl·TranShk·ADF`, not `ς·pLvl·TranShk`).

**Pre-matsya workflow.** Two parallel reader subagents: one extracts the exact splurge formula from `AggFiscalModel.py:1393` and the CDC asset rule from `:159-178`; one extracts §6 (splurge mechanic, Version A) from `HAFiscal-bellman-for-matsya.md`. The operator pastes the resulting two snippets into the prompt to give matsya source-of-truth context.

**Matsya invocation.** Prompt body details the encoding-A/B/C trichotomy from the mapping; includes the realized-consumption formula with ADF factor explicit; asks Q1 (which encoding), Q2 (does absence-from-Bellman-max suffice as "not a control"?), Q3 (is the EGM reverse `m_d[>] = a + ς·θ·ADF + c_opt[>]` syntactically valid?), Q4 (closest KB example). Required structure of response: explicit single-letter Q1 verdict, plus a verbatim YAML fragment for `dcsn_to_cntn_transition` and `cntn_to_dcsn_transition`.

**Concrete mitigation from Critique 3.** Add a turn 2.5 that drafts an explicit DDSL extension proposal (a `mechanical_flows:` block specification) as a *parallel deliverable*, regardless of matsya's turn-2 answer. The proposal goes into `matsya_turns/ddsl_extension_proposal_mechanical_flows.md` and gets referenced in a header comment of the final YAML ("pending DDSL extension; see ddsl_extension_proposal_mechanical_flows.md").

**Post-matsya parallel reviewers.**
1. *Envelope-theorem checker* — verify ∂c_sp/∂m_d = 0 is preserved in the proposed encoding (c_sp depends on z and ξ, NOT on m).
2. *ADF-factor verifier* — grep the proposed YAML fragment for `ADF` or its inline expansion; FAIL if ADF is missing from either the forward or reverse transition (this catches the Critique-1 bug).
3. *Code-cross-reference reviewer* — match the proposed splurge formula against `AggFiscalModel.py:1393` `cLvl_splurge = (1-ς)*cLvl + ς*pLvl*TranShk*AggDemandFac`.
4. *Version-A-preservation reviewer* — confirm matsya did not silently switch from Version A (splurge in budget) to Version B (splurge in utility).

**Halt criterion.** HALT if matsya recommends ENCODING C as the *only* path forward (cannot produce clean YAML today). HALT if Q3 reveals `theta` must be renamed in a way that breaks forward/reverse consistency. HALT if ADF-factor verifier FAILS (matsya silently dropped the ADF coupling in the splurge term).

**Output artifact.** `matsya_turns/turn2_splurge.md` (raw response), `matsya_turns/turn2_yaml_fragment.yaml` (extracted YAML snippet), `matsya_turns/turn2_verdict.md` (4 reviewer verdicts), `matsya_turns/ddsl_extension_proposal_mechanical_flows.md` (extension request draft).

### Step 3 — Γ̂^(1-γ) normalization (matsya turn 3)

**Purpose.** Confirm the Carroll-style permanent-income normalization. Mapping confidence is HIGH (matches `ConsIndShock_stage.yaml:72` directly), but the prior matsya draft flagged this PROVISIONAL (line 331), so explicit re-confirmation is needed.

**Pre-matsya workflow.** None new — the locked Bellman in `HAFiscal-bellman-for-matsya.md` §7.1 is already in matsya's session context from turn 1.

**Matsya invocation.** Prompt body asks Q1 (is `V[<] = E[G^(1-γ)*V]` with factor INSIDE expectation acceptable?), Q2 (is `dV[<] = R·E[G^(-γ)*dV]` the canonical marginal-value form?), Q3 (scalar PermGroFac with calibration vs vector PermGroFac with z-subscript?), Q4 (is "RNrmByG" a canonical dolo-plus name or just documentation?). Required response: verdict + KB-reference per Q + a verbatim YAML fragment for `arvl_to_dcsn_transition` and `dcsn_to_arvl_mover`.

**Post-matsya parallel reviewers.**
1. *Math-preservation checker* — verify the proposed `V[<]` formula matches `HAFiscal-bellman-for-matsya.md` line 185 `J_t[v^arr]( a, z) = E[Gamma_hat^(1-gamma) * v^arr]`.
2. *Euler-equation cross-checker* — verify the marginal-value form is consistent with the Euler at `HAFiscal-bellman-for-matsya.md` §7.4 line 247.
3. *HARK RNrmByG verifier* — confirm `R/G` appears as the normalized return factor in `AggFiscalModel.py` solver iteration.
4. *KB-citation verifier* — confirm `ConsIndShock_stage.yaml:72` exists with the cited form.

**Halt criterion.** HALT if matsya proposes a CORRECTION that changes the MATH (e.g. moves Γ̂ outside the expectation — wrong since Γ̂ = ψ·Γ_e depends on stochastic ψ). NOTATIONAL corrections are fine.

**Output artifact.** `matsya_turns/turn3_normalization.md`, `matsya_turns/turn3_yaml_fragment.yaml`, `matsya_turns/turn3_verdict.md`.

### Step 4 — Perpetual youth (matsya turn 4)

**Purpose.** Confirm `β · LivPrb` discount-factor encoding (canonical per ConsMarkov line 76) and document T_age + newborn-pool as out-of-scope.

**Matsya invocation.** Prompt body details LivPrb_base = 1 - 1/160, Markov-invariant; asks Q1 (β·LivPrb canonical vs separate D parameter?), Q2 (is there ANY canonical dolo-plus syntax for T_age forced death or newborn injection — if so cite KB filepath?), Q3 (comment block vs dedicated `out_of_scope:` key for documenting orchestrator-handled items?), Q4 (one comment per item vs consolidated line?). Required response: verdict + verbatim YAML fragment for Bellman line and out-of-scope preamble.

**Post-matsya parallel reviewers.**
1. *Equivalence checker* — verify β·LivPrb = β·(1-D) when LivPrb = 1-D (formal equivalence with HAFiscal-bellman-for-matsya.md §7.2 line 210).
2. *HARK-implementation cross-checker* — confirm `EndOfPrdvP *= LivPrb` at `AggFiscalModel.py:1857`.
3. *KB-citation verifier* — if matsya claims T_age syntax exists, verify the cited filepath; if absent, FAIL.
4. *Out-of-scope consistency reviewer* — confirm the four enumerated out-of-scope items match the locked Architectural Decisions.

**Halt criterion.** HALT if matsya claims canonical T_age forced-death or mass-balance syntax exists in dolo-plus, AND cannot produce a concrete KB filepath when asked. Treat as hallucination; revert to OUT-OF-SCOPE.

**Output artifact.** `matsya_turns/turn4_mortality.md`, `matsya_turns/turn4_yaml_fragment.yaml`, `matsya_turns/turn4_verdict.md`.

### Step 4.5 — Scope-ledger checkpoint (no matsya, addresses Critique 2 gap)

After four turns of context accumulation, force a structured re-summary of "what is in the YAML now" in 5 bullets:
- States, controls, exogenous (turn 1 + 5)
- Splurge encoding (turn 2)
- Normalization (turn 3)
- Effective discount (turn 4)
- Pending decisions for turn 5 (Markov) and turn 6 (Cratio/AD)

The operator runs `matsya ask --session HAFiscal-Latest "Restate the current YAML scope in 5 bullets. No questions, no preamble."` and saves to `matsya_turns/turn4.5_scope_ledger.md`. This catches silent drift before steps 5-6.

### Step 5 — Joint Markov encoding (matsya turn 5)

**Purpose.** Settle the flat-Z encoding (single Categorical(MrkvArray[z_prev])) and the inline-vs-lookup decomposition of (MicroMrkv, MacroMrkv, RecState).

**Critical critique from Critique 1.** The proposal `MicroMrkv = z_d mod J, MacroMrkv = z_d / J` IS consistent with HAFiscal's `Mrkv = num_base_MrkvStates * MacroMrkv + MicroMrkv` encoding — but verify RecState = `(MacroMrkv % 2 == 1)` against `make_hierarchical_mrkv_array` and confirm MacroMrkv=0 is normal-stationary while odd indices in [1, 2(K+1)) are recession-states.

**Matsya invocation.** Prompt body asks: Q1 (confirm flat-Z is canonical), Q2 (does dolo-plus support `mod` and integer-division inline, or do we need precomputed lookup arrays?), Q3 (can same J=6 schema cover all four policy scenarios?), Q4 (stationary single MrkvArray vs dated finite-sequence backward sweep?). Required response: verdict + KB-reference per Q + verbatim YAML fragment for symbols + arvl_to_dcsn_transition.

**Forward dependency note (from Critique 2).** If Q2 = "precompute lookup needed", step 6's inline `RecState = (MacroMrkv mod 2 == 1)` breaks; we must revise step 6 to consume `RecState_of_z` as a length-N_z lookup parameter. The halt criterion includes this rewiring.

**Post-matsya parallel reviewers.**
1. *RecState-direction verifier* — read `Parameters.py:353-434` `make_hierarchical_mrkv_array` and confirm odd MacroMrkv indices are recession-states.
2. *Mod/integer-division support verifier* — grep `/home/shared/github/bright-forest/bellman-ddsl/docs/examples/` for any example using `mod` or `//` inline in a transition block.
3. *HARK solver parity reviewer* — confirm Q4's answer matches HARK's `MarkovConsumerType.solve_one_period` (stationary single MrkvArray).
4. *Policy-unification verifier* — confirm Q3's answer is consistent with feature (h) of the mapping (UI uses J=6 same as bug_fix baseline; Check and TaxCut differ only in calibration scalars).

**Halt criterion.** HALT if Q4 = "dated finite-sequence" (contradicts single-stage architecture). HALT if Q3 says separate schemas per policy are needed (breaks the unified-YAML plan). Soft-handle Q2: if precompute-lookup is needed, revise the prompt in step 6 accordingly.

**Output artifact.** `matsya_turns/turn5_markov.md`, `matsya_turns/turn5_yaml_fragment.yaml`, `matsya_turns/turn5_verdict.md`.

### Step 5.5 — KB sweep for forecast-rule precedent (no matsya, addresses Critique 3)

Before step 6, grep matsya's accessible KB for *any* canonical example with a state evolving via a parameterized forecast rule (Krusell-Smith reference implementation, an `aggregate_consistency` example, or similar). If none exists, the v1 YAML must either:
- (a) keep Cratio as a state with `CRule` as a parameter (current proposal — encode honestly and flag as DDSL extension), OR
- (b) downgrade Cratio to a time-varying exogenous parameter overwritten between orchestrator solves (loses 2D interpolation fidelity; flag as known fidelity gap).

The sweep result determines which option turn 6 proposes. Output: `matsya_turns/turn5.5_forecast_rule_kb_sweep.md`.

### Step 6 — AD coupling (matsya turn 6)

**Purpose.** Settle Cratio as a continuous state, CRule as a parameter, ADF in both budget AND expectation, with the outer Cratio fixed point in Python.

**Critical critique from Critique 1.** Two real gaps to address explicitly: (i) ADF must appear in BOTH `arvl_to_dcsn_transition` (budget side, matching `AggFiscalModel.py:1215`) AND `dcsn_to_arvl_mover` (expectation side, matching `AggFiscalModel.py:1785` `TranShkValsNext_tiled *= AggDemandFacnext_array`); (ii) `CRule: @in [0,1]^(N_z, N_z)` typed as a probability matrix is WRONG — CRule maps `Cratio_now → Cratio_next`, so it's a function (slope+intercept per (i,j) cell), not a stochastic matrix. The correct type is `[real, real]^(N_z, N_z)` (i.e. a (slope, intercept) pair per cell, NOT a `[0,1]` probability).

**Matsya invocation.** Prompt body asks: Q1 (confirm external Krusell-Smith pattern), Q2 (Cratio as state vs time-varying parameter? — this determines whether cFunc has shape `(n_m, n_C, N_z)` or `(n_m, N_z)`-indexed-by-t), Q3 (CRule typing and parameterization), Q4 (inline forecast rule application inside Bellman vs separate definitions block), Q5 (Cratio fixed-point convergence criterion in YAML `settings` block vs strictly out-of-YAML). Required response: verdict + KB-reference per Q + verbatim YAML fragment integrating Cratio into symbols, arvl_to_dcsn_transition, and dcsn_to_arvl_mover.

**Post-matsya parallel reviewers.**
1. *CRule-type verifier* — confirm CRule is typed as `real^(N_z, N_z, 2)` (slope+intercept per cell), NOT as `[0,1]` (probability matrix). FAIL on the probability-matrix typing bug.
2. *ADF-dual-occurrence verifier* — grep the proposed YAML for `ADF` (or its inline expansion) in BOTH the forward transition (budget) AND the expectation block. FAIL if only one occurrence.
3. *cFunc-dimensionality reviewer* — confirm Q2's answer (Cratio as state) is consistent with `AggFiscalModel.py`'s 2D `LinearInterpOnInterp1D(cFunc[z](m, Cratio))` construction.
4. *AD-loop reviewer* — confirm Q1's external-loop pattern matches `welfare6_scenario.solve_ad_recession` (max 15 iters, 1e-3 tol, damped step ≤ 1.0).

**Halt criterion.** HALT if Q1 = "dolo-plus has a forecast_rule block" AND matsya cannot produce a specific KB example file. HALT if Q2 = "time-varying parameter" (contradicts HAFiscal's 2D cFunc). HALT if reviewer 1 FAILS the CRule-type check. HALT if reviewer 2 FAILS the ADF-dual-occurrence check.

**Output artifact.** `matsya_turns/turn6_ad.md`, `matsya_turns/turn6_yaml_fragment.yaml`, `matsya_turns/turn6_verdict.md`.

### Step 7 — Assembled YAML (matsya turn 7)

**Purpose.** Produce the final clean YAML by assembling all settled fragments.

**Matsya invocation.** Prompt body restates all six prior decisions, requires RAW YAML output (first line `name: hafiscal_household`), specifies exact top-level key order (`name`, `symbols`, `equations`, `calibration`), specifies the inner `symbols` order (`spaces`, `prestate`, `states`, `poststates`, `controls`, `exogenous`, `values`, `values_marginal`, `parameters`, `settings`), specifies the four perch movers in `equations`, mandates Baseline calibration values per `Parameters.py`, mandates the four-item out-of-scope comment block at file head, target length 120-180 lines, requires self-validation (re-parse before responding).

**Post-matsya parallel reviewers (mandatory cascade — all must PASS).**
1. *YAML parse verifier* — `yq eval . HAFiscal-doloplus-draft.yaml` exits 0.
2. *Perch-mover presence verifier* — `grep -c 'arvl_to_dcsn_transition\|dcsn_to_cntn_transition\|cntn_to_dcsn_mover\|dcsn_to_arvl_mover'` returns 4.
3. *Splurge encoding verifier* — grep `c_sp = varsigma` AND `NOT_OPTIMIZED` annotation.
4. *Γ̂ factor verifier* — grep `G ^ (1 - gamma)` or equivalent inside `V[<]` expectation.
5. *β·LivPrb verifier* — grep `beta * LivPrb` in `cntn_to_dcsn_mover.Bellman`.
6. *Flat-Z verifier* — grep `Categorical(MrkvArray[z_prev])`.
7. *Cratio-state verifier* — confirm `Cratio_d` appears in `symbols.states` AND `CRule` in `symbols.parameters` with non-probability type.
8. *ADF-dual-occurrence verifier* — confirm ADF in both `arvl_to_dcsn_transition` and `dcsn_to_arvl_mover`.
9. *Calibration sanity reviewer* — diff numeric values in `calibration` block against `Parameters.py` defaults; flag drift > 1%.
10. *Out-of-scope preamble verifier* — confirm 4-item block (T_age, newborn, AD loop, 21-cohort) appears at file head.
11. *Line-count reviewer* — line count in [80, 300].

All 11 reviewers run in parallel; all must PASS. On any FAIL, send matsya a targeted-fix follow-up prompt (do not regenerate whole YAML).

**Halt criterion.** HALT if response is not raw YAML (contains markdown fences, preamble, or trailing source block) — re-prompt with stricter wording. HALT if parse fails after the third targeted-fix attempt; at that point manually edit the broken section.

**Output artifact.** `/home/shared/github/llorracc/HAFiscal-Latest/HAFiscal-doloplus-draft.yaml` (the deliverable).

### Step 8 — Numerical round-trip validation (replaces literary round-trip from prior plan, addresses Critique 3)

**Purpose.** The prior plan asked matsya to render the YAML back to math as a validation gate; Critique 3 correctly notes this is "the same model validating itself." Replace with a *numerical* spot-check.

**Mechanical test.** Write a small Python script `Code/HA-Models/dolo_plus_validation/test_euler_at_point.py` that:
1. Loads `HAFiscal-doloplus-draft.yaml`.
2. Loads Baseline calibration values from the YAML.
3. Evaluates the proposed Euler equation `c_opt^(-γ) = β·LivPrb·R·E[Γ̂^(-γ)·c_opt[next]^(-γ)]` at a known test point `(m_test, z_test, Cratio_test) = (5.0, 0, 1.0)` (employed, normal-macro, Cratio at baseline).
4. Compares to HAFiscal's HARK 0.17.x solver output at the same `(m, z, Cratio)` point from a small Baseline solve.
5. Reports relative error.

**PASS criterion.** Relative error < 1e-3 at the test point. Even one passing point catches sign errors, factor-of-G mistakes, splurge-in-utility-vs-budget conflations, ADF dropouts. Failures are debugged by isolating which YAML equation block disagrees with HARK.

**Companion literary round-trip (optional, downgraded).** A turn-8 matsya prompt asks for math-rendering of the YAML for documentation purposes; the result goes into `HAFiscal-doloplus-validated.md` but is *not* the validation gate.

**Halt criterion.** HALT and debug if relative error ≥ 1e-3. The two most likely failure modes are (i) Γ̂ exponent on marginal value (should be -γ, easy to swap with 1-γ), (ii) ADF missing from one of the two locations.

**Output artifact.** `Code/HA-Models/dolo_plus_validation/test_euler_at_point.py` (script), `Code/HA-Models/dolo_plus_validation/validation_report.txt` (test output), optionally `HAFiscal-doloplus-validated.md`.

## Workflow patterns to use

- **Step 0**: sequential bash (no parallelism).
- **Steps 1, 2, 5, 6, 7**: pre-matsya parallel readers (2-3 subagents extracting context), then matsya turn, then post-matsya parallel verdict reviewers (4-11 subagents each producing PASS/FAIL with one-line reason). Aggregate verdicts before deciding whether to proceed.
- **Steps 3, 4**: lighter pattern — single matsya turn + 4 parallel reviewers.
- **Step 2.5**: parallel auxiliary deliverable (DDSL extension proposal) generated by a single dedicated subagent reading the splurge feature context.
- **Step 4.5**: scope-ledger checkpoint, single matsya call, no reviewers.
- **Step 5.5**: KB-sweep, single grep + summary by a context-extraction subagent.
- **Step 8**: code-generation subagent writes the validation script; another subagent runs it and parses output.

The orchestration is **always plan-for-parallelism**: every step that has >1 independent verification task launches them as concurrent subagent calls, not sequential.

## Validation cascade

End-to-end gating, in cascade order (HALT at first FAIL, fix at that tier, do not skip):

1. **YAML parse** (`yq eval .`).
2. **Structural check** (all required keys present, perch movers count = 4).
3. **Spec-text faithfulness** — for each of features (a)-(h) in the mapping table, grep the YAML for the required encoding pattern. Tier (a)-(g) are mandatory; (h) is per-policy (4 calibration files).
4. **Calibration value cross-check** — `Parameters.py` defaults vs YAML scalars, tolerance 1%.
5. **Paper-faithfulness** — diff `dcsn_to_arvl_mover.Bellman` against `Subfiles/Model.tex` eq. `eq:perm_income` Bellman; diff ADF formula against eq. (7) `eq:ad_feedback`; diff income map against eq. `eq:income`.
6. **Numerical Euler check** at one test point (step 8).
7. **Multi-point sanity** (deferred to v2, but documented): repeat step 6 at three test points `(m, z, Cratio) ∈ {(1, 0, 1), (5, 1, 1.1), (10, 5, 0.9)}` spanning employed, UI, exhaustee × normal/recession × Cratio levels.

## Failure modes + recovery

- **Matsya hallucinates a KB filepath.** Reviewer flags this; operator escalates by asking matsya to produce the file content verbatim. If matsya cannot, treat as confabulation and revert that turn's decision to FALLBACK.
- **Matsya recommends DDSL extension only (Encoding C).** Pause execution. The DDSL extension proposal from step 2.5 is filed as an upstream issue against econ-ark/Matsya. The v1 YAML proceeds with Encoding A + an explicit `# PENDING_EXTENSION:` annotation. Document the gap in `HAFiscal-doloplus-draft.yaml` header.
- **Cratio-as-state KB sweep finds no precedent (step 5.5).** Choose option (b): downgrade Cratio to time-varying exogenous parameter overwritten between solves; document as known fidelity gap.
- **`yq eval` fails on step-7 output 3+ times.** Manually edit the most-broken section using the previous-turn fragments as ground truth; do not regenerate full YAML.
- **Numerical Euler check fails (step 8).** Bisect by feature: zero out splurge (ς=0), zero out AD (κ=0), zero out micro-Markov heterogeneity (collapse to E-only). The first collapse that passes localizes the bug.
- **Session expires or matsya CLI breaks.** All turn artifacts are checkpointed in `matsya_turns/` so the run can resume at any failed step without re-running prior turns.

## Output artifacts

| Path | Content |
|---|---|
| `/home/shared/github/llorracc/HAFiscal-Latest/HAFiscal-doloplus-draft.yaml` | The deliverable (final YAML) |
| `/home/shared/github/llorracc/HAFiscal-Latest/matsya_turns/turn{1..8}_*.md` | Raw matsya responses |
| `/home/shared/github/llorracc/HAFiscal-Latest/matsya_turns/turn{1..7}_yaml_fragment.yaml` | Extracted YAML snippets per turn |
| `/home/shared/github/llorracc/HAFiscal-Latest/matsya_turns/turn{1..7}_verdict.md` | Parallel reviewer verdicts |
| `/home/shared/github/llorracc/HAFiscal-Latest/matsya_turns/turn4.5_scope_ledger.md` | Mid-execution scope re-summary |
| `/home/shared/github/llorracc/HAFiscal-Latest/matsya_turns/turn5.5_forecast_rule_kb_sweep.md` | KB-sweep result for Cratio-as-state precedent |
| `/home/shared/github/llorracc/HAFiscal-Latest/matsya_turns/ddsl_extension_proposal_mechanical_flows.md` | DDSL extension request draft (splurge) |
| `/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/dolo_plus_validation/test_euler_at_point.py` | Numerical Euler check script |
| `/home/shared/github/llorracc/HAFiscal-Latest/Code/HA-Models/dolo_plus_validation/validation_report.txt` | Test output |
| `/home/shared/github/llorracc/HAFiscal-Latest/HAFiscal-doloplus-validated.md` (optional) | Literary round-trip for documentation |

## To execute

Execute the plan in `plan_hafiscal_dolo_plus_v2.md` starting with Step 0 pre-flight checks, then Step 1 (matsya turn 1, architecture confirmation), proceeding through each step's parallel-orchestrated workflow with halt criteria enforced at each gate.
