# Plan 1 (v2): Ladder presets and convergence-aware defaults

**Status:** Draft (revision of `asymptotic-equality-driver-ladder-presets.md`)
**Scope:** Items A, B, C from the asymptotic-equality driver review, with the convergence-test invariant elevated to a hard requirement.
**Out of scope:** Baseline-work caching / refactor — see Plan 2 (`asymptotic-equality-driver-baseline-cache-refactor.md`).

**Recommended implementation order:** B → A → C (defaults and behavior first, then explicit `--ladder` wiring, then user-facing documentation).

---

## Guiding principle: every default invocation must be a *real* convergence test

This driver is `test_asymptotic_equality_revised.py`. Its job is to
check that as `AgentCount → ∞` for MC and as `mCount → ∞` for the TM
grid, the two methods agree at the per-period and per-NPV level. A
single-grid, single-N invocation does not test that — the "vs ref"
column is mechanically zero against itself, and there is no second
data point to extrapolate from.

**Paired-cell design.** Every default invocation runs **exactly two
configurations**, paired as follows:

- **Cell 1 (lower):** smaller MC `N` + TM `mCount = 50`
- **Cell 2 (upper):** larger MC `N` + TM `mCount = 100`

Convergence is then visible directly: as you go from Cell 1 to Cell 2,
both the MC sample size grows (`σ ∝ 1/√N` shrinks) *and* the TM grid
refines (discretization error shrinks). If the MC and TM methods are
both converging to the same limit, the absolute and relative gap
between Cell 1's TM result and Cell 2's TM result must shrink, *and*
the gap between Cell 1's MC and Cell 2's MC must shrink, *and* the
within-cell MC↔TM gap must shrink. That's three independent
convergence indicators from just two cells.

**Why exactly two TM grids and exactly two MC tiers per preset:**

1. Two TM grids (`mCount = 50` and `mCount = 100`) are enough to
   demonstrate TM grid convergence — `mCount=100` is essentially
   exact (TMMC §10, error ~O(M⁻²) puts mCount=100 around 0.15% of
   AggCons), so the gap between 50 and 100 directly bounds the
   discretization error at mCount=50.
2. Two MC tiers are enough to show the SLLN scaling provided the
   two `N` values differ by at least a factor of ~2.
3. More than two of either is wasteful at smoke / parity scale.
   Users who want a 3-grid TM ladder can pass `--tm` explicitly.

**Hard rules for every preset (including `smoke`):**

1. The preset names exactly **two cells**, each cell being a
   `(MC_label, TM_mCount)` pair.
2. Cell 1 uses TM `mCount=50`; Cell 2 uses TM `mCount=100`.
3. Cell 2's MC `N` must be at least ~2× Cell 1's MC `N`.
4. The summary table prints both cells' TM results, both cells' MC
   results, and the within-cell MC↔TM gap for each cell.

A preset that violates these is not a valid convergence test and must
not be the default. Users who want a degenerate single-cell run can
pass `--mc <one>` and `--tm <one>` explicitly.

---

## B — Convergence-aware default `--mc` / `--tm` behavior (first)

**Problem:** The current per-phase defaults are an inconsistent mix
(some phases default to a 3-grid TM list, some to a 2-tier MC list,
some to neither). This makes "what does running a phase with no
flags actually do?" unclear, and it makes the `--ladder` work in §A
harder because there is no shared baseline.

**Goal:** Define one canonical *convergence-aware* default for every
phase, satisfying the principle above.

**Tasks**

1. Inventory every phase runner in `test_asymptotic_equality_revised.py`
   that sets `mc_configs = [...]` or `tm_configs = [...]` when `None`.
2. Replace the per-phase defaults with a single function
   `default_configs_for_phase(phase_name)` returning:
   - `mc_configs`: a list of **at least two** MC labels
     (e.g. `["MC-small", "MC-med"]`) where the phase consumes MC.
   - `tm_configs`: a list of **at least two** TM labels
     (e.g. `["TM-coarse", "TM-default"]`).
   The function may special-case heavy phases (`recession-policies`)
   to use slightly cheaper lists, but must still return ≥2 in each
   list.
3. Preserve sweep semantics when the user passes more than one `--mc`
   or `--tm` argument (this is unchanged from the current loop).
