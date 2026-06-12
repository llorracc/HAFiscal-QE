"""
HAFISCAL_INTERPRETATION helper module.

Single source of truth for the CDC-vs-ESC interpretation flag and the
filename-suffix convention. Used by:
  - tm_methods.py kernel functions (interpretation parameter dispatch)
  - AggFiscalModel.py AggFiscalType (self.interpretation attribute)
  - EstimAggFiscalMAIN.py (Phase 3 filename-suffix wiring landed 2026-05:
    interp_suffix() on the DiscFacEstim/registry result paths)
  - Estimation_BetaNablaSplurge.py (reads get_interpretation() for the Step-1
    agent-type dispatch, BUG-035 — not the filename suffix)
  - test files (so tests can override the env var via patching)

Per plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md §6
(design decisions resolved 2026-04-27):
  - Configuration mechanism: BOTH env var and CLI flag (precedence:
    explicit kwarg > env var > default 'CDC').
  - Default = 'CDC' preserves byte-identical behavior for unflagged runs.
  - Filename suffix convention: append '_<INTERPRETATION>' before '.txt'.
  - Reader-side fallback: if suffixed file doesn't exist, fall back to
    un-suffixed (legacy compat).

Usage:

  from _interpretation import get_interpretation, suffix_path, resolve_path

  # Read the env var:
  interp = get_interpretation()  # → 'CDC' or 'ESC'

  # Write to a suffixed file:
  out_path = suffix_path('Result_AllTarget.txt')
  # → 'Result_AllTarget_CDC.txt' or 'Result_AllTarget_ESC.txt'

  # Read with fallback:
  in_path = resolve_path('Result_AllTarget.txt')
  # → suffixed if it exists, else un-suffixed
"""

import os


def get_interpretation(require=False):
    """Return current HAFISCAL_INTERPRETATION value, validated.

    Reads `os.environ['HAFISCAL_INTERPRETATION']`; defaults to 'CDC'.
    Raises ValueError on invalid values (fail-fast).

    Parameters
    ----------
    require : bool, default False
        If True and HAFISCAL_INTERPRETATION is None/empty (i.e. NOT
        explicitly set in the environment), raise RuntimeError rather than
        silently assuming the 'CDC' default. Use at guarded entry points
        (BUG-051 matched-pair safety) where assuming an interpretation is
        unsafe. When False, the legacy default-'CDC' behavior is preserved
        for backward compatibility.

    Returns
    -------
    str: 'CDC' or 'ESC' (always uppercase).
    """
    raw = os.environ.get('HAFISCAL_INTERPRETATION')
    if require and (raw is None or raw == ''):
        raise RuntimeError(
            "HAFISCAL_INTERPRETATION must be set explicitly to 'ESC' or "
            "'CDC' — refusing to assume a default in a guarded entry point"
        )
    val = (raw if raw else 'CDC').upper()
    if val not in ('CDC', 'ESC'):
        raise ValueError(
            f"HAFISCAL_INTERPRETATION must be 'CDC' or 'ESC', got: {val!r}"
        )
    return val


def assert_interpretation(passed, context=''):
    """Assert an explicitly-passed interpretation matches the env single source.

    Matched-pair safety guard (BUG-051): a function that takes an explicit
    `interpretation=` argument must not run a TM kernel / asset rule under an
    interpretation that disagrees with HAFISCAL_INTERPRETATION — that is
    exactly the silent CDC-kernel-under-ESC-run class of bug this guards.

    Parameters
    ----------
    passed : str or None
        The explicit interpretation argument. If None, no check is done
        (caller is expected to resolve None from get_interpretation()).
    context : str
        Caller name / site, surfaced in the error message.

    Raises
    ------
    RuntimeError if `passed` is not None and disagrees (case-insensitively)
    with get_interpretation().
    """
    if passed is None:
        return
    env_interp = get_interpretation()
    if str(passed).upper() != env_interp:
        raise RuntimeError(
            f"matched-pair violation: explicit interpretation "
            f"{str(passed).upper()!r} disagrees with "
            f"HAFISCAL_INTERPRETATION={env_interp!r}"
            + (f" (context: {context})" if context else "")
        )


