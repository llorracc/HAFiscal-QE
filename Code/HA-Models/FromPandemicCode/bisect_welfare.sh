#!/usr/bin/env bash
# Bisect W_6 drop from QE publish (01fc50f8) → current (HEAD) by re-running
# mc_welfare_diagnostic.py at a small set of checkpoints. See
# plans/20260418-1053h_welfare-drop-bisection.md.
#
# Usage:
#   bash bisect_welfare.sh [commit1 commit2 ...]   # explicit list
#   bash bisect_welfare.sh                          # default checkpoint list

set -uo pipefail
cd "$(dirname "$0")" || exit 1

REPO_ROOT="$(git rev-parse --show-toplevel)"
OUT_DIR="/tmp/welfare_diag/bisect"
SUMMARY="$OUT_DIR/summary.tsv"
mkdir -p "$OUT_DIR"

# Files to copy into each worktree (current-version diagnostic that knows about
# HAFISCAL_SPLURGE_OLD / HAFISCAL_SPLURGE_OVERRIDE env overrides, etc).
DIAG_SRC="$REPO_ROOT/Code/HA-Models/FromPandemicCode/mc_welfare_diagnostic.py"
ANALYZE_SRC="$REPO_ROOT/Code/HA-Models/FromPandemicCode/analyze_splurge_isolation.py"

DEFAULT_COMMITS=(
    2db82a86  # HARK 0.17.0 migration
    a2a50c24  # HARK 0.17.0 + API compat
    5b9c02f3  # 0.14.1↔0.17.0 equivalence confirmed
    c45cd8e9  # Markov refactor (AggIndMrkvConsumerType)
    58444c83  # Phase 1 TM fix + BUG-014 + mCount=100
    2680b3a0  # pre-splurge-in-budget T_age=200 lagged (known Baseline UI=1.41)
)

if [[ $# -gt 0 ]]; then
    COMMITS=("$@")
else
    COMMITS=("${DEFAULT_COMMITS[@]}")
fi

# Initialize summary if missing
if [[ ! -f "$SUMMARY" ]]; then
    printf "sha\tdate\tui_w6_ad1\tui_m_10y\tcheck_w6_ad1\tcheck_m_10y\tstatus\tsubject\n" > "$SUMMARY"
fi

run_one() {
    local sha=$1
    local wt="$REPO_ROOT/.worktrees/bisect-$sha"
    local log="$OUT_DIR/$sha.log"
    local npz="$OUT_DIR/$sha.npz"
    local date_iso subject
    date_iso=$(git -C "$REPO_ROOT" log -1 --format=%ad --date=short "$sha")
    subject=$(git -C "$REPO_ROOT" log -1 --format=%s "$sha" | tr '\t' ' ')

    echo "==== $sha [$date_iso] $subject ===="

    if [[ -f "$npz" ]]; then
        echo "  already have $npz — skipping MC run"
    else
        # Worktree setup
        if [[ -d "$wt" ]]; then
            echo "  worktree $wt already exists — reusing"
        else
            git -C "$REPO_ROOT" worktree add --detach "$wt" "$sha" >"$log" 2>&1 || {
                printf "%s\t%s\tERROR\tERROR\tERROR\tERROR\tworktree-failed\t%s\n" \
                    "$sha" "$date_iso" "$subject" >> "$SUMMARY"
                return 1
            }
        fi

        # Copy current-version diagnostic into the worktree
        cp "$DIAG_SRC" "$wt/Code/HA-Models/FromPandemicCode/mc_welfare_diagnostic.py"
        cp "$ANALYZE_SRC" "$wt/Code/HA-Models/FromPandemicCode/analyze_splurge_isolation.py" 2>/dev/null || true

        # Run diagnostic from inside the worktree, writing npz to OUT_DIR
        # (not the worktree's /tmp since we'll delete the worktree).
        if ( cd "$wt/Code/HA-Models/FromPandemicCode" && \
             HAFISCAL_DIAG_OUT_DIR="$OUT_DIR" python mc_welfare_diagnostic.py ) >>"$log" 2>&1; then
            # mc_welfare_diagnostic.py writes to /tmp/welfare_diag/NEW.npz by default.
            # Rename to per-sha file.
            if [[ -f /tmp/welfare_diag/NEW.npz ]]; then
                mv /tmp/welfare_diag/NEW.npz "$npz"
            fi
        else
            printf "%s\t%s\tRUN_FAIL\tRUN_FAIL\tRUN_FAIL\tRUN_FAIL\trun-failed\t%s\n" \
                "$sha" "$date_iso" "$subject" >> "$SUMMARY"
            echo "  RUN FAILED — see $log"
            return 1
        fi
    fi

    # Extract W_6 and multiplier via small inline analyzer (UI scenario only).
    python - "$npz" "$sha" "$date_iso" "$subject" >>"$SUMMARY" 2>>"$log" <<'PY'
import sys, numpy as np
npz_path, sha, date_iso, subject = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
d = np.load(npz_path)
CRRA = float(d['CRRA']); R = float(d['Rfree']); T = int(d['act_T'])
wt_ = R ** (-np.arange(T))

def w6(pol_key, base_key, ss_key='base'):
    c_pol  = d[f'{pol_key}_cLvl_all_splurge']
    c_base = d[f'{base_key}_cLvl_all_splurge']
    c_ss   = d[f'{ss_key}_cLvl_all_splurge']
    Agg_pol  = d[f'{pol_key}_AggCons']
    Agg_base = d[f'{base_key}_AggCons']
    Y_pol    = d[f'{pol_key}_AggIncome']
    Y_base   = d[f'{base_key}_AggIncome']
    disc = R ** (-np.arange(T))
    NPV_cost = np.sum((Y_pol - Y_base) * disc)
    NPV_dC   = np.sum((Agg_pol - Agg_base) * disc)
    M = NPV_dC / NPV_cost
    cb  = np.maximum(c_base, 1e-16)
    css = np.maximum(c_ss,   1e-16)
    mu  = css ** (-CRRA)
    dU  = -1.0/np.maximum(c_pol,1e-16) + 1.0/cb
    W_U = np.sum(np.sum(dU/mu, axis=1) * disc) / NPV_cost
    return W_U + (1.0 - M), M

ui_w6,  ui_m  = w6('recUIAD', 'recAD')
chk_w6, chk_m = float('nan'), float('nan')  # check scenario not in diagnostic
print(f"{sha}\t{date_iso}\t{ui_w6:.4f}\t{ui_m:.4f}\t{chk_w6}\t{chk_m}\tOK\t{subject}")
PY

    echo "  done — see $SUMMARY"

    # Remove worktree after successful run (keeps disk use bounded).
    if [[ -d "$wt" ]]; then
        git -C "$REPO_ROOT" worktree remove --force "$wt" >>"$log" 2>&1 || true
    fi
}

for sha in "${COMMITS[@]}"; do
    run_one "$sha" || echo "  (continuing with next commit)"
done

echo
echo "Summary:"
column -t -s $'\t' "$SUMMARY"