4. Add a one-line log at phase start showing the actual configs in
   use, so the log makes it obvious when a sweep ran:
   `[phase] MC configs: MC-small, MC-med; TM configs: TM-coarse, TM-default`.
5. Add a runtime assertion in the phase runner: if either list has
   length 1, print a `⚠ NOT A CONVERGENCE TEST` warning. This
   prevents accidental single-grid defaults from being introduced
   later.

**Acceptance**

- `uv run python test_asymptotic_equality_revised.py --phase norec-taxcut`
  (no `--mc` / `--tm`) runs **at least two** TM grids and **at least
  two** MC tiers.
- The summary table shows monotone-shrinking err columns
  (TM ladder converging; MC error shrinking with N).
- Passing `--tm TM-coarse TM-default TM-fine` still runs a 3-grid
  sweep (current loop behavior preserved).
- Passing a single config triggers the `⚠ NOT A CONVERGENCE TEST`
  warning, but the run still completes.

---

## A — Preset ladder levels (`--ladder`) (second)

**Problem:** Operators want a named scale that selects matched
`(MC sweep, TM sweep)` pairs without memorizing labels.

**Goal:** A single CLI flag selects a named *pair of sweeps* that
are guaranteed to satisfy the convergence-test invariant.

### Naming

`smoke / quick / parity / careful` — explicitly avoid the
`tiny / small / medium / large` quartet because those collide with
`MC_CONFIGS` labels (`MC-tiny`, `MC-small`, …). In particular, the
fastest level is named **`smoke`**, not `tiny`, so that
`--ladder smoke` cannot be confused with `--mc MC-tiny`.

### Ladder table (paired cells)

Each preset names exactly **two cells**. Cell 1 always uses TM
`mCount = 50`; Cell 2 always uses TM `mCount = 100`. Adjacent ladder
levels share an MC config (e.g. `smoke`'s Cell 2 == `quick`'s Cell 1)
so successive runs are directly comparable.

| `--ladder`  | Cell 1 (TM=50)             | Cell 2 (TM=100)              | typical wall |
|-------------|----------------------------|------------------------------|--------------|
| `smoke`     | `MC-tiny` + `TM-50`        | `MC-small` + `TM-100`        | ~2–5 min     |
| `quick`     | `MC-small` + `TM-50`       | `MC-med` + `TM-100`          | ~10–20 min   |
| `parity`    | `MC-med` + `TM-50`         | `MC-large` + `TM-100`        | ~45–90 min   |
| `careful`   | `MC-large` + `TM-50`       | `MC-xlarge` + `TM-100`       | hours        |

Notes:
- Only two TM `mCount` values are needed across the entire ladder:
  50 and 100. (TMMC §10 puts mCount=100 at ~0.15% of the
  per-period AggCons truth, which is essentially exact at every
  scale below `MC-xlarge`.)
- Every preset is a 2-cell convergence test by construction:
  Cell 1 → Cell 2 simultaneously increases both `N` and `mCount`,
  so any drift in MC↔TM agreement between cells is informative.
- `MC-xlarge` (now N=8000, 5 seeds) is reachable via `careful`.
- Adjacent rows share an MC config on purpose. After running both
  `smoke` and `quick`, the user can stack `smoke`'s Cell 2
  (`MC-small + TM-100`) directly against `quick`'s Cell 1
  (`MC-small + TM-50`) and watch the TM grid effect at fixed `N`.

### Tasks

1. Add `LADDER_PRESETS` table (above) near `MC_CONFIGS` / `TM_CONFIGS`.
2. Add argument `--ladder {smoke,quick,parity,careful}`. No alias.
3. Use `default=None` for `--mc` and `--tm` (so we can distinguish
   "absent" from "explicit empty"); document this as the *standard*
   pattern in a code comment to forestall future regressions.
