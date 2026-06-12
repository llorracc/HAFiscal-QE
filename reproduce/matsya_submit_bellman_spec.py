#!/usr/bin/env python3
"""
Submit the focused HAFiscal household-Bellman spec to matsya, ONCE, into the
HAFiscal session. After this turn the spec lives in matsya's session memory and
all follow-up turns can be short and focused (a single question per turn) without
re-pasting the spec.

Per the matsya README:
  - "Don't paste in whole papers or large blocks of code." -- a focused
    pre-digested spec like this one is the right intermediate artifact.
  - For long excerpts, prefer the Python API over the CLI.
  - Use --session to maintain context across turns.

Usage:
    python reproduce/matsya_submit_bellman_spec.py

Requires:
    - matsya installed (pip install git+https://github.com/econ-ark/matsya.git)
    - MATSYA_TOKEN configured (matsya configure, or env var)
"""

from pathlib import Path
from matsya import ask

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "HAFiscal-bellman-for-matsya.md"
SESSION = "HAFiscal-Latest"

DIRECTIVE = """\
This message contains the focused mathematical specification of the household
Bellman problem in HAFiscal (Carroll, Crawley, Frankovic, Tretvoll). I am
giving it to you ONCE at the start of this session. All my subsequent turns
in this session will refer back to this spec without re-pasting it.

Your task on THIS turn is ONLY to:

1. Read the spec carefully.
2. Confirm what you have parsed: list the state variable(s), the control,
   the exogenous shocks, the discrete Markov state, the constraint(s), the
   per-period payoff, the effective discount, and the state transition --
   in modular-DDSL notation (perch notation, not YAML yet).
3. Flag any ambiguities, internal inconsistencies, or missing information
   that would block construction of a dolo-plus YAML.
4. Identify which features (if any) do not map cleanly onto current
   Bellman-DDSL syntax and will require workarounds when we eventually
   write the YAML.

Do NOT produce a YAML on this turn. Do NOT critique the economics. Do NOT
expand into welfare, fiscal multipliers, HANK, or aggregate demand -- those
are deliberately out of scope. Stay strictly within the household stage.

The spec follows below the line.

================================================================
"""


def main() -> None:
    spec = SPEC_PATH.read_text()
    prompt = DIRECTIVE + spec
    print(f"Submitting {len(spec)} chars of spec to matsya session '{SESSION}'...")
    response = ask(prompt, session=SESSION)
    print("\n" + "=" * 72 + "\nMATSYA RESPONSE\n" + "=" * 72 + "\n")
    print(response)


if __name__ == "__main__":
    main()
