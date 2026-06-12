# Plan: refactor codebase to run *either* CDC *or* ESC interpretation (or both) — staged

**Date:** 2026-04-25 (revised 2026-04-26: split into Stage 1 / Stage 2 to balance the symmetric end-state goal against debuggability during construction; per-phase evidence checks added)
**Status:** Planned
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (working branch); implementation on `feature/cdc-esc-configurable` (created at kickoff)
**Predecessors:**
- `plans/20260425-2058h_cdc-anchors-in-codebase.md` — anchor-mapping plan
- `plans/20260425-2102h_cdc-implementation-map.md` — per-anchor inventory + paired alternatives + pinned baselines + architecture decision
- `plans/20260426-0706h_pre-refactor-prep.md` — pre-refactor prep (LANDED on `_TM-vs-MC` as items 1-4: CDC helpers extracted, `_ESC` calibration files staged, `test_cdc_baseline_pin.py` in place)
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md` — formal CDC↔ESC side-by-side specification
- `proposed_path_forward_20260424.md` §1 — the "bonded-pair port" item that this plan implements

## 1. Goal

Produce a single codebase that can run *either* the CDC (household-bargain) or ESC (Campbell–Mankiw bound-pair) interpretation, selectable at runtime. **The end-state codebase treats the two interpretations symmetrically — neither is privileged in the class hierarchy, helper-function naming, default-value selection, or call-site assumptions.**

To balance that symmetric end-state against debuggability during construction, the work proceeds in two stages:

- **Stage 1 — debugging-friendly, additive, CDC-preserving.** When the new interpretation parameter is absent (or set to `'CDC'`), the *exact same code executes in the exact same order* as today. Bit-identical reproduction of the existing CDC anchor (`reproduce-20260425-comp-full-tm-only`) is the gating test at every commit. ESC is implemented by *adding* code (a sibling subclass, sibling helpers, new branches inside parameter-passing functions); no existing CDC code is moved, renamed, or reordered. This makes any post-Stage-1 behavior change diagnosable: the CDC path is git-equivalent to the original, so any failure of the CDC pin must come from infrastructure changes or from ESC code accidentally executing in CDC mode — not from a CDC body-edit gone wrong.

- **Stage 2 — symmetric polish, behavior-preserving.** Refactor the now-working both-interpretations codebase to remove the asymmetry. `AggFiscalType` becomes an abstract base; CDC and ESC become equal sibling subclasses; call sites name `CDCAggFiscalType` explicitly; helper-function naming becomes consistently paired or consolidated to a dispatcher; documentation reflects symmetric treatment. The Stage 1 ESC anchor and the original CDC anchor both gate Stage 2: bit-identical reproduction of *both* is required at every Stage 2 commit. Stage 2 adds no functionality — it only removes architectural debt.

Stage 1 alone yields a runnable both-interpretations codebase suitable for the paper's CDC↔ESC comparison and the methodology appendix. Stage 2 is for codebase health and is not on the critical path for any paper-facing deliverable; it can be done in a separate session after Stage 1 lands and the side-by-side numbers are reported.

### Acceptance criteria

**Stage 1:**
- `pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py` passes (proves Stage 1 didn't perturb CDC at the pinned points).
- `./reproduce.sh --comp full --tm-only` reproduces the anchor `reproduce-20260425-comp-full-tm-only` bit-identically.
- `./reproduce.sh --comp full --mc-only --interpretation esc` produces ESC welfare-6 numbers; the result is anchored as `reproduce-<date>-comp-full-mc-only-esc`.
- A side-by-side comparison driver runs both interpretations in one process and reports a comparison table.
- `git diff <pre-stage-1>..<post-stage-1>` of CDC code paths shows additive changes only — no rename, no reorder, no body-edit of any existing CDC function/method/class.

**Stage 2:**
- Stage 1 acceptance criteria still hold (CDC anchor + ESC anchor both reproduce bit-identically).
- `grep -rn '\bAggFiscalType\b' Code/` returns only `AbstractAggFiscalType`, `CDCAggFiscalType`, `ESCAggFiscalType` — no bare `AggFiscalType` references in production code.
- Both `test_cdc_baseline_pin.py` and `test_esc_baseline_pin.py` pass.
- Symmetric language check: `grep -ic '\bcdc\b'` and `grep -ic '\besc\b'` over user-facing docs (README, CLAUDE.md, INTERPRETATIONS.md) return comparable counts.

## 1.5 Debugging methodology and evidence requirements

The Stage 1 design is bisect-friendly: at every phase, the CDC code path is byte-equivalent to pre-Stage-1, so any CDC pin failure narrows to *that phase's added code* — not to a body-edit somewhere upstream. This makes the debugging story crisp: you stop at the phase that broke the pin, you read the diff (which is purely additive), you see what was added, you find the bug.

To enforce this discipline, every Stage 1 phase has an **"Evidence required before proceeding"** subsection that lists:
- The exact commands to run
- The exact expected output (numerical values, file paths, exit codes)
- The failure-mode handlers ("If X fails: do Y, look at Z")
- A sign-off checklist

The rule is: **no phase begins until the previous phase's evidence checklist is fully ticked.** A failed evidence check is not a "soft" signal to investigate later — it is a hard stop. The cost of investigating immediately (~minutes) is much lower than the cost of compounding bugs across phases (hours to days).

### Evidence-cost taxonomy

| Evidence type | What it proves | Time cost | Run when |
|---|---|---|---|
| `pytest test_cdc_baseline_pin.py` | CDC behavior at pinned points unchanged | seconds | After every commit |
| `git diff <pre>..HEAD` shows additive only | Additive-only invariant holds | seconds | After every commit |
| `python -c "import …"` succeeds | New classes/imports well-formed | seconds | After Phase A, D |
| `pytest Code/HA-Models/FromPandemicCode/test_*.py` | Wider regression suite passes | seconds-minutes | At each phase boundary |
| `./reproduce.sh --comp nano` exits 0 | Run pipeline still works end-to-end | ~10 seconds | At each phase boundary |
| Step-1 CDC re-estimation reproduces ς | Estimation's CDC branch unchanged | minutes | After Phase B |
| Step-1 ESC re-estimation reproduces ς | ESC implementation matches Edmund's | minutes | After Phase B |
| `./reproduce.sh --comp full --tm-only` reproduces anchor bit-identically | Full CDC pipeline preserves anchor | ~25 minutes | After Phase E (and Phase C if included) |
| `./reproduce.sh --comp full --mc-only --interpretation esc` runs to completion | ESC path is operational end-to-end | ~6-12 hours | After Phase E |
| Manual code review against the additive-only invariant | Catches inline edits the pin tests miss | minutes | After every phase |

Cheap evidence (seconds) runs after every commit. Mid-cost evidence (minutes) runs at phase boundaries. Expensive evidence (~25 min full-anchor reproduction; ~hours for ESC end-to-end) runs at the indicated phase boundary, not after every commit, because the pin test catches the same drift in seconds.

### Hard-stop rule

If any evidence check fails:
1. Do **not** proceed to the next phase.
2. Do **not** proceed to the next (more expensive) tier of checks within the same phase.
3. Do **not** add a workaround that masks the failure.
4. Read the diff against the last known-good commit.
5. Identify the line(s) responsible.
6. Either fix or revert; re-run all checks at and below the failed tier before continuing.

### Cost-ordered execution rule

Within each phase's evidence section, checks are organized into **cost tiers**. The rule:

> **Run each tier completely before starting the next. Do not begin tier T+1 until every check in tier T has passed.**

The tiers used in this plan are concretely calibrated to this codebase's two cost axes — **parametrization** (Smoke_Test/HS_Only/Reduced_Run/Baseline; see `Parameters.return_parameters`) and **pipeline coverage** (`reproduce.sh --comp nano|micro|mini|min|full`):

- **Tier 1 — instant (~seconds):** focused pytest on a single file (e.g., `pytest test_cdc_baseline_pin.py`), import-and-assert one-liners, `git diff` inspection. Always run every tier-1 check first; expect them to pass; if any fails, you've found the bug without spending compute.
- **Tier 2 — cheap (~10 seconds to ~10 minutes):** smoke tests on light parametrizations:
  - `./reproduce.sh --comp nano` (~30s, parameter loading + agent creation)
  - `./reproduce.sh --comp micro` (~1 min, + economy solve)
  - `./reproduce.sh --comp mini` (~5-10 min, + simulation + baseline experiment, on Reduced_Run)
  - Wider `pytest Code/HA-Models/FromPandemicCode/test_*.py`
  - Step-1 splurge re-estimation on **Reduced_Run** (~minutes, 3 types × 1 β atom)
  - Single-type GLP-style diagnostic via `python test_glp2_ad_comparison.py`
- **Tier 3 — moderate (~10 minutes to ~2 hours):** larger-scope checks:
  - Step-1 splurge re-estimation on **Baseline** (~30 min, 21 types)
  - `./reproduce.sh --comp min` (~1 hour, minimal results)
  - `./reproduce.sh --comp full --tm-only` (~1-2 hours, Baseline-scale TM-only — this IS the existing CDC anchor reproduction)
- **Tier 4 — expensive (~hours to days):** the costly compute that should run only when everything cheaper has passed:
  - `./reproduce.sh --comp full --mc-only --interpretation esc` (~6-12 hours, MC welfare-6 on Baseline) — the ESC anchor production
  - Step-2 (β/∇) re-estimation under our new code (~48 hours on Baseline; ~minutes-hours on Reduced_Run)
  - Step-3 robustness (Splurge=0 re-estimation, ~48 hours, only in `--comp max`)

**Parameter estimation cost dependence.** Step-1 (splurge ς) is moderate (~30 min on Baseline; ~minutes on Reduced_Run). Step-2 (β/∇) is the order-of-magnitude jump (~48 hours on Baseline). Where the plan calls for Step-1 ESC re-estimation, default to **Reduced_Run** for tier 2 and add **Baseline** as a tier 3 check only if you want the tighter pin.

**The expensive compute lives in a dedicated Phase F**, not interleaved with cheaper phases. This means Phases A-E2 stay in the tier-1-through-tier-3 zone and the tier-4 ESC anchor run is the very last Stage 1 phase. The point: if a Phase A bug doesn't surface until Phase F's tier-4 run, you've spent 6-12 hours discovering what cheaper checks should have caught — so always confirm tier-2 ESC nano/mini works before committing to F.

The point of the hierarchy: a tier-3 or tier-4 failure is dramatically more expensive to discover than a tier-1 failure that would have caught the same bug. Always burn the cheapest evidence first.

Within a tier, checks can be run in any order (or in parallel if convenient).

### Per-commit testing within a phase

Within a phase, run `pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py` after every commit. This is a tier-1 test (seconds) that catches the most common failure mode (accidental perturbation of the CDC code path) immediately. Stage 1 is structured so this should never fail under normal Stage 1 work — if it does, it is a signal that the additive-only discipline slipped. Do not run any tier-2+ check after a commit until this passes.

### Reference: the pre-Stage-1 commit hash

Stage 1 work begins from a known commit on `feature/cdc-esc-configurable` branched off `_TM-vs-MC` HEAD at kickoff. Record that commit hash in this document at kickoff time so all subsequent "diff against pre-Stage-1" checks have a definite reference. Placeholder: `<pre-stage-1-commit>` throughout this document is to be replaced with the actual SHA at kickoff.

## 1.6 Logging and monitoring

Because Stage 1 work runs on a remote machine without access to the local Cursor session's notification manager, the only practical signaling channel between the executor (me, in a future session) and the user is **the log file itself**. The executor must write enough structured information to the log that the user can:

- Tail the log and see real-time progress.
- Grep for specific events (halts, failures, background jobs starting) to filter noise.
- Read a single status file at any moment to know where execution currently is.
- Recognize when the executor has halted and needs input.

### Log paths

| Path | Purpose | Format |
|---|---|---|
| `reproduce/logs/cdc-esc-refactor.log` | Main append-only narrative log; canonical timeline of all phases | Structured text (see line format below) |
| `reproduce/logs/cdc-esc-status.json` | Machine-readable current state; updated atomically via temp-file rename | JSON (see schema below) |
| `reproduce/logs/cdc-esc-phase-<X>.log` | Per-phase raw output (pytest -v, full diffs, etc.); forensic only | Free text |
| `reproduce/logs/latest.log` | Symlink to whatever `--comp` run log is current; used by tier-2/3/4 reproduce.sh invocations | Existing convention |
| `Code/HA-Models/FromPandemicCode/welfare6_parallel_logs/Baseline*/` | Per-scenario MC logs during Phase F | Existing convention |

### Log line format

```
[<LEVEL>] [<UTC-timestamp>] [Phase <X>] [Tier <T>] [<check-id>] <message>
```

`<check-id>` is `T<tier>.<index>` (e.g., `T2.3`), or `setup`/`teardown`/`progress` for non-check events.

Log levels (uppercase, fixed-width brackets so `grep` patterns work):

| Level | Meaning | Example |
|---|---|---|
| `INFO ` | Routine progress | `[INFO ] [...] [Phase A] [Tier 1] [T1.1] running pytest test_cdc_baseline_pin.py` |
| `START` | Beginning a phase or tier | `[START] [...] [Phase B] entering phase` |
| `BG   ` | Background task kicked off | `[BG   ] [...] [Phase F] [Tier 4] [T4.1] starting --comp full --mc-only ESC anchor; expected ~6-12h` |
| `ALIVE` | Periodic heartbeat during long-running tasks (every ~10-15 min) | `[ALIVE] [...] [Phase F] [Tier 4] [T4.1] ESC anchor alive; elapsed 2h 14m; 4/12 scenarios complete` |
| `PASS ` | Evidence check passed | `[PASS ] [...] [Phase A] [Tier 1] [T1.1] CDC pin (47 assertions OK in 3.2s)` |
| `FAIL ` | Evidence check failed; entering investigation | `[FAIL ] [...] [Phase B] [Tier 2] [T2.3] ESC ς = 0.281, expected 0.267 ± 2%; rel diff 5.3%` |
| `INV  ` | Investigation step (a hypothesis or diagnostic tool call) | `[INV  ] [...] [Phase B] [Tier 2] [T2.3] hypothesis: ESC wealth-correction sign error; checking _wealth_under_esc impl` |
| `RESOL` | Investigation succeeded; check now passes | `[RESOL] [...] [Phase B] [Tier 2] [T2.3] fixed: missing (1-ς) factor in line 234; ς now 0.268` |
| `HALT ` | Investigation exhausted; user input required | `[HALT ] [...] [Phase F] [Tier 4] [T4.2] cannot proceed (see status file)` |
| `RESUM` | User provided direction; resuming | `[RESUM] [...] [Phase F] [Tier 4] [T4.2] user clarified: use ESC-1 formula; retrying` |
| `DONE ` | Phase complete; all evidence signed off | `[DONE ] [...] [Phase B] all evidence checks PASS; proceeding to Phase D` |

### Status file schema

```json
{
  "state": "running" | "halted" | "complete" | "background",
  "phase": "A" | "B" | "C" | "D" | "E" | "E2" | "F" | "G" | "H" | "I" | "J" | null,
  "tier": 1 | 2 | 3 | 4 | null,
  "current_check": "T2.3" | null,
  "started_at_utc": "2026-04-26T12:00:00Z",
  "last_update_utc": "2026-04-26T17:34:00Z",
  "elapsed_seconds": 20040,
  "phases_complete": ["A", "B", "C", "D", "E", "E2"],
  "halt_reason": null,
  "user_query": null,
  "background_pid": null
}
```

When the executor halts, the file becomes:

```json
{
  "state": "halted",
  "phase": "F",
  "tier": 4,
  "current_check": "T4.2",
  "halt_reason": "ESC welfare-6 UI Rec=1 AD=1 cell = 0.78, outside the ±5% tolerance vs Edmund's 1.36",
  "user_query": "Need clarification on whether recession+AD path should use ESC-1 or ESC-2 from models_CDC_and_ESC.md §5.4. Tried: (a) confirmed ESC calibration loaded correctly; (b) compared MC scenario logs with Edmund's branch — no obvious config mismatch; (c) re-ran with different RNG seed → same 0.78. Most likely a formula error but cannot pick between ESC-1 and ESC-2 without coauthor sign-off.",
  "last_update_utc": "2026-04-26T17:34:00Z"
}
```

### Monitoring commands for the user

**Watch all activity in real time:**
```bash
tail -f reproduce/logs/cdc-esc-refactor.log
```

**Watch only events that need attention** (HALT, FAIL, BG kickoff):
```bash
tail -f reproduce/logs/cdc-esc-refactor.log | grep --color=always -E '\[HALT \]|\[FAIL \]|\[BG   \]|\[DONE \]'
```

**See current state (snapshot, run any time):**
```bash
cat reproduce/logs/cdc-esc-status.json | python -m json.tool
```

**See the last 100 lines** (catch up after stepping away):
```bash
tail -100 reproduce/logs/cdc-esc-refactor.log
```

**See just the recent halt** (if status says `state: "halted"`):
```bash
jq -r '.halt_reason, .user_query' reproduce/logs/cdc-esc-status.json
```

**Watch the underlying compute log during Phase F** (the actual MC run output, alongside the high-level refactor log):
```bash
tail -f reproduce/logs/latest.log
```

**Per-scenario MC logs during Phase F's tier-4 anchor run:**
```bash
tail -f Code/HA-Models/FromPandemicCode/welfare6_parallel_logs/Baseline_esc/*.log
```

### When the executor halts

When the executor (me, in a future session) hits a bug it cannot fix:

1. Write a `[HALT ]` line to the main log with: phase, tier, check, what failed, what was tried, what input is needed from the user.
2. Update the status file to `state: "halted"` with the same information in the `halt_reason` and `user_query` fields.
3. Stop initiating further tool calls.

The `[HALT ]` and `[FAIL ]` markers are deliberately distinctive (with the trailing space inside the brackets to match the fixed-width pattern) so a single `grep '\[HALT \]\|\[FAIL \]'` reliably catches them without false positives from words like "halted" appearing elsewhere.

### Heartbeat during long-running phases

During Phase F's tier-4 ESC anchor run (~6-12 hours), the executor must periodically write `ALIVE` lines:

```
[ALIVE] [2026-04-26T15:34:00Z] [Phase F] [Tier 4] [T4.1] ESC anchor alive; elapsed 3h 14m; 5/12 scenarios complete; latest scenario: recession_AD (84% done per its log).
```

Cadence: every 10-15 minutes. Mechanism: a small wrapper script `reproduce/cdc_esc_heartbeat.sh` that polls the per-scenario logs and writes to the main log every 10 minutes. To be authored as part of Phase F setup.

This lets the user `tail -f` and confirm "still working" without checking process status, and provides a clear marker (gap of >20 min between `ALIVE` lines) that something has gone wrong if the run silently dies.

### Logging discipline by phase

Phases A-E2 are short enough that `INFO`/`PASS`/`FAIL`/`DONE` events are sufficient. Phase F (tier-4) requires the heartbeat mechanism. Stage 2 phases follow Phase A-E2's pattern.

Each phase's evidence section in §5 implicitly assumes the executor is writing to these logs in real time. The phase doesn't sign off until both:
- Every evidence check has logged a `PASS` line.
- A `DONE` line is logged for the phase as a whole.

## 2. The interpretive surface (from the map)

Only **3-4 substitution sites** need actual code-level alternatives. Everything else stays shared.

### 2.1 (I) — `get_poststates` override on `AggFiscalType`

CDC: override that subtracts realized weighted consumption.
ESC: no override (use HARK's default `aNrm = mNrm − cNrm`).

### 2.2 (I+B) — `_option_d_wealth` correction in `Estimation_BetaNablaSplurge.py`

CDC: subtract `ς·pLvl·(TranShk − cNrm)` from `aLvl_hark`.
ESC: multiply `aLvl_hark` by `(1 − ς)`.

Affects: the `WealthNow` aggregator (line 219), the per-quartile counts (lines 228, 230), and the K/Y aggregator (line 461).

### 2.3 (I+B) — lottery-MPC formula in `Estimation_BetaNablaSplurge.py`

CDC: manual `m_base`/`a_base` tracking using the CDC asset rule, since HARK's default rule is wrong under CDC.
ESC: use `ThisType.controls["cNrm"]` directly, since HARK's default rule IS the ESC rule.

### 2.4 (I+B) — `_a` TM kernel formula in `tm_methods.py`

CDC: kernel `g(a, ξ) = (R/Γ)·a + (1−ς)·[ξ − cFunc((R/Γ)·a + ξ)]`.
ESC: kernel `g(a, ξ) = (R/Γ)·a + ξ − cFunc((R/Γ)·a + ξ)` (no `(1−ς)` factor on the splurge piece because the ς·ξ Splurger consumption never enters the Optimizer's ledger).

The other 18 anchors (cLvl_splurge formula, state-var declarations, dispatch wiring, etc.) stay identical between the two paths.

## 3. Architecture

### 3.1 Stage 1 architecture: minimum-disturbance class hierarchy

**Constraint:** when no `interpretation` is selected (or `'CDC'` is explicitly chosen), the running code must be byte-equivalent to the pre-Stage-1 code path — no method moves, no class renames, no reordering of existing definitions. This is the debuggability invariant.

`AggFiscalType` keeps its current implementation exactly. The `get_poststates` override that implements the CDC asset rule stays where it is, on `AggFiscalType`, with no modification to its body.

**Stage 1 additions (additive only):**

```python
# At the bottom of AggFiscalModel.py, after AggFiscalType is fully defined:

# Forward-compat alias for symmetric naming. AggFiscalType IS the CDC
# implementation in Stage 1; CDCAggFiscalType is provided so new code can
# be written in symmetric style. Stage 2 promotes this to a real class.
CDCAggFiscalType = AggFiscalType


class ESCAggFiscalType(AggFiscalType):
    """ESC (Campbell-Mankiw bound-pair) interpretation.

    Overrides only the interpretive methods that differ from CDC; inherits
    everything else from AggFiscalType.
    """

    def get_poststates(self):
        # ESC: use HARK's default a = m - cFunc(m) rule (which IS ESC-1).
        # Skip the CDC splurge-in-budget patch from AggFiscalType.get_poststates.
        AggIndMrkvConsumerType.get_poststates(self)
```

No call-site changes. No edits to `AggFiscalType`. Existing callers continue to use `AggFiscalType` (= `CDCAggFiscalType`) and get CDC behavior.

**Acceptance for Stage 1 architecture:** `git log -p Code/HA-Models/FromPandemicCode/AggFiscalModel.py` against pre-Stage-1 HEAD shows only additions at the bottom of the file. `pytest test_cdc_baseline_pin.py` passes. `./reproduce.sh --comp full --tm-only` reproduces the existing CDC anchor bit-identically.

### 3.2 Stage 2 architecture: symmetric, no-privilege class hierarchy

**Goal:** neither interpretation is structurally privileged over the other.

`AggFiscalType` is renamed to `AbstractAggFiscalType`. `get_poststates` (and any other interpretation-specific methods identified in Stage 1) becomes abstract on the base via `@abstractmethod`.

The two interpretation classes become equal sibling subclasses:
- `class CDCAggFiscalType(AbstractAggFiscalType):` — the CDC `get_poststates` body, moved here from where Stage 1 left it on `AggFiscalType`.
- `class ESCAggFiscalType(AbstractAggFiscalType):` — the ESC `get_poststates` body, where Stage 1 placed it (no move needed).

The Stage 1 alias `CDCAggFiscalType = AggFiscalType` is removed (now redundant since `CDCAggFiscalType` is a real class).

All call sites that used bare `AggFiscalType` are updated to use `CDCAggFiscalType` explicitly. (`Simulate.py`, `EstimAggFiscalMAIN.py`, `welfare6_scenario.py`, `run_welfare6_parallel.py`, tests — estimated ~30 touches.)

**Acceptance for Stage 2 architecture:** `grep -rn '\bAggFiscalType\b' Code/` returns only `AbstractAggFiscalType`, `CDCAggFiscalType`, `ESCAggFiscalType`. CDC pin reproduces (proves Stage 2 didn't break CDC). ESC pin reproduces (proves Stage 2 didn't break ESC).

### 3.3 Interpretation tag for non-class anchors

`Estimation_BetaNablaSplurge.py` and `tm_methods.py` are not class-based at all the relevant sites; they need an `interpretation` parameter.

**Stage 1 pattern:** wrap the existing CDC code in `if interpretation == 'CDC':` and add an `else:` branch for ESC. The CDC branch is the *exact current code, unchanged* — only its indentation and surrounding `if` change. This preserves byte-equivalence under CDC.

```python
# Estimation_BetaNablaSplurge.py — Stage 1 pattern
def FagerengObjFunc(SplurgeEstimate, center, spread, interpretation='CDC', ...):
    # ...
    if interpretation == 'CDC':
        # Exact current code (unchanged from pre-Stage-1):
        WealthNow = np.concatenate([_wealth_under_cdc(t) for t in EstTypeList])
    else:  # ESC
        WealthNow = np.concatenate([_wealth_under_esc(t, SplurgeEstimate) for t in EstTypeList])
    # ... similarly for the lottery-MPC block
```

**Stage 2 may simplify:** if symmetric helpers are paired (`_wealth_under_cdc` + `_wealth_under_esc`), the if/else could become a dispatcher table or a polymorphic call. Stage 2 Phase H makes this decision based on what reads cleanly after Stage 1.

**TM kernel dispatch in `tm_methods.py`** — option (b) per the original plan: define `_build_period_tm_a_esc` paralleling the existing `_build_period_tm_a` (which IS the CDC kernel in Stage 1). Wrappers dispatch based on `isinstance(agent, ESCAggFiscalType)`. Avoids per-call branching inside the hot kernel. (If mitigation #1 is taken, this is deferred.)

### 3.4 Selection mechanism — supports both-at-once

The interpretation is passed as a **parameter** to `return_parameters`, not read from a process-global env var. The env var becomes the *default* for callers that don't specify, so legacy entry points keep working without code changes.

```python
# Parameters.py
def return_parameters(Parametrization='Baseline', OutputFor='_Main.py', interpretation=None):
    if interpretation is None:
        interpretation = os.environ.get('HAFISCAL_INTERPRETATION', 'CDC').upper()
    assert interpretation in ('CDC', 'ESC'), f"Unknown interpretation: {interpretation}"
    # ... select calibration files based on `interpretation`, populate dict, return.
```

This parameter drives:
- Which class (`CDCAggFiscalType` / `AggFiscalType` in Stage 1; `CDCAggFiscalType` proper in Stage 2 / `ESCAggFiscalType` in both stages) to instantiate.
- Which calibration `.txt` files to load (CDC: `Result_AllTarget.txt` + `DiscFacEstim_*.txt`; ESC: `Result_AllTarget_ESC.txt` + `DiscFacEstim_*_ESC.txt` — pre-staged in the prep work).
- Which interpretation tag to pass to `FagerengObjFunc` and the `_a` TM dispatch.

**Both-at-once support.** Because the interpretation is a parameter rather than a process-global flag, both CDC and ESC types can be instantiated in a single process:

```python
# Side-by-side comparison mode (both stages):
cdc_params = return_parameters('Baseline', interpretation='CDC')
esc_params = return_parameters('Baseline', interpretation='ESC')

cdc_types = [CDCAggFiscalType(**cdc_params, ...) for _ in range(num_types)]
esc_types = [ESCAggFiscalType(**esc_params, ...) for _ in range(num_types)]

cdc_economy = AggregateDemandEconomy(...); cdc_economy.agents = cdc_types
esc_economy = AggregateDemandEconomy(...); esc_economy.agents = esc_types
# ... compare results in-memory, no separate processes needed.
```

**Default behavior:** when no `interpretation` parameter is passed and `HAFISCAL_INTERPRETATION` is unset, `Parameters.return_parameters` defaults to `'CDC'`. Current production code (which calls `return_parameters(...)` without the new parameter) continues to behave identically — the env-var read happens only inside `return_parameters` if no explicit parameter was passed.

## 4. Calibration artifact storage

The CDC calibration is in `Result_AllTarget.txt` and `DiscFacEstim_CRRA_2.0_R_1.01*.txt`. The ESC calibration was pre-staged onto `_TM-vs-MC` in pre-refactor item 1 (commit `db48d328`) under `_ESC` suffixed names.

Stage 1 Phase D simply teaches `Parameters.py` to load the right files based on interpretation; no further file work is needed.

The `_ESC`-suffixed files are trusted as-is for operational `Parameters.py` selection. They are also used as the *target* for the Phase B Step-1 ESC re-estimation test: running Step-1 estimation under the new ESC code path should reproduce the pinned ESC ς (=0.26718) within ±0.5% relative — that's the one-direction validation against Edmund's branch's published estimate. Step-2 (β/∇) re-estimation under ESC is more expensive (~hours of compute) and is deferred to a Stage 1 follow-up unless explicitly requested in scope.

## 5. Implementation phases

### Stage 1 phases (additive, debugging-friendly, CDC-preserving)

#### Stage 1, Phase A — class hierarchy scaffold (~half day)

1. Add the `CDCAggFiscalType = AggFiscalType` alias and `class ESCAggFiscalType(AggFiscalType)` definition at the bottom of `AggFiscalModel.py` — see §3.1 for the exact additions.
2. **No changes to `AggFiscalType` itself.** No call-site changes.
3. Run after every commit during this phase: `pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py`. This catches accidental CDC perturbation in seconds.

##### Phase A — evidence required before proceeding to Phase B

Cost-ordered. Do NOT begin tier T+1 until every check in tier T has passed.

###### Tier 1 — instant (~seconds)

**T1.1. CDC pin still passes:**
```bash
pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py -v
```
Expected: every assertion `PASSED`.

**T1.2. Class hierarchy is well-formed:**
```bash
cd Code/HA-Models/FromPandemicCode && python -c "
from AggFiscalModel import AggFiscalType, CDCAggFiscalType, ESCAggFiscalType
assert CDCAggFiscalType is AggFiscalType, 'alias broken'
assert issubclass(ESCAggFiscalType, AggFiscalType), 'ESC inheritance broken'
assert ESCAggFiscalType is not AggFiscalType, 'ESC accidentally aliased to AggFiscalType'
assert 'get_poststates' in ESCAggFiscalType.__dict__, 'ESC.get_poststates override missing'
print('OK')
"
```
Expected: `OK`.

**T1.3. Additive-only invariant holds:**
```bash
git diff <pre-stage-1-commit>..HEAD -- Code/HA-Models/FromPandemicCode/AggFiscalModel.py
```
Expected: only added lines (starting `+`); no `-` lines except trailing-whitespace cleanup.

**T1.4. Manual diff review:** scroll the diff produced by T1.3. Confirm:
- No method moved out of `class AggFiscalType:`.
- No body of any existing method/function is edited.
- No decorators added/removed on existing methods.
- The additions live entirely at the bottom of the file (after `class AggFiscalType:` is fully closed).

**Tier-1 failure handlers:**
- T1.1 failure → revert the additions; investigate why an additive change perturbed CDC. Most likely cause: the `ESCAggFiscalType` definition pulled in an import that changed module-level state, or an inadvertent module-init monkey-patch.
- T1.2 failure → typo in alias or subclass declaration; fix and re-run.
- T1.3 or T1.4 failure → an inline edit slipped in despite intention; revert it. The additive-only invariant is non-negotiable in Stage 1.

###### Tier 2 — cheap (~10 seconds to a few minutes)

Run only if all tier-1 checks passed.

**T2.1. Nano smoke test runs (~10 seconds):**
```bash
./reproduce.sh --comp nano
```
Expected: exit 0. Confirms the run pipeline still operates.

**T2.2. Wider test suite still passes (~minutes):**
```bash
pytest Code/HA-Models/FromPandemicCode/test_*.py
```
Expected: no failures. (Pre-existing failures must be documented and skipped; no NEW failures permitted.)

**Tier-2 failure handlers:**
- T2.1 failure → run pipeline broke; check the nano log under `reproduce/logs/`.
- T2.2 failure → a pre-existing test that was working broke because of the additions. Likely cause: subclass discovery in test collection, or `AggFiscalType.__subclasses__()` semantics changing. Investigate.

(No tier-3 or tier-4 checks for Phase A — the additive-only invariant is the gate, not a full anchor reproduction.)

**Sign-off (all must be `[x]` to proceed to Phase B):**
- [ ] T1.1 `test_cdc_baseline_pin.py` passes
- [ ] T1.2 class-hierarchy script prints `OK`
- [ ] T1.3 `git diff` shows only additions
- [ ] T1.4 manual review confirms no inline edits
- [ ] T2.1 `--comp nano` exits 0
- [ ] T2.2 wider test suite passes

#### Stage 1, Phase B — `Estimation_BetaNablaSplurge.py` parameterization (~1-2 days)

1. Add `interpretation='CDC'` parameter to `FagerengObjFunc` (defaulting to `'CDC'` so existing callers behave identically).
2. Add ESC counterparts to the helpers landed by the prep:
   - `_wealth_under_esc(...)` — sibling to the prep-landed `_wealth_under_cdc`.
   - `_lottery_consumption_under_esc(...)` — sibling to `_lottery_consumption_under_cdc`.
   - `_esc_asset_rule(...)` — sibling to `_cdc_asset_rule` (used by `ESCAggFiscalType.get_poststates` if it ends up needing structured state-update logic; the Phase A scaffold uses HARK default which doesn't need this helper, but the helper is defined for completeness and Stage 2 symmetry).
3. At each interpretive site (lines 219, 228, 230, 287-347, 461 — five sites total), wrap the existing CDC code in `if interpretation == 'CDC':` and add the ESC branch in `else:`. **The CDC branch body is the exact current code (unchanged)**; only the surrounding `if` is added; the ESC branch is added.
4. Run after every commit during this phase: `pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py`.

##### Phase B — evidence required before proceeding to Phase C (or directly to Phase D if mitigation #1)

Cost-ordered. Do NOT begin tier T+1 until every check in tier T has passed.

###### Tier 1 — instant (~seconds)

**T1.1. CDC pin still passes:**
```bash
pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py -v
```

**T1.2. New ESC helpers exist with matching signatures:**
```bash
grep -n '^def _wealth_under_esc\|^def _lottery_consumption_under_esc\|^def _esc_asset_rule' \
    Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py \
    Code/HA-Models/FromPandemicCode/AggFiscalModel.py
```
Expected: three matches; signatures correspond to the prep-landed CDC siblings (same arg names + count, in the same order).

**T1.3. Manual diff review:** `git diff <pre-Phase-B>..HEAD -- Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py`. Confirm:
- At each of the 5 interpretive sites, the original CDC code is wrapped in `if interpretation == 'CDC':` with the body bytes unchanged (only indentation added).
- The ESC `else:` branch is added with calls to `_wealth_under_esc`/`_lottery_consumption_under_esc`/`_esc_asset_rule`.
- No edits to any code outside the 5 sites.

**Tier-1 failure handlers:**
- T1.1 failure → CDC body got perturbed inside the `if`-wrap. Bisect the diff to find the off-by-one or inadvertent edit. Most likely: a stray edit when re-indenting.
- T1.2 failure → ESC helper missing or misnamed; add/rename.
- T1.3 failure → an inline edit slipped in; revert.

###### Tier 2 — cheap (~minutes)

Run only if all tier-1 checks passed.

**T2.1. Wider test suite still passes:**
```bash
pytest Code/HA-Models/FromPandemicCode/test_*.py
```

**T2.2. Step-1 CDC re-estimation on Reduced_Run reproduces pinned ς (~minutes):**
```bash
cd Code/HA-Models/Target_AggMPCX_LiquWealth
# Step-1 driver, no interpretation flag (defaults to CDC), Reduced_Run scope:
HAFISCAL_PARAMETRIZATION=Reduced_Run python Estimation_BetaNablaSplurge.py
# (Or whatever invocation Phase B exposes for swapping parametrization. Default
#  Estimation_BetaNablaSplurge.py uses Baseline; Phase B should add a way to
#  invoke at Reduced_Run for cheaper iteration.)
python -c "
d = eval(open('<wherever-Phase-B-puts-Reduced_Run-CDC-output>').read())
expected = 0.2608750140503139  # CDC ς from Baseline; Reduced_Run should be close
assert abs(d['splurge'] - expected) / expected < 0.02, \
    f\"CDC ς drift on Reduced_Run: {d['splurge']} vs {expected}, rel diff {abs(d['splurge']-expected)/expected:.4f}\"
print(f\"OK: CDC ς (Reduced_Run) = {d['splurge']}\")
"
```
Expected: within ±2% relative of Baseline-pin (Reduced_Run is a smaller sample so tolerance is wider than the ±0.5% used for Baseline).

**T2.3. Step-1 ESC re-estimation on Reduced_Run reproduces pinned ESC ς (~minutes):**
```bash
HAFISCAL_INTERPRETATION=ESC HAFISCAL_PARAMETRIZATION=Reduced_Run python Estimation_BetaNablaSplurge.py
python -c "
d = eval(open('<wherever-Phase-B-puts-Reduced_Run-ESC-output>').read())
expected = 0.26718  # from Result_AllTarget_ESC.txt (Edmund's branch, commit 8d6255dd, Baseline-fit)
assert abs(d['splurge'] - expected) / expected < 0.02, \
    f\"ESC ς drift on Reduced_Run: {d['splurge']} vs {expected}, rel diff {abs(d['splurge']-expected)/expected:.4f}\"
print(f\"OK: ESC ς (Reduced_Run) = {d['splurge']}\")
"
```
Expected: within ±2% relative of Edmund's Baseline pin.

**Tier-2 failure handlers:**
- T2.1 failure → wider test suite regression; investigate.
- T2.2 failure → CDC branch logic accidentally edited inside the `if interpretation == 'CDC':` block (e.g., a CDC-specific call was moved into the ESC branch); review the wrapping carefully.
- T2.3 failure → ESC formula incorrect. Check against `models_CDC_and_ESC.md` §5 and against `origin/maintain_bound_pair_fix_splurge`'s implementation. Most likely culprit: wrong sign or wrong `(1−ς)` factor placement.

###### Tier 3 — moderate (~30 minutes each, optional)

Run only if all tier-1 and tier-2 checks passed. These tighten the pin against Baseline-scale; recommended if you want maximum confidence before Phase F's tier-4 ESC anchor run, but not strictly required if the Reduced_Run tier-2 results were within tolerance.

**T3.1. Step-1 CDC re-estimation on Baseline reproduces pinned ς (~30 min):**
```bash
cd Code/HA-Models/Target_AggMPCX_LiquWealth
python Estimation_BetaNablaSplurge.py  # default = Baseline = full 21 types
python -c "
d = eval(open('Result_AllTarget.txt').read())
expected = 0.2608750140503139
assert abs(d['splurge'] - expected) / expected < 0.005, \
    f\"CDC ς drift: {d['splurge']} vs {expected}, rel diff {abs(d['splurge']-expected)/expected:.4f}\"
print(f\"OK: CDC ς = {d['splurge']}\")
"
```
Expected: within ±0.5% relative of pinned value.

**T3.2. Step-1 ESC re-estimation on Baseline reproduces pinned ESC ς (~30 min):**
```bash
HAFISCAL_INTERPRETATION=ESC python Estimation_BetaNablaSplurge.py
python -c "
d = eval(open('<wherever-Phase-B-puts-Baseline-ESC-output>').read())
expected = 0.26718  # from Result_AllTarget_ESC.txt
assert abs(d['splurge'] - expected) / expected < 0.005, \
    f\"ESC ς drift: {d['splurge']} vs {expected}, rel diff {abs(d['splurge']-expected)/expected:.4f}\"
print(f\"OK: ESC ς = {d['splurge']}\")
"
```
Expected: within ±0.5% relative of Edmund's pin.

**Tier-3 failure handlers:**
- Same as tier-2 but harder to diagnose because runtime is longer; tier-3 failure that didn't show up in tier-2 likely indicates a Reduced_Run-vs-Baseline-specific issue (different number-of-types arithmetic, different beta-distribution discretization, etc.).

(No tier-4 checks for Phase B — Step-2 β/∇ re-estimation is a separate ~2-day follow-up tracked in §9 as out-of-scope for Stage 1.)

**Sign-off:**
- [ ] T1.1 CDC pin passes
- [ ] T1.2 ESC helpers exist with matching signatures
- [ ] T1.3 Manual diff review confirms wrap-only changes
- [ ] T2.1 Wider test suite passes
- [ ] T2.2 Step-1 CDC ς on Reduced_Run reproduces within ±2%
- [ ] T2.3 Step-1 ESC ς on Reduced_Run reproduces within ±2%
- [ ] T3.1 (optional) Step-1 CDC ς on Baseline reproduces within ±0.5%
- [ ] T3.2 (optional) Step-1 ESC ς on Baseline reproduces within ±0.5%

#### Stage 1, Phase C — `tm_methods.py` dispatch (DEFERRED if mitigation #1; ~3-5 days otherwise)

If mitigation #1 (the recommended scope cut) is taken, this phase is deferred to a Stage 1 follow-up; ESC users go through MC only. The Stage 1 acceptance check accommodates this: `./reproduce.sh --comp full --mc-only --interpretation esc` is the gating ESC test, not the TM-only variant.

If included:

1. Add `_build_period_tm_a_esc` function paralleling `_build_period_tm_a` (which IS the CDC kernel in Stage 1; remains so).
2. Add `_build_experiment_period_tm_a_esc` likewise.
3. The wrapper functions (`build_tm_agg_fiscal_a`, `propagate_experiment_tm_a`, etc.) dispatch based on `isinstance(agent, ESCAggFiscalType)`. The CDC branch is unchanged: when no ESC agent is in the list, the existing CDC code path is hit unchanged.

##### Phase C — evidence required before proceeding to Phase D (only if Phase C is in scope)

If mitigation #1 was taken, skip this entire section; proceed from Phase B's evidence directly to Phase D.

Cost-ordered. Do NOT begin tier T+1 until every check in tier T has passed.

###### Tier 1 — instant (~seconds)

**T1.1. CDC pin still passes:**
```bash
pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py -v
```

**T1.2. Manual diff review:** `_build_period_tm_a` body byte-identical to pre-Phase-C; `_build_period_tm_a_esc` is new; wrappers dispatch on `isinstance(agent, ESCAggFiscalType)`; no body-edit of existing CDC kernel functions.

**Tier-1 failure handlers:**
- T1.1 failure → an existing CDC kernel function was perturbed; bisect the diff; revert.
- T1.2 failure → an inline edit slipped in; revert.

###### Tier 2 — cheap (~minutes)

Run only if all tier-1 checks passed.

**T2.1. Wider test suite still passes:**
```bash
pytest Code/HA-Models/FromPandemicCode/test_*.py
```

###### Tier 3 — moderate (~25 minutes each)

Run only if all tier-1 and tier-2 checks passed.

**T3.1. CDC TM multipliers reproduce CDC anchor bit-identically:**
```bash
./reproduce.sh --comp full --tm-only
diff <(cat Code/HA-Models/FromPandemicCode/Tables/Baseline/Multiplier.tex) \
     <(git show reproduce-20260425-comp-full-tm-only:Code/HA-Models/FromPandemicCode/Tables/Baseline/Multiplier.tex)
```
Expected: empty diff (zero exit code).

**T3.2. ESC TM multipliers produce sane numbers:**
```bash
HAFISCAL_INTERPRETATION=ESC ./reproduce.sh --comp full --tm-only
cat Code/HA-Models/FromPandemicCode/Tables/Baseline/Multiplier.tex
```
Expected: multipliers in the 0.7-1.3 range; sanity-check against Edmund's branch's headline multipliers (commit `8d6255dd`: Check 1.070, UI 1.139, TaxCut 0.977 with AD).

**Tier-3 failure handlers:**
- T3.1 failure → the existing CDC kernel was perturbed despite tier-1 passing — possible if perturbation only manifests in full-pipeline scale (e.g., RNG state ordering across many calls). Bisect with smaller `--comp` modes first.
- T3.2 failure → ESC kernel formula incorrect; check against §2.4 and against Edmund's branch.

**Sign-off:**
- [ ] T1.1 CDC pin passes
- [ ] T1.2 Manual diff review confirms additive-only changes
- [ ] T2.1 Wider test suite passes
- [ ] T3.1 CDC TM `Multiplier.tex` bit-identical to anchor
- [ ] T3.2 ESC TM multipliers in sanity range

#### Stage 1, Phase D — calibration-file selection (~half day)

1. Modify `Parameters.return_parameters` to accept an `interpretation=None` parameter.
2. The cascade: `interpretation` arg → `os.environ['HAFISCAL_INTERPRETATION']` → `'CDC'` (default).
3. When `interpretation == 'CDC'`, the function returns *exactly the same dict as today* (loads from `Result_AllTarget.txt` + `DiscFacEstim_*.txt`). When `interpretation == 'ESC'`, loads from `Result_AllTarget_ESC.txt` + `DiscFacEstim_*_ESC.txt` (pre-staged).

##### Phase D — evidence required before proceeding to Phase E

Cost-ordered. Do NOT begin tier T+1 until every check in tier T has passed.

###### Tier 1 — instant (~seconds)

**T1.1. CDC pin still passes:**
```bash
pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py -v
```

**T1.2. `return_parameters()` (no args) byte-equivalent to `interpretation='CDC'`:**
```bash
cd Code/HA-Models/FromPandemicCode && python -c "
from Parameters import return_parameters
import json
p_default = return_parameters('Baseline')
p_cdc = return_parameters('Baseline', interpretation='CDC')
assert json.dumps(p_default, sort_keys=True, default=str) == \
       json.dumps(p_cdc, sort_keys=True, default=str), \
    'CDC dict differs from default dict — Phase D broke default behavior'
print('OK')
"
```
Expected: `OK`.

**T1.3. `return_parameters(interpretation='ESC')` returns ESC calibration:**
```bash
python -c "
from Parameters import return_parameters
p_esc = return_parameters('Baseline', interpretation='ESC')
# ESC ς from Result_AllTarget_ESC.txt = 0.26718
assert abs(p_esc['Splurge'] - 0.26718) < 0.001, \
    f\"ESC ς wrong: {p_esc['Splurge']}\"
p_cdc = return_parameters('Baseline', interpretation='CDC')
assert p_cdc['Splurge'] != p_esc['Splurge'], 'CDC and ESC ς accidentally identical'
print(f\"OK: ESC ς = {p_esc['Splurge']}, CDC ς = {p_cdc['Splurge']}\")
"
```

**T1.4. No cross-contamination in single process:**
```bash
python -c "
from Parameters import return_parameters
p_cdc1 = return_parameters('Baseline', interpretation='CDC')
p_esc = return_parameters('Baseline', interpretation='ESC')
p_cdc2 = return_parameters('Baseline', interpretation='CDC')
assert p_cdc1['Splurge'] == p_cdc2['Splurge'], \
    'CDC contaminated by intervening ESC call'
assert p_cdc1['Splurge'] != p_esc['Splurge'], \
    'CDC and ESC values accidentally identical'
print('OK')
"
```

**T1.5. Env-var fallback works:**
```bash
HAFISCAL_INTERPRETATION=ESC python -c "
from Parameters import return_parameters
p = return_parameters('Baseline')  # no interpretation arg; should pick up env
assert abs(p['Splurge'] - 0.26718) < 0.001, \
    f\"env-var fallback broken: {p['Splurge']}\"
print('OK')
"
```

**Tier-1 failure handlers:**
- T1.2 failure → `Parameters.return_parameters` introduced a side effect or changed default-path behavior. Bisect the function.
- T1.3 failure → ESC files not loaded; check the `_ESC` file paths and the `Parameters.py` cascade.
- T1.4 failure → module-level state is being mutated by `return_parameters`; refactor to be re-entrant (no module-level caches that retain interpretation state).
- T1.5 failure → env-var read happens at module-import time instead of call time; move it inside the function body.

###### Tier 2 — cheap (~minutes)

Run only if all tier-1 checks passed.

**T2.1. Wider test suite still passes:**
```bash
pytest Code/HA-Models/FromPandemicCode/test_*.py
```

(No tier-3 or tier-4 checks for Phase D — Parameters.py changes don't justify a full-pipeline reproduction; that gate lives in Phase E.)

**Sign-off:**
- [ ] T1.1 CDC pin passes
- [ ] T1.2 Default dict == CDC dict
- [ ] T1.3 ESC dict has ESC ς
- [ ] T1.4 No cross-contamination
- [ ] T1.5 Env-var fallback works
- [ ] T2.1 Wider test suite passes

#### Stage 1, Phase E — `Simulate.py` dispatch + reproduce.sh integration (~1 day)

1. `Simulate.py` reads `interpretation = Run_Dict.get('interpretation', os.environ.get('HAFISCAL_INTERPRETATION', 'CDC'))`. When `interpretation == 'CDC'`, instantiates `AggFiscalType` (= `CDCAggFiscalType` alias) — same as today. When `'ESC'`, instantiates `ESCAggFiscalType`.
2. Add `--interpretation cdc|esc` flag to `reproduce.sh` that sets `HAFISCAL_INTERPRETATION` for the run.
3. Add a `code_state.interpretation` field to the manifest schema so anchored runs record which interpretation produced them.

##### Phase E — evidence required before proceeding to Phase E2

Cost-ordered. Do NOT begin tier T+1 until every check in tier T has passed. Tier 4 is a multi-hour ESC run; only commit to it once tiers 1-3 are clean.

###### Tier 1 — instant (~seconds)

**T1.1. CDC pin still passes:**
```bash
pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py -v
```

**T1.2. Manifest schema includes interpretation field:**
```bash
grep -n 'interpretation' reproduce/build_manifest.py | head -5
```
Expected: at least one match showing the field is written into the manifest.

**Tier-1 failure handlers:**
- T1.1 failure → CDC perturbation; bisect.
- T1.2 failure → manifest-schema update incomplete; finish the schema work before running anything that produces a manifest.

###### Tier 2 — cheap (~10 seconds to a few minutes)

Run only if all tier-1 checks passed.

**T2.1. Nano smoke (no interpretation flag) exits 0** (~10 seconds):
```bash
./reproduce.sh --comp nano
```

**T2.2. Nano smoke with `--interpretation cdc` exits 0** (~10 seconds):
```bash
./reproduce.sh --comp nano --interpretation cdc
```

**T2.3. Nano smoke with `--interpretation esc` exits 0** (~10 seconds, possibly more):
```bash
./reproduce.sh --comp nano --interpretation esc
```
Expected: exit 0. (This is the cheapest test that ESC actually runs end-to-end without crashing — much cheaper than T4.1 and catches gross-construction errors immediately.)

**T2.4. Wider test suite still passes** (~minutes):
```bash
pytest Code/HA-Models/FromPandemicCode/test_*.py
```

**T2.5. Manifest interpretation field populated** (~seconds, run after T2.1 produced a manifest):
```bash
jq '.code_state.interpretation' reproduce/run-manifests/comp_nano_*.json | tail -1
```
Expected: prints `"CDC"` (for T2.1 and T2.2) and `"ESC"` (for T2.3).

**Tier-2 failure handlers:**
- T2.1 failure → CDC nano broke despite T1.1 passing. Check the run log; likely the `Simulate.py` dispatch logic broke even though pin tests didn't catch it (because pin tests don't exercise the run-pipeline integration).
- T2.3 failure (non-zero exit) → ESC code path bug. Catches issues that would otherwise only surface in T4.1 after hours of compute. Look at the nano log for the specific failure.
- T2.5 failure → manifest field write logic is wrong; fix before tier-3.

###### Tier 3 — moderate (~25 minutes)

Run only if all tier-1 and tier-2 checks passed.

**T3.1. Default (no interpretation flag) reproduces CDC anchor bit-identically:**
```bash
./reproduce.sh --comp full --tm-only
python reproduce/verify_anchor.py reproduce-20260425-comp-full-tm-only \
    || (echo "BIT-IDENTITY FAIL; do not proceed to tier 4"; exit 1)
```
(Note: `reproduce/verify_anchor.py` does not yet exist; to be written as part of Phase E if needed, OR substitute with manual sha256 comparison against the anchor manifest's `outputs` block.)
Expected: all output sha256s match anchor manifest.

**T3.2. `--interpretation cdc` matches default:**
```bash
./reproduce.sh --comp full --tm-only --interpretation cdc
python reproduce/verify_anchor.py reproduce-20260425-comp-full-tm-only
```
Expected: bit-identical to anchor (same as T3.1).

**Tier-3 failure handlers:**
- T3.1 or T3.2 failure → CDC code path perturbed despite Phase A-D additive discipline. Critical — revert and investigate. Use the per-output sha256 comparison to identify which output(s) drifted; that narrows the search.

(No tier-4 checks for Phase E — the ESC end-to-end MC welfare-6 anchor lives in the dedicated Phase F. Phase E ends after the tier-3 CDC anchor reproduction.)

**Sign-off:**
- [ ] T1.1 CDC pin passes
- [ ] T1.2 Manifest schema includes interpretation field
- [ ] T2.1 CDC nano exits 0
- [ ] T2.2 `--interpretation cdc` nano exits 0
- [ ] T2.3 `--interpretation esc` nano exits 0
- [ ] T2.4 Wider test suite passes
- [ ] T2.5 Manifest interpretation field populated correctly
- [ ] T3.1 Default reproduces CDC anchor bit-identically
- [ ] T3.2 `--interpretation cdc` matches default

#### Stage 1, Phase E2 — side-by-side comparison driver (~half day)

Add a small driver script `Code/HA-Models/FromPandemicCode/run_cdc_vs_esc_comparison.py` that, in a single Python process:

1. Builds CDC parameters and a CDC economy; solves + simulates baseline.
2. Builds ESC parameters and an ESC economy; solves + simulates baseline.
3. Reports CDC and ESC headline numbers (multipliers, K/Y, welfare-6 cells) side-by-side in a single table.

This is the most useful comparison mode for the paper-facing analysis: a deterministic, single-process, single-RNG-seed way to measure CDC↔ESC differences without comparing across separate runs (which would have inherent sampling-noise jitter).

##### Phase E2 — evidence required before declaring Stage 1 complete

Cost-ordered. Do NOT begin tier T+1 until every check in tier T has passed. Tier 4 (re-running both anchors from their recipes) is recommended as a one-time end-of-Stage-1 check; it can be skipped per-phase if Phase E's tier-3/4 already passed cleanly.

###### Tier 1 — instant (~seconds)

**T1.1. CDC pin still passes:**
```bash
pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py -v
```

**T1.2. Side-by-side driver script exists and is importable:**
```bash
cd Code/HA-Models/FromPandemicCode && python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('drv', 'run_cdc_vs_esc_comparison.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('OK')
"
```
Expected: `OK`. Catches syntax errors / missing imports without running the expensive solve+simulate.

###### Tier 2 — cheap (~minutes; possibly tens of minutes for solve+sim)

Run only if all tier-1 checks passed.

**T2.1. Side-by-side driver runs end-to-end:**
```bash
cd Code/HA-Models/FromPandemicCode
python run_cdc_vs_esc_comparison.py
```
Expected: exit 0; prints a comparison table to stdout.

**T2.2. Comparison table format check:** the printed table has 9 welfare-6 cells per interpretation (Check/UI/TaxCut × Rec=0/Rec=1/Rec=1+AD), plus headline multipliers, plus K/Y. Both columns populated.

**T2.3. CDC column matches CDC anchor:** compare CDC column values to the CDC anchor's `welfare6.tex` cells. Match within ±0.5% (sampling-noise tolerance).

**T2.4. ESC column matches ESC anchor:** compare ESC column to the ESC anchor produced in Phase E. Match within ±0.5%.

**Tier-2 failure handlers:**
- T2.3 failure → CDC numbers in the side-by-side driver don't match the anchor. Likely cause: the driver's CDC path is using slightly different RNG seeding or scenario configuration than `reproduce.sh`. Investigate the driver's setup.
- T2.4 failure → similar for ESC.

(No tier-3 within Phase E2 — the moderate-cost full-anchor reproductions live in Phase E and at the Stage 1 acceptance gate below.)

(No tier-3 or tier-4 checks for Phase E2 — the moderate-cost full-anchor reproductions live in Phase E's tier 3, and the tier-4 ESC anchor production + recipe-replay validation live in the dedicated Phase F.)

**Note on T2.4:** the ESC anchor referenced here doesn't exist yet at the end of Phase E2 (it's produced by Phase F). For Phase E2 sign-off, T2.4 compares against Edmund's branch reference values from `models_CDC_and_ESC.md` (commit `8d6255dd`); see Phase F for the proper ESC anchor reproduction check.

**Sign-off (all must be `[x]` to proceed to Phase F):**
- [ ] T1.1 CDC pin passes
- [ ] T1.2 Driver script importable
- [ ] T2.1 Driver runs to completion
- [ ] T2.2 Table format correct
- [ ] T2.3 CDC column matches CDC anchor
- [ ] T2.4 ESC column matches Edmund-branch reference (within ±5%; full anchor comes in Phase F)

#### Stage 1, Phase F — welfare estimation + ESC anchor (~6-12h compute, one calendar day)

Phase F is the ONLY Stage 1 phase that runs at tier-4 cost. It is structured as a dedicated phase precisely so the expensive MC welfare-6 run is not gated on cheaper integration testing — and so the cheaper testing in Phases A-E2 is not gated on having an ESC anchor.

**Run only after all phases A through E2 are signed off.** A failure here typically indicates a bug introduced in Phases A-E2 that escaped cheaper detection — bisect through prior commits before re-running the expensive computation. The cheap tests in those phases (nano, mini, single-type GLP) may need new checks added to catch what F caught.

##### Phase F — logging setup (mandatory before kicking off the run)

Phase F is the only Stage 1 phase that runs unattended for hours. The user's only window into progress is the log file (per §1.6). Before running the anchor invocation:

1. Author `reproduce/cdc_esc_heartbeat.sh` — a small loop that, every 10-15 minutes:
   - Counts completed scenarios in `welfare6_parallel_logs/Baseline_esc/` (look for `[base] saved:` / `[<scenario>] saved:` lines).
   - Estimates progress percentage of the latest in-progress scenario from its log file.
   - Writes one `[ALIVE]` line to `reproduce/logs/cdc-esc-refactor.log`.
2. Confirm the executor (or a wrapper) writes `[BG   ]` to the log when kicking off the anchor run, and updates `cdc-esc-status.json` to `state: "background"` with `background_pid` set.
3. Tell the user the monitoring commands (from §1.6) to use during the run:
   ```bash
   # In one terminal — high-level narrative:
   tail -f reproduce/logs/cdc-esc-refactor.log

   # In another terminal — only attention-grabbing events:
   tail -f reproduce/logs/cdc-esc-refactor.log | grep --color=always -E '\[HALT \]|\[FAIL \]|\[ALIVE\]|\[DONE \]'

   # On demand — current state:
   cat reproduce/logs/cdc-esc-status.json | python -m json.tool
   ```

##### Phase F — work

1. Run the ESC end-to-end MC anchor in background:
   ```bash
   ./reproduce.sh --comp full --mc-only --interpretation esc --auto-commit
   ```
   Wall: ~6-12 hours. Run inside `tmux` or via `nohup … &`; monitor via `tail -f reproduce/logs/latest.log`.

2. Inspect outputs:
   - `Code/HA-Models/FromPandemicCode/Tables/Baseline/welfare6.tex` populated.
   - `Code/HA-Models/FromPandemicCode/Tables/Baseline/welfare6_parallel_summary.json` shows all 12 scenarios `rc=0`.
   - Manifest at `reproduce/run-manifests/comp_full_*_mc-only.json` has `code_state.interpretation == "ESC"`.

3. Capture ESC pin values from the run for use in Stage 2 Phase I (`test_esc_baseline_pin.py`):
   - `aLvl[period, agent_index]` at a specific (period, agent) pin.
   - K/Y under ESC asset rule at a specific period.
   - Cumulative `cLvl_splurge` over a short horizon.
   - Per-agent `aNrm` post-`get_poststates` for the first period.

4. The `--auto-commit` flag stages the manifest + recipe + pip-freeze + log + output dirs and creates the commit + tag automatically. Push:
   ```bash
   git push origin <branch> reproduce-<date>-comp-full-mc-only-esc
   ```

##### Phase F — evidence required to declare Stage 1 complete

Tier 4 only — by construction, F has no cheaper checks because all the cheap ones already passed in A-E2.

###### Tier 4 — expensive (~6-12 hours main run + ~30 min recipe replays)

**T4.1. ESC anchor run completed cleanly:** exit 0; all 12 scenarios `rc=0` in `welfare6_parallel_summary.json`; `welfare6.tex` produced; manifest auto-committed with `code_state.interpretation == "ESC"`.

**T4.2. ESC welfare-6 cells in sanity range vs Edmund's branch (commit `8d6255dd`):**

| | Check | UI | TaxCut |
|---|---|---|---|
| Rec=0 AD=0 | 0.97 | 0.85 | 0.99 |
| Rec=1 AD=0 | 1.01 | 1.46 | 1.00 |
| Rec=1 AD=1 | 1.01 | 1.36 | 1.00 |

Acceptance: no-AD cells (top two rows) within ±2% relative (target-matching identity per `BUGS_private/HAFiscal_splurge_budget_inconsistency/why_results_match_at_target.md`); Rec=1 AD=1 cells within ±5% relative (off-target dynamics tolerance, accounting for intervening bug fixes that affect both interpretations).

**T4.3. ESC pins captured for Stage 2 Phase I:** values printed and saved to a snippet that can be hardcoded into `test_esc_baseline_pin.py` later. Suggested to print a `# ESC PIN VALUES (captured <date>):` block to stdout at end of run.

**T4.4. ESC anchor reproducible from its own recipe:**
```bash
git worktree add /tmp/repro-esc <esc-anchor-tag>
cd /tmp/repro-esc
bash reproduce/run-manifests/<esc-anchor>.reproduce-recipe.sh
# Should reproduce welfare6.tex bit-identically (~6-12 hours).
git worktree remove /tmp/repro-esc
```

**T4.5. CDC anchor still reproduces from its recipe (regression check):** confirms that Stage 1 work didn't subtly break the CDC anchor's recipe machinery.
```bash
git worktree add /tmp/repro-cdc reproduce-20260425-comp-full-tm-only
cd /tmp/repro-cdc
bash reproduce/run-manifests/comp_full_20260425-2128_tm-only.reproduce-recipe.sh
# Should reproduce CDC anchor bit-identically (~25 min).
git worktree remove /tmp/repro-cdc
```

**Tier-4 failure handlers:**
- T4.1 failure (non-zero exit) → ESC code path bug. Check the per-scenario logs in `welfare6_parallel_logs/Baseline*/`. Bisect through Phase A-E2 commits to find which one introduced the bug. Add a new tier-2 check in the offending phase to prevent regression.
- T4.2 failure (out of sanity range) → ESC formula bug. Cross-check with Edmund's branch by running its MC and comparing the same scenario set. Most likely cause: kernel formula error (only relevant if Phase C was included), or asset-rule error in `ESCAggFiscalType.get_poststates`.
- T4.4 failure → ESC recipe broken; investigate `reproduce/build_manifest.py` for what was captured.
- T4.5 failure → CDC recipe regression — Stage 1 changed something that broke the CDC anchor's reproducibility despite the CDC pin still passing. This is bad; investigate immediately. Likely cause: a change to `reproduce.sh` or `build_manifest.py` that affects how recipes are emitted or replayed.

**Sign-off (all must be `[x]` to declare Stage 1 complete and commit to Stage 2):**
- [ ] T4.1 ESC anchor run completed cleanly
- [ ] T4.2 ESC welfare-6 cells in sanity range
- [ ] T4.3 ESC pins captured for Stage 2 Phase I
- [ ] T4.4 ESC anchor reproduces from recipe
- [ ] T4.5 CDC anchor still reproduces from recipe

#### Stage 1 acceptance gate

Before declaring Stage 1 done and committing to Stage 2:
- All Phase A-F tests above are signed off.
- ESC anchor `reproduce-<date>-comp-full-mc-only-esc` exists, is pushed to origin, and is reachable from `_TM-vs-MC` after merge.
- CDC anchor `reproduce-20260425-comp-full-tm-only` still reproduces (T4.5).
- The side-by-side driver report (Phase E2) is reviewed and the headline CDC↔ESC differences are recorded somewhere paper-facing (a memo, a table in `models_CDC_and_ESC.md`'s "Implementation status" section, etc.) — this is the actual deliverable of Stage 1.

### Stage 2 phases (symmetric polish, behavior-preserving)

Stage 2 begins after Stage 1's acceptance gate is met and both anchors are pushed. Stage 2 can be done in a separate session — it's not on the critical path for the paper.

Stage 2's evidence pattern is simpler than Stage 1's because the test surface is now both pin tests + both anchor reproductions. Each Stage 2 phase ends with: "Both pin tests pass; both anchors reproduce bit-identically." That single check (~minutes for the pins; ~hours combined for both anchor reproductions) is sufficient evidence — the additive-only invariant of Stage 1 is replaced by the symmetric-behavior-preservation invariant of Stage 2.

#### Stage 2, Phase G — promote `AggFiscalType` to abstract base (~half day)

1. In `AggFiscalModel.py`, rename `AggFiscalType` → `AbstractAggFiscalType`. Use `from abc import abstractmethod` to mark `get_poststates` (and any other interpretation-specific methods) as abstract.
2. Move the existing CDC `get_poststates` body from `AbstractAggFiscalType` into `class CDCAggFiscalType(AbstractAggFiscalType):` (which now becomes a real class, replacing the Stage 1 alias).
3. Remove the Stage 1 alias `CDCAggFiscalType = AggFiscalType`.
4. ESC's `get_poststates` (added in Stage 1 Phase A) stays where it is.
5. Update all call sites that used bare `AggFiscalType` to use `CDCAggFiscalType` explicitly: `Simulate.py`, `EstimAggFiscalMAIN.py`, `welfare6_scenario.py`, `run_welfare6_parallel.py`, `test_*.py` files. Estimated ~30 touches.

##### Phase G — evidence

```bash
pytest Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py
pytest Code/HA-Models/FromPandemicCode/test_esc_baseline_pin.py
./reproduce.sh --comp full --tm-only && python reproduce/verify_anchor.py reproduce-20260425-comp-full-tm-only
./reproduce.sh --comp full --mc-only --interpretation esc && python reproduce/verify_anchor.py <esc-anchor-tag>
grep -rn '\bAggFiscalType\b' Code/ | grep -v Abstract | grep -v 'CDC\|ESC'
# Last grep should produce NO output (only Abstract/CDC/ESC variants remain).
```

#### Stage 2, Phase H — symmetric helper-function naming (~half day)

Stage 1 will have established whether the paired-siblings pattern (`_wealth_under_cdc` + `_wealth_under_esc`, `_cdc_asset_rule` + `_esc_asset_rule`) reads cleanly or whether a dispatcher pattern (`_wealth(interp, ...)`, `_asset_rule(interp, ...)`) is cleaner. Phase H makes the final call.

If paired siblings: audit completeness. Every `_*_under_cdc` helper has a matching `_*_under_esc`. Every `_cdc_*` rule has a matching `_esc_*`. No "CDC default" semantics in any helper signature. Note that the prep work used two patterns simultaneously (`_wealth_under_cdc` vs. `_cdc_asset_rule`) — Phase H picks one and applies consistently.

If dispatcher: collapse the pairs into single functions taking an `interpretation` argument; update call sites.

##### Phase H — evidence

Both pin tests + both anchor reproductions, as in Phase G.

#### Stage 2, Phase I — pin-test symmetrization (~half day)

1. Audit `test_cdc_baseline_pin.py` for any helper names, fixtures, or constants with "cdc" in the name. Add ESC counterparts where relevant.
2. Add `test_esc_baseline_pin.py` mirroring the CDC test exactly. Pin values captured from a Stage 1 ESC end-to-end run (recorded during Stage 1 Phase E acceptance).
3. Both tests should run via the standard `pytest Code/HA-Models/FromPandemicCode/test_*.py` invocation.

##### Phase I — evidence

Both pin tests pass (the new ESC test passes by construction since pins were captured during Stage 1; the CDC test continues to pass).

#### Stage 2, Phase J — documentation pass + ESC-MOD-BUG markers (~half day)

1. `CLAUDE.md` — update to mention both interpretations on equal footing. Currently CDC-implicit; should be neutral.
2. `README.md` and other top-level docs — same.
3. `plans/20260425-2102h_cdc-implementation-map.md` — add `# ESC-MOD-BUG<NN>:` markers on the ESC sibling methods so the marker symmetry is greppable. Update the map's "post-refactor" status section. Update CDC-MOD-BUG markers if their line numbers shifted in Phase G.
4. Add a brief `Code/HA-Models/FromPandemicCode/INTERPRETATIONS.md` (or section in an existing readme) explaining the user-facing knobs: `--interpretation cdc|esc`, `HAFISCAL_INTERPRETATION` env var, the comparison driver, the pin tests.
5. Update `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md` with an "Implementation status (post-refactor)" section noting that the codebase now runs both. Update the 13-quote audit in `welfare_code_and_paper_text_on_interpretation.md` to note the post-refactor implementation choice.

