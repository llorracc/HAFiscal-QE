"""Phase 0 profile harness for do_all.py.

Wraps do_all.py's five steps individually so we get:
- per-step wall time
- per-step peak RSS
- per-step peak CPU utilization (via /usr/bin/time -v on Linux)
- cumulative total

Outputs JSON to plans/results/<timestamp>_<parametrization>_profile.json
for comparison against matsya HEAD as the reference. Runs step 1,
step 2, step 4, step 5 (skips step 3 unless HAFISCAL_RUN_STEP_3=1).

Usage:
    python reproduce/profile_do_all.py [--steps 1,2,4,5] [--tag baseline]

Intended to run on matsya HEAD as the reference, and again on each
candidate speedup branch/commit to measure before/after.
"""
import argparse, json, os, pathlib, resource, shutil, signal, subprocess, sys, time
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "plans" / "results"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Each step maps to (substep label, cwd relative to ROOT, command list).
# Mirrors do_all.py:46-178 exactly; we split it up so we can time each.
STEPS = {
    1: [
        ("splurge_estimation",
         "Code/HA-Models/Target_AggMPCX_LiquWealth",
         [sys.executable, "Estimation_BetaNablaSplurge.py"]),
    ],
    2: [
        ("EstimAggFiscalMAIN",
         "Code/HA-Models/FromPandemicCode",
         [sys.executable, "EstimAggFiscalMAIN.py"]),
        ("CreateLPfig",
         "Code/HA-Models/FromPandemicCode",
         [sys.executable, "CreateLPfig.py"]),
        ("CreateIMPCfig",
         "Code/HA-Models/FromPandemicCode",
         [sys.executable, "CreateIMPCfig.py"]),
        ("estimBetas_tabular",
         "Code/HA-Models/FromPandemicCode",
         [sys.executable, "estimBetas_tabular_generate.py"]),
        ("nonTargetedMoments_tabular",
         "Code/HA-Models/FromPandemicCode",
         [sys.executable, "nonTargetedMoments_tabular_generate.py"]),
    ],
    3: [
        ("EstimAggFiscalMAIN_Splurge0",
         "Code/HA-Models/FromPandemicCode",
         [sys.executable, "EstimAggFiscalMAIN.py", "--splurge0"]),
    ],
    4: [
        # HANK-SAM entry points; exact filenames may differ; defer until seen live.
        ("HA-Fiscal-HANK-SAM",
         "Code/HA-Models/FromPandemicCode",
         [sys.executable, "HA-Fiscal-HANK-SAM.py"]),
    ],
    5: [
        ("AggFiscalMAIN_policy",
         "Code/HA-Models/FromPandemicCode",
         [sys.executable, "AggFiscalMAIN.py"]),
    ],
}


def sample_peak_rss_mb():
    """Self + children peak RSS in MB (Linux: kilobytes; macOS: bytes)."""
    r_self = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    r_ch = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if sys.platform == "darwin":
        return (r_self + r_ch) / (1024 ** 2)
    return (r_self + r_ch) / 1024


def run_substep(label, cwd_rel, cmd):
    cwd = ROOT / cwd_rel
    log_path = OUT_DIR / f"_tmp_{label}.log"
    t0 = time.time()
    rss_pre = sample_peak_rss_mb()
    with open(log_path, "w") as logf:
        rc = subprocess.call(cmd, cwd=str(cwd), stdout=logf, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    rss_post = sample_peak_rss_mb()
    return {
        "label": label,
        "cwd": cwd_rel,
        "cmd": cmd,
        "wall_sec": wall,
        "rss_peak_mb": max(rss_pre, rss_post),
        "returncode": rc,
        "log_path": str(log_path.relative_to(ROOT)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", default="1,2,4,5",
                    help="Comma-separated list of do_all.py steps to run (default 1,2,4,5; 3 is opt-in)")
    ap.add_argument("--tag", default="baseline",
                    help="Short tag used in the output filename")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the plan without running anything")
    args = ap.parse_args()

    steps = [int(s) for s in args.steps.split(",")]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = {
        "timestamp": ts,
        "tag": args.tag,
        "steps_requested": steps,
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT)).decode().strip(),
        "git_branch": subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ROOT)).decode().strip(),
        "env": {k: v for k, v in os.environ.items() if k.startswith("HAFISCAL_")},
        "substeps": [],
    }

    if args.dry_run:
        for s in steps:
            for label, cwd_rel, cmd in STEPS.get(s, []):
                print(f"  step {s}: {label}  (cd {cwd_rel}; {' '.join(cmd)})")
        return

    t_pipe0 = time.time()
    for s in steps:
        for label, cwd_rel, cmd in STEPS.get(s, []):
            print(f"[profile] step {s} — {label}", flush=True)
            rec = run_substep(label, cwd_rel, cmd)
            rec["step"] = s
            out["substeps"].append(rec)
            # Incremental dump so we don't lose progress on crash.
            with open(OUT_DIR / f"{ts}_{args.tag}_profile.json", "w") as f:
                json.dump(out, f, indent=2)
            if rec["returncode"] != 0:
                print(f"[profile] nonzero exit on {label} (rc={rec['returncode']}); continuing", flush=True)

    out["wall_total_sec"] = time.time() - t_pipe0
    with open(OUT_DIR / f"{ts}_{args.tag}_profile.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"[profile] done in {out['wall_total_sec']:.0f}s; report at "
          f"{(OUT_DIR / f'{ts}_{args.tag}_profile.json').relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
