#!/bin/bash
# Chain C — runs after chains A + B complete. Two parts:
#   1. CRRA sensitivity validation at Baseline (CRRA1 + CRRA3, recessionCheck)
#   2. CONDITIONAL: flip HAFISCAL_USE_JAX_2B default to ON if all of
#      Chain A/B/C welfare cells passed paper-grade (<0.5%)
#
# The flip is implemented as two edits:
#   - AggFiscalModel.solve(): default env-var value '' becomes treated as '1'
#   - solution_cache/keys.py: normalize env var '' -> '1' so cache key
#     distinguishes pre-flip (HARK-driven) from post-flip (2B-driven) entries
#     (prevents loading an old HARK result under the new default).
set -uo pipefail

cd /home/shared/github/llorracc/HAFiscal-Latest || exit 1
unset VIRTUAL_ENV

PY=.venv-linux-x86_64/bin/python
LOG_DIR=Code/HA-Models/jax_mc_speedup/overnight_chainC_logs
mkdir -p "$LOG_DIR"

echo "[$(date '+%F %T')] chain C START" | tee -a "$LOG_DIR/master.log"

# Wait for chains A + B to finish
A_LOG="Code/HA-Models/jax_mc_speedup/overnight_2B_policies_logs/master.log"
B_LOG="Code/HA-Models/jax_mc_speedup/overnight_phase5_parallel_logs/master.log"
echo "[$(date '+%F %T')] waiting for chains A + B to finish..." | tee -a "$LOG_DIR/master.log"
WAITED=0
while [ "$WAITED" -lt 28800 ]; do  # 8 hours max
    a_done=0
    b_done=0
    grep -q "overnight 2B policies DONE" "$A_LOG" 2>/dev/null && a_done=1
    grep -q "phase 5 parallel+2B retry DONE" "$B_LOG" 2>/dev/null && b_done=1
    if [ "$a_done" = "1" ] && [ "$b_done" = "1" ]; then
        echo "[$(date '+%F %T')] chains A + B done; proceeding" | tee -a "$LOG_DIR/master.log"
        break
    fi
    sleep 60
    WAITED=$((WAITED + 60))
done
if [ "$WAITED" -ge 28800 ]; then
    echo "[$(date '+%F %T')] WARN: 8h timeout waiting for A/B; proceeding anyway" | tee -a "$LOG_DIR/master.log"
fi

run_step() {
    local label="$1"; shift
    echo "==========================================================" | tee -a "$LOG_DIR/master.log"
    echo "[$(date '+%F %T')] STEP: $label" | tee -a "$LOG_DIR/master.log"
    echo "==========================================================" | tee -a "$LOG_DIR/master.log"
    local start_ts=$(date +%s)
    "$@" > "$LOG_DIR/${label}.log" 2>&1
    local rc=$?
    local elapsed=$(($(date +%s) - start_ts))
    if [ $rc -ne 0 ]; then
        echo "[FAIL rc=$rc t=${elapsed}s] $label (see $LOG_DIR/${label}.log)" | tee -a "$LOG_DIR/master.log"
    else
        echo "[OK t=${elapsed}s] $label" | tee -a "$LOG_DIR/master.log"
        grep -E "HARK welfare cell:|JAX-replay-v2 welfare cell:|Relative diff:|paper-grade" \
            "$LOG_DIR/${label}.log" 2>/dev/null | tee -a "$LOG_DIR/master.log"
    fi
}

# Part 1: CRRA sensitivity
run_step "verify_CRRA1_recessionCheck" \
    env HAFISCAL_USE_JAX_2B=1 HAFISCAL_USE_SOLUTION_CACHE=1 PYTHONUNBUFFERED=1 \
    "$PY" Code/HA-Models/FromPandemicCode/verify_welfare_replay.py \
    --parametrization CRRA1 --policy recessionCheck

run_step "verify_CRRA3_recessionCheck" \
    env HAFISCAL_USE_JAX_2B=1 HAFISCAL_USE_SOLUTION_CACHE=1 PYTHONUNBUFFERED=1 \
    "$PY" Code/HA-Models/FromPandemicCode/verify_welfare_replay.py \
    --parametrization CRRA3 --policy recessionCheck

# Part 2: CONDITIONAL flip — only if EVERY verify_welfare_replay run
# (from chains A/B/C) shows "paper-grade" in its log. Pessimistic: any
# missing log or any FAIL aborts the flip.
echo "[$(date '+%F %T')] checking paper-grade across all overnight verify runs..." | tee -a "$LOG_DIR/master.log"
ALL_PG=1
declare -a CHECK_LOGS=(
    "Code/HA-Models/jax_mc_speedup/overnight_2B_policies_logs/verify_Baseline_2B_recessionUI.log"
    "Code/HA-Models/jax_mc_speedup/overnight_2B_policies_logs/verify_Baseline_2B_recessionTaxCut.log"
    "Code/HA-Models/jax_mc_speedup/overnight_chainC_logs/verify_CRRA1_recessionCheck.log"
    "Code/HA-Models/jax_mc_speedup/overnight_chainC_logs/verify_CRRA3_recessionCheck.log"
)
for f in "${CHECK_LOGS[@]}"; do
    if [ ! -f "$f" ]; then
        echo "  MISSING: $f" | tee -a "$LOG_DIR/master.log"
        ALL_PG=0
    elif ! grep -q "matches HARK welfare to <0.5% — paper-grade" "$f"; then
        echo "  NOT paper-grade: $f" | tee -a "$LOG_DIR/master.log"
        ALL_PG=0
    else
        echo "  paper-grade OK: $f" | tee -a "$LOG_DIR/master.log"
    fi