4. In `main()`, after parsing:
   - If `--ladder` is set and `--mc`/`--tm` are absent, copy the
     ladder's lists into `args.mc` / `args.tm`.
   - If `--ladder` and explicit `--mc` / `--tm` are both set,
     **error out** with a clear message ("cannot mix `--ladder` with
     explicit `--mc`/`--tm`; pick one"). This is stricter than the
     v1 plan's "explicit wins" precedence, because silent override
     is the bigger footgun here.
5. If neither `--ladder` nor `--mc`/`--tm` is set, fall back to the
   per-phase default from §B. Log at startup which fallback was
   used: `[ladder] no --ladder given; using per-phase default
   convergence sweep`.
6. **Do not** map `Parametrization` to a default `--ladder`. (The
   v1 Task 4 is dropped.) Implicit inference creates exactly the
   bug "user runs same command twice with different
   `Parametrization` and gets results that disagree at scales they
   didn't realize were different."

### Acceptance

- `uv run python test_asymptotic_equality_revised.py --phase baseline --ladder smoke`
  uses exactly 2 TM grids and 2 MC tiers from the table.
- Mixing `--ladder` with `--mc` errors out with a clear message.
- `--ladder careful` reaches `MC-xlarge` (no MC config is
  unreachable via the preset table).
- Each ladder run prints a one-line `[ladder] ...` startup banner
  identifying which preset is in use.

---

## C — Documentation (third)

### Tasks

1. **Driver module docstring**: rewrite the "Usage" section to
   describe the convergence-aware default, the `--ladder`
   alternative, and the explicit `--mc` / `--tm` form. Mention that
   every preset is a *real* convergence test (no single-grid
   defaults). Include a worked example showing how to read the
   `vs TM-ref` and `MC err` columns.
2. **`plans/20260404-1746h_asymptotic-equality-test-plan_revised.md`**: add a
   pointer to this plan, and a one-paragraph statement of the
   "every default is a convergence test" invariant (it's the same
   principle that motivates the §13.5 PROVEN comparisons — we
   should also be able to *demonstrate* convergence, not just
   assert it).
3. **Two-solve rationale**: a short subsection explaining why
   baseline and policy each get a separate `solve()` call (point
   to `AggFiscalModel.switch_shock_type`: `base` vs
   `TaxCut` / `UI` / `Check` use different `MrkvArray` /
   `IncShkDstn`, hence different Bellman problems).
4. **Update the `history/` ladder scripts** (e.g.
   `asymptotic-equality-test-plan_revised_ladder_*.log`-producing
   shell snippets) to use the new `--ladder` flag instead of
   long `--mc ... --tm ...` invocations. This avoids drift.

### Acceptance

- A new reader can discover (a) why two solves appear, (b) how to
  run a real convergence test in under 5 minutes
  (`--ladder smoke`), and (c) how to escalate to a fuller test
  without memorizing `MC_CONFIGS` / `TM_CONFIGS` entries.

---

## Rollout / risk

- **Risk:** CI or local scripts rely on old multi-default sweeps
  with specific config labels. Mitigation:
  - Grep for `test_asymptotic_equality_revised` in CI and `history/`.
  - Update `plans/` and `history/` ladder scripts in the same PR.
  - One-release deprecation window: keep accepting the old
    `--mc <label>` form but emit a deprecation warning if used
    without a sibling `--mc` of a different size (the
    convergence-invariant warning from §B Task 5 covers this).

---

## Dependencies

- None. Plan 2 (baseline cache refactor) is independent and should
  *not* land first — see the Plan 2 response document for why
  profiling under stripped defaults would miss real duplication.

---

## Why this version exists

This document supersedes `asymptotic-equality-driver-ladder-
presets.md`. It addresses two objections raised in the response
file `asymptotic-equality-driver-ladder-presets_claude-response.md`:

1. **Convergence-test invariant.** v1 allowed (and recommended) a
   single-grid default. v2 makes "≥2 TM grids and ≥2 MC tiers
   per default invocation" a hard rule, with a runtime warning if
   ever violated. The driver remains a *convergence test* even at
   smoke scale.
2. **Naming collision.** v1 used `tiny / small / medium / large`,
   which collide with `MC_CONFIGS`. v2 uses
   `smoke / quick / parity / careful` with `smoke` (not `tiny`) as
   the cheapest level.

It also folds in the smaller fixes:
- `MC-xlarge` is reachable via `careful` (v1 omitted the level).
- `--ladder` + explicit `--mc`/`--tm` is an *error*, not a silent
  override.
- v1 Task 4 (Parametrization → ladder inference) is dropped.
- The argparse `default=None` pattern is mandated and documented.