##### Phase J — evidence

```bash
# Marker symmetry:
grep -rn 'CDC-MOD-' Code/ | wc -l
grep -rn 'ESC-MOD-' Code/ | wc -l
# Should produce equivalent counts.

# Doc symmetry:
grep -ic '\bcdc\b' README.md CLAUDE.md
grep -ic '\besc\b' README.md CLAUDE.md
# Comparable counts.
```

#### Stage 2 acceptance gate

- All Stage 2 phase-tests pass.
- Stage 1's acceptance criteria still hold (both CDC and ESC anchors reproduce bit-identically).
- `grep -rn '\bAggFiscalType\b' Code/` returns only `AbstractAggFiscalType`, `CDCAggFiscalType`, `ESCAggFiscalType` — no bare references in production code.
- Symmetric language check: `grep -ic '\bcdc\b'` and `grep -ic '\besc\b'` over user-facing docs return comparable counts.
- `grep -rn 'CDC-MOD-' Code/` and `grep -rn 'ESC-MOD-' Code/` produce equivalent counts at corresponding sites.

## 6. Validation milestones (summary cross-reference)

This section is a high-level cross-reference; the concrete evidence checks live inside each phase above.

### After each Stage 1 phase A-E2
- `pytest test_cdc_baseline_pin.py` passes (CDC pin holds).
- `pytest Code/HA-Models/FromPandemicCode/test_*.py` passes (no regressions in the wider test suite).
- Phase-specific evidence checks all signed off (per-tier).