done

if [ "$ALL_PG" = "1" ]; then
    echo "[$(date '+%F %T')] ALL paper-grade — flipping HAFISCAL_USE_JAX_2B default to ON" | tee -a "$LOG_DIR/master.log"

    # Edit 1: AggFiscalModel.solve()
    "$PY" - <<'PYEOF'
import re
path = "Code/HA-Models/FromPandemicCode/AggFiscalModel.py"
with open(path) as f:
    src = f.read()
old = "        use_2b = _os.environ.get('HAFISCAL_USE_JAX_2B', '').lower() in ('1', 'on', 'true')"
new = "        # Default flipped 2026-05-22 (overnight chain C) after CRRA1/CRRA3\n        # + 3-policy Baseline sweeps all passed paper-grade. Opt-out:\n        # HAFISCAL_USE_JAX_2B=0 (or 'off' / 'false' / 'no').\n        _v = _os.environ.get('HAFISCAL_USE_JAX_2B', '1').lower()\n        use_2b = _v not in ('0', 'off', 'false', 'no')"
if old not in src:
    print("[flip] AggFiscalModel.py — old pattern not found; skipping (already flipped?)")
else:
    src = src.replace(old, new)
    with open(path, "w") as f:
        f.write(src)
    print("[flip] AggFiscalModel.py updated")
PYEOF

    # Edit 2: keys.py — normalize empty env var to '1' for cache key
    "$PY" - <<'PYEOF'
path = "Code/HA-Models/solution_cache/keys.py"
with open(path) as f:
    src = f.read()
old = """def _env_dict():
    \"\"\"Numerical-output-affecting env vars (whitelisted).\"\"\"
    return {
        k: os.environ.get(k, \"\")
        for k in _HAFISCAL_NUMERICAL_ENV_VARS
    }"""
new = """def _env_dict():
    \"\"\"Numerical-output-affecting env vars (whitelisted).

    HAFISCAL_USE_JAX_2B is normalized: empty env var (default) maps to '1'
    after the 2026-05-22 default flip, so pre-flip cache entries (saved
    with key env='') don't get loaded under the new default (which would
    deliver HARK-computed results under code that expects 2B).
    \"\"\"
    out = {k: os.environ.get(k, \"\") for k in _HAFISCAL_NUMERICAL_ENV_VARS}
    if out.get('HAFISCAL_USE_JAX_2B', '') == '':
        out['HAFISCAL_USE_JAX_2B'] = '1'
    return out"""
if old not in src:
    print("[flip] keys.py — old pattern not found; skipping (already flipped?)")
else:
    src = src.replace(old, new)
    with open(path, "w") as f:
        f.write(src)
    print("[flip] keys.py updated")
PYEOF

    # Quick parity check that the flipped code still passes the SHA tests
    if "$PY" Code/HA-Models/solution_cache/test_sha_excluded_from_key.py >/dev/null 2>&1; then
        echo "[flip] SHA-exclusion unit tests still pass" | tee -a "$LOG_DIR/master.log"
    else
        echo "[flip] WARN: SHA tests failed after flip — reverting" | tee -a "$LOG_DIR/master.log"
        git checkout -- Code/HA-Models/FromPandemicCode/AggFiscalModel.py Code/HA-Models/solution_cache/keys.py
        ALL_PG=0
    fi

    if [ "$ALL_PG" = "1" ]; then
        # Commit + push
        git add Code/HA-Models/FromPandemicCode/AggFiscalModel.py Code/HA-Models/solution_cache/keys.py
        git commit -m "$(cat <<'COMMIT_EOF'
default-flip: HAFISCAL_USE_JAX_2B=1 is now the default (was opt-in)

All overnight 2026-05-22 paper-grade welfare tests passed (<0.5% rel
diff): Baseline recessionUI/recessionTaxCut + CRRA1/CRRA3 recessionCheck
+ earlier-session recessionCheck (HS_Only / Reduced_Run / Baseline).

Combined with the Baseline JAX-AD wall improvement (3121s -> 1885s =
1.66x faster, parity 0.045% on welfare-cell direct comparison), 2B is
production-ready.

Behavioral change: AggregateDemandEconomy.solve() now uses the JAX
lax.while_loop per-cohort solve by default. Opt-out via
  HAFISCAL_USE_JAX_2B=0   (also accepts off / false / no)

Cache safety: solution_cache/keys.py normalizes empty env-var to '1'
so post-flip cache keys don't match pre-flip entries. Pre-flip entries
become orphaned (~30 MB on disk; regenerate on next miss).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
COMMIT_EOF
)"
        git push origin 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC 2>&1 | tail -3 | tee -a "$LOG_DIR/master.log"
    fi
else
    echo "[$(date '+%F %T')] at least one test was NOT paper-grade; flip ABORTED" | tee -a "$LOG_DIR/master.log"
fi

echo "[$(date '+%F %T')] chain C DONE" | tee -a "$LOG_DIR/master.log"
