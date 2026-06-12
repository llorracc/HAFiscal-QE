"""HAFISCAL_PERMGROFAC_FIX — single source of truth binding the BUG-047 solver
fix to the discount-factor calibration it was estimated under, AND to the
solutions the simulator consumes.

The PermGroFac^(-CRRA) marginal-value fix (BUG-047) changes the solved cFunc by
~6-7%, so the discount-factor calibration (beta) is re-estimated PAIRED with the
fix regime. A beta estimated under one regime is meaningless paired with a
solution from the other (memory: feedback_calibration_solver_matched_pair). To
make a mismatch IMPOSSIBLE rather than merely discouraged, the SAME flag drives:

  1. the solver math            -> permgrofac_fix_on()            (AggFiscalModel.py)
  2. the calibration file read  -> permgrofac_calib_path()        (Parameters.py)
  3. the solution the simulator uses -> stamp_regime()/assert_regime()
     (stamp at solve time; assert at simulate / cache-restore time, so a cached
      or pickled solution from the OTHER regime cannot be silently simulated).

  HAFISCAL_PERMGROFAC_FIX=1 (default): fixed solver  + canonical calibration.
  HAFISCAL_PERMGROFAC_FIX=0 (legacy):  buggy solver  + Results/_pgf_legacy/ calibration.
"""
import os

_LEGACY_SUBDIR = "_pgf_legacy"
_ATTR = "_permgrofac_regime"


def permgrofac_fix_on():
    """True iff the BUG-047 PermGroFac^(-CRRA) fix is active. Default ON."""
    return os.environ.get("HAFISCAL_PERMGROFAC_FIX", "1") != "0"


def permgrofac_regime():
    """Short tag for the active regime: 'pgfFix' (on) or 'pgfLegacy' (off)."""
    return "pgfFix" if permgrofac_fix_on() else "pgfLegacy"


def permgrofac_calib_path(path):
    """Map a DiscFacEstim_* calibration path to the regime-matched location.

    FIX on  -> canonical path unchanged.
    FIX off -> insert the '_pgf_legacy/' subdir before the filename; RAISE if that
               legacy (buggy-solver) calibration is absent, rather than silently
               falling back to the fixed-solver calibration (a mismatched pair).
    """
    if permgrofac_fix_on():
        return path
    d, fn = os.path.split(path)
    legacy = os.path.join(d, _LEGACY_SUBDIR, fn)
    if not os.path.exists(legacy):
        raise FileNotFoundError(
            "[PermGroFac matched-pair] HAFISCAL_PERMGROFAC_FIX=0 (legacy solver) "
            "requires the matched legacy-regime calibration at\n  "
            f"{legacy}\nwhich is missing. Refusing to fall back to the fixed-solver "
            "calibration or hardcoded defaults (a meaningless mismatched pairing). "
            "Materialize the legacy calibration there, or run with HAFISCAL_PERMGROFAC_FIX=1."
        )
    return legacy


def stamp_regime(obj):
    """Tag obj (an agent / economy / solution) with the regime it was solved under."""
    try:
        setattr(obj, _ATTR, permgrofac_regime())
    except (AttributeError, TypeError):
        pass  # immutable / slotted object — best-effort tag
    return obj


def assert_regime(obj, context="simulation"):
    """Raise if obj carries a regime tag that disagrees with the active flag.

    Soft by design: an untagged object (no tag) passes, so legacy pickles and
    third-party objects don't break — only an EXPLICIT regime mismatch (a solution
    solved under the other PermGroFac regime) is blocked. Stamp at solve time so
    production solutions carry the tag.
    """
    have = getattr(obj, _ATTR, None)
    want = permgrofac_regime()
    if have is not None and have != want:
        raise RuntimeError(
            f"[PermGroFac matched-pair] {context} is about to use a solution solved "
            f"under regime '{have}', but HAFISCAL_PERMGROFAC_FIX is currently '{want}'. "
            "A solution and the active (beta, PermGroFac) regime MUST match — simulating "
            "a solution from the other regime (e.g. a cached/pickled solve) with this "
            "regime's betas is a meaningless mismatched pairing. Re-solve under the "
            "current flag, or set HAFISCAL_PERMGROFAC_FIX to match the solution."
        )
    return obj