### After Stage 1 Phase B
- Step-1 ESC re-estimation reproduces ς to within ±2% (Reduced_Run, tier-2) or ±0.5% (Baseline, optional tier-3).
- Pre-staged ESC calibration files are validated via Phase D test.

### After Stage 1 Phase E
- `--comp full --tm-only` (CDC default) reproduces existing CDC anchor bit-identically.
- `--comp mini --interpretation esc` runs end-to-end without crashing (tier-2 ESC sanity).
- (Note: full ESC end-to-end MC welfare-6 is deferred to Phase F.)

### After Stage 1 Phase F
- ESC end-to-end MC produces measurable welfare-6 numbers for the first time under the current code. These become the *first* ESC pinned baseline; commit + tag as the ESC anchor.
- Welfare-6 cells match Edmund's branch reference within ±2% (no-AD) and ±5% (Rec=1 AD=1).
- ESC pin values captured for Stage 2 Phase I's `test_esc_baseline_pin.py`.

### After each Stage 2 phase
- Both `test_cdc_baseline_pin.py` and `test_esc_baseline_pin.py` pass.
- Both anchors reproduce bit-identically (Stage 2 is behavior-preserving).

### After Stage 2 Phase J
- `grep -rn 'CDC-MOD-' Code/` and `grep -rn 'ESC-MOD-' Code/` produce equivalent counts at corresponding sites.

