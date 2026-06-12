"""Cascade-gate Tier (c): full population (3 cohorts × 7 β each), Baseline."""
import sys
sys.argv = ['harmenberg_doob_tier_c']
from harmenberg_doob_tier1 import main
if __name__ == "__main__":
    main(parametrization='Baseline', edTypes=(0, 1, 2), N_MC=200_000)
