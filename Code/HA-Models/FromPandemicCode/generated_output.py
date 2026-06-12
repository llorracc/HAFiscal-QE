"""Candidate-suffix routing for generated result files (tables + figures).

Part of the QE-baseline freeze (plans/20260611_qe-baseline-freeze-and-candidate-lock_plan.md):
the canonical ("frozen") result files in the repo hold the QE-published numbers
and are protected by LOCKED_TABLES.manifest + the pre-commit hook. A normal
pipeline run must therefore never write a canonical path directly; instead it
writes a gitignored `_candidate` sibling (e.g. `welfare6_candidate.tex`).

The ONLY way to change a canonical file is the deliberate promote step
(`promote_candidates.py`, run under HAFISCAL_PROMOTE=1 / HAFISCAL_UNLOCK=1).

Usage (tables):
    from generated_output import open_generated
    with open_generated(table_dir + 'welfare6.tex') as f:   # writes welfare6_candidate.tex
        f.write(output)

Usage (figures saved through HARK's make_figs):
    from generated_output import make_figs_generated
    make_figs_generated('IMPCs_both', True, False, target_dir=figs_dir)
    # -> IMPCs_both_candidate.{pdf,png,jpg,svg}

Usage (direct matplotlib savefig):
    from generated_output import output_path
    plt.savefig(output_path(os.path.join(fig_dir, 'HANK_tax_IRF.pdf')))
"""

import os

CANDIDATE_SUFFIX = "_candidate"


def is_promote():
    """True only during the deliberate promote step (writes canonical paths)."""
    return os.environ.get("HAFISCAL_PROMOTE") == "1"


def candidate_path(canonical_path):
    """Insert the candidate suffix before the extension.

    'Tables/CRRA2/welfare6.tex' -> 'Tables/CRRA2/welfare6_candidate.tex'
    """
    root, ext = os.path.splitext(str(canonical_path))
    return root + CANDIDATE_SUFFIX + ext


def candidate_name(canonical_name):
    """Suffix a bare (extension-less) figure basename for make_figs."""
    return str(canonical_name) + CANDIDATE_SUFFIX


def output_path(canonical_path):
    """The path a generator should actually write: candidate sibling,
    or the canonical path itself under HAFISCAL_PROMOTE=1."""
    canonical_path = str(canonical_path)
    return canonical_path if is_promote() else candidate_path(canonical_path)


def output_name(canonical_name):
    """make_figs counterpart of output_path (operates on basenames)."""
    canonical_name = str(canonical_name)
    return canonical_name if is_promote() else candidate_name(canonical_name)


def input_path(canonical_path):
    """Read-side counterpart of output_path for INTERMEDIATE result files
    (e.g. Results/AllResults_*.txt): prefer the `_candidate` sibling when it
    exists, so a pipeline run consumes the intermediates it just produced;
    fall back to the canonical (frozen) file otherwise. Under
    HAFISCAL_PROMOTE=1 always reads the canonical path."""
    canonical_path = str(canonical_path)
    if is_promote():
        return canonical_path
    cand = candidate_path(canonical_path)
    return cand if os.path.exists(cand) else canonical_path


def open_generated(canonical_path, mode="w", **kwargs):
    """Drop-in replacement for open(canonical_path, 'w'): opens the routed path."""
    path = output_path(canonical_path)
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    return open(path, mode, **kwargs)


def write_generated(canonical_path, content):
    """Write content to the routed path; returns the path written."""
    path = output_path(canonical_path)
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return path


def save_generated_figure(canonical_path, fig=None, **savefig_kwargs):
    """savefig to the routed path. `fig` may be a Figure or pyplot module;
    defaults to the current pyplot state. Returns the path written."""
    path = output_path(canonical_path)
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    if fig is None:
        import matplotlib.pyplot as plt
        fig = plt
    fig.savefig(path, **savefig_kwargs)
    return path


def make_figs_generated(figure_name, saveFigs, drawFigs, target_dir):
    """Candidate-routing wrapper around HARK.utilities.make_figs
    (which writes <name>.{pdf,png,jpg,svg} into target_dir)."""
    from HARK.utilities import make_figs
    make_figs(output_name(figure_name), saveFigs, drawFigs, target_dir=target_dir)