## 7. Risks and open questions

1. **(I+B) anchor 32.5 — manual state propagation under CDC** is intricate and may not be cleanly factorable into a CDC-vs-ESC if/else without losing readability. Mitigation: encapsulate the CDC manual-tracking block into a helper function called only when interpretation is CDC (the prep already extracted the asset-rule piece as `_cdc_asset_rule`; the manual-tracking block can use the same pattern).

2. **(I+B) anchor 32.2 — wealth correction** uses `agent.controls.get("cNrm", agent.state_now.get("cNrm"))` which returns different things in CDC vs ESC contexts; under ESC, simply `(1−ς)·aLvl_hark` should work without that lookup, but care needed.

3. **TM kernel under ESC may need its own validation harness.** BUG-033 validated the CDC `_a` kernel against MC under CDC. The ESC kernel needs the same validation against an ESC MC reference — which doesn't exist yet under the current code (Edmund's branch has its own MC but it's a different code path). Suggested validation: run `origin/maintain_bound_pair_fix_splurge`'s MC, capture its multiplier numbers, then check that `_TM-vs-MC` with `--interpretation esc` reproduces them. Runs both branches; can be done once and then encoded as a regression test. **Only relevant if Phase C is included; deferred along with Phase C if mitigation #1 is taken.**

4. **Welfare-6 under both interpretations.** The aggregator A (`u(c_total)`) is shared, so the *formula* doesn't change. But the simulated `cLvl_splurge` paths *do* differ between CDC and ESC because the underlying calibrations (β, ∇, ς) differ. So welfare-6 numbers under each interpretation will differ even though the welfare formula is shared. Test: confirm the welfare-6 cells under each interpretation are stable across reruns (sampling-noise tolerance ~0.5%).

