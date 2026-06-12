"""Tier 1 (b) — same production calibration but interpretation='ESC'.

OUTCOME (2026-06-05, BUG-051 investigation): Doob was NOT adopted."""
import os
import sys
sys.argv = ['harmenberg_doob_tier1_esc']
# BUG-051 matched-pair: this ESC-only driver passes interpretation='ESC' down to
# build_tm_agg_fiscal_a, whose guard asserts the explicit value matches
# HAFISCAL_INTERPRETATION. Set ESC here so the env agrees with the kernel.
os.environ.setdefault('HAFISCAL_INTERPRETATION', 'ESC')
from harmenberg_doob_tier1 import main
if __name__ == "__main__":
    main(parametrization='Reduced_Run', edTypes=(0, 1, 2), N_MC=200_000,
         interpretation='ESC')