def suffix_path(path):
    """Append '_<INTERPRETATION>' before '.txt' suffix.

    Parameters
    ----------
    path : str
        File path ending in '.txt'.

    Returns
    -------
    str: '<basename>_<INTERPRETATION>.txt'.

    Raises
    ------
    ValueError if path does not end in '.txt' (defensive — current convention
    only applies to .txt files).
    """
    if not path.endswith('.txt'):
        raise ValueError(
            f"suffix_path expects a .txt path, got: {path!r}"
        )
    interp = get_interpretation()
    return path[:-4] + f'_{interp}.txt'


def _prefer_candidate(path):
    """QE-baseline freeze: prefer the `_candidate` sibling when it exists.

    Pipeline runs write intermediates as `<base>_candidate.txt`
    (FromPandemicCode/generated_output.py), so readers must pick those up
    for regenerated results to flow downstream. Under HAFISCAL_PROMOTE=1
    the canonical (frozen) file is read instead. The '_candidate' suffix
    constant mirrors generated_output.CANDIDATE_SUFFIX.
    """
    if os.environ.get('HAFISCAL_PROMOTE') == '1':
        return path
    root, ext = os.path.splitext(path)
    cand = root + '_candidate' + ext
    return cand if os.path.exists(cand) else path


def resolve_path(path):
    """Return suffixed path if it exists; else fall back to un-suffixed.

    Used by reader sites to support backward-compat with legacy un-suffixed
    files while preferring the suffixed variant when it exists.
    Each variant is candidate-aware (see _prefer_candidate): a fresh
    `_candidate` sibling from the current pipeline run wins over the frozen
    canonical file.

    Parameters
    ----------
    path : str
        File path ending in '.txt'.

    Returns
    -------
    str: suffixed path if it exists, else `path` unchanged (each preferring
    its `_candidate` sibling when present).
    """
    suffixed = suffix_path(path)
    cand = _prefer_candidate(suffixed)
    if cand != suffixed:
        return cand
    if os.path.exists(suffixed):
        return suffixed
    # HAZARD GUARD (added 2026-06-04): under ESC, silently falling back to the
    # un-suffixed default loads the CDC/legacy calibration (e.g.
    # DiscFacEstim_CRRA_2.0_R_1.01.txt holds CDC betas). An ESC run reading CDC
    # discount factors is WRONG and silently shifted the recession+AD Check
    # multiplier ~+4% (1.32 -> 1.37) for ESC runs done before the aggregate
    # _ESC.txt was synced. Warn loudly so this cannot recur unnoticed.
    if get_interpretation() == 'ESC':
        import warnings
        warnings.warn(
            f"[ESC calibration HAZARD] expected ESC file "
            f"'{os.path.basename(suffixed)}' not found; falling back to the "
            f"NON-ESC (CDC/legacy) file '{os.path.basename(path)}'. An ESC run "
            f"reading CDC discount factors is WRONG (can shift multipliers ~4%). "
            f"Regenerate the _ESC file or set HAFISCAL_DISCFAC_FILE explicitly.",
            stacklevel=2)
    return _prefer_candidate(path)


def interp_suffix():
    """Return '_<INTERP>' for ESC; empty string for CDC.

    Use this at WRITE sites that want CDC to remain unsuffixed (matching
    the legacy filenames the rest of the codebase already references) while
    tagging ESC outputs with a distinct `_ESC` suffix.

    This is the registry mechanism for cross-interpretation isolation: ESC
    writes a separate file from CDC, so warm-start, comparison, and reads
    get the right artifact for their interpretation.

    Returns
    -------
    str: '_ESC' if HAFISCAL_INTERPRETATION=ESC; '' otherwise.

    Examples
    --------
    >>> # CDC (default):
    >>> 'DiscFacEstim_CRRA_2.0_R_1.01' + interp_suffix() + '.txt'
    'DiscFacEstim_CRRA_2.0_R_1.01.txt'
    >>> # ESC (HAFISCAL_INTERPRETATION=ESC):
    >>> 'DiscFacEstim_CRRA_2.0_R_1.01' + interp_suffix() + '.txt'
    'DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt'
    """
    interp = get_interpretation()
    return '_ESC' if interp == 'ESC' else ''