5. **Stage 2 documentation update.** Phase J should update `models_CDC_and_ESC.md` with a "Implementation status (post-refactor)" section noting that the codebase now runs both. The 13-quote paper-text audit in `welfare_code_and_paper_text_on_interpretation.md` should also note the post-refactor implementation choice.

6. **Helper-naming consistency in the prep work.** The prep landed `_wealth_under_cdc`, `_lottery_consumption_under_cdc` (under_<interp> suffix) but also `_cdc_asset_rule` (<interp>_ prefix) — two different patterns. Stage 2 Phase H must pick one and apply consistently across all paired helpers. Stage 1 Phase B can use whichever pattern is closest to the prep helper it pairs with (so `_wealth_under_esc`, `_lottery_consumption_under_esc`, `_esc_asset_rule`); Stage 2 unifies.

7. **`reproduce/verify_anchor.py` does not yet exist.** The Phase E evidence checks reference such a tool to do automated sha256 comparison between current outputs and an anchor's manifest. Either build it as a small utility during Phase E (~1 hour), or substitute manual sha256 comparison against the anchor manifest's `outputs` block. Recommendation: build it; it will be useful beyond Stage 1.

## 8. Estimated total effort (revised 2026-04-26 — staged)

| Stage | Phase | Effort | Notes |
|---|---|---|---|
| 1 | A — class scaffold | 0.5 day | Pure addition; no edits to AggFiscalType |
| 1 | B — Estimation parameterization | 1-2 days | Five sites; CDC body unchanged inside `if interpretation == 'CDC':` wrapper; ESC branches new; Step-1 tested on Reduced_Run (tier 2) and optionally Baseline (tier 3) |
| 1 | C — tm_methods (DEFERRED if mitigation #1) | (3-5 days if included) | Six `_a` functions need ESC siblings; (1−ς) factor + aNrm-semantics shift in multiple sites |
| 1 | D — calibration selection | 0.5 day | `Parameters.py` cascade; CDC behavior unchanged |
| 1 | E — Simulate.py + reproduce.sh + manifest field | 1 day | Plus tier-2 ESC nano/mini smoke + tier-3 CDC anchor reproduction; build `verify_anchor.py` if helpful |
| 1 | E2 — side-by-side driver | 0.5 day | Small new script; tier-2 sanity only |
| 1 | F — welfare estimation + ESC anchor | 1-2 calendar days (mostly background compute) | The ONLY tier-4 phase; runs `--comp full --mc-only --interpretation esc --auto-commit` (~6-12h); sanity-checks vs Edmund's branch; recipe replays for both anchors (~6-12h ESC + ~25min CDC) |
| 1 | **Stage 1 subtotal (with mitigation #1)** | **~1 working week of focused work + ~12-24h background ESC compute** (split between Phase F's anchor run and recipe replays) | |
| 2 | G — promote to abstract base | 0.5 day | Rename + ~30 call-site touches |
| 2 | H — symmetric helper naming | 0.5 day | Decision-led: paired siblings or dispatcher; pick based on what reads clean post-Stage-1 |
| 2 | I — pin-test symmetrization | 0.5 day | Add `test_esc_baseline_pin.py`; pin ESC values captured during Stage 1 Phase E |
| 2 | J — documentation pass + ESC-MOD-BUG markers | 0.5 day | CLAUDE.md, README.md, models_CDC_and_ESC.md, INTERPRETATIONS.md, marker symmetry |
| 2 | Validation | 0.5 day | Both anchors must reproduce bit-identically |
| 2 | **Stage 2 subtotal** | **~2.5 days** | |
| **Total (Stage 1 + Stage 2 with mitigation #1)** | | **~1.5 working weeks of focused work** | |

### Mitigation #1 (recommended, taken by default)

Defer the ESC `_a` TM kernel; ship MC-only ESC support first. ESC users would run only via MC (already validated under Edmund's branch on its own terms). The TM speed-up is nice-to-have but not strictly required for the paper-facing CDC↔ESC comparison. Cuts ~3-5 days from Stage 1 Phase C.

If Stage 1 lands and the ESC TM kernel becomes important later, it's a focused follow-up effort: add Phase C as a Stage-1.5 increment, run Stage 1 phase tests + both pin tests, anchor a TM-only ESC run.

### Mitigation #2 (rejected)

Keep Edmund's branch as the ESC code path entirely; don't merge into `_TM-vs-MC`. Add a `--interpretation esc` to `reproduce.sh` that does `git worktree add` of `origin/maintain_bound_pair_fix_splurge` and runs there. Two interpretations stay physically separate at the branch level; eliminates the parallel-implementation work for `tm_methods.py`.

**Rejected because:** branches drift over time (HARK upgrades, infrastructure improvements happen on `_TM-vs-MC` only); the side-by-side comparison mode (Phase E2) becomes effectively impossible; the symmetric end-state goal is unreachable.

## 9. What this plan does NOT include (deferred)

- **Comparing CDC and ESC numerical outputs in a paper-facing memo.** That's a separate analysis task once Stage 1 lands and both can be run under common code.
- **Welfare-6 sensitivity sweeps under each interpretation.** Out of scope; deferred until Stage 1 lands and the basic CDC vs ESC comparison is in hand.
- **Online-appendix write-up of the alternative formulation** (per `proposed_path_forward_20260424.md` §2). That's a paper-facing deliverable downstream of this code work.
- **Full ESC re-estimation of Step 1 + Step 2 (β/∇) under the new ESC code path.** Phase B Step-1 ESC re-estimation IS in scope (validates ς against Edmund's pin). Full re-derivation of the entire ESC calibration triple (ς, β, ∇) — i.e., re-running the equivalent of Edmund's overnight production run on `_TM-vs-MC` with our new ESC code — is a separate **~2-day follow-up** (~30 min Step-1 + ~48 hr Step-2 on Baseline). It validates the *complete* ESC calibration end-to-end, not just ς. Out of scope for Stage 1 because:
  - The pre-staged `_ESC` files are trusted as the operational ESC calibration (Phase D loads them).
  - Phase B's Step-1 ESC test is sufficient validation that our ESC code matches Edmund's at the splurge level.
  - Step-2 takes ~48 hours; running it during Stage 1 would block other work for 2 days.
  - If a future Stage 1.5 effort wants tighter validation, it adds: (a) Step-2 ESC re-estimation on Baseline (~48 hr), (b) compare resulting β, ∇ against Edmund's pinned values, (c) commit + tag as a Stage 1.5 anchor (`reproduce-<date>-comp-full-mc-only-esc-fully-recalibrated`).
- **Step-3 (Splurge=0) robustness re-estimation under ESC.** Even further out — ~48 hr more. Only relevant for `--comp max` paths.
- **A third interpretation** (e.g., a hybrid CDC/ESC variant). The architecture supports it (Stage 2 abstract base + sibling subclasses), but no work toward it is in this plan.
